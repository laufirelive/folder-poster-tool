"""Tests for async scanner worker."""

import sys
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


def _ensure_project_core():
    bad = sys.modules.get("core")
    if bad is not None:
        f = (getattr(bad, "__file__", "") or "").replace("\\", "/")
        if f.endswith("/tests/core/__init__.py") or "/tests/core/" in f:
            del sys.modules["core"]
            for k in list(sys.modules):
                if k.startswith("core."):
                    del sys.modules[k]


@pytest.fixture(autouse=True)
def _path():
    sys.path.insert(0, _ROOT)
    _ensure_project_core()
    yield


def test_scanner_worker_emits_finished_ok(tmp_path, qapp):
    from ui.workers.scanner_worker import ScannerWorker

    (tmp_path / "a.jpg").write_bytes(b"")
    w = ScannerWorker(str(tmp_path), "image", 3)

    got_batches: list[list] = []
    got_done: list[tuple] = []
    w.batch_ready.connect(lambda batch: got_batches.append(batch))
    w.finished_ok.connect(lambda path, mode, depth, total: got_done.append((path, mode, depth, total)))
    w.run()

    assert len(got_done) == 1
    path, mode, depth, total = got_done[0]
    assert path == str(tmp_path)
    assert mode == "image"
    assert depth == 3
    assert total == 1
    assert len(got_batches) == 1
    assert len(got_batches[0]) == 1
