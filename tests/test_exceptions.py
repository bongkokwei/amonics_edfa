from amonics_edfa.exceptions import (
    AEDFACommandError,
    AEDFAError,
    AEDFAProtocolError,
    AEDFATimeoutError,
)


def test_timeout_error_is_aedfa_error():
    assert issubclass(AEDFATimeoutError, AEDFAError)


def test_command_error_is_aedfa_error():
    assert issubclass(AEDFACommandError, AEDFAError)


def test_protocol_error_is_aedfa_error():
    assert issubclass(AEDFAProtocolError, AEDFAError)


def test_aedfa_error_is_exception():
    assert issubclass(AEDFAError, Exception)
