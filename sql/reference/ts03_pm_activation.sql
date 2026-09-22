WITH bounds AS (
    SELECT MAX(event_date) AS max_date
    FROM analytics.user_events
), cohort AS (
    SELECT u.user_id, u.device, u.signup_date
    FROM analytics.users AS u
    CROSS JOIN bounds
    WHERE u.signup_date >= date_trunc('month', bounds.max_date)::date - interval '2 months'
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
    COUNT(*) AS signup_users,
    COUNT(a.user_id) AS activated_users,
    ROUND(COUNT(a.user_id)::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS activation_rate
FROM cohort AS c
LEFT JOIN activated AS a ON a.user_id = c.user_id
GROUP BY c.device
ORDER BY c.device;
