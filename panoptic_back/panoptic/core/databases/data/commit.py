from typing import Any

from panoptic.core.databases.data.helper import OP_CREATE, OP_UPDATE, OP_DIFF
from panoptic.core.databases.registry.registry_db import RegistryDB
from panoptic.models.data import (
    UpsertCommit, FileSource, Folder, File,
    Instance, Property, Tag, PropertyValueWrite, InstanceValue, Sha1Value
)

class CommitBuilder:
    def __init__(self, registry: RegistryDB):
        self.registry = registry
        self.data = UpsertCommit()

    def create_file_source(self, dtype: str, name: str, root_url: str) -> FileSource:
        fs_id = str(self.registry.allocate_file_sources())
        fs = FileSource(
            id=fs_id,
            dtype=dtype,
            name=name,
            root_url=root_url,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.file_sources[fs_id] = fs
        return fs

    def create_folder(self, source_id: str, path: str, name: str, parent: int | None = None) -> Folder:
        f_id = self.registry.allocate_folders()
        folder = Folder(
            id=f_id,
            source_id=source_id,
            path=path,
            name=name,
            parent=parent,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.folders[f_id] = folder
        return folder

    def create_file(self, name: str, folder_id: int, sha1: str) -> File:
        file_id = self.registry.allocate_files()
        file = File(
            id=file_id,
            name=name,
            folder_id=folder_id,
            sha1=sha1,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.files[file_id] = file
        return file

    def create_instance(self, file_id: int, sha1: str) -> Instance:
        inst_id = self.registry.allocate_instances()
        instance = Instance(
            id=inst_id,
            file_id=file_id,
            sha1=sha1,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.instances[inst_id] = instance
        return instance

    def create_property(self, dtype: str, mode: str, name: str, access='write', tag_list_id=None) -> Property:
        prop_id = self.registry.allocate_properties()
        if tag_list_id is None:
            tag_list_id = prop_id
        prop = Property(
            id=prop_id,
            dtype=dtype,
            mode=mode,
            name=name,
            access=access,
            tag_list_id=tag_list_id,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.properties[prop_id] = prop
        return prop

    def create_tag(self, list_id: int, value: str, color: int, parents: list[int] = None) -> Tag:
        tag_id = self.registry.allocate_tags()
        tag = Tag(
            id=tag_id,
            list_id=list_id,
            parents=parents or [],
            value=value,
            color=color,
            commit_id=0,
            operation=OP_CREATE
        )
        self.data.tags[tag_id] = tag
        return tag

    def update_file_source(self, source: FileSource):
        source.operation = OP_UPDATE
        self.data.file_sources[source.id] = source

    def update_folder(self, folder: Folder):
        folder.operation = OP_UPDATE
        self.data.folders[folder.id] = folder

    def update_file(self, file: File):
        file.operation = OP_UPDATE
        self.data.files[file.id] = file

    def update_instance(self, instance: Instance):
        instance.operation = OP_UPDATE
        self.data.instances[instance.id] = instance

    def update_property(self, prop: Property):
        prop.operation = OP_UPDATE
        self.data.properties[prop.id] = prop

    def update_tag(self, tag: Tag):
        tag.operation = OP_UPDATE
        self.data.tags[tag.id] = tag

    def create_instance_value_write(self, property_id: int, stamp_mode: str = None, ids: list[int] = None, values: Any = None):
        if property_id in self.data.instance_values:
            raise ValueError(f'Write order for property {property_id} already exists.')

        value_write = PropertyValueWrite(
            stamp_mode=stamp_mode,
            keys=ids or [],
            values=values
        )
        self.data.instance_values[property_id] = value_write
        return value_write



    def update_instance_value(self, value: InstanceValue):
        if value.property_id not in self.data.instance_values:
            self.data.instance_values[value.property_id] = []
        if value.operation != OP_DIFF:
            value.operation = OP_UPDATE
        self.data.instance_values[value.property_id].append(value)

    def update_sha1_value(self, value: Sha1Value):
        if value.property_id not in self.data.sha1_values:
            self.data.sha1_values[value.property_id] = []
        if value.operation != OP_DIFF:
            value.operation = OP_UPDATE
        self.data.sha1_values[value.property_id].append(value)

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