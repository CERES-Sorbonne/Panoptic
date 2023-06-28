import os
import pickle

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