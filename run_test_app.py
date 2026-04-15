import sys
import faulthandler
faulthandler.enable()

def my_excepthook(type, value, tback):
    import traceback
    sys.__excepthook__(type, value, tback)
    traceback.print_exception(type, value, tback)

sys.excepthook = my_excepthook

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from pathlib import Path

app = QApplication(sys.argv)
win = MainWindow()
win.show()

p = Path("dummy.jpg")
p.touch()

import time
from PyQt6.QtCore import QTimer

def simulate():
    print("Starting simulation")
    win.handle_start_scan(".", "image", 3)
    
    if not win._project_state:
        print("No project state")
        return
        
    sf = win._project_state.scanned_files[0]
    win._on_image_toggle(sf.source_id, True)
    
    print("Clicking next")
    try:
        win._on_materials_next()
        print("Next clicked successfully")
    except Exception as e:
        print("Exception:", e)

QTimer.singleShot(1000, simulate)
sys.exit(app.exec())
