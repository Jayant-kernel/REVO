"""Adapt source-derived campaigns without editing preserved historical producers."""
import argparse
import runpy
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", choices=("saas", "logistics"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    historical = "run_phase3_breakages.py" if args.contract == "saas" else "run_phase8_logistics_breakages.py"
    namespace = runpy.run_path(str(root / "scratch/funnel_experiment/evidence" / historical))
    variants = namespace["VARIANTS"]
    previous = variants["drop_sequence_tie_break"]
    replacement = ((('(_timestamp(row["occurred_at"]), row["sequence"], row["record_id"])',
                    '(_timestamp(row["occurred_at"]),)'),), *previous[1:])
    variants["drop_sequence_tie_break"] = replacement
    # The original fail-closed source-count and failing-node checks remain intact.
    sys.argv = [str(Path(__file__)), "--output", str(args.output)]
    result = namespace["main"]()
    if result:
        raise SystemExit(result)


if __name__ == "__main__":
    main()
