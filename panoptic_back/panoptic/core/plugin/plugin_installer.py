import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib import metadata, util
from pathlib import Path

import requests

from panoptic.core.databases.panoptic.models import PluginKey


SOURCE_PIP  = 'pip'
SOURCE_GIT  = 'git'
SOURCE_PATH = 'path'

# Minimum versions for known pip plugins that work with this panoptic.
# A pre-release bound also lets pip pick pre-releases, which it skips otherwise.
PIP_MIN_VERSIONS = {'panopticml': '1.0.0rc2'}


class CudaTorchUpgradeError(ValueError):
    """The upgrade needs a new torch, and pip alone would replace the CUDA one with PyPI's."""

    def __init__(self, torch: str):
        self.torch = torch
        super().__init__(
            f"This update needs a newer torch than the installed CUDA build ({torch}), and pip "
            f"would replace it with a CPU-only one. Upgrade torch and torchvision with CUDA "
            f"yourself (https://pytorch.org/get-started/locally/), then update the plugin again.")


def torch_version() -> str | None:
    # read from the metadata: importing torch would load (and lock, on Windows) its DLLs
    try:
        return metadata.version('torch')
    except metadata.PackageNotFoundError:
        return None


class PluginInstaller:
    """Handles filesystem operations for plugin install, reinstall, and removal.

    All methods are sync blocking subprocess calls — acceptable because plugin
    operations are explicit admin actions, never called during request handling.
    """

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install_from_pip(self, source: str) -> str:
        """pip install -U <source>, return the resolved install_path.

        source is a requirement: a package name, optionally pinned (panopticml==1.0.0rc6).
        """
        source = source.strip()
        match = re.match(r'[A-Za-z0-9][A-Za-z0-9._-]*', source)
        if not match:
            raise ValueError(f"Invalid pip requirement {source!r}")
        name = match.group()
        min_version = PIP_MIN_VERSIONS.get(name)
        requirement = f'{name}>={min_version}' if min_version and source == name else source
        subprocess.check_call(self._pip_upgrade_cmd(name, requirement))
        dist = metadata.distribution(name)
        return str(Path(str(dist.locate_file(''))) / name)

    def install_from_git(self, url: str, name: str = None) -> str:
        """Download zip from GitHub/GitLab/Bitbucket, extract, install requirements.txt."""
        plugin_name = name or url.rstrip('/').split('/')[-1].removesuffix('.git')
        install_path = self.plugins_dir / plugin_name

        zip_url = self._zip_url(url)

        if install_path.exists():
            shutil.rmtree(install_path)
        install_path.mkdir(parents=True)

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'repo.zip')
            response = requests.get(zip_url, stream=True)
            response.raise_for_status()
            with open(zip_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

            with zipfile.ZipFile(zip_path, 'r') as zf:
                root = zf.namelist()[0]
                zf.extractall(str(install_path))

            # flatten the top-level subfolder that zip archives include
            root_dir = install_path / root
            if root_dir.is_dir():
                for item in root_dir.iterdir():
                    shutil.move(str(item), str(install_path / item.name))
                root_dir.rmdir()

        self._install_requirements(install_path)
        return str(install_path)

    def install_from_path(self, path: str) -> str:
        """Install requirements.txt for a local plugin directory."""
        p = Path(path)
        if not (p / '__init__.py').exists():
            raise ValueError(f"No __init__.py found at {p} — not a valid plugin directory")
        self._install_requirements(p)
        return str(p)

    # ------------------------------------------------------------------
    # Reinstall
    # ------------------------------------------------------------------

    def reinstall(self, plugin: PluginKey) -> str:
        """Re-run the appropriate install for a registered plugin."""
        if plugin.source_type == SOURCE_PIP:
            return self.install_from_pip(plugin.source_path)
        if plugin.source_type == SOURCE_GIT:
            return self.install_from_git(plugin.source_path, name=plugin.id)
        if plugin.source_type == SOURCE_PATH:
            return self.install_from_path(plugin.source_path)
        raise ValueError(f"Unknown source_type {plugin.source_type!r}")

    # ------------------------------------------------------------------
    # Remove
    # ------------------------------------------------------------------

    def uninstall_files(self, plugin: PluginKey) -> None:
        """Remove cloned git directories. pip installs are left in the Python env."""
        if plugin.source_type == SOURCE_GIT:
            p = Path(plugin.install_path)
            if p.exists():
                shutil.rmtree(p)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _install_requirements(self, plugin_dir: Path) -> None:
        req = plugin_dir / 'requirements.txt'
        if req.exists():
            subprocess.check_call(self._pip_install_cmd() + ['-r', str(req)])

    @classmethod
    def _pip_upgrade_cmd(cls, name: str, requirement: str) -> list[str]:
        """Upgrade `name` only; its dependencies move only when they no longer fit.

        A CUDA torch must stay CUDA if the upgrade has to replace it, but pip only sees
        PyPI, whose Windows torch is CPU-only: uv's torch backend picks the build that
        matches the driver instead.
        """
        uv = cls._find_uv()
        cuda = '+cu' in (torch_version() or '')
        if uv and cuda:
            return [uv, 'pip', 'install', '--python', sys.executable,
                    '--upgrade-package', name, '--torch-backend=auto', requirement]
        cmd = cls._pip_install_cmd() + ['-U', requirement]
        if cuda:
            cls._refuse_cuda_torch_replacement(cmd)
        return cmd

    @staticmethod
    def _refuse_cuda_torch_replacement(cmd: list[str]) -> None:
        report = json.loads(subprocess.check_output(cmd + ['--dry-run', '--quiet', '--report', '-']))
        names = {item['metadata']['name'].lower() for item in report.get('install', [])}
        if names & {'torch', 'torchvision'}:
            raise CudaTorchUpgradeError(torch_version())

    @staticmethod
    def _find_uv() -> str | None:
        # the launchers install uv in ~/.local/bin, not always on the backend's PATH
        local = Path.home() / '.local' / 'bin' / ('uv.exe' if os.name == 'nt' else 'uv')
        return shutil.which('uv') or (str(local) if local.is_file() else None)

    @classmethod
    def _pip_install_cmd(cls) -> list[str]:
        """Install command for the running interpreter.

        Envs created by uv have no pip module, so fall back to uv targeting this env.
        """
        if util.find_spec('pip') is not None:
            return [sys.executable, '-m', 'pip', 'install']
        uv = cls._find_uv()
        if uv:
            return [uv, 'pip', 'install', '--python', sys.executable]
        raise RuntimeError(f"Neither pip nor uv is available to install packages into {sys.executable}")

    @staticmethod
    def _zip_url(git_url: str) -> str:
        base = git_url.split('.git')[0].rstrip('/')
        if 'github.com' in git_url:
            return base + '/archive/refs/heads/main.zip'
        if 'gitlab.com' in git_url:
            return base + '/-/archive/main/main.zip'
        if 'bitbucket.org' in git_url:
            return base + '/get/main.zip'
        raise ValueError(f"Unsupported git host in URL: {git_url!r}")
