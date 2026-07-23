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

    for _ in range(POLL_COUNT):
        time.sleep(POLL_INTERVAL_S)
        output_power_mw = amp.get_output_power_mw(channel=CHANNEL)
        box_temp_degc = amp.get_box_temp_degc()
        print(f"Output power: {output_power_mw:.2f} mW, case temp: {box_temp_degc:.2f} degC")

        if amp.get_interlock():
            print("WARNING: interlock active")
        if amp.get_alarm_tec_over():
            print("WARNING: TEC overheat alarm")

    print("Done.")
