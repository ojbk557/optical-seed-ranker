from __future__ import annotations

from zipfile import ZipFile

import pytest

from optical_seed_ranker.release import PROJECT_ROOT, verify_release


def _write_wheel(path, *, name="optical-seed-ranker", version="0.1.1"):
    with ZipFile(path, "w") as archive:
        archive.writestr(
            f"optical_seed_ranker-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )


def test_release_gate_accepts_matching_tag_and_wheel(tmp_path):
    wheel = tmp_path / "optical_seed_ranker-0.1.1-py3-none-any.whl"
    _write_wheel(wheel)

    assert verify_release("v0.1.1", dist_dir=tmp_path) == wheel


def test_release_gate_rejects_tag_version_mismatch():
    with pytest.raises(ValueError, match="release tag"):
        verify_release("v0.1.2")


def test_release_gate_rejects_wheel_metadata_mismatch(tmp_path):
    wheel = tmp_path / "optical_seed_ranker-0.1.1-py3-none-any.whl"
    _write_wheel(wheel, version="0.1.2")

    with pytest.raises(ValueError, match="wheel metadata"):
        verify_release("v0.1.1", dist_dir=tmp_path)


def test_release_workflow_is_non_overwriting_and_reproducible_by_policy():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "--clobber" not in workflow
    assert "SOURCE_DATE_EPOCH" in workflow
    assert "--require-hashes" in workflow
    assert "Refuse to overwrite an existing release asset" in workflow
    assert "optical_seed_ranker.release --tag" in workflow
