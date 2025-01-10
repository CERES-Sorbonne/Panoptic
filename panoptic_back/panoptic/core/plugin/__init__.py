import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests

from panoptic.utils import get_datadir


def get_zip_url(git_url):
    """Determine the zip download URL based on the git hosting provider."""
    short_url = git_url.split('.git')[0]
    if "github.com" in git_url:
        # Convert the GitHub URL to the zip URL format
        return short_url + "/archive/refs/heads/main.zip"
    elif "gitlab.com" in git_url:
        # Convert the GitLab URL to the zip URL format
        return short_url + "/-/archive/main/main.zip"
    elif "bitbucket.org" in git_url:
        # Convert the Bitbucket URL to the zip URL format
        return short_url + "/get/main.zip"
    else:
        raise ValueError("Unsupported git provider. Only GitHub, GitLab, and Bitbucket are supported.")


def download_and_extract_zip(zip_url, plugin_name):
    """Download and extract the zip file to a temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir: # Create a temporary directory
        zip_path = os.path.join(temp_dir, "repo.zip")
        plugin_path = os.path.join(get_datadir(), 'panoptic', 'plugins', plugin_name)

        # reset folder if already exist
        if os.path.exists(plugin_path) and os.path.isdir(plugin_path):
            shutil.rmtree(plugin_path)
        os.makedirs(plugin_path)

        # Download the zip file
        response = requests.get(zip_url, stream=True)
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(response.raw, f)

        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            root_folder = zip_ref.namelist()[0]
            zip_ref.extractall(plugin_path)

        file_names = os.listdir(os.path.join(plugin_path, root_folder))
        for file_name in file_names:
            shutil.move(os.path.join(plugin_path, root_folder, file_name), os.path.join(plugin_path, file_name))

        return plugin_path


def add_plugin_from_git(git_url, plugin_name=None):
    zip_url = get_zip_url(git_url)
    name = git_url.split("/")[-1] if not plugin_name else plugin_name
    folder_name = download_and_extract_zip(zip_url, name)
    return folder_name
