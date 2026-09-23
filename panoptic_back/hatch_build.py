from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface


class ReadmeMetadataHook(MetadataHookInterface):
    """
    Recent hatchling refuses a `readme` outside the project directory, so the repo README
    is injected as text at build time instead.
    An unpacked sdist has its own copy at the root (see sdist force-include), a git checkout uses ../README.md
    """

    def update(self, metadata: dict) -> None:
        root = Path(self.root)
        for candidate in (root / 'README.md', root.parent / 'README.md'):
            if candidate.is_file():
                metadata['readme'] = {
                    'content-type': 'text/markdown',
                    'text': candidate.read_text(encoding='utf-8'),
                }
                return
        raise FileNotFoundError('README.md not found in the project directory or its parent')
