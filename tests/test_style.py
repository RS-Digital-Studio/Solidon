"""Formsprache: Stylesheet, Typografie-Skala, Abstandsraster (§19.3).

„Sieht standard aus" ist kein Geschmacksurteil, sondern hat nachweisbare
Ursachen — keine Formsprache, keine Typografie-Skala, kein Abstandsrhythmus.
Diese Datei hält die drei Antworten darauf fest, damit sie nicht wieder
auseinanderlaufen: eine Gestaltung, die an fünfzig Einzelstellen entschieden
wird, ist nach zehn Änderungen keine mehr.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.ui.style import LEVELS, NORMAL, ROOMY, SPACE, TIGHT, WIDE, stylesheet, type_scale
from app.ui.theme import THEMES

UI = Path(__file__).parent.parent / "app" / "ui"


def test_the_scale_gets_quieter_step_by_step() -> None:
    """Vier Stufen, und jede leiser als die davor.

    Vorher war alles gleich laut: im Objektbaum war der Name so groß wie das
    Maß, im Prüfbericht ein Fehler so groß wie ein Hinweis. Eine Skala, deren
    Stufen sich überschneiden, wäre wieder keine.
    """
    sizes = type_scale(10)
    assert list(sizes) == list(LEVELS)

    values = [sizes[level][0] for level in LEVELS]
    assert values == sorted(values, reverse=True), f"nicht absteigend: {values}"
    assert len(set(values)) == len(values), "zwei Stufen gleich groß sind eine Stufe"

    assert sizes["caption"][1] < sizes["section"][1], "Nebentext soll nicht mitreden"


def test_the_scale_follows_the_system_font() -> None:
    """§19.3 verlangt skalierbare Schrift: wer seine Systemschrift größer
    stellt, bekommt die ganze Anwendung größer, nicht nur den Rest."""
    small = type_scale(8)
    large = type_scale(16)
    for level in LEVELS:
        assert large[level][0] > small[level][0], level


def test_the_grid_is_one_number_and_its_multiples() -> None:
    for step in (TIGHT, NORMAL, ROOMY, WIDE):
        assert step % SPACE == 0
    assert TIGHT < NORMAL < ROOMY < WIDE


#: ``setSpacing(…)`` und ``setContentsMargins(…)`` mit nackten Zahlen.
_SPACING = re.compile(r"set(?:Spacing|ContentsMargins)\(([^)]*)\)")


def test_no_layout_invents_its_own_distance() -> None:
    """Elemente standen mal 2, mal 3, mal 5, mal 6 Pixel auseinander.

    Das ist der Eindruck, dass alles ein bisschen daneben sitzt, ohne dass man
    einen einzelnen Fehler benennen kann. Null bleibt erlaubt: kein Abstand ist
    eine Aussage, kein Zwischenwert.
    """
    off: dict[str, list[str]] = {}
    for path in sorted(UI.glob("*.py")):
        for match in _SPACING.finditer(path.read_text(encoding="utf-8")):
            for part in match.group(1).split(","):
                value = part.strip()
                if not value.isdigit() or int(value) == 0:
                    continue
                if int(value) % SPACE:
                    off.setdefault(path.name, []).append(match.group(0))

    assert not off, (
        f"Diese Abstände liegen nicht auf dem Raster von {SPACE} px: {off}. "
        "TIGHT, NORMAL, ROOMY und WIDE aus app/ui/style.py sind die Stufen."
    )


def test_the_stylesheet_covers_the_states_a_control_has() -> None:
    """Ein Knopf, den man nicht überfahren sieht, fühlt sich tot an.

    Fusion bringt Zustände mit; sobald ein Stylesheet ein Element anfasst,
    bringt es keine mehr. Wer also stylt, muss alle vier liefern.
    """
    sheet = stylesheet("dark", 10)
    for state in (":hover", ":focus", ":pressed", ":disabled"):
        assert state in sheet, f"kein Zustand {state} im Stylesheet"

    assert "QPushButton:default" in sheet, "Haupt- und Nebenknopf müssen sich unterscheiden"


def test_a_styled_control_keeps_the_parts_qt_stops_drawing() -> None:
    """Wer die Box anfasst, muss ihre Teile mitliefern.

    Sobald ein Stylesheet an einem ``QSpinBox`` eine Rahmeneigenschaft setzt —
    und die Regel, die allen Eingabefeldern ihren Radius gibt, tut das —, hört
    Qt auf, dessen Unterelemente selbst zu zeichnen. Übrig blieben zwei leere
    Kästchen mit einem Strich dazwischen, auf jedem Zahlenfeld jedes Dialogs,
    in beiden Themen; 27 Felder in 13 Dateien. Wer das sieht, hält es für einen
    Grafikfehler und klickt nicht hin.

    Ein Dreieck aus Rahmenkanten, wie man es in HTML baut, hilft nicht: Qt
    füllt die Fläche und zeichnet einen hellen Block. Es muss ein Bild sein.
    """
    sheet = stylesheet("dark", 10, {"up": "/tmp/up.svg", "down": "/tmp/down.svg"})

    assert "QSpinBox::up-button" in sheet, "die Knöpfe brauchen ihre Fläche"
    for part in ("up-arrow", "down-arrow"):
        assert f"QSpinBox::{part}" in sheet, f"kein {part} — das Kästchen bliebe leer"

    # **Jeder gestaltete Pfeil trägt ein Bild** — und nicht: es gibt genau
    # zwei. Hier stand ``count("image: url(") == 2``, und das war der
    # Ist-Zustand statt der Zusage: Als die Combobox ihr Pfeilfeld bekam und
    # denselben Pfeil brauchte, wurde der Test rot, obwohl genau das Richtige
    # geschah. Ein Test, der eine Menge festnagelt, sichert auch zu, was nicht
    # darin steht.
    arrows_drawn = re.findall(r"([\w:]+::(?:up|down)-arrow)[^{]*\{([^}]*)\}", sheet)
    assert arrows_drawn, "kein einziger Pfeil im Stylesheet"
    for selector, rule in arrows_drawn:
        assert "image: url(" in rule, f"{selector}: ein Pfeil ohne Bild ist kein Pfeil"


def test_the_arrows_follow_the_theme_and_survive_a_missing_cache() -> None:
    """Die Pfeile sind Dateien, und Dateien können fehlen.

    Sie tragen die Textfarbe ihres Themas, werden also je Thema neu
    geschrieben. Lässt sich nichts schreiben, bleiben die Knöpfe leer — das ist
    der Zustand von vorher und kein Grund, eine Anwendung nicht zu starten.
    """
    from app.ui.style import arrow_files

    written = arrow_files("dark")
    assert written is not None
    assert set(written) == {"up", "down"}
    for path in written.values():
        assert Path(path).is_file()
        assert THEMES["dark"]["text"] in Path(path).read_text(encoding="utf-8")

    assert THEMES["light"]["text"] in Path(arrow_files("light")["up"]).read_text(  # type: ignore[index]
        encoding="utf-8"
    )

    # Ohne Pfeile bleibt das Stylesheet ein Stylesheet.
    assert "image: url(" not in stylesheet("dark", 10, None)


def test_a_splitter_handle_can_be_hit_with_a_mouse() -> None:
    """Ein Bildpunkt Griff ist eine Trennlinie, kein Griff.

    Die Fuge zwischen Bausteinliste und Detailspalte war einen Punkt breit —
    wer die Spalte verbreitern wollte, musste diesen einen Punkt treffen.
    """
    sheet = stylesheet("dark", 10)
    width = re.search(r"QSplitter::handle:horizontal \{ width: (\d+)px", sheet)
    assert width is not None, "der Griff hat keine Breite mehr"
    assert int(width.group(1)) >= NORMAL, "unter zwei Rasterschritten trifft ihn niemand"
    assert "QSplitter::handle:hover" in sheet, "er sagt nicht, dass er sich ziehen lässt"


def test_the_tooltip_wears_the_form_of_the_application() -> None:
    """Der Hinweis unter dem Zeiger erklärt jeden gesperrten Knopf.

    Er war das letzte Element ohne eigene Form — kantig, randlos, und im hellen
    Thema auf dem Blassgelb, das Qt von Windows erbt: die einzige Farbe im
    ganzen hellen Thema, die aus keiner Tabelle dieser Anwendung stammte.
    """
    assert "QToolTip" in stylesheet("dark", 10)
    assert THEMES["light"]["tooltip"] == "#ffffff", "das Blassgelb ist wieder da"


def test_both_themes_build_a_stylesheet_out_of_their_own_colours() -> None:
    """Ein Themenwechsel, der nur die Palette umstellt, lässt die Form stehen —
    und die Form trägt hier Farben."""
    sheets = {}
    for theme in THEMES:
        sheets[theme] = stylesheet(theme, 10)
        assert THEMES[theme]["highlight"] in sheets[theme]
        assert THEMES[theme]["base"] in sheets[theme]

    assert len(set(sheets.values())) == len(THEMES), "zwei Themen, ein Aussehen"


def test_a_size_is_never_hardcoded_in_the_sheet() -> None:
    """Die Stufen kommen aus der Skala, nicht aus der Datei."""
    sheet = stylesheet("dark", 10)
    sizes = {size for size, _weight in type_scale(10).values()}
    for match in re.finditer(r"font-size:\s*(\d+)pt", sheet):
        assert int(match.group(1)) in sizes, f"{match.group(0)} steht in keiner Stufe"


# --- der Themenwechsel kommt überall an (Konzept Teil 10, Punkt 10) --------------


def _corner_colours(pixmap: object) -> set[tuple[int, int, int]]:
    """Die Farben, die in einem Symbol vorkommen — ohne die durchsichtigen."""
    image = pixmap.toImage()  # type: ignore[attr-defined]
    found = set()
    for x in range(0, image.width(), 2):
        for y in range(0, image.height(), 2):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 128:
                found.add((colour.red(), colour.green(), colour.blue()))
    return found


def test_an_icon_takes_its_colour_when_it_is_drawn(qt_app: object) -> None:
    """Dasselbe Symbol, zwei Themen, zwei Farben.

    Vorher wurde beim Aufbau einmal gerastert, in der Textfarbe, die gerade
    galt. Nach dem Wechsel stand dieselbe Grafik weiter da: im hellen Thema
    hell auf hell, und die halbe Werkzeugzeile bestand aus Text mit Lücken
    davor.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication, QWidget

    from app.ui.icons import icon
    from app.ui.theme import apply_theme

    widget = QWidget()
    application = QApplication.instance()
    assert application is not None

    apply_theme(application, "dark")  # type: ignore[arg-type]
    same = icon("save", widget)
    on_dark = _corner_colours(same.pixmap(QSize(32, 32)))

    apply_theme(application, "light")  # type: ignore[arg-type]
    on_light = _corner_colours(same.pixmap(QSize(32, 32)))

    assert on_dark and on_light
    assert on_dark != on_light, "dasselbe Symbol-Objekt, und es folgt dem Thema"


