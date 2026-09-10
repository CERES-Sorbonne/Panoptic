"""Writers for the new multi-database format (task 3.3).

    ir  ->  data.db  ->  media.db  ->  project.db  ->  post-conditions

That order is not cosmetic. `project.db`'s `id_registry` is seeded from
`MAX(id) + 1` over the rows the other two DBs actually contain
(ID_STRATEGY 2.2: compute the seeds from the output, because that is the check
that cannot drift), so it can only be written once they exist.

The four modules, and the one idea each carries:

* `genesis.py` -- the only code path that writes a logged entity, so a result
  row can never be written without its `entity_log` genesis op;
* `ids.py` -- ids are preserved verbatim, counters are *next free*, and the nine
  system properties are allocated above every legacy property id;
* `data_db.py` / `media_db.py` / `project_db.py` -- MAPPING sections 3-8;
* `postcheck.py` -- ID_STRATEGY section 6, run against the written files.

`panoptic.db` (the instance registry) is `panoptic_db.py`, added by task 3.4. It
is deliberately apart from the four above: it belongs to the panoptic *home*,
not to the project folder, it is an upsert onto a long-lived file rather than a
fresh write, and it holds the other half of
`projects.id == project_config.id` -- the invariant `load_project` enforces.
"""

from __future__ import annotations

from .data_db import DataDbWriter, write_data_db
from .genesis import (GENESIS_COMMIT_ID, LOGGED_ENTITIES, OP_CREATE, OP_DELETE,
                      OP_UPDATE, SEQUENCE, Genesis, encode_key)
from .ids import (ID_REGISTRY_KEYS, SYSTEM_PROPERTIES, SystemPropertyPlan,
                  next_free)
from .media_db import MediaDbWriter, write_media_db
from .panoptic_db import (DEFAULT_USER_ID, HomeDbError, PanopticHomeWriter,
                          read_project_config)
from .postcheck import PostConditionError, PostConditions
from .project_db import ProjectDbWriter, write_project_db

__all__ = [
    "write_data_db", "write_media_db", "write_project_db",
    "PanopticHomeWriter", "HomeDbError", "read_project_config",
    "DEFAULT_USER_ID",
    "DataDbWriter", "MediaDbWriter", "ProjectDbWriter",
    "Genesis", "LOGGED_ENTITIES", "encode_key",
    "GENESIS_COMMIT_ID", "OP_CREATE", "OP_UPDATE", "OP_DELETE", "SEQUENCE",
    "SystemPropertyPlan", "SYSTEM_PROPERTIES", "ID_REGISTRY_KEYS", "next_free",
    "PostConditions", "PostConditionError",
]
