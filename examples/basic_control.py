"""Basic monitoring example for an Amonics AEDFA, mirroring Example A from the programming
manual.

Connects over serial and polls the sensors this specific device reports supporting, checking
for alarms. Does not enable any channel or the master control, since without input power
connected there is nothing to safely amplify.
"""

import time

from amonics_edfa import AEDFA

PORT = "COM13"
CHANNEL = 1
POLL_INTERVAL_S = 1.0
POLL_COUNT = 5

with AEDFA(port=PORT) as amp:
    print(f"Modes available: {amp.get_modes()}")
    print(f"Current channels: {amp.n_current_channels}")
    print(f"Output power channels: {amp.n_power_out_channels}")
    if amp.n_voltage_channels:
        print(f"Supply voltage: {amp.get_supply_voltage():.2f} V")

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

        if amp.get_interlock():
            print("WARNING: interlock active")
        if amp.n_power_in_channels >= CHANNEL and amp.get_alarm_input_loss(channel=CHANNEL):
            print("WARNING: input power loss alarm")
        if amp.get_alarm_current_over():
            print("WARNING: over-current alarm")
        if amp.n_box_temp_channels and amp.get_alarm_box_temp():
            print("WARNING: case over-temperature alarm")
        if amp.n_fibre_chamber_temp_channels and amp.get_alarm_fibre_chamber():
            print("WARNING: fibre chamber alarm")
        if amp.n_tec_channels:
            if amp.get_alarm_tec_warn():
                print("WARNING: TEC warning alarm")
            if amp.get_alarm_tec_over():
                print("WARNING: TEC overheat alarm")
        if amp.n_voltage_channels and amp.get_alarm_supply_voltage():
            print("WARNING: supply voltage alarm")

    print("Done.")
