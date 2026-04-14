import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


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


def test_predict_matte_writes_file(tmp_path, monkeypatch):
    _ensure_project_core()
    monkeypatch.delenv("FOLDER_POSTER_MATTING_STUB", raising=False)

    from PIL import Image
    import torch

    inp = tmp_path / "in.png"
    Image.new("RGB", (32, 32), color=(255, 0, 0)).save(inp)
    out = tmp_path / "out_matte.png"

    mock_model = MagicMock()
    logits = torch.full((1, 1, 32, 32), 20.0)
    mock_model.return_value = [logits]

    with patch("core.birefnet._load_model", return_value=(mock_model, "cpu")):
        from core.birefnet import MattingEngine

        eng = MattingEngine()
        eng.predict_matte(str(inp), str(out))

    assert out.is_file()
    im = Image.open(out)
    assert im.mode in ("RGBA", "RGB")


def test_stub_predict_matte_writes_rgba(tmp_path, monkeypatch):
    _ensure_project_core()
    monkeypatch.setenv("FOLDER_POSTER_MATTING_STUB", "1")

    from PIL import Image

    inp = tmp_path / "in.png"
    Image.new("RGB", (16, 16), color=(0, 128, 255)).save(inp)
    out = tmp_path / "stub_matte.png"

    from core.birefnet import MattingEngine

    MattingEngine().predict_matte(str(inp), str(out))

    assert out.is_file()
    im = Image.open(out)
    assert im.mode == "RGBA"
