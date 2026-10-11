"""Themenkontrast und Farbpalette (Bauplan §19.1, §19.3). Die Suche *Funktion suchen*:
``tests/test_search.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

import app
from app.ui.theme import THEMES, contrast_ratio, viewport_colours

#: WCAG AA for body text.
MINIMUM_CONTRAST = 4.5


@pytest.mark.parametrize("theme", list(THEMES))
def test_text_has_enough_contrast_in_both_themes(theme: str) -> None:
    """§19.3: ausreichender Kontrast im hellen und im dunklen Thema."""
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["text"], colours["window"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["text"], colours["base"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["highlight_text"], colours["highlight"]) >= 3.0


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_severity_reads_on_the_surface_it_is_written_on(theme: str) -> None:
    """Der Prüfbericht schreibt jede Zeile in der Farbe ihres Schweregrads.

    Die Rollenfarben sind für den dunklen Untergrund gewählt, auf dem die
    Anwendung startet. Auf der weißen Liste des hellen Themas brachten sie
    2,22 (Warnung), 2,67 (Hinweis) und 3,97 (Fehler) — die zentrale Ansicht der
    Anwendung stand vollständig unter der Lesbarkeitsgrenze. Geprüft hat das
    niemand: die Kontrasttests hier kannten nur die Themenfarben, und die
    Rollenfarben lagen daneben in einer eigenen Datei.
    """
    from app.ui.palette import text_colour

    surface = THEMES[theme]["base"]  # type: ignore[index]
    for role in ("info", "warning", "error"):
        ratio = contrast_ratio(text_colour(role, surface), surface)  # type: ignore[arg-type]
        assert ratio >= MINIMUM_CONTRAST, (
            f"{role} bringt auf {surface} nur {ratio:.2f} — ein Befund, den man nicht liest."
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_focus_ring_is_visible_on_its_own_background(theme: str) -> None:
    """Wer ohne Maus arbeitet, sieht nur den Fokusring.

    Er nahm ``highlight``, und der Bernstein bringt gegen das helle Fenster
    1,70 und gegen ein weißes Feld 2,06. WCAG 1.4.11 verlangt 3,0 für die
    Umrandung eines Bedienelements — im hellen Thema war der Ring praktisch
    nicht da. Er nimmt jetzt ``accent_line``, die für genau diese Rechnung
    schon je Thema abgestuft war.
    """
    colours = THEMES[theme]  # type: ignore[index]
    for surface in ("base", "window"):
        ratio = contrast_ratio(colours["accent_line"], colours[surface])
        assert ratio >= 3.0, f"Fokusring auf {surface}: {ratio:.2f}"


@pytest.mark.parametrize("theme", list(THEMES))
def test_quiet_text_stays_readable_and_locked_text_looks_locked(theme: str) -> None:
    """Zwei Aufgaben, zwei Farben.

    ``disabled`` versorgte beide: den Sperrzustand *und* jeden Nebentext —
    Maße, Einheiten, Spaltenköpfe, Gruppentitel, den stillen Reiter. Damit war
    beides falsch. Ein Fünftel aller Beschriftungen kam im hellen Thema auf
    2,59 Kontrast, und ein gesperrter Knopf unterschied sich farblich nicht von
    einem Spaltenkopf, der nie bedienbar war.
    """
    colours = THEMES[theme]  # type: ignore[index]
    for surface in ("window", "base"):
        quiet = contrast_ratio(colours["muted"], colours[surface])
        assert quiet >= MINIMUM_CONTRAST, (
            f"Nebentext auf {surface}: {quiet:.2f} — leise heißt nicht unlesbar."
        )

    assert colours["muted"] != colours["disabled"], (
        "Eine Farbe für zwei Aussagen ist für beide die falsche."
    )
    assert (
        contrast_ratio(colours["text"], colours["window"])
        > contrast_ratio(colours["muted"], colours["window"])
        > contrast_ratio(colours["disabled"], colours["window"])
    ), (
        "Die Reihenfolge muss stimmen: Haupttext lauter als Nebentext, Nebentext lauter "
        "als Gesperrtes."
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_locked_control_looks_locked_in_every_role(theme: str) -> None:
    """Gesperrt ist ein Zustand, den man sehen muss.

    Die Palette setzte ihn für ``Text`` und ``ButtonText`` — nicht für
    ``WindowText``. Daran hängen genau die Elemente, die das Stylesheet nicht
    anfasst: QLabel, QCheckBox, QRadioButton, QGroupBox. Ein gesperrtes
    Ankreuzfeld war pixelgleich mit einem bedienbaren; „Scheibe" in der
    Schnittleiste und „Projektdatei anhängen" im Fehlerbericht sahen
    anklickbar aus und waren es nicht.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    palette = build_palette(theme)  # type: ignore[arg-type]
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        locked = palette.color(QPalette.ColorGroup.Disabled, role).name()
        usable = palette.color(QPalette.ColorGroup.Active, role).name()
        assert locked != usable, f"{role.name}: gesperrt sieht aus wie bedienbar"


