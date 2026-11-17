-- legacy generic mapping recovered from tests/test_business_tasks.py, lines 228-233.
-- It was the generic funnel mapping before SaaS received its contract-specific SQL.
SELECT group_key, SUM(amount) AS total_amount
FROM account_funnel
WHERE status = 'eligible'
  AND EXTRACT(YEAR FROM occurred_at) = 2025
GROUP BY group_key
ORDER BY group_key ASC;
