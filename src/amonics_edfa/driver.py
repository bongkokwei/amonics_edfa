"""Driver for the Amonics AEDFA erbium-doped fibre amplifier."""

from __future__ import annotations

import time
from enum import IntEnum

import serial

from .exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError
from .protocol import build_query, build_set, parse_bool, parse_float, parse_int, parse_str

MIN_COMMAND_INTERVAL_S = 0.05


class ChannelStatus(IntEnum):
    """Driving/master-control status, per the programming manual."""

    OFF = 0
    ON = 1
    BUSY = 2
    LOCK = 4


class AEDFA:
    """Serial driver for a single Amonics AEDFA erbium-doped fibre amplifier."""

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 2.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: serial.Serial | None = None
        self._last_write_time: float = 0.0

        self.modes: list[str] = []
        self.n_driving_channels: int = 0
        self.n_current_channels: int = 0
        self.n_power_in_channels: int = 0
        self.n_power_out_channels: int = 0
        self.n_pd_channels: int = 0
        self.n_box_temp_channels: int = 0
        self.n_fibre_chamber_temp_channels: int = 0
        self.n_tec_channels: int = 0
        self.n_voltage_channels: int = 0

    def open(self) -> None:
        """Open the serial port and discover the device's channel/mode capabilities."""
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )
        self._discover_capabilities()

    def close(self) -> None:
        """Close the serial port, if open."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def __enter__(self) -> "AEDFA":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _discover_capabilities(self) -> None:
        self.modes = self._query_str("READ:MODE:NAMES").split()
        self.n_driving_channels = (
            self._query_int(f"READ:CH:DRIV:{self.modes[0]}") if self.modes else 0
        )
        self.n_current_channels = self._query_int("READ:CH:CUR")
        self.n_power_in_channels = self._query_int("READ:CH:POW:IN")
        self.n_power_out_channels = self._query_int("READ:CH:POW:OUT")
        self.n_pd_channels = self._query_int("READ:CH:POW:PD")
        self.n_box_temp_channels = self._query_int("READ:CH:TEMP:BOX")
        self.n_fibre_chamber_temp_channels = self._query_int("READ:CH:TEMP:FC")
        self.n_tec_channels = self._query_int("READ:CH:TEMP:TEC")
        self.n_voltage_channels = self._query_int("READ:CH:VOLT:PS")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_write_time
        if elapsed < MIN_COMMAND_INTERVAL_S:
            time.sleep(MIN_COMMAND_INTERVAL_S - elapsed)

    def _write(self, data: bytes) -> None:
        if self._serial is None:
            raise AEDFAError("Device is not open. Call open() first.")
        self._throttle()
        self._serial.write(data)
        self._last_write_time = time.monotonic()

    def _query_raw(self, path: str) -> str:
        self._write(build_query(path))
        raw = self._serial.readline()
        if not raw:
            raise AEDFATimeoutError(f"No reply to query ':{path}?'")
        return raw.decode("ascii")

    def _query_str(self, path: str) -> str:
        return parse_str(self._query_raw(path))

    def _query_float(self, path: str) -> float:
        return parse_float(self._query_raw(path))

    def _query_int(self, path: str) -> int:
        return parse_int(self._query_raw(path))

    def _query_bool(self, path: str) -> bool:
        return parse_bool(self._query_raw(path))

    def _set_value(self, path: str, value: bool | int | float | str) -> None:
        self._write(build_set(path, value))

    def _validate_channel(self, channel: int, count: int, label: str) -> None:
        if not (1 <= channel <= count):
            raise AEDFACommandError(
                f"{label} channel {channel} not available on this device (has {count})"
            )

    def _validate_mode(self, mode: str) -> None:
        if mode not in self.modes:
            raise AEDFACommandError(f"Mode {mode!r} not supported (available: {self.modes})")
