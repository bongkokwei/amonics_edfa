"""PyQt6 control panel for an Amonics AEDFA amplifier.

All serial I/O happens on a background thread (see :mod:`amonics_edfa.worker`),
so readings update by themselves and the window never freezes on a slow reply.
"""

from __future__ import annotations

import sys
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from .driver import ChannelStatus
from .worker import AmpWorker, Capabilities, Limits, Telemetry

POLL_INTERVALS = [("0.5 s", 500), ("1 s", 1000), ("2 s", 2000), ("5 s", 5000)]

STYLESHEET = """
QWidget {
    background: #f4f6f9;
    color: #1e2532;
    font-family: "Segoe UI", "Helvetica Neue", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #dbe1ea;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #6b7686;
    font-size: 11px;
    letter-spacing: 1px;
}
QLabel { background: transparent; }
QLabel#fieldLabel { color: #6b7686; }
QLabel#headline { font-size: 18px; font-weight: 600; }
QLabel#tileTitle { color: #6b7686; font-size: 11px; letter-spacing: 1px; }
QLabel#tileValue { font-size: 22px; font-weight: 600; color: #1e2532; }
QLabel#tileUnit { color: #8b95a5; font-size: 12px; }
QFrame#tile {
    background: #f8fafc;
    border: 1px solid #e3e8ef;
    border-radius: 8px;
}
QFrame#pill {
    background: #eef1f5;
    border: 1px solid #dbe1ea;
    border-radius: 13px;
}
QLabel#pillText { font-weight: 600; color: #6b7686; }

QPushButton {
    background: #ffffff;
    border: 1px solid #c8d0dc;
    border-radius: 6px;
    padding: 7px 16px;
    min-height: 20px;
    font-weight: 500;
}
QPushButton:hover { background: #eef2f7; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #a6aebb; background: #f2f4f7; border-color: #e0e5ec; }

QPushButton#primary {
    background: #2563eb;
    border: 1px solid #1d4ed8;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:pressed { background: #1a43bf; }
QPushButton#primary:disabled { background: #b7c6e8; border-color: #b7c6e8; color: #eef2ff; }

QPushButton#danger {
    background: #dc2626;
    border: 1px solid #b91c1c;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#danger:hover { background: #b91c1c; }
QPushButton#danger:disabled { background: #edb6b6; border-color: #edb6b6; color: #fff5f5; }

QPushButton#segment { padding: 7px 22px; }
QPushButton#segment:checked {
    background: #1e2532;
    border-color: #1e2532;
    color: #ffffff;
    font-weight: 600;
}

QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #c8d0dc;
    border-radius: 6px;
    padding: 6px 8px;
    min-height: 20px;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #2563eb; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #f2f4f7;
    color: #a6aebb;
}
QComboBox::drop-down { border: none; width: 18px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px;
    border: none;
    background: transparent;
}
QStatusBar { background: #eef1f5; color: #6b7686; }
QStatusBar::item { border: none; }
"""

STATUS_COLOURS = {
    "ok": ("#dcfce7", "#15803d"),
    "warn": ("#fef3c7", "#b45309"),
    "error": ("#fee2e2", "#b91c1c"),
    "idle": ("#eef1f5", "#6b7686"),
}


