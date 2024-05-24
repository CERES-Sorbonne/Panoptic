# import asyncio
# import json
#
# import aiosqlite
#
# from panoptic.core.project.project import Project
# from panoptic.utils import clean_value
#
# source_db_file = '/Users/david/Downloads/panoptic-edouard.db'
# target_folder = '/Users/david/panoptic-projects/panoptic-edouard'
#
#
# async def run():
#     async with aiosqlite.connect(source_db_file) as db:
#         # Execute a SELECT query
#         computed_values = []
#         instances = []
#         folders = []
#         properties = []
#         instance_values = []
#         image_values = []
#         tags = []
#         async with db.execute('SELECT * FROM computed_values') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 computed_values.append(row)
#         async with db.execute('SELECT * FROM images') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 row[5] = row[5][8:]
#                 instances.append(row)
#         async with db.execute('SELECT * FROM folders') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 folders.append(row)
#         async with db.execute('SELECT * FROM properties') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 properties.append(row)
#         async with db.execute('SELECT * FROM property_values') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 if row[1] == -1:
#                     row = [r for i, r in enumerate(row) if i != 1]
#                     image_values.append(row)
#                 else:
#                     print(row[2])
#                     row = [r for i, r in enumerate(row) if i != 2]
#                     instance_values.append(row)
#         async with db.execute('SELECT * FROM tags') as cursor:
#             async for row in cursor:
#                 row = list(row)
#                 row[4] = 0
#                 tags.append(row)
#
#         project = Project(target_folder, [])
#         await project.start()
#
#         sha1_to_ahash = {v[0]: v[1] for v in computed_values}
#
#         for folder in folders:
#             await project.db.get_raw_db().import_folder(*folder)
#         for instance in instances:
#             ahash = sha1_to_ahash[instance[4]] if instance[4] in sha1_to_ahash else 'none'
#             await project.db.get_raw_db().import_instance(*instance, ahash)
#         for prop in properties:
#             await project.db.get_raw_db().import_property(*prop)
#         prop_index = {p.id: p for p in await project.db.get_properties(computed=True)}
#
#         for tag in tags:
#             if tag[1] in prop_index:
#                 await project.db.get_raw_db().import_tag(*tag)
#
#         for val in image_values:
#             if val[0] not in prop_index:
#                 continue
#             v = clean_value(prop_index[val[0]], val[2])
#             if type(v) is not int:
#                 v = json.loads(v)
#             if v:
#                 val[2] = v
#                 val[1] = [val[1]]
#                 await project.db.get_raw_db().set_image_property_value(*val)
#         for val in instance_values:
#             v = clean_value(prop_index[val[0]], val[2])
#             if type(v) is not int:
#                 v = json.loads(v)
#             if v:
#                 val[2] = v
#                 val[1] = [val[1]]
#                 await project.db.get_raw_db().set_instance_property_value(*val)
#         await project.close()
#
#
# asyncio.run(run())
