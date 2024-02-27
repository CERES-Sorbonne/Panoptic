from panoptic.models import Property


class ComputedId:
    id = -1
    sha1 = -2
    ahash = -3
    folder = -4
    width = -5
    height = -6
    path = -7


id_property = Property(id=ComputedId.id, name='id', type='id', mode='id', computed=True)
sha1_property = Property(id=ComputedId.sha1, name='sha1', type='sha1', mode='sha1', computed=True)
ahash_property = Property(id=ComputedId.ahash, name='average hash', type='ahash', mode='sha1', computed=True)
folder_property = Property(id=ComputedId.folder, name='folder', type='folder', mode='id', computed=True)
width_property = Property(id=ComputedId.width, name='width', type='width', mode='sha1', computed=True)
height_property = Property(id=ComputedId.height, name='height', type='height', mode='sha1', computed=True)
path_property = Property(id=ComputedId.path, name='path', type='path', mode='id', computed=True)

computed_properties = {p.id: p for p in
                       [id_property, sha1_property, ahash_property, folder_property, width_property, height_property,
                        path_property]}
