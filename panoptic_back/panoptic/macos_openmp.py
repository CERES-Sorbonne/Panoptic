"""Make every library share torch's OpenMP runtime on macOS.

torch, faiss-cpu and scikit-learn macOS wheels each bundle their own libomp.dylib,
so plugins importing several of them load 2-3 OpenMP runtimes in one process and
crash (segfault / OMP Error #15). With DYLD_LIBRARY_PATH pointing at torch/lib, dyld
resolves every libomp.dylib to torch's copy. dyld only reads it at process start,
so we re-exec the interpreter once with it set. Must run before torch/faiss load.

The torch/lib dirs don't need to exist yet: dyld searches them on every later
dlopen, so it also works when a plugin installs torch while Panoptic is running.
"""
import os
import site
import sys
import sysconfig
from importlib.util import find_spec

_MARKER = 'PANOPTIC_OPENMP_FIXED'


def _torch_lib_dirs():
    dirs = [sysconfig.get_paths()['purelib'], site.getusersitepackages()]
    dirs = [os.path.join(d, 'torch', 'lib') for d in dirs]
    try:
        spec = find_spec('torch')  # already installed elsewhere (PYTHONPATH, ...)
    except (ImportError, ValueError):
        spec = None
    if spec is not None and spec.origin:
        dirs.insert(0, os.path.join(os.path.dirname(spec.origin), 'lib'))
    return list(dict.fromkeys(dirs))


def ensure_single_openmp():
    if sys.platform != 'darwin' or os.environ.get(_MARKER):
        return
    # REPL / script read from stdin: a re-exec would lose the session / the input
    if not sys.argv or sys.argv[0] in ('', '-'):
        return
    paths = [p for p in os.environ.get('DYLD_LIBRARY_PATH', '').split(os.pathsep) if p]
    missing = [d for d in _torch_lib_dirs() if d not in paths]
    if not missing:
        return

    env = dict(os.environ)
    env[_MARKER] = '1'  # SIP may strip DYLD_* on exec: never loop
    env['DYLD_LIBRARY_PATH'] = os.pathsep.join(missing + paths)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        # orig_argv keeps the exact invocation (console script, -m module, ...)
        os.execve(sys.executable, sys.orig_argv, env)
    except OSError:
        pass  # keep running without the fix rather than failing to start
