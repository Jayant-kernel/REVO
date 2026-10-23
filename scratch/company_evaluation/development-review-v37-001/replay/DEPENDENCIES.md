# Dependency census and closure decision

## Runtime separation

| Workflow | Required installed dependencies |
| --- | --- |
| A illustrative | Python standard library + DuckDB (tested 1.5.5) |
| B1 check-inputs / historical inspection | Python standard library only |
| B2 full native | Windows; pinned Python 3.12.10; DuckDB 1.5.5, Pydantic 2.13.5, PyYAML 6.0.3, httpx 0.28.1, PyArrow 25.0.1; existing configured native/container sandbox and its retained runtime inputs |

The B2 versions come from the pinned `engineering_dependencies.json`, not a new
dependency selection. Bundled validation verifies runtime identity. Nothing here
auto-installs dependencies, downloads images, invokes a model, changes privileges
or changes configuration. Missing native prerequisites are a run blocker, not a
reason to downgrade the checks. B2 may exercise the existing sandbox/container
backend as the original bundled validator requires; only run in its assigned lane.

## Why 123,765 release files exist

The frozen baseline `../audit/baseline.json` reports **123,765 manifest-declared
release files / 528,602,604 bytes** and **123,854 total package files / 602,194,502
bytes**. These are distinct counts: the package includes packet, anchor, context,
driver and other non-manifest material. The release count is not an examples count.

Inspection of the pinned manifest/dependency JSON gives the exact additive census:

| Contributor | Files |
| --- | ---: |
| Initially discovered dependencies | 49,029 |
| Additional recursively retained replay inputs | 74,726 |
| Non-replay-root release assets (data + nine packaging assets) | 10 |
| **Total declared release assets** | **123,765** |

Thus `replay_root/` contains 123,755 declared files. Of the 49,029 discovered
dependencies, 48,025 are under `scratch/company_evaluation/`, 449 under
`scratch/funnel_experiment/`, and 555 elsewhere.

The precise mechanism is in bundled
`release/replay_root/src/verified_data_factory/products/release.py:314-347`:

1. Recursively discover `.py`, `.yaml`, `.json` files under `src`, `scripts`,
   `configs`, `templates`, `tests`, excluding `__pycache__`.
2. Recursively discover **every `.py`** under `scratch`, plus JSON filenames
   containing `threshold`, excluding `__pycache__`; include `pyproject.toml`.
   This broad scratch policy retains historical/copied operator code too, rather
   than deriving an import-only closure for these eight rows.
3. `acceptance.retain_replay_inputs` copies those files and recursively walks
   selected `engineering_record` evidence. Every exact `{path, sha256}` reference
   and `source_hashes` entry is copied and checked; schema-v2 qualification
   receipts with `task` and `details` are recursively inspected. It also retains
   ACTIVE matching rule bundles from the evidence index, events/index files and
   quarantine manifest. Already-copied paths are deduplicated.
4. Every resulting file in `replay_root` is appended to the release manifest,
   along with data and packaging assets. Native replay checks those bindings.

The baseline's final large subtrees are:

| Final release subtree | Files | Bytes |
| --- | ---: | ---: |
| `replay_root/scratch/company_evaluation` | 48,026 | 309,335,057 |
| `replay_root/scratch/funnel_experiment` | 75,170 | 204,161,602 |
| All other declared assets | 569 | 15,105,945 |

The two scratch subtrees alone account for 123,196 files, explaining nearly all
of the size. Retained recursive evidence, as well as broad discovery, matters:
an eight-fixture bundle cannot substitute for this trust/qualification closure.

## Decision

**Keep the pinned tree intact for B.** No smaller closure was demonstrated.
Deleting apparently historical files would change the pinned manifest and can
also remove nested receipt/source bindings required by qualification. A smaller
future authoritative package would need its own proven transitive closure,
fresh manifest/anchor/context and full native qualification; that is outside this
preview. A remains the deliberately small illustrative reviewer layer.