class Tile(QFrame):
    """A single large read-only telemetry value."""

    def __init__(self, title: str, unit: str = "") -> None:
        super().__init__()
        self.setObjectName("tile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        heading = QLabel(title.upper())
        heading.setObjectName("tileTitle")
        layout.addWidget(heading)

        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        self.value_label = QLabel("--")
        self.value_label.setObjectName("tileValue")
        self.value_label.setFont(QFont("DejaVu Sans Mono", 15, QFont.Weight.DemiBold))
        value_row.addWidget(self.value_label)
        if unit:
            unit_label = QLabel(unit)
            unit_label.setObjectName("tileUnit")
            unit_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            value_row.addWidget(unit_label)
        value_row.addStretch()
        layout.addLayout(value_row)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class StatusPill(QFrame):
    """Rounded badge used for the connection, output and interlock indicators."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.setObjectName("pill")
        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        self.label = QLabel(text)
        self.label.setObjectName("pillText")
        layout.addWidget(self.label)

    def set_state(self, text: str, state: str) -> None:
        background, foreground = STATUS_COLOURS[state]
        self.label.setText(text)
        self.setStyleSheet(
            f"QFrame#pill {{ background: {background}; border: 1px solid {background}; }}"
            f"QLabel#pillText {{ color: {foreground}; }}"
        )


class MainWindow(QMainWindow):
    request_open = pyqtSignal(str)
    request_close = pyqtSignal()
    request_mode = pyqtSignal(str)
    request_setpoint = pyqtSignal(float)
    request_output = pyqtSignal(bool)
    request_channel = pyqtSignal(int)
    request_interval = pyqtSignal(int)
    request_unlock = pyqtSignal()
    request_stop = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Amonics AEDFA Control")
        self.setMinimumWidth(780)
        self.setStyleSheet(STYLESHEET)

        self.connected = False
        self.output_on = False
        self.busy = False

        self._build_ui()
        self._start_worker()
        self.refresh_ports()
        self._apply_enabled_state()

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 10)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addWidget(self._build_connection_group())

        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addWidget(self._build_control_group(), 1)
        columns.addWidget(self._build_readings_group(), 1)
        root.addLayout(columns)
        root.addStretch()

        self.setStatusBar(QStatusBar())
        self.status_message = QLabel("Ready")
        self.updated_label = QLabel("")
        self.statusBar().addWidget(self.status_message, 1)
        self.statusBar().addPermanentWidget(self.updated_label)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title = QLabel("Amonics AEDFA")
        title.setObjectName("headline")
        header.addWidget(title)
        header.addStretch()
        self.connection_pill = StatusPill()
        self.connection_pill.set_state("Disconnected", "idle")
        header.addWidget(self.connection_pill)
        return header

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("CONNECTION")
        row = QHBoxLayout(group)
        row.setSpacing(10)

        label = QLabel("Serial port")
        label.setObjectName("fieldLabel")
        row.addWidget(label)

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(220)
        row.addWidget(self.port_combo, 1)

        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.setFixedWidth(90)
        self.rescan_button.clicked.connect(self.refresh_ports)
        row.addWidget(self.rescan_button)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primary")
        self.connect_button.setFixedWidth(130)
        self.connect_button.clicked.connect(self.toggle_connection)
        row.addWidget(self.connect_button)
        return group

    def _build_control_group(self) -> QGroupBox:
        group = QGroupBox("CONTROL")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)

        channel_label = QLabel("Channel")
        channel_label.setObjectName("fieldLabel")
        layout.addWidget(channel_label, 0, 0)
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 8)
        self.channel_spin.setFixedWidth(80)
        self.channel_spin.valueChanged.connect(self.request_channel)
        layout.addWidget(self.channel_spin, 0, 1, Qt.AlignmentFlag.AlignLeft)

        mode_label = QLabel("Mode")
        mode_label.setObjectName("fieldLabel")
        layout.addWidget(mode_label, 1, 0)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode in ("ACC", "APC"):
            button = QPushButton(mode)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda _checked, m=mode: self.request_mode.emit(m))
            mode_row.addWidget(button)
            self.mode_buttons[mode] = button
        mode_row.addStretch()
        layout.addLayout(mode_row, 1, 1)

        self.setpoint_label = QLabel("Setpoint")
        self.setpoint_label.setObjectName("fieldLabel")
        layout.addWidget(self.setpoint_label, 2, 0)
        setpoint_row = QHBoxLayout()
        setpoint_row.setSpacing(8)
        self.setpoint_spin = QDoubleSpinBox()
        self.setpoint_spin.setRange(0, 2000)
        self.setpoint_spin.setDecimals(2)
        self.setpoint_spin.setMinimumWidth(130)
        setpoint_row.addWidget(self.setpoint_spin)
        self.apply_setpoint_button = QPushButton("Apply")
        self.apply_setpoint_button.setFixedWidth(90)
        self.apply_setpoint_button.clicked.connect(
            lambda: self.request_setpoint.emit(self.setpoint_spin.value())
        )
        setpoint_row.addWidget(self.apply_setpoint_button)
        setpoint_row.addStretch()
        layout.addLayout(setpoint_row, 2, 1)

        self.limits_label = QLabel("")
        self.limits_label.setObjectName("fieldLabel")
        layout.addWidget(self.limits_label, 3, 1)

        self.output_button = QPushButton("Enable Output")
        self.output_button.setObjectName("primary")
        self.output_button.setMinimumHeight(42)
        self.output_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_button.clicked.connect(self.toggle_output)
        layout.addWidget(self.output_button, 4, 0, 1, 2)

        self.unlock_button = QPushButton("Unlock interlock")
        self.unlock_button.clicked.connect(self.request_unlock)
        self.unlock_button.setVisible(False)
        layout.addWidget(self.unlock_button, 5, 0, 1, 2)
        layout.setRowStretch(6, 1)
        return group

    def _build_readings_group(self) -> QGroupBox:
        group = QGroupBox("LIVE READINGS")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        badges = QHBoxLayout()
        badges.setSpacing(8)
        self.output_pill = StatusPill()
        self.output_pill.set_state("Output --", "idle")
        self.interlock_pill = StatusPill()
        self.interlock_pill.set_state("Interlock --", "idle")
        badges.addWidget(self.output_pill)
        badges.addWidget(self.interlock_pill)
        badges.addStretch()
        layout.addLayout(badges)

        tiles = QGridLayout()
        tiles.setSpacing(10)
        self.output_tile = Tile("Output power", "mW")
        self.input_tile = Tile("Input power", "mW")
        self.current_tile = Tile("Pump current", "mA")
        self.temp_tile = Tile("Case temp", "°C")
        tiles.addWidget(self.output_tile, 0, 0)
        tiles.addWidget(self.input_tile, 0, 1)
        tiles.addWidget(self.current_tile, 1, 0)
        tiles.addWidget(self.temp_tile, 1, 1)
        layout.addLayout(tiles)

        interval_row = QHBoxLayout()
        interval_label = QLabel("Update every")
        interval_label.setObjectName("fieldLabel")
        interval_row.addWidget(interval_label)
        self.interval_combo = QComboBox()
        for text, value in POLL_INTERVALS:
            self.interval_combo.addItem(text, value)
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.setFixedWidth(90)
        self.interval_combo.currentIndexChanged.connect(
            lambda _index: self.request_interval.emit(self.interval_combo.currentData())
        )
        interval_row.addWidget(self.interval_combo)
        interval_row.addStretch()
        layout.addLayout(interval_row)
        layout.addStretch()
        return group

    def _start_worker(self) -> None:
        self.thread = QThread(self)
        self.worker = AmpWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.start)
        self.request_open.connect(self.worker.open_device)
        self.request_close.connect(self.worker.close_device)
        self.request_mode.connect(self.worker.set_mode)
        self.request_setpoint.connect(self.worker.set_setpoint)
        self.request_output.connect(self.worker.set_output)
        self.request_channel.connect(self.worker.set_channel)
        self.request_interval.connect(self.worker.set_poll_interval)
        self.request_unlock.connect(self.worker.unlock_interlock)
        self.request_stop.connect(self.worker.stop)

        self.worker.connected.connect(self.on_connected)
        self.worker.disconnected.connect(self.on_disconnected)
        self.worker.telemetry.connect(self.on_telemetry)
        self.worker.limits.connect(self.on_limits)
        self.worker.command_failed.connect(self.on_command_failed)
        self.worker.poll_failed.connect(self.on_poll_failed)
        self.worker.busy.connect(self.on_busy)

        self.thread.start()

    # -- actions -----------------------------------------------------------

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(sorted(port.device for port in list_ports.comports()))
        if current:
            self.port_combo.setCurrentText(current)
        self.status_message.setText(f"{self.port_combo.count()} serial port(s) found")

    def toggle_connection(self) -> None:
        if self.connected:
            self.request_close.emit()
            return
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No port", "Select or type a serial port first.")
            return
        self.connection_pill.set_state("Connecting...", "warn")
        self.request_channel.emit(self.channel_spin.value())
        self.request_interval.emit(self.interval_combo.currentData())
        self.request_open.emit(port)

    def toggle_output(self) -> None:
        turning_on = not self.output_on
        if turning_on:
            confirm = QMessageBox.question(
                self,
                "Enable laser output",
                f"Enable optical output on channel {self.channel_spin.value()}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        self.request_output.emit(turning_on)

    # -- worker callbacks --------------------------------------------------

    def on_connected(self, caps: Capabilities) -> None:
        self.connected = True
        self.connect_button.setText("Disconnect")
        self._set_button_style(self.connect_button, "")
        self.connection_pill.set_state(f"Connected - {caps.port}", "ok")
        if caps.n_driving_channels:
            self.channel_spin.setMaximum(caps.n_driving_channels)
        for mode, button in self.mode_buttons.items():
            button.setEnabled(not caps.modes or mode in caps.modes)
        self.status_message.setText(
            f"Connected to {caps.port} - {caps.n_driving_channels} channel(s), "
            f"modes: {', '.join(caps.modes) or 'unknown'}"
        )
        self._apply_enabled_state()

    def on_disconnected(self) -> None:
        self.connected = False
        self.output_on = False
        self.connect_button.setText("Connect")
        self._set_button_style(self.connect_button, "primary")
        self.connection_pill.set_state("Disconnected", "idle")
        self.output_pill.set_state("Output --", "idle")
        self.interlock_pill.set_state("Interlock --", "idle")
        self.output_button.setText("Enable Output")
        self._set_button_style(self.output_button, "primary")
        self.unlock_button.setVisible(False)
        for tile in (self.output_tile, self.input_tile, self.current_tile, self.temp_tile):
            tile.set_value("--")
        self.limits_label.setText("")
        self.updated_label.setText("")
        self.status_message.setText("Disconnected")
        self._apply_enabled_state()

    def on_telemetry(self, data: Telemetry) -> None:
        self.output_tile.set_value(_fmt(data.output_mw))
        self.input_tile.set_value(_fmt(data.input_mw))
        self.current_tile.set_value(_fmt(data.current_ma, 1))
        self.temp_tile.set_value(_fmt(data.box_temp_c, 1))

        if data.mode is not None:
            button = self.mode_buttons.get(data.mode)
            if button is not None and not button.isChecked():
                button.setChecked(True)

        self.output_on = data.status == ChannelStatus.ON and data.master == ChannelStatus.ON
        self.output_button.setText("Disable Output" if self.output_on else "Enable Output")
        self._set_button_style(self.output_button, "danger" if self.output_on else "primary")
        if data.status is None:
            self.output_pill.set_state("Output --", "idle")
        elif self.output_on:
            self.output_pill.set_state("Output ON", "ok")
        elif ChannelStatus.BUSY in (data.status, data.master):
            self.output_pill.set_state("Output busy", "warn")
        else:
            self.output_pill.set_state("Output OFF", "idle")

        if data.interlock is None:
            self.interlock_pill.set_state("Interlock --", "idle")
            self.unlock_button.setVisible(False)
        elif data.interlock:
            self.interlock_pill.set_state("Interlock TRIPPED", "error")
            self.unlock_button.setVisible(True)
        else:
            self.interlock_pill.set_state("Interlock clear", "ok")
            self.unlock_button.setVisible(False)

        self.updated_label.setText(f"Updated {datetime.now():%H:%M:%S}")

    def on_limits(self, limits: Limits) -> None:
        unit = "mA" if limits.mode == "ACC" else "mW"
        self.setpoint_label.setText(f"Setpoint ({unit})")
        self.setpoint_spin.blockSignals(True)
        self.setpoint_spin.setRange(limits.min_value, limits.max_value)
        if limits.step > 0:
            self.setpoint_spin.setSingleStep(limits.step)
        if limits.setpoint is not None:
            self.setpoint_spin.setValue(limits.setpoint)
        self.setpoint_spin.blockSignals(False)
        self.limits_label.setText(f"Allowed {limits.min_value:g} - {limits.max_value:g} {unit}")

    def on_command_failed(self, title: str, message: str) -> None:
        if not self.connected:
            self.connection_pill.set_state("Disconnected", "idle")
        self.status_message.setText(f"{title}: {message}")
        QMessageBox.critical(self, title, message)

    def on_poll_failed(self, message: str) -> None:
        self.status_message.setText(f"Read warning: {message}")

    def on_busy(self, busy: bool) -> None:
        self.busy = busy
        self._apply_enabled_state()

    # -- helpers -----------------------------------------------------------

    def _apply_enabled_state(self) -> None:
        live = self.connected and not self.busy
        for widget in (
            self.channel_spin,
            self.setpoint_spin,
            self.apply_setpoint_button,
            self.output_button,
            self.unlock_button,
            *self.mode_buttons.values(),
        ):
            widget.setEnabled(live)
        self.connect_button.setEnabled(not self.busy)
        self.port_combo.setEnabled(not self.connected and not self.busy)
        self.rescan_button.setEnabled(not self.connected and not self.busy)

    def _set_button_style(self, button: QPushButton, name: str) -> None:
        """Swap a button between the default/primary/danger looks."""
        if button.objectName() == name:
            return
        button.setObjectName(name)
        button.style().unpolish(button)
        button.style().polish(button)

    def closeEvent(self, event) -> None:
        self.request_stop.emit()
        self.thread.quit()
        self.thread.wait(3000)
        event.accept()


def _fmt(value: float | None, decimals: int = 2) -> str:
    return "--" if value is None else f"{value:.{decimals}f}"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Amonics AEDFA Control")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
