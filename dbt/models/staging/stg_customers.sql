select
    customer_id,
    country_code,
    occurred_at as registered_at,
    age_band,
    income_band,
    occupation,
    consent_version
from {{ source('warehouse', 'customers') }}

