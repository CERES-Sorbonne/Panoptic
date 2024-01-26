import json
from json import JSONDecodeError


def auto_dict(row, cursor):
    return {key: decode_if_json(value) for key, value in zip([c[0] for c in cursor.description], row)}


def decode_if_json(value):
    try:
        return json.loads(value)
    except (TypeError, JSONDecodeError, UnicodeDecodeError):
        return value
