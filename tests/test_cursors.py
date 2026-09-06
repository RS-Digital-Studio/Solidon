"""Mauszeiger des Viewports (§19.3, Regel 18).

Ein Zeiger ist Beiwerk — er darf die Anwendung nie aufhalten und nie
verschwinden. Beides wird hier festgehalten, dazu die zwei Eigenschaften, die
man ihm nicht ansieht: der Saum, ohne den er über einem gewählten Körper
unsichtbar wäre, und der Griffpunkt, der beim Messen den Unterschied macht.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.ui import cursors
from app.ui.theme import THEMES
from tests.render_fakes import RecordingRenderer


def test_every_role_yields_a_cursor(qt_app: QApplication) -> None:
    """Jede Rolle liefert einen Zeiger — keine leere Grafik, kein Fehler."""
    widget = QWidget()
    for role in cursors.known():
        found = cursors.cursor(role, widget)
        assert found is not None
        if role in cursors.SHAPES:
            assert not found.pixmap().isNull(), role


def test_an_unknown_role_falls_back_instead_of_failing(qt_app: QApplication) -> None:
    """Ein Zeiger hält die Anwendung nie an. Wer eine Rolle falsch schreibt,
    bekommt den gewöhnlichen Pfeil und keine Ausnahme."""
    widget = QWidget()
    assert cursors.cursor("gibtesnicht", widget).shape() == Qt.CursorShape.ArrowCursor


def test_drawn_shapes_carry_the_accent_and_a_dark_edge() -> None:
    """Der Akzent allein genügt nicht: über einem gewählten Körper liegt er auf
    sich selbst. Jede eigene Zeichnung führt deshalb beide Farben."""
    accent = THEMES["dark"]["highlight"]
    edge = THEMES["dark"]["highlight_text"]
    for role in cursors.SHAPES:
        source = cursors.svg_source(role)
        assert accent in source, role
        assert edge in source, role


def test_the_edge_is_drawn_wider_than_the_accent(qt_app: QApplication) -> None:
    """Der Saum entsteht dadurch, dass er *unter* dem Akzent liegt und breiter
    ist. Wäre er dünner, gäbe es ihn nur auf dem Papier."""
    source = cursors.svg_source("measure")
    edge_width = float(source.split('stroke-width="')[1].split('"')[0])
    accent_width = float(source.split('stroke-width="')[2].split('"')[0])
    assert edge_width > accent_width


def test_the_hotspot_sits_where_the_shape_points(qt_app: QApplication) -> None:
    """Der Griffpunkt liegt da, wo die Zeichnung hinzeigt — auf den Anteil genau.

    **Dieser Test war zu locker und hat den Fehler durchgelassen**, den ein
    Kunde am 27.08.2026 meldete: „klickt nicht an der Spitze sondern in der
    Mitte des Symbols." Er verglich den Griffpunkt mit
    ``deviceIndependentSize()`` — also mit der *logischen* Größe — und der Code
    setzte ihn in genau denselben logischen Punkten. Zwei Zahlen aus derselben
    Annahme stimmten miteinander überein, während die Zeichnung darunter
    doppelt so viele Pixel hatte: Die Pfeilspitze kam bei 7,8 % der Breite an,
    wo sie bei 15,6 % liegt.

    **Ein Test, der dieselbe Annahme benutzt wie sein Prüfling, findet keinen
    gemeinsamen Irrtum.** Gemessen wird deshalb gegen die **Pixmap in Pixeln**
    und gegen den Anteil aus :data:`cursors.SHAPES` — beides Zahlen, die der
    Code nicht selbst gewählt hat.
    """
    widget = QWidget()

    for role in ("select", "feature", "measure", "sculpt"):
        drawn = cursors.cursor(role, widget)
        pixmap = drawn.pixmap()
        spot = drawn.hotSpot()
        wanted_x, wanted_y = cursors.SHAPES[role][1]

        # Ein Pixel Toleranz je Achse: der Punkt wird gerundet.
        tolerance = 1.0 / pixmap.width()
        assert abs(spot.x() / pixmap.width() - wanted_x / 32.0) <= tolerance, (
            f"{role}: Griffpunkt liegt bei {spot.x() / pixmap.width():.3f} der Breite, "
            f"gezeichnet ist er bei {wanted_x / 32.0:.3f}"
        )
        assert abs(spot.y() / pixmap.height() - wanted_y / 32.0) <= tolerance, (
            f"{role}: Griffpunkt liegt bei {spot.y() / pixmap.height():.3f} der Höhe, "
            f"gezeichnet ist er bei {wanted_y / 32.0:.3f}"
        )

    # Und die Aussage, um die es geht: Fadenkreuz mittig, Pfeil an der Spitze.
    middle = cursors.cursor("measure", widget)
    assert abs(middle.hotSpot().x() / middle.pixmap().width() - 0.5) <= 0.02
    tip = cursors.cursor("select", widget)
    assert tip.hotSpot().x() / tip.pixmap().width() < 0.25, "die Spitze sitzt links oben"


def test_the_same_role_is_built_once(qt_app: QApplication) -> None:
    """Der Zeiger wird bei jeder Mausbewegung gesetzt. Ihn dabei neu zu rastern
    wäre die teuerste Zeile der Anwendung."""
    widget = QWidget()
    cursors.forget()
    first = cursors.cursor("rotate", widget)
    second = cursors.cursor("rotate", widget)
    assert first is second


def test_forget_lets_a_theme_change_through(qt_app: QApplication) -> None:
    widget = QWidget()
    before = cursors.cursor("zoom", widget)
    cursors.forget()
    assert cursors.cursor("zoom", widget) is not before


def test_system_shapes_stay_system_shapes(qt_app: QApplication) -> None:
    """Wo das System eine bekannte Form hat, wird sie benutzt: Sie folgt der
    eingestellten Zeigergröße, unsere folgt ihr seit dem 27.08.2026 auch."""
    widget = QWidget()
    assert cursors.cursor("panning", widget).shape() == Qt.CursorShape.ClosedHandCursor
    assert cursors.cursor("move", widget).shape() == Qt.CursorShape.SizeAllCursor
    for role in cursors.SYSTEM:
        assert role not in cursors.SHAPES, f"{role} wäre zweimal beschrieben"


def test_a_drawn_cursor_follows_the_size_the_system_was_told(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer seine Zeiger auf 24 stellt, meint alle Zeiger — auch unsere.

    Ein Kunde auf CachyOS mit GNOME meldete am 27.08.2026: „Der Cursor ist
    SEHR gross und viel zu ungenau." Bis dahin hing die Größe allein an der
    **Zeilenhöhe** der Anwendung, und die wächst mit der Textskalierung: bei
    30 Punkten Zeilenhöhe ein Zeiger von 60, wo Systemzeiger 24 bis 32 messen.
    Wer die Schrift größer stellt, hat damit nichts über seine Zeiger gesagt.

    ``XCURSOR_SIZE`` ist die Stelle, an der Linux die Antwort hinterlegt —
    GNOME, KDE und die Wayland-Compositoren setzen sie. Qt hilft nicht:
    ``styleHints()`` kennt nur ``cursorFlashTime``.
    """
    widget = QWidget()
    # Gemessen wird als Linux-Rechner, weil ``XCURSOR_SIZE`` dort die Quelle
    # ist. Windows und macOS haben ihre eigenen, und die stehen unten.
    monkeypatch.setattr(cursors.sys, "platform", "linux")

    def with_size(named: str | None) -> int:
        if named is None:
            monkeypatch.delenv("XCURSOR_SIZE", raising=False)
        else:
            monkeypatch.setenv("XCURSOR_SIZE", named)
        cursors.forget()
        return cursors._size_for(widget)

    assert with_size("24") == 24, "die Einstellung des Nutzers gewinnt"

    # Der Deckel bleibt: Windows lehnt zu große Zeiger ab und zeigt dann keinen.
    assert with_size("96") == cursors.MAX_SIZE

    from_font = int(widget.fontMetrics().height() * cursors.SCALE)
    # Was keine Zahl ist, ist keine Antwort — dann gilt die Zeilenhöhe wie bisher.
    for unusable in ("0", "", "gross", "24px"):
        assert with_size(unusable) == from_font, (
            f"{unusable!r} ist keine Größe und darf keine erfinden"
        )

    assert with_size(None) == from_font, "ohne Systemangabe bleibt es bei der Zeilenhöhe"


