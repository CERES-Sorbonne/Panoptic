"""Wire benchmark — today's Python encoder. Re-encodes the column streams `collection-bench
--wire=<dir>` wrote, with the same msgspec structs as panoptic/models/stream_models.py
(copied here so the script runs on msgspec alone).

Only `msgspec.json.encode` of each line is timed: the batches are decoded into structs first,
so the SQLite read and the Python list building of get_property_column are left out (a lower
bound of what the route spends).

    panoptic_back/.venv/bin/python py/stream_encode.py --dir=results/wire-1000000
"""
import json
import sys
import time
from typing import Optional

import msgspec


class LoadState(msgspec.Struct):
    finished_property: bool = False
    finished_instance: bool = False
    finished_tags: bool = False
    finished_instance_values: bool = False
    finished_image_values: bool = False
    finished_file_values: bool = False
    finished_property_groups: bool = False
    counter_instance: int = 0
    counter_instance_value: int = 0
    counter_image_value: int = 0
    counter_file_value: int = 0
    max_instance: int = 0
    max_instance_value: int = 0
    max_image_value: int = 0
    max_file_value: int = 0
    max_sequence: int = 0


class InstanceValuesColumn(msgspec.Struct):
    property_id: int
    ids: list[int]
    values: list[str]


class StreamResult(msgspec.Struct, omit_defaults=True):
    state: LoadState
    chunk: Optional[dict] = None
    instance_values: Optional[list[InstanceValuesColumn]] = None


def arg(name, default=None):
    p = f'--{name}='
    return next((a[len(p):] for a in sys.argv[1:] if a.startswith(p)), default)


def main():
    d = arg('dir')
    manifest = json.load(open(f'{d}/manifest.json'))
    n = manifest['n']
    reps = 2 if n >= 5_000_000 else 3
    dec = msgspec.json.Decoder(StreamResult)
    for e in manifest['files']:
        if e['group'] != 'stream':
            continue
        with open(f"{d}/{e['file']}", 'rb') as f:
            raw = f.read()
        lines = [dec.decode(l) for l in raw.split(b'\n') if l]
        times, size = [], 0
        for r in range(reps + 1):
            t0 = time.perf_counter()
            size = sum(len(msgspec.json.encode(l) + b'\n') for l in lines)
            if r:
                times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        print(json.dumps({'impl': 'python', 'kind': 'wire', 'n': n, 'group': 'stream', 'op': e['op'],
                          'fmt': 'ndjson', 'lib': 'msgspec', 'same_bytes': size == e['bytes'],
                          'ms': times[len(times) // 2], 'min_ms': times[0], 'reps': reps}))


main()
