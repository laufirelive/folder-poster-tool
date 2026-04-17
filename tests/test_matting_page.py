"""Tests for matting page retry UI."""

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


@pytest.fixture(autouse=True)
def _path():
    sys.path.insert(0, _ROOT)
    yield


def test_retry_button_hidden_until_failures(qapp, tmp_path):
    from models import ProjectState
    from ui.pages.matting_page import MattingPage, MattingRowStatus

    state = ProjectState(project_id="p", input_path=str(tmp_path), mode="image")
    sample = tmp_path / "s.png"
    from PIL import Image

    Image.new("RGB", (8, 8), (1, 1, 1)).save(sample)
    specs = [("a", str(sample), ("src", None))]

    page = MattingPage(state, specs)
    page.show()
    assert not page.retry_failed_button.isVisible()

    page.set_row_status(0, MattingRowStatus.ERROR)
    page.set_failures_present(True)
    assert page.retry_failed_button.isVisible()
    assert page.retry_failed_button.isEnabled()


def test_retry_all_failed_signal_emitted(qapp, tmp_path):
    from models import ProjectState
    from ui.pages.matting_page import MattingPage, MattingRowStatus

    state = ProjectState(project_id="p", input_path=str(tmp_path), mode="image")
    sample = tmp_path / "s2.png"
    from PIL import Image

    Image.new("RGB", (8, 8), (2, 2, 2)).save(sample)
    specs = [("a", str(sample), ("src", None))]

    page = MattingPage(state, specs)
    received: list[object] = []
    page.retry_all_failed_requested.connect(lambda: received.append(True))

    page.set_failures_present(True)
    page.retry_failed_button.click()
    assert received == [True]


def test_back_signal_and_worker_running_toggle(qapp, tmp_path):
    from models import ProjectState
    from ui.pages.matting_page import MattingPage

    state = ProjectState(project_id="p", input_path=str(tmp_path), mode="image")
    sample = tmp_path / "s3.png"
    from PIL import Image

    Image.new("RGB", (8, 8), (2, 2, 2)).save(sample)
    page = MattingPage(state, [("a", str(sample), ("src", None))])

    got_back: list[bool] = []
    page.back_requested.connect(lambda: got_back.append(True))
    page._back_btn.click()
    assert got_back == [True]

    page.set_worker_running(True)
    assert page._stop_btn.isEnabled()
    assert not page._back_btn.isEnabled()

    page.set_worker_running(False)
    assert not page._stop_btn.isEnabled()
    assert page._back_btn.isEnabled()


def test_next_button_hidden_until_ready_and_emits_signal(qapp, tmp_path):
    from models import ProjectState
    from ui.pages.matting_page import MattingPage

    state = ProjectState(project_id="p", input_path=str(tmp_path), mode="image")
    sample = tmp_path / "s4.png"
    from PIL import Image

    Image.new("RGB", (8, 8), (2, 2, 2)).save(sample)
    page = MattingPage(state, [("a", str(sample), ("src", None))])

    got_next: list[bool] = []
    page.next_requested.connect(lambda: got_next.append(True))

    assert page._next_btn.isHidden()
    page.set_ready_for_next(True)
    assert not page._next_btn.isHidden()
    assert page._next_btn.isEnabled()
    page._next_btn.click()
    assert got_next == [True]
