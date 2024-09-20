from collections import defaultdict

from panoptic.core.project.project import Project


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

    instance_values = await db.get_instance_property_values(instance_ids=[i.id for i in instances])
    image_values = await db.get_image_property_values(sha1s=list({i.sha1 for i in instances}))

    assert len(image_values) == 0
    assert len(instance_values) == 75

    instance_values_index = defaultdict(list)


    tags = await db.get_tags()
    assert len(tags) == 22
