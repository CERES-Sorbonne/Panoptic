# Panoptic 👀

[![PyPI - Version](https://img.shields.io/pypi/v/panoptic.svg)](https://pypi.org/project/panoptic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panoptic.svg)](https://pypi.org/project/panoptic)

This documentation also exist in [French](https://github.com/CERES-Sorbonne/Panoptic/blob/main/README-FR.md)

![Preview](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/8e6389c7-ee80-4e0f-95d8-790602bd028e)

Panoptic is a tool for exploring and annotating large image corpora, using image analysis and machine learning tools to facilitate these tasks. 

Since it requires deep learning libraries, it is recommended to use it with a computer with minimal computing capabilities.

> Caution: Panoptic is still in active development and is currently a prototype, it is likely that you will encounter bugs, so we recommend to use this tool only for testing and not to rely on it for a substantial academic work. 

## Windows and Linux installation

Python 3.9 or higher is required, and a custom environnment (venv, pyenv, conda etc.) is recommended.
Open a terminal and type:

- `pip install panoptic`
- `panoptic`

## Mac installation

Just like the windows installation but you will need to also install the xcode tools first. 
For this, just use this command in a terminal: `xcode-select –-install`, it should trigger the installation of the command line tools.
Then run:
- `pip install panoptic`
- `panoptic`

## Docker installation
If you're having issues with the installation (sometimes the packages can be tricky) or if you just prefair to use Docker it's possible:
Start by installing docker:
- [On MacOS](https://docs.docker.com/desktop/install/mac-install/)
- [On Windows](https://docs.docker.com/desktop/install/windows-install/)
- [On Linux](https://docs.docker.com/desktop/install/linux-install/)

### Option 1 : One folder to rule them all
Make a folder for the docker with a subfolder for the images `/path/to/your/folder/images`.
```console
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic
```
### Option 2 : Separate data and images folders
Make a folder for the panoptic datas (database, thumbnails, etc.) `/path/to/your/data/`.
And another one withe your images (could be an existing one) `/path/to/your/images/`.
```console
docker run -it -p 8000:8000 \
-v /path/to/your/data:/data \
-v /path/to/your/images:/data/images \
--name panoptic \
ceressorbonne/panoptic
```

### Access
You can now access panoptic through:
https://localhost:8000
As if you were to launch it with the python version

### Restart
If you happen to stop panoptic, you can re launch it with :
```console
docker start -ia panoptic
```


## Installation (development)
The following steps involve cloning the directory and are recommended for users who wish to have access to the development versions, or who wish to modify the code themselves in order to contribute.

### Backend development only

To test and modify the backend operation, we provide an already built frontend in the backend html folder.
* go to the `panoptic-back` folder
* to install the dependencies
    - `python setup.py install` to simply use panoptic
    - `pip install -e .` to develop
    - `pip install -r requirements.txt` and you have to add `panoptic-back` to the PYTHON_PATH for developping purpose too
* run `python panoptic/main.py`


### Front and back development

1. First of all, perform the installation steps of the backend
2. go to the `panoptic-front` folder
3. Run `npm install`.
4. run `npm run dev`.
5. before running the backend the `PANOPTIC_ENV` environment variable should be set to `DEV` in order to use the development frontend.
