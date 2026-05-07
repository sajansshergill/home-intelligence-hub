-- stg_authorizations.sql
-- Cleans and types payor authorization records.
-- Computes auth lag in business days from submitted → approved.

with source as (
    select * from {{ source('raw', 'payor_authorizations') }}
),

staged as (
    select
        auth_id,
        referral_id,
        payor_id,

        try_cast(submitted_date as timestamp_ntz) as submitted_date,
        try_cast(approved_date  as timestamp_ntz) as approved_date,
        try_cast(denied_date    as timestamp_ntz) as denied_date,
        try_cast(created_at     as timestamp_ntz) as created_at,

        lower(trim(status)) as status,

        -- Units
        units_requested,
        units_approved,
        round(
            try_cast(units_approved as float) / nullif(try_cast(units_requested as float), 0),
            2
        ) as units_approval_rate,

        denial_reason,

        -- Pre-computed lag from generator (calendar days)
        try_cast(auth_lag_days as integer) as auth_lag_calendar_days,

        -- Derived flags
        case when lower(trim(status)) = 'approved'     then true else false end as is_approved,
        case when lower(trim(status)) = 'denied'       then true else false end as is_denied,
        case when lower(trim(status)) = 'pending_info' then true else false end as is_pending_info,

        -- Date parts
        date_trunc('week',  try_cast(submitted_date as timestamp_ntz)) as submitted_week,
        date_trunc('month', try_cast(submitted_date as timestamp_ntz)) as submitted_month

    from source
)

select * from staged