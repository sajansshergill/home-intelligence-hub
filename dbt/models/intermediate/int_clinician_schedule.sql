-- int_clinician_schedule.sql
-- Weekly clinician schedule rollup used for capacity analysis and QA.

with visits as (
    select * from {{ ref('stg_visits') }}
),

clinicians as (
    select * from {{ ref('stg_clinicians') }}
),

visit_weeks as (
    select distinct scheduled_week
    from visits
    where scheduled_week is not null
),

clinician_weeks as (
    select
        c.clinician_id,
        c.full_name as clinician_name,
        c.specialty,
        c.weekly_capacity_visits,
        c.active,
        w.scheduled_week
    from clinicians c
    cross join visit_weeks w
    where c.active = true
),

visit_counts as (
    select
        clinician_id,
        scheduled_week,
        count(*) as scheduled_visits,
        count(case when is_completed then 1 end) as completed_visits,
        count(case when is_missed then 1 end) as missed_visits
    from visits
    group by 1, 2
)

select
    cw.clinician_id,
    cw.clinician_name,
    cw.specialty,
    cw.weekly_capacity_visits,
    cw.scheduled_week,
    coalesce(vc.scheduled_visits, 0) as scheduled_visits,
    coalesce(vc.completed_visits, 0) as completed_visits,
    coalesce(vc.missed_visits, 0) as missed_visits,
    round(
        coalesce(vc.completed_visits, 0)
        / nullif(cw.weekly_capacity_visits, 0)::float * 100,
        1
    ) as utilization_rate_pct
from clinician_weeks cw
left join visit_counts vc
    on cw.clinician_id = vc.clinician_id
    and cw.scheduled_week = vc.scheduled_week
