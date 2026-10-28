"""Column load benchmark — Python side. Times today's routes on a real data.db: the backend
code is imported as is, only `Project` is stubbed (the routes use `get_properties` and
`_data_reader`).

- `route`: `get_property_column(prop_id)` (/instances/column/{id}) and `stream_instances_base`
  (/instances/base), their whole response body iterated as Starlette does it (sync generator
  in the threadpool), so SQLite read + per-row Python lists + msgspec/orjson encode. Not HTTP.
- `sqlite`: the route's query alone through the same reader, rows fetched in 10k batches.
- `reader/open`: opening + closing a `DataReader` (connect, pragmas, WAL checkpoint), which every
  route call and every `sqlite` timing pays once.

    panoptic_back/.venv/bin/python py/column_load.py --create=<data.db>   schema-only data.db
    panoptic_back/.venv/bin/python py/column_load.py --db=<data.db> [--dump=<dir>] [--reps=5]

`--dump` writes each route's body to <dir>/stream-<name>.ndjson with a manifest, so
js/wire.js can time the front's ingest of exactly these bytes.
"""
import asyncio
import json
import sys
import time

import msgspec


def arg(name, default=None):
    p = f'--{name}='
    return next((a[len(p):] for a in sys.argv[1:] if a.startswith(p)), default)


if arg('create'):
    from panoptic.core.databases.data.data_writer import DataWriter
    with DataWriter(arg('create')):
        pass
    sys.exit(0)

from panoptic.core.databases.data.data_reader import DataReader  # noqa: E402
from panoptic.routes.project_routes import get_property_column, stream_instances_base  # noqa: E402

DB = arg('db')
DUMP = arg('dump')
ONLY = arg('only')
# front column kind per dtype, as wire.js / columnStore name them
KIND = {'text': 'string', 'number': 'numeric', 'date': 'date', 'checkbox': 'bool', 'multi_tags': 'tag', 'tag': 'tag'}


class StubProject:
    def get_properties(self):
        with DataReader(DB) as r:
            return r.get_properties()

    def _data_reader(self):
        return DataReader(DB)


PROJECT = StubProject()


async def drain(resp):
    return [chunk async for chunk in resp.body_iterator]


def body(route, *a):
    return b''.join(asyncio.run(drain(route(*a, project=PROJECT))))


def timed(reps, f):
    out = f()  # warmup
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        out = f()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return out, {'ms': round(times[len(times) // 2], 3), 'min_ms': round(times[0], 3), 'reps': reps}


def scan(sql, params=()):
    with DataReader(DB) as r:
        cur = r.conn.execute(sql, params)
        rows = 0
        while batch := cur.fetchmany(10_000):
            rows += len(batch)
        return rows


def emit(n, op, variant, t, **extra):
    print(json.dumps({'impl': 'python', 'kind': 'load', 'n': n, 'op': op, 'variant': variant, **t, **extra}), flush=True)


def stream_stats(raw):
    """(lines, value rows, distinct instance ids) of a column stream."""
    dec = msgspec.json.Decoder()
    lines = [dec.decode(l) for l in raw.split(b'\n') if l]
    ids = [i for l in lines for c in l['instance_values'] for i in c['ids']]
    return len(lines), len(ids), len(set(ids))


def main():
    with DataReader(DB) as r:
        n = r.conn.execute('SELECT COUNT(*) FROM instances').fetchone()[0]
    reps = int(arg('reps', 3 if n >= 5_000_000 else 5))
    manifest = []

    def open_close():
        with DataReader(DB):
            pass
    _, t = timed(reps, open_close)
    emit(n, 'reader', 'open', t)

    raw, t = timed(reps, lambda: body(stream_instances_base))
    emit(n, 'base', 'route', t, bytes=len(raw))
    rows, t = timed(reps, lambda: scan('SELECT id, sha1, file_id FROM instances'))
    emit(n, 'base', 'sqlite', t, rows=rows)

    props = [p for p in PROJECT.get_properties() if not p.system_key]
    for p in props:
        if ONLY and ONLY not in p.name:
            continue
        is_tag = p.dtype in ('tag', 'multi_tags')
        sql = ('SELECT instance_id, tag_id FROM instance_tag_values WHERE property_id = ? AND operation = 1' if is_tag
               else 'SELECT instance_id, value FROM instance_values WHERE property_id = ?')
        rows, t = timed(reps, lambda: scan(sql, (p.id,)))
        emit(n, p.name, 'sqlite', t, rows=rows)

        raw, t = timed(reps, lambda: body(get_property_column, p.id))
        lines, ids, distinct = stream_stats(raw)
        emit(n, p.name, 'route', t, bytes=len(raw), lines=lines, ids=ids, distinct_ids=distinct)
        if DUMP:
            f = f'stream-{p.name}.ndjson'
            with open(f'{DUMP}/{f}', 'wb') as out:
                out.write(raw)
            manifest.append({'group': 'stream', 'op': p.name, 'fmt': 'ndjson', 'file': f, 'bytes': len(raw),
                             'prop': p.id, 'col_kind': KIND.get(p.dtype, 'string'), 'lines': lines})
    if DUMP:
        with open(f'{DUMP}/manifest.json', 'w') as out:
            json.dump({'n': n, 'files': manifest}, out)


main()
