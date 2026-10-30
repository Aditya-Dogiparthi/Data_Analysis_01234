"""Build the assignment-specific, point-in-time-aware analytical outputs.

This script runs after run_pipeline.py and advanced_analysis.py. It overwrites
legacy account-month and agent outputs where the initial implementation used
month-end status (survivorship leakage) or a non-unique agent dimension.
All timestamps stay source-local/naive unless a source contract explicitly
certifies their timezone semantics.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
GOLD = ROOT / "data" / "golden"
QUAR = ROOT / "data" / "quarantine"
REPORTS = ROOT / "reports"
for p in (PROC, GOLD, QUAR, REPORTS):
    p.mkdir(parents=True, exist_ok=True)

ELIGIBLE_STATUSES = {"ACTIVE", "DELINQUENT", "NPA", "PTP"}
AS_OF_CUTOFF = pd.Timestamp("2026-08-08 23:59:59")


def read_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / f"{name}.csv", low_memory=False)


def read_clean(name: str) -> pd.DataFrame:
    path = PROC / f"{name}_deduped.csv"
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return read_raw(name).drop_duplicates().copy()


def save(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
    # CSV remains the portable canonical export; Parquet is an optional local accelerator.
    if len(df) <= 50000:
        try:
            df.to_parquet(path.with_suffix(".parquet"), index=False)
        except (ImportError, ModuleNotFoundError, ValueError):
            pass


def month_str(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").astype(str)


def latest_asof(history: pd.DataFrame, cutoff: pd.Timestamp, strict: bool = True) -> pd.DataFrame:
    """Latest effective status known by system time cutoff."""
    if history.empty:
        return pd.DataFrame(columns=["account_id", "status", "event_ts", "recorded_ts"])
    mask = history.event_ts.lt(cutoff) & history.recorded_ts.le(cutoff) if strict else (
        history.event_ts.le(cutoff) & history.recorded_ts.le(cutoff)
    )
    eligible = history.loc[mask].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["account_id", "status", "event_ts", "recorded_ts"])
    eligible = eligible.sort_values(["account_id", "event_ts", "recorded_ts", "history_id"])
    return eligible.drop_duplicates("account_id", keep="last")[
        ["account_id", "status", "event_ts", "recorded_ts"]
    ]


def add_finding(rows: list[dict], issue: str, measured: object, evidence: str,
                treatment: str, impact: str, confidence: str = "FACT") -> None:
    rows.append({"issue": issue, "measured_value": measured, "evidence": evidence,
                 "treatment": treatment, "business_impact": impact, "confidence": confidence})


# Read every source through the exact-row-deduplicated layer for analysis.
source_names = [
    "accounts", "borrowers", "agents", "agent_sessions", "campaigns", "daily_targeting",
    "calls", "call_attempts", "call_dispositions", "whatsapp_events", "sms_events",
    "field_visits", "promises_to_pay", "payments", "vendor_telephony", "complaints",
    "account_status_history",
]
src = {name: read_clean(name) for name in source_names}
raw = {name: read_raw(name) for name in source_names}

# Stable event identifiers with conflicting non-identical payloads are quarantined in full.
event_key_map = {
    "calls": "call_id", "call_attempts": "attempt_id", "call_dispositions": "disposition_id",
    "whatsapp_events": "whatsapp_event_id", "sms_events": "sms_event_id", "field_visits": "visit_id",
    "promises_to_pay": "ptp_id", "agent_sessions": "session_id", "daily_targeting": "target_id",
    "complaints": "complaint_id", "account_status_history": "history_id",
}
event_conflict_frames = []
event_conflict_ids: dict[str, set] = {}
for table, key in event_key_map.items():
    d = src[table]
    n = d.groupby(key, dropna=False).size()
    bad_ids = set(n[n > 1].index)
    if bad_ids:
        conflict = d[d[key].isin(bad_ids)].copy()
        conflict.insert(0, "source_table", table)
        conflict.insert(1, "source_key", key)
        event_conflict_frames.append(conflict)
        event_conflict_ids[table] = bad_ids
        # Do not pick an arbitrary payload for an allegedly stable event ID.
        src[table] = d[~d[key].isin(bad_ids)].copy()
if event_conflict_frames:
    event_conflicts = pd.concat(event_conflict_frames, ignore_index=True, sort=False)
else:
    event_conflicts = pd.DataFrame(columns=["source_table", "source_key"])
save(event_conflicts, QUAR / "event_id_conflicts.csv")

# --- Canonical dimensions: preserve history, create deterministic current snapshots. ---
accounts = src["accounts"].drop_duplicates("account_id").copy()
accounts["dpd_num"] = pd.to_numeric(accounts["dpd"], errors="coerce")
accounts["dpd_bucket"] = pd.cut(
    accounts["dpd_num"], [-1, 0, 30, 60, 90, 180, 100000],
    labels=["Current", "1-30", "31-60", "61-90", "91-180", "180+"],
).astype("string").fillna("Unknown")
save(accounts, GOLD / "golden_accounts_snapshot.csv")

borrowers = src["borrowers"].copy()
borrowers["updated_ts"] = pd.to_datetime(borrowers["updated_at"], errors="coerce")
borrowers = borrowers.sort_values(["borrower_id", "updated_ts", "created_at"])
borrower_snapshot = borrowers.drop_duplicates("borrower_id", keep="last").copy()
save(borrower_snapshot, GOLD / "golden_borrowers_snapshot.csv")

agents = src["agents"].copy()
ag_raw_rows = len(agents)
ag_versions = agents.groupby("agent_id", dropna=False).size()
ag_conflict_ids = ag_versions[ag_versions > 1].index
agents["updated_ts"] = pd.to_datetime(agents["updated_at"], errors="coerce")
agents = agents.sort_values(["agent_id", "updated_ts", "joined_at"])
agent_snapshot = agents.drop_duplicates("agent_id", keep="last").copy()
save(agent_snapshot, GOLD / "golden_agents_snapshot.csv")

# Keep all source versions auditable; current dimensions use latest updated_at only.
if len(agents) > len(agent_snapshot):
    agent_superseded = agents[~agents.index.isin(agent_snapshot.index)].copy()
    save(agent_superseded, QUAR / "agent_superseded_versions.csv")

borrower_conflict_counts = borrowers.groupby("borrower_id").size()
borrower_conflict_ids = borrower_conflict_counts[borrower_conflict_counts > 1].index
borrower_superseded = borrowers[~borrowers.index.isin(borrower_snapshot.index)].copy()
save(borrower_superseded, QUAR / "borrower_superseded_versions.csv")

account_dim = accounts.merge(
    borrower_snapshot[["borrower_id", "city", "state"]], on="borrower_id", how="left", validate="many_to_one"
)
save(account_dim, GOLD / "account_dimension_enriched.csv")

# Agent identity alias review is performed on the latest record per agent, not all versions.
agent_alias = agent_snapshot.groupby("employee_code", dropna=False).agg(
    agent_ids=("agent_id", "nunique"), agent_id_list=("agent_id", lambda x: ";".join(sorted(set(x.astype(str)))))
).reset_index()
agent_alias["review_flag"] = agent_alias.agent_ids.gt(1)
save(agent_alias, GOLD / "agent_identity_alias_review.csv")
agent_id_history = agents.groupby("agent_id").agg(
    historical_rows=("updated_at", "size"), employee_code_versions=("employee_code", "nunique"),
    employee_codes=("employee_code", lambda x: ";".join(sorted(set(x.dropna().astype(str)))))
).reset_index()
agent_id_history["review_flag"] = agent_id_history.employee_code_versions.gt(1)
save(agent_id_history, GOLD / "agent_identity_history_review.csv")

# --- Payments: use the already-cleaned golden payment table produced by the main pipeline. ---
payments = pd.read_csv(GOLD / "golden_payments.csv", low_memory=False)
payments["event_ts"] = pd.to_datetime(payments.get("event_ts_source", payments.get("event_at")), errors="coerce")
if "payment_status_norm" not in payments:
    payments["payment_status_norm"] = payments["payment_status"].astype(str).str.upper().str.strip()
if "gross_success_amount" not in payments:
    payments["gross_success_amount"] = np.where(
        payments.payment_status_norm.eq("SUCCESS"), pd.to_numeric(payments.amount, errors="coerce").clip(lower=0), 0
    )
payments["month"] = payments.event_ts.dt.to_period("M").astype(str)
payments["amount_num"] = pd.to_numeric(payments["amount"], errors="coerce")
success = payments[payments.payment_status_norm.eq("SUCCESS") & payments.event_ts.notna()].copy()
all_payment_month = payments[payments.event_ts.notna()].groupby("month").agg(
    payment_rows=("payment_id", "size"),
    successful_payment_events=("payment_status_norm", lambda s: int(s.eq("SUCCESS").sum())),
    failed_payment_events=("payment_status_norm", lambda s: int(s.eq("FAILED").sum())),
    pending_payment_events=("payment_status_norm", lambda s: int(s.eq("PENDING").sum())),
    reversal_events=("payment_status_norm", lambda s: int(s.eq("REVERSED").sum())),
    gross_successful_collections=("gross_success_amount", "sum"),
    reversal_amount_reported_separately=("reversal_amount" if "reversal_amount" in payments else "amount_num", "sum"),
    unique_accounts_with_success=("account_id", lambda s: s[payments.loc[s.index, "payment_status_norm"].eq("SUCCESS")].nunique()),
).reset_index()
periods = pd.PeriodIndex(all_payment_month.month, freq="M")
complete = []
for m in periods:
    ts = payments.loc[payments.month.eq(str(m)), "event_ts"]
    complete.append(bool(len(ts) and ts.max().date() >= m.end_time.date()))
all_payment_month["complete_month"] = complete
all_payment_month["metric_scope"] = "GROSS_SUCCESSFUL_PAYMENT_EVENTS_NOT_NET_RECOVERY"
all_payment_month = all_payment_month.sort_values("month")
all_payment_month["gross_cash_mom_pct"] = all_payment_month.gross_successful_collections.pct_change() * 100
# Month-over-month for an incomplete month is mechanically partial and must not be compared.
all_payment_month.loc[~all_payment_month.complete_month, "gross_cash_mom_pct"] = np.nan
save(all_payment_month, GOLD / "monthly_cash_metrics.csv")

# --- Point-in-time status reconstruction: start-of-month denominator avoids post-outcome leakage. ---
history = src["account_status_history"].copy()
history["event_ts"] = pd.to_datetime(history["event_at"], errors="coerce")
history["recorded_ts"] = pd.to_datetime(history["recorded_at"], errors="coerce")
months = [str(x) for x in pd.period_range(
    payments.event_ts.min().to_period("M"), payments.event_ts.max().to_period("M"), freq="M"
)]
account_ids = accounts[["account_id"]].drop_duplicates()
status_rows = []
start_eligible_ids: dict[str, set] = {}
end_eligible_ids: dict[str, set] = {}
start_known_ids: dict[str, set] = {}
end_known_ids: dict[str, set] = {}

for month in months:
    period = pd.Period(month, freq="M")
    start = period.start_time
    end_exclusive = period.end_time + pd.Timedelta(nanoseconds=1)
    start_status = latest_asof(history, start, strict=True).rename(columns={
        "status": "status_at_month_start", "event_ts": "status_event_ts_at_start", "recorded_ts": "status_recorded_ts_at_start"
    })
    end_status = latest_asof(history, end_exclusive, strict=False).rename(columns={
        "status": "status_at_month_end", "event_ts": "status_event_ts_at_end", "recorded_ts": "status_recorded_ts_at_end"
    })
    s = account_ids.merge(start_status, on="account_id", how="left").merge(end_status, on="account_id", how="left")
    s["month"] = month
    s["status_known_at_month_start"] = s.status_at_month_start.notna()
    s["status_known_at_month_end"] = s.status_at_month_end.notna()
    s["eligible_at_month_start"] = s.status_at_month_start.astype("string").str.upper().isin(ELIGIBLE_STATUSES)
    s["eligible_at_month_end"] = s.status_at_month_end.astype("string").str.upper().isin(ELIGIBLE_STATUSES)
    s["start_unknown_reason"] = np.where(s.status_known_at_month_start, "KNOWN", "NO_PRIOR_STATUS_KNOWN_BY_PERIOD_START")
    status_rows.append(s)
    start_eligible_ids[month] = set(s.loc[s.eligible_at_month_start, "account_id"])
    end_eligible_ids[month] = set(s.loc[s.eligible_at_month_end, "account_id"])
    start_known_ids[month] = set(s.loc[s.status_known_at_month_start, "account_id"])
    end_known_ids[month] = set(s.loc[s.status_known_at_month_end, "account_id"])

status_panel = pd.concat(status_rows, ignore_index=True)
status_panel = status_panel.merge(
    account_dim[["account_id", "borrower_id", "opened_at", "loan_type", "risk_segment", "dpd_num", "dpd_bucket", "outstanding_amount", "city", "state"]],
    on="account_id", how="left", validate="many_to_one"
)
status_panel["opened_month"] = pd.to_datetime(status_panel.opened_at, errors="coerce").dt.to_period("M").astype(str)
status_panel["dimension_timing"] = "CURRENT_SNAPSHOT_NOT_HISTORICAL"
save(status_panel, GOLD / "account_month_status_snapshot.csv")

success_by_acct_month = success.groupby(["account_id", "month"], as_index=False).agg(
    gross_cash=("gross_success_amount", "sum"), successful_payment_events=("payment_id", "count")
)
status_panel = status_panel.merge(success_by_acct_month, on=["account_id", "month"], how="left")
status_panel[["gross_cash", "successful_payment_events"]] = status_panel[["gross_cash", "successful_payment_events"]].fillna(0)

# Golden account-month panel is the population eligible at the *start* of the month.
# January is intentionally empty because no status history is known before 1 Jan 2026.
panel = status_panel[status_panel.eligible_at_month_start].copy()
panel["denominator_basis"] = "LAST_STATUS_EVENT_EFFECTIVE_AND_RECORDED_BEFORE_MONTH_START"
panel["cash_measure"] = "GROSS_SUCCESSFUL_CASH; NOT_NET_RECOVERY"
save(panel, GOLD / "account_month_recovery_panel.csv")

monthly_status_metrics = []
for month in months:
    s = status_panel[status_panel.month.eq(month)]
    st_eligible = s[s.eligible_at_month_start]
    en_eligible = s[s.eligible_at_month_end]
    month_success = success[success.month.eq(month)]
    start_ids = start_eligible_ids[month]
    end_ids = end_eligible_ids[month]
    eligible_success = month_success[month_success.account_id.isin(start_ids)]
    end_eligible_success = month_success[month_success.account_id.isin(end_ids)]
    cash_total = float(month_success.gross_success_amount.sum())
    cash_start = float(eligible_success.gross_success_amount.sum())
    cash_end = float(end_eligible_success.gross_success_amount.sum())
    start_paid = int(eligible_success.account_id.nunique())
    known_n = int(s.status_known_at_month_start.sum())
    known_end_n = int(s.status_known_at_month_end.sum())
    n_accounts = int(len(s))
    month_complete = bool(all_payment_month.loc[all_payment_month.month.eq(month), "complete_month"].iloc[0])
    monthly_status_metrics.append({
        "month": month,
        "accounts_in_source_snapshot": n_accounts,
        "accounts_with_status_known_at_start": known_n,
        "start_status_coverage_pct": 100 * known_n / n_accounts if n_accounts else np.nan,
        "eligible_accounts_at_month_start": int(st_eligible.account_id.nunique()),
        "accounts_with_status_known_at_end": known_end_n,
        "end_status_coverage_pct": 100 * known_end_n / n_accounts if n_accounts else np.nan,
        "eligible_accounts_at_month_end": int(en_eligible.account_id.nunique()),
        "gross_successful_cash_all_accounts": cash_total,
        "gross_successful_cash_from_start_eligible_accounts": cash_start,
        "gross_successful_cash_from_end_eligible_accounts": cash_end,
        "cash_capture_share_start_eligible_pct": 100 * cash_start / cash_total if cash_total else np.nan,
        "cash_capture_share_end_eligible_pct": 100 * cash_end / cash_total if cash_total else np.nan,
        "paying_accounts_in_start_eligible_population": start_paid,
        "gross_cash_per_start_eligible_account": cash_start / st_eligible.account_id.nunique() if st_eligible.account_id.nunique() else np.nan,
        "paying_account_share_start_eligible": start_paid / st_eligible.account_id.nunique() if st_eligible.account_id.nunique() else np.nan,
        "start_eligible_became_noneligible_by_month_end": int((s.eligible_at_month_start & ~s.eligible_at_month_end).sum()),
        "start_eligible_status_changed_to_paid_closed_or_writeoff": int((s.eligible_at_month_start & s.status_at_month_end.astype("string").str.upper().isin(["PAID", "CLOSED", "WRITEOFF"])).sum()),
        "gross_cash_from_start_eligible_now_noneligible": float(month_success[month_success.account_id.isin(start_ids - end_ids)].gross_success_amount.sum()),
        "complete_month": month_complete,
        "denominator_warning": "OBSERVED STATUS-HISTORY SUBPOPULATION ONLY; UNKNOWN START STATUS EXCLUDED; NO HISTORICAL EXPOSURE",
    })
monthly_status_metrics = pd.DataFrame(monthly_status_metrics)
monthly_status_metrics = monthly_status_metrics.merge(
    all_payment_month[["month", "payment_rows", "successful_payment_events", "reversal_events", "reversal_amount_reported_separately", "gross_cash_mom_pct"]],
    on="month", how="left"
)
save(monthly_status_metrics, GOLD / "monthly_eligible_account_metrics.csv")

trend = monthly_status_metrics[[
    "month", "gross_successful_cash_all_accounts", "gross_cash_mom_pct", "eligible_accounts_at_month_start",
    "start_status_coverage_pct", "gross_successful_cash_from_start_eligible_accounts",
    "gross_cash_per_start_eligible_account", "paying_account_share_start_eligible", "complete_month"
]].copy()
trend["cash_per_start_eligible_mom_pct"] = trend.gross_cash_per_start_eligible_account.pct_change() * 100
trend.loc[~trend.complete_month, "cash_per_start_eligible_mom_pct"] = np.nan
trend["interpretation"] = "CASH-EVENT TREND; DENOMINATOR IS OBSERVED PRIOR-STATUS SUBPOPULATION"
save(trend, GOLD / "monthly_trend_analysis.csv")

# A direct diagnostic for month-end survivorship leakage and historical denominator coverage.
survivorship = monthly_status_metrics[[
    "month", "accounts_in_source_snapshot", "accounts_with_status_known_at_start", "start_status_coverage_pct",
    "eligible_accounts_at_month_start", "eligible_accounts_at_month_end",
    "start_eligible_became_noneligible_by_month_end", "start_eligible_status_changed_to_paid_closed_or_writeoff",
    "gross_successful_cash_all_accounts", "gross_successful_cash_from_start_eligible_accounts",
    "gross_successful_cash_from_end_eligible_accounts", "gross_cash_from_start_eligible_now_noneligible",
    "cash_capture_share_start_eligible_pct", "cash_capture_share_end_eligible_pct"
]].copy()
survivorship["interpretation"] = "MONTH-END STATUS IS POST-OUTCOME; START-OF-MONTH IS THE CORRECT TEMPORAL ORDER BUT OBSERVED STATUS COVERAGE IS INCOMPLETE"
save(survivorship, GOLD / "denominator_survivorship_diagnostics.csv")

# Risk/DPD/loan mix standardization proxy: February is the first month with a valid start snapshot.
seg_rows = []
for dim in ["risk_segment", "loan_type", "dpd_bucket", "state"]:
    by = panel.groupby(["month", dim], dropna=False).agg(
        eligible_accounts=("account_id", "nunique"), gross_cash=("gross_cash", "sum"),
        paying_accounts=("gross_cash", lambda x: int((x > 0).sum()))
    ).reset_index()
    by["gross_cash_per_eligible"] = by.gross_cash / by.eligible_accounts.replace(0, np.nan)
    by["attribute_timing"] = "CURRENT SNAPSHOT; DESCRIPTIVE ONLY"
    save(by, GOLD / f"portfolio_mix_by_{dim}.csv")

reference_month = next((m for m in months if len(start_eligible_ids[m]) > 0), None)
if reference_month:
    ref = panel[panel.month.eq(reference_month)].groupby("risk_segment").account_id.nunique()
    ref_weights = ref / ref.sum()
    mix_rows = []
    for month, g in panel.groupby("month"):
        seg = g.groupby("risk_segment").agg(cash=("gross_cash", "sum"), eligible=("account_id", "nunique"))
        seg["cash_per_eligible"] = seg.cash / seg.eligible.replace(0, np.nan)
        common = ref_weights.index.intersection(seg.index[seg.cash_per_eligible.notna()])
        weighted = float((seg.loc[common, "cash_per_eligible"] * ref_weights.loc[common]).sum()) if len(common) else np.nan
        mix_rows.append({
            "month": month,
            "observed_gross_cash_per_start_eligible": float(g.gross_cash.sum() / g.account_id.nunique()),
            "fixed_reference_risk_mix_cash_per_start_eligible_proxy": weighted,
            "reference_month": reference_month,
            "reference_mix": "FIRST_MONTH_WITH_OBSERVED_START_STATUS",
            "limitation": "CURRENT RISK ATTRIBUTES; OBSERVED SUBPOPULATION; NOT AN EXPOSURE-WEIGHTED RECOVERY RATE",
        })
    save(pd.DataFrame(mix_rows), GOLD / "mix_adjusted_recovery_proxy.csv")

# Simpson's-paradox / within-segment direction diagnostic. This is a screen, not a causal
# decomposition: dimensions are current snapshots, and the denominator is the observed
# month-start account-count subpopulation. It deliberately avoids asserting a true reversal.
simpson_segment_rows = []
simpson_pair_rows = []
for dim in ["risk_segment", "dpd_bucket", "loan_type", "state"]:
    grouped = panel.groupby(["month", dim], dropna=False).agg(
        eligible_accounts=("account_id", "nunique"), gross_cash=("gross_cash", "sum")
    ).reset_index()
    grouped["gross_cash_per_eligible"] = grouped.gross_cash / grouped.eligible_accounts.replace(0, np.nan)
    available_months = sorted(grouped.month.dropna().unique())
    for prev_month, curr_month in zip(available_months[:-1], available_months[1:]):
        prev = grouped[grouped.month.eq(prev_month)].set_index(dim)
        curr = grouped[grouped.month.eq(curr_month)].set_index(dim)
        common = prev.index.intersection(curr.index)
        if len(common) == 0:
            continue
        changes = []
        for segment in common:
            before = prev.loc[segment, "gross_cash_per_eligible"]
            after = curr.loc[segment, "gross_cash_per_eligible"]
            if pd.isna(before) or before == 0 or pd.isna(after):
                continue
            pct = (float(after) / float(before) - 1) * 100
            changes.append(pct)
            simpson_segment_rows.append({
                "dimension": dim, "segment": str(segment), "previous_month": prev_month,
                "current_month": curr_month, "previous_gross_cash_per_eligible": float(before),
                "current_gross_cash_per_eligible": float(after), "segment_change_pct": pct,
                "attribute_timing": "CURRENT_SNAPSHOT_NOT_HISTORICAL",
                "denominator": "OBSERVED_MONTH_START_ELIGIBLE_ACCOUNT_COUNT",
            })
        prev_total = monthly_status_metrics.loc[monthly_status_metrics.month.eq(prev_month), "gross_cash_per_start_eligible_account"]
        curr_total = monthly_status_metrics.loc[monthly_status_metrics.month.eq(curr_month), "gross_cash_per_start_eligible_account"]
        if prev_total.empty or curr_total.empty or pd.isna(prev_total.iloc[0]) or prev_total.iloc[0] == 0 or pd.isna(curr_total.iloc[0]):
            aggregate_pct = np.nan
        else:
            aggregate_pct = (float(curr_total.iloc[0]) / float(prev_total.iloc[0]) - 1) * 100
        up = sum(x > 0 for x in changes)
        down = sum(x < 0 for x in changes)
        if not changes:
            classification = "INSUFFICIENT_COMMON_SEGMENTS"
        elif aggregate_pct > 0 and down == len(changes):
            classification = "STRICT_REVERSAL_SCREEN_FLAG"
        elif aggregate_pct > 0 and down > up:
            classification = "AGGREGATE_UP_MAJORITY_SEGMENTS_DOWN"
        elif aggregate_pct < 0 and up > down:
            classification = "AGGREGATE_DOWN_MAJORITY_SEGMENTS_UP"
        else:
            classification = "NO_STRICT_REVERSAL_DETECTED"
        simpson_pair_rows.append({
            "dimension": dim, "previous_month": prev_month, "current_month": curr_month,
            "aggregate_cash_per_eligible_change_pct": aggregate_pct, "common_segments": len(changes),
            "segments_up": up, "segments_down": down, "classification": classification,
            "limitation": "SCREEN ONLY; CURRENT SNAPSHOT ATTRIBUTES AND INCOMPLETE OBSERVED DENOMINATOR; NOT A CAUSAL OR HISTORICAL MIX DECOMPOSITION",
        })
simpson_segments = pd.DataFrame(simpson_segment_rows)
simpson_pairs = pd.DataFrame(simpson_pair_rows)
save(simpson_segments, GOLD / "simpsons_paradox_segment_diagnostics.csv")
save(simpson_pairs, GOLD / "simpsons_paradox_pair_summary.csv")

# Account vintage cohort outcome using the same start-of-month observed eligible population.
cohort = panel.copy()
cohort["cohort_month"] = pd.to_datetime(cohort.opened_at, errors="coerce").dt.to_period("M").astype(str)
cohort = cohort.groupby(["cohort_month", "month"]).agg(
    eligible_accounts=("account_id", "nunique"), gross_cash=("gross_cash", "sum"),
    paying_accounts=("gross_cash", lambda x: int((x > 0).sum()))
).reset_index()
cohort["gross_cash_per_eligible"] = cohort.gross_cash / cohort.eligible_accounts.replace(0, np.nan)
cohort["limitation"] = "START-STATUS OBSERVED SUBPOPULATION; CURRENT SNAPSHOT COHORT LABEL"
save(cohort, GOLD / "account_vintage_cohorts.csv")

# Account-level bootstrap uncertainty for descriptive cash per observed eligible account.
rng = np.random.default_rng(42)
boot = []
for month in months:
    vals = panel.loc[panel.month.eq(month), "gross_cash"].to_numpy(float)
    if len(vals) == 0:
        boot.append({"month": month, "mean_cash_per_eligible": np.nan, "ci_2_5": np.nan, "ci_97_5": np.nan,
                     "n_eligible": 0, "method": "Not estimable: no pre-period status snapshot"})
        continue
    draws = np.array([rng.choice(vals, size=len(vals), replace=True).mean() for _ in range(500)])
    boot.append({"month": month, "mean_cash_per_eligible": float(vals.mean()),
                 "ci_2_5": float(np.quantile(draws, .025)), "ci_97_5": float(np.quantile(draws, .975)),
                 "n_eligible": len(vals), "method": "500 account-level bootstrap resamples; descriptive only"})
save(pd.DataFrame(boot), GOLD / "monthly_cash_bootstrap_ci.csv")

# --- Calls, attempts, agent tenure, calling-time and telephony vendor. ---
calls = src["calls"].copy()
calls["event_ts"] = pd.to_datetime(calls.event_at, errors="coerce")
calls["month"] = calls.event_ts.dt.to_period("M").astype(str)
calls["source_recorded_hour"] = calls.event_ts.dt.hour
calls["call_status_norm"] = calls.call_status.astype(str).str.upper().str.strip()
save(calls, GOLD / "golden_calls.csv")
call_vendor = src["vendor_telephony"][["vendor_id", "vendor_name", "timezone", "status", "schema_version"]].drop_duplicates("vendor_id")
calls = calls.merge(call_vendor, on="vendor_id", how="left", suffixes=("_call", "_vendor"), validate="many_to_one")

call_month = calls.groupby("month").agg(
    calls=("call_id", "count"), accounts=("account_id", "nunique"),
    answered_technical=("call_status_norm", lambda s: int(s.eq("ANSWERED").sum())),
    mean_duration_sec=("duration_sec", "mean"),
).reset_index()
call_month["technical_answer_share"] = call_month.answered_technical / call_month.calls.replace(0, np.nan)
call_month["metric_warning"] = "ANSWERED IS A TELEPHONY STATUS; NOT CONTACT OR RPC"
save(call_month, GOLD / "monthly_calls_operations.csv")

hour = calls.groupby(["timezone_call" if "timezone_call" in calls else "timezone", "source_recorded_hour", "call_status_norm"], dropna=False).agg(
    calls=("call_id", "count"), accounts=("account_id", "nunique")
).reset_index()
hour["timezone_warning"] = "EVENT_AT HOUR AS STORED; TIMEZONE SEMANTICS NOT CERTIFIED; NOT A BORROWER-LOCAL HOUR"
save(hour, GOLD / "call_hour_performance.csv")

vendor_calls = calls.groupby(["month", "vendor_id", "vendor_name", "schema_version", "timezone_vendor" if "timezone_vendor" in calls else "timezone"], dropna=False).agg(
    calls=("call_id", "count"), accounts=("account_id", "nunique"),
    answered_technical=("call_status_norm", lambda s: int(s.eq("ANSWERED").sum())),
    mean_duration_sec=("duration_sec", "mean")
).reset_index()
vendor_calls["technical_answer_share"] = vendor_calls.answered_technical / vendor_calls.calls.replace(0, np.nan)
vendor_calls["limitation"] = "NO RPC MAP; TECHNICAL ANSWER SHARE ONLY"
save(vendor_calls, GOLD / "vendor_call_performance.csv")

attempts = src["call_attempts"].copy()
attempts["event_ts"] = pd.to_datetime(attempts.event_at, errors="coerce")
attempts["month"] = attempts.event_ts.dt.to_period("M").astype(str)
attempts["attempt_status_norm"] = attempts.attempt_status.astype(str).str.upper().str.strip()
conflict_call_ids = event_conflict_ids.get("calls", set())
valid_call_ids = set(calls.call_id.dropna())
attempts["parent_call_resolution"] = np.select(
    [attempts.call_id.isin(conflict_call_ids), attempts.call_id.isin(valid_call_ids)],
    ["CONFLICTING_CALL_ID_QUARANTINED", "MATCHED_TO_UNAMBIGUOUS_CALL"], default="NO_CALL_PARENT_MATCH"
)
attempts["parent_call_warning"] = "ATTEMPT EVENT REMAINS VALID; PARENT LINK STATUS IS DIAGNOSTIC"
save(attempts, GOLD / "golden_call_attempts.csv")
parent_diag = attempts.groupby(["month", "parent_call_resolution"]).agg(attempts=("attempt_id", "count"), accounts=("account_id", "nunique")).reset_index()
save(parent_diag, GOLD / "attempt_parent_resolution.csv")
attempt_month = attempts.groupby("month").agg(
    attempts=("attempt_id", "count"), accounts=("account_id", "nunique")
).reset_index()
save(attempt_month, GOLD / "monthly_call_attempts_operations.csv")

acct_attempts = attempts.groupby(["account_id", "month"]).agg(
    attempt_count=("attempt_id", "nunique"), attempt_no_max=("attempt_no", "max"), attempt_status_variety=("attempt_status_norm", "nunique")
).reset_index()
acct_attempts["attempt_frequency_band"] = pd.cut(
    acct_attempts.attempt_count, [-1, 0, 1, 2, 5, 10, 100000],
    labels=["0", "1", "2", "3-5", "6-10", "11+"],
).astype(str)
acct_attempts = panel[["account_id", "month", "gross_cash", "risk_segment", "dpd_bucket"]].merge(
    acct_attempts, on=["account_id", "month"], how="left"
)
acct_attempts["attempt_count"] = acct_attempts.attempt_count.fillna(0).astype(int)
acct_attempts["attempt_frequency_band"] = acct_attempts.attempt_frequency_band.fillna("0")
frequency = acct_attempts.groupby(["month", "attempt_frequency_band"]).agg(
    eligible_accounts=("account_id", "nunique"), paying_accounts=("gross_cash", lambda x: int((x > 0).sum())),
    gross_cash=("gross_cash", "sum"), mean_cash_per_eligible=("gross_cash", "mean")
).reset_index()
frequency["interpretation"] = "DESCRIPTIVE ASSOCIATION; ATTEMPTS ARE NOT RANDOMIZED"
save(frequency, GOLD / "attempt_frequency_outcomes.csv")

attempt_no = attempts.groupby(["month", "attempt_no", "attempt_status_norm"]).agg(
    attempt_events=("attempt_id", "count"), accounts=("account_id", "nunique")
).reset_index()
save(attempt_no, GOLD / "attempt_no_status_distribution.csv")

agent_calls = calls.merge(
    agent_snapshot[["agent_id", "employee_code", "joined_at", "team", "vendor_id"]].rename(columns={"vendor_id": "agent_vendor_id"}),
    on="agent_id", how="left", suffixes=("", "_agent"), validate="many_to_one"
)
agent_calls["tenure_days_at_event"] = (
    agent_calls.event_ts - pd.to_datetime(agent_calls.joined_at, errors="coerce")
).dt.days
agent_calls["tenure_band"] = pd.cut(
    agent_calls.tenure_days_at_event, [-1, 30, 90, 180, 365, 100000],
    labels=["0-30d", "31-90d", "91-180d", "181-365d", "365d+"],
).astype("string").fillna("Unknown")
agent_tenure = agent_calls.groupby(["month", "tenure_band"]).agg(
    calls=("call_id", "count"), answered_technical=("call_status_norm", lambda s: int(s.eq("ANSWERED").sum())),
    accounts=("account_id", "nunique"), mean_duration_sec=("duration_sec", "mean")
).reset_index()
agent_tenure["technical_answer_share"] = agent_tenure.answered_technical / agent_tenure.calls.replace(0, np.nan)
agent_tenure["limitation"] = "CALL ACTIVITY ONLY; PAYMENTS NOT ATTRIBUTED TO AGENTS; ANSWERED IS NOT RPC"
save(agent_tenure, GOLD / "agent_tenure_performance.csv")
agent_perf = agent_calls.groupby(["month", "agent_id", "employee_code", "team", "tenure_band"]).agg(
    calls=("call_id", "count"), answered_technical=("call_status_norm", lambda s: int(s.eq("ANSWERED").sum())),
    accounts=("account_id", "nunique"), mean_duration_sec=("duration_sec", "mean")
).reset_index()
agent_perf["technical_answer_share"] = agent_perf.answered_technical / agent_perf.calls.replace(0, np.nan)
agent_perf["limitation"] = "NOT RECOVERY PER AGENT; PAYMENT/AGENT ATTRIBUTION AND PRODUCTIVE HOURS ABSENT"
save(agent_perf, GOLD / "agent_performance_descriptive.csv")

attempt_vendor = attempts.groupby(["month", "vendor_id", "attempt_status_norm"]).agg(
    attempts=("attempt_id", "count"), accounts=("account_id", "nunique")
).reset_index()
save(attempt_vendor, GOLD / "vendor_attempt_status_distribution.csv")

# Vendor disposition distributions: can reveal changed code mix but does not certify semantic mappings.
disp = src["call_dispositions"].copy()
disp = disp.merge(calls[["call_id", "vendor_id", "schema_version"]].drop_duplicates("call_id"),
                  on="call_id", how="left", validate="many_to_one")
disp["disposition_code_norm"] = disp.disposition_code.astype(str).str.upper().str.strip()
vdisp = disp.groupby(["schema_version", "disposition_version", "disposition_code_norm"]).agg(
    disposition_rows=("disposition_id", "count"), accounts=("account_id", "nunique")
).reset_index()
vdisp["mapping_status"] = "VERSIONED FREQUENCY ONLY; NO AUTHORITATIVE SEMANTIC MAP"
save(vdisp, GOLD / "vendor_disposition_code_distribution.csv")

# --- Campaigns, channel events, complaints and PTP. ---
campaigns = src["campaigns"].drop_duplicates("campaign_id").copy()
save(campaigns, GOLD / "golden_campaigns_snapshot.csv")
targeting = src["daily_targeting"].copy()
targeting["event_ts"] = pd.to_datetime(targeting.target_date, errors="coerce")
targeting["month"] = targeting.event_ts.dt.to_period("M").astype(str)
targeting = targeting.merge(campaigns[["campaign_id", "campaign_name", "channel", "strategy_version", "target_definition"]],
                            on="campaign_id", how="left", validate="many_to_one")

calls_campaign = calls.merge(
    campaigns[["campaign_id", "campaign_name", "channel", "strategy_version"]],
    on="campaign_id", how="left", validate="many_to_one", suffixes=("", "_campaign")
)
campaign_calls = calls_campaign.groupby(["month", "campaign_id", "campaign_name", "channel", "strategy_version"], dropna=False).agg(
    call_events=("call_id", "count"), called_accounts=("account_id", "nunique"),
    answered_technical=("call_status_norm", lambda s: int(s.eq("ANSWERED").sum()))
).reset_index()
campaign_calls["technical_answer_share"] = campaign_calls.answered_technical / campaign_calls.call_events.replace(0, np.nan)
campaign_calls["limitation"] = "CAMPAIGN ACTIVITY ONLY; CASH IS NOT CAUSALLY ATTRIBUTED"
save(campaign_calls, GOLD / "campaign_call_performance.csv")

# Cash per targeted account-month is a non-exclusive observational join; not incrementality.
tgt_acct = targeting.groupby(["account_id", "month", "strategy_version", "channel"], dropna=False).agg(
    target_events=("target_id", "count"), campaigns=("campaign_id", "nunique"),
    target_statuses=("status", lambda x: ";".join(sorted(set(x.dropna().astype(str)))))
).reset_index()
strat_cash = tgt_acct.merge(success_by_acct_month, on=["account_id", "month"], how="left")
strat_cash["gross_cash"] = strat_cash.gross_cash.fillna(0)
strategy = strat_cash.groupby(["month", "strategy_version", "channel"], dropna=False).agg(
    targeted_account_strategy_months=("account_id", "nunique"), target_events=("target_events", "sum"),
    paying_account_strategy_months=("gross_cash", lambda x: int((x > 0).sum())),
    gross_cash=("gross_cash", "sum"), mean_cash_per_targeted_account_month=("gross_cash", "mean")
).reset_index()
strategy["interpretation"] = "DESCRIPTIVE ONLY; NON-RANDOMIZED; MULTIPLE STRATEGIES/CHANNELS MAY OVERLAP; CASH MAY PRECEDE TARGET"
save(strategy, GOLD / "targeting_strategy_outcomes_descriptive.csv")

# Single operational event table for activity, never payment attribution.
channel_rows = []
for table, channel, id_col, event_col in [
    ("calls", "VOICE", "call_id", "call_status"),
    ("whatsapp_events", "WHATSAPP", "whatsapp_event_id", "event_type"),
    ("sms_events", "SMS", "sms_event_id", "event_type"),
    ("field_visits", "FIELD", "visit_id", "outcome"),
]:
    df = src[table].copy()
    df["event_ts"] = pd.to_datetime(df.event_at, errors="coerce")
    df["month"] = df.event_ts.dt.to_period("M").astype(str)
    counts = df.groupby(["month", event_col]).agg(events=(id_col, "count"), accounts=("account_id", "nunique")).reset_index()
    counts = counts.rename(columns={event_col: "event_outcome"})
    counts["channel"] = channel
    counts["source_table"] = table
    counts["interpretation"] = "EVENT VOLUME/STATUS ONLY; NO CAUSAL PAYMENT ATTRIBUTION"
    channel_rows.append(counts)
channel_activity = pd.concat(channel_rows, ignore_index=True)
save(channel_activity, GOLD / "channel_activity_monthly.csv")

# Per-channel monthly summary for executive overview.
channel_summary = channel_activity.groupby(["month", "channel"]).agg(
    events=("events", "sum"), unique_account_event_groups=("accounts", "sum")
).reset_index()
channel_summary["limitation"] = "ACCOUNTS ARE SUMMED OVER EVENT OUTCOMES; NOT A DEDUPLICATED CHANNEL REACH DENOMINATOR"
save(channel_summary, GOLD / "channel_summary_monthly.csv")

# PTP: mature status labels are separately disclosed; payments lack ptp_id so no verified kept match.
ptp = src["promises_to_pay"].copy()
ptp["event_ts"] = pd.to_datetime(ptp.event_at, errors="coerce")
ptp["month"] = ptp.event_ts.dt.to_period("M").astype(str)
ptp["promised_ts"] = pd.to_datetime(ptp.promised_date, errors="coerce")
ptp["status_norm"] = ptp.status.astype(str).str.upper().str.strip()
ptp["matured_by_cutoff"] = ptp.promised_ts.le(AS_OF_CUTOFF)
ptp_rows = []
for month, g in ptp.groupby("month"):
    matured = g[g.matured_by_cutoff]
    closed = matured[matured.status_norm.isin(["KEPT", "BROKEN"])]
    ptp_rows.append({
        "month": month, "ptp_rows": len(g), "ptp_accounts": g.account_id.nunique(),
        "matured_by_dataset_cutoff": len(matured), "matured_kept_status": int(matured.status_norm.eq("KEPT").sum()),
        "matured_broken_status": int(matured.status_norm.eq("BROKEN").sum()),
        "matured_cancelled_status": int(matured.status_norm.eq("CANCELLED").sum()),
        "matured_open_status": int(matured.status_norm.eq("OPEN").sum()),
        "source_status_kept_share_closed_matured": (int(closed.status_norm.eq("KEPT").sum()) / len(closed)) if len(closed) else np.nan,
        "limitation": "SOURCE LABEL AMONG MATURED KEPT/BROKEN ONLY; NOT MATCHED TO SETTLED PAYMENTS; NO PTP_ID IN PAYMENTS",
    })
save(pd.DataFrame(ptp_rows), GOLD / "monthly_ptp_diagnostics.csv")

# Disposition code/version counts. No candidate RPC or contact rate is certified.
disp_summary = src["call_dispositions"].copy()
disp_summary["parent_call_resolution"] = np.select(
    [disp_summary.call_id.isin(event_conflict_ids.get("calls", set())), disp_summary.call_id.isin(set(calls.call_id.dropna()))],
    ["CONFLICTING_CALL_ID_QUARANTINED", "MATCHED_TO_UNAMBIGUOUS_CALL"], default="NO_CALL_PARENT_MATCH"
)
save(disp_summary, GOLD / "golden_call_dispositions.csv")
disp_summary["month"] = month_str(disp_summary.event_at)
disp_summary["code_norm"] = disp_summary.disposition_code.astype(str).str.upper().str.strip()
disposition = disp_summary.groupby(["month", "disposition_version", "code_norm"]).agg(
    rows=("disposition_id", "count"), accounts=("account_id", "nunique")
).reset_index()
disposition["rpc_status"] = "UNMAPPED — DO NOT USE AS RPC"
save(disposition, GOLD / "disposition_version_diagnostics.csv")

complaints = src["complaints"].copy()
save(complaints, GOLD / "golden_complaints.csv")
complaints["month"] = month_str(complaints.event_at)
complaint_summary = complaints.groupby(["month", "source", "complaint_type", "severity", "status"], dropna=False).agg(
    complaints=("complaint_id", "count"), accounts=("account_id", "nunique")
).reset_index()
save(complaint_summary, GOLD / "complaint_diagnostics.csv")

# --- Payment-to-touch candidate windows: count candidates, never select a last touch. ---
# Avoid a full many-to-many payment x interaction merge. Per-account sorted event arrays
# let us count 7-day windows in O((P + T) log T) work without materializing a huge join.
touches = []
for table, channel, event_id in [
    ("calls", "VOICE", "call_id"), ("whatsapp_events", "WHATSAPP", "whatsapp_event_id"),
    ("sms_events", "SMS", "sms_event_id"), ("field_visits", "FIELD", "visit_id")
]:
    d = src[table][["account_id", "event_at", event_id]].copy()
    d["touch_ts"] = pd.to_datetime(d.event_at, errors="coerce")
    d = d[d.touch_ts.notna()][["account_id", "touch_ts"]]
    d["channel"] = channel
    touches.append(d)
touch_df = pd.concat(touches, ignore_index=True)
touch_index: dict[str, tuple[np.ndarray, np.ndarray]] = {}
for account_id, g in touch_df.groupby("account_id", sort=False):
    g = g.sort_values("touch_ts")
    touch_index[str(account_id)] = (
        g.touch_ts.to_numpy(dtype="datetime64[ns]"),
        g.channel.to_numpy(dtype=object),
    )

payment_touch_rows = []
window_days_set = (1, 7, 30)
for row in success[["payment_id", "account_id", "event_ts", "gross_success_amount", "month"]].itertuples(index=False):
    key = str(row.account_id)
    times, channels = touch_index.get(key, (np.array([], dtype="datetime64[ns]"), np.array([], dtype=object)))
    pay_ts = np.datetime64(row.event_ts.to_datetime64(), "ns")
    right = int(np.searchsorted(times, pay_ts, side="left"))  # strictly preceding, not simultaneous
    result = {
        "payment_id": row.payment_id, "account_id": row.account_id, "month": row.month,
        "gross_success_amount": row.gross_success_amount,
        "attribution_status": "CANDIDATE WINDOW ONLY; NO CAUSAL OR LAST-TOUCH CREDIT",
    }
    for window_days in window_days_set:
        left = int(np.searchsorted(times, pay_ts - np.timedelta64(window_days, "D"), side="left"))
        window_channels = channels[left:right]
        result[f"candidate_touches_prior_{window_days}d"] = int(right-left)
        result[f"candidate_channel_count_prior_{window_days}d"] = len(set(window_channels.tolist()))
        if window_days == 7:
            unique_channels = sorted(set(window_channels.tolist()))
            result["candidate_channels_prior_7d"] = ";".join(unique_channels)
            result["voice_candidate_touches_prior_7d"] = int(np.count_nonzero(window_channels == "VOICE"))
            result["whatsapp_candidate_touches_prior_7d"] = int(np.count_nonzero(window_channels == "WHATSAPP"))
            result["sms_candidate_touches_prior_7d"] = int(np.count_nonzero(window_channels == "SMS"))
            result["field_candidate_touches_prior_7d"] = int(np.count_nonzero(window_channels == "FIELD"))
    payment_touch_rows.append(result)
payment_touch = pd.DataFrame(payment_touch_rows)
save(payment_touch, GOLD / "payment_touch_candidate_diagnostics.csv")

# Show how arbitrary look-back length changes apparent touch coverage. These are
# nested candidate windows, not evidence that a touch caused or received payment credit.
window_sensitivity_rows = []
for scope_month, scope in [(m, g) for m, g in payment_touch.groupby("month")] + [("ALL", payment_touch)]:
    for window_days in window_days_set:
        count_col = f"candidate_touches_prior_{window_days}d"
        touched = scope[count_col].gt(0)
        cash_total = float(scope.gross_success_amount.sum())
        cash_with_touch = float(scope.loc[touched, "gross_success_amount"].sum())
        window_sensitivity_rows.append({
            "month": scope_month, "window_days": window_days,
            "successful_payment_events": int(len(scope)),
            "payments_with_any_candidate_touch": int(touched.sum()),
            "share_payments_with_candidate_touch_pct": float(touched.mean() * 100) if len(scope) else np.nan,
            "candidate_touch_events": int(scope[count_col].sum()),
            "gross_successful_cash": cash_total,
            "gross_cash_on_payments_with_candidate_touch": cash_with_touch,
            "share_gross_cash_on_payments_with_candidate_touch_pct": (cash_with_touch / cash_total * 100) if cash_total else np.nan,
            "accounts_with_any_candidate_touch": int(scope.loc[touched, "account_id"].nunique()),
            "interpretation": "LOOK-BACK SENSITIVITY ONLY; MULTIPLE TOUCHES/CHANNELS CAN OVERLAP; NO PAYMENT ATTRIBUTION",
        })
window_sensitivity = pd.DataFrame(window_sensitivity_rows)
save(window_sensitivity, GOLD / "payment_touch_window_sensitivity.csv")
payment_touch["candidate_touch_band"] = pd.cut(
    payment_touch.candidate_touches_prior_7d, [-1, 0, 1, 5, 100000], labels=["0", "1", "2-5", "6+"],
).astype(str)
touch_summary = payment_touch.groupby(["month", "candidate_touch_band"]).agg(
    successful_payments=("payment_id", "count"), accounts=("account_id", "nunique"),
    gross_successful_cash=("gross_success_amount", "sum")
).reset_index()
touch_summary["limitation"] = "7-DAY PRECEDING ACCOUNT-LEVEL CANDIDATE WINDOW; DOES NOT PROVE INFLUENCE"
save(touch_summary, GOLD / "payment_touch_candidate_summary.csv")

# --- Geography and current portfolio segment cuts, not historical attributes. ---
pay_geo = success.merge(accounts[["account_id", "loan_type", "risk_segment", "dpd_bucket", "outstanding_amount"]],
                         on="account_id", how="left", validate="many_to_one")
pay_geo = pay_geo.merge(account_dim[["account_id", "city", "state"]], on="account_id", how="left", validate="many_to_one")
for dim in ["state", "city", "loan_type", "risk_segment", "dpd_bucket"]:
    out = pay_geo.groupby(["month", dim], dropna=False).agg(
        gross_successful_cash=("gross_success_amount", "sum"), successful_events=("payment_id", "count"),
        paying_accounts=("account_id", "nunique")
    ).reset_index()
    out["attribute_timing"] = "CURRENT SNAPSHOT; DESCRIPTIVE ONLY"
    save(out, GOLD / f"recovery_by_{dim}.csv")

# --- Reconciliation flow: raw -> removed/quarantined/superseded -> golden. ---
flow_rows = []
for name in source_names:
    raw_n = len(raw[name])
    dedup_n = len(raw[name].drop_duplicates())
    clean_n = len(src[name])
    exact_removed = raw_n - dedup_n
    quarantined = 0
    superseded = 0
    golden_n = clean_n
    if name == "payments":
        q = pd.read_csv(QUAR / "payment_id_conflicts.csv", low_memory=False)
        quarantined = len(q)
        golden_n = len(payments)
    elif name in event_conflict_ids:
        quarantined = len(event_conflicts[event_conflicts.source_table.eq(name)])
        golden_n = len(src[name])
    elif name == "borrowers":
        quarantined = len(borrower_superseded)
        superseded = len(borrower_superseded)
        golden_n = len(borrower_snapshot)
    elif name == "agents":
        superseded = len(agents) - len(agent_snapshot)
        golden_n = len(agent_snapshot)
    elif name == "accounts":
        golden_n = len(accounts)
    elif name == "account_status_history":
        golden_n = len(src[name])  # retained as full event history; point-in-time snapshots are separate.
    flow_rows.append({
        "source": name, "raw_rows": raw_n, "exact_duplicate_rows_removed": exact_removed,
        "rows_after_exact_dedup": dedup_n, "conflicting_rows_quarantined": quarantined,
        "historical_rows_superseded_in_current_dimension": superseded, "golden_or_clean_rows": golden_n,
        "treatment_note": {
            "payments": "Exact duplicates removed; conflicting payment_id payloads quarantined in full",
            "borrowers": "Latest updated_at used for current dimension; older versions quarantined, history retained",
            "agents": "Latest updated_at per agent_id used for current dimension; prior versions retained for audit",
            "account_status_history": "All events retained; bitemporal start/end snapshots rebuilt from event_at and recorded_at",
        }.get(name, "Exact full-row dedup only; source values otherwise retained"),
    })
reconciliation_flow = pd.DataFrame(flow_rows)
save(reconciliation_flow, REPORTS / "reconciliation_flow.csv")

# Data-quality findings: merge existing broad findings with newly measured defects/risks.
findings = []
existing_path = REPORTS / "forensic_findings.csv"
if existing_path.exists():
    old_findings = pd.read_csv(existing_path).to_dict("records")
else:
    old_findings = []
# Keep already measured issues, but replace incorrect/ambiguous metrics below.
replace_issues = {
    "Agent employee-code aliases", "Agent session overlap/invalid duration", "Historical status denominator leakage",
    "Agent dimension version inflation", "Source-recorded call hour only", "Client dimension unavailable",
    "Language dimension unavailable", "No payment-to-interaction key", "No cost ledger", "No RPC mapping",
    "No historical exposure balance", "No dialing-mode field", "Borrower segment unavailable as a separate field",
}
old_findings = [x for x in old_findings if x.get("issue") not in replace_issues]
findings.extend(old_findings)

# Recompute exact duplicate counts from raw files, not stale report values.
dup_counts = {n: int(raw[n].duplicated().sum()) for n in source_names}
total_dups = sum(dup_counts.values())
add_finding(findings, "Exact full-row duplicates", total_dups, str(dup_counts),
            "Remove exact duplicate rows from derived copies only; retain raw files",
            "Inflates event/payment counts if not removed")
q_pay = pd.read_csv(QUAR / "payment_id_conflicts.csv", low_memory=False)
add_finding(findings, "Conflicting payment IDs", len(q_pay), f"{q_pay.payment_id.nunique()} IDs with multiple non-identical payloads after exact dedup",
            "Quarantine every payload version; do not pick latest or aggregate", "Can inflate or misstate cash; quarantined amount is not assumed loss")
if "calls" in event_conflict_ids:
    q_calls = event_conflicts[event_conflicts.source_table.eq("calls")]
    add_finding(findings, "Conflicting call IDs", len(q_calls), f"{q_calls.call_id.nunique()} call IDs have non-identical payloads after exact dedup",
                "Quarantine every payload version; use only unambiguous call IDs in golden activity and joins",
                "Call/vendor/campaign/agent activity would otherwise be duplicated or arbitrarily mapped")
add_finding(findings, "Borrower ID multiple versions", len(borrower_superseded),
            f"{len(borrower_conflict_ids)} borrower IDs have more than one distinct row; latest updated_at used for current dimension",
            "Quarantine superseded versions and retain full raw history", "Current snapshot is not a historical borrower truth")
add_finding(findings, "Agent dimension version inflation", f"{ag_raw_rows} rows / {len(agent_snapshot)} unique agent IDs",
            f"{int(ag_raw_rows-len(agent_snapshot))} prior versions per the source history; call table has {len(calls)} deduped rows",
            "Latest updated_at per agent_id for current dimension; retain prior versions for audit",
            "A many-to-many join multiplied agent call counts; corrected agent stats now reconcile to deduped calls")
add_finding(findings, "Agent employee-code aliases", int(agent_alias.review_flag.sum()),
            f"{int(agent_alias.review_flag.sum())} employee codes map to multiple current agent IDs; {int(agent_id_history.review_flag.sum())} agent IDs changed employee code across history",
            "Do not merge IDs without HR identity crosswalk", "Agent-level productivity and tenure attribution may be split")

# Timestamp quality: preserve separate event and ingestion times.
lag = (history.recorded_ts - history.event_ts).dt.total_seconds() / 3600
add_finding(findings, "Status-history event/recorded timestamp divergence",
            f"median={lag.median():.2f}h; p95={lag.quantile(.95):.2f}h; negative_lags={(lag<0).sum()}",
            "recorded_at minus event_at has substantial spread, including future-effective/negative lags",
            "Apply bitemporal as-of logic; monitor negative lag and late-arrival corrections",
            "Historical state can differ depending on whether event time or recorded time is used")
field = src["field_visits"].copy()
bad_sched = pd.to_datetime(field.scheduled_at, errors="coerce").isna().sum()
add_finding(findings, "Unparseable field visit scheduled_at", int(bad_sched), f"{int(bad_sched)} of {len(field)} scheduled_at values fail parsing",
            "Preserve original string; request upstream correction", "Visit lead-time and schedule adherence analyses incomplete")
add_finding(findings, "Historical status denominator leakage", "Month-end status excludes accounts that become paid/closed/writeoff during the month",
            "Start-vs-end status and cash capture are quantified in denominator_survivorship_diagnostics.csv",
            "Start-of-month status snapshot now defines the provisional eligible cohort; unknown statuses excluded and quantified",
            "Month-end population is outcome-dependent and can understate eligible denominators / cash coverage")
add_finding(findings, "Incomplete start-of-month status coverage", "; ".join(f"{r.month}:{r.start_status_coverage_pct:.1f}%" for r in monthly_status_metrics.itertuples()),
            "Only accounts with a status event effective and recorded before month start count as known; Jan 2026 has no prior history",
            "Do not extrapolate observed-start subpopulation to full portfolio; obtain effective-dated daily status snapshots",
            "No complete historical eligible-account denominator; recovery per account/rate remains unverified")
add_finding(findings, "Payment timezone metadata missing", len(payments), "payments.csv has no row-level timezone or UTC offset",
            "Preserve source-local timestamp string and do not convert; require source timezone contract",
            "Daily/hourly cash cutoff and payment-date reconciliation cannot be certified")
add_finding(findings, "Source-recorded call hour only", calls.timezone_call.nunique() if "timezone_call" in calls else 0,
            "Call rows have timezone labels, but event_at storage semantics (UTC vs local wall time) are undocumented",
            "Report event_at hour as stored; do not label as borrower-local calling hour",
            "Calling-time performance and regulatory contact-window compliance cannot be certified")
add_finding(findings, "Disposition code versions", int(disp_summary.disposition_version.nunique()),
            f"Codes={sorted(disp_summary.disposition_code.astype(str).str.upper().unique())}; versions={sorted(disp_summary.disposition_version.astype(str).unique())}",
            "Require owner-approved versioned mapping to CONTACT/RPC/PTP/REFUSAL/etc.",
            "Contact, RPC and conversion metrics are not certified")
add_finding(findings, "Vendor schema versions without semantic map", int(src["vendor_telephony"].schema_version.nunique()),
            "Vendor reference contains schema_version/timezone/status but no response-code mapping table",
            "Keep schema/version cuts descriptive; require vendor mapping registry and effective dates",
            "Cannot conclude vendor response-code semantics changed")
add_finding(findings, "Client dimension unavailable", "NOT PRESENT", "No client_id/client_name field appears in the supplied 17 source schemas",
            "Request client/servicer master and account-client effective-dated bridge", "Client driver analysis cannot be performed")
add_finding(findings, "Borrower segment unavailable as a separate field", "PARTIAL ACCOUNT-LEVEL PROXY",
            "An account-level risk_segment exists in the current accounts snapshot; no distinct borrower_segment or effective-dated borrower segmentation field is supplied",
            "Use current risk_segment only as an explicitly labelled descriptive proxy; request point-in-time borrower segment history",
            "Borrower-segment effects cannot be isolated from account risk and time-varying portfolio mix")
add_finding(findings, "Language dimension unavailable", "NOT PRESENT", "No borrower language/preferred_language field appears in supplied schemas",
            "Request effective-dated borrower language preference and source confidence", "Language driver analysis cannot be performed")
add_finding(findings, "No dialing-mode field", "NOT PRESENT", "Call/campaign schemas do not distinguish human, predictive/progressive, IVR or agentic voice mode",
            "Add dialer_mode/automation_mode to call and campaign contracts", "Cannot compare automation or dialing-mode effectiveness")
add_finding(findings, "No payment-to-interaction key", "NOT PRESENT", "Payments have no call_id, touch_id, campaign_id, channel or PTP ID",
            "Persist collection_assignment_id/touch_id or experiment_id and explicit payment/settlement linkage where valid",
            "No defensible channel/agent/campaign conversion or causal attribution")
add_finding(findings, "No cost ledger", "NOT PRESENT", "No payroll-loaded agent cost, telecom cost, vendor bill, messaging cost, field visit cost or AI platform cost",
            "Add monthly cost fact by channel/vendor/team/technology with allocation rules",
            "Cost per ₹ recovered, ROI and break-even cannot be estimated")
add_finding(findings, "No historical exposure balance", "NOT PRESENT", "Account status history contains status only; no month-start outstanding exposure history",
            "Add daily/month-end principal/outstanding balance snapshots with effective/recorded timestamps",
            "Amount-weighted recovery rate cannot be estimated")

# More precise session overlap diagnostics.
sessions = src["agent_sessions"].copy()
sessions["login"] = pd.to_datetime(sessions.login_at, errors="coerce")
sessions["logout"] = pd.to_datetime(sessions.logout_at, errors="coerce")
sessions["duration_hours"] = (sessions.logout - sessions.login).dt.total_seconds() / 3600
sessions["invalid_duration"] = sessions.duration_hours.le(0) | sessions.duration_hours.gt(24) | sessions.duration_hours.isna()
sessions_ok = sessions[~sessions.invalid_duration].copy().sort_values(["agent_id", "login"])
sessions_ok["previous_logout"] = sessions_ok.groupby("agent_id").logout.shift()
sessions_ok["overlap_hours"] = (sessions_ok.previous_logout - sessions_ok.login).dt.total_seconds().div(3600).clip(lower=0).fillna(0)
sessions_ok["overlap"] = sessions_ok.overlap_hours.gt(0)
session_quality = pd.DataFrame([{
    "sessions_after_exact_dedup": len(sessions), "invalid_or_over_24h_sessions": int(sessions.invalid_duration.sum()),
    "valid_sessions": len(sessions_ok), "overlapping_sessions": int(sessions_ok.overlap.sum()),
    "overlap_hours_adjacent_only": float(sessions_ok.overlap_hours.sum()),
    "valid_logged_hours_raw_sum": float(sessions_ok.duration_hours.sum()),
    "limitation": "Logged-in time is not productive time; overlaps are not subtracted from per-agent shift totals",
}])
save(session_quality, REPORTS / "agent_session_quality.csv")
add_finding(findings, "Agent session overlap/invalid duration",
            f"invalid={int(sessions.invalid_duration.sum())}; overlaps={int(sessions_ok.overlap.sum())}; overlap_hours={sessions_ok.overlap_hours.sum():.1f}",
            "15,000 post-dedup sessions checked for non-positive/>24h duration and adjacent overlaps",
            "Exclude invalid sessions from duration metrics; investigate overlaps; logged-in time is not productive time",
            "Naive agent-hour productivity can be overstated")

# Language/client availability is also machine-readable.
unavailable = pd.DataFrame([
    ["client", "UNAVAILABLE", "No client_id/client_name column in any supplied source", "Client master + effective-dated account-client bridge"],
    ["language", "UNAVAILABLE", "No language/preferred_language column in any supplied source", "Effective-dated borrower language preference"],
    ["borrower_segment", "PARTIAL_PROXY_ONLY", "Current account risk_segment exists, but no borrower_segment or effective-dated borrower segmentation history", "Effective-dated borrower segment history linked to account-month"],
    ["dialing_mode", "UNAVAILABLE", "No human/predictive/progressive/IVR/agentic mode column", "Call/campaign dialer_mode and vendor event mode"],
    ["historical_exposure", "UNAVAILABLE", "No point-in-time balance/exposure in status history", "Daily or month-start balance snapshots"],
    ["channel_cost", "UNAVAILABLE", "No channel/vendor/agent cost ledger", "Fully loaded cost fact with allocation rules"],
    ["payment_touch_link", "UNAVAILABLE", "No touch/campaign/agent/PTP key in payment events", "Assignment/touch IDs plus payment settlement linkage"],
], columns=["dimension_or_metric", "status", "evidence", "required_additional_data"])
save(unavailable, REPORTS / "unavailable_dimensions.csv")

# Reconciliation and summary metrics for memo/dashboard.
findings_df = pd.DataFrame(findings).drop_duplicates(subset=["issue"], keep="last")
save(findings_df, REPORTS / "forensic_findings.csv")

summary_path = PROC / "pipeline_summary.json"
summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
core_source_rows = int(sum(len(frame) for frame in raw.values()))
dictionary_rows = int(len(read_raw("data_dictionary")))
summary.update({
    "dataset": "SYNTHETIC CHALLENGE DATA (seed 42)",
    "raw_rows_total": core_source_rows + dictionary_rows,
    "raw_rows_total_all_sources": core_source_rows + dictionary_rows,
    "raw_rows_total_core_tables": core_source_rows,
    "raw_rows_data_dictionary": dictionary_rows,
    "payment_coverage_start": str(payments.event_ts.min()), "payment_coverage_end": str(payments.event_ts.max()),
    "complete_payment_months": int(all_payment_month.complete_month.sum()),
    "partial_payment_months": int((~all_payment_month.complete_month).sum()),
    "gross_successful_collections": float(success.gross_success_amount.sum()),
    "successful_payment_events": int(len(success)),
    "reversal_events": int(payments.payment_status_norm.eq("REVERSED").sum()),
    "reversal_amount_reported_separately": float(pd.to_numeric(payments.get("reversal_amount", 0), errors="coerce").sum()),
    "deduped_and_conflict_free_call_rows": int(len(calls)), "conflicting_call_id_rows_quarantined": int(len(event_conflicts[event_conflicts.source_table.eq("calls")])), "unique_agent_ids": int(len(agent_snapshot)),
    "raw_agent_version_rows": int(ag_raw_rows), "agent_rows_superseded_in_current_dimension": int(ag_raw_rows-len(agent_snapshot)),
    "start_of_month_status_coverage": {r.month: round(float(r.start_status_coverage_pct), 2) for r in monthly_status_metrics.itertuples()},
    "month_start_denominator_policy": "Last status event effective before month start and recorded by month start; unknown status excluded; Jan 2026 unavailable",
    "reported_11pct_claim": "INCONCLUSIVE; original KPI formula, complete 12-month window and historical exposure denominator absent",
    "counterfactual": "NOT IDENTIFIED; targeting assignment is observational and overlapping",
    "investment_decision": "No ₹10 Cr deployment can be financially recommended; borrower targeting is the leading controlled-pilot candidate only",
    "financial_roi": "NOT ESTIMABLE: incremental treatment effect and fully loaded cost ledger absent",
    "unavailable_dimensions": ["client", "language", "dialing_mode", "historical_exposure", "channel_cost", "payment_touch_link"],
    "partially_available_dimensions": ["borrower_segment: current account risk_segment proxy only"],
})
(PROC / "pipeline_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "monthly_cash": all_payment_month[["month", "gross_successful_collections", "gross_cash_mom_pct", "complete_month"]].to_dict("records"),
    "monthly_start_denominators": monthly_status_metrics[["month", "eligible_accounts_at_month_start", "start_status_coverage_pct", "gross_cash_per_start_eligible_account"]].to_dict("records"),
    "agent_rows": {"raw": ag_raw_rows, "snapshot": len(agent_snapshot), "calls_after_join": len(agent_calls), "dedup_calls": len(calls)},
}, indent=2, default=str))
