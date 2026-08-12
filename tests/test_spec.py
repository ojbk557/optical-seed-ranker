import math

import pytest

from optical_seed_ranker.models import SeedRecord, TargetSpec
from optical_seed_ranker.specs import load_spec


def test_large_aperture_derived_values():
    spec = load_spec("specs/large_aperture_60mm.yaml")
    assert 27.9 < spec.diagonal_full_field_deg < 28.1
    assert 42.42 < spec.corner_image_height_mm < 42.44
    assert 0.249 < spec.normalized_image_height < 0.250
    assert 109.9 < spec.entrance_pupil_mm < 110.1


def test_rejects_non_physical_spec():
    raw = {
        "name": "bad",
        "focal_length_mm": 0,
        "f_number": 2,
        "field": {"x_full_deg": 20, "y_full_deg": 20},
        "image": {
            "width_mm": 10,
            "height_mm": 10,
            "surface_semi_diameter_mm": 8,
        },
        "wavelengths_nm": [550],
    }
    try:
        TargetSpec.from_mapping(raw)
    except ValueError as error:
        assert "focal_length_mm" in str(error)
    else:
        raise AssertionError("non-physical spec was accepted")


def test_rejects_non_finite_spec_values():
    with pytest.raises(ValueError, match="finite"):
        TargetSpec(
            name="bad",
            conjugate="infinity",
            architecture="camera",
            focal_length_mm=math.nan,
            f_number=2,
            field_x_full_deg=10,
            field_y_full_deg=10,
            image_width_mm=10,
            image_height_mm=10,
            image_surface_semi_diameter_mm=8,
            wavelengths_nm=(550,),
        )


def test_rejects_reversed_seed_spectrum():
    with pytest.raises(ValueError, match="cannot exceed"):
        SeedRecord(
            seed_id="bad",
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
