import json
from json import JSONDecodeError
from random import randint

from panoptic.models import Tag
from copy import deepcopy


def auto_dict(row, cursor):
    return {key: decode_if_json(value) for key, value in zip([c[0] for c in cursor.description], row)}


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError, UnicodeDecodeError):
        return value


def find_path(tag_index: dict[int, Tag], source: int, target: int):
    if source == 0:
        return False
    if source == target:
        return True
    tag = tag_index[source]

    parents_to_check = []
    for parent in tag.parents:
        if parent == target:
            return True
        parents_to_check.append(parent)

    return any([find_path(tag_index, p, target) for p in parents_to_check])


def safe_update_tag_parents(tag_index: dict[int, Tag], tags: list[Tag]):
    # the tags should have distinct reference from the tag_index
    parents_to_add: dict[int, list[int]] = {}
    for tag in tags:
        if tag.id in tag_index:
            new_parents = set(tag.parents)
            old_parents = set(tag_index[tag.id].parents)
            tag_index[tag.id].parents = list(new_parents & old_parents)
            parents_to_add[tag.id] = list(new_parents - old_parents)
        else:
            tag_index[tag.id] = deepcopy(tag)
            tag_index[tag.id].parents = []
            parents_to_add[tag.id] = tag.parents

    for tag in tags:
        to_add = parents_to_add[tag.id]
        for parent in to_add:
            if find_path(tag_index, parent, tag.id):
                continue
            tag_index[tag.id].parents.append(parent)

    for tag in tags:
        tag.parents = tag_index[tag.id].parents

    return tags


def verify_tag_color(tags: list[Tag]):
    for tag in tags:
        if tag.parents is None:
            tag.parents = []
        if tag.color < 0 or tag.color is None:
            tag.color = randint(0, 11)
