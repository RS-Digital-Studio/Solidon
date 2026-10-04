"""Alles, was aus dem Register erzeugt wird (Bauplan §10).

| Ausgabe                    | Abgeleitet aus                        |
|----------------------------|---------------------------------------|
| Menüeintrag und Dialog     | title, category, Parameterschema      |
| Kontextmenü                | applies_to                            |
| Palette und Kürzel         | title, doc, shortcut                  |
| Kommandozeile              | name, Parameterschema                 |
| Agenten-Werkzeugschema     | name, doc, JSON-Schema                |
| Dokumentationsabschnitt    | alles davon                           |

Nichts hier weiß von Qt: das sind Datenstrukturen, die eine Oberfläche
darstellt.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Container
from dataclasses import dataclass, replace
from typing import Any, Final

from app.core import figures, markup
from app.core.errors import AppError
from app.core.registry.params import condition_text, json_schema
from app.core.registry.registry import (
    CATEGORIES,
    FEATURE_TITLES,
    MENU_GROUPS,
    REGISTRY,
    VARIABLE,
    VARIANT_GROUPS,
    MenuSection,
    OperationSpec,
    Registry,
    group_title,
    in_the_menu_bar,
    menu_twins,
    twin_way,
    variant_members,
)
from app.core.types import ParamSpec
from app.i18n import TranslatableText, _, format_decimal, sort_key

#: Wie eine Seite heißt, in die eine Richtung zeigt — je Achse positiv, negativ.
#: Gemeinsam für Flächennamen, Rückfragen, Auswahlfelder und Handbuch.
SIDE_NAMES: Final[tuple[tuple[TranslatableText, TranslatableText], ...]] = (
    (_("Rechte Seite"), _("Linke Seite")),
    (_("Rückseite"), _("Vorderseite")),
    (_("Oberseite"), _("Unterseite")),
)

#: Auswahlwerte, die selbst kein Name sind. Der Schlüssel bleibt englisch, weil
#: er in der Projektdatei steht (§4.2); gezeigt wird der übersetzte Text. Was
#: schon ein Name ist — „M4", „PLA", „z" — steht hier nicht.
#: Wie ein Auswahlwert heißt, wenn er nicht schon sein eigener Name ist.
#:
#: Die Liste ist flach, und das ist eine Entscheidung: derselbe Schlüssel
#: bedeutet in dieser Anwendung überall dasselbe. Wo das einmal nicht mehr
#: stimmt, bekommt der Wert einen eigenen Schlüssel — nicht diese Liste eine
#: zweite Ebene.
_CHOICE_NAMES: dict[str, TranslatableText] = {
    "motedis-2020-b6": _("Motedis 2020 B-Typ, Nut 6"),
    "motedis-3030-b8": _("Motedis 3030 B-Typ, Nut 8"),
    "2020": _("2020 — ältere Vorgabe, Maße prüfen"),
    "3030": _("3030 — ältere Vorgabe, Maße prüfen"),
    "4040": _("4040 — ältere Vorgabe, Maße prüfen"),
    "relative": _("um"),
    "absolute": _("nach"),
    "feature": _("Merkmal"),
    "corner_000": _("Ecke links vorn unten"),
    "corner_001": _("Ecke links vorn oben"),
    "corner_010": _("Ecke links hinten unten"),
    "corner_011": _("Ecke links hinten oben"),
    "corner_100": _("Ecke rechts vorn unten"),
    "corner_101": _("Ecke rechts vorn oben"),
    "corner_110": _("Ecke rechts hinten unten"),
    "corner_111": _("Ecke rechts hinten oben"),
    "whole_face": _("Gesamte Fläche"),
    "keep": _("Nur Bohrungsdurchmesser"),
    # Die Kette einer Magnettasche trägt statt der Senkung eine Verengung, und
    # die geht mit (RM-271) — der Name nennt, was mitgehen kann.
    "follow": _("Senkung, Stufen und Verengung mitnehmen"),
    "legacy_raw": _("Unveränderte Quellachsen"),
    "gltf": _("glTF: Y nach oben"),
    "clearance": _("Spielpassung"),
    "press": _("Presspassung"),
    "thread": _("Gewindepassung"),
    "flush": _("Bündige Passung"),
    "mouth": _("Mündung"),
    "centre": _("Mitte"),
    "centred": _("Mittig auf der Fläche"),
    "point_on_surface": _("Am gewählten Punkt"),
    # Bei Mehrfachauswahl setzt das Fenster ihn auf die Mitte der
    # gemeinsamen Hülle; im Dialog trägt ihn ein, wer eine bestimmte
    # Stelle im Sinn hat. „Genannter Punkt" und nicht „Pivot": Das
    # Fachwort kennt, wer aus dem CAD kommt, und sonst niemand.
    "point": _("Genannter Punkt"),
    # Die acht Texturmuster standen als „knurl_diamond" und „voronoi" im
    # Dialog: englische Schlüssel, unübersetzt, und damit gegen Regel 20 dem
    # Geist nach. Die Namen kommen aus dem Abbildungskatalog, der dieselben
    # Kacheln beschriftet — zwei Listen wären eine Frage der Zeit.
    **figures.TEXTURE_NAMES,
    # Ein gelesenes Muster, das Solidon nicht selbst zeichnet — so steht es
    # in *Merkmal ändern* vorbelegt, bis der Kunde einen der acht Stile wählt.
    "other": _("Fremdes Muster"),
    # Und dieselbe Sorte Fund im selben Dialog eine Zeile tiefer: „Art:
    # raised", „Auflegen: flat". Über das ganze Register waren es
    # sechsundzwanzig Werte; ``tests/test_translations.py`` hält sie jetzt
    # zusammen.
    # Die Symmetrieebenen des Formens. „xz" ist für den Kern der richtige
    # Schlüssel und für den Dialog kein Wort — „ohne" und „X- und Z-Ebene"
    # sagen dasselbe in lesbar. Die einzelnen Achsen bleiben, wie sie sind:
    # ein „x" ist selbst schon der Name (siehe ``SELF_NAMING`` in der Suite).
    "none": _("Ohne"),
    "xy": _("X- und Y-Ebene"),
    "xz": _("X- und Z-Ebene"),
    "yz": _("Y- und Z-Ebene"),
    "xyz": _("Alle drei Ebenen"),
    # Die drei Projektionen des Reliefs. „planar" ist kein Wort, das jemand
    # in einem Auswahlfeld erwartet, und „spherical" schon gar nicht — benannt
    # wird, was passiert, nicht wie die Rechnung heißt.
    "planar": _("Von oben"),
    "cylindrical": _("Um die Achse"),
    "spherical": _("Über die Kugel"),
    "face": _("Auf eine Fläche"),
    "raised": _("Erhaben"),
    "engraved": _("Vertieft"),
    # Die Schnitte einer Beschriftungsschrift. Der Schlüssel ist englisch, weil
    # er in der Projektdatei steht; der Name hier ist es nicht, denn „bold" ist
    # kein Wort, das eine deutsche Oberfläche stehen lässt.
    "regular": _("Normal"),
    "bold": _("Fett"),
    "italic": _("Kursiv"),
    "bold_italic": _("Fett kursiv"),
    "flat": _("Flach"),
    "cylinder": _("Umlaufend"),
    "all": _("Alle"),
    "top": _("Oben"),
    "bottom": _("Unten"),
    "side": _("Seitlich"),
    "horizontal": _("Waagerecht"),
    "vertical": _("Senkrecht"),
    "linear": _("Geradlinig"),
    "circular": _("Kreisförmig"),
    # Die dritte Art des Merkmalsmusters (P6.7).
    "mirror": _("Gespiegelt"),
    # Wohin die Wand beim Aushöhlen wächst (P6.3).
    "inside": _("Innen"),
    "outside": _("Außen"),
    # Was geschieht, wenn der exakte Kern keine Innenwand findet (P6.3).
    "raster": _("Am Dreiecksmodell"),
    "unchanged": _("Teil unverändert lassen"),
    "origin": _("Ursprung"),
    "bed": _("Druckbett"),
    "corner": _("Ecke"),
    # Wie eine Kollision geprüft wurde: genau am Netz oder nur über die
    # Hüllquader. Der Befund trug „exact" und „box" als rohes Englisch in
    # den Tooltip — dieselbe Sorte Fund wie bei den Texturmustern.
    "exact": _("Genau"),
    "box": _("Über den Hüllquader"),
    # Woher der obere Umriss eines Übergangs kommt (RM-147 E2). „scaled" und
    # „drawn" sind Schlüssel des Registers; im Dialog steht, was der Kunde
    # bekommt — eine gerechnete Kopie oder seine zweite Zeichnung.
    "scaled": _("Aus dem unteren gerechnet"),
    "drawn": _("Eigene Zeichnung"),
    "arc": _("Gleichmäßiger Bogen"),
    # Die sechste Kantenauswahl (RM-147 E4): nicht nach der Lage, sondern
    # einzeln — die Antwort auf „diese eine Ecke".
    "named": _("Einzeln gewählt"),
    "pin": _("Stift"),
    "bore": _("Bohrung"),
    # Der Standfuß kann beides, und beide Werte sind englische Schlüssel: Was
    # der Kunde wählt, heißt „Fuß" oder „Tasche" — die Tasche nimmt einen
    # gekauften Gummifuß auf, der Fuß wird gedruckt.
    "foot": _("Fuß"),
    "pocket": _("Tasche"),
    "rectangle": _("Rechteck"),
    "circle": _("Kreis"),
    "polygon": _("Vieleck"),
    "slot": _("Langloch"),
    "hexagon": _("Sechseck"),
    "staggered": _("Versetzte Reihen"),
    # Die zwei Lochbilder. Sie stehen bei den Grundformen, weil sie dasselbe
    # sind — ein Umriss, den die Operation hochzieht oder ausschneidet —, nur
    # dass es mehrere davon sind.
    "bolt_circle": _("Lochkreis"),
    "hole_grid": _("Lochraster"),
    # Die vier Verbinder. „round" und „hex" wären als Schlüssel noch zu
    # erraten, „dovetail" und „snap" nicht — und das sind die beiden, für die
    # man sich bewusst entscheidet.
    "round": _("Rund"),
    "rectangular": _("Rechteckig"),
    "screw": _("Schraubdeckel"),
    "push": _("Steckdeckel"),
    "hinged": _("Klappdeckel"),
    "ellipse": _("Oval"),
    "lower": _("Untere Hälfte"),
    "upper": _("Obere Hälfte"),
    "below": _("Kleinere Seite"),
    "above": _("Größere Seite"),
    # Woran die Ebene von *Abschneiden* hängt (RM-400). Eigene Schlüssel: „face“
    # heißt oben schon „Auf eine Fläche“.
    "along_axis": _("An einer Achse"),
    "at_face": _("An einer Fläche"),
    "through_edge": _("Durch eine Kante"),
    "through_points": _("Durch drei Punkte"),
    "hex": _("Sechskant"),
    "dovetail": _("Schwalbenschwanz"),
    "snap": _("Schnapper"),
    "honeycomb": _("Wabe"),
    "cubic": _("Würfelgitter"),
    "auto": _("Automatisch"),
    "mesh": _("Dreiecksnetz"),
    "brep": _("Echte Flächen und Kanten"),
    # Die drei Antworten auf die Frage, was mit den übrigen Abschnitten eines
    # Hohlraums geschieht (``remove_feature.sections``). „Nachfragen“ ist die
    # Vorgabe: Der Kern entscheidet die Mehrdeutigkeit nicht selbst (Regel 21).
    "ask": _("Nachfragen"),
    "ask_side": _("Nachfragen"),
    # Die Anfangsrichtung eines Kanals und der Drehsinn eines Übergangs, die
    # beim Schnitt mit Werkzeug zur Wahl stehen (P6.5b/c).
    "ask_twist": _("Nachfragen"),
    "counterclockwise": _("Linksherum"),
    "clockwise": _("Rechtsherum"),
    "down": _("Nach unten"),
    "up": _("Nach oben"),
    "equal_distances": _("Gleiche Breite"),
    "two_distances": _("Zwei Abstände"),
    "distance_angle": _("Abstand und Winkel"),
    # Der Verlauf einer Verrundung (P6.1): ein Radius oder einer, der sich
    # entlang der Kante ändert.
    "constant_radius": _("Gleichbleibend"),
    "variable_radius": _("Mit Verlauf"),
    # Die Entformungsrichtung der Formschräge (P6.4): in welche Richtung das
    # Teil schmaler wird, benannt wie die Seiten am Druckbett.
    "pull_up": _("Nach oben"),
    "pull_down": _("Nach unten"),
    "pull_right": _("Nach rechts"),
    "pull_left": _("Nach links"),
    "pull_back": _("Nach hinten"),
    "pull_front": _("Nach vorn"),
    "neutral_start": _("Am Anfang"),
    "neutral_end": _("Am Ende"),
    "neutral_height": _("Auf einer Höhe"),
    "right_side": SIDE_NAMES[0][0],
    "left_side": SIDE_NAMES[0][1],
    "back_side": SIDE_NAMES[1][0],
    "front_side": SIDE_NAMES[1][1],
    "top_side": SIDE_NAMES[2][0],
    "bottom_side": SIDE_NAMES[2][1],
    "chain": _("Ganzer Hohlraum"),
    "single": _("Nur das gewählte Merkmal"),
    # **Die Druckeinstellungen waren die zweite Feldquelle, und sie stand hier
    # nicht drin.** ``tests/test_translations.py`` prüft Regel 20 für
    # Auswahlwerte am Operationsregister; die sechsundfünfzig Felder des
    # Druckdialogs (``print_settings_dialog.FIELDS``) sind eine eigene Liste
    # und liefen an der Prüfung vorbei. Im deutschen Fenster stand deshalb
    # „Naht: aligned", „Wandbahnen: arachne", „Druckbetthaftung: brim" — und im
    # Füllmuster englische Schlüssel **neben** deutschen Namen: grid, lines,
    # triangles, Wabe, Würfelgitter.
    #
    # Wo der englische Begriff der ist, unter dem der Kunde ihn in seinem
    # Slicer wiederfindet, steht er in Klammern dahinter — dasselbe Muster wie
    # „Exakter Körper (B-Rep)".
    "aligned": _("Ausgerichtet"),
    "nearest": _("Nächstgelegen"),
    "random": _("Zufällig"),
    # Nicht „Hinten" und nicht „Rückseite": Das erste ist die **Rückansicht**
    # im Ansichtsmenü (Strg+2, englisch „Back"), das zweite der Name einer
    # **Fläche**, deren Normale nach hinten zeigt (``_SIDES``). Ein
    # Katalogschlüssel trägt genau eine Bedeutung — mit einem für zwei bekäme
    # eine von ihnen das falsche Wort. (``TranslatableText`` kennt ein
    # ``context``-Feld, aber der Extraktor liest es nicht; siehe ROADMAP.)
    "rear": _("Auf der Rückseite"),
    "classic": _("Klassisch"),
    # Eigennamen wie „Gyroid": so heißt der Algorithmus, in jedem Slicer und in
    # jeder Sprache. Dasselbe gilt für die drei Haftarten — im Dialog heißen die
    # Felder daneben „Skirt-Runden", „Brim-Breite" und „Raft-Schichten", und ein
    # Wert, der anders heißt als sein Feld, ist eine Fährte ins Nichts.
    "arachne": _("Arachne"),
    "gyroid": _("Gyroid"),
    "grid": _("Gitter"),
    "lines": _("Linien"),
    "triangles": _("Dreiecke"),
    "tree": _("Baum"),
    "everywhere": _("Überall"),
    "build_plate": _("Nur vom Bett"),
    "skirt": _("Skirt"),
    "brim": _("Brim"),
    "raft": _("Raft"),
    # Die zwei Wege von *Dreiecke verringern* (``mesh_ops.DECIMATE_METHODS``).
    "measured": _("Gemessen"),
    "fast": _("Schnell"),
    "keyhole": _("Schlüsselloch"),
    "screws": _("Schraublöcher"),
    "pegboard": _("Lochwand-Haken"),
    "clamp": _("Klemme"),
    # Die Hälften der Paare aus dem Dateiaudit (RM-184): Bajonett und
    # Rastdrehscheibe stehen je in einem Baustein, die Wahl ist die Hälfte.
    "socket": _("Aufnahme mit Schlitzen"),
    "plug": _("Kragen mit Nocken"),
    "base": _("Führung mit Zapfen"),
    "disc": _("Drehscheibe"),
    # Die Bauformen des Stangenverbinders, nach ihrer Wegezahl.
    "sleeve": _("Steckhülse"),
    "straight": _("Gerade, zwei Wege"),
    "elbow": _("Winkel, zwei Wege"),
    "tee": _("T-Stück, drei Wege"),
    "corner_3d": _("Raumecke, drei Wege"),
    "cross": _("Kreuz, vier Wege"),
    # Die zwei Bauarten der Kanalnaht. Eigene Schlüssel: „inside“ und
    # „outside“ meinen beim Aushöhlen, wohin die Wand wächst.
    "outer_sleeve": _("Hülse außen"),
    "inner_insert": _("Einlage innen"),
    # Die Platten und Öffnungen der Raumvorlage.
    "room_back": _("Rückwand"),
    "room_side": _("Seitenwand"),
    "window": _("Fenster"),
    "door": _("Tür"),
}


def _choice_measure(value: float, with_unit: bool) -> str:
    """Ein Normteilmaß für die Dokumentation, in lokalisierten Millimetern."""
    text = format_decimal(value, 2)
    return f"{text} mm" if with_unit else text


def choice_label(value: str, *, format_measure: Callable[[float, bool], str] | None = None) -> str:
    """Ein Auswahlwert, wie der Nutzer ihn lesen kann.

    Normteilschlüssel sind englisch und kurz, weil sie Schlüssel sind — im
    Dialog standen sie aber als Beschriftung: „cable-5", „ptfe-4x2". Das tippt
    niemand ab und niemand erkennt es, ohne die Tabelle danebenzulegen.

    Erzeugt aus den Maßen und nicht als zweite Liste gepflegt: sonst hätte ein
    neues Normteil einen Namen an einer Stelle und keinen an der anderen. Was
    die Tabelle nicht kennt — „M4", „PLA", „z" —, bleibt, wie es ist; diese
    Werte sind selbst schon der Name.

    Ohne ``format_measure`` stehen Maße in Millimetern im Handbuch. Die
    Oberfläche reicht ihren Zahlenformatierer samt gewählter Anzeigeeinheit
    herein; Qt bleibt dort.
    """
    from app.core.knowledge import standards

    measure = format_measure or _choice_measure
    named = _CHOICE_NAMES.get(value)
    if named is not None:
        return str(named)
    try:
        insert = standards.insert(value)
    except AppError:
        pass
    else:
        # M4 ist nicht nur eine Buchse, sondern auch Schraube, Mutter und
        # Gewinde. ``choice_label`` kennt das Feld nicht; eine Buchsenlänge an
        # **jedem** M4 wäre daher falsch. Nur die kurzen Buchsen haben einen
        # eigenen Tabellenschlüssel. Dort ersetzt die lesbare Länge das
        # technische S, bei den gemeinsamen Schlüsseln bleibt M4 einfach M4.
        if insert.size != insert.thread:
            return f"{insert.thread} · {measure(insert.length, True)}"
        return value
    try:
        bearing = standards.bearing(value)
    except AppError:
        pass
    else:
        # Die Lagernummer bleibt zum Abgleichen mit der Beschriftung erhalten;
        # die drei Maße daneben machen sie ohne Tabellenwissen verständlich.
        inner = measure(bearing.inner, False)
        outer = measure(bearing.outer, False)
        return f"{bearing.size} · {inner} × {outer} × {measure(bearing.width, True)}"  # noqa: RUF001
    try:
        board = standards.board(value)
    except AppError:
        pass
    else:
        # **Ohne den Markennamen**, und das ist eine Entscheidung: „SKÅDIS"
        # gehört einem Möbelhaus, das Rastermaß gehört niemandem. Was der
        # Kunde erkennen muss, ist die Platte vor ihm, und die erkennt er am
        # Raster. Wessen sie ist, steht in der Beschreibung des Bausteins.
        return f"{_('Lochwand')} {measure(board.pitch, True)}"
    try:
        tube = standards.tube(value)
    except AppError:
        return value
    if tube.inner > 0.0:
        return f"{_('Schlauch')} {measure(tube.outer, False)} × {measure(tube.inner, True)}"  # noqa: RUF001
    return f"{_('Rundkabel')} Ø{measure(tube.outer, True)}"


def menu_tree(
    registry: Registry | None = None, skip: Container[str] = frozenset()
) -> tuple[MenuSection, ...]:
    """Das Menü, in der Reihenfolge des Katalogs (§25).

    ``skip`` lässt Operationen aus der Menüleiste heraus, ohne sie aus dem
    Register zu nehmen — sie bleiben über Katalog, Befehlspalette und
    Kontextmenü erreichbar.

    **Die Entscheidung, *wen* das trifft, gehört nicht hierher.** Der Kern
    bekommt Namen und nicht den Grund: Die Oberfläche reicht die eigenen
    Bausteine des Nutzers herein (§24.5), weil jeder davon eine Operation wird
    und zwanzig eigene Teile aus einem Menü eine Liste zum Absuchen machen.
    Welche Regel dahintersteht, weiß der Aufrufer.
    """
    source = registry or REGISTRY
    sections = []
    for category, entries in source.by_category().items():
        kept = tuple(entry for entry in entries if entry.name not in skip)
        if kept:
            sections.append(
                MenuSection(category=category, title=CATEGORIES[category], entries=kept)
            )
    return tuple(sections)


#: Wie viele Zeilen ein Menü zeigen darf, bevor es eine Liste zum Absuchen
#: wird. Dieselbe Zahl hält ``tests/test_interface_limits.py`` ein zweites Mal
#: — **absichtlich als eigene Kopie und nicht als Import**: Ein Wächter, der
#: seine Grenze von dem holt, den er bewacht, ist an dem Tag blind, an dem
#: jemand die Grenze erhöht.
MAX_MENU_ROWS: Final = 12


def menu_rows_of(categories: Collection[str], registry: Registry | None = None) -> int:
    """Wie viele Zeilen diese Kategorien flach in einem Menü belegen.

    Die eine Zählung für die Frage „passt das ohne Zwischenebene", und sie
    zählt, **was zu sehen ist**: Zwillinge aus ``MENU_TWINS`` haben keinen
    Eintrag, und die Mitglieder einer Variantengruppe teilen einen — vier
    Skizzen-Operationen sind eine Zeile.

    Als eigene Funktion, damit sie prüfbar ist, ohne ein Fenster zu bauen: Die
    Zeilenzahl lässt sich gegen das gebaute Menü halten, unabhängig davon,
    welche Kategorien anschließend gefaltet werden.
    """
    source = registry or REGISTRY
    inside = [spec for spec in source.all() if spec.category in categories]
    names = {spec.name for spec in inside if spec.name not in menu_twins()}
    members = variant_members()
    rows = len(names - members)
    # Je Variantengruppe, die hier überhaupt vertreten ist, genau eine Zeile
    # für den Sammeleintrag.
    rows += sum(1 for group in VARIANT_GROUPS if any(name in names for name in group.members))
    return rows


def menu_rank(title: str) -> int:
    """Wo diese Gruppe in der Reihenfolge der Menüleiste steht.

    Kennt ``MENU_GROUPS`` den Titel nicht, steht er hinten — dieselbe Antwort,
    die ``group_title`` einer unbekannten Kategorie gibt, und aus demselben
    Grund: Eine neue Kategorie soll auftauchen und nicht verschwinden.
    """
    for position, (menu_title, _categories) in enumerate(MENU_GROUPS):
        if str(menu_title) == title:
            return position
    return len(MENU_GROUPS)


def folded_groups(
    sizes: dict[str, int],
    limit: int = MAX_MENU_ROWS,
    fixed: int = 0,
    keep: Collection[str] = (),
    rank: Callable[[str], int] | None = None,
) -> list[str]:
    """Welche Gruppen ein Untermenü bekommen, damit das Menü in die Grenze passt.

    Die Rechnung nimmt Namen und Zeilenzahlen ohne Qt entgegen. Gefaltet
    werden nur Gruppen mit mindestens zwei Einträgen und nur so viele, bis
    die Grenze eingehalten ist. Eine alleinstehende Gruppe ohne zusätzliche
    feste Zeilen bekommt keine nutzlose Zwischenebene.

    ``fixed`` zählt nicht faltbare Zeilen mit. ``keep`` schützt Gruppen bei
    der Auswahl, garantiert aber keinen dauerhaften Platz auf der ersten
    Ebene. ``rank`` ordnet die Gruppen; ohne Angabe gilt ``menu_rank``.

    Genügt eine Gruppe allein, gewinnt unter den ungeschützten die hinterste.
    Genügt keine allein, gewinnt dort die größte. Rang, Größe und Name lösen
    Gleichstände eindeutig auf. Die Menüleiste verwendet dieselbe Rechnung
    für Kategorien innerhalb einer Gruppe über ``folded_categories``.
    """
    ordering = rank or menu_rank
    if len(sizes) < 2 and not fixed:
        return []
    rows = sum(sizes.values()) + fixed
    # Nur Gruppen ab zwei Einträgen: eine von eins spart keine Zeile.
    foldable = {title: count for title, count in sizes.items() if count > 1}
    folded: list[str] = []
    while rows > limit and foldable:
        missing = rows - limit
        enough = [title for title, count in foldable.items() if count - 1 >= missing]
        if enough:
            # Erst die Ungeschützten, dann die hinterste, die allein genügt;
            # bei gleichem Platz die größere, und ganz zuletzt der Name, damit
            # die Antwort eindeutig bleibt.
            title = min(
                enough,
                key=lambda name: (name in keep, -ordering(name), -foldable[name], name),
            )
        else:
            # **Bei gleicher Größe entscheidet die Reihenfolge, nicht das
            # Alphabet.** Der Zweig darüber fragte den Rang, dieser nicht — und
            # damit stand die Zusage „wer falten muss, faltet hinten" nur für
            # die halbe Rechnung. Gemessen am Menü *Ändern* (27.08.2026): Bei
            # gleich großen Gruppen fiel „Verbinden und Abziehen" statt
            # „Formgebung", weil „boolean" alphabetisch vor „shaping" steht —
            # die häufigere Gruppe wanderte eine Ebene tiefer als die seltenere.
            title = min(
                foldable,
                key=lambda name: (name in keep, -foldable[name], -ordering(name), name),
            )
        folded.append(title)
        rows -= foldable.pop(title) - 1
    return folded


def folded_categories(category: str, registry: Registry | None = None) -> frozenset[str]:
    """Welche Kategorien dieser Gruppe ein Untermenü bekommen (§2.6).

    Gezählt werden die sichtbaren Zeilen aus ``menu_rows_of`` einschließlich
    zusammengelegter Einträge. Die Reihenfolge folgt ``MENU_GROUPS``;
    ``folded_groups`` bündelt nur so weit, bis der Rest in die Grenze passt.
    Bohrungen sind bei der Auswahl geschützt, können aber gefaltet werden,
    wenn ungeschützte Kategorien nicht genügen.

    Eine Gruppe mit einer einzigen besetzten Kategorie bleibt flach. Welche
    Gruppen tatsächlich in der Leiste erscheinen, entscheidet getrennt davon
    ``in_the_menu_bar``; Handlungen rechts werden dadurch nicht zu Menüs.
    """
    source = registry or REGISTRY
    in_group = next(
        (categories for _title, categories in MENU_GROUPS if category in categories),
        (),
    )
    # Gezählt wird, was im Menü **eine Zeile hat** — nicht, was irgendeine
    # Operation trägt. Eine Kategorie, deren Operationen alle Zwillinge aus
    # ``MENU_TWINS`` sind, ist besetzt und im Menü unsichtbar; sie zählte
    # trotzdem als eine der Kategorien, unter denen gefaltet wird, und stand
    # mit null Zeilen in ``sizes``. Heute trifft das keine (gemessen am
    # 02.09.2026), und genau deshalb steht es hier: Die nächste Zwillingsgruppe
    # bräuchte sonst niemanden, der daran denkt.
    present = [name for name in in_group if menu_rows_of([name], source)]
    if len(present) <= 1:
        return frozenset()
    sizes = {name: menu_rows_of([name], source) for name in present}
    order = {name: position for position, name in enumerate(present)}
    return frozenset(
        folded_groups(
            sizes,
            keep={"holes"},
            rank=lambda name: order.get(name, len(order)),
        )
    )


def menu_path(spec: OperationSpec, registry: Registry | None = None) -> str:
    """Der tatsächliche Ort einer Operation aus denselben Daten wie die Oberfläche.

    Zusammengelegte Zwillinge führen zum gemeinsamen Dialog. Bausteine nennen
    den Katalog mit Gruppe und Kachel; auswahlbezogene Operationen nennen die
    Handlungen rechts und das benötigte Merkmal beziehungsweise den Körper.

    Für Einträge der Menüleiste entstehen die Ebenen aus ``MENU_GROUPS`` und
    ``folded_categories``. Eine Variantengruppe nennt den gemeinsamen Dialog
    und die dort auszuwählende Variante. Diese Orte folgen dem Register und
    behalten keine festgeschriebenen Beispielwege oder Operationszahlen.
    """
    source = registry or REGISTRY
    twins = menu_twins()
    if spec.name in twins:
        # Ein zusammengelegter Zwilling hat keinen eigenen Eintrag
        # (MENU_TWINS): sein Ort ist der Eintrag des Partners — alles andere
        # schickte Nutzer und Agent an eine Stelle, die es nicht gibt.
        #
        # Wie er dort erreicht wird, hängt am Paar (``registry.twin_way``):
        # ein Erzeuger über das Kontextmenü im Verlauf, eine Bearbeitung über den
        # Körper, den man ihr gibt. Der Zusatz nannte früher den Umschalter
        # „Exakt" — den gibt es seit P2.8 nicht mehr.
        twin = source.get(twins[spec.name])
        where = menu_path(twin, source)
        return f"{where} ({twin_way(spec.name)})"
    if spec.name in catalogue_operations():
        # **Ein Baustein nennt den Ort, den er wirklich hat.**
        # Die Bausteine der Bibliothek stehen seit dem 29.08.2026 nur noch im
        # Katalog; ein Weg „Bausteine → Mechanik → Filmscharnier" schickte
        # Kunde, Agent und Handbuch zu einem Menü, das es nicht mehr gibt.
        # Gefragt wird nach der Kachel und nicht nach der Kategorie — warum,
        # steht in :func:`catalogue_operations`.
        #
        # **Und der Ersatz darf nicht dieselbe Kette weiterschreiben.** Hier
        # stand zuerst „Datei → Bausteinkatalog → Mechanik → Bolzenscharnier",
        # also vier Glieder in einer Pfeilkette — von denen die letzten beiden
        # keine Menüeinträge sind, sondern Gruppe und Kachel *im Katalogfenster*.
        # Siebenundzwanzig Werkzeugbeschreibungen nannten das unter dem Vorwort
        # „Menü:", und wer danach im Datei-Menü ein Untermenü *Mechanik* sucht,
        # findet keines. Ein Pfeil zwischen zwei Menüs bedeutet „dann dort
        # weiter"; zwischen Menü und Dialog bedeutet er nichts.
        #
        # Der Bruch wird deshalb ausgeschrieben: bis zum Katalog ein Menüweg,
        # danach ein Satz. Er ist auch die Antwort auf die Zusage von
        # ``tests/test_agent_suite.py``, dass kein Menüweg tiefer als drei
        # Ebenen wird — die Leiste faltet höchstens eine Ebene, tiefer *kann*
        # keiner sein.
        return _catalogue_path(spec)
    if not in_the_menu_bar(spec.category):
        # **Was einer Auswahl gilt, steht rechts im Fenster** — seit dem
        # 11.09.2026 nicht mehr in der Leiste. Der Weg nennt den Ort und die
        # Auswahl, die es braucht: Ohne gewählten Körper steht dort nichts,
        # und ein Wegweiser, der das verschweigt, schickt zu einer leeren
        # Karte. Die Gruppe steht nicht dabei: Rechts sind die Gruppen
        # Abschnitte einer Liste mit Suchfeld, und der Titel ist es, was man
        # dort sucht.
        return f"{_panel_place(spec)} → {spec.title}"
    steps = [group_title(spec.category)]

    # **Je Kategorie gefragt, nicht je Gruppe.** Die frühere Abfrage war gröber:
    # alles flach oder jede Kategorie eine Ebene
    # tiefer —, und die Leiste faltet seit dem 27.08.2026 nur so weit, wie sie
    # muss. Ein Pfad, der die alte Frage stellt, schickt den Nutzer und den
    # Agenten zu einer Zwischenebene, die es nicht mehr gibt.
    if spec.category in folded_categories(spec.category, source):
        steps.append(str(CATEGORIES.get(spec.category, spec.category)))

    # **Eine Variante hat keinen eigenen Eintrag.** Die Menüleiste zeigt für
    # ``VARIANT_GROUPS`` einen Eintrag je Gruppe („Aus Skizze erzeugen …"),
    # die Art wählt der Dialog. Der Weg nannte trotzdem „Erzeugen → Grundform
    # hochziehen" — einen Eintrag, den es nicht gibt, und der Agent schrieb
    # ihn in jede Werkzeugbeschreibung (Gesamtreview 05.09.2026, CORE-22).
    # Aus derselben Deklaration wie die Leiste: bis zur Gruppe ein Menüweg,
    # danach die Wahl im Dialog.
    group = next((entry for entry in VARIANT_GROUPS if spec.name in entry.members), None)
    if group is not None:
        steps.append(str(group.title))
        # Der Doppelpunkt gehört zum übersetzten Satz: Französisch setzt davor
        # ein Leerzeichen.
        return (
            " → ".join(steps)
            + " "
            + str(_("({choice}: {title})", choice=group.choice, title=spec.title))
        )

    steps.append(str(spec.title))
    return " → ".join(steps)


def _panel_place(spec: OperationSpec) -> str:
    """Der Ort einer Handlung rechts im Fenster, mit der Auswahl, die sie braucht."""
    if spec.applies_to:
        kinds = ", ".join(str(FEATURE_TITLES.get(kind, kind)) for kind in spec.applies_to if kind)
        selection = _("bei gewähltem Merkmal: {kinds}", kinds=kinds)
        return f"{_('Handlungen rechts')} ({selection})"
    return f"{_('Handlungen rechts')} ({_('bei gewähltem Körper')})"


def catalogue_operations() -> frozenset[str]:
    """Die Operationen, die im Bausteinkatalog eine Kachel haben.

    **Die Trennlinie für den Menüort, und sie liegt an der Bibliothek — nicht
    an der Kategorie.** Hier stand zuerst eine Menge von Kategorien
    (``WITHOUT_MENU = {"parts"}``), und das war eine Näherung: Von den
    neunundzwanzig Operationen der Kategorie ``parts`` haben
    siebenundzwanzig eine Kachel, zwei nicht — ``create_lid`` und
    ``screw_lid`` sind Operationen, die einen Deckel *bauen*, und der Katalog
    zeigt ``PARTS.all()``.

    Die Näherung hat beide aus der Menüleiste genommen, ohne sie irgendwo
    hinzustellen: gemessen am gebauten Fenster **114 Menüeinträge, kein
    „Deckel erzeugen" darunter**, im Katalog nicht vorhanden, und
    :func:`menu_path` schickte jeden Fragenden dorthin. Auch das Kontextmenü
    einer Fläche verlor sie — also genau der Ort, den §18.5 für sie vorsieht,
    und den die Tour *dose-mit-deckel* dem Kunden nennt.

    Gefragt wird deshalb nach der Sache: Wer eine Kachel hat, steht im
    Katalog; wer keine hat, steht im Menü. Lazy importiert, weil die
    Bausteine ihrerseits das Register laden.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.ops import creation_name, op_name

    return frozenset(
        name for part in PARTS.all() for name in (op_name(part.name), creation_name(part.name))
    )


