"""Übergabe an den Slicer (Bauplan §29, §28.1).

Solidon baut keinen G-Code-Slicer (§22) — es bedient einen. Der Unterschied
zum Wechseln in ein anderes Programm ist, dass die Einstellungen hier bleiben:
Solidon schreibt sie als Profil, ruft den Slicer im Konsolenmodus, und liest
die entstandene Datei mit :mod:`app.core.slice.gcode` wieder ein. Wer das
benutzt, sieht den Slicer nicht mehr.

Was Solidon **nicht** mitbringt, ist das Maschinenwissen: Bettform,
Anfahrwege, Start- und Endcode, die Eigenheiten einer Kinematik. Das steht in
den Profilen, die der Slicer mitbringt, und genau dort bleibt es. Solidon
setzt sein Profil darauf — es überschreibt, es ersetzt nicht.

Ein Lauf ist abgesichert nach §32: feste Argumentliste, kein Shell, eigener
Arbeitsordner, Zeitlimit. Hier läuft kein fremder Quelltext, sondern ein
Programm zeigt auf eine Datei — seit dem OpenSCAD-Ausbau ist das der einzige
Fall, den es in Solidon noch gibt.
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from app.core import activation, discover
from app.core.errors import (
    ARRANGE_ON_BED,
    CANCEL,
    CHANGE_SELECTION,
    CHECK_SLICER_PROFILE,
    CHOOSE_PRINTER,
    CHOOSE_SLICER,
    EXPORT_ONLY,
    INSTALL_MISSING,
    OPEN_SETTINGS,
    REPAIR_AND_RETRY,
    RETRY,
    SCALE_TO_FIT,
    SHOW_LOCATIONS,
    SHOW_SLICER_OUTPUT,
    ExternalToolError,
    FileWriteError,
    OperationCancelled,
)
from app.core.export import slicer_keys, slicer_profiles, threemf
from app.core.export.slicer_keys import (
    SlicerFlavour,
    has_filament_profiles,
    has_key_definitions,
    names_its_own_output,
    reads_settings_from_project_file,
    takes_a_machine_profile,
    wants_bed_coordinates,
)
from app.core.knowledge import profiles
from app.core.knowledge.print_settings import read_path, with_path
from app.core.log import get_logger
from app.core.process import (
    ProcessCancelled,
    ProcessOutputLimitExceeded,
    detached_process_options,
    run_limited,
)
from app.core.slice import gcode
from app.core.types import (
    BoundingBox,
    CancelToken,
    Finding,
    MaterialSlot,
    PrintSettings,
    Profile,
    SettingAdvice,
    SlotOverride,
)
from app.i18n import _

_log = get_logger(__name__)

#: Slicen dauert länger als alles andere, was Solidon außer Haus gibt. Fünf
#: Minuten sind großzügig für ein Teil und immer noch eine Grenze.
TIMEOUT_SECONDS: Final = 300.0

#: Konsolenausgaben der Slicer sind Diagnose, keine Druckdatei. Acht MiB
#: lassen ausführliche Protokolle zu, ohne dass ein defekter Slicer den
#: Arbeitsprozess mit einer endlosen Ausgabe füllen kann.
SLICER_OUTPUT_LIMIT: Final = 8 * 1024 * 1024

#: Beim Behalten wird höchstens dieser Teil der Druckdatei zugleich gelesen.
#: Die Blockgrenze ist zugleich ein natürlicher Punkt für den Abbruchtest.
COPY_BLOCK_BYTES: Final = 1024 * 1024

#: Wonach im Ausgabeordner gesucht wird — die Slicer benennen selbst.
#:
#: **Dieselbe Liste, die der Öffnen-Dialog anbietet** (`ui.main_window`
#: holt sie von hier). Sie stand dort ein zweites Mal und war um ``.nc``
#: länger: Der Kunde durfte eine ``.nc`` also öffnen, aber wenn ein
#: Slicer eine schrieb, fand Solidon sie im Ausgabeordner nicht und
#: meldete „Der Slicer hat keine Druckdatei geschrieben." Zwei Stellen,
#: dieselbe Frage, eine gepflegt — gefunden am 27.08.2026.
GCODE_SUFFIXES: Final = (".gcode", ".gco", ".g", ".nc")

#: Wie die Druckdatei heißt, wo Solidon den Namen selbst nennt — PrusaSlicer
#: über ``--output``, CuraEngine über ``-o``. Die Orca-Familie benennt selbst
#: und hängt Plattennummern an; für sie gibt es keinen erwarteten Namen.
OUTPUT_NAME: Final = "solidon.gcode"

#: Was in einem Profil „dazu sage ich nichts" heißt. Ein Filamentprofil, das
#: den Rückzug auf ``nil`` stellt, widerspricht Solidon nicht — es überlässt
#: den Wert dem Drucker.
_NO_STATEMENT: Final = frozenset({"nil", "", "none"})

#: Vorgabewerte aus ``fdmprinter.def.json``, die in eine gerechnete Ableitung
#: eingehen und die Solidon selbst nicht setzt (siehe :func:`_cura_rated`).
#: Ausgeschrieben, weil eine Zahl mitten in einer Formel niemandem sagt, woher
#: sie kommt — und weil die Definition nicht auf jedem Rechner liegt.
_SUPPORT_SKIP_PER_MM: Final = 20.0
_SKIN_OVERLAP: Final = 5.0
_INFILL_OVERLAP: Final = 10.0
_MAX_RESOLUTION: Final = 0.5
_IRONING_FLOW: Final = 10.0
_TRAVEL_ACCELERATION: Final = 5000.0
_SUPPORT_GROWTH: Final = 0.4
_SUPPORT_BRIM_LINES: Final = 3.0
_STAIR_STEP: Final = 0.3
#: Bis zu dieser Fülldichte stützt Cura die Deckfläche zusätzlich ab. Darüber
#: trägt die Füllung selbst genug.
_SKIN_SUPPORT_BELOW: Final = 0.4
#: Ab dieser Fülldichte lässt Cura die Überlappung weg — die Füllung stößt
#: dann ohnehin an die Wand.
_DENSE_INFILL: Final = 0.95


@dataclass(frozen=True, slots=True)
class SlicerSetup:
    """Welcher Slicer, und worauf seine Profile aufsetzen.

    ``machine_profile`` und ``base_process`` tragen bevorzugt **Namen** aus
    dem Bestand des Slicers — so reisen sie in eine Projektdatei, ohne gegen
    Regel 12 zu verstoßen, und zeigen auf einem zweiten Rechner nicht ins
    Leere. Ein Pfad wird ebenso angenommen; :func:`profile_file` löst beides
    zur Datei auf, denn der Slicer nimmt nur die.
    """

    executable: Path
    flavour: SlicerFlavour
    machine_profile: str = ""
    base_process: str = ""
    base_filament: str = ""
    """Das Filamentprofil des Slicers, auf das Solidon seine Werte legt.

    Ohne das kennt der Slicer nur „PETG"; mit ihm weiß er, *welches* — und
    fährt die Werte des Herstellers für alles, was Solidon nicht setzt.
    """

    @property
    def name(self) -> str:
        return self.executable.stem


def profile_file(chosen: str, setup: SlicerSetup, kind: slicer_profiles.ProfileKind) -> Path | None:
    """Die Datei zu einem Profil, gleich ob ein Name oder ein Pfad ankam.

    Beides muss gehen, und das ist kein Entgegenkommen, sondern die Folge aus
    zwei Anforderungen, die auseinanderziehen: in die Projektdatei gehört der
    **Name** — ein Pfad dort verstößt gegen Regel 12 und zeigt auf einem
    zweiten Rechner ins Leere. Der Slicer dagegen nimmt nur die **Datei**; wer
    ihm den Namen reicht, bekommt „can not find setting file" und einen
    Abbruch, bevor das Modell angesehen wird.

    Ohne diese Auflösung dazwischen war das Ergebnis stiller: ``base_process``
    trug einen Namen, ``Path(name).is_file()`` sagte nein, und das
    geschriebene Prozessprofil hatte zweiundvierzig Schlüssel statt
    zweiundsechzig — ohne ``inherits``, ohne ``compatible_printers``. Genau
    die beiden, an denen die Orca-Familie die Verträglichkeit prüft.
    """
    if not chosen:
        return None
    direct = Path(chosen)
    if direct.is_file():
        return direct
    # ``kind`` und nicht ``type_of``: das eine ist der Ordner, aus dem das
    # Profil stammt, das andere sein ``type``-Feld — und das steht in den
    # mitgelieferten Profilen der Orca-Familie durchweg leer.
    #
    # Gesucht wird ausdrücklich nach dieser Art. Ohne die Angabe gilt
    # ``DEFAULT_KINDS``, und darin fehlen die Filamentprofile mit Absicht —
    # sie vervielfachen den Bestand. Wer hier nach einem Filament fragte, bekam
    # deshalb nie eines: die Schleife lief über Maschinen und Prozesse und
    # endete in „no filament profile named ...". Nach einer Art zu fragen ist
    # obendrein schneller als nach zweien.
    for entry in slicer_profiles.find_profiles(setup.executable, setup.flavour, kinds=(kind,)):
        if entry.name == chosen and entry.kind == kind:
            found = Path(entry.path)
            if found.is_file():
                return found
    _log.warning("no %s profile named %r in this slicer", kind, chosen)
    return None


def machine_for(setup: SlicerSetup, profile: Profile) -> str:
    """Das Maschinenprofil dieser Übergabe — gewählt, sonst das des Slicers.

    **Warum es diesen Rückfall gibt.** Prozess und Filament schreibt Solidon
    selbst aus; die Maschine schreibt es **nicht**. Startcode,
    Schichtwechselcode und Maschinengrenzen weiß nur der Hersteller, und
    Geratenes wäre bei G-Code gefährlich. Ist keine Maschine hinterlegt, fehlt
    diese Seite in der Datei ganz, und der Slicer füllt sie aus seinen eigenen
    Vorgaben — die nicht zusammenpassen müssen. Am 03.09.2026 lehnte
    ElegooSlicer eine übergebene Datei deshalb ab: Seine Vorgabe fährt mit
    relativer Extruderadressierung und verlangt dafür ein ``G92 E0`` im
    Schichtwechselcode, das im Herstellerprofil steht und in der Datei fehlte.
    Gemessen an einem Centauri Carbon 2: ohne Maschinenseite 73 Werte, mit ihr
    160.

    **Auch eine getroffene Wahl wird gefragt** — seit dem 03.09.2026, und das
    war ein Fund von 3d-druck-c7 an vier echten Druckern. Der Druckdialog merkt
    sich das zuletzt gewählte Maschinenprofil und reichte es unbesehen weiter;
    wer den Drucker des Projekts wechselte, bekam es trotzdem. Die geschriebene
    Maschinendatei eines Prusa-MK4S-Projekts trug damit ``printer_model``
    „Elegoo Centauri Carbon 2", einen Bauraum von 256 x 256 x 256 statt
    250 x 210 x 220 und den Anfahrcode ``CC2_START_GCODE``. Ein Teil, das
    Solidon als passend ausweist, ragt so 46 mm über die Kante des Prusa.

    Die Sperre dagegen gab es: ``UiSettings.slicer_profile_printer`` merkt,
    für welchen Drucker die Profile gewählt wurden, und ``settings_for_export``
    fragt sie. ``_current_setup`` im Dialog las die Auswahlfelder ungefiltert —
    ein Wächter, den ein Weg von zweien ruft. Er steht jetzt hier, wo beide
    durchmüssen.

    **Und warum der Rückfall fragt, statt zu nehmen.** Der Slicer nennt seine
    eingestellte Maschine, aber das muss nicht der Drucker sein, für den
    Solidon gerade rechnet — auf dieser Maschine stand ElegooSlicer auf einem
    „Bambu Lab A1 0.2 nozzle", während das Projekt einem Centauri Carbon 2
    galt. Ein blind übernommenes Profil brächte den Startcode eines fremden
    Druckers in die Datei, dazu dessen Bauraum und Düse; ein Homing-Befehl der
    falschen Maschine fährt die Düse ins Bett. Übernommen wird deshalb nur,
    was über :func:`slicer_profiles.printer_for` auf **denselben** Drucker
    zeigt, den das Projekt benutzt. Sonst bleibt es beim bisherigen Verhalten:
    keine Maschinenseite, und Regel 21 — nicht raten.
    """
    if setup.machine_profile:
        return setup.machine_profile if _fits_the_printer(setup.machine_profile, profile) else ""
    chosen = slicer_profiles.chosen_machine(setup.flavour, setup.executable)
    if not chosen:
        return ""
    same = slicer_profiles.printer_for(chosen, profiles.printer_profiles())
    if same != profile.printer.id:
        _log.info(
            "slicer is set to %r (%s), the project prints on %s — no machine side handed over",
            chosen,
            same or "unknown",
            profile.printer.id,
        )
        return ""
    return chosen


def _fits_the_printer(machine_profile: str, profile: Profile) -> bool:
    """Gehört dieses Maschinenprofil zum Drucker des Projekts?

    **Nicht erkannt heißt ja.** ``printer_for`` ordnet nur zu, was es kennt;
    ein selbst gebautes Profil gehört seinem Besitzer, und es ihm wegzunehmen
    wäre schlimmer als es zu nehmen — ohne Maschinenprofil lehnt die
    Orca-Familie den Auftrag ganz ab. Geprüft wird deshalb gegen einen
    **anderen bekannten** Drucker und nicht gegen „unbekannt".

    Ein Pfad statt eines Namens ist der zweite Fall, den ``printer_for`` nicht
    beantwortet: In die Projektdatei gehört der Name (Regel 12), der Dialog
    reicht aber die Datei weiter. Der Stamm des Dateinamens ist derselbe Name —
    ``profile_file`` löst beide Richtungen ebenso auf.

    **Der Stamm wird nur genommen, wenn der ganze Name nichts ergibt**, und
    nicht anhand einer Dateiendung: Profilnamen tragen Punkte. „Elegoo Centauri
    Carbon 2 0.4 nozzle" hat für ``Path`` das Suffix „.4 nozzle", und wer daran
    entscheidet, fragt nach „Elegoo Centauri Carbon 2 0" — einem Namen, den es
    nicht gibt. Der Prüfling galt damit als nicht zuordenbar und ging durch.
    """
    known = profiles.printer_profiles()
    belongs = slicer_profiles.printer_for(machine_profile, known)
    if not belongs:
        belongs = slicer_profiles.printer_for(Path(machine_profile).stem, known)
    return not belongs or belongs == profile.printer.id


def machine_missing(setup: SlicerSetup, profile: Profile) -> list[Finding]:
    """Sagt dem Kunden, warum die Maschinenseite fehlt (§29, Regel 21).

    :func:`machine_for` weigert sich mit gutem Grund, ein fremdes
    Maschinenprofil zu nehmen — ein Homing-Befehl der falschen Maschine fährt
    die Düse ins Bett. Es weigerte sich bis zum 03.09.2026 aber **schweigend**:
    Die Begründung ging in eine Protokollzeile, die niemand liest, und der
    Kunde bekam dieselbe Datei, die sein Slicer schon einmal abgelehnt hatte.
    Genau so kam der Fall herein — ElegooSlicer stand auf einem „Bambu Lab A1
    0.2 nozzle", das Projekt galt einem Centauri Carbon 2, und die Absage
    sprach von ``G92 E0``.

    Zwei Fälle und zwei Sätze, denn der Ausweg ist ein anderer: Wer auf dem
    falschen Drucker steht, wechselt ihn im Slicer; wer noch gar keinen
    eingerichtet hat, kann das nicht — er wählt in Solidon ein Maschinenprofil.
    Ein Rat, der ins Leere zeigt, ist keiner.

    Nichts zu melden ist der Regelfall: Steht die Maschine, ist die Datei
    vollständig, und eine Beruhigung wäre eine Zeile, die nichts unterscheidet.

    **Und nur für die Orca-Familie.** Der Befund galt einen halben Tag lang
    weiter, als er gemeint war: Cura und PrusaSlicer bekommen von Solidon
    **nie** ein Maschinenprofil aus fremdem Bestand — ihre Maschinenseite baut
    :func:`_machine_keys` aus dem eigenen Druckerprofil, und eine ``.ini`` ist
    eigenständig lauffähig, sobald Düse und Bettform darin stehen. Für sie ist
    „keine Maschinenseite" kein Mangel, sondern die Bauart. Gemessen am
    03.09.2026: Beide bekamen bei jedem Export ein ``slicer.machine_unset``
    und den Rat, im Slicer einen Drucker einzurichten, den sie dafür nicht
    brauchen. Eine Warnung, die nicht stimmt, ist teurer als keine.
    """
    if not takes_a_machine_profile(setup.flavour):
        return []
    if machine_for(setup, profile):
        return []
    if setup.machine_profile:
        # **Nicht „der Slicer steht falsch", denn er steht gar nicht.** Hier hat
        # der Kunde selbst gewählt, und seine Wahl gehört zu einer anderen
        # Maschine — meist, weil sie aus dem vorigen Projekt stammt. Der Rat
        # ist deshalb ein anderer: nicht den Slicer umstellen, sondern die
        # Wahl. Ein Satz, der die falsche Ursache nennt, schickt den Kunden an
        # die falsche Stelle.
        return [
            Finding(
                code="slicer.machine_mismatch",
                severity="warning",
                message=_(
                    "Das gewählte Maschinenprofil gehört zu einem anderen Drucker "
                    "und wird deshalb nicht übergeben — sein Bauraum, seine Düse "
                    "und sein Startcode wären die einer fremden Maschine. Wählen "
                    "Sie in den Druckeinstellungen das Profil dieses Druckers."
                ),
                values={"machine": setup.machine_profile, "printer": profile.printer.title},
                suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER, EXPORT_ONLY),
            )
        ]
    chosen = slicer_profiles.chosen_machine(setup.flavour, setup.executable)
    if chosen:
        return [
            Finding(
                code="slicer.machine_mismatch",
                severity="warning",
                message=_(
                    "Der Slicer ist auf einen anderen Drucker eingestellt. Die Datei "
                    "trägt deshalb keine Maschinenangaben — Startcode, "
                    "Schichtwechselcode und Maschinengrenzen fehlen, und der Slicer "
                    "füllt sie mit eigenen Vorgaben, die er anschließend ablehnen "
                    "kann. Stellen Sie den Slicer auf denselben Drucker um oder "
                    "wählen Sie das Maschinenprofil in den Druckeinstellungen."
                ),
                values={"machine": chosen, "printer": profile.printer.title},
                suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER, EXPORT_ONLY),
            )
        ]
    return [
        Finding(
            code="slicer.machine_unset",
            severity="warning",
            message=_(
                "In diesem Slicer ist noch kein Drucker eingerichtet. Die Datei trägt "
                "deshalb keine Maschinenangaben — Startcode, Schichtwechselcode und "
                "Maschinengrenzen fehlen. Wählen Sie das Maschinenprofil in den "
                "Druckeinstellungen oder richten Sie den Drucker im Slicer ein."
            ),
            values={"slicer": setup.name, "printer": profile.printer.title},
            suggestions=(CHECK_SLICER_PROFILE, EXPORT_ONLY),
        )
    ]


def detect(executable: Path | str) -> SlicerSetup:
    """Was für ein Slicer das ist. Erkennt an seinem Namen (§29)."""
    path = Path(executable)
    flavour = slicer_keys.flavour_of(path.name)
    if flavour is None:
        raise ExternalToolError(
            tool=path.name,
            detail=_("Solidon kennt die Kommandozeile dieses Programms nicht."),
            suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
        )
    return SlicerSetup(executable=path, flavour=flavour)


def as_mapping(settings: PrintSettings, flavour: SlicerFlavour) -> dict[str, str]:
    """Die Einstellungen in der Sprache dieses Slicers (§29).

    Ohne Datei und ohne Aufruf — die Tests prüfen die Zuordnung, ohne dass ein
    Slicer installiert sein muss, und die Gegenprobe vergleicht dagegen. Alle
    Profile zusammen, weil die Gegenprobe die Druckdatei als Ganzes liest und
    dort nicht mehr steht, aus welchem Profil ein Wert kam.

    Was hier herauskommt, ist die **Einstellungsseite**: die Zuordnung, und was
    sich allein aus den Einstellungen umrechnen lässt. Die Maschine kommt in
    :func:`_machine_keys` dazu, das Abgeleitete in :func:`_cura_dependants` —
    beides führt :func:`values_for` zusammen, und nur diese eine Stelle.
    """
    written: dict[str, str] = {}
    for entry in slicer_keys.TABLES[flavour]:
        value = entry.write(read_path(settings, entry.path))
        # Ein leerer Text heißt „dazu sagt Solidon nichts" (siehe
        # ``_number_or_silent``). Er darf weder in die Datei noch in die
        # Gegenprobe: geschrieben überschriebe er den Wert des Herstellers,
        # verglichen meldete er eine Abweichung von nichts.
        if value != "":
            written[entry.key] = value
    chosen = _only_chosen_adhesion(written, settings, flavour)
    if flavour == "cura":
        return _first_layer_width(chosen)
    return _support_spacing(chosen, settings, flavour)


def values_for(settings: PrintSettings, profile: Profile, flavour: SlicerFlavour) -> dict[str, str]:
    """Alles, was dieser Slicer bekommt — Einstellungen, Maschine, Abgeleitetes.

    Die eine Stelle, an der die drei Stufen zusammenkommen. Sie hat einen
    Grund, und der ist die Reihenfolge: ``CuraEngine`` rechnet aus der
    Bahnbreite zwölf weitere und aus dem Düsendurchmesser sieben, und der
    Düsendurchmesser steht in der Maschine. Wer die Ableitung vor dem
    Zusammenführen laufen ließe, bekäme die Hälfte.
    """
    values = as_mapping(settings, flavour)
    values |= _machine_keys(profile, flavour)
    if flavour == "cura":
        return _cura_dependants(values, settings)
    return values


def by_section(
    settings: PrintSettings, flavour: SlicerFlavour
) -> dict[slicer_keys.ProfileSection, dict[str, str]]:
    """Dieselben Werte, getrennt nach dem Profil, in das sie gehören (§29).

    Der Unterschied ist nicht kosmetisch: die Orca-Familie nimmt einen Wert
    nur an, wenn er im richtigen Profil steht. Eine Düsentemperatur im
    Prozessprofil wird stillschweigend übergangen — kein Fehler, keine
    Warnung, gedruckt wird mit dem, was zuletzt im Slicer eingestellt war.

    Was die Zuordnungstabelle nicht kennt, geht in den Prozess. Gemessen am
    Bestand ist das genau ein Schlüssel, und er kommt aus
    :func:`_support_spacing`: ``support_material_spacing`` bei PrusaSlicer,
    ``support_base_pattern_spacing`` bei der Orca-Familie — beide gehören ins
    Prozessprofil, und dort landen sie so auch. (:func:`_only_chosen_adhesion`
    erzeugt keine eigenen Schlüssel, es nullt vorhandene, und
    ``initial_layer_line_width_factor`` aus :func:`_first_layer_width` steht in
    Curas Tabelle.)

    Sie hier wegzusortieren hieße, sie gar nicht zu schreiben: die Aufteilung
    ist eine Aufteilung und kein zweiter Filter. Für Cura ist der Prozess
    ohnehin der einzige Satz, den es gibt — die Ableitungen aus
    :func:`_cura_dependants` sieht diese Funktion gar nicht, denn sie liest
    :func:`as_mapping` und nicht :func:`values_for`.
    """
    complete = as_mapping(settings, flavour)
    split: dict[slicer_keys.ProfileSection, dict[str, str]] = {"process": {}}
    placed: set[str] = set()
    for entry in slicer_keys.TABLES[flavour]:
        if entry.key in complete:
            split.setdefault(entry.section, {})[entry.key] = complete[entry.key]
            placed.add(entry.key)
    for key, value in complete.items():
        if key not in placed:
            split["process"][key] = value
    return split


def object_keys(
    settings: PrintSettings, advice: Sequence[SettingAdvice], flavour: SlicerFlavour
) -> dict[str, str]:
    """Die Abweichungen eines Teils in der Sprache des Slicers (§29).

    Übernommen wird die ganze Gruppe, nicht nur der geänderte Wert. Wer die
    Haftungsart auf Brim stellt, braucht auch dessen Breite — und die Maße der
    Arten, die *nicht* gewählt sind, müssen auf null, sonst läuft unter dem
    Teil zusätzlich ein Raft mit (siehe :func:`_only_chosen_adhesion`).

    Dazu, was sich sonst noch geändert hat. Nicht jeder Schlüssel steht in der
    Zuordnungstabelle: die Stützdichte etwa wird für PrusaSlicer und die
    Orca-Familie erst zu einem Linienabstand gerechnet, und über die Gruppe
    allein wäre sie nicht zu finden. Ein Vergleich findet sie, ohne dass
    irgendwo eine zweite Liste gepflegt werden muss.
    """
    if not advice:
        return {}
    groups = {entry.path.partition(".")[0] for entry in advice}
    keys = {
        entry.key for entry in slicer_keys.TABLES[flavour] if entry.path.partition(".")[0] in groups
    }
    before = as_mapping(settings, flavour)
    changed = as_mapping(_applied(settings, advice), flavour)
    return {key: value for key, value in changed.items() if key in keys or before.get(key) != value}


def _applied(settings: PrintSettings, advice: Sequence[SettingAdvice]) -> PrintSettings:
    """Die Einstellungen mit den Abweichungen dieses Teils darin.

    Nicht über :func:`app.core.slice.advise.apply` — der Kern soll von hier
    nach dort nicht abhängen, und es sind zwei Zeilen.
    """
    changed = settings
    for entry in advice:
        changed = with_path(changed, entry.path, entry.value)
    return changed


def _only_chosen_adhesion(
    written: dict[str, str], settings: PrintSettings, flavour: SlicerFlavour
) -> dict[str, str]:
    """Nullt die Maße der Haftungsarten, die nicht gewählt sind.

    ``skirt_loops``, ``brim_width`` und ``raft_layers`` sind Maße *ihrer
    jeweiligen Art*, keine unabhängigen Schalter — aber die Slicer lesen sie
    als solche. Wer alle drei schreibt, bekommt alle drei: ein Raft unter
    einem Teil, für das „Skirt" eingestellt war.

    Das ist kein Schönheitsfehler. Ein ungewollter Raft kostet Material, Zeit
    und die Unterseite des Teils, und er fällt erst auf der Platte auf —
    hier gefunden, weil zwei kleine Teile plötzlich nicht mehr nebeneinander
    passten.
    """
    kind = settings.adhesion.kind
    for wanted, keys in slicer_keys.ADHESION_KEYS[flavour].items():
        if wanted == kind:
            continue
        for key in keys:
            if key in written:
                written[key] = "0"
    return written


def _support_spacing(
    written: dict[str, str], settings: PrintSettings, flavour: SlicerFlavour
) -> dict[str, str]:
    """Die Stützdichte, wo der Slicer sie als Abstand führt (§29).

    Solidon sagt „15 Prozent", Cura auch. PrusaSlicer und die Orca-Familie
    kennen dort keinen Anteil, sondern den Abstand zweier Stützlinien in
    Millimetern — ``support_material_spacing`` beim einen,
    ``support_base_pattern_spacing`` beim anderen. Ohne die Umrechnung war die
    Einstellung für zwei von drei Slicern folgenlos, und der Dialog bot sie
    trotzdem an.

    Gerechnet wie Cura es rechnet: Bahnbreite mal hundert durch Prozent —
    ohne dessen Kreuzungsfaktor, denn beide legen ihre Stützfüllung als *eine*
    Linienschar. Eine Dichte von null heißt „keine Füllung"; der Abstand dazu
    ist keine Zahl, und der Slicer meint mit 0 dasselbe.
    """
    key = {"prusa": "support_material_spacing", "orca": "support_base_pattern_spacing"}.get(flavour)
    if key is None:
        return written
    density = settings.support.density
    written[key] = "0" if density <= 0.0 else f"{settings.layers.line_width / density:g}"
    return written


def _cura_dependants(written: dict[str, str], settings: PrintSettings) -> dict[str, str]:
    """Was ``CuraEngine`` aus einem geschriebenen Wert nicht selbst ableitet (§29).

    ``fdmprinter.def.json`` gibt jeder abgeleiteten Einstellung zweierlei mit:
    einen ``value``-Ausdruck und einen ``default_value``. Das Fenster wertet
    den Ausdruck aus, die Rechenmaschine dahinter nimmt den Vorgabewert.
    Solidons Wert bleibt damit an seinem Schlüssel stehen und erreicht die
    nicht, aus denen gerechnet wird — die Bahnbreite die zwölf Bahnbreiten,
    die Beschleunigung die einundzwanzig Beschleunigungen, die Füllung ihren
    Linienabstand.

    Gemessen an einem 20-mm-Würfel, zweimal derselbe Lauf: **1100 mm Filament
    gegen 818, 753 Sekunden gegen 660.** Ein Drittel zu viel, und der größte
    Posten war ``infill_line_distance``: es blieb bei 2 mm, wo 5,6 gemeint
    waren — also gut vierzig Prozent Füllung statt fünfzehn.

    Die reinen Kopien stehen als Tabelle in
    :data:`app.core.export.slicer_keys.CURA_MIRRORED`. Hier steht, was Cura
    **rechnet** — jede Zeile die Formel aus der Definition, nicht eine eigene
    Meinung darüber, was richtig wäre.
    """
    # Erst rechnen, dann spiegeln: ``support_line_distance`` und
    # ``skin_preshrink`` sind selbst Quellen für weitere Schlüssel.
    _cura_computed(written, settings)
    for source, targets in slicer_keys.CURA_MIRRORED.items():
        copied = written.get(source)
        if copied is not None:
            for target in targets:
                written[target] = copied
    for target, source, factor in slicer_keys.CURA_SCALED:
        number = _as_float(written.get(source))
        if number is not None:
            written[target] = f"{number * factor:g}"
    # Der einzige Wert mit einem Summanden statt einem Faktor — eine eigene
    # Tabellenspalte für einen Fall wäre mehr Aufwand als diese Zeile.
    raft = _as_float(written.get("raft_interface_line_width"))
    if raft is not None:
        written["raft_interface_line_spacing"] = f"{raft + 0.2:g}"
    return written


def _first_layer_width(written: dict[str, str]) -> dict[str, str]:
    """Die erste Bahnbreite ist bei ``CuraEngine`` ein Anteil, kein Maß.

    ``initial_layer_line_width_factor`` will Prozent von ``line_width``.
    Solidon schrieb den Millimeterwert hinein: 0,449 wurde zu 0,449 Prozent,
    und die erste Schicht bekam ein Zweihundertstel der Breite, die sie haben
    sollte. Gemessen an einem Lauf gegen PrusaSlicer, derselbe Würfel.

    Steht hier und nicht in :func:`_cura_dependants`, weil die Gegenprobe den
    umgerechneten Wert sehen muss — sie vergleicht gegen :func:`as_mapping`.
    """
    width = _as_float(written.get("line_width"))
    first = _as_float(written.get("initial_layer_line_width_factor"))
    if width and first:
        written["initial_layer_line_width_factor"] = f"{first / width * 100.0:g}"
    return written


def _cura_computed(written: dict[str, str], settings: PrintSettings) -> None:
    """Die gerechneten Ableitungen — je Zeile die Formel aus der Definition.

    Keine eigene Meinung darüber, was richtig wäre: was hier steht, hätte das
    Cura-Fenster genauso gerechnet, bevor es die Werte weitergibt.
    """
    _from_line_width(written, settings)
    _for_supports(written, settings)
    _for_speeds(written, settings)


def _from_line_width(written: dict[str, str], settings: PrintSettings) -> None:
    """Was Cura aus der Bahnbreite rechnet — der Wert mit den meisten Erben."""
    width = _as_float(written.get("line_width"))
    if not width:
        return
    crossings = slicer_keys.CURA_INFILL_CROSSINGS.get(written.get("infill_pattern", ""), 1.0)
    density = settings.infill.density
    written["infill_line_distance"] = "0" if density <= 0.0 else f"{width * crossings / density:g}"
    # Wie weit die Deckflächen unter die Wände greifen: ``wall_line_width_0 +
    # (n-1) * wall_line_width_x``, und beide Breiten sind hier dieselbe.
    preshrink = width * settings.shell.wall_count
    written["skin_preshrink"] = f"{preshrink:g}"
    written["expand_skins_expand_distance"] = f"{preshrink:g}"
    written["skin_overlap_mm"] = f"{width * _SKIN_OVERLAP / 100.0:g}"
    written["infill_overlap_mm"] = (
        "0" if density >= _DENSE_INFILL else f"{width * _INFILL_OVERLAP / 100.0:g}"
    )
    written["infill_overlap"] = "0" if density >= _DENSE_INFILL else f"{_INFILL_OVERLAP:g}"
    written["skin_support"] = "true" if density < _SKIN_SUPPORT_BELOW else "false"
    written["meshfix_maximum_travel_resolution"] = f"{min(_MAX_RESOLUTION, 2.0 * width):g}"
    # Ab welcher Länge eine Wand als Brücke gilt.
    written["bridge_wall_min_length"] = f"{width + settings.support.xy_gap + 1.0:g}"
    # Beim Bügeln: wie weit die Bahn von der Kante wegbleibt.
    written["ironing_inset"] = f"{width / 2.0 + width * (1.0 - _IRONING_FLOW / 100.0) / 2.0:g}"

    brim = _as_float(written.get("brim_width"))
    first_width = _as_float(written.get("initial_layer_line_width_factor"))
    if brim is not None and first_width:
        # Wie viele Runden ein Brim bekommt. Ohne die Zahl blieben es zwanzig
        # aus der Definition — bei fünf Millimetern Breite fast doppelt so
        # viel Rand, wie eingestellt war.
        strand = width * first_width / 100.0
        written["brim_line_count"] = str(math.ceil(brim / strand)) if strand > 0.0 else "0"
        written["support_brim_width"] = f"{strand * _SUPPORT_BRIM_LINES:g}"
        written["support_brim_line_count"] = f"{_SUPPORT_BRIM_LINES:g}"
        written["support_brim_minimum_hole_area"] = f"{width * width * 100.0:g}"

    # Die Außenwand rückt nach innen, wenn sie schmaler ist als die Düse —
    # außer sie wird zuerst gefahren, dann liegt sie ohnehin auf Maß.
    diameter = _as_float(written.get("machine_nozzle_size"))
    if diameter and width < diameter and not settings.shell.outer_wall_first:
        written["wall_0_inset"] = f"{(diameter - width) / 2.0:g}"
    else:
        written["wall_0_inset"] = "0"


def _for_supports(written: dict[str, str], settings: PrintSettings) -> None:
    """Die Stützen. Ihre Schnittstelle ist bei Cura eine Höhe, keine Schichtzahl."""
    width = _as_float(written.get("line_width"))
    density = settings.support.density
    if width:
        distance = width * slicer_keys.CURA_SUPPORT_CROSSINGS / density if density > 0.0 else 0.0
        written["support_line_distance"] = f"{distance:g}"
        # Auf den eben gerechneten Abstand, nicht noch einmal auf die Breite:
        # zwei Formeln für dieselbe Sache laufen irgendwann auseinander.
        written["support_zag_skip_count"] = (
            "0" if distance <= 0.0 else str(round(_SUPPORT_SKIP_PER_MM / distance))
        )
        # Die Schnittstelle steht bei Cura auf voller Dichte; ihr Linienabstand
        # ist dann genau eine Bahnbreite.
        for key in ("support_roof_line_distance", "support_bottom_line_distance"):
            written[key] = f"{width:g}"
        # Die Stütze wächst um eine Bahnbreite plus Curas festen Zuschlag —
        # beim Baum um nichts.
        tree = settings.support.style == "tree"
        written["support_offset"] = "0" if tree else f"{width + _SUPPORT_GROWTH:g}"
        written["support_wall_count"] = "1" if tree else "0"

    # Ohne den Schalter entsteht gar keine Schnittstelle, und ohne die Höhe
    # wurden aus zwei Schichten zwei Millimeter — das Zehnfache bei 0,2ern.
    layers = settings.support.interface_layers
    written["support_interface_height"] = f"{layers * settings.layers.layer_height:g}"
    for key in ("support_interface_enable", "support_roof_enable", "support_bottom_enable"):
        written[key] = "true" if layers > 0 else "false"
    written["support_bottom_stair_step_height"] = "0" if layers > 0 else f"{_STAIR_STEP:g}"
    written["support_tree_top_rate"] = "30" if layers > 0 else "10"
    written["support_tree_rest_preference"] = (
        "buildplate" if settings.support.placement == "build_plate" else "graceful"
    )
    # Der Baum bekommt seinen eigenen Winkel, gedeckelt wie in der Definition.
    angle = settings.support.threshold_angle
    written["support_tree_angle"] = f"{max(min(angle, 85.0), 20.0):g}"


def _for_speeds(written: dict[str, str], settings: PrintSettings) -> None:
    """Geschwindigkeiten, Temperaturen und die Schalter, ohne die sie nicht gelten."""
    # Ohne diesen gelten weder die Brückengeschwindigkeit noch der
    # Brückenlüfter — beide stehen in Cura dahinter, und Solidon schreibt beide.
    written["bridge_settings_enabled"] = "true"
    # Beide Muster, die Cura für Solidons Füllungen ausrechnet, fallen auf
    # dieselbe Antwort: ``cross`` und ``cubicsubdiv`` werden hier nicht
    # angeboten.
    written["connect_infill_polygons"] = "false"
    written["skirt_height"] = "3" if settings.adhesion.skirt_distance > 0.0 else "1"
    written["acceleration_travel_layer_0"] = f"{_TRAVEL_ACCELERATION:g}"

    printing = _as_float(written.get("speed_print"))
    if printing:
        # ``speed_support_interface = speed_support / 1.5``, und die beiden
        # Seiten der Schnittstelle erben davon.
        interface = f"{printing / 1.5:g}"
        for key in ("speed_support_interface", "speed_support_roof", "speed_support_bottom"):
            written[key] = interface
        first_layer = _as_float(written.get("speed_layer_0"))
        travel = _as_float(written.get("speed_travel"))
        if first_layer and travel:
            written["speed_travel_layer_0"] = f"{first_layer * travel / printing:g}"

    surface = _as_float(written.get("speed_topbottom"))
    if surface:
        written["speed_ironing"] = f"{surface * 20.0 / 30.0:g}"

    nozzle = _as_float(written.get("material_print_temperature"))
    if nozzle:
        # Curas Vorgabe fährt die Düse vor dem ersten und nach dem letzten
        # Zug etwas kühler. Nachgerechnet, nicht überstimmt.
        written["material_initial_print_temperature"] = f"{nozzle - 10.0:g}"
        written["material_final_print_temperature"] = f"{nozzle - 15.0:g}"


def _as_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _machine_keys(profile: Profile, flavour: SlicerFlavour) -> dict[str, str]:
    """Was der Slicer über die Maschine wissen muss, wenn kein Profil greift.

    Für ``prusa`` ist eine ``.ini`` eigenständig lauffähig, sobald Düse und
    Bettform darin stehen. Orca lädt ein Maschinenprofil aus seinem Bestand,
    und dem hier hineinzureden hieße, seine Anfahrwege und seinen Startcode
    zu überschreiben.

    ``cura`` stand lange bei Orca, und das war falsch: ``CuraEngine`` ist
    nicht die Kommandozeile eines Slicers, sondern die Rechenmaschine hinter
    dem Fenster. Sie löst keine Vererbung auf — was das Fenster sonst aus
    Definition, Qualität, Material und Variante zusammenrechnet, muss ihr
    einzeln mitgegeben werden. Ohne Bettmaße rechnete sie einen G-Code, in
    dessen Kopf ``MINX:2.14748e+06`` stand: der Grenzwert eines Ganzzahltyps,
    also gar keine Angabe.
    """
    if flavour == "cura":
        width, depth, height = profile.printer.build_volume
        return {
            "machine_width": f"{width:g}",
            "machine_depth": f"{depth:g}",
            "machine_height": f"{height:g}",
            "machine_nozzle_size": f"{profile.printer.nozzle_diameter:g}",
            # Solidon rechnet um den Ursprung, hier wie bei Prusa.
            "machine_center_is_zero": "true",
            # Wo „hinten" liegt, wenn die Naht dorthin soll. Cura sucht den
            # Konturpunkt, der diesem hier am nächsten liegt; ohne die Angabe
            # stünde er bei (100, 100) und damit rechts hinten statt hinten.
            # Gelesen wird er nur bei ``z_seam_type=back``, geschrieben immer:
            # ein Punkt, den niemand abfragt, kostet nichts.
            "z_seam_x": "0",
            "z_seam_y": f"{depth / 2.0:g}",
            "machine_heated_build_volume": "true" if profile.printer.enclosed else "false",
            # Einstellungen, die `CuraEngine` abfragt und in keiner Definition
            # findet, die es geladen hat — das Fenster füllt sie aus Qualitäts-
            # und Materialprofil. Ohne sie bricht der Lauf mit „Trying to
            # retrieve setting with no value given" ab, bevor er die erste
            # Schicht ansieht.
            #
            # Die beiden Stützwerte sind teuer erkauft: mit eingeschalteten
            # Stützen endete `grid` in einer Speicherzugriffsverletzung und
            # `tree` ohne jede Datei. Solidon meldete beides als „der Slicer
            # hat das Modell nicht verarbeitet" — richtig, aber ratlos.
            "roofing_layer_count": "0",
            "flooring_layer_count": "0",
            "support_z_seam_away_from_model": "false",
            "min_wall_line_width": f"{profile.printer.nozzle_diameter * 0.85:g}",
            # Und einer, ohne den zwei geschriebene Werte nicht gelten:
            # ``CuraEngine`` rechnet ohne ihn mit ``machine_acceleration``
            # weiter und übergeht `acceleration_print` und
            # `acceleration_wall_0`, die daneben stehen.
            "acceleration_enabled": "true",
        }
    if flavour != "prusa":
        return {}
    printer = profile.printer
    width, depth, height = printer.build_volume
    # Um den Ursprung, nicht ab der Ecke: Solidon rechnet zentriert — die
    # Anordnung beginnt bei ``-width/2`` (siehe ``arrange_on_bed``), und ein
    # exportierter Körper steht bei x -30..30. Ein Bett von 0 bis 256 liegt
    # daneben, und PrusaSlicer sagte dazu „All objects are outside of the
    # print volume" und schrieb nichts. Die Bettform beschreibt hier dieselbe
    # Welt wie die Koordinaten, die mit ihr kommen.
    half_width, half_depth = width / 2.0, depth / 2.0
    corners = (
        f"{-half_width:g}x{-half_depth:g},{half_width:g}x{-half_depth:g},"
        f"{half_width:g}x{half_depth:g},{-half_width:g}x{half_depth:g}"
    )
    return {
        "nozzle_diameter": f"{printer.nozzle_diameter:g}",
        "bed_shape": corners,
        "max_print_height": f"{height:g}",
    }


@dataclass(frozen=True, slots=True)
class SlicerConfig:
    """Die Profildateien für einen Lauf.

    ``process`` trägt bei ``prusa`` und ``cura`` alles; bei der Orca-Familie
    stehen daneben die ``filaments``, weil sie Werte nur aus dem Profil annimmt,
    in das sie gehören.

    **Mehrzahl, nicht Einzahl.** Ein Modell hat so viele Filamente wie
    Materialslots (§20), und die sind nicht dasselbe: ein Schriftzug in Weiß
    auf einem Gehäuse in Schwarz sind zwei Spulen mit zwei Temperaturen. Solange
    hier eine Datei stand, bekam der Slicer für jeden Slot dasselbe Filament —
    und die zweite Farbe fuhr mit den Werten der ersten.
    """

    process: Path
    filaments: tuple[Path, ...] = ()
    machine: Path | None = None

    @property
    def filament(self) -> Path | None:
        """Das erste Filament. Für alles, was nur eines kennt."""
        return self.filaments[0] if self.filaments else None


def settings_for_slot(settings: PrintSettings, override: SlotOverride | None) -> PrintSettings:
    """Die Einstellungen, mit denen dieser eine Slot fährt (§20, §29).

    Vier Spulen sind nicht vier Farben desselben Materials: Ein Schriftzug in
    PLA auf einem Gehäuse aus PETG fährt 210 Grad statt 250. Ohne diese
    Auflösung bekamen alle Slots die Werte des Projektmaterials, und die
    zweite Spule fuhr mit den Temperaturen der ersten.

    Übersteuert wird **gruppenweise**: Was der Slot nicht setzt, kommt aus dem
    Projekt. Ein leerer Übersteuerer gibt die Einstellungen unverändert
    zurück — dasselbe Objekt, nicht eine gleiche Kopie, damit der häufige Fall
    nichts kostet.
    """
    if override is None or override.empty:
        return settings
    return replace(
        settings,
        temperature=override.temperature or settings.temperature,
        cooling=override.cooling or settings.cooling,
        retraction=override.retraction or settings.retraction,
        filament=override.filament or settings.filament,
    )


def unreachable_overrides(
    settings: PrintSettings,
    setup: SlicerSetup,
    slots: Sequence[MaterialSlot] = (),
) -> list[Finding]:
    """Meldet Werte je Spule, die dieser Slicer nicht entgegennimmt (§20, §29).

    Nur die Orca-Familie bekommt ein Filamentprofil **je Slot**
    (``--load-filaments`` nimmt mehrere). PrusaSlicer bekommt eine ``.ini``
    und ``CuraEngine`` einen Satz Schlüssel — beide kennen genau ein Filament,
    und was für den zweiten Slot eingestellt wurde, fällt weg.

    Es fällt still weg, und das ist der Grund für diese Meldung: Der Kunde
    hat die Temperatur seiner zweiten Spule gesetzt, sieht sie im Dialog
    stehen und bekäme einen Druck, der sie nicht verwendet. Ein Fehler ist es
    nicht — der Slicer kann nicht mehr —, aber eine Auskunft schon
    (Regel 17: mit Handlungsvorschlag, nicht mit „fehlgeschlagen").
    """
    if has_filament_profiles(setup.flavour):
        return []
    reachable = (slots[0].name, slots[0].colour) if slots else None
    present = {(slot.name, slot.colour) for slot in slots}
    affected = [
        position
        for position, entry in enumerate(settings.slot_overrides)
        if entry is not None
        and not entry.empty
        and (not present or entry.key in present)
        and (reachable is None or entry.key != reachable)
    ]
    if not affected:
        return []
    return [
        Finding(
            code="slicer.overrides_unreachable",
            severity="warning",
            message=_(
                "Dieser Slicer nimmt nur einen Satz Filamentwerte. Was für die "
                "weiteren Filamente eingestellt ist, wird nicht gedruckt — dafür "
                "braucht es einen Slicer der Orca-Familie, etwa OrcaSlicer oder "
                "Bambu Studio."
            ),
            values={"slots": len(affected), "slicer": setup.name},
        )
    ]


def override_for(settings: PrintSettings, slot: MaterialSlot) -> SlotOverride | None:
    """Der Übersteuerer dieses Filaments, wenn es einen gibt (§20).

    Gesucht wird über die **Identität** — Name und Farbe, derselbe Schlüssel
    wie in :func:`app.core.export.threemf.merge_slots` —, nicht über die
    Position in der Liste. Der Grund steht bei :class:`SlotOverride`: Was der
    Dialog zeigt und was ein Plattenlauf fährt, sind zwei verschiedene
    Reihenfolgen, und positionsweise landete die Temperatur der einen Spule
    auf der anderen.

    Ohne Eintrag gilt das Projekt. Das ist der Normalfall — ein einfarbiges
    Teil hat gar keine.
    """
    for entry in settings.slot_overrides:
        if entry is not None and entry.key == (slot.name, slot.colour):
            return entry
    return None


def with_slot_override(
    settings: PrintSettings,
    slot: MaterialSlot,
    override: SlotOverride | None,
) -> PrintSettings:
    """Setzt oder entfernt die eigenen Werte eines Filaments (§20, §29).

    Der Schlüssel ist Name und Farbe, nicht die Position. Die Oberfläche zeigt
    die Zusammenlegung aller gewählten Platten, ein einzelner Slicerlauf kann
    dieselben Filamente in einer anderen Reihenfolge führen. Ein positionsweiser
    Austausch gäbe dann wieder der falschen Spule die Temperatur.

    Ein leerer oder entfernter Übersteuerer reist nicht als Platzhalter mit.
    Das hält alte Projekte klein und macht ``None`` weiterhin eindeutig:
    Dieses Filament benutzt die Projektwerte.
    """
    key = (slot.name, slot.colour)
    kept = tuple(
        entry
        for entry in settings.slot_overrides
        if entry is not None and entry.key != key and not entry.empty
    )
    if override is None or override.empty:
        return replace(settings, slot_overrides=kept)
    identified = replace(override, name=slot.name, colour=slot.colour)
    return replace(settings, slot_overrides=(*kept, identified))


def settings_for_shared_slicer(
    settings: PrintSettings, slots: Sequence[MaterialSlot]
) -> PrintSettings:
    """Der eine Filamentwertsatz für einen Slicer ohne Mehrfachprofile.

    PrusaSlicer und CuraEngine nehmen auf diesem Weg genau einen Satz an. Der
    gehört dem ersten Extruder der Platte; weitere Filamente werden gesondert
    als nicht erreichbar gemeldet. Ohne Slot bleibt es bei den Projektwerten.
    """
    if not slots:
        return settings
    return settings_for_slot(settings, override_for(settings, slots[0]))


def settings_for_handover(
    settings: PrintSettings,
    flavour: SlicerFlavour,
    slots: Sequence[MaterialSlot] = (),
) -> PrintSettings:
    """Der Satz, den dieser Slicer auf seinem Übergabeweg wirklich erhält.

    Die Orca-Familie nimmt ein Profil je Spule und behält deshalb die
    Projektwerte als gemeinsame Grundlage. PrusaSlicer und CuraEngine nehmen
    genau einen Satz; dort gewinnt die erste Spule. Schreiben und Gegenprobe
    benutzen diese eine Funktion, damit ein richtig übernommener Spulenwert
    nicht anschließend als Abweichung gemeldet wird.
    """
    if has_filament_profiles(flavour):
        return settings
    return settings_for_shared_slicer(settings, slots)


def with_slot_profiles(
    slots: Sequence[MaterialSlot], chosen: Sequence[str]
) -> tuple[MaterialSlot, ...]:
    """Heftet die im Dialog gewählten Filamentprofile an die Slots (§20).

    ``chosen`` ist ``PrintSettings.slot_profiles``: je Extrudernummer ein
    Profilname. Gelesen wird deshalb :attr:`MaterialSlot.index` und nicht die
    Lage in ``slots`` — eine einzeln exportierte Platte kann nur Extruder 2
    enthalten und darf dadurch nicht das Profil von Extruder 1 bekommen. Wo
    nichts steht, bleibt der Slot, wie er ist; dann gilt das Filament der
    Platte.

    Diese Zuordnung ist das Stück, das fehlte: Der Dialog sammelte die Wahl
    ein und meldete „druckt mit", ``write_config`` war auf
    ``MaterialSlot.material`` vorbereitet — nur gesetzt hat es niemand, und
    alle Slots slicten mit dem Basisfilament.
    """
    return tuple(
        replace(entry, material=chosen[entry.index])
        if 0 <= entry.index < len(chosen) and chosen[entry.index]
        else entry
        for entry in slots
    )


def _single_line(text: str) -> bool:
    """Ob der Text keinen Zeilentrenner enthält — auch keinen abwegigen.

    Gemessen wird mit ``splitlines()`` und nicht gegen eine Liste von Zeichen,
    denn genau ``splitlines()`` liest der Cura-Zweig die Werte später wieder
    ein (:func:`_command`). Was dort trennt, muss hier auffallen — und das ist
    mehr als Wagenrücklauf und Zeilenvorschub: Vertikaltabulator,
    Seitenvorschub, die vier Trennzeichen der Zeichensatzsteuerung und drei
    weitere Unicode-Zeilentrenner zählen für Python ebenso dazu.
    """
    return text.splitlines() == [text] if text else True


def _one_line(text: str) -> str:
    """Bringt einen schmückenden Text auf eine Zeile.

    Gilt nur für Texte, die als **Kommentar** in eine Konfigurationsdatei
    gehen. Dort ist der Umbruch bedeutungstragend, der Text selbst aber nicht:
    Ein Titel aus einer fremden Projektdatei, der einen Umbruch trägt,
    schriebe sonst eine zweite Zeile — und die liest der Slicer als
    Einstellung. ``post_process`` stünde dann in einer Datei, in die Solidon
    ihn nie geschrieben hat.

    Für **Werte** ist Bereinigen der falsche Weg; dort hält
    :func:`_without_line_break` an, statt eine Druckeinstellung stillschweigend
    zu verändern.
    """
    return " ".join(text.splitlines())


def _without_line_break(values: Mapping[str, str], setup: SlicerSetup) -> None:
    """Hält an, wenn ein Einstellungswert einen Zeilenumbruch enthält (§28).

    Eine Slicer-Konfiguration trennt ihre Einträge mit Zeilenumbrüchen, und der
    Cura-Zweig liest sie danach mit ``splitlines()`` wieder ein: Ein Umbruch
    mitten in einem Wert macht aus einem Eintrag zwei, und der zweite steht
    dort, ohne dass Solidon ihn geschrieben hätte. Die Werte kommen unter
    anderem aus der geöffneten Projektdatei, sind also fremder Herkunft — genau
    dieser Weg war der Befund der Sicherheitsdurchsicht vom 04.09.2026.

    **Abgelehnt statt bereinigt, wie beim Trenner im Profilpfad.** Einen Wert
    still zu ändern hieße, eine Druckeinstellung zu verändern, ohne es zu sagen
    (Regel 21) — und für einen Umbruch in einem Slicer-Wert ist nirgends
    zugesagt, wie man ihn maskiert.

    Der Fall kann im normalen Betrieb nicht auftreten: Die Schemaprüfung der
    Projektdatei weist Steuerzeichen schon beim Öffnen ab
    (:func:`app.core.scene.project._validate_print_settings`). Diese Prüfung
    ist die Gegenprobe an der Stelle, an der es darauf ankommt.
    """
    marked = sorted(key for key, value in values.items() if not _single_line(value))
    if not marked:
        return
    raise ExternalToolError(
        tool=setup.name,
        detail=_(
            "Eine Druckeinstellung enthält einen Zeilenumbruch. In einer "
            "Slicer-Konfiguration trennt der die Einträge und ergäbe eine "
            "Einstellung, die niemand gesetzt hat."
        ),
        # ``setting`` und nicht ``key``: Jeder Wertschlüssel eines Befunds
        # braucht eine Beschriftung in ``ui.labels._VALUE_NAMES``, sonst steht
        # der rohe Bezeichner im Tooltip des Kunden.
        # ``tests/test_value_labels.py`` hat genau das gefangen — und
        # ``setting`` ist dort seit je als „Einstellung" beschriftet, trifft
        # die Sache also besser als ein neuer Eintrag in fünf Katalogen.
        values={"setting": ", ".join(marked)},
        suggestions=(OPEN_SETTINGS, CANCEL),
    )


def write_config(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    directory: Path,
    slots: Sequence[MaterialSlot] = (),
) -> SlicerConfig:
    """Schreibt die Profile, die der Slicer gleich lädt.

    ``slots`` sind die Materialslots der Platte (§20). Je Slot entsteht ein
    Filamentprofil, denn ein Slot *ist* ein Filament — zwei Farben sind zwei
    Spulen, und die fahren verschieden. Trägt ein Slot einen eigenen
    Profilnamen (``MaterialSlot.material``), wird der als Unterlage genommen;
    sonst gilt für alle das eine aus dem ``setup``.
    """
    setup = replace(setup, machine_profile=machine_for(setup, profile))

    # Gerechnet wird in dem Zweig, der es braucht: Die Orca-Familie schreibt
    # ihre Werte aus ``by_section`` und ``_orca_*``, nicht aus dieser Abbildung
    # — sie stand hier und lief bei jedem Lauf mit, ohne gelesen zu werden.
    def flat_values() -> dict[str, str]:
        """Alles, was ein Slicer als einen Satz Schlüssel bekommt."""
        return values_for(
            settings_for_handover(settings, setup.flavour, slots), profile, setup.flavour
        )

    if setup.flavour == "prusa":
        target = directory / "solidon.ini"
        # Der Titel wird auf eine Zeile gebracht, die Werte werden geprüft: In
        # einer INI trennt der Umbruch die Einträge, und der Titel kommt aus
        # der Projektdatei. Ein Umbruch darin schrieb sonst eine zweite Zeile,
        # die PrusaSlicer als Einstellung liest — mit ``post_process`` als
        # Befehl, den niemand gesetzt hat.
        flat = flat_values()
        _without_line_break(flat, setup)
        lines = [f"# {_one_line(settings.title)} — von Solidon geschrieben, nicht von Hand"]
        lines += [f"{key} = {value}" for key, value in sorted(flat.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SlicerConfig(process=target)

    if setup.flavour == "orca":
        split = by_section(settings, setup.flavour)
        # Das Maschinenprofil zuerst: Der Prozess daneben nennt es in
        # ``compatible_printers``, und beide Namen kommen aus
        # ``_machine_name``.
        machine_target = directory / "solidon_machine.json"
        machine_target.write_text(
            json.dumps(_orca_machine(setup), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        target = directory / "solidon_process.json"
        target.write_text(
            json.dumps(
                _orca_process(split.get("process", {}), settings, setup),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # Je Slot eine Datei. Ohne Slots bleibt es bei einer — der einfarbige
        # Druck ist der Sonderfall mit einem Eintrag, nicht ein anderer Weg.
        #
        # **Die Reihenfolge ist die der Liste, nicht ``MaterialSlot.index``.**
        # ``--load-filaments`` macht aus ihr die Extruderbelegung des Laufs, und
        # hierher kommt die Belegung **einer Platte**: Der Dialog legt sie mit
        # ``merge_slots`` ohne ``across`` zusammen, also lückenlos ab null. Die
        # Lückenfüllung aus :func:`app.core.export.threemf.by_extruder` gehört
        # deshalb auf den anderen Weg — die 3MF und ihre Beilage
        # (:func:`project_settings`) tragen die Nummern des ganzen Auftrags.
        written: list[Path] = []
        for index, slot in enumerate(slots or (MaterialSlot(index=0, name=""),)):
            own = replace(setup, base_filament=slot.material) if slot.material else setup
            # Je Slot seine eigenen Werte: Temperaturen, Kühlung,
            # Rückzug und Materialkennwerte dürfen sich unterscheiden,
            # denn sie hängen an der Spule. Was der Slot nicht setzt,
            # kommt aus dem Projekt — deshalb wird die Aufteilung hier
            # noch einmal gerechnet und nicht die von oben genommen.
            mine = settings_for_slot(settings, override_for(settings, slot))
            part = split if mine is settings else by_section(mine, setup.flavour)
            path = directory / f"solidon_filament_{index}.json"
            path.write_text(
                json.dumps(
                    _orca_filament(part.get("filament", {}), mine, profile, own, slot),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            written.append(path)
        return SlicerConfig(process=target, filaments=tuple(written), machine=machine_target)

    target = directory / "solidon_cura.txt"
    # Hier wiegt der Umbruch schwerer als bei Prusa: ``_command`` liest diese
    # Datei mit ``splitlines()`` zurück und macht aus jeder Zeile ein eigenes
    # ``-s``-Argument. Eine zweite Zeile wäre damit ein zusätzliches Argument
    # für CuraEngine.
    flat = flat_values()
    _without_line_break(flat, setup)
    target.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(flat.items())) + "\n",
        encoding="utf-8",
    )
    return SlicerConfig(process=target)


def project_settings(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    extruders: int = 1,
    slots: Sequence[MaterialSlot] = (),
) -> dict[str, object]:
    """Die Einstellungen einer Platte, wie eine Orca-Projektdatei sie führt.

    Dieselben Werte wie in :func:`write_config`, nur in *einer* Abbildung statt
    in zwei Dateien: eine 3MF trennt Prozess und Filament nicht, sie hat einen
    Satz Schlüssel. Damit trägt die exportierte Datei ihre Temperaturen,
    Geschwindigkeiten und Kühlung selbst — sonst öffnet der Slicer sie mit dem
    Profil, das gerade eingestellt ist, und was Solidon über dieses Teil weiß,
    ist beim Öffnen weg.

    Aufgesetzt wird auf den Bestand des Slicers, nicht auf Erfundenes: das
    benannte System-Prozessprofil und -Filamentprofil werden gelesen, Solidons
    Werte kommen darüber. Was Solidon nicht anfasst, bleibt so, wie der
    Hersteller es abgestimmt hat (§29).

    Die Filamentschlüssel werden zu **Listen**, einer je Extruder — so führt
    das Format sie, und ein blanker String kommt in der Oberfläche als leeres
    Feld an.
    """
    if not reads_settings_from_project_file(setup.flavour):
        # Cura bekommt sie über die Kommandozeile, PrusaSlicer über seine INI.
        return {}

    # Vor den Grundlagen: Steht keine Maschine, fragt :func:`machine_for` den
    # Slicer — und übernimmt nur, was derselbe Drucker ist.
    setup = replace(setup, machine_profile=machine_for(setup, profile))

    split = by_section(settings, setup.flavour)

    # Eine Projektdatei trägt kein ``inherits`` — sie muss die Werte
    # ausgeschrieben enthalten. Die Erbkette wird deshalb **aufgelöst**, für
    # Maschine wie Prozess, nicht nur die oberste Datei gelesen.
    #
    # Das ist der Unterschied zu ``write_config``: dort bekommt der Slicer eine
    # Profildatei und löst selbst auf. Hier bekommt er ein Projekt, und was
    # darin fehlt, füllt er aus dem Profil, das gerade eingestellt ist. Genau
    # das ist passiert: von 546 Schlüsseln standen 122 in der Datei, der Rest
    # kam aus der Auswahl des Nutzers — die 3MF sagte drei Wände, gedruckt
    # wurden zwei, und der Unterschied waren 127 Gramm.
    document: dict[str, object] = {}
    foundations: tuple[tuple[slicer_profiles.ProfileKind, str], ...] = (
        ("machine", setup.machine_profile),
        ("process", setup.base_process),
    )
    for kind, chosen in foundations:
        found = profile_file(chosen, setup, kind)
        if found is not None:
            document.update(slicer_profiles.resolve_values(found))

    document.update(_orca_process(split.get("process", {}), settings, setup))
    document.update(_machine_keys(profile, setup.flavour))

    for key in ("type", "instantiation", "inherits"):
        document.pop(key, None)

    # Jeder Materialslot ist ein Filament. Die Beilage führt dessen Werte als
    # Listen, in Extruderreihenfolge. Bisher wurde ein gemeinsamer Satz nur
    # vervielfacht; eine PLA-Schrift auf PETG trug damit zwar Weiß als Farbe,
    # aber 240 statt 210 Grad als Temperatur.
    #
    # **Über die Extrudernummer, nicht über die Position in der Liste.** Eine
    # Platte, die eine frühere Farbe des Auftrags auslässt, hat eine Lücke
    # (``threemf.by_extruder``); ohne sie stünde die Farbe der zweiten Spule an
    # erster Stelle und widerspräche der Geometrie derselben Datei.
    placed = threemf.by_extruder(slots)
    count = max(1, extruders, len(placed))
    ordered_slots: tuple[MaterialSlot | None, ...] = tuple(placed) + (None,) * (count - len(placed))
    filament_documents: list[dict[str, object]] = []
    for slot in ordered_slots:
        mine = (
            settings if slot is None else settings_for_slot(settings, override_for(settings, slot))
        )
        own = (
            replace(setup, base_filament=slot.material)
            if slot is not None and slot.material
            else setup
        )
        slot_values = by_section(mine, setup.flavour).get("filament", {})
        filament_documents.append(_orca_filament(slot_values, mine, profile, own, slot))

    filament_keys = sorted(
        set().union(*(set(entry) - slicer_profiles.DESCRIBING_KEYS for entry in filament_documents))
    )

    def scalar(value: object) -> object:
        """Ein Einzelwert aus der Ein-Filament-Darstellung."""
        if isinstance(value, list) and len(value) == 1:
            return value[0]
        return value

    resolved: dict[str, object] = dict(document)
    for key in filament_keys:
        filament_values = [entry.get(key, "") for entry in filament_documents]
        vectors = [
            value for value in filament_values if isinstance(value, list) and len(value) != 1
        ]
        if vectors:
            # Listen mit null oder mehreren Einträgen beschreiben **einen**
            # Profilwert und keine Extruderbelegung. Sind sie überall gleich,
            # bleibt die gültige flache Form erhalten. Verschiedene Vektoren
            # kann das Projektformat nicht je Extruder ausdrücken; dann wird
            # der Schlüssel weggelassen, statt eine ungültige verschachtelte
            # Liste zu erfinden, die der Slicer still verwirft.
            stated = [value for value in filament_values if value not in ("", [])]
            if not stated:
                resolved[key] = []
            elif all(value == stated[0] for value in stated):
                resolved[key] = stated[0]
            else:
                _log.warning("not writing incompatible multi-value filament key %s", key)
            continue
        resolved[key] = [scalar(value) for value in filament_values]

    # Erst nach der Umwandlung: das hier sind Angaben *über* die Datei, keine
    # Werte je Extruder. Als Liste geschrieben liest der Slicer sie nicht.
    resolved["from"] = "project"
    resolved["name"] = "project_settings"

    # Woran der Slicer erkennt, wofür diese Werte gelten. Ohne sie lädt er
    # seine eigene Auswahl darunter, und was hier nicht ausdrücklich steht,
    # kommt aus einem Profil, das niemand gewählt hat.
    #
    # Als **Namen**, nie als Pfade: Die Oberfläche merkt sich Profile als
    # Pfade, und unverändert durchgereicht stand `C:\Program Files\…` in
    # einer Datei, die weitergegeben wird (Regel 12) — und die Orca-Familie
    # trifft mit einem Pfad ohnehin kein Preset. Prozess und Filament tragen
    # den Solidon-Namen, unter dem `write_config` sie wirklich schreibt:
    # unter dem Namen eines Systemprofils lüde der Slicer sein eigenes
    # darunter — die Verwechslung, die einen Satz Gewürzbehälter gekostet
    # hat.
    if setup.machine_profile:
        resolved["printer_settings_id"] = _profile_name(setup.machine_profile)
    resolved["print_settings_id"] = f"Solidon {settings.title}"
    resolved["filament_settings_id"] = [
        str(entry.get("name", f"Solidon {settings.title}")) for entry in filament_documents
    ]
    resolved.setdefault("printer_model", profile.printer.title)
    resolved.setdefault("nozzle_diameter", [str(profile.printer.nozzle_diameter)])
    return resolved


def _profile_name(reference: str) -> str:
    """Der Name eines Profils — gleich, ob ein Name oder ein Pfad kam.

    Beschnitten wird nur, was wie eine Profildatei endet: ``.stem`` auf
    „0.12mm Fine @Elegoo CC2 0.4 nozzle" schnitte mitten ins Maß, denn dort
    ist der letzte Punkt Teil des Namens.
    """
    candidate = Path(reference)
    if candidate.suffix.lower() in (".json", ".ini"):
        return candidate.stem
    return reference


def _machine_name(setup: SlicerSetup) -> str:
    """Der Name, unter dem Solidons eigenes Maschinenprofil läuft.

    An einer Stelle festgelegt, weil zwei Dateien ihn brauchen: Das
    Maschinenprofil trägt ihn als ``name``, das Prozessprofil daneben als
    ``compatible_printers``. Gehen die beiden auseinander, nimmt der Slicer
    den Auftrag nicht an, und die Meldung nennt den Drucker — nicht die
    Ursache.
    """
    printer = _profile_name(setup.machine_profile) if setup.machine_profile else ""
    return f"Solidon {printer}" if printer else "Solidon"


def _orca_machine(setup: SlicerSetup) -> dict[str, object]:
    """Das Maschinenprofil für die Orca-Familie — ausgeschrieben.

    Bisher bekam der Slicer hier den **Namen** eines Profils aus seinem
    eigenen Bestand, und alles Weitere löste er selbst auf. Das ging, solange
    der Bestand stimmte: Gemessen am Elegoo-Profil ``Elegoo Centauri 0.2
    nozzle`` stehen sechzehn Schlüssel in der Datei und dreiundachtzig im
    Lauf. Die übrigen siebenundsechzig — Anfahrcode, Maschinengrenzen,
    Rückzug — kamen aus einer Erbkette, die dem Slicer gehört.

    Jetzt schreibt Solidon sie aus. Der Gewinn ist nicht Genauigkeit, denn
    beide Wege ergeben dieselben Werte, sondern **Unabhängigkeit**: Die
    Übergabe steht auch dann, wenn der Drucker im Bestand anders heißt, das
    Herstellerprofil sich mit einem Update verschiebt oder der Anwender einen
    anderen Slicer derselben Familie führt. Für einen Bambu-Drucker mit
    Bambu Studio läuft derselbe Code — es ist dieselbe Familie, und Solidon
    fragt nichts mehr aus ihrem Bestand ab, was es nicht selbst mitgibt.

    **Der Anfahrcode bleibt der des Herstellers** (Entscheidung Robert,
    26.08.2026). Er wird übernommen, nicht erzeugt und nicht verändert: Was
    ein Drucker beim Start tut — Düse säubern, Bett vermessen, Naht
    anlegen —, weiß der Hersteller, und ein selbstgeschriebener Ablauf wäre
    eine Zusage, die Solidon nicht halten kann.
    """
    document: dict[str, object] = {
        "type": "machine",
        # **CLI-Kategorie, keine Herkunftsbehauptung.** ElegooSlicer 1.5.3.4
        # behandelt ein Maschinenprofil mit ``from: User`` als unverknüpften
        # Einzelwert. Ein daneben geladenes Prozessprofil bleibt dann selbst
        # bei einer wörtlich passenden ``compatible_printers``-Angabe
        # unvereinbar; der Lauf endet mit Code -17 und ohne Druckdatei.
        # ``system`` lässt den CLI-Leser das vollständig ausgeschriebene
        # Profil in seine Verträglichkeitsprüfung aufnehmen. Der eigene Name
        # und die aufgelösten Werte weisen weiterhin aus, was Solidon schrieb.
        "from": "system",
        "instantiation": "true",
    }
    base = profile_file(setup.machine_profile, setup, "machine")
    if base is not None:
        # ``resolve_values`` lässt die beschreibenden Schlüssel weg
        # (``inherits``, ``name``, ``type`` …). Genau richtig: Das Profil
        # soll keinen fremden Namen tragen und nichts nachladen.
        document.update(slicer_profiles.resolve_values(base))
    # Nach dem Auffüllen, damit kein geerbter Wert ihn überschreibt.
    document["name"] = _machine_name(setup)
    return document


def _orca_process(
    values: dict[str, str],
    settings: PrintSettings,
    setup: SlicerSetup,
) -> dict[str, object]:
    """Das Prozessprofil für die Orca-Familie.

    Diese Slicer nehmen kein Prozessprofil an, das nicht zum Drucker passt —
    sie brechen mit „process not compatible with printer" ab, bevor sie das
    Modell überhaupt ansehen. Die Kompatibilität steht in Feldern, die
    Solidon nicht kennt und nicht erfinden sollte (``compatible_printers``,
    ``inherits``, die Düsenbindung).

    Also wird nichts erfunden: das benannte Systemprofil wird gelesen und die
    Solidon-Werte kommen darüber. Was Solidon nicht anfasst, bleibt genau so
    stehen, wie der Hersteller es abgestimmt hat — das ist die Aufteilung aus
    §29 in einer Datei.
    """
    # Die beschreibenden Schlüssel zuerst, weil ``resolve_values`` sie
    # ausdrücklich weglässt (``_DESCRIBING``: ``type``, ``from``,
    # ``instantiation``, ``inherits`` …). Für die Erbkette ist das
    # richtig — ein geerbtes ``from: system`` wäre gelogen —, für die
    # geschriebene Datei fehlt es dann. Der Slicer sagt dazu
    # „solidon_process.json's from  unsupported" und bricht ab, bevor
    # er das Modell ansieht.
    document: dict[str, object] = {
        "type": "process",
        # Dieselbe CLI-Kategorie wie an der Maschine. Gemessen mit
        # ElegooSlicer 1.5.3.4: ``User`` ergibt trotz identischer Namen
        # ``compatible 0``, ``system`` ergibt ``compatible 1`` und G-Code.
        "from": "system",
        "instantiation": "true",
    }
    base = profile_file(setup.base_process, setup, "process")
    if base is not None:
        # Aufgelöst, nicht kopiert — wie beim Filament nebenan.
        # Gemessen am Elegoo-Bestand: ``0.12mm Fine`` trägt sieben
        # Schlüssel und fährt mit einhundertsechsunddreißig. Die
        # übrigen einhundertneunundzwanzig holte bisher der Slicer
        # selbst über ``inherits`` — also aus seinem Bestand, an dem
        # Solidon damit hing.
        document.update(slicer_profiles.resolve_values(base))
    document.update(values)
    # Objektmarken, unabhängig von den Einstellungen: Solidon schickt eine
    # Baugruppe mit benannten Teilen, und ohne die Marken im G-Code kann der
    # Drucker keines davon einzeln ausschließen. Löst sich einer von zwölf
    # Behältern nach sechs Stunden, ist sonst die ganze Platte verloren — der
    # Satz, um den es hier geht, lief ohne sie.
    document["gcode_label_objects"] = "1"
    # Ein eigener Name, obwohl das Systemprofil die Grundlage war. Sonst steht
    # im G-Code „0.20mm Standard @Elegoo CC2 0.4 nozzle", und wer die Datei
    # hinterher liest, hält Solidons Werte für die des Herstellers. Genau
    # diese Verwechslung hat einen Satz Gewürzbehälter gekostet: die
    # Projektdatei trug den Namen eines Systemprofils, der Slicer lud sein
    # eigenes darunter, und zehn von elf Werten waren still weg.
    document["name"] = f"Solidon {settings.title}"
    # Die Bindung an den Drucker, selbst gesetzt.
    #
    # Die Orca-Familie nimmt kein Prozessprofil an, das nicht zu einem
    # ihr bekannten Drucker gehört; sie bricht mit „process not
    # compatible with printer" ab, bevor sie das Modell ansieht. Bisher
    # hielt diese Bindung ``inherits``: In der kopierten Datei stand
    # kein ``compatible_printers`` — es steht eine Stufe tiefer
    # (gemessen: ``0.20mm Standard @Elegoo C 0.4 nozzle`` trägt
    # ``['Elegoo Centauri 0.4 nozzle']``), und der Slicer fand es, weil
    # er die Kette selbst ablief.
    #
    # Da die Werte jetzt ausgeschrieben sind, fällt ``inherits`` weg,
    # und mit ihm der Fund. Solidon setzt die Bindung deshalb selbst —
    # auf das Maschinenprofil, das es daneben schreibt. Damit hängt die
    # Übergabe an keinem fremden Profilnamen mehr.
    if setup.machine_profile:
        document["compatible_printers"] = [_machine_name(setup)]
    elif base is not None:
        # Kein eigenes Maschinenprofil, also auch keine eigene Bindung:
        # ``_command`` lädt dann keines, und der Slicer bleibt bei seinem
        # eigenen. Der Prozess muss zu **dem** passen, und das tut er nur
        # mit der geerbten Angabe. Sie steht selten in der obersten Datei,
        # deshalb über ``binding`` aus der Kette statt aus ``document``.
        document.update(slicer_profiles.binding(base))
    document.pop("inherits", None)
    return document


def _orca_filament(
    values: dict[str, str],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slot: MaterialSlot | None = None,
) -> dict[str, object]:
    """Das Filamentprofil für die Orca-Familie.

    Zwei Dinge unterscheiden es vom Prozessprofil. Erstens stehen die Werte
    dort als Liste, ein Eintrag je Filamentplatz — ein blanker String wird
    nicht angenommen. Zweitens braucht es ``filament_type``, sonst weiß der
    Slicer nicht, welche Grundannahmen gelten.

    Wie beim Prozess (§29) legt Solidon seine Werte auf das Profil des
    Herstellers, statt eines zu erfinden. Der Unterschied zum Prozess: hier
    wird die Erbkette vorher **aufgelöst**. Ein Filamentprofil bei Elegoo
    setzt selbst drei Werte und erbt fünfzig; kopierte man nur die oberste
    Datei, stünde in der Übergabe ein Bruchstück.
    """
    # Der Name nennt die Spule, nicht die Qualitätsstufe. „Solidon Standard —
    # PETG" stand über Werten von Elegoo PETG PRO: 5 mm³/s statt 11, 240 Grad
    # statt 250 — richtig gerechnet, falsch beschriftet. Wer die Druckdatei
    # später liest oder sie jemandem gibt, sieht nur „PETG" und legt die
    # falsche Rolle ein. Das „Solidon" davor bleibt, denn die Werte sind
    # Solidons und nicht die des Herstellers.
    marke = _profile_name(setup.base_filament) if setup.base_filament else ""
    document: dict[str, object] = {
        "type": "filament",
        "name": f"Solidon {marke or settings.title}",
        "from": "User",
        "instantiation": "true",
        "filament_type": [
            slot.material_type
            if slot is not None and slot.material_type
            else slicer_keys.filament_type(profile.material.id)
        ],
    }
    # Über ``profile_file``, nicht über ``Path(...).is_file()``: hierher kommt
    # bevorzugt ein **Name** aus dem Bestand des Slicers, denn ein Pfad
    # verstieße in der Projektdatei gegen Regel 12. Direkt als Pfad gelesen
    # sagte ``is_file()`` schlicht nein, und das Herstellerprofil wurde still
    # übersprungen — dieselbe Falle, die beim Prozessprofil schon einmal
    # zweiundvierzig Schlüssel statt zweiundsechzig ergab.
    #
    # Hier kostete es mehr als Schlüssel: ohne das Profil des Herstellers
    # fehlten die Temperaturen aller Druckplatten außer der einen, die Solidon
    # selbst setzt. Der Slicer wählte „Cool Plate", fand dort die 35 Grad
    # seiner eigenen Vorgabe, und ein PETG-Druck ging mit kaltem Bett hinaus.
    base = profile_file(setup.base_filament, setup, "filament")
    inherited: dict[str, object] = {}
    if base is not None:
        inherited = slicer_profiles.resolve_values(base)
        document.update({key: _as_slots(value) for key, value in inherited.items()})

    # Solidons Werte kommen darüber — außer sie gehören einem anderen Material.
    #
    # Die Einstellungen kennen ein Material, das Projekt-Material. Ein Slot
    # kann ein anderes tragen: eine Schrift in PLA auf einem Gehäuse aus PETG.
    # Für die Schrift sind 240 Grad und 10 mm³/s keine Solidon-Entscheidung
    # mehr, sondern ein Wert aus der falschen Zeile — PLA fährt 210 bei 21.
    # Wo der Slot sein eigenes Profil nennt, gilt deshalb der Hersteller für
    # alles, was am Material hängt.
    eigene = {key: [value] for key, value in values.items()}
    if slot is not None and slot.material and inherited:
        override = override_for(settings, slot)
        vom_material = {
            orca
            for solidon, orca, _kind in slicer_profiles.FILAMENT_READBACK
            if override is None or getattr(override, solidon.partition(".")[0]) is None
        }
        eigene = {key: value for key, value in eigene.items() if key not in vom_material}
    document.update(eigene)
    # Die ausdrücklich gewählte Spule gewinnt zuletzt. Eine lokale PLA-Spule
    # hat einen Typ, aber kein eigenes Herstellerprofil; in diesem Fall dient
    # das allgemeine PETG-Profil nur als Unterlage für fehlende Werte. Sein
    # ``filament_type`` darf die sichtbare PLA-Wahl nicht überschreiben.
    if slot is not None and slot.material_type:
        document["filament_type"] = [slot.material_type]
    # Die Farbe gehört dem Slot, nicht der Einstellung: sie ist der Grund,
    # warum es diesen Slot überhaupt gibt (§20). Ein Schriftzug in Weiß auf
    # schwarzem Gehäuse sind zwei Spulen, und beide bekämen sonst die eine
    # Farbe aus den Druckeinstellungen.
    if slot is not None and slot.colour is not None:
        red, green, blue = (round(channel * 255) for channel in slot.colour)
        document["filament_colour"] = [f"#{red:02X}{green:02X}{blue:02X}"]
    if slot is not None and slot.name:
        document["name"] = f"Solidon {slot.name}"
    # Aus dem Dokument, nicht aus ``values``: bei einem Slot mit eigenem
    # Material stehen dort die Werte des Herstellers, und die Platte soll die
    # Temperatur bekommen, die auch sonst gilt — PLA bei 60, nicht bei den 80
    # des Projektmaterials.
    return _with_every_plate(document, _plate_source(document, values))


def _plate_source(document: Mapping[str, object], values: Mapping[str, str]) -> dict[str, str]:
    """Welche Betttemperatur auf alle Platten geschrieben wird."""
    source: dict[str, str] = {}
    for key in ("hot_plate_temp", "hot_plate_temp_initial_layer"):
        value = document.get(key, values.get(key))
        if isinstance(value, list):
            value = value[0] if value else None
        if value is not None:
            source[key] = str(value)
    return source


#: Die Druckplatten, die die Orca-Familie auseinanderhält. Welche aufliegt,
#: weiß Solidon nicht — deshalb bekommt jede denselben Wert.
PLATE_KINDS: Final = ("cool", "eng", "hot", "textured", "supertack")


def _with_every_plate(document: dict[str, object], values: Mapping[str, str]) -> dict[str, object]:
    """Die Betttemperatur auf jede Druckplatte, nicht nur auf eine.

    ``curr_bed_type`` gehört der Maschine, die Temperatur dem Material — und
    Solidon kennt nur das zweite. Schreibt es allein ``hot_plate_temp`` und
    der Nutzer hat eine andere Platte eingestellt, liest der Slicer die
    Temperatur einer Platte, über die nie jemand entschieden hat.

    Erfunden wird dabei nichts: geschrieben wird derselbe Wert, den Solidon
    ohnehin für das Bett gesetzt hat. Danach ist das Ergebnis unabhängig
    davon, welche Platte gewählt ist — dieselbe Vorsicht wie bei den
    Haftungsarten, wo ein ungenutztes Maß sonst als eigener Schalter wirkt.
    """
    for suffix in ("", "_initial_layer"):
        value = values.get(f"hot_plate_temp{suffix}")
        if value is None:
            continue
        for plate in PLATE_KINDS:
            document[f"{plate}_plate_temp{suffix}"] = [value]
    return document


def _as_slots(value: object) -> object:
    """Filamentwerte stehen als Liste. Was aus einem Profil einzeln kommt,
    wird dazu gemacht — sonst mischt die Datei zwei Schreibweisen."""
    return value if isinstance(value, list) else [value]


def profile_differences(settings: PrintSettings, setup: SlicerSetup) -> list[Finding]:
    """Wo Solidons Werte von denen des Filamentprofils abweichen (§29, §22.5).

    Beide Seiten haben recht, und das ist der Punkt. Solidons Tabelle sagt,
    was PETG im Allgemeinen verträgt; das Profil des Herstellers sagt, was
    *diese Spule* auf *diesem Drucker* verträgt. Beim transluzenten Elegoo-PETG
    sind das 255 °C bei 70 °C Bett gegen 240 bei 80. Beim Volumenstrom sind
    sich beide mit 10 mm³/s einig — der Unterschied steht beim PRO, und dort
    um das Doppelte (5 gegen 10).

    Gemeldet, nicht stillschweigend übernommen: die Einstellung ist die
    Entscheidung des Nutzers. Wer den Hinweis liest, kann ihr widersprechen —
    und genau das soll er können (§2.7).
    """
    if not has_filament_profiles(setup.flavour) or not setup.base_filament:
        return []
    # Über ``profile_file``, nicht über ``Path(...).is_file()`` — dasselbe
    # Muster wie in ``_orca_filament``, und derselbe Grund: hierher kommt
    # bevorzugt ein **Name** aus dem Bestand des Slicers (Regel 12). Direkt
    # als Pfad gelesen sagte ``is_file()`` schlicht nein, und die ganze
    # Gegenüberstellung entfiel wortlos.
    base = profile_file(setup.base_filament, setup, "filament")
    if base is None:
        return []

    inherited = slicer_profiles.resolve_values(base)
    written = by_section(settings, setup.flavour).get("filament", {})
    apart: list[str] = []
    for key, ours in written.items():
        theirs = inherited.get(key)
        if theirs is None:
            continue
        value = theirs[0] if isinstance(theirs, list) and theirs else theirs
        # ``nil`` ist keine Gegenaussage, sondern eine Nicht-Aussage: der Wert
        # bleibt dann beim Drucker. Das als Abweichung zu melden hieße, fünf
        # Zeilen Rauschen neben die drei zu stellen, auf die es ankommt.
        if str(value).strip().casefold() in _NO_STATEMENT:
            continue
        if not _same(str(value), ours):
            apart.append(f"{key}: {ours} statt {value}")

    if not apart:
        return []
    _log.info("filament profile differs in %d value(s)", len(apart))
    return [
        Finding(
            code="slicer.filament_differs",
            severity="info",
            message=_(
                "Das Filamentprofil des Herstellers nennt andere Werte als die "
                "Einstellungen. Übergeben werden die Einstellungen."
            ),
            values={
                "profile": base.stem,
                "count": len(apart),
                "settings": "; ".join(sorted(apart)),
            },
            source="internal",
        )
    ]


def unknown_keys(settings: PrintSettings, profile: Profile, setup: SlicerSetup) -> list[Finding]:
    """Schlüssel, die diese Cura-Version nicht kennt (§29, §28.2).

    Was :func:`verify` für PrusaSlicer und die Orca-Familie leistet, kann es
    für Cura nicht: ``CuraEngine`` schreibt seine Einstellungen nicht in die
    Druckdatei, und die Gegenprobe findet dort null von den geschriebenen
    Schlüsseln wieder. Genau in dieser Lücke saß ``outer_inset_first`` — ein
    Name aus Cura 4, in Cura 5 verworfen, ohne Fehler und ohne Warnung.

    Die Auskunft, die es stattdessen gibt, liegt neben dem Programm:
    ``fdmprinter.def.json`` nennt jeden gültigen Schlüssel der **installierten
    Version**. Damit prüft sich auch eine Cura, die beim Bauen der Tabelle
    niemand vorliegen hatte — dieselbe Absicht wie bei der Gegenprobe, nur
    aus der einzigen Quelle, die dieser Slicer hergibt.

    Liegt die Datei nicht da, wird nichts behauptet: dann läuft der Slicer aus
    einem Paket, dessen Aufbau Solidon nicht kennt.
    """
    if not has_key_definitions(setup.flavour):
        return []
    known: set[str] = set()
    for name in ("fdmprinter.def.json", "fdmextruder.def.json"):
        path = _cura_definition(setup.executable, name)
        if path:
            known |= _definition_keys(Path(path))
    if not known:
        return []

    written = values_for(settings, profile, setup.flavour)
    strange = sorted(key for key in written if key not in known)
    if not strange:
        return []
    _log.warning("cura does not know %d key(s): %s", len(strange), ", ".join(strange[:5]))
    return [
        Finding(
            code="slicer.unknown_key",
            severity="warning",
            message=_(
                "Diese Version des Slicers kennt einige Einstellungen nicht — "
                "sie werden ohne Meldung übergangen."
            ),
            values={"count": len(strange), "settings": ", ".join(strange[:10])},
            source="internal",
        )
    ]


def _definition_keys(path: Path) -> set[str]:
    """Alle Einstellungsnamen einer Cura-Definition, über alle Ebenen."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    found: set[str] = set()

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, dict):
                found.add(key)
                walk(value.get("children"))

    walk(loaded.get("settings"))
    return found


