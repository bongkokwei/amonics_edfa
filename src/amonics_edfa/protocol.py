"""Command framing and response parsing for the Amonics AEDFA SCPI-style protocol."""

from __future__ import annotations

from .exceptions import AEDFAProtocolError


def _format_value(value: bool | int | float | str) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def build_query(path: str) -> bytes:
    """Build the wire bytes for a query, e.g. path='SENS:CUR:CH1' -> b':SENS:CUR:CH1?\\r\\n'."""
    return f":{path}?\r\n".encode("ascii")


def build_set(path: str, value: bool | int | float | str) -> bytes:
    """Build the wire bytes for a set command, e.g. path='DRIV:ACC:CUR:CH1', value=350
    -> b':DRIV:ACC:CUR:CH1 350\\r\\n'."""
    return f":{path} {_format_value(value)}\r\n".encode("ascii")


def parse_float(raw: str) -> float:
    """Parse a decimal or scientific-notation response, e.g. '3.060000e+02\\r\\n' -> 306.0."""
    stripped = raw.strip()
    try:
        return float(stripped)
    except ValueError as exc:
        raise AEDFAProtocolError(f"Expected a decimal number, got {stripped!r}") from exc


def parse_int(raw: str) -> int:
    """Parse a base-10 integer response, e.g. '2\\r\\n' -> 2."""
    stripped = raw.strip()
    try:
        return int(stripped)
    except ValueError as exc:
        raise AEDFAProtocolError(f"Expected an integer, got {stripped!r}") from exc


def parse_bool(raw: str) -> bool:
    """Parse a 0/1 flag response, e.g. '1\\r\\n' -> True."""
    return raw.strip() == "1"


def parse_str(raw: str) -> str:
    """Parse an ASCII string response, stripping the trailing terminator, e.g. 'ACC\\r\\n' -> 'ACC'."""
    return raw.strip()
