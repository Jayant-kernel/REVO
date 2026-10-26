# Diverse smoke 002: new task contracts

**FACT** — Seven new version-1 IDs extend the existing library from 14 to 21
distinct business-template IDs. Version changes are not counted as new tasks.
The original registry remains readable; no historical task is reinterpreted.

Contracts live in the corresponding YAML in `templates/sql/`. Generator:
`task_engine/business_fixtures.py`; independent Python semantics:
`verification/business_oracles.py`; separately authored runtime cases:
`verification/business_adversarial.py`. The adversarial cases were authored by
the engineering agent, independently of the generator, **not human reviewed**.
Hand-authored SQL in `tests/test_business_tasks.py` is a contract test only;
it is never submitted as model output or included in the new dataset.

## Schema meanings and semantic coverage

| ID suffix / family / declared difficulty | Domain, schema and relationships | Business outcome and output grain | Distinctions from existing task |
| --- | --- | --- | --- |
| `joins.logistics_final_leg` / multi joins / 2 | Logistics. `shipments.shipment_id` identifies a parcel; `delivered_on` is its delivery date; nullable `final_leg_id` references `legs.leg_id`. Each leg has nullable `carrier_id` and a depot name; `carriers` maps a unique ID to a name. Many shipments can reference one leg; many legs can reference one carrier. Unmatched references are intentional test exceptions. | One row per delivered parcel with a valid final leg and carrier: shipment_id, depot, carrier_name. | Final-leg responsibility, not retail order-item revenue. Orphan leg/carrier and NULL delivery are excluded. |
| `cte.inventory_net_flow` / CTE / 3 | Inventory. `receipts` and `issues` have independent movement-ID namespaces. `warehouse` names the stock location; `occurred_on` is the movement date; `units` is a signed integer quantity; `status` determines whether it is posted. Repeated quantities are separate movements. There is no receipt-to-issue one-to-one relationship. | One row per warehouse having at least one qualifying movement, net receipt units minus issue units. | Reconciles two populations, including one-sided warehouses and zero totals, rather than ranking monthly retail revenue. |
| `subqueries.education_all_required` / subqueries / 4 | Education. A unique student belongs to one program. `required_courses` is a potentially duplicated program/course requirement relation. `attempts` has an attempt ID, student/course references and nullable integer score. Several attempts may refer to the same student/course. | One student ID when every distinct required course has at least one score >= 50. Programs without requirements are excluded. | Universal course coverage, not existential high-value purchase selection. Optional courses, repeated successes and NULL scores cannot replace missing requirements. |
| `windows.media_previous_play` / window functions / 3 | Media. Unique `play_id` identifies one playback. `viewer_id` and `title_id` are grouping identities; `played_at` is its timestamp; `status` distinguishes completed and partial plays. Several viewers may play the same title; one viewer may play several titles. | One row per qualifying playback, with the previous play ID in that viewer/title history or NULL for the first. | Composite viewer/title history and equal-timestamp event-ID ordering, not customer order ranking and running totals. |
| `temporal.clinic_weekly_visits` / temporal / 2 | Entirely synthetic healthcare operations. A unique visit ID identifies a visit; `clinic` is an operational location label; nullable `started_at` is the visit start timestamp; `status` marks completion/cancellation. No real patients or personal data. | One row per clinic/Monday-week with completed starts in the year; week_start is an ISO DATE and visit_count counts individual visits. | Calendar weeks can start in the prior year, unlike monthly retail totals. A timestamp and a DATE are deliberately different output representations. |
| `retention.saas_repeat_payment` / retention / 3 | SaaS. Unique invoice ID identifies a billing record; account_id groups invoices; nullable paid_on is a calendar date; status determines payment eligibility. Multiple invoices may be paid on the same day. | Each retained account once: first-ever paid date in 2025 and a later paid date within 30 days. | Payment-anchored cohort, not signup-anchored purchase retention. Same-day invoices are not a return; earlier-year first payments exclude an account. |
| `funnel.support_resolution_chain` / funnel / 4 | Support operations. Unique event_id identifies a state event, ticket_id is the case identity, event_time is its timestamp and state is a lifecycle label. A ticket has many events; the same state may recur. | Each ticket once if an opened -> assigned -> resolved subsequence exists in the year. | Ticket-lifetime support completion, not sessionized retail step counts. Repeated states do not reset progress; different tickets cannot supply parts of a chain. |

