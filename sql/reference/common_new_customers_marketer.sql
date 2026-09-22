WITH bounds AS (
    SELECT MAX(order_date) AS max_date FROM analytics.orders
), first_orders AS (
    SELECT user_id, MIN(order_date) AS first_order_date
    FROM analytics.orders
    WHERE status = 'completed'
    GROUP BY user_id
)
SELECT
    date_trunc('month', f.first_order_date)::date AS month,
    u.acquisition_channel,
    COUNT(f.user_id) AS new_customers
FROM first_orders AS f
JOIN analytics.users AS u ON u.user_id = f.user_id
CROSS JOIN bounds
WHERE f.first_order_date >= date_trunc('month', bounds.max_date)::date - interval '5 months'
GROUP BY 1, u.acquisition_channel
ORDER BY 1, u.acquisition_channel;
