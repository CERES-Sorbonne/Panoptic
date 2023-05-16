# TODO: conditionnal imports for people who just want base app

import concurrent.futures.process
import os
import pickle
from pathlib import Path

import cv2
import numpy as np
from imagehash import average_hash
from hashlib import sha1 as sha1hash
import glob
from PIL import Image
from sklearn.decomposition import PCA
from sklearn.neighbors import KDTree
from transformers import AutoImageProcessor, MobileNetV2Model
# from .ocr import full_ocr
from .utils import load_data

from transformers import logging

logging.set_verbosity_error()

PCA_SIZE = 15
USE_PCA_IF_POSSIBLE = True

processor = AutoImageProcessor.from_pretrained("google/mobilenet_v2_1.0_224")
model = MobileNetV2Model.from_pretrained("google/mobilenet_v2_1.0_224")
pca: None | PCA = None
tree: None | KDTree = None
try:
    data = load_data()
except ValueError:
    data = None

"""
every image should be represented this way
{
    'sha1': {
        'ocr': '',
        'vector': '',
        'ahash': '',
        'hash': '',
        'image_path': '',
    }
}
"""


def transform_directory(path: str):
    images_paths = glob.glob(path + "/*.jpg") + glob.glob(path + "/*.png")
    # TODO: make this concurrent
    with concurrent.futures.process.ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(transform_image, path) for path in images_paths]
    return [future.result() for future in concurrent.futures.as_completed(futures)]


def transform_image(_image_path: str, ocr=False):
    image_path = str(Path(_image_path))
    img = Image.open(image_path)

    sha1 = to_sha1(img)
    if sha1 in data:
        return data[sha1]
    label = image_path.split(os.sep)[-1]
    ahash = to_average_hash(img)
    vector = to_vector(img)
    # TODO: conditionnal import if we want to skip ocr
    text, confidence = "", 0
    try:
        if ocr:
            text, confidence = to_ocr(img)
    except cv2.error as e:
        pass
    result = {
        sha1: {
            'ocr': {
                'text': text,
                'confidence': confidence
            },
            'vector': vector,
            'ahash': str(ahash),
            'hash': str(sha1),
            'label': label,
            'path': image_path,
        }
    }

    data[sha1] = result
    # can we trigger pca and use it ?
    if pca is None and can_use_pca(len(data.values()), list(data.values())[0]['vector']):
        sha1_list = list(data.keys())
        vector_list = [data[sha1_key]['vector'] for sha1_key in sha1_list]
        create_pca(vector_list)
        for sha1_key, vector in zip(sha1_list, vector_list):
            data[sha1_key]['vector'] = vector
    return result


def to_sha1(image: Image):
    return str(sha1hash(image.tobytes()))


def to_average_hash(image: Image):
    ahash = average_hash(image)
    return ahash


def to_vector(img):
    input1 = processor(images=img, return_tensors="pt")
    output1 = model(**input1)
    pooled_output1 = output1[1].detach().numpy()
    vector = pooled_output1.flatten()
    # if a pca was already trained use it
    if pca is not None:
        return to_pca(vector)
    return vector


# def to_ocr(image: Image):
#     return full_ocr(image)


def make_clusters(sensibility):
    pass


def load_clusters():
    pass


def create_pca(vectors: []):
    from sklearn.decomposition import PCA
    global pca
    pca = PCA(PCA_SIZE)
    pca.fit(vectors)
    return pca


def to_pca(vectors: []):
    if pca is not None:
        return pca.transform(vectors)


def save_pca():
    with open(os.path.join(os.getenv('PANOPTIC_DATA'), 'pca.pkl'), 'wb') as f:
        pickle.dump(pca, f)


def can_use_pca(nb_vectors: int, vector_sample: np.array) -> bool:
    """
    Can we start training a PCA to reduce vector size ?
    Basically it's: do we have more vectors than 110% the number of dimensions ?
    :param nb_vectors: number of vectors that are going to be used to train pca
    :param vector_sample: one of the vectors
    :return: bool
    """
    if not USE_PCA_IF_POSSIBLE:
        return False
    if nb_vectors > vector_sample.shape[0] + (vector_sample.shape[0] / 10):
        return True
    return False
