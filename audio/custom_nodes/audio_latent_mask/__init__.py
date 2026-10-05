"""Audio-latent noise mask: the 1-line gap that blocks region repaint for audio.

WHY THIS EXISTS (E19, ai-gamedev-tasks)

ComfyUI's `SetLatentNoiseMask` writes:

    s["noise_mask"] = mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1]))

That unconditional 4-D reshape is correct for IMAGE latents (4-D, two spatial dims).
An AUDIO latent is 3-D - `[batch, channels, frames]` - so `reshape_mask` takes its
`dims == 1` path, which calls `interpolate(input_mask, size=[frames], mode="linear")`
and therefore requires a 3-D mask. Handing it the 4-D mask above raises:

    Input and output must have the same number of spatial dimensions, but got input
    with spatial dimensions of [1, 3000] and output size of torch.Size([3000])

This node is `SetLatentNoiseMask` for latents with ONE spatial dimension: it stores the
mask as-is, so the `linear` path gets the 3-D `[B, H, W]` mask that `SolidMask` /
`MaskComposite` already produce, interpolates it along the time axis, and broadcasts it
across channels. That is the whole fix - masked-latent (region) sampling works for audio
once the mask keeps its shape.

Drop-in: same inputs/output as `SetLatentNoiseMask`, so a flow can swap one node.
"""
from __future__ import annotations


class SetAudioLatentNoiseMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples": ("LATENT",), "mask": ("MASK",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "set_mask"
    CATEGORY = "audio"
    DESCRIPTION = ("Set a noise mask on a latent with ONE spatial dimension (audio: "
                   "[B, C, frames]). Like SetLatentNoiseMask but without the 4-D reshape.")

    def set_mask(self, samples, mask):
        s = samples.copy()
        if mask.dim() == 4 and mask.shape[1] == 1:
            mask = mask.reshape((-1, mask.shape[-2], mask.shape[-1]))
        s["noise_mask"] = mask
        return (s,)


NODE_CLASS_MAPPINGS = {"SetAudioLatentNoiseMask": SetAudioLatentNoiseMask}
NODE_DISPLAY_NAME_MAPPINGS = {"SetAudioLatentNoiseMask": "Set Audio Latent Noise Mask"}
