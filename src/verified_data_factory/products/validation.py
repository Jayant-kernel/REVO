"""Release validation (Phase 7, §27).

``validate_release`` re-checks everything a consumer depends on:
manifest integrity, checksums, schema conformance, split isolation,
provenance references, and visibility policy. Errors fail the release;
warnings (documentation-worthy observations) never do.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import read_checksums, read_manifest
from .models import ReleaseValidationReport, ValidationCheck
from .schemas import canonical_schema, validate_product_record
from .serializers import hash_file, read_jsonl, read_parquet


def _err(check: str, detail: str) -> ValidationCheck:
    return ValidationCheck(check=check, passed=False, detail=detail)


def _warn(check: str, detail: str) -> ValidationCheck:
    return ValidationCheck(check=check, passed=False, detail=detail)


def validate_release(
    release_dir: str | Path,
    *,
    quarantined_ids: set[str] | None = None,
    qualities_by_id: dict[str, dict[str, Any]] | None = None,
    justifications: dict[str, str] | None = None,
    supply_chain: dict[str, Any] | None = None,
    review_package: str | Path | None = None,
    mutation_min_score: float = 0.9,
) -> ReleaseValidationReport:
    """Validate a built release directory; never raises on bad content.

    Audit inputs activate remediation gates: ``quarantined_ids``
    rejects quarantined rows, ``qualities_by_id`` (+ ``justifications``)
    re-checks mutation evidence per shipped row, and ``supply_chain``
    (a supply_chain_report_payload dict) enforces commercial clearance.
    PUBLIC releases require all gate inputs. Internal releases retain warnings
    when optional evidence is absent.
    """
    root = Path(release_dir)
    errors: list[ValidationCheck] = []
    warnings: list[ValidationCheck] = []
    schema = canonical_schema()

    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        errors.append(_err("manifest.present", "manifest.json missing"))
        return ReleaseValidationReport(
            status="INVALID",
            errors=errors,
            warnings=warnings,
            manifest_status="missing",
            schema_version=schema.schema_version,
        )
    try:
        manifest = read_manifest(manifest_path)
        manifest_status = "ok"
    except Exception as exc:  # noqa: BLE001 — validation outcomes are data, never raised
        errors.append(_err("manifest.parse", str(exc)))
        return ReleaseValidationReport(
            status="INVALID",
            errors=errors,
            warnings=warnings,
            manifest_status="unparseable",
            schema_version=schema.schema_version,
        )

    # --- files & checksums -------------------------------------------------
    checksum_status = "ok"
    seen_hashes: dict[str, str] = {}
    for entry in manifest.files:
        candidate = root / entry.relative_path
        if not candidate.exists():
            errors.append(_err("files.present", f"missing file: {entry.relative_path}"))
            checksum_status = "missing-files"
            continue
        size, digest = hash_file(candidate)
        seen_hashes[entry.relative_path] = digest
        if size != entry.byte_size:
            errors.append(
                _err("files.size", f"{entry.relative_path}: {size} != manifest {entry.byte_size}")
            )
            checksum_status = "mismatch"
        if digest != entry.content_hash:
            errors.append(_err("files.checksum", f"{entry.relative_path}: sha256 mismatch"))
            checksum_status = "mismatch"

    sums_path = root / "SHA256SUMS"
    if sums_path.exists():
        try:
            sums = read_checksums(sums_path)
            for rel, digest in seen_hashes.items():
                if rel in sums and sums[rel] != digest:
                    errors.append(_err("checksums.consistent", f"SHA256SUMS mismatch: {rel}"))
                    checksum_status = "mismatch"
        except Exception as exc:  # noqa: BLE001 — validation outcomes are data, never raised
            errors.append(_err("checksums.parse", str(exc)))
            checksum_status = "unparseable"
    else:
        warnings.append(_warn("checksums.present", "SHA256SUMS missing"))

    # --- records & schema --------------------------------------------------
    schema_status = "ok"
    records: list[dict[str, Any]] = []
    split_of: dict[str, str] = {}
    duplicate_ids: set[str] = set()
    require_sql = manifest.product_type in ("TRAIN", "PRIVATE_EVAL", "BENCHMARK", "SAMPLE")
    for shard in manifest.shards:
        shard_path = root / shard.relative_path
        if not shard_path.exists():
            continue
        try:
            if shard_path.suffix == ".parquet":
                shard_records = read_parquet(shard_path)
            else:
                shard_records = read_jsonl(shard_path)
        except Exception as exc:  # noqa: BLE001 — validation outcomes are data, never raised
            errors.append(_err("records.parse", f"{shard.relative_path}: {exc}"))
            schema_status = "unparseable"
            continue
        if len(shard_records) != shard.record_count:
            errors.append(
                _err(
                    "records.count",
                    f"{shard.relative_path}: {len(shard_records)} != manifest {shard.record_count}",
                )
            )
            schema_status = "count-mismatch"
        for record in shard_records:
            record_errors = validate_product_record(record, schema, require_sql=require_sql)
            for detail in record_errors:
                errors.append(_err("records.schema", f"{shard.relative_path}: {detail}"))
                schema_status = "schema-violations"
            gid = str(record.get("golden_record_id", ""))
            if gid:
                if gid in split_of:
                    duplicate_ids.add(gid)
                split_of[gid] = shard.relative_path
            records.append(record)

    # --- splits -------------------------------------------------------------
    split_status = "ok"
    if duplicate_ids:
        errors.append(
            _err("splits.disjoint", f"{len(duplicate_ids)} record(s) appear in multiple shards")
        )
        split_status = "overlap"
    if manifest.record_count != len(records):
        errors.append(
            _err(
                "splits.count",
                f"manifest record_count {manifest.record_count} != records read {len(records)}",
            )
        )
        split_status = "count-mismatch"
    for name, count in manifest.split_counts.items():
        if count < 0:
            errors.append(_err("splits.counts", f"negative count for split {name}"))
            split_status = "invalid-counts"

    # --- provenance ----------------------------------------------------------
    provenance_status = "ok"
    for record in records:
        if record.get("dataset_snapshot_id") != manifest.dataset_snapshot_id:
            errors.append(_err("provenance.snapshot", "record dataset_snapshot_id mismatch"))
            provenance_status = "mismatch"
            break
    else:
        if not records:
            warnings.append(_warn("provenance.records", "release contains no records"))

    # --- visibility -----------------------------------------------------------
    public_release = manifest.visibility == "PUBLIC"
    reviewed_package_id: str | None = None
    if public_release:
        if review_package is None:
            errors.append(
                _err("release.independent_review", "PUBLIC release requires a frozen two-reviewer package")
            )
        else:
            try:
                from verified_data_factory.quality.review_package import review_status

                review = review_status(review_package)
                reviewed_package_id = review.get("package_id")
                if manifest.acceptance_profile == "PREMIUM_93":
                    if review.get("candidate_class") != "PREMIUM_PRE_REVIEW":
                        errors.append(
                            _err(
                                "release.premium_review",
                                "PREMIUM_93 requires a premium-qualified frozen review package",
                            )
                        )
                    if review.get("item_count") != 80 or any(
                        verdict != "PASS" for verdict in review["status_by_record"].values()
                    ):
                        errors.append(
                            _err(
                                "release.premium_review",
                                "all 80 premium review rows require final PASS",
                            )
                        )
                    if not reviewed_package_id:
                        errors.append(
                            _err("release.premium_review", "review package identity is missing")
                        )
                for record in records:
                    record_id = str(record.get("golden_record_id", ""))
                    if review["status_by_record"].get(record_id) != "PASS":
                        errors.append(
                            _err("release.independent_review", f"{record_id}: final two-reviewer status is not PASS")
                        )
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                errors.append(_err("release.independent_review", f"invalid review package: {exc}"))
    if public_release:
        for record in records:
            if record.get("sql") and manifest.product_type == "PUBLIC_EVAL":
                # PUBLIC_EVAL must withhold targets; a present target is a leak.
                errors.append(_err("visibility.targets", "PUBLIC_EVAL release exposes target SQL"))
                break
            forbidden = {
                "raw_response",
                "execution",
                "verification",
                "quality",
                "fixture",
                "requirements",
                "stderr",
                "stdout",
            }
            leaked = sorted(forbidden & set(record))
            if leaked:
                errors.append(
                    _err("visibility.internal_evidence", f"public row exposes {leaked}")
                )
                break

    # --- dataset card / preview presence --------------------------------------
    if not (root / "dataset_card.md").exists():
        warnings.append(_warn("docs.card", "dataset_card.md missing"))
    if not (root / "preview.json").exists():
        warnings.append(_warn("docs.preview", "preview.json missing"))

    # --- remediation gates ------------------------------------------------------
    quarantine_evidence_supplied = quarantined_ids is not None
    quarantined_ids = quarantined_ids or set()
    if public_release and not quarantine_evidence_supplied:
        errors.append(
            _err("release.quarantine_evidence", "PUBLIC release requires a quarantine set")
        )
    justifications = justifications or {}
    for record in records:
        gid = str(record.get("golden_record_id", ""))
        if gid and gid in quarantined_ids:
            errors.append(_err("release.quarantine", f"quarantined record shipped: {gid}"))
    if qualities_by_id is not None:
        contamination_missing = 0
        for record in records:
            gid = str(record.get("golden_record_id", ""))
            quality = qualities_by_id.get(gid)
            if quality is None:
                errors.append(
                    _err("release.quality", f"no quality evidence for shipped row: {gid}")
                )
                continue
            if "contamination_flags" not in quality:
                contamination_missing += 1
            verification = quality.get("verification", {})
            if not isinstance(verification, dict):
                continue
            applicable = int(verification.get("mutation_applicable", 0) or 0)
            status = verification.get("mutation_status", "NOT_APPLICABLE")
            score = verification.get("mutation_score")
            if public_release and verification.get("verification_strength") != "STRONG":
                errors.append(
                    _err("release.verification_strength", f"{gid}: verification is not STRONG")
                )
            if public_release and quality.get("auditor_result") != "PASS":
                errors.append(
                    _err("release.human_audit", f"{gid}: human audit result is not PASS")
                )
            if (
                public_release
                and manifest.acceptance_profile == "PREMIUM_93"
                and quality.get("review_package_id") != reviewed_package_id
            ):
                errors.append(
                    _err("release.premium_review", f"{gid}: derived review evidence is not bound to the frozen package")
                )
            if status == "SCORED" and score is not None and score < mutation_min_score:
                errors.append(
                    _err(
                        "release.mutation_threshold",
                        f"{gid}: scored {score} below {mutation_min_score}",
                    )
                )
            if (status == "NOT_APPLICABLE" or applicable == 0) and not str(
                justifications.get(gid, "")
            ).strip():
                errors.append(
                    _err(
                        "release.mutation_evidence",
                        f"{gid}: zero-applicable mutation without justification",
                    )
                )
        if contamination_missing:
            errors.append(
                _err(
                    "release.contamination",
                    f"{contamination_missing} shipped row(s) lack contamination evidence",
                )
            )
    else:
        check = _err if public_release else _warn
        target = errors if public_release else warnings
        target.append(
            check(
                "release.quality.unchecked",
                "no quality evidence supplied; mutation/contamination gates cannot run",
            )
        )
    if public_release and supply_chain is None:
        errors.append(
            _err(
                "release.commercial_clearance",
                "PUBLIC release requires an explicit supply-chain clearance report",
            )
        )
    elif supply_chain is not None and not supply_chain.get("commercially_cleared", False):
        reasons = supply_chain.get("clearance_reasons", ["unresolved supply chain"])
        errors.append(
            _err(
                "release.commercial_clearance",
                f"commercial clearance refused: {reasons[0] if reasons else 'unknown'}",
            )
        )

    status = "VALID" if not errors else "INVALID"
    report = ReleaseValidationReport(
        status=status,
        errors=errors,
        warnings=warnings,
        record_count=len(records),
        file_count=len(manifest.files),
        checksum_status=checksum_status,
        schema_status=schema_status,
        split_status=split_status,
        provenance_status=provenance_status,
        manifest_status=manifest_status,
        schema_version=schema.schema_version,
    )
    report_path = root / "validation.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
