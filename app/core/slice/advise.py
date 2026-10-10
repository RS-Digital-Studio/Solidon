"""Einstellungen, die die Geometrie selbst verlangt (Bauplan §22.2, §29).

Der Startbestand in ``print_settings.toml`` weiß, was PETG bei 240 Grad tut.
Er weiß nicht, dass *dieses* Teil auf zwei Quadratzentimetern steht, dass es
im dritten Zentimeter eine schwebende Insel hat, oder dass seine dünnste Wand
schmaler ist als die Linie, die der Drucker legen kann. Das weiß die
Schichtanalyse — und dieses Modul übersetzt es in Werte.

Jeder Vorschlag trägt seinen Grund (:class:`SettingAdvice`). Das ist keine
Höflichkeit: eine Zahl, deren Herkunft niemand nachvollziehen kann, ist im
Zweifel schlechter als die Vorgabe, weil sie sich nicht widerlegen lässt. Wer
den Grund liest, kann widersprechen — und genau das soll er können, denn
angewandt wird nichts von allein (§2.7).

Was hier entsteht, ist eine Empfehlung aus **interner** Analyse und trägt
deshalb ``source="internal"``, wo es in den Prüfbericht geht. Mit gemessenen
Werten aus dem G-Code wird es nie vermischt (Regel 14, §22.5).
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

import numpy as np

from app.core import build_area
from app.core.errors import (
    CALIBRATE_MATERIAL,
    CHOOSE_PRINTER,
    OPEN_PRINT_SETTINGS,
    SHOW_SUPPORT_NEED,
    ValidationError,
)
from app.core.knowledge import print_settings as settings_table
from app.core.log import get_logger
from app.core.slice.analysis import (
    OVERHANG_LAYER_MINIMUM,
    OVERHANG_LAYER_WORTH_SUPPORT,
    OVERHANG_MARGIN,
    SPAN_INTERESTING,
    ModelSupport,
    _layer_shape,
    cantilevers,
    channel_space,
    island_layers,
    largest_overhang_patch,
    largest_sloped_patch,
    ledge_space,
    ledges,
    model_support,
    narrow_share,
    narrowest_measured,
    open_bridge_width,
    piece_area,
    smooth_outline_height,
    steep_reach,
    tapered_layers,
    thinnest_spot,
    tip_islands,
    total_overhang,
    worth_support,
)
from app.core.types import (
    BoundingBox,
    CancelToken,
    Finding,
    MaterialProfile,
    PrintSettings,
    Profile,
    SceneObject,
    SettingAdvice,
    Severity,
    SliceResult,
)
from app.core.units import EPS_GEOM, format_length, is_close, is_zero
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.export.slicer_keys import SlicerFlavour

_log = get_logger(__name__)

#: Unter dieser Standfläche in mm² hält ein Skirt das Teil nicht mehr — ein
#: Brim verdoppelt die Haftfläche eines schlanken Körpers, ohne die Geometrie
#: anzufassen.
SMALL_FOOTPRINT = 400.0

#: Ab diesem Verhältnis von Höhe zu kleinster Grundkante ist ein Teil schlank
#: genug, dass die Düse es beim Anfahren kippen kann.
SLENDER_RATIO = settings_table.SLENDER_RATIO

#: Wie breit ein Steg der ersten Schicht höchstens ist, um als schmal zu gelten,
#: in Bahnbreiten der ersten Schicht. Auf Roberts Minigolf-Platte (27.09.2026)
#: rissen zwischen Loch 3, Loch 4 und dem inneren Bogen die kurzen Bodenbahnen
#: der ersten Schicht bei 105 mm/s; die Stege dort sind schmaler als sechs
#: Bahnen zu 0,5 mm.
NARROW_WEB_LINES: Final = 6.0

#: Ab welchem Anteil der ersten Schicht in schmalen Stegen deren Tempo zählt.
#: Die Minigolf-Platte trägt 22 % darin, der Wedge-Lock 4 %, die Waschschüssel
#: auf ihren Füßen 2 % (``analysis.narrow_share``, 27.09.2026).
NARROW_WEB_SHARE: Final = 0.10

#: Ab welcher Fläche schmaler Stege in der ersten Schicht deren Tempo zählt,
#: in mm² — auch unter :data:`NARROW_WEB_SHARE`. Der Rumpf ``Gövde59`` der
#: Minigolf-Platte, an dem die Bodenbahnen rissen, trägt 195 mm² bei 8,6 %;
#: im Korpus von 186 Körpern liegt der nächste darunter bei 106 mm²
#: (Besenhalter), der Wedge-Lock bei 78 (Eichung 27.09.2026).
NARROW_WEB_AREA: Final = 100.0

#: Das Tempo der ersten Schicht über schmalen Stegen, in mm/s. Mit 50 mm/s für
#: die ganze erste Schicht lief Roberts zweiter Druck der Platte sauber; es ist
#: das Wandtempo der ersten Schicht in Elegoos und Bambus Standardprozessen.
NARROW_WEB_SPEED: Final = 50.0

#: Ab diesem Anteil der Schichten mit einem Keil in der Wand lohnt es, die
#: Außenwand zuerst zu legen. Der Becher im Organizer vom 20.09.2026 steht auf
#: neun Zehnteln der Höhe; ein Keil, der nur eine Schulter lang ist, hinterlässt
#: ein paar Rillen, aber kein Band, für das man die Wandreihenfolge ändert.
TAPERED_LAYERS_SHARE = 0.2

#: So viele Schichten mit Inseln machen aus Gitterstützen Baumstützen: viele
#: verteilte Ansatzpunkte sind genau der Fall, für den Bäume gebaut wurden.
TREE_FROM_ISLANDS = 8

#: Ab welcher Höhe über dem Bett, in mm, Baumstämme zwei Wände brauchen (RM-584,
#: Recherche Nr. 5): Mit einer brechen oder kippen hohe Bäume, und ein
#: abgerissener Ast lässt den Überhang darüber in die Luft drucken.
TALL_TREE_HEIGHT: Final = 100.0

#: Zwei Wände je Baumstamm für hohe Bäume.
TALL_TREE_WALLS: Final = 2

#: Kleinste Schichtfläche in mm², unter der eine Schicht so schnell durch ist,
#: dass die vorige noch weich liegt.
THIN_LAYER_AREA = 120.0

#: Beschleunigung in mm/s² für eine Außenwand, deren Maß zählt. Der Wert ist
#: nicht die Grenze der Maschine, sondern die, ab der die Kontur ausschwingt —
#: und eine Passung ist auf Zehntelmillimeter gerechnet.
CAREFUL_ACCELERATION = 2000.0

#: Wandtempo in mm/s für einen schlanken Körper auf kleinem Fuß — ein Drittel
#: von Elegoos 200 mm/s. Die Kippkraft kommt vor allem aus der Beschleunigung
#: (:data:`CAREFUL_ACCELERATION`); das Tempo nimmt der Düse den Rest. An
#: Roberts Stangenplatte (30.09.2026, ElegooSlicer) kostete das 29 Minuten,
#: das Tempo einer Passungswand (30 mm/s) 1 h 46 min.
SLENDER_WALL_SPEED = 60.0

#: Ab wie vielen Linienbreiten eine Wand auf ganze Bahnen aufgeht. Darunter
#: bleibt beim klassischen Generator eine Lücke, die mit Lückenfüllung
#: geschlossen wird — bei einem Federarm ist genau das der Bruch.
LINES_FOR_CLASSIC = 3.0

#: Mindestschichtzeit in Sekunden für solche Spitzen, wo sonst keine gilt.
#: Weniger, und der Turm kippt in sich zusammen; mehr, und die Düse kokelt auf
#: der Stelle.
THIN_LAYER_SECONDS = 15.0

#: Mindesttempo in mm/s für Körper mit kleinen Spitzen. Damit erreicht eine
#: Schicht von 8,4 mm² bei 0,42 mm Bahnbreite (20 mm Weg) Elegoos 4 s, am
#: Drachen alles außer dem letzten Millimeter jeder Spitze; die Slicer lassen
#: es zu (Orca und PrusaSlicer ab 1 mm/s).
TIP_SPEED = 5.0

#: So hoch müssen zu kurze Schichten zusammen sein, bevor gebremst wird — die
#: oberste Schicht einer Kuppe ist immer klein.
TIP_HEIGHT = 1.0

#: Weiche Filamente stauchen im Antrieb, statt zu fördern. Darüber wird der
#: Faden im Bowden zur Feder.
FLEXIBLE_MAX_SPEED = 30.0

#: Materialien, die sich beim Abkühlen zusammenziehen. Ohne geschlossenen
#: Bauraum reißen hohe Teile an den Ecken auf.
WARPING_MATERIALS: Final = frozenset({"asa", "abs"})

#: Materialien, die zu weich sind, um schnell gefördert zu werden.
FLEXIBLE_MATERIALS: Final = frozenset({"tpu-95a"})

#: Mehr Wände schlägt hier nichts vor — es ist die Obergrenze des Feldes, in
#: das der Vorschlag hineingeht (``shell.wall_count`` in
#: ``knowledge.print_fields.FIELDS``).
#:
#: Ein Vorschlag über diesem Wert wäre nicht bloß unpraktisch, sondern
#: gefährlich: Er ist **übernehmbar**, das Feld kann ihn aber nicht anzeigen.
#: Gemessen am 03.09.2026 mit einem Zapfen von Ø 60 mm — Vorschlag 36,
#: „Vorschläge übernehmen" schrieb 36 ins Dokument, die übergebene Datei trug
#: ``wall_loops: 36``, und der Dialog zeigte daneben 20. Bei 0,42 mm Bahn sind
#: 36 Wände 15 mm Wandstärke.
#:
#: Der Kern kennt die Oberfläche nicht (Regel 1) und darf das Feld nicht
#: fragen; dass beide Zahlen zusammenpassen, hält
#: ``tests/test_print_settings_ui.py`` fest.
MOST_WALLS_WORTH_SUGGESTING: Final = 20

#: Wie viel des Verbinder-Querschnitts Material sein soll, wenn die Füllung
#: einspringen muss.
#:
#: Keine neue Zahl, sondern dieselbe Schwelle wie beim Wandvorschlag, nur in
#: Fläche statt in Breite: „Material mindestens so breit wie der Kern" heißt
#: im Durchmesser kern = d/2, und ein Kreis mit halbem Durchmesser hat ein
#: Viertel der Fläche — also drei Viertel Material ringsum.
SOLID_SHARE_OF_A_CONNECTOR: Final = 0.75

#: Kammertemperatur, die ein schrumpfendes Material auf einem geschlossenen
#: Gerät braucht. Warm genug, dass die unteren Schichten nicht erstarren,
#: bevor die oberen liegen — und weit unter dem, was der Antrieb aushält.
CHAMBER_FOR_WARPING: Final = 50

#: Schmaler als dieser Anteil des Düsendurchmessers wird keine Bahn — enger
#: gequetscht reißt die Spur ab, statt dünner zu werden. Die Bahnbreiten-Regel
#: senkt bis zu dieser Grenze, der Befund ``settings.wall_below_nozzle``
#: übernimmt darunter. **Eine Zahl für beide Stellen**: Zwei Schwellen für
#: dieselbe Frage ließen dazwischen einen Bereich, in dem beide Antworten
#: falsch sind.
NARROW_LINE_SHARE: Final = 0.85

#: Ab welchem Umfang eine glatte Außenschleife ihre Naht als Linie zeigt, in
#: mm: zwei Rampen der Schrägnaht (``print_settings.SCARF_LENGTH``). Ein Stift
#: unter Ø 13 mm hat keinen Platz für die Rampe, und seine Naht fällt kaum auf.
SCARF_MIN_LOOP: Final = 2.0 * settings_table.SCARF_LENGTH

#: Über wie viel Höhe die glatte Außenwand reichen muss, bevor die Schrägnaht
#: vorgeschlagen wird, in mm. Auf einem flachen Rand wird keine Linie aus der
#: Naht, und die Rampe kostet trotzdem Zeit.
SCARF_MIN_HEIGHT: Final = 10.0


def advise(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult | None = None,
    *,
    bounds: BoundingBox | None = None,
    fit_kinds: Sequence[str] = (),
    connectors: Sequence[float] = (),
    flavour: SlicerFlavour | None = None,
    whole_layers: bool = False,
    organic: Collection[str] = (),
    declined: Collection[str] = (),
    trees: Collection[str] | None = None,
) -> list[SettingAdvice]:
    """Was an diesen Einstellungen für dieses Teil nicht passt (§29).

    ``result`` darf fehlen — dann bleiben die Vorschläge übrig, die allein aus
    Material und Drucker folgen. Das ist der Fall vor dem ersten Schnitt, und
    er soll nicht zu einem leeren Bericht führen.

    ``connectors`` sind die Durchmesser der Verbinder, die beim Teilen
    entstanden sind. Sie stehen neben ``fit_kinds`` und nicht darin: eine
    Passung sagt, dass zwei Flächen aufeinandergehen, ein Verbinderdurchmesser
    sagt, wie dick der Zapfen dabei ist — und nur die zweite Angabe lässt sich
    gegen die Bahnbreite rechnen.

    ``whole_layers`` sagt, dass der Slicer den Stützabstand auf der Platte
    dieses Teils auf ganze Schichten rundet, weil dort ein Reinigungsturm steht;
    ``organic`` sind die Stützarten, die das Programm als organische Bäume auf
    den Schichten des Modells druckt (:func:`rounds_to_whole_layers`, RM-622).
    ``declined`` sind Pfade, deren Vorschlag der Kunde nicht übernimmt — im
    Druckdialog abgewählt, im Export nicht übernommen: Abstand und untere
    Trennschicht fragen dann mit der eigenen Stützart (:func:`printed_style`).
    ``trees`` sind die Stützarten, die das Programm als Bäume druckt
    (``handover.tree_styles``, RM-584), ``None`` ohne Programm: Gitter oder
    Hybrid unter einer großen flachen Decke und die Wände hoher Bäume fragen
    danach.

    **Für einen Resin-Drucker bleibt die Liste leer.** Jede Regel hier spricht
    über Düse, Bahn, Bett, Lüfter oder Rückzug — für Resin nicht falsch
    justiert, sondern gegenstandslos. Ein Bericht, in dem neun von zwanzig
    Zeilen fürs eigene Verfahren leer laufen, wirkt nicht hochwertig, sondern
    unaufmerksam (Resin-Konzept B4).
    """
    if profile.printer.is_resin:
        return []
    advice: list[SettingAdvice] = []
    advice += _from_machine(settings, profile)
    advice += _from_material(settings, profile)
    if result is not None:
        advice += _from_geometry(
            settings, profile, result, bounds, flavour, whole_layers, organic, declined, trees
        )
    if fit_kinds:
        advice += _from_fits(settings, fit_kinds)
    # Erst nach den Regeln oben, und gegen deren Stand gerechnet: Die
    # Wandzahl hängt an der Bahnbreite, und genau die senkt die Regel über die
    # dünnste Stelle. Vorher gerechnet stand im Bericht eine Wandzahl, die zu
    # einer Breite passte, die daneben schon zurückgenommen war — zwei
    # Vorschläge, die zusammen nicht aufgehen.
    advice += _from_connectors(apply(settings, advice), connectors)

    # Der Volumenstrom hängt an Schichthöhe, Bahnbreite und Tempo — und an
    # genau diesen Werten haben die Vorschläge oben womöglich gedreht. Er wird
    # deshalb gegen den Stand *nach* ihnen gerechnet, sonst begrenzt er ein
    # Tempo erneut, das nebenan bereits ausreichend gesenkt wurde.
    # Vor dem Zusammenführen auslassen: Ein nachträglicher Filter verlöre
    # den Passungs- oder TPU-Grund, den der kleinere Flow-Wert verdrängt hat.
    if not settings_table.caps_volumetric_speed(flavour):
        advice += _from_flow(apply(settings, advice))
    advice = _merged(settings, advice)

    _log.info("advising %d settings", len(advice))
    return advice


def _advice(
    settings: PrintSettings,
    *,
    path: str,
    value: object,
    reason: TranslatableText | str,
    severity: Severity = "info",
) -> SettingAdvice:
    """Ein Vorschlag, dessen Ausgangswert aus dem Pfad kommt statt aus der Hand.

    ``was`` stand bis zum 04.09.2026 an siebenundzwanzig Stellen ausgeschrieben
    — und zwar wirkungslos: :func:`_merged` setzt es für **jeden** Vorschlag
    ohnehin neu auf ``read_path(settings, path)``, damit es auch nach dem
    Zusammenführen zweier Regeln der Ausgangswert ist. Wer eine dieser
    siebenundzwanzig Zeilen geändert hätte, hätte nichts geändert; wer den
    Pfad geändert und die Zeile vergessen hätte, hätte es nicht gemerkt.

    Jetzt nennt ein Vorschlag seine Einstellung einmal.
    """
    return SettingAdvice(
        path=path,
        value=value,
        was=settings_table.read_path(settings, path),
        reason=reason,
        severity=severity,
    )


#: Tempi und Beschleunigungen, die ein Vorschlag nur senkt. Die Leerfahrt
#: fehlt: Sie hebt die Maschinenregel auf das, was der Drucker kann.
_BRAKING_PATHS: Final = frozenset(
    {
        "speed.outer_wall",
        "speed.inner_wall",
        "speed.infill",
        "speed.top_surface",
        "speed.first_layer",
        "speed.bridge",
        "speed.acceleration",
        "speed.outer_wall_acceleration",
        "cooling.minimum_speed",
    }
)


def _merged(settings: PrintSettings, advice: list[SettingAdvice]) -> list[SettingAdvice]:
    """Ein Vorschlag je Einstellung, und ``was`` ist immer der Ausgangswert.

    Zwei Regeln können denselben Wert meinen — bei weichem Filament senkt die
    Materialregel das Tempo, und der Volumenstrom will es womöglich noch
    weiter. Zwei Zeilen für dieselbe Einstellung wären keine zwei Vorschläge,
    sondern eine Liste, die sich selbst widerspricht: die spätere Regel hat den
    Stand der früheren gesehen, also gewinnt sie.

    **Eine Bremse lockert keine frühere** (RM-328): Nicht jede Regel rechnet
    gegen den Stand ihrer Vorgänger. Die ruhigen Wände einer schlanken Stange
    (60 mm/s) kamen nach der Materialregel für TPU (30 mm/s) und hoben deren
    Grenze auf. Auf :data:`_BRAKING_PATHS` bleibt deshalb der kleinere Wert,
    mit dem Grund der Regel, die ihn verlangt.
    """
    by_path: dict[str, SettingAdvice] = {}
    for entry in advice:
        earlier = by_path.get(entry.path)
        if (
            earlier is not None
            and entry.path in _BRAKING_PATHS
            and isinstance(earlier.value, int | float)
            and isinstance(entry.value, int | float)
            and earlier.value < entry.value
        ):
            continue
        by_path[entry.path] = replace(entry, was=settings_table.read_path(settings, entry.path))
    # Vorschläge, die nach dem Zusammenführen nichts mehr ändern, fallen weg.
    return [entry for entry in by_path.values() if _differs(entry.value, entry.was)]


def combine(
    settings: PrintSettings,
    groups: Sequence[tuple[PrintSettings, Sequence[SettingAdvice]]],
    *,
    separate: Collection[str] = frozenset(),
    trees: Collection[str] | None = None,
) -> list[SettingAdvice]:
    """Vereint Anforderungen mehrerer Körper an gemeinsame Einstellungen.

    Jede Gruppe enthält ihren effektiven Ausgangsstand und ihre Vorschläge.
    Auch ein Körper ohne Änderungsvorschlag behält seine Anforderungen: Ein
    Würfel kann die schon eingeschalteten Stützen seines Nachbarn nicht
    abschalten. Filamentabhängige Werte werden nur innerhalb desselben
    Materialslots zusammengeführt; verschiedene Spulen behalten eigene Werte.

    **Was je Teil geschrieben wird** (``separate``, im Druckdialog die
    Kontaktpfade aus ``handover.asked_for_contact``), zählt nur, wo ein Körper
    es verlangt: Die übrigen behalten ihren Wert, jedes Teil bekommt seinen
    eigenen (RM-583). Gefragt wird dafür gegen die Grundlage, nicht gegen die
    Übernahme. Innerhalb eines Teils mit mehreren Spulen gilt weiter der Wert,
    der alle einschließt — der Dialog führt erst je Körper zusammen.

    **Gitter und Baum zweier Körper werden Hybrid, wo die Stützart der Platte
    gilt** (RM-584). Steht sie in ``separate`` (``handover.style_per_part``),
    bekommt jedes Teil seine eigene, und Hybrid käme in keiner Datei an. Kennt
    das Programm kein Hybrid (``trees`` ohne ``hybrid``, Cura), werden beide
    Gitter, mit dem Grund der Decke (Nachprüfung RM-584, N3): Hybrid hatte der
    Kunde nie gesehen, und der Ersatzsatz verdrängte den Grund.
    """
    candidates: dict[str, list[SettingAdvice]] = {}
    final = [apply(base, list(entries)) for base, entries in groups]
    for _base, entries in groups:
        for entry in entries:
            candidates.setdefault(entry.path, []).append(entry)
    merged: list[SettingAdvice] = []
    for path, entries in candidates.items():
        relevant = final
        if path == "support.placement":
            relevant = [value for value in final if value.support.style != "none"] or final
        values = [settings_table.read_path(value, path) for value in relevant]
        # Was je Teil geschrieben wird, zählt nur, wo ein Körper es verlangt;
        # die übrigen behalten ihren Wert ohnehin (RM-583).
        # Die Stützart zählt jeden Körper, auch je Teil: Ein Würfel ohne Bedarf
        # schaltet die Stützen des Kegels nicht ab. Getrennt heißt bei ihr nur,
        # dass Gitter und Baum nicht Hybrid werden (RM-584).
        requested = path in separate and path != "support.style"
        value = _combined_value(
            path,
            [entry.value for entry in entries] if requested else values,
            together=path not in separate,
            hybrid=trees is None or "hybrid" in trees,
        )
        was = settings_table.read_path(settings, path)
        if not _differs(value, was):
            continue
        reason = next((entry for entry in entries if not _differs(entry.value, value)), entries[0])
        merged.append(replace(reason, value=value, was=was))
    return merged


def _combined_value(
    path: str, values: Sequence[object], *, together: bool = True, hybrid: bool = True
) -> object:
    """Nimmt je Einstellungsart die Anforderung, die alle Körper einschließt.

    ``together`` heißt, der Wert gilt allen Körpern zugleich; nur dann werden
    Gitter und Baum Hybrid, wo das Programm es kennt (``hybrid``), sonst Gitter."""
    ranks = {
        # ``auto`` steht über „aus" und unter jeder ausdrücklichen Art: Wo ein
        # Körper Bäume verlangt, schließt das den ein, der nur Stützen will.
        # Hybrid schließt Bäume und Gitter ein (RM-584).
        "support.style": ("none", "auto", "grid", "tree", "hybrid"),
        "support.placement": ("build_plate", "everywhere"),
        # Der Auto-Brim des Slicers kann einen Brim legen, ein Skirt nie.
        "adhesion.kind": ("none", "skirt", "auto", "brim", "raft"),
        "shell.wall_generator": ("classic", "arachne"),
    }
    if (
        together
        and path == "support.style"
        and {"grid", "tree"} <= {str(value) for value in values}
    ):
        # Ein Körper mit flacher Decke und einer mit Details auf einer Platte:
        # Hybrid gibt beiden, was sie verlangen (RM-584); ohne Hybrid trägt
        # Gitter die Decke.
        return "hybrid" if hybrid else "grid"
    if path in ranks:
        return max(values, key=lambda value: ranks[path].index(str(value)))
    if all(isinstance(value, bool) for value in values):
        return any(values)
    numbers = [value for value in values if isinstance(value, int | float)]
    if len(numbers) == len(values):
        if path.startswith(("speed.", "layers.")) or path in (
            "cooling.fan_speed",
            "cooling.minimum_speed",
            # Die dichtere Trennschicht hält eine flache Decke auf der Platte;
            # eine lockere ließe sie durchhängen (RM-583).
            "support.interface_spacing",
            # Weniger Fluss braucht nur die freie Brücke; ein Körper ohne Brücke
            # merkt ihn nicht (RM-587).
            "shell.bridge_flow",
        ):
            return min(numbers)
        return max(numbers)
    return values[0]


def _differs(value: object, was: object) -> bool:
    """Unterscheiden sich diese zwei Werte — und bei Zahlen: hörbar?

    Hier stand ``!=``, und das ist auf Fließkomma die falsche Frage (Regel 6).
    Eine gerechnete Bahnbreite, die sich von der eingestellten erst in der
    zwölften Stelle unterscheidet, blieb damit als Vorschlag stehen: im Dialog
    eine Zeile „0,42 → 0,42", die niemand deuten kann und die die vier
    Vorschläge daneben unglaubwürdig macht.

    Text, Wahrheitswerte und Aufzählungen — ``support.style``,
    ``adhesion.kind`` — werden weiter genau verglichen; dort gibt es kein
    „fast gleich".
    """
    if isinstance(value, bool) or isinstance(was, bool):
        return value is not was
    if isinstance(value, int | float) and isinstance(was, int | float):
        return not is_close(float(value), float(was))
    return value != was


def flow_of(settings: PrintSettings, speed: float, *, first_layer: bool = False) -> float:
    """Wie viel Material bei diesem Tempo je Sekunde durch die Düse muss, in
    mm³/s.

    Schichthöhe mal Bahnbreite mal Geschwindigkeit — die Rechnung, die die drei
    Einstellungen verbindet, an denen sonst einzeln gedreht wird. Sie ist der
    Grund, warum eine Schichthöhe, die gestern ging, heute mit einer schnelleren
    Stufe Löcher in die Wand zieht.

    ``first_layer=True`` rechnet mit den Maßen der ersten Schicht. Sie ist
    höher und breiter als alle darüber — 0,25 auf 0,45 gegen 0,20 auf 0,42,
    ein Drittel mehr Material je Millimeter Bahn. Mit den Maßen der übrigen
    gerechnet fällt genau der Wert durch, der als erster reißt.
    """
    return settings_table.bead_area(settings, first_layer=first_layer) * speed


def _from_flow(settings: PrintSettings) -> list[SettingAdvice]:
    """Begrenzt jedes fördernde Tempo auf den hinterlegten Volumenstrom.

    Eine Temperatur-Volumenstrom-Kurve ist nicht hinterlegt. Höhere Temperatur
    behebt deshalb rechnerisch nichts und würde bei jeder Übernahme erneut
    vorgeschlagen. Die erste Schicht benutzt ihre eigenen Bahnmaße; ein
    Problem dort darf die Temperatur aller späteren Schichten nicht erhöhen.
    Fahrt und Brücken mit gesondertem Fluss bleiben außerhalb dieser Rechnung.
    """
    advice: list[SettingAdvice] = []
    limit = settings.filament.max_flow
    if limit <= 0.0 or any(
        settings_table.bead_area(settings, first_layer=first) <= 0.0 for first in (False, True)
    ):
        return advice

    breaking: list[tuple[str, float, bool]] = []
    for name, first in settings_table.FLOW_BOUND_SPEEDS:
        speed = float(getattr(settings.speed, name))
        if flow_of(settings, speed, first_layer=first) > limit:
            breaking.append((f"speed.{name}", speed, first))
    if not breaking:
        return advice

    for path, speed, first in breaking:
        allowed = settings_table.flow_speed_limit(settings, first_layer=first)
        if allowed <= 0.0:
            # Die Geschwindigkeitsfelder beginnen bei 1 mm/s. Eine leere
            # Liste wäre hier eine Entwarnung trotz überschrittener Grenze.
            raise ValidationError(
                field="filament.max_flow",
                detail=_(
                    "Mit dieser Schichthöhe und Bahnbreite überschreitet selbst "
                    "das kleinste einstellbare Tempo den Volumenstrom. Verringern "
                    "Sie die Schichthöhe oder Bahnbreite, oder prüfen Sie den "
                    "gemessenen Volumenstrom im Filamentprofil."
                ),
                values={"flow_limit": limit, "speed_field": path},
            )
        if allowed >= speed:
            continue
        advice.append(
            SettingAdvice(
                path=path, value=allowed, was=speed, reason=FLOW_LIMIT_REASON, severity="warning"
            )
        )
    return advice


#: Der Grund jedes Tempodeckels aus :func:`_from_flow` — und woran er zu
#: erkennen ist (:func:`limits_flow`).
#:
#: **Ein Grund hat höchstens 60 Zeichen** (RM-514): Der Druckdialog zeigt ihn
#: unter der Tabelle, und bei 620 px Breite endete jeder längere auf „…“.
#: Ein Satz, ohne Pointe; wo zwei Regeln dasselbe sagen, teilen sie sich
#: eine Konstante (``tests/test_advise.py`` hält beides).
FLOW_LIMIT_REASON: Final = _("Mehr Tempo überschreitet den Volumenstrom des Filaments.")

#: Ein hohes, schmales Teil — für den Brim wie für die ruhigen Wände.
SLENDER_REASON: Final = _("Die Düse kann das hohe, schmale Teil umstoßen.")

#: Zu wenig Standfläche — im Rat für die Platte wie im Rat je Teil.
SMALL_FOOTPRINT_REASON: Final = _("Die Standfläche ist zu klein, um ohne Brim zu halten.")

#: Die Schichthöhe über der Düsengrenze, für jede Schicht wie für die erste.
LAYER_TOO_HIGH_REASON: Final = _("Schichten über drei Viertel der Düse haften schlecht.")

#: Das Bett am Höchstwert des Druckers, für jede Schicht wie für die erste.
BED_AT_MAXIMUM_REASON: Final = _("Wärmer wird das Bett dieses Druckers nicht.")


def limits_flow(entry: SettingAdvice) -> bool:
    """Ist dieser Vorschlag ein Tempodeckel nach dem Volumenstrom?

    Die Orca-Familie und PrusaSlicer deckeln das Tempo selbst nach dem
    Volumenstrom des Filaments, den Solidon ihnen schreibt
    (``slicer_keys.caps_volumetric_speed``). Dort ändert der Vorschlag nichts
    am Druck; an der Kobra 2 hob er über die Innenwand sogar die Lückenfüllung
    des Herstellers an (Gesamtprüfung, 27.09.2026). Der Druckdialog lässt ihn
    dort weg. Erkannt wird er am Grund, nicht am Feld: Ein Tempo kann auch
    aus anderem Anlass einen Vorschlag bekommen.
    """
    return entry.reason == FLOW_LIMIT_REASON


def _from_machine(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was die Maschine nicht kann, muss vor dem Druck gesagt werden."""
    advice: list[SettingAdvice] = []
    printer = profile.printer

    # **Und was sie kann, auch** — die Leerfahrt. Ein Projekt trägt seine
    # Einstellungen selbst, und eines von vor ``PrinterProfile.travel_speed``
    # fährt mit der allgemeinen Vorgabe: die Waschschüssel mit 150 statt 500
    # mm/s, und in dieser Zeit läuft die Düse zwischen den Inseln aus.
    # Schneller als der Drucker wird nichts vorgeschlagen; wer dort bewusst
    # langsamer fährt, behält es, wenn er den Vorschlag abwählt.
    if printer.travel_speed is not None and settings.speed.travel < printer.travel_speed:
        advice.append(
            _advice(
                settings,
                path="speed.travel",
                value=printer.travel_speed,
                reason=_("Der Drucker fährt leer schneller; das gibt weniger Fäden."),
            )
        )

    # **Und ab welchem Winkel er stützt.** Der Slicer bekommt die Grenze, mit
    # der die Schichtanalyse rechnet (``Profile.overhang_limit_degrees``); ein
    # Projekt von vor dem 27.09.2026 trägt noch die Startregel von 45 Grad und
    # schickte sie über den Wert des Herstellers — am Centauri 60 Grad. Dann
    # stützt der Slicer, was die Analyse als druckbar gemeldet hat.
    limit = profile.overhang_limit_degrees
    if not is_close(settings.support.threshold_angle, limit):
        advice.append(
            _advice(
                settings,
                path="support.threshold_angle",
                value=limit,
                reason=_("Bis zu diesem Winkel druckt der Drucker ohne Stütze.")
                if settings.support.threshold_angle < limit
                else _("Ab diesem Winkel sacken Überhänge ohne Stütze ab."),
            )
        )

    wanted = settings_table.MAX_LAYER_RATIO * printer.nozzle_diameter
    if settings.layers.layer_height > wanted:
        advice.append(
            _advice(
                settings,
                path="layers.layer_height",
                value=round(wanted, 3),
                reason=LAYER_TOO_HIGH_REASON,
                severity="warning",
            )
        )

    # **Dieselbe Grenze gilt der ersten Schicht**, und sie stand hier nicht.
    # ``resolve()`` deckelt beide beim Auflösen mit demselben Verhältnis; wer
    # die erste danach von Hand höher stellt, bekam bis zum 03.09.2026 kein
    # Wort — obwohl der Slicer sie genauso ablehnt. Eine Regel, die den einen
    # Wert prüft und den Nachbarn nicht, ist keine halbe Regel: Sie sieht aus
    # wie eine ganze.
    if settings.layers.first_layer_height > wanted:
        advice.append(
            _advice(
                settings,
                path="layers.first_layer_height",
                value=round(wanted, 3),
                reason=LAYER_TOO_HIGH_REASON,
                severity="warning",
            )
        )

    # **Und dieselbe Lücke bei den Temperaturen.** Systematisch gemessen am
    # 03.09.2026: Von fünf Temperaturfeldern prüfte `_from_machine` genau
    # eines gegen die Maschine. Der Kunde konnte 400 Grad erste Schicht und
    # 150 Grad Bett einstellen — das Feld erlaubt es, der Drucker kann 260
    # und 100, und niemand sagte ein Wort.
    #
    # Das Muster dahinter ist das eigentliche Ergebnis: Geprüft wurde immer
    # der Hauptwert, nie sein ``_first_layer``-Nachbar. Bei der Schichthöhe
    # ebenso. Wer eine Regel für einen Wert schreibt, schreibt sie für seine
    # Geschwister mit — sonst sieht die halbe Regel aus wie eine ganze.
    for path, current, ceiling, why in (
        (
            "temperature.nozzle_first_layer",
            settings.temperature.nozzle_first_layer,
            printer.nozzle_temperature_max,
            _("Heißer heizt die Düse dieses Druckers nicht."),
        ),
        (
            "temperature.bed",
            settings.temperature.bed,
            printer.bed_temperature_max,
            BED_AT_MAXIMUM_REASON,
        ),
        (
            "temperature.bed_first_layer",
            settings.temperature.bed_first_layer,
            printer.bed_temperature_max,
            BED_AT_MAXIMUM_REASON,
        ),
    ):
        if current > ceiling:
            advice.append(
                SettingAdvice(path=path, value=ceiling, was=current, reason=why, severity="warning")
            )

    # **Und die Bahnbreite nach unten.** :data:`NARROW_LINE_SHARE` sagt, dass
    # eine Bahn schmaler als 85 % der Düse abreißt, statt dünner zu werden. Die
    # Regel in ``_from_geometry`` senkt bis zu dieser Grenze — nach unten
    # eingestellt hat sie nie jemand geprüft. Bei einer 0,4er Düse liegt damit
    # der Bereich von 0,10 bis 0,34 mm im Feld und ist ungedruckbar; das Feld
    # hat feste Grenzen, die Düse nicht.
    narrowest = NARROW_LINE_SHARE * printer.nozzle_diameter
    for path in ("layers.line_width", "layers.first_layer_line_width"):
        if 0.0 < settings_table.read_path(settings, path) < narrowest:
            advice.append(
                _advice(
                    settings,
                    path=path,
                    value=round(narrowest, 3),
                    reason=_("Schmaler legt diese Düse keine Bahn, sie reißt ab."),
                    severity="warning",
                )
            )

    if settings.temperature.nozzle >= printer.nozzle_temperature_max:
        advice.append(
            _advice(
                settings,
                path="temperature.nozzle",
                value=printer.nozzle_temperature_max,
                reason=_("Das Material verlangt die Höchsttemperatur dieses Druckers."),
                severity="warning",
            )
        )

    if settings.temperature.chamber > 0 and not printer.enclosed:
        advice.append(
            _advice(
                settings,
                path="temperature.chamber",
                value=0,
                reason=_("Dieser Drucker hat keinen geschlossenen Bauraum."),
            )
        )
    return advice


