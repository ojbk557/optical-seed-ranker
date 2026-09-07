from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .identifiers import (
    LOCAL_PROVIDER,
    PATENT_PROVIDER,
    resolve_seed_selector,
)
from .index_io import read_seed_index, write_seed_index
from .ingest import parse_lenslibrary_properties
from .json_io import standard_json_dumps
from .mcp_tools import get_local_seed_structure, search_uv_seed_structures
from .patent_seeds import (
    get_patent_seed_structure,
    load_patent_seed_evidence,
    load_patent_seed_records,
)
from .reports import write_html_report, write_ranking_csv
from .scoring import rank_seeds
from .specs import load_spec


def _index_command(args: argparse.Namespace) -> int:
    result = parse_lenslibrary_properties(args.source.resolve())
    count = write_seed_index(result.seeds, args.output)
    print(f"Indexed {count} LensLibrary seeds -> {args.output}")
    if result.skipped_lines:
        print(f"Skipped {result.skipped_lines} non-image-space or incomplete rows")
    for warning in result.warnings[:5]:
        print(f"Warning: {warning}")
    return 0


def _search_command(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    seeds = read_seed_index(args.index)
    ranked = [result for result in rank_seeds(seeds, spec) if result.eligible]
    top = ranked[: args.top_k]
    output_dir = Path(args.output_dir)
    ranking_path = output_dir / "ranking.csv"
    report_path = output_dir / "report.html"
    write_ranking_csv(top, ranking_path)
    write_html_report(top, spec, report_path)
    print(f"Ranked {len(seeds)} seeds; wrote top {len(top)} -> {output_dir}")
    if top:
        winner = top[0]
        print(
            f"Top metadata candidate: {winner.seed.seed_id} "
            f"({winner.metadata_score:.1f}/100, scale {winner.scale_factor:.3f}x)"
        )
    return 0


def _write_json(payload: dict[str, Any], output: Path) -> None:
    serialized = standard_json_dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(f"Wrote {output}")


def _uv_search_command(args: argparse.Namespace) -> int:
    seeds = load_patent_seed_records()
    evidence = load_patent_seed_evidence()
    local_count = 0
    if args.index is not None:
        local_seeds = read_seed_index(args.index)
        local_count = len(local_seeds)
        seeds.extend(local_seeds)

    result = search_uv_seed_structures(
        seeds=seeds,
        evidence_by_seed=evidence,
        field_x_full_deg=args.field_x,
        field_y_full_deg=args.field_y,
        detector_diameter_mm=args.detector_diameter,
        entrance_pupil_min_mm=args.entrance_pupil,
        wavelength_min_nm=args.wavelength_min,
        wavelength_max_nm=args.wavelength_max,
        minimum_mtf_nyquist=args.minimum_mtf,
        maximum_distortion_percent=args.maximum_distortion,
        minimum_relative_illumination_percent=args.minimum_illumination,
        require_documented_spectral_overlap=(
            args.require_documented_spectral_overlap
        ),
        top_k=args.top_k,
    )
    _write_json(result, args.output)
    print(
        f"Searched {len(seeds)} seeds ({local_count} local); "
        f"returned {len(result['candidates'])} metadata candidates"
    )
    return 0


def _structure_command(args: argparse.Namespace) -> int:
    patents = load_patent_seed_records()
    local_seeds = (
        read_seed_index(args.index)
        if args.index is not None and args.index.is_file()
        else []
    )
    try:
        provider, seed_id = resolve_seed_selector(
            args.seed_id,
            local_seed_ids=(seed.seed_id for seed in local_seeds),
            patent_seed_ids=(seed.seed_id for seed in patents),
        )
    except KeyError as error:
        if args.index is None:
            raise KeyError(f"{error.args[0]}; provide --index for a local seed") from error
        raise
    if provider == PATENT_PROVIDER:
        result = get_patent_seed_structure(
            seed_id=seed_id,
            scale_to_focal_length_mm=args.scale_to_focal_length,
        )
    else:
        assert provider == LOCAL_PROVIDER
        assert args.index is not None
        result = get_local_seed_structure(
            index_path=args.index,
            seed_id=seed_id,
            scale_to_focal_length_mm=args.scale_to_focal_length,
        )
    _write_json(result, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seedranker",
        description="Rank optical seeds with transparent, asymmetric engineering distances.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser(
        "index", help="Index LensLibrary's lens_properties_list.txt"
    )
    index_parser.add_argument("--source", type=Path, required=True)
    index_parser.add_argument("--output", type=Path, required=True)
    index_parser.set_defaults(handler=_index_command)

    search_parser = subparsers.add_parser(
        "search", help="Rank an indexed seed database for a target YAML specification"
    )
    search_parser.add_argument("--spec", type=Path, required=True)
    search_parser.add_argument("--index", type=Path, required=True)
    search_parser.add_argument("--top-k", type=int, default=10)
    search_parser.add_argument("--output-dir", type=Path, required=True)
    search_parser.set_defaults(handler=_search_command)

    uv_parser = subparsers.add_parser(
        "uv-search",
        help="Search bundled UV patent records, optionally with a local index",
    )
    uv_parser.add_argument("--index", type=Path)
    uv_parser.add_argument("--field-x", type=float, default=60.0)
    uv_parser.add_argument("--field-y", type=float, default=60.0)
    uv_parser.add_argument("--detector-diameter", type=float, default=18.0)
    uv_parser.add_argument("--entrance-pupil", type=float, default=12.0)
    uv_parser.add_argument("--wavelength-min", type=float, default=240.0)
    uv_parser.add_argument("--wavelength-max", type=float, default=320.0)
    uv_parser.add_argument("--minimum-mtf", type=float, default=0.4)
    uv_parser.add_argument("--maximum-distortion", type=float, default=3.0)
    uv_parser.add_argument("--minimum-illumination", type=float, default=60.0)
    uv_parser.add_argument(
        "--require-documented-spectral-overlap",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    uv_parser.add_argument("--top-k", type=int, default=5)
    uv_parser.add_argument("--output", type=Path, default=Path("uv-shortlist.json"))
    uv_parser.set_defaults(handler=_uv_search_command)

    structure_parser = subparsers.add_parser(
        "structure", help="Export a bundled patent or indexed local prescription"
    )
    structure_parser.add_argument(
        "--seed-id",
        required=True,
        help="Bare seed ID when unique, or a provider-qualified local:/patent: handle",
    )
    structure_parser.add_argument("--index", type=Path)
    structure_parser.add_argument("--scale-to-focal-length", type=float)
    structure_parser.add_argument("--output", type=Path, required=True)
    structure_parser.set_defaults(handler=_structure_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "top_k", 1) < 1:
        parser.error("--top-k must be at least 1")
    try:
        return int(args.handler(args))
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
