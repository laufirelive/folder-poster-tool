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

MODEL_ID = "ZhengPeng7/BiRefNet"

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

    device = _select_device()
    model = AutoModelForImageSegmentation.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
    )
    model.eval()
    model.to(device)
    if device == "cuda":
        torch.set_float32_matmul_precision("high")
        model.half()
    return model, device


def _stub_predict_matte(input_path: str, output_path: str) -> None:
    """Write an RGBA copy of the input (full alpha) without loading the model."""
    from PIL import Image

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    Image.open(input_path).convert("RGBA").save(output_path)


class MattingEngine:
    """Lazy-loaded BiRefNet matting engine."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._device: str | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        self._model, self._device = _load_model()

    def predict_matte(self, input_path: str, output_path: str) -> None:
        """
        Run matting on ``input_path`` and save an RGBA PNG to ``output_path``.

        Parent directories for ``output_path`` are created if needed.
        """
        if os.environ.get(_STUB_ENV) == "1":
            _stub_predict_matte(input_path, output_path)
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

        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        rgba.save(output_path)
