"""Business-evidence export with redaction and secret scrubbing (§51, §68).

Writes the ``business-validation/`` layout. Private benchmark answers,
restricted records, credentials, and customer free text never land in
exports unless explicitly opted in — and secrets are scrubbed via the
Phase 6 scrubber (reused, not duplicated).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verified_data_factory.provenance import scrub_secrets

from .errors import BusinessIOError
from .models import BusinessEvidence, CustomerValidation, ExperimentResult

LAYOUT_DIRS: tuple[str, ...] = (
    "experiments",
    "benchmarks",
    "economics",
    "customer-validation",
    "claims",
)

SECRET_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "credentials",
)


def contains_secret_markers(payload: Any) -> bool:
    """True when dumped text mentions credential-like keys (§51)."""
    return any(marker in json.dumps(payload, default=str).lower() for marker in SECRET_MARKERS)


def scrub_payload(payload: Any) -> tuple[Any, int]:
    """Scrub secrets via the Phase 6 scrubber; returns (cleaned, count)."""
    return scrub_secrets(payload)


def _write_json(path: Path, payload: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise BusinessIOError(f"cannot write {path}: {exc}") from exc


def export_business_evidence(
    *,
    out_dir: str | Path,
    report_json: str,
    report_markdown: str,
    experiments: list[dict[str, Any]] | None = None,
    benchmarks: list[dict[str, Any]] | None = None,
    economics: dict[str, Any] | None = None,
    validations: list[CustomerValidation] | None = None,
    claims: list[dict[str, Any]] | None = None,
    evidence: list[BusinessEvidence] | None = None,
    experiment_results: list[ExperimentResult] | None = None,
    include_feedback_text: bool = False,
) -> list[str]:
    """Write the full business-validation/ tree with redaction (§68)."""
    from .customer import redact_validation

    root = Path(out_dir)
    written: list[str] = []
    _write_json(root / "report.json", json.loads(report_json))
    written.append("report.json")
    (root / "report.md").write_text(report_markdown, encoding="utf-8")
    written.append("report.md")
    for directory in LAYOUT_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)

    for index, payload in enumerate(experiments or []):
        cleaned, _ = scrub_payload(payload)
        _reject_private_answers(cleaned, f"experiments/{index}")
        _write_json(root / "experiments" / f"experiment-{index:03d}.json", cleaned)
        written.append(f"experiments/experiment-{index:03d}.json")
    for index, payload in enumerate(benchmarks or []):
        _reject_private_answers(payload, f"benchmarks/{index}")
        cleaned, _ = scrub_payload(payload)
        _write_json(root / "benchmarks" / f"benchmark-{index:03d}.json", cleaned)
        written.append(f"benchmarks/benchmark-{index:03d}.json")
    if economics is not None:
        cleaned, _ = scrub_payload(economics)
        _write_json(root / "economics" / "economics.json", cleaned)
        written.append("economics/economics.json")
    redacted_validations = [
        redact_validation(v, include_feedback_text=include_feedback_text)
        for v in (validations or [])
    ]
    for index, payload in enumerate(redacted_validations):
        cleaned, _ = scrub_payload(payload)
        _write_json(root / "customer-validation" / f"validation-{index:03d}.json", cleaned)
        written.append(f"customer-validation/validation-{index:03d}.json")
    for index, payload in enumerate(claims or []):
        cleaned, _ = scrub_payload(payload)
        _write_json(root / "claims" / f"claim-{index:03d}.json", cleaned)
        written.append(f"claims/claim-{index:03d}.json")
    if evidence is not None:
        cleaned, _ = scrub_payload([e.model_dump(mode="json") for e in evidence])
        _write_json(root / "evidence.json", cleaned)
        written.append("evidence.json")
    if experiment_results is not None:
        cleaned, _ = scrub_payload([r.model_dump(mode="json") for r in experiment_results])
        _write_json(root / "experiment-results.json", cleaned)
        written.append("experiment-results.json")
    return written


def _reject_private_answers(payload: Any, where: str) -> None:
    from .errors import BusinessConfigError

    if "expected_sql" in json.dumps(payload, default=str):
        raise BusinessConfigError(f"{where} contains private benchmark answers; redaction required")
