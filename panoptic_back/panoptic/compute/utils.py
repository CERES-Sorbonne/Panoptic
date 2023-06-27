import math
import os
import pickle

import faiss
import numpy as np
from faiss import index_factory
from sklearn.neighbors import KDTree

from panoptic.models import ComputedValue

os.environ['PANOPTIC_DATA'] = os.getenv('PANOPTIC_DATA', os.getcwd())


def load_data(data_path=os.getenv('PANOPTIC_DATA')):
    if not data_path:
        raise ValueError("PANOPTIC_DATA was not set")

    full_path = os.path.join(data_path, 'data.pkl')
    if full_path and os.path.exists(full_path):
        with open(full_path, 'rb') as f:
            data = pickle.load(f)
        return data
    return {
        'images': {},
        'pca': None,
        'tree': None
    }


def save_data(images_dict, data_path=os.getenv('PANOPTIC_DATA')):
    if not data_path:
        raise ValueError("PANOPTIC_DATA was not set")

    full_path = os.path.join(data_path, 'data.pkl')
    with open(full_path, 'wb') as f:
        pickle.dump(images_dict, f)


def load_similarity_tree():
    path = os.path.join(os.getenv('PANOPTIC_DATA'), 'tree_faiss.pkl')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return pickle.load(f)


class SimilarityTreeWithLabel:
    def __init__(self, images: list[ComputedValue]):
        vectors, sha1_list = zip(*[(i.vector, i.sha1) for i in images])
        self.image_labels = sha1_list
        self.tree = KDTree(vectors)

    def query(self, image: np.ndarray):
        dist, ind = self.tree.query(image.reshape(1, -1), len(self.image_labels))
        indices = [x for x in ind[0]]
        distances = [x for x in dist[0]]
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in enumerate(indices)]


class SimilarityFaissWithLabel:
    def __init__(self, images: list[ComputedValue]):
        vectors, sha1_list = zip(*[(i.vector, i.sha1) for i in images])
        vectors = np.asarray(vectors)
        self.image_labels = sha1_list
        # create the faiss index based on this post: https://anttihavanko.medium.com/building-image-search-with-openai-clip-5a1deaa7a6e2
        nb_vectors = vectors.shape[0]
        vector_size = vectors.shape[1]
        # reduce vector size only if we have more than 100k images otherwise it's not worth it since we lose accuracy
        if nb_vectors < 100000:
            index = faiss.IndexFlatL2(vector_size)
        else:
            cells = min(round(math.sqrt(nb_vectors)), int(nb_vectors / 39))
            index = index_factory(vector_size, f"IVF{cells},PQ16np")
            index.train(vectors)
        self.tree = index
        self.tree.add(np.asarray(vectors))

    def query(self, image: np.ndarray):
        dist, ind = self.tree.search(np.asarray([image]), 200) # len(self.image_labels))
        indices = [x for x in ind[0]]
        distances = [x for x in dist[0]]
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in enumerate(indices)]