import os
import multiprocessing
from pathlib import Path
from random import randint
from tempfile import TemporaryDirectory
from time import sleep

from panoptic.core.databases.registry.registry_db import RegistryDB


# Assuming your classes are defined in your project structure:
# from your_module import RegistryDB

def worker_task(db_path, iterations, batch_size):
    """
    Worker process: Creates its own RegistryDB instance and performs allocations.
    """
    try:
        # Every process MUST have its own instance/connection
        db = RegistryDB(db_path)
        db.start()

        process_ids = []
        for _ in range(iterations):
            # allocate now returns a range object
            id_range = db.allocate_commits(batch_size)

            # We add every individual ID in that range to our local list
            process_ids.extend(list(id_range))
            sleep(randint(0,100) / 10000)

        db.close()
        return process_ids
    except Exception as e:
        print(f"Process {os.getpid()} error: {e}")
        return []


def test_run_stress_test():
    # --- Configuration ---
    NUM_PROCESSES = 10
    ITERATIONS_PER_PROC = 50
    BATCH_SIZE = 2  # Each call reserves 10 IDs

    total_expected_count = NUM_PROCESSES * ITERATIONS_PER_PROC * BATCH_SIZE

    with TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "stress_test.db")

        print(f"🚀 Starting Concurrency Test")
        print(f"Processes: {NUM_PROCESSES} | Total IDs expected: {total_expected_count}")

        # Initial setup in main process to ensure tables exist before workers start
        init_db = RegistryDB(db_path)
        init_db.start()
        init_db.close()

        # Run processes in parallel
        with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
            results = pool.starmap(
                worker_task,
                [(db_path, ITERATIONS_PER_PROC, BATCH_SIZE) for _ in range(NUM_PROCESSES)]
            )

        for res in results:
            print(res)

        # Flatten the list of lists from all workers
        all_ids = [item for sublist in results for item in sublist]
        unique_ids = set(all_ids)

        # --- Validation ---
        print("\n" + "=" * 30)
        print("📊 TEST RESULTS")
        print("=" * 30)
        print(f"Total Allocations Attempted: {total_expected_count}")
        print(f"Total IDs Collected:       {len(all_ids)}")
        print(f"Unique IDs Count:          {len(unique_ids)}")

        # 1. Check for duplicates
        if len(all_ids) != len(unique_ids):
            diff = len(all_ids) - len(unique_ids)
            print(f"❌ FAIL: Found {diff} duplicate IDs!")
            assert False
        else:
            print("✅ PASS: No duplicate IDs found.")

        # 2. Check for continuity (No gaps)
        # Since we start at 1, the max ID should equal our total count
        if len(all_ids) > 0:
            max_id = max(all_ids)
            min_id = min(all_ids)
            print(f"Sequence Range:            {min_id} to {max_id}")

            if max_id == total_expected_count and min_id == 1:
                print("✅ PASS: Perfect sequence, no gaps detected.")
            else:
                print(f"⚠️  WARNING: Sequence gap detected. Expected max {total_expected_count}, got {max_id}.")
                assert False
        else:
            print("❌ FAIL: No IDs were collected.")
            assert False
