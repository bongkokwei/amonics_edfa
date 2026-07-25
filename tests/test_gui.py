"""GUI tests against a fake amplifier, driven with a real Qt event loop."""

import os
import time
from unittest import mock

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from amonics_edfa import worker as worker_module  # noqa: E402
from amonics_edfa.driver import ChannelStatus, CurrentLimits  # noqa: E402
from amonics_edfa.gui import MainWindow  # noqa: E402


class FakeAmp:
    """Stands in for AEDFA inside the worker thread."""

    def __init__(self, port, **kwargs):
        self.port = port
        self.modes = ["ACC", "APC"]
        self.n_driving_channels = 2
        self.n_current_channels = 2
        self.n_power_in_channels = 2
        self.n_power_out_channels = 2
        self.n_box_temp_channels = 1
        self.mode = "APC"
        self.channel_on = False
        self.master_on = False
        self.setpoint = 120.0
        self.closed = False

    def open(self):
        pass

    def close(self):
        self.closed = True

    def get_mode(self, channel=1):
        return self.mode

    def set_mode(self, mode, channel=1):
        self.mode = mode

    def get_current_limits(self, channel, mode=None):
        return CurrentLimits(0.0, 500.0, 0.1, 1.0)

    def get_current_setpoint(self, channel, mode=None):
        return self.setpoint

    def set_current_setpoint(self, channel, value_ma, mode=None):
        self.setpoint = value_ma

    def get_channel_status(self, channel, mode=None):
        return ChannelStatus.ON if self.channel_on else ChannelStatus.OFF

    def set_channel_status(self, channel, on, mode=None):
        self.channel_on = on

    def is_master_enabled(self):
        return ChannelStatus.ON if self.master_on else ChannelStatus.OFF

    def master_enable(self):
        self.master_on = True

    def master_disable(self):
        self.master_on = False

    def get_current_ma(self, channel):
        return 231.4

    def get_input_power_mw(self, channel):
        return 0.98

    def get_output_power_mw(self, channel):
        return 42.17

    def get_box_temp_degc(self):
        return 31.8

    def get_interlock(self):
        return False


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    with mock.patch.object(worker_module, "AEDFA", FakeAmp):
        window = MainWindow()
        yield window
        window.close()


def wait_until(app, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def connect(app, window):
    window.port_combo.setCurrentText("/dev/fake0")
    window.toggle_connection()
    assert wait_until(app, lambda: window.connected), "worker never reported a connection"


def test_readings_update_without_a_refresh_button(app, window):
    connect(app, window)
    assert wait_until(app, lambda: window.output_tile.value_label.text() != "--")
    assert window.output_tile.value_label.text() == "42.17"
    assert window.input_tile.value_label.text() == "0.98"
    assert window.current_tile.value_label.text() == "231.4"
    assert window.temp_tile.value_label.text() == "31.8"
    assert window.updated_label.text().startswith("Updated")


def test_connect_populates_channels_modes_and_limits(app, window):
    connect(app, window)
    assert wait_until(app, lambda: window.limits_label.text() != "")
    assert window.channel_spin.maximum() == 2
    assert window.mode_buttons["APC"].isChecked()
    assert window.setpoint_spin.maximum() == 500.0
    assert "mW" in window.setpoint_label.text()


def test_output_toggle_updates_button_and_badge(app, window):
    connect(app, window)
    window.request_output.emit(True)
    assert wait_until(app, lambda: window.output_on)
    assert window.output_button.text() == "Disable Output"
    assert window.output_button.objectName() == "danger"
    assert window.output_pill.label.text() == "Output ON"

    window.request_output.emit(False)
    assert wait_until(app, lambda: not window.output_on)
    assert window.output_button.text() == "Enable Output"
    assert window.output_button.objectName() == "primary"


def test_mode_switch_updates_setpoint_units(app, window):
    connect(app, window)
    window.request_mode.emit("ACC")
    assert wait_until(app, lambda: "mA" in window.setpoint_label.text())
    assert window.mode_buttons["ACC"].isChecked()


def test_disconnect_clears_readings(app, window):
    connect(app, window)
    assert wait_until(app, lambda: window.output_tile.value_label.text() != "--")
    window.request_close.emit()
    assert wait_until(app, lambda: not window.connected)
    assert window.output_tile.value_label.text() == "--"
    assert window.connection_pill.label.text() == "Disconnected"
