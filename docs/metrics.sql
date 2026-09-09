-- Adoption and quality metrics. Run against data/sift.db:
--   sqlite3 data/sift.db < docs/metrics.sql

-- 1. ADOPTION — is it still being used?
SELECT date(started_at) AS day,
       COUNT(*) AS cvs_screened,
       COUNT(DISTINCT substr(started_at, 1, 13)) AS sessions
FROM runs
GROUP BY day ORDER BY day;

-- 2. TRUST — what proportion of judgments are accepted unchanged?
SELECT ROUND(100.0 * SUM(human_action = 'approved') / COUNT(*), 1) AS pct_unedited,
       COUNT(*) AS judgments_with_a_decision
FROM assessments WHERE human_action IS NOT NULL;

-- 3. QUALITY DRIFT — where does the human disagree with the system?
--    This is the backlog for the next iteration.
SELECT criterion_id,
       status      AS system_said,
       human_status AS human_said,
       COUNT(*)    AS times
FROM assessments
WHERE human_action = 'overridden'
GROUP BY 1, 2, 3
ORDER BY times DESC;

-- 4. RELIABILITY — how are quotes being verified?
SELECT verification_method, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM assessments
                                 WHERE evidence_quote IS NOT NULL), 1) AS pct
FROM assessments WHERE evidence_quote IS NOT NULL
GROUP BY 1 ORDER BY n DESC;

-- 5. EXCEPTIONS — what keeps needing a human?
SELECT type, severity, COUNT(*) AS n
FROM exceptions GROUP BY 1, 2 ORDER BY n DESC;

-- 6. SPEED AND COST
SELECT date(started_at) AS day,
       COUNT(*) AS runs,
       ROUND(AVG(latency_ms)) AS mean_ms,
       MAX(latency_ms) AS max_ms,
       ROUND(SUM(est_cost_usd), 4) AS est_usd,
       SUM(retries) AS retries
FROM runs WHERE status = 'completed'
GROUP BY day ORDER BY day;

-- 7. FAILURES — what is being rejected before assessment, and why?
SELECT error_code, COUNT(*) AS n
FROM runs WHERE error_code IS NOT NULL
GROUP BY 1 ORDER BY n DESC;
