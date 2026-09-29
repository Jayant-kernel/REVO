# Consuming products

The only supported entry point is `products.load_release`:

```python
from verified_data_factory.products import load_release, records_by_split

loaded = load_release("release/")  # raises ProductValidationError on anything malformed
by_split = records_by_split(loaded)
```

Every load re-checks shard checksums, per-record schema conformance
under the release's product profile, and full release validation.
Consumers never see partial data: anything malformed raises instead of
returning a subset.

## Rules for consumers

- Pin `release_id` (content-defined) rather than directory names.
- Pin `schema_name`/`schema_version`; refuse anything your reader does
  not support — the loader already rejects unknown major versions.
- `PUBLIC_EVAL` records carry no `sql`; score against your own harness,
  never by expecting hidden targets.
- Provenance questions (which snapshot? which config? which policy?)
  are answered by `manifest.json`, not by record contents.
- `dataset_card.md` states intended use, metrics, caveats, and
  provenance; treat any claim not present there as unmade.
- Prefer the upstream metrics (`metrics.json`) over recomputing from
  record contents — coverage/duplicate/verification/audit summaries
  are Phase 5 artifacts referenced into the release.

## What consumers must NOT do

Parse `data/` shards directly (bypasses checksum/visibility checks),
repair malformed records, or mix records across releases without
recording both `release_id`s.
