import asyncio

from tqdm import tqdm

from panoptic.core import db, db_utils
from panoptic.compute import create_pca, to_pca, create_similarity_tree, can_use_pca
from panoptic.models import ImageVector


async def compute_all_pca(force=False):
    # await db_utils.init()
    all_images: list[ImageVector] = await db.get_images_with_vectors()
    if not force and not can_use_pca(len(all_images), all_images[0].vector):
        print("can't run PCA yet")
        pass
    else:
        print("get all images: " + str(len(all_images)))
        vectors = [i.vector for i in all_images]
        print("creating pca")
        create_pca(vectors)
        print("converting vectors")
        for i, v in tqdm(zip(all_images, vectors)):
            pca_vec = to_pca(v)
            await db.update_image_hashs(i.sha1, i.ahash, pca_vec)
    all_images_pca: list[ImageVector] = await db.get_images_with_vectors()
    create_similarity_tree(all_images_pca)
    return

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(compute_all_pca())