# Panoptic 👀

[![PyPI - Version](https://img.shields.io/pypi/v/panoptic.svg)](https://pypi.org/project/panoptic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panoptic.svg)](https://pypi.org/project/panoptic)

This documentation also exist in [French](https://github.com/CERES-Sorbonne/Panoptic/blob/main/README-FR.md)

![Preview](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/8e6389c7-ee80-4e0f-95d8-790602bd028e)

## Table of Contents

1. [Description](#description)
2. [Installation](#installation)
    1. [Via pip](#via-pip)
    2. [Automatic Installation and Launch Scripts (recommended)](#automatic-installation-and-launch-scripts-recommended)
        1. [Windows](#windows)
        2. [Linux](#linux)
        3. [MacOS](#macos)
    3. [Docker Installation](#docker-installation)
    4. [Installation (development)](#installation-development)
3. [Usage](#usage)
4. [License](#license)

## Description

Panoptic is a tool for exploring and annotating large image corpora, utilizing image analysis and machine learning tools to facilitate these tasks.

Since it requires deep learning libraries, it is recommended to use it on a computer with minimal computing capabilities.

> Warning: Panoptic is still in active development and currently only a prototype. You may encounter bugs, so we recommend using this tool only for testing and not relying on it for significant academic work.

## Installation
### Via pip
<p style="color: red;">
Regardless of your OS, you will need Python 3.10 or higher; we recommend using version 3.12.
</p>

<p style="color: red;">
If you are on MacOS, you may need to install the x-tools command line tools. Open a terminal and run the following command:
`xcode-select --install`
Once installed, you can continue with the Panoptic installation.
</p>

Generally, you just need to open a terminal and run the following commands to install and then launch Panoptic:

- `pip3 install panoptic`
- `panoptic`

### Automatic Installation and Launch Scripts (recommended)
<p style="color: red;">
The script may ask for your password to install dependencies. This is necessary if you are missing system dependencies to install Panoptic (python, pip, and/or venv).
</p>

#### Windows

Here are the two commands to run to install Panoptic on Windows:

```powershell
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1
powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1
```


For more detailed steps:

1. Download the automatic installation and launch script for Panoptic by clicking the following link: [start_panoptic_windows.ps1](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1) or directly from the terminal with the following command:

```powershell
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1
```


2. Run the script by double-clicking the file or using the following command:

```powershell
powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1
```


#### Post-installation

After installation, you can launch Panoptic by going back to the folder where you executed the installation script and running the following command:

```powershell
powershell -ExecutionPolicy Bypass -File start-panoptic.ps1
```


#### Linux
Here are the three commands to run to install Panoptic on Linux:
```bash
wget https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh -O start_panoptic_linux.sh
chmod +x start_panoptic_linux.sh
./start_panoptic_linux.sh
```

For more detailed steps:
1. Download the automatic installation and launch script for Panoptic by clicking the following link: [start_panoptic_linux.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh)
or directly from the terminal with the following command:
```bash
wget https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh -O start_panoptic_linux.sh
```
2. Make the script executable by using the file properties or with the following command:
```bash
chmod +x start_panoptic_linux.sh
```
3. Run the script (double-click the file or use the following command):
```bash
./start_panoptic_linux.sh
```

You can also specify Panoptic launch parameters using the following command:
```bash
./start_panoptic_linux.sh [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [--no-update-script] [-h|--help]
```
Available options are:
- `-y`, `--yes` or `--assume-yes`: Use this option to automatically accept all confirmation requests.
- `-r` or `--reinstall`: Use this option to reinstall Panoptic.
- `-s` or `--start-only`: Use this option to launch Panoptic without reinstalling.
- `-u` or `--uninstall`: Use this option to uninstall Panoptic (does not delete data or system dependencies).
- `--no-bin-copy`: Use this option to not copy the Panoptic launch script to the `/usr/local/bin` directory.
- `--no-update-script`: Use this option to not update the Panoptic launch script in the `/usr/local/bin` directory.
- `-h` or `--help`: Use this option to display help.

##### Post-installation
After installation, you can launch Panoptic using the following command:
```bash
start-panoptic
```
 
You can also specify Panoptic launch parameters using the following command:
```bash
start-panoptic [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [-no-update-script] [-h|--help]
```
Available options are:
- `-y`, `--yes` or `--assume-yes`: Use this option to automatically accept all confirmation requests.
- `-r` or `--reinstall`: Use this option to reinstall Panoptic.
- `-s` or `--start-only`: Use this option to launch Panoptic without reinstalling.
- `-u` or `--uninstall`: Use this option to uninstall Panoptic (does not delete data or system dependencies).
- `--no-bin-copy`: Use this option to not copy the Panoptic launch script to the `/usr/local/bin` directory.
- `--no-update-script`: Use this option to not update the Panoptic launch script in the `/usr/local/bin` directory.
- `-h` or `--help`: Use this option to display help.


#### MacOS
Here are the three commands to run to install Panoptic on MacOS:
```bash
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_mac.sh
chmod +x start_panoptic_mac.sh
./start_panoptic_mac.sh
```

For more detailed steps:
1. Download the automatic installation and launch script for Panoptic by clicking the following link: [start_panoptic_mac.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_mac.sh)
2. Make the script executable by using the file properties or with the following command:
```bash
chmod +x start_panoptic_mac.sh
```
3. Run the script (double-click the file or use the following command):
```bash
./start_panoptic_mac.sh
```

#### Post-installation
After installation, you can launch Panoptic by going back to the folder where you executed the installation script and running the following command:
```bash
./start-panoptic.sh
```


### Docker Installation

If you encountered issues with the standard installation, or prefer using Docker, an image is available. First, you need to:

#### Install Docker
- [On MacOS](https://docs.docker.com/desktop/install/mac-install/)
- [On Windows](https://docs.docker.com/desktop/install/windows-install/)
- [On Linux](https://docs.docker.com/desktop/install/linux-install/)

#### Differences from the Python version

In the Docker version, there is no small interface for adding folders or managing projects; you need to directly specify the folders to Docker to work with:

#### Option 1: One folder for images and Panoptic data:

This requires creating a special folder named "images" within the folder you provide to Panoptic as input. In the following example, you would need a folder named `images` inside `/path/to/your/folder`, resulting in `/path/to/your/folder/images`.

Then run the following command (with Docker already running):

```console
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic
```

#### Option 2: Separate folders for images and Panoptic data:

```console
docker run -it -p 8000:8000 \
-v /path/to/images:/images \
-v /path/to/panoptic/data:/data \
--name panoptic ceressorbonne/panoptic
```

Once launched, visit [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser to access Panoptic.

#### Post-installation (Docker)

To relaunch Panoptic with Docker after the initial installation:

```console
docker start -ai panoptic
```

You can also specify Panoptic launch parameters as follows:

```console
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [--no-update-script] [-h|--help]
```

Available options are the same as for the Linux installation.

### Development Installation

If you want to contribute to Panoptic's development or test the latest unpublished features, you can clone the GitHub repository and install Panoptic in development mode.

#### Backend Development Only

To test and modify the backend, we provide a pre-built frontend in the backend's `html` folder.
* Navigate to the `panoptic-back` folder.
* To install dependencies:
    - `python3 setup.py install` to simply use Panoptic.
    - `pip3 install -e .` for development.
    - `pip3 install -r requirements.txt` and add `panoptic-back` to `PYTHON_PATH` for development as well.
* Run the backend with `python panoptic/main.py`.

#### Frontend and Backend Development

1. First, complete the backend installation steps.
2. Navigate to the `panoptic-front` folder.
3. Run `npm install`.
4. Start the frontend server with `npm run dev`.
5. Before starting the backend, set the environment variable `PANOPTIC_ENV` to `DEV` to use the development frontend.



## License
This project is licensed under the MPL-2.0 License - see the [LICENSE](https://github.com/CERES-Sorbonne/Panoptic/blob/main/LICENSE) file for details.
