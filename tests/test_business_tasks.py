"""Contract counterexamples, distinct from generated/model candidates."""
from datetime import date, datetime

import duckdb
import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.mutations import applicable_operators
from verified_data_factory.verification.oracle_registry import get_oracle

SAAS_V2_CHAINED_JOIN_SQL = """WITH scoped AS (
    SELECT * FROM account_funnel
    WHERE EXTRACT(YEAR FROM occurred_at)=2025
      AND status IN ('signup','trial','activation','payment')
), segments AS (
    SELECT DISTINCT group_key FROM scoped
), signup_candidates AS (
    SELECT s.*, ROW_NUMBER() OVER (
        PARTITION BY entity_id ORDER BY occurred_at, sequence
    ) AS step_rn
    FROM scoped s WHERE status = 'signup'
), signups AS (
    SELECT * FROM signup_candidates WHERE step_rn = 1
), trial_candidates AS (
    SELECT t.*, ROW_NUMBER() OVER (
        PARTITION BY t.entity_id ORDER BY t.occurred_at, t.sequence
    ) AS step_rn
    FROM signups s JOIN scoped t ON t.entity_id = s.entity_id
      AND t.status = 'trial'
      AND (t.occurred_at, t.sequence) > (s.occurred_at, s.sequence)
), trials AS (
    SELECT * FROM trial_candidates WHERE step_rn = 1
), activation_candidates AS (
    SELECT a.*, ROW_NUMBER() OVER (
        PARTITION BY a.entity_id ORDER BY a.occurred_at, a.sequence
    ) AS step_rn
    FROM trials t JOIN scoped a ON a.entity_id = t.entity_id
      AND a.status = 'activation'
      AND (a.occurred_at, a.sequence) > (t.occurred_at, t.sequence)
), activations AS (
    SELECT * FROM activation_candidates WHERE step_rn = 1
), payment_candidates AS (
    SELECT p.*, ROW_NUMBER() OVER (
        PARTITION BY p.entity_id ORDER BY p.occurred_at, p.sequence
    ) AS step_rn
    FROM activations a JOIN scoped p ON p.entity_id = a.entity_id
      AND p.status = 'payment'
      AND (p.occurred_at, p.sequence) > (a.occurred_at, a.sequence)
), payments AS (
    SELECT * FROM payment_candidates WHERE step_rn = 1
)
SELECT s.group_key, COALESCE(SUM(p.amount), 0) AS total_amount
FROM segments s LEFT JOIN payments p ON p.group_key = s.group_key
GROUP BY s.group_key ORDER BY s.group_key ASC"""

