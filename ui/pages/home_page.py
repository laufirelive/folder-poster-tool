from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QRadioButton, QSpinBox,
                             QHBoxLayout, QButtonGroup, QFileDialog)


class HomePage(QWidget):
    def __init__(self, start_callback):
        super().__init__()
        self.start_callback = start_callback
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Folder Poster")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Path Input
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("文件夹路径")
        browse_btn = QPushButton("浏览")
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        browse_btn.clicked.connect(self._browse_folder)
        layout.addLayout(path_layout)

        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("模式:"))
        self.video_radio = QRadioButton("视频模式")
        self.video_radio.setChecked(True)
        self.image_radio = QRadioButton("图片模式")

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.video_radio)
        self.mode_group.addButton(self.image_radio)

        mode_layout.addWidget(self.video_radio)
        mode_layout.addWidget(self.image_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Depth Selection
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("递归深度:"))
        self.depth_spinner = QSpinBox()
        self.depth_spinner.setRange(1, 10)
        self.depth_spinner.setValue(3)
        depth_layout.addWidget(self.depth_spinner)
        depth_layout.addWidget(QLabel("层 (1-10)"))
        depth_layout.addStretch()
        layout.addLayout(depth_layout)

        # Start Button
        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.on_start)
        self.path_input.textChanged.connect(self._update_start_button_enabled)
        layout.addWidget(self.start_btn)

        layout.addStretch()

    def _update_start_button_enabled(self, _text: str) -> None:
        self.start_btn.setEnabled(bool(self.path_input.text().strip()))

    def _browse_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            self.path_input.setText(d)

    def on_start(self):
        path = self.path_input.text()
        mode = "video" if self.video_radio.isChecked() else "image"
        depth = self.depth_spinner.value()
        self.start_callback(path, mode, depth)