def _catalogue_path(spec: OperationSpec) -> str:
    """Wo ein Baustein liegt — Menüweg bis zum Katalog, danach ein Satz.

    Getrennt von :func:`menu_path`, weil es zwei verschiedene Auskünfte sind:
    Ein Menüweg ist eine Kette gleichartiger Schritte, hier wechselt nach dem
    zweiten das Fenster. Die Bausteingruppe ist dieselbe, nach der der Katalog
    seine Kacheln ordnet — lazy importiert, weil die Bausteine ihrerseits das
    Register laden.

    Kennt der Katalog die Gruppe nicht, bleibt der kurze Satz: Eine erfundene
    Gruppe wäre schlechter als keine (Regel 21).
    """
    from app.core.knowledge.parts import GROUPS
    from app.core.knowledge.parts.ops import part_of

    where = f"{_('Datei')} → {_('Bausteinkatalog …')}"
    part = part_of(spec.name)
    part_group = part.group if part is not None else None
    if part_group is not None and part_group in GROUPS:
        return str(_("{path}, dort unter {group}: {title}")).format(
            path=where, group=GROUPS[part_group], title=spec.title
        )
    return str(_("{path}, dort: {title}")).format(path=where, title=spec.title)


def context_menu(feature_kind: str, registry: Registry | None = None) -> tuple[OperationSpec, ...]:
    """Was ein Klick auf ein Merkmal anbietet — der kürzeste Weg vom Sehen
    zum Tun (§2.6).

    **Die Rohmenge, nicht die Zeilen des Menüs.** Der Name legt das andere
    nahe, und `tests/test_acceptance_p0.py` nagelt ausdrücklich diese Lesart
    fest: alles, dessen ``applies_to`` die Art nennt. Was die Oberfläche daraus
    macht, entscheidet sie — sie legt zusammengelegte Zwillinge zusammen
    (``MENU_TWINS``), faltet nach Zeilen und vertritt die Bausteine mit Kachel
    durch den Katalog.

    Der Satz steht hier, weil die Verwechslung Geld gekostet hat: An jeder
    Fläche stand *Bohrung setzen* zweimal, weil ``operations_for_feature`` in
    `app/ui/panels.py` diese Menge ungefiltert weitergab und die
    Zusammenlegung nicht kannte, die die Menüleiste seit je macht.
    """
    return (registry or REGISTRY).for_feature(feature_kind)


