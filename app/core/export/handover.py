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
import os
import re
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final
from xml.etree import ElementTree as ET

from app.core import activation, discover, expressions
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
    SPLIT_MODEL,
    ExternalToolError,
    FileWriteError,
    OperationCancelled,
    ValidationError,
)
from app.core.export import manufacturer, slicer_keys, slicer_profiles, threemf
from app.core.export.slicer_keys import (
    SlicerFlavour,
    has_filament_profiles,
    has_key_definitions,
    machine_from_definition,
    names_its_own_output,
    reads_settings_from_project_file,
    takes_a_machine_profile,
    wants_bed_coordinates,
)
from app.core.ingest.threemf import SETTINGS_PATH
from app.core.knowledge import print_settings, profiles
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
    PrinterProfile,
    PrintSettings,
    Profile,
    SettingAdvice,
    SlotOverride,
    SlotProfileBinding,
)
from app.core.units import is_close, is_zero
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

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

#: Crealitys GUI-Startpositionen, aus PartPlate.cpp/set_default_wipe_tower_pos_for_plate.
CREALITY_TOWER_SIDE_OFFSET: Final = 15.0
CREALITY_TOWER_TOP_OFFSET: Final = 35.0

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
#: eingehen und die Solidon selbst nicht setzt (siehe :func:`_cura_computed`).
#: Ausgeschrieben, weil eine Zahl mitten in einer Formel niemandem sagt, woher
#: sie kommt — und weil die Definition nicht auf jedem Rechner liegt.
_SUPPORT_SKIP_PER_MM: Final = 20.0
_SKIN_OVERLAP: Final = 5.0
_INFILL_OVERLAP: Final = 10.0
_MAX_RESOLUTION: Final = 0.5
_IRONING_FLOW: Final = 10.0
_SUPPORT_GROWTH: Final = 0.4
_SUPPORT_BRIM_LINES: Final = 3.0
_STAIR_STEP: Final = 0.3
#: Bis zu dieser Fülldichte stützt Cura die Deckfläche zusätzlich ab. Darüber
#: trägt die Füllung selbst genug.
_SKIN_SUPPORT_BELOW: Final = 0.4
#: Ab dieser Fülldichte lässt Cura die Überlappung weg — die Füllung stößt
#: dann ohnehin an die Wand.
_DENSE_INFILL: Final = 0.95

#: Stütze und Schnittstelle höchstens so schnell, wie die Werksprozesse von
#: Elegoo, Creality und Bambu sie fahren (``support_speed`` 150,
#: ``support_interface_speed`` 80 mm/s). ``fdmprinter`` gibt ihnen die
#: Innenwand und zwei Drittel davon: 214 und 143 mm/s am Ender-3 V3.
_SUPPORT_SPEED: Final = 150.0
_SUPPORT_INTERFACE_SPEED: Final = 80.0
#: Die Schnittstelle zu einem Drittel dicht, wie Creality und Elegoo in Cura
#: (``support_interface_density`` 33,3 %): Linienabstand drei Bahnbreiten.
_INTERFACE_SPACING: Final = 3.0
#: So viel Fläche braucht ein Stützstück mindestens, in mm² (Creality in Cura).
_MINIMUM_SUPPORT_AREA: Final = 2.0
#: Wie überhängende Wände bremsen, wenn der Hersteller keine Stufen nennt
#: (``PrinterProfile.overhang_speed_factors``), in Prozent der Wand: der
#: Vorschlag des Prüfberichts (Cura, B5).
_OVERHANG_FACTORS: Final = (50.0, 25.0)
#: Ab welchem Anteil der Bahnbreite eine Wand in Orcas Stufe 2/4 fällt und
#: gebremst wird (``overhang_2_4_speed``: 25 bis 50 %; die Stufe 1/4 steht
#: bei jedem Hersteller auf 0, also ungebremst).
_OVERHANG_ONSET: Final = 0.25
#: Wie weit der Kopf ohne Rückzug durch das Teil kämmt, in mm: 30 wie
#: Creality in Cura; 10 für ein Filament, das Fäden zieht (Elegoo 9 bis 14,
#: der KE 5). ``fdmprinter`` kennt keine Grenze, und ohne sie kämmte der Kopf
#: beliebig weit ohne Rückzug.
_COMBING_LIMIT: Final = 30.0
_COMBING_LIMIT_STRINGING: Final = 10.0
_STRINGING_MATERIALS: Final = frozenset({"petg", "petg-cf"})
#: Die Leerfahrt der ersten Schicht nie langsamer als die Werksprofile in
#: Cura sie fahren (Elegoo 100 bis 120, Kobra 2 125, Creality 150 mm/s) —
#: oder die Leerfahrt selbst, wenn sie langsamer ist. Curas Formel gab dem
#: Kobra 2 16,9 mm/s (Prüfbericht Cura, B7).
_FIRST_LAYER_TRAVEL: Final = 100.0
#: Die Beschleunigung der ersten Schicht, wenn der Drucker keine eigene trägt
#: (``PrinterProfile.first_layer_acceleration``), in mm/s²: der Wert der
#: Werksprozesse von Elegoo, Bambu, Prusa und Creality-Orca am Ender-3 V3.
_FIRST_LAYER_ACCELERATION: Final = 500.0


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
    plate: str = ""
    """Die Druckplatte, wie die Orca-Familie sie nennt (``Textured PEI Plate``).

    Leer heißt: die Standardplatte der Maschine. Die Konsole nimmt ohne Angabe
    „Cool Plate" mit 35 °C für PLA — gemessen am ElegooSlicer, während das
    Fenster am Centauri Carbon 2 die texturierte PEI-Platte wählt (Konzept
    Herstellerprofil, Entscheidung F, 27.09.2026).
    """

    @property
    def name(self) -> str:
        return self.executable.stem


def _profile_roots(setup: SlicerSetup) -> tuple[Path, ...]:
    """Der ganze Profilbestand dieser Installation — für die Erbkette eines
    eigenen Profils, die aus ``user/`` in ``resources/profiles/`` hinüberreicht
    (:func:`app.core.export.slicer_profiles.profile_roots`)."""
    return slicer_profiles.profile_roots(setup.flavour, setup.executable)


