from optical_seed_ranker.models import SeedRecord, TargetSpec
from optical_seed_ranker.scoring import (
    f_number_distance,
    field_distance,
    rank_seeds,
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
