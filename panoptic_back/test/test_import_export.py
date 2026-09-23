"""Folder import, CSV data import (Importer) and CSV export (Exporter) on a real project.

The CSVs in test/data describe the 10 images of test/data/images (number_1..number_10.png),
with one column per property type.
"""
from pathlib import Path

import pytest

from panoptic.core.project.project import Project

DATA = Path(__file__).parent / 'data'
IMAGES = DATA / 'images'


@pytest.fixture
def project(tmp_path):
    p = Project(tmp_path / 'proj')
    p.start()
    p.import_folder(str(IMAGES)).wait()
    yield p
    p.close()


def _import_csv(project: Project, csv_path: Path) -> dict:
    project.importer.parse_headers(str(csv_path))
    mapping = project.importer.verify_mapping(relative=True, fusion='new')
    project.importer.import_data_and_commit()
    return mapping


def _values_by_file(project: Project) -> dict[str, dict]:
    """{file name: {property name: value}}; tag values as a sorted list of tag names."""
    props = {p.id: p for p in project.get_properties() if not p.system_key}
    tags = {t.id: t.value for t in project.get_tags()}
    by_sha1 = {}
    for v in project.get_sha1_values():
        if v.property_id in props and v.value is not None:
            by_sha1.setdefault(v.sha1, {})[props[v.property_id].name] = v.value
    for v in project.get_sha1_tag_values():
        if v.property_id in props:
            by_sha1.setdefault(v.sha1, {}).setdefault(props[v.property_id].name, []).append(tags[v.tag_id])
    for values in by_sha1.values():
        for name, value in values.items():
            if isinstance(value, list):
                value.sort()
    return {f.name: by_sha1.get(f.sha1, {}) for f in project.get_files()}


def _export(project: Project, folder: Path, name: str) -> list[list[str]]:
    """Exported rows (header first), cells split, multi-tag cells sorted (their order
    in the CSV is not stable)."""
    props = [p.id for p in project.get_properties() if not p.system_key]
    out = project.exporter.export_data(path=str(folder), name=name, properties=props, key='path')
    lines = (Path(out) / 'data.csv').read_text().splitlines()
    rows = [[','.join(sorted(cell.split(','))) for cell in line.split(';')] for line in lines[1:]]
    return [lines[0].split(';')] + sorted(rows)


# ---------------------------------------------------------------------------
# Folder import
# ---------------------------------------------------------------------------

def test_import_folder(project):
    assert len(project.get_instances()) == 10
    folders = {f.id: f.name for f in project.get_folders()}
    assert sorted(folders.values()) == ['2-3', '4-6', '7-10', 'images']
    counts = {folders[fid]: n for fid, n in project.count_instances_per_folder().items() if fid in folders}
    assert counts['2-3'] == 2
    assert counts['4-6'] == 3
    assert counts['7-10'] == 4


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def test_parse_headers_detects_property_types(project):
    headers = project.importer.parse_headers(str(DATA / 'import.csv'))
    assert headers['key'] == 'path'
    assert headers['errors'] == {}
    types = {c['name']: c['type'] for c in headers['col_to_property'].values()}
    assert types == {
        'tag': 'tag', 'multi_tags': 'multi_tags', 'string': 'text', 'number': 'number',
        'date': 'date', 'color': 'color', 'url': 'url', 'checkbox': 'checkbox',
    }


def test_import_csv_values(project):
    mapping = _import_csv(project, DATA / 'import.csv')
    assert mapping['missing_rows'] == []

    values = _values_by_file(project)
    seven = values['number_7.png']
    assert seven['tag'] == ['7']
    assert seven['multi_tags'] == ['7', 'odd']
    assert seven['string'] == 'seven'
    assert float(seven['number']) == 7
    assert str(seven['checkbox']).lower() == 'true'
    # every image got a value for every text column
    assert all(v.get('string') for v in values.values())


def test_import_csv_with_empty_cells(project):
    _import_csv(project, DATA / 'import_with_empty.csv')
    values = _values_by_file(project)
    assert 'tag' not in values['number_1.png']
    assert 'multi_tags' not in values['number_7.png']
    assert 'string' not in values['number_9.png']
    assert 'number' not in values['number_8.png']
    assert float(values['number_1.png']['number']) == 1.1


def test_import_csv_reports_missing_rows(project):
    project.importer.parse_headers(str(DATA / 'import_with_missing.csv'))
    mapping = project.importer.verify_mapping(relative=True, fusion='new')
    # number_200.png and number_300.png are not in the project
    assert len(mapping['missing_rows']) == 2


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('csv_name', ['import.csv', 'import_with_empty.csv'])
def test_export_import_round_trip(project, tmp_path, csv_name):
    """Exporting, re-importing the export into a fresh project and exporting again
    gives the same CSV."""
    _import_csv(project, DATA / csv_name)
    first = _export(project, tmp_path, 'first')
    assert len(first) == 11  # header + 10 images

    other = Project(tmp_path / 'other')
    other.start()
    try:
        other.import_folder(str(IMAGES)).wait()
        _import_csv(other, tmp_path / 'exports' / 'first' / 'data.csv')
        assert _values_by_file(other) == _values_by_file(project)
        assert _export(other, tmp_path, 'second') == first
    finally:
        other.close()
