"""Null-safe dictionary access.

Python's dict.get(key, default) returns the default ONLY when the key is
absent.  When the key exists with a None value, .get() returns None — not
the default.  This is a common source of bugs when reading JSON data where
fields may be explicitly null.

    >>> d = {"pillar": None}
    >>> d.get("pillar", 1)   # returns None, NOT 1
    >>> safe_get(d, "pillar", 1)  # returns 1

Use safe_get() whenever the data source is external JSON (weekly plan,
content log, pin schedule, API responses, Sheet data).
"""

from typing import TypeVar

T = TypeVar("T")


def safe_get(d: dict, key: str, default: T = None) -> T:  # type: ignore[assignment]
    """Return d[key] if present and not None, else default.

    Drop-in replacement for ``d.get(key, default)`` that also handles
    the case where the key exists with a ``None`` value.
    """
    value = d.get(key)
    return value if value is not None else default
