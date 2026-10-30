"""Pin the independently reviewed bounded handoff without modifying evidence."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("consolidation", ROOT / "NEW v2/consolidate-v35.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.stable()
report = c.OUT / "INDEPENDENT-VERIFICATION-v2.md"
assert "VERIFY-PASS" in report.read_text(encoding="utf-8")
summary = c.load(c.OUT / "summary-v2.json")
assert summary["accepted80"] == 0 and summary["score"] == "NOT_COMPUTABLE"
assert summary["frozen80_normalized_sql_text_target"]["passed"] is False
protected = c.load(c.OUT / "inventory.json")["protected_hashes"]
assert all(c.sha(Path(p)) == digest for p, digest in protected.items())
files = ["inventory.json", "summary-v2.json", "HANDOFF.md", "INDEPENDENT-VERIFICATION.md",
         "INDEPENDENT-VERIFICATION-v2.md", "negative-controls.json", "focused-tests.xml"]
c.save(c.OUT / "FINAL-STATUS.json", dict(status="BOUNDED_MILESTONE_COMPLETE_WITH_DISCLOSED_LIMITS",
    independent_verdict="VERIFY-PASS_ROUND2", proof_hashes={name: c.sha(c.OUT / name) for name in files},
    delivered_representatives=8, target_new_deliveries=2, accepted80=0, company_examples=0,
    score="NOT_COMPUTABLE", full_same_source_suite="NOT_CERTIFIED", human_review="PENDING", sharing="BLOCKED",
    budget=summary["budget"], model_calls_this_consolidation=0))
print("FINAL_BOUNDED_CLOSEOUT_PINNED; full80=0; score=NOT_COMPUTABLE")