@dataclass(frozen=True, slots=True)
class PaletteEntry:
    """Eine Zeile der Befehlspalette. Das Kürzel steht daneben, so lernt man
    es nebenbei.
    """

    name: str
    title: TranslatableText | str
    category: str
    doc: TranslatableText | str
    shortcut: str | None = None
    available: bool = True
    """Ob der Eintrag jetzt ausführbar ist — die Palette zeigt ihn trotzdem:
    sie ist eine Reihenfolge, keine Auswahl."""
    reason: TranslatableText | str = ""
    """Warum nicht, wenn nicht — dieselbe Auskunft, die das Menü im
    Hinweistext trägt (Regel 18: der Grund ist die zweite Kodierung neben
    dem Ausgrauen)."""


def palette_entries(
    registry: Registry | None = None, *, for_feature: str | None = None
) -> tuple[PaletteEntry, ...]:
    """Alle Operationen als Palettenzeilen.

    Ist ein Merkmal ausgewählt, stehen die Operationen vorn, die dafür
    deklariert sind (``applies_to``, §10). Wer eine Bohrung angeklickt hat,
    sucht Senken und Verschließen — und nicht das, was zufällig vorn im
    Alphabet steht.

    Es ist eine **Reihenfolge, keine Auswahl**: alles bleibt erreichbar. Eine
    Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen, und die
    stehen auf der Nicht-bauen-Liste.
    """
    specs = list((registry or REGISTRY).all())
    # **Nach dem Titel, nicht nach dem Namen.** ``Registry.all()`` sortiert nach
    # dem internen englischen Bezeichner, und die Palette gab das ungefiltert
    # weiter: „An Merkmal ausrichten", „Textur aufbringen", „Auf dem Bett
    # anordnen", „Slot zuweisen" — für einen deutschen Leser eine Zufallsfolge,
    # während die Menüleiste daneben nach Titel sortiert (``by_category``, mit
    # genau dieser Begründung im Docstring).
    #
    # Zuerst nach Titel, dann stabil nach ``applies_to``: Python sortiert
    # stabil, also steht die passende Gruppe vorn und innerhalb jeder Gruppe
    # alphabetisch.
    #
    # Über ``sort_key``, denselben Schlüssel wie ``by_category`` in der
    # Menüleiste — nicht bloß ``str``: 23 der 85 Titel tragen einen Umlaut, und
    # nach Codepunkt verglichen landet „Überhangfächer" hinter allem anderen,
    # weil „Ü" hinter „z" steht. Nicht zu verwechseln mit der Suchfaltung der
    # Palette (``registry.search.fold``, „ä" → „ae"): hier zählt „ä" wie „a"
    # nach DIN 5007-1, dort wie es auf einer Tastatur ohne Umlaute geschrieben
    # wird.
    specs.sort(key=lambda spec: sort_key(spec.title))
    if for_feature:
        specs.sort(key=lambda spec: for_feature not in spec.applies_to)
    return tuple(
        PaletteEntry(
            name=spec.name,
            title=spec.title,
            category=spec.category,
            doc=spec.doc,
            shortcut=spec.shortcut,
        )
        for spec in specs
    )


