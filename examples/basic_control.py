"""Basic monitoring example for an Amonics AEDFA, mirroring Example A from the programming
manual.

Connects over serial and polls output power and temperature a few times, checking for
alarms. Does not enable any channel or the master control, since without input power
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
    print(f"Laser timer: {amp.get_laser_timer()}")

    for _ in range(POLL_COUNT):
        time.sleep(POLL_INTERVAL_S)
        output_power_mw = amp.get_output_power_mw(channel=CHANNEL)
        box_temp_degc = amp.get_box_temp_degc()
        fibre_chamber_temp_degc = amp.get_fibre_chamber_temp_degc()
        current_ma = amp.get_current_ma(channel=CHANNEL)
        tec_temp_degc = amp.get_tec_temp_degc(channel=CHANNEL)
        print(
            f"Output power: {output_power_mw:.2f} mW, "
            f"current: {current_ma:.2f} mA, "
            f"case temp: {box_temp_degc:.2f} degC, "
            f"fibre chamber temp: {fibre_chamber_temp_degc:.2f} degC, "
            f"TEC temp: {tec_temp_degc:.2f} degC"
        )

        if amp.get_interlock():
            print("WARNING: interlock active")
        if amp.get_alarm_input_loss(channel=CHANNEL):
            print("WARNING: input power loss alarm")
        if amp.get_alarm_current_over():
            print("WARNING: over-current alarm")
        if amp.get_alarm_box_temp():
            print("WARNING: case over-temperature alarm")
        if amp.get_alarm_fibre_chamber():
            print("WARNING: fibre chamber alarm")
        if amp.get_alarm_tec_warn():
            print("WARNING: TEC warning alarm")
        if amp.get_alarm_tec_over():
            print("WARNING: TEC overheat alarm")

    print("Done.")
