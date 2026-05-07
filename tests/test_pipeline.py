from pathlib import Path

import pandas as pd

from dashboard.utils.data import (
    clinician_utilization,
    load_synthetic_data,
    payor_authorization_lag,
    referral_funnel,
)
from scripts import generate_synthetic_data


def test_generator_writes_expected_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_synthetic_data, "OUTPUT_DIR", tmp_path)

    generate_synthetic_data.main(n_patients=25, n_clinicians=5, n_referrals=50, seed=123)

    expected_files = {
        "patients.csv",
        "clinicians.csv",
        "payors.csv",
        "referrals.csv",
        "payor_authorizations.csv",
        "visits.csv",
    }
    actual_files = {path.name for path in tmp_path.glob("*.csv")}
    assert expected_files.issubset(actual_files)

    for filename in expected_files:
        path = tmp_path / filename
        assert path.stat().st_size > 0
        assert not pd.read_csv(path).empty


def test_local_dashboard_marts_have_expected_grain(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_synthetic_data, "OUTPUT_DIR", tmp_path)
    generate_synthetic_data.main(n_patients=50, n_clinicians=8, n_referrals=120, seed=55)

    data = load_synthetic_data(tmp_path)
    funnel = referral_funnel(data)
    payor_lag = payor_authorization_lag(data)
    utilization = clinician_utilization(data)

    assert not funnel.empty
    assert {"referral_month", "service_type", "urgency", "total_referrals"}.issubset(funnel.columns)
    assert funnel["total_referrals"].sum() == len(data["referrals"])

    assert not payor_lag.empty
    assert {"payor_name", "submitted_month", "avg_lag_days", "approval_rate_pct"}.issubset(payor_lag.columns)

    assert not utilization.empty
    assert {"clinician_id", "scheduled_week", "utilization_rate_pct", "is_over_capacity"}.issubset(
        utilization.columns
    )


def test_load_synthetic_data_reports_missing_files(tmp_path):
    (tmp_path / "patients.csv").write_text("patient_id\nPAT-1\n")

    try:
        load_synthetic_data(Path(tmp_path))
    except FileNotFoundError as exc:
        assert "Missing or empty data files" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for incomplete synthetic data directory")