@dataclass(frozen=True, slots=True)
class CliArgument:
    """Eine Kommandozeilen-Option, abgeleitet aus einem Parameter."""

    flag: str
    name: str
    kind: str
    required: bool
    help: str
    choices: tuple[str, ...] = ()
    default: Any = None


@dataclass(frozen=True, slots=True)
class CliCommand:
    """Ein Kommandozeilen-Befehl, abgeleitet aus einer Operation."""

    name: str
    help: str
    arguments: tuple[CliArgument, ...]


def _help_text(spec: ParamSpec) -> str:
    text = str(spec.doc) if spec.doc is not None else str(spec.title)
    return f"{text} [{spec.unit}]" if spec.unit else text


def cli_commands(registry: Registry | None = None) -> tuple[CliCommand, ...]:
    """Befehle aus dem Register (ROADMAP P0: die Kommandozeile liest
    dieselbe Quelle).
    """
    commands: list[CliCommand] = []
    for spec in (registry or REGISTRY).all():
        arguments = tuple(
            CliArgument(
                flag=f"--{entry.name.replace('_', '-')}",
                name=entry.name,
                kind=entry.kind,
                required=entry.required,
                help=_help_text(entry),
                choices=entry.choices,
                default=entry.default,
            )
            for entry in spec.params.spec()
            if not entry.internal
        )
        commands.append(CliCommand(name=spec.name, help=str(spec.doc), arguments=arguments))
    return tuple(commands)


