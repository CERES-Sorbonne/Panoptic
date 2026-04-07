from typing import Any
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models.data import (
    UpsertCommit, FileSource, Folder, File,
    Instance, Property, Tag, PropertyValueWrite
)

class CommitBuilder:
    def __init__(self, registry: RegistryDB):
        self.registry = registry
        self.data = UpsertCommit()

    def add_file_source(self, dtype: str, name: str, root_url: str) -> FileSource:
        fs_id = str(self.registry.allocate_file_sources())
        fs = FileSource(
            id=fs_id,
            dtype=dtype,
            name=name,
            root_url=root_url,
            commit_id=0
        )
        self.data.file_sources[fs_id] = fs
        return fs

    def add_folder(self, source_id: str, path: str, name: str, parent: int | None = None) -> Folder:
        f_id = self.registry.allocate_folders()
        folder = Folder(
            id=f_id,
            source_id=source_id,
            path=path,
            name=name,
            parent=parent,
            commit_id=0
        )
        self.data.folders[f_id] = folder
        return folder

    def add_file(self, name: str, folder_id: str, sha1: str) -> File:
        file_id = self.registry.allocate_files()
        file = File(
            id=file_id,
            name=name,
            folder_id=folder_id,
            sha1=sha1,
            commit_id=0
        )
        self.data.files[file_id] = file
        return file

    def add_instance(self, file_id: int, sha1: str) -> Instance:
        inst_id = self.registry.allocate_instances()
        instance = Instance(
            id=inst_id,
            file_id=file_id,
            sha1=sha1,
            commit_id=0
        )
        self.data.instances[inst_id] = instance
        return instance

    def add_property(self, dtype: str, mode: str, name: str, access='write', layer=None) -> Property:
        prop_id = self.registry.allocate_properties()
        if layer is None:
            layer = prop_id
        prop = Property(
            id=prop_id,
            dtype=dtype,
            mode=mode,
            name=name,
            access=access,
            layer=layer,
            commit_id=0
        )
        self.data.properties[prop_id] = prop
        return prop

    def add_tag(self, property_id: int, value: str, color: int, parents: list[int] = None) -> Tag:
        tag_id = self.registry.allocate_tags()
        tag = Tag(
            id=tag_id,
            property_id=property_id,
            parents=parents or [],
            value=value,
            color=color,
            commit_id=0
        )
        self.data.tags[tag_id] = tag
        return tag

    def add_instance_value_write(self, property_id: int, stamp_mode: str = None, ids: list[int] = None, values: Any = None):
        if property_id in self.data.instance_values:
            raise ValueError(f'Write order for property {property_id} already exists.')

        value_write = PropertyValueWrite(
            stamp_mode=stamp_mode,
            keys=ids or [],
            values=values
        )
        self.data.instance_values[property_id] = value_write
        return value_write

    def add_sha1_value_write(self, property_id: int, stamp_mode: str = None, sha1s: list[str] = None, values: Any = None):
        if property_id in self.data.instance_values:
            raise ValueError(f'Write order for property {property_id} already exists.')

        value_write = PropertyValueWrite(
            stamp_mode=stamp_mode,
            keys=sha1s or [],
            values=values
        )
        self.data.sha1_values[property_id] = value_write
        return value_write

    def build(self) -> UpsertCommit:
        return self.data