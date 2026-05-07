-- stg_clinicians.sql
-- Cleaned clinician roster with derived capacity fields.

with source as (
    select * from {{ source('raw', 'clinicians') }}
),

staged as (
    select
        clinician_id,
        first_name,
        last_name,
        first_name || ' ' || last_name      as full_name,
        specialty,
        license_number,
        zip_code,
        state,
        active,

        try_cast(hire_date   as date)          as hire_date,
        try_cast(created_at  as timestamp_ntz) as created_at,

        weekly_capacity_visits,

        -- Derived
        datediff('year', try_cast(hire_date as date), current_date()) as tenure_years

    from source
)

select * from staged