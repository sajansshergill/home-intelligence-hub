from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "synthetic"
REQUIRED_FILES = {
    "patients": "patients.csv",
    "clinicians": "clinicians.csv",
    "payors": "payors.csv",
    "referrals": "referrals.csv",
    "authorizations": "payor_authorizations.csv",
    "visits": "visits.csv",
}


def load_synthetic_data(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load generated CSV data and normalize key fields used by the dashboard."""
    data_path = Path(data_dir)
    missing = [
        filename
        for filename in REQUIRED_FILES.values()
        if not (data_path / filename).exists() or (data_path / filename).stat().st_size == 0
    ]
    if missing:
        raise FileNotFoundError(
            "Missing or empty data files: "
            + ", ".join(missing)
            + ". Run `python scripts/generate_synthetic_data.py` from the repo root."
        )

    data = {
        name: pd.read_csv(data_path / filename)
        for name, filename in REQUIRED_FILES.items()
    }

    for column in ["referral_date", "accepted_date", "created_at"]:
        data["referrals"][column] = pd.to_datetime(data["referrals"][column], errors="coerce")

    for column in ["submitted_date", "approved_date", "denied_date", "created_at"]:
        data["authorizations"][column] = pd.to_datetime(data["authorizations"][column], errors="coerce")

    for column in ["scheduled_date", "completed_date", "created_at"]:
        data["visits"][column] = pd.to_datetime(data["visits"][column], errors="coerce")

    data["clinicians"]["hire_date"] = pd.to_datetime(data["clinicians"]["hire_date"], errors="coerce")

    for frame_name in ["referrals", "authorizations", "visits"]:
        if "status" in data[frame_name].columns:
            data[frame_name]["status"] = data[frame_name]["status"].str.lower().str.strip()

    return data


def referral_journey(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    referrals = data["referrals"].copy()
    auths = data["authorizations"].copy()
    visits = data["visits"].copy()
    payors = data["payors"].copy()

    latest_auths = (
        auths.sort_values("submitted_date")
        .drop_duplicates("referral_id", keep="last")
    )
    first_visits = (
        visits[visits["visit_number"].eq(1)]
        .sort_values("scheduled_date")
        .drop_duplicates("referral_id", keep="first")
    )

    journey = (
        referrals.merge(payors[["payor_id", "payor_name", "payor_type"]], on="payor_id", how="left")
        .merge(
            latest_auths.add_prefix("auth_"),
            left_on="referral_id",
            right_on="auth_referral_id",
            how="left",
        )
        .merge(
            first_visits.add_prefix("first_visit_"),
            left_on="referral_id",
            right_on="first_visit_referral_id",
            how="left",
        )
    )

    journey["is_accepted"] = journey["status"].eq("accepted")
    journey["is_rejected"] = journey["status"].eq("rejected")
    journey["referral_month"] = journey["referral_date"].dt.to_period("M").dt.to_timestamp()
    journey["referral_week"] = journey["referral_date"].dt.to_period("W").dt.start_time
    journey["acceptance_lag_hours"] = (
        journey["accepted_date"] - journey["referral_date"]
    ).dt.total_seconds() / 3600

    journey["auth_is_approved"] = journey["auth_status"].eq("approved")
    journey["auth_is_denied"] = journey["auth_status"].eq("denied")
    journey["auth_lag_calendar_days"] = (
        journey["auth_approved_date"] - journey["auth_submitted_date"]
    ).dt.days

    journey["first_visit_completed"] = journey["first_visit_status"].eq("completed")
    journey["referral_to_first_visit_days"] = (
        journey["first_visit_completed_date"] - journey["referral_date"]
    ).dt.days

    journey["funnel_stage_referral"] = "pending"
    journey.loc[journey["is_accepted"], "funnel_stage_referral"] = "accepted"
    journey.loc[journey["status"].eq("rejected"), "funnel_stage_referral"] = "rejected"
    journey.loc[journey["status"].eq("cancelled"), "funnel_stage_referral"] = "cancelled"

    journey["funnel_stage_auth"] = "no_auth"
    journey.loc[journey["auth_status"].notna(), "funnel_stage_auth"] = "in_review"
    journey.loc[journey["auth_is_approved"], "funnel_stage_auth"] = "authorized"
    journey.loc[journey["auth_is_denied"], "funnel_stage_auth"] = "denied"

    journey["funnel_stage_visit"] = "no_visit"
    journey.loc[journey["first_visit_visit_id"].notna(), "funnel_stage_visit"] = "visit_scheduled"
    journey.loc[journey["first_visit_completed"], "funnel_stage_visit"] = "visit_completed"

    return journey


def referral_funnel(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    journey = referral_journey(data)
    rows: list[dict] = []

    for keys, group in journey.groupby(["referral_month", "service_type", "urgency"], dropna=False):
        referral_month, service_type, urgency = keys
        total = len(group)
        accepted = group["funnel_stage_referral"].eq("accepted").sum()
        authorized = group["funnel_stage_auth"].eq("authorized").sum()
        completed = group["funnel_stage_visit"].eq("visit_completed").sum()

        rows.append(
            {
                "referral_month": referral_month,
                "service_type": service_type,
                "urgency": urgency,
                "total_referrals": total,
                "accepted_referrals": accepted,
                "rejected_referrals": group["funnel_stage_referral"].eq("rejected").sum(),
                "cancelled_referrals": group["funnel_stage_referral"].eq("cancelled").sum(),
                "authorized_referrals": authorized,
                "denied_referrals": group["funnel_stage_auth"].eq("denied").sum(),
                "in_review_referrals": group["funnel_stage_auth"].eq("in_review").sum(),
                "completed_first_visits": completed,
                "scheduled_first_visits": group["funnel_stage_visit"].eq("visit_scheduled").sum(),
                "dropped_at_referral": total - accepted,
                "dropped_at_auth": accepted - authorized,
                "dropped_at_visit": authorized - completed,
                "acceptance_rate_pct": _pct(accepted, total),
                "auth_rate_pct": _pct(authorized, accepted),
                "visit_completion_rate_pct": _pct(completed, authorized),
                "end_to_end_conversion_pct": _pct(completed, total),
                "avg_acceptance_lag_hours": group["acceptance_lag_hours"].mean(),
                "avg_auth_lag_days": group["auth_lag_calendar_days"].mean(),
                "avg_referral_to_first_visit_days": group.loc[
                    group["referral_to_first_visit_days"].gt(0),
                    "referral_to_first_visit_days",
                ].mean(),
            }
        )

    return pd.DataFrame(rows).sort_values(["referral_month", "total_referrals"], ascending=[False, False])


def payor_authorization_lag(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    auths = data["authorizations"].copy()
    payors = data["payors"].copy()

    auths["submitted_month"] = auths["submitted_date"].dt.to_period("M").dt.to_timestamp()
    auths["is_approved"] = auths["status"].eq("approved")
    auths["is_denied"] = auths["status"].eq("denied")
    auths["is_pending_info"] = auths["status"].eq("pending_info")
    auths["auth_lag_calendar_days"] = (auths["approved_date"] - auths["submitted_date"]).dt.days
    auths["units_approval_rate"] = auths["units_approved"] / auths["units_requested"].replace(0, pd.NA)

    joined = auths.merge(payors, on="payor_id", how="left")
    joined["is_sla_breach"] = (
        joined["is_approved"]
        & joined["auth_lag_calendar_days"].gt(joined["avg_auth_lag_days"] * 1.5)
    )

    rows: list[dict] = []
    for keys, group in joined.groupby(
        ["payor_id", "payor_name", "payor_type", "avg_auth_lag_days", "requires_prior_auth", "submitted_month"],
        dropna=False,
    ):
        payor_id, payor_name, payor_type, expected_lag, requires_prior_auth, submitted_month = keys
        approved = group[group["is_approved"]]
        total_auths = len(group)
        approved_count = len(approved)
        breach_count = int(group["is_sla_breach"].sum())

        rows.append(
            {
                "payor_id": payor_id,
                "payor_name": payor_name,
                "payor_type": payor_type,
                "payor_expected_lag_days": expected_lag,
                "requires_prior_auth": requires_prior_auth,
                "submitted_month": submitted_month,
                "total_auths": total_auths,
                "approved_auths": approved_count,
                "denied_auths": int(group["is_denied"].sum()),
                "pending_info_auths": int(group["is_pending_info"].sum()),
                "avg_lag_days": approved["auth_lag_calendar_days"].mean(),
                "min_lag_days": approved["auth_lag_calendar_days"].min(),
                "max_lag_days": approved["auth_lag_calendar_days"].max(),
                "p50_lag_days": approved["auth_lag_calendar_days"].quantile(0.50),
                "p90_lag_days": approved["auth_lag_calendar_days"].quantile(0.90),
                "sla_breach_count": breach_count,
                "sla_breach_rate_pct": _pct(breach_count, approved_count),
                "approval_rate_pct": _pct(approved_count, total_auths),
                "denial_rate_pct": _pct(int(group["is_denied"].sum()), total_auths),
                "avg_units_approval_rate": approved["units_approval_rate"].mean(),
                "lag_vs_expected_delta_days": approved["auth_lag_calendar_days"].mean() - expected_lag,
            }
        )

    return pd.DataFrame(rows).sort_values(["submitted_month", "avg_lag_days"], ascending=[False, False])


def clinician_utilization(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    visits = data["visits"].copy()
    clinicians = data["clinicians"].copy()

    visits["scheduled_week"] = visits["scheduled_date"].dt.to_period("W").dt.start_time
    visits["is_completed"] = visits["status"].eq("completed")
    visits["is_missed"] = visits["status"].eq("missed")
    visits["visit_start_offset_minutes"] = (
        visits["completed_date"] - visits["scheduled_date"]
    ).dt.total_seconds() / 60

    weeks = pd.DataFrame({"scheduled_week": sorted(visits["scheduled_week"].dropna().unique())})
    active_clinicians = clinicians[clinicians["active"].astype(str).str.lower().isin(["true", "1"])]
    clinician_weeks = active_clinicians.merge(weeks, how="cross")

    visit_agg = (
        visits.groupby(["clinician_id", "scheduled_week"], dropna=False)
        .agg(
            total_scheduled=("visit_id", "count"),
            total_completed=("is_completed", "sum"),
            total_missed=("is_missed", "sum"),
            total_cancelled=("status", lambda s: s.eq("cancelled").sum()),
            avg_visit_duration_min=("duration_minutes", lambda s: s.dropna().mean()),
            total_completed_hours=("duration_minutes", lambda s: s.dropna().sum() / 60),
            unique_patients_seen=("patient_id", "nunique"),
            avg_late_minutes=("visit_start_offset_minutes", lambda s: s[s.gt(0)].mean()),
        )
        .reset_index()
    )

    result = clinician_weeks.merge(visit_agg, on=["clinician_id", "scheduled_week"], how="left")
    numeric_fill = [
        "total_scheduled",
        "total_completed",
        "total_missed",
        "total_cancelled",
        "avg_visit_duration_min",
        "total_completed_hours",
        "unique_patients_seen",
    ]
    result[numeric_fill] = result[numeric_fill].fillna(0)
    result["clinician_name"] = result["first_name"] + " " + result["last_name"]
    result["tenure_years"] = ((pd.Timestamp.today() - result["hire_date"]).dt.days / 365.25).round(1)
    result["missed_rate_pct"] = result.apply(lambda row: _pct(row["total_missed"], row["total_scheduled"]), axis=1)
    result["utilization_rate_pct"] = result.apply(
        lambda row: _pct(row["total_completed"], row["weekly_capacity_visits"]),
        axis=1,
    )
    result["capacity_remaining"] = result["weekly_capacity_visits"] - result["total_completed"]
    result["is_over_capacity"] = result["total_completed"] > result["weekly_capacity_visits"] * 1.10
    result["is_underutilized"] = result["total_completed"] < result["weekly_capacity_visits"] * 0.50

    columns = [
        "clinician_id",
        "clinician_name",
        "specialty",
        "weekly_capacity_visits",
        "tenure_years",
        "scheduled_week",
        "total_scheduled",
        "total_completed",
        "total_missed",
        "total_cancelled",
        "unique_patients_seen",
        "avg_visit_duration_min",
        "total_completed_hours",
        "avg_late_minutes",
        "missed_rate_pct",
        "utilization_rate_pct",
        "capacity_remaining",
        "is_over_capacity",
        "is_underutilized",
    ]
    return result[columns].sort_values(["scheduled_week", "utilization_rate_pct"], ascending=[False, False])


def latest_month(frame: pd.DataFrame, column: str) -> pd.Timestamp | None:
    values = frame[column].dropna()
    if values.empty:
        return None
    return values.max()


def _pct(numerator: float, denominator: float) -> float:
    if denominator in (0, None) or pd.isna(denominator):
        return 0.0
    return round(float(numerator) / float(denominator) * 100, 1)
