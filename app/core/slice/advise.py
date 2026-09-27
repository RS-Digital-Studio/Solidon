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
from collections.abc import Sequence
from dataclasses import replace
from typing import Final

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
    OVERHANG_MARGIN,
    ModelSupport,
    _layer_shape,
    island_layers,
    largest_overhang_patch,
    model_support,
    narrow_share,
    narrowest_measured,
    piece_area,
    tapered_layers,
    thinnest_spot,
    total_overhang,
)
from app.core.types import (
    BoundingBox,
    Finding,
    PrintSettings,
    Profile,
    SettingAdvice,
    Severity,
    SliceResult,
)
from app.core.units import EPS_GEOM, is_close
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Unter dieser Standfläche in mm² hält ein Skirt das Teil nicht mehr — ein
#: Brim verdoppelt die Haftfläche eines schlanken Körpers, ohne die Geometrie
#: anzufassen.
SMALL_FOOTPRINT = 400.0

#: Ab diesem Verhältnis von Höhe zu kleinster Grundkante ist ein Teil schlank
#: genug, dass die Düse es beim Anfahren kippen kann.
SLENDER_RATIO = 4.0

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

#: Das Tempo der ersten Schicht über schmalen Stegen, in mm/s. Mit 50 mm/s für
#: die ganze erste Schicht lief Roberts zweiter Druck der Platte sauber; es ist
#: das Wandtempo der ersten Schicht in Elegoos und Bambus Standardprozessen.
NARROW_WEB_SPEED: Final = 50.0

#: Ab diesem Anteil der Schichten mit einem Keil in der Wand lohnt es, die
#: Außenwand zuerst zu legen. Der Becher im Organizer vom 20.09.2026 steht auf
#: neun Zehnteln der Höhe; ein Keil, der nur eine Schulter lang ist, hinterlässt
#: ein paar Rillen, aber kein Band, für das man die Wandreihenfolge ändert.
TAPERED_LAYERS_SHARE = 0.2

#: Überhangfläche in mm², ab der Stützen mehr nützen als kosten. Darunter
#: trägt die Schicht darunter genug, dass ein Absacken in der Wand verschwindet.
OVERHANG_WORTH_SUPPORT = 150.0

#: Und wie viel davon auf **einer** Schicht anfangen muss.
#:
#: Die Summe allein sprach ein Fehlurteil: ein Becher verteilt seine
#: zweihundertvierzig Quadratmillimeter über dreihundertachtunddreißig
#: Schichten, keine davon trägt mehr als knapp vier, und jede Wand fängt das in
#: sich auf — er bekam trotzdem dieselbe Stützenwarnung wie ein Deckel, dessen
#: Lochplatte mit achthundertfünfundvierzig auf einmal über einem Hohlraum
#: beginnt.
#:
#: Hundert ist die Fläche, die eine Düse nicht mehr überspannt: ein Kreis von
#: gut elf Millimetern, also das Doppelte dessen, was die Slicer als längste
#: freie Brücke zulassen.
OVERHANG_LAYER_WORTH_SUPPORT = 100.0

#: Und wie viel je Schicht mindestens anfallen muss, damit die **Summe**
#: überhaupt zählt.
#:
#: Ohne diese Untergrenze wäre der Becher wieder drin: dreihundertachtunddreißig
#: Schichten mit weniger als vier Quadratmillimetern, die jede Wand in sich
#: auffängt. Zehn Quadratmillimeter sind ein Quadrat von gut drei Millimetern —
#: darunter ist ein Überhang eine Kante und kein Feld.
OVERHANG_LAYER_MINIMUM = 10.0

#: So viele Schichten mit Inseln machen aus Gitterstützen Baumstützen: viele
#: verteilte Ansatzpunkte sind genau der Fall, für den Bäume gebaut wurden.
TREE_FROM_ISLANDS = 8

#: Kleinste Schichtfläche in mm², unter der eine Schicht so schnell durch ist,
#: dass die vorige noch weich liegt.
THIN_LAYER_AREA = 120.0

