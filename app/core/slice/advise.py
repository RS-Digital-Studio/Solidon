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
from app.core.slice.analysis import (
    island_layers,
    narrowest_measured,
    support_on_model,
    total_overhang,
    worst_overhang,
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
from app.core.units import is_close
from app.i18n import TranslatableText, _

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

#: Um so viel Grad wird die Düse angehoben, wenn der Volumenstrom es verlangt.
#: Zehn Grad sind ein spürbarer Schritt und bleiben im Rahmen dessen, was ein
#: Filament aushält — die große Änderung gehört ins Materialprofil, nicht in
#: einen Vorschlag.
TEMPERATURE_STEP: Final = 10

#: Um so viel Grad wird das Bett angehoben, wo die Haftung es verlangt.
BED_STEP: Final = 5

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
    """
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
    # deshalb gegen den Stand *nach* ihnen gerechnet, sonst empfiehlt er eine
    # heißere Düse für ein Tempo, das nebenan schon gesenkt wurde.
    advice = _merged(settings, advice + _from_flow(apply(settings, advice), profile))

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
    height = settings.layers.first_layer_height if first_layer else settings.layers.layer_height
    width = settings.layers.first_layer_line_width if first_layer else settings.layers.line_width
    return height * width * speed


def _from_flow(settings: PrintSettings, profile: Profile) -> list[SettingAdvice]:
    """Was nicht durch die Düse passt (§29).

    Das Hotend ist die eigentliche Grenze, und sie wird selten als solche
    gezeigt: der Antrieb fördert weiter, das Material wird nur nicht mehr
    warm genug. Die Bahn wird dann dünner als gerechnet, die Wand porös, und
    an den Einstellungen sieht man nichts.

    Zwei Wege heraus, und beide werden genannt: heißer, solange die Maschine
    das kann, sonst langsamer. Welcher richtig ist, weiß Solidon nicht —
    darum entscheidet es das nicht.

    **Gedeckelt wird der Wert, der die Grenze reißt.** Hier stand immer
    ``speed.infill``, auch wenn die Innenwand die schnellere von beiden war:
    Herausgekommen ist der Rat „Füllung 20 → 143" — eine **Erhöhung** —,
    während der Wert, an dem es lag, unangetastet blieb und der Volumenstrom
    verletzt. Gefragt wird deshalb jeder Wert einzeln.

    **Und jeder heißt jeder.** Geprüft wurden zwei von sechs Geschwindigkeiten;
    die Außenwand, die Deckfläche und die erste Schicht liefen ungeprüft
    durch. Eine Stufe, die nur an der Außenwand zieht, kam damit ohne einen
    Satz durch — und die erste Schicht ist der Wert, der als erster reißt:
    Sie ist höher und breiter als alle über ihr. Der Fahrweg bleibt draußen,
    weil dabei nichts gefördert wird, und die Brücke bleibt draußen, weil
    ihre Bahn mit Absicht dünner liegt als gerechnet.

    **Und was der heißere Weg nicht leistet:** ``max_flow`` ist eine Zahl des
    Materialprofils und hängt dort an keiner Temperatur. Zehn Grad mehr machen
    das Filament flüssiger, die Grenze in den Einstellungen bewegen sie nicht —
    der Vorschlag nennt den anderen Weg, er rechnet ihn nicht nach. Wer ihn
    annimmt, bekommt die Zeile beim nächsten Durchgang wieder, und das ist
    ehrlicher, als eine Grenze zu verschieben, die niemand gemessen hat.
    """
    advice: list[SettingAdvice] = []
    limit = settings.filament.max_flow
    per_millimetre = settings.layers.layer_height * settings.layers.line_width
    first_per_millimetre = (
        settings.layers.first_layer_height * settings.layers.first_layer_line_width
    )
    if limit <= 0.0 or per_millimetre <= 0.0 or first_per_millimetre <= 0.0:
        return advice

    breaking = [
        (path, speed, first)
        for path, speed, first in (
            ("speed.infill", settings.speed.infill, False),
            ("speed.inner_wall", settings.speed.inner_wall, False),
            ("speed.outer_wall", settings.speed.outer_wall, False),
            ("speed.top_surface", settings.speed.top_surface, False),
            ("speed.first_layer", settings.speed.first_layer, True),
        )
        if flow_of(settings, speed, first_layer=first) > limit
    ]
    if not breaking:
        return advice

    headroom = profile.printer.nozzle_temperature_max - settings.temperature.nozzle
    if headroom >= TEMPERATURE_STEP:
        advice.append(
            _advice(
                settings,
                path="temperature.nozzle",
                value=settings.temperature.nozzle + TEMPERATURE_STEP,
                reason=_(
                    "Bei diesem Tempo müssen mehr Kubikmillimeter je Sekunde durch die "
                    "Düse, als das Material bei dieser Temperatur flüssig wird."
                ),
                severity="warning",
            )
        )
        return advice

    # Ohne Luft nach oben bleibt nur der andere Weg — und ein Vorschlag,
    # der die Maschinengrenze überschreitet, wäre keiner.
    # Abgerundet und nicht gerundet: Ein aufgerundeter Wert liegt wieder über
    # der Grenze, um die es geht — knapp, aber der Vorschlag hätte sie dann
    # nicht eingehalten.
    for path, speed, first in breaking:
        allowed = float(math.floor(limit / (first_per_millimetre if first else per_millimetre)))
        if allowed <= 0.0 or allowed >= speed:
            # Nur Rundung, oder eine Einstellung, für die es kein sinnvolles
            # Tempo mehr gibt: ein „Vorschlag", der nichts senkt, ist keiner.
            continue
        advice.append(
            SettingAdvice(
                path=path,
                value=allowed,
                was=speed,
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
    if 0.0 < settings.layers.line_width < narrowest:
        advice.append(
            _advice(
                settings,
                path="layers.line_width",
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
    needs_support = (
        bool(islands)
        or worst > OVERHANG_LAYER_WORTH_SUPPORT
        or (overhang > OVERHANG_WORTH_SUPPORT and worst > OVERHANG_LAYER_MINIMUM)
    )

    if needs_support and settings.support.style == "none":
        style = "tree" if len(islands) >= TREE_FROM_ISLANDS else "grid"
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
    # Geometrie und nicht ein Nebenbefund (:func:`support_on_model`).
    if (
        needs_support
        and not islands
        and settings.support.placement == "everywhere"
        and not support_on_model(result)
    ):
        advice.append(
            _advice(
                settings,
                path="support.placement",
                value="build_plate",
                reason=_(
                    "Alle Überhänge erreichen das Bett. Stützen auf dem Modell "
                    "hinterlassen Narben, die keine sein müssen."
                ),
            )
        )

    if 0.0 < result.first_layer_area < SMALL_FOOTPRINT and settings.adhesion.kind == "skirt":
        advice.append(
            _advice(
                settings,
                path="adhesion.kind",
                value="brim",
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
            _advice(
                settings,
                path="temperature.bed_first_layer",
                value=min(
                    settings.temperature.bed_first_layer + BED_STEP,
                    profile.printer.bed_temperature_max,
                ),
                reason=_(
                    "Kleine Standfläche und ein Material, das sich zusammenzieht — ein "
                    "wärmeres Bett hält die erste Schicht unten."
                ),
            )
        )

    if bounds is not None and _slender(bounds) and settings.adhesion.kind == "skirt":
        advice.append(
            _advice(
                settings,
                path="adhesion.kind",
                value="brim",
                reason=_("Das Teil ist hoch und schmal. Die Düse kann es beim Anfahren kippen."),
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
        # Der Befund ``settings.wall_below_nozzle`` (``warnings_for``) deckt
        # den ganzen Bereich darunter: kleinere Düse oder breitere Stelle,
        # beides entscheidet der Nutzer, kein Wert.
        advice.append(
            _advice(
                settings,
                path="layers.line_width",
                value=round(max(thin / 2.0, least), 3),
                reason=_(
                    "Die dünnste Stelle ist schmaler als zwei Linien breit. Mit der "
                    "jetzigen Breite fällt sie im Druck weg."
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
            value=round(needed, 2),
            reason=_(
                "Der Verbinder ist zu dick, um ihn mit Wänden zu schließen — er "
                "trägt dann über das Füllmuster in seiner Mitte. So viel Füllung "
                "macht seinen Querschnitt so tragfähig wie ein Ring aus Wänden; "
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
                "Füllmuster und trägt nur mit seiner Außenhaut. So viele Wände "
                "treffen sich in seiner Mitte — sie gelten dann für das ganze "
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
    if settings.adhesion.kind != "skirt":
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

    # **Was die Maschine nicht kann, wird gesagt und nicht gedeckelt.**
    # ``print_settings._temperatures`` nimmt das Kleinere aus Materialwunsch
    # und Maschinengrenze, und sein Docstring sagt dazu „gedeckelt wird, aber
    # ``advise`` sagt es auch". Für die Düse stimmte das (``_from_machine``),
    # für Bett und Bauraum nicht: ABS will 100 °C Bett, der A1 mini kann 80 —
    # der Druck lief mit zwanzig Grad zu kaltem Bett los, und im Bericht stand
    # kein Wort. Ein **Befund** und kein Vorschlag, denn kein Wert behebt es:
    # 80 Grad sind bereits das Höchste, was die Maschine hergibt (§17.3).
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

    if result is not None:
        least = NARROW_LINE_SHARE * profile.printer.nozzle_diameter
        thin = narrowest_measured(result)
        if thin is not None and thin < 2.0 * least:
            # Das Gegenstück zur Bahnbreiten-Regel in ``_from_geometry``: Was
            # keine zwei Bahnen dieser Düse mehr trägt, behebt kein Wert mehr —
            # nach der Doktrin also ein Befund. Beide Auswege stehen im Satz
            # (Regel 17): die kleinere Düse gehört danach ins Druckerprofil,
            # sonst rechnet alles Weitere mit der falschen.
            #
            # **Bis zur doppelten schmalsten Bahn und nicht bis zur einfachen.**
            # Dazwischen lag ein Bereich ohne Antwort: Der Vorschlag daneben
            # senkte die Bahnbreite auf einen Wert, dessen zwei Bahnen immer
            # noch breiter waren als die Stelle, und hier schwieg es. Eine
            # Stelle von 0,50 mm an einer 0,4er Düse bekam damit einen
            # Vorschlag, der nichts änderte, und keinen Satz dazu.
            findings.append(
                Finding(
                    code="settings.wall_below_nozzle",
                    severity="warning",
                    message=_(
                        "Die dünnste Stelle trägt keine zwei Bahnen, auch nicht mit "
                        "der schmalsten, die diese Düse legen kann — daran ändert "
                        "keine Einstellung etwas. Eine kleinere Düse druckt sie "
                        "(danach den Durchmesser im Druckerprofil nachziehen), oder "
                        "die Stelle wird auf zwei Bahnbreiten verbreitert."
                    ),
                    values={
                        "width_mm": thin,
                        "nozzle_mm": profile.printer.nozzle_diameter,
                        "least_mm": least,
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