SQL = {
    "sql.joins.saas_paid_invoices": """SELECT i.invoice_id, a.account_name, i.amount_cents
        FROM invoices i INNER JOIN accounts a ON i.account_id = a.account_id
        WHERE i.invoice_status = 'paid' AND a.account_status = 'active'
          AND i.issued_on >= DATE '2025-01-01' AND i.issued_on < DATE '2026-01-01'
        ORDER BY i.invoice_id ASC""",
    "sql.aggregation.payment_net_settled": """SELECT merchant_id,
        SUM(amount_cents) AS net_settled_cents FROM payment_entries
        WHERE entry_status = 'posted' AND entry_kind IN ('settlement', 'reversal')
          AND posted_on >= DATE '2025-01-01' AND posted_on < DATE '2026-01-01'
        GROUP BY merchant_id ORDER BY merchant_id ASC""",
    "sql.aggregation.support_sla_breaches": """SELECT team, priority,
        COUNT(*) AS breach_count FROM support_tickets
        WHERE opened_at >= TIMESTAMP '2025-01-01 00:00:00'
          AND opened_at < TIMESTAMP '2026-01-01 00:00:00'
          AND resolved_at IS NOT NULL AND resolved_at > due_at
        GROUP BY team, priority ORDER BY team ASC, priority ASC""",
    "sql.dedup.education_grade_revisions": """SELECT student_id, course_id, grade,
        recorded_at, revision_id FROM grade_revisions WHERE revision_status = 'valid'
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY student_id, course_id ORDER BY recorded_at DESC, revision_id DESC
        ) = 1 ORDER BY student_id ASC, course_id ASC""",
    "sql.joins.logistics_final_leg": """SELECT s.shipment_id, l.depot, c.carrier_name FROM shipments s
        JOIN legs l ON s.final_leg_id=l.leg_id JOIN carriers c ON l.carrier_id=c.carrier_id
        WHERE s.delivered_on >= DATE '2025-01-01' AND s.delivered_on < DATE '2026-01-01'
        ORDER BY s.shipment_id""",
    "sql.cte.inventory_net_flow": """WITH flows AS (
        SELECT warehouse, CAST(units AS HUGEINT) AS units FROM receipts WHERE status='posted' AND EXTRACT(YEAR FROM occurred_on)=2025
        UNION ALL SELECT warehouse, -CAST(units AS HUGEINT) AS units FROM issues WHERE status='posted' AND EXTRACT(YEAR FROM occurred_on)=2025)
        SELECT warehouse, SUM(units) AS net_units FROM flows GROUP BY warehouse ORDER BY warehouse ASC""",
    "sql.subqueries.education_all_required": """SELECT s.student_id FROM students s
        WHERE EXISTS (SELECT 1 FROM required_courses r WHERE r.program_id=s.program_id)
        AND NOT EXISTS (SELECT 1 FROM required_courses r WHERE r.program_id=s.program_id
          AND NOT EXISTS (SELECT 1 FROM attempts a WHERE a.student_id=s.student_id
          AND a.course_id=r.course_id AND a.score >= 50)) ORDER BY s.student_id""",
    "sql.windows.media_previous_play": """SELECT play_id, LAG(play_id) OVER
        (PARTITION BY viewer_id,title_id ORDER BY played_at,play_id) AS previous_play_id
        FROM plays WHERE status='completed' AND EXTRACT(YEAR FROM played_at)=2025 ORDER BY play_id""",
    "sql.temporal.clinic_weekly_visits": """SELECT clinic, CAST(date_trunc('week',started_at) AS DATE) AS week_start,
        COUNT(*) AS visit_count FROM visits WHERE status='completed' AND EXTRACT(YEAR FROM started_at)=2025
        GROUP BY clinic,week_start ORDER BY clinic,week_start""",
    "sql.temporal.media_first_full_week_viewers": """WITH completed AS (
        SELECT viewer_id, CAST(watched_at AS DATE) AS watched_on FROM viewing_events
        WHERE playback_status='completed' AND EXTRACT(YEAR FROM watched_at)=2025), firsts AS (
        SELECT viewer_id, MIN(watched_on) AS first_completed_on FROM completed GROUP BY viewer_id)
        SELECT f.viewer_id, f.first_completed_on FROM firsts f JOIN completed c ON c.viewer_id=f.viewer_id
        AND c.watched_on>=f.first_completed_on AND c.watched_on<f.first_completed_on+INTERVAL 7 DAY
        GROUP BY f.viewer_id,f.first_completed_on HAVING COUNT(DISTINCT c.watched_on)=7 ORDER BY f.viewer_id ASC""",
    "sql.temporal.manufacturing_shift_downtime": """SELECT line_code,shift_name,
        SUM(date_diff('minute',started_at,ended_at)) AS downtime_minutes FROM downtime_events
        WHERE event_status='closed' AND ended_at IS NOT NULL AND EXTRACT(YEAR FROM started_at)=2025
        GROUP BY line_code,shift_name ORDER BY line_code ASC,shift_name ASC""",
    "sql.temporal.logistics_service_level_as_of": """WITH latest AS (
        SELECT *,ROW_NUMBER() OVER (PARTITION BY shipment_id ORDER BY event_at DESC,event_id DESC) AS rn
        FROM tracking_events WHERE event_at<=TIMESTAMP '2025-06-30 23:59:59')
        SELECT s.depot,COUNT(*) AS shipments_in_scope,
        SUM(CASE WHEN l.tracking_state='delivered' AND l.event_at<=s.promised_at THEN 1 ELSE 0 END) AS delivered_on_time
        FROM shipments s LEFT JOIN latest l ON l.shipment_id=s.shipment_id AND l.rn=1
        WHERE EXTRACT(YEAR FROM s.accepted_at)=2025 GROUP BY s.depot ORDER BY s.depot ASC""",
    "sql.temporal.saas_account_snapshot": """WITH latest AS (
        SELECT *,ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY effective_at DESC,revision_id DESC) AS rn
        FROM subscription_revisions WHERE effective_at<=TIMESTAMP '2025-07-01 00:00:00')
        SELECT plan_name,COUNT(*) AS active_accounts,SUM(mrr_cents) AS total_mrr_cents FROM latest
        WHERE rn=1 AND subscription_status='active' GROUP BY plan_name ORDER BY plan_name ASC""",
    "sql.retention.saas_repeat_payment": """WITH firsts AS (SELECT account_id,MIN(paid_on) AS first_on FROM billing
        WHERE status='paid' AND paid_on IS NOT NULL GROUP BY account_id)
        SELECT DISTINCT f.account_id FROM firsts f JOIN billing b ON b.account_id=f.account_id
        WHERE EXTRACT(YEAR FROM f.first_on)=2025 AND b.status='paid'
        AND b.paid_on > f.first_on AND b.paid_on <= f.first_on + INTERVAL 30 DAY ORDER BY f.account_id ASC""",
    "sql.funnel.support_resolution_chain": """SELECT DISTINCT a.ticket_id FROM ticket_events a
        JOIN ticket_events b ON a.ticket_id=b.ticket_id AND (b.event_time,b.event_id)>(a.event_time,a.event_id)
        JOIN ticket_events c ON a.ticket_id=c.ticket_id AND (c.event_time,c.event_id)>(b.event_time,b.event_id)
        WHERE a.state='opened' AND b.state='assigned' AND c.state='resolved'
        AND EXTRACT(YEAR FROM a.event_time)=2025 AND EXTRACT(YEAR FROM b.event_time)=2025
        AND EXTRACT(YEAR FROM c.event_time)=2025 ORDER BY a.ticket_id ASC""",
    "sql.aggregation.warehouse_throughput": """SELECT warehouse, SUM(units) AS total_units
        FROM warehouse_loads WHERE status='posted' AND EXTRACT(YEAR FROM loaded_on)=2025
        GROUP BY warehouse HAVING SUM(units) >= 40 ORDER BY warehouse ASC""",
    "sql.aggregation.top_category_sales": """SELECT category, SUM(amount) AS total_sales
        FROM category_sales WHERE status='completed' AND EXTRACT(YEAR FROM sold_on)=2025
        GROUP BY category ORDER BY total_sales DESC, category ASC LIMIT 2""",
    "sql.aggregation.fulfillment_sla_dashboard": """SELECT warehouse, COUNT(*) AS delivered_fulfillments,
        SUM(CASE WHEN delivered_at <= promised_at THEN 1 ELSE 0 END) AS on_time_fulfillments
        FROM fulfillments WHERE fulfillment_status='delivered' AND delivered_at IS NOT NULL
        AND EXTRACT(YEAR FROM shipped_at)=2025 GROUP BY warehouse ORDER BY warehouse ASC""",
    "sql.aggregation.product_unique_conversion": """SELECT product_id,
        COUNT(DISTINCT CASE WHEN event_name='view' THEN visitor_id END) AS unique_viewers,
        COUNT(DISTINCT CASE WHEN event_name='purchase' THEN visitor_id END) AS unique_buyers
        FROM product_events WHERE EXTRACT(YEAR FROM occurred_at)=2025 AND event_name IN ('view','purchase')
        GROUP BY product_id HAVING COUNT(DISTINCT CASE WHEN event_name='view' THEN visitor_id END) > 0 ORDER BY product_id ASC""",
    "sql.cte.order_line_reconciliation": """WITH line_totals AS (
        SELECT order_id, SUM(CAST(quantity AS HUGEINT) * unit_price_cents) AS line_total_cents FROM order_lines GROUP BY order_id)
        SELECT o.order_id,o.header_total_cents,COALESCE(l.line_total_cents,0) AS line_total_cents FROM orders o
        LEFT JOIN line_totals l ON l.order_id=o.order_id WHERE o.order_status='completed'
        AND EXTRACT(YEAR FROM o.ordered_on)=2025 AND o.header_total_cents<>COALESCE(l.line_total_cents,0) ORDER BY o.order_id ASC""",
    "sql.cte.category_descendant_sales": """WITH RECURSIVE descendants AS (
        SELECT category_id, category_id AS descendant_id FROM categories
        UNION ALL SELECT d.category_id, c.category_id FROM descendants d JOIN categories c ON c.parent_category_id=d.descendant_id), sales AS (
        SELECT category_id,SUM(amount_cents) AS amount_cents FROM category_orders WHERE sale_status='completed'
        AND EXTRACT(YEAR FROM sold_on)=2025 GROUP BY category_id)
        SELECT c.category_id,c.category_name,COALESCE(SUM(s.amount_cents),0) AS descendant_sales_cents FROM categories c
        JOIN descendants d ON d.category_id=c.category_id LEFT JOIN sales s ON s.category_id=d.descendant_id
        GROUP BY c.category_id,c.category_name ORDER BY c.category_id ASC""",
    "sql.cte.session_funnel_completion": """WITH completed AS (
        SELECT DISTINCT v.session_id FROM session_events v JOIN session_events a ON a.session_id=v.session_id
        AND (a.occurred_at,a.event_id)>(v.occurred_at,v.event_id) JOIN session_events c ON c.session_id=v.session_id
        AND (c.occurred_at,c.event_id)>(a.occurred_at,a.event_id) WHERE v.event_name='view' AND a.event_name='add_to_cart' AND c.event_name='checkout')
        SELECT s.channel,COUNT(*) AS started_sessions,COUNT(c.session_id) AS completed_sessions FROM sessions s
        LEFT JOIN completed c ON c.session_id=s.session_id WHERE EXTRACT(YEAR FROM s.started_at)=2025 GROUP BY s.channel ORDER BY s.channel ASC""",
    "sql.cte.customer_first_month_repeat": """WITH firsts AS (
        SELECT customer_id,ordered_at,order_id,ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ordered_at,order_id) AS rn
        FROM customer_orders WHERE order_status='completed'), repeats AS (
        SELECT f.customer_id,f.ordered_at AS first_at FROM firsts f JOIN customer_orders o ON o.customer_id=f.customer_id
        AND o.order_status='completed' AND (o.ordered_at,o.order_id)>(f.ordered_at,f.order_id)
        AND date_trunc('month',o.ordered_at)=date_trunc('month',f.ordered_at) WHERE f.rn=1)
        SELECT customer_id,strftime(first_at,'%Y-%m') AS first_purchase_month FROM repeats WHERE EXTRACT(YEAR FROM first_at)=2025 ORDER BY customer_id ASC""",
    "sql.subqueries.customer_outreach": """SELECT customer_id FROM outreach_activity
        WHERE status='completed' AND EXTRACT(YEAR FROM contacted_on)=2025 AND channel='email'
        UNION SELECT customer_id FROM outreach_activity
        WHERE status='completed' AND EXTRACT(YEAR FROM contacted_on)=2025 AND channel='phone'
         ORDER BY customer_id ASC""",
    "sql.funnel.checkout_paid_session": """WITH qualified AS (
        SELECT DISTINCT s.session_id FROM sessions s
        JOIN session_events v ON v.session_id=s.session_id AND v.event_name='product_view'
        JOIN session_events a ON a.session_id=s.session_id AND a.event_name='add_to_cart'
          AND (a.occurred_at,a.event_id)>(v.occurred_at,v.event_id)
        JOIN session_events c ON c.session_id=s.session_id AND c.event_name='checkout_started'
          AND (c.occurred_at,c.event_id)>(a.occurred_at,a.event_id)
        JOIN payments p ON p.session_id=s.session_id AND p.payment_status='captured'
          AND p.captured_at>=c.occurred_at AND p.captured_at<=s.expires_at
        WHERE EXTRACT(YEAR FROM s.started_at)=2025)
        SELECT s.channel, COUNT(DISTINCT s.session_id) AS started_sessions,
          COUNT(DISTINCT q.session_id) AS paid_checkouts FROM sessions s
        LEFT JOIN qualified q ON q.session_id=s.session_id
         WHERE EXTRACT(YEAR FROM s.started_at)=2025 GROUP BY s.channel ORDER BY s.channel ASC""",
    "sql.funnel.saas_activation_payment": SAAS_V2_CHAINED_JOIN_SQL,
    "sql.funnel.kyc_document_approval": """WITH identities AS (
        SELECT application_id, MIN(checked_at) AS identity_at FROM identity_checks
        WHERE result='passed' GROUP BY application_id), latest_reviews AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY application_id,document_type
          ORDER BY reviewed_at DESC,review_id DESC) AS rn FROM document_reviews), documents AS (
        SELECT a.application_id, MAX(r.reviewed_at) AS documents_at FROM applications a
        JOIN identities i ON i.application_id=a.application_id AND i.identity_at>=a.submitted_at
        JOIN country_document_requirements cr ON cr.country=a.country
        JOIN latest_reviews r ON r.application_id=a.application_id AND r.document_type=cr.document_type
          AND r.rn=1 AND r.result='approved' AND r.reviewed_at>=i.identity_at
        GROUP BY a.application_id HAVING COUNT(*)=(SELECT COUNT(*) FROM country_document_requirements x WHERE x.country=(SELECT country FROM applications z WHERE z.application_id=a.application_id)))
        SELECT a.application_id FROM applications a JOIN documents x ON x.application_id=a.application_id
        JOIN approval_decisions d ON d.application_id=a.application_id AND d.result='approved'
          AND d.decided_at>=x.documents_at AND d.decided_at<=a.submitted_at+INTERVAL 14 DAY
        WHERE EXTRACT(YEAR FROM a.submitted_at)=2025 ORDER BY a.application_id ASC""",
    "sql.funnel.parcel_exception_recovery": """WITH latest_exception AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY parcel_id ORDER BY scanned_at DESC,scan_id DESC) AS rn
        FROM parcel_scans WHERE scan_state='exception'), recovered AS (
        SELECT e.parcel_id,e.scanned_at AS exception_at,r.scanned_at AS recovered_at,r.scan_id AS recovered_id
        FROM latest_exception e JOIN parcel_scans r ON r.parcel_id=e.parcel_id AND r.scan_state='recovered'
          AND (r.scanned_at,r.scan_id)>(e.scanned_at,e.scan_id) WHERE e.rn=1), qualified AS (
        SELECT p.parcel_id,p.depot,MIN(d.scanned_at) AS delivered_at,MIN(r.exception_at) AS exception_at
        FROM parcels p JOIN recovered r ON r.parcel_id=p.parcel_id JOIN parcel_scans d ON d.parcel_id=p.parcel_id
          AND d.scan_state='delivered' AND (d.scanned_at,d.scan_id)>(r.recovered_at,r.recovered_id)
          AND d.scanned_at<=r.exception_at+INTERVAL 72 HOUR
        WHERE EXTRACT(YEAR FROM p.accepted_at)=2025 GROUP BY p.parcel_id,p.depot)
        SELECT depot,COUNT(*) AS recovered_parcels,SUM(date_diff('minute',exception_at,delivered_at)) AS total_exception_to_delivery_minutes
        FROM qualified GROUP BY depot ORDER BY depot ASC""",
    "sql.funnel.curriculum_gate_completion": """WITH passed AS (
        SELECT a.*,ROW_NUMBER() OVER (PARTITION BY a.enrollment_id,a.lesson_id ORDER BY a.completed_at,a.attempt_id) AS rn
        FROM lesson_attempts a JOIN enrollments e ON e.enrollment_id=a.enrollment_id WHERE a.result='passed' AND a.completed_at>=e.enrolled_at), module_completion AS (
        SELECT enrollment_id,module_id,stage_number,completed_at,attempt_id FROM (
          SELECT e.enrollment_id,m.module_id,m.stage_number,p.completed_at,p.attempt_id,
            COUNT(*) OVER (PARTITION BY e.enrollment_id,m.module_id) AS passed_lessons,
            ROW_NUMBER() OVER (PARTITION BY e.enrollment_id,m.module_id ORDER BY p.completed_at DESC,p.attempt_id DESC) AS completion_rank
          FROM enrollments e JOIN program_modules m ON m.program_id=e.program_id
          JOIN module_lessons l ON l.module_id=m.module_id JOIN passed p ON p.enrollment_id=e.enrollment_id AND p.lesson_id=l.lesson_id AND p.rn=1) x
        WHERE completion_rank=1 AND passed_lessons=(SELECT COUNT(*) FROM module_lessons y WHERE y.module_id=x.module_id)), completed AS (
        SELECT e.enrollment_id,e.learner_id,e.cohort FROM enrollments e JOIN module_completion m ON m.enrollment_id=e.enrollment_id
        WHERE EXTRACT(YEAR FROM e.enrolled_at)=2025 GROUP BY e.enrollment_id,e.learner_id,e.cohort,e.program_id
        HAVING COUNT(*)=(SELECT COUNT(*) FROM program_modules x WHERE x.program_id=e.program_id)
          AND NOT EXISTS (SELECT 1 FROM module_completion earlier JOIN module_completion later ON earlier.enrollment_id=later.enrollment_id
            AND earlier.stage_number<later.stage_number AND (earlier.completed_at,earlier.attempt_id)>=(later.completed_at,later.attempt_id) WHERE earlier.enrollment_id=e.enrollment_id))
        SELECT e.cohort,COUNT(DISTINCT c.learner_id) AS learners_completed_program FROM enrollments e
        LEFT JOIN completed c ON c.enrollment_id=e.enrollment_id WHERE EXTRACT(YEAR FROM e.enrolled_at)=2025
        GROUP BY e.cohort ORDER BY e.cohort ASC""",
}
SQL_TEMPLATE_VERSIONS = {"sql.funnel.logistics_parcel_delivery": 1}
EXPANSION_TABLES = {
    "sql.joins.payments_country_transfer": "transfers", "sql.joins.clinic_scheduled_clinician": "appointments",
    "sql.joins.manufacturing_approved_supplier": "part_usage", "sql.joins.education_completed_enrollment": "enrollments",
    "sql.aggregation.manufacturing_line_scrap": "production_runs", "sql.cte.saas_mrr_changes": "plan_changes",
    "sql.cte.logistics_depot_delay": "shipment_stops", "sql.subqueries.payments_no_settlement": "merchant_events",
    "sql.subqueries.support_unresolved_reopen": "agent_events", "sql.windows.payments_risk_rank": "merchant_settlements",
    "sql.windows.logistics_previous_stop": "parcel_stops", "sql.temporal.saas_trial_activation": "account_events",
    "sql.temporal.inventory_daily_stock": "stock_events", "sql.dedup.refund_prefer_approved": "refund_requests",
    "sql.dedup.payments_latest_profile": "profile_revisions", "sql.retention.media_week_two_return": "viewer_plays",
    "sql.retention.clinic_followup_window": "patient_visits",
    "sql.funnel.logistics_parcel_delivery": "parcel_scans",
}
SQL.update({
    template_id: f"""SELECT group_key, SUM(amount) AS total_amount FROM {table}
        WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025
        GROUP BY group_key ORDER BY group_key ASC"""
    for template_id, table in EXPANSION_TABLES.items()
})
SQL["sql.funnel.logistics_parcel_delivery"] = """WITH RECURSIVE scoped AS (
         SELECT *, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY occurred_at, sequence, record_id) AS rn
         FROM parcel_scans
         WHERE EXTRACT(YEAR FROM occurred_at)=2025 AND status IN ('accepted','sorted','dispatched','delivered')
       ), walk AS (
         SELECT entity_id, group_key, rn, amount,
           CASE WHEN status='accepted' THEN 1 ELSE 0 END AS progress,
           CAST(NULL AS INTEGER) AS matched_amount
         FROM scoped WHERE rn=1
         UNION ALL
         SELECT s.entity_id, s.group_key, s.rn, s.amount,
           CASE WHEN w.progress < 4 AND s.status=CASE w.progress WHEN 0 THEN 'accepted' WHEN 1 THEN 'sorted' WHEN 2 THEN 'dispatched' WHEN 3 THEN 'delivered' END THEN w.progress+1 ELSE w.progress END,
           CASE WHEN w.progress=3 AND s.status='delivered' THEN s.amount ELSE w.matched_amount END
         FROM walk w JOIN scoped s ON s.entity_id=w.entity_id AND s.rn=w.rn+1
       ), completed AS (
         SELECT entity_id, MAX(group_key) AS group_key, MAX(progress) AS progress, MAX(matched_amount) AS matched_amount
         FROM walk GROUP BY entity_id
       ), depots AS (SELECT group_key FROM scoped GROUP BY group_key)
       SELECT d.group_key, COALESCE(SUM(CASE WHEN c.progress=4 THEN c.matched_amount ELSE 0 END), 0) AS total_amount
       FROM depots d LEFT JOIN completed c ON c.group_key=d.group_key
       GROUP BY d.group_key ORDER BY d.group_key ASC"""
