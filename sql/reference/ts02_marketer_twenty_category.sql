WITH bounds AS (
    SELECT MAX(order_date) AS max_date
    FROM analytics.orders
), periods AS (
    SELECT
        date_trunc('month', max_date)::date - interval '2 months' AS current_start,
        max_date,
        date_trunc('month', max_date)::date - interval '5 months' AS previous_start,
        date_trunc('month', max_date)::date - interval '3 months' AS previous_end
    FROM bounds
)
SELECT
    p.category,
    CASE
        WHEN o.order_date >= periods.current_start THEN 'current'
        ELSE 'previous'
    END AS period,
    SUM(o.sales_amount) AS revenue
FROM analytics.orders AS o
JOIN analytics.users AS u ON u.user_id = o.user_id
JOIN analytics.products AS p ON p.product_id = o.product_id
CROSS JOIN periods
WHERE o.status = 'completed'
  AND u.age >= 20 AND u.age < 30
  AND o.order_date >= periods.previous_start
  AND o.order_date <= periods.max_date
  AND (
      o.order_date < periods.previous_end + interval '1 day'
      OR o.order_date >= periods.current_start
  )
GROUP BY p.category, period
ORDER BY p.category, period;
