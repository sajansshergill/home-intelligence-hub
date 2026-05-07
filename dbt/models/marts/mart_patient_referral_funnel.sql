-- mart_patient_referral_funnel.sql
-- Answers: Where are referrals dropping off in the funnel?
--
-- Grain: one row per referral_month + service_type + urgency
-- Powers: funnel chart, conversion trend, provider leakage analysis

with journey as (
    select * from {{ ref('int_referral_journey') }}
),

funnel_base as (
    select
        referral_month,
        service_type,
        urgency,

        -- Volume at each stage
        count(referral_id)                                                           as total_referrals,

        count(case when funnel_stage_referral = 'accepted'    then 1 end)            as accepted_referrals,
        count(case when funnel_stage_referral = 'rejected'    then 1 end)            as rejected_referrals,
        count(case when funnel_stage_referral = 'cancelled'   then 1 end)            as cancelled_referrals,

        count(case when funnel_stage_auth     = 'authorized'  then 1 end)            as authorized_referrals,
        count(case when funnel_stage_auth     = 'denied'      then 1 end)            as denied_referrals,
        count(case when funnel_stage_auth     = 'in_review'   then 1 end)            as in_review_referrals,

        count(case when funnel_stage_visit    = 'visit_completed' then 1 end)        as completed_first_visits,
        count(case when funnel_stage_visit    = 'visit_scheduled' then 1 end)        as scheduled_first_visits,

        -- Lag metrics (only meaningful rows)
        round(avg(case when acceptance_lag_hours is not null then acceptance_lag_hours end), 1)
                                                                                     as avg_acceptance_lag_hours,
        round(avg(case when auth_lag_calendar_days is not null then auth_lag_calendar_days end), 1)
                                                                                     as avg_auth_lag_days,
        round(avg(case when referral_to_first_visit_days is not null
                        and referral_to_first_visit_days > 0
                        then referral_to_first_visit_days end), 1)                   as avg_referral_to_first_visit_days

    from journey
    group by 1, 2, 3
),

with_rates as (
    select
        *,

        -- Conversion rates
        round(accepted_referrals   / nullif(total_referrals,      0)::float * 100, 1) as acceptance_rate_pct,
        round(authorized_referrals / nullif(accepted_referrals,   0)::float * 100, 1) as auth_rate_pct,
        round(completed_first_visits / nullif(authorized_referrals, 0)::float * 100, 1) as visit_completion_rate_pct,

        -- End-to-end funnel conversion: referral → completed first visit
        round(completed_first_visits / nullif(total_referrals, 0)::float * 100, 1)   as end_to_end_conversion_pct,

        -- Drop-off volumes
        (total_referrals - accepted_referrals)                                        as dropped_at_referral,
        (accepted_referrals - authorized_referrals)                                   as dropped_at_auth,
        (authorized_referrals - completed_first_visits)                               as dropped_at_visit

    from funnel_base
)

select
    referral_month,
    service_type,
    urgency,
    total_referrals,
    accepted_referrals,
    rejected_referrals,
    cancelled_referrals,
    authorized_referrals,
    denied_referrals,
    in_review_referrals,
    completed_first_visits,
    scheduled_first_visits,
    dropped_at_referral,
    dropped_at_auth,
    dropped_at_visit,
    acceptance_rate_pct,
    auth_rate_pct,
    visit_completion_rate_pct,
    end_to_end_conversion_pct,
    avg_acceptance_lag_hours,
    avg_auth_lag_days,
    avg_referral_to_first_visit_days,
    current_timestamp() as dbt_updated_at

from with_rates
order by referral_month desc, total_referrals desc