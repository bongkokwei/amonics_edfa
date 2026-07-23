"""Exception hierarchy for the Amonics AEDFA driver."""


class AEDFAError(Exception):
    """Base exception for all Amonics AEDFA driver errors."""


class AEDFATimeoutError(AEDFAError):
    """Raised when the device does not reply within the configured timeout."""


class AEDFACommandError(AEDFAError):
    """Raised when a command references a channel or mode the device does not support."""
