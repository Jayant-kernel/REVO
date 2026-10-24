"""Read-only production planning, preflight, status, and report operations."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import yaml

from verified_data_factory.generation.models import PROMPT_VERSION
from verified_data_factory.provenance import content_id
from verified_data_factory.task_engine.errors import RegistryError

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
    payload = config.model_dump(mode="json")
    if config.schedule_mode == "legacy" and not config.selected_contract_ids:
        # These fields did not exist in frozen legacy configurations, so their
        # defaults must not invalidate an existing manifest on resume.
        payload.pop("schedule_mode")
        payload.pop("selected_contract_ids")
        payload.pop("distinct_contract_selection")
    return content_id("PRODUCTION_CONFIG", config.config_version, payload)


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


def implementation_id() -> str:
    """Bind resume to executable source, including uncommitted local changes."""
    package = Path(__file__).resolve().parents[1]
    files = {
        path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*.py"))
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


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


def _matches_ollama_digest(revision: str, digest: object) -> bool:
    """Match the exact observed Ollama digest while retaining its evidence type."""
    if not isinstance(digest, str):
        return False
    namespace, separator, observed = revision.partition(":")
    return separator == ":" and namespace in {"ollama-digest", "ollama-manifest"} and observed == digest


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


ContractReadiness = Callable[[str], bool]
_READINESS_MANIFEST_VERSIONS = {"1.0", "2.0"}
_READINESS_COLUMNS = (
    "template_validates",
    "fixture_generator",
    "independent_oracle",
    "registry_entry",
    "adversarial_case",
    "reference_sql_mapping",
    "mutation_applicability",
    "focused_test",
)


def _quarantined_contract_ids(manifest_path: Path) -> set[str]:
    """Load Package A's additive selection exclusions, when present."""
    path = manifest_path.parent / "package-a-contract-quarantine.json"
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise ProductionConfigError(f"quarantine file is unreadable: {exc}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("quarantines"), list):
        raise ProductionConfigError("quarantine file has invalid structure")
    ids: set[str] = set()
    for entry in payload["quarantines"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("contract_id"), str)
            or not isinstance(entry.get("contract_version"), int)
            or not isinstance(entry.get("reason"), str)
            or not isinstance(entry.get("evidence_id"), str)
            or not isinstance(entry.get("scope"), list)
            or "production" not in entry["scope"]
        ):
            raise ProductionConfigError("quarantine file has invalid contract entry")
        ids.add(entry["contract_id"])
    return ids


