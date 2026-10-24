"""Every profile input is locked; challenge/relations are re-executed, not copied outcomes."""
import shutil
from pathlib import Path

import pytest

from scripts.engineering_qualification_receipts import INPUTS, profile
from scripts.engineering_receipt_artifacts import SUPPORTED, ArtifactWriter
from tests.test_stage2_receipt_producer import assert_receipt

pytest_plugins = ["tests.test_stage2_receipt_producer"]


@pytest.mark.parametrize("contract,version", sorted(SUPPORTED))
def test_complete_profile_categories(producer_root, contract, version):
    root = Path(__file__).resolve().parents[1]
    for relative in INPUTS:
        destination = producer_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, destination)
    writer = ArtifactWriter(producer_root, "bundle-profile-proof", contract, version, INPUTS)
    alternatives, wrong, discriminators = profile(producer_root, contract, version)
    assert len(set(alternatives)) == 3
    assert_receipt(writer, "challenge", writer.challenges(wrong, alternatives))
    assert_receipt(writer, "relations", writer.relations(alternatives[0], discriminators))
    assert_receipt(writer, "named_tests", writer.named_tests([
        f"tests/test_qualification_named.py::test_attributed_contract_execution[{contract}]",
    ]))
