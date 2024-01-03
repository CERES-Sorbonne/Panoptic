import os
import pickle

from panoptic.project_manager import panoptic


def load_data(data_path=None):
    if not data_path:
        data_path = panoptic.project.path

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


def save_data(images_dict, data_path=None):
    if not data_path:
        data_path = panoptic.project.path

    full_path = os.path.join(data_path, 'data.pkl')
    with open(full_path, 'wb') as f:
        pickle.dump(images_dict, f)


def load_similarity_tree(path: str):
    path = os.path.join(path, 'tree_faiss.pkl')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return pickle.load(f)