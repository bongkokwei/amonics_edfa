"""Minimal PyQt6 GUI for switching an Amonics AEDFA channel between ACC and APC mode."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from .driver import AEDFA
from .exceptions import AEDFAError


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Amonics AEDFA - ACC/APC Mode")
        self.amp: AEDFA | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        port_row.addWidget(self.port_combo)
        self.refresh_ports_button = QPushButton("Refresh")
        self.refresh_ports_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.refresh_ports_button)
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        port_row.addWidget(self.connect_button)
        layout.addLayout(port_row)
        self.refresh_ports()

        channel_row = QHBoxLayout()
        channel_row.addWidget(QLabel("Channel:"))
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 8)
        channel_row.addWidget(self.channel_spin)
        layout.addLayout(channel_row)

        mode_row = QHBoxLayout()
        self.acc_radio = QRadioButton("ACC")
        self.apc_radio = QRadioButton("APC")
        self.acc_radio.setChecked(True)
        mode_row.addWidget(self.acc_radio)
        mode_row.addWidget(self.apc_radio)
        layout.addLayout(mode_row)

        self.apply_button = QPushButton("Apply Mode")
        self.apply_button.clicked.connect(self.apply_mode)
        self.apply_button.setEnabled(False)
        layout.addWidget(self.apply_button)

        setpoint_row = QHBoxLayout()
        setpoint_row.addWidget(QLabel("Setpoint (mA/mW):"))
        self.setpoint_spin = QDoubleSpinBox()
        self.setpoint_spin.setRange(0, 2000)
        self.setpoint_spin.setDecimals(2)
        setpoint_row.addWidget(self.setpoint_spin)
        self.set_setpoint_button = QPushButton("Set")
        self.set_setpoint_button.clicked.connect(self.set_setpoint)
        self.set_setpoint_button.setEnabled(False)
        setpoint_row.addWidget(self.set_setpoint_button)
        layout.addLayout(setpoint_row)

        readings_row = QHBoxLayout()
        readings_row.addWidget(QLabel("Current (mA):"))
        self.current_label = QLabel("--")
        readings_row.addWidget(self.current_label)
        readings_row.addWidget(QLabel("Output power (mW):"))
        self.power_label = QLabel("--")
        readings_row.addWidget(self.power_label)
        self.refresh_readings_button = QPushButton("Refresh")
        self.refresh_readings_button.clicked.connect(self.refresh_readings)
        self.refresh_readings_button.setEnabled(False)
        readings_row.addWidget(self.refresh_readings_button)
        layout.addLayout(readings_row)

        self.status_label = QLabel("Not connected")
        layout.addWidget(self.status_label)

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(sorted(port.device for port in list_ports.comports()))
        if current:
            self.port_combo.setCurrentText(current)

    def toggle_connection(self) -> None:
        if self.amp is None:
            try:
                self.amp = AEDFA(port=self.port_combo.currentText())
                self.amp.open()
            except (AEDFAError, OSError) as exc:
                self.amp = None
                QMessageBox.critical(self, "Connection failed", str(exc))
                return
            self.connect_button.setText("Disconnect")
            self.apply_button.setEnabled(True)
            self.set_setpoint_button.setEnabled(True)
            self.refresh_readings_button.setEnabled(True)
            self.refresh_mode()
            self.refresh_readings()
        else:
            self.amp.close()
            self.amp = None
            self.connect_button.setText("Connect")
            self.apply_button.setEnabled(False)
            self.set_setpoint_button.setEnabled(False)
            self.refresh_readings_button.setEnabled(False)
            self.current_label.setText("--")
            self.power_label.setText("--")
            self.status_label.setText("Not connected")

    def refresh_mode(self) -> None:
        if self.amp is None:
            return
        try:
            mode = self.amp.get_mode(channel=self.channel_spin.value())
        except AEDFAError as exc:
            QMessageBox.critical(self, "Read failed", str(exc))
            return
        self.status_label.setText(f"Current mode: {mode}")
        self.acc_radio.setChecked(mode == "ACC")
        self.apc_radio.setChecked(mode == "APC")

    def apply_mode(self) -> None:
        if self.amp is None:
            return
        mode = "APC" if self.apc_radio.isChecked() else "ACC"
        try:
            self.amp.set_mode(mode, channel=self.channel_spin.value())
        except AEDFAError as exc:
            QMessageBox.critical(self, "Mode switch failed", str(exc))
            return
        self.refresh_mode()

    def set_setpoint(self) -> None:
        if self.amp is None:
            return
        try:
            self.amp.set_current_setpoint(
                channel=self.channel_spin.value(), value_ma=self.setpoint_spin.value()
            )
        except AEDFAError as exc:
            QMessageBox.critical(self, "Setpoint failed", str(exc))

    def refresh_readings(self) -> None:
        if self.amp is None:
            return
        channel = self.channel_spin.value()
        try:
            self.current_label.setText(f"{self.amp.get_current_ma(channel=channel):.2f}")
        except AEDFAError:
            self.current_label.setText("N/A")
        try:
            self.power_label.setText(f"{self.amp.get_output_power_mw(channel=channel):.2f}")
        except AEDFAError:
            self.power_label.setText("N/A")

    def closeEvent(self, event) -> None:
        if self.amp is not None:
            self.amp.close()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
