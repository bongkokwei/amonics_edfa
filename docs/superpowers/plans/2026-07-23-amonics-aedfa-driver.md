# Amonics AEDFA Python Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installable Python package (`amonics_edfa`) that drives an Amonics AEDFA erbium-doped fibre amplifier over its RS-232 SCPI-style command set.

**Architecture:** A single flat `AEDFA` driver class over `pyserial`, backed by a stateless `protocol` module for command framing/response parsing. Capabilities (channel counts, supported modes) are discovered once at `open()` and cached, so public methods can validate arguments before sending a command the device won't recognise.

**Tech Stack:** Python 3.11+, `pyserial`, `pytest` (mocked-serial unit tests + one `--hw`-gated hardware smoke test).

## Global Constraints

- Baud rate 19200bps, 8 data bits, no parity, 1 stop bit, no flow control (manual, "Configuration").
- Commands are ASCII, start with `:`, end with `\r\n` (manual, "SCPI Command").
- A minimum 50ms delay must be enforced between successive commands (manual, "Important Notes" #4).
- Python >=3.11; only dependency is `pyserial` (no `pyvisa` — there is no VISA/GPIB layer here).
- `src/` layout; public import is `from amonics_edfa import AEDFA, ChannelStatus, AEDFAError, AEDFATimeoutError, AEDFACommandError`.
- British spelling in identifiers/docstrings where it doesn't collide with the manual's own terms (`fibre_chamber`, not `fiber_chamber`).
- Not implemented (cut during spec review, see `docs/superpowers/specs/2026-07-23-amonics-aedfa-driver-design.md`): PLL status, `:SWAP:CH*` EDFA switching, HTTP/web commands.

---

### Task 1: Project scaffolding, exceptions, pytest config

**Files:**
- Create: `pyproject.toml`
- Create: `src/amonics_edfa/__init__.py`
- Create: `src/amonics_edfa/exceptions.py`
- Test: `tests/test_exceptions.py`

**Interfaces:**
- Produces: `AEDFAError`, `AEDFATimeoutError(AEDFAError)`, `AEDFACommandError(AEDFAError)` — imported by every later task.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "amonics-edfa"
version = "0.1.0"
description = "Python driver for Amonics AEDFA erbium-doped fibre amplifiers"
requires-python = ">=3.11"
dependencies = [
    "pyserial",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-mock"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
addopts = "-v"
markers = [
    "hw: requires a physical AEDFA connected over serial",
]
```

- [ ] **Step 2: Create the package skeleton**

`src/amonics_edfa/__init__.py`:

```python
"""Python driver for Amonics AEDFA erbium-doped fibre amplifiers."""
```

- [ ] **Step 3: Install in editable mode**

Run: `pip install -e ".[dev]" --break-system-packages`
Expected: installs successfully (no `amonics_edfa` submodules yet, but the package is importable).

- [ ] **Step 4: Write the failing test**

`tests/test_exceptions.py`:

```python
from amonics_edfa.exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError


def test_timeout_error_is_aedfa_error():
    assert issubclass(AEDFATimeoutError, AEDFAError)


def test_command_error_is_aedfa_error():
    assert issubclass(AEDFACommandError, AEDFAError)


def test_aedfa_error_is_exception():
    assert issubclass(AEDFAError, Exception)
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'amonics_edfa.exceptions'`

- [ ] **Step 6: Implement the exception hierarchy**

`src/amonics_edfa/exceptions.py`:

```python
"""Exception hierarchy for the Amonics AEDFA driver."""


class AEDFAError(Exception):
    """Base exception for all Amonics AEDFA driver errors."""


class AEDFATimeoutError(AEDFAError):
    """Raised when the device does not reply within the configured timeout."""


class AEDFACommandError(AEDFAError):
    """Raised when a command references a channel or mode the device does not support."""
```

- [ ] **Step 7: Export exceptions from the package**

`src/amonics_edfa/__init__.py`:

```python
"""Python driver for Amonics AEDFA erbium-doped fibre amplifiers."""

from .exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError

__all__ = [
    "AEDFAError",
    "AEDFATimeoutError",
    "AEDFACommandError",
]
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_exceptions.py -v`
Expected: PASS (3 passed)

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/amonics_edfa/__init__.py src/amonics_edfa/exceptions.py tests/test_exceptions.py
git commit -m "Add project scaffolding and exception hierarchy"
```

---

### Task 2: Protocol layer — command framing & response parsing

**Files:**
- Create: `src/amonics_edfa/protocol.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Consumes: nothing (pure functions, no I/O).
- Produces: `build_query(path: str) -> bytes`, `build_set(path: str, value: bool | int | float | str) -> bytes`, `parse_float(raw: str) -> float`, `parse_int(raw: str) -> int`, `parse_bool(raw: str) -> bool`, `parse_str(raw: str) -> str` — used by `driver.py` in Task 3 onward.

- [ ] **Step 1: Write the failing tests**

`tests/test_protocol.py`:

```python
from amonics_edfa.protocol import (
    build_query,
    build_set,
    parse_bool,
    parse_float,
    parse_int,
    parse_str,
)


def test_build_query_wraps_path_with_colon_and_question_mark():
    assert build_query("SENS:CUR:CH1") == b":SENS:CUR:CH1?\r\n"


def test_build_set_with_int_value():
    assert build_set("DRIV:ACC:CUR:CH1", 350) == b":DRIV:ACC:CUR:CH1 350\r\n"


def test_build_set_with_float_value():
    assert build_set("THRES:POW:IN:LEV:SET1", -15.0) == b":THRES:POW:IN:LEV:SET1 -15\r\n"


def test_build_set_with_bool_value():
    assert build_set("DRIV:ACC:STAT:CH1", True) == b":DRIV:ACC:STAT:CH1 1\r\n"


def test_build_set_with_string_value():
    assert build_set("MODE:SW:CH1", "ACC") == b":MODE:SW:CH1 ACC\r\n"


def test_parse_float_from_scientific_notation():
    assert parse_float("3.060000e+02\r\n") == 306.0


def test_parse_int():
    assert parse_int("2\r\n") == 2


def test_parse_bool_true():
    assert parse_bool("1\r\n") is True


def test_parse_bool_false():
    assert parse_bool("0\r\n") is False


def test_parse_str_strips_terminator():
    assert parse_str("ACC\r\n") == "ACC"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'amonics_edfa.protocol'`

- [ ] **Step 3: Implement the protocol module**

`src/amonics_edfa/protocol.py`:

```python
"""Command framing and response parsing for the Amonics AEDFA SCPI-style protocol."""

from __future__ import annotations


def _format_value(value: bool | int | float | str) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def build_query(path: str) -> bytes:
    """Build the wire bytes for a query, e.g. path='SENS:CUR:CH1' -> b':SENS:CUR:CH1?\\r\\n'."""
    return f":{path}?\r\n".encode("ascii")


def build_set(path: str, value: bool | int | float | str) -> bytes:
    """Build the wire bytes for a set command, e.g. path='DRIV:ACC:CUR:CH1', value=350
    -> b':DRIV:ACC:CUR:CH1 350\\r\\n'."""
    return f":{path} {_format_value(value)}\r\n".encode("ascii")


def parse_float(raw: str) -> float:
    """Parse a decimal or scientific-notation response, e.g. '3.060000e+02\\r\\n' -> 306.0."""
    return float(raw.strip())


def parse_int(raw: str) -> int:
    """Parse a base-10 integer response, e.g. '2\\r\\n' -> 2."""
    return int(raw.strip())


def parse_bool(raw: str) -> bool:
    """Parse a 0/1 flag response, e.g. '1\\r\\n' -> True."""
    return raw.strip() == "1"


def parse_str(raw: str) -> str:
    """Parse an ASCII string response, stripping the trailing terminator, e.g. 'ACC\\r\\n' -> 'ACC'."""
    return raw.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_protocol.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/protocol.py tests/test_protocol.py
git commit -m "Add SCPI command framing and response parsing helpers"
```

---

### Task 3: Driver core — connection, capability discovery, typed I/O helpers

**Files:**
- Create: `src/amonics_edfa/driver.py`
- Create: `tests/conftest.py`
- Create: `tests/test_driver.py`
- Modify: `src/amonics_edfa/__init__.py`

**Interfaces:**
- Consumes: `build_query`, `build_set`, `parse_float`, `parse_int`, `parse_bool`, `parse_str` (Task 2); `AEDFAError`, `AEDFATimeoutError`, `AEDFACommandError` (Task 1).
- Produces: `ChannelStatus(IntEnum)` with `OFF=0, ON=1, BUSY=2, LOCK=4`; `AEDFA.__init__(port, baudrate=19200, timeout=2.0)`; `open()`/`close()`/context manager; cached capability attributes `self.modes: list[str]`, `self.n_driving_channels`, `self.n_current_channels`, `self.n_power_in_channels`, `self.n_power_out_channels`, `self.n_pd_channels`, `self.n_box_temp_channels`, `self.n_fibre_chamber_temp_channels`, `self.n_tec_channels`, `self.n_voltage_channels` (all `int`); protected helpers `_query_str/_query_float/_query_int/_query_bool(path) -> value`, `_set_value(path, value)`, `_validate_channel(channel, count, label)`, `_validate_mode(mode)` — all consumed by Tasks 4–8. Test fixtures `mock_serial` and `opened_device`, consumed by Tasks 4–8's tests.

- [ ] **Step 1: Write the failing tests and shared fixtures**

`tests/conftest.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from amonics_edfa import AEDFA

DISCOVERY_RESPONSES = [
    b"ACC\r\n",
    b"2\r\n",
    b"2\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"2\r\n",
    b"1\r\n",
]


def pytest_addoption(parser):
    parser.addoption(
        "--hw",
        action="store_true",
        default=False,
        help="run tests marked 'hw' against real hardware",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--hw"):
        return
    skip_hw = pytest.mark.skip(reason="requires physical AEDFA; run with --hw")
    for item in items:
        if "hw" in item.keywords:
            item.add_marker(skip_hw)


@pytest.fixture
def mock_serial():
    """Patch amonics_edfa.driver.serial.Serial; readline is pre-loaded with capability
    discovery responses matching a single-mode, single-channel-input, dual-current device."""
    with patch("amonics_edfa.driver.serial.Serial") as mock_serial_cls:
        instance = MagicMock()
        instance.readline.side_effect = list(DISCOVERY_RESPONSES)
        mock_serial_cls.return_value = instance
        yield instance


@pytest.fixture
def opened_device(mock_serial):
    """An AEDFA already open()'d against the mocked serial port."""
    device = AEDFA(port="COM8")
    device.open()
    return device
```

`tests/test_driver.py`:

```python
import pytest

from amonics_edfa import AEDFA
from amonics_edfa.exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError


def test_open_discovers_capabilities(opened_device):
    assert opened_device.modes == ["ACC"]
    assert opened_device.n_driving_channels == 2
    assert opened_device.n_current_channels == 2
    assert opened_device.n_power_in_channels == 1
    assert opened_device.n_power_out_channels == 1
    assert opened_device.n_pd_channels == 1
    assert opened_device.n_box_temp_channels == 1
    assert opened_device.n_fibre_chamber_temp_channels == 1
    assert opened_device.n_tec_channels == 2
    assert opened_device.n_voltage_channels == 1


def test_open_sends_expected_discovery_queries(mock_serial):
    device = AEDFA(port="COM8")
    device.open()
    written = [c.args[0] for c in mock_serial.write.call_args_list]
    assert written == [
        b":READ:MODE:NAMES?\r\n",
        b":READ:CH:DRIV:ACC?\r\n",
        b":READ:CH:CUR?\r\n",
        b":READ:CH:POW:IN?\r\n",
        b":READ:CH:POW:OUT?\r\n",
        b":READ:CH:POW:PD?\r\n",
        b":READ:CH:TEMP:BOX?\r\n",
        b":READ:CH:TEMP:FC?\r\n",
        b":READ:CH:TEMP:TEC?\r\n",
        b":READ:CH:VOLT:PS?\r\n",
    ]


def test_context_manager_closes_serial(mock_serial):
    with AEDFA(port="COM8"):
        pass
    mock_serial.close.assert_called_once()


def test_query_before_open_raises():
    device = AEDFA(port="COM8")
    with pytest.raises(AEDFAError):
        device._query_str("READ:MODE:NAMES")


def test_query_timeout_raises_when_no_reply(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b""]
    with pytest.raises(AEDFATimeoutError):
        opened_device._query_float("SENS:CUR:CH1")


def test_validate_channel_raises_for_out_of_range(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device._validate_channel(5, opened_device.n_current_channels, "current")


def test_validate_mode_raises_for_unsupported_mode(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device._validate_mode("APC")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'amonics_edfa.driver'`

- [ ] **Step 3: Implement the driver core**

`src/amonics_edfa/driver.py`:

```python
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
```

- [ ] **Step 4: Export `AEDFA` and `ChannelStatus`**

`src/amonics_edfa/__init__.py`:

```python
"""Python driver for Amonics AEDFA erbium-doped fibre amplifiers."""

from .driver import AEDFA, ChannelStatus
from .exceptions import AEDFACommandError, AEDFAError, AEDFATimeoutError

__all__ = [
    "AEDFA",
    "ChannelStatus",
    "AEDFAError",
    "AEDFATimeoutError",
    "AEDFACommandError",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add src/amonics_edfa/driver.py src/amonics_edfa/__init__.py tests/conftest.py tests/test_driver.py
git commit -m "Add AEDFA driver core: connection, capability discovery, typed I/O helpers"
```

---

### Task 4: Mode & set-point methods

**Files:**
- Modify: `src/amonics_edfa/driver.py`
- Modify: `tests/test_driver.py`

**Interfaces:**
- Consumes: `_query_str/_query_float/_query_int`, `_set_value`, `_validate_channel`, `_validate_mode`, `ChannelStatus` (Task 3).
- Produces: `CurrentLimits` namedtuple (`min_ma, max_ma, step_ma, lo_margin_ma`); `get_modes()`, `get_mode(channel=1)`, `set_mode(mode, channel=1)`, `get_current_setpoint(channel, mode=None)`, `set_current_setpoint(channel, value_ma, mode=None)`, `get_current_limits(channel, mode=None) -> CurrentLimits`, `get_channel_status(channel, mode=None) -> ChannelStatus`, `set_channel_status(channel, on, mode=None)`, `master_enable()`, `master_disable()`, `is_master_enabled() -> ChannelStatus`, and the protected helper `_resolve_mode(channel, mode) -> str` (used by Task 4 methods only).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
from unittest.mock import call


def test_get_modes_returns_cached_list(opened_device):
    assert opened_device.get_modes() == ["ACC"]


def test_get_mode_queries_device(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"ACC\r\n"]
    assert opened_device.get_mode(channel=1) == "ACC"
    mock_serial.write.assert_called_with(b":MODE:SW:CH1?\r\n")


def test_set_mode_sends_expected_command(opened_device, mock_serial):
    opened_device.set_mode("ACC", channel=1)
    mock_serial.write.assert_called_with(b":MODE:SW:CH1 ACC\r\n")


def test_set_mode_rejects_unsupported_mode(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device.set_mode("APC", channel=1)


def test_get_current_setpoint_uses_current_mode(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"ACC\r\n", b"3.500000e+02\r\n"]
    assert opened_device.get_current_setpoint(channel=1) == 350.0
    assert mock_serial.write.call_args_list[-1] == call(b":DRIV:ACC:CUR:CH1?\r\n")


def test_set_current_setpoint_sends_expected_command(opened_device, mock_serial):
    opened_device.set_current_setpoint(channel=1, value_ma=350, mode="ACC")
    mock_serial.write.assert_called_with(b":DRIV:ACC:CUR:CH1 350\r\n")


def test_set_current_setpoint_rejects_out_of_range_channel(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device.set_current_setpoint(channel=9, value_ma=100, mode="ACC")


def test_get_current_limits_returns_named_tuple(opened_device, mock_serial):
    mock_serial.readline.side_effect = [
        b"0.000000e+00\r\n",
        b"4.000000e+02\r\n",
        b"1.000000e+00\r\n",
        b"1.000000e+02\r\n",
    ]
    limits = opened_device.get_current_limits(channel=1, mode="ACC")
    assert limits.min_ma == 0.0
    assert limits.max_ma == 400.0
    assert limits.step_ma == 1.0
    assert limits.lo_margin_ma == 100.0


def test_get_channel_status_returns_enum(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_channel_status(channel=1, mode="ACC") == ChannelStatus.ON


def test_set_channel_status_sends_expected_command(opened_device, mock_serial):
    opened_device.set_channel_status(channel=1, on=True, mode="ACC")
    mock_serial.write.assert_called_with(b":DRIV:ACC:STAT:CH1 1\r\n")


def test_master_enable_sends_expected_command(opened_device, mock_serial):
    opened_device.master_enable()
    mock_serial.write.assert_called_with(b":DRIV:MCTRL 1\r\n")


def test_master_disable_sends_expected_command(opened_device, mock_serial):
    opened_device.master_disable()
    mock_serial.write.assert_called_with(b":DRIV:MCTRL 0\r\n")


def test_is_master_enabled_returns_enum(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.is_master_enabled() == ChannelStatus.ON
```

Add `ChannelStatus` to the existing import line at the top of the file:

```python
from amonics_edfa import AEDFA, ChannelStatus
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL — `AttributeError: 'AEDFA' object has no attribute 'get_modes'` (and similar for the other new methods)

- [ ] **Step 3: Implement mode & set-point methods**

Append to the `AEDFA` class in `src/amonics_edfa/driver.py` (and add the `namedtuple` import at the top: `from collections import namedtuple`):

```python
CurrentLimits = namedtuple("CurrentLimits", ["min_ma", "max_ma", "step_ma", "lo_margin_ma"])
```

(module level, above the `ChannelStatus` class)

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (19 passed)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/driver.py tests/test_driver.py
git commit -m "Add mode switching and set-point control methods"
```

---

### Task 5: Sensor methods

**Files:**
- Modify: `src/amonics_edfa/driver.py`
- Modify: `tests/test_driver.py`

**Interfaces:**
- Consumes: `_query_float/_query_bool`, `_set_value`, `_validate_channel` (Task 3).
- Produces: `get_current_ma`, `get_input_power_mw`, `get_output_power_mw`, `get_pd_power_mw`, `get_box_temp_degc`, `get_fibre_chamber_temp_degc`, `get_tec_temp_degc`, `get_supply_voltage`, `get_seed_stabilising`, `get_interlock`, `unlock_interlock`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
@pytest.mark.parametrize(
    "method_name, args, expected_query, response, expected_value",
    [
        ("get_current_ma", (1,), b":SENS:CUR:CH1?\r\n", b"7.180000e+02\r\n", 718.0),
        ("get_input_power_mw", (1,), b":SENS:POW:IN:CH1?\r\n", b"9.010000e+02\r\n", 901.0),
        ("get_output_power_mw", (1,), b":SENS:POW:OUT:CH1?\r\n", b"3.060000e+02\r\n", 306.0),
        ("get_pd_power_mw", (1,), b":SENS:POW:PD:CH1?\r\n", b"9.010000e+02\r\n", 901.0),
        ("get_box_temp_degc", (), b":SENS:TEMP:BOX?\r\n", b"3.131733e+01\r\n", 31.31733),
        ("get_fibre_chamber_temp_degc", (), b":SENS:TEMP:FC?\r\n", b"3.131733e+01\r\n", 31.31733),
        ("get_tec_temp_degc", (1,), b":SENS:TEMP:TEC:CH1?\r\n", b"2.417492e+01\r\n", 24.17492),
        ("get_supply_voltage", (), b":SENS:VOLT:PS?\r\n", b"5.217492e+00\r\n", 5.217492),
    ],
)
def test_sensor_getters_query_and_parse_correctly(
    opened_device, mock_serial, method_name, args, expected_query, response, expected_value
):
    mock_serial.readline.side_effect = [response]
    method = getattr(opened_device, method_name)
    assert method(*args) == pytest.approx(expected_value)
    mock_serial.write.assert_called_with(expected_query)


def test_get_seed_stabilising_true(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_seed_stabilising() is True


def test_get_interlock_true(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_interlock() is True


def test_unlock_interlock_sends_expected_command(opened_device, mock_serial):
    opened_device.unlock_interlock()
    mock_serial.write.assert_called_with(b":THRES:INTERLOCK:UNLOCK 1\r\n")


def test_get_current_ma_rejects_out_of_range_channel(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device.get_current_ma(channel=9)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL — `AttributeError: 'AEDFA' object has no attribute 'get_current_ma'` (and similar)

- [ ] **Step 3: Implement sensor methods**

Append to the `AEDFA` class in `src/amonics_edfa/driver.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (32 passed)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/driver.py tests/test_driver.py
git commit -m "Add sensor read methods (current, power, temperature, voltage, interlock)"
```

---

### Task 6: Alarm read methods

**Files:**
- Modify: `src/amonics_edfa/driver.py`
- Modify: `tests/test_driver.py`

**Interfaces:**
- Consumes: `_query_bool/_query_int`, `_validate_channel` (Task 3).
- Produces: `get_alarm_input_loss(channel, latched=False)`, `get_alarm_input_over(channel, latched=False)`, `get_alarm_current_over(latched=False)`, `get_alarm_box_temp(latched=False)`, `get_alarm_fibre_chamber()`, `get_alarm_tec_warn(latched=False)`, `get_alarm_tec_over(latched=False)`, `get_alarm_supply_voltage(latched=False)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
@pytest.mark.parametrize(
    "method_name, args, base_path",
    [
        ("get_alarm_input_loss", (1,), "SENS:THRES:ALARM:POW:IN:LOS:CH1"),
        ("get_alarm_input_over", (1,), "SENS:THRES:ALARM:POW:IN:OVER:CH1"),
        ("get_alarm_current_over", (), "SENS:THRES:ALARM:CUR:OVER"),
        ("get_alarm_box_temp", (), "SENS:THRES:ALARM:TEMP:BOX"),
        ("get_alarm_tec_warn", (), "SENS:THRES:ALARM:TEMP:TEC:WARN"),
        ("get_alarm_supply_voltage", (), "SENS:THRES:ALARM:VOLT:PS"),
    ],
)
@pytest.mark.parametrize("latched", [False, True])
def test_latched_alarm_getters_query_expected_path(
    opened_device, mock_serial, method_name, args, base_path, latched
):
    mock_serial.readline.side_effect = [b"1\r\n"]
    method = getattr(opened_device, method_name)
    assert method(*args, latched=latched) is True
    expected_path = base_path + (":LATCH" if latched else "")
    mock_serial.write.assert_called_with(f":{expected_path}?\r\n".encode("ascii"))


def test_get_alarm_fibre_chamber_returns_int(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_alarm_fibre_chamber() == 1
    mock_serial.write.assert_called_with(b":SENS:THRES:ALARM:TEMP:FC?\r\n")


def test_get_alarm_tec_over_returns_int(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_alarm_tec_over() == 1
    mock_serial.write.assert_called_with(b":SENS:THRES:ALARM:TEMP:TEC:OVER?\r\n")


def test_get_alarm_input_loss_rejects_out_of_range_channel(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device.get_alarm_input_loss(channel=9)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL — `AttributeError: 'AEDFA' object has no attribute 'get_alarm_input_loss'` (and similar)

- [ ] **Step 3: Implement alarm read methods**

Append to the `AEDFA` class in `src/amonics_edfa/driver.py`:

```python
    def get_alarm_input_loss(self, channel: int, latched: bool = False) -> bool:
        """Get the loss-of-input-power alarm flag for the specified channel."""
        self._validate_channel(channel, self.n_power_in_channels, "input power")
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:POW:IN:LOS:CH{channel}{suffix}")

    def get_alarm_input_over(self, channel: int, latched: bool = False) -> bool:
        """Get the over-input-power alarm flag for the specified channel."""
        self._validate_channel(channel, self.n_power_in_channels, "input power")
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:POW:IN:OVER:CH{channel}{suffix}")

    def get_alarm_current_over(self, latched: bool = False) -> bool:
        """Get the over-current alarm flag."""
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:CUR:OVER{suffix}")

    def get_alarm_box_temp(self, latched: bool = False) -> bool:
        """Get the case-temperature alarm flag."""
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:TEMP:BOX{suffix}")

    def get_alarm_fibre_chamber(self) -> int:
        """Get the fibre chamber alarm flag (0=READY, 1=FAIL, 2=OFF)."""
        return self._query_int("SENS:THRES:ALARM:TEMP:FC")

    def get_alarm_tec_warn(self, latched: bool = False) -> bool:
        """Get the TEC warning alarm flag."""
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:TEMP:TEC:WARN{suffix}")

    def get_alarm_tec_over(self, latched: bool = False) -> int:
        """Get the TEC overheat alarm flag (0=off, >0=alarm on for that channel)."""
        suffix = ":LATCH" if latched else ""
        return self._query_int(f"SENS:THRES:ALARM:TEMP:TEC:OVER{suffix}")

    def get_alarm_supply_voltage(self, latched: bool = False) -> bool:
        """Get the power supply voltage alarm flag."""
        suffix = ":LATCH" if latched else ""
        return self._query_bool(f"SENS:THRES:ALARM:VOLT:PS{suffix}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (49 passed)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/driver.py tests/test_driver.py
git commit -m "Add alarm read methods"
```

---

### Task 7: Alarm configuration methods

**Files:**
- Modify: `src/amonics_edfa/driver.py`
- Modify: `tests/test_driver.py`

**Interfaces:**
- Consumes: `_query_bool/_query_float`, `_set_value`, `_validate_channel` (Task 3).
- Produces (getter/setter pairs unless noted read-only): `get_ipd_active(channel)` (read-only), `get_ipd_enabled`/`set_ipd_enabled`, `get_ipd_level_dbm`/`set_ipd_level_dbm`, `get_opd_enabled`/`set_opd_enabled`, `get_opd_range_pct`/`set_opd_range_pct`, `get_opd_range_min_pct`/`set_opd_range_min_pct`, `get_opd_range_max_pct`/`set_opd_range_max_pct`, `get_opd_reference_mw` (read-only), `get_opd_autostart_time_s`/`set_opd_autostart_time_s`, `get_current_alarm_enabled`/`set_current_alarm_enabled`, `get_current_alarm_level_ma`/`set_current_alarm_level_ma`, `get_obr_alarm_enabled`/`set_obr_alarm_enabled`, `get_obr_alarm_level_dbm`/`set_obr_alarm_level_dbm`, `get_box_temp_alarm_enabled`/`set_box_temp_alarm_enabled`, `get_box_temp_min_degc`/`set_box_temp_min_degc`, `get_box_temp_max_degc`/`set_box_temp_max_degc`, `get_fibre_chamber_alarm_enabled`/`set_fibre_chamber_alarm_enabled`, `get_fibre_chamber_max_degc`/`set_fibre_chamber_max_degc`, `can_unlock_tec_overheat`/`unlock_tec_overheat`, `get_voltage_alarm_enabled`/`set_voltage_alarm_enabled`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
BOOL_CONFIG_PAIRS = [
    ("get_ipd_enabled", "set_ipd_enabled", "THRES:POW:IN:STAT:SET1"),
    ("get_opd_enabled", "set_opd_enabled", "THRES:POW:OUT:STAT:SET1"),
    ("get_current_alarm_enabled", "set_current_alarm_enabled", "THRES:CUR:OVER:STAT"),
    ("get_obr_alarm_enabled", "set_obr_alarm_enabled", "THRES:OBR:OVER:STAT"),
    ("get_box_temp_alarm_enabled", "set_box_temp_alarm_enabled", "THRES:TEMP:BOX:STAT"),
    ("get_fibre_chamber_alarm_enabled", "set_fibre_chamber_alarm_enabled", "THRES:TEMP:FC:STAT"),
    ("get_voltage_alarm_enabled", "set_voltage_alarm_enabled", "THRES:VOLT:PS:STAT"),
]


@pytest.mark.parametrize("getter_name, setter_name, path", BOOL_CONFIG_PAIRS)
def test_bool_config_getter(opened_device, mock_serial, getter_name, setter_name, path):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert getattr(opened_device, getter_name)() is True
    mock_serial.write.assert_called_with(f":{path}?\r\n".encode("ascii"))


@pytest.mark.parametrize("getter_name, setter_name, path", BOOL_CONFIG_PAIRS)
def test_bool_config_setter(opened_device, mock_serial, getter_name, setter_name, path):
    getattr(opened_device, setter_name)(True)
    mock_serial.write.assert_called_with(f":{path} 1\r\n".encode("ascii"))


FLOAT_CONFIG_PAIRS = [
    ("get_ipd_level_dbm", "set_ipd_level_dbm", "THRES:POW:IN:LEV:SET1", -15.0),
    ("get_opd_range_pct", "set_opd_range_pct", "THRES:POW:OUT:RANGE:SET1", 20.0),
    ("get_opd_range_min_pct", "set_opd_range_min_pct", "THRES:POW:OUT:RANGE_MIN:SET1", 10.0),
    ("get_opd_range_max_pct", "set_opd_range_max_pct", "THRES:POW:OUT:RANGE_MAX:SET1", 80.0),
    ("get_opd_autostart_time_s", "set_opd_autostart_time_s", "THRES:POW:OUT:TIME", 60.0),
    ("get_current_alarm_level_ma", "set_current_alarm_level_ma", "THRES:CUR:OVER:LEV:SET1", 280.0),
    ("get_obr_alarm_level_dbm", "set_obr_alarm_level_dbm", "THRES:OBR:OVER:LEV:SET1", -15.0),
    ("get_box_temp_min_degc", "set_box_temp_min_degc", "THRES:TEMP:BOX:MIN", 10.0),
    ("get_box_temp_max_degc", "set_box_temp_max_degc", "THRES:TEMP:BOX:MAX", 60.0),
    ("get_fibre_chamber_max_degc", "set_fibre_chamber_max_degc", "THRES:TEMP:FC:MAX", 50.0),
]


@pytest.mark.parametrize("getter_name, setter_name, path, value", FLOAT_CONFIG_PAIRS)
def test_float_config_getter(opened_device, mock_serial, getter_name, setter_name, path, value):
    mock_serial.readline.side_effect = [f"{value:e}\r\n".encode("ascii")]
    assert getattr(opened_device, getter_name)() == pytest.approx(value)
    mock_serial.write.assert_called_with(f":{path}?\r\n".encode("ascii"))


@pytest.mark.parametrize("getter_name, setter_name, path, value", FLOAT_CONFIG_PAIRS)
def test_float_config_setter(opened_device, mock_serial, getter_name, setter_name, path, value):
    getattr(opened_device, setter_name)(value)
    mock_serial.write.assert_called_with(f":{path} {value:g}\r\n".encode("ascii"))


def test_get_ipd_active_rejects_out_of_range_channel(opened_device):
    with pytest.raises(AEDFACommandError):
        opened_device.get_ipd_active(channel=9)


def test_get_ipd_active_queries_expected_path(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.get_ipd_active(channel=1) is True
    mock_serial.write.assert_called_with(b":THRES:POW:IN:ACT:CH1?\r\n")


def test_get_opd_reference_mw_queries_expected_path(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"3.000000e+02\r\n"]
    assert opened_device.get_opd_reference_mw() == pytest.approx(300.0)
    mock_serial.write.assert_called_with(b":THRES:POW:OUT:REF:SET1?\r\n")


def test_can_unlock_tec_overheat_queries_expected_path(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1\r\n"]
    assert opened_device.can_unlock_tec_overheat() is True
    mock_serial.write.assert_called_with(b":THRES:TEMP:TEC:OVER:UNLOCK?\r\n")


def test_unlock_tec_overheat_sends_expected_command(opened_device, mock_serial):
    opened_device.unlock_tec_overheat()
    mock_serial.write.assert_called_with(b":THRES:TEMP:TEC:OVER:UNLOCK 1\r\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL — `AttributeError: 'AEDFA' object has no attribute 'get_ipd_enabled'` (and similar)

- [ ] **Step 3: Implement alarm configuration methods**

Append to the `AEDFA` class in `src/amonics_edfa/driver.py`:

```python
    # --- Input power / seed (IPD) ---

    def get_ipd_active(self, channel: int) -> bool:
        """Check whether Input Power Detection has disabled the specified channel."""
        self._validate_channel(channel, self.n_power_in_channels, "input power")
        return self._query_bool(f"THRES:POW:IN:ACT:CH{channel}")

    def get_ipd_enabled(self) -> bool:
        """Get whether Input Power Detection is enabled."""
        return self._query_bool("THRES:POW:IN:STAT:SET1")

    def set_ipd_enabled(self, enabled: bool) -> None:
        """Enable or disable Input Power Detection."""
        self._set_value("THRES:POW:IN:STAT:SET1", enabled)

    def get_ipd_level_dbm(self) -> float:
        """Get the Input Power Detection threshold level (dBm)."""
        return self._query_float("THRES:POW:IN:LEV:SET1")

    def set_ipd_level_dbm(self, value: float) -> None:
        """Set the Input Power Detection threshold level (dBm)."""
        self._set_value("THRES:POW:IN:LEV:SET1", value)

    # --- Output power (OPD) ---

    def get_opd_enabled(self) -> bool:
        """Get whether Output Power Detection is enabled."""
        return self._query_bool("THRES:POW:OUT:STAT:SET1")

    def set_opd_enabled(self, enabled: bool) -> None:
        """Enable or disable Output Power Detection."""
        self._set_value("THRES:POW:OUT:STAT:SET1", enabled)

    def get_opd_range_pct(self) -> float:
        """Get the Output Power Detection range (% of reference power)."""
        return self._query_float("THRES:POW:OUT:RANGE:SET1")

    def set_opd_range_pct(self, value: float) -> None:
        """Set the Output Power Detection range (% of reference power)."""
        self._set_value("THRES:POW:OUT:RANGE:SET1", value)

    def get_opd_range_min_pct(self) -> float:
        """Get the minimum allowed Output Power Detection range (%)."""
        return self._query_float("THRES:POW:OUT:RANGE_MIN:SET1")

    def set_opd_range_min_pct(self, value: float) -> None:
        """Set the minimum allowed Output Power Detection range (%)."""
        self._set_value("THRES:POW:OUT:RANGE_MIN:SET1", value)

    def get_opd_range_max_pct(self) -> float:
        """Get the maximum allowed Output Power Detection range (%)."""
        return self._query_float("THRES:POW:OUT:RANGE_MAX:SET1")

    def set_opd_range_max_pct(self, value: float) -> None:
        """Set the maximum allowed Output Power Detection range (%)."""
        self._set_value("THRES:POW:OUT:RANGE_MAX:SET1", value)

    def get_opd_reference_mw(self) -> float:
        """Get the Output Power Detection reference power (mW)."""
        return self._query_float("THRES:POW:OUT:REF:SET1")

    def get_opd_autostart_time_s(self) -> float:
        """Get the Output Power Detection auto-start time (s)."""
        return self._query_float("THRES:POW:OUT:TIME")

    def set_opd_autostart_time_s(self, value: float) -> None:
        """Set the Output Power Detection auto-start time (s)."""
        self._set_value("THRES:POW:OUT:TIME", value)

    # --- Current alarm ---

    def get_current_alarm_enabled(self) -> bool:
        """Get whether the over-current alarm is enabled."""
        return self._query_bool("THRES:CUR:OVER:STAT")

    def set_current_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the over-current alarm."""
        self._set_value("THRES:CUR:OVER:STAT", enabled)

    def get_current_alarm_level_ma(self) -> float:
        """Get the over-current alarm threshold (mA)."""
        return self._query_float("THRES:CUR:OVER:LEV:SET1")

    def set_current_alarm_level_ma(self, value: float) -> None:
        """Set the over-current alarm threshold (mA)."""
        self._set_value("THRES:CUR:OVER:LEV:SET1", value)

    # --- Output back reflection (OBR) ---

    def get_obr_alarm_enabled(self) -> bool:
        """Get whether the OBR alarm is enabled."""
        return self._query_bool("THRES:OBR:OVER:STAT")

    def set_obr_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the OBR alarm."""
        self._set_value("THRES:OBR:OVER:STAT", enabled)

    def get_obr_alarm_level_dbm(self) -> float:
        """Get the OBR alarm threshold (dBm)."""
        return self._query_float("THRES:OBR:OVER:LEV:SET1")

    def set_obr_alarm_level_dbm(self, value: float) -> None:
        """Set the OBR alarm threshold (dBm)."""
        self._set_value("THRES:OBR:OVER:LEV:SET1", value)

    # --- Case temperature ---

    def get_box_temp_alarm_enabled(self) -> bool:
        """Get whether the case temperature alarm is enabled."""
        return self._query_bool("THRES:TEMP:BOX:STAT")

    def set_box_temp_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the case temperature alarm."""
        self._set_value("THRES:TEMP:BOX:STAT", enabled)

    def get_box_temp_min_degc(self) -> float:
        """Get the minimum case temperature alarm threshold (deg C)."""
        return self._query_float("THRES:TEMP:BOX:MIN")

    def set_box_temp_min_degc(self, value: float) -> None:
        """Set the minimum case temperature alarm threshold (deg C)."""
        self._set_value("THRES:TEMP:BOX:MIN", value)

    def get_box_temp_max_degc(self) -> float:
        """Get the maximum case temperature alarm threshold (deg C)."""
        return self._query_float("THRES:TEMP:BOX:MAX")

    def set_box_temp_max_degc(self, value: float) -> None:
        """Set the maximum case temperature alarm threshold (deg C)."""
        self._set_value("THRES:TEMP:BOX:MAX", value)

    # --- Fibre chamber temperature ---

    def get_fibre_chamber_alarm_enabled(self) -> bool:
        """Get whether the fibre chamber temperature alarm is enabled."""
        return self._query_bool("THRES:TEMP:FC:STAT")

    def set_fibre_chamber_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the fibre chamber temperature alarm."""
        self._set_value("THRES:TEMP:FC:STAT", enabled)

    def get_fibre_chamber_max_degc(self) -> float:
        """Get the maximum fibre chamber temperature alarm threshold (deg C)."""
        return self._query_float("THRES:TEMP:FC:MAX")

    def set_fibre_chamber_max_degc(self, value: float) -> None:
        """Set the maximum fibre chamber temperature alarm threshold (deg C)."""
        self._set_value("THRES:TEMP:FC:MAX", value)

    # --- TEC overheat unlock ---

    def can_unlock_tec_overheat(self) -> bool:
        """Check whether lasers can be unlocked from a TEC overheat event."""
        return self._query_bool("THRES:TEMP:TEC:OVER:UNLOCK")

    def unlock_tec_overheat(self) -> None:
        """Unlock lasers after a TEC overheat event has cleared."""
        self._set_value("THRES:TEMP:TEC:OVER:UNLOCK", True)

    # --- Supply voltage alarm ---

    def get_voltage_alarm_enabled(self) -> bool:
        """Get whether the power supply voltage alarm is enabled."""
        return self._query_bool("THRES:VOLT:PS:STAT")

    def set_voltage_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the power supply voltage alarm."""
        self._set_value("THRES:VOLT:PS:STAT", enabled)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (89 passed)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/driver.py tests/test_driver.py
git commit -m "Add alarm configuration methods (IPD, OPD, current, OBR, temperature, voltage)"
```

---

### Task 8: Extras + hardware smoke test

**Files:**
- Modify: `src/amonics_edfa/driver.py`
- Modify: `tests/test_driver.py`

**Interfaces:**
- Consumes: `_query_int/_query_float/_query_str`, `_set_value` (Task 3); `AEDFA` (Task 3, for the hardware smoke test).
- Produces: `get_usb_current_mode()`, `get_power_limit_mw()`/`set_power_limit_mw(value)`, `get_laser_timer()`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_driver.py`:

```python
def test_get_usb_current_mode(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"3\r\n"]
    assert opened_device.get_usb_current_mode() == 3
    mock_serial.write.assert_called_with(b":READ:DRIV:PD?\r\n")


def test_get_power_limit_mw(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"1.000000e+04\r\n"]
    assert opened_device.get_power_limit_mw() == pytest.approx(10000.0)
    mock_serial.write.assert_called_with(b":DRIV:LIMIT:POW:OUT:MAX?\r\n")


def test_set_power_limit_mw(opened_device, mock_serial):
    opened_device.set_power_limit_mw(10000)
    mock_serial.write.assert_called_with(b":DRIV:LIMIT:POW:OUT:MAX 10000\r\n")


def test_get_laser_timer(opened_device, mock_serial):
    mock_serial.readline.side_effect = [b"5d.10h:10m:10s\r\n"]
    assert opened_device.get_laser_timer() == "5d.10h:10m:10s"
    mock_serial.write.assert_called_with(b":READ:DRIV:TIME?\r\n")


@pytest.mark.hw
def test_real_hardware_smoke():
    """Smoke test against a physical AEDFA. Run with: pytest --hw -k test_real_hardware_smoke
    Set AEDFA_PORT to override the default serial port (COM8)."""
    import os

    port = os.environ.get("AEDFA_PORT", "COM8")
    with AEDFA(port=port) as device:
        assert device.get_modes()
        mode = device.get_mode()
        assert isinstance(mode, str)
        status = device.get_channel_status(channel=1)
        assert status is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_driver.py -v`
Expected: FAIL — `AttributeError: 'AEDFA' object has no attribute 'get_usb_current_mode'` (and similar); `test_real_hardware_smoke` is skipped, not failing, since `--hw` isn't passed

- [ ] **Step 3: Implement extras methods**

Append to the `AEDFA` class in `src/amonics_edfa/driver.py`:

```python
    def get_usb_current_mode(self) -> int:
        """Get the USB operating current mode (1=default 0-2A, 3=USB-C 3A)."""
        return self._query_int("READ:DRIV:PD")

    def get_power_limit_mw(self) -> float:
        """Get the maximum output power limit (mW)."""
        return self._query_float("DRIV:LIMIT:POW:OUT:MAX")

    def set_power_limit_mw(self, value: float) -> None:
        """Set the maximum output power limit (mW)."""
        self._set_value("DRIV:LIMIT:POW:OUT:MAX", value)

    def get_laser_timer(self) -> str:
        """Get the cumulative laser operating time, as 'DAY.HOUR:MINUTES:SECOND'."""
        return self._query_str("READ:DRIV:TIME")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_driver.py -v`
Expected: PASS (93 passed, 1 skipped)

- [ ] **Step 5: Commit**

```bash
git add src/amonics_edfa/driver.py tests/test_driver.py
git commit -m "Add extras (USB current mode, power limit, laser timer) and hardware smoke test"
```

---

### Task 9: Example script + README

**Files:**
- Create: `examples/basic_control.py`
- Create: `README.md`

**Interfaces:**
- Consumes: the full public `AEDFA` API (Tasks 3–8). No new interfaces produced.

- [ ] **Step 1: Write the example script**

`examples/basic_control.py`:

```python
"""Basic control example for an Amonics AEDFA, mirroring Example A from the programming manual.

Connects over serial, sets a current set-point, enables the laser, polls output
power and temperature a few times, checks for alarms, then disables and exits.
"""

import time

from amonics_edfa import AEDFA

PORT = "COM8"
CHANNEL = 1
CURRENT_SETPOINT_MA = 350
POLL_INTERVAL_S = 1.0
POLL_COUNT = 5

with AEDFA(port=PORT) as amp:
    print(f"Modes available: {amp.get_modes()}")
    print(f"Current channels: {amp.n_current_channels}")
    print(f"Output power channels: {amp.n_power_out_channels}")

    amp.set_current_setpoint(channel=CHANNEL, value_ma=CURRENT_SETPOINT_MA)
    amp.set_channel_status(channel=CHANNEL, on=True)
    amp.master_enable()

    for _ in range(POLL_COUNT):
        time.sleep(POLL_INTERVAL_S)
        output_power_mw = amp.get_output_power_mw(channel=CHANNEL)
        box_temp_degc = amp.get_box_temp_degc()
        print(f"Output power: {output_power_mw:.2f} mW, case temp: {box_temp_degc:.2f} degC")

        if amp.get_interlock():
            print("WARNING: interlock active")
        if amp.get_alarm_tec_over():
            print("WARNING: TEC overheat alarm")

    amp.master_disable()
    amp.set_channel_status(channel=CHANNEL, on=False)
    print("Done.")
```

- [ ] **Step 2: Write the README**

`README.md`:

`````markdown
# amonics-edfa

Python driver for Amonics AEDFA erbium-doped fibre amplifiers, controlling and monitoring the
device over its RS-232 SCPI-style command set (`Amonics_AEDFA_Programming_Manual.pdf`, ver. 2.08).

## Install

```bash
pip install -e . --break-system-packages
```

## Usage

```python
from amonics_edfa import AEDFA

with AEDFA(port="COM8") as amp:
    amp.set_current_setpoint(channel=1, value_ma=350)
    amp.set_channel_status(channel=1, on=True)
    amp.master_enable()
    print(amp.get_output_power_mw(channel=1))
```

See `examples/basic_control.py` for a complete example.

## Testing

```bash
pip install -e ".[dev]" --break-system-packages
pytest                # unit tests, mocked serial port
pytest --hw           # include the hardware smoke test (requires a connected device)
```

## Scope

Covers initialisation/capability discovery, mode switching, set-point control, all sensor and
alarm reads, and alarm threshold configuration. Not included: HTTP/web commands (manual states
these require an Ethernet connection, out of scope for a direct serial driver), PLL status
(exclusive to one unsupported firmware variant), and EDFA switching (`:SWAP:CH*`, relevant only
to multi-EDFA rack units).
`````

- [ ] **Step 3: Verify the full test suite still passes**

Run: `pytest -v`
Expected: PASS (93 passed, 1 skipped)

- [ ] **Step 4: Commit**

```bash
git add examples/basic_control.py README.md
git commit -m "Add basic control example and README"
```
