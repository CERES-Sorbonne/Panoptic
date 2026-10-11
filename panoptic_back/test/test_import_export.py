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


def test_import_csv_as_task(project):
    """start_import writes the same values as a direct import, in a background task."""
    project.importer.parse_headers(str(DATA / 'import.csv'))
    project.importer.verify_mapping(relative=True, fusion='new')
    task = project.importer.start_import()
    task.wait()
    assert task.state.finished and not task.state.cancelled
    assert task.state.total == task.state.done == 10
    assert task.state.failed == 0

    values = _values_by_file(project)
    assert values['number_7.png']['multi_tags'] == ['7', 'odd']
    assert all(v.get('string') for v in values.values())


def test_import_csv_upload_is_deleted(project):
    """An uploaded CSV gets its own file, deleted once imported or replaced by another upload."""
    content = (DATA / 'import.csv').read_bytes()
    project.importer.upload('import.csv', content)
    first = Path(project.importer.file_path)
    assert first.name == 'import.csv' and first.read_bytes() == content

    project.importer.upload('import.csv', content)
    second = Path(project.importer.file_path)
    assert not first.exists() and second.exists()

    project.importer.verify_mapping(relative=True, fusion='new')
    project.importer.start_import().wait()
    assert not second.exists()
    assert _values_by_file(project)['number_7.png']['string'] == 'seven'


def test_import_csv_stopped_keeps_written_rows(project, monkeypatch):
    """Stopping an import between commits keeps the rows already written."""
    from panoptic.core.importer import importer
    # One CSV row per commit
    monkeypatch.setattr(importer, '_COMMIT_VALUES', 1)
    project.importer.parse_headers(str(DATA / 'import.csv'))
    project.importer.verify_mapping(relative=True, fusion='new')
    job = project.importer._take_import(None, None)
    progress = job.run()
    assert next(progress) == (1, 0)
    assert next(progress) == (2, 0)
    progress.close()

    with_string = [name for name, v in _values_by_file(project).items() if v.get('string')]
    assert sorted(with_string) == ['number_1.png', 'number_7.png']


def test_import_csv_counts_unparsable_cells(project, tmp_path):
    csv_path = tmp_path / 'bad.csv'
    csv_path.write_text('path;string[text];number[number]\n'
                        'images/number_1.png;one;not a number\n'
                        'images/7-10/number_7.png;seven;7\n')
    project.importer.parse_headers(str(csv_path))
    project.importer.verify_mapping(relative=True, fusion='new')
    task = project.importer.start_import()
    task.wait()
    assert task.state.failed == 1

    values = _values_by_file(project)
    assert values['number_1.png'] == {'string': 'one'}
    assert values['number_7.png']['number'] == 7


def test_import_csv_fusion_new_copies_instance(project, tmp_path):
    """With fusion 'new', a second row for an image whose instance is taken gets a new
    instance of that image."""
    csv_path = tmp_path / 'twice.csv'
    csv_path.write_text('path;note[text]\n'
                        'images/number_1.png;first\n'
                        'images/number_1.png;second\n')
    project.importer.parse_headers(str(csv_path))
    mapping = project.importer.verify_mapping(relative=True, fusion='new')
    assert mapping['new_instances_count'] == 1
    project.importer.import_data_and_commit(properties={'1': {'mode': 'id'}})

    one = next(f for f in project.get_files() if f.name == 'number_1.png')
    instances = [i.id for i in project.get_instances() if i.file_id == one.id]
    assert len(instances) == 2
    notes = {v.value for v in project.get_instance_values() if v.instance_id in instances}
    assert notes == {'first', 'second'}


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
