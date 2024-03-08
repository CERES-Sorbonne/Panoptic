import asyncio

import aiosqlite

from panoptic.core.project.project import Project
from panoptic.models import PropertyType


async def run():
    async def query_data():
        async with aiosqlite.connect('/Users/david/Downloads/panoptic__rkr.db') as db:
            # Execute a SELECT query
            async with db.execute('SELECT * FROM users') as cursor:
                async for row in cursor:
                    print(row)
    # project = Project('/Users/david/panoptic-projects/script', [])
    # await project.start()
    # await project.db.add_property('lala', PropertyType.multi_tags, 'id')
    # await project.close()

asyncio.run(run())
