import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib import metadata
from pathlib import Path

import requests

from panoptic2.core.databases.panoptic.models import PluginKey


SOURCE_PIP  = 'pip'
SOURCE_GIT  = 'git'
SOURCE_PATH = 'path'


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
        """pip install -U <source>, return the resolved install_path."""
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', source])
        dist = metadata.distribution(source)
        return str(Path(str(dist.locate_file(''))) / source)

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
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '-r', str(req)]
            )

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
