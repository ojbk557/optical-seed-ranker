from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import hypot, isfinite, radians, tan
from pathlib import Path
from typing import Any, Iterable, Mapping

from .identifiers import (
    LOCAL_PROVIDER,
    PATENT_PROVIDER,
    make_seed_handle,
    provider_for_seed,
    seed_handle,
)
from .index_io import read_seed_index
from .json_io import ensure_standard_json, standard_json_dumps
from .models import ScoreBreakdown, SeedRecord, TargetSpec
from .scoring import rank_seeds
from .zmx import parse_zmx_prescription, prescription_payload


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


def _percent(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{name} must be finite and between 0 and 100")
    return value


def _display_number(value: float) -> str:
    return format(value, ".15g")


def derive_rectilinear_target(
    *,
    field_x_full_deg: float,
    field_y_full_deg: float,
    detector_diameter_mm: float,
    entrance_pupil_min_mm: float,
) -> dict[str, float]:
    """Derive a consistent rectilinear target from field, image circle, and pupil.

    The rectangular field corners are assumed to land on the circular detector edge.
    This is the strict interpretation of an ``X by Y`` angular field specification.
    """

    field_x_full_deg = _positive("field_x_full_deg", field_x_full_deg)
    field_y_full_deg = _positive("field_y_full_deg", field_y_full_deg)
    if field_x_full_deg >= 180 or field_y_full_deg >= 180:
        raise ValueError("full field angles must be below 180 degrees")
    detector_diameter_mm = _positive("detector_diameter_mm", detector_diameter_mm)
    entrance_pupil_min_mm = _positive(
        "entrance_pupil_min_mm", entrance_pupil_min_mm
    )

    x_tangent = tan(radians(field_x_full_deg / 2.0))
    y_tangent = tan(radians(field_y_full_deg / 2.0))
    corner_tangent = hypot(x_tangent, y_tangent)
    if not isfinite(corner_tangent) or corner_tangent <= 0:
        raise ValueError("field angles must produce a finite rectilinear projection")
    detector_radius_mm = detector_diameter_mm / 2.0
    focal_length_mm = detector_radius_mm / corner_tangent
    image_width_mm = 2.0 * focal_length_mm * x_tangent
    image_height_mm = 2.0 * focal_length_mm * y_tangent
    f_number_max = focal_length_mm / entrance_pupil_min_mm

    derived = {
        "focal_length_mm": focal_length_mm,
        "f_number_max": f_number_max,
        "image_width_mm": image_width_mm,
        "image_height_mm": image_height_mm,
        "image_surface_semi_diameter_mm": detector_radius_mm,
        "entrance_pupil_min_mm": entrance_pupil_min_mm,
    }
    if any(not isfinite(value) or value <= 0 for value in derived.values()):
        raise ValueError("derived target values must be finite and greater than zero")
    return ensure_standard_json(derived)


def build_uv_target_spec(
    *,
    field_x_full_deg: float,
    field_y_full_deg: float,
    detector_diameter_mm: float,
    entrance_pupil_min_mm: float,
    wavelength_min_nm: float,
    wavelength_max_nm: float,
    minimum_mtf_nyquist: float,
) -> tuple[TargetSpec, dict[str, float]]:
    wavelength_min_nm = _positive("wavelength_min_nm", wavelength_min_nm)
    wavelength_max_nm = _positive("wavelength_max_nm", wavelength_max_nm)
    if wavelength_max_nm <= wavelength_min_nm:
        raise ValueError("wavelength_max_nm must exceed wavelength_min_nm")
    minimum_mtf_nyquist = float(minimum_mtf_nyquist)
    if not isfinite(minimum_mtf_nyquist) or not 0 <= minimum_mtf_nyquist <= 1:
        raise ValueError("minimum_mtf_nyquist must be finite and between 0 and 1")

    derived = derive_rectilinear_target(
        field_x_full_deg=field_x_full_deg,
        field_y_full_deg=field_y_full_deg,
        detector_diameter_mm=detector_diameter_mm,
        entrance_pupil_min_mm=entrance_pupil_min_mm,
    )
    midpoint_nm = (wavelength_min_nm + wavelength_max_nm) / 2.0
    spec = TargetSpec(
        name="wide_field_uv_image_intensifier",
        conjugate="infinity",
        architecture="camera",
        focal_length_mm=derived["focal_length_mm"],
        f_number=derived["f_number_max"],
        field_x_full_deg=float(field_x_full_deg),
        field_y_full_deg=float(field_y_full_deg),
        image_width_mm=derived["image_width_mm"],
        image_height_mm=derived["image_height_mm"],
        image_surface_semi_diameter_mm=derived[
            "image_surface_semi_diameter_mm"
        ],
        wavelengths_nm=(wavelength_min_nm, midpoint_nm, wavelength_max_nm),
        mtf_frequency_lpmm=None,
        minimum_mtf=minimum_mtf_nyquist,
        preferred_element_range=(4, 14),
        metadata_weights={
            "f_number": 0.35,
            "full_fov": 0.30,
            "architecture": 0.15,
            "spectrum": 0.10,
            "geometry": 0.00,
            "complexity": 0.10,
        },
        asymmetric_penalty=3.0,
    )
    return spec, derived


def _spectrum_status(seed: SeedRecord, spec: TargetSpec) -> str:
    if seed.wavelength_min_nm is None or seed.wavelength_max_nm is None:
        return "unknown"
    if (
        seed.wavelength_min_nm <= min(spec.wavelengths_nm)
        and seed.wavelength_max_nm >= max(spec.wavelengths_nm)
    ):
        return "metadata_covers_target"
    return "metadata_does_not_cover_target"


def _risk_flags(result: ScoreBreakdown, spec: TargetSpec) -> list[str]:
    seed = result.seed
    flags: list[str] = []
    if seed.f_number > spec.f_number:
        flags.append("seed_is_slower_than_required")
    if seed.full_fov_deg < spec.diagonal_full_field_deg:
        flags.append("seed_field_is_narrower_than_required")
    if seed.full_fov_deg >= 100:
        flags.append("ultra_wide_projection_model_unverified")
    if not 0.25 <= result.scale_factor <= 4.0:
        flags.append("large_geometric_scale_change")
    spectrum_status = _spectrum_status(seed, spec)
    if spectrum_status == "unknown":
        flags.append("uv_material_and_coating_data_missing")
    elif spectrum_status == "metadata_does_not_cover_target":
        flags.append("recorded_spectrum_does_not_cover_uv_target")
    if seed.obsolete_glass_count:
        flags.append("contains_obsolete_glass")
    return flags


def _candidate_payload(
    result: ScoreBreakdown,
    spec: TargetSpec,
    rank: int,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    seed = result.seed
    payload = {
        "rank": rank,
        "seed_id": seed.seed_id,
        "seed_handle": seed_handle(seed),
        "provider": provider_for_seed(seed),
        "lens_type": seed.lens_type,
        "metadata_score": round(result.metadata_score, 3),
        "weighted_engineering_distance": round(result.weighted_distance, 6),
        "scale_factor": round(result.scale_factor, 6),
        "seed": {
            "focal_length_mm": seed.focal_length_mm,
            "f_number": seed.f_number,
            "full_fov_deg": seed.full_fov_deg,
            "surface_count": seed.surface_count,
            "element_count": seed.element_count,
        },
        "scaled_estimate": {
            "focal_length_mm": round(
                seed.focal_length_mm * result.scale_factor, 6
            ),
            "entrance_pupil_mm_at_seed_f_number": round(
                spec.focal_length_mm / seed.f_number, 6
            ),
        },
        "spectrum_status": _spectrum_status(seed, spec),
        "risk_flags": _risk_flags(result, spec),
        "score_components": {
            name: round(value, 3)
            for name, value in result.component_scores.items()
        },
        "source": {
            "provider": seed.source,
            "reference": seed.reference,
        },
    }
    if evidence:
        payload["evidence"] = dict(evidence)
    else:
        payload["evidence"] = {
            "evidence_level": "index_metadata_only",
            "known_gaps": [
                "No source-specific performance evidence is attached to this index row."
            ],
        }
    return payload


def search_uv_seed_structures(
    *,
    seeds: Iterable[SeedRecord],
    evidence_by_seed: Mapping[str, Mapping[str, Any]] | None = None,
    field_x_full_deg: float,
    field_y_full_deg: float,
    detector_diameter_mm: float,
    entrance_pupil_min_mm: float,
    wavelength_min_nm: float,
    wavelength_max_nm: float,
    minimum_mtf_nyquist: float = 0.4,
    maximum_distortion_percent: float = 3.0,
    minimum_relative_illumination_percent: float = 60.0,
    require_documented_spectral_overlap: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    try:
        parsed_top_k = int(top_k)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError("top_k must be an integer between 1 and 20") from error
    if isinstance(top_k, bool) or parsed_top_k != top_k or not 1 <= parsed_top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    maximum_distortion_percent = _percent(
        "maximum_distortion_percent", maximum_distortion_percent
    )
    minimum_relative_illumination_percent = _percent(
        "minimum_relative_illumination_percent",
        minimum_relative_illumination_percent,
    )
    spec, derived = build_uv_target_spec(
        field_x_full_deg=field_x_full_deg,
        field_y_full_deg=field_y_full_deg,
        detector_diameter_mm=detector_diameter_mm,
        entrance_pupil_min_mm=entrance_pupil_min_mm,
        wavelength_min_nm=wavelength_min_nm,
        wavelength_max_nm=wavelength_max_nm,
        minimum_mtf_nyquist=minimum_mtf_nyquist,
    )
    seed_list = list(seeds)
    seed_id_counts = Counter(seed.seed_id for seed in seed_list)
    evidence_by_seed = evidence_by_seed or {}
    all_ranked = [item for item in rank_seeds(seed_list, spec) if item.eligible]

    def has_documented_spectral_overlap(result: ScoreBreakdown) -> bool:
        seed = result.seed
        return (
            seed.wavelength_min_nm is not None
            and seed.wavelength_max_nm is not None
            and seed.wavelength_max_nm >= wavelength_min_nm
            and seed.wavelength_min_nm <= wavelength_max_nm
        )

    ranked = (
        [item for item in all_ranked if has_documented_spectral_overlap(item)]
        if require_documented_spectral_overlap
        else all_ranked
    )
    selected = ranked[:parsed_top_k]

    def evidence_for(seed: SeedRecord) -> Mapping[str, Any] | None:
        qualified = evidence_by_seed.get(seed_handle(seed))
        if qualified is not None:
            return qualified
        # The patent evidence loader historically returned bare keys. Only bind
        # that legacy form to a patent record when providers collide.
        if provider_for_seed(seed) == PATENT_PROVIDER:
            return evidence_by_seed.get(seed.seed_id)
        if seed_id_counts[seed.seed_id] == 1:
            return evidence_by_seed.get(seed.seed_id)
        return None

    query_fields = {
        "field_x_full_deg": float(field_x_full_deg),
        "field_y_full_deg": float(field_y_full_deg),
        "detector_diameter_mm": float(detector_diameter_mm),
        "entrance_pupil_min_mm": float(entrance_pupil_min_mm),
        "wavelength_min_nm": float(wavelength_min_nm),
        "wavelength_max_nm": float(wavelength_max_nm),
        "minimum_mtf_nyquist": float(minimum_mtf_nyquist),
        "maximum_distortion_percent": maximum_distortion_percent,
        "minimum_relative_illumination_percent": (
            minimum_relative_illumination_percent
        ),
        "require_documented_spectral_overlap": bool(
            require_documented_spectral_overlap
        ),
    }
    query_id = sha256(
        standard_json_dumps(query_fields, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    result_payload = {
        "query_id": query_id,
        "evidence_level": "metadata_topology_shortlist",
        "derived_target": {
            **{name: round(value, 6) for name, value in derived.items()},
            "diagonal_full_field_deg": round(spec.diagonal_full_field_deg, 6),
            "wavelengths_nm": list(spec.wavelengths_nm),
            "minimum_mtf_at_nyquist": minimum_mtf_nyquist,
            "maximum_distortion_percent": maximum_distortion_percent,
            "minimum_relative_illumination_percent": (
                minimum_relative_illumination_percent
            ),
        },
        "assumptions": [
            "infinite_conjugate",
            "rectilinear_projection",
            "rectangular_field_corners_touch_the_"
            f"{_display_number(2.0 * derived['image_surface_semi_diameter_mm'])}"
            "_mm_image_circle",
            "entrance_pupil_is_evaluated_at_its_"
            f"{_display_number(derived['entrance_pupil_min_mm'])}_mm_minimum",
        ],
        "indexed_seed_count": len(seed_list),
        "eligible_seed_count": len(all_ranked),
        "spectrally_screened_seed_count": len(ranked),
        "excluded_without_documented_spectral_overlap_count": (
            len(all_ranked) - len(ranked)
        ),
        "ranking_policy": (
            "documented_spectral_overlap_then_metadata_score"
            if require_documented_spectral_overlap
            else "metadata_score"
        ),
        "candidates": [
            _candidate_payload(
                result,
                spec,
                rank,
                evidence=evidence_for(result.seed),
            )
            for rank, result in enumerate(selected, start=1)
        ],
        "unverified_constraints": [
            "actual_nyquist_frequency_lpmm",
            "mtf_after_uv_glass_substitution",
            "distortion_after_optimization",
            "relative_illumination_after_optimization",
            "240_to_320_nm_bulk_transmission",
            "cement_window_and_coating_compatibility",
            "back_focal_length_and_total_track",
        ],
        "next_step": (
            "Inspect the prescription and UV materials of the top candidates, then "
            "validate equal-budget adaptations in Zemax before selecting a seed."
        ),
    }
    return ensure_standard_json(result_payload)


def search_uv_seed_index(index_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    return search_uv_seed_structures(seeds=read_seed_index(index_path), **kwargs)


def _resolve_seed_source(index_path: Path, source_path: str) -> Path:
    raw_path = Path(source_path)
    if raw_path.is_absolute():
        candidates = [raw_path]
    else:
        repository_root = Path(__file__).resolve().parents[2]
        candidates = [
            repository_root / raw_path,
            index_path.parent / raw_path,
            Path.cwd() / raw_path,
        ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
        if resolved.suffix.casefold() == ".zmx" and resolved.parent.is_dir():
            matches = [
                item.resolve()
                for item in resolved.parent.iterdir()
                if item.is_file() and item.name.casefold() == resolved.name.casefold()
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    "the indexed prescription path has multiple case-insensitive matches"
                )
    raise FileNotFoundError("the indexed local prescription file is unavailable")


def get_local_seed_structure(
    *,
    index_path: str | Path,
    seed_id: str,
    scale_to_focal_length_mm: float | None = None,
) -> dict[str, Any]:
    """Read a seed prescription selected by ID from the configured local index."""

    resolved_index = Path(index_path).resolve()
    matching = [seed for seed in read_seed_index(resolved_index) if seed.seed_id == seed_id]
    if not matching:
        raise KeyError(f"seed_id {seed_id!r} is not present in the local index")
    if len(matching) > 1:
        raise ValueError(f"seed_id {seed_id!r} is not unique in the local index")
    seed = matching[0]
    if not seed.source_path:
        raise FileNotFoundError("the indexed seed has no local prescription")

    scale_factor = 1.0
    if scale_to_focal_length_mm is not None:
        target_focal_length = _positive(
            "scale_to_focal_length_mm", scale_to_focal_length_mm
        )
        scale_factor = target_focal_length / seed.focal_length_mm

    prescription_path = _resolve_seed_source(resolved_index, seed.source_path)
    parsed = parse_zmx_prescription(prescription_path)
    payload = {
        "evidence_level": "source_prescription_unvalidated",
        "seed": {
            "seed_id": seed.seed_id,
            "seed_handle": make_seed_handle(LOCAL_PROVIDER, seed.seed_id),
            "lens_type": seed.lens_type,
            "reference": seed.reference,
            "source": seed.source,
            "focal_length_mm": seed.focal_length_mm,
            "f_number": seed.f_number,
            "full_fov_deg": seed.full_fov_deg,
        },
        "scaling": {
            "target_focal_length_mm": scale_to_focal_length_mm,
            "scale_factor": round(scale_factor, 9),
            "invariant_warning": (
                "Uniform geometric scaling does not improve F-number, field angle, "
                "glass transmission, or aberration balance."
            ),
        },
        "prescription": prescription_payload(parsed, scale_factor=scale_factor),
        "warnings": [
            "Prescription values are an initial structure, not a qualified design.",
            "Model-glass index and Abbe values do not establish 240-320 nm transmission.",
            "Re-run glass, coating, MTF, distortion, illumination, and tolerance analyses.",
        ],
    }
    return ensure_standard_json(payload)
