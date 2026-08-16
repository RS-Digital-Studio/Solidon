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

from app.core.knowledge import print_settings as settings_table
from app.core.log import get_logger
from app.core.slice.analysis import island_layers, narrowest, total_overhang, worst_overhang
from app.core.types import (
    BoundingBox,
    Finding,
    PrintSettings,
    Profile,
    SettingAdvice,
    SliceResult,
)
from app.i18n import _

_log = get_logger(__name__)

#: Unter dieser Standfläche in mm² hält ein Skirt das Teil nicht mehr — ein
#: Brim verdoppelt die Haftfläche eines schlanken Körpers, ohne die Geometrie
#: anzufassen.
SMALL_FOOTPRINT = 400.0

#: Ab diesem Verhältnis von Höhe zu kleinster Grundkante ist ein Teil schlank
#: genug, dass die Düse es beim Anfahren kippen kann.
SLENDER_RATIO = 4.0

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

#: Um so viel Grad wird die Düse angehoben, wenn der Volumenstrom es verlangt.
#: Zehn Grad sind ein spürbarer Schritt und bleiben im Rahmen dessen, was ein
#: Filament aushält — die große Änderung gehört ins Materialprofil, nicht in
#: einen Vorschlag.
TEMPERATURE_STEP: Final = 10

#: Um so viel Grad wird das Bett angehoben, wo die Haftung es verlangt.
BED_STEP: Final = 5

#: Kammertemperatur, die ein schrumpfendes Material auf einem geschlossenen
#: Gerät braucht. Warm genug, dass die unteren Schichten nicht erstarren,
#: bevor die oberen liegen — und weit unter dem, was der Antrieb aushält.
CHAMBER_FOR_WARPING: Final = 50


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
    """
    advice: list[SettingAdvice] = []
    advice += _from_machine(settings, profile)
    advice += _from_material(settings, profile)
    if result is not None:
        advice += _from_geometry(settings, profile, result, bounds)
    if fit_kinds:
        advice += _from_fits(settings, fit_kinds)
    advice += _from_connectors(settings, connectors)

    # Der Volumenstrom hängt an Schichthöhe, Bahnbreite und Tempo — und an
    # genau diesen Werten haben die Vorschläge oben womöglich gedreht. Er wird
    # deshalb gegen den Stand *nach* ihnen gerechnet, sonst empfiehlt er eine
    # heißere Düse für ein Tempo, das nebenan schon gesenkt wurde.
    advice = _merged(settings, advice + _from_flow(apply(settings, advice), profile))

    _log.info("advising %d settings", len(advice))
    return advice


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
    return [entry for entry in by_path.values() if entry.value != entry.was]


def flow_of(settings: PrintSettings, speed: float) -> float:
    """Wie viel Material bei diesem Tempo je Sekunde durch die Düse muss, in
    mm³/s.

    Schichthöhe mal Bahnbreite mal Geschwindigkeit — die Rechnung, die die drei
    Einstellungen verbindet, an denen sonst einzeln gedreht wird. Sie ist der
    Grund, warum eine Schichthöhe, die gestern ging, heute mit einer schnelleren
    Stufe Löcher in die Wand zieht.
    """
    return settings.layers.layer_height * settings.layers.line_width * speed


def _from_flow(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was nicht durch die Düse passt (§29).

    Das Hotend ist die eigentliche Grenze, und sie wird selten als solche
    gezeigt: der Antrieb fördert weiter, das Material wird nur nicht mehr
    warm genug. Die Bahn wird dann dünner als gerechnet, die Wand porös, und
    an den Einstellungen sieht man nichts.

    Zwei Wege heraus, und beide werden genannt: heißer, solange die Maschine
    das kann, sonst langsamer. Welcher richtig ist, weiß Solidon nicht —
    darum entscheidet es das nicht.
    """
    advice: list[SettingAdvice] = []
    limit = settings.filament.max_flow
    if limit <= 0.0:
        return advice

    fastest = max(settings.speed.infill, settings.speed.inner_wall)
    needed = flow_of(settings, fastest)
    if needed <= limit:
        return advice

    headroom = profile.printer.nozzle_temperature_max - settings.temperature.nozzle
    if headroom >= TEMPERATURE_STEP:
        advice.append(
            SettingAdvice(
                path="temperature.nozzle",
                value=settings.temperature.nozzle + TEMPERATURE_STEP,
                was=settings.temperature.nozzle,
                reason=_(
                    "Bei diesem Tempo müssen mehr Kubikmillimeter je Sekunde durch die "
                    "Düse, als das Material bei dieser Temperatur flüssig wird."
                ),
                severity="warning",
            )
        )
    else:
        # Ohne Luft nach oben bleibt nur der andere Weg — und ein Vorschlag,
        # der die Maschinengrenze überschreitet, wäre keiner.
        advice.append(
            SettingAdvice(
                path="speed.infill",
                value=round(limit / (settings.layers.layer_height * settings.layers.line_width)),
                was=settings.speed.infill,
                reason=_(
                    "Schneller bekommt dieses Hotend das Material nicht mehr aufgeschmolzen, "
                    "und heißer kann der Drucker nicht."
                ),
                severity="warning",
            )
        )
    return advice


