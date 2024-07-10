from panoptic.models import Property, PropertyType, PropertyMode


class ComputedId:
    id = -1
    sha1 = -2
    ahash = -3
    folder = -4
    width = -5
    height = -6
    path = -7


id_property = Property(id=ComputedId.id, name='id', type=PropertyType('id'), mode=PropertyMode('id'), computed=True)
sha1_property = Property(id=ComputedId.sha1, name='sha1', type=PropertyType('sha1'), mode=PropertyMode('sha1'), computed=True)
ahash_property = Property(id=ComputedId.ahash, name='average hash', type=PropertyType('ahash'), mode=PropertyMode('sha1'), computed=True)
folder_property = Property(id=ComputedId.folder, name='folder', type=PropertyType('folder'), mode=PropertyMode('id'), computed=True)
width_property = Property(id=ComputedId.width, name='width', type=PropertyType('width'), mode=PropertyMode('sha1'), computed=True)
height_property = Property(id=ComputedId.height, name='height', type=PropertyType('height'), mode=PropertyMode('sha1'), computed=True)
path_property = Property(id=ComputedId.path, name='path', type=PropertyType('path'), mode=PropertyMode('id'), computed=True)

computed_properties = {p.id: p for p in
                       [id_property, sha1_property, ahash_property, folder_property, width_property, height_property,
                        path_property]}
