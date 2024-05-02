import asyncio
from time import time

from fastapi import UploadFile

from panoptic.core.importer import ImportData, ImportValues, Importer
from panoptic.core.project.project import Project
from panoptic.models import Property, PropertyType, PropertyMode, Tag


async def test_import_data():
    project = Project('/Users/david/panoptic-projects/refactorZ', [])
    await project.start()

    instances = await project.db.get_instances()

    new_i = instances[0:10]
    for i in range(len(new_i)):
        new_i[i].id = -i - 1

    data = ImportData()
    data.instances = new_i

    data.properties = [Property(id=-1, name='testing', type=PropertyType.multi_tags, mode=PropertyMode.id)]
    data.tags = [Tag(id=-1, property_id=-1, value='AAAA', parents=[0], color=0),
                 Tag(id=-2, property_id=-1, value='BBBB', parents=[-1], color=1),
                 Tag(id=-3, property_id=-1, value='CCCC', parents=[-1], color=2),
                 Tag(id=-4, property_id=-1, value='DDDD', parents=[-2], color=3)]

    data.values = [ImportValues(property_id=-1, instance_ids=[-1, -2, -3], values=[[-1], [-2], [-3]])]

    await project.importer.import_data(data)

    await project.close()


async def test_import_file():
    project = Project('/Users/david/panoptic-projects/refactorZ', [])
    try:
        await project.start()

        importer = project.importer
        with open('/Users/david/Downloads/tpmp+h2pros/fusion_with_path.csv', 'rb') as file:
            start = time()
            await importer.upload_csv(UploadFile(file=file))
            print(f"import: {time() - start} seconds")


        await project.close()
    except Exception as e:
        await project.close()
        raise e



asyncio.run(test_import_file())
