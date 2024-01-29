from __future__ import annotations

from typing import List, Any
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
from panoptic.models import Instances, Properties


class Cluster(BaseModel):
    name: str | None
    score: str | None
    imageIds: List[int] | None
    imageSha1s: List[str] | None
    meta: Any = {}


#
# def text_similarity(text: str, vectors):
#     """
#     Function to compute the similarity between a text and an array of image vectors
#     @text: the text to compare the images with
#     @vectors: pas besoin de préciser c'est un mot réservé
#     """
#     return
#
#
# class ClusterResult(BaseModel):
#     groups: List[Cluster] = []
#     meta: Any = {}
#
#
# class ExampleInput(BaseModel):
#     seed: str = Field(description='Custom Seed to control randomness')  # custom param in UI
#     images: List[Image]  # reserved keyword -> input from backend
#
#
# def my_func(input: ExampleInput) -> ClusterResult:
#     return ClusterResult()
#
#
# class Param:
#     def __init__(self, name: str, param_type: type):
#         self.type = param_type
#         self.name = name
# #
# #
# # # class PluginParams(BaseModel):
# # class PluginParams(BaseModel):
# #     a: int = 0
# #     b: str = ''
# #     c: bool = False
# #     aa: List[int] = []
# #     bb: List[str] = []
# #     cc: List[bool] = []
# #

# class Plugin:
#     def __init__(self, name):
#         self.name = name
#         self.id = None  # to be set later by plugin manager
#
#         self.params = PluginParams()
#
#         self.register('compute_clusters', self.my_cluster_func)
#
#
# def test(a: int, b: [PluginParams]):
#     pass


# Get variable names and their types using __annotations__
# variables_and_types = PluginParams.__annotations__


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

# def test_func(instances: Instances, properties: Properties, vectors: Vectors, custom1: int, custom2: str = 'lala'):
#     """
#     Description test de ma function
#
#     @param custom1: Mon premier parametre custom permet de regler la temparture de panoptic
#     @param custom2: Mon deuxieme parametre, ne sert a rien
#
#     """
#

#
# def get_params(f):
#     signature = inspect.signature(f)
#     parameters = signature.parameters
#     return {k: parameters[k].annotation for k in parameters}
#
#
# def get_dependencies(f):
#     types = get_params(f)
#     return {t: types[t] for t in types if types[t] in possible_dependencies}
#
#
# def get_inputs(f):
#     types = get_params(f)
#     return {t: types[t] for t in types if types[t] in possible_inputs}
#
#
# def verify_dependencies(f: Callable, required: List):
#     dependencies = get_dependencies(f).values()
#
#     if Instances in dependencies and Images in dependencies:
#         return False
#
#     count = 0
#     required_nb = len(required)
#     if Instances in required and Images in required:
#         required_nb -= 1
#
#     for r in required:
#         if r in dependencies:
#             count += 1
#
#     return count == required_nb
#
#
# print(verify_dependencies(test_func, [Images, Instances, Vectors, Properties]))
# print(inspect.signature(test_func).return_annotation)
#

# signature = inspect.signature(ff)
#
# # Access the parameters
# parameters = signature.parameters
# print(f"params: {signature.parameters}")
# print(f"return: {signature.return_annotation}")
#

class UrlResult(BaseModel):
    url: str


class GroupMeta:
    pass


class Test(BaseModel):
    """
    @param: lala
    """
    pass


class EmptyParam(BaseModel):
    pass


class Plugin:
    def __init__(self, name: str, project: Project):
        self.params: EmptyParam = EmptyParam()
        self.name: str = name
        self.project = project

    async def start(self):
        pass


class KibanaPluginParams(BaseModel):
    """
    @param base_url: The base Kibana URL
    """
    base_url: str


class KibanaPlugin(Plugin):
    params: KibanaPluginParams

    def __init__(self, project: Project):
        super().__init__(name="kibana", project=project)

    def open_images(self, instance: Instances):
        """
        Open Kibana dashboard with only the selected instances
        """
        computed_url = 'todo'
        return UrlResult(url=self.params.base_url + computed_url)

    def open_time_interval(self, instance: Instances, properties: Properties):
        """
        Open Kibana dashboard with a time interval [minDate, maxDate]
        """
        computed_url = 'todo-interval'
        return UrlResult(url=self.params.base_url + computed_url)


# class FaissPluginParams(BaseModel):
#     """
#     @value: some value needed for the Faiss plugin
#     """
#     value: str




#
# plugin = FaissPlugin()
#
# for f in plugin.hooks['cluster']:
#     signature = inspect.signature(f)
#     print(signature.parameters)
