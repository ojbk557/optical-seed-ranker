from __future__ import annotations

import csv
from html import escape
from pathlib import Path
from typing import Iterable

from .models import ScoreBreakdown, TargetSpec

COMPONENTS = (
    ("f_number", "f_number"),
    ("full_fov", "field"),
    ("architecture", "architecture"),
    ("spectrum", "spectrum"),
    ("geometry", "geometry"),
    ("complexity", "complexity"),
)


def _csv_value(values, name: str) -> str:
    value = values.get(name)
    return "" if value is None else f"{value:.6f}"


def write_ranking_csv(results: Iterable[ScoreBreakdown], path: str | Path) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(results)
    fields = [
        "rank",
        "seed_id",
        "metadata_score",
        "f_number_score",
        "field_score",
        "architecture_score",
        "spectrum_score",
        "geometry_score",
        "complexity_score",
        "f_number_weight",
        "field_weight",
        "architecture_weight",
        "spectrum_weight",
        "geometry_weight",
        "complexity_weight",
        "seed_f_number",
        "seed_full_fov_deg",
        "seed_focal_length_mm",
        "scale_factor",
        "element_count",
        "surface_count",
        "lens_type",
        "reference",
        "source",
        "source_path",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, result in enumerate(rows, start=1):
            seed = result.seed
            writer.writerow(
                {
                    "rank": rank,
                    "seed_id": seed.seed_id,
                    "metadata_score": f"{result.metadata_score:.3f}",
                    **{
                        f"{column}_score": _csv_value(result.component_scores, name)
                        for name, column in COMPONENTS
                    },
                    **{
                        f"{column}_weight": _csv_value(result.used_weights, name)
                        for name, column in COMPONENTS
                    },
                    "seed_f_number": seed.f_number,
                    "seed_full_fov_deg": seed.full_fov_deg,
                    "seed_focal_length_mm": seed.focal_length_mm,
                    "scale_factor": f"{result.scale_factor:.6f}",
                    "element_count": seed.element_count,
                    "surface_count": seed.surface_count,
                    "lens_type": seed.lens_type,
                    "reference": seed.reference,
                    "source": seed.source,
                    "source_path": seed.source_path or "",
                }
            )
    return len(rows)


def _score_cell(result: ScoreBreakdown, name: str) -> str:
    value = result.component_scores.get(name)
    if value is None:
        return "—"
    weight = result.used_weights.get(name)
    if weight is None:
        return f"{value:.1f} score"
    return f"{value:.1f} score · {weight * 100:.1f}% normalized weight"


def write_html_report(
    results: Iterable[ScoreBreakdown], spec: TargetSpec, path: str | Path
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(results)
    table_rows: list[str] = []
    for rank, result in enumerate(rows, start=1):
        seed = result.seed
        table_rows.append(
            "<tr>"
            f"<td><span class='rank'>{rank}</span></td>"
            f"<td><strong>{escape(seed.seed_id)}</strong><small>{escape(seed.reference)}</small></td>"
            f"<td><span class='score'>{result.metadata_score:.1f}</span></td>"
            f"<td>{seed.f_number:.3g}<small>{_score_cell(result, 'f_number')}</small></td>"
            f"<td>{seed.full_fov_deg:.2f}°<small>{_score_cell(result, 'full_fov')}</small></td>"
            f"<td>{escape(seed.lens_type)}<small>{_score_cell(result, 'architecture')}</small></td>"
            f"<td>{_score_cell(result, 'spectrum')}</td>"
            f"<td>{_score_cell(result, 'geometry')}</td>"
            f"<td>{seed.element_count} / {seed.surface_count}<small>{_score_cell(result, 'complexity')}</small></td>"
            f"<td>{result.scale_factor:.3f}×<small>{seed.focal_length_mm:.2f} → {spec.focal_length_mm:.2f} mm</small></td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(spec.name)} · OpticalSeedRanker</title>
  <style>
    :root {{ color-scheme: light; --ink:#13231d; --muted:#617269; --line:#dfe7e2; --paper:#f7faf8; --accent:#166b4f; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:48px 24px 80px; }}
    header {{ display:grid; grid-template-columns:1.5fr 1fr; gap:32px; align-items:end; margin-bottom:28px; }}
    h1 {{ margin:0 0 8px; font-size:clamp(32px,5vw,58px); line-height:1; letter-spacing:-.04em; }}
    p {{ color:var(--muted); margin:0; }}
    .target {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line); border:1px solid var(--line); border-radius:18px; overflow:hidden; }}
    .target div {{ background:white; padding:18px; }}
    .target strong {{ display:block; font-size:22px; }}
    .target span, small {{ display:block; color:var(--muted); font-size:12px; margin-top:3px; }}
    .note {{ background:#e8f3ee; border:1px solid #cce3d8; padding:16px 18px; border-radius:14px; margin:24px 0; }}
    .table-wrap {{ overflow:auto; background:white; border:1px solid var(--line); border-radius:18px; }}
    table {{ width:100%; border-collapse:collapse; min-width:1280px; }}
    th,td {{ padding:15px 14px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{ color:var(--muted); font-size:11px; letter-spacing:.08em; text-transform:uppercase; background:#fbfcfb; }}
    tr:last-child td {{ border-bottom:0; }}
    .rank {{ display:grid; place-items:center; width:28px; height:28px; border-radius:50%; background:var(--ink); color:white; font-weight:700; }}
    .score {{ color:var(--accent); font-size:23px; font-weight:800; }}
    footer {{ margin-top:22px; color:var(--muted); }}
    @media(max-width:760px) {{ header {{ grid-template-columns:1fr; }} .target {{ grid-template-columns:1fr 1fr; }} }}
  </style>
</head>
<body><main>
  <header>
    <div><p>OpticalSeedRanker · metadata shortlist</p><h1>{escape(spec.name)}</h1><p>Transparent ranking before target feasibility and equal-budget Zemax optimization.</p></div>
    <div class="target">
      <div><strong>{spec.focal_length_mm:.2f} mm</strong><span>target EFL</span></div>
      <div><strong>F/{spec.f_number:.3f}</strong><span>target aperture</span></div>
      <div><strong>{spec.diagonal_full_field_deg:.2f}°</strong><span>diagonal full field</span></div>
      <div><strong>{spec.corner_image_height_mm:.2f} mm</strong><span>corner image height</span></div>
      <div><strong>{spec.entrance_pupil_mm:.2f} mm</strong><span>entrance pupil</span></div>
      <div><strong>{min(spec.wavelengths_nm):.0f}–{max(spec.wavelengths_nm):.0f} nm</strong><span>target spectrum</span></div>
    </div>
  </header>
  <div class="note"><strong>Interpretation:</strong> this is a metadata shortlist, not a final lens recommendation. Each candidate still needs scaling, ray-trace feasibility checks, and the same optimization budget.</div>
  <div class="table-wrap"><table>
    <thead><tr><th>Rank</th><th>Seed</th><th>Metadata</th><th>F/#</th><th>Full field</th><th>Architecture</th><th>Spectrum</th><th>Geometry</th><th>Complexity</th><th>Scale</th></tr></thead>
    <tbody>{''.join(table_rows)}</tbody>
  </table></div>
  <footer>Generated by OpticalSeedRanker 0.1.1. Missing spectrum and packaging features were excluded and available weights were renormalized.</footer>
</main></body></html>"""
    output_path.write_text(html, encoding="utf-8")
