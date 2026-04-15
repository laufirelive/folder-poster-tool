"""Tests for matting worker cache skip and row_done ordering."""

import sys
import threading
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


_ROOT = str(Path(__file__).resolve().parents[1])


@pytest.fixture(autouse=True)
def _path():
    sys.path.insert(0, _ROOT)
    yield


def test_matting_worker_skips_model_when_cache_valid(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("FOLDER_POSTER_MATTING_STUB", "1")

    from PIL import Image
    from models import Material, MatteRecord
    from ui.workers.matting_worker import MattingWorker

    src = tmp_path / "in.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(src)
    mtime = src.stat().st_mtime

    existing_matte = tmp_path / "cached.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(existing_matte)

    matte_map = [
        MatteRecord(
            source_id="m1",
            source_mtime=mtime,
            matte_path=str(existing_matte),
            is_active=True,
        )
    ]

    mat = Material(source_id="m1", frame_idx=None, selected=True)
    rows = [("file1", str(src), mat)]

    worker = MattingWorker(rows, str(tmp_path), "proj1", threading.Event(), matte_map)
    calls: list[None] = []

    def spy_predict(self_, inp, outp):
        calls.append(None)
        return __import__("core.birefnet", fromlist=["MattingEngine"]).MattingEngine.predict_matte(
            self_, inp, outp
        )

    monkeypatch.setattr("core.birefnet.MattingEngine.predict_matte", spy_predict)

    done: list[tuple] = []
    worker.row_done.connect(lambda *a: done.append(tuple(a)))

    worker.run()

    assert calls == []
    assert len(done) == 1
    idx, path, ok, err = done[0]
    assert (idx, ok, err) == (0, True, "")
    assert Path(path).resolve() == Path(str(existing_matte)).resolve()


def test_matting_worker_runs_model_when_cache_missing(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("FOLDER_POSTER_MATTING_STUB", "1")

    from PIL import Image
    from models import Material
    from ui.workers.matting_worker import MattingWorker

    src = tmp_path / "in2.png"
    Image.new("RGB", (4, 4), (9, 9, 9)).save(src)
    mat = Material(source_id="m2", frame_idx=None, selected=True)
    rows = [("n", str(src), mat)]

    worker = MattingWorker(rows, str(tmp_path), "proj2", threading.Event(), [])
    predicts = {"n": 0}
    real = __import__("core.birefnet", fromlist=["MattingEngine"]).MattingEngine.predict_matte

    def counting_pred(self_, inp, out):
        predicts["n"] += 1
        return real(self_, inp, out)

    monkeypatch.setattr("core.birefnet.MattingEngine.predict_matte", counting_pred)

    worker.run()
    assert predicts["n"] == 1
