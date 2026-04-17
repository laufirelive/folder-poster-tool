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


def test_predict_outputs_writes_matte_and_mask(tmp_path, monkeypatch):
    _ensure_project_core()
    monkeypatch.delenv("FOLDER_POSTER_MATTING_STUB", raising=False)

    from PIL import Image
    import torch

    inp = tmp_path / "in2.png"
    Image.new("RGB", (24, 20), color=(0, 255, 0)).save(inp)
    matte = tmp_path / "out_matte.png"
    mask = tmp_path / "out_mask.png"

    mock_model = MagicMock()
    logits = torch.full((1, 1, 32, 32), 12.0)
    mock_model.return_value = [logits]

    with patch("core.birefnet._load_model", return_value=(mock_model, "cpu")):
        from core.birefnet import MattingEngine

        eng = MattingEngine()
        eng.predict_outputs(str(inp), str(matte), str(mask))

    assert matte.is_file()
    assert mask.is_file()
    assert Image.open(matte).mode == "RGBA"
    assert Image.open(mask).mode == "L"


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


def test_stub_predict_outputs_writes_white_mask(tmp_path, monkeypatch):
    _ensure_project_core()
    monkeypatch.setenv("FOLDER_POSTER_MATTING_STUB", "1")

    from PIL import Image

    inp = tmp_path / "in3.png"
    Image.new("RGB", (6, 5), color=(0, 128, 255)).save(inp)
    matte = tmp_path / "stub_matte.png"
    mask = tmp_path / "stub_mask.png"

    from core.birefnet import MattingEngine

    MattingEngine().predict_outputs(str(inp), str(matte), str(mask))

    assert matte.is_file()
    assert mask.is_file()
    im_m = Image.open(mask)
    assert im_m.mode == "L"
    assert set(im_m.getdata()) == {255}


def test_load_model_uses_local_dir_and_local_files_only(monkeypatch):
    _ensure_project_core()
    monkeypatch.delenv("FOLDER_POSTER_MATTING_STUB", raising=False)

    calls = {}

    class DummyModel:
        def eval(self):
            return self

        def to(self, _device):
            return self

        def float(self):
            return self

    def fake_from_pretrained(path, **kwargs):
        calls["path"] = path
        calls["kwargs"] = kwargs
        return DummyModel()

    monkeypatch.setattr("core.birefnet._select_device", lambda: "cpu")
    monkeypatch.setattr("core.model_manager.ModelManager.ensure_installed", lambda self: "/tmp/fake_model")
    monkeypatch.setattr(
        "transformers.AutoModelForImageSegmentation.from_pretrained",
        fake_from_pretrained,
    )

    from core.birefnet import _load_model

    _model, device = _load_model()
    assert device == "cpu"
    assert calls["path"] == "/tmp/fake_model"
    assert calls["kwargs"]["local_files_only"] is True
