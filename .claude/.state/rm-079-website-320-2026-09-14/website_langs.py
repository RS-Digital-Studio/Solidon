"""RM-079: Wo liegt die Sprachliste bei schmalen Breiten — und wohin öffnet sie sich?

Öffnet ``details.langs`` per Skript und misst die Lage von Navigation, Griff
und Liste bei mehreren Fensterbreiten; danach dieselbe Messung mit einer
eingespritzten Regel (Kandidat für die Behebung), damit die Wahl gemessen ist.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --log-level=3")

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ROOT = Path("F:/3D Druck/website")
PAGE = sys.argv[1] if len(sys.argv) > 1 else "index.html"
WIDTHS = (320, 360, 414, 600, 800, 890, 1000)
OVERRIDE = sys.argv[2] if len(sys.argv) > 2 else ""

JS = """
(function (override) {
  const rect = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; };
  const w = document.documentElement.clientWidth;
  const nav = document.querySelector('nav.lang');
  const d = document.querySelector('nav.lang details.langs');
  const ul = d.querySelector('ul');
  d.open = true;
  const before = {nav: rect(nav), details: rect(d), list: rect(ul)};
  let after = null;
  if (override) {
    const s = document.createElement('style'); s.textContent = override; document.head.appendChild(s);
    after = {list: rect(ul)};
    s.remove();
  }
  d.open = false;
  return JSON.stringify({clientWidth: w, before, after});
})(%s)
"""

app = QApplication.instance() or QApplication(sys.argv)
view = QWebEngineView()
step = 0


def load() -> None:
    view.resize(WIDTHS[step], 700)
    view.show()
    view.load(QUrl.fromLocalFile(str(ROOT / PAGE)))


def loaded(ok: bool) -> None:
    del ok
    QTimer.singleShot(400, measure)


def measure() -> None:
    def got(value: object) -> None:
        global step
        data = json.loads(value) if isinstance(value, str) else {"error": str(value)}
        data["width"] = WIDTHS[step]
        print("RESULT " + json.dumps(data, ensure_ascii=False), flush=True)
        step += 1
        if step >= len(WIDTHS):
            app.quit()
            return
        load()

    view.page().runJavaScript(JS % json.dumps(OVERRIDE), 0, got)


view.loadFinished.connect(loaded)
load()
app.exec()
