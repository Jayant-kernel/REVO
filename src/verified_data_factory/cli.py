"""CLI for the Data Factory (Phases 1-5).

Thin wrappers only — business logic lives in ``task_engine``,
``generation``, ``verification``, and ``quality``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verified_data_factory.generation.provider import Provider
from verified_data_factory.task_engine import (
    deserialize_task,
    generate_batch,
    generate_task,
    get_template,
    list_templates,
    load_builtin_registry,
    recreate_task,
    serialize_task,
    write_jsonl,
)


def cmd_list(args: argparse.Namespace) -> int:
    registry = load_builtin_registry()
    for t in list_templates(registry, args.family):
        print(f"{t.template_id}  v{t.version}  [{t.family}]  d{t.difficulty}  {t.description}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    registry = load_builtin_registry()
    t = get_template(registry, args.template)
    print(json.dumps(t.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    registry = load_builtin_registry()
    if args.template:
        print(serialize_task(generate_task(get_template(registry, args.template), args.seed)))
    else:
        templates = list_templates(registry)
        for i in range(args.count):
            template = templates[i % len(templates)]
            print(serialize_task(generate_task(template, args.seed + i)))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    task = deserialize_task(Path(args.file).read_text(encoding="utf-8-sig"))
    print(f"OK: {task.task_id}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    import yaml

    registry = load_builtin_registry()
    catalog_path = Path(args.catalog) if args.catalog else None
    tasks = []
    if catalog_path and catalog_path.is_file():
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        for entry in catalog.get("templates", []):
            template = registry.get(entry["template_id"], entry.get("version"))
            tasks.extend(generate_batch(template, list(entry.get("seeds", []))))
    else:
        templates = registry.list()
        seeds = list(range(args.seed, args.seed + args.count))
        per = max(1, args.count // max(1, len(templates)))
        for template in templates:
            batch_seeds = seeds[:per]
            seeds = seeds[per:]
            tasks.extend(generate_batch(template, batch_seeds))
            if len(tasks) >= args.count:
                break
        tasks = tasks[: args.count]
    out = Path(args.output) if args.output else Path("tasks.jsonl")
    write_jsonl(tasks, out)
    print(f"exported {len(tasks)} tasks -> {out}")
    # Reproducibility self-check via the public replay API (raises on mismatch).
    if tasks:
        recreate_task(registry, tasks[0])
    return 0


def _generation_provider(args: argparse.Namespace) -> Provider:
    """Build a generation provider from CLI flags (no secrets on the CLI)."""
    import os

    from verified_data_factory.generation import FakeProvider, create_provider

    if args.provider == "fake":
        return FakeProvider()
    return create_provider(
        args.provider,
        base_url=args.base_url,
        api_key=os.environ.get("VDF_API_KEY"),
        timeout_s=120.0,
        max_retries=2,
        retry_backoff_s=1.0,
    )


def cmd_gen_one(args: argparse.Namespace) -> int:
    from verified_data_factory.generation import (
        GenerationConfig,
        generate_candidates,
        write_candidates_jsonl,
    )

    registry = load_builtin_registry()
    task = generate_task(get_template(registry, args.template), args.seed)
    provider = _generation_provider(args)
    config = GenerationConfig(temperature=args.temperature)
    results = generate_candidates(task, [provider], config, args.num_candidates)
    candidates = [r.candidate_solution for r in results if r.candidate_solution]
    if args.output:
        write_candidates_jsonl(candidates, args.output)
        print(f"exported {len(candidates)}/{len(results)} candidates -> {args.output}")
    else:
        for candidate in candidates:
            print(candidate.model_dump_json(indent=2, by_alias=True))
        for r in results:
            if r.candidate_solution is None:
                print(f"FAILED: {r.failure_reason}")
    return 0


def cmd_gen_batch(args: argparse.Namespace) -> int:
    import yaml

    from verified_data_factory.generation import (
        GenerationConfig,
        generate_for_tasks,
        write_candidates_jsonl,
    )

    registry = load_builtin_registry()
    catalog = yaml.safe_load(Path(args.catalog).read_text(encoding="utf-8"))
    tasks = []
    for entry in catalog.get("templates", []):
        template = registry.get(entry["template_id"], entry.get("version"))
        tasks.extend(generate_batch(template, list(entry.get("seeds", []))))
    provider = _generation_provider(args)
    config = GenerationConfig(temperature=args.temperature)
    results = generate_for_tasks(tasks, [provider], config, args.num_candidates)
    candidates = [r.candidate_solution for r in results if r.candidate_solution]
    write_candidates_jsonl(candidates, args.output)
    failed = len(results) - len(candidates)
    print(
        f"exported {len(candidates)}/{len(results)} candidates -> {args.output} ({failed} failed)"
    )
    return 0


def cmd_verify_one(args: argparse.Namespace) -> int:
    import json

    from verified_data_factory.generation import candidate_from_json
    from verified_data_factory.sandbox.models import ExecutionResult
    from verified_data_factory.task_engine import deserialize_task
    from verified_data_factory.verification import (
        load_verification_config,
        verification_to_json,
        verify_candidate,
    )

    task = deserialize_task(Path(args.task).read_text(encoding="utf-8-sig"))
    candidate = candidate_from_json(Path(args.candidate).read_text(encoding="utf-8-sig"))
    execution = ExecutionResult.model_validate(
        json.loads(Path(args.execution).read_text(encoding="utf-8-sig"))
    )
    config = load_verification_config(args.config) if args.config else None
    result = verify_candidate(task, candidate, execution, config)
    if args.output:
        Path(args.output).write_text(verification_to_json(result), encoding="utf-8")
        print(f"verdict {result.verdict} -> {args.output}")
    else:
        print(verification_to_json(result))
    return 0


def cmd_verify_batch(args: argparse.Namespace) -> int:
    import json

    from verified_data_factory.generation import candidate_from_dict
    from verified_data_factory.sandbox.models import ExecutionResult
    from verified_data_factory.task_engine import task_from_dict
    from verified_data_factory.verification import (
        load_verification_config,
        verify_candidate,
        write_verifications_jsonl,
    )

    config = load_verification_config(args.config) if args.config else None
    results = []
    with open(args.manifest, encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            triple = json.loads(line)
            results.append(
                verify_candidate(
                    task_from_dict(triple["task"]),
                    candidate_from_dict(triple["candidate"]),
                    ExecutionResult.model_validate(triple["execution"]),
                    config,
                )
            )
    write_verifications_jsonl(results, args.output)
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    print(f"verified {len(results)} -> {args.output} {counts}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factory", description="Verified SQL Data Factory")
    sub = parser.add_subparsers(dest="command", required=True)
    task = sub.add_parser("task", help="Task Engine commands")
    tsub = task.add_subparsers(dest="task_command", required=True)

    p_list = tsub.add_parser("list", help="List templates")
    p_list.add_argument("--family", default=None)
    p_list.set_defaults(func=cmd_list)

    p_show = tsub.add_parser("show", help="Show a template")
    p_show.add_argument("template")
    p_show.set_defaults(func=cmd_show)

    p_gen = tsub.add_parser("generate", help="Generate task(s)")
    p_gen.add_argument("--template", default=None)
    p_gen.add_argument("--seed", type=int, default=123)
    p_gen.add_argument("--count", type=int, default=1)
    p_gen.set_defaults(func=cmd_generate)

    p_val = tsub.add_parser("validate", help="Validate a task JSON file")
    p_val.add_argument("file")
    p_val.set_defaults(func=cmd_validate)

    p_exp = tsub.add_parser("export", help="Export tasks to JSONL")
    p_exp.add_argument("--count", type=int, default=100)
    p_exp.add_argument("--seed", type=int, default=123)
    p_exp.add_argument("--catalog", default="configs/task_catalog.yaml")
    p_exp.add_argument("--output", default="tasks.jsonl")
    p_exp.set_defaults(func=cmd_export)

    gen = sub.add_parser("generate", help="Candidate Generation commands")
    gsub = gen.add_subparsers(dest="gen_command", required=True)

    p_one = gsub.add_parser("one", help="Generate candidate(s) for one task")
    p_one.add_argument("--template", required=True)
    p_one.add_argument("--seed", type=int, default=123)
    p_one.add_argument("--provider", default="fake", help="qwen | devstral | fake")
    p_one.add_argument("--base-url", default="http://localhost:8000/v1")
    p_one.add_argument("--num-candidates", type=int, default=1)
    p_one.add_argument("--temperature", type=float, default=0.4)
    p_one.add_argument("--output", default=None, help="JSONL file (stdout if omitted)")
    p_one.set_defaults(func=cmd_gen_one)

    p_batch = gsub.add_parser("batch", help="Generate candidates for catalog tasks")
    p_batch.add_argument("--catalog", default="configs/task_catalog.yaml")
    p_batch.add_argument("--provider", default="fake")
    p_batch.add_argument("--base-url", default="http://localhost:8000/v1")
    p_batch.add_argument("--num-candidates", type=int, default=1)
    p_batch.add_argument("--temperature", type=float, default=0.4)
    p_batch.add_argument("--output", default="candidates.jsonl")
    p_batch.set_defaults(func=cmd_gen_batch)

    ver = sub.add_parser("verify", help="Independent Verification commands")
    vsub = ver.add_subparsers(dest="verify_command", required=True)

    p_vone = vsub.add_parser("one", help="Verify one task/candidate/execution triple")
    p_vone.add_argument("--task", required=True, help="TaskInstance JSON file")
    p_vone.add_argument("--candidate", required=True, help="CandidateSolution JSON file")
    p_vone.add_argument("--execution", required=True, help="ExecutionResult JSON file")
    p_vone.add_argument("--config", default=None, help="verification YAML config")
    p_vone.add_argument("--output", default=None, help="VerificationResult JSON file")
    p_vone.set_defaults(func=cmd_verify_one)

    p_vbatch = vsub.add_parser("batch", help="Verify a JSONL manifest of triples")
    p_vbatch.add_argument(
        "--manifest", required=True, help="JSONL with task/candidate/execution per line"
    )
    p_vbatch.add_argument("--config", default=None)
    p_vbatch.add_argument("--output", default="verifications.jsonl")
    p_vbatch.set_defaults(func=cmd_verify_batch)

    from verified_data_factory.cli_business import register_business_commands
    from verified_data_factory.cli_production import register_production_commands
    from verified_data_factory.cli_products import register_product_commands
    from verified_data_factory.cli_provenance import register_provenance_commands
    from verified_data_factory.cli_quality import register_quality_commands

    register_quality_commands(sub)
    register_provenance_commands(sub)
    register_product_commands(sub)
    register_production_commands(sub)
    register_business_commands(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
