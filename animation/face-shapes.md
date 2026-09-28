# Face shapes: what the 72 morph targets are

Our S17 export writes facial expression as **72 glTF morph targets**, and glTF gives morph targets no names - so an engine has to map them **by index**. The order is not arbitrary: the exporter writes them in basis order (`for e in range(NEXPR)` over MHR's `expr_basis`, `glb_skeletal.py:245`), so **morph target `k` is MHR expression axis `k`**.

This table comes from the `_AXIS_TO_ARKIT` map in the node pack's own `face_expression.py` (inside ComfyUI's core `comfy_extras`), which is the mapping `SAM3DBody_FaceExpression` uses to turn MediaPipe's 52 ARKit blendshapes into the 72-axis MHR basis. **44 of the 72 axes are reachable from video**; the rest stay at zero. Read it as "axis = which ARKit shape drives it, and with what weight" - an axis with two shapes is a blend, which is why the count is not 52.

| axis | ARKit shape (weight) | group |
|---|---|---|
| 0 | browDownLeft (1.00) | brow |
| 1 | browDownRight (1.00) | brow |
| 2 | cheekPuff (1.00) | cheek |
| 3 | cheekPuff (1.00) | cheek |
| 4 | cheekSquintLeft (1.00) | cheek |
| 5 | cheekSquintRight (1.00) | cheek |
| 6 | mouthStretchLeft (1.00) | mouth |
| 7 | mouthStretchRight (1.00) | mouth |
| 8 | mouthShrugLower (1.00) | mouth |
| 9 | mouthShrugUpper (1.00) | mouth |
| 10 | mouthDimpleLeft (1.00) | mouth |
| 11 | mouthDimpleRight (1.00) | mouth |
| 12 | eyeLookDownLeft (0.30) | eye |
| 13 | eyeLookDownRight (0.30) | eye |
| 14 | eyeBlinkLeft (1.00) | eye |
| 15 | eyeBlinkRight (1.00) | eye |
| 16 | eyeLookOutLeft (1.00) | eye |
| 17 | eyeLookInRight (1.00) | eye |
| 18 | eyeLookInLeft (1.00) | eye |
| 19 | eyeLookOutRight (1.00) | eye |
| 22 | eyeLookUpLeft (1.00), browInnerUp (0.50) | eye + brow |
| 23 | eyeLookUpRight (1.00), browInnerUp (0.50) | eye + brow |
| 24 | jawOpen (1.00), mouthLowerDownLeft (0.30), mouthLowerDownRight (0.30) | jaw |
| 25 | jawLeft (1.00) | jaw |
| 26 | jawRight (1.00) | jaw |
| 27 | jawForward (1.00) | jaw |
| 28 | eyeSquintLeft (1.00) | eye |
| 29 | eyeSquintRight (1.00) | eye |
| 32 | mouthSmileLeft (1.00) | mouth |
| 33 | mouthSmileRight (1.00) | mouth |
| 40 | mouthLeft (1.00) | mouth |
| 41 | mouthRight (1.00) | mouth |
| 42 | mouthFrownLeft (1.00) | mouth |
| 43 | mouthFrownRight (1.00) | mouth |
| 54 | mouthLowerDownLeft (1.00) | mouth |
| 55 | mouthLowerDownRight (1.00) | mouth |
| 60 | noseSneerLeft (1.00) | nose |
| 61 | noseSneerRight (1.00) | nose |
| 66 | browOuterUpLeft (1.00) | brow |
| 67 | browOuterUpRight (1.00) | brow |
| 68 | eyeWideLeft (1.00) | eye |
| 69 | eyeWideRight (1.00) | eye |
| 70 | mouthUpperUpLeft (1.00) | mouth |
| 71 | mouthUpperUpRight (1.00) | mouth |

**Not driven by video (28 axes, always zero with this pipeline):** 20, 21, 30, 31, 34-39, 44-53, 56-59, 62-65. So a rig's face only needs mapping onto the 44 above; the remainder are MHR's own shape space, reachable by retargeting a *named* ARKit performance from elsewhere rather than from footage.

**Measured on our example clip** (`woman_holding_water_glass.mp4`, E20/E20b): **28 of the 72 axes move**, and the most active are **15-19** - `eyeBlinkRight`, `eyeLookOutLeft`, `eyeLookInRight`, `eyeLookInLeft`, `eyeLookOutRight`. Eye and gaze shapes lead, not the jaw; a person looking around exercises the eye axes hardest. `jawOpen` (24) is the mouth axis to check first on a clip where someone talks.

The `blendshape_smooth_window` knob is the facial twin of the body's `bone_smooth_window`, and its sweet spot is **15** (E20b): the largest single-frame weight jump falls from 0.4153 at 1 and 0.3038 at the shipped 7 to **0.1810**, while keeping 87% of each shape's range and 0.984 correlation with the unsmoothed track. At 31 the spike falls further but the *performance* starts going with it - 72% of the range and 0.946 correlation - so larger is not better. See `EXPERIMENTS.md` E20/E20b.
