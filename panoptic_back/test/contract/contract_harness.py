"""Implementation-agnostic contract harness for the Panoptic HTTP + socket.io API.

Everything here talks to a server over the network only (httpx + python-socketio client);
nothing imports the panoptic package, so the same suite runs against the Python reference
backend and the Rust port.

Pieces:
- ``make_fixture_images``: deterministic image set (PNG + JPEG, exact duplicates, nested folders)
- ``ServerProcess``: starts a backend subprocess on a free port with an isolated HOME / db
- ``Api``: thin httpx wrapper mirroring how the frontend calls the backend
  (``connection_id`` / ``user_id`` query params, ``/projects/{id}`` prefix)
- ``SocketRecorder``: socket.io client recording every event, with ``wait_for``
- ``Normalizer`` + ``Golden``: placeholder substitution and golden JSON record / compare
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx
import socketio

# ---------------------------------------------------------------------------
# Fixture images
# ---------------------------------------------------------------------------

#: fixed mtime of every fixture file (2024-01-02 03:04:05 UTC) -> deterministic File.created_at
FIXTURE_MTIME = 1704164645

# (relative path, format, width, height) of the unique images
_UNIQUE = (
    [(f'a/img_a{i:02d}.{"png" if i % 2 == 0 else "jpg"}', 'PNG' if i % 2 == 0 else 'JPEG',
      48 + 8 * i, 40 + 4 * (i % 5)) for i in range(12)]
    + [(f'b/img_b{i:02d}.{"jpg" if i % 3 == 0 else "png"}', 'JPEG' if i % 3 == 0 else 'PNG',
        64 + 4 * (i % 4), 32 + 8 * i) for i in range(11)]
    + [(f'b/deep/img_d{i:02d}.png', 'PNG', 50, 50 + 10 * i) for i in range(4)]
)
# (copy, original): byte-identical duplicates -> same sha1, different files / instances
_DUPLICATES = [
    ('b/copy_of_a00.png', 'a/img_a00.png'),
    ('a/img_a05_copy.jpg', 'a/img_a05.jpg'),
    ('b/deep/img_b03.jpg', 'b/img_b03.jpg'),
]


def make_fixture_images(root: Path) -> dict:
    """Write 30 images (27 unique + 3 exact duplicates) under root/{a,b,b/deep} plus one
    non-image file. Returns {'files': {relpath: sha1}, 'sha1_to_paths': {sha1: [relpaths]}}."""
    from PIL import Image, ImageDraw

    root.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    for idx, (rel, fmt, w, h) in enumerate(_UNIQUE):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new('RGB', (w, h), ((37 * idx) % 256, (91 * idx) % 256, (53 * idx + 120) % 256))
        draw = ImageDraw.Draw(img)
        draw.rectangle([idx % w, idx % h, min(w - 1, idx % w + w // 3), min(h - 1, idx % h + h // 3)],
                       fill=((200 + idx) % 256, (17 * idx) % 256, (5 * idx) % 256))
        draw.line([0, h - 1, w - 1, 0], fill=(255 - idx, 255, idx), width=2)
        if fmt == 'JPEG':
            img.save(path, format='JPEG', quality=90)
        else:
            img.save(path, format='PNG')
    for copy, orig in _DUPLICATES:
        (root / copy).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / orig, root / copy)
    (root / 'a' / 'notes.txt').write_text('not an image\n')

    for path in sorted(root.rglob('*')):
        if path.is_file():
            os.utime(path, (FIXTURE_MTIME, FIXTURE_MTIME))
            if path.suffix.lower() in ('.png', '.jpg'):
                files[path.relative_to(root).as_posix()] = hashlib.sha1(path.read_bytes()).hexdigest()
    sha1_to_paths: dict[str, list[str]] = {}
    for rel, sha1 in sorted(files.items()):
        sha1_to_paths.setdefault(sha1, []).append(rel)
    return {'files': files, 'sha1_to_paths': sha1_to_paths}


# ---------------------------------------------------------------------------
# Server process
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]          # panoptic_back/
DEFAULT_CMD = '{python} -m panoptic.cli --db {db}'


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class ServerProcess:
    """Runs the backend as a subprocess.

    The command is ``PANOPTIC_CONTRACT_CMD`` (default ``DEFAULT_CMD``), a template formatted
    with {python} {port} {db} {home} {tmp}. The environment always carries the same values
    (PANOPTIC_PORT, PANOPTIC_DB, PANOPTIC_HOST=127.0.0.1, HOME, PANOPTIC_REMOTE=1 — no browser,
    PANOPTIC_NO_LEGACY_SCAN=1, TZ=UTC) so a server that reads env instead of flags works too.
    ``open`` / ``xdg-open`` are shimmed to no-ops on PATH (the python /export route reveals the
    export folder in the file manager).
    """

    def __init__(self, tmp: Path, cmd_template: str | None = None, log_path: Path | None = None):
        self.tmp = tmp
        self.cmd_template = cmd_template or os.environ.get('PANOPTIC_CONTRACT_CMD') or DEFAULT_CMD
        self.port = free_port()
        self.home = tmp / 'home'
        self.db = tmp / 'panoptic_home' / 'panoptic.db'
        self.log_path = log_path or tmp / 'server.log'
        self.proc: subprocess.Popen | None = None
        self._log = None

    @property
    def url(self) -> str:
        return f'http://127.0.0.1:{self.port}'

    def start(self, timeout: float = 90.0) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        shim = self.tmp / 'shim_bin'
        shim.mkdir(exist_ok=True)
        for name in ('open', 'xdg-open'):
            p = shim / name
            p.write_text('#!/bin/sh\nexit 0\n')
            p.chmod(0o755)

        cmd = self.cmd_template.format(python=shlex.quote(sys.executable), port=self.port,
                                       db=shlex.quote(str(self.db)), home=shlex.quote(str(self.home)),
                                       tmp=shlex.quote(str(self.tmp)))
        env = {k: v for k, v in os.environ.items() if not k.startswith('PANOPTIC_')}
        env.update({
            'HOME': str(self.home),
            'USERPROFILE': str(self.home),
            'PANOPTIC_PORT': str(self.port),
            'PANOPTIC_HOST': '127.0.0.1',
            'PANOPTIC_DB': str(self.db),
            'PANOPTIC_REMOTE': '1',
            'PANOPTIC_NO_LEGACY_SCAN': '1',
            'TZ': 'UTC',
            'PATH': str(shim) + os.pathsep + env.get('PATH', ''),
            'PYTHONUNBUFFERED': '1',
        })
        self._log = open(self.log_path, 'wb')
        self.proc = subprocess.Popen(cmd, shell=True, cwd=str(BACKEND_DIR), env=env,
                                     stdout=self._log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f'server exited with {self.proc.returncode}, log:\n{self.log_tail()}')
            try:
                if httpx.get(self.url + '/version', timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        self.stop()
        raise RuntimeError(f'server did not answer on {self.url} within {timeout}s, log:\n{self.log_tail()}')

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(5)
        if self._log:
            self._log.close()
            self._log = None

    def log_tail(self, n: int = 60) -> str:
        try:
            return '\n'.join(self.log_path.read_text(errors='replace').splitlines()[-n:])
        except OSError:
            return ''


# ---------------------------------------------------------------------------
# HTTP client mirroring the frontend
# ---------------------------------------------------------------------------

class Api:
    def __init__(self, base_url: str, connection_id: str):
        self.base_url = base_url.rstrip('/')
        self.http = httpx.Client(base_url=self.base_url, timeout=60)
        self.connection_id = connection_id
        self.user_id = 'default'
        self.project_id: str | None = None

    def close(self):
        self.http.close()

    # panoptic-level routes: ?connection_id=  (panopticApi.ts interceptor)
    def _params(self, params: dict | None, project: bool) -> dict:
        out = {'connection_id': self.connection_id}
        if project and self.user_id:
            out['user_id'] = self.user_id
        out.update(params or {})
        return out

    def request(self, method: str, path: str, *, project: bool = False, params: dict | None = None,
                **kw) -> httpx.Response:
        if project:
            assert self.project_id, 'no project loaded'
            path = f'/projects/{self.project_id}{path}'
        return self.http.request(method, path, params=self._params(params, project), **kw)

    def get(self, path, **kw):
        return self.request('GET', path, **kw)

    def post(self, path, **kw):
        return self.request('POST', path, **kw)

    def put(self, path, **kw):
        return self.request('PUT', path, **kw)

    def delete(self, path, **kw):
        return self.request('DELETE', path, **kw)

    # project-level shortcuts
    def pget(self, path, **kw):
        return self.request('GET', path, project=True, **kw)

    def ppost(self, path, **kw):
        return self.request('POST', path, project=True, **kw)

    def pput(self, path, **kw):
        return self.request('PUT', path, project=True, **kw)

    def pdelete(self, path, **kw):
        return self.request('DELETE', path, project=True, **kw)

    def stream_ndjson(self, path: str, project: bool = True) -> tuple[httpx.Response, list, bytes]:
        """GET an NDJSON stream the way the frontend does (plain fetch, no query params)."""
        if project:
            path = f'/projects/{self.project_id}{path}'
        lines = []
        with self.http.stream('GET', path) as r:
            body = b''.join(r.iter_bytes())
        for raw in body.split(b'\n'):
            if raw.strip():
                lines.append(json.loads(raw))
        return r, lines, body


# ---------------------------------------------------------------------------
# socket.io recorder
# ---------------------------------------------------------------------------

class SocketRecorder:
    """Records every server->client event as (index, name, payload)."""

    def __init__(self, url: str, connection_id: str | None):
        self.url = url
        self.connection_id = connection_id
        self.events: list[tuple[int, str, Any]] = []
        self._cond = threading.Condition()
        self.sio = socketio.Client(reconnection=False)

        @self.sio.on('*')
        def _catch_all(event, *args):
            payload = args[0] if len(args) == 1 else (list(args) if args else None)
            with self._cond:
                self.events.append((len(self.events), event, payload))
                self._cond.notify_all()

    def connect(self, timeout: float = 15):
        auth = {'connection_id': self.connection_id} if self.connection_id else {}
        self.sio.connect(self.url, transports=['websocket'], auth=auth, socketio_path='socket.io',
                         wait_timeout=timeout)

    def disconnect(self):
        if self.sio.connected:
            self.sio.disconnect()

    def emit(self, event: str, data: Any = None):
        self.sio.emit(event, data)

    def mark(self) -> int:
        with self._cond:
            return len(self.events)

    def since(self, mark: int, name: str | None = None) -> list[tuple[int, str, Any]]:
        with self._cond:
            evs = self.events[mark:]
        return [e for e in evs if name is None or e[1] == name]

    def wait_for(self, name: str, pred: Callable[[Any], bool] | None = None, *, since: int = 0,
                 timeout: float = 30) -> Any:
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for _, ev, payload in self.events[since:]:
                    if ev == name and (pred is None or pred(payload)):
                        return payload
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    seen = [e[1] for e in self.events[since:]]
                    raise TimeoutError(f'no {name!r} event matching within {timeout}s; got {seen}')
                self._cond.wait(remaining)

    def quiet(self, period: float = 0.6, timeout: float = 15) -> None:
        """Wait until no event arrived for `period` seconds."""
        deadline = time.monotonic() + timeout
        last = self.mark()
        while time.monotonic() < deadline:
            time.sleep(period)
            now = self.mark()
            if now == last:
                return
            last = now


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

UUID_RE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
HEX32_RE = re.compile(r'\b[0-9a-f]{32}\b')

#: keys whose (non-null) value is time-dependent
VOLATILE_KEYS = {'timestamp', 'started_at', 'elapsed', 'rate', 'eta_seconds', 'last_synced_at',
                 'connected_at', 'migrated_at'}


class Normalizer:
    """Turns a response into a stable, implementation-agnostic JSON value.

    - temp paths -> <TMP>, <IMAGES>, <PROJECT>  (realpath variants too: macOS /private/var)
    - registered values (project id, user ids, ...) -> their placeholder
    - remaining UUIDs -> <uuid>
    - fixture sha1s -> <sha1:first/relative/path.png>  (also as dict keys)
    - VOLATILE_KEYS values -> <volatile>
    Instance / file ids are NOT deterministic in the python backend (parallel import, ids
    allocated in completion order), so tests map them with ``inst()`` / ``file()`` to
    <inst:relpath> / <file:relpath> using the maps built after import.
    """

    def __init__(self):
        self.path_subs: list[tuple[str, str]] = []
        self.values: dict[str, str] = {}
        self.sha1: dict[str, str] = {}
        self.inst_map: dict[int, str] = {}
        self.file_map: dict[int, str] = {}

    def add_path(self, path: Path | str, placeholder: str):
        for p in {str(path), os.path.realpath(str(path))}:
            self.path_subs.append((p, placeholder))
        # longest first so <IMAGES> wins over <TMP>
        self.path_subs.sort(key=lambda x: -len(x[0]))

    def register(self, value: str, placeholder: str):
        if value:
            self.values[value] = placeholder

    def set_sha1s(self, sha1_to_paths: dict[str, list[str]]):
        self.sha1 = {s: f'<sha1:{paths[0]}>' for s, paths in sha1_to_paths.items()}

    def inst(self, i):
        return self.inst_map.get(i, f'<inst:?{i}>') if isinstance(i, int) else i

    def file(self, i):
        return self.file_map.get(i, f'<file:?{i}>') if isinstance(i, int) else i

    def _str(self, s: str) -> str:
        if s in self.values:
            return self.values[s]
        if s in self.sha1:
            return self.sha1[s]
        if len(s) == 42 and s[0] == s[-1] == '"' and s[1:-1] in self.sha1:   # JSON-encoded sha1
            return f'"{self.sha1[s[1:-1]]}"'
        for p, ph in self.path_subs:
            if p in s:
                s = s.replace(p, ph)
        for v, ph in self.values.items():
            if len(v) >= 8 and v in s:
                s = s.replace(v, ph)
        s = UUID_RE.sub('<uuid>', s)
        return s

    def __call__(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                nk = self._str(k) if isinstance(k, str) else k
                if k in VOLATILE_KEYS and v is not None:
                    out[nk] = '<volatile>'
                else:
                    out[nk] = self(v)
            return out
        if isinstance(obj, (list, tuple)):
            return [self(v) for v in obj]
        if isinstance(obj, str):
            return self._str(obj)
        if isinstance(obj, float) and obj.is_integer():
            return obj  # keep floats as floats (json distinguishes 1 and 1.0 for us)
        return obj


def sort_key(v: Any) -> str:
    return json.dumps(v, sort_keys=True)


def sorted_list(items: Iterable, key: Callable | None = None) -> list:
    return sorted(items, key=key or sort_key)


# ---------------------------------------------------------------------------
# Golden files
# ---------------------------------------------------------------------------

class GoldenMismatch(AssertionError):
    pass


class Golden:
    def __init__(self, directory: Path, record: bool):
        self.dir = directory
        self.record = record
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.dir / f'{name}.json'

    @staticmethod
    def dumps(obj: Any) -> str:
        return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + '\n'

    def check(self, name: str, data: Any) -> None:
        text = self.dumps(data)
        path = self.path(name)
        if self.record:
            path.write_text(text, encoding='utf-8')
            return
        if not path.exists():
            raise GoldenMismatch(f'golden {path.name} missing — run with --record against the python backend')
        expected = path.read_text(encoding='utf-8')
        if expected != text:
            diff = ''.join(difflib.unified_diff(
                expected.splitlines(True), text.splitlines(True),
                fromfile=f'golden/{path.name}', tofile='actual', n=3))
            raise GoldenMismatch(f'response differs from golden {path.name}:\n{diff[:12000]}')
