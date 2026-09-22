WITH bounds AS (
    SELECT MAX(order_date) AS max_date FROM analytics.orders
), first_orders AS (
    SELECT user_id, MIN(order_date) AS first_order_date
    FROM analytics.orders
    WHERE status = 'completed'
    GROUP BY user_id
), cohort AS (
    SELECT u.user_id, u.device, u.signup_date, f.first_order_date
    FROM analytics.users AS u
    JOIN first_orders AS f ON f.user_id = u.user_id
    CROSS JOIN bounds
    WHERE f.first_order_date >= date_trunc('month', bounds.max_date)::date - interval '5 months'
      AND u.signup_date <= bounds.max_date - interval '7 days'
), activated AS (
    SELECT DISTINCT c.user_id
    FROM cohort AS c
    JOIN analytics.user_events AS e ON e.user_id = c.user_id
    WHERE e.event_name = 'feature_used'
      AND e.event_date BETWEEN c.signup_date AND c.signup_date + interval '7 days'
)
SELECT
    c.device,
    COUNT(c.user_id) AS new_customers,
    COUNT(a.user_id) AS activated_new_customers,
    ROUND(COUNT(a.user_id)::numeric / NULLIF(COUNT(c.user_id), 0) * 100, 2) AS activation_rate
FROM cohort AS c
LEFT JOIN activated AS a ON a.user_id = c.user_id
GROUP BY c.device
ORDER BY c.device;
