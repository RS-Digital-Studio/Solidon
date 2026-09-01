"""Die Titelleiste trägt die Farben der Anwendung (G15).

Windows malt Titelleiste und Rahmen selbst, in seinem eigenen Grau. Darunter
beginnt die Anwendung in ihrer Farbe, und quer über die Fensteroberkante läuft
ein Absatz, an dem das Fenster in zwei Teile zerfällt.

Gemessen am 30.08.2026 an einem Bildschirmausschnitt, Build 26200:

===========  ====================  ====================
Thema        Titelleiste vorher    nachher
===========  ====================  ====================
dunkel       ``(32, 32, 32)``      ``(52, 58, 69)``
hell         ``(243, 243, 243)``   ``(231, 233, 237)``
===========  ====================  ====================

**Geprüft wird hier die Zusage, nicht die Farbe auf dem Schirm.** Die Suite
läuft offscreen, es gibt keinen Bildschirm — und selbst mit einem wäre die
Messung fragil: Drei Anläufe sind daran gescheitert, dass ein Ausschnitt
erfasst, was gerade oben liegt (einmal eine Einblendanimation, einmal ein
fremdes Fenster, das sich während der Wartezeit davorschob; gemessen
(77, 52, 62), eine Farbe, die in keinem Thema vorkommt). Und
``DwmGetWindowAttribute`` hilft nicht: Die Farbe ist schreibbar und **nicht
lesbar**, Windows antwortet mit ``E_INVALIDARG``.

Die Zusage lautet deshalb: Jedes Fenster, das erscheint, und jedes, das schon
steht, wenn das Thema wechselt, wird angestrichen — **ohne dass irgendwo ein
Aufruf dafür steht**. Genau das ist der Punkt des Wächters: Eine Liste von
Aufrufen vergisst den nächsten Dialog, und zwar still.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QWidget

from app.ui import window_chrome
from app.ui.theme import apply_theme


def test_only_supported_windows_versions_offer_window_chrome(monkeypatch) -> None:
    """Die Plattform- und Buildgrenze bleibt trotz plattformneutraler Typisierung erhalten."""
    monkeypatch.setattr(window_chrome, "_PLATFORM", "linux")
    assert not window_chrome.available()

    monkeypatch.setattr(window_chrome, "_PLATFORM", "win32")
    monkeypatch.setattr(
        window_chrome.sys,
        "getwindowsversion",
        lambda: type("WindowsVersion", (), {"build": window_chrome._MIN_BUILD - 1})(),
        raising=False,
    )
    assert not window_chrome.available()

    monkeypatch.setattr(
        window_chrome.sys,
        "getwindowsversion",
        lambda: type("WindowsVersion", (), {"build": window_chrome._MIN_BUILD})(),
        raising=False,
    )
    assert window_chrome.available()


def test_a_missing_windows_loader_is_harmless(monkeypatch) -> None:
    """Außerhalb von Windows fehlt ``WinDLL`` und das Chrom bleibt einfach unverändert."""
    monkeypatch.setattr(window_chrome, "_library", None)
    monkeypatch.delattr(window_chrome.ctypes, "WinDLL", raising=False)

    assert window_chrome._dwm() is None


def test_the_windows_library_is_loaded_only_once(monkeypatch) -> None:
    """Auf Windows bleibt die Bibliothek über alle Fenster hinweg im Speicher."""
    loaded: list[str] = []
    library = object()
    monkeypatch.setattr(window_chrome, "_library", None)
    monkeypatch.setattr(
        window_chrome.ctypes,
        "WinDLL",
        lambda name: loaded.append(name) or library,
        raising=False,
    )

    assert window_chrome._dwm() is library
    assert window_chrome._dwm() is library
    assert loaded == ["dwmapi"]


def test_a_window_that_appears_is_painted(qt_app: QApplication, monkeypatch) -> None:
    """Jedes Fenster wird angestrichen, sobald es erscheint.

    **Ein Dialog steht in keiner Liste, und das ist Absicht.** Die Anwendung
    hat ein Hauptfenster und achtzehn Dialoge; jeder weitere käme dazu. Ein
    Wächter am Ereignisstrom kann keinen vergessen, weil er nicht aufzählt.
    """
    painted: list[str] = []
    monkeypatch.setattr(
        window_chrome, "paint_chrome", lambda w: painted.append(type(w).__name__) or True
    )
    watcher = window_chrome.ChromeWatcher()
    qt_app.installEventFilter(watcher)
    try:
        dialog = QDialog()
        dialog.show()
        QApplication.processEvents()
        assert "QDialog" in painted, (
            f"ein erscheinender Dialog wurde nicht angestrichen, gemalt wurde: {painted}"
        )
        dialog.close()
    finally:
        qt_app.removeEventFilter(watcher)


def test_a_child_widget_is_not_a_window(qt_app: QApplication, monkeypatch) -> None:
    """Und was kein Fenster ist, bekommt auch keins gemalt.

    Die Gegenprobe zur Zusage darüber. Ohne sie bliebe offen, ob der Wächter
    überhaupt unterscheidet — einer, der auf **jedes** ``Show`` anspringt,
    riefe die Funktion für jedes Label und jeden Knopf, und der erste Test
    wäre trotzdem grün.
    """
    painted: list[str] = []
    monkeypatch.setattr(
        window_chrome, "paint_chrome", lambda w: painted.append(type(w).__name__) or True
    )
    watcher = window_chrome.ChromeWatcher()
    qt_app.installEventFilter(watcher)
    try:
        holder = QWidget()
        child = QLabel("nur ein Kind", holder)
        holder.show()
        child.show()
        QApplication.processEvents()
        assert "QLabel" not in painted, (
            f"ein Kind-Widget ist kein Fenster und braucht kein Chrom: {painted}"
        )
        holder.close()
    finally:
        qt_app.removeEventFilter(watcher)


def test_a_theme_change_repaints_what_already_stands(qt_app: QApplication, monkeypatch) -> None:
    """Ein Themenwechsel zieht die offenen Fenster nach.

    **Und zwar ohne eine Zeile in ``action_theme``.** Der Wächter hört auf
    ``ApplicationPaletteChange``, und das Umstellen des Themas löst es aus —
    damit kann niemand die Zeile beim nächsten Umbau vergessen, weil es sie
    nicht gibt.
    """
    repainted: list[int] = []
    monkeypatch.setattr(window_chrome, "paint_every_window", lambda: repainted.append(1) or 1)
    watcher = window_chrome.ChromeWatcher()
    qt_app.installEventFilter(watcher)
    before = qt_app.styleSheet()
    try:
        apply_theme(qt_app, "light")
        QApplication.processEvents()
        assert repainted, (
            "ein Themenwechsel hat die offenen Fenster nicht nachgezogen — "
            "dann trägt die Titelleiste die Farbe des alten Themas"
        )
        # **Und genau einmal.** Qt stellt ``ApplicationPaletteChange`` jedem
        # Empfänger einzeln zu, nicht einmal je Wechsel: gemessen sechs
        # Feuerungen bei zwei Fenstern und zwanzig Kindern. Gemalt werden
        # müssen die Fenster aber einmal — bei neunzehn offenen Dialogen wären
        # es sonst einige hundert DWM-Aufrufe für dasselbe Ergebnis.
        assert len(repainted) == 1, (
            f"der Themenwechsel hat {len(repainted)}-mal nachgezogen statt einmal — "
            "das Ereignis kommt je Empfänger an, gemalt wird am Anwendungsobjekt"
        )
    finally:
        qt_app.removeEventFilter(watcher)
        apply_theme(qt_app, "dark")
        qt_app.setStyleSheet(before)


def test_the_colour_conversion_matches_what_windows_expects() -> None:
    """Windows will ``0x00BBGGRR``, Qt hält RGB — die Reihenfolge dreht sich.

    Der Fehler wäre still: Ein vertauschtes Rot und Blau ergibt eine Farbe,
    die es gibt, und niemand sieht ihr an, dass sie falsch herum ist. Bei
    ``#343a45`` fiele es kaum auf; bei einem warmen Akzent stünde die
    Titelleiste in Blau.
    """
    from PySide6.QtGui import QColor

    assert window_chrome._colorref(QColor("#343a45")) == 0x453A34, "BGR statt RGB"
    assert window_chrome._colorref(QColor("#ff0000")) == 0x0000FF, "reines Rot wird 0x0000FF"
    assert window_chrome._colorref(QColor("#0000ff")) == 0xFF0000, "reines Blau wird 0xFF0000"
