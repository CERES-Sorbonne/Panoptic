"""CSV and image exporter for Panoptic V2."""
from __future__ import annotations

import datetime
import os
import shutil
from typing import Any, TYPE_CHECKING

import polars as pl

from panoptic.core.databases.data.system_properties import SYSTEM_PROPERTY_MAP

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
    from panoptic.core.databases.data.data_reader import DataReader

_TAG_DTYPES = {'tag', 'multi_tags'}

# Above this many properties, build the DataFrame in horizontal slices to cap
# peak memory usage (each slice is written as a CSV chunk).
_PROP_CHUNK = 200

# Above this many instances, iterate rows in batches rather than loading all
# property columns into one wide frame at once.
_ROW_CHUNK = 500_000


class Exporter:
    def __init__(self, project: 'Project'):
        self.project = project

    def export_data(self, path: str, name: str | None = None,
                    instance_ids: list[int] | None = None,
                    properties: list[int] | None = None,
                    copy_images: bool = False,
                    key: str = 'id') -> str:
        if not name:
            name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        export_dir = os.path.join(path, 'exports', name)
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        os.makedirs(export_dir, exist_ok=True)

        with self.project._data_reader() as reader:
            if properties:
                csv_path = os.path.join(export_dir, 'data.csv')
                self._write_csv(reader, csv_path, instance_ids, properties, key)

            if copy_images:
                img_dir = os.path.join(export_dir, 'images')
                os.makedirs(img_dir, exist_ok=True)
                self._copy_images(reader, instance_ids, img_dir)

        return export_dir

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write_csv(self, reader: 'DataReader', csv_path: str,
                   instance_ids: list[int] | None,
                   property_ids: list[int],
                   key: str) -> None:
        # --- metadata (small, always fits in memory) ---
        prop_map = {p.id: p for p in reader.get_properties()}
        tag_map  = {t.id: t.value for t in reader.get_tags()}

        # --- base instance list ---
        from panoptic.core.databases.entity_schema import OP_DELETE
        from panoptic.core.databases.data.create import (
            INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA,
        )

        if instance_ids is not None:
            rows = INSTANCES_SCHEMA.get(reader.conn, id=instance_ids)
        else:
            rows = reader.get_instances()

        all_ids     = [i.id      for i in rows]
        all_sha1s   = [i.sha1    for i in rows]
        all_file_ids = [i.file_id for i in rows]

        if not all_ids:
            return

        # --- key column ---
        key_col = self._build_key_column(reader, key, all_ids, all_file_ids,
                                         FILES_SCHEMA, FOLDERS_SCHEMA)

        # --- column headers ---
        valid_prop_ids = [p for p in property_ids if p in prop_map]
        col_names = [
            f"{prop_map[p].name}[{prop_map[p].dtype}]"
            for p in valid_prop_ids
        ]

        base = pl.DataFrame({key: key_col})

        # Choose strategy based on dataset size
        if len(all_ids) <= _ROW_CHUNK:
            df = self._build_wide_frame(
                reader, base, key, all_ids, all_sha1s, all_file_ids,
                valid_prop_ids, col_names, prop_map, tag_map,
            )
            df.write_csv(csv_path, separator=';')
        else:
            self._write_chunked(
                reader, csv_path, key, all_ids, all_sha1s, all_file_ids,
                valid_prop_ids, col_names, prop_map, tag_map,
            )

    # ------------------------------------------------------------------

    def _build_key_column(self, reader, key: str,
                          all_ids, all_file_ids,
                          FILES_SCHEMA, FOLDERS_SCHEMA) -> list[str]:
        if key == 'id':
            return [str(i) for i in all_ids]

        file_rows   = FILES_SCHEMA.get(reader.conn)
        folder_rows = FOLDERS_SCHEMA.get(reader.conn)
        file_map    = {f.id: f for f in file_rows}
        folder_map  = {f.id: f for f in folder_rows}

        result = []
        for file_id in all_file_ids:
            f = file_map.get(file_id)
            if not f:
                result.append('')
                continue
            if key == 'local_path':
                folder = folder_map.get(f.folder_id)
                base   = os.path.basename(f.name or '')
                result.append(f"{folder.name if folder else ''}/{base}")
            else:  # global_path / path
                result.append(f.name or '')
        return result

    # ------------------------------------------------------------------

    def _build_wide_frame(self, reader, base: pl.DataFrame, key: str,
                          all_ids, all_sha1s, all_file_ids,
                          valid_prop_ids, col_names,
                          prop_map, tag_map) -> pl.DataFrame:
        """Assemble the full DataFrame in one pass (fits in memory)."""
        id_series = pl.Series('__id__', all_ids)

        for prop_id, col_name in zip(valid_prop_ids, col_names):
            prop = prop_map[prop_id]
            inst_ids, values = reader.get_full_column(
                prop_id, prop.mode, prop.system_key
            )
            if not inst_ids:
                base = base.with_columns(pl.lit(None).cast(pl.String).alias(col_name))
                continue

            is_tag = prop.dtype in _TAG_DTYPES

            sparse = pl.DataFrame({
                '__id__': pl.Series(inst_ids, dtype=pl.Int64),
                col_name: pl.Series(values),
            })
            joined = id_series.to_frame().join(sparse, on='__id__', how='left')

            if is_tag:
                col_series = joined[col_name].map_elements(
                    lambda ids: ','.join(tag_map[i] for i in (ids or []) if i in tag_map),
                    return_dtype=pl.String,
                )
            else:
                col_series = joined[col_name].cast(pl.String)

            base = base.with_columns(col_series)

        return base

    # ------------------------------------------------------------------

    def _write_chunked(self, reader, csv_path: str, key: str,
                       all_ids, all_sha1s, all_file_ids,
                       valid_prop_ids, col_names,
                       prop_map, tag_map) -> None:
        """Row-chunked path for very large instance counts.

        Loads values for one chunk of instances at a time to keep memory
        proportional to chunk_size × n_properties rather than n_instances ×
        n_properties.
        """
        header_written = False

        for chunk_start in range(0, len(all_ids), _ROW_CHUNK):
            chunk_ids      = all_ids     [chunk_start: chunk_start + _ROW_CHUNK]
            chunk_file_ids = all_file_ids[chunk_start: chunk_start + _ROW_CHUNK]

            from panoptic.core.databases.data.create import FILES_SCHEMA, FOLDERS_SCHEMA
            key_col = self._build_key_column(
                reader, key, chunk_ids, chunk_file_ids, FILES_SCHEMA, FOLDERS_SCHEMA
            )
            chunk_df = pl.DataFrame({key: key_col})
            id_series = pl.Series('__id__', chunk_ids)

            for prop_id, col_name in zip(valid_prop_ids, col_names):
                prop = prop_map[prop_id]
                val_map: dict[int, Any] = reader.get_values_for_instances(
                    chunk_ids, prop_id, prop.mode, prop.system_key
                )
                values = [val_map.get(i) for i in chunk_ids]

                is_tag = prop.dtype in _TAG_DTYPES
                if is_tag:
                    str_values = [
                        ','.join(tag_map[t] for t in (v or []) if t in tag_map)
                        if v is not None else None
                        for v in values
                    ]
                    chunk_df = chunk_df.with_columns(
                        pl.Series(col_name, str_values, dtype=pl.String)
                    )
                else:
                    chunk_df = chunk_df.with_columns(
                        pl.Series(col_name, [str(v) if v is not None else None for v in values],
                                  dtype=pl.String)
                    )

            if not header_written:
                chunk_df.write_csv(csv_path, separator=';')
                header_written = True
            else:
                with open(csv_path, 'a', encoding='utf-8') as f:
                    f.write(chunk_df.write_csv(separator=';', include_header=False))

    # ------------------------------------------------------------------

    def _copy_images(self, reader: 'DataReader',
                     instance_ids: list[int] | None, dest: str) -> None:
        from panoptic.core.databases.data.create import INSTANCES_SCHEMA, FILES_SCHEMA
        from panoptic.core.databases.entity_schema import OP_DELETE

        if instance_ids is not None:
            insts = INSTANCES_SCHEMA.get(reader.conn, id=instance_ids)
        else:
            insts = reader.get_instances()

        file_ids = [i.file_id for i in insts if i.file_id is not None]
        if not file_ids:
            return

        file_map = {f.id: f for f in FILES_SCHEMA.get(reader.conn, id=file_ids)}
        for file_id in file_ids:
            f = file_map.get(file_id)
            if f and f.name and os.path.exists(f.name):
                try:
                    shutil.copy(f.name, dest)
                except Exception:
                    pass
