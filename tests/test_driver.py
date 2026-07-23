from unittest.mock import call

import pytest

from amonics_edfa import AEDFA, ChannelStatus
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
