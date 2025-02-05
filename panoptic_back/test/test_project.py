from collections import defaultdict
from pathlib import Path

from panoptic.core.project.project import Project
from panoptic.models import PropertyType, Property, PropertyMode, InstanceProperty, DbCommit, Instance
from panoptic.utils import Trie, RelativePathTrie

TAG_ID = 1
MULTI_TAGS_ID = 2
STRING_ID = 3
NUMBER_ID = 4
DATE_ID = 5
COLOR_ID = 6
URL_ID = 7
CHECKBOX_ID = 8


async def test_create_project(tmp_path: str):
    project = Project(tmp_path, [])
    await project.start()
    await project.wait_full_start()

    instances = await project.db.get_instances()
    assert len(instances) == 0

    await project.close()


async def test_load_instance_project(instance_project: Project):
    db = instance_project.db
    folders = await db.get_folders()
    assert len(folders) == 4

    instances = await db.get_instances()
    assert len(instances) == 10

    folder_index = {f.name: f for f in folders}
    index = defaultdict(int)
    for instance in instances:
        index[instance.folder_id] += 1

    assert index[folder_index["images"].id] == 1
    assert index[folder_index["2-3"].id] == 2
    assert index[folder_index["4-6"].id] == 3
    assert index[folder_index["7-10"].id] == 4


async def test_load_data_project(data_project: Project):
    db = data_project.db
    instances = await db.get_instances()
    instance_index = {i.name: i for i in instances}

    assert len(instances) == 10

    properties = await db.get_properties()

    assert len(properties) == 8

    instance_values = await db.get_instance_property_values(instance_ids=[i.id for i in instances])
    image_values = await db.get_image_property_values(sha1s=list({i.sha1 for i in instances}))

    assert len(image_values) == 25
    assert len(instance_values) == 50

    instance1 = instance_index['number_1.png']
    values1 = await db.get_property_values(instances=[instance1])
    values1_index = {v.property_id: v.value for v in values1}

    assert len(values1_index[TAG_ID]) == 1
    assert len(values1_index[MULTI_TAGS_ID]) == 2
    assert values1_index[STRING_ID] == 'one'
    assert values1_index[NUMBER_ID] == 1
    assert values1_index[DATE_ID] == "2024-09-01T00:00:00Z"
    assert values1_index[COLOR_ID] == 0
    assert values1_index[URL_ID] == "1"
    assert values1_index[CHECKBOX_ID] is True

    instance10 = instance_index['number_10.png']
    values10 = await db.get_property_values(instances=[instance10])
    values10_index = {v.property_id: v.value for v in values10}

    assert len(values10_index[TAG_ID]) == 1
    assert len(values10_index[MULTI_TAGS_ID]) == 2
    assert values10_index[STRING_ID] == 'ten'
    assert values10_index[NUMBER_ID] == 10
    assert values10_index[DATE_ID] == "2024-09-10T00:00:00Z"
    assert values10_index[COLOR_ID] == 9
    assert values10_index[URL_ID] == "10"
    assert CHECKBOX_ID not in values10_index


async def test_import_images(empty_project: Project, image_dir: str):
    await empty_project.import_folder(image_dir)
    await empty_project.task_queue.onFinish.wait()

    db = empty_project.db
    folders = await db.get_folders()
    assert len(folders) == 4

    instances = await db.get_instances()
    assert len(instances) == 10

    folder_index = {f.name: f for f in folders}
    index = defaultdict(int)
    for instance in instances:
        index[instance.folder_id] += 1

    assert index[folder_index["images"].id] == 1
    assert index[folder_index["2-3"].id] == 2
    assert index[folder_index["4-6"].id] == 3
    assert index[folder_index["7-10"].id] == 4


