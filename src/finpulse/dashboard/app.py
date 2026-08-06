from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
DEMO_SUMMARY_PATH = Path(os.getenv("DEMO_SUMMARY_PATH", "artifacts/local-demo/demo-summary.json"))
COUNTRY_NAMES = {
    "KEN": "Kenya",
    "UGA": "Uganda",
    "GHA": "Ghana",
    "TZA": "Tanzania",
    "ZMB": "Zambia",
}
COLORS = ["#29D3A1", "#FFC857", "#6C8CFF", "#F4777F", "#A77BF3"]

st.set_page_config(
    page_title="FinPulse | Credit Data Platform",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
    :root { --ink:#10251f; --mint:#29d3a1; --cream:#f4f7f2; --amber:#ffc857; }
    .stApp { background: radial-gradient(circle at 85% 3%, #d8fff2 0, transparent 24%), #f4f7f2; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    h1, h2, h3 { letter-spacing: -0.035em; }
    [data-testid="stSidebar"] { background: #10251f; color: white; }
    [data-testid="stSidebar"] * { color: #eafaf4 !important; }
    [data-testid="stMetric"] { background: rgba(255,255,255,.82); border: 1px solid #dbe8e2;
        border-radius: 16px; padding: 18px; box-shadow: 0 8px 28px rgba(16,37,31,.05); }
    [data-testid="stMetricLabel"] { color: #5c7069; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #10251f; font-family: 'Space Mono', monospace; }
    .hero { background: #10251f; color: white; border-radius: 24px; padding: 30px 34px;
        margin: 2px 0 24px; box-shadow: 0 16px 45px rgba(16,37,31,.16); position:relative; overflow:hidden; }
    .hero:after { content:''; position:absolute; width:220px; height:220px; right:-55px; top:-90px;
        border:35px solid #29d3a1; border-radius:50%; opacity:.42; }
    .eyebrow { color:#73ecc7; font-family:'Space Mono',monospace; font-size:12px; letter-spacing:.11em; }
    .hero h1 { color:white; margin:7px 0 3px; font-size:40px; }
    .hero p { color:#b9d0c8; margin:0; max-width:760px; }
    .status-dot { width:9px; height:9px; background:#29d3a1; border-radius:50%; display:inline-block;
        box-shadow:0 0 0 5px rgba(41,211,161,.14); margin-right:8px; }
    .section-label { font-family:'Space Mono',monospace; font-size:12px; color:#687b74;
        letter-spacing:.09em; margin-top:10px; }
    .architecture { background:#fff; border:1px solid #dbe8e2; border-radius:18px; padding:20px;
        font-family:'Space Mono',monospace; text-align:center; line-height:2.5; }
    .node { display:inline-block; border-radius:10px; padding:6px 12px; background:#e5fbf4; color:#10251f; }
    .arrow { color:#829890; margin:0 6px; }
    div[data-testid="stDataFrame"] { border:1px solid #dbe8e2; border-radius:14px; overflow:hidden; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius:10px; padding:8px 16px; background:#e7eee9; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=5, show_spinner=False)
def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    response = httpx.get(f"{API_URL}{path}", params=params, timeout=5)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=30, show_spinner=False)
def local_demo_data() -> dict[str, Any]:
    if not DEMO_SUMMARY_PATH.exists():
        return {}
    return json.loads(DEMO_SUMMARY_PATH.read_text(encoding="utf-8"))


def safe_get(path: str, default: Any, params: dict[str, Any] | None = None) -> Any:
    try:
        return api_get(path, params)
    except (httpx.HTTPError, ValueError):
        demo = local_demo_data()
        if path == "/api/v1/summary" and demo:
            return {
                **demo.get("business_metrics", {}),
                "total_events": demo.get("records", {}).get("accepted", 0),
                "events_5m": 0,
                "latest_event_at": None,
            }
        if path == "/api/v1/countries" and demo:
            return demo.get("country_performance", [])
        return default


def number(value: Any, decimals: int = 0) -> str:
    if value is None:
        return "—"
    numeric = float(value)
    return f"{numeric:,.{decimals}f}"


with st.sidebar:
    st.markdown("## ◈ FINPULSE")
    st.caption("CREDIT INTELLIGENCE PLATFORM")
    st.markdown("---")
    st.markdown("**Live stack**")
    st.markdown("`Kafka` → `Spark` → `S3`")
    st.markdown("`Airflow` → `dbt` → `PostgreSQL`")
    st.markdown("`Prometheus` → `Grafana`")
    st.markdown("---")
    refresh = st.button("↻ Refresh live data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
    st.caption(f"API: {API_URL}")
    st.caption(f"UTC {datetime.now(UTC).strftime('%H:%M:%S')}")

health = safe_get("/health", {"status": "portable_demo"})
summary = safe_get("/api/v1/summary", {})
is_healthy = health.get("status") == "healthy"
platform_mode = "operational" if is_healthy else "portable demo"

st.markdown(
    f"""
    <div class="hero">
      <div class="eyebrow">DATA PRODUCT / REAL-TIME CREDIT OPERATIONS</div>
      <h1>Finance signals, made decision-ready.</h1>
      <p>Streaming GSM and mobile-money activity into governed credit features, portfolio insights,
      and observable data products across five African markets.</p>
      <p style="margin-top:16px"><span class="status-dot"></span>
      Platform <b>{platform_mode}</b></p>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_tab, portfolio_tab, risk_tab, platform_tab = st.tabs(
    ["Executive overview", "Country portfolio", "Risk & decisions", "Platform operations"]
)

with overview_tab:
    st.markdown('<div class="section-label">LIVE PORTFOLIO PULSE</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Events processed", number(summary.get("total_events")))
    col2.metric("Applications", number(summary.get("applications")))
    col3.metric("Approval rate", f"{number(summary.get('approval_rate_pct'), 1)}%")
    col4.metric("Average score", number(summary.get("average_score"), 0))
    col5.metric("PAR30", f"{number(summary.get('par30_pct'), 1)}%")

    throughput = pd.DataFrame(safe_get("/api/v1/throughput", [], {"minutes": 60}))
    left, right = st.columns([1.65, 1])
    with left:
        st.markdown("### Streaming throughput")
        if not throughput.empty:
            throughput["minute"] = pd.to_datetime(throughput["minute"])
            fig = px.area(
                throughput,
                x="minute",
                y="event_count",
                color="event_type",
                color_discrete_sequence=COLORS,
            )
            fig.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=15, b=10),
                legend_title_text="",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "Throughput appears here once the producer and Spark job have processed events."
            )
    with right:
        st.markdown("### Credit funnel")
        funnel = go.Figure(
            go.Funnel(
                y=["Applications", "Decisions", "Approvals", "Repaying"],
                x=[
                    summary.get("applications", 0),
                    summary.get("decisions", 0),
                    summary.get("approvals", 0),
                    summary.get("loans_with_repayment", 0),
                ],
                textinfo="value+percent initial",
                marker={"color": COLORS[:4]},
            )
        )
        funnel.update_layout(
            height=350,
            margin=dict(l=15, r=15, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(funnel, use_container_width=True)

    st.markdown("### End-to-end lineage")
    st.markdown(
        """
        <div class="architecture">
          <span class="node">GSM + money sources</span><span class="arrow">→</span>
          <span class="node">Kafka</span><span class="arrow">→</span>
          <span class="node">Spark quality gates</span><span class="arrow">→</span>
          <span class="node">S3 medallion lake</span><span class="arrow">→</span>
          <span class="node">dbt marts</span><span class="arrow">→</span>
          <span class="node">Risk + BI products</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with portfolio_tab:
    countries = pd.DataFrame(safe_get("/api/v1/countries", []))
    st.markdown("### Market performance")
    if not countries.empty:
        countries["market"] = countries["country_code"].map(COUNTRY_NAMES)
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                countries,
                x="market",
                y="applications",
                color="approval_rate_pct",
                color_continuous_scale=["#e8eee9", "#29d3a1", "#0d6b51"],
                text="applications",
                title="Application volume and approval rate",
            )
            fig.update_layout(height=390, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.scatter(
                countries,
                x="approval_rate_pct",
                y="par30_pct",
                size="applications",
                color="market",
                color_discrete_sequence=COLORS,
                text="country_code",
                title="Growth–risk frontier",
            )
            fig.update_traces(textposition="top center")
            fig.update_layout(height=390, plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        display_columns = [
            "market",
            "applications",
            "applicants",
            "approvals",
            "approval_rate_pct",
            "average_credit_score",
            "par30_pct",
        ]
        st.dataframe(countries[display_columns], use_container_width=True, hide_index=True)
    else:
        st.info(
            "Country metrics will populate as coherent loan application and decision events arrive."
        )

with risk_tab:
    distribution = pd.DataFrame(safe_get("/api/v1/risk-distribution", []))
    monitoring = pd.DataFrame(safe_get("/api/v1/model-monitoring", []))
    left, right = st.columns(2)
    with left:
        st.markdown("### Decision distribution")
        if not distribution.empty:
            fig = px.bar(
                distribution,
                x="risk_band",
                y="decisions",
                color="approval_rate_pct",
                color_continuous_scale=["#f4777f", "#ffc857", "#29d3a1"],
                text="decisions",
            )
            fig.update_layout(height=370, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Waiting for loan decisions.")
    with right:
        st.markdown("### Model stability")
        if not monitoring.empty:
            monitoring["period"] = pd.to_datetime(monitoring["period"])
            fig = px.line(
                monitoring,
                x="period",
                y="average_score",
                color="model_version",
                markers=True,
                color_discrete_sequence=COLORS,
            )
            fig.update_layout(height=370, plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Model score monitoring will appear here.")
    st.caption(
        "The synthetic data includes latent customer risk, enabling a credible relationship between "
        "behavioral features, model scores, approval decisions, and repayment outcomes."
    )

with platform_tab:
    quality = safe_get("/api/v1/data-quality", {"checks": [], "latest_pipeline_run": None})
    recent = pd.DataFrame(safe_get("/api/v1/events/recent", []))
    st.markdown("### Service-level objectives")
    col1, col2, col3, col4 = st.columns(4)
    event_age = None
    if summary.get("latest_event_at"):
        latest = datetime.fromisoformat(str(summary["latest_event_at"]).replace("Z", "+00:00"))
        event_age = max(0, (datetime.now(UTC) - latest).total_seconds())
    col1.metric("API status", "Healthy" if is_healthy else "Offline")
    col2.metric("Latest event age", f"{number(event_age, 1)}s")
    col3.metric("Events / 5 min", number(summary.get("events_5m")))
    col4.metric("Quality checks", number(len(quality.get("checks", []))))
    st.markdown("### Recent event flow")
    if not recent.empty:
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info(
            "No events loaded yet. Start the producer and streaming processor to see live flow."
        )
    with st.expander("Operational endpoints and consoles"):
        st.markdown(
            "- Kafka console: `http://localhost:8080`\n"
            "- API documentation: `http://localhost:8000/docs`\n"
            "- MinIO console: `http://localhost:9001`\n"
            "- Airflow: `http://localhost:8088`\n"
            "- Grafana: `http://localhost:3000`\n"
            "- Prometheus: `http://localhost:9090`"
        )
