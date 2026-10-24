# Candidate task coverage matrix — design, not implemented templates

The library now has 40 distinct template IDs: four independent IDs in every
family. This satisfies the premium template-diversity floor only; implemented
templates must not be counted as selected dataset coverage.

Each row is a different business question. Schema IDs name independently
designed table relationships, not renamed copies of one retail schema. These
are design inputs for new versioned templates and independent oracles. None is
an accepted Golden merely by appearing here. Before generation, add for each
row a formal output contract, normal fixture, boundary fixture, independently
authored adversarial fixture, and a wrong SQL counterexample.

Implementation progress (2026-10-01): the matrix's forty design cells now have
versioned templates, deterministic fixtures, independent Python oracle wiring,
and hand-authored adversarial runtime fixtures. Earlier implementation examples:
`sql.joins.saas_paid_invoices` (SA simple joins) and
`sql.aggregation.payment_net_settled` (PA aggregation), plus
`sql.aggregation.support_sla_breaches` (SU aggregation) and
`sql.dedup.education_grade_revisions` (ED deduplication). The SaaS cell below
originally asked for active subscription accounts; the implemented contract
specifies *currently active* accounts and *paid invoices issued in 2025*.
The payments cell specifies signed posted settlement/reversal ledger entries
in 2025. Both new financial templates store integer minor units. These are
qualification inputs, not accepted Goldens. All four have focused
real-sandbox end-to-end verification; this does not establish an 80-row pool.

Schema IDs: EC e-commerce orders/products; SA SaaS accounts/plans/invoices;
PA payments merchants/transactions/disputes; LO logistics shipments/stops;
HC synthetic clinic patients/appointments/clinicians; ME media titles/plays;
SU support tickets/agents/events; MA manufacturing work orders/parts;
IN inventory warehouses/stock movements; ED education students/courses/enrollments.
All HC data must be entirely synthetic.

| Family | Schema | Business question | Discriminating edge |
| --- | --- | --- | --- |
| Simple joins | EC | Which completed orders have a valid buyer, with buyer region? | orphan buyer |
| Simple joins | SA | Which paid 2025 invoices belong to currently active subscription accounts? (implemented template; sandbox checked) | suspended account, year boundary |
| Simple joins | PA | Which settled transfers belong to merchants in a selected country? | unmatched merchant |
| Simple joins | HC | Which scheduled appointments have an assigned clinician? | missing clinician |
| Multi joins | LO | Show delivered shipments with the depot and carrier that handled the final leg. | missing final leg |
| Multi joins | MA | Which work orders consumed parts from an approved supplier? | duplicate part usage |
| Multi joins | ED | Show completed enrollments with course department and instructor. | changed instructor |
| Multi joins | IN | Which replenishments linked a stock movement to a purchase order and warehouse? | missing purchase order |
| Aggregation | PA | What was 2025 net posted settlement value by merchant after reversals? (implemented template; sandbox checked) | negative reversal, failed entry |
| Aggregation | SU | How many tickets opened in 2025 were resolved after their SLA deadline, by priority and team? (implemented template; sandbox checked) | NULL resolution, deadline equality, opening-year boundary |
| Aggregation | MA | What was produced quantity and scrap rate by production line? | zero production |
| Aggregation | ME | Which titles had at least five distinct paying viewers? | duplicate plays/HAVING |
| CTE | SA | Show monthly recurring revenue after plan upgrades and downgrades. | midmonth change |
| CTE | LO | Which depots caused the largest delay after separating transit and handling time? | zero handling |
| CTE | HC | Which clinic had the most completed follow-ups within 30 days? | boundary day |
| CTE | IN | Compare weekly receipts and issues to find net stock change per warehouse. | negative movement |
| Subqueries | EC | Which buyers purchased a product from each required category? | duplicate category |
| Subqueries | PA | Which merchants had no successful settlement after a chargeback? | missing settlement |
| Subqueries | ED | Which students passed every required course in a program? | incomplete program |
| Subqueries | SU | Which agents handled a reopened ticket without any later resolution? | late resolution |
| Window functions | ME | What was each title's previous playback day for each viewer? | timestamp ties |
| Window functions | PA | Rank merchants by monthly settled value within risk tier. | equal values |
| Window functions | LO | Show each shipment's previous recorded stop and elapsed time. | out-of-order ingestion |
| Window functions | MA | Find the first failed inspection after a passed inspection per work order. | multiple same-time inspections |
| Temporal | HC | How many completed visits occurred in each calendar week per clinic? | week boundary |
| Temporal | SA | Show accounts whose trial ended within 48 hours after first activation. | exactly 48 hours |
| Temporal | IN | What was end-of-day stock at each warehouse after all dated movements? | day-end boundary |
| Temporal | ME | Which titles gained viewers in the first seven full days after release? | release-day partial interval |
| Deduplication | SU | Keep the latest state update per ticket using event ID to break ties. | same timestamp |
| Deduplication | EC | Keep one refund request per order and reason, preferring approved records. | approved tie |
| Deduplication | ED | Keep the latest valid grade correction per student/course, breaking timestamp ties by revision ID. (implemented template; sandbox checked) | canceled latest correction, equal timestamps, no valid revision |
| Deduplication | PA | Keep the most recent valid merchant profile per merchant. | invalid latest row |
| Retention | SA | Which accounts paid again within 30 days after first paid invoice? | day 30/31 |
| Retention | ME | Which viewers returned in week two after their first completed play? | partial plays |
| Retention | HC | Which patients completed a follow-up after an initial visit within a defined window? | same-day visit |
| Retention | EC | Which buyers placed a second completed order in the next calendar month? | canceled order |
| Funnel | SU | How many tickets moved from opened to assigned to resolved without skipping a required state? | repeated assignment |
| Funnel | SA | Which accounts completed signup, trial, activation, and first payment in order? | cross-session steps |
| Funnel | LO | Which parcels reached accepted, sorted, dispatched, and delivered in order? | late duplicate scan |
| Funnel | ME | Which viewers reached impression, play, completion, and subscription in order? | same-time event IDs |

The 80-row release target needs eight accepted records per family. This
40-question matrix is an initial design floor, not evidence that 80 distinct
release semantics exist. Expand each family's matrix after the first reviewed
qualification results identify coverage gaps. Do not count multiple seeds or
SQL candidate siblings as new questions.
