import sys
import re

with open("ui/main_window.py", "r", encoding="utf-8") as f:
    content = f.read()

replacement = """    def _on_video_pick(self, source_id: str) -> None:
        if self._project_state is None:
            return
        sf = next((f for f in self._project_state.scanned_files if f.source_id == source_id), None)
        if sf is None:
            return

        out_dir = os.path.join(
            self._state_manager.base_dir,
            self._project_state.project_id,
            "previews",
            source_id,
        )

        import glob
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt

        existing_frames = sorted(glob.glob(os.path.join(out_dir, "frame_*.png")))
        if len(existing_frames) == 32:
            self._show_video_frames_modal(sf, source_id, out_dir, existing_frames)
            return

        progress = QProgressDialog("正在提取视频预览帧，请稍候...", "取消", 0, 0, self)
        progress.setWindowTitle("处理中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        from ui.workers.extractor_worker import ExtractorWorker
        self._extractor_thread = QThread()
        self._extractor_worker = ExtractorWorker(sf.path, out_dir, 32)
        self._extractor_worker.moveToThread(self._extractor_thread)

        def on_ok(paths):
            progress.close()
            self._extractor_thread.quit()
            self._extractor_thread.wait()
            self._show_video_frames_modal(sf, source_id, out_dir, paths)

        def on_err(err):
            progress.close()
            self._extractor_thread.quit()
            self._extractor_thread.wait()
            QMessageBox.warning(self, "提取失败", err)

        self._extractor_worker.finished_ok.connect(on_ok)
        self._extractor_worker.finished_err.connect(on_err)
        self._extractor_thread.started.connect(self._extractor_worker.run)
        
        # Prevent GC
        self._extractor_progress = progress

        self._extractor_thread.start()

    def _show_video_frames_modal(self, sf, source_id, out_dir, paths) -> None:
        pm = QPixmap(paths[0])
        if self._materials_page is not None and not pm.isNull():
            self._materials_page.set_video_thumbnail(source_id, pm)

        initial_selected_indices = sorted(
            m.frame_idx
            for m in self._project_state.selected_materials
            if m.selected
            and m.frame_idx is not None
            and scanned_file_source_id_for_material(m) == source_id
        )

        modal = VideoFramesModal(
            paths,
            sf.path,
            out_dir,
            initial_selected_indices=initial_selected_indices,
            parent=self,
        )
        if modal.exec() != QDialog.DialogCode.Accepted:
            return

        indices = modal.selected_frame_indices()
        mats = [
            m
            for m in self._project_state.selected_materials
            if scanned_file_source_id_for_material(m) != source_id
        ]
        for idx in sorted(indices):
            mats.append(
                Material(
                    source_id=material_source_id_for_video(source_id, idx),
                    frame_idx=idx,
                    selected=True,
                )
            )
        self._project_state.selected_materials = mats
        self._state_manager.save_state(self._project_state)
        if self._materials_page is not None:
            self._materials_page.set_state(self._project_state)
"""

pattern = r"    def _on_video_pick\(self, source_id: str\) -> None:.*?        if self\._materials_page is not None:\n            self\._materials_page\.set_state\(self\._project_state\)\n"

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open("ui/main_window.py", "w", encoding="utf-8") as f:
    f.write(new_content)
