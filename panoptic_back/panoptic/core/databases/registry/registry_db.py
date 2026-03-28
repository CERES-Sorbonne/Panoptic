import logging

from panoptic.core.databases.registry.create import registry_desc, registry_keys
from panoptic.core.databases.sqlite_db import SQLiteWriter


class RegistryDB(SQLiteWriter):
    def __init__(self, path: str):
        super().__init__(path=path, description=registry_desc)

    def start(self):
        super().start()
        self._initialize_counters()

    def _initialize_counters(self):
        query = "INSERT OR IGNORE INTO registry (key, next_id) VALUES (?, 1)"
        data = [(key,) for key in registry_keys]
        with self.transaction() as tx:
            tx.executemany(query, data)
        logging.info("Registry counters verified.")

    def allocate(self, key: str, number: int = 1) -> int | range:
        if key not in registry_keys:
            raise ValueError(f"Key '{key}' is not a valid registry key.")
        with self.transaction() as tx:
            tx.execute("SELECT next_id FROM registry WHERE key = ?", (key,))
            row = tx.fetchone()
            current_id = row[0] if row else 1
            tx.execute("UPDATE registry SET next_id = next_id + ? WHERE key = ?", (number, key))
            if number > 1:
                return range(current_id, current_id + number)
            return current_id

    # --- Allocation Methods ---
    def allocate_commits(self, n: int = 1) -> int | range:
        return self.allocate('commits', n)

    def allocate_file_sources(self, n: int = 1) -> int | range:
        return self.allocate('file_sources', n)

    def allocate_folders(self, n: int = 1) -> int | range:
        return self.allocate('folders', n)

    def allocate_files(self, n: int = 1) -> int | range:
        return self.allocate('files', n)

    def allocate_instances(self, n: int = 1) -> int | range:
        return self.allocate('instances', n)

    def allocate_properties(self, n: int = 1) -> int | range:
        return self.allocate('properties', n)

    def allocate_tags(self, n: int = 1) -> int | range:
        return self.allocate('tags', n)

    def allocate_maps(self, n: int = 1) -> int | range:
        return self.allocate('maps', n)

    def allocate_vector_types(self, n: int = 1) -> int | range:
        return self.allocate('vector_types', n)