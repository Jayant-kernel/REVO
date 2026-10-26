"""Validate a delivered strict export using its checksum-bound bundled implementation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.release.resolve()
    bundled = root / "replay_root"
    if not (bundled / "src/verified_data_factory/products/validation.py").is_file():
        raise ValueError("bundled implementation missing")
    sys.path.insert(0, str(bundled))
    sys.path.insert(0, str(bundled / "src"))
    from verified_data_factory.products.validation import validate_release

    report = validate_release(root)
    print(json.dumps(report.model_dump(mode="json")))
    return 0 if report.status == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
