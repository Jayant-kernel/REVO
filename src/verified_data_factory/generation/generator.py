"""Candidate orchestration (Phase 2).

Pure flow per task: TaskInstance -> prompt -> provider -> raw text ->
parser -> CandidateSolution. Tasks are treated as immutable input and are
never modified. Failures are returned as data (``GenerationResult``), so
one bad call never destroys a batch. Sequential execution only; the
per-(task, provider, index) independence allows future parallelization.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
from typing import Any

from verified_data_factory.task_engine.models import TaskInstance

from .errors import ProviderError
from .models import (
    GENERATION_SCHEMA_VERSION,
    PROMPT_VERSION,
    CandidateSolution,
    GenerationConfig,
    GenerationResult,
)
from .parser import extract_candidate_sql
from .prompt import build_sql_prompt
from .provider import Provider

logger = logging.getLogger(__name__)


def build_candidate_id(
    task_id: str,
    model: str,
    model_revision: str,
    prompt_version: str,
    config: GenerationConfig,
    candidate_index: int,
) -> str:
    """Traceable candidate id: human prefix + hash of generation metadata."""
    payload = {
        "candidate_index": candidate_index,
        "config": config.model_dump(mode="json"),
        "model": model,
        "model_revision": model_revision,
        "prompt_version": prompt_version,
        "task_id": task_id,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12]
    slug = "".join(ch if ch.isalnum() else "-" for ch in model.split("/")[-1].lower())
    return f"{task_id}.{slug}.{candidate_index:02d}.{digest}"


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def generate_candidate(
    task: TaskInstance,
    provider: Provider,
    config: GenerationConfig,
    candidate_index: int = 0,
) -> GenerationResult:
    """Generate one candidate for ``task`` via ``provider``."""
    prompt = build_sql_prompt(task)
    try:
        response = provider.generate(prompt=prompt, generation_config=config)
    except ProviderError as exc:
        result = GenerationResult(
            generation_status="provider_failed",
            parse_status="failed",
            candidate_solution=None,
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
        logger.info(
            "candidate provider failure",
            extra={"task_id": task.task_id, "model": provider.model_id},
        )
        return result

    parsed = extract_candidate_sql(response.raw_text)
    candidate = CandidateSolution(
        candidate_id=build_candidate_id(
            task.task_id,
            provider.model_id,
            response.model_revision,
            PROMPT_VERSION,
            config,
            candidate_index,
        ),
        task_id=task.task_id,
        model=provider.model_id,
        model_revision=response.model_revision,
        prompt_version=PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        provider=provider.provider_name,
        endpoint_id=provider.endpoint_id(),
        candidate_index=candidate_index,
        raw_response=response.raw_text,
        candidate_sql=parsed.sql,
        generation_config=config,
        generation_timestamp=_utc_now_iso(),
        generation_duration_ms=response.generation_time_ms,
        finish_reason=response.finish_reason,
        token_usage=response.token_usage,
        provider_metadata=dict(response.provider_metadata),
        generation_status="success",
        parse_status=parsed.status,
        failure_reason=parsed.failure_reason,
    )
    logger.info(
        "candidate generated",
        extra={
            "task_id": task.task_id,
            "candidate_id": candidate.candidate_id,
            "model": provider.model_id,
            "parse_status": parsed.status,
        },
    )
    return GenerationResult(
        generation_status="success",
        parse_status=parsed.status,
        candidate_solution=candidate,
        failure_reason=parsed.failure_reason,
    )


def generate_candidates(
    task: TaskInstance,
    providers: list[Provider],
    config: GenerationConfig,
    num_candidates: int = 1,
) -> list[GenerationResult]:
    """Generate ``num_candidates`` per provider; failures stay isolated."""
    results: list[GenerationResult] = []
    for provider in providers:
        for i in range(num_candidates):
            results.append(generate_candidate(task, provider, config, i))
    return results


def generate_for_tasks(
    tasks: list[TaskInstance],
    providers: list[Provider],
    config: GenerationConfig,
    num_candidates: int = 1,
) -> list[GenerationResult]:
    """Batch generation: continues after individual failures, order preserved."""
    results: list[GenerationResult] = []
    for task in tasks:
        results.extend(generate_candidates(task, providers, config, num_candidates))
    return results


def candidate_to_dict(candidate: CandidateSolution) -> dict[str, Any]:
    return candidate.model_dump(mode="json", by_alias=True)
