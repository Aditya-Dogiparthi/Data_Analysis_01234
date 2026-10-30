"""Run the full reproducible collections-investigation pipeline."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import pandas as pd
import numpy as np
import json
import hashlib
import platform
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
GOLDEN = ROOT / "data" / "golden"
QUARANTINE = ROOT / "data" / "quarantine"
for folder in (PROCESSED, GOLDEN, QUARANTINE):
    folder.mkdir(parents=True, exist_ok=True)


def read(name: str) -> pd.DataFrame:
    path = RAW / f"{name}.csv"
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def save(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
    # CSV is canonical; Parquet is optional and deliberately best-effort.
    if len(df) <= 50_000:
        try:
            df.to_parquet(path.with_suffix(".parquet"), index=False)
        except (ImportError, ModuleNotFoundError, ValueError):
            pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> dict:
    started_at = datetime.now(timezone.utc)
    import time
    _tick = time.perf_counter()
    def _progress(label: str) -> None:
        nonlocal _tick
        now = time.perf_counter()
        print(f"[pipeline] {label} (+{now - _tick:.1f}s)", flush=True)
        _tick = now
    inventory = []
    for path in sorted(RAW.glob("*.csv")):
        df = pd.read_csv(path, low_memory=False)
        clean = df.drop_duplicates().copy()
        inventory.append({
            "source": path.name, "raw_rows": len(df), "columns": list(df.columns),
            "exact_duplicate_rows": int(df.duplicated().sum()),
            "retained_rows": len(clean),
            "null_cells_pct": round(float(df.isna().mean().mean() * 100), 3),
        })
        save(clean, PROCESSED / f"{path.stem}_deduped.csv")
    _progress("raw inventory, exact deduplication and processed copies")

    raw_pay = read("payments")
    pay_exact = raw_pay.drop_duplicates().copy()
    counts = pay_exact.groupby("payment_id", dropna=False).size()
    conflict_ids = counts[counts > 1].index
    payment_conflicts = pay_exact[pay_exact.payment_id.isin(conflict_ids)].copy()
    save(payment_conflicts, QUARANTINE / "payment_id_conflicts.csv")
    pay = pay_exact[~pay_exact.payment_id.isin(conflict_ids)].copy()
    pay["amount"] = pd.to_numeric(pay["amount"], errors="coerce")
    pay["event_at_parsed"] = pd.to_datetime(pay["event_at"], errors="coerce")
    pay["payment_status_norm"] = pay["payment_status"].astype(str).str.upper().str.strip()
    pay["event_month"] = pay["event_at_parsed"].dt.to_period("M").astype(str)
    pay["gross_success_amount"] = np.where(
        pay.payment_status_norm.eq("SUCCESS"), pay.amount.clip(lower=0), 0.0
    )
    pay["reversal_amount"] = np.where(
        pay.payment_status_norm.eq("REVERSED"), pay.amount.clip(lower=0), 0.0
    )
    save(pay, GOLDEN / "golden_payments.csv")

    source_recon = pd.DataFrame(inventory)
    save(source_recon, PROCESSED / "source_reconciliation.csv")
    summary = {
        "dataset_label": "SYNTHETIC CHALLENGE DATA (seed 42)",
        "raw_source_files": len(inventory),
        "raw_rows_total": int(sum(x["raw_rows"] for x in inventory)),
        "exact_duplicate_rows_removed_across_core_tables": int(sum(x["exact_duplicate_rows"] for x in inventory if x["source"] != "data_dictionary.csv")),
        "payment_exact_duplicate_rows_removed": int(raw_pay.duplicated().sum()),
        "payment_id_conflict_rows_quarantined": int(len(payment_conflicts)),
        "payment_id_conflict_unique_ids": int(payment_conflicts.payment_id.nunique()),
        "golden_payment_rows": int(len(pay)),
        "successful_payment_events": int(pay.payment_status_norm.eq("SUCCESS").sum()),
        "gross_successful_collections": float(pay.gross_success_amount.sum()),
        "reversal_events": int(pay.payment_status_norm.eq("REVERSED").sum()),
        "reversal_amount_reported_separately": float(pay.reversal_amount.sum()),
        "payment_coverage_start": str(pay.event_at_parsed.min()),
        "payment_coverage_end": str(pay.event_at_parsed.max()),
        "timezone_policy": "Preserve source timestamps; do not infer timezone conversion",
    }
    (PROCESSED / "pipeline_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _progress("golden payments and initial reconciliation")

    # Contract validation, the legacy descriptive analyses, then the assignment-specific
    # bitemporal/identity/operational layer. All scripts are synchronous and fail-fast.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_contracts.py")], check=True, cwd=ROOT)
    _progress("contract validation")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "advanced_analysis.py")], check=True, cwd=ROOT)
    _progress("advanced analysis")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_required_analyses.py")], check=True, cwd=ROOT)
    _progress("assignment-specific golden and forensic outputs")

    # Reproducibility/lineage manifest: immutable raw-file hashes plus generated artifact
    # hashes, row counts, runtime versions and the UTC build interval. No source files are changed.
    finished_at = datetime.now(timezone.utc)
    raw_manifest = []
    for item in inventory:
        path = RAW / item["source"]
        raw_manifest.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "rows": int(item["raw_rows"]), "columns": item["columns"],
            "sha256": sha256_file(path),
        })

    def count_csv_rows(path: Path) -> int:
        # Count line-feed bytes in chunks; avoid slow Python text decoding for large extracts.
        newline_count = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                newline_count += chunk.count(b"\n")
        return max(newline_count - 1, 0)

    _progress("raw source hashes")
    artifacts = []
    artifact_roots = [PROCESSED, GOLDEN, QUARANTINE, ROOT / "reports"]
    for folder in artifact_roots:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.csv")):
            artifacts.append({
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "rows": count_csv_rows(path), "bytes": path.stat().st_size, "sha256": sha256_file(path),
            })
    _progress("generated artifact hashes and row counts")
    manifest = {
        "run_id": finished_at.strftime("%Y%m%dT%H%M%SZ"),
        "started_at_utc": started_at.isoformat(), "completed_at_utc": finished_at.isoformat(),
        "dataset_label": "SYNTHETIC CHALLENGE DATA (seed 42)",
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
        "entrypoint": "scripts/run_pipeline.py",
        "code_files": [
            {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(p)}
            for p in [ROOT / "scripts/run_pipeline.py", ROOT / "scripts/validate_contracts.py",
                      ROOT / "scripts/advanced_analysis.py", ROOT / "scripts/build_required_analyses.py"]
        ],
        "sql_files": [
            {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(p)}
            for p in sorted((ROOT / "sql").rglob("*.sql"))
        ],
        "pipeline_steps": ["exact-row-dedup", "payment-key-conflict-quarantine", "contract-validation",
                           "advanced-descriptive-analyses", "bitemporal-account-month-and-forensics",
                           "lineage-manifest"],
        "raw_sources": raw_manifest, "generated_csv_artifacts": artifacts,
        "interpretation_guardrails": [
            "Gross successful cash is not net settled recovery.",
            "Month-start eligible-account panel is incomplete and is not exposure weighted.",
            "Current snapshot dimensions are descriptive, not historical point-in-time attributes.",
            "No causal attribution or ROI is estimated from observational data.",
        ],
    }
    manifest_path = PROCESSED / "pipeline_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    _progress("manifest write")
    summary_path = PROCESSED / "pipeline_summary.json"
    final_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else summary
    final_summary.update({"run_id": manifest["run_id"], "pipeline_completed_at_utc": finished_at.isoformat(),
                          "pipeline_manifest": "data/processed/pipeline_manifest.json"})
    summary_path.write_text(json.dumps(final_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(final_summary, indent=2))
    return final_summary


if __name__ == "__main__":
    main()
