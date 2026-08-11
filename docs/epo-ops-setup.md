# EPO OPS setup

EPO Open Patent Services (OPS) is an optional discovery provider. LensLibrary indexing and local ranking work without credentials.

## Create credentials

1. Register at <https://developers.epo.org/>.
2. Sign in and create an application under **My Apps**.
3. Copy the application's consumer key and consumer secret into local environment variables:

   ```powershell
   $env:EPO_OPS_KEY = "your-consumer-key"
   $env:EPO_OPS_SECRET = "your-consumer-secret"
   ```

   Do not paste the values into issues, chat messages, commits, screenshots, or configuration files. `.env` is ignored and `.env.example` contains names only.

## Provider boundary

`EpoOpsProvider` implements the common `PatentProvider` protocol. It performs OAuth 2.0 client-credentials authentication, builds optics-scoped CQL, requests at most 100 results at a time, and normalizes OPS XML into `PatentRecord` objects.

The framework intentionally does not run a live request during tests. Tests inject recorded XML so CI never consumes quota or secrets. A future `seedranker patents search` command can compose this provider with caching, provenance storage, family deduplication, and prescription extraction.

## Official references

- EPO OPS portal: <https://developers.epo.org/>
- EPO OPS product and fair-use page: <https://www.epo.org/en/searching-for-patents/data/web-services/ops>
- OPS 3.2 reference guide: <https://link.epo.org/web/searching-for-patents/data/en-ops-v3.2-documentation-version-1.3.20.pdf>
