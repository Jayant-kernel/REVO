# Phase 7 Full Regression

Command: `python -m pytest -q`

Terminal result: `1064 passed in 1945.14s (0:32:25)`.

Certification launch identity is recorded in
`phase7-certified-regression-launch.json`; post-run identity is recorded in
`phase7-post-regression-paused-run-guard.json`. `git_head`,
`tracked_diff_sha256`, and `untracked_source_content_manifest_sha256` match.
The untracked path manifest differs only because Phase 7 created its evidence
artifacts. Both frozen paused-run guards passed with all 15 baseline files.
