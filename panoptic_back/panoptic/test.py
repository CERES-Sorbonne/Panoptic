import asyncio
from time import time

from fastapi import UploadFile

from panoptic.core.importer import ImportData, ImportValues, Importer
from panoptic.core.project.project import Project
from panoptic.models import Property, PropertyType, PropertyMode, Tag, Instance


async def test_import_data():
    project = Project('/Users/david/panoptic-projects/celebs', [])
    await project.start()

    now = time()
    res = await project.db.get_raw_db().get_instances2()
    print(time() - now)

    # instances = await project.db.get_instances(ids=[1])
    # instances[0].id = -1
    # res = await project.db.get_raw_db().import_instances(instances)
    # print(res)
    # res = await project.db.get_raw_db().get_new_instance_ids(10)
    # print(res)
    #
    # res = await project.db.get_raw_db().get_new_property_ids(10)
    # print(res)
    #
    # res = await project.db.get_raw_db().get_new_tag_ids(10)
    # print(res)

    # instances = await project.db.get_instances()
    #
    # new_i = instances[0:10]
    # for i in range(len(new_i)):
    #     new_i[i].id = -i - 1
    #
    # data = ImportData()
    # data.instances = new_i
    #
    # data.properties = [Property(id=-1, name='testing', type=PropertyType.multi_tags, mode=PropertyMode.id)]
    # data.tags = [Tag(id=-1, property_id=-1, value='AAAA', parents=[0], color=0),
    #              Tag(id=-2, property_id=-1, value='BBBB', parents=[-1], color=1),
    #              Tag(id=-3, property_id=-1, value='CCCC', parents=[-1], color=2),
    #              Tag(id=-4, property_id=-1, value='DDDD', parents=[-2], color=3)]
    #
    # data.values = [ImportValues(property_id=-1, instance_ids=[-1, -2, -3], values=[[-1], [-2], [-3]])]
    #
    # await project.importer.import_data(data)

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


async def run_command(command):
    # Create the subprocess
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Capture the output and error
    stdout, stderr = await process.communicate()

    # Decode the output and error from bytes to strings
    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    return stdout, stderr


# Example usage
async def main():
    file_path = '/Users/david/Desktop/Capture d’écran 2024-05-19 à 20.24.10.png'
    command = f'shortcuts run ocr-img -i "{file_path}"'
    stdout, stderr = await run_command(command)

    print('Output:', stdout)
    print('Error:', stderr)

asyncio.run(test_import_data())
#
# import subprocess
#
# file_path = '/Users/david/Desktop/Capture d’écran 2024-05-19 à 20.24.10.png'
# ocr_out = subprocess.check_output(
#     f'shortcuts run ocr-img -i "{file_path}"', shell=True
# )
# print(ocr_out.decode('utf-8'))
