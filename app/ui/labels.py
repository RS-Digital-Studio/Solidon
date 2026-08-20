"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor

from app.core import figures
from app.core.activation import Activation
from app.core.errors import AppError
from app.core.registry import MENU_GROUPS as MENU_GROUPS
from app.core.registry import group_title as group_title
from app.core.types import Feature, FeatureId
from app.core.units import LengthUnit, format_length, format_volume
from app.i18n import TranslatableText, _, tr

# Die Zuordnung Kategorie → Menü (MENU_GROUPS, group_title) lebt seit der
# Agent-Vertiefung (4.3) im Register: neben Leiste und Kontextmenü braucht sie
# jetzt auch der Kern — die Werkzeugbeschreibungen nennen den Menüort, damit
# der Chat als Suchfeld taugt (§2.6). Die Nutzer der Oberfläche importieren
# beide weiter von hier; der Import darüber ist die Weiterleitung.


def localised(text: str) -> str:
    """Setzt das Dezimaltrennzeichen der Anzeigesprache ein.

    Der Kern rechnet und schreibt mit Punkt — das ist richtig, dort ist eine
    Zahl ein Wert und keine Anzeige. Nur kam sie so auch beim Nutzer an: im
    Objektbaum standen die Maße mit Punkt, vierzig Pixel neben einem
    Eingabefeld mit Komma. Zwei Schreibweisen derselben Zahl im selben Blick.

    Gefragt wird ``QLocale`` und nicht die Sprache selbst, weil die
    Eingabefelder es ebenso tun — eine Quelle, oder das Problem kommt an der
    nächsten Stelle wieder.
    """
    separator = QLocale().decimalPoint()
    return text.replace(".", separator) if separator != "." else text


