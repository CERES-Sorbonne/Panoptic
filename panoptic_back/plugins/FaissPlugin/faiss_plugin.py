from panoptic.core.project.project import Project
from panoptic.models import Instance, ActionContext, Clusters
from panoptic.plugin import Plugin
from .compute import reload_tree, get_similar_images, make_clusters

from .compute_vector_task import ComputeVectorTask


class FaissPlugin(Plugin):
    def __init__(self, project: Project):
        super().__init__(name='Faiss', project=project)
        reload_tree(project.base_path)

        project.on.import_instance.register(self.compute_image_vector)
        project.action.find_images.register(self, self.find_images)
        project.action.group_images.register(self, self.compute_clusters)

    async def compute_image_vector(self, instance: Instance):
        task = ComputeVectorTask(self.project, self.name, 'clip', instance)
        self.project.task_queue.add_task(task)

    async def compute_clusters(self, context: ActionContext, nb_clusters: int):
        instances = await self.project.db.get_instances(context.instance_ids)
        sha1s = [i.sha1 for i in instances]

        if not sha1s:
            return []

        vectors = await self.project.db.get_default_vectors(sha1s)
        clusters, distances = make_clusters(vectors, method="kmeans", nb_clusters=nb_clusters)
        return Clusters(clusters=clusters, distances=distances)

    # if not sha1s:
    #         return []
    #     values = await db.get_sha1_computed_values(sha1s)
    #     clusters, distances = compute.make_clusters(values, method="kmeans", nb_clusters=sensibility)
    #     return Clusters(clusters=clusters, distances=distances)

    async def find_images(self, context: ActionContext):
        instances = await self.project.db.get_instances(context.instance_ids)
        sha1s = [i.sha1 for i in instances]
        vectors = await self.project.db.get_default_vectors(sha1s)
        vector_datas = [x.data for x in vectors]
        res = get_similar_images(vector_datas)
        res = [r for r in res if r['sha1'] not in sha1s]
        return res