def test_the_palette_leaves_no_role_to_the_system() -> None:
    """Was hier nicht gesetzt wird, kommt vom Betriebssystem.

    ``PlaceholderText`` stand als einzige Rolle nicht in der Palette. Auf einem
    Rechner mit dunkel eingestelltem Windows war er hell — und im hellen Thema
    damit weiß auf Weiß. Dreizehn Felder tragen ihre Auskunft dort: das
    Suchfeld des Prüfberichts stand leer da, der Chat fragte nichts mehr, und
    im Schlüsseldialog fehlte das Muster, das als Einziges sagt, wie ein
    Lizenzschlüssel aussieht.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    for theme in THEMES:
        palette = build_palette(theme)  # type: ignore[arg-type]
        placeholder = palette.color(QPalette.ColorRole.PlaceholderText).name()
        base = THEMES[theme]["base"]  # type: ignore[index]
        assert contrast_ratio(placeholder, base) >= 3.0, (
            f"{theme}: Platzhalter {placeholder} auf {base} — man sieht ihn nicht."
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_links_are_readable_and_follow_the_theme(theme: str) -> None:
    """Links bleiben auf Fenster und Feld lesbar, auch nach einem Besuch.

    Qt nahm dafür die Systempalette. Unter Windows war deren helle Linkfarbe
    im hellen Thema fast weiß auf hellgrau — gerade die Sicherheitsmeldung im
    Über-Dialog verlor damit ihren einzigen sichtbaren Weg.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    colours = THEMES[theme]  # type: ignore[index]
    palette = build_palette(theme)  # type: ignore[arg-type]
    for surface in ("window", "base"):
        ratio = contrast_ratio(colours["link"], colours[surface])
        assert ratio >= MINIMUM_CONTRAST, f"{theme}: Link auf {surface}: {ratio:.2f}"

    for role in (QPalette.ColorRole.Link, QPalette.ColorRole.LinkVisited):
        assert palette.color(role).name() == colours["link"]
        assert palette.color(QPalette.ColorGroup.Disabled, role).name() == colours["disabled"], (
            f"{theme}: ein gesperrter Link sieht für {role.name} weiter bedienbar aus"
        )


