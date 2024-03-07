# TODO: conditionnal imports for people who just want base app
from __future__ import annotations

import os
import pickle
from hashlib import sha1 as sha1hash

import numpy as np
from PIL import Image
from imagehash import average_hash
from sklearn.decomposition import PCA
from sklearn.neighbors import KDTree

from .transformers import get_transformer
PCA_SIZE = 10
USE_PCA_IF_POSSIBLE = True

transformer = get_transformer("clip")

pca: None | PCA = None
tree: None | KDTree = None


def to_sha1(image: Image) -> str:
    return sha1hash(image.tobytes()).hexdigest()


def to_vector(image: Image, project_path: str):
    vec = transformer.to_vector(image)
    # if a pca was already trained use it
    if get_pca(project_path) is not None:
        return to_pca(vec)
    return vec


def to_average_hash(image: Image):
    ahash = average_hash(image)
    return ahash


# def to_ocr(image: Instance):
#     return full_ocr(image)

def get_pca(project_path: str):
    path = os.path.join(project_path, 'pca.pkl')
    global pca
    if pca:
        return pca
    if not pca and os.path.exists(path):
        with open(path, 'rb') as f:
            pca = pickle.load(f)
        return pca
    return None


def create_pca(vectors: [], project_path: str):
    from sklearn.decomposition import PCA
    global pca
    pca = PCA(PCA_SIZE)
    pca.fit(vectors)
    save_pca(project_path)


def to_pca(vector: np.ndarray):
    if pca is not None:
        return np.float32(pca.transform([vector])[0])


def save_pca(project_path: str):
    with open(os.path.join(project_path, 'pca.pkl'), 'wb') as f:
        pickle.dump(pca, f)


def can_compute_pca(nb_vectors: int, vector_sample: np.array) -> bool:
    """
    Can we start training a PCA to reduce vector size ?
    Basically it's: do we have more vectors than 110% the number of dimensions ?
    :param nb_vectors: number of vectors that are going to be used to train pca
    :param vector_sample: one of the vectors
    :return: bool
    """
    if not USE_PCA_IF_POSSIBLE:
        return False
    if get_pca() is not None:
        return False
    if nb_vectors > vector_sample.shape[0] + (vector_sample.shape[0] / 10):
        return True
    return False