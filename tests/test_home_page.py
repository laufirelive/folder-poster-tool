"""Tests for home page UI behavior."""

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


def test_start_scan_disabled_when_path_empty(qapp):
    _root = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, _root)

    from ui.pages.home_page import HomePage

    page = HomePage(lambda *_: None)
    assert not page.start_btn.isEnabled()

    page.path_input.setText("/some/path")
    assert page.start_btn.isEnabled()

    page.path_input.clear()
    assert not page.start_btn.isEnabled()

    page.path_input.setText("   ")
    assert not page.start_btn.isEnabled()
