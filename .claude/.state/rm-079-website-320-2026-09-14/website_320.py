"""RM-079: Jede Website-Seite bei 320 px Breite laden und waagerechten Überlauf messen.

Messung, kein Test. Lädt jede HTML-Seite unter website/ in einer QtWebEngine-Ansicht
mit 320 Bildpunkten Breite und fragt das Dokument, ob es breiter ist als das Fenster —
und welches Element am weitesten nach rechts ragt.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("F:/3D Druck/website")
WIDTH = 320
HEIGHT = 640

JS = """
(function () {
  const w = document.documentElement.clientWidth;
  const sw = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0);
  let worst = null;
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0) continue;
    const over = r.right - w;
    if (over > 1 && (!worst || over > worst.over)) {
      worst = {over: Math.round(over), tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 60),
               text: (el.innerText || '').trim().slice(0, 60)};
    }
  }
  return JSON.stringify({clientWidth: w, scrollWidth: sw, worst: worst});
})()
"""

pages = sorted(p for p in ROOT.rglob("*.html") if "google" not in p.name)
app = QApplication.instance() or QApplication(sys.argv)
view = QWebEngineView()
view.resize(WIDTH, HEIGHT)
view.show()
results: list[dict] = []
index = 0


def load_next() -> None:
    global index
    if index >= len(pages):
        app.quit()
        return
    view.load(QUrl.fromLocalFile(str(pages[index])))


def loaded(_ok: bool) -> None:
    # Kurz warten, damit Schriften und Layout stehen.
    QTimer.singleShot(400, measure)


def measure() -> None:
    global index
    page = pages[index]

    def got(value: object) -> None:
        global index
        data = json.loads(value) if isinstance(value, str) else {"error": str(value)}
        data["page"] = str(page.relative_to(ROOT)).replace("\\", "/")
        results.append(data)
        print(json.dumps(data, ensure_ascii=False), flush=True)
        index += 1
        load_next()

    view.page().runJavaScript(JS, 0, got)


view.loadFinished.connect(loaded)
load_next()
app.exec()
wide = [r for r in results if r.get("scrollWidth", 0) > r.get("clientWidth", WIDTH) + 1]
print(f"\n{len(results)} Seiten gemessen, {len(wide)} breiter als das Fenster", flush=True)
