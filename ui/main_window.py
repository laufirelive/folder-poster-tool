from PyQt6.QtWidgets import QMainWindow, QStackedWidget
from ui.pages.home_page import HomePage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Poster")
        self.resize(800, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_page = HomePage(self.handle_start_scan)
        self.stacked_widget.addWidget(self.home_page)

    def handle_start_scan(self, path, mode, depth):
        print(f"Scanning: {path}, Mode: {mode}, Depth: {depth}")
        # In a later task, we'll scan files and transition to MaterialPage