def _command(
    setup: SlicerSetup,
    models: Sequence[Path],
    config: SlicerConfig,
    output: Path,
    keep_arrangement: bool = False,
) -> list[str]:
    """Die Kommandozeile dieses Slicers. Eine Liste, nie eine Zeichenkette —
    ein Dateiname mit Leerzeichen ist sonst zwei Argumente.

    Mehrere Modelle gehen zusammen hinein: die Slicer ordnen sie selbst auf der
    Platte an, und das ist ihre Aufgabe. Eines nach dem anderen zu slicen
    ergäbe ebenso viele Druckdateien, von denen jede so tut, als sei sie der
    ganze Auftrag.
    """
    binary = str(setup.executable)
    files = [str(entry) for entry in models]

    if setup.flavour == "prusa":
        return [
            binary,
            "--export-gcode",
            "--load",
            str(config.process),
            "--output",
            str(output / OUTPUT_NAME),
            *files,
        ]

    if setup.flavour == "orca":
        # Beide Profile, immer in dieser Reihenfolge: erst die Maschine, dann
        # der Prozess. Umgekehrt prüft der Slicer die Verträglichkeit gegen
        # einen Drucker, den er noch nicht kennt, und bricht ab.
        # Auch hier die Datei, nicht der Name: der Slicer sucht keinen Bestand
        # ab, er öffnet einen Pfad. Steht dort ein Name, endet der Lauf mit
        # „can not find setting file", noch bevor das Modell an die Reihe kommt.
        # Solidons eigenes Maschinenprofil, nicht das des Herstellers.
        # Es trägt dieselben Werte — ausgeschrieben statt geerbt — und
        # bindet den Prozess daneben über seinen Namen. Fällt es aus
        # (ein Aufruf ohne ``write_config``), bleibt der alte Weg als
        # Rückfall: besser das Profil des Herstellers als keines.
        machine = config.machine or profile_file(setup.machine_profile, setup, "machine")
        # Der Trenner steht im Pfad: geprüft, bevor der Slicer daran scheitert.
        _without_separator(
            [*([machine] if machine else []), config.process, *config.filaments], setup
        )
        settings_arg = f"{machine};{config.process}" if machine else str(config.process)
        arguments = [binary, "--load-settings", settings_arg]
        # Das Filament kommt über einen eigenen Schalter. Es mit in
        # ``--load-settings`` zu geben hilft nicht: der Slicer sortiert die
        # Dateien nach ihrem ``type``, und ein Filamentprofil, das dort
        # ankommt, wird verworfen statt geladen.
        # Alle Filamente auf einmal, durch Semikolon getrennt — je Slot eines,
        # in der Reihenfolge der Slots. Die *ist* die Extruderbelegung (§20);
        # gäbe man nur das erste, druckte die zweite Farbe mit den Werten der
        # ersten.
        if config.filaments:
            arguments += ["--load-filaments", ";".join(str(one) for one in config.filaments)]
        if keep_arrangement:
            # Ohne diesen Schalter ordnet die Orca-Familie **immer** neu an,
            # egal in welchen Koordinaten die Teile ankommen — gemessen an zwei
            # Läufen derselben Szene, die denselben G-Code ergaben. Damit war
            # alles folgenlos, was Solidon über die Platte weiß: `arrange_bed`,
            # der Haftungsrand, die Plattenzuordnung. Gesetzt wird er nur, wenn
            # die Anordnung wirklich eine ist (siehe
            # :func:`app.core.export.writer.arrangement_holds`) — sonst
            # druckten zwei Teile übereinander.
            arguments += ["--arrange", "0"]
        return [*arguments, "--slice", "0", "--outputdir", str(output), *files]

    arguments = [binary, "slice", "-v"]
    basis = setup.machine_profile or _cura_base(setup.executable)
    if basis:
        arguments += ["-j", basis]
    values: list[str] = []
    for line in config.process.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values += ["-s", line.strip()]
    arguments += values
    # **Und dieselben Werte noch einmal auf dem Extruder.** ``CuraEngine`` hält
    # zwei Ebenen: was global gilt, und was der Extruder-Zug sagt — und das
    # meiste, was einen Druck ausmacht, liest es vom Zug. Was nur global steht,
    # wird nicht etwa übernommen, sondern von der Vorgabe der Definition
    # überschrieben. Gemessen an einem 20-mm-Würfel gegen PrusaSlicer: 748 mm
    # Filament statt 1410, weil Wandzahl, Bahnbreite und Füllung nie ankamen.
    # Das Fenster sortiert die Werte nach ``settable_per_extruder``; sie beide
    # Male zu setzen kommt am selben Ort heraus und braucht die Definition
    # nicht zu lesen.
    arguments += ["-e0"]
    extruder = _cura_extruder_base(setup.executable)
    if extruder:
        arguments += ["-j", extruder]
    arguments += values
    for entry in files:
        arguments += ["-l", entry]
    arguments += ["-o", str(output / OUTPUT_NAME)]
    return arguments


