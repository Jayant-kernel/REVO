import json

import pytest

from scripts.engineering_metric_preflight import validate_metric
from scripts.engineering_program_audit import population
from verified_data_factory.verification.receipt_validation import digest


def test_claimed_full_count_cannot_hide_partial_population(tmp_path):
    path = tmp_path / "forged.json"
    path.write_text(json.dumps({"population_count": len(population()), "population": [],
                               "metrics": {"challenge_deficient_contracts": 0}}))
    with pytest.raises(ValueError, match="partial, duplicated or stale population"):
        validate_metric(tmp_path, {"path": path.name, "sha256": digest(path)}, "challenge_deficient_contracts")
