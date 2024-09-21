from collections import defaultdict
from pathlib import Path

from panoptic.core.project.project import Project
from panoptic.models import PropertyType, Property, PropertyMode


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


async def test_load_project(instance_project: Project):
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


async def test_import_data(instance_project: Project, import_csv: str):
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


async def test_import_data_prop_mode_image(instance_project: Project, import_csv):
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


async def test_import_export_equal2(instance_project: Project, import_csv: str, tmp_path: Path):
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


