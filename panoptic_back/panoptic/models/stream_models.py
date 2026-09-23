"""msgspec Struct models for the db_state_stream ndjson response.

DB models (Property, Tag, etc.) are used directly as the source of truth.
The only model defined here that has no DB equivalent is FullInstance,
which is a join of the Instance and File tables.
Frontend translates the few field-name mismatches (e.g. dtype→type).
"""
from __future__ import annotations

from typing import Any, Optional

import msgspec


class FullInstance(msgspec.Struct):
    """Instance enriched with File data (folder_id, file_id, name, extension, url)."""
    id: int
    sha1: Optional[str]
    name: str
    ahash: str
    width: int
    height: int
    url: str
    folder_id: Optional[int]
    file_id: Optional[int]
    extension: str
    properties: dict


class StreamChunk(msgspec.Struct, omit_defaults=True):
    """Subset of a DbCommit sent in one stream line or delta response."""
    instances: Optional[list[FullInstance]] = None
    properties: Optional[list[Any]] = None
    tags: Optional[list[Any]] = None
    property_groups: Optional[list[Any]] = None
    # Delete fields — only present in delta responses, omitted from stream via omit_defaults
    empty_instances:        Optional[list[int]] = None
    empty_properties:       Optional[list[int]] = None
    empty_tags:             Optional[list[int]] = None
    empty_property_groups:  Optional[list[int]] = None
    empty_instance_values: Optional[list[Any]] = None  # [{property_id, instance_id}]
    empty_image_values:    Optional[list[Any]] = None  # [{property_id, sha1}]
    empty_file_values:     Optional[list[Any]] = None  # [{property_id, file_id}]


class InstanceValuesColumn(msgspec.Struct):
    """Columnar instance-value batch for a single property.

    Each entry in values is a JSON-encoded string; the frontend calls
    JSON.parse() on each one (matching the v1 wire format).
    """
    property_id: int
    ids: list[int]
    values: list[str]


class ImageValuesColumn(msgspec.Struct):
    """Columnar sha1-value batch for a single property."""
    property_id: int
    sha1s: list[str]
    values: list[str]


class FileValuesColumn(msgspec.Struct):
    """Columnar file-value batch for a single property."""
    property_id: int
    file_ids: list[int]
    values: list[str]


class LoadState(msgspec.Struct):
    finished_property: bool = False
    finished_instance: bool = False
    finished_tags: bool = False
    finished_instance_values: bool = False
    finished_image_values: bool = False
    finished_file_values: bool = False
    finished_property_groups: bool = False

    counter_instance: int = 0
    counter_instance_value: int = 0
    counter_image_value: int = 0
    counter_file_value: int = 0

    max_instance: int = 0
    max_instance_value: int = 0
    max_image_value: int = 0
    max_file_value: int = 0

    max_sequence: int = 0


class TagCount(msgspec.Struct):
    tag_id: int
    count: int


class StreamResult(msgspec.Struct, omit_defaults=True):
    """One ndjson line in the db_state_stream response."""
    state: LoadState
    chunk: Optional[StreamChunk] = None
    instance_values: Optional[list[InstanceValuesColumn]] = None
    image_values: Optional[list[ImageValuesColumn]] = None
    file_values: Optional[list[FileValuesColumn]] = None
    tag_counts: Optional[list[TagCount]] = None
    folder_counts: Optional[dict[int, int]] = None
