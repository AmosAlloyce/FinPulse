with gsm as (
    select
        customer_id,
        count(*) as gsm_observation_count,
        avg(call_duration_seconds) as avg_call_duration_seconds,
        avg(unique_contacts) as avg_unique_contacts,
        sum(airtime_topup_amount) as airtime_topup_value,
        max(network_tenure_days) as network_tenure_days
    from {{ ref('stg_gsm_usage') }}
    group by customer_id
), money as (
    select
        customer_id,
        count(*) as transaction_count,
        sum(amount) as transaction_value_local,
        count(distinct date(occurred_at)) as active_transaction_days,
        count(distinct channel) as channel_diversity
    from {{ ref('stg_mobile_money_transactions') }}
    group by customer_id
), credit as (
    select
        customer_id,
        count(*) as application_count,
        avg(score) as average_score,
        max(max_days_past_due) as max_days_past_due,
        bool_or(ever_par30) as ever_par30
    from {{ ref('fct_credit_portfolio') }}
    group by customer_id
)
select
    c.customer_id,
    c.country_code,
    c.registered_at,
    c.age_band,
    c.income_band,
    c.occupation,
    coalesce(g.gsm_observation_count, 0) as gsm_observation_count,
    coalesce(g.avg_call_duration_seconds, 0) as avg_call_duration_seconds,
    coalesce(g.avg_unique_contacts, 0) as avg_unique_contacts,
    coalesce(g.airtime_topup_value, 0) as airtime_topup_value,
    coalesce(g.network_tenure_days, 0) as network_tenure_days,
    coalesce(m.transaction_count, 0) as transaction_count,
    coalesce(m.transaction_value_local, 0) as transaction_value_local,
    coalesce(m.active_transaction_days, 0) as active_transaction_days,
    coalesce(m.channel_diversity, 0) as channel_diversity,
    coalesce(cr.application_count, 0) as application_count,
    cr.average_score,
    coalesce(cr.max_days_past_due, 0) as max_days_past_due,
    coalesce(cr.ever_par30, false) as ever_par30,
    current_timestamp as feature_computed_at
from {{ ref('stg_customers') }} c
left join gsm g using (customer_id)
left join money m using (customer_id)
left join credit cr using (customer_id)