#: Haftungsarten, die ein Teil auf wenig Fläche nicht sicher halten: Der Skirt
#: berührt es nicht, „keine“ auch nicht, und „automatisch“ heißt bei
#: PrusaSlicer und Cura die Art aus Solidons Tabelle, die das Teil nicht kennt.
#: Wo der Slicer seinen Brim selbst aus dem Teil rechnet, gilt „automatisch“
#: als gehalten (:func:`_unanchored`). „Keine“ ist die Grundlage an Prusas
#: eigenen Druckern (``skirts = 0``, ``brim_width = 0``, der Startcode zieht
#: eine Spüllinie); ohne sie bekam dort kein Turm einen Brim, auch nicht je
#: Teil (Durchsicht 0.5.1, B3).
UNANCHORED: Final = frozenset({"skirt", "auto", "none"})

#: Die Slicerfamilien, deren „automatisch“ den Brim aus dem Teil rechnet: Orcas
#: ``auto_brim`` aus Höhe, Flächenmomenten der Grundfläche und Tempo, bis 18 mm
#: breit (OrcaSlicer ``Brim.cpp``, ``configBrimWidthByVolumeGroups``).
#: PrusaSlicer und CuraEngine kennen keinen; dort heißt „automatisch“ die Art
#: aus Solidons Tabelle (``handover.effective_adhesion`` fragt dieselbe Menge).
AUTO_BRIM_FLAVOURS: Final[frozenset[SlicerFlavour]] = frozenset({"orca"})


