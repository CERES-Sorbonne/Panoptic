from __future__ import annotations

import math
import os
import pickle
from typing import List

import faiss
import numpy as np
from faiss import index_factory
from scipy.stats import hmean
from sklearn.cluster import DBSCAN, KMeans, estimate_bandwidth, MeanShift
from sklearn.metrics import silhouette_score
from sklearn.neighbors import KDTree
from panoptic.models import ComputedValue, Vector

from .transform import transformer
from .utils import load_similarity_tree


class SimilarityTreeWithLabel:
    def __init__(self, images: list[ComputedValue]):
        vectors, sha1_list = zip(*[(i.vector, i.sha1) for i in images])
        self.image_labels = sha1_list
        self.tree = KDTree(vectors)

    def query(self, image: np.ndarray, k=9999):
        dist, ind = self.tree.query(image.reshape(1, -1), k)
        indices = [x for x in ind[0]]
        distances = [x for x in dist[0]]
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in
                enumerate(indices)]


class SimilarityFaissWithLabel:
    def __init__(self, images: list[Vector]):
        vectors, sha1_list = zip(*[(i.data, i.sha1) for i in images])
        print(sha1_list)
        vectors = np.asarray(vectors)
        faiss.normalize_L2(vectors)
        self.image_labels = sha1_list
        # create the faiss index based on this post: https://anttihavanko.medium.com/building-image-search-with-openai-clip-5a1deaa7a6e2
        nb_vectors = vectors.shape[0]
        vector_size = vectors.shape[1]
        # reduce vector size only if we have more than 100k images otherwise it's not worth it since we lose accuracy
        if nb_vectors < 100000:
            index = faiss.IndexFlatIP(vector_size)
        else:
            cells = min(round(math.sqrt(nb_vectors)), int(nb_vectors / 39))
            index = index_factory(vector_size, f"IVF{cells},PQ16np")
            index.train(vectors)
            index.nprobe = 10
        self.tree = index
        self.tree.add(np.asarray(vectors))

    def query(self, image: np.ndarray, k=99999):
        # by normalizing it allows to search by cosine distance instead of inner product, need to do text / image sim
        faiss.normalize_L2(image)
        vector = image.reshape(1, -1)
        dist, ind = self.tree.search(vector, k)  # len(self.image_labels))
        indices = [x for x in ind[0]]
        distances = [x if x <= 1.0 else 0 for x in dist[0]]  # avoid some strange overflow behavior
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in
                enumerate(indices)]


SIMILARITY_TREE: SimilarityTreeWithLabel | None = None


def reload_tree(path: str):
    global SIMILARITY_TREE
    SIMILARITY_TREE = load_similarity_tree(path)


def create_similarity_tree(path: str, images: list[ComputedValue]):
    tree = SimilarityTreeWithLabel(images)
    with open(os.path.join(path, 'tree.pkl'), 'wb') as f:
        pickle.dump(tree, f)
    global SIMILARITY_TREE
    SIMILARITY_TREE = tree


def create_similarity_tree_faiss(path: str, images: list[Vector]):
    tree = SimilarityFaissWithLabel(images)
    with open(os.path.join(path, 'tree_faiss.pkl'), 'wb') as f:
        pickle.dump(tree, f)
    global SIMILARITY_TREE
    SIMILARITY_TREE = tree


async def get_similar_images_from_text(input_text: str):
    if transformer.can_handle_text:
        vec = transformer.to_text_vector(input_text)
        return SIMILARITY_TREE.query(vec)


def get_similar_images(vectors: list[np.ndarray]):
    print('yayayayaayayayayayayay')
    if not SIMILARITY_TREE:
        raise ValueError("Cannot compute image similarity since KDTree was not computed yet")
    vector = np.mean(vectors, axis=0)
    return SIMILARITY_TREE.query(np.asarray([vector]))


def make_clusters(vectors: List[Vector], *, method='kmeans', **kwargs) -> (list[list[str]], list[int]):
    res_clusters = []
    res_distances = []
    vectors, sha1 = zip(*[(i.data, i.sha1) for i in vectors])
    sha1 = np.asarray(sha1)
    clusters: np.ndarray
    distances: np.ndarray | None = None
    method = "faiss"
    # for now faiss method is better than the others, and probably this will be refactored with plugin system
    # so for now the matching is dead code
    clusters, distances = _make_clusters_faiss(vectors, **kwargs)
    # match method:
    #     case 'kmeans':
    #         clusters = _make_clusters_kmeans(vectors, **kwargs)
    #     case 'dbscan':
    #         clusters = _make_clusters_dbscan(vectors, **kwargs)
    #     case 'meanshift':
    #         clusters = _make_clusters_meanshift(vectors, **kwargs)
    #     case 'faiss':
    #         clusters, distances = _make_clusters_faiss(vectors, **kwargs)
    #     case other:
    #         return [[]]
    for cluster in list(set(clusters)):
        sha1_clusters = sha1[clusters == cluster]
        # sort by average_hash
        # sorted_cluster = [sha1 for _, sha1 in sorted(zip(ahashs_clusters, sha1_clusters))]
        if distances is not None:
            # clusters_distances = distances[clusters == cluster]
            # max_distance = np.max(clusters_distances)
            # clusters_distances / max_distance
            res_distances.append(hmean(distances[clusters == cluster]))
        res_clusters.append(list(sha1_clusters))
    # sort clusters by distances
    # TODO: trouver un meilleur indicateur que juste la moyenne des distances ?
    # TODO: virer les groupes avec une seule image ?
    sorted_clusters = [cluster for _, cluster in sorted(zip(res_distances, res_clusters))]
    return sorted_clusters, sorted(res_distances)


def _make_clusters_dbscan(vectors, eps=3, *args, **kwargs) -> np.ndarray:
    clusters = DBSCAN(eps=eps).fit(np.asarray(vectors))
    return clusters.labels_


def _make_clusters_kmeans(vectors, nb_clusters=6, *args, **kwargs) -> np.ndarray:
    clusters = KMeans(n_clusters=int(nb_clusters)).fit_predict(vectors)
    return clusters


def _make_clusters_faiss(vectors, nb_clusters=6, *args, **kwargs) -> (np.ndarray, np.ndarray):
    def _make_single_kmean(vectors, nb_clusters):
        kmean = faiss.Kmeans(vectors.shape[1], nb_clusters, niter=20, verbose=False)
        kmean.train(vectors)
        return kmean.index.search(vectors, 1)

    vectors = np.asarray(vectors)
    if nb_clusters == 0:
        k_silhouettes = []
        for k in range(3, 30):
            distances, indices = _make_single_kmean(vectors, k)
            indices = indices.flatten()
            k_silhouettes.append(silhouette_score(vectors, indices))
        nb_clusters = int(np.argmax(k_silhouettes)) + 3
    distances, indices = _make_single_kmean(vectors, nb_clusters)
    return indices.flatten(), distances.flatten()


def _make_clusters_meanshift(vectors, *args, **kwargs) -> np.ndarray:
    bandwidth = estimate_bandwidth(vectors, quantile=0.2, n_samples=500)
    clusters = MeanShift(bandwidth=bandwidth, bin_seeding=True).fit(np.asarray(vectors))
    return clusters.labels_
