from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..models import SeedRecord


@dataclass(frozen=True, slots=True)
class LensLibraryIndexResult:
    seeds: tuple[SeedRecord, ...]
    skipped_lines: int
    warnings: tuple[str, ...]


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: str) -> int | None:
    number = _as_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def parse_lenslibrary_properties(path: str | Path) -> LensLibraryIndexResult:
    """Parse LensLibrary's fixed-column property list.

    V0.1 intentionally indexes only the image-space table rows with complete
    numeric F/#, field, surface, and element values. Other sections are kept
    out of the ranking instead of being guessed into the wrong schema.
    """

    source_path = Path(path)
    seeds: list[SeedRecord] = []
    warnings: list[str] = []
    skipped = 0
    section = "image_space"

    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("-"):
                continue
            if line == "image_space":
                section = "image_space"
                continue
            if line == "object_space" or line.startswith("object_space "):
                section = "object_space"
                continue
            if line.startswith("filename"):
                continue

            columns = re.split(r"\s{2,}", line)
            if section != "image_space" or len(columns) != 8:
                skipped += 1
                continue

            seed_id, lens_type, focal, f_number, ffov, surfaces, elements, reference = columns
            numeric = (
                _as_float(focal),
                _as_float(f_number),
                _as_float(ffov),
                _as_int(surfaces),
                _as_int(elements),
            )
            if any(value is None for value in numeric):
                skipped += 1
                warnings.append(
                    f"line {line_number}: skipped incomplete row for {seed_id}"
                )
                continue

            focal_mm, f_no, full_fov_deg, surface_count, element_count = numeric
            assert focal_mm is not None
            assert f_no is not None
            assert full_fov_deg is not None
            assert surface_count is not None
            assert element_count is not None

            zmx_candidate = source_path.parent / "zemax_files" / f"{seed_id}.zmx"
            seeds.append(
                SeedRecord(
                    seed_id=seed_id,
                    lens_type=lens_type,
                    focal_length_mm=focal_mm,
                    f_number=f_no,
                    full_fov_deg=full_fov_deg,
                    surface_count=surface_count,
                    element_count=element_count,
                    reference=reference,
                    conjugate="infinity",
                    source="LensLibrary",
                    source_path=str(zmx_candidate) if zmx_candidate.exists() else None,
                )
            )

    if not seeds:
        raise ValueError(f"no complete image-space seed rows found in {source_path}")

    return LensLibraryIndexResult(
        seeds=tuple(seeds), skipped_lines=skipped, warnings=tuple(warnings)
    )
