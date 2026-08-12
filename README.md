# OpticalSeedRanker

[![tests](https://github.com/ojbk557/optical-seed-ranker/actions/workflows/tests.yml/badge.svg)](https://github.com/ojbk557/optical-seed-ranker/actions/workflows/tests.yml)

OpticalSeedRanker finds the optical starting point that is **easiest to adapt to a target specification**. It does not ask an AI to guess a lens from a prompt.

The engineering workflow is deliberately split into measurable stages:

```text
seed sources -> normalized features -> metadata shortlist
             -> target feasibility -> equal-budget optimization -> final rank
```

V0.1 implements the first stage with the open [LensLibrary](https://github.com/nzhagen/LensLibrary): specification validation, diagonal-field derivation, hard conjugate filtering, asymmetric F-number/field penalties, focal-length scaling, CSV ranking, and an HTML report.

## Why this is a separate project

- **OpticalSeedRanker** answers: “Which architecture should we start from?”
- The companion [OpticalSeedOptimizer](https://github.com/ojbk557/optical-seed-optimizer) answers: “Given this seed, how do we turn it into a final, reviewable design?”

They can share schemas and optical analysis code, but their datasets, benchmarks, and success metrics are different.

## Quick start

```bash
git clone https://github.com/nzhagen/LensLibrary.git data/external/LensLibrary
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"

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

## Scoring rules in V0.1

F-number and field penalties are asymmetric:

- A faster seed can usually be stopped down; a slower seed is penalized more because opening it exposes uncorrected marginal rays.
- A wider seed can usually be cropped; a narrower seed is penalized more because expanding its field creates new off-axis aberrations.
- Focal length is reported as a scale factor rather than treated as a dominant distance, because a lens architecture can be scaled while roughly preserving F/# and angular field.
- Missing feature groups are not silently scored as perfect. Their weights are excluded and the available weights are renormalized.
- A monochromatic target is supported: uncovered spectral distance is normalized by the target wavelength instead of a zero-width band.
- V0.1 ranks conventional objectives with full field below 180°. Fisheye/panoramic and spectrometer rows are marked ineligible until they have dedicated field models.

The report exposes every component score. There is no opaque single “AI confidence” number.

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

- V0.2: parse real `.zmx`/`.zar` files with `ray-optics` and enrich topology, glass, wavelength, track, and stop features.
- V0.3: optional Windows + OpticStudio validation through ZOS-API.
- V0.4: give every shortlisted seed identical variables, merit function, and optimization budget; rank adaptability.
- V0.5: use AI only for natural-language-to-YAML conversion and evidence-grounded report explanations.

Commercial software and licenses are never bundled with this repository. Private `.zos`, `.zar`, and raw patent files are ignored by default.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

The code is MIT licensed. External optical files retain their original licenses and terms; the repository stores source attribution and hashes instead of republishing restricted files.
