import logging

from panoptic.core.project.project_db import ProjectDb
from .compute.similarity import create_similarity_tree_faiss

logger = logging.getLogger('Create Faiss')


async def compute_faiss_index(path: str, db: ProjectDb, source: str, type_: str):
    logger.info('Start')
    vectors = await db.get_vectors(source, type_)
    create_similarity_tree_faiss(path, vectors)
    logger.info('Success')

