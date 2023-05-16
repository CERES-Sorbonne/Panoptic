# Panoptic



Panoptic est un outil d'exploration et d'annotation de large corpus d'images, utilisant des outils d'analyse d'image et de machine learning pour faciliter ces tâches. 

Ayant besoin de librairies de deep learning, il est recommandé de l'utiliser avec un ordinateur ayant des capacités minimales en terme de calcul.

> Attention: Panoptic est encore en phase active de développement et n'est pour l'instant qu'un prototype, il est fort probable que vous rencontriez des bugs, aussi nous recommandons de n'utiliser cet outil que pour des tests et ne pas se reposer dessus pour un travail académique conséquent. 

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

## Installation pip (WIP)

- `pip install panoptic`
- `panoptic`

## Installation Windows (A venir)
## Installation Mac (A venir)
## Installation Linux (A venir)
