import asyncio

from panoptic.core.project.project import Project


async def run():
    project = Project("D:\\VIRAPIX2", [])
    await project.start()

    instances = await project.db.get_instances_with_properties()
    values = await project.db.get_property_values(instances)

    print(len([v for v in values if v.property_id == 1]))

    await project.close()

asyncio.run(run())