#: Womit die Orca-Familie mehrere Profile in einem Argument trennt.
PROFILE_SEPARATOR: Final = ";"


def _without_separator(paths: Sequence[Path], setup: SlicerSetup) -> None:
    """Hält an, wenn ein Profilpfad den Trenner selbst enthält (§28).

    ``--load-settings`` und ``--load-filaments`` nehmen mehrere Dateien in
    **einem** Argument, getrennt durch Semikolon. Ein Semikolon im Pfad macht
    daraus zwei Pfade, und der Slicer antwortet mit „can not find setting
    file" über eine Datei, die es so nie gab — die Meldung zeigt dann auf ein
    Profil und die Ursache liegt im Ordnernamen.

    **Abgelehnt statt maskiert, und das ist keine Bequemlichkeit.** Für diesen
    Schalter ist nirgends zugesagt, wie man den Trenner maskiert; eine
    geratene Maskierung ergäbe wieder eine Slicer-Meldung über einen Pfad, den
    niemand geschrieben hat. Ein Satz, der die Lage benennt, ist mehr wert als
    ein Versuch, der still danebengeht (Regel 21).

    Der Fall ist selten und nicht erfunden: Der Arbeitsordner liegt unter dem
    Nutzerverzeichnis, und ein Semikolon ist dort ein erlaubtes Zeichen.
    """
    marked = [str(entry) for entry in paths if PROFILE_SEPARATOR in str(entry)]
    if not marked:
        return
    raise ExternalToolError(
        tool=setup.name,
        detail=_(
            "Ein Profilpfad enthält ein Semikolon. Dieser Slicer trennt damit seine "
            "Profile und liest den Pfad als zwei."
        ),
        values={"path": ", ".join(marked)},
        suggestions=(OPEN_SETTINGS, CANCEL),
    )


