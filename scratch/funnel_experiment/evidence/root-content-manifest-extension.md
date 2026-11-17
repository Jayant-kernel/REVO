# Source Content Manifest Extension

The untracked source-content manifest now includes content hashes for every regular
file at the repository root in addition to untracked files under `configs/`,
`docs/`, `manifests/`, `scripts/`, `src/`, `templates/`, and `tests/`.

This covers root-level project and configuration files, including ignored `.env`
style files if present, without recording their contents. `scratch/` remains
excluded from content hashing and covered only by the untracked-path manifest.
