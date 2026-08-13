from __future__ import annotations

from math import exp, log, radians, tan
from typing import Iterable

from .models import ScoreBreakdown, SeedRecord, TargetSpec


def f_number_distance(seed_f_number: float, target_f_number: float, penalty: float) -> float:
    distance = abs(log(seed_f_number / target_f_number))
    return distance * penalty if seed_f_number > target_f_number else distance


def field_distance(seed_full_deg: float, target_full_deg: float, penalty: float) -> float:
    if not 0 < seed_full_deg < 180 or not 0 < target_full_deg < 180:
        raise ValueError("field distance requires full field angles between 0 and 180 degrees")
    seed_tangent = tan(radians(seed_full_deg / 2.0))
    target_tangent = tan(radians(target_full_deg / 2.0))
    distance = abs(log(seed_tangent / target_tangent))
    return distance * penalty if seed_full_deg < target_full_deg else distance


def architecture_distance(seed_type: str, target_architecture: str) -> float:
    seed = seed_type.lower().replace("-", "_")
    target = target_architecture.lower().replace("-", "_")
    if seed == target or seed.startswith(f"{target}_"):
        return 0.0
    if target == "camera" and seed.startswith("cell_phone"):
        return 0.25
    if target in seed or seed in target:
        return 0.20
    if any(token in seed for token in ("objective", "telescope", "projector")):
        return 0.65
    return 1.0


def complexity_distance(element_count: int, preferred_range: tuple[int, int]) -> float:
    low, high = preferred_range
    if low <= element_count <= high:
        return 0.0
    nearest = low if element_count < low else high
    return abs(element_count - nearest) / max(float(nearest), 1.0)


def _spectrum_distance(seed: SeedRecord, spec: TargetSpec) -> float | None:
    if seed.wavelength_min_nm is None or seed.wavelength_max_nm is None:
        return None
    target_min = min(spec.wavelengths_nm)
    target_max = max(spec.wavelengths_nm)
    missing_blue = max(0.0, seed.wavelength_min_nm - target_min)
    missing_red = max(0.0, target_max - seed.wavelength_max_nm)
    target_span = target_max - target_min
    # Monochromatic targets have no span. Normalize an uncovered wavelength
    # distance by the target wavelength while preserving zero for coverage.
    normalizer = target_span if target_span > 0 else target_min
    return (missing_blue + missing_red) / normalizer


def _geometry_distance(seed: SeedRecord, spec: TargetSpec) -> float | None:
    if seed.total_track_mm is None or seed.back_focal_length_mm is None:
        return None
    track_ratio = seed.total_track_mm / seed.focal_length_mm
    bfl_ratio = seed.back_focal_length_mm / seed.focal_length_mm
    # V0.1 has no target packaging limits. Reward physically positive values,
    # but leave detailed package matching to a later specification field.
    if track_ratio <= 0 or bfl_ratio <= 0:
        return 1.0
    return 0.0


def score_seed(seed: SeedRecord, spec: TargetSpec) -> ScoreBreakdown:
    scale_factor = spec.focal_length_mm / seed.focal_length_mm
    if seed.conjugate.lower() != spec.conjugate.lower():
        return ScoreBreakdown(
            seed=seed,
            eligible=False,
            metadata_score=0.0,
            weighted_distance=float("inf"),
            scale_factor=scale_factor,
            component_distances={},
            component_scores={},
            used_weights={},
            reason=f"conjugate mismatch: {seed.conjugate} != {spec.conjugate}",
        )

    if not 0 < seed.full_fov_deg < 180:
        return ScoreBreakdown(
            seed=seed,
            eligible=False,
            metadata_score=0.0,
            weighted_distance=float("inf"),
            scale_factor=scale_factor,
            component_distances={},
            component_scores={},
            used_weights={},
            reason=(
                f"unsupported full field {seed.full_fov_deg:g} degrees; "
                "V0.1 ranks conventional objectives below 180 degrees"
            ),
        )

    distances: dict[str, float | None] = {
        "f_number": f_number_distance(
            seed.f_number, spec.f_number, spec.asymmetric_penalty
        ),
        "full_fov": field_distance(
            seed.full_fov_deg,
            spec.diagonal_full_field_deg,
            spec.asymmetric_penalty,
        ),
        "architecture": architecture_distance(seed.lens_type, spec.architecture),
        "spectrum": _spectrum_distance(seed, spec),
        "geometry": _geometry_distance(seed, spec),
        "complexity": complexity_distance(
            seed.element_count, spec.preferred_element_range
        ),
    }

    available = {
        name: value
        for name, value in distances.items()
        if value is not None and spec.metadata_weights.get(name, 0.0) > 0
    }
    available_weight = sum(spec.metadata_weights[name] for name in available)
    if available_weight <= 0:
        raise ValueError("no score components have usable data and positive weights")

    used_weights = {
        name: spec.metadata_weights[name] / available_weight for name in available
    }
    weighted_distance = sum(used_weights[name] * value for name, value in available.items())
    # Preserve ranking resolution for difficult targets. A clipped linear
    # display score collapses every candidate to zero once distance exceeds 1.
    score = 100.0 * exp(-weighted_distance)
    component_scores = {
        name: 100.0 * exp(-value) for name, value in available.items()
    }

    return ScoreBreakdown(
        seed=seed,
        eligible=True,
        metadata_score=score,
        weighted_distance=weighted_distance,
        scale_factor=scale_factor,
        component_distances={name: float(value) for name, value in available.items()},
        component_scores=component_scores,
        used_weights=used_weights,
    )


def rank_seeds(seeds: Iterable[SeedRecord], spec: TargetSpec) -> list[ScoreBreakdown]:
    ranked = [score_seed(seed, spec) for seed in seeds]
    return sorted(
        ranked,
        key=lambda item: (
            not item.eligible,
            -item.metadata_score,
            item.weighted_distance,
            item.seed.seed_id,
        ),
    )
