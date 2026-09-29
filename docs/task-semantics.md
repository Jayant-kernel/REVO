# Task Semantics — Phase 1 Contract Reference

Status: **frozen with Phase 1**. Semantic reference for Phase 4 verification:
each family states exactly what a future independent oracle must establish.
No candidate SQL is generated or judged here.

Conventions: naive timestamps (no timezones); `NULL` join keys never match;
table order carries no semantics; column order within a table does.

## 1. simple_joins (`sql.joins.simple`)

1. Purpose: total revenue per customer, one-to-many join.
2. Input: `customers`, `orders`; only `status = 'completed'` orders in `year`.
3. Output: `(customer_id, total_revenue)` ordered by revenue desc.
4. Nulls: `country` may be NULL (ignored); join keys and `amount` never NULL.
5. Boundaries: calendar year `year-01-01`..`year-12-31` inclusive.
6. Duplicates: each order counted once.
7. Ordering: revenue desc (ties: unspecified order — oracle must accept any).
8. Edge cases: `missing_relationships` (orderless customers exist, excluded via
   INNER JOIN), `null_values` (a NULL is injected into a nullable column).
9. Oracle must establish: INNER JOIN on `customer_id`, correct filter,
   exclusion of unmatched customers.

## 2. multi_joins (`sql.joins.multi`)

1. Purpose: revenue per (customer, category) across 4 tables.
2. Input: `customers → orders → order_items → products`; completed orders, year.
3. Output: `(customer_id, category, line_revenue)` ordered by revenue desc,
   where `line_revenue = SUM(quantity * price)`.
4. Nulls: no nullable columns participate in joins or arithmetic.
5. Boundaries: as above.
6. Duplicates: multiple items per order expected (`multiple_matching_rows`).
7. Ordering: revenue desc.
8. Edge cases: `missing_relationships` (orderless customers; itemless orders),
   enforced: ≥1 customer with ≥2 orders.
9. Oracle must establish: full-chain INNER JOINs, `quantity * price` definition,
   exclusion of chain-broken entities.

## 3. aggregation (`sql.aggregation.grouped`)

1. Purpose: per-status `COUNT(*)`, `SUM(amount)`, `AVG(amount)`.
2. Input: `orders` in `year`; `amount` nullable.
3. Output: `(status, order_count, total_amount, avg_amount)` ordered by status.
4. Nulls: `SUM`/`AVG` skip NULLs; `COUNT(*)` counts rows;
   `COUNT(amount)` counts non-NULL (both reported via `count_semantics`).
5. Boundaries: year window inclusive.
6. Duplicates: n/a beyond repeated statuses.
7. Ordering: status asc.
8. Edge cases: `null_values` (NULL amount injected), `zero_values` (0 injected),
   `single_row_groups` (a singleton status group is enforced).
9. Oracle must establish: NULL handling, absent statuses produce **no row**
   (`empty_group_behavior`), zero vs NULL distinction.

## 4. cte (`sql.cte.monthly`)

1. Purpose: monthly revenue per customer, then each customer's top month —
   a genuine two-stage analytical problem suited to CTE decomposition.
2. Input: completed orders in `year`.
3. Output: `(customer_id, revenue_month YYYY-MM, monthly_revenue)` by customer.
4. Nulls: none participate.
5. Boundaries: year window inclusive; months are calendar months.
6. Duplicates: multiple orders per month aggregate.
7. Ordering: customer_id asc.
8. Edge cases: `missing_relationships` (customers without qualifying orders are
   excluded). Month-revenue ties break by earliest month (`top_tie_break`).
9. Oracle must establish: correct monthly bucketing, top-month selection,
   tie-break, exclusion of unmatched customers. (Whether the candidate *uses*
   a CTE is style, not correctness.)

## 5. subqueries (`sql.subqueries.exists`)

1. Purpose: customers having ≥1 completed order in `year` with
   `amount > min_amount` (strictly greater, `threshold_operator`).
2. Input: correlated EXISTS on `customer_id`.
3. Output: `(customer_id, name)` ordered by customer_id.
4. Nulls: none participate.
5. Boundaries: year window inclusive; threshold strict.
6. Duplicates: multiple qualifying orders still yield one row.
7. Ordering: customer_id asc.
8. Edge cases: `missing_relationships` (orderless customers exist and are
   excluded — the NOT EXISTS side is fixture-verifiable).
