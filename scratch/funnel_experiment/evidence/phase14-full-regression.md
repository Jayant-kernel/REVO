# Phase 14 Certified Full Regression

Command: `python -m pytest -q`

Terminal result: `1085 passed in 1268.53s (0:21:08)`.

The pre-regression and post-regression frozen-run guards both passed with 15
baseline files, no missing, unexpected, or mismatched paths. Their tracked-diff
SHA-256 and untracked-source-content-manifest SHA-256 values are identical:

- `tracked_diff_sha256`: `5c903194612084605616bdea28dd022acf3747bbecba1157fb2bf3b2ae0b7cde`
- `untracked_source_content_manifest_sha256`: `79b19e450ac59c12f3446a46edba489c1bdffcf41ef370cc76f1eb3641f4a451`

The untracked path manifest changed only because Phase 14 scratch evidence was
materialized between guards.
