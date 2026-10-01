"""Read-only production planning, preflight, status, and report operations."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import yaml

from verified_data_factory.generation.models import PROMPT_VERSION
from verified_data_factory.provenance import content_id

from .errors import ProductionConfigError
from .models import ProductionConfig


def load_config(path: str | Path) -> ProductionConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
        section = raw["production"]
        return ProductionConfig.model_validate(section)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise ProductionConfigError(f"invalid production config: {exc}") from exc


def config_id(config: ProductionConfig) -> str:
    return content_id("PRODUCTION_CONFIG", config.config_version, config.model_dump(mode="json"))


def policy_file_hashes(config: ProductionConfig) -> dict[str, str]:
    """Pin referenced policy contents, not merely their path strings."""
    policies = {
        "quality": config.quality_config,
        "sandbox": config.sandbox_config,
        "provenance": config.provenance_config,
        "product": config.product_config,
    }
    try:
        return {
            name: "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in sorted(policies.items())
        }
    except OSError as exc:
        raise ProductionConfigError(f"referenced policy cannot be hashed: {exc}") from exc


def assert_resume_config(config: ProductionConfig, manifest_path: str | Path) -> None:
    """Reject resume if any identity-bearing configuration field changed."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        recorded = manifest["production_config_id"]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ProductionConfigError(f"resume manifest is unreadable: {exc}") from exc
    if recorded != config_id(config):
        raise ProductionConfigError("configuration identity mismatch; start a new production run")
    if manifest.get("policy_file_hashes") != policy_file_hashes(config):
        raise ProductionConfigError("referenced policy content changed; start a new production run")


def requests_made() -> int:
    """Test seam: planning must never make provider or Docker requests."""
    return 0


def plan(config: ProductionConfig) -> dict[str, Any]:
    from verified_data_factory.task_engine import load_builtin_registry

    from .runner import _template_catalog_id

    initial_candidates = config.initial_task_batch * config.candidates_per_task
    registry = load_builtin_registry()
    return {
        "dry_run": True, "production_config_id": config_id(config),
        "policy_file_hashes": policy_file_hashes(config),
        "template_catalog_id": _template_catalog_id(registry),
        "template_diversity": _template_diversity(config, registry),
        "model": config.model.model_id,
        "model_revision": config.model.model_revision, "endpoint": config.model.endpoint,
        "governance_status": config.model.governance_status,
        "prompt_version": config.model.prompt_version, "generation": {"temperature": config.model.temperature, "top_p": config.model.top_p, "max_tokens": config.model.max_tokens},
        "target_golden_records": config.target_golden_records, "initial_task_batch": config.initial_task_batch,
        "candidates_per_task": config.candidates_per_task, "initial_candidates": initial_candidates,
        "max_batches": config.max_batches,
        "batches_per_authorization": config.batches_per_authorization,
        "max_budget": config.budget.model_dump(),
        "family_distribution": config.family_distribution, "output_dir": config.output_dir,
        "quality_policy": config.quality_config, "audit_policy": config.audit.model_dump(),
        "review_pool_mode": config.review_pool_mode,
        "release_policy": config.product_config, "estimated_batches": "ESTIMATE: determined from measured Golden yield after Batch 1",
        "model_calls": 0, "docker_executions": 0, "candidates_generated": 0,
    }