def test_no_fill_colour_is_used_as_text() -> None:
    """Eine Füllfarbe füllt, sie schreibt nicht.

    ``ROLES`` sind **Flächenfarben** — Auswahlbalken, gewählter Körper,
    Schichtkarten. Als Schriftfarbe auf der Dialogfläche halten sie die
    Schwelle nicht: ``select`` bringt im hellen Thema 1,70, WCAG AA verlangt
    4,5 für Text.

    **Zwei Stellen sind darauf hereingefallen, und beide plausibel.** Der
    Suchtreffer der Druckeinstellungen färbte die gefundene Zeile mit
    ``select`` — ausgerechnet die gesuchte war damit die am schlechtesten
    lesbare des Dialogs. Die Ringlegende der Analyseleiste nahm die Farben der
    3D-Karten, zwischen 1,82 und 3,26.

    Und der naheliegende Ausweg trägt nicht: ``accent_line``, auf das der
    Fokusring umgestellt wurde, bringt 3,01 — das ist die Schwelle für die
    **Umrandung** eines Bedienelements (WCAG 1.4.11), nicht für Text. Wer eine
    Zahl aus einem benachbarten Test übernimmt, übernimmt womöglich die falsche
    Regel dazu.

    Was trägt, ist eines von beiden: die Rolle als Fläche benutzen und die
    dafür deklarierte Schriftfarbe darauf (7,93 in beiden Themen), oder ein
    Farbfeld neben regulärem Text — dann zeigt die Oberfläche die Farbe, statt
    sie lesen zu lassen, und die Bedeutung hängt nicht mehr allein an ihr
    (Regel 18).

    Geprüft wird der Quelltext und nicht die laufende Oberfläche: Ein
    Stilblatt, das nur in einer bestimmten Lage gesetzt wird, erwischt kein
    Fenstertest zuverlässig.
    """
    import re

    ui = Path(app.__file__).parent / "ui"
    # ``color:`` mit einem Wert aus ROLES — nicht ``background``, nicht
    # ``border``: Für Flächen ist die Farbe richtig, für Rahmen gilt eine
    # andere Schwelle (3,0), und beide prüfen eigene Tests.
    pattern = re.compile(r"[^-\w]color:\s*\{ROLES\[")
    paths = sorted(ui.rglob("*.py"))
    assert ui / "viewport.py" in paths and ui / "render" / "api.py" in paths
    guilty = [
        f"{path.relative_to(ui)}:{number}"
        for path in paths
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not guilty, (
        "Füllfarben aus ROLES als Schriftfarbe — auf hellem Grund unter der "
        "Lesbarkeitsschwelle:\n  " + "\n  ".join(guilty)
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_border_is_actually_visible(theme: str) -> None:
    """Ein Knopf ohne sichtbaren Rahmen ist kein Knopf, sondern Text.

    ``line`` trägt keine Schrift und muss deshalb nicht AA erfüllen — sie muss
    zu sehen sein. Der erste Anlauf nahm dafür ``alternate``, die Farbe der
    Zebrazeile: im dunklen Thema 1,05 gegen das Fenster, also nichts. Im Bild
    fiel genau das auf, und es fällt nur im Bild auf.
    """
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["line"], colours["window"]) >= 1.9
    assert contrast_ratio(colours["line"], colours["base"]) >= 1.9


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_flash_border_is_visible_on_the_surface_it_points_at(theme: str) -> None:
    """Ein Rahmen, der auf einen Bereich zeigt, muss zu sehen sein.

    Ein Tourschritt sagt „Sehen Sie links in den Verlauf" und lässt den Bereich
    eine Sekunde lang aufleuchten; derselbe Rahmen führt aus den
    Druckeinstellungen zum Filamentwähler. Die Farbe war ``ROLES['select']``
    direkt — Bernstein, gewählt für die dunkle Fläche, auf der die Anwendung
    startet. Dort trägt es 5,54, auf der hellen 1,70.

    Gefordert sind 3,0 (WCAG 1.4.11 für eine Umrandung), also weniger als für
    Schrift, und trotzdem um mehr als die Hälfte gerissen. Ein Rahmen, den man
    nicht sieht, zeigt auf nichts.

    Der Zwilling stand daneben schon gelöst: ``ROLES_ON_LIGHT`` dunkelt genau
    dafür ab, und der Kommentar darüber nennt Bernstein als schlechtesten Fall
    — nur stand es nicht in der Tabelle.
    """
    from app.ui.palette import text_colour

    for surface_name in ("window", "base"):
        surface = THEMES[theme][surface_name]  # type: ignore[index]
        ratio = contrast_ratio(text_colour("select", surface), surface)
        assert ratio >= 3.0, (
            f"der Rahmen bringt auf {surface_name} ({surface}) nur {ratio:.2f} — "
            "ein Aufleuchten, das niemand sieht"
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_drawing_grid_is_visible_without_shouting(theme: str) -> None:
    """Das Raster der Zeichenfläche wurde gezeichnet und war unsichtbar.

    ``sketch_editor._paint_grid`` nahm ``palette.mid()`` mit Alpha 60 und 140 —
    eine Rolle, die diese Tabelle nie gesetzt hat. Angekommen ist Qts Vorgabe
    ``#282828``, in beiden Themen dieselbe, und gemischt waren das **1,02** und
    **1,05** Kontrast gegen die dunkle Zeichenfläche. Gefangen wird darauf
    trotzdem: „Am Raster fangen" steht auf an, mit einem Millimeter Weite.

    Im hellen Thema war es der umgekehrte Fehler: 3,55 für die Hauptlinie, mehr
    als die Trennlinienfarbe des Themas selbst mitbringt.

    Geprüft wird deshalb nach oben **und** nach unten. Die Spanne ist weit genug
    für die Asymmetrie zwischen den Themen — dunkel steht auf 1,60 und 2,59,
    hell auf 1,35 und 2,0, weil derselbe Kontrastwert auf dunklem Grund
    schwächer liest — und eng genug, dass ein Griff in die Tabelle hier
    auffällt und nicht erst im Bild.
    """
    colours = THEMES[theme]  # type: ignore[index]
    minor = contrast_ratio(colours["grid_minor"], colours["base"])
    major = contrast_ratio(colours["grid_major"], colours["base"])
    assert 1.3 <= minor <= 1.8, f"{theme}: Nebenlinie {minor:.2f} — unsichtbar oder zu laut"
    assert 1.9 <= major <= 2.8, f"{theme}: Hauptlinie {major:.2f} — unsichtbar oder zu laut"
    assert major > minor, "jede fünfte Linie soll kräftiger sein, nicht schwächer"


def test_the_grid_reaches_the_canvas_through_the_palette() -> None:
    """Und die Zeichenfläche muss die Farben auch bekommen.

    Sie liest sie über ``Midlight`` und ``Mid``, nicht über eine eigene
    Konstante — sonst zieht ein Themenwechsel sie nicht mit. Genau dieser Weg
    war unterbrochen: die Rollen standen nicht in der Palette, und was nicht
    gesetzt ist, kommt vom Betriebssystem.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    for theme in THEMES:
        palette = build_palette(theme)  # type: ignore[arg-type]
        colours = THEMES[theme]  # type: ignore[index]
        assert palette.color(QPalette.ColorRole.Midlight).name() == colours["grid_minor"]
        assert palette.color(QPalette.ColorRole.Mid).name() == colours["grid_major"]


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_locked_surface_loses_the_accent_too(theme: str) -> None:
    """Gesperrt ist ein Zustand, den man sehen muss — auch an einer Fläche.

    Für die Schriftrollen stand das schon; ``Highlight`` fehlte. Fusion
    zeichnet damit die Rille des Reglers und den Fortschrittsbalken, und beide
    trugen gesperrt denselben vollen Bernstein: an einem Regler und einem
    Balken je zweimal gerendert und die Punkte gezählt — **2638 bedienbar,
    2638 gesperrt**, pixelgleich, in beiden Themen. Der Schnittregler ohne
    gewählte Achse sah dadurch bedienbar aus, obwohl ``SectionBar`` ihn
    abschaltet.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    palette = build_palette(theme)  # type: ignore[arg-type]
    locked = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight).name()
    usable = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight).name()
    assert locked != usable, "eine gesperrte Fläche trägt den Akzent weiter"
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(locked, colours["window"]) >= 1.5, (
        "gesperrt heißt leiser, nicht unsichtbar"
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_surfaces_stand_apart(theme: str) -> None:
    """Sieben Flächenrollen lagen in einem Helligkeitsband von 3,7 Punkten.

    Panel gegen Fenster 1,10, Zebrazeile gegen Panel 1,16, der Viewport-Verlauf
    1,21 — nichts trat vor oder zurück, und wer keine Auswahl getroffen hatte,
    sah ein einfarbiges Fenster. Die Schwellen unten halten den Abstand fest,
    damit er nicht Farbe für Farbe zurückrutscht.

    Sie sind je Thema verschieden, und das ist keine Nachlässigkeit: Was dunkel
    für Tiefe sorgt, macht hell aus dem Weiß ein schmutziges Grau.
    """
    colours = THEMES[theme]  # type: ignore[index]
    panel = 1.4 if theme == "dark" else 1.18
    zebra = 1.25 if theme == "dark" else 1.15
    assert contrast_ratio(colours["base"], colours["window"]) >= panel, (
        "das Panel muss sich vom Fenster lösen"
    )
    assert contrast_ratio(colours["alternate"], colours["base"]) >= zebra, (
        "die Zebrazeile muss eine sein"
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_accent_line_carries_on_its_own_window(theme: str) -> None:
    """Die Akzentkante — Fokusring, aktives Werkzeug, laufender Tourschritt —
    muss auf beiden Untergründen tragen; der Bernstein selbst bringt gegen das
    helle Fenster nur 1,37.
    """
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["accent_line"], colours["window"]) >= 3.0


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_viewport_follows_the_theme(theme: str) -> None:
    colours = viewport_colours(theme)  # type: ignore[arg-type]
    assert set(colours) == {"bottom", "top", "object", "bed", "bed_surface", "edge"}
    assert contrast_ratio(colours["object"], colours["bottom"]) >= 1.8, "a body stands out"
    # Der gefüllte Grund der Platte liegt zwischen Hintergrund und Raster: hebt
    # er sich von keinem der beiden ab, ist entweder die Platte unsichtbar oder
    # ihr Raster darauf.
    assert contrast_ratio(colours["bed"], colours["bed_surface"]) >= 1.4, (
        "das Raster muss auf seinem Grund zu sehen sein"
    )
    assert contrast_ratio(colours["bed_surface"], colours["bottom"]) >= 1.1, (
        "und der Grund gegen den Hintergrund"
    )
    # Eine Körperkante, die man suchen muss, hilft niemandem — dieselbe
    # Schwelle, die WCAG für lesbaren Text nennt, und aus demselben Grund.
    assert contrast_ratio(colours["edge"], colours["object"]) >= 4.0, (
        "die Kante muss sich vom Körper abheben"
    )


def test_the_two_themes_are_actually_different() -> None:
    assert THEMES["dark"]["window"] != THEMES["light"]["window"]
    assert contrast_ratio(THEMES["dark"]["window"], THEMES["light"]["window"]) > 5.0


def test_contrast_ratio_matches_the_known_extremes() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)