async def test_import_data_mode_instance(instance_project: Project, import_csv: str):
    await instance_project.importer.upload_csv(import_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new')
    await instance_project.importer.confirm_import()

    db = instance_project.db
    instances = await db.get_instances()
    instance_index = {i.name: i for i in instances}

    assert len(instances) == 10

    properties = await db.get_properties()

    assert len(properties) == 8

    instance_values = await db.get_instance_property_values(instance_ids=[i.id for i in instances])
    image_values = await db.get_image_property_values(sha1s=list({i.sha1 for i in instances}))

    assert len(image_values) == 0
    assert len(instance_values) == 75

    instance_values_index = defaultdict(list)
    for val in instance_values:
        instance_values_index[val.property_id].append(val)

    property_index = {p.type: p for p in properties}

    instance_1 = instance_index['number_1.png']
    instance_8 = instance_index['number_8.png']

    tag_property = property_index[PropertyType.tag]
    tag_values = instance_values_index[tag_property.id]
    assert all([type(v.value) == list for v in tag_values])
    assert all([len(v.value) == 1 for v in tag_values])

    multi_tag_property = property_index[PropertyType.multi_tags]
    multi_tag_values = instance_values_index[multi_tag_property.id]
    assert all([type(v.value) == list for v in multi_tag_values])
    assert all([len(v.value) == 2 for v in multi_tag_values])

    string_property = property_index[PropertyType.string]
    string_values = instance_values_index[string_property.id]
    assert all([type(v.value) == str for v in string_values])
    value_index = {v.instance_id: v for v in string_values}
    assert value_index[instance_1.id].value == 'one'
    assert value_index[instance_8.id].value == 'eight'

    number_property = property_index[PropertyType.number]
    number_values = instance_values_index[number_property.id]
    assert all([type(v.value) == float or type(v.value) == int for v in number_values])
    value_index = {v.instance_id: v for v in number_values}
    assert value_index[instance_1.id].value == 1
    assert value_index[instance_8.id].value == 8

    date_property = property_index[PropertyType.date]
    date_values = instance_values_index[date_property.id]
    assert all([type(v.value) == str for v in date_values])
    value_index = {v.instance_id: v for v in date_values}
    assert value_index[instance_1.id].value == "2024-09-01T00:00:00Z"
    assert value_index[instance_8.id].value == "2024-09-08T00:00:00Z"

    color_property = property_index[PropertyType.color]
    color_values = instance_values_index[color_property.id]
    assert all([type(v.value) == int for v in color_values])
    value_index = {v.instance_id: v for v in color_values}
    assert value_index[instance_1.id].value == 0
    assert value_index[instance_8.id].value == 7

    url_property = property_index[PropertyType.url]
    url_values = instance_values_index[url_property.id]
    assert all([type(v.value) == str for v in url_values])
    value_index = {v.instance_id: v for v in url_values}
    assert value_index[instance_1.id].value == '1'
    assert value_index[instance_8.id].value == '8'

    checkbox_property = property_index[PropertyType.checkbox]
    checkbox_values = instance_values_index[checkbox_property.id]
    assert all([type(v.value) == bool for v in checkbox_values])
    value_index = {v.instance_id: v for v in checkbox_values}
    assert value_index[instance_1.id].value is True
    assert instance_8.id not in value_index

    tags = await db.get_tags()
    assert len(tags) == 22


async def test_import_data_mode_image(instance_project: Project, import_csv):
    prop_definitions = {
        1: Property(id=-1, name="tag", type=PropertyType.tag, mode=PropertyMode.sha1),
        2: Property(id=-2, name="multi_tags", type=PropertyType.multi_tags, mode=PropertyMode.sha1),
        3: Property(id=-3, name="string", type=PropertyType.string, mode=PropertyMode.sha1),
        4: Property(id=-4, name="number", type=PropertyType.number, mode=PropertyMode.sha1),
        5: Property(id=-5, name="date", type=PropertyType.date, mode=PropertyMode.sha1),
        6: Property(id=-6, name="color", type=PropertyType.color, mode=PropertyMode.sha1),
        7: Property(id=-7, name="url", type=PropertyType.url, mode=PropertyMode.sha1),
        8: Property(id=-8, name="checkbox", type=PropertyType.checkbox, mode=PropertyMode.sha1)
    }

    await instance_project.importer.upload_csv(import_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new', properties=prop_definitions)
    await instance_project.importer.confirm_import()

    db = instance_project.db
    instances = await db.get_instances()
    instance_index = {i.name: i for i in instances}

    assert len(instances) == 10

    properties = await db.get_properties()

    assert len(properties) == 8

    instance_values = await db.get_instance_property_values(instance_ids=[i.id for i in instances])
    image_values = await db.get_image_property_values(sha1s=list({i.sha1 for i in instances}))

    assert len(image_values) == 75
    assert len(instance_values) == 0

    tags = await db.get_tags()
    assert len(tags) == 22

    image_values_index = defaultdict(list)
    for val in image_values:
        image_values_index[val.property_id].append(val)

    property_index = {p.type: p for p in properties}

    instance_1 = instance_index['number_1.png']
    instance_8 = instance_index['number_8.png']

    tag_property = property_index[PropertyType.tag]
    tag_values = image_values_index[tag_property.id]
    assert all([type(v.value) == list for v in tag_values])
    assert all([len(v.value) == 1 for v in tag_values])

    multi_tag_property = property_index[PropertyType.multi_tags]
    multi_tag_values = image_values_index[multi_tag_property.id]
    assert all([type(v.value) == list for v in multi_tag_values])
    assert all([len(v.value) == 2 for v in multi_tag_values])

    string_property = property_index[PropertyType.string]
    string_values = image_values_index[string_property.id]
    assert all([type(v.value) == str for v in string_values])
    value_index = {v.sha1: v for v in string_values}
    assert value_index[instance_1.sha1].value == 'one'
    assert value_index[instance_8.sha1].value == 'eight'

    number_property = property_index[PropertyType.number]
    number_values = image_values_index[number_property.id]
    assert all([type(v.value) == float or type(v.value) == int for v in number_values])
    value_index = {v.sha1: v for v in number_values}
    assert value_index[instance_1.sha1].value == 1
    assert value_index[instance_8.sha1].value == 8

    date_property = property_index[PropertyType.date]
    date_values = image_values_index[date_property.id]
    assert all([type(v.value) == str for v in date_values])
    value_index = {v.sha1: v for v in date_values}
    assert value_index[instance_1.sha1].value == "2024-09-01T00:00:00Z"
    assert value_index[instance_8.sha1].value == "2024-09-08T00:00:00Z"

    color_property = property_index[PropertyType.color]
    color_values = image_values_index[color_property.id]
    assert all([type(v.value) == int for v in color_values])
    value_index = {v.sha1: v for v in color_values}
    assert value_index[instance_1.sha1].value == 0
    assert value_index[instance_8.sha1].value == 7

    url_property = property_index[PropertyType.url]
    url_values = image_values_index[url_property.id]
    assert all([type(v.value) == str for v in url_values])
    value_index = {v.sha1: v for v in url_values}
    assert value_index[instance_1.sha1].value == '1'
    assert value_index[instance_8.sha1].value == '8'

    checkbox_property = property_index[PropertyType.checkbox]
    checkbox_values = image_values_index[checkbox_property.id]
    assert all([type(v.value) == bool for v in checkbox_values])
    value_index = {v.sha1: v for v in checkbox_values}
    assert value_index[instance_1.sha1].value is True
    assert instance_8.id not in value_index


async def test_import_data_mode_mix(instance_project: Project, import_csv):
    prop_definitions = {
        TAG_ID: Property(id=-TAG_ID, name="tag", type=PropertyType.tag, mode=PropertyMode.sha1),
        MULTI_TAGS_ID: Property(id=-MULTI_TAGS_ID, name="multi_tags", type=PropertyType.multi_tags,
                                mode=PropertyMode.sha1),
        STRING_ID: Property(id=-STRING_ID, name="string", type=PropertyType.string, mode=PropertyMode.sha1),
        NUMBER_ID: Property(id=-NUMBER_ID, name="number", type=PropertyType.number, mode=PropertyMode.sha1),
        DATE_ID: Property(id=-DATE_ID, name="date", type=PropertyType.date, mode=PropertyMode.sha1),
        COLOR_ID: Property(id=-COLOR_ID, name="color", type=PropertyType.color, mode=PropertyMode.id),
        URL_ID: Property(id=-URL_ID, name="url", type=PropertyType.url, mode=PropertyMode.id),
        CHECKBOX_ID: Property(id=-CHECKBOX_ID, name="checkbox", type=PropertyType.checkbox, mode=PropertyMode.id)
    }

    await instance_project.importer.upload_csv(import_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new', properties=prop_definitions)
    await instance_project.importer.confirm_import()

    db = instance_project.db
    instances = await db.get_instances()
    instance_index = {i.name: i for i in instances}

    assert len(instances) == 10

    properties = await db.get_properties()

    assert len(properties) == 8

    instance_values = await db.get_instance_property_values(instance_ids=[i.id for i in instances])
    image_values = await db.get_image_property_values(sha1s=list({i.sha1 for i in instances}))

    assert len(image_values) == 50
    assert len(instance_values) == 25


async def test_import_export_equal(instance_project: Project, import_csv: str, tmp_path: Path):
    await instance_project.importer.upload_csv(import_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new')
    await instance_project.importer.confirm_import()

    res_dir = await instance_project.exporter.export_data(str(tmp_path), "tmp", None, [1, 2, 3, 4, 5, 6, 7, 8],
                                                          False, key='local_path')
    res_csv = Path(res_dir) / "data.csv"

    with open(import_csv) as f:
        import_data = f.read()
    with open(res_csv) as f:
        export_data = f.read()

    assert import_data == export_data


async def test_import_export_equal_with_empty(instance_project: Project, import_with_empty_csv: str, tmp_path: Path):
    await instance_project.importer.upload_csv(import_with_empty_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new')
    await instance_project.importer.confirm_import()

    res_dir = await instance_project.exporter.export_data(str(tmp_path), "tmp", None, [1, 2, 3, 4, 5, 6, 7, 8],
                                                          False, key='local_path')
    res_csv = Path(res_dir) / "data.csv"

    with open(import_with_empty_csv) as f:
        import_data = f.read()
    with open(res_csv) as f:
        export_data = f.read()

    assert export_data == import_data


async def test_import_missing_detection(instance_project: Project, import_with_missing_csv: str, tmp_path: Path):
    await instance_project.importer.upload_csv(import_with_missing_csv)
    missing = await instance_project.importer.parse_file(relative=True, fusion='new')

    assert len(missing) == 2


async def test_import_export_equal_mode_image(instance_project: Project, import_csv: str, tmp_path: Path):
    prop_definitions = {
        1: Property(id=-1, name="tag", type=PropertyType.tag, mode=PropertyMode.sha1),
        2: Property(id=-2, name="multi_tags", type=PropertyType.multi_tags, mode=PropertyMode.sha1),
        3: Property(id=-3, name="string", type=PropertyType.string, mode=PropertyMode.sha1),
        4: Property(id=-4, name="number", type=PropertyType.number, mode=PropertyMode.sha1),
        5: Property(id=-5, name="date", type=PropertyType.date, mode=PropertyMode.sha1),
        6: Property(id=-6, name="color", type=PropertyType.color, mode=PropertyMode.sha1),
        7: Property(id=-7, name="url", type=PropertyType.url, mode=PropertyMode.sha1),
        8: Property(id=-8, name="checkbox", type=PropertyType.checkbox, mode=PropertyMode.sha1)
    }
    await instance_project.importer.upload_csv(import_csv)
    await instance_project.importer.parse_file(relative=True, fusion='new', properties=prop_definitions)
    await instance_project.importer.confirm_import()

    res_dir = await instance_project.exporter.export_data(str(tmp_path), "tmp", None, [1, 2, 3, 4, 5, 6, 7, 8],
                                                          False, key='local_path')
    res_csv = Path(res_dir) / "data.csv"

    with open(import_csv) as f:
        import_data = f.read()
    with open(res_csv) as f:
        export_data = f.read()

    assert import_data == export_data


async def test_update_tag_value(data_project: Project):
    prop_id = TAG_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    tags = await db.get_tags(prop_id)
    tag_index = {t.value: t for t in tags}

    instance3 = instance_index['number_3.png']
    tag4 = tag_index["4"]

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=[tag4.id])

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value[0] == tag4.id
    assert len(db_value.value) == 1


async def test_update_multi_tags_value(data_project: Project):
    prop_id = MULTI_TAGS_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    tags = await db.get_tags(prop_id)
    tag_index = {t.value: t for t in tags}

    instance3 = instance_index['number_3.png']
    tag4 = tag_index["4"]

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=[tag4.id])

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value[0] == tag4.id
    assert len(db_value.value) == 1


async def test_update_string_value(data_project: Project):
    prop_id = STRING_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value="four")

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value == "four"


async def test_update_number_value(data_project: Project):
    prop_id = NUMBER_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=5)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value == 5


async def test_update_date_value(data_project: Project):
    prop_id = DATE_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value="1999-10-01T00:00:00Z")

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value == "1999-10-01T00:00:00Z"


