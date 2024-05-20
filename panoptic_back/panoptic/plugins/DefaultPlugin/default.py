import asyncio
from pathlib import Path

from pydantic import BaseModel

from panoptic.core.project.project import Project
from panoptic.models import ActionContext, PropertyId, PropertyType, PropertyMode, InstancePropertyValue, DbCommit, \
    Instance
from panoptic.models.results import ActionResult
from panoptic.plugin import Plugin


# class TestParams(BaseModel):
#     eau: str = None
#     terre: int = 0
#     feu: float = 2.4
#     air: Path = None

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


async def ocr(instance: Instance):
    command = f'shortcuts run ocr-img -i "{instance.url}"'
    text, err = await run_command(command)
    return InstancePropertyValue(property_id=-1, instance_id=instance.id, value=text)


class DefaultPlugin(Plugin):
    def __init__(self, project: Project, plugin_path: str):
        super().__init__(name='TestPlugin1', project=project, plugin_path=plugin_path)
        # self.params = TestParams()
        self.project.action.easy_add(self, self.ocr, ['execute'])

    async def ocr(self, context: ActionContext):
        instances = await self.project.db.get_instances(ids=context.instance_ids)
        tasks = [ocr(i) for i in instances]

        prop = await self.project.db.add_property('OCR', PropertyType.string)
        values = await asyncio.gather(*tasks)
        for v in values:
            v.property_id = prop.id
        commit = DbCommit(instance_values=list(values))
        commit = await self.project.undo_queue.do(commit)
        commit.properties = [prop]
        return ActionResult(commit=commit)
