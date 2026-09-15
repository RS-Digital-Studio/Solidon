"""RM-079, dritter Schritt: Welche Elemente tragen inneren Überlauf bei 320 px?

Listet je Seite alle Elemente, deren scrollWidth den clientWidth übersteigt
(also Inhalt breiter als das Element), mit overflow-x, Breite, Klasse und
den ::before/::after-Pseudoelementen, die absolut stehen.
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
PAGES = sys.argv[1:] or ["index.html", "agb.html", "widerruf.html"]
WIDTH, HEIGHT = 320, 640

JS = """
(function () {
  const doc = document.documentElement;
  const w = doc.clientWidth;
  const label = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '');
  const rows = [];
  for (const el of document.querySelectorAll('h1, h2, h3, h4, p, li, td, th, a, span, code, dt, dd, summary, button')) {
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && getComputedStyle(el).overflowX === 'visible') {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      rows.push({el: label(el), over: el.scrollWidth - el.clientWidth, right: Math.round(r.right), font: s.fontSize,
                 wrap: s.overflowWrap, hyphens: s.hyphens, text: (el.innerText || '').trim().slice(0, 50)});
    }
  }
  rows.sort((a, b) => b.over - a.over);
  const outside = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if ((r.left < -1 || r.right > w + 1) && r.width > 0) {
      const s = getComputedStyle(el);
      outside.push({el: label(el), parent: label(el.parentElement), left: Math.round(r.left), right: Math.round(r.right),
                    pos: s.position, vis: s.visibility, disp: s.display, text: (el.innerText || '').trim().slice(0, 30)});
    }
  }
  return JSON.stringify({clientWidth: w, lang: doc.lang, rows: rows.slice(0, 8), outside: outside.slice(0, 4)});
})()
"""

app = QApplication.instance() or QApplication(sys.argv)
view = QWebEngineView()
view.resize(WIDTH, HEIGHT)
view.show()
index = 0


def load_next() -> None:
    if index >= len(PAGES):
        app.quit()
        return
    view.load(QUrl.fromLocalFile(str(ROOT / PAGES[index])))


def loaded(ok: bool) -> None:
    del ok
    QTimer.singleShot(400, measure)


def measure() -> None:
    page = PAGES[index]

    def got(value: object) -> None:
        global index
        data = json.loads(value) if isinstance(value, str) else {"error": str(value)}
        data["page"] = page
        print("RESULT " + json.dumps(data, ensure_ascii=False), flush=True)
        index += 1
        load_next()

    view.page().runJavaScript(JS, 0, got)


view.loadFinished.connect(loaded)
load_next()
app.exec()
