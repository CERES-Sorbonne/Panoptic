import asyncio
from concurrent.futures import ProcessPoolExecutor


def compute(value):
    return value ** 4


async def launch():
    while True:
        taks = await asyncio.wrap_future(pool.submit(compute, 5))
        # await taks


if __name__ == '__main__':
    # print(' OR '.join(['123', 'lala']))
    pool = ProcessPoolExecutor(max_workers=4)
    asyncio.run(launch())
