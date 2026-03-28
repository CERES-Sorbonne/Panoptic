from dataclasses import dataclass, field
from typing import Dict, Callable, Any


@dataclass
class DbDescription:
    """
    Metadata describing a database's schema and lifecycle.

    version: The current software version for this DB.
    tables: A dictionary mapping table names to their CREATE TABLE SQL statements.
    migrations: A map of {current_version: migration_func}.
                The function should accept the DB instance as its only argument.
    """
    version: int
    tables: Dict[str, str]
    migrations: Dict[int, Callable[[Any], None]] = field(default_factory=dict)