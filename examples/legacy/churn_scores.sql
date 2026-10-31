-- churn_scores: retired when the CRM moved. Kept here as a relic.
WITH active AS (
    SELECT c.customer_id, MAX(o.order_ts) AS last_order
    FROM crm.customers AS c
    JOIN raw.orders AS o ON o.cust_id = c.customer_id
    GROUP BY c.customer_id
)
INSERT INTO analytics.churn_scores
SELECT customer_id, DATEDIFF(CURRENT_DATE, last_order) AS days_quiet FROM active;

CREATE TABLE reports.churn_weekly AS
SELECT DATE_TRUNC('week', CURRENT_DATE) AS week, AVG(days_quiet) AS avg_quiet
FROM analytics.churn_scores;
