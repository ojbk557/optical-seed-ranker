from __future__ import annotations

import argparse
from pathlib import Path

from .index_io import read_seed_index, write_seed_index
from .ingest import parse_lenslibrary_properties
from .reports import write_html_report, write_ranking_csv
from .scoring import rank_seeds
from .specs import load_spec


def _index_command(args: argparse.Namespace) -> int:
    result = parse_lenslibrary_properties(args.source)
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "top_k", 1) < 1:
        parser.error("--top-k must be at least 1")
    return int(args.handler(args))
