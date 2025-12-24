from io import BytesIO

from PIL import Image

from panoptic.core.task.task import Task
from panoptic.models import ImageAtlas


class GenerateAtlasTask(Task):
    def __init__(self):
        super().__init__()

    async def run(self):
        instances = await self._project.db.get_instances()
        sha1s = list({i.sha1 for i in instances})
        sha1_mapping: dict[str, tuple[int, int]] = {}

        atlas_id = 0
        atlas_width = 2048
        atlas_height = 2048
        cell_width = 32
        cell_height = 32

        # Calculate how many cells fit in the atlas
        cells_per_row = atlas_width // cell_width
        cells_per_col = atlas_height // cell_height
        cells_per_sheet = cells_per_row * cells_per_col

        sheets: list[Image.Image] = []
        current_sheet: Image.Image | None = None
        current_cell_index = 0
        current_sheet_index = 0

        for sha1 in sha1s:
            img_blob = await self._project.db.get_small_image(sha1)

            # Create new sheet if needed
            if current_sheet is None or current_cell_index >= cells_per_sheet:
                if current_sheet is not None:
                    sheets.append(current_sheet)
                    current_sheet_index += 1

                current_sheet = Image.new('RGBA', (atlas_width, atlas_height), (0, 0, 0, 0))
                current_cell_index = 0

            # Calculate cell position from index
            row = current_cell_index // cells_per_row
            col = current_cell_index % cells_per_row
            cell_x = col * cell_width
            cell_y = row * cell_height

            try:
                # Load and process the image
                img_stream = BytesIO(img_blob)
                img = Image.open(img_stream).convert("RGBA")
                img.load()

                # Resize image to fit within cell while maintaining aspect ratio
                img.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)

                # Calculate centering offset
                img_width, img_height = img.size
                x_offset = cell_x + (cell_width - img_width) // 2
                y_offset = cell_y + (cell_height - img_height) // 2

                # Paste the image centered in its cell
                current_sheet.paste(img, (x_offset, y_offset), img)

                # Record the mapping (sheet number, cell index)
                sha1_mapping[sha1] = (current_sheet_index, current_cell_index)

            except Exception as e:
                print(f"Error processing image {sha1}: {e}")
                # Still advance the cell index even on error

            current_cell_index += 1

        # Add the final sheet
        if current_sheet is not None:
            sheets.append(current_sheet)

        atlas = ImageAtlas(atlas_id, len(sheets), atlas_width, atlas_height, cell_width, cell_height, sha1_mapping)
        await self._project.db.import_atlas(atlas)
        await self.save_sheets(atlas, sheets)


    async def save_sheets(self, atlas: ImageAtlas, sheets: list[Image.Image]):
        if not self._project.paths.get_atlas_path(atlas.id).exists():
            self._project.paths.get_atlas_path(atlas.id).mkdir()
        for i, sheet in enumerate(sheets):
            path = self._project.paths.get_atlas_sheet_path(atlas.id, i)
            await self._project.run_async(sheet.save, path, format="PNG", optimize=True)