def length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Eine Länge, wie die Oberfläche sie schreibt."""
    return localised(format_length(value_mm, unit, with_unit))


def compact_length(value_mm: float, unit: LengthUnit = "mm") -> str:
    """Dieselbe Länge, ohne Nachkommastellen, die nichts sagen.

    „60,00" braucht Platz und trägt genau so viel Auskunft wie „60" — die
    Nullen stehen dort, weil die Formatierung eine feste Stellenzahl hat,
    nicht weil jemand sie gemessen hätte. Wo ein Maß wirklich krumm ist,
    bleiben die Stellen stehen: „60,25" sagt etwas anderes als „60", und
    genau diesen Unterschied darf eine Abkürzung nicht verschlucken.

    Für Spalten und Zeilen, die eng sind. Wo Platz ist, gilt weiter
    :func:`length` — eine Anzeige, die zwischen zwei Schreibweisen springt,
    weil das Fenster schmaler wurde, ist schlimmer als eine lange.
    """
    text = format_length(value_mm, unit, with_unit=False)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return localised(text or "0")


def volume(value_mm3: float, unit: LengthUnit = "mm") -> str:
    """Ein Volumen, wie die Oberfläche es schreibt."""
    return localised(format_volume(value_mm3, unit))


#: Grundfarben nach Farbton, in Grad. Die Grenze gilt bis zu diesem Wert.
#:
#: Als ``_()`` und nicht als nackte Zeichenkette: der Sprachtest sammelt die
#: Texte aus dem Quelltext, und was nur als Variable in ein ``tr()`` geht,
#: findet er nicht — es stünde übersetzt im Katalog und gälte trotzdem als
#: verwaist.
_HUES: tuple[tuple[int, TranslatableText], ...] = (
    (15, _("Rot")),
    (45, _("Orange")),
    (70, _("Gelb")),
    (160, _("Grün")),
    (200, _("Türkis")),
    (260, _("Blau")),
    (290, _("Violett")),
    (345, _("Magenta")),
    (360, _("Rot")),
)

_BLACK = _("Schwarz")
_WHITE = _("Weiß")
_GREY = _("Grau")
_BROWN = _("Braun")


def colour_name(value: str) -> str:
    """Eine Farbe, wie man sie nennt — nicht, wie man sie schreibt.

    Über dem Filamentfeld stand „#4A90D9". Das ist der genaue Wert und
    beschreibt für niemanden eine Spule im Regal; wer sein Filament sucht, sucht
    Blau.

    Grob mit Absicht: Filamentfarben sind Regalfarben, und ein Name wie
    „Kornblumenblau" wäre genauer und trotzdem nicht die Spule, die dasteht.
    Der Hexwert bleibt daneben stehen, wo er hingehört — im Tooltip.
    """
    colour = QColor(value)
    if not colour.isValid():
        return value
    hue = colour.hslHue()
    saturation = colour.hslSaturation()
    lightness = colour.lightness()
    if lightness < 40:
        return str(_BLACK)
    if lightness > 225 and saturation < 40:
        return str(_WHITE)
    if saturation < 40:
        return str(_GREY)
    if hue < 0:
        return value
    for limit, name in _HUES:
        if hue <= limit:
            # Dunkles Orange heißt Braun, und nur dort — bei jeder anderen
            # Farbe ist Dunkelheit kein eigener Name.
            if name.msgid == "Orange" and lightness < 110:
                return str(_BROWN)
            return str(name)
    return value


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
    "mouth": _("Mündung"),
    "centre": _("Mitte"),
    # Die acht Texturmuster standen als „knurl_diamond" und „voronoi" im
    # Dialog: englische Schlüssel, unübersetzt, und damit gegen Regel 20 dem
    # Geist nach. Die Namen kommen aus dem Abbildungskatalog, der dieselben
    # Kacheln beschriftet — zwei Listen wären eine Frage der Zeit.
    **figures.TEXTURE_NAMES,
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
    "origin": _("Ursprung"),
    "bed": _("Druckbett"),
    "corner": _("Ecke"),
    # Wie eine Kollision geprüft wurde: genau am Netz oder nur über die
    # Hüllquader. Der Befund trug „exact" und „box" als rohes Englisch in
    # den Tooltip — dieselbe Sorte Fund wie bei den Texturmustern.
    "exact": _("Genau"),
    "box": _("Über den Hüllquader"),
    "pin": _("Stift"),
    "bore": _("Bohrung"),
    "rectangle": _("Rechteck"),
    "circle": _("Kreis"),
    "polygon": _("Vieleck"),
    "slot": _("Langloch"),
    # Die vier Verbinder. „round" und „hex" wären als Schlüssel noch zu
    # erraten, „dovetail" und „snap" nicht — und das sind die beiden, für die
    # man sich bewusst entscheidet.
    "round": _("Rund"),
    "hex": _("Sechskant"),
    "dovetail": _("Schwalbenschwanz"),
    "snap": _("Schnapper"),
    "honeycomb": _("Wabe"),
    "cubic": _("Würfelgitter"),
    "auto": _("Automatisch"),
}


#: Was hinter einem Wert-Schlüssel steht, in der Sprache des Nutzers.
#:
#: ``Finding.values`` und ``AppError.values`` tragen Zahlen, und ihre Schlüssel
#: sind Bezeichner: englisch, mit Unterstrich, mit Einheitensuffix. Die
#: Oberfläche schrieb sie **roh** hin — im Befund-Tooltip und in den
#: Einzelheiten eines Fehlers stand „oversize_mm: 12.4" und „open_edges: 6".
#: Das ist eine feste Zeichenkette in der Oberfläche mit einem Umweg (Regel 20),
#: und für den Leser ist es die Sorte Text, die man überliest statt liest.
#:
#: Die Einheit wird **nicht** eingetragen, sondern aus dem Suffix gelesen
#: (:data:`_VALUE_UNITS`): ``size_mm`` und ``size`` teilen sich einen Eintrag,
#: und ein neuer Schlüssel mit bekanntem Stamm ist damit schon übersetzt.
#:
#: Vollständig gehalten wird die Liste nicht von Hand — von Hand heißt driften.
#: ``tests/test_value_labels.py`` liest jeden ``values=``-Schlüssel aus
#: ``app/core`` per AST und wird rot, sobald einer keine Beschriftung hat.
_VALUE_NAMES: dict[str, TranslatableText] = {
    "a": _("Erstes"),
    # Was eine Ausnahme selbst beisteuert (``_with_values`` in errors.py).
    # Sieben Schlüssel standen als rohes Englisch im Tooltip, weil der
    # Wächter nur Wörterbücher sah und keine Aufrufe.
    "action": _("Handlung"),
    "attempted": _("Versuchte Stufen"),
    "exit_code": _("Rückgabewert"),
    "first": _("Erste Bedingung"),
    "overshoot": _("Überstand je Achse"),
    "second": _("Zweite Bedingung"),
    "tool": _("Programm"),
    "actual": _("Tatsächlich"),
    "after": _("Nachher"),
    "alignment": _("Ausrichtung"),
    "amount": _("Betrag"),
    "annotation": _("Anmerkung"),
    "app_major": _("Programmfassung"),
    "axes": _("Achsen"),
    "axis": _("Achse"),
    "b": _("Zweites"),
    "before": _("Vorher"),
    "bones": _("Knochen"),
    "bore": _("Bohrung"),
    "brush": _("Pinsel"),
    "bytes": _("Bytes"),
    "candidates": _("Kandidaten"),
    "cavities": _("Hohlräume"),
    "chain": _("Kette"),
    "changes": _("Änderungen"),
    "character": _("Zeichen"),
    "choice": _("Wahl"),
    "choices": _("Auswahl"),
    "checked": _("Geprüft"),
    "clearance": _("Spiel"),
    "comfortable": _("Bequem"),
    "components": _("Komponenten"),
    "constraint": _("Bedingung"),
    "contours": _("Konturen"),
    "core": _("Kern"),
    "count": _("Anzahl"),
    "cut": _("Schnitt"),
    "cycle": _("Zyklus"),
    "depth": _("Tiefe"),
    "deviation": _("Abweichung"),
    "diameter": _("Durchmesser"),
    "drawn_width": _("Gezeichnete Breite"),
    "edge": _("Kante"),
    "edges": _("Kanten"),
    "entries": _("Einträge"),
    "estimated": _("Geschätzt"),
    "expected": _("Erwartet"),
    "expected_prefix": _("Erwarteter Anfang"),
    "faces": _("Flächen"),
    "feature": _("Merkmal"),
    "field": _("Feld"),
    "file": _("Datei"),
    "file_version": _("Dateifassung"),
    "first_kind": _("Erste Art"),
    "fit": _("Passung"),
    "excess": _("Überstand"),
    "footprint": _("Standfläche"),
    "formats": _("Formate"),
    "from": _("Von"),
    "gap": _("Spalt"),
    "given": _("Vorhanden"),
    "grams": _("Gramm"),
    "grid": _("Raster"),
    "groups": _("Gruppen"),
    "height": _("Höhe"),
    "key_major": _("Schlüsselfassung"),
    "kind": _("Art"),
    "known": _("Bekannt"),
    "known_faces": _("Bekannte Flächen"),
    "layer": _("Schicht"),
    "layer_height": _("Schichthöhe"),
    "layers": _("Schichten"),
    "limit": _("Grenze"),
    "materials": _("Materialien"),
    "lost": _("Verloren"),
    "major": _("Hauptfassung"),
    "material": _("Material"),
    "maximum": _("Höchstwert"),
    "measured": _("Gemessen"),
    "minimum": _("Mindestwert"),
    "minutes": _("Minuten"),
    "missing": _("Fehlt"),
    "name": _("Name"),
    "neck": _("Hals"),
    "needed": _("Nötig"),
    "node": _("Knoten"),
    "nominal": _("Nennmaß"),
    "now": _("Jetzt"),
    "nozzle": _("Düse"),
    "object": _("Objekt"),
    "op": _("Operation"),
    "open_edges": _("Offene Kanten"),
    "operation": _("Operation"),
    "operations": _("Operationen"),
    "output": _("Ausgabe"),
    "overhang": _("Überhang"),
    "oversize": _("Übermaß"),
    "parameter": _("Parameter"),
    "params": _("Parameter"),
    "part": _("Baustein"),
    "parts": _("Teile"),
    "path": _("Pfad"),
    "pitch": _("Steigung"),
    "pixels": _("Bildpunkte"),
    "plate": _("Platte"),
    "plates": _("Platten"),
    "posed": _("Gestellt"),
    "position": _("Position"),
    "printer": _("Drucker"),
    "produced": _("Erzeugt"),
    "profile": _("Profil"),
    "radius": _("Radius"),
    "reachable": _("Erreichbar"),
    "reason": _("Grund"),
    "reference": _("Bezug"),
    "refused": _("Abgelehnt"),
    "regions": _("Bereiche"),
    "removed": _("Entfernt"),
    "requested": _("Angefragt"),
    "residual": _("Rest"),
    "role": _("Rolle"),
    "samples": _("Stichproben"),
    "saved": _("Gespart"),
    "scale": _("Maßstab"),
    "scheme": _("Schema"),
    "seams": _("Nähte"),
    "second_kind": _("Zweite Art"),
    "seconds": _("Sekunden"),
    "seed": _("Startwert"),
    "settings": _("Einstellungen"),
    "share": _("Anteil"),
    "shortcut": _("Kürzel"),
    "size": _("Größe"),
    "slicer": _("Slicer"),
    "slot": _("Platz"),
    "slots": _("Plätze"),
    "source": _("Quelle"),
    "sources": _("Quellen"),
    "span": _("Spannweite"),
    "stages": _("Stufen"),
    "status": _("Zustand"),
    "strokes": _("Striche"),
    "suffix": _("Endung"),
    "support": _("Stützen"),
    "supported": _("Unterstützt"),
    "target": _("Ziel"),
    "text": _("Text"),
    "to": _("Nach"),
    "tolerance": _("Toleranz"),
    "transaction": _("Transaktion"),
    "triangles": _("Dreiecke"),
    "type": _("Art"),
    "unit": _("Einheit"),
    "unpacked": _("Entpackt"),
    "url": _("Adresse"),
    "used_by": _("Benutzt von"),
    "value": _("Wert"),
    "vents": _("Entlüftungen"),
    "vertices": _("Ecken"),
    "volume": _("Volumen"),
    "wall": _("Wandstärke"),
    "wanted": _("Gewünscht"),
    "what": _("Was"),
    "where": _("Wo"),
    "z": _("Z"),
}

#: Welches Suffix welche Einheit meint.
#:
#: Nach Länge sortiert geprüft, sonst schluckt _mm das _mm3.
_VALUE_UNITS: tuple[tuple[str, str], ...] = (
    ("_mm3", "mm³"),
    ("_mm2", "mm²"),
    ("_cm3", "cm³"),
    ("_percent", "%"),
    ("_deg", "°"),
    ("_mm", "mm"),
)


def value_label(key: str) -> str:
    """Die Beschriftung zu einem Wert-Schlüssel — mit Einheit, wenn er eine trägt.

    Unbekanntes kommt durch, wie es ist: Ein Schlüssel aus einem Zweig, den der
    Test nicht statisch sieht (``values=dict(...)``), soll den Tooltip nicht
    leeren. Der Test hält die Liste vollständig, diese Zeile hält sie harmlos.
    """
    for suffix, unit in _VALUE_UNITS:
        if key.endswith(suffix):
            name = _VALUE_NAMES.get(key[: -len(suffix)])
            return f"{name} ({unit})" if name is not None else key
    name = _VALUE_NAMES.get(key)
    return str(name) if name is not None else key


#: Was als Zahl durchgeht: Vorzeichen, Ziffern, höchstens ein Punkt, dahinter
#: höchstens eine Einheit ohne Ziffern und ohne Punkt.
#:
#: Die Einheit darf nicht selbst Ziffern oder Punkte enthalten, sonst passte
#: „1.2.3" als Zahl mit der Einheit „.3" — und eine Fassungsnummer wäre in der
#: Anzeige zerschnitten.
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?(\s*[^\d.\s]+)?$")


def localised_value(value: object) -> str:
    """Ein Wert, wie er beim Nutzer steht: Zahlen mit Komma, alles andere heil.

    **Hier stand :func:`localised` auf jedem Wert**, und das war eine
    Textverfälschung: Die Funktion tauscht jeden Punkt gegen das
    Dezimaltrennzeichen der Sprache, und Befunde tragen Pfade, Adressen und
    Dateiendungen. In der deutschen Oberfläche stand damit
    ``Pfad: sources/1_cube_clean,stl``, ``Adresse: https://example,com/x,stl``
    und ``Endung: ,step`` — ein Pfad, den niemand benutzen kann, und eine
    Adresse, die falsch ist.

    Was keine Zahl ist, geht durch :func:`choice_label`: Ein Auswahlwert wie
    ``exact`` bekommt dort seinen Namen, und alles Unbekannte kommt unverändert
    durch. Zwei Wege, eine Zeile — und keiner davon fasst einen Pfad an.
    """
    text = str(value)
    return localised(text) if _NUMBER.match(text) else choice_label(text)


def value_line(key: str, value: object) -> str:
    """Eine Zeile „Beschriftung: Wert" für Tooltip und Einzelheiten.

    Die Zahl bekommt ihr Komma (§13), der Rest bleibt, wie er ist — siehe
    :func:`localised_value`.
    """
    return f"{value_label(key)}: {localised_value(value)}"


def kind_requirement(spec: Any, kinds: Sequence[str]) -> str | None:
    """Warum diese Operation auf dieser Auswahl nicht geht — oder ``None``.

    Eine Operation des exakten Kerns trägt ``requires_kind="brep"``; auf einem
    Netz kann sie nicht arbeiten. Die Menüleiste graut sie dann aus und schreibt
    diesen Satz in den Tooltip, statt sie anzubieten und nach dem ausgefüllten
    Dialog abzulehnen (Regel 19).

    **Der Satz steht hier, weil zwei Ansichten ihn brauchen.** Das Kontextmenü
    am Körper bot alle Operationen mit einem Eingang an, ungeprüft — auch die
    sieben des exakten Kerns. Wer am Netz-Körper *Verrunden* wählte, füllte
    einen Dialog aus und bekam danach eine Absage: genau die Sackgasse, die die
    Menüleiste zwei Dateien weiter vermeidet. Zwei Stellen, dieselbe Auskunft —
    also gehört sie in diese Datei und nicht zweimal in die Oberfläche.
    """
    if not spec.requires_kind or not kinds:
        return None
    if all(kind == spec.requires_kind for kind in kinds):
        return None
    return str(
        tr(
            "Diese Operation braucht einen exakten Körper (B-Rep). Exakte Körper "
            "kommen aus einer STEP-Datei oder aus den Grundformen mit „Exakt“."
        )
    )


def by_title(entries: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """Profile in der Reihenfolge, in der sie gelesen werden.

    Sortiert wurde nach der Kennung, angezeigt wird der Titel — und die beiden
    laufen auseinander, sobald ein Hersteller anders heißt als sein Schlüssel.
    In der Druckerliste stand „Elegoo Centauri Carbon 2" zwischen Bambu und
    Creality (``centauri-carbon-2``) und „Allgemeiner FDM-Drucker 220 mm"
    zwischen Elegoo und Prusa (``generic-220``). Für den, der die Liste liest,
    war sie unsortiert.
    """
    return sorted(entries.items(), key=lambda pair: str(pair[1].title).casefold())


def choice_label(value: str) -> str:
    """Ein Auswahlwert, wie der Nutzer ihn lesen kann.

    Normteilschlüssel sind englisch und kurz, weil sie Schlüssel sind — im
    Dialog standen sie aber als Beschriftung: „cable-5", „ptfe-4x2". Das tippt
    niemand ab und niemand erkennt es, ohne die Tabelle danebenzulegen.

    Erzeugt aus den Maßen und nicht als zweite Liste gepflegt: sonst hätte ein
    neues Normteil einen Namen an einer Stelle und keinen an der anderen. Was
    die Tabelle nicht kennt — „M4", „PLA", „z" —, bleibt, wie es ist; diese
    Werte sind selbst schon der Name.
    """
    from app.core.knowledge import standards

    named = _CHOICE_NAMES.get(value)
    if named is not None:
        return str(named)
    try:
        tube = standards.tube(value)
    except AppError:
        return value
    if tube.inner > 0.0:
        return f"{tr('Schlauch')} {length(tube.outer, with_unit=False)} × {length(tube.inner)}"
    return f"{tr('Rundkabel')} Ø{length(tube.outer)}"


#: Wie eine Fläche heißt, deren Normale in diese Richtung zeigt. Die Reihenfolge
#: ist die der Achsen; ein Vorzeichen entscheidet zwischen den beiden Namen.
#:
#: Als ``_()``-Literale und nicht als nackte Zeichenketten mit ``tr()``
#: darüber: der Extraktor liest den Quelltext, und ``tr(variable)`` sieht er
#: nicht. Sechs Namen wären stumm ins Englische durchgereicht worden.
_SIDES: tuple[tuple[TranslatableText, TranslatableText], ...] = (
    (_("Rechte Seite"), _("Linke Seite")),
    (_("Rückseite"), _("Vorderseite")),
    (_("Oberseite"), _("Unterseite")),
)

#: Ab wann eine Normale als achsparallel gilt. Darunter ist die Fläche schräg,
#: und ein Seitenname wäre eine Behauptung.
_AXIS_ALIGNED = 0.9


def feature_name(feature_id: FeatureId, feature: Feature) -> str:
    """Wie das Merkmal heißt, wenn man es jemandem zeigt.

    Im Baum stand `face_2` — die Kennung, mit der der Op-Stack rechnet, und
    für einen Menschen eine Nummer ohne Aussage. Eine ebene Fläche weiß, wohin
    sie zeigt, und „Oberseite" ist dieselbe Auskunft in lesbar. Die Kennung
    bleibt: sie steht im Tooltip und in jedem Parameterfeld.
    """
    if feature.kind == "face":
        normal = feature.params.get("normal")
        if isinstance(normal, tuple | list) and len(normal) == 3:
            for axis, (positive, negative) in enumerate(_SIDES):
                value = float(normal[axis])
                if abs(value) >= _AXIS_ALIGNED:
                    return str(positive if value > 0 else negative)
        return tr("Schrägfläche")
    if feature.kind == "hole":
        return f"{tr('Bohrung')} {feature_id.rsplit('_', 1)[-1]}"
    if feature.kind == "edge_loop":
        return tr("Offene Kante")
    return feature_id


def feature_measure(feature: Feature) -> str:
    """Die eine Zahl, die dieses Merkmal ausmacht — ohne seinen Namen.

    Getrennt vom Namen, weil der Objektbaum zwei Spalten hat: dort stand die
    ganze Beschriftung links und rechts der Typ („hole", „face"). Links war
    damit abgeschnitten, was rechts gefehlt hat.
    """
    params = feature.params
    if feature.kind == "hole":
        return f"Ø{length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "face":
        return f"{float(params.get('area', 0.0)):.0f} mm²"
    if feature.kind == "edge_loop":
        return f"{params.get('open_edges', 0)} {tr('offene Kanten')}"
    return ""


def feature_label(feature_id: FeatureId, feature: Feature) -> str:
    """``Bohrung 3 · ⌀4,2`` — die Beschriftung, die §18.5 verlangt, Name
    zuerst.

    Für die Stellen, an denen nur eine Zeile Platz hat: Viewport-Beschriftung
    und Statusleiste. Wo zwei Spalten stehen, gehören Name und Maß getrennt.
    """
    measure = feature_measure(feature)
    name = feature_name(feature_id, feature)
    return f"{name} · {measure}" if measure else name


def deadline_date(state: Activation) -> str:
    """Der Stichtag der Demo, wie ihn der Nutzer liest.

    Ein Ort dafür, weil er an fünf Stellen steht: Statusleiste, Über-Dialog,
    Freischaltdialog, Ersteinrichtung und die Meldung, mit der sich eine
    abgelaufene Demo verabschiedet. Fünf Formulierungen desselben Datums
    lesen sich wie fünf verschiedene Fristen.
    """
    return state.deadline.strftime("%d.%m.%Y") if state.deadline is not None else ""


def demo_line(state: Activation) -> str:
    """„Demo — noch 47 Tage, bis zum 30.10.2026".

    Steht dauerhaft in der Statusleiste und nicht erst am vorletzten Tag. Für
    ein Kaufprodukt wäre das Druck (Veröffentlichungskonzept §2 C); für eine
    Demo mit hartem Ende ist es die Zusage, dass niemand überrascht wird —
    wer am 28.10. ein Projekt anfängt, soll es vorher gewusst haben.
    """
    return tr("Demo — noch {days} Tage, bis zum {date}").format(
        days=state.days_left, date=deadline_date(state)
    )
