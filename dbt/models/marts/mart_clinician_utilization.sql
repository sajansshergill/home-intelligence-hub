-- mart_clinician_utilization.sql
-- Answers: Are we burning out clinicians or leaving capacity on the table?
--
-- Grain: one row per clinician + scheduled_week
-- Powers: utilization heatmap, over/under capacity alert table

with visits as (
    select * from {{ ref('stg_visits') }}
),

clinicians as (
    select * from {{ ref('stg_clinicians') }}
),

-- All clinician-week combinations (ensures zeros for quiet weeks)
clinician_weeks as (
    select
        c.clinician_id,
        c.full_name,
        c.specialty,
        c.weekly_capacity_visits,
        c.active,
        c.tenure_years,
        v.scheduled_week
    from clinicians c
    cross join (
        select distinct scheduled_week
        from visits
        where scheduled_week is not null
    ) v
    where c.active = true
),

visit_agg as (
    select
        clinician_id,
        scheduled_week,

        count(visit_id)                                              as total_scheduled,
        count(case when is_completed then 1 end)                    as total_completed,
        count(case when is_missed    then 1 end)                    as total_missed,
        count(case when status = 'cancelled' then 1 end)            as total_cancelled,

        round(avg(case when is_completed then duration_minutes end), 0)
                                                                     as avg_visit_duration_min,
        round(sum(case when is_completed then duration_minutes end) / 60.0, 1)
                                                                     as total_completed_hours,

        count(distinct case when is_completed then patient_id end)  as unique_patients_seen,

        -- Punctuality: avg minutes late for completed visits
        round(avg(case when is_completed and visit_start_offset_minutes > 0
                       then visit_start_offset_minutes end), 0)     as avg_late_minutes,

        -- Missed visit rate
        round(count(case when is_missed then 1 end)
              / nullif(count(visit_id), 0)::float * 100, 1)         as missed_rate_pct

    from visits
    group by 1, 2
),

joined as (
    select
        cw.clinician_id,
        cw.full_name                  as clinician_name,
        cw.specialty,
        cw.weekly_capacity_visits,
        cw.active,
        cw.tenure_years,
        cw.scheduled_week,

        coalesce(va.total_scheduled,      0) as total_scheduled,
        coalesce(va.total_completed,      0) as total_completed,
        coalesce(va.total_missed,         0) as total_missed,
        coalesce(va.total_cancelled,      0) as total_cancelled,
        coalesce(va.avg_visit_duration_min, 0) as avg_visit_duration_min,
        coalesce(va.total_completed_hours,  0) as total_completed_hours,
        coalesce(va.unique_patients_seen,   0) as unique_patients_seen,
        va.avg_late_minutes,
        coalesce(va.missed_rate_pct,        0) as missed_rate_pct,

        -- Utilization: completed / weekly capacity
        round(
            coalesce(va.total_completed, 0)
            / nullif(cw.weekly_capacity_visits, 0)::float * 100, 1
        ) as utilization_rate_pct,

        -- Headroom: capacity remaining
        (cw.weekly_capacity_visits - coalesce(va.total_completed, 0)) as capacity_remaining,

        -- Burnout flag: >110% utilization
        case
            when coalesce(va.total_completed, 0) > (cw.weekly_capacity_visits * 1.10)
            then true else false
        end as is_over_capacity,

        -- Underutilized flag: <50% utilization (opportunity)
        case
            when coalesce(va.total_completed, 0) < (cw.weekly_capacity_visits * 0.50)
            then true else false
        end as is_underutilized

    from clinician_weeks cw
    left join visit_agg va
        on cw.clinician_id   = va.clinician_id
        and cw.scheduled_week = va.scheduled_week
)

select
    clinician_id,
    clinician_name,
    specialty,
    weekly_capacity_visits,
    tenure_years,
    scheduled_week,
    total_scheduled,
    total_completed,
    total_missed,
    total_cancelled,
    unique_patients_seen,
    avg_visit_duration_min,
    total_completed_hours,
    avg_late_minutes,
    missed_rate_pct,
    utilization_rate_pct,
    capacity_remaining,
    is_over_capacity,
    is_underutilized,
    current_timestamp() as dbt_updated_at

from joined
order by scheduled_week desc, utilization_rate_pct desc