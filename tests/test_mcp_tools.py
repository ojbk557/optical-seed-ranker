import pytest

from optical_seed_ranker.index_io import write_seed_index
from optical_seed_ranker.mcp_tools import (
    derive_rectilinear_target,
    get_local_seed_structure,
    search_uv_seed_structures,
)
from optical_seed_ranker.models import SeedRecord
from optical_seed_ranker.patent_seeds import (
    get_patent_seed_structure,
    load_patent_seed_evidence,
    load_patent_seed_records,
)
from optical_seed_ranker.zmx import parse_zmx_prescription, prescription_payload


def _seed(seed_id: str, *, fno: float, field: float) -> SeedRecord:
    return SeedRecord(
        seed_id=seed_id,
        lens_type="camera",
        focal_length_mm=10.0,
        f_number=fno,
        full_fov_deg=field,
        surface_count=10,
        element_count=6,
        reference="test",
        source="unit-test",
    )


def test_derives_strict_rectangular_target_from_18_mm_image_circle():
    target = derive_rectilinear_target(
        field_x_full_deg=60,
        field_y_full_deg=60,
        detector_diameter_mm=18,
        entrance_pupil_min_mm=12,
    )
    assert 11.01 < target["focal_length_mm"] < 11.03
    assert 0.91 < target["f_number_max"] < 0.93
    assert 12.72 < target["image_width_mm"] < 12.74
    assert target["image_surface_semi_diameter_mm"] == 9


def test_uv_search_returns_evidence_limited_candidates():
    result = search_uv_seed_structures(
        seeds=[
            _seed("wide-fast", fno=0.9, field=85),
            _seed("narrow-slow", fno=2.8, field=30),
        ],
        field_x_full_deg=60,
        field_y_full_deg=60,
        detector_diameter_mm=18,
        entrance_pupil_min_mm=12,
        wavelength_min_nm=240,
        wavelength_max_nm=320,
        top_k=2,
    )
    assert result["evidence_level"] == "metadata_topology_shortlist"
    assert result["candidates"][0]["seed_id"] == "wide-fast"
    assert result["candidates"][0]["metadata_score"] > 0
    assert result["candidates"][1]["metadata_score"] > 0
    assert "uv_material_and_coating_data_missing" in result["candidates"][0]["risk_flags"]
    assert "distortion_after_optimization" in result["unverified_constraints"]


def test_uv_search_rejects_invalid_percentages():
    try:
        search_uv_seed_structures(
            seeds=[_seed("seed", fno=1.0, field=90)],
            field_x_full_deg=60,
            field_y_full_deg=60,
            detector_diameter_mm=18,
            entrance_pupil_min_mm=12,
            wavelength_min_nm=240,
            wavelength_max_nm=320,
            minimum_relative_illumination_percent=120,
        )
    except ValueError as error:
        assert "minimum_relative_illumination_percent" in str(error)
    else:
        raise AssertionError("invalid relative illumination was accepted")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("detector_diameter_mm", float("nan")),
        ("entrance_pupil_min_mm", float("inf")),
        ("minimum_mtf_nyquist", float("nan")),
        ("maximum_distortion_percent", float("inf")),
        ("minimum_relative_illumination_percent", float("nan")),
    ],
)
def test_uv_search_rejects_non_finite_public_inputs(field, value):
    inputs = {
        "seeds": [_seed("seed", fno=1.0, field=90)],
        "field_x_full_deg": 60,
        "field_y_full_deg": 60,
        "detector_diameter_mm": 18,
        "entrance_pupil_min_mm": 12,
        "wavelength_min_nm": 240,
        "wavelength_max_nm": 320,
        "minimum_mtf_nyquist": 0.4,
        "maximum_distortion_percent": 3,
        "minimum_relative_illumination_percent": 60,
    }
    inputs[field] = value

    with pytest.raises(ValueError, match="finite"):
        search_uv_seed_structures(**inputs)


def test_uv_search_assumptions_report_actual_detector_and_pupil_inputs():
    result = search_uv_seed_structures(
        seeds=[_seed("seed", fno=1.0, field=90)],
        field_x_full_deg=50,
        field_y_full_deg=40,
        detector_diameter_mm=25,
        entrance_pupil_min_mm=8,
        wavelength_min_nm=240,
        wavelength_max_nm=320,
    )

    assert "rectangular_field_corners_touch_the_25_mm_image_circle" in result[
        "assumptions"
    ]
    assert "entrance_pupil_is_evaluated_at_its_8_mm_minimum" in result[
        "assumptions"
    ]


