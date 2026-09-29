"""Production-preparation commands. `plan` is dry; no command generates by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .production import (
    assert_resume_config,
    load_config,
    plan,
    preflight,
    status,
    write_report_bundle,
)
from .production.runner import run_authorized


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def cmd_plan(args: argparse.Namespace) -> int:
    _print(plan(load_config(args.config)))
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    result = preflight(load_config(args.config))
    _print(result)
    return 0 if result["ok"] else 2


def cmd_status(args: argparse.Namespace) -> int:
    _print(status(args.run))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    payload = write_report_bundle(args.run)
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(payload)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not args.execute:
        raise SystemExit("Refusing to generate. Use preflight and plan; a future authorized run must explicitly pass --execute.")
    run_authorized(load_config(args.config), args.run, execute=True)
    _print({"started": True, "run": args.run})
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    assert_resume_config(load_config(args.config), Path(args.run) / "manifests/run-manifest.json")
    _print({"resume_allowed": True, "message": "configuration identity matches; no generation was started"})
    return 0


def register_production_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    production = subparsers.add_parser("production", help="Production planning and preflight")
    psub = production.add_subparsers(dest="production_command", required=True)
    for name, func in (("plan", cmd_plan), ("preflight", cmd_preflight)):
        parser = psub.add_parser(name)
        parser.add_argument("--config", required=True)
        parser.set_defaults(func=func)
    p_status = psub.add_parser("status")
    p_status.add_argument("--run", required=True)
    p_status.set_defaults(func=cmd_status)
    p_report = psub.add_parser("report")
    p_report.add_argument("--run", required=True)
    p_report.add_argument("--output", default=None)
    p_report.set_defaults(func=cmd_report)
    p_run = psub.add_parser("run", help="Execute one guarded, explicitly authorized batch")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--run", required=True)
    p_run.add_argument("--execute", action="store_true", help="Required explicit authorization")
    p_run.set_defaults(func=cmd_run)
    p_resume = psub.add_parser("resume", help="Validate immutable configuration before a future resume")
    p_resume.add_argument("--config", required=True)
    p_resume.add_argument("--run", required=True)
    p_resume.set_defaults(func=cmd_resume)