def _cura_base(executable: Path) -> str:
    """Die Grunddefinition neben ``CuraEngine``, sofern sie dort liegt.

    ``CuraEngine`` braucht mindestens eine Definition, sonst kennt es keinen
    einzigen Einstellungsnamen. ``fdmprinter.def.json`` ist die Wurzel, von
    der alle Druckerdefinitionen erben — die Maschine selbst beschreibt
    Solidon daneben über :func:`_machine_keys`, statt eine der
    zwölfhundert Herstellerdefinitionen zu wählen und deren Vererbungskette
    nachzubauen. Die kennt nur das Fenster.

    Nichts, wenn sie nicht daliegt: dann scheitert der Lauf und sagt das,
    statt einen Pfad zu erfinden.
    """
    return _cura_definition(executable, "fdmprinter.def.json")


def _cura_extruder_base(executable: Path) -> str:
    """Die Grunddefinition des Extruder-Zugs, neben der des Druckers.

    Sie gibt dem Zug die Werte, die keine Einstellung von Solidon setzt —
    Düsenversatz, Startposition, Kühlung im Ruhezustand. Ohne sie bleibt der
    Zug leer, und eine Abfrage darauf endet mit „Trying to retrieve setting
    with no value given".
    """
    return _cura_definition(executable, "fdmextruder.def.json")


