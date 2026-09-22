WITH bounds AS (
    SELECT MAX(order_date) AS max_date FROM analytics.orders
), first_orders AS (
    SELECT user_id, MIN(order_date) AS first_order_date
    FROM analytics.orders
    WHERE status = 'completed'
    GROUP BY user_id
), monthly AS (
    SELECT date_trunc('month', first_order_date)::date AS month, COUNT(user_id) AS new_customers
    FROM first_orders CROSS JOIN bounds
    WHERE first_order_date >= date_trunc('month', bounds.max_date)::date - interval '5 months'
    GROUP BY 1
)
SELECT m.month, m.new_customers, t.target_value AS target_new_customers
FROM monthly AS m
JOIN analytics.monthly_targets AS t
  ON t.target_month = m.month AND t.metric_name = 'new_customers'
ORDER BY m.month;
