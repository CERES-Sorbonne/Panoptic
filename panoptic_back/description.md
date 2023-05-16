# Panoptic



Panoptic is a tool for exploring and annotating large image corpora, using image analysis and machine learning tools to facilitate these tasks. 

Since it requires deep learning libraries, it is recommended to use it with a computer with minimal computing capabilities.

> Caution: Panoptic is still in active development and is currently a prototype, it is likely that you will encounter bugs, so we recommend to use this tool only for testing and not to rely on it for a substantial academic work. 

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

## Pip installation (WIP)

- `pip install panoptic`
- `panoptic`

## Windows install (coming soon)
## Mac installation (coming soon)
## Linux installation (coming soon)