from pathlib import Path
import shutil, argparse
ROOT=Path(__file__).resolve().parents[1]
def ingest(source_dir):
    src=Path(source_dir)
    target=ROOT/'data'/'raw'
    target.mkdir(parents=True,exist_ok=True)
    copied=[]
    for p in src.glob('*'):
        if p.suffix.lower() in {'.csv','.xlsx','.parquet'}:
            shutil.copy2(p,target/p.name); copied.append(p.name)
    print(f'Copied {len(copied)} source files into {target}')
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dir',required=True)
    ingest(ap.parse_args().source_dir)
