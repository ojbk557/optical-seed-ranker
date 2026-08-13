from __future__ import annotations

from dataclasses import dataclass, field
from math import atan, degrees, hypot, isclose, isfinite, radians, tan
from typing import Any, Mapping

DEFAULT_WEIGHTS: dict[str, float] = {
    "f_number": 0.30,
    "full_fov": 0.25,
    "architecture": 0.15,
    "spectrum": 0.15,
    "geometry": 0.10,
    "complexity": 0.05,
}


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class TargetSpec:
    name: str
    conjugate: str
    architecture: str
    focal_length_mm: float
    f_number: float
    field_x_full_deg: float
    field_y_full_deg: float
    image_width_mm: float
    image_height_mm: float
    image_surface_semi_diameter_mm: float
    wavelengths_nm: tuple[float, ...]
    mtf_frequency_lpmm: float | None = None
    minimum_mtf: float | None = None
    preferred_element_range: tuple[int, int] = (4, 16)
    metadata_weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )
    asymmetric_penalty: float = 3.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if not self.conjugate.strip() or not self.architecture.strip():
            raise ValueError("conjugate and architecture cannot be empty")
        _positive("focal_length_mm", self.focal_length_mm)
        _positive("f_number", self.f_number)
        _positive("field_x_full_deg", self.field_x_full_deg)
        _positive("field_y_full_deg", self.field_y_full_deg)
        _positive("image_width_mm", self.image_width_mm)
        _positive("image_height_mm", self.image_height_mm)
        _positive("image_surface_semi_diameter_mm", self.image_surface_semi_diameter_mm)
        if (
            self.image_surface_semi_diameter_mm < self.corner_image_height_mm
            and not isclose(
                self.image_surface_semi_diameter_mm,
                self.corner_image_height_mm,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError(
                "image_surface_semi_diameter_mm must cover the rectangular "
                "image corner"
            )
        if self.field_x_full_deg >= 180 or self.field_y_full_deg >= 180:
            raise ValueError("full field angles must be below 180 degrees")
        if not self.wavelengths_nm:
            raise ValueError("at least one wavelength is required")
        if any(not isfinite(float(w)) or float(w) <= 0 for w in self.wavelengths_nm):
            raise ValueError("wavelengths must be finite and greater than zero")
        if self.mtf_frequency_lpmm is not None:
            _positive("mtf_frequency_lpmm", self.mtf_frequency_lpmm)
        if self.minimum_mtf is not None and (
            not isfinite(float(self.minimum_mtf))
            or not 0 <= float(self.minimum_mtf) <= 1
        ):
            raise ValueError("minimum_mtf must be finite and between 0 and 1")
        lo, hi = self.preferred_element_range
        if lo < 1 or hi < lo:
            raise ValueError("preferred_element_range must be [positive_min, max]")
        if not isfinite(float(self.asymmetric_penalty)) or self.asymmetric_penalty < 1:
            raise ValueError("asymmetric_penalty must be finite and at least 1")
        if not self.metadata_weights or any(
            not isfinite(float(value)) or float(value) < 0
            for value in self.metadata_weights.values()
        ):
            raise ValueError(
                "metadata_weights must contain finite, non-negative values"
            )
        unknown_weights = set(self.metadata_weights) - set(DEFAULT_WEIGHTS)
        if unknown_weights:
            raise ValueError(
                "unknown metadata_weights: " + ", ".join(sorted(unknown_weights))
            )
        if not any(float(value) > 0 for value in self.metadata_weights.values()):
            raise ValueError("metadata_weights must contain at least one positive value")

    @property
    def diagonal_half_field_deg(self) -> float:
        x_half = radians(self.field_x_full_deg / 2.0)
        y_half = radians(self.field_y_full_deg / 2.0)
        return degrees(atan(hypot(tan(x_half), tan(y_half))))

    @property
    def diagonal_full_field_deg(self) -> float:
        return 2.0 * self.diagonal_half_field_deg

    @property
    def corner_image_height_mm(self) -> float:
        return hypot(self.image_width_mm / 2.0, self.image_height_mm / 2.0)

    @property
    def normalized_image_height(self) -> float:
        return self.corner_image_height_mm / self.focal_length_mm

    @property
    def entrance_pupil_mm(self) -> float:
        return self.focal_length_mm / self.f_number

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TargetSpec":
        field_raw = raw.get("field") or {}
        image_raw = raw.get("image") or {}
        perf_raw = raw.get("performance") or {}
        element_range = raw.get("preferred_element_range", [4, 16])
        if len(element_range) != 2:
            raise ValueError("preferred_element_range must contain two integers")

        return cls(
            name=str(raw["name"]),
            conjugate=str(raw.get("conjugate", "infinity")),
            architecture=str(raw.get("architecture", "camera")),
            focal_length_mm=float(raw["focal_length_mm"]),
            f_number=float(raw["f_number"]),
            field_x_full_deg=float(field_raw["x_full_deg"]),
            field_y_full_deg=float(field_raw["y_full_deg"]),
            image_width_mm=float(image_raw["width_mm"]),
            image_height_mm=float(image_raw["height_mm"]),
            image_surface_semi_diameter_mm=float(
                image_raw["surface_semi_diameter_mm"]
            ),
            wavelengths_nm=tuple(float(w) for w in raw["wavelengths_nm"]),
            mtf_frequency_lpmm=(
                float(perf_raw["mtf_frequency_lpmm"])
                if perf_raw.get("mtf_frequency_lpmm") is not None
                else None
            ),
            minimum_mtf=(
                float(perf_raw["minimum_mtf"])
                if perf_raw.get("minimum_mtf") is not None
                else None
            ),
            preferred_element_range=(int(element_range[0]), int(element_range[1])),
            metadata_weights={
                **DEFAULT_WEIGHTS,
                **{k: float(v) for k, v in (raw.get("metadata_weights") or {}).items()},
            },
            asymmetric_penalty=float(raw.get("asymmetric_penalty", 3.0)),
        )


@dataclass(frozen=True, slots=True)
class SeedRecord:
    seed_id: str
    lens_type: str
    focal_length_mm: float
    f_number: float
    full_fov_deg: float
    surface_count: int
    element_count: int
    reference: str
    conjugate: str = "infinity"
    source: str = "unknown"
    source_path: str | None = None
    wavelength_min_nm: float | None = None
    wavelength_max_nm: float | None = None
    total_track_mm: float | None = None
    back_focal_length_mm: float | None = None
    asphere_count: int | None = None
    obsolete_glass_count: int | None = None

    def __post_init__(self) -> None:
        if not self.seed_id.strip():
            raise ValueError("seed_id cannot be empty")
        _positive("seed focal_length_mm", self.focal_length_mm)
        _positive("seed f_number", self.f_number)
        _positive("seed full_fov_deg", self.full_fov_deg)
        if self.surface_count < 1 or self.element_count < 1:
            raise ValueError("surface_count and element_count must be positive")
        for name, value in (
            ("wavelength_min_nm", self.wavelength_min_nm),
            ("wavelength_max_nm", self.wavelength_max_nm),
        ):
            if value is not None:
                _positive(name, value)
        if (
            self.wavelength_min_nm is not None
            and self.wavelength_max_nm is not None
            and self.wavelength_min_nm > self.wavelength_max_nm
        ):
            raise ValueError("wavelength_min_nm cannot exceed wavelength_max_nm")
        for name, value in (
            ("total_track_mm", self.total_track_mm),
            ("back_focal_length_mm", self.back_focal_length_mm),
        ):
            if value is not None:
                _finite(name, value)
        for name, value in (
            ("asphere_count", self.asphere_count),
            ("obsolete_glass_count", self.obsolete_glass_count),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    seed: SeedRecord
    eligible: bool
    metadata_score: float
    weighted_distance: float
    scale_factor: float
    component_distances: Mapping[str, float]
    component_scores: Mapping[str, float]
    used_weights: Mapping[str, float]
    reason: str | None = None
