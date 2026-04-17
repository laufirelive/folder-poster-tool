"""Export source images as PSD layers with editable raster masks."""

from __future__ import annotations

import os
from typing import Iterable, Mapping

import numpy as np
from PIL import Image as PilImage
from pytoshop import enums
from pytoshop.enums import ChannelId
from pytoshop import layers
from pytoshop.user.nested_layers import Image as PsdImage, nested_layers_to_psd
from pytoshop import core as psd_core

from models import MatteRecord

# Photoshop compatibility mode: ZIP-compressed layer channel data is rejected
# by some versions, while RAW consistently opens.
_PSD_COMPRESSION = enums.Compression.raw


def _validate_canvas_2_3(canvas_width: int, canvas_height: int) -> None:
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("canvas dimensions must be positive")


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


def _rgb_to_psd_image(
    name: str,
    rgb: np.ndarray,
    top: int,
    left: int,
) -> PsdImage:
    channels = {
        ChannelId.red: np.ascontiguousarray(rgb[:, :, 0]),
        ChannelId.green: np.ascontiguousarray(rgb[:, :, 1]),
        ChannelId.blue: np.ascontiguousarray(rgb[:, :, 2]),
    }
    return PsdImage(
        name=name,
        visible=False,
        top=top,
        left=left,
        channels=channels,
    )


def _opaque_transparency_channel(height: int, width: int) -> layers.ChannelImageData:
    return layers.ChannelImageData(
        image=np.full((height, width), 255, dtype=np.uint8),
        compression=_PSD_COMPRESSION,
    )


def export_matte_psd(
    matte_records: Iterable[MatteRecord],
    source_path_by_source_id: Mapping[str, str],
    canvas_width: int,
    canvas_height: int,
    output_path: str,
) -> None:
    """Write PSD with hidden source-image layers and editable raster layer masks."""
    _validate_canvas_2_3(canvas_width, canvas_height)

    layer_specs: list[tuple[PsdImage, np.ndarray]] = []
    for rec in matte_records:
        if not rec.is_active:
            continue
        source_path = source_path_by_source_id.get(rec.source_id, "")
        if not source_path or not os.path.isfile(source_path):
            raise ValueError(f"missing source raster for {rec.source_id}")
        if not rec.mask_path or not os.path.isfile(rec.mask_path):
            raise ValueError(f"missing mask for {rec.source_id}")

        with PilImage.open(source_path) as pil_src:
            rgb = np.asarray(pil_src.convert("RGB"), dtype=np.uint8)
        with PilImage.open(rec.mask_path) as pil_mask:
            mask = np.asarray(pil_mask.convert("L"), dtype=np.uint8)

        ih, iw = rgb.shape[0], rgb.shape[1]
        if mask.shape[0] != ih or mask.shape[1] != iw:
            raise ValueError(f"mask size mismatch for {rec.source_id}")

        left = (canvas_width - iw) // 2
        top = (canvas_height - ih) // 2
        name = _sanitize_layer_name(source_path)
        layer_specs.append((_rgb_to_psd_image(name, rgb, top=top, left=left), mask))

    if not layer_specs:
        raise ValueError("no active matte images")

    psd = nested_layers_to_psd(
        [spec[0] for spec in layer_specs],
        color_mode=enums.ColorMode.rgb,
        size=(canvas_width, canvas_height),
        compression=_PSD_COMPRESSION,
    )

    layer_records = psd.layer_and_mask_info.layer_info.layer_records
    if len(layer_records) != len(layer_specs):
        raise ValueError("unexpected layer count while attaching masks")

    # ``nested_layers_to_psd`` emits layer records in reverse stack order,
    # so masks must be attached against reversed input specs.
    for rec, (_layer, mask) in zip(layer_records, reversed(layer_specs)):
        h = rec.bottom - rec.top
        w = rec.right - rec.left
        rec.channels[ChannelId.transparency] = _opaque_transparency_channel(h, w)
        rec.channels[ChannelId.user_layer_mask] = layers.ChannelImageData(
            image=np.ascontiguousarray(mask),
            # Photopea compatibility: ZIP-compressed user masks may decode as
            # solid black. Keep mask channel uncompressed for robustness.
            compression=enums.Compression.raw,
        )
        rec.mask.top = rec.top
        rec.mask.left = rec.left
        rec.mask.bottom = rec.bottom
        rec.mask.right = rec.right
    with open(output_path, "wb") as f:
        psd.write(f)
    _verify_export_integrity(output_path)


def _verify_export_integrity(output_path: str) -> None:
    """Read back exported PSD and assert hidden layers + usable masks."""
    with open(output_path, "rb") as f:
        psd = psd_core.PsdFile.read(f)
    layer_info = psd.layer_and_mask_info.layer_info
    visible_names: list[str] = []
    missing_masks: list[str] = []
    for rec in layer_info.layer_records:
        if bool(getattr(rec, "visible", False)):
            visible_names.append(getattr(rec, "name", "<unnamed>"))
        if rec.mask.width <= 0 or rec.mask.height <= 0:
            missing_masks.append(getattr(rec, "name", "<unnamed>"))
    if visible_names:
        joined = ", ".join(visible_names[:5])
        if len(visible_names) > 5:
            joined += ", ..."
        raise ValueError(f"exported PSD contains visible layers: {joined}")
    if missing_masks:
        joined = ", ".join(missing_masks[:5])
        if len(missing_masks) > 5:
            joined += ", ..."
        raise ValueError(f"exported PSD contains layers without usable masks: {joined}")
