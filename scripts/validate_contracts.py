"""Validate the raw-source schema contracts and emit key/status diagnostics.

Stable source IDs may legitimately repeat in versioned dimensions and may be
conflicting event keys that the golden builder quarantines. Those are reported,
not silently treated as schema failures.
"""
from pathlib import Path
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "contract_validation.csv"


def main() -> pd.DataFrame:
    config = yaml.safe_load((ROOT / "config" / "data_contracts.yml").read_text(encoding="utf-8"))
    records = []
    for name, spec in config.get("contracts", {}).items():
        path = RAW / f"{name}.csv"
        if not path.exists():
            records.append({"source": name, "schema_status": "MISSING_FILE", "status": "FAIL",
                            "missing_columns": name, "primary_key": spec.get("primary_key"),
                            "key_duplicate_rows": None, "null_key_rows": None,
                            "invalid_status_values": None, "negative_amount_rows": None})
            continue
        header = pd.read_csv(path, low_memory=False, nrows=0)
        missing = sorted(set(spec.get("required", [])) - set(header.columns))
        key = spec.get("primary_key")
        duplicate_rows = null_key_rows = invalid_status = negative_amount = None
        if key and key in header.columns:
            key_col = pd.read_csv(path, usecols=[key], low_memory=False)[key]
            duplicate_rows = int(key_col.duplicated(keep="first").sum())
            null_key_rows = int(key_col.isna().sum())
        allowed = spec.get("allowed_statuses")
        status_col = spec.get("status_column", "payment_status")
        if allowed and status_col in header.columns:
            values = pd.read_csv(path, usecols=[status_col], low_memory=False)[status_col]
            invalid_status = int((~values.astype(str).str.upper().str.strip().isin(allowed)).sum())
        if spec.get("non_negative_amount_for_gross"):
            amounts = pd.read_csv(path, usecols=["amount"], low_memory=False)["amount"]
            negative_amount = int((pd.to_numeric(amounts, errors="coerce") < 0).sum())
        records.append({
            "source": name,
            "schema_status": "PASS" if not missing else "MISSING_COLUMNS",
            "status": "PASS" if not missing else "FAIL",
            "missing_columns": ";".join(missing),
            "primary_key": key,
            "key_duplicate_rows": duplicate_rows,
            "null_key_rows": null_key_rows,
            "invalid_status_values": invalid_status,
            "negative_amount_rows": negative_amount,
        })
    result = pd.DataFrame(records)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result.to_string(index=False))
    if (result.status != "PASS").any():
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
