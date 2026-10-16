## Architecture Générale

**Panoptic** implémente un système de plugins pour personnaliser le traitement de données d'images. Les plugins s'intègrent à trois niveaux :
- Actions UI (opèrent sur images sélectionnées)
- Événements système (automatisation via hooks)
- Couche de données (propriétés, vecteurs, cartes)

**Cycle de vie** : les plugins sont chargés au niveau projet par `LoadPluginTask` à l'ouverture, puis `start()` est appelé ; `stop()` est appelé à l'arrêt du plugin ou à la fermeture du projet.

**Tout est synchrone** : les actions sont appelées directement depuis une route FastAPI synchrone (exécutée dans un thread), et les tâches longues tournent chacune dans leur thread. Une action `async def` ne fonctionne pas : elle renverrait une coroutine jamais exécutée.

## Classes Principales

### `APlugin` (classe de base obligatoire)
```python
from panoptic.core.plugin.plugin import APlugin

class MonPlugin(APlugin):
    """Description du plugin, affichée dans l'UI."""

    def __init__(self, name: str, project, plugin_path: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
```
Le plugin est instancié avec des arguments nommés (`project=`, `plugin_path=`, `name=`).

**Attributs clés** :
- `params` : objet Pydantic persistant, modifiable via l'UI (voir plus bas)
- `data_path` : dossier dédié au plugin (`<projet>/plugin_data/<nom>`), créé automatiquement
- `project` : `PluginProjectInterface`, seul accès au projet
- `vector_types` : types de vecteurs dont `source` est le nom du plugin (rempli dans `start()`)
- `registered_functions` : actions enregistrées

**Méthodes** :
- `add_action_easy(fonction, hooks)` : enregistrement rapide, la description est construite par introspection
- `add_action(fonction, description)` : enregistrement avec une `FunctionDescription` explicite
- `_start()` : à surcharger, appelé après le chargement des params (initialisation, création des types de vecteurs...)
- `_stop()` : à surcharger pour libérer les ressources (modèles, threads, fichiers). Les tâches du plugin ont déjà reçu l'ordre d'arrêt et ses actions et callbacks ont été retirés.
- `update_params(params)` : appelé quand l'utilisateur modifie les params. Il fait un `model_copy` sans validation : surchargez-le si vos params contiennent des `Enum` ou des nombres, pour les revalider.

### `PluginProjectInterface`
Interface autonome, sans référence au `Project` : elle ouvre ses propres connexions aux bases (`data.db`, `media.db`, `project.db`) à chaque appel. Elle donne accès à :
- la lecture des données (dossiers, fichiers, instances, propriétés, tags, valeurs)
- l'écriture par commits (annulables), toujours avec le nom du plugin comme source
- les vecteurs, types de vecteurs et cartes
- les tâches longues et les événements

Chaque écriture prévient automatiquement les clients connectés, qui récupèrent le nouveau delta.

## Configuration du Plugin

### Structure de fichiers
```
mon_plugin/
├── __init__.py         # Point d'entrée (déclare plugin_class)
├── main.py             # Code principal
└── requirements.txt    # Dépendances pip, installées à l'installation du plugin
```
Un plugin s'installe depuis un dépôt git (GitHub, GitLab, Bitbucket), un dossier local ou un paquet pip. Utilisez des imports relatifs (`from .main import ...`) : le module est chargé sous le nom du plugin, pas sous le nom de son dossier.

### Paramètres (Pydantic BaseModel)
```python
class MesParams(BaseModel):
    """
    @auto_process: traiter les images à l'import
    @batch_size: nombre d'images par lot
    @model: modèle utilisé
    """
    auto_process: bool = True
    batch_size: int = 32
    model: ModelEnum = ModelEnum.small
```
Les lignes `@nom: ...` de la docstring servent de description dans l'UI ; le texte avant le premier `@` décrit le groupe de params. Les params sont sauvegardés dans `project.db` (`load_params` / `save_params`) et rechargés au démarrage.

