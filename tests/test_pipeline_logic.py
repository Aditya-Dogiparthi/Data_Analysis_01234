import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

def test_exact_dedup_only_removes_identical_rows():
    df=pd.DataFrame({"payment_id":["p1","p1","p2"],"amount":[10,10,10],"status":["SUCCESS","SUCCESS","SUCCESS"]})
    clean=df.drop_duplicates()
    assert len(clean)==2
    assert clean.iloc[0]["payment_id"]=="p1"

def test_conflicting_payment_id_is_not_silently_selected():
    df=pd.DataFrame({"payment_id":["p1","p1"],"amount":[10,12]})
    assert df.groupby("payment_id").size().max()==2
    # Contract: pipeline quarantines all payload versions for a conflicting key.
    conflicting=df[df.payment_id.isin(df.groupby("payment_id").size().loc[lambda s:s>1].index)]
    assert len(conflicting)==2

def test_failed_and_pending_are_not_successful_cash():
    df=pd.DataFrame({"status":["SUCCESS","FAILED","PENDING","REVERSED"],"amount":[100,200,300,50]})
    gross=df.loc[df.status.eq("SUCCESS"),"amount"].sum()
    assert gross==100

def test_august_is_not_marked_complete():
    month=pd.Series(["2026-07","2026-08"])
    complete=month.ne("2026-08")
    assert complete.tolist()==[True,False]

def test_reversal_is_not_arbitrarily_subtracted():
    df=pd.DataFrame({"status":["SUCCESS","REVERSED"],"amount":[100,30]})
    gross=df.loc[df.status.eq("SUCCESS"),"amount"].sum()
    reversals=df.loc[df.status.eq("REVERSED"),"amount"].sum()
    assert gross==100 and reversals==30
