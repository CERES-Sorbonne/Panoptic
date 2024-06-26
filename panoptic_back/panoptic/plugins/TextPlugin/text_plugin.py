import os.path
import pickle

import numpy as np
from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer

from pydantic import BaseModel
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

from panoptic.core.plugin.plugin import APlugin
from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.models import ActionContext, PropertyId, InstanceProperty
from panoptic.models.results import ActionResult, Group
from panoptic.plugins.TextPlugin.utils import raw_stopword_list


class TestParams(BaseModel):
    base_text: str = None
    base_number: int = 0
    base_floating: float = 2.4
    base_prop: PropertyId = 1


class PluginBase(APlugin):
    def __init__(self, project: PluginProjectInterface, plugin_path: str):
        super().__init__(name='TextePlugin', project=project, plugin_path=plugin_path)
        self.params = TestParams()

        self.add_action_easy(self.cluster_text_syntax, ['group'])
        self.add_action_easy(self.cluster_text_semantic, ['group'])

    def get_vectors(self):
        path_name = os.path.join(self.project.base_path, 'vectors.pkl')
        if os.path.exists(path_name):
            with open(path_name, 'rb') as f:
                vectors = pickle.load(f)
                return vectors
        else:
            return None

    def save_vectors(self, vectors):
        path_name = os.path.join(self.project.base_path, 'vectors.pkl')
        with open(path_name, 'wb') as f:
            pickle.dump(vectors, f)

    def create_vectors(self, values: list[InstanceProperty]):
        texts = [x.value for x in values]
        vectorizer = TfidfVectorizer(ngram_range=(3, 9))
        # Transformer les textes en vecteurs TF-IDF
        vectors = vectorizer.fit_transform(texts)
        self.save_vectors(vectors)
        return vectors

    async def cluster_text_semantic(self, context: ActionContext, text: PropertyId) -> ActionResult:

        values = await self.project.get_instance_property_values(property_ids=[text], instance_ids=context.instance_ids)
        ids = np.array([v.instance_id for v in values])
        texts = [x.value for x in values]

        # ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)
        # model = BERTopic(ctfidf_model=ctfidf_model, language="french")
        vectorizer_model = CountVectorizer(stop_words=raw_stopword_list)
        model = BERTopic(vectorizer_model=vectorizer_model, language="french")
        clusters, probs = model.fit_transform(texts)
        cluster_set = set(clusters)
        clusters = np.asarray(clusters)
        # Afficher les clusters et les sujets principaux associés
        top_n = 5  # Nombre de sujets principaux à afficher par cluster
        groups = []
        for topic in cluster_set:
            topic_words = model.get_topic(topic)[:top_n]
            topic_words = [w[0] for w in topic_words]
            groups.append(Group(ids=ids[clusters == topic], name="-".join(topic_words)))
        return ActionResult(groups=groups)

    async def cluster_text_syntax(self, context: ActionContext, num_clusters: int, text: PropertyId) -> ActionResult:
        values = await self.project.get_instance_property_values(property_ids=[text], instance_ids=context.instance_ids)
        vectors = self.get_vectors()
        if vectors is not None:
            vectors = self.create_vectors(values)

        kmeans = KMeans(n_clusters=num_clusters)
        kmeans.fit(vectors)
        clusters = kmeans.predict(vectors)

        # Créer une liste de listes pour stocker les IDs par cluster
        clustered_ids = [[] for _ in range(num_clusters)]

        # Assigner chaque ID au cluster correspondant
        for idx, cluster in enumerate(clusters):
            clustered_ids[cluster].append(values[idx].instance_id)
        groups = [Group(ids=cluster_ids) for cluster_ids in clustered_ids]
        return ActionResult(groups=groups)

