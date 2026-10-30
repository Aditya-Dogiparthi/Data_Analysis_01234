"""Append-only CSV landing into PostgreSQL raw schema using batch + row hashes.

Requires psycopg 3 and environment variables from .env. Raw CSVs remain unchanged.
"""
from pathlib import Path
import os, hashlib, json, csv, io
from dotenv import load_dotenv
import pandas as pd
import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/".env")
RAW=ROOT/"data"/"raw"

def main():
    conn=psycopg.connect(
        host=os.getenv("POSTGRES_HOST","localhost"),
        port=os.getenv("POSTGRES_PORT","5433"),
        dbname=os.getenv("POSTGRES_DB","collections"),
        user=os.getenv("POSTGRES_USER","collections_admin"),
        password=os.getenv("POSTGRES_PASSWORD","change_me")
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            for path in sorted(RAW.glob("*.csv")):
                if path.name=="data_dictionary.csv":
                    table="data_dictionary"
                else:
                    table=path.stem.lower()
                file_hash=hashlib.sha256(path.read_bytes()).hexdigest()
                df=pd.read_csv(path,dtype=str,keep_default_na=False)
                cols=[str(c) for c in df.columns]
                # Source columns and ingestion metadata are text to preserve raw values.
                col_defs=[sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in cols]
                col_defs += [sql.SQL("_source_file TEXT"),sql.SQL("_batch_hash TEXT"),
                             sql.SQL("_source_row_number BIGINT"),sql.SQL("_row_hash TEXT")]
                cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS raw.{} ({}, PRIMARY KEY (_row_hash))")
                            .format(sql.Identifier(table),sql.SQL(",").join(col_defs)))
                for c in cols:
                    cur.execute(sql.SQL("ALTER TABLE raw.{} ADD COLUMN IF NOT EXISTS {} TEXT")
                                .format(sql.Identifier(table),sql.Identifier(c)))
                cur.execute(sql.SQL("ALTER TABLE raw.{} ADD COLUMN IF NOT EXISTS _source_file TEXT").format(sql.Identifier(table)))
                cur.execute(sql.SQL("ALTER TABLE raw.{} ADD COLUMN IF NOT EXISTS _batch_hash TEXT").format(sql.Identifier(table)))
                cur.execute(sql.SQL("ALTER TABLE raw.{} ADD COLUMN IF NOT EXISTS _source_row_number BIGINT").format(sql.Identifier(table)))
                cur.execute(sql.SQL("ALTER TABLE raw.{} ADD COLUMN IF NOT EXISTS _row_hash TEXT").format(sql.Identifier(table)))
                temp="tmp_"+table
                cur.execute(sql.SQL("CREATE TEMP TABLE {} (LIKE raw.{} INCLUDING DEFAULTS) ON COMMIT DROP")
                            .format(sql.Identifier(temp),sql.Identifier(table)))
                buffer=io.StringIO()
                writer=csv.writer(buffer,lineterminator="\n")
                all_cols=cols+["_source_file","_batch_hash","_source_row_number","_row_hash"]
                writer.writerow(all_cols)
                for i,row in enumerate(df.itertuples(index=False,name=None),start=1):
                    values=[str(v) for v in row]
                    payload=json.dumps(values,ensure_ascii=False,separators=(",",":"))
                    row_hash=hashlib.sha256(f"{file_hash}:{i}:{payload}".encode()).hexdigest()
                    writer.writerow(values+[path.name,file_hash,i,row_hash])
                buffer.seek(0)
                copy_cols=sql.SQL(",").join(map(sql.Identifier,all_cols))
                with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
                    sql.Identifier(temp),copy_cols)) as cp:
                    cp.write(buffer.getvalue())
                cur.execute(sql.SQL("INSERT INTO raw.{} ({}) SELECT {} FROM {} ON CONFLICT (_row_hash) DO NOTHING").format(
                    sql.Identifier(table),copy_cols,copy_cols,sql.Identifier(temp)))
                print(f"{path.name}: {len(df):,} source rows staged; batch {file_hash[:12]}")
    conn.close()

if __name__=="__main__":
    main()
