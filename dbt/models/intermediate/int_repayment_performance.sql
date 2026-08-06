select
    application_id,
    max(loan_id::text)::uuid as loan_id,
    sum(amount) as total_repaid,
    count(*) as repayment_count,
    max(days_past_due) as max_days_past_due,
    bool_or(days_past_due > 7) as ever_par7,
    bool_or(days_past_due > 30) as ever_par30,
    bool_or(payment_status = 'settled') as is_settled,
    max(paid_at) as last_paid_at
from {{ ref('stg_repayments') }}
group by application_id

