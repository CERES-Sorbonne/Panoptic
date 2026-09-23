# Tests

## Panoptic

### Backend (`panoptic_back/test`, pytest)

```sh
cd panoptic_back && python -m pytest test panoptic/core/task/tests
```

- `python -m pytest` (pas `pytest` seul) : c'est ce qui rend `panoptic` importable sans l'installer.
- `panoptic/core/task/tests` contient les tests du cycle de vie des plugins.
- Les bases (`*_db.py`), le modèle undo / redo (`test_undo_redo.py`), la migration des anciens
  projets (`test_legacy_migration.py`, `test_conversion.py`), l'import de dossier et l'import / export
  CSV (`test_import_export.py`, sur les images et CSV de `test/data`).
- `test/scripts/` contient des benchmarks, ce ne sont pas des tests.

### Frontend (`panoptic_front/test/group`, node)

```sh
cd panoptic_front
npm test          # suite de non-régression du grouping / clustering
npm run test:sim  # simulation aléatoire
```

Nécessite Node 24. Détails dans `test/group/README.md`.

### Action « Test Installation » (`.github/workflows/test-install-scripts.yml`)

Lance le script d'installation de chaque OS (Linux, macOS, Windows), puis `install/verify_install.py`
(import de torch et vectorisation d'une image avec CLIP).

- Déclenchement manuel uniquement (onglet Actions ou `gh workflow run test-install-scripts.yml`).
- Installe `panoptic` depuis le checkout de la branche, pas depuis PyPI.
- Option `panopticml_branch` : branche GitHub de PanopticML à installer (vide : version PyPI).

## PanopticML

### Tests (`tests/test_transformers.py`, pytest)

Pour chaque modèle de `ModelEnum` : image→vecteur, texte→vecteur, index faiss, recherche
image→image et texte→image, et le chemin de calcul utilisé en prod (`forward_from_arrays`).

```sh
cd PanopticML
PYTHONPATH=../Panoptic/panoptic_back pytest tests
```

- `PYTHONPATH` n'est utile que si `panoptic` n'est pas installé dans l'environnement.
- `PANOPTICML_TEST_MODELS=clip,siglip,dinov3` : ne teste que ces modèles (noms de `ModelEnum`).
  Vide ou `all` : tous les modèles (~11 Go à télécharger au premier lancement).
- `PANOPTICML_DEVICE=cpu|cuda|mps` : force le device, sinon il est détecté automatiquement.
- Ne pas lancer `pytest` à la racine : il récupère `mistral_test.py`, qui n'est pas un test.

### Action « Tests Multi-Plateformes » (`.github/workflows/workflow.yaml`)

Lance les tests sur Python 3.11 à 3.13. Déclenchement manuel, avec ces options :

| Option | Défaut | Rôle |
|---|---|---|
| `os` | `all` | `ubuntu-latest`, `windows-latest`, `macos-latest` ou `all` |
| `panoptic-branch` | vide | Branche GitHub de Panoptic à installer. Vide : dernière version sur PyPI |
| `all-models` | non | Teste tous les modèles, sinon seulement clip, siglip et dinov3 |
| `debug` | non | Ouvre une session tmate si un job échoue (30 min max) |

```sh
gh workflow run workflow.yaml --ref <branche> -f os=macos-latest -f panoptic-branch=main
```

- Tant que Panoptic 1.0 n'est pas sur PyPI, il faut indiquer `panoptic-branch=main`.
- Sur macOS, les tests tournent sur CPU (`PANOPTICML_DEVICE=cpu`), parce que le GPU virtualisé
  des runners donne des vecteurs CLIP / SigLIP faux.
