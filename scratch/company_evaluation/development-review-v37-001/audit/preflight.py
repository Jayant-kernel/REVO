"""Freeze current delivery identity and exact dependency census without replay."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
EVIDENCE = ROOT / "scratch/company_evaluation/record-delivery-v3/runtime/delivery37"
spec = importlib.util.spec_from_file_location("retained_delivery_operator", EVIDENCE / "operate.py")
assert spec and spec.loader
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)
frozen = op.check()
base = op.d.DURABLE / "original8"
inventory = op.d.trust.inventory(base)
assert inventory == op.d.load(EVIDENCE / "durable-inventory.json")
final = op.d.load(EVIDENCE / "FINAL-RESULT.json")
assert final["eligible"] == final["exported"] == final["successfully_replayed"] == 8
assert op.d.usage() == final["budget"]
manifest = op.d.load(base / "release/manifest.json")
assert len(manifest["files"]) == 123765
assert op.digest(base / "release/manifest.json") == final["manifest_sha256"]
assert op.digest(base / "anchor.json") == final["anchor_sha256"]
assert op.digest(base / "quality-context.json") == final["context_sha256"]
from scripts.engineering_guarded_operation import _snapshot, _sources

# Exact old suite controller scope, without mutating its stored manifests.
controller = ROOT / "scratch/company_evaluation/record-delivery-v3/workstream-c"
source = _snapshot(ROOT, _sources(ROOT) + [ROOT / "governance"] + list(controller.glob("*.py")), source=True)
assert source == op.d.load(controller / "full-suite-v37/source.post.json")
counts: Counter[str] = Counter()
sizes: Counter[str] = Counter()
for entry in manifest["files"]:
    parts = entry["relative_path"].split("/")
    key = "/".join(parts[:3]) if parts[0] == "replay_root" else parts[0]
    counts[key] += 1
    sizes[key] += entry["byte_size"]
report = {"status": "VERIFIED_FROZEN_BASELINE", "at": time.time(),
    "manifest_sha256": final["manifest_sha256"], "anchor_sha256": final["anchor_sha256"],
    "context_sha256": final["context_sha256"], "source_freeze_sha256": final["source_freeze_sha256"],
    "suite_source_sha256": op.digest(controller / "full-suite-v37/source.post.json"),
    "eligible": 8, "replayed": 8, "source_current": True, "budget": op.d.usage(),
    "package_files": len(inventory),
    "package_bytes": sum(op.io_path(base / p).stat().st_size for p in inventory),
    "declared_release_files": len(manifest["files"]),
    "declared_release_bytes": sum(e["byte_size"] for e in manifest["files"]),
    "release_census": {k: {"files": counts[k], "bytes": sizes[k]} for k in sorted(counts)},
    "original_checklist": op.d.load(EVIDENCE / "original16-checklist.json")["summary"],
    "spec_sha256": op.digest(Path(__file__).parent.parent / "SPEC.md"),
    "preserved_identity": "full V36/V37 package inventories and current 687 qualification inputs checked"}
op.save(Path(__file__).parent / "baseline.json", report)
print(json.dumps({k: v for k, v in report.items() if k != "release_census"}, indent=2))
