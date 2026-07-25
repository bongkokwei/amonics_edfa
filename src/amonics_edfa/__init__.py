"""Python driver for Amonics AEDFA erbium-doped fibre amplifiers."""

import logging

from .driver import AEDFA, ChannelStatus
from .exceptions import AEDFACommandError, AEDFAError, AEDFAProtocolError, AEDFATimeoutError

# Library code only emits records; the application decides where they go.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AEDFA",
    "ChannelStatus",
    "AEDFAError",
    "AEDFATimeoutError",
    "AEDFACommandError",
    "AEDFAProtocolError",
]