Types UI supportés (params et arguments d'action) : `int`, `float`, `str`, `bool`, `Path`, `Enum` (liste déroulante des valeurs), `PropertyId`, `VectorType`, `OwnVectorType`, `InputFile`, `FolderPath`, `FilePath` (ces sentinelles sont dans `panoptic.models.action_models`). Un argument d'un autre type est ignoré avec un warning.

## Actions et Fonctions

### Signature de fonction
```python
from panoptic.models.action_models import ActionContext, ActionResult, Notif, NotifType

def ma_fonction(self, context: ActionContext, seuil: float = 0.5) -> ActionResult:
    """Description affichée dans l'UI.
    @seuil: description du paramètre
    """
    instances = self.project.get_instances(id=context.instance_ids)
    # Traitement...
    return ActionResult(notifs=[Notif(NotifType.INFO, name='ma_fonction', message='Terminé')])
```
L'id de l'action est `<nom du plugin>.<nom de la fonction>`. Les valeurs reçues de l'UI sont reconverties pour les `Enum`, `VectorType`/`OwnVectorType` (en `VectorType`), `FolderPath` et `FilePath`.

**ActionContext** :
- `instance_ids` : IDs des instances sélectionnées, vide ou `None` sans sélection. Attention : `get_instances(id=None)` ne renvoie rien ; pour traiter tout le projet, appelez `get_instances()` sans filtre
- `group_name` : nom du groupe d'où l'action est lancée
- `ui_inputs` : valeurs brutes des arguments

### Hooks UI disponibles
- `'execute'` : actions générales (bouton d'exécution)
- `'group'` : clustering / regroupement, renvoie des `groups`
- `'similar'` : recherche d'images similaires, renvoie des `groups`
- `'map'` : création d'une vue spatiale, renvoie la carte dans `value`
- `'vector_type'` : création d'un type de vecteur (réglages des vecteurs), renvoie le type dans `value`
- `'vector'` : calcul des vecteurs d'un type (réglages des vecteurs)
- `'text_search'` : mode de la barre de recherche ; la fonction doit avoir un argument `text`

### ActionResult
```python
@dataclass
class ActionResult:
    groups: list[Group] | None = None   # Groupes d'images à afficher
    datas:  list[dict]  | None = None
    urls:   list[str]   | None = None
    notifs: list[Notif] | None = None   # Notifications
    value:  Any         = None          # Résultat unique (carte, type de vecteur...)
    task_id: str | None = None          # Id d'une tâche lancée, pour que l'UI suive sa progression
```

### Group (affichage de résultats)
```python
@dataclass
class Group:
    ids: list[int] | None = None        # IDs d'instances OU
    sha1s: list[str] | None = None      # SHA1 d'images (pas les deux !)
    scores: ScoreList | None = None     # Un score par élément
    score: Score | None = None          # Score du groupe
    name: str | None = None             # Nom affiché
```

**Score** : `value`, `min`, `max`, `description`, `max_is_best` ; **ScoreList** : idem avec `values: list[float]`.

### Notifications
```python
@dataclass
class Notif:
    type: NotifType                 # DEBUG / INFO / WARNING / ERROR
    name: str | None = None
    message: str | None = None
    data: Any = None                # Affiché en JSON
```

## Événements Système

```python
# Dans __init__
self.project.on_import_complete(self._on_import)
self.project.on_folder_delete(self._on_folder_delete)

def _on_import(self, root_folder_id: int | None = None): ...
def _on_folder_delete(self, folders: list[Folder]): ...
```
- `on_import_complete(callback)` : fin d'un import, avec l'id du dossier racine importé (ou `None`)
- `on_folder_delete(callback)` : suppression de dossiers

## Opérations de Données

Les modèles sont des `msgspec.Struct` dans `panoptic.core.databases.data.models` (données) et `panoptic.core.databases.media.models` (vecteurs, cartes). Pour en modifier un : `msgspec.structs.replace(obj, champ=valeur)`.

### Lecture
Toutes les méthodes acceptent des filtres par champ, une liste valant `IN` :
```python
self.project.get_instances(id=[...])          # Instance(id, file_id, sha1)
self.project.get_instances(sha1=[...])
self.project.get_files(id=[...])              # File(id, name, folder_id, sha1, width, height...)
self.project.get_folders(id=[...])            # Folder(id, source_id, path, name, parent)
self.project.get_file_sources()
self.project.get_properties(name='ocr')       # Property(id, dtype, mode, name, access, tag_list_id...)
self.project.get_property_groups()
self.project.get_tags(list_id=prop.tag_list_id)
self.project.get_instance_values(property_id=[...], instance_id=[...])
self.project.get_sha1_values(property_id=[...], sha1=[...])
self.project.get_file_values(property_id=[...])
```
Les valeurs des propriétés `tag` / `multi_tags` ne sont pas dans `get_*_values` : elles sont dans les tables de jonction (`get_sha1_tag_values`, `get_instance_tag_values` du `DataReader`), sans méthode publique sur l'interface pour l'instant.

**Chemin d'une image** : il n'y a pas encore d'accès public. Combinez `get_files` et `get_folders` (`folder.path + '/' + file.name` pour une source locale), ou utilisez `self.project._data_reader()` et `resolve_image_ref(sha1)`, qui renvoie `{'kind': 'local', 'path': ...}` ou `{'kind': 'iiif', 'url': ...}`. Les miniatures stockées (`small` 256 px, `large` 1024 px) sont dans `media.db` (`self.project._media_db()`, `get_image_types()`, `get_images(type_id=..., sha1=[...])`).

### Écriture
```python
from panoptic.core.databases.data.models import DataCommit, Sha1Value, InstanceValue

# Créer une propriété (id alloué immédiatement), mode 'sha1' ou 'id'
prop = self.project.add_property('score', 'number', 'sha1', readonly=True, property_group_id=None)
group = self.project.add_property_group('Mon groupe')

# Écrire des valeurs : un commit annulable (undo/redo)
self.project.apply_commit(DataCommit(sha1_values=[
    Sha1Value(property_id=prop.id, sha1=sha1, value=0.8),
]))
```
- dtypes : `text`, `number`, `tag`, `multi_tags`, `url`, `date`, `path`, `color`, `checkbox`, `image_link`
- `readonly=True` : non modifiable dans l'UI, le plugin continue à écrire normalement
- `DataCommit` contient `properties`, `property_groups`, `tags`, `instance_values`, `sha1_values`, `file_values` ; chaque entité porte son `operation` (`OP_CREATE`, `OP_UPDATE`, `OP_DELETE` de `panoptic.core.databases.entity_schema`), un même commit peut donc créer, modifier et supprimer
- `value=None` vide la valeur ; pour une propriété à tags, `value` est la liste des ids de tags
- un commit qui ne change rien n'est pas enregistré (`apply_commit` renvoie `None`)
- `apply_upsert_commit(UpsertCommit)` et `apply_delete_commit(DeleteCommit)` existent aussi

Il n'y a pas d'aide publique pour créer des tags : allouez les ids avec `self.project._project_db()` (`allocate_tags(n)`), puis envoyez `Tag(id=..., list_id=prop.tag_list_id, value='chat', parents=[], color=0, operation=OP_CREATE)` dans un `DataCommit`.

### Vecteurs et cartes (`media.db`, hors commits)
```python
from panoptic.core.databases.media.models import Map, Vector, VectorType

vt = self.project.upsert_vector_type(VectorType(id=-1, source=self.name, params={'model': 'clip'}))
self.project.upsert_vectors([Vector(type_id=vt.id, sha1=sha1, data=np_array)])
self.project.get_vectors(vt.id, sha1s=[...])
self.project.vector_exist(vt.id, sha1)

point_map = self.project.upsert_map(Map(id=-1, source=self.name, name='Ma carte',
                                        key='sha1', count=n, data=[sha1, x, y, sha1, x, y, ...]))
return ActionResult(value=msgspec.structs.asdict(point_map))
```
Un `id` négatif alloue un nouvel id. Les cartes tiennent dans un disque de rayon 100.

## Concurrence et Calculs Lourds

Les actions doivent répondre vite : lancez les traitements longs dans une `Task`. Plusieurs actions peuvent tourner en même temps dans des threads différents : protégez l'état partagé du plugin (modèle chargé, création de propriétés) avec un `threading.Lock`.

`self.project.run_in_executor(fn, *args)` appelle simplement `fn(*args)` (l'appelant est déjà dans un thread).

### Task (tâches suivies dans l'UI)
```python
from panoptic.core.task.task import Task

class MaTache(Task):
    def __init__(self, plugin, sha1s):
        super().__init__()
        self.plugin = plugin
        self.sha1s = sha1s
        self.name = 'Nom affiché'
        # self.key (nom de la classe par défaut) groupe les tâches pour on_last()

    def start(self):
        self.state.total = len(self.sha1s)
        self.set_step('Chargement du modèle')
        for sha1 in self.sha1s:
            if self.is_cancelled():
                break
            ...
            self.state.done += 1      # ou self.state.failed += 1
            self._notify()

    def on_last(self):
        """Appelé après la dernière tâche de même key, même si elle a été arrêtée."""
        self.plugin.rebuild_index()
```
```python
task = self.project.add_task(MaTache(self, sha1s))      # high_priority=False
return ActionResult(task_id=task.id)
```
- `is_cancelled()` entre les étapes pour s'arrêter proprement ; sinon le TaskManager interrompt la tâche
- `set_step(step, detail)` affiche la phase en cours, `set_workers(n)` le nombre de workers
- les tâches d'un plugin sont arrêtées quand le plugin s'arrête

## Workflow Type : Vecteurs + Clustering

### 1. Créer un type de vecteur
```python
def _start(self):
    if not self.vector_types:
        vt = self.project.upsert_vector_type(VectorType(id=-1, source=self.name, params={'model': 'mon_modele'}))
        self.vector_types = [vt]
```

### 2. Calculer des vecteurs
```python
def compute_vectors(self, context: ActionContext, vec_type: OwnVectorType) -> ActionResult:
    instances = self.project.get_instances(id=context.instance_ids)
    task = self.project.add_task(ComputeVectorsTask(self, vec_type, instances))
    return ActionResult(task_id=task.id)
```
avec, dans la tâche :
```python
self.project.upsert_vectors([Vector(type_id=vt.id, sha1=sha1, data=compute(image)) for ...])
```

### 3. Clustering
```python
def compute_clusters(self, context: ActionContext, vec_type: OwnVectorType, nb_clusters: int = 10) -> ActionResult:
    instances = self.project.get_instances(id=context.instance_ids)
    sha1s = list(dict.fromkeys(i.sha1 for i in instances))
    vectors = self.project.get_vectors(vec_type.id, sha1s=sha1s)
    labels = clustering_algorithm(vectors, nb_clusters)
    groups = [Group(sha1s=[v.sha1 for v, l in zip(vectors, labels) if l == c], name=f'Cluster {c}')
              for c in range(nb_clusters)]
    return ActionResult(groups=groups)
```

## Points Clés

1. **Synchrone** : actions et `Task.start()` sont des fonctions normales, pas de `async` / `await`
2. **Unicité SHA1** : plusieurs instances peuvent partager une image ; dédupliquez par sha1 avant un traitement (`list(dict.fromkeys(i.sha1 for i in instances))`)
3. **IDs négatifs** : pour `upsert_vector_type` et `upsert_map` ; propriétés et groupes via `add_property` / `add_property_group`
4. **Erreurs** : une exception non attrapée dans une action renvoie une erreur 500 avec la stacktrace ; pour un message lisible, renvoyez une `Notif(NotifType.ERROR, ...)`. Dans une tâche, attrapez les erreurs par élément et comptez-les dans `state.failed`
5. **Références** : **PanopticML** (vecteurs, clustering, cartes), **PanopticColor** (propriétés sha1, groupe de propriétés, cartes) et **PanopticOCR** (tâche par lots, lecture des fichiers originaux)

## Exemple Minimal

```python
# __init__.py
from .main import MonPlugin

plugin_class = MonPlugin
```
```python
# main.py
from panoptic.core.databases.data.models import DataCommit, Sha1Value
from panoptic.core.plugin.plugin import APlugin
from panoptic.models.action_models import ActionContext, ActionResult, Notif, NotifType


class MonPlugin(APlugin):
    """Compte les images sélectionnées."""

    def __init__(self, name: str, project, plugin_path: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.add_action_easy(self.ma_fonction, ['execute'])

    def ma_fonction(self, context: ActionContext) -> ActionResult:
        instances = self.project.get_instances(id=context.instance_ids)
        prop = next(iter(self.project.get_properties(name='vu')), None) \
            or self.project.add_property('vu', 'checkbox', 'sha1')
        self.project.apply_commit(DataCommit(sha1_values=[
            Sha1Value(property_id=prop.id, sha1=sha1, value=True)
            for sha1 in dict.fromkeys(i.sha1 for i in instances)
        ]))
        return ActionResult(notifs=[Notif(NotifType.INFO, name='ma_fonction',
                                          message=f'{len(instances)} images traitées')])
```