def _from_machine(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was die Maschine nicht kann, muss vor dem Druck gesagt werden."""
    advice: list[SettingAdvice] = []
    printer = profile.printer

    wanted = settings_table.MAX_LAYER_RATIO * printer.nozzle_diameter
    if settings.layers.layer_height > wanted:
        advice.append(
            SettingAdvice(
                path="layers.layer_height",
                value=round(wanted, 3),
                was=settings.layers.layer_height,
                reason=_(
                    "Eine Schicht über drei Vierteln des Düsendurchmessers haftet nicht "
                    "sicher auf der darunterliegenden."
                ),
                severity="warning",
            )
        )

    if settings.temperature.nozzle >= printer.nozzle_temperature_max:
        advice.append(
            SettingAdvice(
                path="temperature.nozzle",
                value=printer.nozzle_temperature_max,
                was=settings.temperature.nozzle,
                reason=_(
                    "Das Material will an die Grenze dessen, was dieser Drucker heizen "
                    "kann — für einen Dauerlauf ist das knapp."
                ),
                severity="warning",
            )
        )

    if settings.temperature.chamber > 0 and not printer.enclosed:
        advice.append(
            SettingAdvice(
                path="temperature.chamber",
                value=0,
                was=settings.temperature.chamber,
                reason=_("Dieser Drucker hat keinen geschlossenen Bauraum."),
            )
        )
    return advice


def _from_material(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was am Filament hängt und die Stufe nicht wissen kann."""
    advice: list[SettingAdvice] = []
    material = profile.material.id

    if material in WARPING_MATERIALS and not profile.printer.enclosed:
        if settings.adhesion.kind != "brim":
            advice.append(
                SettingAdvice(
                    path="adhesion.kind",
                    value="brim",
                    was=settings.adhesion.kind,
                    reason=_(
                        "Dieses Material zieht sich beim Abkühlen zusammen, und der "
                        "Bauraum ist offen. Ein Brim hält die Ecken unten."
                    ),
                    severity="warning",
                )
            )
        if settings.cooling.fan_speed > 0.3:
            advice.append(
                SettingAdvice(
                    path="cooling.fan_speed",
                    value=0.2,
                    was=settings.cooling.fan_speed,
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
            SettingAdvice(
                path="temperature.chamber",
                value=CHAMBER_FOR_WARPING,
                was=settings.temperature.chamber,
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
    overhang = total_overhang(result)
    worst = worst_overhang(result)
    # Die Summe allein reicht nicht, und der Unterschied entscheidet: ein
    # Becher sammelte über dreihundertachtunddreißig Schichten
    # zweihundertvierzig Quadratmillimeter und bekam dieselbe Warnung wie ein
    # Deckel, dessen Lochplatte mit achthundertfünfundvierzig auf einmal
    # anfängt. Beim Becher trägt jede Wand ihren Anteil selbst; beim Deckel
    # hängt eine ganze Fläche über einem Hohlraum. Gefragt ist deshalb beides
    # — wie viel insgesamt, und wie viel davon auf einmal.
    needs_support = bool(islands) or (
        overhang > OVERHANG_WORTH_SUPPORT and worst > OVERHANG_LAYER_WORTH_SUPPORT
    )

    if needs_support and settings.support.style == "none":
        style = "tree" if len(islands) >= TREE_FROM_ISLANDS else "grid"
        advice.append(
            SettingAdvice(
                path="support.style",
                value=style,
                was=settings.support.style,
                reason=_("Ohne Stützen druckt dieses Teil in die Luft.")
                if islands
                else _("Die Überhänge sind zu groß, um sich selbst zu tragen."),
                severity="warning",
            )
        )
    elif not needs_support and settings.support.style != "none":
        advice.append(
            SettingAdvice(
                path="support.style",
                value="none",
                was=settings.support.style,
                reason=_(
                    "Nichts an diesem Teil schwebt. Stützen kosten hier nur Material "
                    "und hinterlassen Spuren."
                ),
            )
        )

    if needs_support and not islands and settings.support.placement == "everywhere":
        advice.append(
            SettingAdvice(
                path="support.placement",
                value="build_plate",
                was=settings.support.placement,
                reason=_(
                    "Alle Überhänge erreichen die Platte. Stützen auf dem Modell "
                    "hinterlassen Narben, die keine sein müssen."
                ),
            )
        )

    if 0.0 < result.first_layer_area < SMALL_FOOTPRINT and settings.adhesion.kind == "skirt":
        advice.append(
            SettingAdvice(
                path="adhesion.kind",
                value="brim",
                was=settings.adhesion.kind,
                reason=_("Die Standfläche ist klein — ein Brim verhindert, dass das Teil abreißt."),
                severity="warning",
            )
        )

    if (
        0.0 < result.first_layer_area < SMALL_FOOTPRINT
        and profile.material.id in WARPING_MATERIALS
        and settings.temperature.bed_first_layer < profile.printer.bed_temperature_max
    ):
        # Wenig Fläche und ein Material, das zieht: das Bett ist der einzige
        # Halt, den das Teil in der ersten Minute hat.
        advice.append(
            SettingAdvice(
                path="temperature.bed_first_layer",
                value=min(
                    settings.temperature.bed_first_layer + BED_STEP,
                    profile.printer.bed_temperature_max,
                ),
                was=settings.temperature.bed_first_layer,
                reason=_(
                    "Kleine Standfläche und ein Material, das sich zusammenzieht — ein "
                    "wärmeres Bett hält die erste Schicht unten."
                ),
            )
        )

    if bounds is not None and _slender(bounds) and settings.adhesion.kind == "skirt":
        advice.append(
            SettingAdvice(
                path="adhesion.kind",
                value="brim",
                was=settings.adhesion.kind,
                reason=_("Das Teil ist hoch und schmal. Die Düse kann es beim Anfahren kippen."),
                severity="warning",
            )
        )

    thin = narrowest(result)
    if (
        0.0 < thin < LINES_FOR_CLASSIC * settings.layers.line_width
        and settings.shell.wall_generator == "classic"
    ):
        advice.append(
            SettingAdvice(
                path="shell.wall_generator",
                value="arachne",
                was=settings.shell.wall_generator,
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
            SettingAdvice(
                path="speed.bridge",
                value=settings.speed.outer_wall,
                was=settings.speed.bridge,
                reason=_(
                    "Über einer Lücke trägt nichts von unten. Schneller als die "
                    "Außenwand gefahren hängt die erste Bahn durch."
                ),
            )
        )

    minimum = 2.0 * settings.layers.line_width
    if 0.0 < thin < minimum:
        advice.append(
            SettingAdvice(
                path="layers.line_width",
                value=round(max(thin / 2.0, profile.printer.nozzle_diameter * 0.85), 3),
                was=settings.layers.line_width,
                reason=_(
                    "Die dünnste Stelle ist schmaler als zwei Linien breit. Mit der "
                    "jetzigen Breite fällt sie im Druck weg."
                ),
                severity="warning",
            )
        )

    if _has_thin_layers(result) and settings.cooling.minimum_layer_time < THIN_LAYER_SECONDS:
        advice.append(
            SettingAdvice(
                path="cooling.minimum_layer_time",
                value=THIN_LAYER_SECONDS,
                was=settings.cooling.minimum_layer_time,
                reason=_(
                    "Das Teil läuft nach oben spitz zu. Ohne Mindestzeit je Schicht "
                    "legt die Düse auf noch weiches Material."
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
            SettingAdvice(
                path="shell.ironing",
                value=True,
                was=settings.shell.ironing,
                reason=_(
                    "Eine bündige Passung legt zwei Flächen aufeinander. Gebügelt "
                    "gleitet die obere, statt auf den Bahnkanten zu sitzen."
                ),
            )
        )
    if not settings.shell.precise_outer_wall:
        advice.append(
            SettingAdvice(
                path="shell.precise_outer_wall",
                value=True,
                was=settings.shell.precise_outer_wall,
                reason=_(
                    "Das Projekt hat Passungen. Die Außenwand auf das Sollmaß zu "
                    "rechnen statt auf die Bahnmitte ist genau dafür da."
                ),
            )
        )
    if settings.speed.outer_wall_acceleration > CAREFUL_ACCELERATION:
        advice.append(
            SettingAdvice(
                path="speed.outer_wall_acceleration",
                value=CAREFUL_ACCELERATION,
                was=settings.speed.outer_wall_acceleration,
                reason=_(
                    "Hohe Beschleunigung schwingt die Kontur aus. Das kostet die "
                    "Zehntelmillimeter, auf die eine Passung gerechnet ist."
                ),
            )
        )
    if settings.speed.outer_wall > careful:
        advice.append(
            SettingAdvice(
                path="speed.outer_wall",
                value=careful,
                was=settings.speed.outer_wall,
                reason=_(
                    "Das Projekt hat Passungen. Eine langsam gefahrene Außenwand hält "
                    "das Maß, auf das sie gerechnet sind."
                ),
            )
        )
    if not settings.shell.outer_wall_first:
        advice.append(
            SettingAdvice(
                path="shell.outer_wall_first",
                value=True,
                was=settings.shell.outer_wall_first,
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
    if not diameters:
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
    # aufgeloest: 2*w*lw >= d - 2*w*lw, also w >= d / (4*lw).
    needed = math.ceil(thickest / (4.0 * width))
    return [
        SettingAdvice(
            path="shell.wall_count",
            value=needed,
            was=settings.shell.wall_count,
            reason=_(
                "Der Verbinder besteht bei den eingestellten Wänden im Kern aus "
                "Füllmuster und trägt nur mit seiner Außenhaut. So viele Wände "
                "treffen sich in seiner Mitte."
            ),
        )
    ]


def for_part(settings: PrintSettings, bounds: BoundingBox, footprint: float) -> list[SettingAdvice]:
    """Was dieses eine Teil anders braucht als die Platte (§29).

    Die Plattenhaftung ist die eine Einstellung, die je Teil zählt statt je
    Auftrag: sie hängt daran, worauf ein Körper steht, und das ist bei jedem
    ein anderer Wert. Beim Gewürzset stehen zwölf Behälter auf Ø 40 und drei
    Streuscheiben auf je drei 1,1-mm-Federarmen — dieselbe Platte, und der
    Brim gehört nur unter die Scheiben. Ohne diese Unterscheidung gäbe es nur
    „alle bekommen einen" oder „keiner".

    Temperatur, Kühlung und Stützen bleiben plattenweit: sie hängen am Material
    oder an der Maschine, und je Teil verstellt wären sie ein Widerspruch, den
    der Slicer auflösen müsste.
    """
    if settings.adhesion.kind != "skirt":
        return []
    if 0.0 < footprint < SMALL_FOOTPRINT:
        reason = _("Dieses Teil steht auf zu wenig Fläche, um ohne Brim zu halten.")
    elif _slender(bounds):
        reason = _("Dieses Teil ist hoch und schmal. Die Düse kann es beim Anfahren kippen.")
    else:
        return []
    return [
        SettingAdvice(
            path="adhesion.kind",
            value="brim",
            was=settings.adhesion.kind,
            reason=reason,
            severity="warning",
        )
    ]


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
    """
    findings: list[Finding] = []

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
            )
        )

    if not profile.material.calibrated:
        findings.append(
            Finding(
                code="settings.uncalibrated_material",
                severity="info",
                message=_(
                    "Die Toleranzen dieses Materials sind der mitgelieferte Startwert, "
                    "keine Messung."
                ),
                values={"material": profile.material.title},
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


def _from_spans(result: SliceResult | None) -> list[Finding]:
    """Decken, die quer durch die Luft spannen (§22.2).

    Kein Vorschlag, sondern ein Befund: keine Einstellung macht aus einer
    27-mm-Brücke eine tragende Fläche. Was hilft, ist die Geometrie — ein
    Übergang unter 45 Grad statt einer waagerechten Schulter — oder eine
    Stütze. Beides entscheidet der Nutzer, nicht die Regel.

    Gemeldet wird die schlimmste Stelle mit ihrer Höhe, nicht jede einzelne:
    ein Bericht mit dreißig Zeilen derselben Sache wird nicht gelesen.
    """
    if result is None:
        return []
    spanning = [layer for layer in result.layers if layer.bridge_width > SPAN_INTERESTING]
    if not spanning:
        return []

    worst = max(spanning, key=lambda layer: layer.bridge_width)
    _log.info("%d layer(s) span more than %.0f mm", len(spanning), SPAN_INTERESTING)
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
                "span_mm": round(worst.bridge_width, 1),
                "z_mm": round(worst.z, 2),
                "layers": len(spanning),
            },
            location=(0.0, 0.0, worst.z),
        )
    ]


def apply(settings: PrintSettings, advice: list[SettingAdvice]) -> PrintSettings:
    """Vorschläge übernehmen — alle, oder die ausgewählten.

    Der Aufrufer entscheidet, was in der Liste steht. Angewandt wird nie von
    allein: das hier ist die Umsetzung einer Zustimmung, nicht ihr Ersatz.
    """
    result = settings
    for entry in advice:
        result = settings_table.with_path(result, entry.path, entry.value)
    return result
