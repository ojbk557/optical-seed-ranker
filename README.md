# OpticalSeedRanker

[![tests](https://github.com/ojbk557/optical-seed-ranker/actions/workflows/tests.yml/badge.svg)](https://github.com/ojbk557/optical-seed-ranker/actions/workflows/tests.yml)

OpticalSeedRanker finds the optical starting point that is **easiest to adapt to a target specification**. It does not ask an AI to guess a lens from a prompt.

The engineering workflow is deliberately split into measurable stages:

```text
seed sources -> normalized features -> metadata shortlist
             -> target feasibility -> equal-budget optimization -> final rank
```

V0.1 implements the first stage with the open [LensLibrary](https://github.com/nzhagen/LensLibrary) and a bundled, evidence-labelled UV patent dataset: specification validation, diagonal-field derivation, hard conjugate filtering, asymmetric F-number/field penalties, focal-length scaling, CSV/JSON ranking, and an HTML report.

## Why this is a separate project

- **OpticalSeedRanker** answers: “Which architecture should we start from?”
- The companion [OpticalSeedOptimizer](https://github.com/ojbk557/optical-seed-optimizer) answers: “Given this seed, how do we turn it into a final, reviewable design?”

They can share schemas and optical analysis code, but their datasets, benchmarks, and success metrics are different.

## Install and run immediately

Python 3.11 or newer is required. The project is distributed as a versioned GitHub Release wheel; it is not currently published to PyPI.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install "https://github.com/ojbk557/optical-seed-ranker/releases/download/v0.1.0/optical_seed_ranker-0.1.0-py3-none-any.whl"

seedranker uv-search --top-k 5 --output uv-shortlist.json
seedranker structure --seed-id CN113504627B --output CN113504627B.json
```

These commands need no external dataset or API credential. The output is an evidence-limited metadata shortlist and a transcribed starting prescription, not a qualified UV design. Verify the release wheel against `SHA256SUMS.txt` on the [v0.1.0 release page](https://github.com/ojbk557/optical-seed-ranker/releases/tag/v0.1.0) when integrity matters.

## Rank a local LensLibrary checkout

```bash
git clone https://github.com/nzhagen/LensLibrary.git data/external/LensLibrary

seedranker index \
  --source data/external/LensLibrary/lens_properties_list.txt \
  --output data/index/seeds.csv

seedranker search \
  --spec specs/large_aperture_60mm.yaml \
  --index data/index/seeds.csv \
  --top-k 10 \
  --output-dir runs/large_aperture_60mm
```

The search command creates:

```text
runs/large_aperture_60mm/
├── ranking.csv
└── report.html
```

`seedranker index` records absolute prescription paths, so the selected row can be handed directly to the companion optimizer:

```powershell
seedopt run `
  --backend zosapi `
  --ranking-csv runs\large_aperture_60mm\ranking.csv `
  --rank 1 `
  --config path\to\optimizer-target.yaml `
  --output-root runs\optimized
```

The selected ranking row must contain an accessible local `source_path`; metadata-only patent rows cannot be passed to OpticStudio until they have been reconstructed as a supported optical file.

## Local MCP server

The optional MCP server exposes the same deterministic ranker to ChatGPT or
another MCP client. It binds to the loopback interface only and does not call an
external AI API.

```powershell
python -m pip install "optical-seed-ranker[mcp] @ https://github.com/ojbk557/optical-seed-ranker/releases/download/v0.1.0/optical_seed_ranker-0.1.0-py3-none-any.whl"
seedranker-mcp
```

Add `--index data/index/seeds.csv` to combine a local LensLibrary index with the bundled records.

The local endpoint is `http://127.0.0.1:8765/mcp`. Test it with MCP Inspector
before connecting a model client. The available tools are:

- `seedranker_derive_uv_target`
- `seedranker_search_uv_structures`
- `seedranker_get_local_structure`
- `seedranker_local_status`

The search combines the generated local LensLibrary index with a small, auditable
set of public UV patent records. The two leading patent records include transcribed
surface tables, so `seedranker_get_local_structure` can return a numerical starting
prescription without any EPO credential or external AI connection. See
[`docs/uv-wide-field-seed-shortlist.md`](docs/uv-wide-field-seed-shortlist.md) for
the current 240-320 nm ranking and its limitations.

Each patent candidate also carries its evidence level, the basis for focal length,
F-number, and field values, and explicit known gaps. Ultra-wide candidates are
flagged when their patent projection model has not been verified against the
rectilinear target convention.

The UV search tool treats an `X by Y` angular field as a rectilinear rectangular
field whose corners touch the circular detector edge. It returns a transparent
metadata shortlist, not a claim that UV glass, MTF, distortion, or illumination
requirements have been met. By default the MCP search excludes geometry-only
records with no documented overlap with the requested wavelength band; this can
be disabled with `require_documented_spectral_overlap=false`. The structure tool
accepts only a seed ID already in
the configured local sources; it reads either a matching Zemax text prescription
or a transcribed patent surface table without exposing an arbitrary filesystem
browser. Optional uniform scaling changes radii, thicknesses, and apertures, but
never improves F-number, field angle, UV transmission, or aberration balance by
itself.

## Scoring rules in V0.1

F-number and field penalties are asymmetric:

- A faster seed can usually be stopped down; a slower seed is penalized more because opening it exposes uncorrected marginal rays.
- A wider seed can usually be cropped; a narrower seed is penalized more because expanding its field creates new off-axis aberrations.
- Focal length is reported as a scale factor rather than treated as a dominant distance, because a lens architecture can be scaled while roughly preserving F/# and angular field.
- A monochromatic target is supported: spectrum mismatch is normalized to the target wavelength when the target span is zero.
- Missing feature groups are not silently scored as perfect. Their weights are excluded and the available weights are renormalized.
- V0.1 ranks conventional objectives with full field below 180°. Fisheye/panoramic and spectrometer rows are marked ineligible until they have dedicated field models.

The report exposes every component score. There is no opaque single “AI confidence” number.

Display scores use `100 * exp(-weighted_distance)`, so extremely difficult
targets retain a monotonic, nonzero ranking instead of collapsing to tied zeros.

## Patent data providers

Worldwide patent ingestion is provider-based. V0.1 includes a tested `PatentProvider` protocol and an EPO OPS adapter for OAuth client credentials, optics-scoped CQL, range control, XML normalization, and provenance. Its HTTP layer is injected in tests, so CI never consumes credentials or quota. LensLibrary indexing remains fully usable without an API account.

Create local credentials only when live discovery is added to the CLI:

```powershell
$env:EPO_OPS_KEY = "your-consumer-key"
$env:EPO_OPS_SECRET = "your-consumer-secret"
```

Never commit or paste these values. See [docs/epo-ops-setup.md](docs/epo-ops-setup.md).

The next provider targets are USPTO Open Data/PatentsView and Google Patents Public Datasets on BigQuery. WIPO PATENTSCOPE pages will not be scraped; programmatic WIPO access requires its authorized data service.

See [docs/patent-data-architecture.md](docs/patent-data-architecture.md) for the provider contract, provenance rules, and patent-to-prescription reconstruction pipeline.

## Roadmap

- V0.2: add `.zar` ingestion and ray-trace feasibility features beyond the current Zemax text-prescription parser.
- V0.3: optional Windows + OpticStudio validation through ZOS-API.
- V0.4: give every shortlisted seed identical variables, merit function, and optimization budget; rank adaptability.
- V0.5: use AI only for natural-language-to-YAML conversion and evidence-grounded report explanations.

Commercial software and licenses are never bundled with this repository. Private `.zos`, `.zar`, and raw patent files are ignored by default.

## Development

```bash
git clone https://github.com/ojbk557/optical-seed-ranker.git
cd optical-seed-ranker
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## License

The code is MIT licensed. External optical files retain their original licenses and terms; the repository stores source attribution and hashes instead of republishing restricted files.