def test_a_role_colour_stays_what_it_means(qt_app: object) -> None:
    """Der Schweregrad eines Befunds ist keine Themenfrage.

    Rot heißt Fehler, in beiden Themen. Nur die Symbole ohne eigene Farbe
    folgen der Schrift.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QWidget

    from app.ui.icons import icon
    from app.ui.theme import apply_theme

    widget = QWidget()
    application = QApplication.instance()
    assert application is not None
    role = QColor("#d05a5a")

    apply_theme(application, "dark")  # type: ignore[arg-type]
    fixed = icon("severity-error", widget, colour=role)
    on_dark = _corner_colours(fixed.pixmap(QSize(32, 32)))

    apply_theme(application, "light")  # type: ignore[arg-type]
    on_light = _corner_colours(icon("severity-error", widget, colour=role).pixmap(QSize(32, 32)))

    assert on_dark == on_light


def test_a_cached_pixmap_is_dropped_when_the_theme_turns(qt_app: object) -> None:
    """Ein QLabel kann nur Pixmaps, und ein Pixmap altert.

    Die Häkchen und der Pfeil der Tour liegen als Bild vor. Wer eines
    zwischenspeichert, muss darauf hören, wann seine Farbe nicht mehr stimmt.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from app.ui.session import Session
    from app.ui.theme import apply_theme
    from app.ui.tour import TourPanel

    application = QApplication.instance()
    assert application is not None
    apply_theme(application, "dark")  # type: ignore[arg-type]

    panel = TourPanel(Session())
    before = _corner_colours(panel._mark("done"))
    assert before

    apply_theme(application, "light")  # type: ignore[arg-type]
    panel.changeEvent(QEvent(QEvent.Type.PaletteChange))

    assert _corner_colours(panel._mark("done")) != before


