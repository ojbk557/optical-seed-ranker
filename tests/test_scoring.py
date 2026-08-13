import math

import pytest

from optical_seed_ranker.models import SeedRecord, TargetSpec
from optical_seed_ranker.scoring import (
    f_number_distance,
    field_distance,
    rank_seeds,
    score_seed,
)


def target() -> TargetSpec:
    return TargetSpec(
        name="target",
        conjugate="infinity",
        architecture="camera",
        focal_length_mm=170.14,
        f_number=1.547,
        field_x_full_deg=20,
        field_y_full_deg=20,
        image_width_mm=60,
        image_height_mm=60,
        image_surface_semi_diameter_mm=43.5,
        wavelengths_nm=(450, 587.6, 800),
        preferred_element_range=(4, 16),
    )


def seed(seed_id: str, focal: float, fno: float, field: float) -> SeedRecord:
    return SeedRecord(
        seed_id=seed_id,
        lens_type="camera",
        focal_length_mm=focal,
        f_number=fno,
        full_fov_deg=field,
        surface_count=10,
        element_count=7,
        reference="synthetic",
    )


def test_slow_f_number_is_penalized_asymmetrically():
    fast = f_number_distance(1.0, 2.0, 3.0)
    slow = f_number_distance(4.0, 2.0, 3.0)
    assert slow == 3.0 * fast


def test_narrow_field_is_penalized_asymmetrically():
    narrow = field_distance(20, 40, 3.0)
    wide = field_distance(40, 20, 3.0)
    assert narrow > wide


def test_architecture_beats_nearest_focal_length():
    nearest_focal_but_slow = seed("A", 168, 4.0, 10)
    scalable_fast_seed = seed("B", 85, 1.4, 29)
    ranked = rank_seeds([nearest_focal_but_slow, scalable_fast_seed], target())
    assert ranked[0].seed.seed_id == "B"
    assert 1.99 < ranked[0].scale_factor < 2.01


def test_full_field_at_180_is_explicitly_ineligible():
    panoramic = seed("panoramic", 10, 2.0, 180)
    result = rank_seeds([panoramic], target())[0]
    assert not result.eligible
    assert "below 180" in (result.reason or "")


def test_difficult_targets_keep_a_nonzero_monotonic_score():
    difficult = seed("difficult", 100, 8.0, 5)
    result = rank_seeds([difficult], target())[0]
    assert result.weighted_distance > 1
    assert 0 < result.metadata_score < 100


def test_monochromatic_spectrum_scoring_has_no_zero_division():
    mono_target = TargetSpec(
        name="mono",
        conjugate="infinity",
        architecture="camera",
        focal_length_mm=100,
        f_number=2,
        field_x_full_deg=10,
        field_y_full_deg=10,
        image_width_mm=10,
        image_height_mm=10,
        image_surface_semi_diameter_mm=8,
        wavelengths_nm=(550,),
    )
    covered = SeedRecord(
        seed_id="covered",
        lens_type="camera",
        focal_length_mm=100,
        f_number=2,
        full_fov_deg=15,
        surface_count=4,
        element_count=2,
        reference="synthetic",
        wavelength_min_nm=500,
        wavelength_max_nm=600,
    )
    missed = SeedRecord(
        seed_id="missed",
        lens_type="camera",
        focal_length_mm=100,
        f_number=2,
        full_fov_deg=15,
        surface_count=4,
        element_count=2,
        reference="synthetic",
        wavelength_min_nm=600,
        wavelength_max_nm=700,
    )
    assert score_seed(covered, mono_target).component_distances["spectrum"] == 0
    assert score_seed(missed, mono_target).component_distances["spectrum"] > 0


def test_rejects_non_finite_and_reversed_metadata():
    with pytest.raises(ValueError, match="finite"):
        seed("bad", math.nan, 2, 20)
    with pytest.raises(ValueError, match="cannot exceed"):
        SeedRecord(
            seed_id="bad-spectrum",
            lens_type="camera",
            focal_length_mm=100,
            f_number=2,
            full_fov_deg=20,
            surface_count=4,
            element_count=2,
            reference="synthetic",
            wavelength_min_nm=700,
            wavelength_max_nm=400,
        )
