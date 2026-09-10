"""Migrator exception types."""


class MigratorError(Exception):
    """Base class for every error the migrator raises deliberately."""


class SourceNotFound(MigratorError):
    """The old project directory or its panoptic.db is missing/unreadable."""


class UnknownShape(MigratorError):
    """The source DB does not match any legacy schema shape we can read."""


class TargetExists(MigratorError):
    """The new project directory already exists and is not empty."""


class AlreadyMigrated(MigratorError):
    """The source is already in the new format; there is nothing to convert."""
