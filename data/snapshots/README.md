Raw snapshots (`<source>/<xx>/<sha256>.json.gz`) and `manifest.jsonl`. Git-ignored while source terms are unverified
(see docs/source-matrix.md). Consequence: a clean checkout has no snapshots, so `make ingest` must run before `make replay`.