ADVERSARIAL_EXPECTED = {
    "sql.joins.saas_paid_invoices": [[1, "Active", 0]],
    "sql.aggregation.payment_net_settled": [[1, 0]],
    "sql.aggregation.support_sla_breaches": [["Accounts", "high", 2], ["Payments", "normal", 1]],
    "sql.dedup.education_grade_revisions": [
        [1, 10, "A+", "2025-02-01 10:00:00", 4],
        [1, 20, "B+", "2025-05-01 10:00:00", 6],
        [3, 30, "C", "2025-06-01 10:00:00", 7],
    ],
    "sql.joins.logistics_final_leg": [[71, "West", "Road"]],
    "sql.cte.inventory_net_flow": [["X", 0], ["Y", 2]],
    "sql.subqueries.education_all_required": [[7]],
    "sql.windows.media_previous_play": [[10, None], [15, None], [20, 10]],
    "sql.temporal.clinic_weekly_visits": [["West", "2025-05-26", 1], ["West", "2025-06-02", 1]],
    "sql.temporal.media_first_full_week_viewers": [[9, "2025-12-25"]],
    "sql.temporal.manufacturing_shift_downtime": [["A", "day", 90]],
    "sql.temporal.logistics_service_level_as_of": [["east", 2, 0]],
    "sql.temporal.saas_account_snapshot": [["enterprise", 1, 9000], ["growth", 1, 3000]],
    "sql.retention.saas_repeat_payment": [[9]],
    "sql.funnel.support_resolution_chain": [[9]],
    "sql.aggregation.warehouse_throughput": [["A", 100], ["B", 99]],
    "sql.aggregation.top_category_sales": [["apparel", 100], ["books", 100]],
    "sql.aggregation.fulfillment_sla_dashboard": [["east", 2, 1]],
    "sql.aggregation.product_unique_conversion": [[1, 1, 2]],
    "sql.cte.order_line_reconciliation": [[1, 100, 99]],
    "sql.cte.category_descendant_sales": [[1, "Root", 15], [2, "Child", 10], [3, "Empty", 0]],
    "sql.cte.session_funnel_completion": [["email", 1, 1], ["search", 1, 0]],
    "sql.cte.customer_first_month_repeat": [[2, "2025-02"]],
    "sql.subqueries.customer_outreach": [[1], [2]],
    "sql.funnel.checkout_paid_session": [["cross-session", 1, 0], ["expiry-boundary", 1, 1], ["no-events", 1, 0], ["pre-checkout", 1, 0]],
    "sql.funnel.kyc_document_approval": [[10]],
    "sql.funnel.parcel_exception_recovery": [["north", 1, 30], ["south", 1, 4320]],
    "sql.funnel.curriculum_gate_completion": [["blue", 0], ["red", 1]],
}
ADVERSARIAL_EXPECTED.update({template_id: [["west", 7]] for template_id in EXPANSION_TABLES})
ADVERSARIAL_EXPECTED["sql.funnel.saas_activation_payment"] = [["east", 11], ["north", 0], ["west", 7], ["zero", 0]]
ADVERSARIAL_EXPECTED["sql.funnel.logistics_parcel_delivery"] = [["east", 0], ["north", 7], ["south", 0]]


