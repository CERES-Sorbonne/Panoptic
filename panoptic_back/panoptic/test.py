import asyncio

from panoptic.core import db, db_utils


async def run():
    await db_utils.init()
    res = await db.get_sha1_computed_values()
    lens = {len(r.vector) for r in res}


asyncio.run(run())
