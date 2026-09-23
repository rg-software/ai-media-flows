"""Spec for 2d/workflows/pbr-material.json - build with scripts/build_workflow.py.

Kept next to the generator it feeds so the workflow can be rebuilt instead of hand-edited.
"""

NOTE = (
    "## pbr-material.json\n\n"
    "Marigold-sourced PBR material set\n\n"
    "**Does:** one texture in -> albedo (basecolor), normal, roughness, metallic, AO and a glTF-valid **ORM** "
    "out. Marigold IID predicts the intrinsics; QFX turns them into maps. This is the graph version of "
    "`scripts/pbr_set.py`, and the two agree: the node's raw metallic (mean **0.359**, 0.5% of pixels > 0.5) "
    "matches the script's **0.354** within the run-to-run spread of the method itself (the script differs from "
    "its own re-run by 0.017 per pixel).\n"
    "**Why two Marigold loaders:** `MarigoldModelLoader` is stateful - the second load replaces the first - so "
    "each model gets its own loader + inference pair. Appearance gives albedo + material (roughness, metallic); "
    "lighting gives albedo + shading + residual, and QFX uses its index 1 as AO.\n"
    "**`albedo_source`:** both Marigold outputs are wired in and BOTH are used - appearance supplies the "
    "albedo plus the roughness/metallic material, lighting supplies the AO - so this setting only picks which "
    "of the two albedos becomes the base colour; the flow ships `appearance`. `gamma_metal_rough 2.2` is what "
    "takes metallic from Marigold's ~0.36 down to ~0.11 in the packed output, so do not 'correct' it away.\n"
    "**The ORM output is glTF-ordered already** (R=occlusion, G=roughness, B=metallic - verified against the "
    "node's own Metallic output, byte-identical), so it drops straight into a glTF/engine material; the "
    "`metallicRoughness` slot and the `occlusion` slot share this one image by convention. No repacking step "
    "is needed. NB the channel swap that DOES matter is Unity's own shaders (R=metal, A=smoothness) - see "
    "PIPELINES open item 1.\n"
    "**Input:** `LoadImage` reads only ComfyUI's `input/`. Marigold wants ~768 px, so feed a seamless, "
    "power-of-two-ish square; the flow ships `2d/tex_stone_seamless.png` at 768.\n"
    "**`seamless_mode` is about your MESH, not a ritual.** Leave it `off` when the texture is applied "
    "once (one quad / one UV island), and leave it on the source side too when the source already tiles. "
    "The source must actually tile only when the UVs **repeat across a surface** - grid/tiled UVs, or "
    "a 3D mesh whose UVs tile; then make it tile first with "
    "`seamless-texture.json` `method=offset`, because the discontinuity is in the albedo and no "
    "normal/AO map hides it (measured on our stone: raw wrap step 13.0 / 40.4 of 255 against a typical "
    "interior step of 6.7; seamless 7.3 / 9.5). QFX's own `seamless_mode` is a separate thing - it crops "
    "the maps 16 px per side - so enable it deliberately, not as a default.\n"
    "**From here:** only the PACKED map is missing - the flow already writes `basecolor`, `normal`, "
    "`roughness`, `ao` and `metallic` at one size, and nothing else needs rewriting (a grayscale AO already "
    "satisfies glTF's R and Unity's G). Two small tools, by target: `scripts/pack_pbr_material.py "
    "--roughness r.png --metallic m.png --out metallicSmoothness.png` for Unity (R=metallic, "
    "A=smoothness=1-roughness, because Unity samples smoothness where glTF packs roughness), or "
    "`scripts/make_gltf_material.py` for glTF (G=roughness, B=metallic; `--mesh/--glb-out` also applies "
    "the material to a mesh that has UVs). Import settings (linear/sRGB off, normal-map type, keep alpha, "
    "Metallic=1) are yours to set - no .meta is emitted.\n\n"
    "---\n*Why it is this way: E25 (node route verified against U4), and the U4 entry in `2d/EXPERIMENTS-2D.md`.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "widgets_values": ["2d/tex_stone_seamless.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "MarigoldModelLoader", "pos": [360, 120],
     "widgets_values": ["prs-eth/marigold-iid-appearance-v1-1"],
     "outputs": [{"name": "marigold_model", "type": "MARIGOLDMODEL", "slot_index": 0}]},
    {"id": 3, "type": "MarigoldDepthEstimation_v2", "pos": [700, 120],
     "widgets_values": [1101, "fixed", 10, 1, 768, "DDIMScheduler", False, False],
     "inputs": [{"name": "marigold_model", "type": "MARIGOLDMODEL"},
                {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 4, "type": "MarigoldModelLoader", "pos": [360, 340],
     "widgets_values": ["prs-eth/marigold-iid-lighting-v1-1"],
     "outputs": [{"name": "marigold_model", "type": "MARIGOLDMODEL", "slot_index": 0}]},
    {"id": 5, "type": "MarigoldDepthEstimation_v2", "pos": [700, 340],
     "widgets_values": [1101, "fixed", 10, 1, 768, "DDIMScheduler", False, False],
     "inputs": [{"name": "marigold_model", "type": "MARIGOLDMODEL"},
                {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 6, "type": "QFXPBRGeneratorAdvanced", "pos": [1060, 220],
     "widgets_values": ["tex_stone", "off", "appearance", 0.45, 2.2, 0.45, 0, 1, 0, 1, 1, True, 2, 1, False],
     "inputs": [{"name": "image", "type": "IMAGE"},
                {"name": "marigold_appearance", "type": "IMAGE"},
                {"name": "marigold_lighting", "type": "IMAGE"}],
     "outputs": [{"name": n, "type": "IMAGE", "slot_index": i} for i, n in enumerate(
         ["Original", "BaseColor", "Normal", "Roughness", "Displacement", "AO", "Metallic", "ORM"])]},
    {"id": 7, "type": "SaveImage", "pos": [1400, 60], "widgets_values": ["2D/pbr_material/basecolor"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 8, "type": "SaveImage", "pos": [1400, 200], "widgets_values": ["2D/pbr_material/normal"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 9, "type": "SaveImage", "pos": [1400, 340], "widgets_values": ["2D/pbr_material/roughness"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 10, "type": "SaveImage", "pos": [1400, 480], "widgets_values": ["2D/pbr_material/ao"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 11, "type": "SaveImage", "pos": [1400, 620], "widgets_values": ["2D/pbr_material/metallic"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 12, "type": "SaveImage", "pos": [1400, 760],
     "widgets_values": ["2D/pbr_material/metallicRoughness_ORM"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 13, "type": "MarkdownNote", "pos": [40, 460]},
]

LINKS = [
    [1, 1, 0, 3, 1, "IMAGE"],
    [2, 2, 0, 3, 0, "MARIGOLDMODEL"],
    [3, 3, 0, 6, 1, "IMAGE"],
    [4, 4, 0, 5, 0, "MARIGOLDMODEL"],
    [5, 1, 0, 5, 1, "IMAGE"],
    [6, 5, 0, 6, 2, "IMAGE"],
    [7, 1, 0, 6, 0, "IMAGE"],
    [8, 6, 1, 7, 0, "IMAGE"],
    [9, 6, 2, 8, 0, "IMAGE"],
    [10, 6, 3, 9, 0, "IMAGE"],
    [11, 6, 5, 10, 0, "IMAGE"],
    [12, 6, 6, 11, 0, "IMAGE"],
    [13, 6, 7, 12, 0, "IMAGE"],
]