def test_a_step_that_does_not_fit_ends_in_an_ellipsis(qt_app: object) -> None:
    """„…Transaktionen: Bode" liest sich nicht wie eine Kürzung, sondern wie
    ein Fehler."""
    from app.ui.tour import StepLabel

    long = "1. Der Verlauf zeigt sie als Transaktionen: Boden, Befestigung, Kabel."
    label = StepLabel(long)
    label.resize(120, 20)
    label.set_wrapped(False)

    assert label.text().endswith("…")
    assert label.full_text() == long, "gekürzt wird die Anzeige, nicht der Text"

    label.set_wrapped(True)
    assert label.text() == long, "umgebrochen steht er wieder ganz da"


# --- der Hauptknopf --------------------------------------------------------------


def test_a_primary_button_is_wide_enough_for_its_own_bold_label(qt_app: QApplication) -> None:
    """Der Fehler, den man erst im Bild sieht.

    Das Stylesheet zeichnet ``QPushButton:default`` halbfett, Qt rechnet die
    bevorzugte Breite aber aus der normalen Schrift des Widgets. Wo ein Layout
    dem Knopf genau diese Breite gibt — in einer engen Leiste tut es das —,
    stand auf dem Hauptknopf des Trennwerkzeugs „etzt trenne": vorn und hinten
    ein Buchstabe abgeschnitten.

    Gemessen wird gegen die Schrift, mit der wirklich gezeichnet wird, plus
    den Innenabstand aus dem Stylesheet. Ein Knopf, der ``setDefault(True)``
    ohne :func:`make_primary` bekommt, fällt hier durch.

    **Und gemessen mit angewandtem Thema** — das fehlte, und damit stand dieser
    Test von seinem ersten Tag an rot (`49d4c731`, auf dieser Maschine
    nachgeprüft). Der Innenabstand kommt aus dem Stylesheet; ohne es rechnet Qt
    seinen eigenen. Gemessen am 24.08.2026, offscreen bei ``Sans Serif`` 9 pt:

    ===================  ==================  ===========
    Text                 ohne Thema          mit Thema
    ===================  ==================  ===========
    „Jetzt trennen"      170 (braucht 180)   **182**
    „Slicen"             86 (braucht 96)     **98**
    ===================  ==================  ===========

    Dass auch die **kurzen** Texte scheiterten, ist der Beleg: keine Frage der
    Textlänge, sondern eine feste Differenz von zehn Bildpunkten zwischen zwei
    Innenabständen. Alle fünf Texte scheiterten um genau diesen Betrag. Die
    Schwelle bleibt deshalb unverändert — ein Test, dessen Zahl man verschiebt,
    bis er grün ist, prüft nichts mehr.

    Das Vorbild steht in ``tests/test_sketch_editor.py``, wo die Breitengrenze
    der Skizzenleiste seit je mit Thema gemessen wird. Der Docstring dort nennt
    die **Gegenrichtung** desselben Fehlers: ein Test, der zwei Runden lang
    grün war, weil ihm die Polsterung fehlte. Dieselbe Ursache, zwei Vorzeichen
    — das Stylesheet gehört zur Messung und nicht zur Kulisse.

    **Was dieser Test offscreen nicht prüfen kann, und das gehört dazu:** den
    Unterschied zwischen halbfett und normal. Gemessen am 24.08.2026 sind beide
    hier **gleich breit** — „Jetzt trennen" 156 Bildpunkte in beiden Schnitten,
    „Slicen" 72 —, weil die Ersatzschrift der Offscreen-Plattform keine echte
    DemiBold-Variante hat und Qt sie in der Breite nicht synthetisiert. Die
    Gegenprobe zeigt es unmittelbar: Ersetzt man :func:`make_primary` durch ein
    nacktes ``setDefault(True)``, bleibt dieser Test **grün**. Er ist damit
    eine Untergrenze — „der Innenabstand des Themas kommt in der Rechnung an" —
    und nicht die Prüfung der Fettschrift. Die steht als eigener Test darunter,
    und dort ist sie schriftunabhängig.
    """
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QPushButton

    from app.ui.style import make_primary

    # ``qt_app`` ist eine Sitzungs-Fixture: Ein gesetztes Stylesheet nähme jeden
    # folgenden Test mit. Das ``finally`` gilt darum auch für einen
    # fehlgeschlagenen Vergleich — dieselbe Auflage wie bei
    # ``labels.set_display_unit`` (siehe ``.claude/rules/oberflaeche.md``).
    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", 10))
    try:
        for text in ("Jetzt trennen", "Neues Projekt", "Slicen", "Fertig", "Weiter"):
            button = make_primary(QPushButton(text))
            # Sonst rechnet Qt die Breite womöglich noch ohne das Thema.
            button.ensurePolished()
            drawn = QFontMetrics(button.font()).horizontalAdvance(text)

            assert button.sizeHint().width() >= drawn + 2 * ROOMY, (
                f"{text!r} bekommt {button.sizeHint().width()} Bildpunkte und braucht "
                f"{drawn + 2 * ROOMY} — die Beschriftung wird abgeschnitten."
            )
    finally:
        qt_app.setStyleSheet(before)


