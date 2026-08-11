from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import TargetSpec


def load_spec(path: str | Path) -> TargetSpec:
    spec_path = Path(path)
    with spec_path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"spec must be a YAML object: {spec_path}")
    return TargetSpec.from_mapping(raw)
