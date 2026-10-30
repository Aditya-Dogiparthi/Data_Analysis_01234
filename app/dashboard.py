"""Single-screen executive dashboard for the Collections Intelligence investigation."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "golden"
PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

st.set_page_config(page_title="Collections Intelligence | CEO Brief", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .block-container { padding-top: 1.0rem; padding-bottom: 0.55rem; max-width: 1500px; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif; }
    .hero { background: #132337; color: #f5f8fc; padding: 19px 23px; border-radius: 14px; margin-bottom: 12px; }
    .hero .eyebrow { font-size: 10px; letter-spacing: .16em; font-weight: 700; color: #9fb6cf; text-transform: uppercase; }
    .hero h1 { font-size: 27px; margin: 5px 0 3px 0; }
    .hero p { color: #cbd6e2; margin: 0; font-size: 13px; }
    .verdict { border-left: 4px solid #d99a33; border-radius: 8px; background: #fff7e8; padding: 11px 14px; margin-bottom: 12px; color: #664b18; }
    .metric { border: 1px solid #e4e9ef; border-radius: 12px; padding: 12px 14px; background: #fff; min-height: 87px; }
    .metric .label { color: #63758b; text-transform: uppercase; letter-spacing: .09em; font-size: 9px; font-weight: 700; }
    .metric .value { color: #122238; font-family: 'Manrope', sans-serif; font-size: 23px; font-weight: 800; margin-top: 7px; }
    .metric .detail { color: #6f7f92; font-size: 10px; margin-top: 2px; }
    .panel { border: 1px solid #e5eaf0; border-radius: 12px; padding: 13px 15px; background: #fff; min-height: 242px; }
    .panel h3 { font-size: 15px; margin: 0 0 8px 0; color: #17283d; }
    .panel p { color: #53657a; font-size: 12px; line-height: 1.45; }
    .decision { background: #f2f6fa; border: 1px solid #dfe7ef; border-radius: 12px; padding: 14px 16px; min-height: 242px; }
    .decision h3 { font-size: 15px; margin: 0 0 8px 0; }
    .decision p { font-size: 12px; color: #43566c; line-height: 1.45; }
    .small { color: #708197; font-size: 10px; }
    [data-testid="stToolbar"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

summary_path = PROC / "pipeline_summary.json"
cash_path = GOLD / "monthly_cash_metrics.csv"
findings_path = REPORTS / "forensic_findings.csv"
if not all(p.exists() for p in (summary_path, cash_path, findings_path)):
    st.error("Run `python scripts/run_pipeline.py` from the repository root to build the executive metrics.")
    st.stop()

summary = json.loads(summary_path.read_text(encoding="utf-8"))
cash = pd.read_csv(cash_path)
findings = pd.read_csv(findings_path)

# Use complete January–July months for like-for-like endpoint comparison.
complete = cash[cash.complete_month.astype(bool)].copy()
complete = complete[complete.month.between("2026-01", "2026-07")].sort_values("month")
if complete.empty:
    st.error("No complete monthly payment periods found. Review pipeline coverage and manifest.")
    st.stop()

jan = complete.loc[complete.month.eq("2026-01"), "gross_successful_collections"]
jul = complete.loc[complete.month.eq("2026-07"), "gross_successful_collections"]
jan_jul_pct = ((float(jul.iloc[0]) / float(jan.iloc[0])) - 1) * 100 if len(jan) and len(jul) and jan.iloc[0] else float("nan")
feb_mar = complete.loc[complete.month.isin(["2026-02", "2026-03"])].sort_values("month")
feb_mar_pct = ((float(feb_mar.iloc[1].gross_successful_collections) / float(feb_mar.iloc[0].gross_successful_collections)) - 1) * 100 if len(feb_mar) == 2 else float("nan")
reversal_amount = float(cash.reversal_amount_reported_separately.sum())
gross_amount = float(cash.gross_successful_collections.sum())
raw_dups = int(summary.get("exact_duplicate_rows_removed_across_core_tables", 2957))
pay_conflicts = int(summary.get("payment_id_conflict_rows_quarantined", 28))
call_conflicts = int(summary.get("conflicting_call_id_rows_quarantined", 158))
reversal_events = int(cash.reversal_events.sum())

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Collections intelligence · executive decision brief</div>
      <h1>Trust the evidence, not the dashboard.</h1>
      <p>Independent reconstruction of payment integrity, population coverage and operational signals.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='verdict'><b>CLAIM STATUS: INCONCLUSIVE.</b> The source package is synthetic, covers 1 Jan–8 Aug 2026 (seven complete months plus partial August), and has no supplied original KPI formula or historical exposure denominator. The +11% recovery-rate claim cannot be verified.</div>",
    unsafe_allow_html=True,
)

kpis = st.columns(4, gap="small")
metric_specs = [
    ("Gross successful cash", f"₹{gross_amount/1e7:,.2f} Cr", "17,523 successful events · gross, not net"),
    ("Jan → Jul cash change", f"{jan_jul_pct:+.3f}%", "Comparable complete-month cash endpoints"),
    ("Reversals reported", f"₹{reversal_amount/1e7:,.2f} Cr", f"{reversal_events:,} events · not netted without links"),
    ("Rows removed / quarantined", f"{raw_dups+pay_conflicts+call_conflicts:,}", f"{raw_dups:,} exact dupes + {pay_conflicts:,} payment + {call_conflicts:,} call conflicts"),
]
for col, (label, value, detail) in zip(kpis, metric_specs):
    col.markdown(
        f"<div class='metric'><div class='label'>{label}</div><div class='value'>{value}</div><div class='detail'>{detail}</div></div>",
        unsafe_allow_html=True,
    )

left, right = st.columns([1.25, 1], gap="medium")
with left:
    st.markdown("<div class='panel'><h3>Monthly gross successful cash</h3>", unsafe_allow_html=True)
    chart = cash.sort_values("month").copy()
    chart["cash_cr"] = chart.gross_successful_collections / 1e7
    chart["period_type"] = chart.complete_month.map({True: "Complete month", False: "Partial month"})
    fig = px.bar(
        chart,
        x="month",
        y="cash_cr",
        color="period_type",
        color_discrete_map={"Complete month": "#2b7a78", "Partial month": "#d6a44b"},
        labels={"month": "Payment month", "cash_cr": "Gross successful cash (₹ Cr)", "period_type": "Coverage"},
        hover_data={"successful_payment_events": True, "reversal_events": True, "cash_cr": ":.2f"},
    )
    fig.update_layout(
        height=205, margin=dict(l=4, r=4, t=6, b=4), template="plotly_white",
        legend=dict(orientation="h", y=1.13, x=0), font=dict(size=10),
    )
    fig.update_yaxes(title=None, gridcolor="#edf1f5")
    fig.update_xaxes(title=None)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f"<p><b>Read:</b> Feb→Mar cash rose {feb_mar_pct:+.2f}%, then fell in April. Jan and Jul are essentially flat. August is partial and excluded from endpoint comparison.</p></div>",
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        """
        <div class="decision">
          <h3>₹10 Cr decision</h3>
          <p><b>Priority to test: better borrower targeting.</b> It is the most directly randomizable option in the supplied operational design, but the observed strategy results are non-random and overlapping. This is a pilot hypothesis, not proof of superior returns.</p>
          <p><b>Do not commit the full ₹10 Cr.</b> Approve a capped, costed 1:1 randomized pilot only after power analysis. Keep the balance uncommitted until net settled cash, linked reversals, cost and complaint guardrails clear the pre-registered hurdle.</p>
          <p><b>Financial case:</b> incremental recovery, cost, ROI and break-even are not estimable from this package.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### What prevents a stronger conclusion?")
flags = st.columns(3, gap="small")
flag_specs = [
    ("Denominator missing", "No monthly point-in-time outstanding exposure. Start-status coverage is 0% in Jan and 24.2% in Feb; the observed account panel is incomplete."),
    ("Attribution missing", "No payment-to-touch, campaign, agent or PTP key. Channel/campaign comparisons are activity correlations, not conversion."),
    ("Definitions and cost missing", "No approved RPC/disposition map, client/language/dialer mode or fully loaded cost ledger. ROI and break-even cannot be calculated."),
]
for col, (title, detail) in zip(flags, flag_specs):
    with col:
        st.markdown(f"<div class='panel' style='min-height:112px'><h3>{title}</h3><p>{detail}</p></div>", unsafe_allow_html=True)

st.markdown(
    f"<div class='small'>Dataset: {summary.get('dataset','SYNTHETIC CHALLENGE DATA (seed 42)')} · Payment coverage: {summary.get('payment_coverage_start','')} to {summary.get('payment_coverage_end','')} · Run: {summary.get('run_id','run manifest pending')} · Detail: README, reports/, notebooks/, sql/ and docs/</div>",
    unsafe_allow_html=True,
)
