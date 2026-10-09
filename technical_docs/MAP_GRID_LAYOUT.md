# Vue spatiale : mode « grille »

Branche : `feature/map-grid-layout`

## Objectif

Dans la vue spatiale (UMAP / t-SNE / PaCMAP), les vignettes se chevauchent dans les zones denses.
Le mode grille place chaque image dans une case d'une grille régulière, sans aucun chevauchement,
tout en conservant la topologie de la projection :

- des images proches dans la projection restent voisines dans la grille ;
- des groupes éloignés restent séparés (on garde des cases vides entre eux) ;
- on peut basculer à tout moment entre la vue « nuage » et la vue « grille ».

Les images sont toujours jointives (aucun espace entre deux cases occupées). Ce qui sépare les
groupes, ce sont des **cases vides** laissées là où la projection est vide.

## État actuel (ce sur quoi on s'appuie)

- Les coordonnées viennent du plugin (`PanopticML/panoptic_ml.py::_save_map`), normalisées dans un
  disque de rayon 100, stockées à plat `[sha1, x, y, ...]`.
- `MapView.vue::showMap` construit un `PointData` par sha1 présent dans la racine de l'arbre
  (donc **le sous-ensemble affiché**, filtres compris) puis appelle `renderer.createMap`.
- Tout le reste lit uniquement `p.x` / `p.y` : `AtlasLayer.updatePositions`, `SpatialIndex`
  (hover, lasso), `HDLayer`, `focusGroup`. Changer `x/y` + reconstruire l'index suffit donc à
  déplacer les images partout.
- Taille d'une vignette en unités monde (shader `InstancedImageMaterial`) : elle tient dans un carré
  de côté `h = imageSize / 50` aux faibles zooms, et ne fait que rétrécir au-delà (`h·z1/zoom`).
  **Une case carrée de côté ≥ `h` garantit l'absence de chevauchement à tous les zooms.**

## Choix d'architecture

**Calcul côté front, fonction pure, sans dépendance à Three.**

- La grille est calculée **une fois par carte, sur tous ses points** (pas sur le sous-ensemble
  filtré) puis mise en cache : un filtre ne déclenche aucun recalcul, et chaque image garde sa
  case d'un filtre à l'autre. Les images masquées laissent simplement leur case vide.
- La taille d'image ne change que l'échelle (voir §3), pas l'assignation.
- Bascule instantanée, aucun changement backend / plugin / migration.
- Testable en node avec le harnais existant.

