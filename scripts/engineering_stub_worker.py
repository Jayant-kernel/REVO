"""Process-boundary stub for crash/recovery tests; never contacts a model."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.engineering_pipeline import run_slot
from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL


class Stub:
    def __init__(self, root, pause):
        self.root, self.pause = root, pause
    def metadata(self):
        return {"name": "stub", "digest": "stub-only", "thinking": False}
    def generate(self, prompt, seed):
        with (self.root / "provider-count.txt").open("a") as handle:
            handle.write("call\n")
        if self.pause:
            (self.root / "provider-paused").touch()
            while True:
                time.sleep(0.1)
        return SAAS_V2_CHAINED_JOIN_SQL
    def unload(self):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pause", choices=("provider", "response", "evaluation-start", "evaluation-finish", "finalization", "none"), default="none")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    run_slot(args.root, Stub(args.root, args.pause == "provider"),
             ("stub-baseline", "sql.funnel.saas_activation_payment", 2, 0, 1, 0),
              pause_after_response=args.pause == "response", pause_at=args.pause)
