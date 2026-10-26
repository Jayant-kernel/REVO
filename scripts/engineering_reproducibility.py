"""Persist inspectable source/dependency hashes and explicit runtime versions."""
import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, identity, safety, stamp, write_new


def main() -> None:
    safety()
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="")
    args = parser.parse_args()
    if args.revision and (not args.revision.startswith("r") or not args.revision[1:].isdigit()):
        raise ValueError("revision must be r followed by digits")
    source = identity()
    environment = {name: importlib.metadata.version(name) for name in ("duckdb", "pydantic", "PyYAML", "httpx", "pyarrow", "pytest", "hypothesis")}
    environment.update(python=sys.version, platform=platform.platform())
    suffix = "-" + args.revision if args.revision else ""
    write_new(OUT / f"phase10-reproducibility{suffix}.json", {"created_at": stamp(), "identity": source,
        "environment": environment, "source_invalidation": "Receipt dependencies are validated by SHA256 at every admission",
        "scratch_producers_included": [p for p in source["per_file_manifest"] if p.startswith("scratch/")],
        "replay_commands": ["python -m pytest tests/test_package_a_challenge_repair.py tests/test_engineering_export.py -q"],
        "not_claimed": ["independent environment attestation", "commercial approval", "new model generation"]})
    print(json.dumps({"hashed_files": len(source["per_file_manifest"]), "runtime_versions": environment}, indent=2))


if __name__ == "__main__":
    main()