def _cura_definition(executable: Path, filename: str) -> str:
    for folder in (
        executable.parent / "share" / "cura" / "resources" / "definitions",
        executable.parent / "resources" / "definitions",
    ):
        found = folder / filename
        if found.is_file():
            return str(found)
    return ""


@dataclass(slots=True)
class SliceOutcome:
    """Was der Lauf gebracht hat."""

    gcode_path: Path
    metrics: gcode.GcodeMetrics
    findings: list[Finding] = field(default_factory=list)
    seconds: float = 0.0


def _run_slicer(
    command: Sequence[str],
    workspace: Path,
    timeout: float,
    setup: SlicerSetup,
    cancelled: CancelToken | None,
) -> subprocess.CompletedProcess[bytes]:
    """Führt den Slicer aus — abbrechbar, und mit der Zeitgrenze als Antwort.

    ``subprocess.run`` wartete blind: Eine Zeitüberschreitung flog als roher
    ``TimeoutExpired`` aus dem Arbeits-Thread, der fing nur ``AppError`` —
    der Dialog stand dauerhaft auf „Der Slicer rechnet …" (Regel 17, §2.8).
    Und abzubrechen gab es nichts: der Kindprozess lief, bis er fertig war,
    gleich was der Nutzer wollte.
    """
    # **Aus einem Flatpak heraus startet der Slicer auf dem Rechner, nicht im
    # Sandkasten.** Dort gibt es keinen — und keine der fünf Suchstufen von
    # ``discover`` konnte je einen finden, weil sie alle Host-Pfade absuchen.
    # Die Übergabe (§29) war im Linux-Paket damit tot, ohne dass etwas
    # abstürzte. ``on_host`` legt ``flatpak-spawn --host`` davor, wenn es nötig
    # ist, und lässt den Befehl sonst unverändert; der Arbeitsordner liegt
    # schon im Nutzer-Cache, weil ``sandboxed`` den eigenen Fall jetzt mitzählt.
    launched = discover.on_host(command)
    try:
        answer = run_limited(
            launched,
            cwd=workspace,
            timeout=timeout,
            output_limit=SLICER_OUTPUT_LIMIT,
            cancelled=(lambda: cancelled.is_cancelled) if cancelled is not None else None,
        )
    except OSError as problem:
        # Eine gewählte Datei kann `flavour_of` bestehen und trotzdem kein
        # Programm sein — eine DLL zum Beispiel.
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der Slicer ließ sich nicht starten."),
            values={"reason": str(problem)},
            suggestions=(
                INSTALL_MISSING,
                EXPORT_ONLY,
            ),
        ) from problem
    except ProcessCancelled:
        raise OperationCancelled from None
    except subprocess.TimeoutExpired:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der Slicer hat das Zeitlimit überschritten."),
            values={"seconds": int(timeout)},
            suggestions=(CHOOSE_SLICER, EXPORT_ONLY, RETRY),
        ) from None
    except ProcessOutputLimitExceeded as problem:
        # **Kein Fehlercode** — es ist gar keiner gekommen: Solidon hat den
        # Lauf abgebrochen, weil die Ausgabe die Sammelgrenze überschritt. Der
        # alte Satz schickte den Leser in den Slicer, wo nichts zu finden ist.
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der Slicer hat mehr Ausgabe erzeugt, als gesammelt wird."),
            values={"reason": str(problem)},
            suggestions=(SHOW_SLICER_OUTPUT, CHOOSE_SLICER, EXPORT_ONLY),
        ) from problem
    return subprocess.CompletedProcess(
        list(command), answer.returncode, answer.stdout, answer.stderr
    )


