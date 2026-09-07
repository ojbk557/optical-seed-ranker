from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .csv_safety import (
    TEXT_ENCODING_FIELD,
    TEXT_ENCODING_VALUE,
    restore_spreadsheet_text,
    spreadsheet_safe_path,
    spreadsheet_safe_text,
)
from .models import SeedRecord

SEED_FIELDS = (*SeedRecord.__dataclass_fields__.keys(), TEXT_ENCODING_FIELD)
TEXT_FIELDS = (
    "seed_id",
    "lens_type",
    "reference",
    "conjugate",
    "source",
    "provider",
)


def write_seed_index(seeds: Iterable[SeedRecord], path: str | Path) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_FIELDS)
        writer.writeheader()
        for seed in seeds:
            row = asdict(seed)
            for field in TEXT_FIELDS:
                row[field] = spreadsheet_safe_text(str(row[field]))
            if row["source_path"]:
                row["source_path"] = spreadsheet_safe_path(str(row["source_path"]))
            row[TEXT_ENCODING_FIELD] = TEXT_ENCODING_VALUE
            writer.writerow(row)
            count += 1
    return count


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _optional_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def read_seed_index(path: str | Path) -> list[SeedRecord]:
    input_path = Path(path)
    seeds: list[SeedRecord] = []
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            encoded = row.get(TEXT_ENCODING_FIELD) == TEXT_ENCODING_VALUE

            def text(field: str, default: str = "") -> str:
                return restore_spreadsheet_text(
                    row.get(field) or default,
                    encoded=encoded,
                )

            seeds.append(
                SeedRecord(
                    seed_id=text("seed_id"),
                    lens_type=text("lens_type"),
                    focal_length_mm=float(row["focal_length_mm"]),
                    f_number=float(row["f_number"]),
                    full_fov_deg=float(row["full_fov_deg"]),
                    surface_count=int(row["surface_count"]),
                    element_count=int(row["element_count"]),
                    reference=text("reference"),
                    conjugate=text("conjugate", "infinity"),
                    source=text("source", "unknown"),
                    # An index is always the local provider trust domain. Do not
                    # let an external CSV impersonate the bundled patent source.
                    provider="local",
                    source_path=row.get("source_path") or None,
                    wavelength_min_nm=_optional_float(row.get("wavelength_min_nm")),
                    wavelength_max_nm=_optional_float(row.get("wavelength_max_nm")),
                    total_track_mm=_optional_float(row.get("total_track_mm")),
                    back_focal_length_mm=_optional_float(
                        row.get("back_focal_length_mm")
                    ),
                    asphere_count=_optional_int(row.get("asphere_count")),
                    obsolete_glass_count=_optional_int(
                        row.get("obsolete_glass_count")
                    ),
                )
            )
    return seeds
