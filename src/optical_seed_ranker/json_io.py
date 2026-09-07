from __future__ import annotations

import json
from typing import Any


def standard_json_dumps(payload: Any, **kwargs: Any) -> str:
    """Serialize JSON while rejecting JavaScript-only NaN/Infinity tokens."""

    return json.dumps(payload, allow_nan=False, **kwargs)


def ensure_standard_json(payload: Any) -> Any:
    """Validate a structured result before an external serializer receives it."""

    standard_json_dumps(payload)
    return payload
