import csv
from pathlib import Path

import pytest

from optical_seed_ranker.csv_safety import (
    FORMULA_PREFIXES,
    restore_spreadsheet_text,
    spreadsheet_safe_path,
    spreadsheet_safe_text,
)
from optical_seed_ranker.index_io import read_seed_index, write_seed_index
from optical_seed_ranker.models import SeedRecord, TargetSpec
from optical_seed_ranker.reports import write_html_report, write_ranking_csv
from optical_seed_ranker.scoring import score_seed


def test_reports_expose_every_score_and_normalized_weight(tmp_path):
    spec = TargetSpec(
        name="report-target",
        conjugate="infinity",
        architecture="camera",
        focal_length_mm=100,
        f_number=2,
        field_x_full_deg=10,
        field_y_full_deg=10,
        image_width_mm=10,
        image_height_mm=10,
        image_surface_semi_diameter_mm=8,
        wavelengths_nm=(500, 600),
    )
    seed = SeedRecord(
        seed_id="complete",
        lens_type="camera",
        focal_length_mm=100,
        f_number=2,
        full_fov_deg=15,
        surface_count=4,
        element_count=2,
        reference="synthetic",
        wavelength_min_nm=450,
        wavelength_max_nm=650,
        total_track_mm=80,
        back_focal_length_mm=20,
    )
    result = score_seed(seed, spec)
    csv_path = tmp_path / "ranking.csv"
    html_path = tmp_path / "report.html"
    write_ranking_csv([result], csv_path)
    write_html_report([result], spec, html_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    for name in (
        "f_number",
        "field",
        "architecture",
        "spectrum",
        "geometry",
        "complexity",
    ):
        assert row[f"{name}_score"]
        assert row[f"{name}_weight"]
    html = html_path.read_text(encoding="utf-8")
    for heading in ("Architecture", "Spectrum", "Geometry", "Complexity"):
        assert f"<th>{heading}</th>" in html


def test_csv_text_is_spreadsheet_safe_and_index_encoding_is_reversible(tmp_path):
    seed = SeedRecord(
        seed_id="=CMD()",
        lens_type="+camera",
        focal_length_mm=100,
        f_number=2,
        full_fov_deg=15,
        surface_count=4,
        element_count=2,
        reference="@reference",
        source="-provider",
        source_path="=seed.zmx",
    )
    index_path = tmp_path / "seeds.csv"
    write_seed_index([seed], index_path)
    with index_path.open(encoding="utf-8", newline="") as handle:
        stored = next(csv.DictReader(handle))

    for field in ("seed_id", "lens_type", "reference", "source", "source_path"):
        assert stored[field][0] not in FORMULA_PREFIXES
    restored = read_seed_index(index_path)[0]
    assert restored.seed_id == seed.seed_id
    assert restored.lens_type == seed.lens_type
    assert restored.reference == seed.reference
    assert restored.source == seed.source


def test_ranking_csv_keeps_dangerous_relative_source_path_machine_usable(tmp_path):
    source = tmp_path / "=seed.zmx"
    source.write_text("UNIT MM\nSURF 0\n", encoding="utf-8")
    spec = TargetSpec(
        name="safe-csv",
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
    seed = SeedRecord(
        seed_id="=seed",
        lens_type="@camera",
        focal_length_mm=100,
        f_number=2,
        full_fov_deg=15,
        surface_count=4,
        element_count=2,
        reference="+reference",
        source="-provider",
        source_path=source.name,
    )
    ranking_path = tmp_path / "ranking.csv"
    write_ranking_csv([score_seed(seed, spec)], ranking_path)
    with ranking_path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))

    for field in ("seed_id", "lens_type", "reference", "source", "source_path"):
        assert row[field][0] not in FORMULA_PREFIXES
    assert row["provider"] == "local"
    assert row["seed_handle"] == "local:%3Dseed"
    assert row["source_path"] == "./=seed.zmx"
    assert (ranking_path.parent / Path(row["source_path"])).resolve() == source.resolve()


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", " ", "\t", "\r", "\n", "\x00", "\ufeff"])
def test_csv_safety_covers_formula_whitespace_and_control_prefixes(prefix):
    original = f"{prefix}=payload"
    encoded = spreadsheet_safe_text(original)

    assert encoded.startswith("'")
    assert restore_spreadsheet_text(encoded, encoded=True) == original
    assert spreadsheet_safe_path(original).startswith("./")
