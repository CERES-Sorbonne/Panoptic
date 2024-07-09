import io
import time
import hashlib
from PIL import Image
import imagehash
import os
import numpy as np
from multiprocessing import Pool


def compute_sha1(image):
    sha1 = hashlib.sha1()
    sha1.update(image.tobytes())
    return sha1.hexdigest()


def create_thumbnail(image, size=(128, 128)):
    thumbnail = image.copy()
    thumbnail.thumbnail(size)
    return thumbnail


def compute_average_hash(image):
    return str(imagehash.average_hash(image))


def measure_time(image_path):
    times_open = []
    times_sha1 = []
    sha1s = []
    times_thumbnail = []
    times_avg_hash = []

    for _ in range(1):
        # Measure time to open the image
        start_time = time.time()
        img = Image.open(image_path)
        w,h = img.size
        # img.thumbnail(size=(1024, 1024))
        # img = img.convert('RGB')

        img.draft('RGB', size=(1024, 1024))
        b = img.tobytes()
        large_bytes = io.BytesIO()
        img.save(large_bytes, format='jpeg', quality=30)
        large_bytes = large_bytes.getvalue()
        times_open.append((time.time() - start_time) * 1000)  # Convert to milliseconds

        # Measure time for SHA1
        start_time = time.time()
        compute_sha1(img)
        times_sha1.append((time.time() - start_time) * 1000)  # Convert to milliseconds

        # Measure time for thumbnail creation
        start_time = time.time()
        thumbnail = create_thumbnail(img)
        times_thumbnail.append((time.time() - start_time) * 1000)  # Convert to milliseconds

        # Measure time for average hash
        start_time = time.time()
        compute_average_hash(img)
        times_avg_hash.append((time.time() - start_time) * 1000)  # Convert to milliseconds

    avg_time_open = np.mean(times_open)
    avg_time_sha1 = np.mean(times_sha1)
    avg_time_thumbnail = np.mean(times_thumbnail)
    avg_time_avg_hash = np.mean(times_avg_hash)

    return avg_time_open, avg_time_sha1, avg_time_thumbnail, avg_time_avg_hash


def process_image(image):
    image_path = os.path.join('/Users/david/Downloads/saveit/flamboyau_cairn_x147_y70/20220806_20221025_cairnflamboyau_lcfaite_xnview', image)
    avg_times = measure_time(image_path)
    return (image, *avg_times)


# Define the list of images
images = ['I__00019.jpg']

if __name__ == "__main__":
    # Use multiprocessing to process images in parallel
    with Pool(processes=os.cpu_count()) as pool:
        results = pool.map(process_image, images)

    # Display results as a Markdown table
    print("\n# Benchmark Results\n")
    print("| Image       | Open Time (ms) | SHA1 Time (ms) | Thumbnail Time (ms) | Average Hash Time (ms) |")
    print("|-------------|----------------|----------------|---------------------|------------------------|")

    for result in results:
        image, open_time, sha1_time, thumbnail_time, avg_hash_time = result
        print(f"| {image} | {open_time:.2f} | {sha1_time:.2f} | {thumbnail_time:.2f} | {avg_hash_time:.2f} |")
