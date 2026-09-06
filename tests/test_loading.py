"""Die Ladeanzeige und ihre Wartezeitauskunft (§2.8, §19.3).

Bauplan §2.8 staffelt die Anzeige nach Dauer, und die letzte Stufe war nie
gebaut: „über 10 s zusätzlich eine Schätzung, wenn möglich". Prozent sagt, wie
weit ein Lauf ist — nicht, wie lange man noch wartet, und genau das ist die
Frage, die jemand vor einem Fortschrittsbalken hat.

Geprüft wird über die Startzeit von Hand, nicht über echtes Warten: Ein Test,
der zehn Sekunden schläft, prüft die Uhr und nicht das Verhalten.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.i18n import tr
from app.ui import app as app_module
from app.ui.loading import ESTIMATE_AFTER_S, ESTIMATE_FROM, LoadingVeil


def _running(veil: LoadingVeil, seconds: float) -> None:
    """Tut so, als liefe der Lauf schon so lange."""
    veil._started = time.monotonic() - seconds


def test_the_first_seconds_get_no_estimate(qt_app: QApplication) -> None:
    """Der Anfang eines Laufs sagt wenig über seinen Rest.

    Eine Zahl, die erst „noch 40 Sekunden" und dann „noch zwei Minuten" sagt,
    ist schlechter als keine — deshalb schweigt sie, bis sie etwas weiß.
    """
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, ESTIMATE_AFTER_S - 2.0)
        veil.step(0.5, "rechnet")

        assert veil.remaining() == ""
    finally:
        veil.deleteLater()


def test_a_run_that_has_barely_started_gets_no_estimate(qt_app: QApplication) -> None:
    """Bei drei Prozent ist der Hochrechnungsfehler größer als die Aussage."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 60.0)
        veil.step(ESTIMATE_FROM / 2, "rechnet")

        assert veil.remaining() == ""
    finally:
        veil.deleteLater()


def test_the_estimate_follows_what_already_passed(qt_app: QApplication) -> None:
    """Dreißig Sekunden für die Hälfte heißt dreißig Sekunden für den Rest."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.5, "rechnet")

        assert veil.remaining() == tr("noch etwa {sekunden} s").format(sekunden=30)
    finally:
        veil.deleteLater()


def test_a_long_run_says_minutes_not_hundreds_of_seconds(qt_app: QApplication) -> None:
    """„noch etwa 270 s" ist eine Zahl, die niemand in eine Vorstellung
    übersetzt."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.1, "rechnet")

        assert tr("min") in veil.remaining()
    finally:
        veil.deleteLater()


def test_the_end_is_named_not_counted(qt_app: QApplication) -> None:
    """Unter fünf Sekunden ist eine Sekundenzahl Unruhe, kein Trost."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.95, "rechnet")

        assert veil.remaining() == tr("gleich fertig")
    finally:
        veil.deleteLater()


def test_a_second_run_starts_its_own_clock(qt_app: QApplication) -> None:
    """Sonst erbt der nächste Lauf die Wartezeit des vorigen und meldet beim
    ersten Prozent, es dauere noch Stunden."""
    veil = LoadingVeil()
    try:
        veil.begin("Erster Lauf")
        _running(veil, 300.0)
        veil.end()

        veil.begin("Zweiter Lauf")
        veil.step(0.5, "rechnet")

        assert veil.remaining() == "", "die Uhr des vorigen Laufs lief weiter"
    finally:
        veil.deleteLater()


def test_the_veil_tells_when_it_really_stands(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``appeared`` kommt beim Erscheinen, ``ended`` nur nach einem Stand.

    Das Hauptfenster verbirgt am ``appeared`` die native Ansicht — zu früh
    gesendet stünde das nie gerenderte Renderfenster über dem Schleier, zu
    spät bliebe die Ansicht verborgen. Ein ``ended`` ohne vorherigen Stand
    meldete etwas, das nie geschah: ``end`` läuft nach jedem Lauf, auch wenn
    die Verzögerung die Anzeige nie hat erscheinen lassen.

    ``animations_enabled`` wird festgenagelt statt von der Plattform
    erraten: Offscreen erscheint der Schleier von selbst sofort, unter xcb
    (die CI fährt xvfb) erst nach 200 ms — und ein synchroner Blick auf das
    Signal sah dort nie eines. Geprüft wird der Signalvertrag, nicht die
    Uhr.
    """
    import app.ui.loading as loading_module

    monkeypatch.setattr(loading_module, "animations_enabled", lambda: False)
    veil = LoadingVeil()
    seen: list[str] = []
    veil.appeared.connect(lambda: seen.append("auf"))
    veil.ended.connect(lambda: seen.append("zu"))
    try:
        veil.end()
        assert seen == [], "ended kam ohne einen Stand"

        veil.begin("Projekt öffnen")  # erscheint ohne Verzögerung, s. o.
        assert seen == ["auf"]

        veil.end()
        assert seen == ["auf", "zu"]
    finally:
        veil.deleteLater()


