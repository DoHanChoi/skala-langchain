WITH bounds AS (
    SELECT MAX(order_date) AS max_date
    FROM analytics.orders
), period AS (
    SELECT
        date_trunc('quarter', max_date)::date AS quarter_start,
        max_date
    FROM bounds
), actual AS (
    SELECT
        date_trunc('month', o.order_date)::date AS month,
        SUM(o.sales_amount) FILTER (WHERE o.status = 'completed') AS actual_revenue
    FROM analytics.orders AS o
    CROSS JOIN period AS p
    WHERE o.order_date BETWEEN p.quarter_start AND p.max_date
    GROUP BY 1
)
SELECT
    a.month,
    a.actual_revenue,
    t.target_value AS target_revenue,
    ROUND(a.actual_revenue / NULLIF(t.target_value, 0) * 100, 2) AS achievement_rate
FROM actual AS a
JOIN analytics.monthly_targets AS t
  ON t.target_month = a.month
 AND t.metric_name = 'revenue'
ORDER BY a.month;
