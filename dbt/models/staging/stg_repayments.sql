select
    event_id,
    loan_id,
    application_id,
    customer_id,
    occurred_at as paid_at,
    country_code,
    amount,
    currency,
    days_past_due,
    payment_status
from {{ source('warehouse', 'repayments') }}

