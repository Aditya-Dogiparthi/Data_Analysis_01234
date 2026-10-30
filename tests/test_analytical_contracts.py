from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"
GOLD=ROOT/"data"/"golden"

def test_raw_payments_are_preserved_and_golden_is_smaller():
    raw=pd.read_csv(RAW/"payments.csv",low_memory=False)
    gold=pd.read_csv(GOLD/"golden_payments.csv",low_memory=False)
    assert len(gold)<len(raw)
    assert len(raw)==25500
    assert gold.payment_id.is_unique

def test_payment_status_financial_reconciliation():
    p=pd.read_csv(GOLD/"golden_payments.csv")
    assert (p.loc[p.payment_status_norm=="SUCCESS","gross_success_amount"]>=0).all()
    assert p.loc[p.payment_status_norm!="SUCCESS","gross_success_amount"].sum()==0
    assert p.loc[p.payment_status_norm=="REVERSED","reversal_amount"].sum()>0

def test_conflicting_payment_ids_quarantined_in_full():
    q=pd.read_csv(ROOT/"data"/"quarantine"/"payment_id_conflicts.csv")
    assert q.payment_id.nunique()==14
    assert q.payment_id.isin(pd.read_csv(GOLD/"golden_payments.csv").payment_id).sum()==0

def test_account_month_panel_has_unique_grain():
    df=pd.read_csv(GOLD/"account_month_recovery_panel.csv")
    assert not df.duplicated(["account_id","month"]).any()

def test_monthly_denominator_coverage_is_explicit():
    df=pd.read_csv(GOLD/"monthly_eligible_account_metrics.csv")
    assert "eligible_accounts_at_month_start" in df.columns
    assert "start_status_coverage_pct" in df.columns
    # January has no pre-period history and must remain unknown, not imputed.
    jan=df.loc[df.month=="2026-01"].iloc[0]
    assert jan.eligible_accounts_at_month_start == 0
    assert jan.start_status_coverage_pct == 0
    assert (df.loc[df.month!="2026-01","eligible_accounts_at_month_start"]>0).all()
    assert df.denominator_warning.str.contains("OBSERVED STATUS-HISTORY SUBPOPULATION").all()

def test_partial_august_is_marked_incomplete():
    df=pd.read_csv(GOLD/"monthly_eligible_account_metrics.csv")
    assert not bool(df.loc[df.month=="2026-08","complete_month"].iloc[0])

def test_mix_adjustment_reference_month_is_stable():
    df=pd.read_csv(GOLD/"mix_adjusted_recovery_proxy.csv")
    ref=df.reference_month.iloc[0]
    row=df.loc[df.month==ref].iloc[0]
    assert np.isclose(row.observed_gross_cash_per_start_eligible,
                      row.fixed_reference_risk_mix_cash_per_start_eligible_proxy)
    assert "NOT AN EXPOSURE-WEIGHTED" in row.limitation

def test_raw_payment_source_is_not_modified_by_pipeline():
    df=pd.read_csv(RAW/"payments.csv",low_memory=False)
    assert len(df)==25500
    assert "gross_success_amount" not in df.columns

def test_no_claimed_roi_without_cost_data():
    df=pd.read_csv(ROOT/"reports"/"six_option_investment_comparison.csv")
    assert df.roi_status.str.contains("not estimable|unproven",case=False).all()

def test_attribution_is_not_called_causal():
    txt=(ROOT/"reports"/"counterfactual_design.md").read_text().lower()
    assert "not identified" in txt
    assert "itt" in txt or "intention-to-treat" in txt


def test_simpsons_paradox_screen_is_explicit_and_caveated():
    p=GOLD/"simpsons_paradox_pair_summary.csv"
    assert p.exists()
    df=pd.read_csv(p)
    assert {"risk_segment","dpd_bucket","loan_type","state"}.issubset(set(df.dimension))
    assert df.limitation.str.contains("CURRENT SNAPSHOT ATTRIBUTES").all()


def test_pipeline_manifest_records_source_hashes_and_outputs():
    import json
    manifest = json.loads((ROOT / "data/processed/pipeline_manifest.json").read_text())
    assert manifest["run_id"]
    assert len(manifest["raw_sources"]) == 18
    assert all(len(item["sha256"]) == 64 for item in manifest["raw_sources"])
    assert any(item["path"].endswith("golden_payments.csv") for item in manifest["generated_csv_artifacts"])


def test_sql_financial_mart_reads_conflict_free_golden_events():
    sql = (ROOT / "dbt_collections/models/golden/golden_monthly_cash.sql").read_text().lower()
    assert "golden_payment_events" in sql
    assert "from {{ ref('stg_payments') }}" not in sql


def test_executed_end_to_end_notebook_is_valid():
    import nbformat
    path = ROOT / "notebooks/07_end_to_end_investigation.ipynb"
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    assert len(notebook.cells) >= 20
    assert any("inconclusive" in cell.source.lower() for cell in notebook.cells if cell.cell_type == "markdown")
    errors = [out for cell in notebook.cells if cell.cell_type == "code"
              for out in cell.get("outputs", []) if out.output_type == "error"]
    assert not errors


def test_borrower_segment_gap_is_disclosed():
    d=pd.read_csv(ROOT/"reports"/"unavailable_dimensions.csv")
    row=d.loc[d.dimension_or_metric=="borrower_segment"].iloc[0]
    assert row.status=="PARTIAL_PROXY_ONLY"
    assert "risk_segment" in row.evidence


def test_manifest_raw_row_total_reconciles_dictionary_and_operational_sources():
    import json
    manifest = json.loads((ROOT / "data/processed/pipeline_manifest.json").read_text())
    summary = json.loads((ROOT / "data/processed/pipeline_summary.json").read_text())
    source_rows = sum(item["rows"] for item in manifest["raw_sources"])
    assert source_rows == summary["raw_rows_total"]
    assert summary["raw_rows_total_core_tables"] + summary["raw_rows_data_dictionary"] == source_rows


def test_attribution_window_sensitivity_is_monotonic_and_caveated():
    d = pd.read_csv(GOLD / "payment_touch_window_sensitivity.csv")
    overall = d.loc[d.month == "ALL"].sort_values("window_days")
    assert overall.window_days.tolist() == [1, 7, 30]
    shares = overall.share_payments_with_candidate_touch_pct.to_numpy()
    assert (shares[1:] >= shares[:-1]).all()
    assert d.interpretation.str.contains("NOT ATTRIBUTION OR CAUSAL CREDIT|NO PAYMENT ATTRIBUTION|NO CAUSAL", case=False, regex=True).all()


def test_sql_attempt_frequency_includes_zero_attempt_eligible_accounts():
    sql = (ROOT / "sql/metrics/operational_descriptive_cuts.sql").read_text().lower()
    assert "from golden.account_month_status" in sql
    assert "coalesce(a.attempts,0)" in sql
    assert "where eligible_at_month_start" in sql