## Boundaries, ordering and numerical policy

- All year filters are `[2025-01-01, 2026-01-01)` except education, which
  intentionally uses all attempts and no date column. The retention cohort
  filter applies to the **first-ever** paid date, not to subsequent payments;
  a qualifying return may be in January 2026.
- Inventory uses integer units, retains signed corrections and includes zero
  groups. Each posted movement counts; equal-valued rows are not deduplicated.
- Education uses distinct required courses and any passing attempt, including
  equality at 50. NULL scores do not pass. A later failure does not erase a pass.
- Playback history excludes partial/out-of-year rows **before** determining
  the predecessor. Ties use `(played_at, play_id)` ascending.
- Clinic weeks start Monday; only the visit start must be in the year. NULL
  starts and cancelled visits are excluded. Empty groups have no output row.
- Retention is strictly after the first date through day 30 inclusive; same-day
  repeats and day 31 do not qualify. NULL/unpaid billing records do not qualify.
- Support chains use `(event_time, event_id)` ascending, including equal times;
  arbitrary intervening states do not reset progress. No session-gap constraint
  applies to this ticket-lifetime task.
- Output ordering is ascending shipment_id, warehouse, student_id, play_id,
  `(clinic, week_start)`, account_id, and ticket_id respectively. The verifier's
  existing numeric tolerances and strict NULL comparison are unchanged.

## Fixture and wrong-SQL evidence

**MEASURED** — All seven tasks passed generated-fixture/oracle/SQL agreement
at seeds 1, 43 and 94001; each rejected at least two executable mutants per
seed. Invalid SQL did not count as a mutation kill. Separately authored fixtures
have explicit expected results in `ADVERSARIAL_EXPECTED`; empty results and row
permutation are checked independently. Full pinned-Docker verification passed
for all seven reference **test** queries, with STRONG evidence, mutation 1.0
and an independent-adversarial hidden case. These checks are implementation
evidence, not seven generated Goldens or human labels.

Applicable counterexamples include joining the wrong carrier, including the
prior year, averaging rather than summing warehouse flow, weakening the passing
score or excluding score 50, using LEAD instead of LAG, counting one visit per
week rather than all visits, widening retention to 300 days, and allowing an
opened state to substitute for assignment. Source operator applicability is
tested; arbitrary candidate SQL may use a form to which fewer operators apply.

**LIMITATION** — New fixtures are deliberately small, boundary-heavy workloads.
Seed variation primarily changes input ordering and inventory scale. It is not
realistic distribution coverage or a new semantic question. The declarations of
difficulty are priors; the observed three-attempt smoke protocol supplies only
limited empirical information. The general pipeline currently has row-order
properties and metamorphic permutation for these schemas; legacy customer/event
relations correctly report non-applicability rather than inventing evidence.

## Selected semantic coverage (15 records)

The selected templates represent retail customer revenue, retail line revenue,
retail status aggregation, monthly top retail buyer, latest retail event,
signup purchase retention, high-value-buyer existence, monthly retail activity,
retail order history, SaaS paid invoice selection, valid education grade revision,
logistics final-leg responsibility, media playback history, SaaS repeat-payment
cohort and support ordered-resolution completion. This is an **INFERRED**
semantic coverage analysis grounded in their frozen contracts; fingerprints
alone do not establish equivalence or non-equivalence.

Inventory reconciliation, course completion, clinic weekly visits and payment
net settlements had no selected survivor in this smoke. They do not contribute
to the selected dataset's construct/domain coverage merely because they exist
in the library. The 15 selected rows are not the 80-row premium candidate.
