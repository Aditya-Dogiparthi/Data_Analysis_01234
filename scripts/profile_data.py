from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

def profile():
    rows = []
    for path in sorted(RAW.glob("*.csv")):
        if path.name == "data_dictionary.csv":
            pass
        df = pd.read_csv(path, low_memory=False)
        date_cols = [c for c in df.columns if c.lower().endswith(("_at", "_date"))]
        ranges = {}
        for col in date_cols:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().any():
                ranges[col] = {"min": str(parsed.min()), "max": str(parsed.max()),
                               "unparseable": int(df[col].notna().sum() - parsed.notna().sum())}
        rows.append({
            "source": path.name, "rows": int(len(df)), "columns": int(len(df.columns)),
            "column_names": list(df.columns),
            "null_cells_pct": round(float(df.isna().mean().mean() * 100), 3),
            "duplicate_full_rows": int(df.duplicated().sum()),
            "date_ranges": ranges
        })
    result = {"profiled_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "sources": rows}
    (OUT / "data_inventory.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    pd.DataFrame([{k:v for k,v in x.items() if k not in ("column_names","date_ranges")} for x in rows]).to_csv(
        OUT / "data_inventory.csv", index=False)
    return result

if __name__ == "__main__":
    report = profile()
    print(f"Profiled {len(report['sources'])} CSV sources.")
