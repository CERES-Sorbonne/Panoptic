import logging

from .compute.similarity import create_similarity_tree_faiss
from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface

logger = logging.getLogger('Create Faiss')


async def compute_faiss_index(path: str, db: PluginProjectInterface, source: str, type_: str):
    logger.info('Start')
    vectors = await db.get_vectors(source, type_)
    create_similarity_tree_faiss(path, vectors)
    logger.info('Success')

