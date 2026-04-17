"""
Foreground matting using Hugging Face ``ZhengPeng7/BiRefNet`` (BiRefNet).

**Output:** RGBA PNG — original RGB pixels with alpha from the predicted foreground mask
(resized to the source image size).

**Stub mode:** set ``FOLDER_POSTER_MATTING_STUB=1`` to skip PyTorch inference and write an
RGBA copy of the input (full opacity). Useful for CI or environments without a GPU.

**Model:** ``MODEL_ID`` below; loaded via ``transformers.AutoModelForImageSegmentation``
with ``trust_remote_code=True`` (see model card).
"""

from __future__ import annotations

import os
from typing import Any, Tuple

from core.model_manager import ModelManager

_STUB_ENV = "FOLDER_POSTER_MATTING_STUB"


def _select_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_model() -> Tuple[Any, str]:
    """Load BiRefNet weights and move to the selected device. Returns ``(model, device)``."""
    import torch
    from transformers import AutoModelForImageSegmentation

    model_dir = ModelManager().ensure_installed()
    device = _select_device()
    model = AutoModelForImageSegmentation.from_pretrained(
        model_dir,
        trust_remote_code=True,
        local_files_only=True,
    )
    model.eval()
    model.to(device)
    if device == "cuda":
        torch.set_float32_matmul_precision("high")
        model.half()
    else:
        # Avoid dtype mismatch on CPU/MPS when weights are loaded as fp16.
        model.float()
    return model, device


def _stub_predict_outputs(input_path: str, matte_path: str, mask_path: str) -> None:
    """Write RGBA + grayscale mask outputs without loading the model."""
    from PIL import Image

    matte_dir = os.path.dirname(os.path.abspath(matte_path)) or "."
    mask_dir = os.path.dirname(os.path.abspath(mask_path)) or "."
    os.makedirs(matte_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)

    rgb = Image.open(input_path).convert("RGB")
    rgba = rgb.copy()
    mask = Image.new("L", rgb.size, color=255)
    rgba.putalpha(mask)
    rgba.save(matte_path)
    mask.save(mask_path)


class MattingEngine:
    """Lazy-loaded BiRefNet matting engine."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._device: str | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        self._model, self._device = _load_model()

    def predict_outputs(self, input_path: str, matte_path: str, mask_path: str) -> None:
        """
        Run matting on ``input_path`` and save both RGBA matte + grayscale mask.

        Parent directories are created for both outputs.
        """
        if os.environ.get(_STUB_ENV) == "1":
            _stub_predict_outputs(input_path, matte_path, mask_path)
            return

        from PIL import Image
        import torch
        from torchvision import transforms

        self._ensure_loaded()
        assert self._model is not None and self._device is not None
        device = self._device
        model = self._model

        image = Image.open(input_path).convert("RGB")
        image_size = (1024, 1024)
        transform_image = transforms.Compose(
            [
                transforms.Resize(image_size),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        input_tensor = transform_image(image).unsqueeze(0).to(device)
        if device == "cuda":
            input_tensor = input_tensor.half()

        with torch.no_grad():
            raw = model(input_tensor)[-1]
            preds = raw.sigmoid().cpu()
        pred = preds[0].squeeze()

        pred_pil = transforms.ToPILImage()(pred)
        mask = pred_pil.resize(image.size, Image.Resampling.LANCZOS)
        rgba = image.copy()
        rgba.putalpha(mask)

        matte_dir = os.path.dirname(os.path.abspath(matte_path))
        mask_dir = os.path.dirname(os.path.abspath(mask_path))
        if matte_dir:
            os.makedirs(matte_dir, exist_ok=True)
        if mask_dir:
            os.makedirs(mask_dir, exist_ok=True)
        rgba.save(matte_path)
        mask.convert("L").save(mask_path)

    def predict_matte(self, input_path: str, output_path: str) -> None:
        """
        Backward-compatible wrapper: emit matte and sibling ``*_mask.png``.
        """
        stem, _ext = os.path.splitext(os.path.abspath(output_path))
        mask_path = f"{stem}_mask.png"
        self.predict_outputs(input_path, output_path, mask_path)
