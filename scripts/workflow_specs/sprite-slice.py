"""Spec for 2d/workflows/sprite-slice.json - build with scripts/build_workflow.py.

UNPACK a sheet into tiles, and prove the round-trip in the same run: `SplitImageToTileList` cuts the atlas
into a tile list (SaveImage writes one file per tile), and `ImageMergeTileList` puts that list back together
so the rebuilt sheet can be compared with the original. That is the E6 round-trip, kept in the flow instead
of only in the notes.
"""

NOTE = (
    "## sprite-slice.json\n\n"
    "Slice a sheet into tiles (and prove the round-trip)\n\n"
    "**Does:** `SplitImageToTileList` cuts an atlas into a list of tiles - **`tile_width`/`tile_height` must "
    "match the sheet** (64x64 here, `overlap` 0) - and `SaveImage` writes one file per tile. The same tile "
    "list goes through `ImageMergeTileList` (`final_width`/`final_height` = the sheet's size) so the rebuilt "
    "sheet is saved too: if the two sheets match, the cut is exact. That round-trip is the check that "
    "`sprite-atlas.json` packs correctly.\n"
    "**Packing instead?** `sprite-atlas.json` combines individual sprites into a sheet.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  \u00b7  Why it is this way: **E6/E33** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "size": [320, 320],
     "widgets_values": ["2d/potion_atlas.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "SplitImageToTileList", "pos": [420, 200], "size": [300, 130],
     "widgets_values": [64, 64, 0],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 3, "type": "SaveImage", "pos": [780, 120], "size": [400, 300],
     "widgets_values": ["2D/atlas/tiles"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    # rebuild from the tile list: 2x2 tiles of 64 px = 128x128
    {"id": 4, "type": "ImageMergeTileList", "pos": [780, 480], "size": [300, 130],
     "widgets_values": [128, 128, 0],
     "inputs": [{"name": "image_list", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 5, "type": "SaveImage", "pos": [1140, 480], "size": [400, 300],
     "widgets_values": ["2D/atlas/rebuilt"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 6, "type": "MarkdownNote", "pos": [420, 620], "size": [420, 320]},
]

LINKS = [
    [1, 1, 0, 2, 0, "IMAGE"],
    [2, 2, 0, 3, 0, "IMAGE"],
    [3, 2, 0, 4, 0, "IMAGE"],
    [4, 4, 0, 5, 0, "IMAGE"],
]
