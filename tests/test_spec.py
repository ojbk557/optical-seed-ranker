import math

import pytest

from optical_seed_ranker.models import TargetSpec
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


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_spec_values(value):
    raw = {
        "name": "bad-finite-value",
        "focal_length_mm": value,
        "f_number": 2,
        "field": {"x_full_deg": 20, "y_full_deg": 20},
        "image": {
            "width_mm": 10,
            "height_mm": 10,
            "surface_semi_diameter_mm": 8,
        },
        "wavelengths_nm": [550],
    }
    with pytest.raises(ValueError, match="focal_length_mm"):
        TargetSpec.from_mapping(raw)


def test_rejects_image_surface_that_does_not_cover_image_corner():
    raw = {
        "name": "undersized-image-surface",
        "focal_length_mm": 20,
        "f_number": 2,
        "field": {"x_full_deg": 20, "y_full_deg": 20},
        "image": {
            "width_mm": 10,
            "height_mm": 10,
            "surface_semi_diameter_mm": 7,
        },
        "wavelengths_nm": [550],
    }
    with pytest.raises(ValueError, match="must cover"):
        TargetSpec.from_mapping(raw)


def test_rejects_unknown_metadata_weight_key():
    raw = {
        "name": "unknown-weight",
        "focal_length_mm": 20,
        "f_number": 2,
        "field": {"x_full_deg": 20, "y_full_deg": 20},
        "image": {
            "width_mm": 10,
            "height_mm": 10,
            "surface_semi_diameter_mm": 8,
        },
        "wavelengths_nm": [550],
        "metadata_weights": {"typo_component": 0.1},
    }
    with pytest.raises(ValueError, match="unknown metadata_weights"):
        TargetSpec.from_mapping(raw)
