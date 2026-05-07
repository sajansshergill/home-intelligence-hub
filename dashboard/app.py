import sys
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.utils.data import clinician_utilization, load_synthetic_data, payor_authorization_lag, referral_funnel


st.set_page_config(
    page_title="Home Care Intelligence Hub",
    page_icon="H",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_dashboard_data():
    data = load_synthetic_data()
    return {
        "raw": data,
        "funnel": referral_funnel(data),
        "payor_lag": payor_authorization_lag(data),
        "clinician_utilization": clinician_utilization(data),
    }


st.title("Home Care Intelligence Hub")
st.caption("A local-first analytics demo for home health referral operations.")

try:
    dashboard_data = get_dashboard_data()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

raw = dashboard_data["raw"]
funnel = dashboard_data["funnel"]
payor_lag = dashboard_data["payor_lag"]
utilization = dashboard_data["clinician_utilization"]

latest_funnel_month = funnel["referral_month"].max()
latest_auth_month = payor_lag["submitted_month"].max()
latest_week = utilization["scheduled_week"].max()

latest_funnel = funnel[funnel["referral_month"].eq(latest_funnel_month)]
latest_auth = payor_lag[payor_lag["submitted_month"].eq(latest_auth_month)]
latest_utilization = utilization[utilization["scheduled_week"].eq(latest_week)]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Synthetic Patients", f"{len(raw['patients']):,}")
col2.metric("Referrals", f"{len(raw['referrals']):,}")
col3.metric("Authorizations", f"{len(raw['authorizations']):,}")
col4.metric("Visits", f"{len(raw['visits']):,}")

st.subheader("Current Operating Snapshot")
snap1, snap2, snap3 = st.columns(3)
snap1.metric(
    "End-to-End Conversion",
    f"{latest_funnel['completed_first_visits'].sum() / max(latest_funnel['total_referrals'].sum(), 1) * 100:.1f}%",
    help="Completed first visits divided by total referrals in the latest referral month.",
)
snap2.metric(
    "Avg Payor Lag",
    f"{latest_auth['avg_lag_days'].mean():.1f} days",
    help="Average approved authorization lag in the latest submitted month.",
)
snap3.metric(
    "Over Capacity Clinicians",
    f"{int(latest_utilization['is_over_capacity'].sum()):,}",
    help="Clinician-week records above 110% of weekly capacity in the latest week.",
)

st.markdown(
    """
    This project models the weekly questions a home health operations leader needs answered:

    - **Referral funnel:** where referrals drop before first visit.
    - **Payor lag:** which insurers delay authorization and create revenue risk.
    - **Clinician utilization:** where teams are overloaded or underused.

    Use the pages in the sidebar to explore each workflow. The dashboard reads directly from
    `data/synthetic/*.csv`, so it runs locally without warehouse credentials.
    """
)
