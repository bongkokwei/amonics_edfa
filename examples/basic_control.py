"""Basic monitoring example for an Amonics AEDFA, mirroring Example A from the programming
manual.

Connects over serial and polls the sensors/alarms this specific device supports. Does not
enable any channel or the master control, since without input power connected there is
nothing to safely amplify.

Per the manual, "not all commands are available in a device". Sensor channel counts are
discovered up front (amp.n_*_channels) and gate the corresponding reads below, but alarm
support has no equivalent discovery query, so each alarm check is tried once; if the device
doesn't reply, it's reported as unsupported and dropped for the rest of the run instead of
being retried every poll.
"""

import time

from amonics_edfa import AEDFA
from amonics_edfa.exceptions import AEDFATimeoutError

PORT = "COM13"
CHANNEL = 1
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

    for _ in range(POLL_COUNT):
        time.sleep(POLL_INTERVAL_S)
        readings = [f"output power: {amp.get_output_power_mw(channel=CHANNEL):.2f} mW"]
        if amp.n_current_channels >= CHANNEL:
            readings.append(f"current: {amp.get_current_ma(channel=CHANNEL):.2f} mA")
        if amp.n_box_temp_channels:
            readings.append(f"case temp: {amp.get_box_temp_degc():.2f} degC")
        if amp.n_fibre_chamber_temp_channels:
            readings.append(f"fibre chamber temp: {amp.get_fibre_chamber_temp_degc():.2f} degC")
        if amp.n_tec_channels >= CHANNEL:
            readings.append(f"TEC temp: {amp.get_tec_temp_degc(channel=CHANNEL):.2f} degC")
        print(", ".join(readings))

        alarms = [(label, fn) for label, fn in alarms if check_alarm(label, fn)]

    print("Done.")
