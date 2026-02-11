from pathlib import Path


class ProjectPaths:
    def __init__(self, root: Path):
        self.root = root
        self.image_data = root / "image_data"
        self.atlas = self.image_data / "atlas"

    def create_paths(self):
        if not self.image_data.exists():
            self.image_data.mkdir()
        if not self.atlas.exists():
            self.atlas.mkdir()

    def get_atlas_path(self, atlas_id: int) -> Path:
        return self.atlas / str(atlas_id)

    def get_atlas_sheet_path(self, atlas_id: int, sheet_nb: int) -> Path:
        return self.get_atlas_path(atlas_id) / f'atlas_{sheet_nb}.png'