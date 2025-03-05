import pandas as pd

from panoptic.models import PropertyType


def parse_string(value):
    return str(value)


def parse_number(value):
    if value is None or value == '':
        return None
    if value.find('.') >= 0:
        value = float(value)
    else:
        value = int(value)
    if pd.isna(value):
        return None
    return value


def parse_tags(value):
    if value is None or value == '' or pd.isnull(value):
        return None
    return value.split(',')


def parse_checkbox(value):
    if value is None or value == '':
        return None
    return True


parser = {
    PropertyType.tag: parse_tags,
    PropertyType.multi_tags: parse_tags,
    PropertyType.string: parse_string,
    PropertyType.number: parse_number,
    PropertyType.date: parse_string,
    PropertyType.color: parse_number,
    PropertyType.url: parse_string,
    PropertyType.checkbox: parse_checkbox
}
