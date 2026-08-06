select
    date_trunc('day', decided_at)::date as decision_date,
    country_code,
    model_version,
    count(*) as decisions,
    avg(score) as average_score,
    stddev_pop(score) as score_stddev,
    percentile_cont(0.5) within group (order by score) as median_score,
    100.0 * count(*) filter (where decision = 'approved') / count(*) as approval_rate_pct,
    100.0 * count(*) filter (where ever_par30) / nullif(count(*) filter (where loan_id is not null), 0) as observed_par30_pct
from {{ ref('fct_credit_portfolio') }}
where decided_at is not null
group by 1, 2, 3

