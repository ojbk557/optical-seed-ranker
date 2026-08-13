from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .index_io import read_seed_index
from .mcp_tools import (
    derive_rectilinear_target,
    get_local_seed_structure,
    search_uv_seed_structures,
)
from .patent_seeds import (
    DEFAULT_PATENT_SEEDS_PATH,
    get_patent_seed_structure,
    load_patent_seed_evidence,
    load_patent_seed_records,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _default_index_path() -> Path:
    configured = os.environ.get("SEEDRANKER_INDEX")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "index" / "seeds.csv"


def _default_patent_seed_path() -> Path:
    configured = os.environ.get("SEEDRANKER_PATENT_SEEDS")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_PATENT_SEEDS_PATH


def create_server(
    *,
    index_path: str | Path | None = None,
    patent_seed_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "The local MCP server requires the optional dependency. "
            "Install it with `python -m pip install \"optical-seed-ranker[mcp]\"` "
            "or, from a source checkout, `python -m pip install -e \".[mcp]\"`."
        ) from error
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the local MCP server may only bind to a loopback address")
    resolved_index = Path(index_path).resolve() if index_path else _default_index_path()
    resolved_patent_seeds = (
        Path(patent_seed_path).resolve()
        if patent_seed_path
        else _default_patent_seed_path()
    )

    def available_seeds() -> list[Any]:
        seeds = read_seed_index(resolved_index) if resolved_index.is_file() else []
        if resolved_patent_seeds.is_file():
            seeds.extend(load_patent_seed_records(resolved_patent_seeds))
        return seeds

    server = FastMCP(
        "optical-seed-ranker-local",
        instructions=(
            "Use these read-only tools to derive optical targets and shortlist seed "
            "topologies. Never describe a metadata candidate as optically qualified; "
            "prescription, UV material, ray-trace, MTF, distortion, and illumination "
            "validation are still required."
        ),
        host=host,
        port=int(port),
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )

    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        openWorldHint=False,
    )

    @server.tool(
        name="seedranker_derive_uv_target",
        title="Derive a UV lens target",
        description=(
            "Derive focal length, maximum F-number, and a consistent rectangular "
            "image area from full X/Y field angles, a circular detector diameter, "
            "and a minimum entrance pupil."
        ),
        annotations=read_only,
        structured_output=True,
    )
    def derive_uv_target(
        field_x_full_deg: float,
        field_y_full_deg: float,
        detector_diameter_mm: float,
        entrance_pupil_min_mm: float,
    ) -> dict[str, float]:
        return derive_rectilinear_target(
            field_x_full_deg=field_x_full_deg,
            field_y_full_deg=field_y_full_deg,
            detector_diameter_mm=detector_diameter_mm,
            entrance_pupil_min_mm=entrance_pupil_min_mm,
        )

    @server.tool(
        name="seedranker_search_uv_structures",
        title="Search UV seed structures",
        description=(
            "Rank locally indexed and curated patent lens structures for an "
            "infinity-conjugate UV camera target. Results are metadata-only "
            "topology candidates and must be verified in optical design software."
        ),
        annotations=read_only,
        structured_output=True,
    )
    def search_uv_structures(
        field_x_full_deg: float,
        field_y_full_deg: float,
        detector_diameter_mm: float,
        entrance_pupil_min_mm: float,
        wavelength_min_nm: float,
        wavelength_max_nm: float,
        minimum_mtf_nyquist: float = 0.4,
        maximum_distortion_percent: float = 3.0,
        minimum_relative_illumination_percent: float = 60.0,
        require_documented_spectral_overlap: bool = True,
        top_k: int = 5,
    ) -> dict[str, Any]:
        seeds = available_seeds()
        if not seeds:
            raise FileNotFoundError(
                "No local seed source is available. Run `seedranker index` or "
                "configure the bundled patent seed dataset."
            )
        return search_uv_seed_structures(
            seeds=seeds,
            evidence_by_seed=(
                load_patent_seed_evidence(resolved_patent_seeds)
                if resolved_patent_seeds.is_file()
                else {}
            ),
            field_x_full_deg=field_x_full_deg,
            field_y_full_deg=field_y_full_deg,
            detector_diameter_mm=detector_diameter_mm,
            entrance_pupil_min_mm=entrance_pupil_min_mm,
            wavelength_min_nm=wavelength_min_nm,
            wavelength_max_nm=wavelength_max_nm,
            minimum_mtf_nyquist=minimum_mtf_nyquist,
            maximum_distortion_percent=maximum_distortion_percent,
            minimum_relative_illumination_percent=(
                minimum_relative_illumination_percent
            ),
            require_documented_spectral_overlap=(
                require_documented_spectral_overlap
            ),
            top_k=top_k,
        )

    @server.tool(
        name="seedranker_get_local_structure",
        title="Read a local seed prescription",
        description=(
            "Return a transcribed patent prescription or local Zemax prescription "
            "for a known seed ID. Optional uniform scaling changes dimensions only "
            "and does not qualify the design."
        ),
        annotations=read_only,
        structured_output=True,
    )
    def get_seed_structure(
        seed_id: str,
        scale_to_focal_length_mm: float | None = None,
    ) -> dict[str, Any]:
        patent_ids = {
            seed.seed_id
            for seed in (
                load_patent_seed_records(resolved_patent_seeds)
                if resolved_patent_seeds.is_file()
                else []
            )
        }
        if seed_id in patent_ids:
            return get_patent_seed_structure(
                seed_id=seed_id,
                path=resolved_patent_seeds,
                scale_to_focal_length_mm=scale_to_focal_length_mm,
            )
        if not resolved_index.is_file():
            raise KeyError(f"seed_id {seed_id!r} is not present in a local source")
        return get_local_seed_structure(
            index_path=resolved_index,
            seed_id=seed_id,
            scale_to_focal_length_mm=scale_to_focal_length_mm,
        )

    @server.tool(
        name="seedranker_local_status",
        title="Check local Seed Ranker status",
        description=(
            "Report whether the configured local seed index is available and how "
            "many records it contains. No filesystem path or credential is returned."
        ),
        annotations=read_only,
        structured_output=True,
    )
    def local_status() -> dict[str, Any]:
        available = resolved_index.is_file()
        patent_available = resolved_patent_seeds.is_file()
        local_count = len(read_seed_index(resolved_index)) if available else 0
        patent_count = (
            len(load_patent_seed_records(resolved_patent_seeds))
            if patent_available
            else 0
        )
        return {
            "server": "optical-seed-ranker-local",
            "transport": "streamable-http",
            "loopback_only": True,
            "index_available": available,
            "indexed_seed_count": local_count,
            "curated_patent_seed_data_available": patent_available,
            "curated_patent_seed_count": patent_count,
            "total_searchable_seed_count": local_count + patent_count,
        }

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seedranker-mcp",
        description="Run the OpticalSeedRanker MCP server on this computer only.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, choices=["127.0.0.1", "localhost", "::1"])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--patent-seeds", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    try:
        server = create_server(
            index_path=args.index,
            patent_seed_path=args.patent_seeds,
            host=args.host,
            port=args.port,
        )
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
