import json
import sys
from importlib import metadata

import pytest

from panoptic.core.plugin import plugin_installer
from panoptic.core.plugin.plugin_installer import CudaTorchUpgradeError, PluginInstaller

UV = '/opt/uv'


@pytest.fixture
def env(monkeypatch):
    """Fake the installed torch and the uv lookup."""
    state = {'torch': None, 'uv': UV}

    def version(name):
        if name == 'torch' and state['torch']:
            return state['torch']
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(plugin_installer.metadata, 'version', version)
    monkeypatch.setattr(PluginInstaller, '_find_uv', staticmethod(lambda: state['uv']))
    monkeypatch.setattr(PluginInstaller, '_pip_install_cmd', classmethod(lambda cls: ['pip', 'install']))
    return state


def test_cuda_torch_upgrades_through_uv_torch_backend(env):
    env['torch'] = '2.5.1+cu118'
    assert PluginInstaller._pip_upgrade_cmd('panopticml', 'panopticml>=1') == [
        UV, 'pip', 'install', '--python', sys.executable,
        '--upgrade-package', 'panopticml', '--torch-backend=auto', 'panopticml>=1']


@pytest.mark.parametrize('torch', [None, '2.6.0', '2.6.0+cpu'])
def test_non_cuda_torch_keeps_pip(env, torch):
    env['torch'] = torch
    assert PluginInstaller._pip_upgrade_cmd('panopticml', 'panopticml>=1') == [
        'pip', 'install', '-U', 'panopticml>=1']


def _pip_would_install(monkeypatch, *names):
    report = {'install': [{'metadata': {'name': n, 'version': '9'}} for n in names]}
    monkeypatch.setattr(plugin_installer.subprocess, 'check_output', lambda cmd: json.dumps(report))


def test_cuda_torch_without_uv_keeps_pip_when_torch_stays(env, monkeypatch):
    env['torch'], env['uv'] = '2.5.1+cu118', None
    _pip_would_install(monkeypatch, 'panopticml', 'faiss-cpu')
    assert PluginInstaller._pip_upgrade_cmd('panopticml', 'panopticml>=1') == [
        'pip', 'install', '-U', 'panopticml>=1']


@pytest.mark.parametrize('replaced', ['torch', 'TorchVision'])
def test_cuda_torch_without_uv_refuses_replacing_torch(env, monkeypatch, replaced):
    env['torch'], env['uv'] = '2.5.1+cu118', None
    _pip_would_install(monkeypatch, 'panopticml', replaced)
    with pytest.raises(CudaTorchUpgradeError) as e:
        PluginInstaller._pip_upgrade_cmd('panopticml', 'panopticml>=1')
    assert e.value.torch == '2.5.1+cu118'
