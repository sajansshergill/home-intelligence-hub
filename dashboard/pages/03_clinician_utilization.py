import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.utils.data import clinician_utilization, load_synthetic_data


st.set_page_config(page_title="Clinician Utilization", page_icon="3", layout="wide")
st.title("Clinician Utilization")
st.caption("Spot burnout risk, unused capacity, missed visits, and weekly workforce balance.")


@st.cache_data(show_spinner=False)
def get_utilization_data() -> pd.DataFrame:
    return clinician_utilization(load_synthetic_data())


try:
    utilization = get_utilization_data()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

specialties = sorted(utilization["specialty"].dropna().unique())
weeks = sorted(utilization["scheduled_week"].dropna().unique())

with st.sidebar:
    st.header("Filters")
    selected_specialties = st.multiselect("Specialty", specialties, default=specialties)
    selected_week = st.selectbox(
        "Scheduled week",
        weeks,
        index=len(weeks) - 1,
        format_func=lambda value: pd.Timestamp(value).strftime("%Y-%m-%d"),
    )

filtered = utilization[
    utilization["specialty"].isin(selected_specialties)
    & utilization["scheduled_week"].eq(selected_week)
]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Completed Visits", f"{int(filtered['total_completed'].sum()):,}")
col2.metric("Avg Utilization", f"{filtered['utilization_rate_pct'].mean():.1f}%")
col3.metric("Over Capacity", f"{int(filtered['is_over_capacity'].sum()):,}")
col4.metric("Underutilized", f"{int(filtered['is_underutilized'].sum()):,}")

left, right = st.columns([1, 1])
with left:
    st.plotly_chart(
        px.histogram(
            filtered,
            x="utilization_rate_pct",
            nbins=20,
            title="Utilization Distribution",
            labels={"utilization_rate_pct": "Utilization %"},
        ),
        use_container_width=True,
    )

with right:
    st.plotly_chart(
        px.bar(
            filtered.sort_values("utilization_rate_pct", ascending=False).head(20),
            x="clinician_name",
            y="utilization_rate_pct",
            color="specialty",
            title="Top 20 Clinicians by Utilization",
            labels={"clinician_name": "Clinician", "utilization_rate_pct": "Utilization %"},
        ),
        use_container_width=True,
    )

weekly_trend = (
    utilization[utilization["specialty"].isin(selected_specialties)]
    .groupby("scheduled_week", as_index=False)
    .agg(
        avg_utilization=("utilization_rate_pct", "mean"),
        over_capacity=("is_over_capacity", "sum"),
        underutilized=("is_underutilized", "sum"),
    )
)
st.plotly_chart(
    px.line(
        weekly_trend,
        x="scheduled_week",
        y=["avg_utilization", "over_capacity", "underutilized"],
        markers=True,
        title="Weekly Workforce Trend",
        labels={"value": "Value", "scheduled_week": "Week", "variable": "Metric"},
    ),
    use_container_width=True,
)

st.subheader("Clinician Detail")
st.dataframe(
    filtered.sort_values("utilization_rate_pct", ascending=False),
    use_container_width=True,
    hide_index=True,
)