def caveat_line(spec: OperationSpec, markup: bool = False) -> str:
    """Wann diese Operation die falsche Wahl ist — als fertige Zeile, oder leer.

    **Die Angabe gab es, und sie kam nur im Handbuch an.** Zwölf Operationen
    tragen einen ``caveat`` („Nicht ohne Entlüftung, wenn im Slicer Stützen
    entstehen"), und gelesen hat ihn allein :func:`documentation`. Der
    Menüeintrag setzte ``doc`` als Tooltip, der Dialog zeigte ``doc`` als
    Beschreibung, und der Agent bekam ``doc`` als Werkzeugbeschreibung — an
    keiner dieser drei Stellen stand die Grenze, also an keiner, an der jemand
    die Operation gerade wählt. Der Docstring des Feldes rechnet selbst mit der
    Oberfläche: „dann steht neben jedem Menüeintrag eine Warnung".

    Das Wort davor steht hier und nicht dreimal daneben — ``caveat`` ohne
    Vorwort liest sich wie eine Fortsetzung des ``doc``-Satzes, und genau davor
    warnt die Deklaration des Feldes.

    ``markup`` setzt die Sternchen für das Handbuch. Ein Tooltip und ein
    Systemprompt wollen keine, und ein Handbuch ohne wäre ein Absatz, den man
    überliest.
    """
    if not spec.caveat:
        return ""
    # Der Doppelpunkt gehört zum übersetzten Satz: Französisch setzt davor
    # ein Leerzeichen.
    if markup:
        return str(_("**Wann nicht:** {caveat}", caveat=spec.caveat))
    return str(_("Wann nicht: {caveat}", caveat=spec.caveat))


