with ranked as (
    select
        *,
        row_number() over (partition by application_id order by decided_at desc, event_id desc) as row_num
    from {{ ref('stg_loan_decisions') }}
)
select
    event_id,
    application_id,
    customer_id,
    decided_at,
    country_code,
    decision,
    score,
    approved_amount,
    interest_rate,
    reason_code,
    model_version
from ranked
where row_num = 1
