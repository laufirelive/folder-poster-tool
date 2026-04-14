"""
Export matte PNGs as a single PSD with a fixed canvas.

Layer ordering: each active matte becomes one image layer in the same order as the
input ``matte_records`` sequence (after filtering). In the resulting PSD, earlier
records appear lower in the layer stack (below later records), matching typical
bottom-to-top iteration order.
"""

from __future__ import annotations

import os
from typing import Iterable, List

import numpy as np
from PIL import Image as PilImage
from pytoshop import enums
from pytoshop.enums import ChannelId
from pytoshop.user.nested_layers import Image as PsdImage, nested_layers_to_psd

from models import MatteRecord

# RLE uses optional ``pytoshop.packbits`` (C extension); when missing, ZIP works
# without it and stays smaller than raw.
_PSD_COMPRESSION = enums.Compression.zip


def _validate_canvas_2_3(canvas_width: int, canvas_height: int) -> None:
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("canvas dimensions must be positive")
    expected = 2.0 / 3.0
    actual = canvas_width / canvas_height
    if abs(actual - expected) > 1e-4:
        raise ValueError(
            "canvas must have a 2:3 width:height aspect ratio, "
            f"got {canvas_width}×{canvas_height}"
        )


def _sanitize_layer_name(matte_path: str) -> str:
    base = os.path.basename(matte_path) or "layer"
    encoded = base.encode("utf-8")
    if len(encoded) <= 127:
        return base
    truncated = encoded[:127]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return "layer"


def _rgba_to_psd_image(
    name: str,
    rgba: np.ndarray,
    top: int,
    left: int,
) -> PsdImage:
    h, w = rgba.shape[0], rgba.shape[1]
    channels = {
        ChannelId.red: np.ascontiguousarray(rgba[:, :, 0]),
        ChannelId.green: np.ascontiguousarray(rgba[:, :, 1]),
        ChannelId.blue: np.ascontiguousarray(rgba[:, :, 2]),
        ChannelId.transparency: np.ascontiguousarray(rgba[:, :, 3]),
    }
    return PsdImage(
        name=name,
        visible=False,
        top=top,
        left=left,
        channels=channels,
    )


def export_matte_psd(
    matte_records: Iterable[MatteRecord],
    canvas_width: int,
    canvas_height: int,
    output_path: str,
) -> None:
    """Write a PSD with one hidden layer per active matte, centered on a 2:3 canvas."""
    _validate_canvas_2_3(canvas_width, canvas_height)

    layers: List[PsdImage] = []
    for rec in matte_records:
        if not rec.is_active:
            continue
        path = rec.matte_path
        if not path or not os.path.isfile(path):
            continue

        with PilImage.open(path) as pil_img:
            rgba = np.asarray(pil_img.convert("RGBA"), dtype=np.uint8)

        ih, iw = rgba.shape[0], rgba.shape[1]
        left = (canvas_width - iw) // 2
        top = (canvas_height - ih) // 2
        name = _sanitize_layer_name(path)
        layers.append(_rgba_to_psd_image(name, rgba, top=top, left=left))

    if not layers:
        raise ValueError("no active matte images")

    psd = nested_layers_to_psd(
        layers,
        color_mode=enums.ColorMode.rgb,
        size=(canvas_width, canvas_height),
        compression=_PSD_COMPRESSION,
    )
    with open(output_path, "wb") as f:
        psd.write(f)
