"""Der Sprachhinweis der deutschen Startseite, ausgeführt in einer Browsermaschine.

``test_website.py`` liest Vorlage, Skript und Stylesheet als Text. Ob der
Block das Versprochene tut — wem er welche Fassung zeigt, wann er schweigt,
was er sich merkt, wohin der Fokus nach dem Schließen geht und dass er unten
Platz freihält —, zeigt erst der Lauf: Im Review blieben die Texttests grün,
als niemand mehr einen Hinweis bekam, als auch Deutschsprachige einen
bekamen und als der Wechsel aus ``/en/`` nicht mehr zählte.

Chromium bringt PySide6 als QtWebEngine schon mit. Es läuft in einem
Kindprozess — diese Datei als Modul gestartet, unten ``_probe`` — gegen die
Seiten aus ``website/`` auf der Rückschleife, ein Profil je Fall, in einer
offscreen gezeigten Ansicht: Ohne sie hätte die Seite null mal null Pixel.
Ein eigener Prozess, weil Chromium seine Hilfsprozesse mitbringt und
QtWebEngine nicht in die Anwendung der Suite gehört. Fenster und Renderer:
Die Datei läuft wie deren übrige Fälle beim Release (``AGENTS.md``,
„Arbeitsweise“).
"""

from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.helpers import LoopbackServer

if TYPE_CHECKING:
    from PySide6.QtWebEngineCore import QWebEnginePage

pytestmark = [pytest.mark.windowed, pytest.mark.rendering]

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"

#: Was ein Fall von der Seite wissen will — als Text, denn ``runJavaScript``
#: gibt ein Objekt als leere Zeichenkette zurück.
STATE = """JSON.stringify((() => {
  const hint = document.querySelector("body > .language-hint");
  const header = document.querySelector("header.site");
  let stored = null;
  try {
    stored = localStorage.getItem("solidon3d.language-hint");
  } catch (e) {
    stored = "gesperrt";
  }
  const root = getComputedStyle(document.documentElement);
  return {
    hint: hint ? hint.lang : "",
    position: hint ? getComputedStyle(hint).position : "",
    // Layoutlage statt Bildlage: Die Einblendung verschiebt die Karte kurz.
    above_header: hint ? hint.offsetTop + hint.offsetHeight <= header.offsetTop : null,
    height: hint ? hint.offsetHeight : 0,
    space: root.getPropertyValue("--language-hint-space").trim(),
    padding: getComputedStyle(document.body).paddingBottom,
    stored,
    focus: document.activeElement ? document.activeElement.className : "",
  };
})())"""

#: Ganz nach unten gerollt: Wie viele Verweise der Fußzeile liegen unter der Karte?
FOOTER_UNDER_HINT = """(() => {
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
  const hint = document.querySelector("body > .language-hint").getBoundingClientRect();
  return [...document.querySelectorAll("footer.site a")].filter((link) => {
    const box = link.getBoundingClientRect();
    return box.bottom > hint.top && box.top < hint.bottom
      && box.right > hint.left && box.left < hint.right;
  }).length;
})()"""

#: Von oben her auf einen Verweis der Fußzeile, wie mit der Tabulatortaste:
#: Sie rollt ein Ziel nur bis an den Rand in den Blick und hält dabei
#: ``scroll-padding-bottom`` ein — ``scrollIntoView`` mit ``nearest`` tut
#: dasselbe. ``focus()`` allein zentriert in Chromium und prüfte die Regel
#: nicht. Steht der Verweis danach ganz über der Karte? Gemessen wird ihre
#: Layoutlage, denn die Einblendung verschiebt sie kurz.
FOCUS_ABOVE_HINT = """(() => {
  document.documentElement.style.scrollBehavior = "auto";
  window.scrollTo(0, 0);
  const link = document.querySelector('footer.site a[href="/datenschutz.html"]');
  link.scrollIntoView({ block: "nearest" });
  link.focus({ preventScroll: true });
  const hint = document.querySelector("body > .language-hint");
  const top = innerHeight - parseFloat(getComputedStyle(hint).bottom) - hint.offsetHeight;
  const box = link.getBoundingClientRect();
  return document.activeElement === link && box.top >= 0 && box.bottom <= top;
})()"""

ESCAPE = """(() => {
  const link = document.querySelector("body > .language-hint .btn");
  link.focus();
  link.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  return "ok";
})()"""

CROSS = """(() => {
  document.querySelector("body > .language-hint .language-hint-close").click();
  return "ok";
})()"""

DESKTOP = (1280, 800)

