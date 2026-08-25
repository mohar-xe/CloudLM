import pytest

from fabric_core.cursor import CursorMismatchError, decode_cursor, encode_cursor


def test_roundtrip() -> None:
    cursor = encode_cursor(500, {"domain": "compute"})
    assert decode_cursor(cursor, {"domain": "compute"}) == 500


def test_none_cursor_starts_at_zero() -> None:
    assert decode_cursor(None, {"domain": None}) == 0
    assert decode_cursor("", {"domain": None}) == 0


def test_filter_mismatch_rejected() -> None:
    cursor = encode_cursor(100, {"domain": None})
    with pytest.raises(CursorMismatchError, match="different filter set"):
        decode_cursor(cursor, {"domain": "compute"})


@pytest.mark.parametrize("bad", ["not-base64!!", "eyJvIjotMX0", "e30"])
def test_malformed_cursors_rejected(bad: str) -> None:
    with pytest.raises(CursorMismatchError, match="malformed|out of range"):
        decode_cursor(bad, {"domain": None})


def test_negative_offset_encode_rejected() -> None:
    with pytest.raises(ValueError):
        encode_cursor(-1, {"domain": None})
