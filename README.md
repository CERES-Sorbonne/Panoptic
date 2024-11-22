# Panoptic

[![PyPI - Version](https://img.shields.io/pypi/v/panoptic.svg)](https://pypi.org/project/panoptic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panoptic.svg)](https://pypi.org/project/panoptic)


![Aperçu](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/8e6389c7-ee80-4e0f-95d8-790602bd028e)

## Table of Contents
1. [Description](#description)
2. [Installation](#installation)
    1. [Through pip](#through-pip)
    2. [Installation and launching scripts recommended](#installation-and-launching-scripts-recommended)
        1. [Windows](#windows)
        2. [Linux](#linux)
        3. [MacOS](#macos)
    3. [Docker installation](#docker-installation)
    4. [Development installation](#development-installation)
3. [Utilisation](#utilisation)
4. [License](#license)

## Description

Panoptic is a tool for exploring and annotating large image datasets, using image analysis and machine learning tools to facilitate these tasks.

Requiring deep learning libraries, it is recommended to use it with a computer with minimal computing capabilities.

> Caution: Panoptic is still in active development and is currently only a prototype, it is likely that you will encounter bugs, so we recommend using this tool only for testing and not relying on it for significant academic work.


## Installation
### Through pip
<p style="color: red;">
Whatever your OS you will need Python 3.10 or higher, we recommend using version 3.12.
</p>

<p style="color: red;">
If you are on MacOS, you may need to install the x-tools command line tools, to do this open a terminal and run the following command:
</p>
`xcode-select –-install`
Once installed you can continue the installation of Panoptic.

Normally you just need to open a terminal and run the following commands to install, then launch panoptic:

- `pip3 install panoptic`
- `panoptic`

### Installation and launching scripts recommended
<p style="color: red;">
The script may ask for your password to install dependencies, this is necessary in case you are missing system dependencies to install Panoptic (python, pip and/or venv).
</p>

#### Windows

Here are the two commands to run to install Panoptic on Windows:

```powershell
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1
powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1
```

To detail the steps a bit more:

1. Download the automatic installation and launch script of Panoptic by clicking on the following link: [start_panoptic_windows.ps1](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1) or directly from the terminal with the following command:

```powershell
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1
```


2. Run the script by double-clicking on the file or using the following command:

```powershell
powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1
```

#### Post-installation

After installation, you can launch Panoptic by going back to the folder where you ran the installation script and running the following command:

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

To detail the steps a bit more:
1. Download the automatic installation and launch script of Panoptic by clicking on the following link: [start_panoptic_linux.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh)
or directly from the terminal with the following command:

```bash
wget https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh -O start_panoptic_linux.sh
```

2. Make the script executable using the file properties or using the following command:

```bash
chmod +x start_panoptic_linux.sh
```

3. Run the script (double-click on the file or use the following command):

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

To detail the steps a bit more:
1. Download the automatic installation and launch script of Panoptic by clicking on the following link: [start_panoptic_mac.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_mac.sh)

2. Make the script executable using the file properties or using the following command:

```bash
chmod +x start_panoptic_mac.sh
```

3. Run the script (double-click on the file or use the following command):

```bash
./start_panoptic_mac.sh
```

#### Post-installation

After installation, you can launch Panoptic by going back to the folder where you ran the installation script and running the following command:

```bash
./start-panoptic.sh
```

### Docker installation

If you have encountered problems with the classic installation, or prefer to use Docker, an image is available. You must first:

#### Install Docker
- [On MacOS](https://docs.docker.com/desktop/install/mac-install/)
- [On Windows](https://docs.docker.com/desktop/install/windows-install/)
- [On Linux](https://docs.docker.com/desktop/install/linux-install/)
#### Differences with the python version

In the docker version, there is no small interface to add folders or manage projects, you have to indicate directly to docker the folders with which you are going to work:

#### Option 1: One folder for images and for panoptic data:

This implies having created a special folder called "images", in the folder you will indicate as input to panoptic. In the following example, you would need to have a folder `images` in the folder: `/path/to/your/folder`, so that there is a folder `images` whose full path would therefore be `/path/to/your/folder/images`.

You then need to run the following command (with Docker running beforehand)

```bash
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic
```

#### Option 2: One folder for images, and one folder for panoptic data:

```bash
docker run -it -p 8000:8000 \
-v /path/to/your/data:/data \
-v /path/to/your/images:/data/images \
--name panoptic \
ceressorbonne/panoptic
```

### Development installation

The following steps involve having cloned the repository and are recommended for users who want to access development versions, or who want to modify the code themselves in order to contribute.

#### Backend development only

To test and modify the backend operation, we provide a pre-built front-end in the back's html folder.
* go to the `panoptic-back` folder
* install dependencies
    - `python3 setup.py install` simply to use panoptic
    - `pip3 install -e .` to develop
    - `pip3 install -r requirements.txt` and `panoptic-back` must be added to the PYTHON_PATH as well to develop
*launch `python panoptic/main.py`

#### Front and back development

1. First perform the backend installation steps
2. go to the `panoptic-front` folder
3. run `npm install`
4. run `npm run dev`
5. before launching the backend the environment variable `PANOPTIC_ENV` must be set to `DEV` to use the development frontend.

## Utilisation

Once installed, you can access the Panoptic interface by going to http://localhost:8000 in your browser.

## License

This project is licensed under MPL-2.0 - see the [LICENSE](https://github.com/CERES-Sorbonne/Panoptic/blob/main/LICENSE) file for more details.
