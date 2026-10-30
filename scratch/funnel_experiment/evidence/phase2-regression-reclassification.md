# Regression Failure Reclassification

The pre-edit full regression recorded three failures. The two runner-integrity
failures are reclassified from `PRE_EXISTING` to `INTRODUCED`.

Evidence: `src/verified_data_factory/production/runner.py` now calls
`production_api.preflight` with `contract_readiness` and `readiness_manifest`
keyword arguments. The affected uncommitted scheduler/readiness work introduced
that signature change while the test doubles in `tests/test_runner_integrity.py`
still accepted only one positional argument. Updating those doubles allowed both
tests to reach and pass their intended assertions.

The oracle-registry coverage failure remains `INTRODUCED`: active funnel template
metadata disagreed with the registered state-machine strategy and was corrected.

The `1003 passed in 1184.03s` Phase 1 full regression is bound to the immediately
following frozen-run guard identity: HEAD
`22ecfeb4e8a92c7c4909c11197dee1e455c4f500`, tracked diff
`be71bc2f18f10879ea08ed2bf5bc57e09d4685cab31196133ca7a45f4febcbff`,
and untracked manifest
`d7f1626b493f822750c146bcbe0cf5404310daf6ab52a1b2e103d0fd2a27399d`.