Rejeté : une « carte grille » calculée dans PanopticML avec `scipy.optimize.linear_sum_assignment`.
Optimale mais O(n³) (inutilisable au-delà de quelques milliers d'images).

## Algorithme

Entrée : les `N` points `(x, y)` de la carte, `d` = nombre de cases par image (réglage
« cases vides », défaut 1.5 ; `d = 1` → grille pleine, sans aucune case vide).
Sortie : une case entière `(col, row)` distincte par point.

### 0. Dimension de la grille

- `cells = ceil(N · d)` ; `aspect = largeur/hauteur` de la bbox des points (borné à [1/4, 4]).
- `cols = round(sqrt(cells · aspect))`, `rows = ceil(cells / cols)`.
- Chaque point reçoit une cible continue en unités de case :
  `u = (x - minX) / bboxW · cols`, `v = (y - minY) / bboxH · rows`.

`d > 1` est ce qui préserve l'écart entre groupes : avec `d = 1` toutes les cases sont remplies
et deux clusters éloignés dans la projection finissent côte à côte.

### 1. Bissection récursive sous contrainte de capacité — O(N log² N)

```
place(région R = [c0,c1) × [r0,r1), points P)        // invariant : |P| ≤ |R|
    si P vide : fin
    si R n'a qu'une case : P[0] → cette case ; fin
    axe = côté le plus long de R (en cases)
    coupe m = milieu géométrique de R sur cet axe
    gauche = { p ∈ P : coord(p) < m },  droite = le reste
    si |gauche| > capacité(gauche) : transférer à droite les points de gauche les plus proches de m
    si |droite| > capacité(droite) : idem dans l'autre sens
    place(R_gauche, gauche) ; place(R_droite, droite)
```

- Couper au milieu **géométrique** (et non à la médiane des points) laisse vides les zones vides
  de la projection.
- Le débordement ne déplace que les points les plus proches de la coupe : déplacement minimal,
  ordre relatif conservé sur chaque axe.
- Déterministe (tri stable, départage par index).

### 2. Raffinement local par assignation sur fenêtres (optionnel, phase 2)

La bissection peut créer de petits artefacts le long des coupes. On les corrige par passes :

- découper la grille en fenêtres `w × w` (w ≈ 6–8), décalées de `w/2` une passe sur deux ;
- dans chaque fenêtre, résoudre une assignation linéaire (Jonker-Volgenant / hongrois, ≤ 64
  éléments) entre les points de la fenêtre et **toutes** ses cases (vides comprises), coût
  `‖(u,v) − centre(case)‖²` ;
- 2 à 4 passes. Coût ≈ N · w⁴ par passe, quelques centaines de ms pour 100k points.

### 3. Placement en coordonnées monde

`x = (col − cols/2 + 0.5) · s`, `y = (row − rows/2 + 0.5) · s`, avec `s = h` : les images sont
jointives. La bordure de couleur est dessinée à l'intérieur de la vignette, rien ne déborde.

On conserve l'assignation entière `(col, row)` : un changement de taille d'image ne fait que
remettre à l'échelle (pas de recalcul).

## Intégration

### Données

- `MapOptions` (`data/models/tab.ts`) : `layout?: 'scatter' | 'grid'`, `gridDensity?: number`,
  `animateLayout?: boolean`.
  Optionnels, valeurs par défaut posées par le `watch` de `MapView` comme pour `borderWidth`,
  et ajoutées à `createMapOptions` (`data/lib/builders.ts`).
- `PointData` : ajouter `sx`, `sy` (coordonnées d'origine de la projection) ; `x`, `y` restent
  les coordonnées affichées.

### Nouveau module `src/mixins/mapview/GridLayout.ts`

- `computeGridAssignment(xs: Float32Array, ys: Float32Array, density): { cols, rows, col: Int32Array, row: Int32Array }`
  appelé sur `media.maps[mapId].data` entier ; résultat indexé par sha1.
- `gridMetrics(...)` : métriques de qualité (voir Tests), utilisées par les tests et un bench.
- Au-delà d'un seuil (~20k points), exécution dans un Web Worker
  (`new Worker(new URL('./gridLayout.worker.ts', import.meta.url), { type: 'module' })`),
  annulé par le `showMapToken` existant.

### `MapView.vue`

- `showMap` : remplir `sx/sy`, puis `applyLayout()` avant `createMap`.
- `applyLayout()` : en mode `scatter` → `x,y = sx,sy` ; en mode `grid` → assignation de la carte
  (cache par `(mapId, densité)`, calculée à la première bascule) puis placement monde.
- Un changement d'appartenance (filtre, ajout d'images) ne fait que relire le cache.
- Watchers : `layout` et `gridDensity` (debounce) → `applyLayout()` + `renderer.updateLayout()` +
  recadrage ; `imageSize` en mode grille → remise à l'échelle seule.

### `MapRenderer.ts`

- `updateLayout(points)` : `spatialIndex.initTree(points)` + `atlasLayers.updatePositions()`
  (le hover, le lasso et `focusGroup` suivent automatiquement).
- `fitAll()` : `lookAtRect` sur la bbox de tous les points, appelé après une bascule.

### UI

- Barre flottante : bouton bascule `bi-grid-3x3` à côté de « points » (tooltip `map.grid_layout`).
- Barre d'en-tête (`Toolbar.vue`) : curseur « Cases vides » (`gridDensity`, 1.0 → 10, pas 0.1),
  visible seulement en mode grille, sur le modèle du curseur de bordure.
- Barre d'en-tête : case à cocher « Animer les transitions » (`animateLayout`, activée par défaut).
- Clés i18n fr / en.

### Transition animée (phase 3)

Interpolation `scatter ↔ grid` sur ~400 ms : chaque frame écrit `x,y = lerp(...)` puis
`atlasLayers.updatePositions()` ; l'index spatial n'est reconstruit qu'à la fin. Rend la
correspondance entre les deux vues lisible.

Coût : une réécriture de toutes les matrices d'instance par frame (O(N)). Désactivable via
`animateLayout` ; désactivée, la bascule est instantanée. Une nouvelle bascule pendant
l'animation repart des positions courantes.

## Tests

Nouveau dossier `panoptic_front/test/map/` (même principe de bundle que `test/group`), branché sur
`npm test` ; mettre à jour `technical_docs/TESTS.md`.

- **Validité** : bijection points → cases, toutes les cases dans les bornes ; cas N = 0, 1, 2, 3,
  points confondus, points colinéaires, `d = 1` (grille pleine).
- **Déterminisme** : même entrée → même sortie.
- **Voisinages** : sur des nuages synthétiques, part des 10 plus proches voisins conservés
  (seuil à calibrer, viser ≥ 0.5) ; corrélation de Spearman des distances sur un échantillon de
  paires (viser ≥ 0.9).
- **Séparation** : sur des gaussiennes bien séparées, accord du label du 1-plus-proche-voisin dans
  la grille ≥ 0.95, et aucune case d'un groupe enclavée dans un autre.
- **Bench** (hors CI) : temps pour 10k / 50k / 100k points, avec et sans raffinement.

## Découpage

1. ✅ `GridLayout.ts` (bissection) + tests + métriques.
2. ✅ Intégration `MapView` / `MapRenderer`, bouton de bascule, option `layout` persistée, i18n,
   cache par carte, mise à l'échelle sur changement de taille d'image, cadrage à la bascule.
3. ✅ Curseur « cases vides » (`gridDensity`, 1 → 10, persisté), cache limité aux 3 dernières densités
   par carte. Bouton « remplir les cases » (`fillCells`) : vignettes carrées, recadrage centré via les
   UV de l'atlas (`AtlasLayer.setFill`), zone de survol carrée. Zoom minimal abaissé à 0.002 pour
   pouvoir cadrer les grandes grilles.
4. Raffinement par fenêtres + Web Worker pour les grands projets.
5. Transition animée + option pour la désactiver.

## Sélection par cases

Outil de la barre flottante (`bi-bounding-box`), visible seulement en mode grille ; le lasso reste
l'outil du mode nuage, avec la même règle (clic gauche : ajoute, clic droit : retire). Un curseur
carré de N × N cases suit la souris :

- clic / glisser gauche : ajoute les images couvertes à la sélection ; clic droit : les retire ;
- Shift (au clic ou pendant le glisser) : rectangle entre la case de départ et la case courante.
  Firefox ouvre toujours son menu sur Shift + clic droit, sans transmettre l'événement à la page :
  on y fait clic droit puis Shift ;
- Ctrl + molette : taille du curseur (1 → 128, +1 par cran jusqu'à 8 puis ×1.25). Seul le vrai
  Ctrl compte (`keyState.ctrl`) : un pincement de trackpad envoie `ctrlKey` sans `keydown` et
  continue de zoomer. La vignette zoomée (Ctrl au survol) est coupée avec cet outil ;
- Espace + glisser : déplace la carte (dans tous les modes).

Pendant le geste, les cases couvertes qui contiennent une image sont teintées (une texture d'un
texel par case posée sur toute la grille) ; la sélection n'est modifiée qu'au relâchement, en une
fois. Un glissé rapide est comblé par une ligne de Bresenham entre deux positions du curseur.
L'aperçu HD agrandi est coupé (il cacherait le curseur), l'aperçu du panneau de droite suit
toujours l'image survolée.

Logique pure dans `GridBrush.ts` (testée), rendu et geste dans `GridBrushLayer.ts`, événements
dans `MapControl.ts`. `MapView` fournit la table case → image (`gridCells`, construite par
`applyLayout`).

### Pinceau à tags

Deuxième outil de la grille (`bi-brush`), sur le même moteur et avec les mêmes gestes : il pose le
tag choisi au lieu de sélectionner, le clic droit le retire.

- Une section « Pinceau » s'ajoute en haut du panneau de droite : propriété de tags (modifiable,
  hors mode fichier), puis le `TagInput` de l'édition sous les images, en `forceMono` : recherche,
  création d'un tag à la volée, couleur ; la croix du badge désélectionne. Propriété et tag sont
  persistés dans `MapOptions` (`paintPropertyId`, `paintTagId`, `paintCollapsed`).
- Le curseur et les cases couvertes prennent la couleur du tag (bleu de la sélection pour un tag
  sans couleur, que le gris des autres images noierait).
- Tant que l'outil est actif avec un tag choisi, la carte montre ce qui est peint : bordure de la
  couleur du tag sur les images qui le portent, les autres en gris (`PAINT_BORDER`,
  `PAINT_DESATURATE`). La colonne de la propriété est chargée en entier pour ça.
- Un geste = un seul commit (`paintTag.ts`, via `setPropertyValues`) = une entrée d'historique,
  annulable par Ctrl+Z. Seules les images dont la valeur change sont envoyées. Une propriété à tag
  unique voit sa valeur remplacée, une propriété multi-tags reçoit le tag en plus.
- Les valeurs du geste s'affichent tout de suite, avant la réponse du serveur ; le surlignage suit
  ensuite `data.onChange` (geste, annulation, modifications venues d'ailleurs).

## Easter egg

En mode grille, pointeur au-dessus de la carte, le Konami code (↑ ↑ ↓ ↓ ← → ← → B A) lance un
snake sur toute la grille (ses bords sont les murs), la caméra suivant la tête. L'image à manger,
surlignée en rouge, est une image affichée tirée n'importe où dans la grille ; hors de l'écran, une
flèche rouge au bord de la vue indique sa direction (`edgeArrow`). +2 segments par image, vitesse
croissante.
Flèches pour diriger, Échap pour quitter, Espace pour rejouer. Logique pure dans `GridSnake.ts`
(testée), rendu dans `SnakeLayer.ts`, survol coupé pendant la partie.

## Décisions prises

- Grille calculée sur toute la carte, une fois, puis mise en cache (pas de recalcul au filtrage).
- Images jointives ; seules des cases vides séparent les groupes, réglables (`d`, défaut 1.5).
- Transition animée, désactivable.
