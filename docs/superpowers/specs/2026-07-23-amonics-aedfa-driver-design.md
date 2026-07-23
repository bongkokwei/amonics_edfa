# Amonics AEDFA Python Driver — Design

## Purpose

A Python driver package for the Amonics AEDFA erbium-doped fibre amplifier, controlling and
monitoring the device over its RS-232 SCPI-style command set (per
`Amonics_AEDFA_Programming_Manual.pdf`, SCPI command ver. 2.08). Target hardware for initial
validation: a single-channel benchtop/module unit.

## Transport

The manual specifies a raw serial link, not a VISA/GPIB-discoverable instrument:

- Baud rate 19200bps, 8 data bits, no parity, 1 stop bit, no flow control
- Commands are ASCII, start with `:`, end with `\r\n`
- Full command must be transmitted within 500ms
- A minimum 50ms delay is required between successive commands
- Queries append `?`; sets are followed by a space then the value

This uses `pyserial` directly (custom RS-232 protocol), not `pyvisa` — despite the SCPI-styled
command syntax, there is no VISA resource layer involved.

## Package layout

```
amonics_edfa/
├── src/amonics_edfa/
│   ├── __init__.py       # exports AEDFA, ChannelStatus, AEDFAError, AEDFATimeoutError, AEDFACommandError
│   ├── driver.py          # AEDFA class — the public API
│   ├── protocol.py        # command framing + response parsing helpers
│   ├── enums.py           # ChannelStatus (OFF/ON/BUSY/LOCK)
│   └── exceptions.py      # AEDFAError, AEDFATimeoutError, AEDFACommandError
├── examples/
│   └── basic_control.py   # straight-line demo script
├── tests/
│   └── test_driver.py
├── pyproject.toml
└── README.md
```

## Core class

A single flat `AEDFA` class — no mixins/plugin architecture. The command set is a direct 1:1
mapping onto the manual, so extra structure would just be indirection. Methods are grouped by
manual section (comments, not sub-classes).

### Connection & capability discovery

- `AEDFA(port: str, baudrate: int = 19200, timeout: float = 2.0)` — stores config, does not open
  the port.
- `open()` / `close()`, plus `__enter__`/`__exit__` context manager support.
- On `open()`, queries `:READ:CH:*` (driving/current/power-in/power-out/PD/box-temp/
  fibre-chamber-temp/TEC/voltage channel counts) and `:READ:MODE:NAMES?` once, caching the
  results on the instance (`self.modes`, `self.n_current_channels`, etc.). Public methods that
  take a channel or mode argument validate against these cached capabilities and raise
  `AEDFACommandError` if the device doesn't have that channel/mode, rather than sending a
  command the device won't recognise.

### Mode & set-point (manual §2–3)

- `get_modes() -> list[str]`
- `get_mode(channel: int = 1) -> str`
- `set_mode(mode: str, channel: int = 1) -> None`
- `get_current_setpoint(channel: int, mode: str | None = None) -> float` (mA)
- `set_current_setpoint(channel: int, value_ma: float, mode: str | None = None) -> None`
- `get_current_limits(channel: int, mode: str | None = None) -> CurrentLimits` (min/max/step/
  lo-margin, named tuple)
- `get_channel_status(channel: int, mode: str | None = None) -> ChannelStatus`
- `set_channel_status(channel: int, on: bool, mode: str | None = None) -> None`
- `master_enable()` / `master_disable()` / `is_master_enabled() -> ChannelStatus`

`mode=None` uses the mode currently active on that channel (queried via `get_mode`).

### Sensors (manual §4)

- `get_current_ma(channel: int) -> float`
- `get_input_power_mw(channel: int) -> float`
- `get_output_power_mw(channel: int) -> float`
- `get_pd_power_mw(channel: int) -> float`
- `get_box_temp_degc() -> float`
- `get_fibre_chamber_temp_degc() -> float`
- `get_tec_temp_degc(channel: int) -> float`
- `get_supply_voltage() -> float`
- `get_seed_stabilising() -> bool`
- `get_interlock() -> bool`
- `unlock_interlock() -> None`

### Alarms — read (manual §5)

