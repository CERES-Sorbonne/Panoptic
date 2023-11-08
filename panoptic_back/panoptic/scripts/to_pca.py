import asyncio
import os
import pickle

from tqdm import tqdm

from panoptic.compute import create_pca, to_pca, create_similarity_tree, can_compute_pca
from panoptic.core import db
from panoptic.models import ComputedValue


async def compute_all_pca(force=False):
    # await db_utils.init()
    all_images: list[ComputedValue] = await db.get_sha1_computed_values()
    if not force and not can_compute_pca(len(all_images), all_images[0].vector):
        print("can't run PCA yet")
        pass
    else:
        print("get all images: " + str(len(all_images)))
        vectors = [i.vector for i in all_images]
        with open(os.path.join(os.getenv('PANOPTIC_DATA'), 'vectors.pkl'), 'wb') as f:
            pickle.dump(vectors, f)
        print("creating pca")
        create_pca(vectors)
        print("converting vectors")
        for i, v in tqdm(zip(all_images, vectors)):
            pca_vec = to_pca(v)
            await db.set_computed_value(i.sha1, i.ahash, pca_vec)
    all_images_pca: list[ComputedValue] = await db.get_sha1_computed_values()
    create_similarity_tree(all_images_pca)
    await db.vacuum()
    return

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(compute_all_pca())
