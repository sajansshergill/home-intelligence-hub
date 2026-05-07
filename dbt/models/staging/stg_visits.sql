-- stg_visits.sql
-- Cleans and enriches visit records.
-- Computes punctuality and duration derived fields.

with source as (
    select * from {{ source('raw', 'visits') }}
),

staged as (
    select
        visit_id,
        referral_id,
        patient_id,
        clinician_id,
        service_type,
        visit_number,

        try_cast(scheduled_date  as timestamp_ntz) as scheduled_date,
        try_cast(completed_date  as timestamp_ntz) as completed_date,
        try_cast(created_at      as timestamp_ntz) as created_at,

        lower(trim(status)) as status,
        missed_reason,

        try_cast(duration_minutes as integer) as duration_minutes,

        -- Derived flags
        case when lower(trim(status)) = 'completed' then true else false end as is_completed,
        case when lower(trim(status)) = 'missed'    then true else false end as is_missed,
        case when visit_number = 1                  then true else false end as is_first_visit,

        -- Punctuality: minutes early (negative) or late (positive)
        datediff(
            'minute',
            try_cast(scheduled_date as timestamp_ntz),
            try_cast(completed_date as timestamp_ntz)
        ) as visit_start_offset_minutes,

        -- Date parts
        date_trunc('week',  try_cast(scheduled_date as timestamp_ntz)) as scheduled_week,
        date_trunc('month', try_cast(scheduled_date as timestamp_ntz)) as scheduled_month

    from source
)

select * from staged