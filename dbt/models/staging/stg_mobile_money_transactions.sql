select
    event_id,
    customer_id,
    occurred_at,
    country_code,
    transaction_type,
    amount,
    currency,
    channel
from {{ source('warehouse', 'mobile_money_transactions') }}

