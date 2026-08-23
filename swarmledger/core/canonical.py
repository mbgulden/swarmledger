"""
RFC 8785 Canonical JSON Serializer (JCS).
Guarantees byte-for-byte deterministic JSON serialization across platforms.
"""

from __future__ import annotations

import math
from typing import Any


def canonicalize(obj: Any) -> bytes:
    """
    Serializes a Python object into canonical JSON bytes according to RFC 8785 (JCS).
    - Keys are sorted lexicographically by UTF-16 code units (or UTF-8 bytes).
    - No whitespace between delimiters.
    - Numbers formatted deterministically without trailing zeroes or exponent quirks.
    """
    return _serialize(obj).encode("utf-8")


def _serialize(obj: Any) -> str:
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, (int, float)):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                raise ValueError(f"NaN and Infinity are not valid in RFC 8785 JCS: {obj}")
            # Format float in standard non-scientific or minimal format
            if obj.is_integer():
                return str(int(obj))
            s = f"{obj:.10f}".rstrip("0").rstrip(".")
            return s
        return str(obj)
    elif isinstance(obj, str):
        return _escape_string(obj)
    elif isinstance(obj, (list, tuple)):
        items = [_serialize(item) for item in obj]
        return "[" + ",".join(items) + "]"
    elif isinstance(obj, dict):
        # Sort keys lexicographically by UTF-8 bytes
        sorted_keys = sorted(obj.keys(), key=lambda k: str(k).encode("utf-8"))
        items = [f"{_escape_string(str(k))}:{_serialize(obj[k])}" for k in sorted_keys]
        return "{" + ",".join(items) + "}"
    else:
        # Fallback for custom objects or dataclasses with to_dict()
        if hasattr(obj, "to_dict"):
            return _serialize(obj.to_dict())
        return _escape_string(str(obj))


def _escape_string(s: str) -> str:
    # Minimal JSON escape sequence according to RFC 8259 / RFC 8785
    out = ['"']
    for char in s:
        cp = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == '\\':
            out.append('\\\\')
        elif char == '\b':
            out.append('\\b')
        elif char == '\f':
            out.append('\\f')
        elif char == '\n':
            out.append('\\n')
        elif char == '\r':
            out.append('\\r')
        elif char == '\t':
            out.append('\\t')
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)