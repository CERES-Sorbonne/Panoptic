import pickle

import faiss
import numpy as np
from faiss import write_index

from panoptic.models import ComputedValue

INPUT_PATH = r"D:\Alie\Documents\panoptic_GJ\dic_vec_no_pca.pkl"

class SimilarityFaissWithLabel:
    def __init__(self, images: list[ComputedValue]):
        vectors, sha1_list = zip(*[(i.vector, i.sha1) for i in images])
        self.image_labels = sha1_list
        self.tree = faiss.IndexFlatL2(len(vectors[0]))
        self.tree.add(np.asarray(vectors))

    def query(self, image: np.ndarray):
        dist, ind = self.tree.search(np.asarray([image]), 15) # len(self.image_labels))
        indices = [x for x in ind[0]]
        distances = [x for x in dist[0]]
        return [{'sha1': self.image_labels[i], 'dist': float('%.2f' % (distances[index]))} for index, i in enumerate(indices)]

if __name__ == "__main__":
    with open(INPUT_PATH, 'rb') as f:
        dic: dict = pickle.load(f)

    images = []
    for sha1, vec in dic.items():
        image = ComputedValue(sha1=sha1, vector=vec, ahash="toto")
        images.append(image)

    # tree = SimilarityTreeWithLabel(images)
    #
    # with open(r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index', 'wb') as f:
    #     pickle.dump(tree, f)
    # write_index(tree, r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index')
    with open(r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index', 'rb') as f:
        tree = pickle.load(f)
    print(images[0].sha1)
    print(tree.query(images[0].vector))