def contract_readiness_from_manifest(path: str | Path) -> ContractReadiness:
    """Load a hash-verified Phase 3 readiness manifest as a scheduler callback."""
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_hash = manifest.pop("manifest_hash")
    except (OSError, AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ProductionConfigError(f"readiness manifest is unreadable: {exc}") from exc
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_hash = "sha256:" + hashlib.sha256(payload).hexdigest()
    if manifest_hash != expected_hash:
        raise ProductionConfigError("readiness manifest hash does not match its contents")
    if manifest.get("manifest_version") == "engineering-3.0":
        from verified_data_factory.verification.readiness import qualify, sha256
        root = Path(__file__).resolve().parents[3]
        try:
            reference = manifest["evidence_index"]
            index_path = (root / reference["path"]).resolve()
            if not index_path.is_relative_to(root) or sha256(index_path) != reference["sha256"]:
                raise ProductionConfigError("engineering readiness evidence index is stale")
            index = json.loads(index_path.read_text(encoding="utf-8"))
            records = index["contracts"]
            if len({(r["contract_id"], r["contract_version"]) for r in records}) != len(records):
                raise ProductionConfigError("duplicate engineering evidence contract")
            expected = {(r["contract_id"], r["template_version"]) for r in manifest["contracts"]}
            if expected != {(r["contract_id"], r["contract_version"]) for r in records}:
                raise ProductionConfigError("engineering manifest and evidence population disagree")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ProductionConfigError(f"engineering readiness evidence invalid: {exc}") from exc
        quarantined = _quarantined_contract_ids(manifest_path)
        def engineering_ready(contract_id: str) -> bool:
            matches = [r for r in records if r["contract_id"] == contract_id]
            return (contract_id not in quarantined and len(matches) == 1
                    and qualify(root, matches[0])["eligible"] is True)
        return engineering_ready
    if manifest.get("manifest_version") not in _READINESS_MANIFEST_VERSIONS:
        raise ProductionConfigError("readiness manifest has an unsupported version")
    columns = manifest.get("readiness_columns")
    contracts = manifest.get("contracts")
    if columns != list(_READINESS_COLUMNS):
        raise ProductionConfigError("readiness manifest has invalid readiness columns")
    if not isinstance(contracts, list):
        raise ProductionConfigError("readiness manifest has invalid contracts")
    statuses: dict[str, bool] = {}
    for contract in contracts:
        if (
            not isinstance(contract, dict)
            or not isinstance(contract.get("contract_id"), str)
            or not isinstance(contract.get("family"), str)
            or not isinstance(contract.get("template_version"), int)
            or contract.get("status") not in {"FULLY_VERIFIED", "NOT_READY", "QUARANTINED"}
        ):
            raise ProductionConfigError("readiness manifest has invalid contract entry")
        contract_id = contract["contract_id"]
        if contract_id in statuses or any(
            contract.get(column) not in ({"yes", "no", "unknown", "differential"} if column == "independent_oracle" else {"yes", "no", "unknown"})
            for column in columns
        ):
            raise ProductionConfigError("readiness manifest has invalid or duplicate contract status")
        statuses[contract_id] = contract.get("status") == "FULLY_VERIFIED" and all(
            contract[column] == "yes" or (column == "independent_oracle" and contract[column] == "differential")
            for column in columns
        )
    quarantined = _quarantined_contract_ids(manifest_path)
    return lambda contract_id: contract_id not in quarantined and statuses.get(contract_id, False)


def _distinct_contract_preflight(
    config: ProductionConfig,
    registry: Any,
    contract_readiness: ContractReadiness | None,
) -> dict[str, Any]:
    """Validate explicitly selected contracts without owning their evidence."""
    if config.schedule_mode == "legacy":
        return {"ok": True, "mode": "legacy"}

    failures: dict[str, list[str]] = {}
    selected: dict[str, list[str]] = {}
    for family, scheduled_count in config.family_distribution.items():
        contract_ids = config.selected_contract_ids[family]
        selected[family] = sorted(contract_ids)
        family_failures: list[str] = []
        if len(contract_ids) < scheduled_count:
            family_failures.append("insufficient selected contracts")
        if len(set(contract_ids)) != len(contract_ids):
            family_failures.append("duplicate selected contract IDs")
        for contract_id in contract_ids:
            try:
                template = registry.get(contract_id)
            except (RegistryError, ValueError):
                family_failures.append(f"unknown contract ID {contract_id}")
                continue
            if template.family != family:
                family_failures.append(f"contract ID {contract_id} belongs to {template.family}")
            elif contract_readiness is None or not contract_readiness(contract_id):
                family_failures.append(f"contract ID {contract_id} is not fully verified")
        if family_failures:
            failures[family] = family_failures
    return {
        "ok": not failures,
        "mode": config.schedule_mode,
        "selection_rule": config.distinct_contract_selection,
        "selected_contract_ids": selected,
        "failures": failures,
    }


def preflight(
    config: ProductionConfig,
    root: str | Path = ".",
    *,
    contract_readiness: ContractReadiness | None = None,
    readiness_manifest: str | Path | None = None,
) -> dict[str, Any]:
    if contract_readiness is not None and readiness_manifest is not None:
        raise ProductionConfigError("supply either a readiness manifest or a readiness callback, not both")
    if readiness_manifest is not None:
        contract_readiness = contract_readiness_from_manifest(readiness_manifest)
    root = Path(root)
    results: dict[str, Any] = {"production_config_id": config_id(config), "checks": {}}
    from verified_data_factory.task_engine import load_builtin_registry

    registry = load_builtin_registry()
    results["checks"]["template_diversity"] = _template_diversity(config, registry)
    results["checks"]["distinct_contracts"] = _distinct_contract_preflight(
        config, registry, contract_readiness
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
        results["checks"]["model"] = {"ok": bool(found and _matches_ollama_digest(config.model.model_revision, found.get("digest"))), "available": bool(found), "digest": (found or {}).get("digest")}
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
