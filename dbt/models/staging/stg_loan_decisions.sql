select
    event_id,
    application_id,
    customer_id,
    occurred_at as decided_at,
    country_code,
    decision,
    score,
    approved_amount,
    interest_rate,
    reason_code,
    model_version
from {{ source('warehouse', 'loan_decisions') }}

