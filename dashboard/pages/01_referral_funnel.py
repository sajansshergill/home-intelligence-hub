import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.utils.data import load_synthetic_data, referral_funnel


st.set_page_config(page_title="Referral Funnel", page_icon="1", layout="wide")
st.title("Referral Funnel")
st.caption("Track where referrals drop from intake to authorization to first completed visit.")


@st.cache_data(show_spinner=False)
def get_funnel_data() -> pd.DataFrame:
    return referral_funnel(load_synthetic_data())


try:
    funnel = get_funnel_data()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

service_types = sorted(funnel["service_type"].dropna().unique())
urgencies = sorted(funnel["urgency"].dropna().unique())
months = sorted(funnel["referral_month"].dropna().unique())

with st.sidebar:
    st.header("Filters")
    selected_services = st.multiselect("Service type", service_types, default=service_types)
    selected_urgencies = st.multiselect("Urgency", urgencies, default=urgencies)
    selected_months = st.slider(
        "Referral month range",
        min_value=pd.Timestamp(min(months)).to_pydatetime(),
        max_value=pd.Timestamp(max(months)).to_pydatetime(),
        value=(pd.Timestamp(min(months)).to_pydatetime(), pd.Timestamp(max(months)).to_pydatetime()),
        format="YYYY-MM",
    )

filtered = funnel[
    funnel["service_type"].isin(selected_services)
    & funnel["urgency"].isin(selected_urgencies)
    & funnel["referral_month"].between(pd.Timestamp(selected_months[0]), pd.Timestamp(selected_months[1]))
]

total_referrals = int(filtered["total_referrals"].sum())
accepted = int(filtered["accepted_referrals"].sum())
authorized = int(filtered["authorized_referrals"].sum())
completed = int(filtered["completed_first_visits"].sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Referrals", f"{total_referrals:,}")
col2.metric("Acceptance Rate", f"{accepted / max(total_referrals, 1) * 100:.1f}%")
col3.metric("Authorization Rate", f"{authorized / max(accepted, 1) * 100:.1f}%")
col4.metric("First Visit Completion", f"{completed / max(authorized, 1) * 100:.1f}%")

stage_counts = pd.DataFrame(
    {
        "stage": ["Referred", "Accepted", "Authorized", "First Visit Complete"],
        "count": [total_referrals, accepted, authorized, completed],
    }
)

left, right = st.columns([1, 1])
with left:
    st.plotly_chart(
        px.funnel(stage_counts, x="count", y="stage", title="Referral Conversion Funnel"),
        width="stretch",
    )

with right:
    monthly = (
        filtered.groupby("referral_month", as_index=False)
        .agg(total_referrals=("total_referrals", "sum"), completed_first_visits=("completed_first_visits", "sum"))
    )
    monthly["end_to_end_conversion_pct"] = (
        monthly["completed_first_visits"] / monthly["total_referrals"].clip(lower=1) * 100
    )
    st.plotly_chart(
        px.line(
            monthly,
            x="referral_month",
            y="end_to_end_conversion_pct",
            markers=True,
            title="End-to-End Conversion Trend",
            labels={"end_to_end_conversion_pct": "Conversion %", "referral_month": "Month"},
        ),
        width="stretch",
    )

dropoffs = (
    filtered.groupby("service_type", as_index=False)
    .agg(
        dropped_at_referral=("dropped_at_referral", "sum"),
        dropped_at_auth=("dropped_at_auth", "sum"),
        dropped_at_visit=("dropped_at_visit", "sum"),
    )
    .melt(id_vars="service_type", var_name="dropoff_stage", value_name="referrals")
)
st.plotly_chart(
    px.bar(
        dropoffs,
        x="service_type",
        y="referrals",
        color="dropoff_stage",
        barmode="group",
        title="Drop-Offs by Service Type",
    ),
    width="stretch",
)

st.subheader("Funnel Detail")
st.dataframe(
    filtered.sort_values(["referral_month", "total_referrals"], ascending=[False, False]),
    width="stretch",
    hide_index=True,
)
