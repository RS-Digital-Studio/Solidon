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

from dataclasses import replace
from typing import Final

from app.core.knowledge import print_settings as settings_table
from app.core.log import get_logger
from app.core.slice.analysis import island_layers, narrowest, total_overhang
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

#: So viele Schichten mit Inseln machen aus Gitterstützen Baumstützen: viele
#: verteilte Ansatzpunkte sind genau der Fall, für den Bäume gebaut wurden.
TREE_FROM_ISLANDS = 8

#: Kleinste Schichtfläche in mm², unter der eine Schicht so schnell durch ist,
#: dass die vorige noch weich liegt.
THIN_LAYER_AREA = 120.0

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
    has_fits: bool = False,
) -> list[SettingAdvice]:
    """Was an diesen Einstellungen für dieses Teil nicht passt (§29).

    ``result`` darf fehlen — dann bleiben die Vorschläge übrig, die allein aus
    Material und Drucker folgen. Das ist der Fall vor dem ersten Schnitt, und
    er soll nicht zu einem leeren Bericht führen.
    """
    advice: list[SettingAdvice] = []
    advice += _from_machine(settings, profile)
    advice += _from_material(settings, profile)
    if result is not None:
        advice += _from_geometry(settings, profile, result, bounds)
    if has_fits:
        advice += _from_fits(settings)

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
    das kann, sonst langsamer. Welcher richtig ist, weiß Formwerk nicht —
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
    needs_support = bool(islands) or overhang > OVERHANG_WORTH_SUPPORT

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


def _from_fits(settings: PrintSettings) -> list[SettingAdvice]:
    """Wo Passungen im Spiel sind, entscheidet die Außenwand über das Maß."""
    advice: list[SettingAdvice] = []
    careful = 30.0
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


def warnings_for(settings: PrintSettings, profile: Profile) -> list[Finding]:
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
    return findings


def apply(settings: PrintSettings, advice: list[SettingAdvice]) -> PrintSettings:
    """Vorschläge übernehmen — alle, oder die ausgewählten.

    Der Aufrufer entscheidet, was in der Liste steht. Angewandt wird nie von
    allein: das hier ist die Umsetzung einer Zustimmung, nicht ihr Ersatz.
    """
    result = settings
    for entry in advice:
        result = settings_table.with_path(result, entry.path, entry.value)
    return result
