"""Convert an export CSV (local_path;sha1[sha1]) into an import-ready CSV.

The export's `local_path` column becomes the `path` key column (the only
path-based key the importer accepts).  Four property columns with fake data
are appended.

Usage:
    python export_to_import.py <export.csv> [--out import.csv] [--seed 42]
"""

import argparse
import csv
import random
from datetime import date, timedelta

# ── fake data helpers ───────────────────────────────────────────────────────

TAG_POOL  = [f"tag_{i}" for i in range(20)]
WORDS     = ['alpha','beta','gamma','delta','epsilon','zeta','eta',
             'theta','iota','kappa','lambda','mu','nu','xi','omicron']
BASE_DATE = date(2020, 1, 1)

PROPS = [
    ('Label',       'text'),
    ('Score',       'number'),
    ('Category',    'tag'),
    ('Keywords',    'multi_tags'),
]

def _fake(dtype: str, rng: random.Random) -> str:
    if dtype == 'text':
        return ' '.join(rng.choices(WORDS, k=rng.randint(1, 4)))
    if dtype == 'number':
        return str(round(rng.uniform(0, 10_000), 2))
    if dtype == 'tag':
        return rng.choice(TAG_POOL)
    if dtype == 'multi_tags':
        return ','.join(rng.sample(TAG_POOL, rng.randint(1, 4)))
    if dtype == 'date':
        return str(BASE_DATE + timedelta(days=rng.randint(0, 1825)))
    return ''

# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input', help='export CSV file')
    p.add_argument('--out', default=None, help='output path (default: <input>_import.csv)')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--fill-rate', type=float, default=0.85,
                   help='fraction of cells that get a value (default: 0.85)')
    return p.parse_args()

# ── main ────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    rng  = random.Random(args.seed)

    out_path = args.out or args.input.replace('.csv', '_import.csv')
    if out_path == args.input:
        out_path = args.input + '_import.csv'

    prop_headers = [f'{name}[{dtype}]' for name, dtype in PROPS]

    rows_in = []
    with open(args.input, newline='', encoding='utf-8') as fin:
        reader = csv.DictReader(fin, delimiter=';')
        src_key = None
        for field in (reader.fieldnames or []):
            if field in ('local_path', 'path', 'id'):
                src_key = field
                break
        if src_key is None:
            raise SystemExit(f"No recognised key column (local_path/path/id) in {args.input}")
        for row in reader:
            rows_in.append(row[src_key])

    print(f"Read {len(rows_in)} rows from {args.input} (key='{src_key}')")

    with open(out_path, 'w', newline='', encoding='utf-8') as fout:
        writer = csv.writer(fout, delimiter=';')
        writer.writerow(['path'] + prop_headers)
        for path_val in rows_in:
            row = [path_val]
            for _, dtype in PROPS:
                row.append(_fake(dtype, rng) if rng.random() < args.fill_rate else '')
            writer.writerow(row)

    print(f"Written {len(rows_in)} rows → {out_path}")
    print(f"Columns: path | {' | '.join(prop_headers)}")

if __name__ == '__main__':
    main()
