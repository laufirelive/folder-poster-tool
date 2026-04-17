"""Tests for startup model gate behavior in MainWindow."""

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


def test_main_window_shows_download_page_when_model_missing(qapp, monkeypatch):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    monkeypatch.setattr("core.model_manager.ModelManager.is_installed", lambda self: False)

    from ui.main_window import MainWindow
    from ui.pages.model_download_page import ModelDownloadPage

    win = MainWindow()
    assert isinstance(win.stacked_widget.currentWidget(), ModelDownloadPage)


def test_main_window_unlocks_home_after_model_ready(qapp, monkeypatch):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    state = {"installed": False}
    monkeypatch.setattr("core.model_manager.ModelManager.is_installed", lambda self: state["installed"])

    from ui.main_window import MainWindow
    from ui.pages.model_download_page import ModelDownloadPage

    win = MainWindow()
    assert isinstance(win.stacked_widget.currentWidget(), ModelDownloadPage)

    state["installed"] = True
    win._on_model_download_ready()
    assert win.stacked_widget.currentWidget() is win.home_page


def test_cleanup_runtime_cache_removes_cache_and_project_artifacts(qapp, monkeypatch, tmp_path):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    monkeypatch.setattr("core.model_manager.ModelManager.is_installed", lambda self: True)

    from ui.main_window import MainWindow

    cache_dir = tmp_path / "cache"
    previews_dir = tmp_path / "temp" / "proj1" / "previews"
    mattes_dir = tmp_path / "temp" / "proj1" / "mattes"
    previews_dir.mkdir(parents=True, exist_ok=True)
    mattes_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "x.txt").parent.mkdir(parents=True, exist_ok=True)
    (cache_dir / "x.txt").write_text("x", encoding="utf-8")
    (previews_dir / "a.png").write_text("x", encoding="utf-8")
    (mattes_dir / "b.png").write_text("x", encoding="utf-8")

    win = MainWindow()
    win._cache_dir = str(cache_dir)
    win._state_manager.base_dir = str(tmp_path / "temp")
    win._cleanup_runtime_cache()

    assert not cache_dir.exists()
    assert not previews_dir.exists()
    assert not mattes_dir.exists()


def test_matting_success_stays_on_matting_until_manual_next(qapp, monkeypatch, tmp_path):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    monkeypatch.setattr("core.model_manager.ModelManager.is_installed", lambda self: True)

    from models import ProjectState
    from ui.main_window import MainWindow

    class _DummyMattingPage:
        def __init__(self):
            self.ready = None
            self.running = None
            self.failures = None

        def set_failures_present(self, has_failures):
            self.failures = has_failures

        def set_ready_for_next(self, ready):
            self.ready = ready

        def set_worker_running(self, running):
            self.running = running

    win = MainWindow()
    win._project_state = ProjectState(project_id="p", input_path=str(tmp_path), mode="image")
    win._matting_cancel_requested = False
    win._matting_any_failure = False
    win._matting_model_missing = False
    dummy = _DummyMattingPage()
    win._matting_page = dummy
    win._matting_records = []

    win._on_matting_worker_finished()

    assert win._project_state.current_step == "matting"
    assert dummy.ready is True
    assert dummy.running is False
