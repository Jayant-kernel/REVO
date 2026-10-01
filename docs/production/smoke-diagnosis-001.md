# Smoke-qualification-001 diagnostic finding

Source: immutable `runs/smoke-qualification-001` task, execution, and
verification JSONL files. This document is a new interpretation, not an edit
to that run.

## Subqueries

One `sql.subqueries.exists.v1` task yielded three executed candidates. All
three matched the Python oracle on the visible fixture and passed three
hidden cases, one property, and two metamorphic relations. Each remained
`INCONCLUSIVE/WEAK_SUITE`: the valid `threshold-to-zero` mutant survived while
`where-clause-drop` was killed, giving mutation score 0.5 against the unchanged
0.90 verifier threshold. The candidates differ little in SQL. The observed
issue is insufficient discrimination of the amount boundary for this task and
its current generated fixtures. It is not evidence that the oracle is wrong.

Next reproduction: add an independently authored customer with only a
completed order in 2025 whose amount is strictly between 0 and 500, and a
customer with an order just above 500. Confirm that the current SQL and oracle
agree while the threshold-to-zero mutant changes the result. Add this through
a new task/fixture version; retain v1 for replay. Do not mark the historical
three candidates PASS.

## Funnel

One `sql.funnel.completion.v3` task yielded three candidates. Two executed but
returned a result mismatch. Their SQL takes `MAX(step_index)` and therefore
counts the farthest event type seen rather than the longest ordered prefix of
steps; this can mark purchase without the required prior chain as completed.
The third candidate has `EXECUTION_ERROR` and references `step` outside the
lateral subquery where it was defined. These are candidate SQL failures on this
task. The current evidence does not establish a family-wide oracle defect.

Next reproduction: run an independently constructed event sequence with a
purchase preceding the view/add-to-cart/checkout chain and another with a
same-timestamp ordered chain. Keep the original task and oracle contract. A
versioned repair is justified only if that reproduction exposes a contract,
fixture, or verifier defect; otherwise improve task diversity and observe
candidate behavior in the next bounded qualification.