async def test_update_color_value(data_project: Project):
    prop_id = COLOR_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=9)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value == 9


async def test_update_url_value(data_project: Project):
    prop_id = URL_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value="https://example.com/updated")

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))[0]

    assert db_value.value == "https://example.com/updated"


async def test_update_checkbox_value_true(data_project: Project):
    prop_id = CHECKBOX_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance4 = instance_index['number_4.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance4.id, value=True)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_value = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance4.id]))[0]

    assert db_value.value is True


async def test_update_checkbox_value_false(data_project: Project):
    prop_id = CHECKBOX_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=False)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_tag_value_empty(data_project: Project):
    prop_id = TAG_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_multi_tags_value_empty(data_project: Project):
    prop_id = MULTI_TAGS_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_string_value_empty(data_project: Project):
    prop_id = STRING_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_number_value_empty(data_project: Project):
    prop_id = NUMBER_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_date_value_empty(data_project: Project):
    prop_id = DATE_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_color_value_empty(data_project: Project):
    prop_id = COLOR_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_url_value_empty(data_project: Project):
    prop_id = URL_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_update_checkbox_value_empty(data_project: Project):
    prop_id = CHECKBOX_ID
    db = data_project.db
    instance_index = {i.name: i for i in await db.get_instances()}

    instance3 = instance_index['number_3.png']

    new_value = InstanceProperty(property_id=prop_id, instance_id=instance3.id, value=None)

    commit = DbCommit(instance_values=[new_value])
    await db.apply_commit(commit)

    db_values = (await db.get_instance_property_values(property_ids=[prop_id], instance_ids=[instance3.id]))
    assert len(db_values) == 0


