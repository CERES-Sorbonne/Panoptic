import asyncio
import logging
import os

from panoptic.compute.similarity import create_similarity_tree_faiss
from panoptic.core import db, db_utils
from panoptic.models import ComputedValue

logger = logging.getLogger('Create Faiss')


async def compute_faiss_index():
    logger.info('Start')
    all_images: list[ComputedValue] = await db.get_sha1_computed_values()
    create_similarity_tree_faiss(all_images)
    logger.info('Success')

async def start():
    os.environ['PANOPTIC_DATA'] = "D:\\Alie\\Documents\\panoptic_GJ"
    await db_utils.init()
    await compute_faiss_index()

if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start())

