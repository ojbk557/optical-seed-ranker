import json
import math

import pytest

from optical_seed_ranker.cli import _write_json, main
from optical_seed_ranker.index_io import write_seed_index
from optical_seed_ranker.models import SeedRecord


def test_uv_search_works_with_only_bundled_data(tmp_path):
    output = tmp_path / "shortlists" / "uv.json"

    assert main(["uv-search", "--top-k", "2", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["indexed_seed_count"] == 6
    assert len(payload["candidates"]) == 2
    assert payload["candidates"][0]["seed_id"] == "CN113504627B"
    assert payload["evidence_level"] == "metadata_topology_shortlist"


def test_structure_exports_bundled_patent_prescription(tmp_path):
    output = tmp_path / "structure.json"

    assert (
        main(
            [
                "structure",
                "--seed-id",
                "CN113504627B",
                "--scale-to-focal-length",
                "11.022703842524301",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scaling"]["scale_factor"] == 1.418623403
    assert len(payload["prescription"]["surfaces"]) == 19


def test_structure_requires_index_for_unknown_seed(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "structure",
                "--seed-id",
                "missing",
                "--output",
                str(tmp_path / "missing.json"),
            ]
        )

    assert error.value.code == 2
    assert "provide --index" in capsys.readouterr().err


def _write_local_collision(tmp_path):
    prescription = tmp_path / "collision.ZMX"
    prescription.write_text(
        "UNIT MM X W X CM MR CPMM\n"
        "SURF 0\n TYPE STANDARD\n CURV 0\n DISZ INFINITY\n"
        "SURF 1\n TYPE STANDARD\n CURV 0\n DISZ 0\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "seeds.csv"
    write_seed_index(
        [
            SeedRecord(
                seed_id="CN113504627B",
                lens_type="camera",
                focal_length_mm=20,
                f_number=2,
                full_fov_deg=40,
                surface_count=2,
                element_count=1,
                reference="local-collision",
                source="curated_patent",
                source_path=str(prescription),
            )
        ],
        index_path,
    )
    return index_path


def test_structure_requires_qualified_handle_only_when_id_collides(tmp_path, capsys):
    index_path = _write_local_collision(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(
            [
                "structure",
                "--seed-id",
                "CN113504627B",
                "--index",
                str(index_path),
                "--output",
                str(tmp_path / "ambiguous.json"),
            ]
        )
    assert error.value.code == 2
    assert "ambiguous" in capsys.readouterr().err

    local_output = tmp_path / "local.json"
    assert (
        main(
            [
                "structure",
                "--seed-id",
                "local:CN113504627B",
                "--index",
                str(index_path),
                "--output",
                str(local_output),
            ]
        )
        == 0
    )
    local = json.loads(local_output.read_text(encoding="utf-8"))
    assert local["seed"]["seed_handle"] == "local:CN113504627B"
    assert local["prescription"]["surface_count_including_object_and_image"] == 2

    patent_output = tmp_path / "patent.json"
    assert (
        main(
            [
                "structure",
                "--seed-id",
                "patent:CN113504627B",
                "--index",
                str(index_path),
                "--output",
                str(patent_output),
            ]
        )
        == 0
    )
    patent = json.loads(patent_output.read_text(encoding="utf-8"))
    assert patent["seed"]["seed_handle"] == "patent:CN113504627B"
    assert len(patent["prescription"]["surfaces"]) == 19


def test_qualified_patent_handle_does_not_depend_on_local_index_health(tmp_path):
    output = tmp_path / "patent.json"

    assert (
        main(
            [
                "structure",
                "--seed-id",
                "patent:CN113504627B",
                "--index",
                str(tmp_path / "missing.csv"),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert json.loads(output.read_text(encoding="utf-8"))["seed"]["seed_handle"] == (
        "patent:CN113504627B"
    )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_cli_rejects_non_finite_numeric_arguments(value, tmp_path, capsys):
    output = tmp_path / "invalid.json"

    with pytest.raises(SystemExit) as error:
        main(
            [
                "uv-search",
                f"--detector-diameter={value}",
                "--output",
                str(output),
            ]
        )

    assert error.value.code == 2
    assert "finite" in capsys.readouterr().err
    assert not output.exists()


def test_cli_json_writer_refuses_non_standard_numbers(tmp_path):
    output = tmp_path / "nonstandard.json"

    with pytest.raises(ValueError, match="JSON"):
        _write_json({"bad": math.nan}, output)

    assert not output.exists()
