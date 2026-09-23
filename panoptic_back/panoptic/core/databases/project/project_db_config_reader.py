import sqlite3
from pathlib import Path
from typing import Optional

from panoptic.core.databases.project.create import PROJECT_CONFIG_SHEMA
from panoptic.core.databases.project.models import ProjectConfig


def get_project_config(path: str | Path) -> Optional[ProjectConfig]:
    if not Path(path).exists():
        return None

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return PROJECT_CONFIG_SHEMA.get(conn.cursor())
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
