from pathlib import Path

class ProjectPaths:
    def __init__(self, root: Path):
        self.root = root
        self.image_data = root / "image_data"
        self.image_small = self.image_data / "small"
        self.image_medium = self.image_data / "medium"
        self.image_large = self.image_data / "large"
        self.atlas = self.image_data / "atlas"

    def create_paths(self):
        # Create all directories with exist_ok=True to avoid race conditions
        self.image_data.mkdir(parents=True, exist_ok=True)
        self.image_small.mkdir(parents=True, exist_ok=True)
        self.image_medium.mkdir(parents=True, exist_ok=True)
        self.image_large.mkdir(parents=True, exist_ok=True)
        self.atlas.mkdir(parents=True, exist_ok=True)


    def get_atlas_path(self, atlas_id: int) -> Path:
        return self.atlas / str(atlas_id)

    def get_atlas_sheet_path(self, atlas_id: int, sheet_nb: int) -> Path:
        return self.get_atlas_path(atlas_id) / f'atlas_{sheet_nb}.png'