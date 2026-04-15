from PyQt6.QtCore import Qt
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
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Main container to center content
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                font-family: sans-serif;
                color: #333333;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
            QLineEdit:focus {
                border: 1px solid #007bff;
                background-color: #ffffff;
            }
            QPushButton {
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QSpinBox {
                padding: 8px;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(20)

        # Title
        title = QLabel("Folder Poster")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #007bff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)
        
        subtitle = QLabel("自动化批量视频/图片抠图与海报生成工具")
        subtitle.setStyleSheet("font-size: 14px; color: #666666;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(subtitle)
        container_layout.addSpacing(20)

        # Path Input
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请选择要扫描的文件夹路径...")
        browse_btn = QPushButton("浏览...")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        browse_btn.clicked.connect(self._browse_folder)
        container_layout.addLayout(path_layout)

        # Settings
        settings_layout = QHBoxLayout()
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_label = QLabel("处理模式:")
        mode_label.setStyleSheet("font-weight: bold;")
        mode_layout.addWidget(mode_label)
        self.video_radio = QRadioButton("视频提取 (截帧)")
        self.video_radio.setChecked(True)
        self.video_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_radio = QRadioButton("图片处理 (直接抠像)")
        self.image_radio.setCursor(Qt.CursorShape.PointingHandCursor)

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.video_radio)
        self.mode_group.addButton(self.image_radio)

        mode_layout.addWidget(self.video_radio)
        mode_layout.addWidget(self.image_radio)
        settings_layout.addLayout(mode_layout)

        settings_layout.addStretch()

        # Depth Selection
        depth_layout = QHBoxLayout()
        depth_label = QLabel("扫描深度:")
        depth_label.setStyleSheet("font-weight: bold;")
        depth_layout.addWidget(depth_label)
        self.depth_spinner = QSpinBox()
        self.depth_spinner.setRange(1, 10)
        self.depth_spinner.setValue(3)
        self.depth_spinner.setCursor(Qt.CursorShape.PointingHandCursor)
        depth_layout.addWidget(self.depth_spinner)
        depth_layout.addWidget(QLabel("层"))
        settings_layout.addLayout(depth_layout)

        container_layout.addLayout(settings_layout)
        container_layout.addSpacing(20)

        # Start Button
        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("font-size: 16px; padding: 15px;")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.on_start)
        self.path_input.textChanged.connect(self._update_start_button_enabled)
        container_layout.addWidget(self.start_btn)

        layout.addStretch()
        layout.addWidget(container)
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
