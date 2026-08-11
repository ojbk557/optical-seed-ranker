# Patent data architecture

The patent pipeline is not a web scraper and not a language-model recommendation loop. It is a provenance-preserving ETL and optical-validation system.

## Three separate jobs

1. **Discovery** finds patent publications and families with official APIs, CPC/IPC classes, multilingual keywords, citations, dates, and applicants.
2. **Prescription reconstruction** locates numerical examples, converts tables and equations into a normalized optical prescription, and records uncertainty.
3. **Optical validation** checks sign conventions, material definitions, apertures, intersections, focus, and ray-trace feasibility before a record can become a rankable Seed.

No discovery provider is allowed to label a document “valid Seed” by itself.

## Provider priorities

| Provider | Role | Access | Important limit |
|---|---|---|---|
| LensLibrary | Reproducible V0.1 baseline with Zemax files | Local Git clone | Small curated collection, not worldwide |
| EPO OPS | Worldwide discovery, families, bibliographic/legal/full-text/image sources | REST/XML + OAuth app credentials | Quotas, coverage varies by office and document |
| USPTO ODP / PatentsView | Structured US patent and application metadata | REST/JSON + API key | US-only and endpoints can migrate |
| Google Patents Public Datasets | Large-scale SQL/vector discovery | BigQuery API + Google Cloud project | Query cost and dataset-specific coverage |
| WIPO PCT Web Service | Authorized PCT documents | Conditional/paid SOAP service | Public PATENTSCOPE pages prohibit automation/scraping |

Every provider implements `PatentProvider` from `src/optical_seed_ranker/providers/base.py`. Provider credentials remain in environment variables or an ignored secrets file.

## Canonical record and provenance

The normalized record stores:

- provider, publication/application/family identifiers, country and dates;
- title, abstract, applicants, CPC/IPC and source URL;
- full-text/image availability;
- retrieval timestamp, source terms reference, content hash and parser version.

Patent families are deduplicated before document processing. One representative is selected for the best combination of structured text, table quality, language, and image availability; family members remain linked.

## Discovery query

High-recall discovery starts with CPC `G02B`, focusing on:

- `G02B 9/*`: objectives classified by component count and positive/negative arrangement;
- `G02B 13/*`: objectives for specified purposes;
- `G02B 15/*`: variable-magnification objectives, when zoom designs are in scope.

Classification filters are combined with phrases such as `radius of curvature`, `surface number`, `thickness`, `refractive index`, `Abbe number`, `F-number`, `angle of view`, and `numerical example`. Multilingual synonym sets belong to configuration, not hard-coded provider queries.

## Reconstruction state machine

```text
discovered
  -> family_normalized
  -> document_downloaded
  -> example_detected
  -> table_extracted
  -> prescription_normalized
  -> raytrace_checked
  -> human_reviewed (when confidence is low)
  -> seed_ready
```

Each transition writes an immutable event. Failed candidates retain a reason such as `missing_table`, `ambiguous_asphere_formula`, `unknown_glass`, `negative_thickness`, or `raytrace_failure`.

## Extraction confidence

Confidence is computed per field rather than per document. Radius, thickness, glass index, Abbe number, semi-diameter, stop, wavelength, and asphere coefficient each retain:

- raw text/cell coordinates;
- normalized value and unit;
- parser/OCR confidence;
- validation result;
- optional reviewer correction.

LLMs may propose table structure or explain an exception, but deterministic parsers and ray tracing decide whether values are accepted.

## Storage

- SQLite is sufficient for local V0.x metadata, state transitions, and FTS search.
- Raw documents use content-addressed files outside Git; rows store SHA-256 and terms/provenance.
- A later hosted service can move metadata to PostgreSQL and raw blobs to object storage without changing the provider contract.
- `.zos`, `.zar`, company seeds, credentials, and redistribution-restricted patent files are ignored by default.

## Connection to the optimizer

The ranker exports a candidate bundle containing target spec, normalized prescription, source/provenance, scaling factor, score breakdown, and validation artifacts. The optimizer consumes that bundle, works on a copy, and returns a final `.zos` plus a reproducible design report. It never overwrites the source Seed.
