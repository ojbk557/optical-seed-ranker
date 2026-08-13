import csv

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
