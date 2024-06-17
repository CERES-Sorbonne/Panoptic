import os.path

from pydantic import BaseModel

from panoptic.core.plugin.plugin import APlugin
from panoptic.models import Instance, ActionContext
from panoptic.models.results import Group, ActionResult
from panoptic.utils import group_by_sha1
from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from .compute import reload_tree, get_similar_images, make_clusters
from .compute_vector_task import ComputeVectorTask


class FaissPluginParams(BaseModel):
    """
    Some base parameters for the Faiss Plugin
    @test_int: an int parameter
    @test_str: a str param
    """
    test_int: int = 0
    test_str: str = 'gouzi'
    test_bool: bool = False


class FaissPlugin(APlugin):
    """
    Default Machine Learning plugin for Panoptic
    Uses CLIP to generate vectors and FAISS for clustering / similarity functions
    """

    def __init__(self, project: PluginProjectInterface, plugin_path: str):
        super().__init__(name='Faiss', project=project, plugin_path=plugin_path)
        self.params = FaissPluginParams()
        reload_tree(self.project.base_path)

        self.project.on_instance_import(self.compute_image_vector)
        self.add_action_easy(self.find_images, ['similar'])
        self.add_action_easy(self.compute_clusters, ['group'])

    async def start(self):
        await super().start()
        vectors = await self.project.get_vectors(self.name, 'clip')

        # TODO: handle this properly with an import hook
        if not os.path.exists(os.path.join(self.project.base_path, 'tree_faiss.pkl')) and len(vectors) > 0:
            from panoptic.plugins.FaissPlugin.create_faiss_index import compute_faiss_index
            await compute_faiss_index(self.project.base_path, self.project, self.name, 'clip')
            reload_tree(self.project.base_path)

    async def compute_image_vector(self, instance: Instance):
        task = ComputeVectorTask(self.project, self.name, 'clip', instance)
        self.project.add_task(task)

    async def compute_clusters(self, context: ActionContext, nb_clusters: int = 10):
        """
        Computes images clusters with Faiss
        @nb_clusters: requested number of clusters
        """
        instances = await self.project.get_instances(context.instance_ids)
        sha1_to_instance = group_by_sha1(instances)
        sha1s = list(sha1_to_instance.keys())
        if not sha1s:
            return None

        vectors = await self.project.get_vectors(source=self.name, vector_type='clip', sha1s=sha1s)
        clusters, distances = make_clusters(vectors, method="kmeans", nb_clusters=nb_clusters)

        groups = [Group(ids=[i.id for sha1 in cluster for i in sha1_to_instance[sha1]], score=distance) for
                  cluster, distance in zip(clusters, distances)]
        for i, g in enumerate(groups):
            g.name = f"Cluster {i}"

        return ActionResult(groups=groups)

    async def find_images(self, context: ActionContext):
        instances = await self.project.get_instances(context.instance_ids)
        sha1s = [i.sha1 for i in instances]
        ignore_sha1s = set(sha1s)
        vectors = await self.project.get_vectors(source=self.name, vector_type='clip', sha1s=sha1s)
        vector_datas = [x.data for x in vectors]
        res = get_similar_images(vector_datas)
        index = {r['sha1']: r['dist'] for r in res if r['sha1'] not in ignore_sha1s}

        res_sha1s = list(index.keys())
        res_scores = [index[sha1] for sha1 in res_sha1s]

        res = Group(sha1s=res_sha1s, scores=res_scores)
        return ActionResult(instances=res)