One getter per manual alarm flag, each with a `latched: bool = False` parameter selecting the
latched vs non-latched variant:

- `get_alarm_input_loss(channel, latched=False) -> bool`
- `get_alarm_input_over(channel, latched=False) -> bool`
- `get_alarm_current_over(latched=False) -> bool`
- `get_alarm_box_temp(latched=False) -> bool`
- `get_alarm_fibre_chamber() -> int` (0=READY, 1=FAIL, 2=OFF; no latched variant in manual)
- `get_alarm_tec_warn(latched=False) -> bool`
- `get_alarm_tec_over(latched=False) -> int` (0 = off, >0 = channel alarm)
- `get_alarm_supply_voltage(latched=False) -> bool`

### Alarm configuration (manual §6)

Enable/level/range getter+setter pairs, one group per alarm type:

- **Input power / seed (IPD)**: `get_ipd_active`, `get_ipd_enabled`/`set_ipd_enabled`,
  `get_ipd_level_dbm`/`set_ipd_level_dbm`
- **Output power (OPD)**: enabled, range %, range-min %, range-max %, reference power (read-only),
  auto-start time (s)
- **Current**: alarm enabled, alarm level (mA)
- **OBR**: alarm enabled, alarm level (dBm)
- **Box temperature**: alarm enabled, min/max threshold (°C)
- **Fibre chamber temperature**: alarm enabled, max threshold (°C)
- **TEC overheat**: `can_unlock_tec_overheat() -> bool`, `unlock_tec_overheat() -> None`
- **Supply voltage**: alarm enabled

### Extras (manual §10)

- `get_usb_current_mode() -> int` (1 = default 0–2A, 3 = USB-C 3A)
- `get_power_limit_mw()` / `set_power_limit_mw(value)`
- `get_pll_status()` / `set_pll_status()` — documented as device-specific (one Amonics firmware
  variant only); wrapped since it's a 3-line method, but callers should expect
  `AEDFACommandError`/timeout on units that don't implement it.
- `get_laser_timer() -> str` (raw `DAY.HOUR:MINUTES:SECOND` string; no parsing into `timedelta` —
  YAGNI unless a use case needs it)
- `get_edfa_count() -> int`, `get_active_edfa() -> int`, `set_active_edfa(channel: int) -> None`
  (`:SWAP:CH*` — thin wrappers, harmless no-ops on the single-channel target hardware, useful if a
  multi-EDFA rack unit is added later)

Not included: HTTP/web commands (§7) — manual states these are unavailable over a direct
Ethernet-to-RS232 link, which is the only transport this package targets.

## Data flow

1. Public method call →
2. `protocol.build_command(...)` formats the `:CMD:PATH value\r\n` or `:CMD:PATH?\r\n` string →
3. Driver enforces the manual's 50ms minimum inter-command delay (tracks last-write timestamp) →
4. Serial write; for queries, read one line up to the configured timeout →
5. `protocol.parse_response(...)` converts the raw string (scientific notation, integer flag, or
   ASCII string) into the typed Python return value.

## Error handling

- `AEDFAError` — base exception
- `AEDFATimeoutError` — no reply within `timeout`
- `AEDFACommandError` — channel/mode argument not supported by this device (checked against
  capabilities cached at `open()`)

No retry logic in the driver — left to the caller.

## Testing

`tests/test_driver.py`, mocking `serial.Serial` at the I/O boundary (per lab convention):

- Command encoding: assert exact bytes written for representative set/query commands
- Response parsing: scientific notation → float, `0`/`1` → bool/`ChannelStatus`, ASCII passthrough
- Capability discovery at `open()` (channel counts, mode list cached correctly)
- `AEDFACommandError` raised for an out-of-range channel/mode
- Context manager closes the serial port on exit
- One `--hw`-marked smoke test (open → read mode/status → close) for real hardware, skipped by
  default

## Example

`examples/basic_control.py` — straight-line script (constants at top for port/current, no
argparse/config file): open via context manager → print discovered modes/channel counts → set a
current setpoint → enable channel + master control → poll output power and temperature a few
times → check alarms → disable → exit. Mirrors Example A from the programming manual.