def test_provider_qualified_handles_keep_colliding_seed_evidence_separate():
    patent = load_patent_seed_records()[0]
    local = SeedRecord(
        seed_id=patent.seed_id,
        lens_type="camera",
        focal_length_mm=12,
        f_number=1,
        full_fov_deg=90,
        surface_count=4,
        element_count=2,
        reference="local-collision",
        # Provider identity is not inferred from this externally controlled label.
        source="curated_patent",
    )

    result = search_uv_seed_structures(
        seeds=[patent, local],
        evidence_by_seed=load_patent_seed_evidence(),
        field_x_full_deg=60,
        field_y_full_deg=60,
        detector_diameter_mm=18,
        entrance_pupil_min_mm=12,
        wavelength_min_nm=240,
        wavelength_max_nm=320,
        top_k=2,
    )
    by_handle = {candidate["seed_handle"]: candidate for candidate in result["candidates"]}

    assert set(by_handle) == {
        f"patent:{patent.seed_id}",
        f"local:{patent.seed_id}",
    }
    assert by_handle[f"patent:{patent.seed_id}"]["evidence"]["title"]
    assert (
        by_handle[f"local:{patent.seed_id}"]["evidence"]["evidence_level"]
        == "index_metadata_only"
    )


def test_uv_search_can_exclude_geometry_only_records():
    unknown = _seed("unknown-spectrum", fno=0.9, field=90)
    documented = SeedRecord(
        seed_id="documented-uv",
        lens_type="camera",
        focal_length_mm=10,
        f_number=1.2,
        full_fov_deg=90,
        surface_count=10,
        element_count=6,
        reference="unit-test",
        source="unit-test",
        wavelength_min_nm=250,
        wavelength_max_nm=280,
    )
    result = search_uv_seed_structures(
        seeds=[unknown, documented],
        field_x_full_deg=60,
        field_y_full_deg=60,
        detector_diameter_mm=18,
        entrance_pupil_min_mm=12,
        wavelength_min_nm=240,
        wavelength_max_nm=320,
        require_documented_spectral_overlap=True,
    )
    assert [item["seed_id"] for item in result["candidates"]] == [
        "documented-uv"
    ]
    assert result["excluded_without_documented_spectral_overlap_count"] == 1