def test_a_primary_button_carries_the_font_it_is_drawn_with(qt_app: QApplication) -> None:
    """Die Zusage von :func:`make_primary`, schriftunabhängig geprüft.

    Der Test darüber kann sie offscreen nicht prüfen: Dort ist halbfett genauso
    breit wie normal (gemessen: 156 gegen 156), und ein Knopf mit nacktem
    ``setDefault(True)`` kommt deshalb durch. Die **Mechanik** dagegen ist ohne
    Schriftmaße prüfbar, und sie ist der ganze Inhalt der Behebung: Das
    Stylesheet zeichnet ``QPushButton:default`` mit ``font-weight: 600``, Qt
    rechnet die bevorzugte Breite aber aus der Schrift **des Widgets** — also
    muss sie dort stehen. Genau das tut ``make_primary``, und genau das fehlte,
    als auf dem Trennknopf „etzt trenne" stand.

    Damit fällt hier durch, was dort durchkommt: ein Hauptknopf, der nur
    ``setDefault(True)`` bekommt. Der Nachbartest darunter sucht solche Knöpfe
    im Quelltext; dieser prüft, was ``make_primary`` daraus macht.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QPushButton

    from app.ui.style import make_primary

    schlicht = QPushButton("Jetzt trennen")
    schlicht.setDefault(True)
    assert schlicht.font().weight() < QFont.Weight.DemiBold, (
        "Ausgangslage: ein nackter Knopf trägt die normale Schrift — sonst prüft dieser Test nichts"
    )

    button = make_primary(QPushButton("Jetzt trennen"))

    assert button.isDefault(), "make_primary macht den Knopf zum Hauptknopf"
    assert button.font().weight() >= QFont.Weight.DemiBold, (
        "Die Schrift, mit der das Stylesheet zeichnet, muss am Widget stehen — "
        "sonst rechnet Qt die Breite aus der normalen und schneidet ab."
    )


def test_every_default_button_of_the_surface_goes_through_make_primary(qt_app: object) -> None:
    """``setDefault(True)`` allein genügt nicht mehr, und das darf niemand
    wieder vergessen.

    Geprüft wird am Quelltext und nicht am gebauten Fenster: Die sieben
    Hauptknöpfe leben in sieben Dateien, und sechs davon brauchen einen
    Dialog, um überhaupt zu entstehen.
    """
    # Der Glob ist die Grundmenge, und ein umbenannter Ordner macht ihn leer,
    # ohne dass jemand etwas merkt: Der Test bliebe grün und prüfte nichts.
    dateien = sorted(UI.glob("*.py"))
    assert len(dateien) > 20, f"nur {len(dateien)} Dateien unter {UI} — falscher Pfad?"

    offenders = [
        path.name
        for path in sorted(UI.glob("*.py"))
        # ``style.py`` selbst ist die eine Stelle, an der der Aufruf stehen
        # darf — dort steht er in ``make_primary``.
        if path.name != "style.py" and "setDefault(True)" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, (
        f"Diese Dateien setzen den Hauptknopf noch von Hand: {offenders}. "
        "make_primary() setzt zugleich die Schrift, aus der die Breite folgt."
    )


def test_no_multiline_field_swallows_the_tab_key() -> None:
    """Ein mehrzeiliges Feld nimmt den Tabulator als Zeichen — und wird damit
    zur Tastenfalle.

    Im Freischaltdialog stand genau das: Wer ohne Maus arbeitet, kam aus dem
    Schlüsselfeld nicht mehr heraus, ausgerechnet dort, wo viele ihren
    Schlüssel aus einer Mail einfügen. Der Chat macht es seit jeher richtig.

    Geprüft am Quelltext: Die zwei Felder leben in zwei Dialogen, und beide zu
    bauen hieße, ein Sprachmodell und einen Lizenzserver zu brauchen.
    """
    offenders = []
    for path in sorted(UI.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(\w+)\s*=\s*QPlainTextEdit\(", source):
            feld = match.group(1)
            if f"{feld}.setReadOnly(True)" in source:
                continue
            if f"{feld}.setTabChangesFocus(True)" not in source:
                offenders.append(f"{path.name}:{feld}")

    assert not offenders, (
        f"Diese Felder schlucken den Tabulator: {offenders}. "
        "setTabChangesFocus(True) macht daraus einen Weg statt einer Falle."
    )


def test_the_tab_bar_shows_where_the_keyboard_is() -> None:
    """Die Reiterleiste zeigte den Fokus mit null Bildpunkten Unterschied.

    Wer mit dem Tabulator dorthin kommt, sah nicht, dass er dort ist — und die
    Pfeiltasten wechselten scheinbar grundlos den Reiter. ``:selected:focus``
    und nicht ``:focus``: Der Zustand gilt der Leiste, also träfe der zweite
    alle Reiter zugleich.
    """
    sheet = stylesheet("dark", 10)

    assert "QTabBar::tab:selected:focus" in sheet
    assert "QTabBar::tab:focus {" not in sheet, (
        "Ein Fokusrahmen an jedem Reiter markiert die ganze Leiste statt einer Stelle."
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_locked_progress_bar_gives_up_the_accent(theme: str, qt_app: object) -> None:
    """Gesperrt heißt leiser — und geprüft wird das am Bild, nicht am Text.

    Die Palette trug den gedämpften Akzent für die Disabled-Gruppe längst; der
    Balken zeichnete trotzdem den vollen, weil ein Stylesheet gegen die Palette
    gewinnt und ``QProgressBar::chunk`` keine gesperrte Regel hatte. Genau diese
    Lücke findet keine Prüfung der Palettenwerte — nur ein Referenzvergleich:
    dasselbe Widget zweimal gerendert, einmal bedienbar, einmal gesperrt, und
    die bernsteinartigen Punkte gezählt. Vorher 2018 gegen 2018, pixelgleich.

    Gesucht wird nach **Farbton**, nicht nach dem Hexwert: Fusion hellt und
    dunkelt den Akzent beim Zeichnen ab, und eine Suche nach ``#f0a54a`` fand
    deshalb null Punkte auf einem Balken, der sichtbar bernsteinfarben war.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QProgressBar, QVBoxLayout, QWidget

    from app.ui.theme import apply_theme

    application = QApplication.instance()
    assert application is not None
    apply_theme(application, theme)  # type: ignore[arg-type]

    def amber_pixels(enabled: bool) -> int:
        host = QWidget()
        layout = QVBoxLayout(host)
        bar = QProgressBar(host)
        bar.setRange(0, 100)
        bar.setValue(60)
        bar.setEnabled(enabled)
        layout.addWidget(bar)
        host.resize(240, 50)
        host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        host.show()
        image = host.grab().toImage()
        found = 0
        for y in range(image.height()):
            for x in range(image.width()):
                hue, saturation, value, _alpha = QColor(image.pixel(x, y)).getHsv()
                if 20 <= hue <= 50 and saturation >= 60 and value >= 90:
                    found += 1
        host.close()
        return found

    usable = amber_pixels(True)
    locked = amber_pixels(False)
    # Das Thema gehört der Anwendung und nicht diesem Test: er hat sie
    # umgeschaltet, also stellt er den Ausgangszustand wieder her. Sonst läuft
    # der nächste Test in derselben Prozessinstanz im hellen Thema weiter, und
    # welcher das ist, entscheidet die Sammelreihenfolge.
    apply_theme(application, "dark")  # type: ignore[arg-type]

    assert usable > 100, f"{theme}: der bedienbare Balken trägt keinen Akzent ({usable} Punkte)"
    assert locked == 0, f"{theme}: der gesperrte Balken trägt ihn weiter ({locked} Punkte)"


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_primary_button_gives_way_when_pressed(theme: str, qt_app: object) -> None:
    """Der lauteste Knopf der Anwendung war der einzige ohne Rückmeldung.

    Die Regel dafür gab es — sie nahm nur ``accent_line``, und die *ist* im
    dunklen Thema der Bernstein selbst: gedrückt sah aus wie losgelassen, im
    voreingestellten Thema, auf jedem Hauptknopf. Im hellen fiel es nie auf,
    weil dort der abgedunkelte Ton steht. Genau deshalb wird hier über **beide**
    Themen geprüft und am Bild, nicht am Stylesheet-Text: dass eine Regel
    dasteht, heißt nicht, dass sie etwas ändert.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

    from app.ui.style import make_primary
    from app.ui.theme import apply_theme

    application = QApplication.instance()
    assert application is not None
    apply_theme(application, theme)  # type: ignore[arg-type]

    def loudest_amber(pressed: bool) -> str | None:
        host = QWidget()
        layout = QVBoxLayout(host)
        button = make_primary(QPushButton("Bohrung setzen", host))
        layout.addWidget(button)
        host.resize(200, 50)
        host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        host.show()
        if pressed:
            button.setDown(True)
        image = host.grab().toImage()
        tally: dict[str, int] = {}
        for y in range(image.height()):
            for x in range(image.width()):
                colour = QColor(image.pixel(x, y))
                hue, saturation, _value, _alpha = colour.getHsv()
                if 20 <= hue <= 50 and saturation >= 60:
                    tally[colour.name()] = tally.get(colour.name(), 0) + 1
        host.close()
        return max(tally, key=lambda name: tally[name]) if tally else None

    resting = loudest_amber(False)
    pressed = loudest_amber(True)
    apply_theme(application, "dark")  # type: ignore[arg-type]

    assert resting, f"{theme}: der Hauptknopf trägt keinen Akzent"
    assert pressed != resting, f"{theme}: gedrückt sieht aus wie losgelassen ({resting})"


def test_no_progress_bar_prints_its_number_over_the_moving_edge() -> None:
    """Die Zahl stand mittig, und der Rand der Füllung wanderte darunter durch.

    Bei 45 % lag sie halb auf Bernstein und halb auf der Spur, ab 60 % ganz auf
    Bernstein — mit 1,69 Kontrast, also unlesbar. Eine Farbe, die auf beiden
    Gründen trägt, gibt es nicht, und eine dunklere Füllung nähme dem Balken
    den Akzent: 4,5 Schriftkontrast kostet die Hälfte des Flächenkontrasts,
    nachgerechnet. Der Prozentwert steht deshalb neben dem Balken.

    Geprüft an der Quelle, weil die vier Balken in vier Dateien entstehen und
    ein neuer sonst stillschweigend wieder eine Zahl mitbringt.
    """
    offenders = []
    for path in sorted(UI.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "QProgressBar(" not in source:
            continue
        if "setTextVisible(False)" not in source:
            offenders.append(path.name)

    assert not offenders, (
        f"Diese Balken schreiben ihre Zahl über die Füllung: {offenders}. "
        "setTextVisible(False), und der Prozentwert daneben."
    )


def test_hover_and_focus_are_not_the_same_thing_on_a_tile() -> None:
    """Beide sagten es über den Rahmen, in derselben Farbe.

    Im dunklen Thema — dem voreingestellten — ist ``highlight`` derselbe
    Bernstein wie der Fokusring: Überfahren setzte ``border-color: highlight``,
    Fokus ``border: 2px solid focus``, und die zwei Zustände unterschieden sich
    um einen Bildpunkt Rahmenbreite. Wer mit dem Tabulator durch die neun
    Kacheln des Startbildschirms geht, sah nicht, welche die Eingabetaste
    auslösen würde.

    Überfahren wechselt jetzt die **Fläche**, Fokus den **Rahmen** — zwei
    Kodierungen für zwei Zustände (Regel 18).
    """
    from app.ui.style import stylesheet
    from app.ui.theme import THEMES

    for theme in ("dark", "light"):
        sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
        hover = next(line for line in sheet.splitlines() if "#exampleTile:hover" in line)
        focus = next(line for line in sheet.splitlines() if "#exampleTile:focus" in line)
        assert "border" not in hover, f"{theme}: das Überfahren spricht über den Rahmen: {hover}"
        assert "background" in hover, f"{theme}: das Überfahren sagt gar nichts: {hover}"
        assert "border" in focus, f"{theme}: der Fokus sagt nichts über den Rahmen: {focus}"

    # Und der Anlass, damit dieser Test seinen Grund behält: die zwei Farben
    # sind im dunklen Thema wirklich dieselbe.
    assert THEMES["dark"]["highlight"] == THEMES["dark"]["accent_line"], (
        "wenn die Farben auseinandergehen, darf dieser Test neu begründet werden"
    )


def _popup_room(application: object, sheet: str, entries: int) -> tuple[int, int]:
    """Öffnet eine fokussierte Combobox und misst Platz gegen Bedarf.

    Zurück kommt, was der Rollbereich des Aufklappmenüs hoch ist, und was seine
    Zeilen zusammen brauchen. Der Fokus gehört dazu: Ohne ihn rechnet Qt
    richtig, und der Fehler, um den es hier geht, wäre unsichtbar.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel

    application.setStyleSheet(sheet)  # type: ignore[attr-defined]
    dialog = QDialog()
    form = QFormLayout(dialog)
    box = QComboBox(dialog)
    box.addItems([f"Eintrag {number}" for number in range(entries)])
    form.addRow(QLabel("Bezugspunkt"), box)
    dialog.show()
    box.setFocus(Qt.FocusReason.MouseFocusReason)
    application.processEvents()  # type: ignore[attr-defined]

    box.showPopup()
    application.processEvents()  # type: ignore[attr-defined]
    view = box.view()
    room = view.viewport().height()
    needed = sum(view.sizeHintForRow(row) for row in range(entries))
    box.hidePopup()
    dialog.close()
    return room, needed


