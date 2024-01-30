import os
import pickle

from tqdm import tqdm

from plugins.FaissPlugin.compute import create_pca, to_pca, create_similarity_tree, can_compute_pca
from panoptic.core.db import db
from panoptic.models import ComputedValue


async def compute_all_pca(project_path: str, force=False):
    # await db_utils.init()
    all_images: list[ComputedValue] = await db.get_sha1_computed_values()
    if not force and not can_compute_pca(len(all_images), all_images[0].vector):
        pass
    else:
        vectors = [i.vector for i in all_images]
        with open(os.path.join(project_path, 'vectors.pkl'), 'wb') as f:
            pickle.dump(vectors, f)
        create_pca(vectors, project_path)
        for i, v in tqdm(zip(all_images, vectors)):
            pca_vec = to_pca(v)
            await db.set_computed_value(i.sha1, i.ahash, pca_vec)
    all_images_pca: list[ComputedValue] = await db.get_sha1_computed_values()
    create_similarity_tree(project_path, all_images_pca)
    await db.vacuum()
    return