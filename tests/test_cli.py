import json

import pytest

from optical_seed_ranker.cli import main


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


def test_structure_requires_index_for_unknown_seed(capsys):
    with pytest.raises(SystemExit) as error:
        main(["structure", "--seed-id", "missing"])

    assert error.value.code == 2
    assert "provide --index" in capsys.readouterr().err
