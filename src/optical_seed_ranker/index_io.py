from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import SeedRecord


SEED_FIELDS = tuple(SeedRecord.__dataclass_fields__.keys())


def write_seed_index(seeds: Iterable[SeedRecord], path: str | Path) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_FIELDS)
        writer.writeheader()
        for seed in seeds:
            writer.writerow(asdict(seed))
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
            seeds.append(
                SeedRecord(
                    seed_id=row["seed_id"],
                    lens_type=row["lens_type"],
                    focal_length_mm=float(row["focal_length_mm"]),
                    f_number=float(row["f_number"]),
                    full_fov_deg=float(row["full_fov_deg"]),
                    surface_count=int(row["surface_count"]),
                    element_count=int(row["element_count"]),
                    reference=row["reference"],
                    conjugate=row.get("conjugate") or "infinity",
                    source=row.get("source") or "unknown",
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
