import os, sys
os.environ.pop("QT_QPA_PLATFORM", None)
from PySide6.QtWidgets import QApplication
app = QApplication([])
for s in app.screens():
    print(s.name(), s.manufacturer(), s.model(), s.geometry(), s.availableGeometry(), s.devicePixelRatio(), s.refreshRate(), "primär" if s == app.primaryScreen() else "")
