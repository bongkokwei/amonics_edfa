"""Basic control example for an Amonics AEDFA, mirroring Examples B/C from the programming
manual: switch a channel to APC (constant output power) mode, set an output power setpoint,
and enable the laser.

Per the manual's SET-POINT section, the driving setpoint is always sent through
DRIV:<mode>:CUR:CH<n>, whatever the mode — the value is mA in ACC mode but mW in APC mode.
set_current_setpoint()/get_current_setpoint() below are that same generic setpoint call; in
APC mode, value_ma is actually a power level in mW.

The manual's own worked example for switching mode also fixes the required order: switch
mode -> set the setpoint value -> set channel status to standby -> master_enable().
"""

import time

from amonics_edfa import AEDFA
from amonics_edfa.exceptions import AEDFATimeoutError

PORT = "COM13"
CHANNEL = 1
MODE = "APC"
OUTPUT_POWER_SETPOINT_MW = 10.0  # adjust to the power level you actually want
POLL_INTERVAL_S = 1.0
POLL_COUNT = 5


def check_alarm(label: str, get_alarm) -> bool:
    """Run one alarm check. Returns False (drop it) if the device didn't reply at all."""
    try:
        if get_alarm():
            print(f"WARNING: {label} alarm")
        return True
    except AEDFATimeoutError:
        print(f"({label} alarm not supported on this device, skipping)")
        return False


with AEDFA(port=PORT) as amp:
    print(f"Modes available: {amp.get_modes()}")
    print(f"Current channels: {amp.n_current_channels}")
    print(f"Output power channels: {amp.n_power_out_channels}")
    if amp.n_voltage_channels:
        print(f"Supply voltage: {amp.get_supply_voltage():.2f} V")

    if amp.get_interlock():
        raise SystemExit("Interlock is active; refusing to enable the laser.")

    amp.set_mode(MODE, channel=CHANNEL)
    limits = amp.get_current_limits(channel=CHANNEL, mode=MODE)
    print(f"{MODE} setpoint limits (mW): {limits}")
    amp.set_current_setpoint(channel=CHANNEL, value_ma=OUTPUT_POWER_SETPOINT_MW, mode=MODE)
    print(f"Setpoint readback: {amp.get_current_setpoint(channel=CHANNEL, mode=MODE):.2f} mW")

    amp.set_channel_status(channel=CHANNEL, on=True, mode=MODE)
    amp.master_enable()

    alarms = [("interlock", amp.get_interlock), ("over-current", amp.get_alarm_current_over)]
    if amp.n_power_in_channels >= CHANNEL:
        alarms.append(("input power loss", lambda: amp.get_alarm_input_loss(channel=CHANNEL)))
    if amp.n_box_temp_channels:
        alarms.append(("case over-temperature", amp.get_alarm_box_temp))
    if amp.n_fibre_chamber_temp_channels:
        alarms.append(("fibre chamber", amp.get_alarm_fibre_chamber))
    if amp.n_tec_channels:
        alarms.append(("TEC warning", amp.get_alarm_tec_warn))
        alarms.append(("TEC overheat", amp.get_alarm_tec_over))
    if amp.n_voltage_channels:
        alarms.append(("supply voltage", amp.get_alarm_supply_voltage))

    try:
        for _ in range(POLL_COUNT):
            time.sleep(POLL_INTERVAL_S)
            readings = [f"output power: {amp.get_output_power_mw(channel=CHANNEL):.2f} mW"]
            if amp.n_current_channels >= CHANNEL:
                readings.append(f"current: {amp.get_current_ma(channel=CHANNEL):.2f} mA")
            if amp.n_box_temp_channels:
                readings.append(f"case temp: {amp.get_box_temp_degc():.2f} degC")
            if amp.n_fibre_chamber_temp_channels:
                readings.append(
                    f"fibre chamber temp: {amp.get_fibre_chamber_temp_degc():.2f} degC"
                )
            if amp.n_tec_channels >= CHANNEL:
                readings.append(f"TEC temp: {amp.get_tec_temp_degc(channel=CHANNEL):.2f} degC")
            print(", ".join(readings))

            alarms = [(label, fn) for label, fn in alarms if check_alarm(label, fn)]
    finally:
        amp.master_disable()
        amp.set_channel_status(channel=CHANNEL, on=False, mode=MODE)

    print("Done.")
