import asyncio
import hashlib

import aiofiles
import aiohttp as aiohttp
from PIL import Image


async def download_stream(src_url, chunk_size=65536):
    try:
        connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(src_url) as resp:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    yield chunk
    except Exception as e:
        raise e


async def download_save_stream(src_url, dest_file, chunk_size=65536):
    async with aiofiles.open(dest_file, 'wb') as fd:
        async for chunk in download_stream(src_url, chunk_size=chunk_size):
            await fd.write(chunk)
            yield chunk


async def launch():
    sha1 = hashlib.sha1()
    async for data in download_save_stream(src_url='https://pbs.twimg.com/media/FxclmLOaEAE45CY.jpg',
                                           dest_file='tmp.jpg', chunk_size=65536):
        sha1.update(data)

    sha1 = sha1.hexdigest()
    print(sha1)

    image = Image.open('tmp.jpg')
    sha1_hash = hashlib.sha1(image.tobytes()).hexdigest()
    print(sha1_hash)


asyncio.run(launch())