def execute(task, tables, sql):
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(sql)
        columns = [c[0] for c in cursor.description]
        rows = [[str(v) if isinstance(v, (date, datetime)) else v for v in r] for r in cursor.fetchall()]
        return columns, rows
    finally:
        connection.close()


@pytest.mark.parametrize("template_id", SQL)
@pytest.mark.parametrize("seed", [1, 43, 94001])
def test_business_contract_and_discriminating_mutants(template_id, seed):
    task = generate_task(load_builtin_registry().get(template_id, SQL_TEMPLATE_VERSIONS.get(template_id)), seed)
    oracle = get_oracle(template_id, task.template_version)
    expected = oracle.fn(task.requirements, task.tables)
    assert execute(task, task.tables, SQL[template_id]) == (expected.columns, expected.rows)
    kills = 0
    for operator in applicable_operators(task, SQL[template_id], 10):
        mutant = operator.apply(task, SQL[template_id])
        try:
            _, actual = execute(task, task.tables, mutant)
        except duckdb.Error:
            continue  # Invalid SQL does not count as a kill.
        assert actual != expected.rows, (template_id, operator.name, "surviving semantic mutant")
        kills += 1
    assert kills >= 2


@pytest.mark.parametrize("template_id", SQL)
def test_separately_authored_case_and_empty_results(template_id):
    task = generate_task(load_builtin_registry().get(template_id, SQL_TEMPLATE_VERSIONS.get(template_id)), 94001)
    tables = independent_adversarial_tables(task)
    assert tables is not None
    expected = get_oracle(template_id, task.template_version).fn(task.requirements, tables)
    if (template_id, task.template_version) == ("sql.cte.inventory_net_flow", 2):
        assert tables["receipts"][0] == tables["receipts"][1]
        assert expected.rows == [["bag", 0], ["minimum", 2147483648]]
        assert independent_adversarial_tables(task.model_copy(update={"template_version": 3})) is None
    else:
        assert expected.rows == ADVERSARIAL_EXPECTED[template_id]
    assert execute(task, tables, SQL[template_id]) == (expected.columns, expected.rows)
    empty = {name: [] for name in task.tables}
    assert get_oracle(template_id, task.template_version).fn(task.requirements, empty).rows == []
    assert execute(task, empty, SQL[template_id])[1] == []
    # A changed input order must not change these business outcomes.
    reversed_tables = {name: list(reversed(rows)) for name, rows in tables.items()}
    assert execute(task, reversed_tables, SQL[template_id])[1] == expected.rows


def test_new_oracles_do_not_import_fixtures_or_execute_sql():
    import inspect

    from verified_data_factory.verification import business_oracles
    source = inspect.getsource(business_oracles)
    assert "business_fixtures" not in source and "duckdb" not in source
    assert ".execute(" not in source
