import asyncio
import os
import pickle
import sys

import faiss
import numpy as np
from faiss import write_index

from panoptic.compute.similarity import create_similarity_tree_faiss
from panoptic.core import db, db_utils
from panoptic.models import ComputedValue

async def compute_faiss_index(force=False):
    os.environ['PANOPTIC_DATA'] = '/Users/david/panoptic-projects/faiss'
    await db_utils.init()
    all_images: list[ComputedValue] = await db.get_sha1_computed_values()
    create_similarity_tree_faiss(all_images)
    return

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(compute_faiss_index())

# if __name__ == "__main__":
#     with open(INPUT_PATH, 'rb') as f:
#         dic: dict = pickle.load(f)
#
#     images = []
#     for sha1, vec in dic.items():
#         image = ComputedValue(sha1=sha1, vector=vec, ahash="toto")
#         images.append(image)
#
#     # tree = SimilarityTreeWithLabel(images)
#     #
#     # with open(r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index', 'wb') as f:
#     #     pickle.dump(tree, f)
#     # write_index(tree, r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index')
#     with open(r'D:\Alie\Documents\panoptic_GJ\faiss_tree.index', 'rb') as f:
#         tree = pickle.load(f)
#     print(images[0].sha1)
#     print(tree.query(images[0].vector))


