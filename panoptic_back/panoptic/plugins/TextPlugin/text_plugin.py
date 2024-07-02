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
from panoptic.models import ActionContext, PropertyId, InstanceProperty, PropertyType, PropertyMode, DbCommit
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

    async def create_props(self):
        # TODO: check if prop exist before
        commit = DbCommit()
        cluster_prop = self.project.create_property(self.name + "_clusters", PropertyType.string, PropertyMode.id)
        tags_prop = self.project.create_property(self.name + "_topics", PropertyType.multi_tags, PropertyMode.id)
        commit.properties.append(cluster_prop)
        commit.properties.append(tags_prop)
        res = await self.project.do(commit)
        return cluster_prop.id, tags_prop.id

    async def save_as_props(self, words: list[str], ids: list[int], cluster_prop: int, tags_prop: int):
        """
        Save the list of words as a unified string to save the whole cluster in this prop
        Also save the list of words as tags
        """
        commit = DbCommit()
        name = "-".join(words)
        values = [InstanceProperty(property_id=cluster_prop, instance_id=_id, value=name) for _id in ids]
        tag_ids = []
        tags = await self.project.get_tags(property_ids=[tags_prop])
        tag_index = {tag.value: tag for tag in tags}
        tags_to_create = []
        for word in words:
            if word in tag_index:
                tag = tag_index[word]
            else:
                tag = self.project.create_tag(tags_prop, word)
                tags_to_create.append(tag)
            tag_ids.append(tag.id)
        values.extend([InstanceProperty(property_id=tags_prop, instance_id=_id, value=tag_ids) for _id in ids])
        commit.instance_values = values
        commit.tags = tags_to_create
        # commit.instance_values = [values[0]]
        res = await self.project.do(commit)
        return res

    async def cluster_text_semantic(self, context: ActionContext, text: PropertyId) -> ActionResult:

        values = await self.project.get_instance_property_values(property_ids=[text], instance_ids=context.instance_ids)
        ids = np.array([v.instance_id for v in values])
        texts = [x.value for x in values]

        ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)
        vectorizer_model = CountVectorizer(stop_words=raw_stopword_list)
        model = BERTopic(ctfidf_model=ctfidf_model, vectorizer_model=vectorizer_model, language="french")
        clusters, probs = model.fit_transform(texts)
        cluster_set = set(clusters)
        clusters = np.asarray(clusters)
        # Afficher les clusters et les sujets principaux associés
        top_n = 5  # Nombre de sujets principaux à afficher par cluster
        groups = []
        cluster_prop, tags_prop = await self.create_props()
        for topic in cluster_set:
            topic_words = model.get_topic(topic)[:top_n]
            topic_words = [w[0] for w in topic_words]
            name = "-".join(topic_words)
            # get ids for the current cluster and cast them back to native python
            current_ids = (ids[clusters == topic]).tolist()
            await self.save_as_props(topic_words, current_ids, cluster_prop, tags_prop)
            groups.append(Group(ids=current_ids, name=name))
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

