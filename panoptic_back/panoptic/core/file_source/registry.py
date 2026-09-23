from panoptic.core.databases.data.models import FileSource
from panoptic.core.file_source.base import FileSourceReader
from panoptic.core.file_source.iiif_config import IIIFSourceConfig
from panoptic.core.file_source.iiif_reader import IIIFFileSourceReader
from panoptic.core.file_source.local_reader import LocalFileSourceReader

READERS: dict[str, type[FileSourceReader]] = {
    LocalFileSourceReader.dtype: LocalFileSourceReader,
    IIIFFileSourceReader.dtype: IIIFFileSourceReader,
}


def get_reader_for_source(project, file_source: FileSource) -> FileSourceReader:
    """Build a reader bound to an existing FileSource row — used at serve time
    (e.g. the /image/raw proxy), where there's no folder path / manifest URL to
    import from, just a row to read bytes through."""
    cls = READERS.get(file_source.dtype)
    if cls is None:
        raise ValueError(f'Unknown file source dtype: {file_source.dtype!r}')

    if cls is IIIFFileSourceReader:
        config = IIIFSourceConfig.from_dict(file_source.metadata)
        reader = cls(project, file_source.root_url or '', config=config)
    else:
        reader = cls(project, file_source.root_url or '')

    reader.file_source_id = file_source.id
    return reader
