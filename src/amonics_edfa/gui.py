"""Minimal PyQt6 GUI for switching an Amonics AEDFA channel between ACC and APC mode."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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
        self.port_edit = QLineEdit("COM1")
        port_row.addWidget(self.port_edit)
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        port_row.addWidget(self.connect_button)
        layout.addLayout(port_row)

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

        self.status_label = QLabel("Not connected")
        layout.addWidget(self.status_label)

    def toggle_connection(self) -> None:
        if self.amp is None:
            try:
                self.amp = AEDFA(port=self.port_edit.text())
                self.amp.open()
            except (AEDFAError, OSError) as exc:
                self.amp = None
                QMessageBox.critical(self, "Connection failed", str(exc))
                return
            self.connect_button.setText("Disconnect")
            self.apply_button.setEnabled(True)
            self.refresh_mode()
        else:
            self.amp.close()
            self.amp = None
            self.connect_button.setText("Connect")
            self.apply_button.setEnabled(False)
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
