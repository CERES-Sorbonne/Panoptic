import logging

from panoptic.compute.similarity import create_similarity_tree_faiss
from panoptic.core.db import db
from panoptic.models import ComputedValue

logger = logging.getLogger('Create Faiss')


async def compute_faiss_index():
    logger.info('Start')
    all_images: list[ComputedValue] = await db.get_sha1_computed_values()
    create_similarity_tree_faiss(all_images)
    logger.info('Success')

