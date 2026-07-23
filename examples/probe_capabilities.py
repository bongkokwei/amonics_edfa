"""Capability probe for an Amonics AEDFA: tries every read-only command in the driver once
and reports which ones this specific unit actually replies to.

Useful for an older/different model than the one the driver was written against, where the
manual's own disclaimer applies: "Not all the command are available in a device, that depends
on the specification and special function of that device." Only calls getters — no setters,
mode switches, unlocks, or master/channel enables — so it's safe to run with no input power
connected and without changing any device state.
"""

from amonics_edfa import AEDFA
from amonics_edfa.exceptions import AEDFACommandError, AEDFATimeoutError

PORT = "COM13"
CHANNEL = 1


def probe(label: str, fn) -> None:
    try:
        value = fn()
        print(f"  OK    {label}: {value!r}")
    except AEDFATimeoutError:
        print(f"  NO REPLY  {label} (not supported on this device)")
    except AEDFACommandError as exc:
        print(f"  N/A   {label} ({exc})")


with AEDFA(port=PORT) as amp:
    print("Discovered capabilities:")
    print(f"  modes={amp.modes}")
    print(f"  n_driving_channels={amp.n_driving_channels}")
    print(f"  n_current_channels={amp.n_current_channels}")
    print(f"  n_power_in_channels={amp.n_power_in_channels}")
    print(f"  n_power_out_channels={amp.n_power_out_channels}")
    print(f"  n_pd_channels={amp.n_pd_channels}")
    print(f"  n_box_temp_channels={amp.n_box_temp_channels}")
    print(f"  n_fibre_chamber_temp_channels={amp.n_fibre_chamber_temp_channels}")
    print(f"  n_tec_channels={amp.n_tec_channels}")
    print(f"  n_voltage_channels={amp.n_voltage_channels}")

    print("\nMode & set-point:")
    probe("get_mode", lambda: amp.get_mode(CHANNEL))
    probe("get_current_setpoint", lambda: amp.get_current_setpoint(CHANNEL))
    probe("get_current_limits", lambda: amp.get_current_limits(CHANNEL))
    probe("get_channel_status", lambda: amp.get_channel_status(CHANNEL))
    probe("is_master_enabled", amp.is_master_enabled)

    print("\nSensors:")
    probe("get_current_ma", lambda: amp.get_current_ma(CHANNEL))
    probe("get_input_power_mw", lambda: amp.get_input_power_mw(CHANNEL))
    probe("get_output_power_mw", lambda: amp.get_output_power_mw(CHANNEL))
    probe("get_pd_power_mw", lambda: amp.get_pd_power_mw(CHANNEL))
    probe("get_box_temp_degc", amp.get_box_temp_degc)
    probe("get_fibre_chamber_temp_degc", amp.get_fibre_chamber_temp_degc)
    probe("get_tec_temp_degc", lambda: amp.get_tec_temp_degc(CHANNEL))
    probe("get_supply_voltage", amp.get_supply_voltage)
    probe("get_seed_stabilising", amp.get_seed_stabilising)
    probe("get_interlock", amp.get_interlock)

    print("\nAlarms (read):")
    probe("get_alarm_input_loss", lambda: amp.get_alarm_input_loss(CHANNEL))
    probe("get_alarm_input_over", lambda: amp.get_alarm_input_over(CHANNEL))
    probe("get_alarm_current_over", amp.get_alarm_current_over)
    probe("get_alarm_box_temp", amp.get_alarm_box_temp)
    probe("get_alarm_fibre_chamber", amp.get_alarm_fibre_chamber)
    probe("get_alarm_tec_warn", amp.get_alarm_tec_warn)
    probe("get_alarm_tec_over", amp.get_alarm_tec_over)
    probe("get_alarm_supply_voltage", amp.get_alarm_supply_voltage)

    print("\nInput power / seed (IPD):")
    probe("get_ipd_active", lambda: amp.get_ipd_active(CHANNEL))
    probe("get_ipd_enabled", amp.get_ipd_enabled)
    probe("get_ipd_level_dbm", amp.get_ipd_level_dbm)

    print("\nOutput power (OPD):")
    probe("get_opd_enabled", amp.get_opd_enabled)
    probe("get_opd_range_pct", amp.get_opd_range_pct)
    probe("get_opd_range_min_pct", amp.get_opd_range_min_pct)
    probe("get_opd_range_max_pct", amp.get_opd_range_max_pct)
    probe("get_opd_reference_mw", amp.get_opd_reference_mw)
    probe("get_opd_autostart_time_s", amp.get_opd_autostart_time_s)

    print("\nCurrent alarm:")
    probe("get_current_alarm_enabled", amp.get_current_alarm_enabled)
    probe("get_current_alarm_level_ma", amp.get_current_alarm_level_ma)

    print("\nOutput back reflection (OBR):")
    probe("get_obr_alarm_enabled", amp.get_obr_alarm_enabled)
    probe("get_obr_alarm_level_dbm", amp.get_obr_alarm_level_dbm)

    print("\nCase temperature:")
    probe("get_box_temp_alarm_enabled", amp.get_box_temp_alarm_enabled)
    probe("get_box_temp_min_degc", amp.get_box_temp_min_degc)
    probe("get_box_temp_max_degc", amp.get_box_temp_max_degc)

    print("\nFibre chamber temperature:")
    probe("get_fibre_chamber_alarm_enabled", amp.get_fibre_chamber_alarm_enabled)
    probe("get_fibre_chamber_max_degc", amp.get_fibre_chamber_max_degc)

    print("\nTEC overheat unlock:")
    probe("can_unlock_tec_overheat", amp.can_unlock_tec_overheat)

    print("\nSupply voltage alarm:")
    probe("get_voltage_alarm_enabled", amp.get_voltage_alarm_enabled)

    print("\nExtras:")
    probe("get_usb_current_mode", amp.get_usb_current_mode)
    probe("get_power_limit_mw", amp.get_power_limit_mw)
    probe("get_laser_timer", amp.get_laser_timer)

    print("\nDone.")
