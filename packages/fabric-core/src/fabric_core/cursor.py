"""Opaque cursored pagination (D-006).

Cursor payload: base64url(JSON {"o": offset, "h": sha256(filter)[0:8]}).
A cursor whose filter hash mismatches the current request raises
``CursorMismatchError`` so walks stay consistent.
"""

import base64
import binascii
import hashlib
import json
from typing import Any

_FILTER_KEYS = ("domain",)


class CursorMismatchError(ValueError):
    pass


def filters_hash(filters: dict[str, Any]) -> str:
    canonical = json.dumps({k: filters.get(k) for k in _FILTER_KEYS}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:8]


def encode_cursor(offset: int, filters: dict[str, Any]) -> str | None:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    payload = json.dumps({"o": offset, "h": filters_hash(filters)}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(cursor: str | None, filters: dict[str, Any]) -> int:
    if not cursor:
        return 0
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        offset, fhash = int(payload["o"]), str(payload["h"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise CursorMismatchError(f"malformed cursor: {cursor!r}") from exc
    if fhash != filters_hash(filters):
        raise CursorMismatchError("cursor was issued for a different filter set; restart the walk")
    if offset < 0:
        raise CursorMismatchError("cursor offset out of range")
    return offset
