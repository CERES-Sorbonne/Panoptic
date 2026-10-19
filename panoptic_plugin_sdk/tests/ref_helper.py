"""Runs under the python reference backend (panoptic_back/.venv) for cross-implementation tests.

    python ref_helper.py create <project_dir> <images.json>
    python ref_helper.py apply <project_dir> <commits.json>
    python ref_helper.py read <project_dir> <property_id>      -> prints {instance_id: value}
"""
import json
import sys
from pathlib import Path

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.models import (
    DataCommit, File, FileValue, Folder, Instance, InstanceValue, Property, PropertyGroup, Sha1Value, Tag,
)
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.core.project.project import Project


def create(path: Path, images_file: str):
    images = json.loads(Path(images_file).read_text())
    p = Project(path)
    p.start()
    try:
        source_id = p.ensure_local_file_source()
        folders = {}
        with ProjectDB(path / 'project.db') as pdb:
            for folder_path, name, sha1 in images:
                if folder_path not in folders:
                    folders[folder_path] = Folder(id=pdb.allocate_folders(1), source_id=source_id, path=folder_path,
                                                  name=Path(folder_path).name, parent=None)
            files, instances = [], []
            for folder_path, name, sha1 in images:
                f = File(id=pdb.allocate_files(1), name=name, folder_id=folders[folder_path].id, sha1=sha1,
                         width=10, height=10, format='jpeg')
                files.append(f)
                instances.append(Instance(id=pdb.allocate_instances(1), file_id=f.id, sha1=sha1))
        with DataWriter(str(path / 'data.db')) as w:
            w.add_structural(folders=list(folders.values()), files=files, instances=instances)
    finally:
        p.close()
    print(json.dumps({'instances': [[i.id, i.file_id, i.sha1] for i in instances]}))


def _commit(d: dict) -> DataCommit:
    return DataCommit(
        properties=[Property(**r) for r in d.get('properties', [])],
        property_groups=[PropertyGroup(**r) for r in d.get('property_groups', [])],
        tags=[Tag(**r) for r in d.get('tags', [])],
        instance_values=[InstanceValue(**r) for r in d.get('instance_values', [])],
        sha1_values=[Sha1Value(**r) for r in d.get('sha1_values', [])],
        file_values=[FileValue(**r) for r in d.get('file_values', [])],
    )


def apply(path: Path, commits_file: str):
    out = []
    for c in json.loads(Path(commits_file).read_text()):
        with DataWriter(str(path / 'data.db')) as w:
            res = w.apply_commit(c.get('source', 'plugin'), _commit(c['commit']), group_id=c.get('group_id'),
                                 author=c.get('author'))
        out.append(res.id if res else None)
    print(json.dumps(out))


def read(path: Path, prop_id: str):
    with DataReader(str(path / 'data.db')) as r:
        prop = r.get_properties(id=int(prop_id))[0]
        ids, values = r.get_full_column(prop.id, prop.mode, prop.system_key)
    print(json.dumps({str(i): v for i, v in zip(ids, values)}, default=str))


if __name__ == '__main__':
    cmd, path, arg = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    {'create': create, 'apply': apply, 'read': read}[cmd](path, arg)
