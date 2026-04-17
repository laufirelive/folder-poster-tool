from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_spec_file_exists_and_defines_folder_poster_executable() -> None:
    spec = ROOT / "folder-poster.spec"
    assert spec.is_file(), "folder-poster.spec must exist"
    text = spec.read_text(encoding="utf-8")
    assert 'name="Folder-Poster"' in text
    assert "Analysis(" in text
    assert 'collect_data_files("transformers"' in text


def test_workflow_exists_and_has_dual_platform_matrix() -> None:
    text = _read(".github/workflows/build.yml")
    assert "name: Build Portable Release" in text
    assert "push:" in text and "tags:" in text and '"v*"' in text
    assert "workflow_dispatch:" in text
    assert "windows-latest" in text
    assert "macos-14" in text
    assert "Folder-Poster-Windows" in text
    assert "Folder-Poster-macOS-ARM" in text


def test_workflow_has_release_and_windows_split_upload_logic() -> None:
    text = _read(".github/workflows/build.yml")
    assert "actions/upload-artifact@v4" in text
    assert "softprops/action-gh-release@v2" in text
    assert "7z a -tzip -v1900m" in text
    assert "zip -r" in text