def test_a_certain_wait_skips_the_delay(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``at_once`` überspringt die 200 ms — auch eine laufende Verzögerung.

    Beim Öffnen eines Projekts mit Schritten ist die Wartezeit sicher, und
    jede unbedeckte Millisekunde gehört dem nativen Ansichtsfenster mit
    seinen alten Pixeln: Beim Öffnen von Weg 1 standen sechs Sekunden
    Startbildschirmreste über dem unsichtbaren Schleier (23.08.2026).
    """
    import app.ui.loading as loading_module

    monkeypatch.setattr(loading_module, "animations_enabled", lambda: True)
    veil = LoadingVeil()
    try:
        veil.begin("Wird berechnet …")
        assert not veil.showing, "ohne at_once wartet die Anzeige ihre 200 ms"

        veil.begin("Projekt wird geladen …", at_once=True)
        assert veil.showing, "die sichere Wartezeit erscheint sofort"
    finally:
        veil.end()
        veil.deleteLater()


def test_the_splash_can_appear_before_the_heavy_half_is_loaded() -> None:
    """Zwei der zweikommavier Sekunden vor dem Ladebildschirm waren Importe.

    Gemessen: ``import app.ui.app`` kostete 2 393 ms, davon 2 462 ms für
    ``app.ui.main_window`` allein (die Zahlen überlappen, weil beide dieselbe
    Kette laden) — ``app.core.scene`` zieht trimesh und networkx nach. Diese
    Zeit lag **vor** dem ersten Bild: Der Ladebildschirm kann erst gebaut
    werden, wenn das Modul geladen ist, das ihn baut. Ein leerer Bildschirm ist
    nach §2.8 ab zwei Sekunden keine Anzeige.

    Geprüft wird in einem eigenen Prozess, denn in der laufenden Suite ist
    längst alles geladen — dieser Test wäre dort immer grün.
    """
    code = textwrap.dedent(
        """
        import sys
        import app.ui.app
        heavy = [name for name in ("app.ui.main_window", "app.ui.session", "trimesh")
                 if name in sys.modules]
        print(",".join(heavy))
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
        check=True,
    )

    assert finished.stdout.strip() == "", (
        f"diese Module gehören hinter den Ladebildschirm, nicht davor: {finished.stdout.strip()}"
    )


def test_the_log_says_when_the_application_ended() -> None:
    """Ein Protokoll, das den Start vermerkt und das Ende nicht, macht jeden
    Absturz unsichtbar.

    **Gefunden im Protokoll des ersten Kunden mit 0.1.3.** Dort steht
    dreimal ``Solidon3D 0.1.3 started``, zweimal davon binnen einer Minute und
    jedes Mal gefolgt von ``opened project unsaved.p3d.autosave`` — die
    Wiederherstellung wird nur angeboten, wenn die Sicherung ein
    Projekt überlebt hat, und ``clear_autosave`` räumt sie beim ordentlichen
    Schließen weg. Der Kunde hatte also zweimal kein sauberes Ende.

    **Ob es ein Absturz war, sagt niemand**, und genau das ist der Mangel: Ein
    abgeschossener Prozess, ein Absturz und ein normales Beenden sehen im
    Protokoll gleich aus — nämlich wie nichts. Wer ein Kundenprotokoll liest,
    kann die wichtigste Frage nicht beantworten.

    ``aboutToQuit`` und nicht ``closeEvent``: Das Signal feuert genau dann,
    wenn die Ereignisschleife ordentlich endet. Bei einem Absturz feuert es
    nicht, und die fehlende Zeile ist dann die Aussage.
    """
    from pathlib import Path

    quelle = Path(app_module.__file__).read_text(encoding="utf-8")

    # **Nach dem Anschluss suchen, nicht nach dem Wort.** Der erste Fassung
    # dieses Tests genügte ``"aboutToQuit" in quelle``, und sie fand den
    # Begriff im **Kommentar** darüber — sie hätte auch dann bestanden, wenn
    # nur die Begründung dastünde und keine Zeile Code.
    assert "aboutToQuit.connect" in quelle, "das ordentliche Ende gehört ins Protokoll"
    start = quelle.index("aboutToQuit.connect")
    umfeld = quelle[start : start + 200]
    assert "_log.info" in umfeld, "und zwar als Zeile, nicht als stiller Rückruf"
    assert "ended" in umfeld, "die Zeile sagt, dass es zu Ende ging"
