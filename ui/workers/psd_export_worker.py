"""PSD export in a background thread (pytoshop)."""

from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import QObject, pyqtSignal

from models import MatteRecord


class PsdExportWorker(QObject):
    finished_ok = pyqtSignal()
    finished_err = pyqtSignal(str)

    def __init__(
        self,
        matte_map: Iterable[MatteRecord],
        width: int,
        height: int,
        output_path: str,
    ) -> None:
        super().__init__()
        self._matte_map = matte_map
        self._width = width
        self._height = height
        self._output_path = output_path

    def run(self) -> None:
        try:
            from core.psd_export import export_matte_psd

            export_matte_psd(
                self._matte_map,
                self._width,
                self._height,
                self._output_path,
            )
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.finished_err.emit(str(exc))
        else:
            self.finished_ok.emit()