# --- Der Körper steht auf der Platte, nicht in ihr (B35) ---------------------


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_body_stands_out_from_the_bed(theme: str) -> None:
    """Ein Körper muss sich von der Druckplatte abheben — in beiden Themen.

    **B35 der Design-Durchsicht, und der Befund lag woanders als vermutet.**
    Notiert war „die Kanten sind im hellen Thema zu schwach"; gemessen standen
    die Kanten mit **4,45 gegen 4,47** in beiden Themen gleich gut da. Der
    Körper hob sich aber von der Plattenfläche nur mit **2,05** ab, im
    dunklen Thema mit 7,50 — er stand in der Platte statt auf ihr.

    Drei Zusagen, alle am dunklen Thema abgelesen, wo der Befund nie auftrat.
    Die Schwelle liegt bei 3,0 und nicht bei den 7,50 des dunklen Themas:
    Dort ist der Körper hell und die Platte sehr dunkel, im hellen Thema liegt
    er zwischen heller Platte und dunkler Kante. Durchgerechnet über alle vier
    Farben gemeinsam bleibt bei „>= 4,0" **keine** Kombination übrig.
    """
    colours = viewport_colours(theme)

    fläche = contrast_ratio(colours["object"], colours["bed_surface"])
    raster = contrast_ratio(colours["object"], colours["bed"])
    kante = contrast_ratio(colours["object"], colours["edge"])

    assert fläche >= 3.0, (
        f"{theme}: der Körper hebt sich mit {fläche:.2f} von der Plattenfläche ab "
        "— unter 3,0 wird er zur flachen Silhouette"
    )
    # Zwei statt drei: Das Raster ist eine Hilfslinie, keine Fläche — es muss
    # vom Körper unterscheidbar sein, nicht von ihm abstechen. Im dunklen Thema
    # sind es 3,39, im hellen ist bei 2,35 die Grenze dessen, was neben den
    # vier bestehenden Zusagen bleibt.
    assert raster >= 2.0, f"{theme}: der Körper hebt sich mit {raster:.2f} vom Plattenraster ab"
    assert kante >= 3.0, (
        f"{theme}: die Kante zeichnet den Körper mit {kante:.2f} — unter 3,0 verliert er seine Form"
    )


def test_the_bed_stays_behind_the_body() -> None:
    """Die Platte ist Kulisse und darf nicht lauter sein als der Körper.

    Sie war im hellen Thema das auffälligste Element im Bild: hell gerastert
    vor einem hellen Grund, während der Körper daneben verschwamm. Der Test
    hält die Rangfolge fest — wer die Platte wieder nach vorn holt, bekommt
    einen roten Lauf.
    """
    for theme in ("light", "dark"):
        colours = viewport_colours(theme)
        koerper = contrast_ratio(colours["object"], colours["bed_surface"])
        platte = contrast_ratio(colours["bed_surface"], colours["bottom"])
        assert koerper > platte, (
            f"{theme}: der Körper hebt sich mit {koerper:.2f} ab, die Platte mit "
            f"{platte:.2f} vom Grund — damit ist die Kulisse lauter als die Sache"
        )
