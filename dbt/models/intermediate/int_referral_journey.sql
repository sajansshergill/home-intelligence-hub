-- int_referral_journey.sql
-- Builds a unified referral journey record by joining:
--   referral → authorization → first visit
-- One row per referral. Used by all three mart models.

with referrals as (
    select * from {{ ref('stg_referrals') }}
),

authorizations as (
    -- Take the latest authorization per referral (re-submissions happen)
    select *
    from {{ ref('stg_authorizations') }}
    qualify row_number() over (
        partition by referral_id
        order by submitted_date desc
    ) = 1
),

first_visits as (
    select *
    from {{ ref('stg_visits') }}
    where is_first_visit = true
    qualify row_number() over (
        partition by referral_id
        order by scheduled_date asc
    ) = 1
),

payors as (
    select
        payor_id,
        payor_name,
        payor_type
    from {{ source('raw', 'payors') }}
),

joined as (
    select
        -- Referral core
        r.referral_id,
        r.patient_id,
        r.payor_id,
        r.referring_provider,
        r.referring_facility,
        r.service_type,
        r.status                 as referral_status,
        r.urgency,
        r.is_accepted,
        r.is_rejected,
        r.referral_date,
        r.accepted_date,
        r.referral_week,
        r.referral_month,
        r.acceptance_lag_hours,

        -- Payor info
        p.payor_name,
        p.payor_type,

        -- Authorization (may be null if no auth submitted)
        a.auth_id,
        a.status                 as auth_status,
        a.is_approved            as auth_is_approved,
        a.is_denied              as auth_is_denied,
        a.submitted_date         as auth_submitted_date,
        a.approved_date          as auth_approved_date,
        a.auth_lag_calendar_days,
        a.units_requested,
        a.units_approved,
        a.units_approval_rate,
        a.denial_reason,

        -- First visit (may be null if no visit yet)
        v.visit_id               as first_visit_id,
        v.clinician_id           as first_clinician_id,
        v.scheduled_date         as first_visit_scheduled_date,
        v.completed_date         as first_visit_completed_date,
        v.is_completed           as first_visit_completed,
        v.duration_minutes       as first_visit_duration_minutes,

        -- Funnel stage flags
        case
            when r.is_accepted                              then 'accepted'
            when r.status = 'rejected'                     then 'rejected'
            when r.status = 'cancelled'                    then 'cancelled'
            else 'pending'
        end as funnel_stage_referral,

        case
            when a.is_approved                             then 'authorized'
            when a.is_denied                               then 'denied'
            when a.auth_id is not null                     then 'in_review'
            else 'no_auth'
        end as funnel_stage_auth,

        case
            when v.is_completed                            then 'visit_completed'
            when v.visit_id is not null                    then 'visit_scheduled'
            else 'no_visit'
        end as funnel_stage_visit,

        -- End-to-end days: referral → first completed visit
        datediff(
            'day',
            r.referral_date,
            v.completed_date
        ) as referral_to_first_visit_days

    from referrals r
    left join payors          p on r.payor_id    = p.payor_id
    left join authorizations  a on r.referral_id = a.referral_id
    left join first_visits    v on r.referral_id = v.referral_id
)

select * from joined