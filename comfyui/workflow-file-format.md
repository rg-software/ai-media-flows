# ComfyUI workflow file format (.json)

The ComfyUI workflow JSON ("Workflow" format, `version: 0.4`) is what gets saved by the UI (Workflow → Export) and can be imported back (drag-drop or Open). This is the format we hand-author for scenarios. Understanding it deeply is the difference between "I clicked in the UI" and "I can build a pipeline as data".

## Top-level structure

```jsonc
{
  "last_node_id": 12,        // highest node id used so far
  "last_link_id": 15,        // highest link id used so far
  "nodes": [ { ...node... }, ... ],
  "links": [ [ ...link... ], ... ],
  "groups": [],
  "config": {},
  "extra": {},               // canvas scale/offset
  "version": 0.4
}
```

`last_node_id` / `last_link_id` are just the running counters; the UI renumbers on import if needed. You can hand-author with sensible ids as long as they're unique.

## Node object

```jsonc
{
  "id": 4,
  "type": "Hy3DRenderMultiView",      // exact node class name from /object_info
  "pos": [-550, 200],                 // canvas position
  "size": [342, 170],                 // node box size
  "flags": {},
  "order": 3,                         // execution order (topological-ish); UI uses this
  "mode": 0,                          // 0=normal, 2=bypassed/*muted*
  "inputs": [                         // the *slots* on the left side
    { "name": "trimesh", "type": "TRIMESH", "link": 3 }
  ],
  "outputs": [                        // the *slots* on the right side
    { "name": "normal_maps", "type": "IMAGE", "links": [6], "slot_index": 0 },
    { "name": "renderer", "type": "MESHRENDER", "links": [10], "slot_index": 2 }
  ],
  "properties": { "Node name for S&R": "Hy3DRenderMultiView" },
  "widgets_values": [1024, 2048, "world"]   // the control values, IN ORDER
}
```

Key points:

- **`inputs`/`outputs` `name`+`type` must match the node's schema** (from `/object_info`). The `link` field on an input is one link id, or `null`. The `links` array on an output lists link ids, or `null`.
- `slot_index` on outputs: which output slot (0-based). Links reference `(source_node, source_slot_index)`.
- **`widgets_values` order is critical.** It is the values in UI order — for a node whose inputs are `{trimesh, render_size, texture_size, camera_config, normal_space}`, the widgets are `render_size, texture_size, normal_space` → `[1024, 2048, "world"]`. **Your `inputs`/`outputs` slots are NOT widgets** — widgets are the inline controls, in `/object_info` `input_order` order, and only for non-linking fields. Get this order wrong and values land in the wrong parameters (a recurring ComfyUI footgun).

## Link object

```jsonc
[ 3, 3, 0, 12, 0, "TRIMESH" ]
//  ^  ^  ^  ^   ^  ^
//  |  |  |  |   |  └── type
//  |  |  |  |   └── destination slot_index
//  |  |  |  └── destination node id
//  |  |  └── source slot_index
//  |  └── source node id
//  └── link id
```

## Rules that matter when hand-editing workflows

1. **`widgets_values` are datatype-sensitive.** Combo values are strings (`"world"`), booleans are `true/false`, INT/FLOAT are numbers. A `FLOAT` widget still expects a number (not a string).
2. **`widgets_values` vs `inputs` are separate worlds.** If a widget exists in the schema it must have a value in `widgets_values` (or the import may fill defaults / mis-fill). If you removed a node's widget, the array length shifts and everything downstream mis-lands.
3. **`mode: 2`** marks a node bypassed/muted (greyed). Keep `mode: 0`.
4. On import, missing nodes → red "Missing nodes" banner. The import won't error; it just shows missing. **The golden check:** after importing, queue once — ComfyUI validates the prompt structure and reports *specifically* which node/field is wrong (`- Value not in list: model_name: None not in [...]`), which is far more actionable than staring at JSON.
5. **`ComfyUI-Login`** protects `/object_info`, `/prompt` etc. POST `/login`, keep the session cookie.
6. `serializationVersion`/`version` may be 0.4; new ComfyUI can import older, not always vice versa.

## Node source-of-truth checklist (authoring or debugging)

1. `GET /object_info/<NodeType>` → gives `input.order` (`required`/`optional`), `output` + `output_name`, combos (`COMBO` values), and tooltips. **This is always correct for the installed version.**
2. Read the node's Python source in the custom-node repo when in doubt about semantics (`hy3d_nodes.py`, `mesh_render.py`, ...).
3. Watch the server console/log after queue — it prints the full traceback with node ids.

## Our own hand-authored workflows

Each scenario's `workflows/` folder contains JSONs built by this recipe. Notable examples that exercised unusual cases:
- `3d/workflows/hy3d-full-workflow.json` — we inserted `Hy3DMeshUVWrap` between two nodes and re-linked; the async `order` field still executed correctly after import.
- `3d/workflows/scratch/tripo-chain-workflow.json` — the `Tripo*` nodes' `widgets_values` wiring for COMBO options (`v1.4-20240625` etc.), demonstrating correct combo-value placement.
- `3d/workflows/scratch/moge-free-chain.json` — MoGe built-in nodes (`LoadMoGeModel` file combo, `MoGeInference`, `MoGePointMapToMesh`), including the "file combo empty until model present" gotcha.