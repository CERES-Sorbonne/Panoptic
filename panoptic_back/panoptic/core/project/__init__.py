import json
from pathlib import Path

from panoptic.models import PluginKey, PanopticDataOld, PanopticData
from panoptic.utils import get_datadir


def verify_panoptic_data():
    global_file_path = get_datadir() / 'panoptic' / 'projects.json'
    try:

        with open(global_file_path, 'r') as file:
            data = json.load(file)
            old_data = PanopticDataOld(**data)

            projects = old_data.projects
            plugins = [PluginKey(name=Path(p).name, path=p) for p in old_data.plugins]

            new_data = PanopticData(projects=projects, plugins=plugins)

        with open(global_file_path, 'w') as file2:
            json.dump(new_data.dict(), file2, indent=2)

    except Exception:
        pass