def test_every_platform_is_asked_where_it_keeps_the_pointer_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows und macOS führen dieselbe Einstellung, nur woanders.

    Die Behebung des Kundenberichts fragte am 27.08.2026 nur ``XCURSOR_SIZE``
    und blieb damit auf halbem Weg stehen: Wer unter Windows die Zeigergröße
    hochstellt oder unter macOS den Faktor, hat genauso **alle** Zeiger
    gemeint. Auf beiden blieb es bei der Zeilenhöhe — also bei derselben
    Rechnung, die dem Kunden einen Zeiger von 60 Punkten beschert hat.

    macOS führt keine Pixelzahl, sondern einen Faktor zwischen 1,0 und 4,0.
    Ein Nutzer, der ihn auf 2 stellt, will 64.
    """
    monkeypatch.setattr(cursors, "_from_windows_registry", lambda: 48)
    cursors.forget()
    assert cursors.system_size("win32") == 48, "die Registry ist Windows' Antwort"

    class Answer:
        returncode = 0
        stdout = b"2\n"

    options: dict[str, object] = {}

    def answer(*_args: object, **kwargs: object) -> Answer:
        options.update(kwargs)
        return Answer()

    monkeypatch.setattr(cursors, "run_limited", answer)
    cursors.forget()
    assert cursors.system_size("darwin") == 2 * cursors.BASE_SIZE, "der Faktor mal die Basis"
    assert options["cwd"] == cursors.trusted_cwd()
    assert options["output_limit"] == 4096

    monkeypatch.setenv("XCURSOR_SIZE", "24")
    cursors.forget()
    assert cursors.system_size("linux") == 24


def test_a_platform_that_says_nothing_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Und wo keine Einstellung steht, wird keine erfunden.

    Der Schlüssel fehlt, solange niemand ihn verstellt hat — unter Windows
    genauso wie unter macOS, wo ``defaults`` dann mit einem Fehlercode endet.
    Das ist keine Störung, sondern die Antwort „Normalgröße", und dann gilt
    weiter die Zeilenhöhe.
    """

    class Missing:
        returncode = 1
        stdout = b""

    monkeypatch.setattr(cursors, "run_limited", lambda *a, **k: Missing())
    monkeypatch.delenv("XCURSOR_SIZE", raising=False)
    cursors.forget()
    assert cursors.system_size("darwin") == 0

    # Ein Prozessaufruf, den es gar nicht gibt, ist genauso eine Nicht-Antwort.
    def missing_program(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("defaults")

    monkeypatch.setattr(cursors, "run_limited", missing_program)
    cursors.forget()
    assert cursors.system_size("darwin") == 0


def test_the_system_is_asked_once_and_forgotten_on_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Einmal fragen, bis jemand ``forget`` ruft.

    Auf macOS kostet die Auskunft einen Prozessaufruf; ihn bei jedem Zeigerbau
    zu wiederholen hieße, die Oberfläche für eine Zahl anzuhalten, die sich im
    Betrieb praktisch nie ändert. Nach ``forget`` — Themen- oder
    Schriftwechsel — wird wieder gefragt, sonst bliebe eine inzwischen
    geänderte Einstellung ungesehen.
    """
    calls: list[int] = []

    def counted() -> int:
        calls.append(1)
        return 40

    monkeypatch.setattr(cursors, "_from_windows_registry", counted)
    cursors.forget()

    assert cursors.system_size("win32") == 40
    assert cursors.system_size("win32") == 40
    assert len(calls) == 1, "zweimal gefragt, obwohl einmal genügt"

    cursors.forget()
    assert cursors.system_size("win32") == 40
    assert len(calls) == 2, "nach forget wird wieder gefragt"


# --- der Anschluss im Viewport ------------------------------------------------
#
# Offscreen gibt es keinen Renderer; ``_cursor_role`` wird trotzdem gepflegt.
# Das ist Absicht: Was der Zeiger sein *soll*, ist eine Frage des Zustands und
# nicht der Grafikkarte — und nur so lässt es sich ohne Bild prüfen.


def test_the_pointer_says_what_a_click_would_do(qt_app: QApplication) -> None:
    """Pinsel schlägt Messen schlägt Auswahl — dieselbe Reihenfolge, die
    ``_on_picked`` beim echten Klick geht. Wer sie hier anders sortiert, baut
    einen Zeiger, der bei zwei aktiven Werkzeugen das Falsche verspricht."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    assert viewport._resting_role() == "select"

    viewport.set_measure_mode("points")
    assert viewport._resting_role() == "measure"

    viewport.set_sculpting(True)
    assert viewport._resting_role() == "sculpt"


def test_dragging_the_camera_beats_every_other_role(qt_app: QApplication) -> None:
    """Wer dreht, will nicht wissen, was unter dem Zeiger liegt."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_sculpting(True)
    viewport.set_drag_cursor("rotate")
    assert viewport._cursor_role == "rotate"


def test_after_the_drag_the_tool_comes_back(qt_app: QApplication) -> None:
    """Der Zeiger nach dem Loslassen ist der des Werkzeugs, nicht der Pfeil.
    Ein Pfad, der pauschal auf „select" zurücksetzt, löscht den Pinsel."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_measure_mode("points")
    viewport.set_drag_cursor("panning")
    viewport.set_drag_cursor(None)
    assert viewport._cursor_role == "measure"


def test_leaving_the_view_forgets_the_feature(qt_app: QApplication) -> None:
    """Sonst bliebe der Merkmalszeiger stehen, während die Maus längst im
    Objektbaum ist."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._hover_feature = True
    viewport._update_cursor()
    assert viewport._cursor_role == "feature"

    viewport._forget_pointer()
    assert viewport._cursor_role == "select"


def test_the_hover_search_waits_for_the_mouse_to_stand_still(qt_app: QApplication) -> None:
    """Bei jeder Bewegung zu suchen hieße, den Tiefenpuffer hunderte Male in
    der Sekunde im Hauptthread zu lesen."""
    from app.ui.viewport import HOVER_DELAY_MS, Viewport

    viewport = Viewport()
    assert viewport._hover_timer.isSingleShot()
    assert viewport._hover_timer.interval() == HOVER_DELAY_MS


def test_a_drag_stops_the_hover_search(qt_app: QApplication) -> None:
    """Während eines Zugs ist die Suche nutzlos und teuer."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._hover_timer.start()
    viewport.set_drag_cursor("rotate")
    assert not viewport._hover_timer.isActive()


def test_the_cursor_actually_reaches_the_interactor(qt_app: QApplication) -> None:
    """Der Test, ohne den alle anderen nichts wert wären.

    Offscreen ist ``renderer`` None, und jeder Pfad, der den Zeiger setzt, steigt
    vorher aus — die Rollenlogik könnte also vollständig stimmen, während im
    Fenster nie ein Zeiger ankommt. Eine Attrappe mit genau der einen Methode,
    die benutzt wird, schließt die Lücke ohne OpenGL.
    """
    from app.ui.viewport import Viewport

    class FakeInteractor:
        def __init__(self) -> None:
            self.cursors: list[object] = []

        def setCursor(self, cursor: object) -> None:  # noqa: N802 — Qt-Name
            self.cursors.append(cursor)

        def height(self) -> int:
            return 480

    viewport = Viewport()
    renderer = RecordingRenderer()
    renderer.widget = FakeInteractor()
    viewport.renderer = renderer

    viewport.set_sculpting(True)
    assert renderer.widget.cursors, "der Pinselzeiger kam nie am Fenster an"
    assert viewport._cursor_role == "sculpt"

    before = len(renderer.widget.cursors)
    viewport.set_drag_cursor("rotate")
    assert len(renderer.widget.cursors) == before + 1


def test_the_same_role_twice_does_not_set_it_twice(qt_app: QApplication) -> None:
    """Der Zeiger hängt an der Mausbewegung. Ihn bei jeder erneut zu setzen,
    lässt ihn auf langsamen Treibern flackern."""
    from app.ui.viewport import Viewport

    class FakeInteractor:
        def __init__(self) -> None:
            self.count = 0

        def setCursor(self, cursor: object) -> None:  # noqa: N802 — Qt-Name
            self.count += 1

        def height(self) -> int:
            return 480

    viewport = Viewport()
    renderer = RecordingRenderer()
    renderer.widget = FakeInteractor()
    viewport.renderer = renderer

    viewport.set_drag_cursor("rotate")
    viewport.set_drag_cursor("rotate")
    viewport.set_drag_cursor("rotate")
    assert renderer.widget.count == 1


def test_the_panels_get_the_same_pointer_as_the_view(qt_app: QApplication) -> None:
    """Sonst stehen zwei Handschriften in einem Fenster: der eigene Zeiger über
    dem Bild, der des Systems daneben."""
    from app.ui.cursors import apply_default_cursor

    window = QWidget()
    child = QWidget(window)
    apply_default_cursor(window)

    assert not window.cursor().pixmap().isNull()
    # Das Kind hat keinen eigenen gesetzt und erbt deshalb — genau darauf
    # beruht der Aufruf auf Fensterebene.
    assert child.cursor().pixmap().cacheKey() == window.cursor().pixmap().cacheKey()


def test_a_text_field_keeps_its_own_pointer(qt_app: QApplication) -> None:
    """Der Textbalken ist eine Auskunft, keine Zierde. Widgets, die ihren
    Zeiger selbst setzen, dürfen von der Vererbung nicht überfahren werden."""
    from PySide6.QtWidgets import QLineEdit

    from app.ui.cursors import apply_default_cursor

    window = QWidget()
    field = QLineEdit(window)
    apply_default_cursor(window)
    assert field.cursor().shape() == Qt.CursorShape.IBeamCursor


def _role_literals() -> dict[str, list[str]]:
    """Jedes Rollen-Literal aus ``app/ui``, mit seinen Fundorten.

    Gesammelt wird über den Syntaxbaum, nicht über eine Textsuche: „section"
    kommt im Quelltext dutzendfach als Werkzeugname vor und nie als
    Zeigerrolle — eine Textsuche zählte das Falsche. Rollen fließen auf drei
    Wegen: als erstes Argument von ``set_drag_cursor``/``cursor``/``on_cursor``
    und als Return-Literal in ``_resting_role``. Die Kameraführung setzt ihre
    vier Rollen im Navigator unter ``app/ui/render/``, deshalb liest die Suche
    das Verzeichnis samt Unterordnern.
    """
    import ast
    from pathlib import Path

    found: dict[str, list[str]] = {}
    calls = {"set_drag_cursor", "cursor", "on_cursor"}
    for path in sorted((Path(__file__).parent.parent / "app" / "ui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in calls and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        found.setdefault(first.value, []).append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.FunctionDef) and node.name == "_resting_role":
                # Auch unter dem Return, nicht nur direkt daran: Zeile wie
                # ``return "feature" if … else "select"`` trägt ihre Rollen
                # in einem ternären Ausdruck, und die Funktion gibt ohnehin
                # nichts als Rollen zurück.
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Return) and inner.value is not None:
                        for leaf in ast.walk(inner.value):
                            if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str):
                                found.setdefault(leaf.value, []).append(
                                    f"{path.name}:{inner.lineno}"
                                )
    # Die Zusicherung über das Werkzeug selbst: Findet die Sammlung fast
    # nichts, sucht sie falsch — dann prüft der Test darunter eine leere
    # Menge und ist grün über nichts.
    assert len(found) >= 6, f"nur {len(found)} Rollen gefunden — sammelt das noch richtig?"
    return found


def test_every_set_role_exists_and_every_drawn_role_is_set() -> None:
    """Beide Richtungen zwischen Zeichnung und Setzstelle (Regel 18 daneben).

    Hin: Ein gesetztes Literal, das keine Rolle ist, fällt still auf den
    Systempfeil zurück — ``set_drag_cursor("moving")`` stand an der häufigsten
    Zuggeste, und die zeigte den Windows-Pfeil statt des Verschiebekreuzes.
    Zurück: Eine gezeichnete Rolle ohne Setzstelle sieht kein Kunde je — der
    Schnittzeiger war fertig gezeichnet, begründet und wurde nie gesetzt,
    denn der Schnitt hat keine Klickgeste. Beides sah kein Test, weil keiner
    die beiden Bestände gegeneinander hielt.
    """
    found = _role_literals()

    unknown = {role: places for role, places in found.items() if role not in cursors.known()}
    assert not unknown, f"gesetzte Rollen, die es nicht gibt: {unknown}"

    never_set = sorted(role for role in cursors.SHAPES if role not in found)
    assert not never_set, (
        f"gezeichnete Rollen ohne Setzstelle: {never_set} — entweder anschließen "
        "oder ausbauen, ein Zeiger ins Leere ist beides nicht"
    )