def test_an_open_combo_box_shows_every_entry_it_has(qt_app: object) -> None:
    """Der Fokusrahmen darf nicht breiter werden — sonst fehlt ein halber Eintrag.

    Gemeldet als „viele Comboboxen haben ein Problem beim Aufklappen": Im
    Bohrdialog stand unter dem hervorgehobenen „Mündung" ein waagerecht
    durchgeschnittenes „Mitte".

    Die Ursache lag im Stylesheet und nicht im Dialog. ``QComboBox:focus`` gab
    dem Rahmen einen zweiten Punkt, der Innenabstand nahm einen zurück, damit
    die Box nicht springt — und Qt leitet die Höhe des Aufklappmenüs aus dem
    **Innenrechteck** der Combobox ab. Es verlor damit zwei Punkte, kippte in
    den Rollbetrieb und verlor an dessen zwei Pfeilen zehn weitere. Zwölf
    Punkte sind ein halber Eintrag, und getroffen hat es jede Combobox mit
    Tastaturfokus — also jede, die man anklickt.

    Die Gegenprobe dazu steht darunter in einem eigenen Test: Sie ist an
    Windows gebunden, diese Zusicherung hier gilt überall.
    """
    from app.ui.style import arrow_files, stylesheet

    sheet = stylesheet("dark", 10, arrow_files("dark"))
    for entries in (2, 3):
        room, needed = _popup_room(qt_app, sheet, entries)
        assert room >= needed, (
            f"{entries} Einträge: das Aufklappmenü hat {room} px für {needed} px Zeilen — "
            "unten fehlt ein angeschnittener Eintrag"
        )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Der Rechenfehler ist auf Windows gemessen; unter Linux tritt er nicht auf",
)
def test_the_widened_focus_ring_would_still_cut_the_popup(qt_app: object) -> None:
    """Die Gegenprobe zum Test darüber — sonst prüft der eines Tages nichts mehr.

    Er wäre auch dann grün, wenn Qt gar nicht mehr falsch rechnen könnte, und
    damit hätte die Regel „konstante Rahmenbreite" ihren Grund verloren, ohne
    dass es jemand merkt. Hier steht deshalb die alte Regel noch einmal und
    muss den Eintrag abschneiden.

    **Und sie gilt nur für Windows.** Der Lauf auf ubuntu-latest hat sie am
    24.08.2026 fallen lassen: 44 px für 44 px Zeilen, der breitere Rahmen
    schnitt dort nichts ab. Auf Windows tut er es unverändert, mit PySide6
    6.11.1 wie mit 6.11.2 — offscreen gemessen und im gebauten Bohrdialog
    nachgesehen. Der Unterschied liegt also am Betriebssystem und nicht an der
    Qt-Version, was der erste Verdacht war.

    Ausgeliefert wird für beide (§40), und die Regel bleibt für beide: Sie ist
    unter Linux nicht *nötig*, aber auch nicht falsch, und ein Stylesheet, das
    je Plattform andere Rahmenbreiten setzt, wäre der schlechtere Tausch. Fällt
    diese Zusicherung eines Tages **unter Windows**, hat Qt seine Rechnung
    geändert; dann braucht sie eine neue Begründung — die Regel darüber nicht.
    """
    from app.ui.style import arrow_files, stylesheet

    sheet = stylesheet("dark", 10, arrow_files("dark"))
    widened = sheet + (
        "\nQLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit "
        f"{{ border: 1px solid {THEMES['dark']['line']}; padding: {TIGHT}px {NORMAL}px; }}\n"
        "QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, "
        "QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus "
        f"{{ border: 2px solid {THEMES['dark']['accent_line']}; "
        f"padding: {TIGHT - 1}px {NORMAL - 1}px; }}\n"
    )
    short, wanted = _popup_room(qt_app, widened, 2)
    qt_app.setStyleSheet(sheet)  # type: ignore[attr-defined]
    assert short < wanted, (
        "der breitere Fokusrahmen schneidet das Aufklappmenü nicht mehr ab — "
        f"{short} px für {wanted} px. Qt rechnet unter Windows anders als "
        "gemessen; diese Gegenprobe braucht dann eine neue Begründung"
    )


