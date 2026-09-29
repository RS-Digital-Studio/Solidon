"""Sonde p22: Projektdatei öffnen — wie lange steht der Hauptfaden?

Drache einlesen (*Sofort laden*), als Projekt speichern, Startfläche, das
Projekt über ``open_path`` wieder öffnen; 5-ms-Takt. Dazu dieselbe Datei mit
einem um 5 s verzögerten Lesen (langsames Laufwerk)."""
import os, sys, time
from pathlib import Path
os.environ.setdefault("SONDE_FRIST", "900")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa
log = common.Log("p22_projekt_oeffnen.txt")
application, window = common.build()
from app.ui.dialogs import AskDialog


def handler(dialog):
    if isinstance(dialog, AskDialog):
        buttons = getattr(dialog, "_answers", [])
        (buttons[0] if buttons else dialog._accept).click()
        return True
    log("  DIALOG:", repr(dialog.windowTitle()))
    return False


dog = common.Watchdog(application, window, log, handler)
window.start()
MODEL = Path(sys.argv[1] if len(sys.argv) > 1 else r"F:\3D Dateien\Mausoleum Dragon.3mf")
window.open_path(MODEL)
common.pump(application, 0.3)
common.wait_until(application, lambda: not window.session.busy, 600)
target = Path(common._ISOLATED) / "projekt.p3d"
window.session.save_project(target)
log("gespeichert:", target.stat().st_size // 1_000_000, "MB")
import app.ui.session as session_module
real = session_module.load
for label, delay in (("normal", 0.0), ("normal", 0.0), ("langsam 5 s", 5.0)):
    def slow(path, delay=delay):
        time.sleep(delay)
        return real(path)
    session_module.load = slow
    window.session.start_new(window.settings.printer, window.settings.material)
    window._show_start_screen(True)
    common.wait_until(application, lambda: not window.session.busy, 30)
    meter = common.GapMeter(application)
    meter.start()
    begun = time.monotonic()
    window.open_path(target)
    returned = time.monotonic() - begun
    common.wait_until(application, lambda: not window.session.busy, 600)
    log(f"{label}: open_path kehrte nach {returned:.2f} s zurück, fertig nach {time.monotonic() - begun:.1f} s, längste Lücke {meter.stop() * 1000:.0f} ms")
session_module.load = real
log("Ende")
common.os._exit(0)
