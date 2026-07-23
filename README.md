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