#: Rahmenbreite und Strichart einer Stylesheet-Regel.
_BORDER = re.compile(r"border:\s*(\d+)px\s+(\w+)")


def _field_border(sheet: str, state: str) -> tuple[int, str]:
    """Breite und Strichart des Feldrahmens in diesem Zustand.

    Nennt die Zustandsregel keinen ganzen Rahmen — sie darf sich auf
    ``border-color`` beschränken —, gilt der Ruhezustand weiter. Das ist keine
    Feinheit: Ohne diesen Rückfall prüfte der Breitentest darüber wieder die
    **Bauart** („in der Fokusregel steht ein ``border:``") statt der Zusage
    („die Breite ändert sich nicht"), und eine zulässige Schreibweise wäre rot.
    """
    rest = sheet.split("QLineEdit, QSpinBox")[1].split("}")[0]
    grund = _BORDER.search(rest)
    assert grund, f"die Grundregel der Eingabefelder nennt keinen Rahmen: {rest.strip()}"
    if state != "focus":
        return int(grund.group(1)), grund.group(2)
    rule = sheet.split("QLineEdit:focus")[1].split("}")[0]
    found = _BORDER.search(rule)
    if found is None:
        return int(grund.group(1)), grund.group(2)
    return int(found.group(1)), found.group(2)


def test_the_focus_ring_never_changes_the_size_of_a_field() -> None:
    """Der Fokus darf alles am Rahmen ändern, nur nicht seine Breite.

    Daran hängt das Aufklappmenü jeder Combobox: Qt leitet dessen Höhe aus dem
    Innenrechteck ab, und ein Punkt mehr Rahmen kostet einen halben Eintrag.

    **Geprüft wird die Zusage, nicht die Bauart.** Die erste Fassung verlangte,
    dass in der Fokusregel überhaupt kein ``border:`` steht — das war die
    damalige Umsetzung und nicht die Sache. Als der Ring eine Strichart bekam
    (Regel 18, siehe unten), wurde dieser Test rot, ohne dass die Zusage
    verletzt war: Er hätte eine Verbesserung aufgehalten. Verglichen werden
    jetzt die Breiten.
    """
    from app.ui.style import stylesheet

    for theme in THEMES:
        sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
        ruhe, _ = _field_border(sheet, "rest")
        fokus, _ = _field_border(sheet, "focus")
        assert fokus == ruhe, (
            f"{theme}: der Rahmen wächst im Fokus von {ruhe} auf {fokus} Punkte — "
            "damit verliert das Aufklappmenü jeder Combobox einen halben Eintrag"
        )
        rule = sheet.split("QLineEdit:focus")[1].split("}")[0]
        assert "padding" not in rule, (
            f"{theme}: die Fokusregel rührt den Innenabstand an ({rule.strip()}) — "
            "das ist die Kompensation, die es ohne Breitenwechsel nicht braucht"
        )


