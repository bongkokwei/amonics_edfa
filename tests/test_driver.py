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
