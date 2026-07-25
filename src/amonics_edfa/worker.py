"""Background serial worker, so the GUI thread never blocks on instrument I/O.

The worker owns the :class:`~amonics_edfa.driver.AEDFA` instance and lives in its
own ``QThread``. The GUI talks to it exclusively through queued signal/slot
connections, and telemetry is pushed back to the GUI on a timer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from .driver import AEDFA, ChannelStatus
from .exceptions import AEDFAError

log = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_MS = 1000


@dataclass(frozen=True)
class Capabilities:
    """What the connected amplifier supports, discovered when the port opens."""

    port: str
    modes: list[str]
    n_driving_channels: int
    n_current_channels: int
    n_power_in_channels: int
    n_power_out_channels: int
    n_box_temp_channels: int


@dataclass(frozen=True)
class Limits:
    """Setpoint limits for the channel/mode currently selected."""

    mode: str
    min_value: float
    max_value: float
    step: float
    setpoint: float | None


@dataclass(frozen=True)
class Telemetry:
    """One poll of the amplifier. ``None`` means "not supported or unreadable"."""

    channel: int
    mode: str | None = None
    status: ChannelStatus | None = None
    master: ChannelStatus | None = None
    current_ma: float | None = None
    input_mw: float | None = None
    output_mw: float | None = None
    box_temp_c: float | None = None
    interlock: bool | None = None


class AmpWorker(QObject):
    """Serialises every driver call onto a single background thread."""

    connected = pyqtSignal(object)  # Capabilities
    disconnected = pyqtSignal()
    telemetry = pyqtSignal(object)  # Telemetry
    limits = pyqtSignal(object)  # Limits
    command_failed = pyqtSignal(str, str)  # title, message
    poll_failed = pyqtSignal(str)
    busy = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._amp: AEDFA | None = None
        self._timer: QTimer | None = None
        self._channel = 1
        self._interval_ms = DEFAULT_POLL_INTERVAL_MS

    # -- lifecycle ---------------------------------------------------------

    @pyqtSlot()
    def start(self) -> None:
        """Create the poll timer. Runs once, on the worker thread."""
        log.info("Worker started, poll interval %d ms", self._interval_ms)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._poll)

    @pyqtSlot()
    def stop(self) -> None:
        """Close the port and tear down. Runs on the worker thread at shutdown."""
        log.info("Worker stopping")
        if self._timer is not None:
            self._timer.stop()
        self._close_port()

    @pyqtSlot(str)
    def open_device(self, port: str) -> None:
        if self._amp is not None:
            log.debug("open_device(%s) ignored, already connected", port)
            return
        log.info("Connecting to %s", port)
        self.busy.emit(True)
        try:
            amp = AEDFA(port=port)
            amp.open()
        except (AEDFAError, OSError, ValueError) as exc:
            log.error("Connection to %s failed: %s", port, exc)
            self._amp = None
            self.command_failed.emit("Connection failed", str(exc))
            self.busy.emit(False)
            return
        self._amp = amp
        log.info("Connected to %s", port)
        self.busy.emit(False)
        self.connected.emit(
            Capabilities(
                port=port,
                modes=list(amp.modes),
                n_driving_channels=amp.n_driving_channels,
                n_current_channels=amp.n_current_channels,
                n_power_in_channels=amp.n_power_in_channels,
                n_power_out_channels=amp.n_power_out_channels,
                n_box_temp_channels=amp.n_box_temp_channels,
            )
        )
        self.refresh_limits()
        self._poll()

    @pyqtSlot()
    def close_device(self) -> None:
        log.info("Disconnecting")
        if self._timer is not None:
            self._timer.stop()
        self._close_port()
        self.disconnected.emit()

    def _close_port(self) -> None:
        if self._amp is None:
            return
        try:
            self._amp.close()
        except (AEDFAError, OSError) as exc:
            log.warning("Error while closing the port, ignoring: %s", exc)
        self._amp = None

    # -- configuration -----------------------------------------------------

    @pyqtSlot(int)
    def set_channel(self, channel: int) -> None:
        log.info("Selected channel %d", channel)
        self._channel = channel
        if self._amp is not None:
            self.refresh_limits()
            self._poll()

    @pyqtSlot(int)
    def set_poll_interval(self, interval_ms: int) -> None:
        log.info("Poll interval set to %d ms", interval_ms)
        self._interval_ms = interval_ms
        if self._timer is not None:
            self._timer.setInterval(interval_ms)

    # -- commands ----------------------------------------------------------

    @pyqtSlot(str)
    def set_mode(self, mode: str) -> None:
        log.info("Requesting mode %s on channel %d", mode, self._channel)

        def action(amp: AEDFA) -> None:
            amp.set_mode(mode, channel=self._channel)

        if self._run("Mode switch failed", action):
            self.refresh_limits()
            self._poll()

    @pyqtSlot(float)
    def set_setpoint(self, value: float) -> None:
        log.info("Requesting setpoint %g on channel %d", value, self._channel)

        def action(amp: AEDFA) -> None:
            amp.set_current_setpoint(channel=self._channel, value_ma=value)

        if self._run("Setpoint failed", action):
            self.refresh_limits()
            self._poll()

    @pyqtSlot(bool)
    def set_output(self, on: bool) -> None:
        log.info("Requesting output %s on channel %d", "ON" if on else "OFF", self._channel)

        def action(amp: AEDFA) -> None:
            if on:
                amp.set_channel_status(channel=self._channel, on=True)
                amp.master_enable()
            else:
                amp.master_disable()
                amp.set_channel_status(channel=self._channel, on=False)

        if self._run("Output control failed", action):
            self._poll()

    @pyqtSlot()
    def unlock_interlock(self) -> None:
        log.info("Requesting interlock unlock")
        if self._run("Interlock unlock failed", lambda amp: amp.unlock_interlock()):
            self._poll()

    @pyqtSlot()
    def refresh_limits(self) -> None:
        amp = self._amp
        if amp is None:
            return
        try:
            mode = amp.get_mode(channel=self._channel)
            bounds = amp.get_current_limits(channel=self._channel, mode=mode)
        except (AEDFAError, OSError, ValueError) as exc:
            log.warning("Could not read limits for channel %d: %s", self._channel, exc)
            self.poll_failed.emit(str(exc))
            return
        try:
            setpoint = amp.get_current_setpoint(channel=self._channel, mode=mode)
        except (AEDFAError, OSError, ValueError) as exc:
            log.warning("Could not read setpoint for channel %d: %s", self._channel, exc)
            setpoint = None
        log.debug(
            "Limits: mode=%s min=%g max=%g step=%g setpoint=%s",
            mode,
            bounds.min_ma,
            bounds.max_ma,
            bounds.step_ma,
            setpoint,
        )
        self.limits.emit(
            Limits(
                mode=mode,
                min_value=bounds.min_ma,
                max_value=bounds.max_ma,
                step=bounds.step_ma,
                setpoint=setpoint,
            )
        )

    def _run(self, title: str, action) -> bool:
        """Run a driver call, reporting failures to the GUI instead of raising."""
        amp = self._amp
        if amp is None:
            log.debug("%r skipped, not connected", title)
            return False
        if self._timer is not None:
            self._timer.stop()
        self.busy.emit(True)
        try:
            action(amp)
            return True
        except (AEDFAError, OSError, ValueError) as exc:
            log.error("%s: %s", title, exc)
            self.command_failed.emit(title, str(exc))
            return False
        finally:
            self.busy.emit(False)
            self._rearm()

    # -- polling -----------------------------------------------------------

    @pyqtSlot()
    def _poll(self) -> None:
        amp = self._amp
        if amp is None:
            return
        if self._timer is not None:
            self._timer.stop()

        channel = self._channel
        readings: dict[str, object] = {"channel": channel}
        errors: list[str] = []

        def read(name: str, fn) -> None:
            try:
                readings[name] = fn()
            except (AEDFAError, ValueError) as exc:
                log.debug("Reading %r failed: %s", name, exc)
                readings[name] = None
                errors.append(str(exc))

        try:
            read("mode", lambda: amp.get_mode(channel=channel))
            read("status", lambda: amp.get_channel_status(channel=channel))
            read("master", amp.is_master_enabled)
            read("current_ma", lambda: amp.get_current_ma(channel=channel))
            read("input_mw", lambda: amp.get_input_power_mw(channel=channel))
            read("output_mw", lambda: amp.get_output_power_mw(channel=channel))
            read("box_temp_c", amp.get_box_temp_degc)
            read("interlock", amp.get_interlock)
        except OSError as exc:  # the port went away underneath us
            log.error("Connection lost while polling: %s", exc)
            self.command_failed.emit("Connection lost", str(exc))
            self.close_device()
            return

        log.debug("Poll: %s", readings)
        self.telemetry.emit(Telemetry(**readings))  # type: ignore[arg-type]

        if errors:
            log.warning("Poll finished with %d error(s), first: %s", len(errors), errors[0])
            self.poll_failed.emit(errors[0])
        self._rearm()

    def _rearm(self) -> None:
        if self._amp is not None and self._timer is not None:
            self._timer.start(self._interval_ms)
