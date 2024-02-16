from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.models import Instance, ActionContext
from panoptic.models.results import GroupResult, Group, InstanceMatch, SearchResult
from panoptic.plugin import Plugin
from panoptic.utils import group_by_sha1
from .compute import reload_tree, get_similar_images, make_clusters
from .compute_vector_task import ComputeVectorTask


class FaissPluginParams(BaseModel):
    """
    Some base parameters for the Faiss Plugin
    @test_int: an int parameter
    @test_str: a str param
    """
    test_int: int = 0
    test_str: str = ''
    test_bool: bool = False


class FaissPlugin(Plugin):
    """
    Default Machine Learning plugin for Panoptic
    Uses CLIP to generate vectors and FAISS for clustering / similarity functions
    """

    def __init__(self, project: Project, plugin_path: str):
        super().__init__(name='Faiss', project=project, plugin_path=plugin_path)
        self.params = FaissPluginParams()
        reload_tree(project.base_path)

        project.on.import_instance.register(self.compute_image_vector)
        project.action.find_images.register(self, self.find_images)
        project.action.group_images.register(self, self.compute_clusters)

    async def compute_image_vector(self, instance: Instance):
        task = ComputeVectorTask(self.project, self.name, 'clip', instance)
        self.project.task_queue.add_task(task)

    async def compute_clusters(self, context: ActionContext, nb_clusters: int = 10):
        """
        Computes images clusters with Faiss
        @nb_clusters: requested number of clusters
        """
        instances = await self.project.db.get_instances(context.instance_ids)
        sha1_to_instance = group_by_sha1(instances)
        sha1s = list(sha1_to_instance.keys())
        if not sha1s:
            return None

        vectors = await self.project.db.get_vectors(source=self.name, type_='clip', sha1s=sha1s)
        clusters, distances = make_clusters(vectors, method="kmeans", nb_clusters=nb_clusters)

        groups = [Group(ids=[i.id for sha1 in cluster for i in sha1_to_instance[sha1]], score=distance) for
                  cluster, distance in zip(clusters, distances)]
        return GroupResult(groups=groups)

    async def find_images(self, context: ActionContext):
        instances = await self.project.db.get_instances(context.instance_ids)
        sha1s = [i.sha1 for i in instances]
        vectors = await self.project.db.get_vectors(source=self.name, type_='clip', sha1s=sha1s)
        vector_datas = [x.data for x in vectors]
        res = get_similar_images(vector_datas)
        index = {r['sha1']: r['dist'] for r in res if r['sha1'] not in sha1s}

        res_sha1s = list(index.keys())
        res_instances = await self.project.db.get_instances(sha1s=res_sha1s)
        matches = [InstanceMatch(id=i.id, score=index[i.sha1]) for i in res_instances]
        return SearchResult(matches=matches)