def bed_box(profile: Profile, flavour: SlicerFlavour) -> BoundingBox:
    """Der Bauraum in den Koordinaten, in denen **dieser** Slicer schreibt.

    Zwei Welten, und sie zu verwechseln kostet einen falschen Befund bei jedem
    Lauf: Cura und PrusaSlicer bekommen von Solidon eine Maschine um den
    Ursprung (:func:`_machine_keys`), die Orca-Familie lädt ihr eigenes
    Maschinenprofil und misst von der Ecke der Platte.

    Gefragt wird über :func:`wants_bed_coordinates` und nicht über den
    Familiennamen: Es ist dieselbe Frage, die auch die Übergabe stellt, und
    zwei Formulierungen davon laufen auseinander, sobald eine vierte Familie
    dazukommt.

    Das hier ist die **Annahme**. Was die Datei selbst über ihr Bett sagt,
    liest :func:`gcode.stated_bed`, und das gilt vor — gebraucht wird die
    Annahme nur, wo der Slicer schweigt, also bei ``cura``, und dort weiß
    Solidon die Maße genau, weil es sie selbst geschrieben hat.
    """
    width, depth, height = profile.printer.build_volume
    if wants_bed_coordinates(flavour):
        return BoundingBox((0.0, 0.0, 0.0), (width, depth, height))
    half_width, half_depth = width / 2.0, depth / 2.0
    return BoundingBox((-half_width, -half_depth, 0.0), (half_width, half_depth, height))


