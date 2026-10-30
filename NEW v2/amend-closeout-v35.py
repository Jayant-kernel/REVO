"""Preserve raw screen; disambiguate selected uniqueness from frozen80 attainment."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("consolidation", ROOT / "NEW v2/consolidate-v35.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

summary = c.load(c.OUT / "summary.json")
old = summary["partial_pool_gates"].pop("normalized_sql_text_variety")
assert old["actual"] == 8 and old["passed"] is True
summary["partial_pool_gates"]["selected_normalized_sql_uniqueness"] = dict(actual=8, target="8 distinct texts among 8 selected rows", passed=True)
summary["frozen80_normalized_sql_text_target"] = dict(actual=8, target=80, passed=False)
summary["raw_screen_interpretation_correction"] = dict(
    raw_screen="partial-pool-screen.json", raw_screen_sha256=c.sha(c.OUT / "partial-pool-screen.json"),
    original_summary_sha256=c.sha(c.OUT / "summary.json"),
    finding="Original screen boolean measures selected-pool uniqueness but its target text says80; preserve raw output and report both denominators explicitly.")
summary["negative_control_scope"] = dict(context_wrapper_controls=24, live_measurement_controls=12,
    context_source_control="altered acceptance digest, not an on-disk source attack", live_validator_context_attacks=0)
summary["status"] = "BOUNDED_CONSOLIDATION_CHECKED_PENDING_INDEPENDENT_RECHECK"
c.stable()
c.save(c.OUT / "summary-v2.json", summary)
print("PRESERVED_RAW_SCREEN; selected uniqueness8/8 PASS; frozen target8/80 FAIL")
