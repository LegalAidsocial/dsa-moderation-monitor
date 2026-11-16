"""SCRUM-64: Streamlit dashboard for our own checking - not the
deliverable report (that's report.py's static HTML), just a quick way
to look at the current numbers interactively.

Run: uv run --package monitor streamlit run monitor/src/monitor/dashboard.py
"""

import duckdb
import streamlit as st

from monitor import charts
from monitor.config import load_settings

st.set_page_config(page_title="DSA moderation monitor", layout="wide")
st.title("DSA platform moderation monitor")

settings = load_settings()
plat_path = settings.out_dir / "platform_monthly.parquet"
scale_path = settings.out_dir / "scale_totals.parquet"

if not plat_path.exists():
    st.error(f"{plat_path} not found - run `monitor build` first.")
    st.stop()

con = duckdb.connect()
months = [
    r[0]
    for r in con.execute(
        f"SELECT DISTINCT month FROM read_parquet('{plat_path.as_posix()}') ORDER BY 1 DESC"
    ).fetchall()
]
month = st.sidebar.selectbox("Month", months)
platform = st.sidebar.selectbox("Platform (for the category chart)", charts.PLATFORM_ORDER)

st.plotly_chart(charts.decisions_per_month(plat_path), use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.illegal_vs_own_rules(plat_path, month), use_container_width=True)
with col2:
    st.plotly_chart(charts.automation_share(plat_path, month), use_container_width=True)

st.plotly_chart(charts.category_trend(plat_path, platform), use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.action_breakdown(plat_path, month), use_container_width=True)
with col4:
    if scale_path.exists():
        st.plotly_chart(charts.top_countries(scale_path, month), use_container_width=True)
    else:
        st.info(f"{scale_path} not found.")
