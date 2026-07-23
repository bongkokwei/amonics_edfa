from unittest.mock import MagicMock, patch

import pytest

from amonics_edfa import AEDFA

DISCOVERY_RESPONSES = [
    b"ACC\r\n",
    b"2\r\n",
    b"2\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"1\r\n",
    b"2\r\n",
    b"1\r\n",
]


def pytest_addoption(parser):
    parser.addoption(
        "--hw",
        action="store_true",
        default=False,
        help="run tests marked 'hw' against real hardware",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--hw"):
        return
    skip_hw = pytest.mark.skip(reason="requires physical AEDFA; run with --hw")
    for item in items:
        if "hw" in item.keywords:
            item.add_marker(skip_hw)


@pytest.fixture
def mock_serial():
    """Patch amonics_edfa.driver.serial.Serial; readline is pre-loaded with capability
    discovery responses matching a single-mode, single-channel-input, dual-current device."""
    with patch("amonics_edfa.driver.serial.Serial") as mock_serial_cls:
        instance = MagicMock()
        instance.readline.side_effect = list(DISCOVERY_RESPONSES)
        mock_serial_cls.return_value = instance
        yield instance


@pytest.fixture
def opened_device(mock_serial):
    """An AEDFA already open()'d against the mocked serial port."""
    device = AEDFA(port="COM8")
    device.open()
    return device