9. Oracle must establish: strict threshold, correlation correctness, exclusion
   of non-matching and orderless customers.

## 6. window_functions (`sql.windows.ranked`)

1. Purpose: per-customer ranking + running totals + LAG deltas.
2. Input: completed orders in `year`, partitioned by `customer_id`.
3. Output: `(customer_id, order_id, order_rank, running_total)` ordered by
   customer and order date.
4. Nulls: `amount` never NULL in fixtures; rule is NULLS LAST regardless.
5. Boundaries: year window inclusive.
6. Duplicates/ties: equal amounts share a RANK with gaps (`tie_policy`);
   ties are injected.
7. Ordering: rank by `amount` desc; running total by `(order_date, order_id)`;
   LAG defaults to NULL on each partition's first row.
8. Edge cases: `ties`, `null_values` (nullable customer column).
9. Oracle must establish: partitioning, both orderings, RANK gap behavior,
   running-total accumulation, LAG default.

## 7. temporal (`sql.temporal.monthly`)

1. Purpose: per-month order/event counts inside a fixed window.
2. Input: `orders.order_date`, `events.event_time`; window
   `window_start..window_end` **inclusive both ends** (`boundary_policy`).
3. Output: `(activity_month YYYY-MM, order_count, event_count)` by month.
4. Nulls: none participate.
5. Boundaries: inclusive; months are calendar months (`month_definition`);
   timestamps naive, no timezones.
6. Duplicates: multiple events per day aggregate.
7. Ordering: month asc.
8. Edge cases: `out_of_order_timestamps` (row order ≠ time order, enforced),
   `same_day_events` (shared calendar day, enforced).
9. Oracle must establish: inclusive boundaries, exact month bucketing of both
   DATE and TIMESTAMP columns.

## 8. deduplication (`sql.dedup.latest`)

1. Purpose: latest event per customer.
2. Input: `events`.
3. Output: `(customer_id, event_type, event_time)` ordered by customer.
4. Duplicates: defined by equal
   `(customer_id, event_type, event_time)` (`duplicate_key`); fixtures contain
   real duplicates (new PK, same business key).
5. Winner: max `event_time`; exact timestamp ties → highest `event_id`
   (`tie_break` / `timestamp_tie_policy`); ties are injected.
6. Ordering: customer_id asc.
7. Oracle must establish: duplicate definition, winner rule, tie-break.

## 9. retention (`sql.retention.30_day`)

1. Purpose: 30-day purchase retention flag per customer.
2. Cohort: **all** customers, anchored at `signup_date` (`cohort_definition`).
3. Qualifying event: `event_type = 'purchase'` with
   `signup_date <= event_time <= signup_date + 30 days`, **inclusive both
   ends — an event exactly 30 days after signup counts**
   (`boundary_policy`). Events before signup never count.
4. Repeats: any single qualifying event retains
   (`repeated_event_policy`); duplicates don't change the flag.
5. Output: `(customer_id, retained BOOLEAN)` ordered by customer.
6. Nulls: none participate.
7. Edge cases: `no_events` (an eventless customer is enforced),
   `duplicate_events` (real duplicate injected), `multiple_purchases`
   (a 2+ purchase customer enforced), `same_day_events` (shared day enforced).
8. Oracle must establish: cohort, anchoring, inclusive boundaries incl. the
   day-30 edge, pre-signup exclusion, repeat invariance.

## 10. funnel (`sql.funnel.completion`)

1. Purpose: per-customer funnel progress + session context.
2. Steps: ordered `funnel_steps`; progress = longest prefix achievable in
   timestamp order; non-step events may interleave (`consecutiveness`);
   earliest occurrence of each step extends the chain (`repeat_policy`).
3. Sessions: a new session starts after a gap **strictly greater than**
   `session_gap_minutes`; steps may span sessions (`cross_session_policy`).
4. Output: `(customer_id, max_step_reached, completed)` ordered by customer;
   `completed` is true iff all steps reached.
5. Nulls: none participate. Timestamps naive, no timezones.
6. Edge cases: `missing_relationships` (eventless customer enforced),
   `out_of_order_timestamps` (inversion enforced),
   `duplicate_events` (real duplicate injected).
7. Oracle must establish: ordered-prefix semantics, first-occurrence chaining,
   strict-inequality session gaps, cross-session chaining.