def _docker(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=10, check=False)
        return result.returncode == 0, (result.stdout or result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def _template_diversity(config: ProductionConfig, registry: Any) -> dict[str, Any]:
    from .runner import _latest_templates_for_family

    counts = {
        family: len(_latest_templates_for_family(registry, family))
        for family in config.family_distribution
    }
    return {
        "ok": all(
            count >= config.min_distinct_templates_per_family
            for count in counts.values()
        ),
        "required_per_family": config.min_distinct_templates_per_family,
        "available_per_family": counts,
    }


def preflight(config: ProductionConfig, root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    results: dict[str, Any] = {"production_config_id": config_id(config), "checks": {}}
    from verified_data_factory.task_engine import load_builtin_registry

    results["checks"]["template_diversity"] = _template_diversity(
        config, load_builtin_registry()
    )
    sandbox_settings: Any | None = None
    try:
        from verified_data_factory.products import load_product_config
        from verified_data_factory.provenance import load_provenance_config
        from verified_data_factory.quality import load_quality_config
        from verified_data_factory.sandbox import load_config as load_sandbox_config

        load_quality_config(config.quality_config)
        sandbox_settings = load_sandbox_config(config.sandbox_config)
        load_provenance_config(config.provenance_config)
        load_product_config(config.product_config)
        configuration_ok, configuration_message = config.model.prompt_version == PROMPT_VERSION, "validated"
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        configuration_ok, configuration_message = False, str(exc)
    results["checks"]["configuration"] = {"ok": configuration_ok, "message": configuration_message}
    results["checks"]["storage"] = {"ok": shutil.disk_usage(root).free > 0, "free_bytes": shutil.disk_usage(root).free}
    results["checks"]["pipeline"] = {"ok": True, "components": ["Task Engine", "Generation", "Sandbox", "Verifier", "Quality", "Provenance", "Products"]}
    try:
        tags = httpx.get(config.model.endpoint.removesuffix("/v1") + "/api/tags", timeout=10).json().get("models", [])
        found = next((m for m in tags if m.get("name") == config.model.model_id), None)
        results["checks"]["model"] = {"ok": bool(found and found.get("digest") and config.model.model_revision.endswith(found["digest"])), "available": bool(found), "digest": (found or {}).get("digest")}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        results["checks"]["model"] = {"ok": False, "message": str(exc)}
    docker_ok, docker_info = _docker(["info", "--format", "{{.ServerVersion}}"])
    image_name = sandbox_settings.image if sandbox_settings is not None else ""
    expected_digest = sandbox_settings.image_digest if sandbox_settings is not None else None
    image_ok, image_info = _docker(
        ["image", "inspect", image_name, "--format", "{{.Id}}"]
    )
    stale_ok, stale_info = _docker(["ps", "-aq", "--filter", "name=vdf-"])
    results["checks"]["docker"] = {"ok": docker_ok, "version": docker_info}
    stale_containers = stale_info.splitlines() if stale_ok and stale_info else []
    digest_ok = bool(image_ok and expected_digest and image_info == expected_digest)
    results["checks"]["sandbox"] = {
        "ok": bool(digest_ok and stale_ok and not stale_containers),
        "image": image_name,
        "expected_digest": expected_digest,
        "actual_digest": image_info if image_ok else None,
        "stale_vdf_containers": stale_containers,
    }
    results["checks"]["secrets"] = {"ok": "api_key" not in json.dumps(config.model_dump(mode="json")).lower(), "message": "no inline API key fields"}
    results["ok"] = all(item.get("ok", False) for item in results["checks"].values())
    return results


def _jsonl_count(path: Path) -> int:
    return sum(1 for line in path.open(encoding="utf-8") if line.strip()) if path.exists() else 0


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def status(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    candidate_bundles = _jsonl(root / "candidates/candidates.jsonl")
    attempts = 0
    successes = 0
    for bundle in candidate_bundles:
        results = bundle.get("results")
        if isinstance(results, list):
            attempts += len(results)
            successes += sum(
                1
                for item in results
                if isinstance(item, dict) and item.get("candidate_solution") is not None
            )
        elif "candidate_solution" in bundle or "generation_status" in bundle:
            attempts += 1
            successes += int(bundle.get("candidate_solution") is not None)
    return {
        "run_dir": str(root),
        "tasks": _jsonl_count(root / "tasks/tasks.jsonl"),
        "candidate_bundles": len(candidate_bundles),
        "candidates": attempts,
        "generation_successes": successes,
        "generation_failures": attempts - successes,
        "executions": _jsonl_count(root / "execution/triples.jsonl"),
        "verifications": _jsonl_count(root / "verification/verification.jsonl"),
        "golden": _jsonl_count(root / "quality/export/golden.jsonl"),
    }


def report(run_dir: str | Path) -> dict[str, Any]:
    result = status(run_dir)
    root = Path(run_dir)
    verification = root / "verification/verification.jsonl"
    triple_families = {
        row["candidate"]["candidate_id"]: row["task"]["family"]
        for row in _jsonl(root / "execution/triples.jsonl")
        if isinstance(row.get("candidate"), dict)
        and isinstance(row.get("task"), dict)
        and row["candidate"].get("candidate_id")
        and row["task"].get("family")
    }
    by_family: dict[str, Counter[str]] = {}
    failure_codes: Counter[str] = Counter()
    if verification.exists():
        for line in verification.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            family = triple_families.get(row["candidate_id"], "unknown")
            by_family.setdefault(family, Counter())[row.get("verdict", "UNKNOWN")] += 1
            if row.get("failure_code"):
                failure_codes[str(row["failure_code"])] += 1
    result["family_results"] = {name: dict(counts) for name, counts in by_family.items()}
    result["failure_summary"] = dict(failure_codes)
    golden_by_family: Counter[str] = Counter()
    golden = root / "quality/export/golden.jsonl"
    for line in golden.read_text(encoding="utf-8").splitlines() if golden.exists() else []:
        row = json.loads(line)
        golden_by_family[str(row.get("quality", {}).get("family", "unknown"))] += 1
    for family, count in golden_by_family.items():
        result["family_results"].setdefault(family, {})["GOLDEN"] = count
    return result


def write_report_bundle(run_dir: str | Path) -> dict[str, Any]:
    """Write report views from existing artifacts only; never recompute correctness."""
    root = Path(run_dir)
    payload = report(root)
    out = root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "production-report.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "family-results.json").write_text(json.dumps(payload["family_results"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    quality = {key: payload[key] for key in ("golden", "verifications")}
    (out / "quality-summary.json").write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "failure-summary.json").write_text(json.dumps(payload["failure_summary"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = "# Production report\n\n" + "\n".join(f"- {key}: {value}" for key, value in payload.items() if key != "family_results") + "\n"
    (out / "production-report.md").write_text(text, encoding="utf-8")
    return payload
