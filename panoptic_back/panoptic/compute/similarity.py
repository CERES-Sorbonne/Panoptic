import os
import pickle

import numpy as np
from sklearn.cluster import DBSCAN, KMeans, estimate_bandwidth, MeanShift

from panoptic.compute.utils import load_similarity_tree, SimilarityTreeWithLabel
from panoptic.models import ImageVector

SIMILARITY_TREE: SimilarityTreeWithLabel = load_similarity_tree()


def create_similarity_tree(images: list[ImageVector]):
    tree = SimilarityTreeWithLabel(images)
    with open(os.path.join(os.getenv('PANOPTIC_DATA'), 'tree.pkl'), 'wb') as f:
        pickle.dump(tree, f)
    global SIMILARITY_TREE
    SIMILARITY_TREE = tree

def get_similar_images(vector: np.ndarray):
    if not SIMILARITY_TREE:
        raise ValueError("Cannot compute image similarity since KDTree was not computed yet")
    return SIMILARITY_TREE.query(vector, k=200)


def make_clusters(images: list[ImageVector], *, method='kmeans', **kwargs) -> list[list[str]]:
    res = []
    vectors, sha1, ahashs = zip(*[(i.vector, i.sha1, i.ahash) for i in images])
    sha1 = np.asarray(sha1)
    ahashs = np.asarray(ahashs)
    clusters: np.ndarray
    match method:
        case 'kmeans':
            clusters = _make_clusters_kmeans(vectors, **kwargs)
        case 'dbscan':
            clusters = _make_clusters_dbscan(vectors, **kwargs)
        case 'meanshift':
            clusters = _make_clusters_meanshift(vectors, **kwargs)
        case other:
            return [[]]
    for cluster in list(set(clusters)):
        sha1_clusters = sha1[clusters == cluster]
        ahashs_clusters = ahashs[clusters == cluster]
        # sort by average_hash
        sorted_cluster = [sha1 for _, sha1 in sorted(zip(ahashs_clusters, sha1_clusters))]
        res.append(sorted_cluster)
    return res


def _make_clusters_dbscan(vectors, eps=3, *args, **kwargs) -> np.ndarray:
    clusters = DBSCAN(eps=eps).fit(np.asarray(vectors))
    return clusters.labels_


def _make_clusters_kmeans(vectors, nb_clusters=6, *args, **kwargs) -> np.ndarray:
    clusters = KMeans(n_clusters=int(nb_clusters)).fit_predict(vectors)
    return clusters


def _make_clusters_meanshift(vectors, *args, **kwargs) -> np.ndarray:
    bandwidth = estimate_bandwidth(vectors, quantile=0.2, n_samples=500)
    clusters = MeanShift(bandwidth=bandwidth, bin_seeding=True).fit(np.asarray(vectors))
    return clusters.labels_