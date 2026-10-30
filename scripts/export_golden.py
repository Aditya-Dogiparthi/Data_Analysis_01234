from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'data'/'golden').glob('*.csv'):
    print(f'{p.name}: {p.stat().st_size:,} bytes')
