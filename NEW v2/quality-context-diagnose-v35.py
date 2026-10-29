"""Read-only diagnosis of retained workclone qualification; no archive changes."""
import json
from pathlib import Path
import sys
import traceback

WORK = Path(r"C:\Users\jayan\AppData\Local\Temp\opencode\qc35-renewal-v34\release")
sys.path.insert(0, str(WORK / "replay_root/src"))
from verified_data_factory.verification.readiness import qualify
from verified_data_factory.verification import readiness as r
from verified_data_factory.verification.receipt_models import ReceiptV2, ArtifactRef
from verified_data_factory.verification.receipt_validation import DetailValidator, validate_sources, read_json
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification.behavior_authority import public_behavior_map

acceptance = json.loads((WORK / "engineering_acceptance.json").read_text())
result = qualify(WORK / "replay_root", acceptance["members"][0]["quality"]["engineering_record"])
print(json.dumps(result, indent=2))
record = acceptance["members"][0]["quality"]["engineering_record"]
for category in ("rules", "mutation"):
    try:
        parsed = ReceiptV2.model_validate(read_json(WORK / "replay_root", ArtifactRef.model_validate(record["evidence"][category])))
        thresholds = validate_sources(WORK / "replay_root", parsed)
        task = TaskInstance.model_validate(read_json(WORK / "replay_root", parsed.task))
        DetailValidator(WORK / "replay_root", task, public_behavior_map(task), parsed.source_hashes, thresholds).validate(parsed)
    except Exception:
        traceback.print_exc()
try:
    r.effective_evidence(WORK / "replay_root", record)
except Exception:
    traceback.print_exc()