#: Beschleunigung in mm/s² für eine Außenwand, deren Maß zählt. Der Wert ist
#: nicht die Grenze der Maschine, sondern die, ab der die Kontur ausschwingt —
#: und eine Passung ist auf Zehntelmillimeter gerechnet.
CAREFUL_ACCELERATION = 2000.0

#: Ab wie vielen Linienbreiten eine Wand auf ganze Bahnen aufgeht. Darunter
#: bleibt beim klassischen Generator eine Lücke, die mit Lückenfüllung
#: geschlossen wird — bei einem Federarm ist genau das der Bruch.
LINES_FOR_CLASSIC = 3.0

#: Mindestschichtzeit in Sekunden für solche Spitzen. Weniger, und der Turm
#: kippt in sich zusammen; mehr, und die Düse kokelt auf der Stelle.
THIN_LAYER_SECONDS = 15.0

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
#: ``print_settings_dialog.FIELDS``).
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


def advise(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult | None = None,
    *,
    bounds: BoundingBox | None = None,
    fit_kinds: Sequence[str] = (),
    connectors: Sequence[float] = (),
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
        advice += _from_geometry(settings, profile, result, bounds)
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
    advice = _merged(settings, advice + _from_flow(apply(settings, advice)))

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


def _merged(settings: PrintSettings, advice: list[SettingAdvice]) -> list[SettingAdvice]:
    """Ein Vorschlag je Einstellung, und ``was`` ist immer der Ausgangswert.

    Zwei Regeln können denselben Wert meinen — bei weichem Filament senkt die
    Materialregel das Tempo, und der Volumenstrom will es womöglich noch
    weiter. Zwei Zeilen für dieselbe Einstellung wären keine zwei Vorschläge,
    sondern eine Liste, die sich selbst widerspricht: die spätere Regel hat den
    Stand der früheren gesehen, also gewinnt sie.
    """
    by_path: dict[str, SettingAdvice] = {}
    for entry in advice:
        by_path[entry.path] = replace(entry, was=settings_table.read_path(settings, entry.path))
    # Vorschläge, die nach dem Zusammenführen nichts mehr ändern, fallen weg.
    return [entry for entry in by_path.values() if _differs(entry.value, entry.was)]


def combine(
    settings: PrintSettings,
    groups: Sequence[tuple[PrintSettings, Sequence[SettingAdvice]]],
) -> list[SettingAdvice]:
    """Vereint Anforderungen mehrerer Körper an gemeinsame Einstellungen.

    Jede Gruppe enthält ihren effektiven Ausgangsstand und ihre Vorschläge.
    Auch ein Körper ohne Änderungsvorschlag behält seine Anforderungen: Ein
    Würfel kann die schon eingeschalteten Stützen seines Nachbarn nicht
    abschalten. Filamentabhängige Werte werden nur innerhalb desselben
    Materialslots zusammengeführt; verschiedene Spulen behalten eigene Werte.
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
        value = _combined_value(path, values)
        was = settings_table.read_path(settings, path)
        if not _differs(value, was):
            continue
        reason = next((entry for entry in entries if not _differs(entry.value, value)), entries[0])
        merged.append(replace(reason, value=value, was=was))
    return merged


def _combined_value(path: str, values: Sequence[object]) -> object:
    """Nimmt je Einstellungsart die Anforderung, die alle Körper einschließt."""
    ranks = {
        # ``auto`` steht über „aus" und unter jeder ausdrücklichen Art: Wo ein
        # Körper Bäume verlangt, schließt das den ein, der nur Stützen will.
        "support.style": ("none", "auto", "grid", "tree"),
        "support.placement": ("build_plate", "everywhere"),
        # Der Auto-Brim des Slicers kann einen Brim legen, ein Skirt nie.
        "adhesion.kind": ("none", "skirt", "auto", "brim", "raft"),
        "shell.wall_generator": ("classic", "arachne"),
    }
    if path in ranks:
        return max(values, key=lambda value: ranks[path].index(str(value)))
    if all(isinstance(value, bool) for value in values):
        return any(values)
    numbers = [value for value in values if isinstance(value, int | float)]
    if len(numbers) == len(values):
        if path.startswith(("speed.", "layers.")) or path == "cooling.fan_speed":
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
FLOW_LIMIT_REASON: Final = _(
    "Dieses Tempo hält den eingestellten maximalen Volumenstrom ein. "
    "Mehr Durchsatz braucht einen gemessenen Wert für dieses Filament "
    "und Hotend; eine höhere Temperatur allein belegt ihn nicht."
)


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
                reason=_(
                    "Dieser Drucker fährt leer schneller. Je länger die Leerfahrt dauert, "
                    "desto mehr läuft die Düse aus und zieht Fäden."
                ),
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
                reason=_(
                    "Bis zu diesem Winkel druckt dieser Drucker Überhänge ohne Stütze. "
                    "Ein kleinerer Winkel stützt auch Schrägen, die sich selbst tragen."
                )
                if settings.support.threshold_angle < limit
                else _(
                    "Ab diesem Winkel braucht dieser Drucker Stützen. Ein größerer Winkel "
                    "lässt Überhänge frei hängen, die absacken."
                ),
            )
        )

    wanted = settings_table.MAX_LAYER_RATIO * printer.nozzle_diameter
    if settings.layers.layer_height > wanted:
        advice.append(
            _advice(
                settings,
                path="layers.layer_height",
                value=round(wanted, 3),
                reason=_(
                    "Eine Schicht über drei Vierteln des Düsendurchmessers haftet nicht "
                    "sicher auf der darunterliegenden."
                ),
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
                reason=_(
                    "Auch die erste Schicht bleibt unter drei Vierteln des "
                    "Düsendurchmessers — höher legt die Düse keine Bahn, die auf dem "
                    "Bett trägt."
                ),
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
            _("Auch die erste Schicht bleibt in dem, was dieser Drucker heizen kann."),
        ),
        (
            "temperature.bed",
            settings.temperature.bed,
            printer.bed_temperature_max,
            _("Wärmer wird dieses Bett nicht — gedruckt würde mit seinem Höchstwert."),
        ),
        (
            "temperature.bed_first_layer",
            settings.temperature.bed_first_layer,
            printer.bed_temperature_max,
            _("Auch für die erste Schicht ist beim Höchstwert dieses Bettes Schluss."),
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
                    reason=_(
                        "Schmaler legt diese Düse keine Bahn — enger gequetscht reißt die "
                        "Spur ab, statt dünner zu werden. Für feinere Bahnen gehört eine "
                        "kleinere Düse ins Druckerprofil."
                    ),
                    severity="warning",
                )
            )

    if settings.temperature.nozzle >= printer.nozzle_temperature_max:
        advice.append(
            _advice(
                settings,
                path="temperature.nozzle",
                value=printer.nozzle_temperature_max,
                reason=_(
                    "Das Material will an die Grenze dessen, was dieser Drucker heizen "
                    "kann — für einen Dauerlauf ist das knapp."
                ),
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


#: Haftungsarten, die ein Teil auf wenig Fläche nicht sicher halten: der Skirt
#: berührt es nicht, und der Auto-Brim des Slicers fragt seine eigene Regel,
#: nicht die Füße und nicht die Höhe, die Solidon misst.
UNANCHORED: Final = frozenset({"skirt", "auto"})


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
                    reason=_(
                        "Dieses Material zieht sich beim Abkühlen zusammen, und der "
                        "Bauraum ist offen. Ein Brim hält die Ecken unten."
                    ),
                    severity="warning",
                )
            )
        if settings.cooling.fan_speed > 0.3:
            advice.append(
                _advice(
                    settings,
                    path="cooling.fan_speed",
                    value=0.2,
                    reason=_("Zugluft auf diesem Material trennt die Schichten voneinander."),
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
                reason=_(
                    "Dieser Drucker hat einen geschlossenen Bauraum, und dieses Material "
                    "ist der Grund, warum das hilft."
                ),
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
                        reason=_(
                            "Weiches Filament staucht im Antrieb, statt zu fördern. "
                            "Langsam ist hier keine Vorsicht, sondern Voraussetzung."
                        ),
                    )
                )
    return advice


def _from_geometry(
    settings: PrintSettings,
    profile: Profile,
    result: SliceResult,
    bounds: BoundingBox | None,
) -> list[SettingAdvice]:
    """Der eigentliche Gewinn: das Teil bestimmt seine Einstellungen mit."""
    advice: list[SettingAdvice] = []

    islands = island_layers(result)
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
    model = (
        model_support(result)
        if _may_need_support(
            result, islands, total_overhang(result), largest_overhang_patch(result)
        )
        else ModelSupport()
    )
    overhang = total_overhang(result, without=model.channels)
    patch = largest_overhang_patch(result, without=model.channels)
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
    needs_support = _may_need_support(result, islands, overhang, patch, model.channel_layers)

    if needs_support and settings.support.style == "none":
        # **Stützen an, die Art des Slicers** — außer das Modell verlangt eine
        # (Entscheidung J, 27.09.2026). Hier stand ``grid``, und Elegoo wie
        # Bambu, deren Standardprozess Bäume stützt, bekamen Gitter.
        style = "tree" if len(islands) >= TREE_FROM_ISLANDS else "auto"
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
    elif not needs_support and settings.support.style != "none":
        advice.append(
            _advice(
                settings,
                path="support.style",
                value="none",
                reason=_(
                    "Nichts an diesem Teil schwebt. Stützen kosten hier nur Material "
                    "und hinterlassen Spuren."
                ),
            )
        )

    # **„Keine Insel“ heißt nicht „alles erreicht das Bett“.** Ein Tisch —
    # Bodenplatte 40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte
    # 40 auf 40 — hat keine Insel und 1 492 mm² Überhang auf einer Schicht,
    # und jede Stütze darunter endet auf der Bodenplatte. Der Vorschlag
    # ``build_plate`` ließ die Tischplatte absacken. Gefragt wird deshalb die
    # Geometrie und nicht ein Nebenbefund (:func:`model_support`).
    #
    # **Und „auf dem Modell“ heißt außen und so viel, dass es selbst Stütze
    # bräuchte.** Eine Säule im Kanal zählt nicht (oben), und was außen auf
    # dem Modell aufsetzt, misst sich an denselben zwei Wegen wie der
    # Stützbedarf selbst: An der Waschschüssel blieb neben der Kanaldecke ein
    # Rest von 11 mm² an der Düsenmündung, und der allein verlangte, dass die
    # Stützen des ganzen Teils überall ansetzen — wieder im Kanal.
    #
    # **Eine Insel auf dem Modell verlangt es immer**, gleich wie klein: Sie
    # hat nichts unter sich. Eine Insel über dem Bett dagegen erreicht es —
    # deshalb steht hier nicht mehr pauschal „keine Inseln": Bis zum
    # 26.09.2026 bekam jedes Teil mit einer Insel „überall", auch wenn alle
    # Säulen das Bett erreichten oder im Kanal endeten, und der Kanal füllte
    # sich wieder.
    on_model = needs_support and (
        model.island_on_model
        or model.open_patch > OVERHANG_LAYER_WORTH_SUPPORT
        or (model.open_area > OVERHANG_WORTH_SUPPORT and model.open_patch > OVERHANG_LAYER_MINIMUM)
    )
    if needs_support and on_model and settings.support.placement == "build_plate":
        advice.append(
            _advice(
                settings,
                path="support.placement",
                value="everywhere",
                reason=_(
                    "Unter diesen Überhängen liegt bereits Modellmaterial. Stützen "
                    "müssen auch auf dem Modell beginnen dürfen, um sie zu erreichen."
                ),
                severity="warning",
            )
        )
    elif needs_support and settings.support.placement == "everywhere" and not on_model:
        advice.append(
            _advice(
                settings,
                path="support.placement",
                value="build_plate",
                reason=_(
                    "Die übrigen Decken liegen in schmalen Kanälen und tragen sich "
                    "selbst. Stützen darin kämen nicht mehr heraus."
                )
                if model.channels
                else _(
                    "Alle Überhänge erreichen das Bett. Stützen auf dem Modell "
                    "hinterlassen Narben, die keine sein müssen."
                ),
            )
        )

    # **Und die Kanäle frei halten** (26.09.2026). „Nur vom Bett" reicht dafür
    # nicht in jedem Slicer: Orcas organische Bäume wuchsen trotzdem in den
    # Wasserkanal der Waschschüssel und führten ihre Stämme durch die Wand, und
    # wo „überall" nötig bleibt — eine Insel auf dem Modell —, füllt jeder
    # Slicer den Kanal. Die Sperre in der Übergabe hält beides heraus.
    if needs_support and model.channels and not settings.support.block_channels:
        advice.append(
            _advice(
                settings,
                path="support.block_channels",
                value=True,
                reason=_(
                    "Dieses Teil hat schmale Kanäle. Eine Sperre hält die Stützen dort "
                    "fern — sie kämen nicht mehr heraus, und die Decken tragen sich selbst."
                ),
            )
        )

    # **Auch über dem Auto-Brim des Slicers** (Entscheidung J): Er entscheidet
    # nach seiner Regel, Solidon nach der Geometrie.
    unanchored = settings.adhesion.kind in UNANCHORED
    if 0.0 < result.first_layer_area < SMALL_FOOTPRINT and unanchored:
        advice.append(
            _advice(
                settings,
                path="adhesion.kind",
                value="brim",
                reason=_("Die Standfläche ist klein — ein Brim verhindert, dass das Teil abreißt."),
                severity="warning",
            )
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
        advice.append(
            _advice(
                settings,
                path="adhesion.kind",
                value="brim",
                reason=_(
                    "Das Teil steht auf kleinen Füßen, und keiner hält allein. "
                    "Ein Brim gibt jedem Fuß Halt."
                ),
                severity="warning",
            )
        )

    if bounds is not None and _slender(bounds) and unanchored:
        advice.append(
            _advice(
                settings,
                path="adhesion.kind",
                value="brim",
                reason=_("Das Teil ist hoch und schmal. Die Düse kann es beim Anfahren kippen."),
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
    if (
        result.layers
        and settings.speed.first_layer > NARROW_WEB_SPEED + EPS_GEOM
        and narrow_share(
            result.layers[0], NARROW_WEB_LINES * settings.layers.first_layer_line_width
        )
        >= NARROW_WEB_SHARE
    ):
        advice.append(
            _advice(
                settings,
                path="speed.first_layer",
                value=NARROW_WEB_SPEED,
                reason=_(
                    "Die erste Schicht hat schmale Stege. Langsamer gelegt, haften ihre "
                    "kurzen Bahnen besser."
                ),
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
                reason=_(
                    "Die schmalste Stelle geht auf keine ganze Zahl von Bahnen auf. "
                    "Mit fester Linienbreite bleibt dort eine Lücke, die nur "
                    "Lückenfüllung schließt — und die trägt nicht."
                ),
                severity="warning",
            )
        )

    if overhang > 0.0 and settings.speed.bridge > settings.speed.outer_wall:
        advice.append(
            _advice(
                settings,
                path="speed.bridge",
                value=settings.speed.outer_wall,
                reason=_(
                    "Über einer Lücke trägt nichts von unten. Schneller als die "
                    "Außenwand gefahren hängt die erste Bahn durch."
                ),
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
                reason=_(
                    "Mit dieser Linienbreite passen zwei Bahnen in die dünnste "
                    "Stelle. Bei breiteren Linien kann der Slicer dort nur eine "
                    "variable Bahn oder Lückenfüllung erzeugen."
                ),
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
                reason=_(
                    "Die Wandstärke läuft an der Außenkontur stetig über mehrere "
                    "Bahnen. Mit variabler Bahnbreite wechselt dort die Wandzahl, "
                    "und zuerst gelegte Innenwände zeichnen das durch die Außenwand "
                    "ab. Zuerst gelegt liegt die Außenwand auf glattem Grund."
                ),
                severity="warning",
            )
        )

    if _has_thin_layers(result) and settings.cooling.minimum_layer_time < THIN_LAYER_SECONDS:
        advice.append(
            _advice(
                settings,
                path="cooling.minimum_layer_time",
                value=THIN_LAYER_SECONDS,
                reason=_(
                    "Weiter oben liegen Schichten mit so wenig Fläche, dass sie in "
                    "Sekunden fertig sind. Ohne Mindestzeit je Schicht legt die Düse "
                    "auf noch weiches Material."
                ),
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
                reason=_(
                    "Eine bündige Passung legt zwei Flächen aufeinander. Gebügelt "
                    "gleitet die obere, statt auf den Bahnkanten zu sitzen."
                ),
            )
        )
    if not settings.shell.precise_outer_wall:
        advice.append(
            _advice(
                settings,
                path="shell.precise_outer_wall",
                value=True,
                reason=_(
                    "Das Projekt hat Passungen. Die Außenwand auf das Sollmaß zu "
                    "rechnen statt auf die Bahnmitte ist genau dafür da."
                ),
            )
        )
    if settings.speed.outer_wall_acceleration > CAREFUL_ACCELERATION:
        advice.append(
            _advice(
                settings,
                path="speed.outer_wall_acceleration",
                value=CAREFUL_ACCELERATION,
                reason=_(
                    "Hohe Beschleunigung schwingt die Kontur aus. Das kostet die "
                    "Zehntelmillimeter, auf die eine Passung gerechnet ist."
                ),
            )
        )
    if settings.speed.outer_wall > careful:
        advice.append(
            _advice(
                settings,
                path="speed.outer_wall",
                value=careful,
                reason=_(
                    "Das Projekt hat Passungen. Eine langsam gefahrene Außenwand hält "
                    "das Maß, auf das sie gerechnet sind."
                ),
            )
        )
    if not settings.shell.outer_wall_first:
        advice.append(
            _advice(
                settings,
                path="shell.outer_wall_first",
                value=True,
                reason=_(
                    "Die Außenwand zuerst zu legen gibt die genauere Kontur — was bei "
                    "einer Passung der Punkt ist."
                ),
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
            reason=_(
                "Der Verbinder ist zu dick, um ihn mit Wänden zu schließen — er "
                "trägt dann über das Füllmuster in seiner Mitte. So viel Füllung "
                "ergibt rechnerisch denselben Materialanteil wie ein Ring aus Wänden; "
                "sie gilt für das ganze Teil und kostet dort Material und Zeit. "
                "Wie gut das Muster die Mitte trifft, hängt an seiner Art: ein "
                "Gyroid liegt in alle Richtungen gleich, ein Gitter lässt dort "
                "eher Luft."
            ),
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
            reason=_(
                "Der Verbinder besteht bei den eingestellten Wänden im Kern aus "
                "Füllmuster. So viele Wände machen den Materialring mindestens "
                "so breit wie den verbleibenden Kern — sie gelten für das ganze "
                "Teil und nicht nur für den Zapfen."
            ),
        )
    ]


def for_part(settings: PrintSettings, bounds: BoundingBox, footprint: float) -> list[SettingAdvice]:
    """Was dieses eine Teil anders braucht als die Platte (§29).

    Die Druckbetthaftung ist die eine Einstellung, die je Teil zählt statt je
    Auftrag: sie hängt daran, worauf ein Körper steht, und das ist bei jedem
    ein anderer Wert. Beim Gewürzset stehen zwölf Behälter auf Ø 40 und drei
    Streuscheiben auf je drei 1,1-mm-Federarmen — dieselbe Platte, und der
    Brim gehört nur unter die Scheiben. Ohne diese Unterscheidung gäbe es nur
    „alle bekommen einen" oder „keiner".

    Temperatur, Kühlung und Stützen bleiben plattenweit: sie hängen am Material
    oder an der Maschine, und je Teil verstellt wären sie ein Widerspruch, den
    der Slicer auflösen müsste.
    """
    if settings.adhesion.kind not in UNANCHORED:
        return []
    if 0.0 < footprint < SMALL_FOOTPRINT:
        reason = _("Dieses Teil steht auf zu wenig Fläche, um ohne Brim zu halten.")
    elif _slender(bounds):
        reason = _("Dieses Teil ist hoch und schmal. Die Düse kann es beim Anfahren kippen.")
    else:
        return []
    return [
        _advice(
            settings,
            path="adhesion.kind",
            value="brim",
            reason=reason,
            severity="warning",
        )
    ]


def _may_need_support(
    result: SliceResult,
    islands: tuple[float, ...],
    overhang: float,
    patch: float,
    channel_layers: frozenset[int] = frozenset(),
) -> bool:
    """Die zwei Wege aus :func:`_from_geometry` zum Stützbedarf, dazu Inseln
    und lange Brücken außerhalb der Kanalschichten."""
    return (
        bool(islands)
        or patch > OVERHANG_LAYER_WORTH_SUPPORT
        or (overhang > OVERHANG_WORTH_SUPPORT and patch > OVERHANG_LAYER_MINIMUM)
        or any(
            layer.bridge_width > SPAN_INTERESTING
            for index, layer in enumerate(result.layers)
            if index not in channel_layers
        )
    )


def _on_small_feet(result: SliceResult) -> bool:
    """Steht der Körper auf mehreren Inseln, von denen keine für sich die
    Standfläche eines Teils hat (:data:`SMALL_FOOTPRINT`)?"""
    if not result.layers:
        return False
    feet = [piece_area(contour) for contour in result.layers[0].contours]
    return len(feet) >= 2 and max(feet) < SMALL_FOOTPRINT


def _slender(bounds: BoundingBox) -> bool:
    size = bounds.size
    footprint = min(size[0], size[1])
    if footprint <= 0.0:
        return False
    return size[2] / footprint >= SLENDER_RATIO


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


def warnings_for(
    settings: PrintSettings, profile: Profile, result: SliceResult | None = None
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

    if not profile.material.calibrated:
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
                    "Die Toleranzen dieses Materials sind Startwerte. Mit dem "
                    "Toleranz-Testkörper stimmen sie für Ihren Drucker."
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
                    "Dieses Material will ein wärmeres Bett, als dieser Drucker heizen "
                    "kann — gedruckt wird mit dem Höchstwert der Maschine. Die erste "
                    "Schicht braucht dann mehr Haftung: Brim oder Raft wählen, sonst "
                    "löst sich das Teil beim Abkühlen."
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
                    "Dieses Material will einen geheizten Bauraum, und dieser Drucker "
                    "hat keinen — die Bauraumtemperatur bleibt aus. Das Teil vor Zugluft "
                    "abschirmen, oder einen Drucker mit geschlossenem Bauraum wählen."
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
                    "Die dünnste Stelle ist schmaler als die hier angesetzte "
                    "Mindestbahnbreite. Die Materialbahnen im Slicer prüfen; "
                    "fehlen sie dort, eine kleinere Düse wählen oder die Stelle "
                    "verbreitern."
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
    return findings


#: Ab welcher freien Spannweite eine Decke gemeldet wird, in Millimetern.
#:
#: Zehn Millimeter überbrückt jeder Drucker, zwanzig hängen bei PETG sichtbar
#: durch. Fünfzehn ist die Stelle dazwischen, an der ein Hinweis noch etwas
#: ändern kann — gemessen wurde er an einem Satz Gewürzbehälter, deren
#: Ringschulter der Slicer mit 27 mm freien Bahnen überspannte, und an dessen
#: Deckeln mit 35 mm.
SPAN_INTERESTING: Final = 15.0


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
                "Hier spannt eine Decke frei durch die Luft. Der Slicer legt dafür gerade "
                "Bahnen quer über die Öffnung; sie hängen durch und bleiben als Fäden "
                "stehen. Ein Übergang unter 45 Grad statt einer waagerechten Schulter "
                "vermeidet das — sonst hilft nur eine Stütze."
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