def test_reads_and_scales_prescription_selected_from_local_index(tmp_path):
    prescription = tmp_path / "example.zmx"
    prescription.write_text(
        "\n".join(
            [
                "MODE SEQ",
                "UNIT MM X W X CM MR CPMM",
                "ENPD 4",
                "FTYP 0 0 2 1 0 0 0",
                "XFLN 0 10",
                "YFLN 0 20",
                "WAVM 1 0.280 1",
                "SURF 0",
                "  TYPE STANDARD",
                "  CURV 0",
                "  DISZ INFINITY",
                "SURF 1",
                "  TYPE STANDARD",
                "  CURV 0.1",
                "  DISZ 2",
                "  GLAS ___BLANK 1 0 1.5 60 0 0 0 0 0 0",
                "  DIAM 3",
                "SURF 2",
                "  STOP",
                "  TYPE STANDARD",
                "  CURV -0.2",
                "  DISZ 5",
                "  DIAM 2",
                "SURF 3",
                "  TYPE STANDARD",
                "  CURV 0",
                "  DISZ 0",
            ]
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "seeds.csv"
    seed = SeedRecord(
        seed_id="example",
        lens_type="camera",
        focal_length_mm=20,
        f_number=2,
        full_fov_deg=40,
        surface_count=2,
        element_count=1,
        reference="unit-test",
        source="unit-test",
        source_path=str(prescription),
    )
    write_seed_index([seed], index_path)

    result = get_local_seed_structure(
        index_path=index_path,
        seed_id="example",
        scale_to_focal_length_mm=10,
    )

    assert result["evidence_level"] == "source_prescription_unvalidated"
    assert result["scaling"]["scale_factor"] == 0.5
    assert result["prescription"]["system"]["wavelengths_nm"] == [280.0]
    assert result["prescription"]["system"]["x_fields_deg"] == [0.0, 10.0]
    assert result["prescription"]["system"]["entrance_pupil_diameter_mm"] == 2.0
    first_element = result["prescription"]["element_regions"][0]
    assert first_element["front_radius_mm"] == 5.0
    assert first_element["back_radius_mm"] == -2.5
    assert first_element["center_thickness_mm"] == 1.0
    assert first_element["model_refractive_index"] == 1.5


def test_reads_utf16_zemax_text(tmp_path):
    prescription = tmp_path / "utf16.zmx"
    prescription.write_text(
        "UNIT MM X W X CM MR CPMM\n"
        "SURF 0\n  TYPE STANDARD\n  CURV 0\n  DISZ INFINITY\n"
        "SURF 1\n  TYPE STANDARD\n  CURV 0\n  DISZ 0\n",
        encoding="utf-16",
    )
    index_path = tmp_path / "seeds.csv"
    write_seed_index(
        [
            SeedRecord(
                seed_id="utf16",
                lens_type="camera",
                focal_length_mm=10,
                f_number=2,
                full_fov_deg=30,
                surface_count=1,
                element_count=1,
                reference="unit-test",
                source_path=str(prescription),
            )
        ],
        index_path,
    )
    result = get_local_seed_structure(index_path=index_path, seed_id="utf16")
    assert result["prescription"]["surface_count_including_object_and_image"] == 2


def test_curated_patents_rank_the_two_wide_fast_structures_first():
    result = search_uv_seed_structures(
        seeds=load_patent_seed_records(),
        field_x_full_deg=60,
        field_y_full_deg=60,
        detector_diameter_mm=18,
        entrance_pupil_min_mm=12,
        wavelength_min_nm=240,
        wavelength_max_nm=320,
        evidence_by_seed=load_patent_seed_evidence(),
        top_k=6,
    )
    assert [item["seed_id"] for item in result["candidates"][:2]] == [
        "CN113504627B",
        "CN112162388A",
    ]
    assert result["candidates"][0]["metadata_score"] == 65.579
    assert result["candidates"][1]["metadata_score"] == 53.619
    first = result["candidates"][0]
    assert first["evidence"]["evidence_level"] == "patent_numeric_prescription_unvalidated"
    assert "focal_length_basis" in first["evidence"]
    assert first["evidence"]["known_gaps"]
    assert "ultra_wide_projection_model_unverified" in first["risk_flags"]


def test_reads_and_scales_curated_patent_prescription():
    result = get_patent_seed_structure(
        seed_id="CN113504627B",
        scale_to_focal_length_mm=11.022703842524301,
    )
    assert result["scaling"]["scale_factor"] == 1.418623403
    assert len(result["prescription"]["surfaces"]) == 19
    assert result["prescription"]["surfaces"][0]["radius_mm"] == 154.319272419
    assert "250-270 nm" in result["warnings"][0]


@pytest.mark.parametrize("scale", [float("nan"), float("inf")])
def test_patent_structure_rejects_non_finite_scaling(scale):
    with pytest.raises(ValueError, match="finite"):
        get_patent_seed_structure(
            seed_id="CN113504627B",
            scale_to_focal_length_mm=scale,
        )


def test_rejects_non_mm_zemax_prescriptions(tmp_path):
    prescription = tmp_path / "inch.zmx"
    prescription.write_text(
        "UNIT IN X W X CM MR CPMM\nSURF 0\n TYPE STANDARD\n CURV 0\n DISZ 0\n",
        encoding="utf-8",
    )
    try:
        parse_zmx_prescription(prescription)
    except ValueError as error:
        assert "UNIT MM" in str(error)
    else:
        raise AssertionError("a non-mm Zemax prescription was accepted")


def test_scales_even_asphere_parameters_with_length_dimensions(tmp_path):
    prescription = tmp_path / "asphere.zmx"
    prescription.write_text(
        "\n".join(
            [
                "UNIT MM X W X CM MR CPMM",
                "SURF 0",
                " TYPE STANDARD",
                " CURV 0",
                " DISZ INFINITY",
                "SURF 1",
                " TYPE EVENASPH",
                " CURV 0.1",
                " PARM 1 -1",
                " PARM 2 0.004",
                " PARM 3 0.000006",
                " DISZ 2",
                "SURF 2",
                " TYPE STANDARD",
                " CURV 0",
                " DISZ 0",
            ]
        ),
        encoding="utf-8",
    )
    payload = prescription_payload(parse_zmx_prescription(prescription), scale_factor=2)
    params = payload["surfaces"][1]["parameters"]
    # Zemax EVENASPH PARM n is alpha_n on r^(2n); CONI stores the conic.
    assert params["1"] == pytest.approx(-0.5)
    assert params["2"] == pytest.approx(0.0005)
    assert params["3"] == pytest.approx(1.875e-07)


@pytest.mark.parametrize("scale_factor", [0, -1, float("nan"), float("inf")])
def test_rejects_invalid_prescription_scale_factor(tmp_path, scale_factor):
    prescription = tmp_path / "scale.zmx"
    prescription.write_text(
        "UNIT MM X W X CM MR CPMM\n"
        "SURF 0\n TYPE STANDARD\n CURV 0\n DISZ INFINITY\n"
        "SURF 1\n TYPE STANDARD\n CURV 0\n DISZ 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="scale_factor"):
        prescription_payload(
            parse_zmx_prescription(prescription), scale_factor=scale_factor
        )


def test_rejects_non_finite_zemax_numeric_tokens(tmp_path):
    prescription = tmp_path / "nonfinite.zmx"
    prescription.write_text(
        "UNIT MM X W X CM MR CPMM\n"
        "SURF 0\n TYPE STANDARD\n CURV NaN\n DISZ INFINITY\n"
        "SURF 1\n TYPE STANDARD\n CURV 0\n DISZ 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="finite"):
        parse_zmx_prescription(prescription)