def off_the_bed(
    payload: str | gcode.GcodeAnalysis, profile: Profile, flavour: SlicerFlavour
) -> Finding | None:
    """Druckt die geschriebene Datei über den Bauraum hinaus? (§29, Regel 14)

    **Gemessen an CuraEngine 5.13.0.** Ein Würfel 150 mm neben der Mitte, ein
    Bett von 220 mm: PrusaSlicer rückt ihn selbst in die Mitte und druckt bei
    x -23,6 bis 23,6, die Orca-Familie schreibt ohne Maschinenprofil gar
    nichts — und CuraEngine schreibt eine Datei, die bei x 130,2 bis 169,8
    druckt. Sein Bauraum reicht bis 110. Es prüft ihn nicht, und im Kopf der
    Datei steht dazu ``MINX:2.14748e+06``, also nichts.

    Das ist der einzige Weg, davon zu erfahren.
    ``arrange.out_of_build_volume`` prüft die **Szene**, und die kann in
    Ordnung sein; hier geht es um die Datei, die der Slicer daraus gemacht
    hat — gemessen an ihren Bahnen, mit ``source="gcode"`` und nie mit der
    Schätzung vermischt.

    Gemeldet, nicht gesperrt (§29): die Datei liegt vor, sie ist rechenbar,
    und wer ein größeres Bett hat als sein Profil sagt, soll sie behalten
    dürfen. Der Befund trägt den Schweregrad, den ein Druck verdient, der in
    den Rahmen fährt.

    **Gegen das Bett der Datei, nicht gegen das eigene.** Die Orca-Familie und
    PrusaSlicer schreiben ihre Bettform in die Datei; dann gilt die
    (:func:`gcode.stated_bed`). Sonst bleibt es bei
    :func:`bed_box` — und das trifft genau CuraEngine, dem Solidon die Maße
    selbst gegeben hat. Der erste Anlauf maß immer gegen den eigenen Bauraum,
    und der ElegooSlicer bekam damit bei einem Würfel in der Bettmitte einen
    Befund: sein Maschinenprofil kommt aus seinem eigenen Bestand, und
    „außerhalb" hieße dort entweder „daneben gedruckt" oder „zwei Profile
    meinen verschiedene Maschinen".

    Unter einer Bahnbreite wird nichts gemeldet: eine Datei, die auf den
    Millimeter passt, ist in Ordnung, und die Bahn selbst liegt mit ihrer
    halben Breite ohnehin neben der Mitte, die hier gemessen wird.
    """
    analysis = payload if isinstance(payload, gcode.GcodeAnalysis) else gcode.analyze(payload)
    extent = analysis.extent
    if extent is None:
        return None
    bed = analysis.bed or bed_box(profile, flavour)
    worst, axis = 0.0, 0
    for index in range(3):
        over = max(
            bed.minimum[index] - extent.minimum[index],
            extent.maximum[index] - bed.maximum[index],
        )
        if over > worst:
            worst, axis = over, index
    if worst <= profile.printer.extrusion_width:
        return None
    return Finding(
        code="gcode.off_the_bed",
        severity="error",
        message=_(
            "Die Druckdatei fährt über den Bauraum hinaus — der Slicer hat ihn nicht geprüft."
        ),
        values={
            "axis": "XYZ"[axis],
            "excess_mm": worst,
            "printed": f"{extent.minimum[axis]:.1f}..{extent.maximum[axis]:.1f}",
            "allowed": f"{bed.minimum[axis]:.1f}..{bed.maximum[axis]:.1f}",
        },
        source="gcode",
    )


#: Programme, die ``--arrange 0`` mit der Standardabsage quittieren
#: (ElegooSlicer 1.5.3.4: Exit 127, „found error", sonst nichts — gemessen:
#: ``--arrange 1`` läuft, die abgelehnte **Wertbelegung** ist die 0, also
#: gerade das „nicht anordnen"). Je Sitzung gemerkt, nachdem der Rückfall es
#: einmal gemessen hat — keine Liste von Hand, denn welche Fassung was
#: annimmt, weiß nur das Programm selbst, und ``--help`` schweigt bei dieser
#: Familie vollständig.
_REFUSES_THE_ARRANGE_FLAG: Final[set[Path]] = set()


def too_short(
    payload: str | gcode.GcodeAnalysis, model_height: float, settings: PrintSettings
) -> Finding | None:
    """Ist die Druckdatei niedriger als das Modell? (§28.2, Regel 14)

    Der Fall, den keine andere Gegenprobe sieht: Ein Körper, der zur Hälfte
    unter dem Druckbett steckt, wird von CuraEngine wortlos unter ``z = 0``
    abgeschnitten — gemessen am 30.08.2026: 50 Schichten statt 100, halbes
    Material, Exit 0. PrusaSlicer hebt denselben Körper selbst aufs Bett, die
    Orca-Familie ordnet ihn an; nur der Cura-Kunde bekommt ein halbes Teil und
    erfährt es erst am Drucker. ``off_the_bed`` schweigt dazu — die halbe Höhe
    liegt brav im Bauraum.

    Verglichen wird die gedruckte Höhe aus den Bahnen mit der Höhe des
    höchsten Teils. Zwei Schichthöhen Luft, weil die oberste Schicht auf das
    Raster gerundet wird und die erste dicker sein darf; ein Raft macht die
    Datei höher, nie niedriger, und stört den Vergleich darum nicht.
    """
    analysis = payload if isinstance(payload, gcode.GcodeAnalysis) else gcode.analyze(payload)
    extent = analysis.extent
    if extent is None or model_height <= 0.0:
        return None
    printed_height = float(extent.maximum[2])
    allowance = 2.0 * settings.layers.layer_height
    if printed_height >= model_height - allowance:
        return None
    return Finding(
        code="gcode.shorter_than_model",
        severity="error",
        message=_(
            "Die Druckdatei ist niedriger als das Modell — was unter dem "
            "Druckbett lag, hat der Slicer nicht gedruckt."
        ),
        # ``printed`` und ``height`` sind vorhandene Wertnamen der Anzeige —
        # „Gedruckt: 10 mm · Höhe: 20 mm" braucht keinen neuen Katalogeintrag.
        values={
            "printed_mm": printed_height,
            "height_mm": model_height,
        },
        source="gcode",
    )