def _unanchored(settings: PrintSettings, flavour: SlicerFlavour | None) -> bool:
    """Hält die Haftungsart ein Teil auf wenig Fläche nicht sicher?

    **Über Orcas Auto-Brim nicht** (:data:`AUTO_BRIM_FLAVOURS`): Er
    rechnet aus Höhe und Grundfläche selbst, und Solidons Brim ersetzte ihn
    durch die feste Breite des Profils — mit weniger Halt: den 200 mm hohen
    Schäften der Minigolf-Platte im ElegooSlicer 0,9 statt 1,9 m Randbahn, der
    Waschschüssel auf zwölf Füßen 0,40 statt 0,93 m. Die Kernabfrage ohne
    Familie bleibt vorsichtig. Der Druckdialog ohne ausgewähltes Programm
    verwendet dagegen wie sein 3MF-Export die Orca-Familie.
    """
    kind = settings.adhesion.kind
    if kind == "auto" and flavour in AUTO_BRIM_FLAVOURS:
        return False
    return kind in UNANCHORED


def _from_material(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was am Filament hängt und die Stufe nicht wissen kann."""
    advice: list[SettingAdvice] = []
    material = profile.material.id

    if material in WARPING_MATERIALS and not profile.printer.enclosed:
        if settings.adhesion.kind != "brim":
            advice.append(
                _advice(
                    settings,
                    path="adhesion.kind",
                    value="brim",
                    reason=_("Im offenen Bauraum hebt dieses Material die Ecken an."),
                    severity="warning",
                )
            )
        if settings.cooling.fan_speed > 0.3:
            advice.append(
                _advice(
                    settings,
                    path="cooling.fan_speed",
                    value=0.2,
                    reason=_("Zugluft trennt bei diesem Material die Schichten."),
                    severity="warning",
                )
            )

    if (
        material in WARPING_MATERIALS
        and profile.printer.enclosed
        and settings.temperature.chamber <= 0
    ):
        # Ein geschlossener Bauraum ist nur so viel wert, wie er geheizt wird.
        # Das Materialprofil setzt die Kammer; steht sie trotzdem auf null, hat
        # jemand sie ausgeschaltet — auf einem Gerät, das den Grund dafür hat.
        advice.append(
            _advice(
                settings,
                path="temperature.chamber",
                value=CHAMBER_FOR_WARPING,
                reason=_("Dieses Material druckt im geheizten Bauraum sicherer."),
            )
        )

    if material in FLEXIBLE_MATERIALS:
        for path, current in (
            ("speed.outer_wall", settings.speed.outer_wall),
            ("speed.inner_wall", settings.speed.inner_wall),
            ("speed.infill", settings.speed.infill),
            ("speed.top_surface", settings.speed.top_surface),
            ("speed.first_layer", settings.speed.first_layer),
            ("speed.bridge", settings.speed.bridge),
        ):
            if current > FLEXIBLE_MAX_SPEED:
                advice.append(
                    SettingAdvice(
                        path=path,
                        value=FLEXIBLE_MAX_SPEED,
                        was=current,
                        reason=_("Weiches Filament staucht sich bei mehr Tempo im Antrieb."),
                    )
                )
    return advice


@dataclass(frozen=True, slots=True)
class SupportNeed:
    """Ob ein Schnitt Stützen braucht, und woran es hängt (:func:`support_need`)."""

    needed: bool
    islands: tuple[float, ...]
    """Höhen, auf denen eine Kontur in der Luft beginnt."""
    model: ModelSupport
    overhang: float
    """Überhang in mm² ohne Kanaldecken und Ränder."""
    patch: float
    """Das größte Feld in mm²: das größte Stück oder eine schräge Decke als Feld,
    ohne Kanaldecken und Ränder."""
    piece: float = 0.0
    """Das größte einzelne Stück in mm², ohne Kanaldecken und Ränder — über
    ``OVERHANG_LAYER_WORTH_SUPPORT`` eine flache Decke."""
    quiet_layers: frozenset[int] = frozenset()
    """Schichten, deren Brücken nicht zählen: Ihr Überhang besteht ganz aus
    Kanal- und Randstücken (:func:`_quiet_layers`)."""
    tips: int = 0
    """Inseln, deren Baumspitze keine Trennschicht bekommt (:func:`tip_islands`)."""
    ledges: frozenset[tuple[int, int]] = frozenset()
    """Stücke (Schicht, Stück), die sich als Rand selbst tragen (:func:`ledges`)."""


def _largest_field(
    result: SliceResult,
    total: float,
    largest: float,
    *,
    without: frozenset[tuple[int, int]] = frozenset(),
) -> float:
    """Das größte Feld: das größte Stück, oder eine Decke in der Aufsicht
    (:func:`largest_sloped_patch`, RM-570), wenn das Stück allein die Grenze
    verfehlt und ein Feld sie tragen könnte. Nur dann gefragt — die Decken
    des ganzen Körpers kosten am Drachen 8 s CPU. Ein Feld ist nie größer
    als die Summe; bis :data:`OVERHANG_LAYER_WORTH_SUPPORT` trägt es deshalb
    keinen der beiden Wege (Review 3: an der Summe von 150 gemessen, blieb ein
    Feld von 134 mm² „keine Stützen“)."""
    if worth_support(largest, total) or total <= OVERHANG_LAYER_WORTH_SUPPORT:
        return largest
    return max(largest, largest_sloped_patch(result, without=without))


def support_need(result: SliceResult, *, cancelled: CancelToken | None = None) -> SupportNeed:
    """Braucht dieser Schnitt Stützen? Die eine Antwort für den Vorschlag
    „Stützen nötig“ (:func:`_from_geometry`) und für *Druckoptimal ausrichten*
    (``orientation.search``) — zwei Regeln für dieselbe Frage liefen sonst
    auseinander. Abbrechbar in der Randfrage, dem teuersten Schritt.
    """
    islands = island_layers(result)
    total = total_overhang(result)
    largest = _largest_field(result, total, largest_overhang_patch(result))
    # Kanaldecken zählen nicht: Sie tragen sich selbst, und eine Stütze darin
    # käme nicht mehr heraus (:func:`model_support`, die Waschschüssel vom
    # 25.09.2026). Ohne diese Ausnahme schaltete ein Wasserkanal die Stützen
    # ein und verlangte zugleich, dass sie auf dem Modell ansetzen — genau dort,
    # wo sie ihn füllen.
    #
    # **Gefragt wird die Kanalfrage nur, wenn es ohne sie Stützen bräuchte.**
    # Sie nimmt Stücke heraus, nie hinzu; ein Körper, der schon mit allen
    # Stücken ohne Stütze auskommt, braucht sie nicht. Am Bohrmaschinenhalter
    # aus dem Korpus kostete sie 0,8 s von 2,5 s Vorschlagsrechnung, ohne dass
    # eine Antwort davon abhing (Weg a der Durchsicht 0.5.1).
    asked = _may_need_support(result, islands, total, largest)
    # **Und kein Rand** (Eiffelturm, 08.10.2026, :func:`ledges`): Was nicht
    # weiter als ``LEDGE_REACH`` über sein Material ragt, trägt sich selbst. Die
    # Ränder der Plattformen verlangten sonst Stützen, und der ElegooSlicer
    # stellte 831 m Baum außen am Turm hoch. Gefragt vor der Kanalfrage, die
    # dieselbe Antwort ohne Abbruch aus dem Merker liest.
    edges = ledges(result, cancelled=cancelled) if asked else frozenset()
    model = model_support(result) if asked else ModelSupport()
    quiet = model.channels | edges
    overhang = total_overhang(result, without=quiet)
    piece = largest_overhang_patch(result, without=quiet)
    patch = _largest_field(result, overhang, piece, without=quiet)
    # Die Summe allein reicht nicht, und der Unterschied entscheidet: ein
    # Becher sammelte über dreihundertachtunddreißig Schichten
    # zweihundertvierzig Quadratmillimeter und bekam dieselbe Warnung wie ein
    # Deckel, dessen Lochplatte mit achthundertfünfundvierzig auf einmal
    # anfängt. Beim Becher trägt jede Wand ihren Anteil selbst; beim Deckel
    # hängt eine ganze Fläche über einem Hohlraum.
    #
    # **Beides mit „und" zu verbinden war trotzdem falsch.** Die Fläche einer
    # Schicht kann nie größer sein als die Summe über alle; die Bedingung
    # bedeutete damit „mehr als hundert auf einer Schicht", mit einem toten
    # Streifen zwischen hundert und hundertfünfzig. Eine Decke von 138 mm²,
    # die vollständig in der Luft hängt, fiel genau dort hinein und bekam
    # nichts. Die zwei Zahlen sind zwei **Wege**, und jeder trägt für sich:
    # viel auf einmal, oder viel insgesamt bei einem Anteil je Schicht, den
    # keine Wand mehr nebenbei auffängt.
    #
    # **Und „auf einmal" heißt an einem Stück, nicht auf einer Schicht.** Ein
    # Gitterbecher (20.09.2026) trug auf seiner schlimmsten Schicht 278 mm² —
    # in 56 Stegunterseiten zu je 5 mm², jede über 4,7 mm frei und jede trägt
    # sich selbst; gedruckt ohne eine einzige Stütze. Die Schichtsumme sah
    # darin dieselbe Decke wie beim Deckel. Gefragt wird deshalb das größte
    # zusammenhängende Stück (:func:`largest_overhang_patch`); lange freie
    # Stege fängt die Brückenregel darunter weiter ab.
    resting = _quiet_layers(result, quiet)
    return SupportNeed(
        needed=_may_need_support(result, islands, overhang, patch, resting),
        islands=islands,
        model=model,
        overhang=overhang,
        patch=patch,
        piece=piece,
        quiet_layers=resting,
        tips=tip_islands(result),
        ledges=edges,
    )


#: Wie weit der Stützabstand vom Wert aus Material und Schichthöhe abweichen
#: darf, bevor Solidon ihn vorschlägt, als Anteil (RM-583) — das Band der
#: Recherche vom 08.10.2026: Prusa nimmt 0,17 bei 0,15er Schichten und 0,22 bei
#: 0,2ern, beides hält ab, was es soll.
SUPPORT_GAP_BAND: Final = (0.8, 1.25)

#: Die Trennschicht unter großen flachen Decken: Lücke in mm und Lagen. Lockerer
#: hängen die ersten Bahnen darüber durch (Recherche Nr. 3: 0,1 bis 0,2 mm,
#: drei Lagen).
DENSE_INTERFACE: Final = (0.2, 3)

#: Unter kleinen und gewölbten Flächen — Schuppen, Kinn, Krallen: Dort sitzt
#: eine dichte Trennschicht fest und reißt Material mit (Recherche Nr. 3: 0,4 bis
#: 0,5 mm, zwei Lagen).
OPEN_INTERFACE: Final = (0.5, 2)

#: Untere Trennschichten, wo die Stütze auf dem Modell steht (Recherche Nr. 2).
#: Ohne sie steht der rohe Stützfuß auf der Fläche und zeichnet sie; das Profil
#: des MK4S führt 0.
BOTTOM_INTERFACE_LAYERS: Final = 2


#: Wo der Slicer den Stützabstand immer in ganzen Schichten rechnet (RM-583):
#: CuraEngine (``support_top_distance`` je Schicht). Die Orca-Familie nur,
#: solange die Stütze die Schichthöhe des Modells hat; die eigene Höhe schaltet
#: die Übergabe dann ein (``slicer_keys.has_independent_support_layers``) — außer
#: neben einem Reinigungsturm (``whole_layers``) und unter organischen Bäumen
#: (``organic``), das sagt der Aufrufer (RM-622).
WHOLE_LAYER_GAP_FLAVOURS: Final[frozenset[SlicerFlavour]] = frozenset({"cura"})


def rounds_to_whole_layers(
    flavour: SlicerFlavour | None,
    whole_layers: bool = False,
    style: str = "",
    organic: Collection[str] = (),
) -> bool:
    """Rechnet der Slicer den Stützabstand hier in ganzen Schichten (RM-622)? Cura
    immer; die Orca-Familie neben einem Reinigungsturm (``whole_layers``); jedes
    Programm unter organischen Bäumen, also wenn ``style`` zu den Arten gehört,
    die es so druckt (``organic``, :func:`handover.organic_styles`): Sie liegen
    auf den Schichten des Modells, auch mit eigener Stützschichthöhe."""
    return whole_layers or flavour in WHOLE_LAYER_GAP_FLAVOURS or style in organic


#: Vorschläge, an deren Übernahme andere hängen (:func:`printed_style`): Wählt
#: der Kunde einen davon ab, fragt der Druckdialog neu (RM-622).
DECIDING_PATHS: Final = frozenset({"support.style"})


def printed_style(
    settings: PrintSettings, advice: Sequence[SettingAdvice], declined: Collection[str] = ()
) -> str:
    """Die Stützart, mit der ein Teil druckt (RM-622): die vorgeschlagene, solange
    der Kunde sie nicht ablehnt (``declined``), sonst die eigene. Abstand und
    untere Trennschicht hängen an ihr — unter organischen Bäumen rundet der
    Slicer den Abstand, und manches Programm druckt dort keine untere
    Trennschicht. Rat, Druckdialog und Export fragen hier, damit ein
    abgelehnter Baum dem Gitter nicht Abstand und Trennschicht nimmt."""
    if "support.style" in declined:
        return settings.support.style
    return next(
        (str(entry.value) for entry in advice if entry.path == "support.style"),
        settings.support.style,
    )


def in_whole_layers(gap: float, layer: float) -> bool:
    """Misst dieser Abstand ganze Schichten? Sonst rundet ein Slicer, der in ganzen
    Schichten rechnet, ihn selbst (RM-583, RM-622)."""
    return layer > 0.0 and is_close(gap / layer, round(gap / layer))


def support_gap_target(
    layer: float,
    material: MaterialProfile,
    flavour: SlicerFlavour | None = None,
    *,
    whole_layers: bool = False,
    style: str = "",
    organic: Collection[str] = (),
) -> float | None:
    """Der Stützabstand, mit dem sich die Stütze von diesem Material sauber löst
    (RM-583): ein Vielfaches der Schichthöhe, begrenzt nach dem Materialprofil.
    Ohne Werte im Profil ``None``: unbekannt, der Abstand bleibt beim Hersteller.

    Wo der Slicer in ganzen Schichten rechnet (Cura), ist es das Vielfache
    innerhalb der Grenzen, das dem Ziel am nächsten liegt, mindestens eine
    Schicht. Liegt keines darin, das kleinste über dem Minimum — oberhalb des
    Maximums bleibt nur eine Schicht (PLA ab 0,28 mm). Die Orca-Familie rundet
    nur ohne eigene Stützschichthöhe; die schaltet die Übergabe ein
    (``handover.frees_support_layers``).

    **Neben einem Reinigungsturm rundet auch die Orca-Familie, unter
    organischen Bäumen jedes Programm, das sie so druckt — die Orca-Familie wie
    PrusaSlicer** (:func:`rounds_to_whole_layers`, RM-622): Die Stütze liegt
    dann auf den Schichten des Modells, und der Abstand rundet auf die nächste
    (am Turm ``SupportMaterial.cpp``, unter Bäumen der organische Generator,
    bei Orca ``TreeSupport3D.cpp``; gemessen in sechs Programmen). PLA
    bei 0,08er Schichten bekäme aus 0,10 mm eine Schicht, also 0,08 — unter dem
    Minimum; in ganzen Schichten gerechnet sind es 0,16."""
    factor, low, high = (
        material.support_gap_factor,
        material.support_gap_min,
        material.support_gap_max,
    )
    if factor is None or low is None or high is None or layer <= 0.0:
        return None
    target = min(max(layer * factor, low), high)
    if not rounds_to_whole_layers(flavour, whole_layers, style, organic):
        return target
    first = max(1, math.ceil(low / layer - EPS_GEOM))
    last = math.floor(high / layer + EPS_GEOM)
    if first > last:
        return first * layer
    # Eine halbe Schicht rundet auf, auch wenn die Division knapp darunter landet.
    return min(max(math.floor(target / layer + 0.5 + EPS_GEOM), first), last) * layer


#: Ab wie vielen Inseln mit Baumspitze ohne Trennschicht (:attr:`SupportNeed.tips`)
#: der Abstand über den Spitzen gilt (RM-584). Gesetzt an 165 Modellen aus Roberts
#: Sammlung und ``tests/data/meshes``: Der Drache hat 199, danach folgen eine
#: Baugruppe mit 49, ein Schachturm mit 34 und ein Küchenteil mit 21, alle übrigen
#: unter 15. Gemessen ist die Wirkung nur am Drachen; die Schwelle liegt mit Abstand
#: zu beiden Seiten, und Teile mit wenigen kleinen Inseln behalten die
#: Trennschicht ihrer großen Decken.
TIP_ISLANDS: Final = 100

#: Wie viele Schichten Luft mindestens über einer Baumspitze ohne Trennschicht
#: stehen (RM-584): Mit einer schweißt die Spitze an, gemessen am Drachen in
#: ElegooSlicer, PrusaSlicer und Cura.
TIP_GAP_LAYERS: Final = 2


def tip_gap(
    layer: float,
    material: MaterialProfile,
    need: SupportNeed,
    flavour: SlicerFlavour | None,
    style: str,
    organic: Collection[str] = (),
) -> float | None:
    """Der Abstand oben über Baumspitzen ohne Trennschicht (RM-584), oder ``None``.

    Unter Inseln unter 1 mm² baut der Slicer keine Trennschicht
    (:func:`analysis.tip_islands`); die Spitze steht eine Schicht unter dem
    Modell und schweißt an. Am Drachen (PLA, 0,2 mm) senkte 0,4 statt 0,2 die
    Kontaktfläche am Kinn von 59,4 auf 6,9 mm², an den Kopfstacheln von 92,4 auf
    3,6 mm² — für eine Minute und 0,7 g. Gilt, wo der Slicer Baumspitzen setzt:
    unter organischen Bäumen (``organic``) und unter Curas Bäumen. In ganzen
    Schichten, mindestens :data:`TIP_GAP_LAYERS`, aus ``support_tip_gap`` des
    Materials; ohne gemessenen Wert ``None``.
    """
    if material.support_tip_gap is None or layer <= 0.0 or need.tips < TIP_ISLANDS:
        return None
    if style not in organic and not (flavour == "cura" and style == "tree"):
        return None
    layers = math.floor(material.support_tip_gap / layer + 0.5 + EPS_GEOM)
    return max(TIP_GAP_LAYERS, layers) * layer


def _support_contact(
    settings: PrintSettings,
    profile: Profile,
    need: SupportNeed,
    on_model: bool,
    flavour: SlicerFlavour | None,
    whole_layers: bool = False,
    style: str = "",
    organic: Collection[str] = (),
) -> list[SettingAdvice]:
    """Abstand und Trennschicht der Stütze nach Material, Schichthöhe und
    Fläche (RM-583) — die häufigsten Ursachen für Narben und festsitzende Stützen
    (``konzepte/recherche-slicer-einstellungen-2026-10.md``, Nr. 1, 2, 3, 7).

    Der Abstand oben ist ein Vielfaches der Schichthöhe aus dem Materialprofil,
    begrenzt nach unten und oben (Regel 7); wo der Slicer in ganzen Schichten
    rechnet (:func:`rounds_to_whole_layers`, mit der Art ``style``, mit der das
    Teil druckt, :func:`printed_style`), das Vielfache. Dort passt auch ein
    Abstand im Band nicht, der keine ganze Schicht ist: Der Slicer rundet ihn
    selbst, Cura auf, die Orca-Familie zur
    nächsten (0,2 mm sind bei 0,08er Schichten zweieinhalb). Unter einer großen
    flachen Decke (ein Stück über ``OVERHANG_LAYER_WORTH_SUPPORT``) wird die
    Trennschicht dicht, sonst locker. Material, das an sich selbst haftet
    (``support_interface_cooling`` im Profil), bekommt volle Kühlung an der
    Trennschicht.
    """
    advice: list[SettingAdvice] = []
    material = profile.material
    layer = settings.layers.layer_height
    style = style or settings.support.style
    target = support_gap_target(
        layer, material, flavour, whole_layers=whole_layers, style=style, organic=organic
    )
    reason = _("Passend zu Schicht und Material löst sich die Stütze sauber.")
    tips = tip_gap(layer, material, need, flavour, style, organic)
    if tips is not None and (target is None or tips > target):
        target = tips
        reason = _("Feine Spitzen brauchen mehr Luft über den Baumstützen.")
    low, high = SUPPORT_GAP_BAND
    gap = settings.support.z_gap
    if target is not None and (
        not low * target <= gap <= high * target
        or (
            rounds_to_whole_layers(flavour, whole_layers, style, organic)
            and not in_whole_layers(gap, layer)
        )
    ):
        advice.append(
            _advice(settings, path="support.z_gap", value=round(target, 4), reason=reason)
        )
    if on_model and settings.support.bottom_interface_layers < BOTTOM_INTERFACE_LAYERS:
        advice.append(
            _advice(
                settings,
                path="support.bottom_interface_layers",
                value=BOTTOM_INTERFACE_LAYERS,
                reason=_("Eine Trennschicht unter dem Stützfuß schont das Teil."),
            )
        )
    flat = need.piece > OVERHANG_LAYER_WORTH_SUPPORT
    spacing, layers = DENSE_INTERFACE if flat else OPEN_INTERFACE
    middle = (DENSE_INTERFACE[0] + OPEN_INTERFACE[0]) / 2.0
    reason = (
        _("Eine dichte Trennschicht hält große flache Decken.")
        if flat
        else _("Lockere Trennschichten lösen sich von Details leichter.")
    )
    current = settings.support.interface_spacing
    if (current > middle) if flat else (current < middle):
        advice.append(
            _advice(settings, path="support.interface_spacing", value=spacing, reason=reason)
        )
    if (
        (settings.support.interface_layers < layers)
        if flat
        else (settings.support.interface_layers > layers)
    ):
        advice.append(
            _advice(settings, path="support.interface_layers", value=layers, reason=reason)
        )
    if material.support_interface_cooling and not settings.cooling.support_interface_cooling:
        advice.append(
            _advice(
                settings,
                path="cooling.support_interface_cooling",
                value=True,
                reason=_("Volle Kühlung löst die Stütze von diesem Material leichter."),
            )
        )
    return advice


def _from_geometry(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult,
    bounds: BoundingBox | None,
    flavour: SlicerFlavour | None = None,
    whole_layers: bool = False,
    organic: Collection[str] = (),
    declined: Collection[str] = (),
    trees: Collection[str] | None = None,
) -> list[SettingAdvice]:
    """Der eigentliche Gewinn: das Teil bestimmt seine Einstellungen mit."""
    advice: list[SettingAdvice] = []

    need = support_need(result)
    islands, model, overhang = need.islands, need.model, need.overhang
    needs_support = need.needed

    # **„Keine Insel“ heißt nicht „alles erreicht das Bett“.** Ein Tisch —
    # Bodenplatte 40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte
    # 40 auf 40 — hat keine Insel und 1 492 mm² Überhang auf einer Schicht,
    # und jede Stütze darunter endet auf der Bodenplatte. Der Vorschlag
    # ``build_plate`` ließ die Tischplatte absacken. Gefragt wird deshalb die
    # Geometrie und nicht ein Nebenbefund (:func:`model_support`).
    #
    # **Und „auf dem Modell“ heißt außen und so viel, dass es selbst Stütze
    # bräuchte.** Eine Säule im Kanal zählt nicht (``support_need``), und was außen auf
    # dem Modell aufsetzt, misst sich an denselben zwei Wegen wie der
    # Stützbedarf selbst, auch als Feld (``ModelSupport.open_field``, RM-570:
    # das Kinn über der Brust): An der Waschschüssel blieb neben der Kanaldecke ein
    # Rest von 11 mm² an der Düsenmündung, und der allein verlangte, dass die
    # Stützen des ganzen Teils überall ansetzen — wieder im Kanal.
    #
    # **Eine Insel auf dem Modell verlangt es immer**, gleich wie klein: Sie
    # hat nichts unter sich. Eine Insel über dem Bett dagegen erreicht es —
    # deshalb steht hier nicht mehr pauschal „keine Inseln": Bis zum
    # 26.09.2026 bekam jedes Teil mit einer Insel „überall", auch wenn alle
    # Säulen das Bett erreichten oder im Kanal endeten, und der Kanal füllte
    # sich wieder.
    #
    # **Und eine lange Brücke über dem Modell verlangt es auch.** Sie ist
    # selbst ein Grund für Stützen (:func:`_may_need_support`), bleibt aber oft
    # unter den Flächengrenzen: Am Wedge-Lock (04.10.2026) hing eine Decke von
    # 25,7 mm auf 65 mm² über dem Modell, der Rat verlangte Stützen und schlug
    # zugleich „nur vom Bett“ vor. Creality Print, Kobra 2, PrusaSlicer und
    # Cura stützten dann gar nichts, Elegoos Bäume die Hälfte. **Die Brücke
    # selbst muss dort hängen**, nicht nur ihre Schicht: An der Waschschüssel
    # war es das Gewölbe des Kanals neben einem kleinen offenen Stück, und
    # Cura stellte mit „überall“ eine Säule in den Kanal (:func:`open_bridge_width`).
    long_bridge_on_model = (
        needs_support
        and open_bridge_width(result, model, profile.minimum_wall_thickness, above=SPAN_INTERESTING)
        > SPAN_INTERESTING
    )
    on_model = needs_support and (
        model.island_on_model
        or worth_support(max(model.open_patch, model.open_field), model.open_area)
        or long_bridge_on_model
    )
    # **Wo Stützen auf dem Modell ansetzen, Bäume** (Drache, 08.10.2026): Ein
    # Gitter setzt mit jeder Säule auf, und jede hinterlässt eine Narbe; ein Baum
    # setzt mit wenigen Füßen auf. Am Drachen setzten die Gitter der Hersteller
    # 212 bis 324 mm² auf dem Modell auf, Solidons Bäume 4 bis 66 mm²
    # (``gcode_auflage.py``). Elegoo und Bambu stützen ohnehin mit Bäumen; „auto“
    # heißt dort Baum, bei Orca, Prusa, Creality und Cura Gitter. **Nicht unter
    # einer großen flachen Decke**: Dort hängt die Unterseite zwischen den
    # Baumspitzen durch, und Orca wie Prusa raten zu Hybrid oder normaler Stütze
    # (Recherche vom 08.10.2026). Flach heißt ein Stück über
    # ``OVERHANG_LAYER_WORTH_SUPPORT`` auf einer Schicht; Schuppen, Kinn und
    # Flügel einer Figur zerfallen in kleine Stücke.
    branching = on_model and need.piece <= OVERHANG_LAYER_WORTH_SUPPORT
    # **Unter einer großen flachen Decke keine Bäume** (RM-584, Recherche Nr. 4):
    # Zwischen den Baumspitzen hängt die Unterseite durch. Dort trägt Gitter;
    # setzen daneben kleine Stücke auf dem Modell auf
    # (``ModelSupport.details_on_model``) oder beginnen viele Inseln in der
    # Luft, Hybrid — Bäume für die Details, normale Stütze unter der Decke.
    # Welche Arten das Programm als Bäume druckt, sagt ``trees``
    # (``handover.tree_styles``): „Automatisch“ ist bei Elegoo und Bambu ein
    # Baum, bei PrusaSlicer mit ``snug`` und bei Cura nicht — dort bleibt es;
    # Hybrid kennen PrusaSlicer und Cura nicht, dort trägt Gitter allein. Ohne
    # Programm bleibt der Rat vorsichtig und zählt „automatisch“ als Baum.
    flat = need.piece > OVERHANG_LAYER_WORTH_SUPPORT
    many_islands = len(islands) >= TREE_FROM_ISLANDS
    printed_trees = frozenset({"tree", "hybrid"}) if trees is None else frozenset(trees)
    auto_trees = trees is None or "auto" in trees
    under_ceiling = (
        "hybrid"
        if "hybrid" in printed_trees and (model.details_on_model or many_islands)
        else "grid"
    )
    # **Wo die Art der ganzen Platte gilt** (Cura: ``support_structure``, Stützen
    # je Netz nur an oder aus), sagt die flache Decke ausdrücklich Gitter
    # (Nachprüfung RM-584, N1): Ihr „automatisch“ hieße dort zwar ``normal``,
    # aber neben einem Körper, der Bäume verlangt, gewann der Baum, und der Hut
    # des Pilzes hing zwischen Baumspitzen durch.
    plate_kind = flavour == "cura"
    if flat:
        wanted = under_ceiling if auto_trees or plate_kind else "auto"
    else:
        wanted = "tree" if many_islands or branching else "auto"
    # Was gerade Bäume druckt und unter der Decke durchhinge — ein gewählter
    # Hybrid nicht: Er legt dort schon Gitter.
    over_trees = (settings.support.style == "tree" and "tree" in printed_trees) or (
        settings.support.style == "auto" and auto_trees
    )
    if needs_support and settings.support.style == "none":
        # **Stützen an, die Art des Slicers** — außer das Modell verlangt eine
        # (Entscheidung J, 27.09.2026). Hier stand ``grid``, und Elegoo wie
        # Bambu, deren Standardprozess Bäume stützt, bekamen Gitter.
        style = wanted
        advice.append(
            _advice(
                settings,
                path="support.style",
                value=style,
                reason=_("Ohne Stützen druckt dieses Teil in die Luft.")
                if islands
                else _("Die Überhänge sind zu groß, um sich selbst zu tragen."),
                severity="warning",
            )
        )
    elif (
        needs_support
        and branching
        and (
            settings.support.style in ("auto", "grid")
            # Ein Hybrid, den das Programm als Gitter druckt (N7).
            or (settings.support.style == "hybrid" and "hybrid" not in printed_trees)
        )
    ):
        advice.append(
            _advice(
                settings,
                path="support.style",
                value="tree",
                reason=_("Bäume hinterlassen auf dem Modell weniger Spuren."),
            )
        )
    elif needs_support and flat and over_trees:
        # Über einem gewählten Gitter nicht: Es trägt die flache Decke.
        advice.append(
            _advice(
                settings,
                path="support.style",
                value=under_ceiling,
                reason=_("Große flache Decken hängen zwischen Baumspitzen durch.")
                if under_ceiling == "grid"
                else _("Bäume für Details, Gitter unter der großen flachen Decke."),
            )
        )
    elif (
        needs_support
        and flat
        and plate_kind
        and settings.support.style == "auto"
        and under_ceiling == "grid"
    ):
        advice.append(
            _advice(
                settings,
                path="support.style",
                value="grid",
                reason=_("Gitter hält die flache Decke, auch neben Baumstützen."),
            )
        )
    elif not needs_support and settings.support.style != "none":
        advice.append(
            _advice(
                settings,
                path="support.style",
                value="none",
                reason=_("Nichts an diesem Teil braucht eine Stütze."),
            )
        )

    if needs_support and on_model and settings.support.placement == "build_plate":
        advice.append(
            _advice(
                settings,
                path="support.placement",
                value="everywhere",
                reason=_("Stützen erreichen diese Überhänge nur vom Modell aus."),
                severity="warning",
            )
        )
    elif needs_support and settings.support.placement == "everywhere" and not on_model:
        advice.append(
            _advice(
                settings,
                path="support.placement",
                value="build_plate",
                reason=_("Stützen in den schmalen Kanälen ließen sich kaum entfernen.")
                if model.channels
                else _("Die Überhänge über dem Modell tragen sich selbst.")
                if model.ledges_on_model
                else _("Stützen erreichen alle Überhänge vom Druckbett aus."),
            )
        )

    # **Und die Kanäle frei halten** (26.09.2026). „Nur vom Bett" reicht dafür
    # nicht in jedem Slicer: Orcas organische Bäume wuchsen trotzdem in den
    # Wasserkanal der Waschschüssel und führten ihre Stämme durch die Wand, und
    # wo „überall" nötig bleibt — eine Insel auf dem Modell —, füllt jeder
    # Slicer den Kanal. Die Sperre in der Übergabe hält beides heraus — **wenn
    # sie Raum sperrt** (:func:`channel_space`): Am Drachen (08.10.2026) blieben
    # Kerben unter einem Millimeter Tiefe Kanaldecken, und der Vorschlag hätte
    # eine Sperre angeboten, die nichts enthält.
    if (
        needs_support
        and model.channels
        and not settings.support.block_channels
        and channel_space(result, model, settings.layers.line_width)
    ):
        advice.append(
            _advice(
                settings,
                path="support.block_channels",
                value=True,
                reason=_("Die Sperre hält Stützen aus den schmalen Kanälen."),
            )
        )
    # **Und von Rändern fern, die sich selbst tragen** (Eiffelturm, 08.10.2026):
    # Der Slicer stützt nach seinem Winkel jede flache Unterseite, auch die
    # Ränder der Plattformen, und stellte dafür 831 m Baum außen am Turm hoch.
    # Vorgeschlagen nur, wo Stützen an sind und die Sperre Fläche hat.
    if (
        needs_support
        and not settings.support.spare_ledges
        and ledge_space(result, settings.layers.line_width)
    ):
        advice.append(
            _advice(
                settings,
                path="support.spare_ledges",
                value=True,
                reason=_("Diese Ränder tragen sich selbst, Stütze ließe Narben."),
            )
        )
    if needs_support:
        # Gefragt mit der Stützart, mit der das Teil druckt: Schlägt der Rat
        # Bäume vor und übernimmt der Kunde sie, liegt die Stütze auf den
        # Schichten des Modells (RM-622).
        printed = printed_style(settings, advice, declined)
        advice += _support_contact(
            settings,
            profile,
            need,
            on_model,
            flavour,
            whole_layers,
            printed,
            organic,
        )
        # Hohe Bäume brechen mit einer Wand (RM-584); gefragt mit derselben
        # Stützart wie der Kontakt, und nur, wo das Programm sie als Baum druckt
        # (``trees``): Hybrid ist bei PrusaSlicer und Cura Gitter, „automatisch“
        # bei Elegoo ein Baum.
        if (
            printed in printed_trees
            and settings.support.tree_walls < TALL_TREE_WALLS
            and need.model.tallest_column >= TALL_TREE_HEIGHT
        ):
            advice.append(
                _advice(
                    settings,
                    path="support.tree_walls",
                    value=TALL_TREE_WALLS,
                    reason=_("Zwei Wände halten hohe Bäume stabil."),
                )
            )
    # **Und was frei druckt, soll halten** (RM-587): Brücken unter Stütze, wo die
    # Stütze sie verlangt, dicke Bahnen über langen freien Brücken, Zusatzwände
    # unter flachen Überhängen ohne Stütze und die Umkehr an steilen Wänden.
    advice += _bridges_and_overhangs(settings, profile, result, need, advice, declined, flavour)

    # **Über „automatisch“ nur, wo der Slicer nichts rechnet** (Entscheidung J,
    # :func:`_unanchored`): Orcas Auto-Brim fragt Höhe und Grundfläche selbst
    # und hält mehr als Solidons Brim fester Breite.
    unanchored = _unanchored(settings, flavour)
    # Zuerst ohne Skirt, wo er keinen Platz hat; ein schmaler Brim danach
    # überstimmt das (:func:`_merged`, die spätere Regel gewinnt).
    advice += _skirt_where_it_fits(settings, profile, result, flavour)
    if 0.0 < result.first_layer_area < SMALL_FOOTPRINT and unanchored:
        advice += _brim_where_it_fits(
            settings,
            profile,
            result,
            SMALL_FOOTPRINT_REASON,
            flavour=flavour,
        )

    # **Und auf vielen kleinen Füßen.** Die Frage oben liest die Summe: Die
    # Waschschüssel steht auf zwölf Füßen zu je 108 mm², zusammen 1417 mm²,
    # und bekam keinen Brim — Nutzer des Designerprofils melden, dass sich die
    # hintere Ecke hebt. Jeder Fuß trägt seinen Teil des Hebels allein, und
    # keiner hat die Fläche, die ein Teil für sich braucht. Im Korpus
    # (447 Körper, 26.09.2026) trifft das außer der Schüssel sechs: den
    # Eiffelturm auf vier Beinen, eine Katze auf drei Pfoten, einen Schaber
    # auf zwei Auflagen.
    if unanchored and result.first_layer_area >= SMALL_FOOTPRINT and _on_small_feet(result):
        advice += _brim_where_it_fits(
            settings,
            profile,
            result,
            _("Ein Brim gibt jedem der kleinen Füße Halt."),
            flavour=flavour,
        )

    if bounds is not None and _slender(bounds) and unanchored:
        advice += _brim_where_it_fits(
            settings,
            profile,
            result,
            SLENDER_REASON,
            flavour=flavour,
        )

    # **Ein Brim hält den Fuß, nicht die Stange darüber.** Roberts Fahnenstangen
    # am Centauri Carbon 2 (29.09.2026): Ø 7,7 mm, 122 mm hoch, auf je 46,5 mm²,
    # Elegoos Auto-Brim lag fest, und die Stangen rissen samt erster Schicht
    # aus ihm heraus — ab 25 mm liefen nur noch sie, mit Wänden bis 200 mm/s
    # und 5000 bis 10 000 mm/s². Gebremst wird deshalb, wo ein schlanker Körper
    # zugleich auf zu wenig Fläche steht, auch unter einem Auto-Brim; die
    # Schäfte derselben Platte (Ø 25,7 mm, 200 mm hoch, 518 mm²) liefen mit vollem
    # Tempo sauber und bleiben schnell.
    if bounds is not None and _slender(bounds) and 0.0 < result.first_layer_area < SMALL_FOOTPRINT:
        advice += _calm_walls(settings)
        if settings.adhesion.kind != "raft" and settings.adhesion.brim_gap > EPS_GEOM:
            advice.append(
                _advice(
                    settings,
                    path="adhesion.brim_gap",
                    value=0.0,
                    reason=_("Ohne Abstand hält der Brim den schmalen Fuß fester."),
                    severity="warning",
                )
            )

    # **Schmale Stege brauchen eine langsame erste Schicht.** Roberts
    # Minigolf-Platte am Centauri Carbon 2 (27.09.2026): Elegoos Standard legt
    # die Füllung der ersten Schicht mit 105 mm/s, und an den Stegen zwischen
    # den Löchern rissen die kurzen Bodenbahnen. Mit der ganzen ersten Schicht
    # auf 50 mm/s lief derselbe Druck sauber. Vorgeschlagen wird deshalb dieses
    # Tempo, wo ein nennenswerter Teil der ersten Schicht in schmalen Stegen
    # liegt; über dem Herstellerprofil macht der Vorschlag die Wände der ersten
    # Schicht dabei nie schneller (``handover._followers_not_faster``).
    #
    # **Nennenswert als Anteil oder als Fläche.** Gerissen ist es am Rumpf
    # ``Gövde59``, 8,6 % seiner ersten Schicht in Stegen — ein großes Teil mit
    # wenigen, aber langen Stegen. Gegen den Anteil allein blieb die Regel dort
    # stumm (:data:`NARROW_WEB_AREA`).
    web_share = (
        narrow_share(result.layers[0], NARROW_WEB_LINES * settings.layers.first_layer_line_width)
        if result.layers and settings.speed.first_layer > NARROW_WEB_SPEED + EPS_GEOM
        else 0.0
    )
    if result.layers and (
        web_share >= NARROW_WEB_SHARE or web_share * result.layers[0].area >= NARROW_WEB_AREA
    ):
        advice.append(
            _advice(
                settings,
                path="speed.first_layer",
                value=NARROW_WEB_SPEED,
                reason=_("Langsamer haften die kurzen Bahnen auf schmalen Stegen."),
                severity="warning",
            )
        )

    # **Gemessen, nicht gedeckelt.** ``narrowest`` meldet
    # ``WIDTH_INTERESTING``, wo der Körper nirgends dünner ist — „mindestens
    # zwei Millimeter", eine untere Schranke und keine Messung. An einer
    # 0,8er-Düse sind drei Linienbreiten 2,55 mm, der Deckel liegt darunter,
    # und ein massiver Klotz bekam beide Warnungen von hier. ``None`` heißt
    # „keine Aussage", und darauf wird nicht gerechnet.
    #
    # **Und die Frage geht in die Messung hinein.** Zwischen dem Deckel und
    # dieser Grenze lag sonst ein Bereich, in dem niemand antwortete: eine Wand
    # von 2,3 mm geht auf 2,7 Bahnen auf, wurde aber als „mindestens 2,0"
    # gemeldet und damit übergangen. Eine Zuordnung, kein toter Bereich —
    # gefragt wird mit der Zahl, um die es geht, und die deckt auch die
    # Bahnbreitenregel weiter unten (zwei Bahnen sind weniger als drei).
    asked = LINES_FOR_CLASSIC * settings.layers.line_width
    thin = narrowest_measured(result, interesting_below=asked)
    if thin is not None and thin < asked and settings.shell.wall_generator == "classic":
        advice.append(
            _advice(
                settings,
                path="shell.wall_generator",
                value="arachne",
                reason=_("Die dünnste Stelle passt in keine ganze Zahl von Bahnen."),
                severity="warning",
            )
        )

    if overhang > 0.0 and settings.speed.bridge > settings.speed.outer_wall:
        advice.append(
            _advice(
                settings,
                path="speed.bridge",
                value=settings.speed.outer_wall,
                reason=_("Schneller als die Außenwand hängen Brücken durch."),
            )
        )

    minimum = 2.0 * settings.layers.line_width
    least = NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    if thin is not None and 2.0 * least <= thin < minimum:
        # **Die Grenze ist die doppelte schmalste Bahn, nicht die einfache.**
        # Der Vorschlag senkt auf ``max(thin/2, least)``, und zwei solche
        # Bahnen passen nur dann in die Stelle, wenn sie mindestens
        # ``2 * least`` breit ist. Darunter kam ein Vorschlag heraus, der
        # nichts behob — bei einer 0,4er Düse und einer Stelle von 0,50 mm
        # lautete er „Bahnbreite 0,34“, und zwei Bahnen davon sind 0,68 mm.
        # Unter zwei Bahnen bleibt eine einzelne variable Bahn möglich.
        # Erst unter der angesetzten Mindestbahnbreite fordert der Befund
        # ``settings.wall_below_nozzle`` die Kontrolle im Slicer.
        advice.append(
            _advice(
                settings,
                path="layers.line_width",
                value=round(max(thin / 2.0, least), 3),
                reason=_("So passen zwei Bahnen in die dünnste Stelle."),
                severity="warning",
            )
        )

    # **Ein Keil in der Wand zeichnet sich durch die Außenwand ab.** Der
    # Organizer vom 20.09.2026: Außenwand 1,0 mm, in den spitzen Enden je ein
    # Becher, der die Wand von innen berührt — auf 24 mm Umfang läuft die
    # Stärke stetig von 1,0 auf 3,0 mm. Arachne wechselt dort die Wandzahl
    # Bahn für Bahn, die Innenwände werden zuerst gelegt, und ihre
    # Übergangsstücke wölben die dünne Außenwand darüber: ein Band aus Rillen
    # über die ganze Höhe, an beiden Enden. Zuerst gelegt liegt die Außenwand
    # auf glattem Grund, und die Übergänge bleiben innen, wo sie niemand sieht.
    #
    # Nicht, wo Stützen nötig sind: Eine zuerst gelegte Außenwand kragt ohne
    # Innenwand neben sich vor, und an steilen Überhängen ist das der
    # schlechtere Tausch.
    if (
        result.layers
        and tapered_layers(result) >= TAPERED_LAYERS_SHARE * len(result.layers)
        and settings.shell.wall_generator == "arachne"
        and not settings.shell.outer_wall_first
        and not needs_support
    ):
        advice.append(
            _advice(
                settings,
                path="shell.outer_wall_first",
                value=True,
                reason=_("Die wechselnde Wandstärke zeichnet sich sonst außen ab."),
                severity="warning",
            )
        )

    # **Eine runde Außenwand hat keine Ecke für die Naht.** Roberts
    # Minigolf-Schäfte (Ø 25,7 mm, 200 mm hoch, 27.09.2026) trugen mit Elegoos
    # Naht „aligned“ eine Linie über die ganze Höhe: Der Slicer fand keine
    # Ecke, in der er sie verstecken kann, und am Ende jeder Schleife stand
    # die Düse zum Rückzug still. Die Schrägnaht setzt Anfang und Ende flach
    # übereinander; nur an der Außenwand kostete sie je Schaft 8 von 558
    # Minuten.
    if (
        not settings.shell.scarf_seam
        and smooth_outline_height(result, SCARF_MIN_LOOP, profile.printer.nozzle_diameter)
        >= SCARF_MIN_HEIGHT
    ):
        advice.append(
            _advice(
                settings,
                path="shell.scarf_seam",
                value=True,
                reason=_("Auf der runden Wand findet die Naht keine Ecke."),
            )
        )

    # **Nur, wo keine Mindestzeit gilt.** Genau dafür ist sie da: Der Slicer
    # bremst jede Schicht, die schneller fertig wäre. Die Hersteller stimmen sie
    # je Filament auf ihre Lüfter ab (Elegoo 4 s, Prusa 6 s, Curas Definitionen
    # 8 s, im Orca-Bestand 5 bis 25 s), Solidons Stufen tragen eigene (5 bis
    # 12 s). Mit „weniger als 15 s“ überstimmte der Vorschlag sie im Druckerplan
    # der Gesamtprüfung 97-mal — an jedem Teil mit einer kleinen Schicht oben,
    # auch dort, wo die Platte in dieser Höhe noch andere Teile druckt.
    if _has_thin_layers(result) and is_zero(settings.cooling.minimum_layer_time):
        advice.append(
            _advice(
                settings,
                path="cooling.minimum_layer_time",
                value=THIN_LAYER_SECONDS,
                reason=_("Kleine Schichten oben kühlen sonst nicht ab."),
            )
        )
    # **Und die Mindestzeit muss erreichbar sein** (Drache, 08.10.2026): Der
    # Slicer bremst eine kurze Schicht nur bis zum Mindesttempo. Elegoo, Bambu
    # und Creality nennen für PLA 20 mm/s, und die obersten 12 mm des Drachen
    # druckten in jedem Slicer unter der eigenen Mindestzeit, die Spitzen in
    # 0,1 bis 1,3 s je Schicht. Die Mindestzeit selbst bleibt beim Hersteller.
    if _tips_stay_too_short(result, settings):
        advice.append(
            _advice(
                settings,
                path="cooling.minimum_speed",
                value=TIP_SPEED,
                reason=_("Kleine Spitzen kühlen nur langsamer gedruckt ab."),
            )
        )
    return advice


def _from_fits(settings: PrintSettings, kinds: Sequence[str]) -> list[SettingAdvice]:
    """Wo Passungen im Spiel sind, entscheidet die Außenwand über das Maß.

    Die Art zählt mit, und nicht nur das Ob: eine bündige Passung legt zwei
    Flächen aufeinander, und die obere ist dann eine Gleitfläche. Die will
    gebügelt werden — bei einem Schiebesitz oder einem Gewinde wäre dasselbe
    nur verlorene Zeit auf einer Fläche, die nichts berührt.
    """
    advice: list[SettingAdvice] = []
    careful = 30.0
    if "flush" in kinds and not settings.shell.ironing:
        advice.append(
            _advice(
                settings,
                path="shell.ironing",
                value=True,
                reason=_("Gebügelt gleiten die Flächen der bündigen Passung."),
            )
        )
    if not settings.shell.precise_outer_wall:
        advice.append(
            _advice(
                settings,
                path="shell.precise_outer_wall",
                value=True,
                reason=_("Für Passungen zählt die Außenwand auf Sollmaß."),
            )
        )
    if settings.speed.outer_wall_acceleration > CAREFUL_ACCELERATION:
        advice.append(
            _advice(
                settings,
                path="speed.outer_wall_acceleration",
                value=CAREFUL_ACCELERATION,
                reason=_("Weniger Beschleunigung hält die Kontur der Passungen genau."),
            )
        )
    if settings.speed.outer_wall > careful:
        advice.append(
            _advice(
                settings,
                path="speed.outer_wall",
                value=careful,
                reason=_("Langsam gefahren hält die Außenwand das Maß der Passungen."),
            )
        )
    if not settings.shell.outer_wall_first:
        advice.append(
            _advice(
                settings,
                path="shell.outer_wall_first",
                value=True,
                reason=_("Zuerst gelegt trifft die Außenwand das Maß der Passungen."),
            )
        )
    return advice


def solid_core(diameter: float, settings: PrintSettings) -> float:
    """Wie viel eines runden Querschnitts beim Drucken **nicht** massiv wird.

    Die Wände legen sich als Ring um den Querschnitt, der Rest ist
    Füllmuster — gerechnet am Durchmesser, so wie man es am geschnittenen Teil
    nachmisst: ``Durchmesser minus zweimal Wandzahl mal Bahnbreite``. Null oder
    weniger heißt: die Wände treffen sich in der Mitte, es bleibt nichts zu
    füllen.
    """
    return diameter - 2.0 * settings.shell.wall_count * settings.layers.line_width


def _fill_the_core(settings: PrintSettings, diameter: float, core: float) -> list[SettingAdvice]:
    """Der zweite Weg, wenn Wände den Kern nicht mehr schließen (§29).

    Die Schwelle ist dieselbe wie beim Wandvorschlag und keine neue Zahl:
    „Material mindestens so breit wie der Kern" heißt im Durchmesser
    ``kern = d/2``, und das sind im **Querschnitt** drei Viertel Material —
    :data:`SOLID_SHARE_OF_A_CONNECTOR`. Über die Füllung ausgedrückt:

        Anteil = (Ring + f · Kern) / Gesamt   mit Ring = (d^2 - kern^2) / d²

    nach ``f`` aufgelöst. Gerechnet für einen Ø-60-Zapfen bei zwei Wänden
    kommen 73,5 % heraus; die Zahl konvergiert mit wachsendem Durchmesser
    gegen die drei Viertel, weil der Ring dann kaum noch etwas beiträgt.

    **Das Muster entscheidet mit, und deshalb steht es im Grund.** Ein Gyroid
    liegt in alle Richtungen gleich, ein Grid lässt bei niedriger Dichte
    gerade in der Mitte Luft — dieselbe Prozentzahl trägt nicht überall
    gleich. Vorgeschlagen wird trotzdem nur die Dichte: Das Muster gilt dem
    ganzen Teil, und es für einen Zapfen umzustellen hieße, an einer Stelle zu
    drehen, die neunundneunzig Prozent des Drucks betrifft.
    """
    if core <= 0.0 or diameter <= 0.0:
        return []
    ring = (diameter * diameter - core * core) / (diameter * diameter)
    needed = (SOLID_SHARE_OF_A_CONNECTOR - ring) * (diameter * diameter) / (core * core)
    if needed > 1.0 or needed <= settings.infill.density:
        # Über hundert Prozent gibt es nicht, und was schon eingestellt ist,
        # ist kein Vorschlag.
        return []
    return [
        _advice(
            settings,
            path="infill.density",
            value=math.ceil(needed * 100.0) / 100.0,
            reason=_("Der Verbinder ist zu dick für Wände; die Füllung trägt ihn."),
        )
    ]


def _from_connectors(settings: PrintSettings, diameters: Sequence[float]) -> list[SettingAdvice]:
    """Ein Verbinder, der beim Drucken zum größten Teil aus Füllung besteht.

    Die Stiftplanung rechnet in Geometrie: Sie sucht auf der Schnittfläche
    Platz für einen Kreis und legt einen Zapfen hinein. Was der Drucker daraus
    macht, ist ein Ring aus Wänden mit Muster darin — und genau in diesem
    Muster sitzt die Verbindung, die die beiden Hälften zusammenhalten soll.

    Nachgemessen am Querschnitt: Ein Verbinder mit Ø 5,00 mm ist bei zwei
    Wänden à 0,42 mm innen **3,32 mm** Füllung und außen 1,68 mm Material. Ein
    Gyroid mit fünfzehn Prozent trifft diesen Kern womöglich gar nicht, und
    dann trägt der Stift auf ganzer Länge nur seine Außenhaut.

    Vorgeschlagen wird die Wandzahl und nicht die Füllung, obwohl beide Wege
    gangbar sind: Wände liegen deterministisch um den Zapfen, Füllung trifft
    ihn statistisch. Wer lieber an der Füllung dreht, sieht am Grund daneben,
    worum es geht — angewandt wird nichts von allein.

    **Nicht bis vollmassiv.** Der Vorschlag bringt den Zapfen genau auf die
    Schwelle, ab der das Material um ihn herum mindestens so breit ist wie sein
    Kern — dieselbe Rechnung, mit der oben entschieden wird, dass es überhaupt
    eine Sache ist. Bis zum vollen Querschnitt zu gehen hieße bei einem
    8-mm-Zapfen zehn Wände auf dem ganzen Teil, und ein Vorschlag, den niemand
    annimmt, macht die vier daneben unglaubwürdig.
    """
    if not diameters or is_close(settings.infill.density, 1.0):
        return []
    width = settings.layers.line_width
    if width <= 0.0:
        return []

    # Der dickste Verbinder gibt den Ausschlag: Was ihn trägt, trägt die
    # dünneren erst recht.
    thickest = max(diameters)
    core = solid_core(thickest, settings)
    solid = 2.0 * settings.shell.wall_count * width
    # Erst wenn der Füllkern breiter ist als das Material um ihn herum. Ein
    # Zapfen mit ein paar Zehnteln Muster in der Mitte trägt; einer, der zur
    # Hälfte aus Muster besteht, ist eine andere Sache.
    if core <= solid:
        return []

    # Aus "Material mindestens so breit wie der Kern" nach der Wandzahl
    # aufgelöst: 2*w*lw >= d - 2*w*lw, also w >= d / (4*lw).
    needed = math.ceil(thickest / (4.0 * width))
    if needed > MOST_WALLS_WORTH_SUGGESTING:
        # Über Wände ist der Kern nicht mehr zu schließen. Der Vorschlag wäre
        # eine Zahl, die niemand einstellen kann — und schlimmer: die man
        # **übernehmen** kann. Gemessen am 03.09.2026 mit einem Zapfen von
        # Ø 60 mm: Vorschlag 36 Wände, „Vorschläge übernehmen" schrieb sie ins
        # Dokument, und in der übergebenen Datei stand ``wall_loops: 36``. Der
        # Dialog zeigte dabei 20, denn sein Feld reicht nicht weiter — Anzeige
        # und Datei sagten Verschiedenes, und der Slicer hätte 15 mm Wand
        # gedruckt.
        #
        # Dann bleibt der zweite Weg, den der Docstring oben als gangbar
        # nennt: das Muster im Kern.
        return _fill_the_core(settings, thickest, core)
    return [
        _advice(
            settings,
            path="shell.wall_count",
            value=needed,
            reason=_("So trägt der Verbinder mehr Wand als Füllung."),
        )
    ]


#: Was je Teil geschrieben wird, wenn sein Grund an der Geometrie hängt
#: (Konzept Herstellerprofil, Entscheidung G): Stützen mit Art, Ort und
#: Sperre, die Haftung, die Werte einer Passung, Wände und Füllung um
#: Verbinder, Wandgenerator und Bahnbreite an schmalen Stellen. Dazu der
#: Stützkontakt: Abstand und Trennschichten hängen am Material der Spule, die
#: das Teil druckt, und nur das gestützte Teil braucht sie (RM-583). Und was
#: frei druckt (RM-587): Brückenstütze, dicke Brücken, Brückenfluss,
#: Zusatzwände und Umkehr gehören dem Teil mit der Brücke oder dem Überhang.
#: Temperatur, Kühlung, Rückzug und Volumenstrom gehen je Spule hinaus
#: (``print_settings_dialog.FILAMENT_GROUPS``), nicht je Teil.
#:
#: **Die Wände der Bäume fehlen, obwohl ihr Grund an der Geometrie hängt**
#: (``support.tree_walls``, RM-584): Ob ein Programm die Wandzahl je Objekt
#: liest, ist für keines gemessen, und eine Objektzahl, die der Slicer
#: übergeht, ließe die hohen Bäume mit einer Wand stehen, während der Dialog
#: zwei nennt. Plattenweit trifft der Wert jedes Teil sicher; ein niedriger Baum
#: daneben trägt die zweite Wand für etwas Material mit.
PART_PATHS: Final = frozenset(
    {
        "support.bridges",
        "shell.thick_bridges",
        "shell.bridge_flow",
        "shell.overhang_walls",
        "shell.overhang_reverse",
        "support.style",
        "support.placement",
        "support.block_channels",
        "support.spare_ledges",
        "support.z_gap",
        "support.interface_layers",
        "support.bottom_interface_layers",
        "support.interface_spacing",
        "adhesion.kind",
        "adhesion.brim_gap",
        "shell.precise_outer_wall",
        "shell.outer_wall_first",
        "shell.ironing",
        "shell.scarf_seam",
        "speed.outer_wall",
        "speed.outer_wall_acceleration",
        "speed.inner_wall",
        "speed.acceleration",
        "shell.wall_count",
        "infill.density",
        "shell.wall_generator",
        "layers.line_width",
    }
)

#: Der Stützkontakt (RM-583): je Teil geschrieben, und der Rat geht je Körper
#: in beide Richtungen — PLA will weniger Abstand als PETG, eine Figur eine
#: lockere Trennschicht als eine flache Decke. Der Druckdialog führt diese Pfade
#: deshalb getrennt zusammen (:func:`combine`, ``separate``).
CONTACT_PATHS: Final = frozenset(
    {
        "support.z_gap",
        "support.interface_layers",
        "support.bottom_interface_layers",
        "support.interface_spacing",
    }
)

#: Was nur der Schnitt des Körpers sagen kann (:func:`_from_geometry` samt
#: :func:`_calm_walls`). Der Export schneidet ein Teil eigens, wenn einer
#: dieser Pfade je Teil geht (``writer._part_values``); fehlt hier ein Pfad,
#: schweigt der Rat je Teil ohne Schnitt, und der übernommene Wert landet an
#: jedem Teil (RM-328). ``tests/test_export.py`` hält die Liste gegen die
#: Pfade, die diese Regeln setzen.
SLICED_PATHS: Final = frozenset(
    {
        "support.style",
        "support.placement",
        "support.block_channels",
        "support.spare_ledges",
        "support.tree_walls",
        "support.z_gap",
        "support.interface_layers",
        "support.bottom_interface_layers",
        "support.interface_spacing",
        "adhesion.kind",
        "adhesion.brim_gap",
        "shell.wall_generator",
        "shell.outer_wall_first",
        "shell.scarf_seam",
        "layers.line_width",
        "speed.outer_wall",
        "speed.inner_wall",
        "speed.outer_wall_acceleration",
        "speed.acceleration",
        "speed.first_layer",
        "speed.bridge",
        "cooling.minimum_layer_time",
        "cooling.minimum_speed",
        "support.bridges",
        "shell.thick_bridges",
        "shell.bridge_flow",
        "shell.overhang_walls",
        "shell.overhang_reverse",
    }
)


def plate_paths(
    settings: PrintSettings, profile: Profile, *, flavour: SlicerFlavour | None = None
) -> frozenset[str]:
    """Was die plattenweiten Regeln an diesen Einstellungen ändern wollen.

    Maschine, Material und Volumenstrom (:func:`advise` ohne Schnitt, Passung
    und Verbinder). ``_from_material`` bremst weiches Filament auch an der
    Außenwand und legt bei ABS einen Brim; ein übernommener Vorschlag auf so
    einem Pfad gilt der ganzen Platte, auch wo die Geometrie ihn ebenfalls
    verlangt.
    """
    return frozenset(entry.path for entry in advise(settings, profile, flavour=flavour))


def connector_diameters(bodies: Sequence[SceneObject]) -> tuple[float, ...]:
    """Die Durchmesser der Zapfen, die beim Teilen an diesen Körpern entstanden sind.

    Aus den Merkmalen und nicht aus dem Stapel: Die Stiftplanung rechnet den
    Durchmesser aus der Schnittfläche, er ist kein eingetragener Parameter.
    Nur erzeugte Zapfen (``provenance == "generated"``): Ein erkannter ist eine
    Vermutung über eine Form, und an einem heruntergeladenen Sockel von 160 auf
    231 auf 14 mm passte die Erkennung einen „Zapfen" von Ø 631,6 mm hinein —
    die Wandregel schlug daraus 376 Wände vor, und *Vorschläge übernehmen*
    schrieb sie ins Projekt. Nur die Zapfen, nicht ihre Bohrungen: dasselbe
    Maß plus Spiel, zweimal gezählt sähe es nach doppelt so vielen Verbindern
    aus.
    """
    return tuple(
        float(feature.params["diameter"])
        for entry in bodies
        for feature in entry.features.values()
        if feature.kind == "pin"
        and feature.provenance == "generated"
        and "diameter" in feature.params
    )


def for_part(
    settings: PrintSettings,
    bounds: BoundingBox,
    footprint: float,
    *,
    profile: Profile | None = None,
    result: SliceResult | None = None,
    fit_kinds: Sequence[str] = (),
    connectors: Sequence[float] = (),
    flavour: SlicerFlavour | None = None,
    whole_layers: bool = False,
    organic: Collection[str] = (),
    declined: Collection[str] = (),
    trees: Collection[str] | None = None,
) -> list[SettingAdvice]:
    """Was dieses eine Teil anders braucht als die Platte (§29).

    Die Druckbetthaftung zählt je Teil statt je Auftrag: sie hängt daran,
    worauf ein Körper steht. Beim Gewürzset stehen zwölf Behälter auf Ø 40 und
    drei Streuscheiben auf je drei 1,1-mm-Federarmen — dieselbe Platte, und der
    Brim gehört nur unter die Scheiben.

    **Mit ``profile`` alles, was an der Geometrie dieses Teils hängt**
    (Entscheidung G): der Rat aus Schnitt, Passung und Verbindern, beschränkt
    auf :data:`PART_PATHS`. So bekommt nur der Körper Stützen, der sie
    braucht, und die übrigen drucken wie die Platte. Die Haftungsregeln hier
    kommen danach und behalten beim Brim das letzte Wort: Sie kennen die
    Grundfläche aus dem Schnitt, die Regel der Platte nur den Hüllquader.
    Über Orcas Auto-Brim schweigen sie (:func:`_unanchored`).
    """
    advice: list[SettingAdvice] = []
    if profile is not None:
        advice += [
            entry
            for entry in advise(
                settings,
                profile,
                result,
                bounds=bounds,
                fit_kinds=fit_kinds,
                connectors=connectors,
                flavour=flavour,
                whole_layers=whole_layers,
                organic=organic,
                declined=declined,
                trees=trees,
            )
            if entry.path in PART_PATHS
        ]
    if _unanchored(settings, flavour):
        if 0.0 < footprint < SMALL_FOOTPRINT:
            reason = SMALL_FOOTPRINT_REASON
        elif _slender(bounds):
            reason = SLENDER_REASON
        else:
            reason = None
        if reason is not None:
            advice += _brim_where_it_fits(
                settings, profile, result, reason, narrower=False, flavour=flavour
            )
    return _merged(settings, advice)


#: Der Brückenfluss über langen freien Brücken (RM-587): die Mitte des Bands
#: 0,85 bis 0,95 der Recherche vom 08.10.2026 (Nr. 11), der Wert von Creality
#: und Anycubic in der Orca-Familie.
BRIDGE_FLOW: Final = 0.9

#: Bis zu welchem Brückenfluss der Wert des Herstellers bleibt: das obere Ende
#: desselben Bands. Prusas Bündel für den SV06 trägt 0,95 und braucht nichts.
BRIDGE_FLOW_ENOUGH: Final = 0.95

#: Materialien, die sich an steilen Überhängen aufrollen: schrumpfende und weiche
#: (Recherche Nr. 12). Für sie lohnt die Umkehr der Wandrichtung.
CURLING_MATERIALS: Final = WARPING_MATERIALS | FLEXIBLE_MATERIALS


def _bridges_and_overhangs(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult,
    need: SupportNeed,
    advice: Sequence[SettingAdvice],
    declined: Collection[str],
    flavour: SlicerFlavour | None,
) -> list[SettingAdvice]:
    """Lange Brücken und Überhänge, die ohne Stütze sauber drucken sollen (RM-587).

    **Brücken stützen**, wo eine lange Brücke Stütze verlangt
    (:func:`_may_need_support`) und das Teil mit Stützen druckt: PrusaSlicer
    spannt sie ohne eigenen Wert frei, auch mit „überall“ (G-Code-Gegenprüfung
    N1, 36-mm-Brücke ohne Stütze). **Dicke Brücken und weniger Fluss**, wo eine
    Brücke über :data:`SPAN_INTERESTING` frei druckt — ohne Stützen, ohne
    Brückenstütze, oder als Kanaldecke oder Rand, die Solidon freihält. Über
    einer Stütze trägt die dünne Brücke und sieht besser aus.

    **Zusatzwände** unter flachen Überhängen ohne Stütze, die breiter sind als die
    Wände (gemessen in PrusaSlicer und OrcaSlicer: zwischen 45 Grad und der
    Stützgrenze ändert der Schalter nichts, unter einer Auskragung ersetzt er die
    losen Brückenbahnen). **Die Umkehr** an steilen Wänden zwischen 45 Grad und
    der Stützgrenze für Material, das sich aufrollt — nur in der Orca-Familie,
    die anderen kennen sie nicht. Steil ist eine Wand, die über ihre Höhe weiter
    als eine Bahnbreite über die 45-Grad-Linie hinauswandert
    (:func:`steep_reach`): Erst dann liegt ihre Außenbahn neben der Bahn, die eine
    45-Grad-Wand dort legte; darunter ist sie eine Kante, eine Rundung von 2 mm
    bringt 0,1 mm.
    """
    found: list[SettingAdvice] = []
    style = printed_style(settings, advice, declined)
    supported = style != "none"
    # Ein Rand spannt nicht (:func:`_from_spans`): Seine Weite ist die Länge der
    # Kante, über die er hängt, und über ihm ist keine Brücke zu tragen.
    long_spans = [
        index
        for index, layer in enumerate(result.layers)
        if layer.bridge_width > SPAN_INTERESTING
        and not (
            layer.overhangs
            and all((index, number) in need.ledges for number in range(len(layer.overhangs)))
        )
    ]
    held = settings.support.bridges
    if supported and not held and need.needed:
        # Welche Decke der Slicer als Brücke liest, rechnet nur er: Am Kobra 2
        # stützte OrcaSlicer vom Pilzhut nur den Rand (``estimate``), an der
        # 36-mm-Brücke alles. Wo Solidon Stütze verlangt, gilt sie deshalb auch
        # unter Brücken.
        spans = any(index not in need.quiet_layers for index in long_spans)
        found.append(
            _advice(
                settings,
                path="support.bridges",
                value=True,
                reason=_("Die lange Brücke hängt ohne Stütze durch.")
                if spans
                else _("Sonst lässt der Slicer Decken frei, die Stütze brauchen."),
            )
        )
        held = "support.bridges" not in declined
    free = [index for index in long_spans if not (supported and held) or index in need.quiet_layers]
    if free and not settings.shell.thick_bridges:
        found.append(
            _advice(
                settings,
                path="shell.thick_bridges",
                value=True,
                reason=_("Dicke Bahnen tragen über die lange freie Brücke."),
            )
        )
    if free and settings.shell.bridge_flow > BRIDGE_FLOW_ENOUGH + EPS_GEOM:
        found.append(
            _advice(
                settings,
                path="shell.bridge_flow",
                value=BRIDGE_FLOW,
                reason=_("Mit etwas weniger Material hängt die Brücke weniger durch."),
            )
        )
    if not settings.shell.overhang_walls and _free_flat_overhang(
        settings, result, need, advice, declined, supported
    ):
        found.append(
            _advice(
                settings,
                path="shell.overhang_walls",
                value=True,
                reason=_("Zusatzwände halten den Überhang ohne Stütze."),
            )
        )
    if (
        profile.material.id in CURLING_MATERIALS
        and flavour not in ("prusa", "cura")
        and not settings.shell.overhang_reverse
        and steep_reach(result, enough=settings.layers.line_width) > settings.layers.line_width
    ):
        found.append(
            _advice(
                settings,
                path="shell.overhang_reverse",
                value=True,
                reason=_("Wechselnd gedruckt rollen sich steile Wände nicht auf."),
            )
        )
    return found


def _free_flat_overhang(
    settings: PrintSettings,
    result: SliceResult,
    need: SupportNeed,
    advice: Sequence[SettingAdvice],
    declined: Collection[str],
    supported: bool,
) -> bool:
    """Druckt ein flacher Überhang frei, der breiter ist als die Wände (RM-587)?

    Frei heißt: ohne Stützen jedes Stück, mit Stützen die Ränder, die Solidon
    freihält (``support.spare_ledges``, gesetzt oder vorgeschlagen). Breit heißt
    im Mittel breiter als alle Wandbahnen zusammen, geschätzt als doppelte Fläche
    durch Umfang; schmaler liegt der Überhang ganz unter den Wänden, und die
    Zusatzwände haben nichts zu verankern. Ein Stück unter
    :data:`OVERHANG_LAYER_MINIMUM` ist eine Kante, kein Überhang. **Und nur, was
    an einer Seite hängt** (:func:`cantilevers`): Eine an beiden Enden gelagerte
    Brücke legt der Slicer mit und ohne Zusatzwände gleich.
    """
    spared = settings.support.spare_ledges or (
        "support.spare_ledges" not in declined
        and any(entry.path == "support.spare_ledges" for entry in advice)
    )
    if supported and not (spared and need.ledges):
        return False
    walls = settings.shell.wall_count * settings.layers.line_width
    wide: list[tuple[int, int]] = []
    for index, layer in enumerate(result.layers):
        for number, piece in enumerate(layer.overhangs):
            if supported and (index, number) not in need.ledges:
                continue
            area = piece_area(piece)
            if area < OVERHANG_LAYER_MINIMUM:
                continue
            perimeter = _ring_length(piece.outline) + sum(
                _ring_length(hole) for hole in piece.holes
            )
            if perimeter > 0.0 and 2.0 * area / perimeter > walls:
                wide.append((index, number))
    return bool(wide) and bool(cantilevers(result, wide, settings.layers.line_width))


def _ring_length(ring: object) -> float:
    """Der Umfang eines geschlossenen Rings in mm."""
    points = np.asarray(ring, dtype=float)
    if len(points) < 2:
        return 0.0
    closed = np.vstack((points, points[:1]))
    return float(np.hypot(*np.diff(closed[:, :2], axis=0).T).sum())


def _quiet_layers(result: SliceResult, quiet: frozenset[tuple[int, int]]) -> frozenset[int]:
    """Schichten, deren Überhang ganz aus Kanal- und Randstücken besteht — ihre
    Brücken tragen sich selbst oder verlangen keine Stütze."""
    return frozenset(
        index
        for index, layer in enumerate(result.layers)
        if layer.overhangs
        and all((index, number) in quiet for number in range(len(layer.overhangs)))
    )


def _may_need_support(
    result: SliceResult,
    islands: tuple[float, ...],
    overhang: float,
    patch: float,
    quiet_layers: frozenset[int] = frozenset(),
) -> bool:
    """Die zwei Wege aus :func:`_from_geometry` zum Stützbedarf, dazu Inseln
    und lange Brücken außerhalb der Schichten aus Kanal- und Randstücken
    (:func:`_quiet_layers`)."""
    return (
        bool(islands)
        or worth_support(patch, overhang)
        or any(
            layer.bridge_width > SPAN_INTERESTING
            for index, layer in enumerate(result.layers)
            if index not in quiet_layers
        )
    )


def _on_small_feet(result: SliceResult) -> bool:
    """Steht der Körper auf mehreren Inseln, von denen keine für sich die
    Standfläche eines Teils hat (:data:`SMALL_FOOTPRINT`)?"""
    if not result.layers:
        return False
    feet = [piece_area(contour) for contour in result.layers[0].contours]
    return len(feet) >= 2 and max(feet) < SMALL_FOOTPRINT


def _calm_walls(settings: PrintSettings) -> list[SettingAdvice]:
    """Wände und Beschleunigung eines schlanken Körpers auf kleinem Fuß.

    Innenwand und Grundbeschleunigung gehören dazu: Bei einer Stange sind die
    Wände fast der ganze Querschnitt, und in Orca fährt die Innenwand mit der
    Grundbeschleunigung — am Centauri Carbon 2 mit 10 000 mm/s², doppelt so
    hart wie die Außenwand.
    """
    reason = SLENDER_REASON
    wanted = (
        ("speed.outer_wall", settings.speed.outer_wall, SLENDER_WALL_SPEED),
        ("speed.inner_wall", settings.speed.inner_wall, SLENDER_WALL_SPEED),
        (
            "speed.outer_wall_acceleration",
            settings.speed.outer_wall_acceleration,
            CAREFUL_ACCELERATION,
        ),
        ("speed.acceleration", settings.speed.acceleration, CAREFUL_ACCELERATION),
    )
    return [
        _advice(settings, path=path, value=calm, reason=reason, severity="warning")
        for path, current, calm in wanted
        if current > calm + EPS_GEOM
    ]


def _slender(bounds: BoundingBox) -> bool:
    return settings_table.is_slender(bounds)


#: Ein Brim unter so vielen Bahnen der ersten Schicht hält nichts; schmaler
#: wird keiner vorgeschlagen.
BRIM_LEAST_LINES: Final = 3


def brim_room(result: SliceResult, profile: Profile) -> float | None:
    """Wie breit ein Rand um dieses Teil auf dem Bett des Druckers höchstens
    sein kann, gedreht wie es am besten passt, in mm (:func:`build_area.rim_room`).

    Der Rand liegt um die unterste Schicht, das ganze Teil muss dabei aufs
    Bett passen (RM-312): Ein Tisch auf einem Fuß in der Mitte hat Platz für
    den Brim, eine Schüssel auf Füßen am Rand nicht. ``None`` ohne Schicht.
    Knapp unter null heißt nicht „passt nicht“: Die Waschschüssel hat am
    Schnitt des Druckdialogs minus 0,06 mm, an ihrem Netz 0,14 mm — ein Brim
    passt in beiden Fällen nicht."""
    layers = [
        [np.asarray(contour.outline, dtype=float) for contour in layer.contours]
        for layer in result.layers
    ]
    layers = [[ring for ring in rings if len(ring) >= 3] for rings in layers]
    layers = [rings for rings in layers if rings]
    if not layers:
        return None
    whole = np.concatenate([ring for rings in layers for ring in rings])
    return build_area.rim_room(np.concatenate(layers[0]), whole, profile.printer)


def _skirt_where_it_fits(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult,
    flavour: SlicerFlavour | None = None,
) -> list[SettingAdvice]:
    """Ohne Skirt, wo neben dem Teil auf dem Bett kein Platz für ihn ist.

    Die Waschschüssel liegt auf 220 auf 220 mm schräg mit 0,15 mm Rand; Curas
    Skirt (3 mm Abstand, zwei Runden) lief über den Bettrand und riss in der
    ersten Schicht in 23 Züge (04.10.2026). Ein Skirt hält nichts fest, er
    spült nur die Düse; fehlt der Platz, ist ohne ihn besser als daneben.
    """
    if settings.adhesion.kind != "skirt":
        return []
    room = brim_room(result, profile)
    if room is None or room >= build_area.rim_of(settings, flavour or "other").reach - EPS_GEOM:
        return []
    return [
        _advice(
            settings,
            path="adhesion.kind",
            value="none",
            reason=_("Für den Skirt ist neben diesem Teil auf dem Bett kein Platz."),
            severity="warning",
        )
    ]


def _brim_where_it_fits(
    settings: PrintSettings,
    profile: Profile | None,
    result: SliceResult | None,
    reason: TranslatableText,
    *,
    narrower: bool = True,
    flavour: SlicerFlavour | None = None,
) -> list[SettingAdvice]:
    """Den Brim vorschlagen, aber nicht über den Bettrand hinaus.

    Die Waschschüssel steht auf zwölf kleinen Füßen und bekam einen Brim von
    5 mm vorgeschlagen; auf 220 auf 220 mm passt sie nur schräg, mit 0,15 mm
    Luft. Übernommen druckte CuraEngine den Rand neben das Bett (04.10.2026).
    Reicht der Platz für einen schmaleren Rand, wird der vorgeschlagen
    (``narrower``, nur plattenweit — die Breite ist kein Teilwert); reicht er
    nicht einmal dafür, bleibt der Vorschlag weg, und der Prüfbericht sagt
    warum (:func:`located_warnings`, ``settings.brim_no_room``).
    """
    brim = _advice(settings, path="adhesion.kind", value="brim", reason=reason, severity="warning")
    if profile is None or result is None:
        return [brim]
    room = brim_room(result, profile)
    # Wie weit der übernommene Brim reicht, sagt dieselbe Rechnung wie bei der
    # Übergabe (:func:`build_area.rim_of`): Brim des Profils, eine Art, die
    # Solidon schreibt.
    suggested = settings_table.with_accepted(settings, "adhesion.kind", "brim")
    reach = build_area.rim_of(suggested, flavour or "other").reach
    if room is None or room >= reach - EPS_GEOM:
        return [brim]
    line = settings.layers.first_layer_line_width or settings.layers.line_width
    width = math.floor((room - (reach - settings.adhesion.brim_width)) * 10.0) / 10.0
    if not narrower or width < BRIM_LEAST_LINES * line:
        return []
    return [
        brim,
        _advice(
            settings,
            path="adhesion.brim_width",
            value=width,
            reason=_("Breiter passt der Brim nicht auf das Bett dieses Druckers."),
            severity="warning",
        ),
    ]


def _has_thin_layers(result: SliceResult) -> bool:
    """Läuft das Teil nach oben so spitz zu, dass Schichten zu schnell fertig
    sind?

    Gefragt ist die Spitze, nicht das Mittel: ein Sockel mit einem Türmchen
    darauf hat eine große Durchschnittsfläche und trotzdem das Problem.
    """
    if not result.layers:
        return False
    upper = result.layers[len(result.layers) // 2 :]
    return any(layer.area < THIN_LAYER_AREA for layer in upper)


def _tips_stay_too_short(result: SliceResult, settings: PrintSettings) -> bool:
    """Bleiben Schichten trotz Mindestzeit zu kurz, weil das Mindesttempo bremst?

    Der Weg einer kleinen Schicht ist ihre Fläche durch die Bahnbreite — eine
    Spitze ist ganz Bahn. Zu kurz heißt: Mit dem Mindesttempo braucht sie nicht
    einmal die halbe Mindestzeit; gezählt wird erst ab :data:`TIP_HEIGHT` solcher
    Schichten, sonst ist es nur die letzte Schicht einer Kuppe.
    """
    minimum_time = settings.cooling.minimum_layer_time
    speed = settings.cooling.minimum_speed
    width = settings.layers.line_width
    if is_zero(minimum_time) or speed <= TIP_SPEED + EPS_GEOM or width <= EPS_GEOM:
        return False
    height = 0.0
    below = 0.0
    for layer in result.layers:
        thickness = layer.z - below
        below = layer.z
        if layer.area <= EPS_GEOM:
            continue
        if layer.area / width / speed < minimum_time / 2.0:
            height += thickness
    return height >= TIP_HEIGHT - EPS_GEOM


def warnings_for(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult | None = None,
    *,
    fitted: bool = True,
) -> list[Finding]:
    """Was gesagt gehört, obwohl keine Einstellung es behebt (§17.3).

    Ein Vorschlag ändert einen Wert. Manches ändert kein Wert: ASA auf einem
    offenen Drucker bleibt heikel, auch wenn Lüfter und Brim schon richtig
    stehen. Das als Vorschlag zu verkleiden hieße, eine Einstellung zu ändern,
    die bereits stimmt — also wird es ein Befund, und der Nutzer entscheidet,
    ob er es trotzdem versucht.

    Herkunft ``internal``: das ist geschlossen aus Profil und Maschine, nicht
    aus einer geslicten Datei gemessen (Regel 14).

    Und für Resin nichts — aus demselben Grund wie bei :func:`advise`: ASA
    ist ein Filament, das Bett heizt kein Harz, und eine Brücke gibt es in
    einem Harzbad nicht (Resin-Konzept B4).

    ``fitted`` sagt, ob die Szene Passungen trägt, eingetragene oder gebaute
    (``scene.fits.fit_kinds_for``). Nur dort wirken die Toleranzen des
    Materials; ohne sie stand der Hinweis zur Kalibrierung an jedem Teil einer
    frischen Installation und sagte nichts über den Druck (Durchsicht 0.5.1).
    """
    findings: list[Finding] = []
    if profile.printer.is_resin:
        return findings

    if profile.material.id in WARPING_MATERIALS and not profile.printer.enclosed:
        findings.append(
            Finding(
                code="settings.warping_material_open_printer",
                severity="warning",
                message=_(
                    "Dieses Material zieht sich stark zusammen, und dieser Drucker hat "
                    "keinen geschlossenen Bauraum. Hohe Teile reißen an den Ecken auf."
                ),
                values={
                    "material": profile.material.title,
                    "printer": profile.printer.title,
                },
                # Regel 17: Ein geschlossener Drucker oder ein anderes Material —
                # beides in den Druckeinstellungen.
                suggestions=(CHOOSE_PRINTER,),
            )
        )

    if fitted and not profile.material.calibrated:
        # **Einmal gesagt und mit dem Weg dorthin.** Der Satz stand in keinem
        # Bericht, weil ``warnings_for`` keinen Aufrufer hatte (Durchsicht
        # 0.5.0); jetzt steht er im Prüfbericht, und der Knopf daneben öffnet
        # die Kalibrierung — ein Hinweis ohne Handlung ist nach Regel 17 nur
        # halb.
        findings.append(
            Finding(
                code="settings.uncalibrated_material",
                severity="info",
                message=_(
                    "Die Toleranzen dieses Materials sind Startwerte. Passen Sie sie anhand "
                    "eines gedruckten Toleranz-Testkörpers in der Materialkalibrierung an."
                ),
                values={"material": profile.material.title},
                suggestions=(CALIBRATE_MATERIAL,),
            )
        )

    if not settings_table.has_material(profile.material.id):
        # `_material_table` fällt still auf die Modellvorgaben zurück — mit
        # Absicht, ein neues Material soll ohne Tabellenpflege druckbar sein.
        # Was fehlte, war der Satz an den Nutzer (Regel 21): Temperaturen und
        # Tempo eines selbst angelegten Materials sind sonst PLA-nahe Werte,
        # ohne dass es irgendwo steht.
        findings.append(
            Finding(
                code="settings.material_without_profile",
                severity="info",
                message=_(
                    "Für dieses Material gibt es keine eigenen Druckeinstellungen — "
                    "es druckt mit den Modellvorgaben. Temperaturen und Tempo bitte "
                    "nachstellen."
                ),
                values={"material": profile.material.title},
            )
        )

    # **Was die Maschine nicht kann, wird gesagt und nicht gedeckelt.**
    # ``print_settings._temperatures`` nimmt das Kleinere aus Materialwunsch
    # und Maschinengrenze, und sein Docstring sagt dazu „gedeckelt wird, aber
    # ``advise`` sagt es auch". Für die Düse stimmte das (``_from_machine``),
    # für Bett und Bauraum nicht: ABS will 100 °C Bett, der A1 mini kann 80 —
    # der Druck lief mit zwanzig Grad zu kaltem Bett los, und im Bericht stand
    # kein Wort. Ein **Befund** und kein Vorschlag, denn kein Wert behebt es:
    # 80 Grad sind bereits das Höchste, was die Maschine hergibt (§17.3).
    wanted_nozzle = settings_table.material_temperature(profile.material.id, "nozzle")
    if wanted_nozzle is not None and wanted_nozzle > profile.printer.nozzle_temperature_max:
        findings.append(
            Finding(
                code="settings.nozzle_below_material",
                severity="warning",
                message=_(
                    "Dieses Material braucht eine höhere Düsentemperatur, als dieser "
                    "Drucker erreicht. Ein anderes Material oder einen Drucker mit "
                    "ausreichender Düsentemperatur wählen."
                ),
                values={
                    "material": profile.material.title,
                    "printer": profile.printer.title,
                    "wanted": float(wanted_nozzle),
                    "possible": float(profile.printer.nozzle_temperature_max),
                },
                # Regel 17: Drucker und Material wählt man in den Druckeinstellungen.
                suggestions=(CHOOSE_PRINTER,),
            )
        )

    wanted_bed = settings_table.material_temperature(profile.material.id, "bed")
    if wanted_bed is not None and wanted_bed > profile.printer.bed_temperature_max:
        findings.append(
            Finding(
                code="settings.bed_below_material",
                severity="warning",
                message=_(
                    "Dieses Material braucht ein wärmeres Bett, als der Drucker heizt. Ohne Brim "
                    "oder Raft löst sich das Teil beim Abkühlen."
                ),
                values={
                    "material": profile.material.title,
                    "printer": profile.printer.title,
                    "wanted": float(wanted_bed),
                    "possible": float(profile.printer.bed_temperature_max),
                },
                # Regel 17: Brim und Raft stehen in den Druckeinstellungen.
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )

    # Dieselbe stille Kürzung beim Bauraum, und sie ist die vollständigere:
    # ``_temperatures`` setzt die Kammer auf null, wo kein geschlossener
    # Bauraum da ist. Der Zweig in :func:`_from_machine`, der davor warnt,
    # sieht deshalb nie einen Wert über null — er greift allein bei einer von
    # Hand eingetragenen Temperatur.
    wanted_chamber = settings_table.material_temperature(profile.material.id, "chamber")
    if wanted_chamber and not profile.printer.enclosed:
        findings.append(
            Finding(
                code="settings.chamber_without_enclosure",
                severity="warning",
                message=_(
                    "Dieses Material will einen geheizten Bauraum, den dieser Drucker nicht hat. "
                    "Das Teil vor Zugluft schützen."
                ),
                values={
                    "material": profile.material.title,
                    "printer": profile.printer.title,
                    "wanted": float(wanted_chamber),
                },
                # Regel 17: Der Drucker mit geschlossenem Bauraum ist der Weg, den der Satz nennt.
                suggestions=(CHOOSE_PRINTER,),
            )
        )

    if settings.support.style != "none" and settings.support.z_gap < settings.layers.layer_height:
        findings.append(
            Finding(
                code="settings.support_gap_too_small",
                severity="warning",
                message=_(
                    "Der Abstand der Stütze zum Teil ist kleiner als eine Schicht — sie "
                    "verschweißt und lässt sich nicht mehr abnehmen."
                ),
                values={
                    "gap": settings.support.z_gap,
                    "layer_height": settings.layers.layer_height,
                },
                # Regel 17: Der Stützabstand steht in den Druckeinstellungen.
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )

    if result is not None:
        findings += located_warnings(result, profile)
    return findings


def located_warnings(result: SliceResult, profile: Profile) -> list[Finding]:
    """Die Befunde aus der Geometrie — jeder mit der Stelle, an der er sitzt.

    Eine Rechnung für zwei Wege: :func:`warnings_for` nimmt sie für den
    Druckdialog, :func:`app.core.slice.findings.body_findings` bindet sie
    zusätzlich an ihren Körper für den Prüfbericht. Der Ort ist die Mitte der
    Fläche, die an der dünnsten Stelle bei der Öffnung verloren geht, bzw. die
    Mitte der freien Fläche über der längsten Brücke; ohne Ort fliegt der
    Klick zum Körper.
    """
    findings: list[Finding] = []
    least = NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    thin = narrowest_measured(result)
    if thin is not None and thin < least:
        # Eine einzelne variable Arachne-Bahn kann eine Wand tragen.
        # Zwei Bahnen sind eine Festigkeitsfrage, keine Druckbarkeitsgrenze.
        layer = min(
            (entry for entry in result.layers if entry.min_width > EPS_GEOM),
            key=lambda entry: entry.min_width,
        )
        spot = thinnest_spot(_layer_shape(layer), layer.min_width)
        findings.append(
            Finding(
                code="settings.wall_below_nozzle",
                severity="warning",
                message=_(
                    "Die dünnste Stelle ist schmaler als eine Bahn und fehlt im Slicer "
                    "womöglich. Eine kleinere Düse hilft."
                ),
                values={
                    "width_mm": thin,
                    "nozzle_mm": profile.printer.nozzle_diameter,
                    "least_mm": least,
                    "z_mm": round(layer.z, 2),
                },
                location=None if spot is None else (spot[0], spot[1], layer.z),
                # Regel 17: Düse und Bahnbreite stehen in den Druckeinstellungen.
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )
    findings += _from_spans(result)
    # **Ein Brim, der nicht aufs Bett passt, wird nicht vorgeschlagen — aber
    # gesagt** (:func:`_brim_where_it_fits`). Gefragt wie dort: kleine
    # Standfläche oder kleine Füße.
    wants_brim = 0.0 < result.first_layer_area < SMALL_FOOTPRINT or (
        result.first_layer_area >= SMALL_FOOTPRINT and _on_small_feet(result)
    )
    room = brim_room(result, profile) if wants_brim else None
    least = BRIM_LEAST_LINES * profile.printer.nozzle_diameter
    if room is not None and room < least:
        findings.append(
            Finding(
                code="settings.brim_no_room",
                severity="warning",
                message=_(
                    "Dieses Teil steht auf wenig Fläche, doch für einen Brim ist auf dem "
                    "Bett dieses Druckers kein Platz."
                ),
                values={"room": format_length(max(room, 0.0)), "least": format_length(least)},
                # Regel 17: Ein größeres Bett hat Platz für den Rand.
                suggestions=(CHOOSE_PRINTER,),
            )
        )
    return findings


def _from_spans(result: SliceResult) -> list[Finding]:
    """Decken, die quer durch die Luft spannen (§22.2).

    Kein Vorschlag, sondern ein Befund: keine Einstellung macht aus einer
    27-mm-Brücke eine tragende Fläche. Was hilft, ist die Geometrie — ein
    Übergang unter 45 Grad statt einer waagerechten Schulter — oder eine
    Stütze. Beides entscheidet der Nutzer, nicht die Regel.

    Gemeldet wird die schlimmste Stelle mit ihrer Höhe, nicht jede einzelne:
    ein Bericht mit dreißig Zeilen derselben Sache wird nicht gelesen.

    **Der Ort ist die freie Fläche, nicht die Achse.** Hier stand
    ``(0, 0, z)``: die Höhe stimmte, der Klick flog aber zum Ursprung der
    Szene, neben das Teil. Jetzt ist es die Mitte der größten freien Fläche
    dieser Schicht über der darunter; ohne sie fliegt er zum Körper.
    """
    spanning = [
        index for index, layer in enumerate(result.layers) if layer.bridge_width > SPAN_INTERESTING
    ]
    if not spanning:
        return []
    # **Ein Rand, der sich selbst trägt, spannt nicht** (:func:`ledges`), wie im
    # Stützbedarf (:func:`_quiet_layers`) — sonst warnte der Bericht, wo der Rat
    # keine Stütze verlangt. Eine Schulter um eine freie Öffnung ist kein Rand
    # (``analysis._spans_an_opening``): Ihre Bahnen laufen quer über die
    # Öffnung, und der Befund bleibt (Gewürzbehälter, Review vom 08.10.2026).
    # Gefragt erst hier, und nur nach den Stücken der spannenden Schichten.
    asked = frozenset(
        (index, number)
        for index in spanning
        for number in range(len(result.layers[index].overhangs))
    )
    resting = _quiet_layers(result, ledges(result, asked))
    spanning = [index for index in spanning if index not in resting]
    if not spanning:
        return []
    worst = max(spanning, key=lambda index: result.layers[index].bridge_width)
    layer = result.layers[worst]
    _log.info("%d layer(s) span more than %.0f mm", len(spanning), SPAN_INTERESTING)
    location = None
    if worst > 0:
        free = _layer_shape(layer).difference(
            _layer_shape(result.layers[worst - 1]).buffer(OVERHANG_MARGIN)
        )
        pieces = [part for part in getattr(free, "geoms", [free]) if part.area > 0.0]
        if pieces:
            anchor = max(pieces, key=lambda part: part.area).representative_point()
            location = (float(anchor.x), float(anchor.y), float(layer.z))
    return [
        Finding(
            code="slice.long_bridge",
            severity="warning",
            message=_(
                "Hier spannt eine Decke frei, ihre Bahnen hängen durch. Ein Übergang unter 45 "
                "Grad oder eine Stütze hilft."
            ),
            values={
                "span_mm": round(layer.bridge_width, 1),
                "z_mm": round(layer.z, 2),
                "layers": len(spanning),
            },
            location=location,
            # Regel 17: Die Stützkarte zeigt die Decke, um die es geht.
            suggestions=(SHOW_SUPPORT_NEED,),
        )
    ]


def apply(settings: PrintSettings, advice: list[SettingAdvice]) -> PrintSettings:
    """Vorschläge übernehmen — alle, oder die ausgewählten.

    Der Aufrufer entscheidet, was in der Liste steht. Angewandt wird nie von
    allein: das hier ist die Umsetzung einer Zustimmung, nicht ihr Ersatz.
    """
    result = settings
    for entry in advice:
        # Als übernommener Vorschlag markiert (Entscheidung A, 27.09.2026):
        # Über das Profil des Herstellers geht nur, was so markiert oder
        # selbst gewählt ist.
        result = settings_table.with_accepted(result, entry.path, entry.value)
    return result