def tool_schemas(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """Werkzeugbeschreibungen für den Agenten (§26.2). Dasselbe Schema wie
    Dialog und Kommandozeile.
    """
    return tuple(
        {
            "name": spec.name,
            # Die Grenze gehört dazu: Der Agent wählt aus derselben Auskunft,
            # aus der ein Mensch wählt (§10, Leitprinzip 3). Ohne sie schlug er
            # *Gitter füllen* für ein Teil vor, das dicht sein muss, und nichts
            # in seiner Werkzeugliste sagte, dass das die falsche Wahl ist.
            "description": _with_caveat(str(spec.doc) or str(spec.title), spec),
            "input_schema": json_schema(
                spec.params,
                literal_fields=(spec.produces_from,) if spec.produces_from is not None else (),
            ),
        }
        for spec in (registry or REGISTRY).all()
    )


def _with_caveat(text: str, spec: OperationSpec) -> str:
    """Beschreibung und Grenze in einem Absatz, getrennt durch eine Leerzeile."""
    line = caveat_line(spec)
    return f"{text}\n\n{line}" if line else text


#: Welche Abbildung eine Kategorieseite eröffnet.
#:
#: Nicht je Operation — dreiundsiebzig Vorher-Nachher-Bilder wären
#: dreiundsiebzig Aufbauten mit je eigenem Ausgangskörper, eigenen Werten und
#: eigener Auswahl, und jedes davon veraltet für sich. Eine je Kategorie zeigt,
#: worum es in dem Kapitel geht, und stammt aus demselben Katalog, den die
#: geschriebenen Seiten benutzen. Wo keine passt, steht keine: ein Bild, das
#: nur ungefähr dazugehört, kostet mehr Vertrauen, als es Verständnis bringt.
CATEGORY_FIGURES: dict[str, str] = {
    "holes": "drill",
    "prepare": "split",
    "surface": "texture",
    "parts": "part-nut-trap",
}


#: Die Ortsangaben, die jede Baustein-Operation zusätzlich trägt — die Namen
#: aus ``knowledge/parts/ops.py`` (``_PLACEMENT``), hier als Konstante, weil
#: das Register die Bausteinbibliothek nicht importieren darf. Ein Test hält
#: beide Listen deckungsgleich. Das Handbuch erklärt sie einmal am Kopf der
#: Kategorie, statt sechs identische Zeilen in jede Bausteintabelle zu setzen.
PART_PLACEMENT_PARAMS: Final = (
    "x",
    "y",
    "z",
    "nx",
    "ny",
    "nz",
    "axis",
    "angle",
    "at_feature",
    "at_features",
)


def normal_fields_of(spec: OperationSpec) -> tuple[str, str, str]:
    """Die Namen der Richtungsfelder dieses Schemas.

    ``nx``, ``ny``, ``nz`` — außer ein Rezept trägt ein gleichnamiges Fachmaß,
    dann hat ``knowledge/parts/ops.py`` sie ``surface_nx`` … genannt und den
    Namen am Schema hinterlegt. Wer die Felder erkennen will (Register,
    Handbuch, Schnellbearbeitung), fragt hier und nicht die feste Dreiergruppe.
    """
    names = getattr(spec.params, "_surface_normal_fields", ("nx", "ny", "nz"))
    return str(names[0]), str(names[1]), str(names[2])


#: Parameter, deren Wert die Operation beim Ausführen **erfragt** (Regel 21).
#:
#: Sie stehen im Schema, weil die Antwort dort festgehalten wird
#: (``OpResult.answered``, §15.7) und die nächste Auswertung sonst dieselbe
#: Frage noch einmal stellte. Sie sind aber **keine Einstellung**, die man
#: vorab trifft: ``remove_feature.sections`` entscheidet, was mit den übrigen
#: Abschnitten eines Hohlraums geschieht — eine Frage, die es nur an einer
#: Bohrung mit Senkung gibt und die an jedem anderen Merkmal ohne Gegenstand
#: wäre.
#:
#: Der Operationsdialog zeigt sie hinter der Klappe wie jeden anderen
#: Feinstellwert; die **Schnellbearbeitung am Merkmal** lässt sie weg — dort
#: soll nur stehen, was das gewählte Merkmal betrifft (Robert, 09.09.2026).
_ASKED_FIELDS: Final[dict[str, frozenset[str]]] = {
    "remove_feature": frozenset({"sections"}),
    # Welche Seite offen bleibt, gibt es nur, wo eine Durchgangsbohrung zum
    # Sackloch wird — an jedem Sackloch wäre das Feld ohne Gegenstand.
    "resize_hole": frozenset({"open_side"}),
}


def asked_fields(spec: OperationSpec) -> frozenset[str]:
    """Welche Felder dieser Operation beim Ausführen erfragt werden."""
    return _ASKED_FIELDS.get(spec.name, frozenset())


def part_placement_params(spec: OperationSpec) -> frozenset[str]:
    """Die Ortsfelder dieses Schemas, auch bei gleichnamigen Rezeptmaßen."""
    declared = getattr(spec.params, "_placement_fields", None)
    if declared is not None:
        return frozenset(declared.values())
    return (
        frozenset(PART_PLACEMENT_PARAMS)
        .difference(("nx", "ny", "nz"))
        .union(normal_fields_of(spec))
    )


def documentation(
    registry: Registry | None = None, category: str = "", *, technical: bool = True
) -> str:
    """Der Referenzteil der Dokumentation — erzeugt, nie von Hand geschrieben.

    Mit ``category`` nur ein Bereich. Das Handbuchfenster zeigt eine Kategorie
    je Seite. ``technical=False`` zeigt Bediennamen und Auswahlbeschriftungen;
    die Vorgabe erhält die Schlüssel und Verträge für Kommandozeile und API.
    Beide Fassungen lesen dieselbe Deklaration.
    """
    lines: list[str] = []
    source = registry or REGISTRY
    for name, entries in source.by_category().items():
        if category and name != category:
            continue
        lines.append(f"## {CATEGORIES[name]}")
        lines.append("")
        opening = CATEGORY_FIGURES.get(name)
        if opening:
            lines.append(f"![](figure:{opening})")
            lines.append("")
        if name == "parts" and entries:
            shared = tuple(
                entry
                for entry in entries[0].params.spec()
                if entry.name in part_placement_params(entries[0])
            )
            if shared:
                lines.append(
                    str(
                        _(
                            "Alle Bausteine teilen dieselben Ortsangaben. Sie stehen "
                            "hier einmal und fehlen deshalb in den Tabellen darunter:"
                        )
                    )
                )
                lines.append("")
                lines.extend(parameter_table(shared, technical=technical))
        for spec in entries:
            suffix = f" (`{spec.name}`)" if technical else ""
            lines.append(f"### {spec.title}{suffix}")
            lines.append("")
            if spec.doc:
                description = str(spec.doc)
                lines.append(description if technical else markup.below_heading(description, 3))
                lines.append("")
            # **Wo man sie findet.** Von 142 Einträgen nannten zwei ihren Ort in
            # der Oberfläche (konzepte/nachweise-handbuch-2026-09/findbarkeit.md,
            # Teil 4) — wer in der Referenz liest, sucht als Nächstes den Knopf.
            # ``menu_path`` antwortet aus denselben Daten wie Menü, Katalog und
            # Auswahlfenster, dieselbe Auskunft, die der Chat bekommt.
            # Doppelpunkte stehen in dieser Referenz im übersetzten Satz:
            # Französisch setzt davor ein Leerzeichen.
            lines.append(str(_("**Ort:** {path}", path=menu_path(spec, source))))
            lines.append("")
            if spec.caveat:
                # Eigener Absatz mit eigenem Wort davor: In den doc-Satz
                # gehängt liest sich eine Grenze wie ein Nachtrag. Das Wort
                # kommt aus ``caveat_line`` — Dialog, Menü und Agent zeigen
                # dasselbe, und ein zweites Vorwort daneben wäre eines zu viel.
                lines.append(caveat_line(spec, markup=True))
                lines.append("")
            facts = []
            if technical:
                facts = [
                    str(
                        _(
                            "Objekte: {consumes} → {produces}",
                            consumes=(
                                f"≥ {spec.minimum_inputs}"
                                if spec.consumes == VARIABLE
                                else spec.consumes
                            ),
                            produces="…" if spec.produces == VARIABLE else spec.produces,
                        )
                    ),
                    str(_("umkehrbar") if spec.reversible else _("nicht umkehrbar")),
                    str(_("ohne Zufall") if spec.deterministic else _("mit Startwert")),
                ]
            if spec.shortcut:
                facts.append(f"{_('Kürzel')} `{spec.shortcut}`")
            if spec.applies_to:
                # Die Merkmalsarten mit ihren Namen, nicht mit ihren
                # Schlüsseln: „Features: face, hole" ist eine Zeile aus dem
                # Register, keine aus einem Handbuch.
                named = ", ".join(str(FEATURE_TITLES.get(kind, kind)) for kind in spec.applies_to)
                facts.append(str(_("Gilt für: {kinds}", kinds=named)))
            if facts:
                lines.append(" · ".join(facts))
                lines.append("")
            parameters = spec.params.spec()
            if name == "parts":
                # Die geteilten Ortsangaben stehen einmal am Kategoriekopf.
                parameters = tuple(
                    entry for entry in parameters if entry.name not in part_placement_params(spec)
                )
            if parameters:
                lines.extend(parameter_table(parameters, technical=technical))
    return "\n".join(lines).rstrip() + "\n"


def _meaning_of(entry: ParamSpec, schema: tuple[ParamSpec, ...]) -> str:
    """Was ein Parameter tut — und wann er es tut.

    Die Bedingung als **eigener Satz** hinter der Bedeutung und nicht in sie
    hineingeschoben: „Von Mitte zu Mitte, bei der linearen Art" sagt es
    beiläufig, „Gilt bei Art = linear." sagt es nachprüfbar. Eine siebte Spalte
    wäre die Alternative gewesen, und eine Tabelle mit sieben Spalten liest
    niemand.
    """
    condition = condition_text(entry, schema)
    meaning = str(entry.doc or "")
    if not condition:
        return meaning
    return f"{meaning} {condition}".strip()


def _span_of(entry: ParamSpec, *, technical: bool = True) -> str:
    """Der zulässige Bereich als Text, oder nichts."""
    if entry.choices:
        return ", ".join(entry.choices if technical else map(choice_label, entry.choices))
    if entry.minimum is None and entry.maximum is None:
        return ""
    low = "" if entry.minimum is None else format_decimal(entry.minimum)
    high = "" if entry.maximum is None else format_decimal(entry.maximum)
    return f"{low} … {high}"


def _default_of(entry: ParamSpec, *, technical: bool = True) -> str:
    """Die Vorgabe, wie ein Mensch sie liest.

    ``True`` und ``False`` standen so in der Tabelle — Pythons Schreibweise in
    einem deutschen Handbuch, und für jeden, der nicht programmiert, zwei
    Wörter ohne Bedeutung. Ein Schalter ist an oder aus.

    Für Zahlen galt dasselbe und blieb übersehen: ``f"{0.2}"`` schreibt einen
    Punkt, und der stand 252-mal im deutschen Handbuch neben einer Anwendung,
    die ``2,40 mm`` anzeigt. :func:`format_decimal` entscheidet das jetzt nach
    der aktiven Sprache — und kürzt dabei ``5.0`` auf ``5``, weil eine
    Nachkommastelle ohne Aussage nur Platz kostet.
    """
    if entry.required:
        return str(_("erforderlich"))
    if isinstance(entry.default, bool):
        return str(_("an") if entry.default else _("aus"))
    if entry.default is None:
        return ""
    if not technical and isinstance(entry.default, (tuple, list)) and not entry.default:
        return ""
    if isinstance(entry.default, (int, float)):
        return format_decimal(entry.default)
    if not technical and entry.choices and entry.default in entry.choices:
        return choice_label(str(entry.default))
    return f"{entry.default}"


def parameter_table(parameters: tuple[ParamSpec, ...], *, technical: bool = True) -> list[str]:
    """Die Parametertabelle einer Operation, als Markdown-Zeilen.

    **Der Titel steht vorn, der Schlüssel dahinter.** Vorher war es umgekehrt:
    die Spalte „Parameter" trug ``fill_holes``, ``small_components``,
    ``self_intersections`` — die internen englischen Namen, in Monospace, in
    einem deutschen Handbuch —, und was sie bedeuten, stand ganz rechts. Der
    Schlüssel bleibt in der technischen Ausgabe stehen: Kommandozeile und
    Agent brauchen ihn. ``technical=False`` zeigt nur den Kundentitel und
    benennt Vorgaben, Auswahlwerte und Bedingungen wie der Dialog.

    **Leere Spalten fallen weg.** Bei der Reparatur waren „Einheit" und
    „Bereich" über die ganze Tabelle leer; eine Spalte, die nichts trägt, ist
    kein Platzhalter für später, sondern eine Frage, die der Leser sich selbst
    stellt.
    """
    # Migrationswerte bleiben im gespeicherten Schema, sind aber auch in der
    # technischen Referenz keine Eingaben für neue Schritte (RM-422).
    parameters = tuple(entry for entry in parameters if not entry.internal)
    if not parameters:
        return []
    if not technical:
        # Nur die Textansicht erhält übersetzte Bedingungswerte. Die gemeinsame
        # Satzbildung verfolgt weiterhin dieselben verschachtelten Bedingungen;
        # die eigentlichen Schemata behalten ihre gespeicherten Schlüssel.
        parameters = tuple(
            replace(
                entry,
                depends_on=(
                    entry.depends_on[0],
                    tuple(
                        choice_label(value) if isinstance(value, str) else value
                        for value in entry.depends_on[1]
                    ),
                ),
            )
            if entry.depends_on is not None
            else entry
            for entry in parameters
        )
    columns: tuple[tuple[str, Callable[[ParamSpec], str]], ...] = (
        (
            str(_("Parameter")),
            lambda entry: f"{entry.title} `{entry.name}`" if technical else str(entry.title),
        ),
        (str(_("Einheit")), lambda entry: entry.unit or ""),
        (str(_("Vorgabe")), lambda entry: _default_of(entry, technical=technical)),
        (str(_("Bereich")), lambda entry: _span_of(entry, technical=technical)),
        (str(_("Bedeutung")), lambda entry: _meaning_of(entry, parameters)),
    )
    shown = [
        (title, value)
        for index, (title, value) in enumerate(columns)
        if index == 0 or any(value(entry) for entry in parameters)
    ]

    lines = ["| " + " | ".join(title for title, _value in shown) + " |"]
    lines.append("|" + "---|" * len(shown))
    for entry in parameters:
        lines.append("| " + " | ".join(value(entry) for _title, value in shown) + " |")
    lines.append("")
    return lines
