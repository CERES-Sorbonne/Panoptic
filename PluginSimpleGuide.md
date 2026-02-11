## Architecture Générale

**Panoptic** implémente un système de plugins pour personnaliser le traitement de données d'images. Les plugins s'intègrent à trois niveaux :
- Actions UI (opèrent sur images sélectionnées)
- Événements système (automatisation via hooks)
- Couche de données (propriétés, vecteurs, structures DB)

**Cycle de vie** : Les plugins sont chargés au niveau projet, initialisés à l'ouverture et actifs durant toute la durée de vie du projet.

## Classes Principales

### `APlugin` (classe de base obligatoire)
```python
class MonPlugin(APlugin):
    def __init__(self, project: Project, plugin_path: str, name: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
```

**Attributs clés** :
- `params`: Objet personnalisable pour stockage persistant (modifiable via UI)
- `data_path`: Dossier dédié au plugin (supprimé avec le plugin)
- `project`: Interface `PluginProjectInterface` pour opérations DB
- `vector_types`: Types de vecteurs enregistrés par le plugin
- `registered_functions`: Liste des actions enregistrées

**Méthodes** :
- `add_action_easy(function, hooks)`: Enregistrement rapide avec hooks UI
- `add_action(function, description)`: Enregistrement manuel avec `FunctionDescription`
- `async _start()`: Méthode asynchrone appelée au chargement (pour initialisations lourdes)

### `PluginProjectInterface`
Donne accès à :
- Opérations DB (instances, propriétés, tags, vecteurs)
- Gestion de tâches longues
- Système d'événements
- Déclencheurs de mise à jour UI

## Configuration du Plugin

### Structure de fichiers
```
mon_plugin/
├── __init__.py         # Point d'entrée (déclare plugin_class)
├── mon_plugin.py       # Code principal
└── requirements.txt    # Dépendances pip
```

### Paramètres (Pydantic BaseModel)
```python
class MesParamsPlugin(BaseModel):
    auto_process: bool = True
    batch_size: int = 32
    threshold: float = 0.75
```
Types UI supportés : `int`, `float`, `str`, `bool`, `PropertyId`, `Enum`, `VectorType`, `OwnVectorType`

## Actions et Fonctions

### Signature de fonction
```python
async def ma_fonction(self, context: ActionContext, param1: str) -> ActionResult:
    instances = await self.project.get_instances(context.instance_ids)
    # Traitement...
    return ActionResult(groups=[...], notifs=[...])
```

