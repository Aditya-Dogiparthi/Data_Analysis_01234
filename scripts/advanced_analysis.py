"""Build account-month metrics, forensic diagnostics, cohorts, mix proxy and pilot evidence tables."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"; GOLD=ROOT/"data"/"golden"; PROC=ROOT/"data"/"processed"
REPORTS=ROOT/"reports"; QUAR=ROOT/"data"/"quarantine"
for p in [GOLD,PROC,REPORTS,QUAR]: p.mkdir(parents=True,exist_ok=True)

def read(name): return pd.read_csv(RAW/f"{name}.csv",low_memory=False)
def save(df,path):
    path=Path(path); df.to_csv(path,index=False)
    try: df.to_parquet(path.with_suffix(".parquet"),index=False)
    except (ImportError,ModuleNotFoundError): pass

names=["accounts","borrowers","agents","agent_sessions","campaigns","daily_targeting","calls","call_attempts",
       "call_dispositions","whatsapp_events","sms_events","field_visits","promises_to_pay","payments",
       "vendor_telephony","complaints","account_status_history"]
src={n:read(n) for n in names}

# Source-level exact duplicate audit before transformations.
dup_by_source={n:int(df.duplicated().sum()) for n,df in src.items()}
# Payment exact duplicate and stable-key conflict treatment.
praw=src["payments"].copy()
p=praw.drop_duplicates().copy()
payment_exact_removed=len(praw)-len(p)
counts=p.groupby("payment_id",dropna=False).size()
conflict_ids=counts[counts>1].index
conflicts=p[p.payment_id.isin(conflict_ids)].copy()
save(conflicts,QUAR/"payment_id_conflicts.csv")
p=p[~p.payment_id.isin(conflict_ids)].copy()
p["amount"]=pd.to_numeric(p.amount,errors="coerce")
p["event_ts_source"]=pd.to_datetime(p.event_at,errors="coerce")
p["month"]=p.event_ts_source.dt.to_period("M").astype(str)
p["payment_status_norm"]=p.payment_status.astype(str).str.upper().str.strip()
p["gross_success_amount"]=np.where(p.payment_status_norm.eq("SUCCESS"),p.amount.clip(lower=0),0)
p["reversal_amount"]=np.where(p.payment_status_norm.eq("REVERSED"),p.amount.clip(lower=0),0)
p["source_timezone_policy"]="SOURCE_LOCAL_NAIVE; NO UTC CONVERSION"
save(p,GOLD/"golden_payments.csv")

# Account snapshot dimensions; label them as current, not historically effective-dated.
a=src["accounts"].drop_duplicates().copy()
a["dpd_num"]=pd.to_numeric(a.dpd,errors="coerce")
a["dpd_bucket"]=pd.cut(a.dpd_num,[-1,0,30,60,90,180,100000],
                       labels=["Current","1-30","31-60","61-90","91-180","180+"]).astype(str)
save(a,GOLD/"golden_accounts_snapshot.csv")

# Monthly account status as-of: last event in month, carry forward after first event.
h=src["account_status_history"].copy()
h["event_ts"]=pd.to_datetime(h.event_at,errors="coerce")
h["month"]=h.event_ts.dt.to_period("M").astype(str)
h["recorded_ts"]=pd.to_datetime(h.recorded_at,errors="coerce")
h=h.sort_values(["account_id","event_ts","recorded_ts"])
last=h.groupby(["account_id","month"],as_index=False).tail(1)[["account_id","month","status","event_ts"]]
months=pd.period_range("2026-01","2026-08",freq="M").astype(str)
grid=pd.MultiIndex.from_product([a.account_id.unique(),months],names=["account_id","month"]).to_frame(index=False)
sm=grid.merge(last,on=["account_id","month"],how="left").sort_values(["account_id","month"])
sm["status"]=sm.groupby("account_id").status.ffill()
sm=sm.merge(a[["account_id","borrower_id","opened_at","loan_type","risk_segment","dpd","outstanding_amount","status","dpd_bucket"]],
            on="account_id",how="left",suffixes=("","_snapshot"))
sm["opened_month"]=pd.to_datetime(sm.opened_at,errors="coerce").dt.to_period("M").astype(str)
sm["eligible_asof_month_end"]=sm.opened_month.le(sm.month) & sm.status.astype(str).str.upper().isin(["ACTIVE","DELINQUENT","NPA","PTP"])
sm["status_observed_this_month"]=sm.event_ts.notna()
sm["denominator_basis"]="STATUS_HISTORY_CARRIED_FORWARD; CURRENT SNAPSHOT ATTRIBUTES"
save(sm,GOLD/"account_month_status_snapshot.csv")

# Payment/account month panel.
paydim=p.merge(a[["account_id","loan_type","risk_segment","dpd_bucket","status","timezone"]],
               on="account_id",how="left",validate="many_to_one")
success=paydim[paydim.payment_status_norm.eq("SUCCESS")].groupby(["account_id","month"],as_index=False).agg(gross_cash=("gross_success_amount","sum"))
panel=sm[["account_id","month","eligible_asof_month_end","risk_segment","loan_type","dpd_bucket","status"]].merge(
    success,on=["account_id","month"],how="left")
panel["gross_cash"]=panel.gross_cash.fillna(0)
eligible=panel[panel.eligible_asof_month_end].copy()
save(eligible,GOLD/"account_month_recovery_panel.csv")

monthly=eligible.groupby("month").agg(
    eligible_accounts=("account_id","nunique"),
    paying_accounts=("gross_cash",lambda s:int((s>0).sum())),
    gross_cash=("gross_cash","sum"),
    median_cash_per_eligible=("gross_cash","median"),
    mean_cash_per_eligible=("gross_cash","mean")
).reset_index()
monthly["paying_account_share"]=monthly.paying_accounts/monthly.eligible_accounts.replace(0,np.nan)
monthly["complete_month"]=monthly.month.ne("2026-08")
monthly["denominator_caveat"]="ACCOUNT COUNT ONLY; NO HISTORICAL BALANCE/EXPOSURE"
save(monthly,GOLD/"monthly_eligible_account_metrics.csv")
trend=monthly.sort_values("month").copy()
trend["gross_cash_mom_pct"]=trend.gross_cash.pct_change()*100
trend["cash_per_eligible_mom_pct"]=trend.mean_cash_per_eligible.pct_change()*100
save(trend,GOLD/"monthly_trend_analysis.csv")

# January risk mix standardization proxy using current risk attributes.
seg=eligible.groupby(["month","risk_segment"]).agg(cash=("gross_cash","sum"),eligible=("account_id","nunique")).reset_index()
seg["cash_per_eligible"]=seg.cash/seg.eligible.replace(0,np.nan)
ref=eligible[eligible.month.eq("2026-01")].groupby("risk_segment").account_id.nunique()
ref=ref/ref.sum()
mix=[]
for month,g in seg.groupby("month"):
    rates=g.set_index("risk_segment").cash_per_eligible
    common=ref.index.intersection(rates.dropna().index)
    mix.append({"month":month,"observed_gross_cash_per_eligible":g.cash.sum()/g.eligible.sum(),
                "jan_risk_mix_standardized_cash_per_eligible":float((rates.loc[common]*ref.loc[common]).sum()),
                "reference_mix":"January eligible account risk_segment share",
                "limitation":"Current risk segment, not historical point-in-time attribute"})
mix=pd.DataFrame(mix); save(mix,GOLD/"mix_adjusted_recovery_proxy.csv")

# Account vintage cohort panel.
cohort_dim=a[["account_id","opened_at"]].copy()
cohort_dim["cohort_month"]=pd.to_datetime(cohort_dim.opened_at,errors="coerce").dt.to_period("M").astype(str)
cohort=eligible.merge(cohort_dim[["account_id","cohort_month"]],on="account_id",how="left")
cohort=cohort.groupby(["cohort_month","month"]).agg(
    eligible_accounts=("account_id","nunique"),gross_cash=("gross_cash","sum"),
    paying_accounts=("gross_cash",lambda s:int((s>0).sum()))).reset_index()
cohort["gross_cash_per_eligible"]=cohort.gross_cash/cohort.eligible_accounts.replace(0,np.nan)
save(cohort,GOLD/"account_vintage_cohorts.csv")

# Campaign/strategy comparison is observational; account-months can have multiple strategy rows.
target=src["daily_targeting"].copy()
target["month"]=pd.to_datetime(target.target_date,errors="coerce").dt.to_period("M").astype(str)
target=target.merge(src["campaigns"][["campaign_id","channel","strategy_version","campaign_name"]],
                    on="campaign_id",how="left",validate="many_to_one")
tgt=target.groupby(["account_id","month","strategy_version"],dropna=False).agg(
    target_events=("target_id","count"),campaigns=("campaign_id","nunique")).reset_index()
strat=tgt.merge(success,on=["account_id","month"],how="left")
strat["gross_cash"]=strat.gross_cash.fillna(0)
strat=strat.groupby(["month","strategy_version"]).agg(
    targeted_account_strategy_months=("account_id","size"),
    paying_account_strategy_months=("gross_cash",lambda s:int((s>0).sum())),
    gross_cash=("gross_cash","sum"),
    gross_cash_per_targeted_account_strategy_month=("gross_cash","mean")).reset_index()
strat["interpretation"]="DESCRIPTIVE ONLY; NON-RANDOMIZED; OVERLAPPING CAMPAIGN EXPOSURES"
save(strat,GOLD/"targeting_strategy_outcomes_descriptive.csv")

# Operational event trends.
for table,tag in [("calls","calls"),("call_attempts","call_attempts"),("whatsapp_events","whatsapp"),
                  ("sms_events","sms"),("field_visits","field_visits")]:
    df=src[table].copy()
    df["month"]=pd.to_datetime(df.event_at,errors="coerce").dt.to_period("M").astype(str)
    if table=="calls":
        g=df.groupby("month").agg(events=("call_id","count"),accounts=("account_id","nunique"),
            answered=("call_status",lambda s:s.astype(str).str.upper().eq("ANSWERED").sum()),
            mean_duration_sec=("duration_sec","mean")).reset_index()
        g["answered_share"]=g.answered/g.events
    else:
        key=next((c for c in df.columns if c.endswith("_id") and c not in ["account_id","borrower_id","agent_id","campaign_id","vendor_id"]),None)
        g=df.groupby("month").agg(events=(key or "account_id","count"),accounts=("account_id","nunique")).reset_index()
    save(g,GOLD/f"monthly_{tag}_operations.csv")

# PTP maturity and status summary (status-reported only; not payment-linked kept rate).
ptp=src["promises_to_pay"].copy()
ptp["month"]=pd.to_datetime(ptp.event_at,errors="coerce").dt.to_period("M").astype(str)
ptp["promised_ts"]=pd.to_datetime(ptp.promised_date,errors="coerce")
ptp["status_norm"]=ptp.status.astype(str).str.upper()
cutoff=pd.Timestamp("2026-08-08 23:59:59")
ptpm=ptp.groupby("month").agg(ptp_rows=("ptp_id","count"),ptp_accounts=("account_id","nunique"),
    kept_status_rows=("status_norm",lambda s:(s=="KEPT").sum()),broken_status_rows=("status_norm",lambda s:(s=="BROKEN").sum()),
    matured_rows=("promised_ts",lambda s:s.le(cutoff).sum())).reset_index()
ptpm["status_kept_share_all_rows"]=ptpm.kept_status_rows/ptpm.ptp_rows
ptpm["limitation"]="NOT LINKED TO SETTLED PAYMENTS; NOT A VERIFIED KEPT RATE"
save(ptpm,GOLD/"monthly_ptp_diagnostics.csv")

# Disposition code/version diagnostics; do not certify candidate RPC map.
d=src["call_dispositions"].copy()
d["month"]=pd.to_datetime(d.event_at,errors="coerce").dt.to_period("M").astype(str)
d["code_norm"]=d.disposition_code.astype(str).str.upper().str.strip()
candidate={"PTP","PROMISE_TO_PAY","PAID","REFUSED","DISPUTE"}
d["candidate_rpc"]=d.code_norm.isin(candidate)
dm=d.groupby(["month","disposition_version"]).agg(rows=("disposition_id","count"),
    candidate_rpc_rows=("candidate_rpc","sum"),accounts=("account_id","nunique")).reset_index()
dm["mapping_status"]="CANDIDATE ONLY — BUSINESS OWNER VALIDATION REQUIRED"
save(dm,GOLD/"disposition_version_diagnostics.csv")

# Identity alias review based on exact employee_code only; no fuzzy matching.
agents=src["agents"].copy()
alias=agents.groupby("employee_code",dropna=False).agg(agent_ids=("agent_id","nunique"),
    agent_id_list=("agent_id",lambda s:";".join(sorted(set(s.astype(str)))))).reset_index()
alias["review_flag"]=alias.agent_ids.gt(1)
save(alias,GOLD/"agent_identity_alias_review.csv")

# Forensic findings, including measured source-level conditions.
findings=[]
def add(issue,value,evidence,treatment,impact,confidence="FACT"):
    findings.append({"issue":issue,"measured_value":value,"evidence":evidence,"treatment":treatment,
                     "business_impact":impact,"confidence":confidence})
add("Exact full-row duplicates",sum(dup_by_source.values()),str(dup_by_source),
    "Remove from derived tables only; raw immutable","Can inflate operational event and payment counts")
add("Conflicting payment IDs",len(conflicts),f"{conflicts.payment_id.nunique()} IDs with multiple payload rows after exact dedup",
    "Quarantine all payload variants","Amount/event distortion possible; do not treat quarantine amount as loss")
ref= p.groupby("payment_reference").agg(rows=("payment_id","size"),accounts=("account_id","nunique")).reset_index()
rep=ref[ref.rows>1]
add("Repeated payment references",len(rep),f"{len(rep)} repeated refs; {int((rep.accounts>1).sum())} span multiple accounts",
    "Do not use reference alone as global dedup key","Could incorrectly delete legitimate distinct transactions")
bad_sched=pd.to_datetime(src["field_visits"].scheduled_at,errors="coerce").isna().sum()
add("Unparseable field visit scheduled_at",int(bad_sched),f"{bad_sched} rows fail timestamp parsing",
    "Preserve source value; request upstream correction","Scheduling and lead-time analysis incomplete")
add("Agent employee-code aliases",int(alias.review_flag.sum()),f"{int(alias.review_flag.sum())} employee codes map to multiple agent IDs",
    "Retain IDs; resolve using authoritative HR mapping","Agent productivity may split across IDs")
hist=src["account_status_history"].copy()
lat=(pd.to_datetime(hist.recorded_at,errors="coerce")-pd.to_datetime(hist.event_at,errors="coerce")).dt.total_seconds()/3600
add("Status-history ingestion latency",round(float(lat.median()),2),
    f"Median {lat.median():.2f}h; p95 {lat.quantile(.95):.2f}h; negative lags {(lat<0).sum()}",
    "Keep event and recorded time; late-arrival backfill","Historical as-of values can change after ingestion")
add("Payment event coverage",f"{p.event_ts_source.min()} to {p.event_ts_source.max()}",
    "Seven complete calendar months plus partial August 2026","Do not label as 12-month evidence","Cannot verify full-year trend")
add("Timezone normalization",len(p),"Payment event rows have no row-level timezone field",
    "Keep source-local naive timestamps; require source contract","Calling hour/day attribution not certified")
add("Disposition code versions",int(d.disposition_version.nunique()),
    f"Versions={sorted(d.disposition_version.dropna().astype(str).unique())}; codes={sorted(d.code_norm.dropna().unique())}",
    "Versioned code map and owner sign-off before RPC metrics","Contact/RPC metrics remain uncertified")
add("Historical exposure denominator",0,"No monthly point-in-time outstanding balance/exposure field in status history",
    "Use provisional account-count denominator only; obtain daily/month-end balance snapshots",
    "Cannot calculate amount-weighted recovery rate","FACT")
add("Current portfolio dimensions",len(a),"Risk, DPD, loan type and timezone come from current account snapshot",
    "Mark segment cuts as current-snapshot descriptive","Historical mix adjustment may be biased")
save(pd.DataFrame(findings),REPORTS/"forensic_findings.csv")

# Bootstrap CI for mean account cash; reproducible seed.
rng=np.random.default_rng(42); boot=[]
for month,g in eligible.groupby("month"):
    vals=g.gross_cash.to_numpy(float)
    means=np.array([rng.choice(vals,size=min(len(vals),5000),replace=True).mean() for _ in range(500)])
    boot.append({"month":month,"mean_cash_per_eligible":float(vals.mean()),
        "ci_2_5":float(np.quantile(means,.025)),"ci_97_5":float(np.quantile(means,.975)),
        "n_eligible":len(vals),"method":"500 account-level bootstrap resamples"})
save(pd.DataFrame(boot),GOLD/"monthly_cash_bootstrap_ci.csv")

# Investment evidence comparison; deliberately no fabricated financial ROI.
options=pd.DataFrame([
["Better telephony infrastructure","Vendor connect/RPC lift, uptime, cost/minute","Stepped-wedge vendor/region rollout","Not estimable"],
["More collection agents","Productive agent-hours, marginal recovery/hour, loaded employment cost","Matched team capacity pilot","Not estimable"],
["AI voice automation","Verified RPC, incremental net cash, complaints, escalations, cost/call","Randomized account-level holdout","Not estimable"],
["Better borrower targeting","Random assignment, frozen eligibility, incremental net cash/account","Stratified randomized controlled trial","Best pilot candidate; ROI unproven"],
["WhatsApp/digital engagement","Delivery/read/payment linkage, opt-outs, complaints, cost/send","Randomized channel encouragement test","Not estimable"],
["Field operations","Visit costs, incremental payments, safety/complaint metrics","Randomized geographic/account pilot","Not estimable"]
],columns=["investment_option","minimum_evidence_required","recommended_pilot","roi_status"])
save(options,REPORTS/"six_option_investment_comparison.csv")

# Full source inventory.
inv=[]
for path in sorted(RAW.glob("*.csv")):
    df=pd.read_csv(path,low_memory=False)
    ranges={}
    for c in [x for x in df.columns if x.endswith("_at") or x.endswith("_date")]:
        dt=pd.to_datetime(df[c],errors="coerce")
        if dt.notna().any(): ranges[c]={"min":str(dt.min()),"max":str(dt.max()),"unparseable":int(dt.isna().sum())}
    inv.append({"source":path.name,"rows":len(df),"columns":len(df.columns),
        "null_cells_pct":round(float(df.isna().mean().mean()*100),4),
        "full_row_duplicates":int(df.duplicated().sum()),"date_ranges":json.dumps(ranges)})
save(pd.DataFrame(inv),PROC/"data_inventory_full.csv")

summary={
 "dataset":"SYNTHETIC CHALLENGE DATA (seed 42)","raw_source_files":len(list(RAW.glob("*.csv"))),
 "raw_rows_total":int(sum(len(x) for x in src.values())),
 "exact_duplicate_rows_removed_across_core_tables":int(sum(dup_by_source.values())),
 "payment_exact_duplicate_rows_removed":int(payment_exact_removed),
 "payment_id_conflict_rows_quarantined":int(len(conflicts)),
 "payment_id_conflict_unique_ids":int(conflicts.payment_id.nunique()),
 "quarantined_payment_payload_amount_sum_not_assumed_loss":float(pd.to_numeric(conflicts.amount,errors="coerce").sum()),
 "golden_payment_rows":int(len(p)),"successful_payment_events":int(p.payment_status_norm.eq("SUCCESS").sum()),
 "gross_successful_collections":float(p.gross_success_amount.sum()),
 "reversal_events":int(p.payment_status_norm.eq("REVERSED").sum()),
 "reversal_amount_reported_separately":float(p.reversal_amount.sum()),
 "payment_coverage_start":str(p.event_ts_source.min()),"payment_coverage_end":str(p.event_ts_source.max()),
 "eligible_account_denominator":"Latest account status event per account-month, carried forward after first observed status; eligible states ACTIVE/DELINQUENT/NPA/PTP",
 "timezone_policy":"Preserve source timestamps; no unsupported UTC conversion",
 "reported_11pct_claim":"INCONCLUSIVE; no supplied metric definition or historical exposure balances",
 "counterfactual":"NOT IDENTIFIED; targeting is observational and overlapping",
 "investment_decision":"Do not commit ₹10 Cr before randomized pilot and full cost measurement",
 "investment_options_compared":6}
(PROC/"pipeline_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))


# Additional dimensions, identity reviews, agent tenure and session-quality diagnostics.
borrowers_raw=src["borrowers"].drop_duplicates().copy()
borrower_dup=borrowers_raw.groupby("borrower_id").size()
borrower_conflict_ids=borrower_dup[borrower_dup>1].index
borrower_conflicts=borrowers_raw[borrowers_raw.borrower_id.isin(borrower_conflict_ids)].copy()
save(borrower_conflicts,QUAR/"borrower_id_multiple_versions.csv")
borrowers=borrowers_raw.copy()
borrowers["updated_ts"]=pd.to_datetime(borrowers.updated_at,errors="coerce")
borrowers=borrowers.sort_values(["borrower_id","updated_ts"]).drop_duplicates("borrower_id",keep="last")
save(borrowers,GOLD/"golden_borrowers_snapshot.csv")
account_dim=a.merge(borrowers[["borrower_id","city","state","name"]],on="borrower_id",how="left",validate="many_to_one")
save(account_dim,GOLD/"account_dimension_enriched.csv")
pay_geo=paydim.merge(borrowers[["borrower_id","city","state"]],on="borrower_id",how="left",validate="many_to_one")
for dim in ["state","city","loan_type","risk_segment","dpd_bucket"]:
    out=pay_geo[pay_geo.payment_status_norm.eq("SUCCESS")].groupby(["month",dim]).agg(
        gross_successful_cash=("gross_success_amount","sum"),successful_events=("payment_id","count"),
        paying_accounts=("account_id","nunique")).reset_index()
    out["attribute_timing"]="CURRENT SNAPSHOT; DESCRIPTIVE ONLY"
    save(out,GOLD/f"recovery_by_{dim}.csv")

agents=src["agents"].drop_duplicates().copy()
calls=src["calls"].copy()
calls["event_ts"]=pd.to_datetime(calls.event_at,errors="coerce")
calls["month"]=calls.event_ts.dt.to_period("M").astype(str)
calls=calls.merge(agents[["agent_id","employee_code","joined_at","vendor_id","team"]],
                  on="agent_id",how="left",suffixes=("","_agent"))
calls["tenure_days_at_event"]=(calls.event_ts-pd.to_datetime(calls.joined_at,errors="coerce")).dt.days
calls["tenure_band"]=pd.cut(calls.tenure_days_at_event,[-1,30,90,180,365,100000],
    labels=["0-30d","31-90d","91-180d","181-365d","365d+"]).astype(str)
agent_tenure=calls.groupby(["month","tenure_band"]).agg(calls=("call_id","count"),
    answered=("call_status",lambda s:s.astype(str).str.upper().eq("ANSWERED").sum()),
    accounts=("account_id","nunique"),mean_duration_sec=("duration_sec","mean")).reset_index()
agent_tenure["answered_share"]=agent_tenure.answered/agent_tenure.calls
save(agent_tenure,GOLD/"agent_tenure_performance.csv")

sessions=src["agent_sessions"].copy()
sessions["login"]=pd.to_datetime(sessions.login_at,errors="coerce")
sessions["logout"]=pd.to_datetime(sessions.logout_at,errors="coerce")
sessions["duration_hours"]=(sessions.logout-sessions.login).dt.total_seconds()/3600
sessions["invalid_duration"]=sessions.duration_hours.le(0) | sessions.duration_hours.gt(24)
sessions_valid=sessions[~sessions.invalid_duration].copy().sort_values(["agent_id","login"])
sessions_valid["previous_logout"]=sessions_valid.groupby("agent_id").logout.shift()
sessions_valid["overlap"]=sessions_valid.login.lt(sessions_valid.previous_logout)
session_quality=pd.DataFrame([{
    "sessions_raw":len(sessions),"invalid_or_over_24h_sessions":int(sessions.invalid_duration.sum()),
    "valid_sessions":len(sessions_valid),"overlapping_sessions_after_sort":int(sessions_valid.overlap.sum()),
    "valid_logged_hours_sum":float(sessions_valid.duration_hours.sum()),
    "limitation":"Logged-in time is not productive time; adjacent overlap check only"
}])
save(session_quality,REPORTS/"agent_session_quality.csv")

phone_counts=borrowers.phone.dropna().astype(str).str.replace(r"\D","",regex=True).value_counts()
email_counts=borrowers.email.dropna().astype(str).str.lower().value_counts()
identity=pd.DataFrame([
    {"identifier_type":"normalized_phone","duplicate_values":int((phone_counts>1).sum()),"rows_in_duplicate_groups":int(phone_counts[phone_counts>1].sum()),"policy":"Review only; do not auto-merge borrowers"},
    {"identifier_type":"normalized_email","duplicate_values":int((email_counts>1).sum()),"rows_in_duplicate_groups":int(email_counts[email_counts>1].sum()),"policy":"Review only; do not auto-merge borrowers"},
    {"identifier_type":"borrower_id_multiple_versions","duplicate_values":int(len(borrower_conflict_ids)),"rows_in_duplicate_groups":int(len(borrower_conflicts)),"policy":"Latest updated_at selected for dimension; all versions quarantined"}
])
save(identity,GOLD/"borrower_identity_review.csv")
vendor=src["vendor_telephony"].copy()
vendor_diag=vendor.groupby(["schema_version","timezone","status"]).agg(vendors=("vendor_id","nunique")).reset_index()
vendor_diag["limitation"]="Metadata only; response/disposition code mapping not present"
save(vendor_diag,GOLD/"vendor_schema_diagnostics.csv")

extra=[
{"issue":"Borrower phone collisions","measured_value":int((phone_counts>1).sum()),"evidence":"Normalized phone values repeated; PII not exported","treatment":"Manual review only; no fuzzy entity merge","business_impact":"Borrower aggregation may be overstated if identities unresolved","confidence":"FACT"},
{"issue":"Borrower email collisions","measured_value":int((email_counts>1).sum()),"evidence":"Lowercased email values repeated; PII not exported","treatment":"Manual review only; no fuzzy entity merge","business_impact":"Borrower aggregation may be overstated if identities unresolved","confidence":"FACT"},
{"issue":"Borrower ID multiple versions","measured_value":int(len(borrower_conflicts)),"evidence":f"{len(borrower_conflict_ids)} borrower IDs have multiple records; latest updated_at selected for dimension","treatment":"Quarantine all versions; deterministic latest-updated dimension snapshot","business_impact":"Historical borrower attributes may have been overwritten","confidence":"FACT"},
{"issue":"Agent session overlap/invalid duration","measured_value":int(sessions.invalid_duration.sum()+sessions_valid.overlap.sum()),"evidence":f"{int(sessions.invalid_duration.sum())} invalid/>24h sessions; {int(sessions_valid.overlap.sum())} overlaps","treatment":"Exclude invalid sessions from duration summaries; review overlaps","business_impact":"Naive agent-hour productivity may be overstated","confidence":"FACT"},
{"issue":"Vendor mapping drift","measured_value":int(vendor.schema_version.nunique()),"evidence":f"Vendor schema versions {sorted(vendor.schema_version.dropna().astype(str).unique())}; no response mapping columns supplied","treatment":"Require versioned vendor response mapping","business_impact":"Semantic drift cannot be established from metadata alone","confidence":"FACT"}
]
fpath=REPORTS/"forensic_findings.csv"
existing=pd.read_csv(fpath)
existing=existing[~existing.issue.isin([x["issue"] for x in extra])]
save(pd.concat([existing,pd.DataFrame(extra)],ignore_index=True),fpath)
summary["borrower_id_multiple_versions"]=int(len(borrower_conflict_ids))
summary["agent_session_overlaps"]=int(sessions_valid.overlap.sum())
summary["raw_rows_total_core_tables"]=int(sum(len(x) for x in src.values()))
summary["raw_rows_data_dictionary"]=int(len(read("data_dictionary")))
(PROC/"pipeline_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")


# Enrich account-month panel with borrower geography while preserving account-month grain.
panel_geo=eligible.merge(account_dim[["account_id","city","state"]],on="account_id",how="left",validate="many_to_one")
panel_geo["borrower_segment"]=panel_geo["risk_segment"]
save(panel_geo,GOLD/"account_month_recovery_panel.csv")
