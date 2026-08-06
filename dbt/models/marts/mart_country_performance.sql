select
    country_code,
    count(*) as applications,
    count(distinct customer_id) as applicants,
    count(*) filter (where decision = 'approved') as approvals,
    round(100.0 * count(*) filter (where decision = 'approved')
        / nullif(count(decision), 0), 2) as approval_rate_pct,
    sum(approved_amount) as approved_value_local,
    avg(score) as average_score,
    round(100.0 * count(*) filter (where ever_par30)
        / nullif(count(*) filter (where loan_id is not null), 0), 2) as par30_pct,
    count(*) filter (where is_settled) as settled_loans
from {{ ref('fct_credit_portfolio') }}
group by country_code