async def test_create_property(data_project: Project):
    db = data_project.db
    new_prop = db.create_property(name="test_prop", type_=PropertyType.string, mode=PropertyMode.sha1)

    commit = DbCommit(properties=[new_prop])
    await db.apply_commit(commit)

    db_prop = next(x for x in await db.get_properties() if x.name == "test_prop")
    assert db_prop is not None
    assert db_prop.type == PropertyType.string
    assert db_prop.mode == PropertyMode.sha1
    assert db_prop.id > 0


async def test_update_property(data_project: Project):
    db = data_project.db
    prop = (await db.get_properties(ids=[STRING_ID]))[0]
    prop.name = "new_name"
    commit = DbCommit(properties=[prop])
    await db.apply_commit(commit)

    db_prop = (await db.get_properties(ids=[STRING_ID]))[0]
    assert db_prop.name == "new_name"


async def test_delete_properties(data_project: Project):
    db = data_project.db
    props = await db.get_properties()
    assert len(props) > 0

    db_values = await db.get_image_property_values()
    assert len(db_values) > 0

    db_values = await db.get_instance_property_values()
    assert len(db_values) > 0

    commit = DbCommit(empty_properties=[p.id for p in props])
    await db.apply_commit(commit)

    db_props = await db.get_properties()
    assert len(db_props) == 0

    db_values = await db.get_image_property_values()
    assert len(db_values) == 0

    db_values = await db.get_instance_property_values()
    assert len(db_values) == 0


