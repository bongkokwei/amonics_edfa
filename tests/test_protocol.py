from amonics_edfa.protocol import (
    build_query,
    build_set,
    parse_bool,
    parse_float,
    parse_int,
    parse_str,
)


def test_build_query_wraps_path_with_colon_and_question_mark():
    assert build_query("SENS:CUR:CH1") == b":SENS:CUR:CH1?\r\n"


def test_build_set_with_int_value():
    assert build_set("DRIV:ACC:CUR:CH1", 350) == b":DRIV:ACC:CUR:CH1 350\r\n"


def test_build_set_with_float_value():
    assert build_set("THRES:POW:IN:LEV:SET1", -15.0) == b":THRES:POW:IN:LEV:SET1 -15\r\n"


def test_build_set_with_bool_value():
    assert build_set("DRIV:ACC:STAT:CH1", True) == b":DRIV:ACC:STAT:CH1 1\r\n"


def test_build_set_with_string_value():
    assert build_set("MODE:SW:CH1", "ACC") == b":MODE:SW:CH1 ACC\r\n"


def test_parse_float_from_scientific_notation():
    assert parse_float("3.060000e+02\r\n") == 306.0


def test_parse_int():
    assert parse_int("2\r\n") == 2


def test_parse_bool_true():
    assert parse_bool("1\r\n") is True


def test_parse_bool_false():
    assert parse_bool("0\r\n") is False


def test_parse_str_strips_terminator():
    assert parse_str("ACC\r\n") == "ACC"