def profile_source(
    chosen: str, setup: SlicerSetup, kind: slicer_profiles.ProfileKind
) -> Path | slicer_profiles.SlicerProfile | None:
    """Einzeldatei oder vollständige Profilidentität einschließlich Prusa-Abschnitt."""
    if not chosen:
        return None
    direct = Path(chosen)
    if direct.is_file():
        return direct
    found = slicer_profiles.profile_by_name(setup.executable, setup.flavour, chosen, kind)
    if found is not None and found.path.is_file():
        return found
    _log.warning("no %s profile named %r in this slicer", kind, chosen)
    return None


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

    Zum Lesen von Werten gilt :func:`profile_source`: Eine Prusa-Bündeldatei
    allein benennt kein Profil; ihr Abschnitt muss dabei erhalten bleiben.
    """
    source = profile_source(chosen, setup, kind)
    return source.path if isinstance(source, slicer_profiles.SlicerProfile) else source


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
        if not _fits_the_printer(setup.machine_profile, profile):
            return ""
        return slicer_profiles.machine_with_nozzle(
            setup.machine_profile, setup.flavour, setup.executable, profile.printer
        )
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
    fitting = slicer_profiles.machine_with_nozzle(
        chosen, setup.flavour, setup.executable, profile.printer
    )
    if fitting != chosen:
        _log.info(
            "slicer is set to %r, the project prints with a %g mm nozzle — handing over %r",
            chosen,
            profile.printer.nozzle_diameter,
            fitting or "no machine side",
        )
    return fitting


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


def foundation_findings(
    settings: PrintSettings, profile: Profile, setup: SlicerSetup | None
) -> list[Finding]:
    """Was der Kunde über die Grundlage wissen muss — Platte und lesbares
    Prozessprofil (:func:`app.core.export.manufacturer.findings`)."""
    if setup is None or setup.flavour != "orca":
        return []
    return manufacturer.findings(manufacturer.base_settings(profile, settings.quality, setup))


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

    **PrusaSlicer bekommt keinen Befund.** Der Befund galt einen halben Tag
    lang weiter, als er gemeint war: Seine Maschinenseite baut
    :func:`_machine_keys` aus dem eigenen Druckerprofil, und eine ``.ini`` ist
    eigenständig lauffähig, sobald Düse und Bettform darin stehen. Gemessen am
    03.09.2026 bekam es bei jedem Export ein ``slicer.machine_unset`` und den
    Rat, im Slicer einen Drucker einzurichten, den es dafür nicht braucht.
    Eine Warnung, die nicht stimmt, ist teurer als keine.

    **Cura bekommt einen, wenn es den Drucker nicht kennt.** Bis zum
    27.09.2026 schwieg die Stelle auch für Cura, mit derselben Begründung —
    und die war dort falsch: CuraEngine druckte dann mit dem Startcode von
    ``fdmprinter`` (``G28``, drei Millimeter Filament in 15 mm Höhe, keine
    Spüllinie, kein Bettnetz). Jetzt kommt die Maschine aus der
    Druckerdefinition (:func:`_cura_machine`); fehlt sie, sagt es dieser
    Befund.
    """
    if machine_from_definition(setup.flavour):
        return _cura_printer_unknown(setup, profile)
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
    if not slicer_profiles.supports_printer(setup.flavour, setup.executable, profile.printer.title):
        # **Der Rat darunter zeigte hier ins Leere.** „Wählen Sie das
        # Maschinenprofil in den Druckeinstellungen" setzt voraus, dass es
        # eines gibt; bringt der Slicer für diesen Drucker gar keines mit,
        # sucht der Kunde in einer Liste, in der nichts steht. Der Unterschied
        # ist messbar: ElegooSlicer kennt 1001 Drucker und den Centauri
        # Carbon 2 darunter, PrusaSlicer kennt 261 und ihn nicht.
        return [
            Finding(
                code="slicer.printer_unknown",
                severity="warning",
                message=_(
                    "{slicer} kennt {printer} nicht — für diesen Drucker liegt dort kein "
                    "Maschinenprofil, und es ist auch keines auszuwählen. Die Datei trägt "
                    "deshalb keine Maschinenangaben. Richten Sie den Drucker im Slicer ein "
                    "oder übergeben Sie an einen Slicer, der ihn kennt.",
                    slicer=setup.name,
                    printer=profile.printer.title,
                ),
                values={"slicer": setup.name, "printer": profile.printer.title},
                suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
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


def _cura_printer_unknown(setup: SlicerSetup, profile: Profile) -> list[Finding]:
    """Der Befund, wenn diese Cura-Installation den Drucker nicht führt.

    Ohne lesbare Definitionen sagt er nichts: Dann startet CuraEngine gar
    nicht, und die Absage des Laufs nennt den Grund.
    """
    if not _cura_base(setup.executable) or _cura_printer_definition(
        setup.executable, profile.printer
    ):
        return []
    return [
        Finding(
            code="slicer.cura_printer_unknown",
            severity="warning",
            message=_(
                "Cura kennt „{printer}“ nicht. Die Druckdatei beginnt deshalb ohne den "
                "Startcode des Herstellers, ohne Spüllinie und ohne Bettnetz.",
                printer=profile.printer.title,
            ),
            values={"printer": profile.printer.title, "slicer": setup.name},
            suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
        )
    ]


def detect(executable: Path | str) -> SlicerSetup:
    """Was für ein Slicer das ist. Erkennt an seinem Namen (§29).

    Ein Programm, dessen Namen Solidon nicht kennt, ist seit dem 22.09.2026
    kein Fehler mehr, sondern die Familie ``other``: Es bekommt die Datei ins
    Fenster und sonst nichts. Bis dahin scheiterte schon das bloße Öffnen an
    einer Übersetzung, die beim Öffnen niemand braucht — ein Resin-Slicer
    kam damit nie an die Reihe (Resin-Konzept §4). Dass der Konsolenlauf für
    diese Familie nicht führt, sagt :func:`slice_model` an seiner Stelle.
    """
    path = Path(executable)
    flavour = slicer_keys.flavour_of(path.name)
    return SlicerSetup(executable=path, flavour=flavour or "other")


def only_opens(setup: SlicerSetup) -> bool:
    """Bekommt dieses Programm die Datei nur ins Fenster — ohne Profil,
    Konfiguration und Konsolenlauf?"""
    return setup.flavour == "other"


def _refuse_untranslated(setup: SlicerSetup) -> None:
    """Der Konsolenweg gibt es für ein Programm ohne Familie nicht (§29)."""
    if only_opens(setup):
        raise ExternalToolError(
            tool=setup.name,
            detail=_(
                "Solidon kennt die Kommandozeile dieses Programms nicht. Öffnen Sie die "
                "Datei in seinem Fenster oder wählen Sie einen anderen Slicer."
            ),
            suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
        )


def as_mapping(
    settings: PrintSettings,
    flavour: SlicerFlavour,
    paths: frozenset[str] | None = None,
) -> dict[str, str]:
    """Die Einstellungen in der Sprache dieses Slicers (§29).

    Ohne Datei und ohne Aufruf — die Tests prüfen die Zuordnung, ohne dass ein
    Slicer installiert sein muss, und die Gegenprobe vergleicht dagegen. Alle
    Profile zusammen, weil die Gegenprobe die Druckdatei als Ganzes liest und
    dort nicht mehr steht, aus welchem Profil ein Wert kam.

    Was hier herauskommt, ist die **Einstellungsseite**: die Zuordnung, und was
    sich allein aus den Einstellungen umrechnen lässt. Die Maschine kommt in
    :func:`_machine_keys` dazu, das Abgeleitete in :func:`_cura_dependants` —
    beides führt :func:`values_for` zusammen, und nur diese eine Stelle.

    ``paths`` beschränkt auf die Punktpfade, die vom Herstellerprofil
    abweichen sollen (Konzept Herstellerprofil, Entscheidung D); ``None``
    heißt alle — dort, wo kein Herstellerprofil darunter liegt. Was ohne
    seinen Partner nicht wirkt, kommt mit (:data:`COUPLED_PATHS`).
    """
    settings = _fan_curve_in_order(settings)
    if paths is not None:
        paths = _with_partners(paths, settings)
    written: dict[str, str] = {}
    for entry in slicer_keys.TABLES[flavour]:
        if paths is not None and entry.path not in paths:
            continue
        value = entry.write(read_path(settings, entry.path))
        # Ein leerer Text heißt „dazu sagt Solidon nichts" (siehe
        # ``_number_or_silent``). Er darf weder in die Datei noch in die
        # Gegenprobe: geschrieben überschriebe er den Wert des Herstellers,
        # verglichen meldete er eine Abweichung von nichts.
        if value != "":
            written[entry.key] = value
    chosen = _only_chosen_adhesion(written, settings, flavour)
    if flavour == "cura":
        return _cura_fan_start(_first_layer_width(chosen), settings)
    if paths is not None and "support.density" not in paths:
        return chosen
    return _support_spacing(chosen, settings, flavour)


#: Werte, die ohne ihren Partner nicht tun, was die Wahl verlangt (Review
#: Stufe A+B, F4 und F7). Eine Haftungsart schreibt die Maße aller Arten,
#: damit :func:`_only_chosen_adhesion` die nicht gewählten nullen kann —
#: „Keine" ließ sonst den Skirt des Herstellers stehen. Eine eigene
#: Lüfter-Obergrenze nimmt das untere Ende mit: Elegoo PLA fährt unten 50 %,
#: und wer oben 20 % wählte, bekam lange Schichten mit 50.
COUPLED_PATHS: Final[Mapping[str, tuple[str, ...]]] = {
    "adhesion.kind": (
        "adhesion.skirt_loops",
        "adhesion.brim_width",
        "adhesion.raft_layers",
    ),
    "cooling.fan_speed": ("cooling.minimum_fan_speed",),
}


def _with_partners(paths: frozenset[str], settings: PrintSettings) -> frozenset[str]:
    """Die Pfade samt ihrer Partner aus :data:`COUPLED_PATHS`.

    Außer bei „Automatisch": Dessen Skirt gehört dem Herstellerprofil, und
    die Brimbreite misst der Auto-Brim selbst.
    """
    extra: set[str] = set()
    for path, partners in COUPLED_PATHS.items():
        if path not in paths:
            continue
        if path == "adhesion.kind" and settings.adhesion.kind == "auto":
            continue
        extra.update(partners)
    return paths | extra


def _fan_curve_in_order(settings: PrintSettings) -> PrintSettings:
    """Der untere Lüfterwert höchstens so hoch wie der obere (§29).

    Beide Enden der Kurve sind einzeln einstellbar, und ein Vorschlag senkt
    nur das obere (``advise``: Zugluft auf ABS). Ein unterer Wert darüber
    hieße, je länger die Schicht, desto stärker der Lüfter — Orca und
    PrusaSlicer rechnen die Gerade trotzdem, Curas ``cool_fan_speed_max`` hat
    kein ``max()``. Das obere Ende ist als Höchstwert gemeint, also gilt es.
    Hier und nicht in der Tabelle, weil eine Zeile nur ihren eigenen Wert
    sieht; alle drei Familien und die Gegenprobe lesen über diese Stelle.
    """
    cooling = settings.cooling
    if cooling.minimum_fan_speed <= cooling.fan_speed:
        return settings
    return replace(settings, cooling=replace(cooling, minimum_fan_speed=cooling.fan_speed))


def values_for(settings: PrintSettings, profile: Profile, flavour: SlicerFlavour) -> dict[str, str]:
    """Alles, was dieser Slicer bekommt — Einstellungen, Maschine, Abgeleitetes.

    Die eine Stelle, an der die drei Stufen zusammenkommen. Sie hat einen
    Grund, und der ist die Reihenfolge: ``CuraEngine`` rechnet aus der
    Bahnbreite zwölf weitere und aus dem Düsendurchmesser sieben, und der
    Düsendurchmesser steht in der Maschine. Wer die Ableitung vor dem
    Zusammenführen laufen ließe, bekäme die Hälfte.
    """
    values = as_mapping(_adhesion_for(settings, profile, flavour), flavour)
    values |= _machine_keys(profile, flavour)
    if flavour == "cura":
        values = _cura_dependants(values, settings, profile)
    _without_line_break(values, flavour)
    return values


def _adhesion_for(
    settings: PrintSettings, profile: Profile, flavour: SlicerFlavour
) -> PrintSettings:
    """„Automatisch" dort, wo der Slicer keinen Auto-Brim kennt (Entscheidung J).

    Die Orca-Familie hat ``auto_brim``; PrusaSlicer und CuraEngine nicht. Dort
    heißt „Automatisch" die Art aus Solidons Tabelle für dieses Material —
    bis Stufe C und D ist sie für beide die Grundlage. Ohne diese Abbildung
    bekam Cura einen Skirt mit null Linien und PrusaSlicer an jedem Teil einen
    Brim (Review Stufe A+B, F5).
    """
    if settings.adhesion.kind != "auto" or flavour not in ("prusa", "cura"):
        return settings
    table = print_settings.resolve(profile, settings.quality).adhesion
    measures = {
        name: getattr(table, name)
        for name in ("skirt_loops", "brim_width", "raft_layers")
        if getattr(settings.adhesion, name) <= 0
    }
    return replace(settings, adhesion=replace(settings.adhesion, kind=table.kind, **measures))


def by_section(
    settings: PrintSettings,
    flavour: SlicerFlavour,
    paths: frozenset[str] | None = None,
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
    complete = as_mapping(settings, flavour, paths)
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
        # Der Auto-Brim misst mit der Brimbreite — sie bleibt stehen.
        if wanted == kind or (kind == "auto" and wanted == "brim"):
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


def _cura_dependants(
    written: dict[str, str], settings: PrintSettings, profile: Profile
) -> dict[str, str]:
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
    _cura_computed(written, settings, profile)
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


def _cura_fan_start(written: dict[str, str], settings: PrintSettings) -> dict[str, str]:
    """Die Schichten ohne Lüfter als Curas Hochlauf (26.09.2026).

    Cura kennt keine Lüfterpause, nur einen Hochlauf vom Anfangslüfter bis zu
    einer Höhe, aus der es die Schicht ``cool_fan_full_layer`` rechnet. Mit
    Anfangslüfter null und der Höhe in der ersten Schicht nach der Pause ist
    das für null und eine Schicht ohne Lüfter die Pause selbst — solange die
    Schicht lange genug dauert: Kürzere kühlt Cura auch dort stärker, was
    :func:`fan_in_off_layers` in der Druckdatei nachmisst. Ab zwei Schichten
    laufen die dazwischen schon an (``slicer_keys.limitation``).

    Die Mitte der Schicht und nicht ihre Oberkante, weil Cura abrundet: Auf
    der Kante entschiede der letzte Bitfehler über eine ganze Schicht. Steht
    hier und nicht in :func:`_cura_dependants`, weil das Cura-Fenster nur
    diese Seite bekommt (:func:`cura_profile_beside`). Vorher bekam es nichts
    davon, und die Konsole fest die zweite Schicht — jede Cura-Übergabe
    meldete die Pause als verloren, auch die, bei der nichts abwich.
    """
    first = _as_float(written.get("layer_height_0"))
    layer = _as_float(written.get("layer_height"))
    if first is None or not layer:
        return written
    off = max(0, settings.cooling.disable_first_layers)
    written["cool_fan_speed_0"] = "0"
    written["cool_fan_full_at_height"] = f"{max(0.0, first + (off - 0.5) * layer):g}"
    return written


def _cura_computed(written: dict[str, str], settings: PrintSettings, profile: Profile) -> None:
    """Die gerechneten Ableitungen — je Zeile die Formel aus der Definition.

    Keine eigene Meinung darüber, was richtig wäre: was hier steht, hätte das
    Cura-Fenster genauso gerechnet, bevor es die Werte weitergibt.
    """
    _from_line_width(written, settings)
    _for_supports(written, settings)
    _for_speeds(written, settings, profile)
    _for_overhangs(written, profile.printer)
    _factory_habits(written, profile)
    _full_fan_layer(written)


def _full_fan_layer(written: dict[str, str]) -> None:
    """Ab welcher Schicht der Lüfter voll läuft — aus der Höhe, die
    :func:`_cura_fan_start` schreibt."""
    height = _as_float(written.get("cool_fan_full_at_height"))
    first = _as_float(written.get("layer_height_0"))
    layer = _as_float(written.get("layer_height"))
    if height is None or first is None or not layer:
        return
    written["cool_fan_full_layer"] = str(max(1, math.floor((height - first) / layer) + 2))


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
    """Die Stützen, wie die Werksprofile sie in Cura legen (Prüfbericht Cura, B4).

    Die Stütze selbst bleibt Curas ``zigzag``, eine verbundene Linienschar,
    die nicht kippt; Solidons Gitter ist an Orcas unverbundenem
    ``rectilinear`` begründet und steht nur dort (``slicer_keys``). Die
    Schnittstelle ist bei Cura eine Höhe, keine Schichtzahl, und CuraEngine
    liest nur die Blätter: ``support_roof_pattern``, nicht
    ``support_interface_pattern``.
    """
    width = _as_float(written.get("line_width"))
    density = settings.support.density
    tree = settings.support.style == "tree"
    if width:
        # Curas Formel: Der Baum trägt keine Füllung, nur seine Wand
        # (``support_infill_rate`` 0 beim Baum, ``support_wall_count`` 1).
        distance = width / density if density > 0.0 and not tree else 0.0
        written["support_line_distance"] = f"{distance:g}"
        # Auf den eben gerechneten Abstand, nicht noch einmal auf die Breite:
        # zwei Formeln für dieselbe Sache laufen irgendwann auseinander.
        written["support_zag_skip_count"] = (
            "0" if distance <= 0.0 else str(round(_SUPPORT_SKIP_PER_MM / distance))
        )
        # Die Schnittstelle in Linien zu einem Drittel, wie Creality und Elegoo
        # in Cura. ``fdmprinter`` legt sie konzentrisch und voll — eine Decke,
        # die schwer abgeht und die Unterseite mit Ringen zeichnet.
        for key in ("support_roof_pattern", "support_bottom_pattern"):
            written[key] = "lines"
        spacing = width * _INTERFACE_SPACING
        for key in ("support_roof_line_distance", "support_bottom_line_distance"):
            written[key] = f"{spacing:g}"
        # Die Stütze wächst um eine Bahnbreite plus Curas festen Zuschlag —
        # beim Baum um nichts.
        written["support_offset"] = "0" if tree else f"{width + _SUPPORT_GROWTH:g}"
        written["support_wall_count"] = "1" if tree else "0"
    # Krümel unter 2 mm² bekommen keine eigene Stütze (Creality in Cura).
    written["minimum_support_area"] = f"{_MINIMUM_SUPPORT_AREA:g}"

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


def _for_speeds(written: dict[str, str], settings: PrintSettings, profile: Profile) -> None:
    """Geschwindigkeiten, Temperaturen und die Schalter, ohne die sie nicht gelten."""
    # Ohne diesen gelten weder die Brückengeschwindigkeit noch der
    # Brückenlüfter — beide stehen in Cura dahinter, und Solidon schreibt beide.
    written["bridge_settings_enabled"] = "true"
    # Beide Muster, die Cura für Solidons Füllungen ausrechnet, fallen auf
    # dieselbe Antwort: ``cross`` und ``cubicsubdiv`` werden hier nicht
    # angeboten.
    written["connect_infill_polygons"] = "false"
    written["skirt_height"] = "3" if settings.adhesion.skirt_distance > 0.0 else "1"
    # **Die erste Schicht mit der Beschleunigung des Herstellers** (Prüfbericht
    # Cura, B2). ``acceleration_layer_0`` spiegelte ``acceleration_print``, und
    # der Ender-3 V3 fuhr Skirt und erste Schicht mit 12 000 mm/s² — Creality
    # fährt dort 500. Nie schneller als der Rest; die Blätter folgen über
    # ``CURA_MIRRORED``. Die Leerfahrt der ersten Schicht rechnet Cura mit
    # ``acceleration_layer_0 * acceleration_travel / acceleration_print``, und
    # weil die Fahrt mit der Druckbeschleunigung fährt (``CURA_MIRRORED``),
    # ist das die Beschleunigung der ersten Schicht selbst.
    printing_acceleration = _as_float(written.get("acceleration_print"))
    if printing_acceleration:
        first = profile.printer.first_layer_acceleration or _FIRST_LAYER_ACCELERATION
        first = min(first, printing_acceleration)
        written["acceleration_layer_0"] = f"{first:g}"
        written["acceleration_travel_layer_0"] = f"{first:g}"

    printing = _as_float(written.get("speed_print"))
    if printing:
        # Stütze und Schnittstelle wie in den Werksprozessen, nie schneller als
        # die Innenwand (``fdmprinter``: ``speed_support = speed_print``) und
        # die Schnittstelle nie schneller als die Außenwand. Die beiden Seiten
        # der Schnittstelle und die Stützfüllung erben davon.
        support = min(printing, _SUPPORT_SPEED)
        for key in ("speed_support", "speed_support_infill"):
            written[key] = f"{support:g}"
        wall = _as_float(written.get("speed_wall_0")) or printing
        interface = f"{min(wall, _SUPPORT_INTERFACE_SPEED):g}"
        for key in ("speed_support_interface", "speed_support_roof", "speed_support_bottom"):
            written[key] = interface
        first_layer = _as_float(written.get("speed_layer_0"))
        travel = _as_float(written.get("speed_travel"))
        if first_layer and travel:
            formula = first_layer * travel / printing
            floor = min(travel, _FIRST_LAYER_TRAVEL)
            written["speed_travel_layer_0"] = f"{max(formula, floor):g}"

    surface = _as_float(written.get("speed_topbottom"))
    if surface:
        written["speed_ironing"] = f"{surface * 20.0 / 30.0:g}"

    nozzle = _as_float(written.get("material_print_temperature"))
    if nozzle:
        # Curas Vorgabe fährt die Düse vor dem ersten und nach dem letzten
        # Zug etwas kühler. Nachgerechnet, nicht überstimmt.
        written["material_initial_print_temperature"] = f"{nozzle - 10.0:g}"
        written["material_final_print_temperature"] = f"{nozzle - 15.0:g}"


def _for_overhangs(written: dict[str, str], printer: PrinterProfile) -> None:
    """Überhängende Wände bremsen wie beim Hersteller (Prüfbericht Cura, B5).

    Orca bremst ab einem Viertel Bahnbreite Überhang in Stufen
    (``overhang_2_4_speed`` bis ``overhang_4_4_speed``). Cura teilt den Bereich
    zwischen ``wall_overhang_angle`` und 90 Grad in gleiche Winkelschritte,
    einen je Faktor, und misst den Überhang an der Mitte der Außenwand gegen
    die Schicht darunter (``FffGcodeWriter.cpp``, CuraEngine 5.13) — der Winkel
    einer Wand, die je Schicht um ein Viertel Bahnbreite auswandert, ist also
    ``atan(0,25 * Bahnbreite / Schichthöhe)``. Dort beginnt die erste Stufe,
    und die letzte gilt zweimal: Bei 0,42 auf 0,2 mm liegen Curas Grenzen dann
    bei 28, 43, 59 und 75 Grad, Orcas bei 28, 46, 58 und 64.

    Ohne Stufen des Herstellers bremst Cura mit 50 und 25 Prozent ab
    demselben Winkel.
    """
    width = _as_float(written.get("line_width"))
    height = _as_float(written.get("layer_height"))
    if not width or not height:
        return
    factors = printer.overhang_speed_factors
    steps = (*factors, factors[-1]) if factors else _OVERHANG_FACTORS
    # Eine Winkelfunktion aus ``math`` ist hier erlaubt: Das Ergebnis ist ein
    # Wert für den Slicer, auf ganze Grad gerundet, keine Geometrie (kern.md).
    onset = math.degrees(math.atan(_OVERHANG_ONSET * width / height))
    written["wall_overhang_angle"] = f"{round(onset)}"
    written["wall_overhang_speed_factors"] = (
        "[" + ",".join(f"{round(step)}" for step in steps) + "]"
    )


def _factory_habits(written: dict[str, str], profile: Profile) -> None:
    """Was ``fdmprinter`` anders vorgibt als die Werksprofile in Cura (B6, B11, B12).

    Creality, Anycubic, Sovol und Elegoo setzen diese Werte in Cura als
    Formel, und Formeln liest die Konsole nicht — ohne Solidons Zeile gälte
    ``fdmprinter``, nicht das Profil des Herstellers.
    """
    # Die Füllung nach den Wänden. ``fdmprinter`` druckt sie vorher, und ihr
    # Muster zeichnet sich durch die Außenwand (gemessen: FILL, WALL-INNER,
    # WALL-OUTER). Creality, Anycubic und Sovol stellen in Cura ``false``.
    written["infill_before_walls"] = "false"
    # Kämmen ohne Rückzug nur ein Stück weit, bei PETG kürzer.
    stringing = profile.material.id in _STRINGING_MATERIALS
    limit = _COMBING_LIMIT_STRINGING if stringing else _COMBING_LIMIT
    written["retraction_combing_max_distance"] = f"{limit:g}"
    # Der Z-Sprung nur über gedruckten Teilen, nicht bei jedem Rückzug, und
    # die Fahrt umgeht Stützen (Creality, Anycubic in Cura).
    written["retraction_hop_only_when_collides"] = "true"
    written["travel_avoid_supports"] = "true"
    # Die Naht bevorzugt verdeckte Ecken, wie Creality, Sovol und Elegoo.
    written["z_seam_corner"] = "z_seam_corner_weighted"


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
    dem Fenster. Sie liest aus einer Definition nur Vorgabewerte, keine
    Formeln — was das Fenster sonst aus Definition, Qualität, Material und
    Variante zusammenrechnet, muss ihr einzeln mitgegeben werden. Die
    Maschine selbst (Start- und Endcode, Name, Grenzen) kommt aus der
    Druckerdefinition (:func:`_cura_machine`); die Werte hier gelten über ihr.

    Der Kopf der Druckdatei bleibt dabei ein Platzhalter: ``;TIME:6666``,
    ``;Filament used: 0m`` und ``;MINX:2.14748e+06`` schreibt CuraEngine im
    Konsolenbetrieb immer, mit oder ohne Bettmaße — das Fenster ersetzt den
    Kopf erst nachträglich. Zeit und Material liest :mod:`app.core.slice.gcode`
    deshalb aus ``;TIME_ELAPSED`` und der Summe der Förderung.
    """
    if flavour == "cura":
        width, depth, height = profile.printer.build_volume
        return {
            "machine_width": f"{width:g}",
            "machine_depth": f"{depth:g}",
            "machine_height": f"{height:g}",
            "machine_nozzle_size": f"{profile.printer.nozzle_diameter:g}",
            "machine_heated_bed": "true" if profile.printer.bed_temperature_max > 0.0 else "false",
            # Die Maschine misst von der Ecke, und die Teile kommen in ihren
            # Koordinaten (``wants_bed_coordinates``). ``true`` stand hier
            # bis zum 05.09.2026 und erklärte dem Slicer eine Maschine, die
            # es nicht gibt — die Bahnen lagen um den halben Bauraum neben
            # der Platte (Gesamtreview, CORE-17).
            "machine_center_is_zero": "false",
            # Wo „hinten" liegt, wenn die Naht dorthin soll: hinten in der
            # Mitte, in Bettkoordinaten. Cura sucht den Konturpunkt, der diesem
            # hier am nächsten liegt; ohne die Angabe stünde er bei (100, 100)
            # und damit irgendwo. Gelesen wird er nur bei ``z_seam_type=back``,
            # geschrieben immer: ein Punkt, den niemand abfragt, kostet nichts.
            "z_seam_x": f"{width / 2.0:g}",
            "z_seam_y": f"{depth:g}",
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
    # Ab der Ecke, wie die Maschine: Die Teile kommen in Bettkoordinaten
    # (``wants_bed_coordinates``), und die Bettform beschreibt dieselbe Welt
    # — die des Druckers, dessen Nullpunkt vorn links liegt. Eine Form von
    # ``-128`` bis ``128`` über verschobenen Teilen endete in „All objects
    # are outside of the print volume"; dieselbe Form über unverschobenen
    # Teilen ließ den Slicer Bahnen bei ``-13,6`` schreiben, die es auf der
    # Maschine nicht gibt (Gesamtreview 05.09.2026, CORE-17).
    corners = f"0x0,{width:g}x0,{width:g}x{depth:g},0x{depth:g}"
    return {
        "nozzle_diameter": f"{printer.nozzle_diameter:g}",
        "bed_shape": corners,
        "max_print_height": f"{height:g}",
        # **Die Grenzen der Maschine kennt Solidon nicht** (RM-191). Mit der
        # Vorgabe ``time_estimate_only`` schätzte PrusaSlicer mit seinen
        # eingebauten 1500 mm/s² — ein Fünftel der Beschleunigung, die die
        # Datei selbst anfordert —, und die Druckzeit stand doppelt so hoch
        # wie bei Orca für dieselbe Platte. ``ignore`` schreibt keine Grenzen
        # in den G-Code (die Firmware behält ihre) und schätzt mit den
        # Werten, die Solidon verlangt.
        "machine_limits_usage": "ignore",
    }


@dataclass(frozen=True, slots=True)
class CuraMesh:
    """Ein Netz für CuraEngine und die Werte, die nur ihm gelten (``-s`` nach ``-l``).

    Heute trägt nur die Stützsperre Werte (``anti_overhang_mesh``); Stufe E des
    Konzepts setzt an den Teilen ``support_enable`` je Teil.
    """

    path: Path
    settings: Mapping[str, str] = field(default_factory=dict)


#: Wie die Netzliste neben dem Modell heißt (:func:`write_cura_meshes`).
CURA_MESHES_SUFFIX: Final = ".meshes.json"

#: Wie ein Einstellungsname aussieht, der je Netz mitreisen darf.
_SETTING_NAME: Final = re.compile(r"[a-z0-9_]+")


def write_cura_meshes(model: Path, meshes: Sequence[CuraMesh]) -> Path:
    """Legt neben das Modell die Liste seiner Netze für CuraEngine.

    Das Modell selbst bleibt das zusammengelegte STL — die Datei, die Curas
    Fenster öffnet. Die Kommandozeile liest stattdessen diese Liste
    (:func:`cura_meshes`): je Teil ein Netz und jede Sperre als eigenes, mit
    ihren Werten. So geht der Weg über den Druckdialog unverändert: Er reicht
    ein Modell weiter, und die Übergabe findet daneben, was dazugehört.
    """
    target = model.with_suffix(CURA_MESHES_SUFFIX)
    document = {
        "meshes": [{"file": mesh.path.name, "settings": dict(mesh.settings)} for mesh in meshes]
    }
    try:
        target.write_text(json.dumps(document, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError as problem:
        raise FileWriteError(
            target=target.name, detail=problem.strerror or str(problem)
        ) from problem
    return target


def cura_meshes(model: Path) -> tuple[CuraMesh, ...]:
    """Die Netze, die CuraEngine für dieses Modell lädt — ohne Liste das Modell selbst.

    Die Liste schreibt Solidon selbst (:func:`write_cura_meshes`), aber sie
    liegt in einem Ordner, und was dort steht, wird geprüft, bevor es zu
    Argumenten wird: Dateinamen ohne Pfad, die daneben liegen, Werte ohne
    Umbruch unter einfachen Namen. Eine Liste, die das nicht erfüllt, hält
    an, statt still das Modell ohne Sperre zu rechnen.
    """
    listing = model.with_suffix(CURA_MESHES_SUFFIX)
    if not listing.is_file():
        return (CuraMesh(model),)
    try:
        document = json.loads(listing.read_text(encoding="utf-8"))
        meshes: list[CuraMesh] = []
        for entry in document["meshes"]:
            name, values = entry["file"], entry.get("settings", {})
            if not isinstance(name, str) or Path(name).name != name or not name.endswith(".stl"):
                raise ValueError(name)
            path = model.parent / name
            if not path.is_file() or not isinstance(values, dict):
                raise ValueError(name)
            for key, value in values.items():
                if not (
                    isinstance(key, str)
                    and _SETTING_NAME.fullmatch(key)
                    and isinstance(value, str)
                    and _single_line(value)
                ):
                    raise ValueError(key)
            meshes.append(CuraMesh(path, dict(values)))
        if not meshes:
            raise ValueError(listing.name)
    except (OSError, ValueError, KeyError, TypeError) as problem:
        raise ExternalToolError(
            tool=model.name,
            title=SLICER_FAILED,
            detail=_(
                "Die Teile für Cura sind unvollständig geschrieben. Slicen Sie noch "
                "einmal, dann entstehen sie neu."
            ),
            values={"file": listing.name},
            suggestions=(RETRY, EXPORT_ONLY),
        ) from problem
    return tuple(meshes)


@dataclass(frozen=True, slots=True)
class CuraMachine:
    """Was CuraEngine über die Maschine bekommt, neben Solidons Werten.

    ``definition`` ist die Datei hinter ``-j``: die Druckerdefinition aus
    ``PrinterProfile.cura_definition``, sonst ``fdmprinter``. CuraEngine löst
    ihre Erbkette selbst auf und lädt die Extruderzüge aus
    ``machine_extruder_trains`` (gemessen mit Cura 5.13, 27.09.2026); dafür
    braucht es die Ordner in ``search_path`` hinter ``-d``, sonst meldet es
    „Couldn't find definition file with ID: creality_base_extruder_0".

    ``codes`` sind Start- und Endcode mit gefüllten Platzhaltern. Sie tragen
    Zeilenumbrüche und reisen deshalb als eigene ``-s``-Argumente, nicht in
    ``solidon_cura.txt``. ``switches`` sind die zwei Schalter, mit denen
    CuraEngine seine eigenen Temperaturbefehle vor den Startcode setzt.
    """

    definition: Path | None = None
    from_printer: bool = False
    """Kommt die Maschine aus einer Druckerdefinition und nicht aus ``fdmprinter``?"""
    search_path: tuple[Path, ...] = ()
    codes: Mapping[str, str] = field(default_factory=dict)
    switches: Mapping[str, str] = field(default_factory=dict)


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
    written: Mapping[str, str] = field(default_factory=dict)
    """Die tatsächlich geschriebenen Sollwerte, einschließlich aller Filamentplätze."""
    cura_machine: CuraMachine | None = None
    """Nur bei Cura: Druckerdefinition, Start- und Endcode (:func:`_cura_machine`)."""

    @property
    def filament(self) -> Path | None:
        """Das erste Filament. Für alles, was nur eines kennt."""
        return self.filaments[0] if self.filaments else None


def settings_for_slot(
    settings: PrintSettings,
    profile: Profile,
    slot: MaterialSlot,
    setup: SlicerSetup | None = None,
) -> PrintSettings:
    """Die Einstellungen, mit denen dieser eine Slot fährt (§20, §29).

    Vier Spulen sind nicht vier Farben desselben Materials: Ein Schriftzug in
    PLA auf einem Gehäuse aus PETG fährt 210 Grad statt 250. Ohne diese
    Auflösung bekamen alle Slots die Werte des Projektmaterials, und die
    zweite Spule fuhr mit den Temperaturen der ersten.

    Die eindeutige Materialart der Spule liefert die Materialgruppen, wenn
    sie vom Projektmaterial abweicht. Prozesswerte bleiben erhalten.
    Mit bekanntem Slicer liefert das gebundene Herstellerprofil seine Werte
    aus der ganzen Erbkette. Ausdrückliche Spulenwerte gewinnen anschließend
    gruppenweise; Beratung und Ausgabe benutzen dieselbe Reihenfolge.
    """
    material_id = profiles.material_id_for_type(slot.material_type or "")
    if material_id and material_id != profile.material.id:
        defaults = print_settings.resolve(
            replace(profile, material=profiles.material(material_id)), settings.quality
        )
        settings = replace(
            settings,
            temperature=defaults.temperature,
            cooling=defaults.cooling,
            retraction=defaults.retraction,
            filament=defaults.filament,
        )
    if setup is not None and slot.material:
        source = profile_source(slot.material, setup, "filament")
        if source is not None:
            for path, value in slicer_profiles.filament_values(
                source, _profile_roots(setup)
            ).items():
                settings = with_path(settings, path, value)
    override = override_for(settings, slot)
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
    *,
    profile: Profile | None = None,
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
    present = {threemf.slot_identity(slot) for slot in slots}
    unassigned = [
        entry
        for entry in settings.slot_overrides
        if entry is not None
        and not entry.empty
        and entry.key not in present
        and any(entry.key[:2] == identity[:2] for identity in present)
    ]
    findings = (
        [
            Finding(
                code="slicer.overrides_unassigned",
                severity="warning",
                message=_(
                    "Gespeicherte Filamentwerte sind keinem aktuellen Material eindeutig "
                    "zugeordnet und werden nicht verwendet. Öffnen Sie die Werte der "
                    "betroffenen Spule und übernehmen oder ersetzen Sie die alten Werte."
                ),
                values={"slots": len(unassigned)},
            )
        ]
        if unassigned
        else []
    )
    if has_filament_profiles(setup.flavour):
        return findings
    reachable = threemf.slot_identity(slots[0]) if slots else None
    affected = {
        entry.key
        for entry in settings.slot_overrides
        if entry is not None
        and not entry.empty
        and (not present or entry.key in present)
        and (reachable is None or entry.key != reachable)
    }
    # Auf diesem Übergabeweg bleibt auch von zwei PLA-Farben nur ein Filament.
    # Gleiche Druckwerte machen die zweite Spule nicht zur ersten. Dieselbe
    # Identität an mehreren Körpern zählt dagegen weiterhin nur einmal.
    affected.update(identity for identity in present if identity != reachable)
    if not affected:
        return findings
    return [
        *findings,
        Finding(
            code="slicer.overrides_unreachable",
            severity="warning",
            message=_(
                "Diese Übergabe verwendet nur das erste Filament. Weitere Farben "
                "und Materialien werden damit nicht gedruckt. Wählen Sie für die "
                "Mehrfilament-Übergabe etwa OrcaSlicer oder Bambu Studio."
            ),
            values={"slots": len(affected), "slicer": setup.name},
            # Regel 17: Der Satz nennt einen anderen Slicer, und der Knopf wählt ihn.
            suggestions=(CHOOSE_SLICER,),
        ),
    ]


def override_for(settings: PrintSettings, slot: MaterialSlot) -> SlotOverride | None:
    """Der Übersteuerer dieses Filaments, wenn es einen gibt (§20).

    Gesucht wird über **Name, Farbe, Profil und Materialtyp**, denselben Schlüssel
    wie in :func:`app.core.export.threemf.merge_slots` —, nicht über die
    Position in der Liste. Der Grund steht bei :class:`SlotOverride`: Was der
    Dialog zeigt und was ein Plattenlauf fährt, sind zwei verschiedene
    Reihenfolgen, und positionsweise landete die Temperatur der einen Spule
    auf der anderen.

    Ohne Eintrag gilt das Projekt. Das ist der Normalfall — ein einfarbiges
    Teil hat gar keine.
    """
    for entry in settings.slot_overrides:
        if entry is not None and entry.key == threemf.slot_identity(slot):
            return entry
    return None


def unbound_override_for(settings: PrintSettings, slot: MaterialSlot) -> SlotOverride | None:
    """Alte Werte zum ausdrücklichen Übernehmen im Dialog, niemals zum Drucken."""
    for entry in settings.slot_overrides:
        if (
            entry is not None
            and not entry.empty
            and entry.material is None
            and entry.material_type is None
            and entry.key[:2] == (slot.name, slot.colour)
            and entry.key != threemf.slot_identity(slot)
        ):
            return entry
    return None


def with_slot_override(
    settings: PrintSettings,
    slot: MaterialSlot,
    override: SlotOverride | None,
) -> PrintSettings:
    """Setzt oder entfernt die eigenen Werte eines Filaments (§20, §29).

    Der Schlüssel umfasst Name, Farbe, Profil und Materialtyp. Die Oberfläche zeigt
    die Zusammenlegung aller gewählten Platten, ein einzelner Slicerlauf kann
    dieselben Filamente in einer anderen Reihenfolge führen. Ein positionsweiser
    Austausch gäbe dann wieder der falschen Spule die Temperatur.

    Ein leerer oder entfernter Übersteuerer reist nicht als Platzhalter mit.
    Das hält alte Projekte klein und macht ``None`` weiterhin eindeutig:
    Dieses Filament benutzt die Projektwerte.
    """
    key = threemf.slot_identity(slot)
    previous = unbound_override_for(settings, slot)
    kept = tuple(
        entry
        for entry in settings.slot_overrides
        if entry is not None and entry.key != key and entry is not previous and not entry.empty
    )
    if override is None or override.empty:
        return replace(settings, slot_overrides=kept)
    identified = replace(
        override,
        name=slot.name,
        colour=slot.colour,
        material=slot.material,
        material_type=slot.material_type,
    )
    return replace(settings, slot_overrides=(*kept, identified))


def settings_for_shared_slicer(
    settings: PrintSettings,
    profile: Profile,
    slots: Sequence[MaterialSlot],
    setup: SlicerSetup | None = None,
) -> PrintSettings:
    """Der eine Filamentwertsatz für einen Slicer ohne Mehrfachprofile.

    PrusaSlicer und CuraEngine nehmen auf diesem Weg genau einen Satz an. Der
    gehört dem ersten Extruder der Platte; weitere Filamente werden gesondert
    als nicht erreichbar gemeldet. Ohne Slot bleibt es bei den Projektwerten.
    """
    if not slots:
        return settings
    return settings_for_slot(settings, profile, slots[0], setup)


def settings_for_handover(
    settings: PrintSettings,
    profile: Profile,
    flavour: SlicerFlavour,
    slots: Sequence[MaterialSlot] = (),
    setup: SlicerSetup | None = None,
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
    return settings_for_shared_slicer(settings, profile, slots, setup)


def bind_slot_profiles(settings: PrintSettings, slots: Sequence[MaterialSlot]) -> PrintSettings:
    """Überführt alte Profilplätze einmalig in beständige Filamentidentitäten.

    Die übergebene Liste gehört zur ursprünglichen vollständigen Szene.
    Nach dieser Übernahme dürfen entfernte Körper und neue Werkzeugnummern
    kein Herstellerprofil an ein anderes Filament weiterreichen.
    """
    if settings.slot_profile_bindings is not None:
        return settings
    bindings = tuple(
        SlotProfileBinding(
            profile_name=settings.slot_profiles[slot.index],
            name=slot.name,
            colour=slot.colour,
            material=slot.material,
            material_type=slot.material_type,
        )
        for slot in slots
        if 0 <= slot.index < len(settings.slot_profiles) and settings.slot_profiles[slot.index]
    )
    return replace(settings, slot_profile_bindings=bindings)


def configured_slots(
    slots: Sequence[MaterialSlot], settings: PrintSettings
) -> tuple[MaterialSlot, ...]:
    """Löst Herstellerprofile nach Identität auf; alte Daten behalten ihren Leseweg."""
    if settings.slot_profile_bindings is None:
        return with_slot_profiles(slots, settings.slot_profiles)
    chosen = {binding.key: binding.profile_name for binding in settings.slot_profile_bindings}
    return tuple(
        replace(slot, material=chosen[threemf.slot_identity(slot)])
        if chosen.get(threemf.slot_identity(slot))
        else slot
        for slot in slots
    )


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


def _without_line_break(values: Mapping[str, str], tool_name: str) -> None:
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
        tool=tool_name,
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
    _refuse_untranslated(setup)
    setup = replace(setup, machine_profile=machine_for(setup, profile))

    # Gerechnet wird in dem Zweig, der es braucht: Die Orca-Familie schreibt
    # ihre Werte aus ``by_section`` und ``_orca_*``, nicht aus dieser Abbildung
    # — sie stand hier und lief bei jedem Lauf mit, ohne gelesen zu werden.
    def flat_values() -> dict[str, str]:
        """Alles, was ein Slicer als einen Satz Schlüssel bekommt."""
        return values_for(
            settings_for_handover(settings, profile, setup.flavour, slots, setup),
            profile,
            setup.flavour,
        )

    if setup.flavour == "prusa":
        target = directory / "solidon.ini"
        # Der Titel wird auf eine Zeile gebracht, die Werte werden geprüft: In
        # einer INI trennt der Umbruch die Einträge, und der Titel kommt aus
        # der Projektdatei. Ein Umbruch darin schrieb sonst eine zweite Zeile,
        # die PrusaSlicer als Einstellung liest — mit ``post_process`` als
        # Befehl, den niemand gesetzt hat.
        flat = flat_values()
        _without_line_break(flat, setup.name)
        lines = [f"# {_one_line(settings.title)} — von Solidon geschrieben, nicht von Hand"]
        lines += [f"{key} = {value}" for key, value in sorted(flat.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SlicerConfig(process=target, written=flat)

    if takes_a_machine_profile(setup.flavour):
        # **Das Herstellerprofil ist die Grundlage** (Konzept Herstellerprofil,
        # 27.09.2026). Geschrieben wird darüber nur, was abweichen soll: die
        # eigene Wahl, der übernommene Vorschlag, das Gemessene. Bis dahin
        # legte Solidon jeden Tabellenwert darüber — 45 Prozess- und 22
        # Filamentwerte am Centauri Carbon 2, darunter Gitter statt Baum und
        # kein Auto-Brim. Ohne lesbares Herstellerprofil schreibt es wie
        # bisher alles; das entscheidet jedes Dokument für sich.
        foundation = manufacturer.base_settings(profile, settings.quality, setup)
        paths = _deviating(settings, foundation)
        split = by_section(settings, setup.flavour)
        deviating = by_section(settings, setup.flavour, paths)
        plate = foundation.plate if foundation.has_profile else ""
        # Das Maschinenprofil zuerst: Der Prozess daneben nennt es in
        # ``compatible_printers``, und beide Namen kommen aus
        # ``_machine_name``.
        machine_target = directory / "solidon_machine.json"
        machine_document = _orca_machine(setup)
        machine_target.write_text(
            json.dumps(machine_document, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        target = directory / "solidon_process.json"
        process_document = _orca_process(
            split.get("process", {}),
            settings,
            setup,
            deviating=deviating.get("process", {}),
            plate=plate,
            suggested=_suggested_speed_keys(settings, setup.flavour),
        )
        target.write_text(
            json.dumps(process_document, indent=2, ensure_ascii=False),
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
        filament_documents: list[dict[str, object]] = []
        for slot in slots or (MaterialSlot(index=0, name=""),):
            own = replace(setup, base_filament=slot.material) if slot.material else setup
            # Je Slot seine eigenen Werte: Temperaturen, Kühlung,
            # Rückzug und Materialkennwerte dürfen sich unterscheiden,
            # denn sie hängen an der Spule. Was der Slot nicht setzt,
            # kommt aus dem Projekt — deshalb wird die Aufteilung hier
            # noch einmal gerechnet und nicht die von oben genommen.
            mine = settings_for_slot(settings, profile, slot, setup)
            part = split if mine is settings else by_section(mine, setup.flavour)
            own_paths = _for_the_slot(paths, settings, slot)
            filament_documents.append(
                _orca_filament(
                    part.get("filament", {}),
                    mine,
                    profile,
                    own,
                    slot,
                    deviating=by_section(mine, setup.flavour, own_paths).get("filament", {}),
                    plate=plate or None,
                )
            )
        # **Erst angleichen, dann schreiben.** Die Orca-Familie indiziert jeden
        # Filamentschlüssel je Filament, ungeprüft; fehlt einer in einem der
        # geladenen Profile, reißt der Lauf (:func:`_with_equal_keys`).
        for index, document in enumerate(_with_equal_keys(filament_documents)):
            path = directory / f"solidon_filament_{index}.json"
            path.write_text(
                json.dumps(
                    document,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            written.append(path)
        # **Geprüft wird, was Solidon schreibt, und eine Stichprobe der
        # Grundlage** (Entscheidung K). Die übrigen Prozesswerte gehören dem
        # Hersteller, und der Slicer liest sie, wie er sie liest: OrcaSlicer
        # nimmt Anycubics „50%" für die erste Schicht der Kobra 2 nicht an und
        # druckt mit seinen 30 mm/s. Gegen die ganze Datei gehalten, war das
        # eine Warnung bei jedem Auftrag, gegen die niemand etwas tun kann
        # (gemessen 27.09.2026). Ohne Herstellerprofil ist alles eigene Wahl.
        own_process = deviating.get("process", {})
        expected = {
            key: _printed(value)
            for key, value in process_document.items()
            if key in own_process or key in FOUNDATION_SAMPLE
        }
        if plate:
            expected["curr_bed_type"] = plate
        firmware = machine_document.get("gcode_flavor")
        if isinstance(firmware, str):
            expected["gcode_flavor"] = firmware
        for entry in slicer_keys.TABLES[setup.flavour]:
            if entry.section != "filament" or not all(
                entry.key in document for document in filament_documents
            ):
                continue
            # Ein Wert je Spule, wie der G-Code sie führt. Die Filamentwerte
            # des Herstellers bleiben ganz in der Gegenprobe: an ElegooSlicer,
            # Bambu Studio, Creality Print und OrcaSlicer kam jeder an.
            expected[entry.key] = ",".join(
                _printed(document[entry.key]) for document in filament_documents
            )
        # Eine eigene Betttemperatur steht unter dem Schlüssel der aufliegenden
        # Platte (``_on_the_plate``), nicht unter ``hot_plate_temp`` — geprüft
        # wird sie dort (Review Stufe A+B, H3).
        bed_key = manufacturer.PLATE_TEMPERATURES.get(plate) if plate else None
        if bed_key is not None:
            for key in (bed_key, f"{bed_key}_initial_layer"):
                if all(key in document for document in filament_documents):
                    expected[key] = ",".join(
                        _printed(document[key]) for document in filament_documents
                    )
        return SlicerConfig(
            process=target, filaments=tuple(written), machine=machine_target, written=expected
        )

    target = directory / "solidon_cura.txt"
    # Hier wiegt der Umbruch schwerer als bei Prusa: ``_command`` liest diese
    # Datei mit ``splitlines()`` zurück und macht aus jeder Zeile ein eigenes
    # ``-s``-Argument. Eine zweite Zeile wäre damit ein zusätzliches Argument
    # für CuraEngine. Start- und Endcode tragen Umbrüche und stehen deshalb
    # nicht hier, sondern in ``cura_machine`` (:func:`_command`).
    flat = flat_values()
    machine = _cura_machine(setup, profile, flat)
    flat |= machine.switches
    _without_line_break(flat, setup.name)
    target.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(flat.items())) + "\n",
        encoding="utf-8",
    )
    return SlicerConfig(process=target, written=flat, cura_machine=machine)


#: Schlüssel, die eine Spule aus sich selbst ergänzt und nie vom Nachbarn
#: nimmt: Die Farben einer anderen Spule wären eine falsche Aussage über
#: diese. Ein einfarbiges Filament neben einem mehrfarbigen führt seine eine
#: Farbe als ``filament_multi_colour`` — so schreibt es auch Bambu Studio.
_OWN_FILLS: Final[dict[str, Callable[[Mapping[str, object]], object]]] = {
    "filament_multi_colour": lambda document: (
        [str(first[0])]
        if isinstance(first := document.get("filament_colour"), list) and first
        else [""]
    ),
    "filament_colour_type": lambda document: ["1"],
}


def _with_equal_keys(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    """Dieselben Schlüssel in jedem Filamentprofil eines Laufs.

    **Der Anlass** (Befund Robert, 19.09.2026, „beim Öffnen im Slicer Fehler"):
    Sein Regal aus einer Bambu-3MF trug auf Platte 1 einen deklarierten Slot
    „SUNLU PETG @BBL A1", den kein Dreieck benutzte, neben der PLA-Spule aus
    dem Lager. Die PLA-Spule erbte das Herstellerprofil des Laufs (Elegoo PLA
    @ECC2, 65 Schlüssel); die PETG-Spule anderen Typs erbt es mit Absicht
    nicht (:func:`_orca_filament`) und kam mit Solidons 34 Schlüsseln. Der
    ElegooSlicer brach mit ``0xC0000409`` ab, ohne ein Wort — Zustandszeile:
    „Der Slicer ist beim Verarbeiten der Übergabe abgestürzt". Gemessen an
    sechs Varianten derselben Platte: ohne Herstellerprofil lief es, mit nur
    der benutzten Spule lief es, mit zwei ungleichen Profilen riss es — die
    Orca-Familie legt die Werte aller geladenen Filamente in Vektoren je
    Schlüssel und indiziert sie mit der Filamentnummer, ungeprüft.

    Was fehlt, kommt aus dem ersten Profil des Laufs, das den Schlüssel führt.
    Das trifft nur, was Solidon **nicht** selbst setzt — Temperaturen, Kühlung,
    Rückzug und Materialwerte stehen in jedem Dokument, denn die schreibt
    :func:`_orca_filament` für jede Spule aus ihren eigenen Werten. Übrig
    bleiben Startsequenzen, Überhangschwellen des Lüfters, Druckvorschub und der Hersteller:
    Werte, die der Slicer sonst aus seiner Vorgabe nähme — und eine Vorgabe
    aus demselben Lauf ist näher an ihr als ein Abbruch ohne Meldung.
    """
    if len(documents) < 2:
        return documents
    keys: list[str] = []
    for document in documents:
        keys.extend(key for key in document if key not in keys)
    filled: list[dict[str, object]] = []
    for document in documents:
        complete = dict(document)
        for key in keys:
            if key in complete:
                continue
            own = _OWN_FILLS.get(key)
            if own is not None:
                complete[key] = own(complete)
                continue
            source = next(entry for entry in documents if key in entry)
            complete[key] = source[key]
        if len(complete) != len(document):
            _log.info(
                "filament profile %s takes %d missing keys from its neighbours",
                document.get("name", "?"),
                len(complete) - len(document),
            )
        filled.append(complete)
    return filled


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
    # Dieselbe Grundlage wie im Konsolenlauf (:func:`write_config`): auf dem
    # Herstellerprofil nur die Abweichung, dazu die Druckplatte.
    foundation = manufacturer.base_settings(profile, settings.quality, setup)
    paths = _deviating(settings, foundation)
    deviating = by_section(settings, setup.flavour, paths)
    plate = foundation.plate if foundation.has_profile else ""

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
            document.update(slicer_profiles.resolve_values(found, roots=_profile_roots(setup)))

    document.update(
        _orca_process(
            split.get("process", {}),
            settings,
            setup,
            deviating=deviating.get("process", {}),
            plate=plate,
            suggested=_suggested_speed_keys(settings, setup.flavour),
        )
    )
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
        mine = settings if slot is None else settings_for_slot(settings, profile, slot, setup)
        own = (
            replace(setup, base_filament=slot.material)
            if slot is not None and slot.material
            else setup
        )
        slot_values = by_section(mine, setup.flavour).get("filament", {})
        slot_paths = paths if slot is None else _for_the_slot(paths, settings, slot)
        filament_documents.append(
            _orca_filament(
                slot_values,
                mine,
                profile,
                own,
                slot,
                deviating=by_section(mine, setup.flavour, slot_paths).get("filament", {}),
                plate=plate or None,
            )
        )

    # Dieselben Schlüssel in jedem Filament — wie bei den Profildateien des
    # Konsolenlaufs, und aus demselben Grund (:func:`_with_equal_keys`); die
    # Mehrfarbschlüssel nimmt jede Spule dabei aus sich selbst.
    filament_documents = _with_equal_keys(filament_documents)

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
        document.update(slicer_profiles.resolve_values(base, roots=_profile_roots(setup)))
    # Nach dem Auffüllen, damit kein geerbter Wert ihn überschreibt.
    document["name"] = _machine_name(setup)
    return document


#: Schlüssel, die ein Solidon-Feld nur mitbedient, weil Solidon sie nicht eigens
#: führt: die Lückenfüllung mit der Innenwand, die innere Vollfüllung mit der
#: Füllung (``slicer_keys``). Solidons eigener Satz braucht für sie einen Wert;
#: über einem Herstellerprozess hat der Hersteller sie eigens abgestimmt.
_ORCA_FOLLOWERS: Final = frozenset({"gap_infill_speed", "internal_solid_infill_speed"})


def _followers_not_faster(
    base: Mapping[str, object],
    deviating: Mapping[str, str],
    suggested: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Eine Abweichung macht einen mitbedienten Schlüssel nie schneller als beim Hersteller.

    Gemessen am 27.09.2026 an Anycubics Kobra 2 in OrcaSlicer: Der Vorschlag
    „Innenwand 142 mm/s“ hob die Lückenfüllung des Herstellers von 100 auf
    142 mm/s, weil ``speed.inner_wall`` beide Schlüssel schreibt. Langsamer
    darf sie werden, denn wer die Innenwand bremst, meint die Lückenfüllung
    mit. Schneller nicht: Das wäre eine Abweichung, die niemand gewählt hat.
    Ein Herstellerwert, der keine Zahl ist, bleibt, wie er ist.

    Dasselbe gilt für jedes Tempo, das nur ein übernommener Vorschlag setzt
    (``suggested``, :func:`_suggested_speed_keys`): Ein Vorschlag bremst, er
    beschleunigt nicht. „Erste Schicht 50 mm/s" an schmalen Stegen legt die
    Füllung langsamer und lässt Wände, die der Hersteller mit 40 legt, bei 40.
    Eine eigene Wahl im Dialog darf beides.
    """
    kept = dict(deviating)
    for key in (_ORCA_FOLLOWERS | suggested) & kept.keys():
        vendor = _as_float(_printed(base.get(key, "")))
        own = _as_float(kept[key])
        if vendor is None or own is None or own > vendor:
            del kept[key]
    return kept


def _suggested_speed_keys(settings: PrintSettings, flavour: SlicerFlavour) -> frozenset[str]:
    """Die Tempo-Schlüssel, die nur ein übernommener Vorschlag setzt, keine eigene Wahl."""
    suggested = settings.accepted - settings.chosen
    return frozenset(
        entry.key
        for entry in slicer_keys.TABLES[flavour]
        if entry.path in suggested
        and entry.path.startswith("speed.")
        and entry.key.endswith("_speed")
    )


def _orca_process(
    values: dict[str, str],
    settings: PrintSettings,
    setup: SlicerSetup,
    *,
    deviating: Mapping[str, str] | None = None,
    plate: str = "",
    suggested: frozenset[str] = frozenset(),
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
        document.update(slicer_profiles.resolve_values(base, roots=_profile_roots(setup)))
    # Auf dem Herstellerprozess nur die Abweichung, ohne ihn alles (Entscheidung D).
    document.update(
        values
        if base is None or deviating is None
        else _followers_not_faster(document, deviating, suggested)
    )
    # **Die Druckplatte, ausdrücklich** (Entscheidung F). Ohne sie nimmt die
    # Konsole „Cool Plate" — gemessen am ElegooSlicer mit 35 °C Bett für PLA,
    # während das Fenster am Centauri Carbon 2 die texturierte PEI-Platte wählt.
    if plate:
        document["curr_bed_type"] = plate
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
        document.update(slicer_profiles.binding(base, roots=_profile_roots(setup)))
    document.pop("inherits", None)
    return document


def _orca_filament(
    values: dict[str, str],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slot: MaterialSlot | None = None,
    *,
    deviating: Mapping[str, str] | None = None,
    plate: str | None = None,
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
    chosen = setup.base_filament
    if (
        slot is not None
        and slot.material_type
        and not slot.material
        and slot.material_type.strip().casefold()
        != slicer_keys.filament_type(profile.material.id).casefold()
    ):
        # Eine lokale Spule anderen Typs erbt keine fremden Materialwerte
        # oder Startsequenzen aus der allgemeinen Herstellerunterlage.
        chosen = ""
    brand = _profile_name(chosen) if chosen else ""
    document: dict[str, object] = {
        "type": "filament",
        "name": f"Solidon {brand or settings.title}",
        "from": "User",
        "instantiation": "true",
        "filament_type": [
            slot.material_type
            if slot is not None and slot.material_type
            else slicer_keys.filament_type(profile.material.id)
        ],
        "filament_is_support": ["0"],
        # Neutraler Slicerstandard, bis eine Herstellerunterlage ihn ersetzt.
        # Bambu indiziert diese Liste ohne Längenprüfung für jedes Filament;
        # fehlt ein lokaler Slot darin, lehnt es den ganzen Auftrag ab (-100).
        "filament_shrink": ["100%"],
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
    base = profile_file(chosen, setup, "filament")
    inherited: dict[str, object] = {}
    if base is not None:
        inherited = slicer_profiles.resolve_values(base, roots=_profile_roots(setup))
        document.update({key: _as_slots(value) for key, value in inherited.items()})

    # Solidons Werte kommen darüber — außer sie gehören einem anderen Material.
    #
    # Die Einstellungen kennen ein Material, das Projekt-Material. Ein Slot
    # kann ein anderes tragen: eine Schrift in PLA auf einem Gehäuse aus PETG.
    # Für die Schrift sind 240 Grad und 10 mm³/s keine Solidon-Entscheidung
    # mehr, sondern ein Wert aus der falschen Zeile — PLA fährt 210 bei 21.
    # Wo der Slot sein eigenes Profil nennt, gilt deshalb der Hersteller für
    # alles, was am Material hängt.
    # Auf dem Herstellerfilament nur die Abweichung, ohne eines alles — eine
    # lokale Spule anderen Typs hat keine Unterlage und braucht Solidons
    # ganzen Satz (Entscheidung D).
    chosen_values = values if base is None or deviating is None else deviating
    own_values = {key: [value] for key, value in chosen_values.items()}
    if plate is not None:
        own_values = _on_the_plate(own_values, plate)
    if slot is not None and slot.material and inherited:
        override = override_for(settings, slot)
        from_the_material = {
            orca
            for solidon, orca, _kind in slicer_profiles.FILAMENT_READBACK
            if orca in inherited
            and (override is None or getattr(override, solidon.partition(".")[0]) is None)
        }
        own_values = {
            key: value for key, value in own_values.items() if key not in from_the_material
        }
    document.update(own_values)
    # Die ausdrücklich gewählte Spule gewinnt zuletzt. Eine lokale PLA-Spule
    # hat einen Typ, aber kein eigenes Herstellerprofil. Ein geerbter
    # ``filament_type`` darf die sichtbare Wahl nicht überschreiben.
    if slot is not None and slot.material_type:
        document["filament_type"] = [slot.material_type]
    # Die Farbe gehört dem Slot, nicht der Einstellung: sie ist der Grund,
    # warum es diesen Slot überhaupt gibt (§20). Ein Schriftzug in Weiß auf
    # schwarzem Gehäuse sind zwei Spulen, und beide bekämen sonst die eine
    # Farbe aus den Druckeinstellungen.
    if slot is not None and slot.colour is not None:
        document["filament_colour"] = [_hex(slot.colour)]
        # **Und alle Farben, wo es mehrere sind.** Die Orca-Familie führt ein
        # mehrfarbiges Filament als ``filament_multi_colour`` — alle Farben in
        # einer Zeichenkette, durch Leerzeichen getrennt, die erste zugleich
        # in ``filament_colour`` — und ``filament_colour_type`` „1" für
        # Abschnitte (im Gegensatz zum Verlauf „0"). Geschrieben nur, wo es
        # etwas zu sagen gibt: Ein einfarbiges Filament bekommt die Schlüssel
        # nicht, und ein Slicer, der sie nicht kennt, bekommt sie so nur von
        # jemandem, der ein solches Filament wirklich eingelegt hat (§20).
        if slot.extra_colours:
            document["filament_multi_colour"] = [
                " ".join(_hex(one) for one in (slot.colour, *slot.extra_colours))
            ]
            document["filament_colour_type"] = ["1"]
    if slot is not None and slot.name:
        document["name"] = f"Solidon {slot.name}"
    if plate is not None:
        # Die Platte ist bekannt: Die Temperaturen der übrigen Platten bleiben,
        # wie der Hersteller sie setzt — auch seine Nullen, mit denen er eine
        # Platte für ein Material sperrt (Entscheidung F).
        return document
    # Aus dem Dokument, nicht aus ``values``: bei einem Slot mit eigenem
    # Material stehen dort die Werte des Herstellers, und die Platte soll die
    # Temperatur bekommen, die auch sonst gilt — PLA bei 60, nicht bei den 80
    # des Projektmaterials.
    return _with_every_plate(document, _plate_source(document, values))


#: Die Stichprobe der Grundlage (Entscheidung K): Prozesswerte, die Solidon
#: auf einem Herstellerprofil nicht schreibt und trotzdem gegen den G-Code
#: hält. Stimmen sie, lag das Profil des Herstellers wirklich darunter —
#: Schichthöhe, Wände und Stützschwelle legt jeder Hersteller für seinen
#: Drucker fest.
FOUNDATION_SAMPLE: Final = frozenset({"layer_height", "wall_loops", "support_threshold_angle"})


def _printed(value: object) -> str:
    """Der eine Wert, den der Slicer aus einem Profileintrag druckt.

    Bambu Studio führt viele Prozess- und Filamentwerte je Düsenvariante als
    Liste: ``inner_wall_speed`` ist ``["300", "400"]`` für Standard und High
    Flow, ``filament_max_volumetric_speed`` ``["21", "29"]``. Solidon nennt
    keine Variante; der Slicer nimmt die erste und schreibt nur sie in den
    G-Code. Gegen die ganze Liste gehalten, meldete die Gegenprobe an jedem
    Auftrag für die P1S fünfzehn „anders übernommene" Werte (gemessen
    27.09.2026).
    """
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _deviating(
    settings: PrintSettings, foundation: manufacturer.Foundation
) -> frozenset[str] | None:
    """Was vom Herstellerprofil abweichen soll — ``None`` heißt alles."""
    return manufacturer.written_paths(settings, foundation)


def _for_the_slot(
    paths: frozenset[str] | None, settings: PrintSettings, slot: MaterialSlot
) -> frozenset[str] | None:
    """Die Abweichungen eines Slots: die des Projekts und die Gruppen, die
    seine Spule ausdrücklich übersteuert — die gehören ihr, nicht dem
    Hersteller (§20)."""
    if paths is None:
        return None
    override = override_for(settings, slot)
    if override is None or override.empty:
        return paths
    groups = [
        group
        for group in ("temperature", "cooling", "retraction", "filament")
        if getattr(override, group) is not None
    ]
    return paths | frozenset(
        path for path in print_settings.all_paths() if path.partition(".")[0] in groups
    )


def _on_the_plate(values: dict[str, list[str]], plate: str) -> dict[str, list[str]]:
    """Eine eigene Betttemperatur gilt der Platte, die aufliegt (Entscheidung F).

    Die Tabelle schreibt sie als ``hot_plate_temp`` — die „High Temp Plate".
    Liegt eine andere auf, bekommt sie deren Schlüssel, und die Temperaturen
    der übrigen Platten bleiben, wie der Hersteller sie setzt.
    """
    key = manufacturer.PLATE_TEMPERATURES.get(plate)
    if key is None or key == "hot_plate_temp":
        return values
    moved = dict(values)
    for suffix in ("", "_initial_layer"):
        value = moved.pop(f"hot_plate_temp{suffix}", None)
        if value is not None:
            moved[f"{key}{suffix}"] = value
    return moved


def _hex(colour: tuple[float, float, float]) -> str:
    """Drei Anteile 0…1 als ``#RRGGBB``, wie die Slicer eine Farbe schreiben."""
    red, green, blue = (round(channel * 255) for channel in colour)
    return f"#{red:02X}{green:02X}{blue:02X}"


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


def setting_limitations(
    flavour: SlicerFlavour, settings: PrintSettings | None = None
) -> list[Finding]:
    """Benannte Übergabeverluste vor dem Öffnen und nach dem Slicen ausweisen.

    Was nur je nach Wert angenähert ankommt (``slicer_keys.LIMITED``), wird
    erst mit den Einstellungen beurteilt — ohne sie gibt es dazu keinen Satz.
    """
    paths = slicer_keys.NOT_TAKEN_BY[flavour] | slicer_keys.LIMITED[flavour]
    return [
        Finding(
            code="slicer.setting_not_transferred",
            severity="warning",
            message=message,
            values={"path": path},
            suggestions=(CHECK_SLICER_PROFILE,),
        )
        for path in sorted(paths)
        if (message := slicer_keys.limitation(flavour, path, settings)) is not None
    ]


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

    **Nur die eigene Wahl** (Konzept Herstellerprofil, 27.09.2026): Was nicht
    ausdrücklich gesetzt ist, geht nicht mehr zum Slicer, sondern kommt aus
    dem Profil — ein Unterschied dort wäre eine Meldung über einen Wert, der
    gar nicht übergeben wird.
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

    inherited = slicer_profiles.resolve_values(base, roots=_profile_roots(setup))
    written = by_section(settings, setup.flavour, settings.explicit).get("filament", {})
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
    except OSError, ValueError:
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

    if takes_a_machine_profile(setup.flavour):
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

    # **Ohne ``-v``.** Das ausführliche Protokoll nennt jede Schicht und
    # jeden Arbeitsschritt; am Eiffelturm aus dem Korpus (313 000 Dreiecke)
    # waren das 12,3 MB, über der Sammelgrenze :data:`SLICER_OUTPUT_LIMIT`,
    # und der Lauf endete ohne Druckdatei (RM-252). Ohne den Schalter bleiben
    # Warnungen und Fehler, 50 kB — mehr liest die Übergabe nicht daraus.
    arguments = [binary, "slice"]
    engine = config.cura_machine or CuraMachine()
    if engine.search_path:
        # Vor ``-j``: CuraEngine sucht die Erbkette und die Extruderzüge beim
        # Laden der Definition, nicht danach.
        arguments += ["-d", os.pathsep.join(str(folder) for folder in engine.search_path)]
    basis = (
        str(engine.definition)
        if engine.definition is not None
        else setup.machine_profile or _cura_base(setup.executable)
    )
    if basis:
        arguments += ["-j", basis]
    values: list[str] = []
    for line in config.process.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values += ["-s", line.strip()]
    arguments += values
    # **Start- und Endcode des Druckers, je ein Argument mit Umbrüchen.**
    # Gemessen: Ein mehrzeiliges ``-s machine_start_gcode=…`` kommt Zeile für
    # Zeile im G-Code an. Sie gelten der Maschine, nicht dem Extruder-Zug.
    for key, code in engine.codes.items():
        arguments += ["-s", f"{key}={code}"]
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
    # Eine Druckerdefinition bringt ihren Extruderzug selbst mit
    # (``machine_extruder_trains``); ``fdmextruder`` darüber setzte dessen
    # Vorgaben auf die allgemeinen zurück. Nur zu ``fdmprinter`` gehört er.
    extruder = "" if engine.from_printer else _cura_extruder_base(setup.executable)
    if extruder:
        arguments += ["-j", extruder]
    arguments += values
    # **Je Netz ein ``-l``, und seine Werte gleich dahinter** — ein ``-s`` nach
    # ``-l`` gilt nur diesem Netz (``CommandLine.cpp``). Die Stützsperre reist
    # so als eigenes Netz mit ``anti_overhang_mesh``; ohne Netzliste bleibt es
    # beim Modell selbst.
    for model in models:
        for mesh in cura_meshes(Path(model)):
            arguments += ["-l", str(mesh.path)]
            for key, value in mesh.settings.items():
                arguments += ["-s", f"{key}={value}"]
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
    der alle Druckerdefinitionen erben, und der Rückfall für einen Drucker,
    den Cura nicht führt; sonst lädt der Lauf die Druckerdefinition
    (:func:`_cura_machine`), und CuraEngine löst deren Erbkette selbst auf.

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


def _cura_printer_definition(executable: Path, printer: PrinterProfile) -> str:
    """Die Druckerdefinition dieses Druckers in dieser Cura-Installation — oder nichts.

    Nichts heißt zweierlei, und beides endet gleich: Der Drucker trägt keine
    (``PrinterProfile.cura_definition`` ist leer, weil Cura ihn nicht führt),
    oder diese Installation hat die Datei nicht, etwa eine ältere Cura. Die
    Kennung ist beim Lesen geprüft (``profiles.CURA_DEFINITION``); hier wird
    sie noch einmal geprüft, weil ein Profil auch ohne Tabelle entsteht.
    """
    name = printer.cura_definition
    if not name or profiles.CURA_DEFINITION.fullmatch(name) is None:
        return ""
    return _cura_definition(executable, f"{name}.def.json")


#: Woran das Cura-Fenster erkennt, dass der Startcode die Temperaturen selbst
#: setzt. Steht einer dieser Namen als Platzhalter darin, schaltet es
#: ``material_bed_temp_prepend`` bzw. ``material_print_temp_prepend`` ab, und
#: CuraEngine setzt kein eigenes ``M190``/``M109`` davor. Dieselben Namen wie
#: ``plugins/CuraEngineBackend/StartSliceJob.py`` (Cura 5.13).
_BED_TEMPERATURES: Final = ("material_bed_temperature", "material_bed_temperature_layer_0")
_PRINT_TEMPERATURES: Final = (
    "material_print_temperature",
    "material_print_temperature_layer_0",
    "default_material_print_temperature",
    "material_initial_print_temperature",
    "material_final_print_temperature",
    "material_standby_temperature",
    "print_temperature",
)

#: Was das Cura-Fenster unter einem zweiten Namen füllt (``_buildReplacementTokens``).
_CURA_ALIASES: Final = {
    "print_temperature": "material_print_temperature",
    "print_bed_temperature": "material_bed_temperature",
    "travel_speed": "speed_travel",
}

#: Ein Platzhalter im Start- und Endcode: was zwischen zwei geschweiften
#: Klammern steht, wie im ``GcodeStartEndFormatter`` des Fensters.
_PLACEHOLDER: Final = re.compile(r"\{([^{}]*)\}")

#: Die zwei Maschinencodes, die Solidon aus der Definition übergibt.
MACHINE_CODES: Final = ("machine_start_gcode", "machine_end_gcode")


def _cura_machine(setup: SlicerSetup, profile: Profile, values: Mapping[str, str]) -> CuraMachine:
    """Die Maschine für CuraEngine: Definition, Start- und Endcode (§29).

    **Die Rechenmaschine liest aus einer Definition nur ``default_value``,
    und Platzhalter füllt sie nicht.** Das Fenster wertet Formeln und
    Platzhalter aus, bevor es CuraEngine ruft; die Konsole bekommt nichts
    davon. Solidon wertet keine Formel aus (Regel 10) — die Maschine kommt
    deshalb aus der Druckerdefinition, und was darin für den Druck zählt,
    Start- und Endcode, füllt :func:`_filled` aus den Werten, die Solidon
    ohnehin schreibt.

    Ohne Druckerdefinition bleibt es bei ``fdmprinter``; dessen Codes haben
    keine Platzhalter, und :func:`machine_missing` sagt, was fehlt.
    """
    base = _cura_base(setup.executable)
    if not base:
        return CuraMachine()
    own = _cura_printer_definition(setup.executable, profile.printer)
    definition = Path(own or base)
    chain = slicer_profiles.resolve_values(definition)
    known = _placeholder_values(chain, values)
    codes = {
        key: _filled(str(chain.get(key) or ""), known, key, setup.name) for key in MACHINE_CODES
    }
    # Beide Ordner hinter ``-d``, getrennt wie auf dieser Plattform üblich. Ein
    # Pfad, der den Trenner selbst trägt, bliebe zwei Pfade — dann sucht
    # CuraEngine die Züge nicht, der Lauf gelingt trotzdem, nur mit den
    # Vorgaben der Maschine statt denen ihres Zugs.
    folder = definition.parent
    extruders = folder.parent / "extruders"
    searchable = extruders.is_dir() and os.pathsep not in f"{folder}{extruders}"
    search = (folder, extruders) if own and searchable else ()
    return CuraMachine(
        definition=definition,
        from_printer=bool(own),
        search_path=search,
        codes=codes,
        switches=_temperature_switches(str(chain.get("machine_start_gcode") or "")),
    )


def _placeholder_values(chain: Mapping[str, object], written: Mapping[str, str]) -> dict[str, str]:
    """Womit Platzhalter gefüllt werden: Solidons Werte, sonst die der Definition.

    Aus der Definition nur Einzelwerte, wie ``str()`` sie im Fenster schriebe
    — keine Listen und keinen Text mit Umbruch, denn ein Platzhalter, der den
    Startcode in sich selbst schriebe, ist keine Angabe.
    """
    known: dict[str, str] = {}
    for key, value in chain.items():
        if isinstance(value, bool):
            known[key] = str(value)
        elif isinstance(value, int | float):
            known[key] = f"{value:g}"
        elif isinstance(value, str) and _single_line(value):
            known[key] = value
    known |= written
    for alias, source in _CURA_ALIASES.items():
        if source in known:
            known[alias] = known[source]
    return known


def _filled(text: str, known: Mapping[str, str], setting: str, tool: str) -> str:
    """Füllt die Platzhalter eines Maschinencodes — oder hält an (Regel 21).

    ``{name}`` und ``{name, n}`` sind Textersetzung. Eine Rechnung wie
    ``{machine_depth - 5}`` (Endcode des Neptune 4) geht durch Solidons
    eigenen Auswerter (``app.core.expressions``, Regel 10), nur über Zahlen,
    die Solidon kennt. Was so nicht zu füllen ist — ein unbekannter Name,
    ``{if …}``, ein Wert, den erst das Fenster nach dem Schneiden kennt —,
    hält die Übergabe an: Wörtlich im G-Code bräche ein Makro wie
    ``START_PRINT EXTRUDER_TEMP=…`` am Drucker ab.
    """

    def value_of(match: re.Match[str]) -> str:
        expression, _comma, extruder = match.group(1).partition(",")
        expression = expression.strip()
        if extruder.strip() and not extruder.strip().isdigit():
            raise _unfillable(match.group(0), setting, tool)
        if expression in known:
            return known[expression]
        number = _arithmetic(expression, known)
        if number is None:
            raise _unfillable(match.group(0), setting, tool)
        return f"{number:g}"

    return _PLACEHOLDER.sub(value_of, text)


def _arithmetic(expression: str, known: Mapping[str, str]) -> float | None:
    """Eine Rechnung über bekannte Zahlen, mit Solidons eigener Grammatik."""
    numbers: dict[str, float] = {}
    for key, text in known.items():
        try:
            numbers[key] = float(text)
        except ValueError:
            continue
    try:
        return expressions.evaluate(expressions.canonical(expression, numbers), numbers)
    except ValidationError:
        return None


def _unfillable(placeholder: str, setting: str, tool: str) -> ExternalToolError:
    """Die Absage für einen Platzhalter, den Solidon nicht füllen kann."""
    return ExternalToolError(
        tool=tool,
        title=SLICER_FAILED,
        detail=_(
            "Der Start- oder Endcode dieses Druckers in Cura verlangt einen Wert, "
            "den Solidon nicht einsetzen kann. Ungefüllt bräche der Drucker den Druck ab."
        ),
        values={"setting": setting, "text": placeholder},
        suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
    )


def _temperature_switches(start: str) -> dict[str, str]:
    """Ob CuraEngine eigene Temperaturbefehle vor den Startcode setzt.

    Dieselbe Regel wie im Cura-Fenster: Kommentare heraus, dann nach einem
    Temperatur-Platzhalter suchen. Setzt der Startcode die Temperatur selbst,
    bleibt Curas eigenes ``M190``/``M109`` weg — sonst stünden beide da,
    gemessen am K1 Max: ``M190 S60`` vor ``START_PRINT … BED_TEMP=60``.
    """
    code = re.sub(r";.+?(\n|$)", "\n", start)

    def sets(names: tuple[str, ...]) -> bool:
        return re.search(r"\{(" + "|".join(names) + r")(,\s?\w+)?\}", code) is not None

    return {
        "material_bed_temp_prepend": "false" if sets(_BED_TEMPERATURES) else "true",
        "material_print_temp_prepend": "false" if sets(_PRINT_TEMPERATURES) else "true",
    }


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


def _usable_area(contour: Sequence[tuple[float, float]]) -> BaseGeometry | None:
    """Die Fläche einer fremden Kontur, oder ``None``, wenn keine darin steckt.

    ``make_valid`` macht aus einem Schmetterling zwei Dreiecke und aus drei
    Punkten auf einer Linie einen Strich; nur was Fläche hat, taugt als Bett
    oder Sperre. Ein Wert, den GEOS gar nicht annimmt, ist ebenfalls keine.
    """
    from shapely import make_valid
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    try:
        shape = make_valid(Polygon(contour))
    except ValueError, GEOSException:
        return None
    pieces = [
        piece
        for piece in getattr(shape, "geoms", (shape,))
        if piece.geom_type in ("Polygon", "MultiPolygon") and piece.area > 0.0
    ]
    if not pieces:
        return None
    return unary_union(pieces)


def off_the_bed(
    payload: str | gcode.GcodeAnalysis,
    profile: Profile,
    flavour: SlicerFlavour,
    *,
    replay: Callable[[], Iterable[str]] | None = None,
    cancelled: CancelToken | None = None,
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
    (:func:`gcode.stated_bed`). Sonst gilt die wirksame Druckfläche des
    Druckerprofils einschließlich seiner Sperrflächen. Das trifft insbesondere
    CuraEngine, dem Solidon die Maße selbst gegeben hat. Der erste Anlauf maß
    immer gegen den eigenen Bauraum,
    und der ElegooSlicer bekam damit bei einem Würfel in der Bettmitte einen
    Befund: sein Maschinenprofil kommt aus seinem eigenen Bestand, und
    „außerhalb" hieße dort entweder „daneben gedruckt" oder „zwei Profile
    meinen verschiedene Maschinen".

    Unter einer Bahnbreite wird nichts gemeldet: eine Datei, die auf den
    Millimeter passt, ist in Ordnung, und die Bahn selbst liegt mit ihrer
    halben Breite ohnehin neben der Mitte, die hier gemessen wird.

    Reicht die Hüllbox als Nachweis nicht aus, prüft ein zweiter Durchlauf
    jede Materialbahn gegen die Kontur. Der erste Durchlauf hat dann auch
    Bett und Firmware aus einem möglichen Schlussblock bereits aufgelöst.
    Der Speicher wächst nicht mit der Zahl der Bahnen. Ohne ``replay`` kann
    eine bereits gelesene Analyse allein keinen Durchtritt durch eine innere
    Sperrfläche belegen.

    Unbrauchbare Konturen bleiben als Warnung sichtbar. Liegt zusätzlich
    eine Bahn außerhalb, trägt der Fehler die Einschränkung als Einzelheit.
    """
    from io import StringIO

    from shapely.affinity import translate
    from shapely.geometry import box

    from app.core import build_area

    analysis = payload if isinstance(payload, gcode.GcodeAnalysis) else gcode.analyze(payload)
    extent = analysis.extent
    if extent is None:
        return None
    # Bett und Sperrflächen kommen aus einer fremden Datei. Eine Kontur, die
    # sich selbst schneidet oder keine Fläche hat, ließ GEOS mit einer
    # Ausnahme abbrechen — nach dem gelungenen Slicen, mit der Druckdatei in
    # einem Ordner, der gleich gelöscht wird. Was keine Fläche ergibt, fällt
    # auf das Profil zurück oder wird übergangen; der Prüfbericht sagt es.
    notes: list[TranslatableText] = []
    area = _usable_area(analysis.bed_outline) if analysis.bed_outline else None
    if area is None:
        if analysis.bed_outline:
            _log.warning("the bed outline of the print file has no area; using the profile")
            notes.append(
                _(
                    "Die Bettkontur der Druckdatei hat keine nutzbare Fläche; "
                    "geprüft wurde gegen das Druckerprofil."
                )
            )
        area = build_area.printable_area(profile.printer)
        if wants_bed_coordinates(flavour):
            width, depth, _height = profile.printer.build_volume
            area = translate(area, xoff=width / 2.0, yoff=depth / 2.0)
    excluded_invalid = False
    for contour in analysis.excluded_areas:
        blocked = _usable_area(contour)
        if blocked is None:
            _log.warning("an exclusion area of the print file has no area and is ignored")
            excluded_invalid = True
            continue
        area = area.difference(blocked)
    if excluded_invalid:
        notes.append(
            _(
                "Mindestens eine Sperrkontur der Druckdatei hat keine nutzbare Fläche "
                "und wurde bei der Prüfung ausgelassen."
            )
        )
    warning = None
    if notes:
        detail = (
            notes[0] if len(notes) == 1 else _("{first} {second}", first=notes[0], second=notes[1])
        )
        warning = Finding(
            code="gcode.invalid_build_area",
            severity="warning",
            message=_("{detail} Prüfen Sie die Druckfläche im Slicer.", detail=detail),
            source="gcode",
            suggestions=(CHECK_SLICER_PROFILE,),
        )
    height = (
        analysis.bed.maximum[2]
        if analysis.bed is not None and math.isfinite(analysis.bed.maximum[2])
        else build_area.printable_height(profile.printer)
    )
    left, front, right, back = area.bounds
    bed = BoundingBox((left, front, 0.0), (right, back, height))
    worst, axis = 0.0, 0
    for index in range(3):
        over = max(
            bed.minimum[index] - extent.minimum[index],
            extent.maximum[index] - bed.maximum[index],
        )
        if over > worst:
            worst, axis = over, index
    if worst <= profile.printer.extrusion_width:
        allowed = area.buffer(profile.printer.extrusion_width, join_style="mitre")
        if allowed.covers(box(*extent.minimum[:2], *extent.maximum[:2])):
            return warning
        inside = analysis.paths_inside
        if isinstance(payload, str):
            text_payload = payload

            def replay_text() -> Iterable[str]:
                """Ein vorhandener Text bleibt auch beim zweiten Lesen derselbe."""
                return StringIO(text_payload)

            replay = replay_text
        if replay is not None:
            checked = gcode.analyze_lines(
                replay(),
                cancelled=cancelled,
                firmware=analysis.firmware,
                path_check=gcode.area_check(allowed),
            )
            inside = checked.paths_inside
        if inside is not False:
            # Eine Hüllbox über einer Sperrzone beweist keine Materialbahn
            # darin. Ohne erneuten Zugriff auf die Bahnen fehlt der Nachweis.
            return warning
        return Finding(
            code="gcode.off_the_bed",
            severity="error",
            message=_(
                "Die Druckdatei führt Materialbahnen außerhalb der Druckfläche oder durch eine "
                "Sperrfläche. Prüfen Sie das Druckerprofil und die Anordnung im Slicer."
            ),
            values={
                "axis": "XY",
                "reason": _("Druckfläche"),
                **({"detail": warning.message} if warning else {}),
            },
            source="gcode",
        )
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
            **({"detail": warning.message} if warning else {}),
        },
        source="gcode",
    )


#: Nur ausdrücklich unbekannte Schalter gelten programmweit. Ein Fehler der
#: konkreten Platte darf keine späteren gültigen Anordnungen verwerfen.
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


def fan_in_off_layers(
    analysis: gcode.GcodeAnalysis, settings: PrintSettings, flavour: SlicerFlavour
) -> Finding | None:
    """Läuft der Lüfter in einer Schicht, die ohne ihn gedruckt werden sollte?

    Nur bei Cura, der einzigen Familie ohne Lüfterpause
    (``slicer_keys.LIMITED``). Sein Hochlauf trifft sie für null und eine
    Schicht genau — aber kurze Schichten kühlt Cura danach stärker, auch in
    der Pause, und dieser Zuschlag hängt an der Druckzeit der Schicht, die
    vor dem Slicen niemand kennt. Gemessen am 26.09.2026 mit einer Schicht
    ohne Lüfter: am 20-mm-Würfel in Schicht 1 21 %, am 120-mm-Würfel aus.
    Also wird die Druckdatei gefragt, mit ihrer Herkunft (Regel 14).
    """
    if "cooling.disable_first_layers" not in slicer_keys.LIMITED[flavour]:
        return None
    start = analysis.fan_start
    if start is None or start[0] > settings.cooling.disable_first_layers:
        return None
    layer, share = start
    return Finding(
        code="gcode.fan_in_first_layers",
        severity="warning",
        message=_(
            "Cura kennt keine Lüfterpause: Der Lüfter läuft schon in Schicht {layer} "
            "mit {percent} %.",
            layer=layer,
            percent=round(share * 100.0),
        ),
        values={"path": "cooling.disable_first_layers"},
        suggestions=(CHOOSE_SLICER,),
        source="gcode",
    )


def spools_left_out(
    analysis: gcode.GcodeAnalysis,
    expected: Sequence[int],
    slots: Sequence[MaterialSlot],
    flavour: SlicerFlavour,
) -> Finding | None:
    """Fehlt eine übergebene Spule in der Druckdatei? (§28.2, Regel 14)

    Die vierte Gegenprobe, und sie sieht, was die drei anderen durchlassen:
    Eine Datei kann die volle Höhe haben, auf dem Bett liegen und jeden
    geschriebenen Wert bestätigen — und trotzdem ist ein Teil des Körpers
    nicht darin, weil der Slicer ein Werkzeug stillschweigend weggelassen hat.

    **Gemessen an Bambu Studio 2.3** (12.09.2026): derselbe zweifarbige
    Würfel, einmal einfarbig übergeben und einmal zweifarbig. Einfarbig
    4,31 g, zweifarbig 2,82 g — ein Drittel weniger Material, ein Filament
    statt zwei, **Exit 0 und kein Wort** in Ausgabe oder Protokoll.
    OrcaSlicer und ElegooSlicer rechnen dieselbe Platte mit beiden Spulen und
    102 Werkzeugwechseln. Ein Kunde, der die Datei an den Drucker gibt, sieht
    den fehlenden Teil erst nach Stunden auf der Platte.

    Verglichen werden die Werkzeuge, die die **Flächen der Platte** benutzen,
    mit denen, die im G-Code wirklich fördern (``metrics.used_tools``). Ein
    deklarierter, aber unbemalter Slot steht nicht in ``expected`` — sonst
    schlüge die Prüfung bei jedem Körper an, dessen alte Spulenliste einen
    Eintrag mehr trägt als seine Flächen.

    **Nur für Familien mit Filamentprofilen je Spule.** PrusaSlicer und
    CuraEngine nehmen einen Satz Filamentwerte für die ganze Platte
    (:func:`slicer_keys.has_filament_profiles`); dass dort nur ein Werkzeug im
    G-Code steht, ist ihre bekannte Bauart und keine verlorene Spule.
    :func:`unreachable_overrides` sagt das dem Kunden bereits, bevor der Lauf
    beginnt — ein zweiter Befund über dieselbe Sache macht den ersten
    schwächer, nicht den Bericht vollständiger.

    Ohne ``expected`` entfällt der Vergleich; geraten wird nichts (Regel 21).
    """
    if not has_filament_profiles(flavour):
        return None
    wanted = {int(tool) for tool in expected}
    # Mit einem einzigen Werkzeug gibt es nichts zu verwechseln, und ein
    # G-Code ohne jeden Werkzeugbefehl ist dann der Normalfall.
    if len(wanted) < 2:
        return None
    metrics = analysis.metrics
    if not metrics.used_tools:
        # Die Liste ist genau dann leer, wenn die Datei **nichts** fördert —
        # ein ungenanntes Werkzeug gilt als Werkzeug 0, und das ist wichtig:
        # Der gemessene Bambu-Fall trug keinen einzigen ``T``-Befehl. Fördert
        # nichts, hält ``slice_model`` schon vorher an („keine einzige
        # Materialbahn"), und diese Aussage ist die deutlichere von beiden.
        return None
    missing = sorted(wanted - set(metrics.used_tools))
    if not missing:
        return None
    by_index = {slot.index: slot for slot in slots}
    names = [by_index[tool].name for tool in missing if tool in by_index]
    label: str | TranslatableText = (
        names[0] if names else ", ".join(str(tool + 1) for tool in missing)
    )
    for name in names[1:]:
        label = _("{head}, {tail}", head=label, tail=name)
    return Finding(
        code="gcode.spool_left_out",
        severity="error",
        message=_(
            "Der Slicer hat nicht alle Filamente gedruckt — was auf den fehlenden "
            "Spulen liegt, ist nicht in der Druckdatei."
        ),
        values={
            "filament": label,
            "expected": len(wanted),
            "found": len(set(metrics.used_tools) & wanted),
        },
        # Regel 17: Bambu Studio lässt die Spule still weg, OrcaSlicer und
        # ElegooSlicer rechnen dieselbe Platte mit beiden — der andere Slicer
        # ist der kürzeste Weg zur vollständigen Druckdatei, das Profil der
        # zweite (gemessen, siehe oben).
        suggestions=(CHOOSE_SLICER, CHECK_SLICER_PROFILE),
        source="gcode",
    )


def _readback_materials(
    config: SlicerConfig,
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slots: Sequence[MaterialSlot],
) -> tuple[tuple[float | None, ...], tuple[float | None, ...]]:
    """Belegte Materialkennwerte dieses Laufs, wenn der G-Code selbst keine nennt.

    Die geschriebenen Werte gewinnen auch gegenüber einem Herstellerprofil.
    Cura überträgt keine Dichte; dort stammt sie aus genau dem einen wirksamen
    Materialwertsatz. Eine Mehrwerkzeugliste bleibt vollständig erhalten.
    """
    effective = (
        tuple(
            settings_for_slot(settings, profile, slot, setup)
            for slot in slots or (MaterialSlot(index=0, name=""),)
        )
        if has_filament_profiles(setup.flavour)
        else (settings_for_handover(settings, profile, setup.flavour, slots, setup),)
    )

    def values(key: str, fallback: tuple[float, ...]) -> tuple[float | None, ...]:
        """Ein fehlender Profilkommentar darf einen belegten Laufwert ergänzen."""
        written = config.written.get(key)
        if written is None:
            return fallback
        parsed: list[float | None] = []
        for component in re.split(r"[,;]", written.strip().strip("[]")):
            try:
                number = float(component.strip().strip("\"'"))
            except ValueError:
                parsed.append(None)
            else:
                parsed.append(number if math.isfinite(number) and number > 0.0 else None)
        return tuple(parsed)

    return (
        values("filament_density", tuple(item.filament.density for item in effective)),
        values(
            "material_diameter" if setup.flavour == "cura" else "filament_diameter",
            tuple(item.filament.diameter for item in effective),
        ),
    )


def _creality_cli_input(model: Path, target: Path, cancelled: CancelToken | None = None) -> Path:
    """Entfernt nur die einzelne Plattenbeilage aus einer temporären CLI-Kopie.

    Creality Print 7.2.2.5483 stürzt bei Mehrfilament-3MF mit diesem Block ab.
    Ohne ihn bleiben Namen, Objektwerkzeuge, Farben und Platzierungen erhalten.
    Mehrere Platten dürfen ihre Zuordnung keinesfalls verlieren; ohne genau
    einen lesbaren Block geht deshalb die vollständige Originaldatei weiter.
    """
    if model.suffix.casefold() != ".3mf":
        return model
    try:
        with zipfile.ZipFile(model) as source:
            if source.namelist().count(SETTINGS_PATH) != 1:
                return model
            config = ET.fromstring(source.read(SETTINGS_PATH))
            plates = config.findall("plate")
            if config.tag != "config" or len(plates) != 1:
                return model
            config.remove(plates[0])
            with zipfile.ZipFile(target, "w") as destination:
                destination.comment = source.comment
                for entry in source.infolist():
                    if cancelled is not None:
                        cancelled.raise_if_cancelled()
                    if entry.filename == SETTINGS_PATH:
                        destination.writestr(entry, ET.tostring(config, encoding="utf-8"))
                        continue
                    with source.open(entry) as reader, destination.open(entry, "w") as writer:
                        while block := reader.read(COPY_BLOCK_BYTES):
                            if cancelled is not None:
                                cancelled.raise_if_cancelled()
                            writer.write(block)
    except zipfile.BadZipFile, ET.ParseError:
        # Eine unlesbare Beilage belegt keine einzelne Platte. Der Slicer
        # bekommt sie unverändert und behält seine eigene Fehlerdiagnose.
        return model
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or target),
            detail=str(problem.strerror or problem),
        ) from problem
    return target


def _is_creality_print(setup: SlicerSetup) -> bool:
    """Ob dieser Slicer Creality Print ist — ein Mitglied der Orca-Familie."""
    return (
        setup.flavour == "orca" and discover.program_mark(setup.executable.name) == "crealityprint"
    )


def _for_the_creality_window(model: Path) -> Path:
    """Dieselbe Datei ohne Plattenblock wie für die Konsole — an Ort und Stelle.

    Die Kopie entsteht wie für die Konsole (:func:`_creality_cli_input`) und
    ersetzt danach die geschriebene Datei, damit das Fenster denselben
    Dateinamen zeigt, den der Kunde im Austauschordner sieht. Ohne genau einen
    Plattenblock bleibt die Datei, wie sie ist.
    """
    staging = model.with_name(f"{model.stem}.staging{model.suffix}")
    if _creality_cli_input(model, staging) == model:
        return model
    try:
        staging.replace(model)
    except OSError as problem:
        with suppress(OSError):
            staging.unlink()
        raise FileWriteError(
            target=model.name, detail=problem.strerror or str(problem)
        ) from problem
    return model


def _creality_cli_tower_position(
    config: SlicerConfig, setup: SlicerSetup, models: Sequence[Path]
) -> SlicerConfig:
    """Initialisiert nur fehlende CLI-Turmkoordinaten nach dem Herstellerprofil.

    Crealitys Fenster übersetzt den Platzierungsmodus in Projektkoordinaten;
    das CLI lässt sonst 15/220 stehen, auch auf einem 220-mm-Bett. Übernommen
    wird die Herstellerregel für rechteckige Betten und 0/90 Grad. Gespeicherte
    Koordinaten gewinnen immer, auch aus einer eingebetteten 3MF-Konfiguration.
    Die G-Code-Gegenprobe bleibt für tatsächliche Turmmaße und Sperrflächen nötig.
    """
    if (
        setup.flavour != "orca"
        or discover.program_mark(setup.executable.name) != "crealityprint"
        or config.machine is None
    ):
        return config
    coordinates = ("wipe_tower_x", "wipe_tower_y")
    try:
        process = json.loads(config.process.read_text(encoding="utf-8"))
        machine = json.loads(config.machine.read_text(encoding="utf-8"))
        if not isinstance(process, dict) or not isinstance(machine, dict):
            return config
        values = machine | process
        if any(key in values for key in coordinates):
            return config
        for model in models:
            if model.suffix.casefold() != ".3mf":
                continue
            with zipfile.ZipFile(model) as container:
                if threemf.PROJECT_SETTINGS_PATH not in container.namelist():
                    continue
                embedded = json.loads(container.read(threemf.PROJECT_SETTINGS_PATH))
                if not isinstance(embedded, dict) or any(key in embedded for key in coordinates):
                    return config
        horizontal, _, vertical = str(values.get("prime_tower_position_type", "")).partition(" ")
        if horizontal not in {"Left", "Middle", "Right"} or vertical not in {
            "Upper",
            "Center",
            "Below",
        }:
            return config
        if str(values.get("enable_prime_tower", "0")) != "1":
            return config
        width = float(values.get("prime_tower_width", "0"))
        rotation = float(values.get("wipe_tower_rotation_angle", "0")) % 360.0
        if not math.isfinite(width) or width <= 0.0 or not math.isfinite(rotation):
            return config
        if not is_zero(rotation) and not is_close(rotation, 90.0):
            return config
        outline = values.get("printable_area", "")
        if isinstance(outline, list) and all(isinstance(point, str) for point in outline):
            outline = ",".join(outline)
        if not isinstance(outline, str):
            return config
        area = _usable_area(gcode.analyze(f"; printable_area = {outline}\n").bed_outline)
        if area is None:
            return config
        from shapely.geometry import box

        if not area.equals(box(*area.bounds)):
            return config
        left, bottom, right, top = area.bounds
        side = CREALITY_TOWER_SIDE_OFFSET
        upper = CREALITY_TOWER_TOP_OFFSET
        if is_zero(rotation):
            xs = {
                "Left": left + side,
                "Middle": (left + right - width) / 2,
                "Right": right - width - side,
            }
            ys = {"Upper": top - upper, "Center": (bottom + top) / 2, "Below": bottom + side}
        else:
            xs = {"Left": left + upper, "Middle": (left + right) / 2, "Right": right - side}
            ys = {"Upper": top - width - side, "Center": (bottom + top) / 2, "Below": bottom + side}
        placed = dict(zip(coordinates, (str(xs[horizontal]), str(ys[vertical])), strict=True))
        process.update({key: [value] for key, value in placed.items()})
        config.process.write_text(
            json.dumps(process, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except ValueError, TypeError, zipfile.BadZipFile:
        # Ein unbekannter oder unlesbarer Auftrag belegt keine automatische
        # Position. Seine ursprüngliche Slicerdiagnose bleibt maßgeblich.
        return config
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or config.process),
            detail=str(problem.strerror or problem),
        ) from problem
    return replace(config, written={**config.written, **placed})


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
    expected_tools: Sequence[int] = (),
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
    _refuse_untranslated(setup)
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
    # Ein Slicer als Flatpak sieht unser ``/tmp`` nicht
    # (``discover.workspace_for``).
    with discover.workspace_for(setup.executable, "solidon-slice-") as workspace:
        cli_models = (
            [
                _creality_cli_input(entry, workspace / f"model_{index}.3mf", cancelled)
                for index, entry in enumerate(models)
            ]
            if _is_creality_print(setup)
            else models
        )
        config = write_config(settings, profile, setup, workspace, slots)
        requested_values = config.written
        config = _creality_cli_tower_position(config, setup, cli_models)
        densities, diameters = _readback_materials(config, settings, profile, setup, slots)
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
        # Ab wann eine Ergebnisdatei zu diesem Lauf gehört (``_result_reason``).
        started = time.time()
        completed = _run_slicer(
            _command(setup, cli_models, config, target, wanted_arrangement),
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
        # **Der Familienname bleibt hier stehen, und das ist gemessen.** Die
        # anderen Vergleiche dieser Datei sind am 07.09.2026 auf benannte
        # Prädikate gestellt (`takes_a_machine_profile`); dieser meint eine
        # eigene Eigenschaft — „bei dieser Familie lohnt ein zweiter Versuch
        # ohne die Anordnungsvorgabe" —, und die wird sonst nirgends gefragt.
        # Ein Prädikat für eine einzige Stelle ist Zierat; es entsteht, wenn
        # die zweite dazukommt oder ein Fork hier abweicht.
        if produced is None and wanted_arrangement and setup.flavour == "orca":
            refused_flag = _refuses_arrange_flag(_tail(completed.stdout, completed.stderr))
            # Die Rückfallstufe: einmal ohne die Anordnungsvorgabe — dieselbe
            # Bauart wie bei den Booleschen Ops, und wie dort wird die
            # benutzte Stufe ausgewiesen statt verschwiegen. Ein Slicer, der
            # auch so nichts schreibt, läuft in die Fehlerbehandlung darunter,
            # mit derselben Meldung wie bisher.
            completed = _run_slicer(
                _command(setup, cli_models, config, target, False),
                workspace,
                timeout,
                setup,
                cancelled,
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            produced = _find_gcode(target, expected)
            if produced is not None:
                if refused_flag:
                    _REFUSES_THE_ARRANGE_FLAG.add(setup.executable)
                arranged_by_slicer = True
        if produced is None:
            # Beide Ströme: die Orca-Familie protokolliert auf stdout und
            # lässt stderr leer. Nur stderr zu zeigen hieße, einen Fehler
            # ohne Text zu melden — und das ist schlimmer als keiner.
            output = _tail(completed.stdout, completed.stderr)
            reason = _result_reason(target, started)
            if reason:
                _log.info("%s refused the job: %s", setup.name, reason)
                output = "\n".join(part for part in (output, reason) if part)
            # **Vor den Ausgabeprüfungen**, denn ein abgestürztes Programm
            # schreibt keinen Satz, an dem sie greifen könnten: Es fällt mitten
            # im Lauf um, und was dasteht, ist die letzte Zeile davor. Der
            # Kunde bekäme sonst nur „Der Slicer hat keine Druckdatei geschrieben“.
            # Der Prozessstatus belegt den Absturz, aber nicht dessen Ursache.
            # Der Rückgabewert gehört ins Protokoll, nicht in den Satz: Unter
            # Windows kam -50 als 4294967246 beim Kunden an (KUNDE-09).
            _log.info(
                "%s ended without a print file, exit code %d",
                setup.name,
                signed_exit_code(completed.returncode),
            )
            if crashed(completed.returncode):
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Der Slicer ist beim Verarbeiten der Übergabe abgestürzt. "
                        "Öffnen Sie die Datei im Slicer und prüfen Sie Drucker- und "
                        "Filamentprofile, oder wählen Sie einen anderen Slicer."
                    ),
                    values={"output": output},
                    # **Die Ursache wird nicht behauptet** (Regel 21): Gemessen
                    # ist der Absturz und dass dieselbe Datei bei anderen
                    # Slicern durchläuft; die offene Ersteinrichtung ist der
                    # Fall, der hier auftrat, nicht der einzig mögliche.
                    # Deshalb steht der Slicerwechsel vorn — auf einem Rechner
                    # mit mehreren ist er der kürzeste Ausweg, und er hängt an
                    # keiner Vermutung (§2.1).
                    suggestions=(CHOOSE_SLICER, RETRY, SHOW_SLICER_OUTPUT, EXPORT_ONLY),
                )
            if (
                setup.flavour == "orca"
                and signed_exit_code(completed.returncode) == ORCA_OFF_THE_PLATE
            ):
                # **Die Orca-Familie sagt es nur mit einer Zahl** (-50,
                # „found error, exit"): Nicht jedes Teil liegt ganz auf ihrer
                # Platte. Gemessen am ElegooSlicer (26.09.2026): halb neben der
                # Platte, ganz daneben und 270 mm lang auf 256 mm, jeweils mit
                # ``--arrange 0``; ohne die Vorgabe ordnet er selbst an und legt
                # den langen Quader schräg. Der Laptop-Ständer (205 auf 272 mm)
                # passt auch schräg nicht — dort half nur Teilen oder
                # Verkleinern, und der Kunde las „hat nicht geantwortet".
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Nicht jedes Teil liegt ganz auf der Druckplatte des Slicers: "
                        "Eines ist größer als der Bauraum oder liegt daneben."
                    ),
                    values={"output": output},
                    suggestions=(SPLIT_MODEL, SCALE_TO_FIT, ARRANGE_ON_BED, SHOW_SLICER_OUTPUT),
                )
            if (
                _is_creality_print(setup)
                and any(entry.suffix.casefold() == ".3mf" for entry in models)
                and _says_print_is_empty(output)
            ):
                # **Creality Print 7.2 rechnet über die Kommandozeile keine
                # 3MF**, gleich woher: Solidons Übergabe, eine nackte 3MF aus
                # trimesh, eine aus PrusaSlicer — jede endet mit -100 und „The
                # print is empty", dasselbe Teil als STL schneidet es
                # (26.09.2026, RM-164). Im eigenen Fenster lädt es die Datei;
                # dorthin führt der Satz, statt den Kunden raten zu lassen.
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Creality Print rechnet eine 3MF-Datei nur in seinem Fenster. "
                        "Öffnen Sie sie dort mit „Im Slicer öffnen“."
                    ),
                    values={"output": output},
                    suggestions=(CHOOSE_SLICER, SHOW_SLICER_OUTPUT, EXPORT_ONLY),
                )
            if _says_outside_the_volume(output):
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_("Der Slicer sagt, die Teile liegen außerhalb seines Bauraums."),
                    values={"output": output},
                    suggestions=(ARRANGE_ON_BED, SCALE_TO_FIT, SHOW_SLICER_OUTPUT),
                )
            if _says_no_layers(output):
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
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
                title=SLICER_FAILED,
                detail=_("Der Slicer hat keine Druckdatei geschrieben."),
                values={"output": output},
                suggestions=(CHOOSE_SLICER, SHOW_SLICER_OUTPUT, CHECK_SLICER_PROFILE, EXPORT_ONLY),
            )

        with produced.open("r", encoding="utf-8", errors="replace") as stream:
            analysis = gcode.analyze_lines(
                stream,
                cancelled=cancelled,
                densities=densities,
                diameters=diameters,
                firmware=config.written.get("gcode_flavor")
                or config.written.get("machine_gcode_flavor"),
            )
        if not analysis.extrudes:
            # Eine große Datei ohne eine einzige Förderbewegung. Der Slicer ist
            # durchgelaufen und hat den Rückgabewert 0 gemeldet, aber das
            # Modell nicht verarbeitet — meist, weil ihm eine Einstellung
            # fehlte, die er stillschweigend als „nichts drucken" auslegt. Das
            # als Erfolg durchzulassen wäre schlimmer als der Abbruch: der
            # Nutzer schickte eine leere Datei an den Drucker.
            raise ExternalToolError(
                tool=setup.name,
                title=SLICER_FAILED,
                detail=_(
                    "Die Druckdatei enthält keine einzige Materialbahn — "
                    "der Slicer hat das Modell nicht verarbeitet."
                ),
                values={"output": _tail(completed.stdout, completed.stderr)},
                suggestions=(CHECK_SLICER_PROFILE, SHOW_SLICER_OUTPUT, CHOOSE_SLICER, EXPORT_ONLY),
            )
        metrics = analysis.metrics
        produced_path = produced

        # Und die zweite Gegenprobe, an der Geometrie statt an den Werten:
        # steht in dieser Datei ein Druck, der auf das Bett passt?
        def replay_gcode() -> Iterable[str]:
            """Öffnet dieselbe Datei bei Bedarf für die genaue Konturprüfung erneut."""
            with produced_path.open("r", encoding="utf-8", errors="replace") as stream:
                yield from stream

        beyond = off_the_bed(
            analysis, profile, setup.flavour, replay=replay_gcode, cancelled=cancelled
        )
        # Die dritte: Ist überhaupt das ganze Modell darin? ``None`` heißt
        # „der Aufrufer kennt die Höhe nicht" — dann entfällt der Vergleich,
        # er wird nie geraten.
        short = too_short(analysis, model_height, settings) if model_height is not None else None
        fan = fan_in_off_layers(analysis, settings, setup.flavour)
        # Die vierte: Sind alle übergebenen Spulen darin? Die drei darüber
        # sehen eine Datei, der ein ganzes Filament fehlt, nicht an — sie hat
        # die volle Höhe, liegt auf dem Bett und bestätigt jeden Wert.
        left_out = spools_left_out(analysis, expected_tools, slots, setup.flavour)
        # Die Gegenprobe: hat der Slicer übernommen, was ihm geschrieben wurde?
        # Das ist die einzige Auskunft, die von ihm selbst kommt statt aus einer
        # Dokumentation, die für die installierte Version gelten mag oder nicht.
        # Creality nullt die Koordinaten des inaktiven Einfilament-Turms.
        # Nur die zusätzlich abgeleitete Position setzt mehrere tatsächlich
        # benutzte Werkzeuge voraus; ausdrückliche Sollwerte bleiben vollständig.
        written = config.written if len(metrics.used_tools) > 1 else requested_values
        ignored = verify_settings(analysis.settings, written)
        if output_dir is None:
            # Der Ordner verschwindet gleich; die Datei muss den Aufrufer noch
            # erreichen können, also wandert sie neben das Modell.
            produced = _kept_beside(models[0], produced, cancelled=cancelled)

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Ohne Einstellungen: Was nur je nach Wert angenähert ankommt, beurteilt
    # nach dem Slicen die Druckdatei selbst (``fan_in_off_layers``).
    findings = [
        *setting_limitations(setup.flavour),
        *profile_differences(settings, setup),
        *unknown_keys(settings, profile, setup),
        *unreachable_overrides(settings, setup, slots, profile=profile),
        # **Auch hier und nicht nur beim Export.** Der Befund entstand für
        # ``write_assembly``; der Kunde, der auf *Slicen* klickt, geht aber gar
        # nicht dort vorbei. Sein Lauf gelingt dann mit den Vorgaben des
        # Slicers statt mit den Werten aus Solidon — oder er scheitert, und die
        # Orca-Familie sagt dazu nur „process not compatible with printer".
        *machine_missing(setup, profile),
        *foundation_findings(settings, profile, setup),
        *ignored,
        *([beyond] if beyond is not None else []),
        *([short] if short is not None else []),
        *([fan] if fan is not None else []),
        *([left_out] if left_out is not None else []),
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

    **Creality Print bekommt dieselbe Datei wie seine Konsole**
    (:func:`_for_the_creality_window`, Durchsicht 0.5.0): ohne den einzelnen
    Plattenblock, an dem Creality Print 7.2 bei einer Mehrfilament-3MF
    abstürzt. Fenster und Konsole sind dasselbe Programm mit demselben
    3MF-Leser; ein Absturz des Fensters wäre der schlechtere Ausgang, und bei
    einer einzelnen Platte verliert die Datei ohne den Block nichts — Namen,
    Werkzeuge, Farben und Lagen bleiben, und das Fenster legt alles auf seine
    eine Platte.
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
    if _is_creality_print(setup):
        model = _for_the_creality_window(model)
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


#: Endung eines Profils, das Cura über *Profile verwalten → Importieren* liest.
CURA_PROFILE_SUFFIX: Final = ".curaprofile"

#: Die Formatversion eines Cura-Containers (``UM.Settings.InstanceContainer``
#: ``Version``). Sie steht seit Cura 4 unverändert auf vier.
_CURA_CONTAINER_VERSION: Final = 4

#: Zeitstempel der Einträge im Profil — fest, damit dieselben Werte dieselbe
#: Datei ergeben.
_CURA_PROFILE_TIMESTAMP: Final = (1980, 1, 1, 0, 0, 0)


def cura_profile_beside(
    model: Path,
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slots: Sequence[MaterialSlot] = (),
) -> Finding | None:
    """Die Einstellungen als importierbares Cura-Profil neben dem Modell (§29).

    **Cura nimmt beim Öffnen einer Datei keine Einstellungen an.** Die
    Konsole bekommt sie als ``-s`` (:func:`_command`); das Fenster liest aus
    einem Modell nur Geometrie. Bis zur Durchsicht 0.5.0 bekam es deshalb
    ein bloßes STL, und alles, was Solidon eingestellt hatte, war auf diesem
    Weg verloren. Was Cura aus einer Datei übernimmt, ist ein Profil: eine
    ``.curaprofile`` mit einem ``quality_changes``-Container, geprüft gegen
    Curas eigenen Leser (``plugins/CuraProfileReader`` und
    ``CuraContainerRegistry.importProfile`` in Cura 5.13).

    Was hineingeht, ist die **Einstellungsseite** (:func:`as_mapping`) —
    nicht die Maschine und nicht das Abgeleitete: Das Fenster rechnet seine
    Formeln selbst, und ein festgeschriebener Linienabstand bliebe stehen,
    wenn der Kunde danach in Cura die Füllung ändert. Wahrheitswerte schreibt
    Cura als ``True``/``False`` (es liest sie mit ``ast.literal_eval``), die
    Konsole als ``true``. Mehrere Spulen bekommen je ein Extruderprofil mit
    ``position``; eine einzelne legt Cura beim Import selbst auf das erste
    Fach.

    **Die Qualitätsstufe gehört dem Drucker, der in Cura aktiv ist**
    (Prüfbericht Cura, B9). Cura setzt ein importiertes Profil auf seine aktive
    Maschine um, lehnt es ab, wenn deren Stufen die genannte nicht führen, und
    zeigt es nicht an, wenn es sie für Düse und Spule nicht gibt. Gewählt wird
    deshalb unter den Stufen dieses Druckers für seine Düse und seine Spule,
    und zwar die mit der nächstliegenden Schichthöhe. Mit den Stufen von
    ``fdmprinter`` (bei 0,2 mm ``draft``) lehnte Cura das Profil an Elegoos
    Druckern ab und zeigte es an Creality und Sovol nicht an. Ist in Cura
    kein Drucker eingerichtet, zu dem es passt, entsteht keine Datei, und der
    Befund sagt, was zu tun ist.

    ``None`` heißt: kein Cura, oder eine Installation ohne lesbare
    Definitionen — dann wird nichts geschrieben, und ein Profil mit geratener
    Version wäre schlimmer als keines. Der zurückgegebene Befund ist der eine
    Satz, den der Dialog dazu zeigt.
    """
    if setup.flavour != "cura":
        return None
    version = slicer_profiles.cura_setting_version(setup.executable)
    if version is None:
        return None
    active = slicer_profiles.cura_active_machine(setup.executable)
    qualities = (
        slicer_profiles.cura_quality_types(
            setup.executable,
            active.definition,
            variant=active.variant,
            material_type=active.material_type,
        )
        if active is not None
        else {}
    )
    if active is None or not qualities:
        return Finding(
            code="handover.cura_profile_unbound",
            severity="warning",
            message=_(
                "In Cura ist kein Drucker eingerichtet, zu dem das Profil passt. Richten Sie "
                "Ihren Drucker in Cura ein und wählen Sie dann noch einmal „Im Slicer öffnen“."
            ),
            values={"slicer": setup.name},
            suggestions=(CHOOSE_SLICER,),
        )
    wanted = float(settings.layers.layer_height)
    quality = min(sorted(qualities), key=lambda kind: abs(qualities[kind] - wanted))
    definition = slicer_profiles.cura_quality_definition(setup.executable, active.definition)
    name = _one_line(model.stem) or "solidon"

    def container(values: Mapping[str, str], position: int | None) -> str:
        lines = [
            "[general]",
            f"version = {_CURA_CONTAINER_VERSION}",
            f"name = {name}",
            f"definition = {definition}",
            "",
            "[metadata]",
            "type = quality_changes",
            f"quality_type = {quality}",
            f"setting_version = {version}",
        ]
        if position is not None:
            lines.append(f"position = {position}")
        lines += ["", "[values]"]
        for key, value in sorted(values.items()):
            written = {"true": "True", "false": "False"}.get(value, value)
            lines.append(f"{key} = {written}")
        return "\n".join(lines) + "\n"

    shared = as_mapping(settings_for_handover(settings, profile, "cura", slots, setup), "cura")
    _without_line_break(shared, setup.name)
    entries = [("solidon", container(shared, None))]
    if len(slots) > 1:
        for position, slot in enumerate(slots):
            own = as_mapping(settings_for_slot(settings, profile, slot, setup), "cura")
            _without_line_break(own, setup.name)
            entries.append((f"solidon_extruder_{position}", container(own, position)))
    target = model.with_suffix(CURA_PROFILE_SUFFIX)
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry_name, body in entries:
                info = zipfile.ZipInfo(entry_name, date_time=_CURA_PROFILE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                archive.writestr(info, body.encode("utf-8"))
    except OSError as problem:
        raise FileWriteError(
            target=target.name, detail=problem.strerror or str(problem)
        ) from problem
    _log.info(
        "wrote a Cura profile beside %s for %s (%s, quality %s)",
        model.name,
        active.name,
        definition,
        quality,
    )
    return Finding(
        code="handover.cura_profile",
        severity="info",
        message=_(
            "Cura übernimmt Einstellungen nur als Profil. Es liegt neben dem Modell: "
            "in Cura unter Profile verwalten → Importieren wählen."
        ),
        values={"file": target.name, "machine": active.name},
    )


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
        # Die zwei Mehrfarbschlüssel sind Anzeige, kein Druckwert: Der G-Code
        # führt sie nicht, und eine Gegenprobe fände dort nie etwas.
        "filament_multi_colour",
        "filament_colour_type",
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


def _same(actual: str, wanted: str) -> bool:
    """Ob zwei Werte dasselbe meinen.

    Verglichen wird nachsichtig: ``0.2`` und ``0.20``, ``15%`` und ``15``,
    und eine Liste aus einem Element gegen dieses Element. Sonst meldete die
    Gegenprobe Unterschiede, die keine sind, und würde nach dem dritten Mal
    weggesehen.
    """
    if actual.strip() == wanted.strip():
        return True

    # Kommentare führen Filamentplätze mit Komma oder Semikolon, die Profile
    # als JSON-Liste. Kein Platz darf beim Gegenprüfen verschwinden.
    def components(value: str) -> list[str]:
        return [
            part.strip().strip("\"'").rstrip("%")
            for part in re.split(r"[,;]", value.strip().strip("[]"))
        ]

    left, right = components(actual), components(wanted)
    if len(left) != len(right):
        return False
    for found, expected in zip(left, right, strict=True):
        if found == expected:
            continue
        try:
            if abs(float(found) - float(expected)) < 1e-6:
                continue
        except ValueError:
            pass
        return False
    return True


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
#: Der Rückgabewert, mit dem die Orca-Familie einen Auftrag ablehnt, dessen
#: Teile nicht ganz auf der Platte liegen (Bambus ``CLI_NO_SUITABLE_OBJECTS``),
#: gemessen am ElegooSlicer 1.5 mit halb, ganz daneben und zu groß.
ORCA_OFF_THE_PLATE: Final = -50
#: Der Titel, wenn der Slicer gelaufen ist und keine brauchbare Druckdatei
#: hinterließ. ``ExternalToolError`` sagt sonst „hat nicht geantwortet" — der
#: Slicer hat aber geantwortet, nur mit einem Fehler.
SLICER_FAILED: Final = _("Der Slicer hat den Auftrag nicht gerechnet.")
#: Gemessen an Creality Print 7.2 mit jeder 3MF über die Kommandozeile
#: (RM-164). Andere Programme der Familie sagen es, wenn alle Teile neben der
#: Platte liegen; gelesen wird es deshalb nur für Creality Print.
PRINT_IS_EMPTY: Final[tuple[str, ...]] = ("the print is empty",)


def _refuses_arrange_flag(output: str) -> bool:
    """Erkennt eine ausdrückliche Ablehnung der CLI-Option, keinen Druckfehler."""
    return any(
        "arrange" in line
        and any(
            marker in line
            for marker in (
                "unknown option",
                "unrecognized option",
                "unrecognised option",
                "unsupported option",
                "invalid option",
            )
        )
        for line in output.casefold().splitlines()
    )


def _says_outside_the_volume(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass nichts im Bauraum liegt?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in OUTSIDE_THE_VOLUME)


def _says_print_is_empty(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass auf der Platte nichts zu drucken ist?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in PRINT_IS_EMPTY)


def _says_no_layers(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass keine druckbare Schicht entstand?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in NO_LAYERS)


def signed_exit_code(exit_code: int) -> int:
    """Ein Rückgabewert mit Vorzeichen — Windows liefert ``-50`` als DWORD 4294967246."""
    return exit_code - (1 << 32) if exit_code >= (1 << 31) else exit_code


def crashed(exit_code: int) -> bool:
    """Ist der Slicer abgestürzt, statt ordentlich aufzugeben?

    Ein Absturz und ein abgelehnter Auftrag sehen für den Aufrufer gleich aus —
    beide enden ohne Druckdatei —, aber sie verlangen verschiedene Antworten.
    „Der Slicer hat keine Druckdatei geschrieben" schickt den Kunden zu seinem
    Profil; bei einem Absturz gibt es dort nichts zu finden.

    **Gemessen an Creality Print 7.2** (12.09.2026): dreimal derselbe Aufruf,
    dreimal ``0xC0000005`` nach der Zeile ``crealityprint_main start``, keine
    Ausgabe, kein Protokolleintrag. Das Programm war auf dieser Maschine nie
    eingerichtet und bricht in seinem eigenen Start ab, lange bevor es das
    Modell ansieht.

    Zwei Schreibweisen, weil zwei Betriebssysteme verschieden zählen: POSIX
    meldet ein Signal als negative Zahl (``-11`` für SIGSEGV), Windows einen
    ``NTSTATUS`` mit Fehlerschwere und freiem reserviertem Bit 28. Eigene
    negative Windows-Rückgabewerte kommen dagegen als unsigned DWORD an:
    Bambus ``-100`` ist ``0xFFFFFF9C`` und kein gültiger NTSTATUS.
    """
    if exit_code < 0:
        return True
    # MS-ERREF §2.3: Schwere 11, N-Bit 0; das Customer-Bit bleibt frei,
    # damit auch nicht abgefangene C++-Ausnahmen (0xE06D7363) erkannt werden.
    return exit_code <= 0xFFFFFFFF and exit_code & 0xD0000000 == 0xC0000000


#: Die Datei, in die Bambu Studio neben die Druckdatei schreibt, wie der Lauf
#: ausging — auch dann, wenn er keine schrieb.
RESULT_FILE: Final = "result.json"

#: Größer ist sie nie: Sie trägt je Platte ein paar Kennzahlen und je Objekt
#: einen Hüllquader.
_RESULT_LIMIT: Final = 1 << 20

#: Wie grob ein Dateisystem die Änderungszeit führt: FAT zählt in zwei
#: Sekunden. Eine Datei, die knapp vor dem Start geschrieben scheint, gehört
#: noch zu diesem Lauf.
_MTIME_SLACK_S: Final = 2.0


def _result_reason(directory: Path, since: float) -> str:
    """Was der Slicer in ``result.json`` über einen gescheiterten Lauf sagt.

    **Bambu Studio sagt seine Absage nicht auf der Konsole.** Gemessen an
    Version 2.3 (RM-163, Durchsicht 0.5.0): Ein Projekt für einen Drucker, den
    Bambu nicht kennt, endet mit Rückgabewert -17 und leerer Ausgabe; der
    Grund steht nur hier — „The selected printer is not compatible with the
    process preset in the 3mf." Der Kunde las „Der Slicer hat keine
    Druckdatei geschrieben", und *Ausgabe des Slicers anzeigen* zeigte ein
    leeres Feld. Orca und Elegoo schrieben die Datei bei denselben Fehlern
    nicht; für sie ändert sich nichts.

    Nur eine Datei dieses Laufs zählt (Änderungszeit ab ``since``) — der
    Zielordner kann der des Kunden sein, mit dem Ergebnis eines älteren
    Laufs —, und nur eine Absage (``return_code`` ungleich null). Was sich
    nicht lesen lässt, sagt nichts.
    """
    path = directory / RESULT_FILE
    try:
        info = path.stat()
        if info.st_mtime < since - _MTIME_SLACK_S or info.st_size > _RESULT_LIMIT:
            return ""
        data = json.loads(path.read_bytes())
    except OSError, ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    code = data.get("return_code")
    text = data.get("error_string")
    if not isinstance(code, int) or code == 0 or not isinstance(text, str) or not text.strip():
        return ""
    return f"{text.strip()} (return_code {code})"


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