async def test_create_tag(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID

    new_tag = db.create_tag(property_id=prop_id, value="new_tag", color=9)

    commit = DbCommit(tags=[new_tag])
    await db.apply_commit(commit)

    db_tag = next(t for t in await db.get_tags(prop_id) if t.value == "new_tag")
    assert db_tag is not None
    assert db_tag.id > 0
    assert db_tag.value == "new_tag"
    assert db_tag.color == 9
    assert db_tag.property_id == prop_id


async def test_update_tag(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID

    tag = next(t for t in await db.get_tags(prop_id) if t.value == "1")
    tag.value = "test_value"
    tag.color = 10

    commit = DbCommit(tags=[tag])
    await db.apply_commit(commit)

    db_tag = next(t for t in await db.get_tags(prop_id) if t.id == tag.id)
    assert db_tag.value == "test_value"
    assert db_tag.color == 10


async def test_update_tag_parent(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID
    tags = await db.get_tags(prop_id)
    tag1 = next(t for t in tags if t.value == "1")
    tag2 = next(t for t in tags if t.value == "2")
    tag1.parents = [tag2.id]

    commit = DbCommit(tags=[tag1])
    await db.apply_commit(commit)

    db_tag = next(t for t in await db.get_tags(prop_id) if t.id == tag1.id)
    assert len(db_tag.parents) == 1
    assert db_tag.parents[0] == tag2.id


async def test_update_tag_parent_ignore_cycles(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID
    tags = await db.get_tags(prop_id)
    tag1 = next(t for t in tags if t.value == "1")
    tag2 = next(t for t in tags if t.value == "2")
    tag1.parents = [tag2.id]
    tag2.parents = [tag1.id]

    commit = DbCommit(tags=[tag1, tag2])
    await db.apply_commit(commit)

    db_tag1 = next(t for t in await db.get_tags(prop_id) if t.id == tag1.id)
    assert len(db_tag1.parents) == 1
    assert db_tag1.parents[0] == tag2.id

    # should not have added parent to avoid cycle
    db_tag2 = next(t for t in await db.get_tags(prop_id) if t.id == tag2.id)
    assert len(db_tag2.parents) == 0


async def test_update_tag_parent_ignore_cycles_2(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID
    tags = await db.get_tags(prop_id)
    tag1 = next(t for t in tags if t.value == "1")
    tag2 = next(t for t in tags if t.value == "2")
    tag1.parents = [tag2.id]
    tag2.parents = [tag1.id]

    commit = DbCommit(tags=[tag1])
    await db.apply_commit(commit)

    db_tag1 = next(t for t in await db.get_tags(prop_id) if t.id == tag1.id)
    assert len(db_tag1.parents) == 1
    assert db_tag1.parents[0] == tag2.id

    commit = DbCommit(tags=[tag2])
    await db.apply_commit(commit)

    # should not have added parent to avoid cycle
    db_tag2 = next(t for t in await db.get_tags(prop_id) if t.id == tag2.id)
    assert len(db_tag2.parents) == 0


async def test_update_tag_parent_ignore_cycles_3(data_project: Project):
    db = data_project.db
    prop_id = TAG_ID
    tags = await db.get_tags(prop_id)
    tag1 = next(t for t in tags if t.value == "1")
    tag2 = next(t for t in tags if t.value == "2")
    tag3 = next(t for t in tags if t.value == "3")
    tag1.parents = [tag2.id]
    tag2.parents = [tag3.id]
    tag3.parents = [tag1.id]

    commit = DbCommit(tags=[tag1, tag3])
    await db.apply_commit(commit)

    db_tag1 = next(t for t in await db.get_tags(prop_id) if t.id == tag1.id)
    db_tag3 = next(t for t in await db.get_tags(prop_id) if t.id == tag3.id)
    assert len(db_tag1.parents) == 1
    assert db_tag1.parents[0] == tag2.id
    assert len(db_tag3.parents) == 1
    assert db_tag3.parents[0] == tag1.id

    commit = DbCommit(tags=[tag2])
    await db.apply_commit(commit)

    # should not have added parent to avoid cycle
    db_tag2 = next(t for t in await db.get_tags(prop_id) if t.id == tag2.id)
    assert len(db_tag2.parents) == 0


async def test_trie(data_project: Project):
    db = data_project.db
    instance_index: dict[str, Instance] = {i.name: i for i in await db.get_instances()}

    instance1 = instance_index['number_1.png']
    instance2 = instance_index['number_2.png']
    instance3 = instance_index['number_3.png']

    instance1.url = 'D:\\some\\windows\\path.jpg'
    instance2.url = '/some/unix/path.jpg'
    instance3.url = 'D:/some/weird/windows/path.jpg'

    win_global = 'D:\\some\\windows\\path.jpg'
    win_local_1 = 'windows\\path.jpg'
    win_local_2 = 'windows/path.jpg'

    unix_global = '/some/unix/path.jpg'
    unix_local = 'unix/path.jpg'
    unix_no_slash = 'th.jpg'

    trie = RelativePathTrie()
    trie.insert_paths([instance1, instance2, instance3])

    res1 = trie.search_absolute_path(win_global)
    assert(res1[0] == instance1.id)

    res2 = trie.search_relative_path(win_local_1)
    assert (res2[0] == instance1.id)

    res3 = trie.search_relative_path(win_local_2)
    assert (res3[0] == instance1.id)

    res4 = trie.search_absolute_path(unix_global)
    assert (res4[0] == instance2.id)

    res5 = trie.search_relative_path(unix_local)
    assert (res5[0] == instance2.id)

    res6 = trie.search_relative_path(unix_no_slash)
    assert (len(res6) == 0)
