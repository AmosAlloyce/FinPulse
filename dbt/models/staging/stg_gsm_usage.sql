select
    event_id,
    customer_id,
    occurred_at,
    country_code,
    call_duration_seconds,
    sms_count,
    data_mb,
    unique_contacts,
    airtime_topup_amount,
    network_tenure_days
from {{ source('warehouse', 'gsm_usage') }}

