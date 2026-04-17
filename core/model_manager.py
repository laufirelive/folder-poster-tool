"""Model installation and download helpers for BiRefNet."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

MODEL_REPO_ID = "ZhengPeng7/BiRefNet"
APP_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = str(APP_ROOT / "models" / "birefnet")
MODEL_CONFIG_FILE = "config.json"
_WEIGHT_FILE_NAMES = ("model.safetensors", "pytorch_model.bin")
_MODEL_MISSING_PREFIX = "[model_missing]"


class ModelNotInstalledError(RuntimeError):
    """Raised when the required local model files are missing."""


def is_model_missing_error(message: str) -> bool:
    return str(message or "").startswith(_MODEL_MISSING_PREFIX)


class ModelManager:
    """Manage local model presence and downloading."""

    def __init__(self, model_dir: str = MODEL_DIR, repo_id: str = MODEL_REPO_ID) -> None:
        self._model_dir = os.path.abspath(os.path.expanduser(model_dir))
        self._repo_id = repo_id

    def get_model_dir(self) -> str:
        return self._model_dir

    def _has_weight_file(self) -> bool:
        model_path = Path(self._model_dir)
        if not model_path.is_dir():
            return False
        for name in _WEIGHT_FILE_NAMES:
            if (model_path / name).is_file():
                return True
        if any(model_path.glob("pytorch_model-*.bin")):
            return True
        if any(model_path.glob("*.safetensors")):
            return True
        return False

    def is_installed(self) -> bool:
        return os.path.isfile(os.path.join(self._model_dir, MODEL_CONFIG_FILE)) and self._has_weight_file()

    def ensure_installed(self) -> str:
        if not self.is_installed():
            raise ModelNotInstalledError(
                f"{_MODEL_MISSING_PREFIX} 未检测到本地模型，请先在模型下载页完成下载。"
            )
        return self._model_dir

    def download_model(
        self,
        progress_cb: Callable[[int, int, str], None] | None = None,
    ) -> str:
        """Download the fixed BiRefNet model to local path."""
        from huggingface_hub import snapshot_download

        os.makedirs(self._model_dir, exist_ok=True)

        tqdm_cls = None
        if progress_cb is not None:
            try:
                from tqdm import tqdm as tqdm_base
            except Exception:  # noqa: BLE001
                tqdm_base = None
            if tqdm_base is not None:

                class _ProgressTqdm(tqdm_base):
                    def __init__(self, *args, **kwargs):
                        kwargs.pop("name", None)
                        kwargs.setdefault("disable", False)
                        super().__init__(*args, **kwargs)

                    def update(self, n=1):
                        super().update(n)
                        total = int(self.total or 0)
                        done = int(self.n or 0)
                        progress_cb(done, total, self.desc or "")

                tqdm_cls = _ProgressTqdm

        kwargs = dict(
            repo_id=self._repo_id,
            local_dir=self._model_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        if tqdm_cls is not None:
            kwargs["tqdm_class"] = tqdm_cls
        snapshot_download(**kwargs)
        self.ensure_installed()
        return self._model_dir
