import os
import sys
from pathlib import Path

import pytest


def _ensure_project_core():
    _root = str(Path(__file__).resolve().parents[2])
    sys.path.insert(0, _root)
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]


def test_is_installed_requires_config_and_weights(tmp_path):
    _ensure_project_core()
    from core.model_manager import ModelManager

    mm = ModelManager(model_dir=str(tmp_path / "models"))
    assert not mm.is_installed()

    os.makedirs(mm.get_model_dir(), exist_ok=True)
    Path(mm.get_model_dir(), "config.json").write_text("{}", encoding="utf-8")
    assert not mm.is_installed()

    Path(mm.get_model_dir(), "model.safetensors").write_bytes(b"fake")
    assert mm.is_installed()


def test_ensure_installed_raises_for_missing_model(tmp_path):
    _ensure_project_core()
    from core.model_manager import ModelManager, ModelNotInstalledError

    mm = ModelManager(model_dir=str(tmp_path / "models"))
    with pytest.raises(ModelNotInstalledError):
        mm.ensure_installed()


def test_download_model_invokes_snapshot_download(monkeypatch, tmp_path):
    _ensure_project_core()
    from core.model_manager import ModelManager

    calls = {}

    def fake_snapshot_download(**kwargs):
        calls.update(kwargs)
        local_dir = kwargs["local_dir"]
        os.makedirs(local_dir, exist_ok=True)
        Path(local_dir, "config.json").write_text("{}", encoding="utf-8")
        Path(local_dir, "model.safetensors").write_bytes(b"fake")
        return local_dir

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    mm = ModelManager(model_dir=str(tmp_path / "models"))
    out = mm.download_model()
    assert out == mm.get_model_dir()
    assert calls["repo_id"] == "ZhengPeng7/BiRefNet"
    assert calls["resume_download"] is True
