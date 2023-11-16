# Panoptic

![Aperçu](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/8e6389c7-ee80-4e0f-95d8-790602bd028e)

Panoptic est un outil d'exploration et d'annotation de large corpus d'images, utilisant des outils d'analyse d'image et de machine learning pour faciliter ces tâches. 

Ayant besoin de librairies de deep learning, il est recommandé de l'utiliser avec un ordinateur ayant des capacités minimales en terme de calcul.

> Attention: Panoptic est encore en phase active de développement et n'est pour l'instant qu'un prototype, il est fort probable que vous rencontriez des bugs, aussi nous recommandons de n'utiliser cet outil que pour des tests et ne pas se reposer dessus pour un travail académique conséquent. 

## Pré-requis
Quel que soit votre OS vous aurez besoin de Python 3.9 ou supérieur. 

## Installation Windows et Linux

Normalement il suffit d'ouvrir un terminal et de lancer les commandes suivantes pour installer, puis lancer panoptic:

- `pip install panoptic`
- `panoptic`

## Installation MAC 

Sur mac il existe un prérequis supplémentaire, celui d'installer les outils en ligne de commande x-tools. 
Pour cela il faut ouvrir un terminal et lancer la commande suivante:
`xcode-select –-install` cela devrait lancer l'installation.

Une fois installé il suffit de lancer:

- `pip install panoptic`
- `panoptic`


## Installation Docker

Si vous avez rencontré des problèmes avec l'installation classique, ou que vous préférez utiliser Docker, une image est à disposition. Il faut tout d'abord:

### Installer Docker
- [Sur MacOS](https://docs.docker.com/desktop/install/mac-install/)
- [Sur Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Sur Linux](https://docs.docker.com/desktop/install/linux-install/)

### Différences avec la version python

Sur la version docker, il n'existe pas la petite interface pour ajouter des dossiers ou gérer ses projets, il faut indiquer directement à docker les dossiers avec lesquels on va travailler:

### Option 1: Un seul dossier pour les images et pour les données panoptic:

Cela implique d'avoir créé un dossier spécial appelé "images", dans le dossier que vous indiquerez en entrée de panoptic. Dans l'exemple suivant, il faudrait ainsi que dans le dossier: `/chemin/vers/le/dossier`, il existe un dossier `images`dont le chemin complet serait par conséquent `/chemin/vers/le/dossier/images`.

Il faut ensuite lancer la commande suivante (avec Docker de lancé au préalable)

`docker run -it -p 8000:8000 -v /chemin/vers/le/dossier:/data --name panoptic ceressorbonne/panoptic`

### Option 2: Un dossier pour les images, et un dossier pour les données panoptic:

`docker run -it -p 8000:8000 -v /chemin/vers/le/dossier/ou/stocker/les/donnees/panoptic:/data -v /chemin/vers/le/dossier/images:/data/images --name panoptic ceressorbonne/panoptic`

## Installation (développement)

Les étapes suivantes impliquent d'avoir cloné le répertoire et sont recommandées pour les utilisateurs souhaitant avoir accès aux versions de développement, ou souhaitant modifier eux même le code afin de constribuer.

### Développement back uniquement

Pour tester et modifier le fonctionnement backend, nous fournissons un front-end déjà buildé dans le dossier html du back.
* aller dans le dossier `panoptic-back`
* pour installer les dépendances
    - `python setup.py install` simplement pour utiliser panoptic
    - `pip install -e .` pour développer
    - `pip install -r requirements.txt` et il faut ajouter `panoptic-back` au PYTHON_PATH également pour développer
* lancer `python panoptic/main.py`


### Développement front et back

1. Réaliser tout d'abord les étapes d'installation du backend
2. aller dans le dossier `panoptic-front`
3. lancer `npm install`
4. lancer `npm run dev`
5. avant de lancer le backend la variable d'environnement `PANOPTIC_ENV` devra être set à `DEV` afin d'utiliser le frontend de développement.
