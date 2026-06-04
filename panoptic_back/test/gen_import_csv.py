"""Generate a fake import CSV for load-testing the Importer.

Usage:
    python gen_import_csv.py [N] [X] [--out PATH] [--seed INT]

    N    number of instance rows  (default: 1000)
    X    number of property cols  (default: 10)
    --out output file path        (default: fake_import.csv)
    --seed random seed            (default: 42)

The first column is `id` (values 1..N).
Property columns are distributed across all supported dtypes and named
`PropN[dtype]`.  Tag pools are small so values repeat realistically.
"""

import argparse
import csv
import random
import sys
from datetime import date, timedelta

# ── dtype pool ──────────────────────────────────────────────────────────────

DTYPES = ['text', 'number', 'tag', 'multi_tags', 'url', 'date', 'color', 'checkbox']

TAG_POOL      = [f"tag_{i}" for i in range(20)]
MULTI_TAG_POOL = TAG_POOL
WORDS         = ['alpha','beta','gamma','delta','epsilon','zeta','eta',
                 'theta','iota','kappa','lambda','mu','nu','xi','omicron']
BASE_DATE     = date(2020, 1, 1)

def _text(rng: random.Random) -> str:
    return ' '.join(rng.choices(WORDS, k=rng.randint(1, 4)))

def _number(rng: random.Random) -> str:
    return str(round(rng.uniform(0, 10_000), 2))

def _tag(rng: random.Random) -> str:
    return rng.choice(TAG_POOL)

def _multi_tags(rng: random.Random) -> str:
    k = rng.randint(1, 4)
    return ','.join(rng.sample(MULTI_TAG_POOL, k))

def _url(rng: random.Random) -> str:
    return f"https://example.com/{rng.choice(WORDS)}/{rng.randint(1, 9999)}"

def _date(rng: random.Random) -> str:
    return str(BASE_DATE + timedelta(days=rng.randint(0, 1825)))

def _color(rng: random.Random) -> str:
    return str(rng.randint(0, 11))

def _checkbox(rng: random.Random) -> str:
    return 'True' if rng.random() > 0.5 else ''

GENERATORS = {
    'text':       _text,
    'number':     _number,
    'tag':        _tag,
    'multi_tags': _multi_tags,
    'url':        _url,
    'date':       _date,
    'color':      _color,
    'checkbox':   _checkbox,
}

# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('N', nargs='?', type=int, default=1000,
                   help='number of instance rows (default: 1000)')
    p.add_argument('X', nargs='?', type=int, default=10,
                   help='number of property columns (default: 10)')
    p.add_argument('--out', default='fake_import.csv',
                   help='output file path (default: fake_import.csv)')
    p.add_argument('--seed', type=int, default=42)
    return p.parse_args()

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    N, X = args.N, args.X
    rng  = random.Random(args.seed)

    # Assign dtypes round-robin so every type appears at least once
    dtypes = [DTYPES[i % len(DTYPES)] for i in range(X)]

    # Column headers: first col is 'id', rest are 'PropN[dtype]'
    headers = ['id'] + [f'Prop{i+1}[{dtypes[i]}]' for i in range(X)]

    # Sparse fill rate: ~80 % of cells have a value (realistic)
    fill_rate = 0.8

    print(f"Generating {N} rows × {X} properties → {args.out}")

    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(headers)

        for inst_id in range(1, N + 1):
            row = [str(inst_id)]
            for dtype in dtypes:
                if rng.random() < fill_rate:
                    row.append(GENERATORS[dtype](rng))
                else:
                    row.append('')
            writer.writerow(row)

            if inst_id % 100_000 == 0:
                print(f"  {inst_id:,} / {N:,} rows written…", file=sys.stderr)

    print(f"Done. {N:,} rows, {X} properties.")

if __name__ == '__main__':
    main()
