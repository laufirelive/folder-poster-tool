"""Tests for model download page UI state changes."""

import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication


class _FakeManager:
    def __init__(self, installed=False):
        self._installed = installed

    def is_installed(self):
        return self._installed

    def get_model_dir(self):
        return "/tmp/fake-model-dir"

    def download_model(self, progress_cb=None):
        if progress_cb is not None:
            progress_cb(50, 100, "test.bin")
        self._installed = True


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_page_shows_download_button_when_missing(qapp):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    from ui.pages.model_download_page import ModelDownloadPage

    page = ModelDownloadPage(_FakeManager(installed=False))
    assert page._download_btn.isEnabled()
    assert "未检测到本地 BiRefNet 模型" in page._hint_label.text()


def test_progress_updates_status(qapp):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    from ui.pages.model_download_page import ModelDownloadPage

    page = ModelDownloadPage(_FakeManager(installed=False))
    page._on_progress(20, 100, "weights.bin")
    assert page._progress.value() == 20
    assert "20%" in page._status_label.text()


def test_error_reenables_download_button(qapp):
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)

    from ui.pages.model_download_page import ModelDownloadPage

    page = ModelDownloadPage(_FakeManager(installed=False))
    page._download_btn.setEnabled(False)
    page._on_download_err("network down")
    assert page._download_btn.isEnabled()
    assert "下载失败" in page._status_label.text()