#: Je Fall: Browsersprachen, Fenstergröße, Schritte.
CASES: dict[str, dict] = {
    "en-vor-de": {"accept": "en-US,de", "steps": [["open", "/"], ["eval", STATE]]},
    "de-vorn": {"accept": "de-DE,en", "steps": [["open", "/"], ["eval", STATE]]},
    "ja-de": {"accept": "ja,de", "steps": [["open", "/"], ["eval", STATE]]},
    "ja": {"accept": "ja", "steps": [["open", "/"], ["eval", STATE]]},
    "es-419": {"accept": "es-419,es", "steps": [["open", "/"], ["eval", STATE]]},
    "fr-ch": {"accept": "fr-CH,fr", "steps": [["open", "/"], ["eval", STATE]]},
    "it": {"accept": "it-IT", "steps": [["open", "/"], ["eval", STATE]]},
    "pt-br": {"accept": "pt-BR", "steps": [["open", "/"], ["eval", STATE]]},
    "wechsel-aus-en": {
        "accept": "ja",
        "steps": [
            ["open", "/en/"],
            ["follow", "/"],
            ["eval", STATE],
            ["follow", "/funktionen.html"],
            ["follow", "/"],
            ["eval", STATE],
        ],
    },
    "unterseite-ist-keine-wahl": {
        "accept": "ja",
        "steps": [["open", "/funktionen.html"], ["follow", "/"], ["eval", STATE]],
    },
    "escape": {
        "accept": "ja",
        "steps": [["open", "/"], ["eval", ESCAPE], ["eval", STATE], ["open", "/"], ["eval", STATE]],
    },
    "kreuz": {
        "accept": "ja",
        "steps": [["open", "/"], ["eval", CROSS], ["eval", STATE], ["open", "/"], ["eval", STATE]],
    },
    "telefon": {
        "accept": "ja",
        "size": (390, 664),
        "steps": [
            ["open", "/"],
            ["eval", STATE],
            ["eval", FOOTER_UNDER_HINT],
            ["eval", FOCUS_ABOVE_HINT],
        ],
    },
    "wenig-hoehe": {"accept": "ja", "size": (683, 384), "steps": [["open", "/"], ["eval", STATE]]},
}


class _Website(socketserver.ThreadingMixIn, LoopbackServer):
    daemon_threads = True


class _Pages(http.server.SimpleHTTPRequestHandler):
    """Liefert ``website/`` aus; der Zählruf geht ins Leere, und das ist recht."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEBSITE), **kwargs)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@pytest.fixture(scope="module")
def outcomes() -> Iterator[dict[str, list]]:
    """Alle Fälle in einem Kindprozess — Chromium startet einmal."""
    server = _Website(("127.0.0.1", 0), _Pages)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cases = {
            name: {**case, "size": list(case.get("size", DESKTOP))} for name, case in CASES.items()
        }
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                f"tests.{Path(__file__).stem}",
                f"http://127.0.0.1:{server.server_port}",
            ],
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert run.returncode == 0, run.stderr[-3000:]
    results = json.loads(run.stdout.strip().splitlines()[-1])
    assert results.keys() == CASES.keys()
    values = {}
    for name, result in results.items():
        assert not result["failed"], f"{name}: hängen geblieben bei {result['failed']}"
        values[name] = [
            json.loads(value) if isinstance(value, str) and value.startswith(("{", "[")) else value
            for value in result["values"]
        ]
    yield values


@pytest.mark.parametrize(
    ("case", "language"),
    [
        ("en-vor-de", "en"),
        ("ja", "en"),
        ("es-419", "es"),
        ("fr-ch", "fr"),
        ("it", "it"),
        ("pt-br", "pt"),
        ("de-vorn", ""),
        ("ja-de", ""),
    ],
)
def test_the_hint_speaks_the_first_offered_language_or_english(
    outcomes: dict[str, list], case: str, language: str
) -> None:
    """Die Browsersprachen gelten in ihrer Reihenfolge, wie ``Accept-Language``:
    Die erste Sprache, die es hier gibt, entscheidet; Deutsch vorn heißt kein
    Hinweis, und wer keine der Sprachen spricht, bekommt Englisch."""
    state = outcomes[case][0]
    assert state["hint"] == language
    assert state["stored"] is None, "nur Ansehen legt nichts ab"


def test_switching_from_another_version_chooses_german_for_good(
    outcomes: dict[str, list],
) -> None:
    """Wer aus ``/en/`` nach ``/`` wechselt, hat Deutsch gewählt — auch für den
    nächsten Aufruf der Startseite über eine Unterseite."""
    after_switch, after_detour = outcomes["wechsel-aus-en"]
    assert (after_switch["hint"], after_switch["stored"]) == ("", "de")
    assert after_detour["hint"] == ""


def test_a_german_subpage_is_not_a_choice(outcomes: dict[str, list]) -> None:
    """Von einer deutschen Unterseite kommt, wer die Sprache nie gewählt hat."""
    (state,) = outcomes["unterseite-ist-keine-wahl"]
    assert (state["hint"], state["stored"]) == ("en", None)


@pytest.mark.parametrize("case", ["escape", "kreuz"])
def test_closing_is_remembered_and_frees_the_space(outcomes: dict[str, list], case: str) -> None:
    """Escape im Hinweis und das Kreuz schließen ihn für dieses und das nächste
    Mal, und der freigehaltene Platz unten geht mit. Nach Escape steht der
    Fokus am Zeichen der Kopfzeile statt im Nichts."""
    _done, closed, reloaded = outcomes[case]
    assert (closed["hint"], closed["stored"], closed["space"]) == ("", "closed", "0px")
    if case == "escape":
        assert closed["focus"] == "brand"
    assert reloaded["hint"] == ""


@pytest.mark.parametrize("case", ["ja", "telefon"])
def test_the_fixed_card_keeps_its_space_free(outcomes: dict[str, list], case: str) -> None:
    """Steht die Karte unten fest, hält die Seite mindestens ihre Höhe frei:
    Kein Verweis der Fußzeile bleibt am Seitenende unter ihr liegen, und was
    den Fokus bekommt, rollt über ihr in den Blick (WCAG 2.4.11)."""
    state = outcomes[case][0]
    assert state["position"] == "fixed"
    assert int(state["space"].removesuffix("px")) >= state["height"] > 0
    # Der Polster selbst, nicht nur die Variable: Unter Chromium auf macOS
    # blieb er über ``var()`` bei 0px stehen (CI-Probe 38855455034).
    assert state["padding"] == state["space"], state
    if case == "telefon":
        _state, under_hint, focused_above = outcomes[case]
        assert under_hint == 0, "Fußverweise am Seitenende unter der Karte"
        assert focused_above is True, "der fokussierte Fußverweis liegt unter der Karte"


def test_with_little_height_the_card_flows_above_the_header(outcomes: dict[str, list]) -> None:
    """Bei 200 % auf einem kleinen Laptop bliebe neben Kopfzeile und fester
    Karte kaum Seite: Dort steht die Karte im Fluss über der Kopfzeile, und
    unten wird nichts freigehalten."""
    (state,) = outcomes["wenig-hoehe"]
    assert (state["hint"], state["position"], state["above_header"]) == ("en", "static", True)
    assert state["space"] == "0px"


# --- Der Kindprozess --------------------------------------------------------
#
# Fälle kommen als JSON über stdin: je Fall Browsersprachen, Fenstergröße und
# Schritte — ``["open", pfad]`` lädt, ``["follow", pfad]`` navigiert per
# ``location.href`` mit Verweis wie ein Klick, ``["eval", skript]`` hält den
# Wert eines Skripts fest. Ausgegeben wird je Fall die Liste dieser Werte oder
# der Schritt, an dem er hängen blieb.

#: Wie lange eine Seite zum Laden hat. Lokal braucht die Startseite unter
#: einer Sekunde; die Grenze fängt nur einen Hänger.
LOAD_LIMIT_MS = 30_000
SCRIPT_LIMIT_MS = 10_000


def _loaded(page: QWebEnginePage, start: Callable[[], object]) -> bool:
    """Startet eine Navigation und wartet, bis sie fertig geladen ist."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    result: list[bool] = []

    def finished(ok: bool) -> None:
        result.append(ok)
        loop.quit()

    page.loadFinished.connect(finished)
    start()
    QTimer.singleShot(LOAD_LIMIT_MS, loop.quit)
    loop.exec()
    page.loadFinished.disconnect(finished)
    return bool(result) and result[0]


