import asyncio

from panoptic.core.project.project import Project
from panoptic.models import PropertyType


async def run():
    project = Project('/Users/david/panoptic-projects/script', [])
    await project.start()
    await project.db.add_property('lala', PropertyType.multi_tags, 'id')
    await project.close()

asyncio.run(run())
