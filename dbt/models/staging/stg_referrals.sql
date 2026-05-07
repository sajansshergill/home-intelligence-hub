-- stg_referrals.sql
-- Typed and cleaned referrals from the raw source.
-- Adds derived fields used across multiple marts.

with source as (
    select * from {{ source('raw', 'referrals') }}
),

staged as (
    select
        referral_id,
        patient_id,
        payor_id,
        referring_provider,
        referring_facility,

        -- Cast timestamps
        try_cast(referral_date as timestamp_ntz)  as referral_date,
        try_cast(accepted_date as timestamp_ntz)  as accepted_date,
        try_cast(created_at    as timestamp_ntz)  as created_at,

        -- Normalize status
        lower(trim(status))   as status,
        lower(trim(urgency))  as urgency,
        service_type,
        notes,

        -- Derived flags
        case when lower(trim(status)) = 'accepted' then true else false end  as is_accepted,
        case when lower(trim(status)) = 'rejected' then true else false end  as is_rejected,

        -- Date parts for partitioning and trending
        date_trunc('week',  try_cast(referral_date as timestamp_ntz)) as referral_week,
        date_trunc('month', try_cast(referral_date as timestamp_ntz)) as referral_month,

        -- Acceptance lag in hours (null if not accepted)
        datediff(
            'hour',
            try_cast(referral_date  as timestamp_ntz),
            try_cast(accepted_date  as timestamp_ntz)
        ) as acceptance_lag_hours

    from source
)

select * from staged