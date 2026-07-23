"""Driver for the Amonics AEDFA erbium-doped fibre amplifier."""

from __future__ import annotations

import time
from collections import namedtuple
from enum import IntEnum

import serial

from .exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError
from .protocol import build_query, build_set, parse_bool, parse_float, parse_int, parse_str

MIN_COMMAND_INTERVAL_S = 0.05

CurrentLimits = namedtuple("CurrentLimits", ["min_ma", "max_ma", "step_ma", "lo_margin_ma"])


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

    def _resolve_mode(self, channel: int, mode: str | None) -> str:
        resolved = mode if mode is not None else self.get_mode(channel)
        self._validate_mode(resolved)
        return resolved

    def get_modes(self) -> list[str]:
        """Return the laser control modes this device supports (e.g. ['ACC', 'APC'])."""
        return list(self.modes)

    def get_mode(self, channel: int = 1) -> str:
        """Get the current laser control mode of the specified channel."""
        return self._query_str(f"MODE:SW:CH{channel}")

    def set_mode(self, mode: str, channel: int = 1) -> None:
        """Switch the laser control mode of the specified channel."""
        self._validate_mode(mode)
        self._set_value(f"MODE:SW:CH{channel}", mode)

    def get_current_setpoint(self, channel: int, mode: str | None = None) -> float:
        """Get the driving current set-point (mA) of the specified channel."""
        self._validate_channel(channel, self.n_driving_channels, "driving")
        resolved_mode = self._resolve_mode(channel, mode)
        return self._query_float(f"DRIV:{resolved_mode}:CUR:CH{channel}")

    def set_current_setpoint(self, channel: int, value_ma: float, mode: str | None = None) -> None:
        """Set the driving current set-point (mA) of the specified channel."""
        self._validate_channel(channel, self.n_driving_channels, "driving")
        resolved_mode = self._resolve_mode(channel, mode)
        self._set_value(f"DRIV:{resolved_mode}:CUR:CH{channel}", value_ma)

    def get_current_limits(self, channel: int, mode: str | None = None) -> CurrentLimits:
        """Get the min/max/step/low-margin driving current (mA) of the specified channel."""
        self._validate_channel(channel, self.n_driving_channels, "driving")
        resolved_mode = self._resolve_mode(channel, mode)
        return CurrentLimits(
            min_ma=self._query_float(f"READ:DRIV:MIN:{resolved_mode}:CH{channel}"),
            max_ma=self._query_float(f"READ:DRIV:MAX:{resolved_mode}:CH{channel}"),
            step_ma=self._query_float(f"READ:DRIV:STEP:{resolved_mode}:CH{channel}"),
            lo_margin_ma=self._query_float(f"READ:DRIV:LO_MARGIN:{resolved_mode}:CH{channel}"),
        )

    def get_channel_status(self, channel: int, mode: str | None = None) -> ChannelStatus:
        """Get the driving status (OFF/ON/BUSY/LOCK) of the specified channel."""
        self._validate_channel(channel, self.n_driving_channels, "driving")
        resolved_mode = self._resolve_mode(channel, mode)
        return ChannelStatus(self._query_int(f"DRIV:{resolved_mode}:STAT:CH{channel}"))

    def set_channel_status(self, channel: int, on: bool, mode: str | None = None) -> None:
        """Turn the specified channel's driving on or off."""
        self._validate_channel(channel, self.n_driving_channels, "driving")
        resolved_mode = self._resolve_mode(channel, mode)
        self._set_value(f"DRIV:{resolved_mode}:STAT:CH{channel}", on)

    def master_enable(self) -> None:
        """Turn the master control switch on, enabling all configured lasers."""
        self._set_value("DRIV:MCTRL", True)

    def master_disable(self) -> None:
        """Turn the master control switch off, disabling all lasers."""
        self._set_value("DRIV:MCTRL", False)

    def is_master_enabled(self) -> ChannelStatus:
        """Get the master control switch status (OFF/ON/BUSY)."""
        return ChannelStatus(self._query_int("DRIV:MCTRL"))

    def get_current_ma(self, channel: int) -> float:
        """Get the existing current (mA) of the specified channel."""
        self._validate_channel(channel, self.n_current_channels, "current")
        return self._query_float(f"SENS:CUR:CH{channel}")

    def get_input_power_mw(self, channel: int) -> float:
        """Get the existing input power (mW) of the specified channel."""
        self._validate_channel(channel, self.n_power_in_channels, "input power")
        return self._query_float(f"SENS:POW:IN:CH{channel}")

    def get_output_power_mw(self, channel: int) -> float:
        """Get the existing output power (mW) of the specified channel."""
        self._validate_channel(channel, self.n_power_out_channels, "output power")
        return self._query_float(f"SENS:POW:OUT:CH{channel}")

    def get_pd_power_mw(self, channel: int) -> float:
        """Get the existing internal photodiode power (mW) of the specified channel."""
        self._validate_channel(channel, self.n_pd_channels, "photodiode")
        return self._query_float(f"SENS:POW:PD:CH{channel}")

    def get_box_temp_degc(self) -> float:
        """Get the existing case temperature (deg C)."""
        return self._query_float("SENS:TEMP:BOX")

    def get_fibre_chamber_temp_degc(self) -> float:
        """Get the existing fibre chamber temperature (deg C)."""
        return self._query_float("SENS:TEMP:FC")

    def get_tec_temp_degc(self, channel: int) -> float:
        """Get the existing pump TEC temperature (deg C) of the specified channel."""
        self._validate_channel(channel, self.n_tec_channels, "TEC")
        return self._query_float(f"SENS:TEMP:TEC:CH{channel}")

    def get_supply_voltage(self) -> float:
        """Get the existing power supply voltage (V)."""
        return self._query_float("SENS:VOLT:PS")

    def get_seed_stabilising(self) -> bool:
        """Check whether seed power is still stabilising (True) or stable (False)."""
        return self._query_bool("DRIV:SEED_ST")

    def get_interlock(self) -> bool:
        """Check whether the interlock is active (lasers locked)."""
        return self._query_bool("DRIV:INTERLOCK")

    def unlock_interlock(self) -> None:
        """Unlock lasers after an interlock event has cleared."""
        self._set_value("THRES:INTERLOCK:UNLOCK", True)
