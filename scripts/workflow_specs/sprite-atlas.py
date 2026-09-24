"""Spec for 2d/workflows/sprite-atlas.json - build with scripts/build_workflow.py.

COMBINE individual sprites into one sheet - the job the name promises and the old flow did not do (it carried
a generation arm plus a slicing arm, so there was no way to pack your own files).

Uses core `ImageGridComposite2x2`, which takes four named images: no batch node, no `inputcount`, and no
DYNAMIC sockets - `ImageBatchMulti` invents `image_3`, `image_4`... from `inputcount`, which
`/object_info` does not declare, so headless tools (including our own checker) cannot see them and a
position-based replica wires only two of four. For a 2x2 sheet the composite node is both simpler and
checkable; the note records the batch route for other counts.
"""

NOTE = (
    "## sprite-atlas.json\n\n"
    "Combine individual sprites into one sheet\n\n"
    "**Does:** packs four separate images into one 2x2 sheet with core `ImageGridComposite2x2` - swap the "
    "`LoadImage` nodes for your own files. It ships the four 64 px potion sprites, so it runs as-is and "
    "reproduces `input/2d/potion_atlas.png` exactly (verified pixel-identical).\n"
    "**Other counts:** `ImageBatchMulti` (`inputcount`, then `image_1`...) feeds a generic `ImageGrid` "
    "(`columns`, `cell_width`, `cell_height`, `padding`) - use that pair for anything that is not 2x2 or 3x3. "
    "Those extra inputs are created by the frontend, so a headless replica must build them by hand.\n"
    "**No generation here:** make the sprites with `pixel-art.json` (or convert an existing picture with "
    "`pixel-art-convert.json` / `pixel-art-restyle.json`), then pack them.\n"
    "**Unpacking?** `sprite-slice.json` turns a sheet back into tiles and proves the round-trip in the same "
    "run.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  \u00b7  Why it is this way: **E6/E33** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 120], "size": [320, 320],
     "widgets_values": ["2d/potion_1.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "LoadImage", "pos": [40, 460], "size": [320, 320],
     "widgets_values": ["2d/potion_2.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 3, "type": "LoadImage", "pos": [40, 800], "size": [320, 320],
     "widgets_values": ["2d/potion_3.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 4, "type": "LoadImage", "pos": [40, 1140], "size": [320, 320],
     "widgets_values": ["2d/potion_4.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 5, "type": "ImageGridComposite2x2", "pos": [420, 300], "size": [300, 180],
     "inputs": [{"name": "image1", "type": "IMAGE"}, {"name": "image2", "type": "IMAGE"},
                {"name": "image3", "type": "IMAGE"}, {"name": "image4", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 6, "type": "SaveImage", "pos": [780, 300], "size": [400, 300],
     "widgets_values": ["2D/atlas/potion_atlas"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 7, "type": "MarkdownNote", "pos": [420, 560], "size": [420, 320]},
]

LINKS = [
    [1, 1, 0, 5, 0, "IMAGE"],
    [2, 2, 0, 5, 1, "IMAGE"],
    [3, 3, 0, 5, 2, "IMAGE"],
    [4, 4, 0, 5, 3, "IMAGE"],
    [5, 5, 0, 6, 0, "IMAGE"],
]
