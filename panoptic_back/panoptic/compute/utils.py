import os
import pickle

import numpy as np
from sklearn.neighbors import KDTree

from panoptic.models import ImageVector

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
    path = os.path.join(os.getenv('PANOPTIC_DATA'), 'tree.pkl')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return pickle.load(f)


class SimilarityTreeWithLabel:
    def __init__(self, images: list[ImageVector]):
        vectors, sha1_list = zip(*[(i.vector, i.sha1) for i in images])
        self.image_labels = sha1_list
        self.tree = KDTree(vectors)

    def query(self, image: np.ndarray, k=200):
        if k > len(self.image_labels):
            k = len(self.image_labels)
        dist, ind = self.tree.query(image.reshape(1, -1), k)
        indices = [x for x in ind[0]]
        distances = [x for x in dist[0]]
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in enumerate(indices)]