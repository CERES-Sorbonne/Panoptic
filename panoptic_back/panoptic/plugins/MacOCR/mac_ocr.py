import asyncio
import math
from enum import Enum

from panoptic.core.plugin.plugin_project_interface import PluginProjectInterface
from panoptic.core.project.project import Project
from panoptic.models import ActionContext, PropertyType, PropertyMode, DbCommit, \
    Instance, ImageProperty, Property
from panoptic.models.results import ActionResult, Group, Notif, NotifType
from panoptic.core.plugin.plugin import APlugin


async def run_command(command):
    # Create the subprocess
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Capture the output and error
    stdout, stderr = await process.communicate()

    # Decode the output and error from bytes to strings
    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    return stdout, stderr


async def ocr(instance: Instance, prop: Property):
    command = f'shortcuts run ocr-img -i "{instance.url}"'
    text, err = await run_command(command)
    return ImageProperty(property_id=prop.id, sha1=instance.sha1, value=text)


class VectorType(Enum):
    clip = 'clip'
    clip_grey = 'clip_grey'


class MacOCR(APlugin):
    def __init__(self, project: PluginProjectInterface, plugin_path: str, name: str):
        super().__init__(name=name, project=project, plugin_path=plugin_path)
        self.add_action_easy(self.ocr, ['execute'])
        self.add_action_easy(self.find_close_id, ['similar'])
        self.add_action_easy(self.cluster_up, ['group'])
        self.add_action_easy(self.test_action, ['execute'])

    async def test_action(self, ctx: ActionContext, vector: VectorType):
        print(vector == VectorType.clip_grey)

    async def ocr(self, context: ActionContext):
        error2 = Notif(type=NotifType.ERROR, name='OCRERROR2', message='Unexpected ERROR during OCR')
        return ActionResult(notifs=[error2])

        commit = DbCommit()
        prop = self.project.create_property('OCR', PropertyType.string, PropertyMode.sha1)
        instances = await self.project.get_instances(ids=context.instance_ids)
        unique_sha1 = list({i.sha1: i for i in instances}.values())
        tasks = [await ocr(i, prop) for i in unique_sha1]
        # values = await asyncio.gather(*tasks)
        values = tasks
        commit.properties.append(prop)
        commit.image_values.extend(values)

        res = await self.project.do(commit)
        return ActionResult(commit=res)

    async def find_close_id(self, context: ActionContext):
        ids = context.instance_ids
        close_ids = [(i - 5) + ids[0] for i in range(10)]

        return ActionResult(instances=Group(ids=close_ids))

    async def cluster_up(self, context: ActionContext, size: int):
        ids = context.instance_ids

        nb = math.ceil(len(ids) / size)

        groups = [Group(ids=ids[i * size: i * size + size]) for i in range(nb)]
        return ActionResult(groups=groups)
