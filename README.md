# Panoptic 👀

![Preview](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/a1da87bf-1d06-4873-8fd7-686211252461)


Panoptic is a tool for exploring and annotating large image corpora, using image analysis and machine learning tools to facilitate these tasks. 

Since it requires deep learning libraries, it is recommended to use it with a computer with minimal computing capabilities.

> Caution: Panoptic is still in active development and is currently a prototype, it is likely that you will encounter bugs, so we recommend to use this tool only for testing and not to rely on it for a substantial academic work. 

## Pip installation

- `pip install panoptic`
- `panoptic`

## Docker installation

### Option 1 : One folder to rule them all
Make a folder for the docker with a subfolder for the images `/path/to/your/folder/images`.
```bash
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic
```
### Option 2 : separate data and images folders
Make a folder for the panoptic datas (database, thumbnails, etc.) `/path/to/your/data/`.
And another one withe your images (could be an existing one) `/path/to/your/images/`.
```bash
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
```bash
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

## Windows install (coming soon)
## Mac installation (coming soon)
## Linux installation (coming soon)
