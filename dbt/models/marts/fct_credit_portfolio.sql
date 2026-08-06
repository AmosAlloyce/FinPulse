{{ config(indexes=[{'columns': ['application_id'], 'unique': true}, {'columns': ['country_code']}]) }}

select
    a.application_id,
    a.customer_id,
    a.applied_at,
    a.country_code,
    a.requested_amount,
    a.currency,
    a.term_days,
    a.product_code,
    a.stated_purpose,
    d.decided_at,
    d.decision,
    d.score,
    d.approved_amount,
    d.interest_rate,
    d.reason_code,
    d.model_version,
    r.loan_id,
    coalesce(r.total_repaid, 0) as total_repaid,
    coalesce(r.repayment_count, 0) as repayment_count,
    coalesce(r.max_days_past_due, 0) as max_days_past_due,
    coalesce(r.ever_par7, false) as ever_par7,
    coalesce(r.ever_par30, false) as ever_par30,
    coalesce(r.is_settled, false) as is_settled,
    r.last_paid_at
from {{ ref('stg_loan_applications') }} a
left join {{ ref('int_latest_loan_decision') }} d using (application_id)
left join {{ ref('int_repayment_performance') }} r using (application_id)

