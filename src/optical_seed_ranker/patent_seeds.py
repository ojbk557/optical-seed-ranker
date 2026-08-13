from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .models import SeedRecord

DEFAULT_PATENT_SEEDS_PATH = Path(__file__).resolve().parent / "data" / "uv_patent_seeds.yaml"

EVIDENCE_FIELDS = (
    "title",
    "evidence_level",
    "focal_length_basis",
    "f_number_basis",
    "full_fov_basis",
    "topology",
    "published_evidence",
    "known_gaps",
)


def _positive(name: str, value: float) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _load_dataset(path: str | Path = DEFAULT_PATENT_SEEDS_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("seeds"), list):
        raise ValueError("patent seed dataset must contain a seeds list")
    return payload


def load_patent_seed_records(
    path: str | Path = DEFAULT_PATENT_SEEDS_PATH,
) -> list[SeedRecord]:
    records: list[SeedRecord] = []
    for item in _load_dataset(path)["seeds"]:
        records.append(
            SeedRecord(
                seed_id=str(item["seed_id"]),
                lens_type=str(item["lens_type"]),
                conjugate=str(item.get("conjugate", "infinity")),
                focal_length_mm=float(item["focal_length_mm"]),
                f_number=float(item["f_number"]),
                full_fov_deg=float(item["full_fov_deg"]),
                surface_count=int(item["surface_count"]),
                element_count=int(item["element_count"]),
                reference=str(item["reference"]),
                source=str(item.get("source", "curated_patent")),
                wavelength_min_nm=(
                    float(item["wavelength_min_nm"])
                    if item.get("wavelength_min_nm") is not None
                    else None
                ),
                wavelength_max_nm=(
                    float(item["wavelength_max_nm"])
                    if item.get("wavelength_max_nm") is not None
                    else None
                ),
                asphere_count=(
                    int(item["asphere_count"])
                    if item.get("asphere_count") is not None
                    else None
                ),
            )
        )
    return records


def load_patent_seed_evidence(
    path: str | Path = DEFAULT_PATENT_SEEDS_PATH,
) -> dict[str, dict[str, Any]]:
    """Return auditable patent evidence that is intentionally not part of scoring."""

    evidence: dict[str, dict[str, Any]] = {}
    for item in _load_dataset(path)["seeds"]:
        seed_id = str(item["seed_id"])
        evidence[seed_id] = {
            field: deepcopy(item[field])
            for field in EVIDENCE_FIELDS
            if field in item
        }
    return evidence


def _scale_surface(surface: dict[str, Any], scale_factor: float) -> dict[str, Any]:
    scaled = deepcopy(surface)
    for field in ("radius_mm", "thickness_to_next_mm", "semi_diameter_mm"):
        if scaled.get(field) is not None:
            scaled[field] = round(float(scaled[field]) * scale_factor, 9)
    coefficients = scaled.get("even_asphere_coefficients_mm")
    if isinstance(coefficients, dict):
        scaled_coefficients: dict[str, float] = {}
        for name, value in coefficients.items():
            order = int(str(name).lstrip("a"))
            # If every length is scaled by s, A_n scales by s^(1-n).
            scaled_coefficients[str(name)] = float(value) * scale_factor ** (1 - order)
        scaled["even_asphere_coefficients_mm"] = scaled_coefficients
    return scaled


def get_patent_seed_structure(
    *,
    seed_id: str,
    path: str | Path = DEFAULT_PATENT_SEEDS_PATH,
    scale_to_focal_length_mm: float | None = None,
) -> dict[str, Any]:
    dataset = _load_dataset(path)
    matches = [item for item in dataset["seeds"] if item.get("seed_id") == seed_id]
    if not matches:
        raise KeyError(f"seed_id {seed_id!r} is not present in the patent dataset")
    if len(matches) > 1:
        raise ValueError(f"seed_id {seed_id!r} is not unique in the patent dataset")
    item = matches[0]
    prescription = item.get("prescription")
    if not isinstance(prescription, dict) or not prescription.get("surfaces"):
        raise FileNotFoundError(
            f"seed_id {seed_id!r} has metadata but no transcribed prescription"
        )

    scale_factor = 1.0
    if scale_to_focal_length_mm is not None:
        target_focal_length = _positive(
            "scale_to_focal_length_mm", scale_to_focal_length_mm
        )
        scale_factor = target_focal_length / float(item["focal_length_mm"])

    scaled_prescription = deepcopy(prescription)
    scaled_prescription["surfaces"] = [
        _scale_surface(surface, scale_factor)
        for surface in prescription["surfaces"]
    ]
    return {
        "evidence_level": item["evidence_level"],
        "seed": {
            "seed_id": item["seed_id"],
            "title": item["title"],
            "reference": item["reference"],
            "source": item["source"],
            "focal_length_mm": item["focal_length_mm"],
            "focal_length_basis": item["focal_length_basis"],
            "f_number": item["f_number"],
            "f_number_basis": item["f_number_basis"],
            "full_fov_deg": item["full_fov_deg"],
            "full_fov_basis": item["full_fov_basis"],
            "wavelength_range_nm": [
                item["wavelength_min_nm"],
                item["wavelength_max_nm"],
            ],
            "topology": item["topology"],
        },
        "scaling": {
            "target_focal_length_mm": scale_to_focal_length_mm,
            "scale_factor": round(scale_factor, 9),
            "invariant_warning": (
                "Uniform geometric scaling does not improve F-number, field angle, "
                "spectrum, distortion, or aberration balance."
            ),
        },
        "prescription": scaled_prescription,
        "published_evidence": item.get("published_evidence", {}),
        "warnings": list(item.get("known_gaps", [])),
    }