**ActionContext** : contient `instance_ids` (liste d'IDs sélectionnés)

### Hooks UI disponibles
- `'vector_type'`: Création de types de vecteurs
- `'vector'`: Calcul de vecteurs
- `'similar'`: Recherche de similarité
- `'group'`: Clustering/regroupement
- `'execute'`: Actions générales

### ActionResult
```python
@dataclass
class ActionResult:
    groups: list[Group] = None      # Groupes d'images à afficher
    notifs: list[Notif] = None      # Notifications INFO/ERROR/WARNING
    value: Any = None               # Résultats à valeur unique
```

### Group (affichage de résultats)
```python
@dataclass
class Group:
    ids: list[int] = None           # IDs d'instances OU
    sha1s: list[str] = None         # SHA1 d'images (pas les deux!)
    scores: ScoreList = None        # Scores par item
    score: Score = None             # Score du groupe
    name: str = None                # Nom affiché
```

**Score** : `value`, `min`, `max`, `description`, `max_is_best`

### Notifications
```python
class Notif:
    type: NotifType                 # DEBUG/INFO/WARNING/ERROR
    name: str
    message: str
    data: Any                       # Affiché en JSON
    functions: list[NotifFunction]  # Suggestions d'actions
```

## Événements Système

```python
# Dans __init__
self.project.on_instance_import(self.callback_import)
self.project.on_folder_delete(self.callback_delete)
```

Événements disponibles :
- `on_instance_import(callback)`: Import d'images
- `on_folder_delete(callback)`: Suppression de dossiers

## Opérations de Données

### Lecture (méthodes asynchrones)
```python
# Instances
await self.project.get_instances(ids=[...], sha1s=[...])

# Propriétés/Tags
await self.project.get_properties(ids=[...], computed=False)
await self.project.get_tags(ids=[...], property_ids=[...])

# Vecteurs
await self.project.get_vectors(type_id, sha1s=[...])
await self.project.vector_exist(type_id, sha1)
await self.project.get_vector_types(source=None)

# Valeurs de propriétés
await self.project.get_instance_property_values(property_ids, instance_ids)
await self.project.get_image_property_values(property_ids, sha1s)
```

### Écriture (système de commit)
```python
class DbCommit:
    # Listes de suppression
    empty_instances: list[int]
    empty_properties: list[int]
    empty_tags: list[int]
    # ... autres empty_*
    
    # Données à créer/modifier
    folders: list[Folder]
    instances: list[Instance]
    properties: list[Property]
    tags: list[Tag]
    instance_values: list[InstanceProperty]
    image_values: list[ImageProperty]
```

**Fonctions utilitaires** (créent objets avec ID négatifs) :
- `create_instance(...)`
- `create_property(name, type_, mode)`
- `create_property_group(name)`
- `create_tag(property_id, value, parent_ids, color)`
- `create_vector_type(params)`

**Application des commits** :
```python
await self.project.apply_commit(commit)  # Application directe
await self.project.do(commit)            # Avec support undo/redo
```

**Vecteurs** (hors commit) :
```python
await self.project.add_vector_type(vec_type)
await self.project.add_vector(vector)
```

## Concurrence et Calculs Lourds

### Assistant asynchrone (tâches simples)
```python
result = await self.project.run_async(fonction_bloquante, *args)
```

### TaskQueue (tâches trackées avec UI)
```python
class MaTache(Task):
    def __init__(self, plugin, data):
        super().__init__(priority=False)
        self.name = 'Nom affiché'
        self.key = 'task_unique_key'  # Groupage et run_if_last()
    
    async def run(self):
        """Exécution principale (arrière-plan)"""
        result = await self.run_async(self._calcul_lourd, data)
        await self.plugin.project.add_vector(result)
        return result
    
    async def run_if_last(self):
        """Appelé après toutes les tâches avec même key"""
        await self.plugin.rebuild_index()
    
    @staticmethod
    def _calcul_lourd(data):
        """CPU-intensif dans thread executor"""
        return process(data)
```

**Ajout à la queue** :
```python
self.project.add_task(MaTache(self, data))
```

## Workflow Type : Vecteurs + Clustering

### 1. Créer un type de vecteur
```python
async def _start(self):
    if len(self.vector_types) == 0:
        vec_type = self.project.create_vector_type({"model": "mon_modele"})
        await self.project.add_vector_type(vec_type)
```

### 2. Calculer des vecteurs
```python
async def compute_vectors(self, ctx: ActionContext):
    instances = await self.project.get_instances(ids=ctx.instance_ids)
    type_id = self.vector_types[0].id
    
    for instance in instances:
        vec_data = await self.project.run_async(compute_func, instance.url)
        vector = Vector(type_id=type_id, sha1=instance.sha1, data=vec_data)
        await self.project.add_vector(vector)
    
    return ActionResult(notifs=[Notif(NotifType.INFO, "Succès", "Calcul terminé")])
```

### 3. Clustering
```python
async def compute_clusters(self, ctx: ActionContext, nb_clusters: int):
    instances = await self.project.get_instances(ids=ctx.instance_ids)
    vectors = await self.project.get_vectors(self.vector_types[0].id)
    
    # Calcul clustering...
    id_groups = clustering_algorithm(instances, vectors, nb_clusters)
    
    groups = [
        Group(ids=group_ids.tolist(), name=f"Cluster {i}")
        for i, group_ids in enumerate(id_groups)
    ]
    
    return ActionResult(groups=groups)
```

## Points Clés

1. **IDs négatifs** : Pour nouveaux objets dans commits, auto-résolus à l'insertion
2. **Unicité SHA1** : Déduplication recommandée avant traitement d'images
3. **Thread safety** : Toujours utiliser `run_async()` ou `Task` pour calculs lourds
4. **Gestion d'erreurs** : Panoptic génère automatiquement notifs d'erreur avec stacktrace
5. **Reference** : Plugin officiel **PanopticML** sur GitHub est la meilleure ressource d'exemples

## Exemple Minimal

```python
# __init__.py
from mon_plugin import MonPlugin
plugin_class = MonPlugin

# mon_plugin.py
from panoptic.core.plugin.plugin import APlugin
from panoptic.models import ActionContext
from panoptic.models.results import ActionResult, Notif, NotifType

class MonPlugin(APlugin):
    def __init__(self, project, plugin_path, name):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.add_action_easy(self.ma_fonction, ['execute'])
    
    async def ma_fonction(self, ctx: ActionContext):
        instances = await self.project.get_instances(ctx.instance_ids)
        # Logique...
        return ActionResult(
            notifs=[Notif(NotifType.INFO, "Terminé", f"{len(instances)} images traitées")]
        )
```

