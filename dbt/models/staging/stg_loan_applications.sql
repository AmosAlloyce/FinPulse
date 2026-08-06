select
    application_id,
    event_id,
    customer_id,
    occurred_at as applied_at,
    country_code,
    requested_amount,
    currency,
    term_days,
    product_code,
    stated_purpose
from {{ source('warehouse', 'loan_applications') }}

