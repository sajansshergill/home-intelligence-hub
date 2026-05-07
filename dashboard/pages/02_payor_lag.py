import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.utils.data import load_synthetic_data, payor_authorization_lag


st.set_page_config(page_title="Payor Authorization Lag", page_icon="2", layout="wide")
st.title("Payor Authorization Lag")
st.caption("Identify payors creating authorization delays, SLA breaches, and revenue risk.")


@st.cache_data(show_spinner=False)
def get_payor_data() -> pd.DataFrame:
    return payor_authorization_lag(load_synthetic_data())


try:
    payors = get_payor_data()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

payor_names = sorted(payors["payor_name"].dropna().unique())
payor_types = sorted(payors["payor_type"].dropna().unique())

with st.sidebar:
    st.header("Filters")
    selected_payors = st.multiselect("Payor", payor_names, default=payor_names)
    selected_types = st.multiselect("Payor type", payor_types, default=payor_types)

filtered = payors[
    payors["payor_name"].isin(selected_payors)
    & payors["payor_type"].isin(selected_types)
]

approved_auths = int(filtered["approved_auths"].sum())
total_auths = int(filtered["total_auths"].sum())
sla_breaches = int(filtered["sla_breach_count"].sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Auths", f"{total_auths:,}")
col2.metric("Approval Rate", f"{approved_auths / max(total_auths, 1) * 100:.1f}%")
col3.metric("Avg Lag", f"{filtered['avg_lag_days'].mean():.1f} days")
col4.metric("SLA Breach Rate", f"{sla_breaches / max(approved_auths, 1) * 100:.1f}%")

latest_month = filtered["submitted_month"].max()
latest = filtered[filtered["submitted_month"].eq(latest_month)]

left, right = st.columns([1, 1])
with left:
    st.plotly_chart(
        px.bar(
            latest.sort_values("avg_lag_days", ascending=False),
            x="payor_name",
            y="avg_lag_days",
            color="payor_type",
            title=f"Average Lag by Payor ({pd.Timestamp(latest_month):%b %Y})",
            labels={"payor_name": "Payor", "avg_lag_days": "Avg lag days"},
        ),
        width="stretch",
    )

with right:
    st.plotly_chart(
        px.scatter(
            latest,
            x="approval_rate_pct",
            y="avg_lag_days",
            size="total_auths",
            color="sla_breach_rate_pct",
            hover_name="payor_name",
            title="Approval Performance vs Lag",
            labels={
                "approval_rate_pct": "Approval rate %",
                "avg_lag_days": "Avg lag days",
                "sla_breach_rate_pct": "SLA breach %",
            },
        ),
        width="stretch",
    )

monthly = (
    filtered.groupby("submitted_month", as_index=False)
    .agg(avg_lag_days=("avg_lag_days", "mean"), p90_lag_days=("p90_lag_days", "mean"))
)
st.plotly_chart(
    px.line(
        monthly,
        x="submitted_month",
        y=["avg_lag_days", "p90_lag_days"],
        markers=True,
        title="Lag Trend",
        labels={"value": "Days", "submitted_month": "Month", "variable": "Metric"},
    ),
    width="stretch",
)

st.subheader("Payor Detail")
st.dataframe(
    filtered.sort_values(["submitted_month", "avg_lag_days"], ascending=[False, False]),
    width="stretch",
    hide_index=True,
)
