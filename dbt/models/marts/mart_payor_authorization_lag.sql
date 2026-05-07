-- mart_payor_authorization_lag.sql
-- Answers: Which payors are delaying authorizations — and by how much?
--
-- Grain: one row per payor + submitted_month
-- Powers: payor lag bar chart, SLA breach table, revenue risk scoring

with auths as (
    select * from {{ ref('stg_authorizations') }}
),

payors as (
    select
        payor_id,
        payor_name,
        payor_type,
        avg_auth_lag_days       as payor_expected_lag_days,   -- from payor master
        requires_prior_auth
    from {{ source('raw', 'payors') }}
),

joined as (
    select
        a.auth_id,
        a.referral_id,
        a.payor_id,
        a.status,
        a.is_approved,
        a.is_denied,
        a.is_pending_info,
        a.submitted_date,
        a.approved_date,
        a.denied_date,
        a.submitted_month,
        a.submitted_week,
        a.auth_lag_calendar_days,
        a.units_requested,
        a.units_approved,
        a.units_approval_rate,
        a.denial_reason,

        p.payor_name,
        p.payor_type,
        p.payor_expected_lag_days,
        p.requires_prior_auth,

        -- SLA breach: actual lag > 1.5x expected
        case
            when a.is_approved
             and a.auth_lag_calendar_days > (p.payor_expected_lag_days * 1.5)
            then true
            else false
        end as is_sla_breach

    from auths a
    left join payors p on a.payor_id = p.payor_id
),

aggregated as (
    select
        payor_id,
        payor_name,
        payor_type,
        payor_expected_lag_days,
        requires_prior_auth,
        submitted_month,

        count(auth_id)                                                           as total_auths,
        count(case when is_approved     then 1 end)                              as approved_auths,
        count(case when is_denied       then 1 end)                              as denied_auths,
        count(case when is_pending_info then 1 end)                              as pending_info_auths,

        -- Lag stats (approved only — denial lag not meaningful for ops)
        round(avg(case when is_approved then auth_lag_calendar_days end), 1)     as avg_lag_days,
        round(min(case when is_approved then auth_lag_calendar_days end), 1)     as min_lag_days,
        round(max(case when is_approved then auth_lag_calendar_days end), 1)     as max_lag_days,

        -- P50 / P90 lag
        round(percentile_cont(0.50) within group (
            order by case when is_approved then auth_lag_calendar_days end
        ), 1)                                                                    as p50_lag_days,
        round(percentile_cont(0.90) within group (
            order by case when is_approved then auth_lag_calendar_days end
        ), 1)                                                                    as p90_lag_days,

        -- SLA performance
        count(case when is_sla_breach then 1 end)                                as sla_breach_count,
        round(
            count(case when is_sla_breach then 1 end)
            / nullif(count(case when is_approved then 1 end), 0)::float * 100, 1
        )                                                                        as sla_breach_rate_pct,

        -- Approval rates
        round(count(case when is_approved then 1 end)
              / nullif(count(auth_id), 0)::float * 100, 1)                       as approval_rate_pct,
        round(count(case when is_denied then 1 end)
              / nullif(count(auth_id), 0)::float * 100, 1)                       as denial_rate_pct,

        -- Units utilization
        round(avg(case when is_approved then units_approval_rate end), 2)        as avg_units_approval_rate,

        -- Lag vs. expectation delta
        round(
            avg(case when is_approved then auth_lag_calendar_days end)
            - max(payor_expected_lag_days), 1
        )                                                                        as lag_vs_expected_delta_days

    from joined
    group by 1, 2, 3, 4, 5, 6
)

select
    payor_id,
    payor_name,
    payor_type,
    payor_expected_lag_days,
    requires_prior_auth,
    submitted_month,
    total_auths,
    approved_auths,
    denied_auths,
    pending_info_auths,
    avg_lag_days,
    min_lag_days,
    max_lag_days,
    p50_lag_days,
    p90_lag_days,
    sla_breach_count,
    sla_breach_rate_pct,
    approval_rate_pct,
    denial_rate_pct,
    avg_units_approval_rate,
    lag_vs_expected_delta_days,
    current_timestamp() as dbt_updated_at

from aggregated
order by submitted_month desc, avg_lag_days desc