def test_the_focus_says_it_twice_and_not_only_in_colour() -> None:
    """Regel 18 gilt auch für den Tastaturfokus.

    Nachdem die Breite konstant sein musste (siehe oben) und der Ruherahmen
    seine volle Farbe behalten musste (siehe unten), blieb dem Fokus nur noch
    der Farbton — eine Bedeutung allein über Farbe. Das Gegenargument war, ein
    Punkt Rahmenbreite sei ohnehin nie eine wahrnehmbare Kodierung gewesen; es
    stimmt und trägt trotzdem nicht, denn die Regel verlangt die zweite
    Kodierung und nicht den Nachweis, dass die alte auch keine war.

    Die Strichart ist die dritte Möglichkeit neben Breite und Farbe, und sie
    lässt die Geometrie in Ruhe — gemessen blieb das Combobox-Popup bei 48 von
    48 Punkten. Dieselbe Wahl trägt der Reiter schon.
    """
    from app.ui.style import stylesheet

    for theme in THEMES:
        sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
        _, ruhe = _field_border(sheet, "rest")
        _, fokus = _field_border(sheet, "focus")
        assert fokus != ruhe, (
            f"{theme}: Ruhe und Fokus zeichnen beide {ruhe} — dann unterscheidet sie "
            "nur die Farbe, und Regel 18 verlangt eine zweite Kodierung"
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_field_keeps_the_edge_that_is_its_only_one(theme: str) -> None:
    """Der Rahmen eines Eingabefelds wird nicht gedämpft.

    Er ist die **einzige** Kante des Feldes: Die Fläche trägt die Grenze nicht
    mit, gemessen 1,45 im dunklen und 1,22 im hellen Thema — wer den Rahmen
    leiser macht, nimmt dem Feld seinen Umriss.

    Das ist keine theoretische Sorge. Als der Rahmen von einem auf zwei Punkte
    ging (das Aufklappmenü der Combobox hängt daran), lag es nahe, die Farbe
    zur Feldfläche hin zu mischen, damit die doppelte Breite so leise wirkt wie
    vorher. Im Bild sah das richtig aus und war gemessen falsch: 1,90 statt
    3,33 im dunklen Thema, also unter den 3,0, die WCAG 1.4.11 für die
    Umrandung eines Bedienelements verlangt.

    Geprüft wird gegen die **Linienfarbe des Themas** und nicht gegen 3,0: Was
    diese Farbe leistet, ist eine Frage an das Thema; dass der Rahmen sie nicht
    unterschreitet, ist eine an das Stylesheet. Zwei Fragen, zwei Orte.
    """
    from app.ui.theme import contrast_ratio

    colours = THEMES[theme]  # type: ignore[index]
    sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
    rule = sheet.split("QLineEdit, QSpinBox")[1].split("}")[0]
    found = re.search(r"border:\s*\d+px solid (#[0-9a-fA-F]{6})", rule)
    assert found, f"{theme}: die Grundregel der Eingabefelder nennt keine Rahmenfarbe: {rule}"

    drawn = contrast_ratio(found.group(1), colours["base"])
    intended = contrast_ratio(colours["line"], colours["base"])
    assert drawn >= intended, (
        f"{theme}: der Feldrahmen bringt {drawn:.2f} auf der Feldfläche, die Linienfarbe "
        f"des Themas {intended:.2f} — gedämpft verliert das Feld seine einzige Kante"
    )


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a_scrollbar_handle_can_be_grabbed_in_both_directions(theme: str) -> None:
    """``min-height`` wirkt nur senkrecht — der waagerechte Griff braucht sein
    eigenes Mindestmaß.

    Gemessen an einer Fläche von 296 Punkten über einem Inhalt von 30 000: Der
    Griff war **zwei Punkte** breit, also weder zu sehen noch mit der Maus zu
    treffen; mit ``min-width`` sind es 16. Die Zahl gehört zu einer echten
    Lage — bei einem milderen Verhältnis (4000 zu 300) ist der Griff ohnehin
    21 Punkte breit, und die erste Messung sah deshalb keinen Unterschied.
    """
    sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
    rule = sheet.split("QScrollBar::handle {")[1].split("}")[0]
    for side in ("min-height", "min-width"):
        found = re.search(rf"{side}:\s*(\d+)px", rule)
        assert found and int(found.group(1)) >= 16, (
            f"{theme}: {side} fehlt oder ist zu klein — {rule}"
        )


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_slider_wears_the_theme_and_shows_when_it_is_locked(theme: str) -> None:
    """Der Regler war das letzte Bedienelement ohne eigene Form.

    Gemessen am **Einbauort** — dem Schnittregler der Werkzeugleiste, den ein
    Kunde wirklich zieht, nicht an einem freistehenden Widget: Er trug in
    beiden Themen dieselben einundzwanzig Farben (#454545, #1e1e1e, #626262),
    und keine davon steht in ``theme.py``. Das waren Qts Vorgaben, also ein
    kantiges Rechteck im dunklen und ein weißer Kreis im hellen Thema. Nach
    der Regel unterscheiden sich die Farben zwischen den Themen.

    Drei Regler hängen daran (Schnittebene, Schichthöhe, Explosionsweite), und
    alle drei werden **gezogen** — deshalb prüft der Test auch die Größe des
    Griffs: Ein Ziel von zehn Punkten trifft niemand zuverlässig.
    """
    sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
    assert "QSlider::handle:horizontal {" in sheet, f"{theme}: der Regler hat keine eigene Form"

    rule = sheet.split("QSlider::handle:horizontal {")[1].split("}")[0]
    width = re.search(r"width:\s*(\d+)px", rule)
    assert width and int(width.group(1)) >= 12, (
        f"{theme}: der Griff ist zu klein zum Ziehen: {rule}"
    )

    # Gesperrt heißt gesperrt: Ein Regler, den nichts bewegt, darf nicht
    # aussehen wie einer, der sich ziehen lässt.
    assert "QSlider::handle:horizontal:disabled" in sheet, (
        f"{theme}: gesperrt sieht aus wie bedienbar"
    )
    # Und der zurückgelegte Teil sagt, wo der Wert steht — dieselbe Aussage
    # wie beim Fortschrittsbalken, in derselben Farbe.
    assert "QSlider::sub-page:horizontal {" in sheet, f"{theme}: der Regler zeigt seinen Wert nicht"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a_splitter_shows_that_it_can_be_dragged(theme: str) -> None:
    """Die Fuge trug die Fensterfarbe — Kontrast 1,00 gegen ihre Umgebung.

    Dass sich die Spalten verschieben lassen, erfuhr damit nur, wer zufällig
    mit der Maus darüberfuhr: Erst beim Überfahren nahm der Griff den Akzent.
    Für einen Kunden ohne CAD-Gewohnheiten ist das eine Entdeckung, die
    ausbleibt.

    Gemessen am gebauten Splitter, Griff ausgeschnitten: 2,11 im dunklen und
    1,84 im hellen Thema gegen das Fenster. Die Linie ist schmal — acht
    Punkte Trennfarbe zwischen zwei Panels wären ein Balken statt einer Fuge.
    """
    sheet = stylesheet(theme, 10)  # type: ignore[arg-type]
    for direction in ("horizontal", "vertical"):
        rule = sheet.split(f"QSplitter::handle:{direction} {{")[1].split("}")[0]
        assert "qlineargradient" in rule, (
            f"{theme}: die {direction}e Fuge ist einfarbig und damit unsichtbar: {rule}"
        )
        assert THEMES[theme]["line"] in rule, (  # type: ignore[index]
            f"{theme}: die Fuge nimmt nicht die Trennfarbe des Themas: {rule}"
        )


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_number_field_and_the_combo_box_can_be_hit(theme: str) -> None:
    """Auf und Ab am Zahlenfeld waren rund zehn auf elf Punkte groß.

    Die zwei Knöpfe teilen sich die Feldhöhe, also ist ihre Höhe gegeben —
    zu holen war die Breite, und ``subcontrol-origin: border`` legte sie
    zusätzlich auf den Feldrahmen, sodass ihre eigene Trennkante darunter
    verschwand. Man sah zwei Pfeile ohne erkennbare Flächen.

    Dieselbe Kante bekommt das Pfeilfeld der Combobox: Ohne eigene Regel
    zeichnet Qt es als Rechteck bis an den Rahmen und schneidet die Rundung
    von innen an.

    **Und wer ein Unterelement gestaltet, verliert Qts Zeichnung darin** —
    die Falle, die dieselbe Datei für das Zahlenfeld beschreibt und die hier
    prompt wieder zuschnappte: Nach der ``drop-down``-Regel standen im
    Pfeilfeld nur noch zwei Farben (Fläche und Trennlinie), gemessen gegen
    vierzehn davor. Der Pfeil kommt deshalb aus derselben Quelle wie der des
    Zahlenfelds — und trägt seither die Textfarbe des Themas statt Qts Grau.
    """
    from app.ui.style import WIDE

    arrows = {"up": "up.svg", "down": "down.svg"}
    sheet = stylesheet(theme, 10, arrows)  # type: ignore[arg-type]

    button = sheet.split("QSpinBox::up-button, QDoubleSpinBox::up-button,")[1].split("}")[0]
    width = re.search(r"width:\s*(\d+)px", button)
    assert width and int(width.group(1)) >= WIDE, f"{theme}: die Auf/Ab-Fläche ist zu schmal"
    assert "subcontrol-origin: padding" in button, (
        f"{theme}: die Knöpfe liegen auf dem Feldrahmen, ihre Trennkante verschwindet darunter"
    )

    assert "QComboBox::drop-down {" in sheet, f"{theme}: das Pfeilfeld schneidet die Ecke an"
    assert "QComboBox::down-arrow {" in sheet, (
        f"{theme}: die Combobox hat ein gestaltetes Pfeilfeld und keinen Pfeil mehr darin"
    )


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a_locked_control_looks_locked_and_a_button_looks_like_one(theme: str) -> None:
    """Zwei Zustände, die man nicht sah.

    Der Werkzeugknopf trug im Ruhezustand eine **durchsichtige** Kante — in
    der Bewegen-Karte stehen drei Modusknöpfe nebeneinander, und nur der
    gewählte hatte eine Fläche; die anderen beiden las man als Beschriftungen.
    Und für das Ankreuzfeld gab es gar keine Regel: Qt zeichnet das Kästchen
    dann in beiden Zuständen gleich, während nur die Beschriftung daneben
    verblasst — ein Haken, der gesetzt aussieht und sich nicht setzen lässt.
    """
    sheet = stylesheet(theme, 10)  # type: ignore[arg-type]

    resting = sheet.split("QToolButton {")[1].split("}")[0]
    assert "transparent" not in resting, (
        f"{theme}: der Werkzeugknopf ist im Ruhezustand rahmenlos: {resting}"
    )
    # **Und die Kante ist zu sehen.** Der erste Anlauf nahm die leisere
    # Zebrafarbe und kam damit auf 1,13 im dunklen und 1,01 im hellen Thema —
    # eine Kante, die es gibt und die niemand sieht; gemessen hat es die
    # Nachbarsitzung am gerenderten Knopf. Geprüft wird gegen die
    # Linienfarbe des Themas, wie beim Feldrahmen: Was sie leistet, ist eine
    # Frage an das Thema, dass der Knopf sie nicht unterschreitet, eine an
    # das Stylesheet.
    from app.ui.theme import contrast_ratio

    colours = THEMES[theme]  # type: ignore[index]
    found = re.search(r"border:\s*1px solid (#[0-9a-fA-F]{6})", resting)
    assert found, f"{theme}: die Ruhekante nennt keine Farbe: {resting}"
    drawn = contrast_ratio(found.group(1), colours["window"])
    intended = contrast_ratio(colours["line"], colours["window"])
    assert drawn >= intended, (
        f"{theme}: die Knopfkante bringt {drawn:.2f} auf der Dialogfläche, die "
        f"Linienfarbe des Themas {intended:.2f} — leiser ist sie keine Kante mehr"
    )

    for control in ("QCheckBox", "QRadioButton"):
        assert f"{control}::indicator:disabled" in sheet, (
            f"{theme}: {control} sieht gesperrt aus wie bedienbar"
        )
