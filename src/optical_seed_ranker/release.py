from __future__ import annotations

import argparse
import tomllib
from email.parser import Parser
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from . import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DISTRIBUTION = "optical-seed-ranker"


def _project_metadata(pyproject_path: Path) -> dict[str, Any]:
    with pyproject_path.open("rb") as handle:
        payload = tomllib.load(handle)
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml has no [project] table")
    return project


def _wheel_identity(wheel_path: Path) -> tuple[str, str]:
    with ZipFile(wheel_path) as archive:
        metadata_paths = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_paths) != 1:
            raise ValueError(
                f"wheel {wheel_path.name!r} must contain exactly one METADATA file"
            )
        metadata = Parser().parsestr(
            archive.read(metadata_paths[0]).decode("utf-8", errors="strict")
        )
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise ValueError(f"wheel {wheel_path.name!r} has incomplete package metadata")
    return name, version


def verify_release(
    tag: str,
    *,
    pyproject_path: str | Path = PROJECT_ROOT / "pyproject.toml",
    dist_dir: str | Path | None = None,
) -> Path | None:
    """Verify source, tag, and optional wheel identities before publication."""

    project_path = Path(pyproject_path)
    project = _project_metadata(project_path)
    project_name = str(project.get("name", ""))
    project_version = str(project.get("version", ""))
    if project_name != EXPECTED_DISTRIBUTION:
        raise ValueError(
            f"project name must remain {EXPECTED_DISTRIBUTION!r}; found {project_name!r}"
        )
    if not project_version:
        raise ValueError("project version cannot be empty")
    if __version__ != project_version:
        raise ValueError(
            f"package __version__ {__version__!r} does not match project version "
            f"{project_version!r}"
        )
    expected_tag = f"v{project_version}"
    if tag != expected_tag:
        raise ValueError(f"release tag must be {expected_tag!r}; found {tag!r}")

    if dist_dir is None:
        return None
    wheels = sorted(Path(dist_dir).glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("release dist directory must contain exactly one wheel")
    wheel = wheels[0]
    expected_prefix = f"optical_seed_ranker-{project_version}-"
    if not wheel.name.startswith(expected_prefix):
        raise ValueError(
            f"wheel filename must start with {expected_prefix!r}; found {wheel.name!r}"
        )
    wheel_name, wheel_version = _wheel_identity(wheel)
    if wheel_name != project_name or wheel_version != project_version:
        raise ValueError(
            "wheel metadata does not match pyproject.toml: "
            f"{wheel_name} {wheel_version}"
        )
    return wheel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a release tag and wheel identity")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--pyproject", type=Path, default=PROJECT_ROOT / "pyproject.toml")
    parser.add_argument("--dist-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    wheel = verify_release(
        args.tag,
        pyproject_path=args.pyproject,
        dist_dir=args.dist_dir,
    )
    message = f"release identity verified for {args.tag}"
    if wheel is not None:
        message += f" ({wheel.name})"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
