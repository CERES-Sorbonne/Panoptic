from contextlib import closing

from panoptic.core.importer.importer import CsvImport
from panoptic.core.task.task import Task


class ImportCsvTask(Task):
    """Writes a verified CSV's values into the project (see Importer.start_import).

    Progress counts CSV rows. Stopping keeps the rows already written: each commit of the
    import can be undone like any other.
    """

    def __init__(self, csv_import: CsvImport):
        super().__init__()
        self.name = f'Import {csv_import.name}'
        self._import = csv_import

    def start(self):
        self.state.total = self._import.n_rows
        self.set_step('Importing values', self._import.name)
        with closing(self._import.run()) as progress:
            for done, failed in progress:
                self.state.done = done
                self.state.failed = failed
                self._notify()
                if self.is_cancelled():
                    break
