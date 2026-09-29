import os
import site
import sys
import sysconfig
from pathlib import Path

_REEXEC_FLAG = 'PANOPTIC_DYLD_REEXEC'


def _torch_lib_dirs() -> list[str]:
    # torch comes with panopticml, pip-installed (maybe later, from the UI) into this environment
    dirs = [Path(sysconfig.get_paths()['purelib']), Path(site.getusersitepackages())]
    return [str(d / 'torch' / 'lib') for d in dirs]


def use_torch_libomp() -> None:
    """Avoid segfaults on macOS: faiss and torch each bundle their own libomp, and two OpenMP
    runtimes in one process crash. DYLD_LIBRARY_PATH on torch/lib makes faiss load torch's copy;
    dyld only reads it at process start, hence the re-exec."""
    if sys.platform != 'darwin' or os.environ.get(_REEXEC_FLAG):
        return
    current = [p for p in os.environ.get('DYLD_LIBRARY_PATH', '').split(os.pathsep) if p]
    missing = [d for d in _torch_lib_dirs() if d not in current]
    if not missing:
        return
    os.environ['DYLD_LIBRARY_PATH'] = os.pathsep.join(missing + current)
    os.environ[_REEXEC_FLAG] = '1'  # SIP may strip DYLD_* on exec: never loop
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, sys.orig_argv)