def slice_model(
    model: Path | Sequence[Path],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    *,
    output_dir: Path | None = None,
    timeout: float = TIMEOUT_SECONDS,
    keep_arrangement: bool = False,
    slots: Sequence[MaterialSlot] = (),
    cancelled: CancelToken | None = None,
    model_height: float | None = None,
) -> SliceOutcome:
    """Slicen lassen und die Datei zurücklesen (§29, §28.1).

    Der Rückweg ist der Punkt: was herauskommt, ist nicht bloß eine Datei auf
    der Platte, sondern gemessene Kennzahlen, die im Prüfbericht neben den
    geschätzten stehen — mit ihrer Herkunft, nie mit ihnen vermischt
    (Regel 14).

    Mehrere Modelle gehen als eine Platte hinein und ergeben eine Druckdatei.
    Ein einzelner Pfad ist dabei der Sonderfall mit einem Eintrag, nicht ein
    anderer Weg.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # §2 C: die Druckdatei ist ein herausgegebenes Ergebnis — wie der Export.
    activation.require(activation.SLICER)
    # Absolut, bevor irgendetwas damit geschieht: der Lauf unten setzt sein
    # eigenes Arbeitsverzeichnis, ein relativer Pfad zeigt dort ins Leere. Die
    # Prüfung gleich darunter sähe die Datei trotzdem — sie sucht im
    # Verzeichnis des aufrufenden Prozesses —, und der Fehler käme erst vom
    # Slicer selbst, als „No such file" mit einem Pfad, den es aus seiner
    # Sicht wirklich nicht gibt.
    models = [entry.resolve() for entry in ([model] if isinstance(model, Path) else model)]
    if not models:
        # **Nicht die geerbten Vorschläge.** ``ExternalToolError`` bietet als
        # erstes „Zusätzliche Programme …" an, und das ist hier die falsche
        # Antwort: Es fehlt kein Programm, es fehlt ein Teil auf der Platte.
        # Ein Knopf, der in eine Liste führt, die mit dem Fehler nichts zu tun
        # hat, ist schlechter als keiner (Regel 17).
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Es wurde nichts zum Slicen übergeben."),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    missing = [entry for entry in models if not entry.is_file()]
    if missing:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Die zu slicende Datei ist nicht da."),
            values={"path": ", ".join(entry.name for entry in missing)},
            # Die Datei ist zwischen Export und Lauf verschwunden. Was hilft,
            # ist derselbe Weg noch einmal — er schreibt sie neu.
            suggestions=(RETRY, CANCEL),
        )
    if not setup.executable.is_file():
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der eingestellte Slicer liegt nicht mehr an seinem Pfad."),
            suggestions=(INSTALL_MISSING, EXPORT_ONLY),
        )

    started = time.perf_counter()
    written_settings = settings_for_handover(settings, setup.flavour, slots)
    # Ein Slicer als Flatpak sieht unser ``/tmp`` nicht
    # (``discover.workspace_for``).
    with discover.workspace_for(setup.executable, "solidon-slice-") as workspace:
        config = write_config(settings, profile, setup, workspace, slots)
        # Aus demselben Grund wie die Modellpfade: der Slicer schreibt sonst
        # neben sein Arbeitsverzeichnis statt dorthin, wo die Datei erwartet
        # wird — und ``_find_gcode`` sucht an der leeren Stelle.
        target = (output_dir if output_dir is not None else workspace).resolve()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as problem:
            # Ein gewähltes Ziel, das keines ist — schreibgeschützt oder
            # bereits eine Datei. Roh geworfen riss es den Arbeits-Thread ab.
            raise FileWriteError(
                target=str(problem.filename or target),
                detail=str(problem.strerror or problem),
            ) from problem

        # Nicht jeder Slicer der Familie nimmt ``--arrange 0`` an:
        # ElegooSlicer 1.5.3.4 bricht darauf mit der Standardabsage der
        # Slic3r-Kommandozeile ab — Exit 127, „found error", kein Wort über
        # den Grund. Gemerkt je Programm und Sitzung, damit die zweite Platte
        # nicht wieder zweimal läuft.
        wanted_arrangement = keep_arrangement and setup.executable not in _REFUSES_THE_ARRANGE_FLAG
        completed = _run_slicer(
            _command(setup, models, config, target, wanted_arrangement),
            workspace,
            timeout,
            setup,
            cancelled,
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Der Name, den wir selbst genannt haben — die Orca-Familie benennt
        # selbst, für sie bleibt es bei der jüngsten Datei.
        expected = "" if names_its_own_output(setup.flavour) else OUTPUT_NAME
        produced = _find_gcode(target, expected)
        arranged_by_slicer = keep_arrangement and not wanted_arrangement
        if produced is None and wanted_arrangement and setup.flavour == "orca":
            # Die Rückfallstufe: einmal ohne die Anordnungsvorgabe — dieselbe
            # Bauart wie bei den Booleschen Ops, und wie dort wird die
            # benutzte Stufe ausgewiesen statt verschwiegen. Ein Slicer, der
            # auch so nichts schreibt, läuft in die Fehlerbehandlung darunter,
            # mit derselben Meldung wie bisher.
            completed = _run_slicer(
                _command(setup, models, config, target, False),
                workspace,
                timeout,
                setup,
                cancelled,
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            produced = _find_gcode(target, expected)
            if produced is not None:
                _REFUSES_THE_ARRANGE_FLAG.add(setup.executable)
                arranged_by_slicer = True
        if produced is None:
            # Beide Ströme: die Orca-Familie protokolliert auf stdout und
            # lässt stderr leer. Nur stderr zu zeigen hieße, einen Fehler
            # ohne Text zu melden — und das ist schlimmer als keiner.
            output = _tail(completed.stdout, completed.stderr)
            if _says_outside_the_volume(output):
                raise ExternalToolError(
                    tool=setup.name,
                    exit_code=completed.returncode,
                    detail=_("Der Slicer sagt, die Teile liegen außerhalb seines Bauraums."),
                    values={"output": output},
                    suggestions=(ARRANGE_ON_BED, SCALE_TO_FIT, SHOW_SLICER_OUTPUT),
                )
            if _says_no_layers(output):
                raise ExternalToolError(
                    tool=setup.name,
                    exit_code=completed.returncode,
                    detail=_(
                        "Der Slicer hat keine druckbaren Schichten gefunden. Prüfen Sie "
                        "offene Stellen, Einheit und Wandstärke."
                    ),
                    values={"output": output},
                    suggestions=(REPAIR_AND_RETRY, SHOW_LOCATIONS, SHOW_SLICER_OUTPUT),
                )
            # ``CHOOSE_SLICER`` zuerst: Auf einem Rechner mit mehreren Slicern
            # ist der Wechsel der kürzeste Ausweg — genau dieser Fall stand
            # als Sackgasse da, mit zwei arbeitenden Slicern neben dem einen,
            # der nicht wollte (§2.1, gemessen am 30.08.2026).
            raise ExternalToolError(
                tool=setup.name,
                exit_code=completed.returncode,
                detail=_("Der Slicer hat keine Druckdatei geschrieben."),
                values={"output": output},
                suggestions=(CHOOSE_SLICER, SHOW_SLICER_OUTPUT, CHECK_SLICER_PROFILE, EXPORT_ONLY),
            )

        with produced.open("r", encoding="utf-8", errors="replace") as stream:
            analysis = gcode.analyze_lines(stream, cancelled=cancelled)
        if not analysis.extrudes:
            # Eine große Datei ohne eine einzige Förderbewegung. Der Slicer ist
            # durchgelaufen und hat den Rückgabewert 0 gemeldet, aber das
            # Modell nicht verarbeitet — meist, weil ihm eine Einstellung
            # fehlte, die er stillschweigend als „nichts drucken" auslegt. Das
            # als Erfolg durchzulassen wäre schlimmer als der Abbruch: der
            # Nutzer schickte eine leere Datei an den Drucker.
            raise ExternalToolError(
                tool=setup.name,
                exit_code=completed.returncode,
                detail=_(
                    "Die Druckdatei enthält keine einzige Materialbahn — "
                    "der Slicer hat das Modell nicht verarbeitet."
                ),
                values={"output": _tail(completed.stdout, completed.stderr)},
                suggestions=(CHECK_SLICER_PROFILE, SHOW_SLICER_OUTPUT, CHOOSE_SLICER, EXPORT_ONLY),
            )
        metrics = analysis.metrics
        # Und die zweite Gegenprobe, an der Geometrie statt an den Werten:
        # steht in dieser Datei ein Druck, der auf das Bett passt?
        beyond = off_the_bed(analysis, profile, setup.flavour)
        # Die dritte: Ist überhaupt das ganze Modell darin? ``None`` heißt
        # „der Aufrufer kennt die Höhe nicht" — dann entfällt der Vergleich,
        # er wird nie geraten.
        short = too_short(analysis, model_height, settings) if model_height is not None else None
        # Die Gegenprobe: hat der Slicer übernommen, was ihm geschrieben wurde?
        # Das ist die einzige Auskunft, die von ihm selbst kommt statt aus einer
        # Dokumentation, die für die installierte Version gelten mag oder nicht.
        ignored = verify_settings(analysis.settings, as_mapping(written_settings, setup.flavour))
        if output_dir is None:
            # Der Ordner verschwindet gleich; die Datei muss den Aufrufer noch
            # erreichen können, also wandert sie neben das Modell.
            produced = _kept_beside(models[0], produced, cancelled=cancelled)

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    findings = [
        *profile_differences(settings, setup),
        *unknown_keys(settings, profile, setup),
        *unreachable_overrides(settings, setup, slots),
        # **Auch hier und nicht nur beim Export.** Der Befund entstand für
        # ``write_assembly``; der Kunde, der auf *Slicen* klickt, geht aber gar
        # nicht dort vorbei. Sein Lauf gelingt dann mit den Vorgaben des
        # Slicers statt mit den Werten aus Solidon — oder er scheitert, und die
        # Orca-Familie sagt dazu nur „process not compatible with printer".
        *machine_missing(setup, profile),
        *ignored,
        *([beyond] if beyond is not None else []),
        *([short] if short is not None else []),
        *gcode.findings_for(metrics),
    ]
    if arranged_by_slicer:
        # Regel 14 im Geist: Die Anordnung kommt dann nicht von Solidon,
        # und das steht dabei — gemessen liegt sie um Dutzende Millimeter
        # daneben, und der gelungene Lauf sähe ohne den Befund richtig aus.
        # Eine verworfene Plattenbelegung, die keiner bemerkt, wäre schlimmer
        # als der Schalter, der sie verwarf (§29).
        findings.append(
            Finding(
                code="slicer.arranged_itself",
                severity="warning",
                message=_(
                    "Dieser Slicer nimmt die Anordnungsvorgabe nicht an und hat die "
                    "Teile selbst angeordnet — die Plattenbelegung aus Solidon gilt "
                    "für diese Druckdatei nicht."
                ),
                values={"slicer": setup.name},
                source="gcode",
            )
        )
    findings.append(
        Finding(
            code="slicer.handover",
            severity="info",
            message=_(
                "Diese Datei kommt aus dem externen Slicer, gerechnet mit den Werten aus Solidon."
            ),
            values={"slicer": metrics.slicer or setup.name, "settings": settings.title},
            source="gcode",
        )
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return SliceOutcome(
        gcode_path=produced,
        metrics=metrics,
        findings=findings,
        seconds=time.perf_counter() - started,
    )


#: Wie das Fenster neben einem reinen Konsolenprogramm heißt.
#:
#: Zwei Familien liefern getrennte Programme: Bei PrusaSlicer trägt die
#: Konsole den Zusatz, bei Cura ist ``CuraEngine`` die Rechenmaschine und das
#: Fenster heißt nach dem Hersteller — mit wechselnder Schreibung des ``M``.
#: Die Orca-Familie ist ein Programm für beides und braucht keinen Eintrag.
_WINDOW_SIBLINGS: Final[dict[str, tuple[str, ...]]] = {
    "prusa-slicer-console": ("prusa-slicer",),
    "curaengine": ("Ultimaker-Cura", "UltiMaker-Cura", "cura"),
}


def window_program(executable: Path) -> Path | None:
    """Das Fenster derselben Installation — oder ``None``, wenn keines da ist.

    Für die zweite Übergabeart aus §29: Die Datei im Slicer **öffnen** braucht
    ein Programm mit Fenster, und das liegt bei zwei Familien neben dem
    Konsolenprogramm im selben Ordner. Gesucht wird nur dort — ein Fenster aus
    einer anderen Installation wäre ein anderer Slicer mit anderen Profilen.
    """
    names = _WINDOW_SIBLINGS.get(executable.stem.casefold())
    if names is None:
        return executable
    for name in names:
        candidate = executable.with_name(name + executable.suffix)
        if candidate.is_file():
            return candidate
    return None


def open_in_slicer(model: Path, setup: SlicerSetup) -> None:
    """Die geschriebene Datei im Fenster des Slicers öffnen (§29).

    Die zweite Übergabeart neben dem Konsolenlauf: kein Profil, kein
    Zeitlimit, kein Rücklesen — ab hier gehört der Auftrag dem Nutzer, und
    der Slicer zeigt selbst, was er daraus macht. Sie trägt auch den Fall,
    in dem die Kommandozeile eines Slicers nicht kann, was sein Fenster kann.

    Gewartet wird nicht: Das Fenster lebt so lange, wie der Nutzer es
    braucht, und ein Solidon, das sich beendet, nimmt es nicht mit. Nach
    §32 bleibt es eine feste Argumentliste ohne Shell — hier läuft kein
    fremder Quelltext, ein Programm zeigt auf eine Datei.
    """
    activation.require(activation.SLICER)
    if not model.is_file():
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Die zu slicende Datei ist nicht da."),
            values={"path": model.name},
            suggestions=(RETRY, CANCEL),
        )
    program = window_program(setup.executable)
    if program is None:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Zu diesem Slicer ist kein Fenster installiert — er rechnet nur."),
            suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
        )
    if not program.is_file():
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der eingestellte Slicer liegt nicht mehr an seinem Pfad."),
            suggestions=(INSTALL_MISSING, EXPORT_ONLY),
        )
    # Losgelöst und leise, dasselbe Muster wie der Dienststart in
    # ``tools.start``: kein Konsolenfenster, kein Kindprozess, der am Ende
    # von Solidon hängt. Und wie jeder Startpfad geht auch dieser auf den
    # Rechner, nicht in den Sandkasten (``discover.on_host``).
    command = discover.on_host([str(program.resolve()), str(model.resolve())])
    try:
        subprocess.Popen(command, **detached_process_options(graphical=True))
    except OSError as problem:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der Slicer ließ sich nicht starten."),
            values={"reason": str(problem)},
            suggestions=(CHOOSE_SLICER, INSTALL_MISSING, EXPORT_ONLY),
        ) from problem
    _log.info("opened %s in %s", model.name, program.name)


#: Schlüssel, deren Wert der Slicer bewusst umrechnet oder ergänzt — eine
#: Abweichung dort ist keine. ``filament_colour`` etwa wird zu einer Liste,
#: weil ein Drucker mehrere Filamente führen kann.
#:
#: Die Filamentwerte standen hier lange mit derselben Begründung. Sie war
#: falsch: der Slicer rechnete sie nicht um, er bekam sie nie — sie lagen im
#: Prozessprofil, und dort liest er sie nicht. Seit sie im Filamentprofil
#: stehen, gehören sie in die Gegenprobe wie alles andere.
_RECOMPUTED: Final = frozenset(
    {
        "filament_colour",
        "nozzle_diameter",
        "bed_shape",
        "first_layer_speed",
        "brim_type",
        "wall_sequence",
        "support_type",
    }
)


def verify(text: str, written: Mapping[str, str]) -> list[Finding]:
    """Kam an, was Solidon geschrieben hat? (§28.2)

    Die Slicer schreiben ihre wirksame Konfiguration als Kommentare in die
    Druckdatei. Das ist die einzige Auskunft darüber, ob eine Zuordnung
    stimmt — und sie kommt von dem Programm selbst, nicht aus einer
    Dokumentation, die für die installierte Version womöglich nicht gilt.

    Damit prüft sich jeder Slicer selbst, auch einer, den beim Bauen der
    Tabelle niemand vorliegen hatte. Gemeldet wird nur, was **nachweislich**
    abweicht: ein Schlüssel, den die Datei gar nicht nennt, sagt nichts —
    kein Slicer schreibt alles.
    """
    return verify_settings(gcode.analyze(text).settings, written)


def verify_settings(found: Mapping[str, str], written: Mapping[str, str]) -> list[Finding]:
    """Vergleicht bereits ausgelesene Einstellungen mit den geschriebenen."""

    ignored: list[str] = []
    for key, wanted in written.items():
        if key in _RECOMPUTED:
            continue
        actual = found.get(key.casefold())
        if actual is None or _same(actual, wanted):
            continue
        ignored.append(f"{key}: {wanted} → {actual}")

    if not ignored:
        return []
    _log.warning("slicer ignored %d setting(s): %s", len(ignored), "; ".join(ignored[:5]))
    return [
        Finding(
            code="slicer.setting_ignored",
            severity="warning",
            message=_(
                "Der Slicer hat Einstellungen anders übernommen, als Solidon sie geschrieben hat."
            ),
            values={"count": len(ignored), "settings": "; ".join(sorted(ignored)[:10])},
            source="gcode",
        )
    ]


def _same(actual: str, wanted: str) -> str | bool:
    """Ob zwei Werte dasselbe meinen.

    Verglichen wird nachsichtig: ``0.2`` und ``0.20``, ``15%`` und ``15``,
    und eine Liste aus einem Element gegen dieses Element. Sonst meldete die
    Gegenprobe Unterschiede, die keine sind, und würde nach dem dritten Mal
    weggesehen.
    """
    left, right = actual.strip().strip("%"), wanted.strip().strip("%")
    if left == right:
        return True
    left = left.strip("[]").split(",")[0].strip().strip("\"'")
    if left == right:
        return True
    try:
        return abs(float(left) - float(right)) < 1e-6
    except ValueError:
        return False


#: Was ein Slicer sagt, wenn von der Platte nichts in seinem Bauraum liegt.
#:
#: **Gemessen, nicht geraten.** PrusaSlicer 2.9.6 schreibt genau diesen Satz,
#: wenn eine Platte in Bettkoordinaten ankommt — so kommt sie aus einer fremden
#: 3MF, denn dort rechnet der Slicer von der Ecke und Solidon um die Mitte.
#: Bisher wurde daraus „Der Slicer hat keine Druckdatei geschrieben": ein Satz
#: über das Ende und nicht über die Ursache, und dazu drei Handlungen, von denen
#: keine hilft (Regel 17).
#:
#: Die anderen zwei Familien stehen aus einem Grund nicht hier. Die
#: Orca-Familie verschluckt die Ursache: ihr CLI meldet nur
#: „Slic3r::CLI::run found error, exit", und denselben Satz auch bei einem
#: fehlenden Maschinenprofil — er taugt nicht zur Unterscheidung. CuraEngine
#: prüft den Bauraum überhaupt nicht: es schreibt eine Datei, die daneben
#: druckt, und dagegen steht ``arrange.out_of_build_volume`` im Prüfbericht,
#: nicht dieser Satz hier.
OUTSIDE_THE_VOLUME: Final[tuple[str, ...]] = ("outside of the print volume",)
#: Gemessen an ElegooSlicer 1.5.3.4 mit einem offenen Würfel. Die Aussage
#: nennt keine Ursache — offen, zu dünn und falsch skaliert führen alle zu
#: derselben leeren Schichtmenge —, deshalb zählt der Nutzersatz die drei
#: Prüfungen auf, statt eine davon zu behaupten (Regel 21).
NO_LAYERS: Final[tuple[str, ...]] = ("no layers were detected",)


def _says_outside_the_volume(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass nichts im Bauraum liegt?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in OUTSIDE_THE_VOLUME)


def _says_no_layers(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass keine druckbare Schicht entstand?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in NO_LAYERS)


def _tail(*streams: bytes, limit: int = 800) -> str:
    """Das Ende dessen, was der Slicer gesagt hat.

    Der Anfang ist bei allen dieser Programme eine Seite Versionsangaben; was
    erklärt, warum nichts herauskam, steht unten.
    """
    text = "\n".join(stream.decode("utf-8", errors="replace").strip() for stream in streams)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[-limit:]


def _kept_beside(model: Path, produced: Path, *, cancelled: CancelToken | None = None) -> Path:
    """Legt die Druckdatei neben das Modell, bevor der Arbeitsordner
    verschwindet.

    Dieselbe Umwandlung wie in :func:`app.core.export.writer.write_plan` und
    aus demselben Grund: Der Platz kann belegt, der Ordner schreibgeschützt
    oder das Laufwerk voll sein. Ein roher ``OSError`` läuft hier aus einem
    Arbeits-Thread, der nur ``AppError`` fängt — danach geschieht im Fenster
    gar nichts mehr.

    Kopiert wird blockweise in eine Nachbardatei und erst vollständig ersetzt.
    Ein Abbruch lässt deshalb weder eine Teildatei als Ergebnis zurück noch
    überschreibt er eine schon vorhandene Druckdatei.
    """
    target = model.with_suffix(".gcode")
    temporary: Path | None = None
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    try:
        with (
            produced.open("rb") as source,
            tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as destination,
        ):
            temporary = Path(destination.name)
            while True:
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                block = source.read(COPY_BLOCK_BYTES)
                if not block:
                    break
                destination.write(block)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        assert temporary is not None
        temporary.replace(target)
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or target),
            detail=str(problem.strerror or problem),
        ) from problem
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError as problem:
                _log.warning("could not remove partial print file %s: %s", temporary, problem)
    return target


def _find_gcode(directory: Path, expected: str = "") -> Path | None:
    """Die Druckdatei dieses Laufs.

    ``expected`` ist der Name, den Solidon dem Slicer selbst genannt hat —
    PrusaSlicer über ``--output``, CuraEngine über ``-o``. Wo es ihn gibt,
    entscheidet er, und zwar aus einem Grund, der über Ordnung hinausgeht:
    Der Zielordner kann der des Nutzers sein, und dort liegen fremde
    Druckdateien. Die jüngste zu nehmen hieß dann, die Kennzahlen eines
    fremden Programms in den Prüfbericht zu schreiben (Regel 14, §22.5).

    Die Orca-Familie benennt selbst und hängt Plattennummern an; für sie
    bleibt es bei der jüngsten. Und wo der erwartete Name fehlt, wird
    zurückgefallen — aber nicht stillschweigend.
    """
    candidates = [
        entry
        for entry in directory.iterdir()
        # Leer zählt nicht als geschrieben. CuraEngine legt die Datei an,
        # bevor es rechnet, und lässt sie liegen, wenn ihm die Maschine nicht
        # reicht — der Lauf meldete dann Erfolg über null Bytes, und die
        # Kennzahlen daraus waren sämtlich ``None``.
        if entry.is_file()
        and entry.suffix.casefold() in GCODE_SUFFIXES
        and entry.stat().st_size > 0
    ]
    if not candidates:
        return None
    if expected:
        named = [entry for entry in candidates if entry.name == expected]
        if named:
            return named[0]
        _log.warning(
            "the slicer wrote no %s in %s — falling back to the newest print file there",
            expected,
            directory,
        )
    return max(candidates, key=lambda entry: entry.stat().st_mtime)
