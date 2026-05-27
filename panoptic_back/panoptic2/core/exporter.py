"""CSV and image exporter for Panoptic V2."""
from __future__ import annotations

import datetime
import os
import shutil
from typing import Any, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from panoptic2.core.project.project import Project2


class Exporter2:
    def __init__(self, project: 'Project2'):
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

        if properties:
            df = self._build_csv(instance_ids, properties, key)
            df.write_csv(os.path.join(export_dir, 'data.csv'), separator=';')

        if copy_images:
            img_dir = os.path.join(export_dir, 'images')
            os.makedirs(img_dir, exist_ok=True)
            self._copy_images(instance_ids, img_dir)

        return export_dir

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_csv(self, instance_ids: list[int] | None,
                   property_ids: list[int], key: str) -> pl.DataFrame:
        all_insts = self.project.get_instances()
        if instance_ids is not None:
            id_set    = set(instance_ids)
            all_insts = [i for i in all_insts if i.id in id_set]

        prop_map   = {p.id: p for p in self.project.get_properties()}
        file_map   = {f.id: f for f in self.project.get_files()}
        folder_map = {f.id: f for f in self.project.get_folders()}
        tag_map    = {t.id: t for t in self.project.get_tags()}

        # Build value look-up tables
        prop_id_set = set(property_ids)
        iv_index: dict[tuple[int, int], Any] = {}    # (prop_id, inst_id) → value
        sv_index: dict[tuple[int, str], Any] = {}    # (prop_id, sha1)    → value
        for iv in self.project.get_instance_values():
            if iv.property_id in prop_id_set:
                iv_index[(iv.property_id, iv.instance_id)] = iv.value
        for sv in self.project.get_sha1_values():
            if sv.property_id in prop_id_set:
                sv_index[(sv.property_id, sv.sha1)] = sv.value

        # Column headers
        prop_cols = [
            f"{prop_map[p].name}[{prop_map[p].dtype}]"
            for p in property_ids if p in prop_map
        ]
        columns = [key, *prop_cols]

        rows: list[list[str | None]] = []
        for inst in all_insts:
            f   = file_map.get(inst.file_id)
            row: list[str | None] = []

            # Key column
            if key == 'id':
                row.append(str(inst.id))
            elif key == 'local_path':
                if f:
                    folder = folder_map.get(f.folder_id)
                    base   = os.path.basename(f.name or '')
                    row.append(f"{folder.name if folder else ''}/{base}")
                else:
                    row.append('')
            else:   # global_path / path
                row.append(f.name or '' if f else '')

            # Property columns
            for prop_id in property_ids:
                prop = prop_map.get(prop_id)
                if not prop:
                    row.append(None)
                    continue

                val: Any
                if prop.mode == 'sha1' and inst.sha1:
                    val = sv_index.get((prop_id, inst.sha1))
                else:
                    val = iv_index.get((prop_id, inst.id))

                if val is None:
                    row.append(None)
                elif prop.dtype in {'tag', 'multi_tags'} and isinstance(val, list):
                    row.append(','.join(tag_map[t].value for t in val if t in tag_map))
                else:
                    row.append(str(val))

            rows.append(row)

        if not rows:
            rows = [[''] * len(columns)]

        data = {col: [r[i] for r in rows] for i, col in enumerate(columns)}
        return pl.DataFrame(data)

    def _copy_images(self, instance_ids: list[int] | None, dest: str):
        all_insts = self.project.get_instances()
        if instance_ids is not None:
            id_set    = set(instance_ids)
            all_insts = [i for i in all_insts if i.id in id_set]
        file_map = {f.id: f for f in self.project.get_files()}
        for inst in all_insts:
            f = file_map.get(inst.file_id)
            if f and f.name and os.path.exists(f.name):
                try:
                    shutil.copy(f.name, dest)
                except Exception:
                    pass