def _evaluated(page: QWebEnginePage, script: str) -> object:
    """Der Wert eines Skripts — ``None``, wenn es nicht antwortet."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    value: list[object] = []

    def answered(result: object) -> None:
        value.append(result)
        loop.quit()

    page.runJavaScript(script, 0, answered)
    QTimer.singleShot(SCRIPT_LIMIT_MS, loop.quit)
    loop.exec()
    return value[0] if value else None


def _run_case(base: str, case: dict[str, Any]) -> dict[str, Any]:
    """Ein Fall in eigenem Profil ohne Ablage auf der Platte: leerer Speicher."""
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView

    profile = QWebEngineProfile()
    profile.setHttpAcceptLanguage(case["accept"])
    view = QWebEngineView()
    page = QWebEnginePage(profile, view)
    view.setPage(page)
    width, height = case["size"]
    view.resize(width, height)
    view.show()
    values: list[object] = []
    failed = ""
    for operation, argument in case["steps"]:
        if operation == "open":
            ok = _loaded(page, partial(page.load, QUrl(base + argument)))
        elif operation == "follow":
            ok = _loaded(
                page, partial(page.runJavaScript, f"location.href = {json.dumps(argument)};")
            )
        else:
            values.append(_evaluated(page, argument))
            ok = True
        if not ok:
            failed = f"{operation} {argument}"
            break
    view.close()
    view.deleteLater()
    profile.deleteLater()
    return {"values": values, "failed": failed}


def _probe(base: str) -> int:
    """Fährt alle Fälle von stdin und schreibt ihre Werte als eine JSON-Zeile."""
    import os

    # Chromium sucht sonst einen GPU-Kontext, den es offscreen nicht bekommt,
    # und meldet das in jeder Zeile; gerechnet wird ohnehin in Software.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
    # Ubuntu 24.04 sperrt per AppArmor die Namensräume, auf die Chromiums
    # Sandkasten baut, und QtWebEngine hat keinen Ersatzweg. Geladen wird nur
    # die eigene Seite von der Rückschleife, kein fremder Inhalt.
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    from PySide6.QtWidgets import QApplication

    cases = json.loads(sys.stdin.read())
    app = QApplication.instance() or QApplication([])
    results = {name: _run_case(base, case) for name, case in cases.items()}
    app.processEvents()
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(_probe(sys.argv[1]))
