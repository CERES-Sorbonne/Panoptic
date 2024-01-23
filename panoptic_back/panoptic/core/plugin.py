import inspect
from collections import defaultdict
from typing import List, Any, Generic, NewType

from pydantic import BaseModel, Field


class Cluster(BaseModel):
    name: str | None
    score: str | None
    imageIds: List[int] | None
    imageSha1s: List[str] | None
    meta: Any = {}


def text_similarity(text: str, vectors):
    """
    Function to compute the similarity between a text and an array of image vectors
    @text: the text to compare the images with
    @vectors: pas besoin de préciser c'est un mot réservé
    """
    return


class Image(BaseModel):
    pass


class ClusterResult(BaseModel):
    groups: List[Cluster] = []
    meta: Any = {}


class ExampleInput(BaseModel):
    seed: str = Field(description='Custom Seed to control randomness')  # custom param in UI
    images: List[Image]  # reserved keyword -> input from backend


def my_func(input: ExampleInput) -> ClusterResult:
    return ClusterResult()


class Param:
    def __init__(self, name: str, param_type: type):
        self.type = param_type
        self.name = name


# class PluginParams(BaseModel):
class PluginParams(BaseModel):
    a: int = 0
    b: str = ''
    c: bool = False
    aa: List[int] = []
    bb: List[str] = []
    cc: List[bool] = []


# class Plugin:
#     def __init__(self, name):
#         self.name = name
#         self.id = None  # to be set later by plugin manager
#
#         self.params = PluginParams()
#
#         self.register('compute_clusters', self.my_cluster_func)


def test(a: int, b: [PluginParams]):
    pass


param = PluginParams()


# Get variable names and their types using __annotations__
# variables_and_types = PluginParams.__annotations__

class A:
    pass


class B:
    pass


class C:
    pass


def ff(a: A, b: B) -> (A, B):
    return A(), B()


# Print the results
# for variable, variable_type in variables_and_types.items():
#     print(f"{variable}: {variable_type}")

# signature = inspect.signature(ff)
#
# # Access the parameters
# parameters = signature.parameters
# print(f"params: {signature.parameters}")
# print(f"return: {signature.return_annotation}")
#

# # Print the names and types of the parameters
# for param_name, param in parameters.items():
#     print(f"{param_name, param}")
#     param_type = param.annotation if param.annotation != inspect._empty else None
#     print(f"{param_name}: {param_type}")
class Vector:
    pass

# Images = NewType('Images', List[])

ImageFiles = NewType('ImageFiles', List[str])
InstanceFiles = NewType('InstanceFiles', )
ImageVectors = NewType('ImageVectors', List[Vector])
Sha1s = NewType('Sha1s', List[str])
Images = NewType('Images', List[Image])


class Test(BaseModel):
    """
    @param: lala
    """
    pass


class Plugin:
    def __init__(self):
        self.params: BaseModel | None = None
        self.hooks = defaultdict(list)
        self._register_function('cluster', self.cluster_images)

    def set_params(self, params: BaseModel):
        self.params = params

    def _register_function(self, action_name, function):
        self.hooks[action_name].append(function)

    def cluster_images(self, images):
        """
        @param images: dependency
        @param nb_cluster: Number of clusters to make
        """
        return ClusterResult()


class FaissPluginParams(BaseModel):
    """
    @value: some value needed for the Faiss plugin
    """
    value: str


class FaissPlugin(Plugin):
    params: FaissPluginParams

    def cluster(self):
        self.params.value = 'lalala'


plugin = FaissPlugin()

for f in plugin.hooks['cluster']:
    signature = inspect.signature(f)
    print(signature.parameters)
