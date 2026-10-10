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
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from contextlib import ExitStack, suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal
from xml.etree import ElementTree as ET

from app.core import activation, build_area, discover, expressions
from app.core.errors import (
    ARRANGE_ON_BED,
    CANCEL,
    CHANGE_SELECTION,
    CHECK_SLICER_PROFILE,
    CHOOSE_PRINTER,
    CHOOSE_SLICER,
    EXPORT_ONLY,
    INSTALL_MISSING,
    OPEN_PRINT_SETTINGS,
    OPEN_SETTINGS,
    PLACE_ON_BED,
    REPAIR_AND_RETRY,
    RETRY,
    SCALE_TO_FIT,
    SHOW_LOCATIONS,
    SHOW_SLICER_OUTPUT,
    SPLIT_MODEL,
    AppError,
    ExternalToolError,
    FileWriteError,
    OperationCancelled,
    ValidationError,
)
from app.core.export import cura_linux, manufacturer, slicer_keys, slicer_profiles, threemf
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
from app.core.geom.attributes import used_slots
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.ingest.threemf import SETTINGS_PATH
from app.core.knowledge import print_fields, print_settings, profiles
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
    Mesh,
    ObjectId,
    PrinterProfile,
    PrintSettings,
    Profile,
    SceneObject,
    SettingAdvice,
    SlotOverride,
    SlotProfileBinding,
)
from app.core.units import EPS_GEOM, format_length, is_close, is_zero
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

_log = get_logger(__name__)

#: Slicen dauert länger als alles andere, was Solidon außer Haus gibt. Fünf
#: Minuten sind großzügig für ein Teil und immer noch eine Grenze.
TIMEOUT_SECONDS: Final = 300.0

#: Bambu Studio wendet nur diese Filamentwerte je Düsenvariante an. Die
#: Wertfelder spiegeln ``filament_options_with_variant`` in
#: ``src/libslic3r/PrintConfig.cpp``; der Selektor selbst bleibt Profilangabe.
#: Die Länge einer Liste ist kein Feldvertrag: AMS-Trocknungswerte können
#: zufällig so viele Einträge wie das Variantenprofil haben.
BAMBU_FILAMENT_VARIANT_SETTINGS: Final = frozenset(
    {
        "filament_flow_ratio",
        "filament_max_volumetric_speed",
        "filament_ramming_volumetric_speed",
        "filament_pre_cooling_temperature",
        "filament_ramming_travel_time",
        "filament_ramming_volumetric_speed_nc",
        "filament_pre_cooling_temperature_nc",
        "filament_ramming_travel_time_nc",
        "filament_retraction_length",
        "filament_retract_length_nc",
        "filament_z_hop",
        "filament_z_hop_types",
        "filament_retract_restart_extra",
        "filament_retraction_speed",
        "filament_deretraction_speed",
        "filament_retraction_minimum_travel",
        "filament_retract_when_changing_layer",
        "filament_wipe",
        "filament_wipe_distance",
        "filament_retract_before_wipe",
        "filament_long_retractions_when_cut",
        "filament_retraction_distances_when_cut",
        "long_retractions_when_ec",
        "retraction_distances_when_ec",
        "nozzle_temperature_initial_layer",
        "nozzle_temperature",
        "filament_flush_volumetric_speed",
        "filament_flush_temp",
        "filament_flush_temp_fast",
        "filament_enable_overhang_speed",
        "filament_bridge_speed",
        "filament_overhang_1_4_speed",
        "filament_overhang_2_4_speed",
        "filament_overhang_3_4_speed",
        "filament_overhang_4_4_speed",
        "filament_overhang_totally_speed",
        "override_process_overhang_speed",
        "volumetric_speed_coefficients",
        "filament_adaptive_volumetric_speed",
        "filament_preheat_temperature_delta",
        "filament_cooling_before_tower",
        "slow_down_min_speed",
    }
)

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

#: Vorgabe aller fünf Orca-Programme, PrintConfig.cpp/prime_tower_brim_width.
#: Auch im G-Code ihrer nativen Kobra-Profile ohne diesen Schlüssel: 3 mm.
ORCA_TOWER_DEFAULT_BRIM: Final = 3.0

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
        """Wie Meldungen den Slicer nennen — wie die Listen darüber
        (:func:`discover.slicer_title`), nicht beim Dateistamm."""
        return discover.slicer_title(self.executable)


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


def machine_for(
    setup: SlicerSetup,
    profile: Profile,
    *,
    available: list[slicer_profiles.SlicerProfile] | None = None,
) -> str:
    """Das Maschinenprofil dieser Übergabe — gewählt, sonst das des Slicers.

    ``available`` sind die schon gelesenen Maschinen dieses Slicers; wer sie
    hat, reicht sie mit, sonst liest die Düsenfrage den Bestand ein zweites
    Mal (:func:`standard_choice`, RM-623).

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
        if setup.flavour == "orca" and profile.printer.id.startswith("slicer-orca-"):
            if available is None:
                available = slicer_profiles.find_profiles(
                    setup.executable, setup.flavour, ("machine",)
                )
            source_machine = slicer_profiles.machine_for_name(available, profile.printer.title)
            selected_machine = slicer_profiles.machine_for_name(available, setup.machine_profile)
            if source_machine is None or selected_machine is None:
                return ""
            source_vendor = slicer_profiles.machine_vendor(source_machine).casefold()
            printer_vendor = profile.printer.vendor.strip().casefold()
            selected_vendor = slicer_profiles.machine_vendor(selected_machine).casefold()
            if source_vendor and printer_vendor and source_vendor != printer_vendor:
                return ""
            same_identity = slicer_profiles.identity(source_machine) == (
                slicer_profiles.identity(selected_machine)
            )
            same_family = slicer_profiles.same_printer_model(source_machine, selected_machine)
            if not same_identity and not same_family:
                return ""
            if not same_identity and printer_vendor and selected_vendor != printer_vendor:
                return ""
            return slicer_profiles.machine_with_nozzle(
                setup.machine_profile,
                setup.flavour,
                setup.executable,
                profile.printer,
                available=available,
            )
        if setup.flavour == "cura":
            selected = profile_source(setup.machine_profile, setup, "machine")
            if isinstance(selected, slicer_profiles.SlicerProfile) and (
                (
                    profile.printer.id.startswith("slicer-cura-")
                    and selected.printer_id != profile.printer.id
                    and not slicer_profiles.matches_saved_cura_printer(
                        selected,
                        profile.printer,
                        discover.program_mark(setup.executable.name),
                    )
                )
                or (
                    profile.printer.cura_definition
                    and selected.printer_model != profile.printer.cura_definition
                )
            ):
                return ""
        if not _fits_the_printer(setup.machine_profile, profile):
            return ""
        return slicer_profiles.machine_with_nozzle(
            setup.machine_profile,
            setup.flavour,
            setup.executable,
            profile.printer,
            available=available,
        )
    chosen = slicer_profiles.chosen_machine(setup.flavour, setup.executable)
    if not chosen:
        return ""
    # Gleich benannte Profile verschiedener Slicer haben verschiedene IDs.
    # Bei gleichem Namen bleibt der ausdrücklich ausgewählte Drucker vorn.
    known = {profile.printer.id: profile.printer, **profiles.printer_profiles()}
    known[profile.printer.id] = profile.printer
    same = (
        slicer_profiles.chosen_printer(setup.flavour, setup.executable, known)
        if setup.flavour == "cura"
        else slicer_profiles.printer_for(chosen, known, prefer=profile.printer.id)
    )
    if same != profile.printer.id:
        _log.info(
            "slicer is set to %r (%s), the project prints on %s — no machine side handed over",
            chosen,
            same or "unknown",
            profile.printer.id,
        )
        return ""
    fitting = slicer_profiles.machine_with_nozzle(
        chosen, setup.flavour, setup.executable, profile.printer, available=available
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
    known = {profile.printer.id: profile.printer, **profiles.printer_profiles()}
    known[profile.printer.id] = profile.printer
    # Derselbe Drucker kann eingebaut und aus dem Slicer übernommen bekannt
    # sein; die Maschine gehört dann beiden (RM-600).
    mine = profile.printer.id
    belongs = slicer_profiles.printer_for(machine_profile, known, prefer=mine)
    if not belongs:
        belongs = slicer_profiles.printer_for(Path(machine_profile).stem, known, prefer=mine)
    if belongs:
        return belongs == mine
    # Ein Verwandter eines bekannten Druckers („Creality K1 SE" zum K1) ist kein
    # eigenes Profil, sondern das eines anderen Geräts (RM-600).
    return not (
        slicer_profiles.related_printer(machine_profile, known)
        or slicer_profiles.related_printer(Path(machine_profile).stem, known)
    )


def standard_choice(
    setup: SlicerSetup, profile: Profile, *, cancelled: CancelToken | None = None
) -> SlicerSetup | None:
    """Maschine, Prozess und Filament, die der Druckdialog ohne gemerkte Maschine vorbelegt.

    Für alle, die ohne gemerkte Maschine eine Grundlage brauchen —
    Hauptfenster und Export über ``remembered_setup``. Ohne sie ging eine
    Datei ohne Herstellerprozess hinaus, und der Slicer füllte, was Solidon
    nicht schreibt, mit seinen eigenen Vorgaben statt mit denen des
    Herstellers (RM-623).

    **Dieselbe Wahl wie der Dialog** (``_take_profiles``, ``_fill_processes``,
    ``_fill_filaments``); ``test_the_dialog_and_the_standard_choice_pick_alike``
    hält beide auf einem Bestand mit je zwei Maschinen, Prozessen und
    Filamenten zusammen. Die Maschine: die im Slicer eingestellte, wenn sie
    dieser Drucker ist (:func:`machine_for`), sonst die zugeordnete
    (:func:`slicer_profiles.match`), sonst die einzige des Bestands — die nur,
    wenn sie diesem Drucker zugeordnet ist. ``base_process``,
    ``base_filament`` und ``plate`` aus ``setup`` sind der Vorzug, wie im
    Dialog die gemerkte Wahl: Prozess und Filament gelten, wenn sie zur
    Maschine passen, sonst der Standardprozess der Maschine und das Filament
    der Materialart (:func:`slicer_profiles.match_filament`); die Platte bleibt.
    ``None``, wo kein Bestand den Drucker kennt — eine fremde Maschine wäre
    geraten (Regel 21) —, und wo der Bestand sich nicht lesen lässt.

    Zwei Abweichungen vom Dialog sind entschieden. **Die Düse bleibt die des
    Projekts**: Steht der Slicer auf derselben Maschine mit anderer Düse,
    übernimmt der Dialog sie in den Drucker, hier gilt die Schwestervariante
    (:func:`slicer_profiles.machine_with_nozzle`) — eine Grundlage ändert das
    Projekt nicht. **Ohne Standardprozess kein Prozess**: Der Dialog zeigt
    dann den ersten der Liste, und der Kunde sieht ihn; hier wäre er
    ungesehen geraten.

    **Kosten:** Erst nur die Maschinen (ein Sechstel des Bestands), Prozesse
    und Filamente nur, wenn eine Maschine feststeht, alle Folgefragen in einem
    Lesedurchgang (:func:`slicer_profiles.single_read`). ``cancelled`` greift
    zwischen den Schritten; ein begonnenes Lesen der Prozesse und Filamente
    endet erst mit ihm, weil :func:`slicer_profiles.find_profiles` keinen
    Abbruch kennt.
    """
    if setup.flavour not in ("orca", "prusa"):
        return None
    try:
        with slicer_profiles.single_read():
            return _standard_choice(setup, profile, cancelled)
    except (AppError, OSError) as problem:
        # Der Bestand ist eine Zugabe: Ein fremdes, kaputtes Profil kostet die
        # Grundlage, nie den Export (wie ``filament_picker.slicer_filaments``).
        _log.warning("slicer stock unreadable, no standard choice: %s", problem)
        return None


def _standard_choice(
    setup: SlicerSetup, profile: Profile, cancelled: CancelToken | None
) -> SlicerSetup | None:
    """Die Schritte von :func:`standard_choice`, ohne Fehlerfang."""

    def step() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    available = slicer_profiles.find_profiles(setup.executable, setup.flavour, ("machine",))
    step()
    current = machine_for(replace(setup, machine_profile=""), profile, available=available)
    matched, _process = slicer_profiles.match(
        available, profile.printer, source=discover.program_mark(setup.executable.name)
    )
    machine = (slicer_profiles.machine_for_name(available, current) if current else None) or matched
    machines = slicer_profiles.machines(available)
    if machine is None and len(machines) == 1 and _assigned_to(machines[0], profile):
        machine = machines[0]
    if machine is None or not _fits_the_printer(machine.name, profile):
        return None
    # Die Zuordnung darf die nächste Düse finden; die Grundlage braucht
    # dagegen die Projektdüse, bevor sie deren Prozess und Filament liest.
    fitting_machine = machine_for(
        replace(setup, machine_profile=slicer_profiles.identity(machine)),
        profile,
        available=available,
    )
    machine = (
        slicer_profiles.machine_for_name(available, fitting_machine) if fitting_machine else None
    )
    if machine is None:
        return None
    step()
    found = slicer_profiles.find_profiles(setup.executable, setup.flavour, ("process", "filament"))
    step()
    fitting = slicer_profiles.processes(found, machine)
    process = _preferred(fitting, setup.base_process) or slicer_profiles.standard_process(
        fitting, machine, profile.printer
    )
    filament = _preferred(slicer_profiles.filaments(found, machine), setup.base_filament)
    if filament is None:
        filament = slicer_profiles.match_filament(
            found, machine, slicer_keys.filament_type(profile.material.id), _profile_roots(setup)
        )
    return replace(
        setup,
        machine_profile=slicer_profiles.identity(machine),
        base_process=slicer_profiles.identity(process) if process is not None else "",
        base_filament=slicer_profiles.identity(filament) if filament is not None else "",
    )


def _assigned_to(machine: slicer_profiles.SlicerProfile, profile: Profile) -> bool:
    """Ordnet der Name diese Maschine dem Drucker des Projekts zu?

    Strenger als :func:`_fits_the_printer`, das Unerkanntes durchlässt: Die
    einzige Maschine eines Bestands („Mein Drucker") zeigt der Dialog, und der
    Kunde sieht, was er nimmt. Hier sähe sie niemand, und ein MK4S- oder
    Resin-Projekt bekäme sie samt Prozess (Regel 21, §29).
    """
    known = {**profiles.printer_profiles(), profile.printer.id: profile.printer}
    mine = profile.printer.id
    return slicer_profiles.printer_for(machine.name, known, prefer=mine) == mine


def _preferred(
    entries: Sequence[slicer_profiles.SlicerProfile], wanted: str
) -> slicer_profiles.SlicerProfile | None:
    """Der gemerkte Eintrag, wenn er unter den passenden steht — nach Kennung,
    sonst nach Namen, wie ein Projekt ihn trägt (Regel 12)."""
    if not wanted:
        return None
    return next(
        (entry for entry in entries if slicer_profiles.identity(entry) == wanted), None
    ) or next((entry for entry in entries if entry.name == wanted), None)


def foundation_findings(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    slots: Sequence[MaterialSlot] = (),
) -> list[Finding]:
    """Was der Kunde über die Grundlage wissen muss — Platte und lesbares
    Prozessprofil (:func:`app.core.export.manufacturer.findings`)."""
    if setup is None or setup.flavour not in ("orca", "prusa"):
        return []
    foundation = manufacturer.base_settings(profile, settings.quality, setup)
    findings = manufacturer.findings(foundation)
    if setup.flavour == "orca":
        chamber = 0 if slots else settings.temperature.chamber
        for slot in slots:
            resolved = _resolve_slot(settings, profile, slot, setup, foundation=foundation)
            chamber = max(chamber, resolved.settings.temperature.chamber)
        reason = manufacturer.chamber_limitation(foundation)
        if chamber > 0 and reason is not None:
            findings.append(
                Finding(
                    code="slicer.chamber_unavailable",
                    severity="warning",
                    message=reason,
                    values={"setting": _("Kammertemperatur"), "value": f"{chamber} °C"},
                    suggestions=(OPEN_PRINT_SETTINGS,),
                )
            )
    if setup.flavour != "orca" or not foundation.has_profile:
        return findings
    for slot in slots:
        resolved = _resolve_slot(settings, profile, slot, setup, foundation=foundation)
        if not resolved.variant_unresolved:
            continue
        findings.append(
            Finding(
                code="slicer.filament_variant_unresolved",
                severity="warning",
                message=_(
                    "Die gebundene Spule „{slot}“ hat keine eindeutige Variante für {variant}. "
                    "Bis Sie das Spulenprofil wählen, gelten die Projektwerte.",
                    slot=slot.name or str(slot.index + 1),
                    variant=foundation.variant_name,
                ),
                values={
                    "slot": slot.name or str(slot.index + 1),
                    "variant": foundation.variant_name,
                },
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )
    return findings


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

    **PrusaSlicer bekommt einen, seit es auf dem Bündel druckt** (Konzept
    Herstellerprofil, Stufe C). Bis dahin schwieg die Stelle mit Absicht: Eine
    ``.ini`` ist lauffähig, sobald Düse und Bettform darin stehen, und am
    03.09.2026 bekam PrusaSlicer bei jedem Export den Rat, einen Drucker
    einzurichten, den es dafür nicht brauchte. Heute druckt es ohne das
    Druckerprofil des Bündels mit seinem eingebauten Startcode — ohne
    Bettvermessung und Spüllinie —, und das ist eine Auskunft wert.

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
    if not takes_a_machine_profile(setup.flavour) and setup.flavour != "prusa":
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
                    "Das gewählte Maschinenprofil gehört zu einem anderen Drucker und wird "
                    "deshalb nicht übergeben."
                ),
                values={"machine": setup.machine_profile, "printer": profile.printer.title},
                suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER, EXPORT_ONLY),
            )
        ]
    known = slicer_profiles.supports_printer(setup.flavour, setup.executable, profile.printer.title)
    chosen = slicer_profiles.chosen_machine(setup.flavour, setup.executable)
    if chosen and known:
        # **Nur, wenn es denselben Drucker dort gibt.** „Stellen Sie den Slicer
        # auf denselben Drucker um" zeigt sonst ins Leere: Ein allgemeiner
        # Drucker mit PrusaSlicer bekam diesen Satz, weil PrusaSlicer zuletzt
        # auf irgendeinem Drucker stand (RM-431) — umstellen konnte der Kunde
        # auf nichts. Dann gilt der Satz darunter.
        return [
            Finding(
                code="slicer.machine_mismatch",
                severity="warning",
                message=_(
                    "Der Slicer ist auf einen anderen Drucker eingestellt. Der Datei fehlen "
                    "deshalb Startcode und Maschinengrenzen."
                ),
                values={"machine": chosen, "printer": profile.printer.title},
                suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER, EXPORT_ONLY),
            )
        ]
    if not known:
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
                    "{slicer} kennt {printer} nicht, deshalb trägt die Datei keine "
                    "Maschinenangaben. Der Drucker lässt sich im Slicer einrichten.",
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
                "In diesem Slicer ist noch kein Drucker eingerichtet, deshalb fehlen der Datei "
                "Startcode und Maschinengrenzen."
            ),
            values={"slicer": setup.name, "printer": profile.printer.title},
            suggestions=(CHECK_SLICER_PROFILE, EXPORT_ONLY),
        )
    ]


def cura_active_printer_mismatch(
    setup: SlicerSetup,
    profile: Profile,
    *,
    solidon_settings_included: bool = True,
) -> Finding | None:
    """Nennt beide Drucker, wenn Curas aktive Maschine eine andere ist.

    **Dieselbe Druckerdefinition mit demselben Bett ist derselbe Drucker.**
    :func:`slicer_profiles.chosen_printer` ordnet eine nicht übernommene
    Cura-Instanz bewusst keinem Solidon-Drucker zu (zwei Instanzen einer
    Familie bleiben getrennt); daran allein gemessen warnte jeder Lauf mit dem
    eingebauten Drucker „In Cura ist „Creality K1 Max“ aktiv, in Solidon
    „Creality K1 Max“" (RM-417). Die Warnung gilt dem Bett, nach dem Curas
    Fenster ausrichtet — hat der Kunde es in Cura geändert, kommt sie weiter.
    """
    active = slicer_profiles.cura_active_machine(setup.executable)
    if active is None:
        return None
    known = dict(profiles.printer_profiles())
    known[profile.printer.id] = profile.printer
    active_id = slicer_profiles.chosen_printer("cura", setup.executable, known)
    if active_id == profile.printer.id or _same_cura_machine(active, profile.printer):
        return None
    cura_printer = active.name or (
        known[active_id].title
        if active_id in known
        else slicer_profiles.cura_definition_id(active.definition)
    )
    if solidon_settings_included:
        message = _(
            "In Cura ist „{cura_printer}“ aktiv, in Solidon „{solidon_printer}“. Das "
            "Cura-Fenster richtet das Modell nach Curas Druckbett aus; Temperaturen "
            "und Druckgeschwindigkeiten stammen weiter aus Solidons Druckerprofil. "
            "Öffnen Sie die Druckeinstellungen. Ist Curas Profil vollständig lesbar, "
            "können Sie den Drucker dort mit einem Klick übernehmen.",
            cura_printer=cura_printer,
            solidon_printer=profile.printer.title,
        )
    else:
        message = _(
            "In Cura ist „{cura_printer}“ aktiv, in Solidon „{solidon_printer}“. Das "
            "Cura-Fenster richtet das Modell nach Curas Druckbett aus. Druckwerte "
            "werden nicht mitgegeben; schalten Sie „Werte mitgeben“ in den "
            "Druckeinstellungen ein, wenn Solidons Werte in Cura gelten sollen. Ist "
            "Curas Profil vollständig lesbar, können Sie den Drucker dort mit einem "
            "Klick übernehmen.",
            cura_printer=cura_printer,
            solidon_printer=profile.printer.title,
        )
    return Finding(
        code="slicer.machine_mismatch",
        severity="warning",
        message=message,
        values={"cura_printer": cura_printer, "solidon_printer": profile.printer.title},
        suggestions=(OPEN_PRINT_SETTINGS, EXPORT_ONLY),
    )


def _same_cura_machine(active: slicer_profiles.CuraActiveMachine, printer: PrinterProfile) -> bool:
    """Ob Curas aktive Maschine die Definition und das Bett dieses Druckers führt.

    Ein Bett, das die Erbkette nicht als Zahl nennt, entscheidet nichts; dann
    zählt die Definition allein.
    """
    if not printer.cura_definition:
        return False
    if slicer_profiles.cura_definition_id(active.definition) != printer.cura_definition:
        return False
    if active.bed is None:
        return True
    width, depth, _height = printer.build_volume
    return is_close(active.bed[0], width) and is_close(active.bed[1], depth)


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


def console_refusal(executable: Path) -> TranslatableText | None:
    """Warum Solidon mit diesem Slicer nicht selbst rechnet, obwohl es seine
    Familie kennt — oder ``None``.

    Eine Cura als Flatpak oder AppImage ohne ihren Lader bekommt die Datei nur
    ins Fenster (RM-521); der Druckdialog sperrt *Slicen* mit diesem Satz.
    """
    if slicer_keys.flavour_of(executable.name) == "cura" and cura_linux.engine_missing(executable):
        return cura_linux.WINDOW_ONLY
    return None


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
    *,
    native_adhesion_kinds: frozenset[str] = frozenset(),
    program: str = "",
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
    seinen Partner nicht wirkt, kommt mit (:data:`COUPLED_PATHS`). Bei Prusa
    Auto bleiben zusätzlich die im nativen Prozess aktiven Haftungsarten stehen.

    ``program`` ist die Marke des Programms (``slicer_keys.program_of``): Eine
    Wahl, die es nicht kennt, geht als ihr Ersatz hinaus, ein Aufzählungswert
    in seiner Schreibweise (RM-480, RM-461). Nur Solidons eigene Werte gehen
    hier durch — die des Herstellerprofils sind schon in ihr.
    """
    settings = _fan_curve_in_order(offered_settings(settings, program))
    if paths is not None:
        paths = _with_partners(paths, settings)
    written: dict[str, str] = {}
    for entry in slicer_keys.TABLES[flavour]:
        if paths is not None and entry.path not in paths:
            continue
        if entry.path in slicer_keys.MAKER_OWNED and entry.path not in settings.explicit:
            continue
        if entry.path == "adhesion.raft_gap" and not raft_gap_active(
            settings, flavour, also=native_adhesion_kinds
        ):
            continue
        value = entry.write(read_path(settings, entry.path))
        # Ein leerer Text heißt „dazu sagt Solidon nichts" (siehe
        # ``_number_or_silent``). Er darf weder in die Datei noch in die
        # Gegenprobe: geschrieben überschriebe er den Wert des Herstellers,
        # verglichen meldete er eine Abweichung von nichts.
        if value != "":
            written[slicer_keys.native_key(entry.key, program)] = slicer_keys.program_value(
                entry.key, value, program
            )
    chosen = _only_chosen_adhesion(
        written, settings, flavour, native_adhesion_kinds=native_adhesion_kinds
    )
    if flavour == "cura":
        # Nur die äußerste obere Haut bekommt das Oberflächentempo, wie bei
        # Prusas ``top_solid_infill_speed``. Die inneren Vollschichten fahren
        # mit der Füllung; ohne Dachschicht bliebe ``speed_roofing`` wirkungslos.
        # Auch der Profilimport im Cura-Fenster läuft durch diese Zuordnung.
        if "top_layers" in chosen or "speed_roofing" in chosen:
            chosen["roofing_layer_count"] = str(min(settings.shell.top_layers, 1))
        surface = _as_float(chosen.get("speed_roofing"))
        if surface:
            # Curas Formel bezieht sich sonst auf die nun schnelleren inneren
            # Vollschichten. Das Bügeln gehört auch im Fenster zur Oberfläche.
            chosen["speed_ironing"] = f"{surface * 20.0 / 30.0:g}"
        return _cura_fan_start(_first_layer_width(chosen), settings)
    if paths is not None and "support.density" not in paths:
        return chosen
    return _support_spacing(chosen, settings, flavour)


def offered_settings(settings: PrintSettings, program: str) -> PrintSettings:
    """Die Einstellungen mit dem Ersatz für jede Wahl, die dieses Programm nicht kennt.

    SuperSlicer kennt keine Baumstütze (RM-480): Wer sie gewählt oder einen
    Vorschlag dazu übernommen hat, bekommt dort Gitterstützen — mit allem, was
    Solidon zu Gitter schreibt, auch dem Kreuzmuster. Die Herkunft bleibt
    (``with_path``), den Satz dazu nennt ``slicer_keys.limitation``.
    """
    for path, table in slicer_keys.NOT_OFFERED_BY_PROGRAM.get(program, {}).items():
        replaced = table.get(read_path(settings, path))
        if replaced is not None:
            settings = with_path(settings, path, replaced.value)
    return settings


#: Werte, die ohne ihren Partner nicht tun, was die Wahl verlangt (Review
#: Stufe A+B, F4 und F7). Eine Haftungsart schreibt die Maße aller Arten,
#: damit :func:`_only_chosen_adhesion` die nicht gewählten nullen kann —
#: „Keine" ließ sonst den Skirt des Herstellers stehen. Eine eigene
#: Lüfter-Obergrenze nimmt das untere Ende mit: Elegoo PLA fährt unten 50 %,
#: und wer oben 20 % wählte, bekam lange Schichten mit 50.
COUPLED_PATHS: Final[Mapping[str, tuple[str, ...]]] = {
    "adhesion.kind": tuple(print_settings.ADHESION_MEASURES.values()),
    "cooling.fan_speed": ("cooling.minimum_fan_speed",),
    "layers.layer_height": ("support.density",),
    "layers.line_width": ("support.density",),
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


def values_for(
    settings: PrintSettings, profile: Profile, flavour: SlicerFlavour, *, program: str = ""
) -> dict[str, str]:
    """Alles, was dieser Slicer bekommt — Einstellungen, Maschine, Abgeleitetes.

    Die eine Stelle, an der die drei Stufen zusammenkommen. Sie hat einen
    Grund, und der ist die Reihenfolge: ``CuraEngine`` rechnet aus der
    Bahnbreite zwölf weitere und aus dem Düsendurchmesser sieben, und der
    Düsendurchmesser steht in der Maschine. Wer die Ableitung vor dem
    Zusammenführen laufen ließe, bekäme die Hälfte.
    """
    written = as_mapping(effective_adhesion(settings, profile, flavour), flavour, program=program)
    written |= _machine_keys(profile, flavour)
    if flavour == "cura":
        written = _cura_dependants(
            _cura_accelerations(written, settings, profile), settings, profile
        )
    _without_line_break(written, flavour)
    return written


def _cura_accelerations(
    written: Mapping[str, str], settings: PrintSettings, profile: Profile
) -> dict[str, str]:
    """Nur belegte oder bewusst gewählte Beschleunigungen, auch im Fensterprofil."""
    configured = dict(written)
    # Eine Qualitätsstufe kennt die Mechanik eines unbekannten Druckers nicht.
    for path, key, native in (
        ("speed.acceleration", "acceleration_print", profile.printer.acceleration),
        (
            "speed.outer_wall_acceleration",
            "acceleration_wall_0",
            profile.printer.outer_wall_acceleration,
        ),
    ):
        if native is None and path not in settings.explicit:
            configured.pop(key, None)
    active = "acceleration_print" in configured or "acceleration_wall_0" in configured
    configured["acceleration_enabled"] = "true" if active else "false"
    if "acceleration_print" in configured:
        configured.setdefault("acceleration_wall_0", configured["acceleration_print"])
    return configured


def effective_adhesion(
    settings: PrintSettings,
    profile: Profile,
    flavour: SlicerFlavour,
    foundation: manufacturer.Foundation | None = None,
) -> PrintSettings:
    """Die wirksame Haftungsart für diesen Slicer und dieses Material.

    Die Orca-Familie hat ``auto_brim``; PrusaSlicer und CuraEngine nicht. Dort
    heißt „Automatisch" die Art aus Solidons Tabelle, außer eine passende
    Prusa-Grundlage ist gewählt; dann gilt die Art des Profils. Ein ausdrücklich
    gewähltes Nullmaß bleibt stehen, während ein ungewähltes Nullmaß auf die
    Vorgabe zurückfällt. Der Druckdialog und die Übergabe fragen dieselbe
    Auflösung ab. Ohne diese Abbildung bekam Cura einen Skirt mit null Linien
    und PrusaSlicer an jedem Teil einen Brim (Review Stufe A+B, F5).
    """
    from app.core.slice import advise

    # „other“ übersetzt Solidon nicht; dort bleibt die Art, wie sie ist.
    if (
        settings.adhesion.kind != "auto"
        or flavour in advise.AUTO_BRIM_FLAVOURS
        or flavour == "other"
    ):
        return settings
    prusa_foundation = _prusa_foundation(profile, flavour, foundation)
    base = (
        prusa_foundation.settings
        if prusa_foundation is not None
        else print_settings.resolve(profile, settings.quality)
    )
    measures = {}
    for path in print_settings.ADHESION_MEASURES.values():
        name = path.partition(".")[2]
        if path not in settings.explicit and (
            prusa_foundation is not None or getattr(settings.adhesion, name) <= 0
        ):
            measures[name] = getattr(base.adhesion, name)
    return replace(
        settings,
        adhesion=replace(settings.adhesion, kind=base.adhesion.kind, **measures),
    )


def _prusa_foundation(
    profile: Profile, flavour: SlicerFlavour, foundation: manufacturer.Foundation | None
) -> manufacturer.Foundation | None:
    """Die Prusa-Grundlage, deren Haftung „Automatisch“ bestimmt — sonst keine."""
    if (
        flavour == "prusa"
        and foundation is not None
        and foundation.has_profile
        and foundation.profile == profile
    ):
        return foundation
    return None


def native_adhesion_kinds(
    settings: PrintSettings,
    profile: Profile,
    flavour: SlicerFlavour,
    foundation: manufacturer.Foundation | None,
) -> frozenset[str]:
    """Die Haftungsarten, die eine Prusa-Grundlage bei „Automatisch“ selbst führt.

    Ein Prusa-Prozess kann Skirt und Brim zugleich tragen; „Automatisch“ heißt
    dort seine Kombination, und :func:`_only_chosen_adhesion` nullt diese Arten
    nicht (:func:`prusa_values`). Nur Maße, die das Profil wirklich nennt.
    """
    chosen = _prusa_foundation(profile, flavour, foundation)
    if settings.adhesion.kind != "auto" or chosen is None:
        return frozenset()
    return frozenset(
        kind
        for kind, path in print_settings.ADHESION_MEASURES.items()
        if path in chosen.from_profile and read_path(chosen.settings, path) > 0
    )


def handed_over_adhesion_kinds(
    settings: PrintSettings,
    profile: Profile,
    flavour: SlicerFlavour,
    foundation: manufacturer.Foundation | None = None,
) -> tuple[str, frozenset[str]]:
    """Die Haftungsart, die dieser Slicer bekommt, und die Arten, deren Maße wirken.

    Dieselbe Auflösung wie die Übergabe (:func:`effective_adhesion`,
    :func:`native_adhesion_kinds`, :func:`print_settings.adhesion_kinds`) —
    der Druckdialog zeigt danach genau die Maße, die hinausgehen (RM-432).
    """
    effective = effective_adhesion(settings, profile, flavour, foundation)
    kind = effective.adhesion.kind
    return kind, print_settings.adhesion_kinds(kind) | native_adhesion_kinds(
        settings, profile, flavour, foundation
    )


def raft_gap_active(
    settings: PrintSettings, flavour: SlicerFlavour, *, also: frozenset[str] = frozenset()
) -> bool:
    """Ob die wirksame Haftung den eigenen Abstand tatsächlich verwenden kann.

    Cura zählt nur die Raft-Deckschichten; null lässt seine Basis stehen.
    Prusa und Orca schalten den gesamten Raft über diese Schichtzahl aus.
    """
    return "raft" in (print_settings.adhesion_kinds(settings.adhesion.kind) | also) and (
        flavour == "cura" or settings.adhesion.raft_layers > 0
    )


def by_section(
    settings: PrintSettings,
    flavour: SlicerFlavour,
    paths: frozenset[str] | None = None,
    *,
    program: str = "",
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
    complete = as_mapping(settings, flavour, paths, program=program)
    split: dict[slicer_keys.ProfileSection, dict[str, str]] = {"process": {}}
    placed: set[str] = set()
    for entry in slicer_keys.TABLES[flavour]:
        key = slicer_keys.native_key(entry.key, program)
        if key in complete:
            split.setdefault(entry.section, {})[key] = complete[key]
            placed.add(key)
    for key, value in complete.items():
        if key not in placed:
            split["process"][key] = value
    return split


def object_keys(
    settings: PrintSettings,
    advice: Sequence[SettingAdvice],
    flavour: SlicerFlavour,
    *,
    program: str = "",
    profile: Profile | None = None,
    native: Mapping[str, object] | None = None,
    brim_foot_offset: float | None = 0.0,
) -> dict[str, str]:
    """Die Abweichungen eines Teils in der Sprache des Slicers (§29).

    Geschrieben werden die Pfade des Rats und ihre Partner aus
    :data:`COUPLED_PATHS`, nicht die ganze Gruppe. Wer die Haftungsart auf
    Brim stellt, braucht auch dessen Breite — und die Maße der Arten, die
    *nicht* gewählt sind, müssen auf null, sonst läuft unter dem Teil
    zusätzlich ein Raft mit (siehe :func:`_only_chosen_adhesion`). Die übrigen
    Werte der Gruppe gehören der Platte: Über die Gruppe bekam ein Teil mit
    Passungsrat am Bambu P1S 21 Objektwerte statt vier, darunter die innere
    Vollfüllung mit 270 statt Bambus 250 mm/s, und der Slicer druckte sie so
    (Durchsicht 0.5.1, B1).

    Dazu, was sich sonst noch geändert hat. Nicht jeder Schlüssel steht in der
    Zuordnungstabelle: die Stützdichte etwa wird für PrusaSlicer und die
    Orca-Familie erst zu einem Linienabstand gerechnet, und über den Pfad
    allein wäre sie nicht zu finden. Ein Vergleich findet sie, ohne dass
    irgendwo eine zweite Liste gepflegt werden muss.
    """
    if not advice:
        return {}
    applied = _applied(settings, advice)
    paths = _with_partners(frozenset(entry.path for entry in advice), applied)
    keys = {
        slicer_keys.native_key(entry.key, program)
        for entry in slicer_keys.TABLES[flavour]
        if entry.path in paths
    }
    # CuraEngine wertet die Formeln seines Fensters nicht aus. Objektwerte
    # und Rücknahmen brauchen dieselben Ableitungen wie die ganze Platte.
    before = (
        values_for(settings, profile, flavour, program=program)
        if flavour == "cura" and profile is not None
        else as_mapping(settings, flavour, program=program)
    )
    changed = (
        values_for(applied, profile, flavour, program=program)
        if flavour == "cura" and profile is not None
        else as_mapping(applied, flavour, program=program)
    )
    written = {
        key: value for key, value in changed.items() if key in keys or before.get(key) != value
    }
    if native is not None:
        written.update(_speed_roles(native, written, flavour, program=program))
        written.update(_acceleration_roles(native, written, flavour, applied))
        if flavour == "orca":
            written.update(tree_over_hybrid(native, applied.support.style, written))
        if flavour == "orca" and profile is not None and "enable_support" in written:
            # Schaltet erst das Teil Stützen ein, prüft der Slicer seine Bäume
            # mit den Werten der Platte (:func:`organic_tree_fitted`).
            written.update(
                organic_tree_fitted({**native, **written}, profile.printer.nozzle_diameter)
            )
    foot = brim_foot_offset
    if (
        flavour == "orca"
        and foot is not None
        and not is_zero(foot)
        and "elefant_foot_compensation" in written
    ):
        # Die Orca-Familie misst den Brim vom unkorrigierten Umriss (RM-318).
        # Zieht dieses Teil die erste Schicht nicht mehr ein, weil sein Modell
        # es tut (RM-589), bleibt der Abstand am Fuß nur mit eigenem Wert.
        foot = float(written["elefant_foot_compensation"])
        if "brim" in print_settings.adhesion_kinds(applied.adhesion.kind):
            written["brim_object_gap"] = ""
    if flavour == "orca" and "brim_object_gap" in written:
        requested = any(entry.path == "adhesion.brim_gap" for entry in advice)
        if "brim" not in print_settings.adhesion_kinds(applied.adhesion.kind) or (
            foot is None and not requested
        ):
            written.pop("brim_object_gap")
        else:
            written.update(manufacturer.part_brim_gap(applied.adhesion.brim_gap, foot, program))
    return _with_automatic_prusa_support(written) if flavour == "prusa" else written


def _with_automatic_prusa_support(written: dict[str, str]) -> dict[str, str]:
    """Wer bei PrusaSlicer Stützen einschaltet, schaltet auch die automatischen ein.

    Prusas Vorgabe ist ``support_material = 1`` mit ``support_material_auto =
    0``: Stützen nur an gemalten Verstärkern (Entscheidung J). Für die Platte
    stand die Regel in :func:`prusa_values`; der Objektwert eines Teils kannte
    sie nicht, und der Pilz der Abnahme von Stufe E erbte „nur Verstärker":
    kein einziger Stützweg im G-Code von PrusaSlicer 2.9.6, während
    ElegooSlicer und CuraEngine ihn stützten (27.09.2026).
    """
    if written.get("support_material") == "1":
        written["support_material_auto"] = "1"
    return written


#: Was CuraEngine je Netz annimmt, gelesen aus ``settable_per_mesh`` in
#: ``fdmprinter.def.json`` (Cura 5.13), einschließlich der geschriebenen
#: Ableitungen. Haftungsart (``adhesion_type``), Stützort (``support_type``)
#: und Stützart (``support_structure``) gelten nur der ganzen Platte.
CURA_PER_MESH: Final = frozenset(
    {
        "acceleration_flooring",
        "acceleration_infill",
        "acceleration_ironing",
        "acceleration_layer_0",
        "acceleration_print",
        "acceleration_print_layer_0",
        "acceleration_roofing",
        "acceleration_topbottom",
        "acceleration_wall",
        "acceleration_wall_0_flooring",
        "acceleration_wall_0_roofing",
        "acceleration_wall_x",
        "acceleration_wall_x_flooring",
        "acceleration_wall_x_roofing",
        "bottom_layers",
        "bottom_skin_expand_distance",
        "bottom_skin_preshrink",
        "bridge_fan_speed",
        "bridge_settings_enabled",
        "bridge_skin_speed",
        "bridge_skin_speed_2",
        "bridge_skin_speed_3",
        "bridge_wall_min_length",
        "bridge_wall_speed",
        "connect_infill_polygons",
        "expand_skins_expand_distance",
        "flooring_layer_count",
        "flooring_line_width",
        "flooring_material_flow",
        "infill_angles",
        "infill_before_walls",
        "infill_line_distance",
        "infill_line_width",
        "infill_material_flow",
        "infill_overlap",
        "infill_overlap_mm",
        "infill_pattern",
        "infill_sparse_thickness",
        "infill_wipe_dist",
        "initial_bottom_layers",
        "initial_layer_inset_direction",
        "ironing_inset",
        "material_flow",
        "min_bead_width",
        "min_even_wall_line_width",
        "min_feature_size",
        "min_odd_wall_line_width",
        "min_wall_line_width",
        "minimum_support_area",
        "retraction_amount",
        "retraction_extrusion_window",
        "retraction_hop",
        "retraction_hop_only_when_collides",
        "retraction_min_travel",
        "retraction_prime_speed",
        "retraction_retract_speed",
        "retraction_speed",
        "roofing_layer_count",
        "roofing_line_width",
        "roofing_material_flow",
        "seam_overhang_angle",
        "skin_line_width",
        "skin_material_flow",
        "skin_overlap_mm",
        "skin_preshrink",
        "skin_support",
        "skin_support_fan_speed",
        "skin_support_speed",
        "small_skin_width",
        "speed_flooring",
        "speed_infill",
        "speed_ironing",
        "speed_layer_0",
        "speed_print",
        "speed_print_layer_0",
        "speed_roofing",
        "speed_topbottom",
        "speed_wall",
        "speed_wall_0_flooring",
        "speed_wall_0_roofing",
        "speed_wall_x",
        "speed_wall_x_flooring",
        "speed_wall_x_roofing",
        "support_angle",
        "support_bottom_distance",
        "support_bottom_enable",
        "support_bottom_height",
        "support_bottom_stair_step_height",
        "support_interface_enable",
        "support_interface_height",
        "support_roof_enable",
        "support_roof_height",
        "support_top_distance",
        "support_tree_angle",
        "support_tree_angle_slow",
        "support_tree_rest_preference",
        "support_tree_tip_diameter",
        "support_tree_top_rate",
        "support_xy_distance",
        "support_xy_distance_overhang",
        "support_z_distance",
        "top_layers",
        "top_skin_expand_distance",
        "top_skin_preshrink",
        "wall_0_inset",
        "wall_0_material_flow",
        "wall_0_material_flow_flooring",
        "wall_0_material_flow_roofing",
        "wall_0_wipe_dist",
        "wall_line_width",
        "wall_line_width_0",
        "wall_line_width_x",
        "wall_material_flow",
        "wall_overhang_angle",
        "wall_overhang_speed_factors",
        "wall_x_material_flow",
        "wall_x_material_flow_flooring",
        "wall_x_material_flow_roofing",
        "z_seam_corner",
        "z_seam_type",
        "z_seam_x",
        "z_seam_y",
        "support_enable",
        "infill_sparse_density",
        "line_width",
        "ironing_enabled",
        "inset_direction",
        "wall_line_count",
        "speed_wall_0",
        "acceleration_wall_0",
        "scarf_joint_seam_length",
        # Was das Modell schon ausgleicht, gleicht das Netz nicht noch einmal aus (RM-589).
        "hole_xy_offset",
        "xy_offset_layer_0",
    }
)


@dataclass(frozen=True, slots=True)
class PartSplit:
    """Welche übernommenen Vorschläge je Teil gelten und was die Platte behält
    (Konzept Herstellerprofil, Entscheidung G).

    Bei der Orca-Familie und PrusaSlicer trägt die Platte die Grundlage, und die
    Teile, deren Geometrie es verlangt, bekommen den übernommenen Wert als
    Objektwert. CuraEngine nimmt Haftungs-, Stützart und Stützort nicht je Netz
    an; dort behält die Platte die Übernahme, und die Teile, die sie nicht
    brauchen, bekommen je Netz die Grundlage zurück (``revert``) — so stützt
    Cura nur das Teil, das es braucht, und mit der gewählten Stützart.
    """

    plate: PrintSettings
    """Was die ganze Platte bekommt."""
    base: PrintSettings
    """Die Einstellungen ohne die Übernahmen je Teil — auch ohne die, die der
    Slicer nur plattenweit annimmt: der Stand, an dem der Rat je Körper gefragt
    wird."""
    per_part: frozenset[str] = frozenset()
    """Die Pfade, die je Teil geschrieben werden."""
    revert: bool = False
    unavailable: frozenset[str] = frozenset()
    """Was die Geometrie je Teil will, der Slicer aber nicht je Teil annimmt —
    es bleibt plattenweit, und der Export sagt, wo es nicht reicht."""
    accepted: PrintSettings | None = None
    """Die Einstellungen mit allen Übernahmen, bevor der Split sie zurücksetzt."""
    native: Mapping[str, object] = field(default_factory=dict)
    """Die wirksamen Rollenwerte der Platte für begrenzende Objektwerte."""
    brim_foot_offset: float | None = None
    """Bezug des nativen Brim-Abstands, aus derselben Herstellergrundlage."""

    def accepted_per_part(self) -> dict[str, object]:
        """Die übernommenen Werte der Pfade je Teil — was der Rat je Teil in
        seiner Kette trägt (:func:`app.core.export.writer.part_advice`)."""
        if self.accepted is None:
            return {}
        return {path: read_path(self.accepted, path) for path in sorted(self.per_part)}


#: Was Cura je Netz aus einer Schichtzahl ableitet (:func:`_for_supports`,
#: :func:`_cura_dependants`): Die
#: Trennschicht ist dort eine Höhe samt Schalter, und beide nimmt CuraEngine je
#: Netz an. Der Linienabstand der Trennschicht gilt dem Stützextruder, nicht
#: dem Netz — die Lücke bleibt deshalb plattenweit (RM-583).
CURA_DERIVED_PER_MESH: Final[dict[str, tuple[str, ...]]] = {
    "support.interface_layers": (
        "support_interface_height",
        "support_roof_height",
        "support_interface_enable",
        "support_roof_enable",
    ),
    "support.bottom_interface_layers": ("support_bottom_height", "support_bottom_enable"),
}


def _part_paths(flavour: SlicerFlavour, program: str = "") -> frozenset[str]:
    """Welche Pfade dieser Slicer je Teil annehmen kann."""
    from app.core.slice import advise

    supported = frozenset(
        path for path in advise.PART_PATHS if slicer_keys.takes(flavour, path, program=program)
    ) - slicer_keys.unknown_in_file(flavour, program)
    if flavour in ("orca", "prusa"):
        # Eine reine Datei kennt die spätere Programmauswahl noch nicht.
        # Deshalb gelten die gemessenen Objektgrenzen aller Programme der
        # Familie; vollständig unbekannte Schlüssel behandelt ``takes``.
        plate_only = (
            slicer_keys.PLATE_ONLY_BY_PROGRAM.get(program, frozenset())
            if slicer_keys.flavour_of(program) == flavour
            else frozenset(
                path
                for name, paths in slicer_keys.PLATE_ONLY_BY_PROGRAM.items()
                if slicer_keys.flavour_of(name) == flavour
                for path in paths
            )
        )
        return supported - plate_only
    if flavour == "cura":
        return (
            slicer_keys.AS_GEOMETRY
            | frozenset(
                entry.path
                for entry in slicer_keys.TABLES["cura"]
                if entry.path in supported and entry.key in CURA_PER_MESH
            )
            | frozenset(path for path in CURA_DERIVED_PER_MESH if path in supported)
        ) - slicer_keys.PLATE_ONLY_BY_PROGRAM["cura"]
    return frozenset()


def asked_for_contact(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    flavour: SlicerFlavour | None,
) -> tuple[frozenset[str], PrintSettings]:
    """Wogegen der Druckdialog den Stützkontakt je Körper fragt (RM-583).

    Die Pfade aus ``advise.CONTACT_PATHS``, die dieser Slicer je Teil annimmt,
    und Einstellungen, in denen sie auf der Grundlage stehen — wie im Export,
    der je Teil gegen ``split_for_parts(...).base`` fragt. Gegen die Übernahme
    gefragt, brachte jedes Übernehmen die Gegenzeile: Der Tisch wollte 0,2 gegen
    die übernommenen 0,5 des Kinns, das Kinn danach wieder 0,5.

    **Die Stützart steht ebenso auf der Grundlage**, wo sie je Teil geht
    (RM-622): Der Export gibt einen übernommenen Baum nur dem Teil, das ihn
    verlangt, und Abstand wie untere Trennschicht hängen an der Art, mit der
    ein Teil druckt. Gegen die Übernahme gefragt, rechnete der Dialog den Tisch
    unter dem Gitter der Platte als Baum, und seine Zeilen verschwanden.
    ``advise.combine`` vergleicht weiter mit der Übernahme, eine Gegenzeile zur
    Stützart entsteht nicht.
    """
    from app.core.slice import advise

    if flavour is None:
        return frozenset(), settings
    # Ohne gefundenen Slicer trennt der Export ebenso, für die Familie der Datei.
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    per_part = _part_paths(flavour, program)
    separate = advise.CONTACT_PATHS & per_part
    if not separate:
        return separate, settings
    base = split_for_parts(settings, profile, setup, flavour).base
    asking = settings
    for path in sorted(separate | (per_part & {"support.style"})):
        asking = with_path(asking, path, read_path(base, path))
    return separate, asking


def style_per_part(flavour: SlicerFlavour | None, program: str = "") -> bool:
    """Bekommt jedes Teil seine eigene Stützart, samt Art (RM-584)?

    In der Orca-Familie und bei PrusaSlicer ja, wo das Programm sie je Objekt
    liest (:func:`_part_paths`). Cura schaltet Stützen je Netz, die Art gilt der
    Platte (:func:`cura_takes_whole`). Wo sie je Teil geht, führt der
    Druckdialog Gitter und Baum zweier Körper nicht zu Hybrid zusammen: Die
    Datei bekäme dafür je Teil Gitter und Baum, und die Zeile zeigte, was nicht
    gedruckt wird.
    """
    if flavour is None:
        return False
    if flavour == "cura" and not cura_takes_whole("support.style"):
        return False
    return "support.style" in _part_paths(flavour, program)


def cura_takes_whole(path: str) -> bool:
    """Ob CuraEngine jeden Schlüssel dieses Pfads je Netz annimmt.

    ``support.style`` geht dort nur halb: ob gestützt wird
    (``support_enable``) je Netz, die Stützart (``support_structure``) nur für
    die ganze Platte. Ein Teil bekommt dann den Wert der Platte, nicht seinen
    eigenen.
    """
    if path in slicer_keys.AS_GEOMETRY or path in CURA_DERIVED_PER_MESH:
        return True
    if path in slicer_keys.PLATE_ONLY_BY_PROGRAM["cura"]:
        return False
    keys = [entry.key for entry in slicer_keys.TABLES["cura"] if entry.path == path]
    return bool(keys) and all(key in CURA_PER_MESH for key in keys)


def split_for_parts(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    flavour: SlicerFlavour,
) -> PartSplit:
    """Trennt die übernommenen Vorschläge in plattenweite und solche je Teil.

    Je Teil geht, was die Geometrie eines Körpers verlangt
    (:data:`app.core.slice.advise.PART_PATHS`) und keine plattenweite Regel —
    Maschine, Material, Volumenstrom (:func:`app.core.slice.advise.plate_paths`)
    — ebenfalls. Die Grundlage ist die des Herstellerprofils, ohne eines
    Solidons Tabelle (:func:`app.core.export.manufacturer.base_settings`).
    ``write_assembly`` und ``slice_model`` fragen dasselbe und bekommen
    dieselbe Platte.
    """
    from app.core.export import manufacturer
    from app.core.slice import advise

    # Was das Programm nicht kennt, geht an kein Teil (RM-459); auf der
    # Platte nimmt es :func:`prusa_values` heraus. Was die Familie gar nicht
    # nimmt, ist auch nicht „nur plattenweit“: Cura bekam die dicke Brücke
    # sonst als Übernahme der Platte gemeldet, die es nie druckt (RM-587).
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    unknown = slicer_keys.NOT_TAKEN_BY_PROGRAM.get(program, frozenset()) | (
        slicer_keys.NOT_TAKEN_BY[flavour] | slicer_keys.unknown_in_file(flavour, program)
        if flavour != "other"
        else frozenset()
    )
    wanted = frozenset(settings.accepted) & advise.PART_PATHS - unknown
    if not wanted:
        return PartSplit(settings, settings)
    origin = manufacturer.base_settings(profile, settings.quality, setup)
    foundation = origin.settings
    base = settings
    # Die Platte bekommt die eigene Wahl unter dem Vorschlag, sonst die
    # Grundlage (RM-289, B2).
    for path in sorted(wanted):
        base = print_settings.for_the_plate(base, path, foundation)
    wanted -= advise.plate_paths(
        base, profiles.for_process(profile, base, effective=True), flavour=flavour
    )
    per_part = wanted & _part_paths(flavour, program)
    unavailable = wanted - per_part
    trimmed = settings
    for path in sorted(per_part):
        trimmed = print_settings.for_the_plate(trimmed, path, foundation)
    # **Der Rat je Teil wird ohne jede Übernahme je Teil gefragt**, auch ohne
    # die, die der Slicer nur plattenweit annimmt. Trug die Grundlage sie
    # schon, schwieg der Rat an der Stange, und am Block stand bei Cura das
    # ruhige Innenwandtempo der Stange, ohne dass ein Befund es sagte (RM-430).
    untouched = trimmed
    for path in sorted(unavailable):
        untouched = print_settings.for_the_plate(untouched, path, foundation)
    if flavour == "cura":
        return PartSplit(
            settings, untouched, per_part, revert=True, unavailable=unavailable, accepted=settings
        )
    native = (
        _part_native_values(trimmed, profile, setup, origin, flavour)
        if per_part
        & {"speed.acceleration", "speed.outer_wall", "speed.inner_wall", "support.style"}
        else {}
    )
    return PartSplit(
        trimmed,
        untouched,
        per_part,
        unavailable=unavailable,
        accepted=settings,
        native=native,
        brim_foot_offset=origin.brim_foot_offset,
    )


def _part_native_values(
    plate: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    foundation: manufacturer.Foundation,
    flavour: SlicerFlavour,
) -> Mapping[str, object]:
    """Tempo- und Beschleunigungsrollen der Platte vor den Teilwerten lesen."""
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    if flavour == "prusa":
        # Auch ohne Kette erbt der vollständige Plattensatz offene Rollen
        # aus den gemessenen Programmvorgaben. Der Dateiexport kennt setup
        # nicht zwingend, seine ausdrücklich gewählte Familie aber schon.
        return prusa_values(plate, profile, setup, console=False)[0]
    if setup is None or not foundation.has_profile:
        return {}
    if setup.flavour != "orca":
        return {}
    source = profile_file(setup.base_process, setup, "process")
    if source is None:
        return {}
    native = slicer_profiles.resolve_values(source, roots=_profile_roots(setup))
    # Bambu ordnet Listen der Düsenvariante zu, nicht grundsätzlich Index 0.
    values = {
        key: _printed_variant(
            value, native, "print_extruder_variant", "print_extruder_id", foundation
        )
        for key, value in native.items()
    }
    own = as_mapping(
        plate, setup.flavour, manufacturer.written_paths(plate, foundation), program=program
    )
    own.update(_acceleration_roles(values, own, setup.flavour, plate))
    return {**values, **own}


def _applied(settings: PrintSettings, advice: Sequence[SettingAdvice]) -> PrintSettings:
    """Die Einstellungen mit den Abweichungen dieses Teils darin.

    Nicht über :func:`app.core.slice.advise.apply` — der Kern soll von hier
    nach dort nicht abhängen, und es sind zwei Zeilen.
    """
    changed = settings
    for entry in advice:
        changed = with_path(changed, entry.path, entry.value)
    # Der Rat dieses Teils ist für das Teil übernommen; so schreibt
    # :func:`as_mapping` auch, was es sonst dem Slicer lässt (RM-589).
    return replace(changed, accepted=changed.accepted | {entry.path for entry in advice})


def _only_chosen_adhesion(
    written: dict[str, str],
    settings: PrintSettings,
    flavour: SlicerFlavour,
    *,
    native_adhesion_kinds: frozenset[str] = frozenset(),
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
    # Der Auto-Brim misst mit der Brimbreite — sie bleibt stehen
    # (:func:`print_settings.adhesion_kinds`, dieselbe Frage wie der Dialog).
    kept = print_settings.adhesion_kinds(settings.adhesion.kind) | native_adhesion_kinds
    for wanted, keys in slicer_keys.ADHESION_KEYS[flavour].items():
        if wanted in kept:
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
    kennen dort keinen Anteil, sondern die **Lücke** zwischen zwei
    Stützlinien in Millimetern — ``support_material_spacing`` beim einen,
    ``support_base_pattern_spacing`` beim anderen; die Teilung ist Lücke plus
    Linienabstand (:func:`manufacturer.support_gap`). Als Teilung geschrieben
    druckten 15 % als 12 %, und 0 % als die dichteste Stütze (RM-475).

    Die Teilung ist Linienabstand durch Dichte. Die dafür verwendete
    Stützbahnbreite geht mit, damit das Herstellerprofil die Rechnung nicht
    verändert. Eine aktive Null-Dichte verlangt eine neue Wahl; eine Lücke
    null wäre das Gegenteil des Gemeinten. Ohne Stützen wirkt der Wert nicht.
    """
    key = {"prusa": "support_material_spacing", "orca": "support_base_pattern_spacing"}.get(flavour)
    if key is None:
        return written
    density = settings.support.density
    if density < print_settings.LEAST_SUPPORT_DENSITY and settings.support.style != "none":
        raise ValidationError(
            field="support.density",
            detail=_(
                "Wählen Sie mindestens 1 % Stützdichte oder schalten Sie die Stützen aus. "
                "Dieser Slicer kann 0 % Stützfüllung nicht darstellen."
            ),
            suggestions=(OPEN_PRINT_SETTINGS,),
        )
    density = max(density, print_settings.LEAST_SUPPORT_DENSITY)
    gap = manufacturer.support_gap(
        density, settings.layers.line_width, settings.layers.layer_height
    )
    # Beide Familien schreiben sechs signifikante Stellen in den G-Code.
    written[key] = f"{gap:.6g}"
    width_key = "support_material_extrusion_width" if flavour == "prusa" else "support_line_width"
    written[width_key] = f"{settings.layers.line_width:.9g}"
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
    _for_supports(written, settings, profile)
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


def _for_supports(written: dict[str, str], settings: PrintSettings, profile: Profile) -> None:
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
        # (``support_infill_rate`` 0 beim Baum, ``support_wall_count``).
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
        # Eine eigene Lücke gilt erst, wenn sie gewählt oder übernommen ist
        # (RM-583); sonst die der Grundlage, auch bei geänderter Bahnbreite.
        gap = settings.support.interface_spacing
        if "support.interface_spacing" not in settings.chosen | settings.accepted:
            gap = manufacturer.cura_interface_gap(print_settings.resolve(profile, settings.quality))
        spacing = width + gap
        for key in ("support_roof_line_distance", "support_bottom_line_distance"):
            written[key] = f"{spacing:g}"
        # Die Stütze wächst um eine Bahnbreite plus Curas festen Zuschlag —
        # beim Baum um nichts.
        written["support_offset"] = "0" if tree else f"{width + _SUPPORT_GROWTH:g}"
        # Beim Baum die Wände der Stämme (RM-584), normale Stütze ohne Wand.
        written["support_wall_count"] = str(settings.support.tree_walls) if tree else "0"
    # Krümel unter 2 mm² bekommen keine eigene Stütze (Creality in Cura).
    written["minimum_support_area"] = f"{_MINIMUM_SUPPORT_AREA:g}"

    # Ohne den Schalter entsteht gar keine Schnittstelle, und ohne die Höhe
    # wurden aus zwei Schichten zwei Millimeter — das Zehnfache bei 0,2ern.
    layers = settings.support.interface_layers
    # Unten eigene Lagen (RM-583): Wo die Stütze auf dem Modell steht,
    # zeichnet ihr roher Fuß die Fläche darunter.
    bottom = settings.support.bottom_interface_layers
    height = settings.layers.layer_height
    written["support_interface_height"] = f"{layers * height:g}"
    written["support_bottom_height"] = f"{bottom * height:g}"
    written["support_roof_enable"] = "true" if layers > 0 else "false"
    written["support_bottom_enable"] = "true" if bottom > 0 else "false"
    written["support_interface_enable"] = "true" if layers > 0 or bottom > 0 else "false"
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

    Für ``prusa`` ohne Druckerprofil des Bündels ist eine ``.ini``
    eigenständig lauffähig, sobald Düse und Bettform darin stehen; mit ihm
    kommt die Maschine aus dem Bündel (:func:`prusa_values`), und diese
    Schlüssel entfallen. Orca lädt ein Maschinenprofil aus seinem Bestand,
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
        from app.core import build_area

        width, depth, height = profile.printer.build_volume
        # **Der Ursprung des Druckers** (RM-424): Cura kennt nur Ecke oder
        # Mitte (``machine_center_is_zero``). Liegt er woanders — am Dremel
        # 3D45 15 mm rechts der Mitte —, verschiebt ``mesh_position_*`` jedes
        # Netz um den Rest, von CuraEngines halbem Bett auf den Nullpunkt der
        # Maschine. Eine Druckerdefinition behält ihren (:func:`_cura_machine`).
        shift = build_area.machine_shift(profile.printer)
        centred = is_zero(shift[0]) and is_zero(shift[1])
        rest = (shift[0] - width / 2.0, shift[1] - depth / 2.0)
        offset = (
            {}
            if centred or (is_zero(rest[0]) and is_zero(rest[1]))
            else {"mesh_position_x": f"{rest[0]:g}", "mesh_position_y": f"{rest[1]:g}"}
        )
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
            # Eine Druckerdefinition mit Ursprung in der Mitte behält ihren
            # (:func:`_cura_machine`), und die Naht folgt ihm. Ohne Definition
            # gilt der Ursprung des Druckers (RM-424).
            "machine_center_is_zero": "true" if centred else "false",
            **offset,
            **_cura_seam(depth, shift),
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
    from app.core import build_area

    printer = profile.printer
    width, depth, height = printer.build_volume
    # Um den Nullpunkt der Maschine: Die Teile kommen in Bettkoordinaten
    # (``wants_bed_coordinates``), und die Bettform beschreibt dieselbe Welt
    # — die des Druckers, dessen Nullpunkt meist vorn links liegt. Eine Form
    # von ``-128`` bis ``128`` über verschobenen Teilen endete in „All objects
    # are outside of the print volume"; dieselbe Form über unverschobenen
    # Teilen ließ den Slicer Bahnen bei ``-13,6`` schreiben, die es auf der
    # Maschine nicht gibt (Gesamtreview 05.09.2026, CORE-17). Ein Bett um den
    # Ursprung (BIBO, Deltas) bekam bis RM-424 trotzdem eines ab der Ecke.
    across, along = build_area.machine_shift(printer)
    left, right = across - width / 2.0, across + width / 2.0
    front, back = along - depth / 2.0, along + depth / 2.0
    corners = f"{left:g}x{front:g},{right:g}x{front:g},{right:g}x{back:g},{left:g}x{back:g}"
    return {
        "nozzle_diameter": f"{printer.nozzle_diameter:g}",
        "bed_shape": corners,
        "max_print_height": f"{height:g}",
    }


#: Was PrusaSlicer ohne Drucker seines Bündels aus seinen eingebauten Vorgaben
#: nähme, obwohl Prusas eigener Bestand es in jedem Prozess anders setzt
#: (``[print:*common*]`` in ``PrusaResearch.ini``, 2.9). ``extra_perimeters``
#: legt an schrägen Flächen Wände über Solidons Wandzahl hinaus, die die
#: Orca-Familie nicht kennt; ``solid_infill_below_area`` füllt jede Fläche
#: unter 70 mm² voll (RM-191).
PRUSA_WITHOUT_BUNDLE: Final[Mapping[str, str]] = {
    "extra_perimeters": "0",
    "solid_infill_below_area": "0",
}

#: Die Beschleunigungen, die Solidons Satz bei PrusaSlicer anfordern kann.
_PRUSA_ACCELERATIONS: Final = (
    "default_acceleration",
    "first_layer_acceleration",
    "travel_acceleration",
    *slicer_keys.ACCELERATION_ROLES["prusa"],
)


def _prusa_time_estimate(written: Mapping[str, str]) -> dict[str, str]:
    """Damit PrusaSlicer ohne Bündel die Zeit schätzt, die die Datei fordert (RM-191).

    Die Grenzen der Maschine kennt Solidon nicht, und in die Druckdatei gehen
    keine (``time_estimate_only``: die Firmware behält ihre). Seine
    Zeitrechnung aber nimmt sie: Mit ``ignore`` die eingebauten 1500 mm/s²
    (``GCodeProcessor``, ``MachineEnvelopeConfig``), und als Dialekt
    ``reprap`` — PrusaSlicers Vorgabe — liest sie überhaupt keine. Deshalb
    stehen die schnellste angeforderte Beschleunigung und das schnellste
    Tempo als Grenze da, und der Dialekt ist ``marlin``: Er schreibt wie
    ``reprap`` ``M204 S`` (am Gewürzregal Byte für Byte derselbe G-Code ohne
    Kommentare), das Marlin, Klipper und Bambus Firmware verstehen; Marlin 2
    schriebe ``M204 P`` ohne ``T``, das Klipper übergeht. Gemessen am
    Centauri Carbon 2 mit zwei Wänden: 334 statt 231 min geschätzt, gegen
    232 min im ElegooSlicer.
    """
    accelerations = [
        number
        for key in _PRUSA_ACCELERATIONS
        if (number := _as_float(written.get(key))) is not None and number > 0.0
    ]
    speeds = [
        number
        for entry in slicer_keys.TABLES["prusa"]
        if entry.path.startswith("speed.")
        and not entry.key.endswith("acceleration")
        and (number := _as_float(written.get(entry.key))) is not None
        and number > 0.0
    ]
    estimate = {"gcode_flavor": "marlin", "machine_limits_usage": "time_estimate_only"}
    if accelerations:
        fastest = f"{max(accelerations):g}"
        for axis in ("extruding", "travel", "x", "y"):
            # Zwei Werte: normaler und leiser Modus; geschätzt wird der erste.
            estimate[f"machine_max_acceleration_{axis}"] = f"{fastest},{fastest}"
    if speeds:
        quickest = f"{max(speeds):g}"
        for axis in ("x", "y"):
            estimate[f"machine_max_feedrate_{axis}"] = f"{quickest},{quickest}"
    return estimate


def _cura_seam(depth: float, shift: tuple[float, float]) -> dict[str, str]:
    """Wo „hinten“ liegt, wenn die Naht dorthin soll: hinten in der Mitte.

    Cura sucht den Konturpunkt, der diesem am nächsten liegt; ohne die Angabe
    stünde er bei (100, 100) und damit irgendwo. Gelesen wird er nur bei
    ``z_seam_type=back``, geschrieben immer: ein Punkt, den niemand abfragt,
    kostet nichts. Gerechnet wie Curas Formel in ``fdmprinter.def.json`` für
    ``z_seam_position = back`` — in Maschinenkoordinaten: ``shift`` ist
    Solidons Bettmitte darin (``build_area.machine_shift``), an einer Maschine
    mit Ursprung in der Ecke das halbe Bett, in der Mitte null.
    """
    x, y = shift[0], shift[1] + depth / 2.0
    return {"z_seam_x": f"{x:g}", "z_seam_y": f"{y:g}"}


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
    settings: Mapping[str, str] = field(default_factory=dict)
    """Belegte Hardwarewerte samt daran begrenzten Prozessbeschleunigungen."""
    name: str = ""
    """``machine_name`` der Definition — CuraEngine schreibt ihn als
    ``;TARGET_MACHINE.NAME`` in den Kopf (:func:`cura_machine_differences`)."""
    origin_at_centre: bool = False
    """Liegt der Ursprung dieser Maschine in der Bettmitte
    (``machine_center_is_zero``)? Dann verschiebt CuraEngine das Modell nicht,
    und die Druckdatei misst von der Mitte (:func:`off_the_bed`, RM-330)."""
    shift: tuple[float, float] | None = None
    """Wohin Solidons Bettmitte in der Druckdatei fällt, wenn eine
    Druckerdefinition die Maschine ist: ihr Ursprung, Ecke oder Mitte, gilt
    auch dann, wenn das Druckerprofil inzwischen einen anderen nennt. Ohne
    Definition ``None`` — dann gilt der des Druckers
    (``build_area.machine_shift``, RM-424)."""


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
    findings: tuple[Finding, ...] = ()
    """Belegte Abweichungen von der eigenen Wahl; ``written`` bleibt der ausgegebene Wert."""

    @property
    def filament(self) -> Path | None:
        """Das erste Filament. Für alles, was nur eines kennt."""
        return self.filaments[0] if self.filaments else None

    @property
    def origin_at_centre(self) -> bool:
        """Misst die Druckdatei dieses Laufs von der Bettmitte statt von der Ecke?

        Nur eine Cura-Maschine kann das sagen; die übrigen Familien schreiben
        ihr Bett in die Druckdatei, und die Gegenprobe nimmt dann dieses.
        """
        return self.cura_machine is not None and self.cura_machine.origin_at_centre

    @property
    def machine_shift(self) -> tuple[float, float] | None:
        """Solidons Bettmitte in der Druckdatei, wenn die Maschine des Slicers
        sie bestimmt (:attr:`CuraMachine.shift`); sonst gilt der Drucker."""
        return self.cura_machine.shift if self.cura_machine is not None else None


@dataclass(frozen=True, slots=True)
class _SlotResolution:
    """Wirksame Einstellungen und sichere Zuordnung des gebundenen Profils."""

    settings: PrintSettings
    source: Path | slicer_profiles.SlicerProfile | None = None
    readback: slicer_profiles.FilamentReadback | None = None

    @property
    def variant_unresolved(self) -> bool:
        """Ob ein gebundenes Profil wegen einer ungeklärten Variante entfällt."""
        return (
            self.source is not None
            and self.readback is not None
            and not self.readback.variant_resolved
        )


def slot_material_type(slot: MaterialSlot, setup: SlicerSetup | None) -> str:
    """Die Materialart, mit der diese Spule druckt (RM-583; Robert: „immer nach dem
    verwendeten Material“): die des gewählten Filamentprofils, sonst die der Spule.

    Eine geladene Datei bringt ihre Spulen samt Materialart mit; gibt der Kunde
    einer davon ein Profil aus PETG, druckt sie PETG, und Rat wie Spulenwerte
    folgen dem Profil, nicht der Herkunft der Datei.
    """
    if setup is not None and slot.material:
        source = profile_source(slot.material, setup, "filament")
        kind = ""
        if isinstance(source, slicer_profiles.SlicerProfile):
            kind = source.filament_type
        elif source is not None:
            values = slicer_profiles.resolve_values(source, roots=_profile_roots(setup))
            raw = values.get("filament_type")
            kind = str(raw[0] if isinstance(raw, list) and raw else raw or "")
        if kind.strip():
            return kind.strip()
    return slot.material_type or ""


def _resolve_slot(
    settings: PrintSettings,
    profile: Profile,
    slot: MaterialSlot,
    setup: SlicerSetup | None = None,
    *,
    foundation: manufacturer.Foundation | None = None,
) -> _SlotResolution:
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
    material_id = profiles.material_id_for_type(slot_material_type(slot, setup))
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
    source: Path | slicer_profiles.SlicerProfile | None = None
    readback: slicer_profiles.FilamentReadback | None = None
    if setup is not None and slot.material:
        source = profile_source(slot.material, setup, "filament")
        if source is not None:
            if foundation is None and setup.flavour == "orca":
                foundation = manufacturer.base_settings(profile, settings.quality, setup)
            readback = slicer_profiles.filament_readback(
                source,
                _profile_roots(setup),
                variant_name=foundation.variant_name if foundation is not None else "",
                extruder_id=foundation.variant_id if foundation is not None else "",
                program=manufacturer.program(setup),
                nozzle_type=foundation.nozzle_type if foundation is not None else "",
            )
            for path, value in readback.values.items():
                settings = with_path(settings, path, value)
    if (material_id and material_id != profile.material.id) or readback is not None:
        # Die Kurve der Spule folgt bei Cura derselben Regel wie die des
        # Projekts (RM-228); ohne neues Material bleibt sie aus der Grundlage.
        settings = manufacturer.cura_fan_curve(settings, profile, setup)
    override = override_for(settings, slot)
    if override is not None and not override.empty:
        settings = replace(
            settings,
            temperature=override.temperature or settings.temperature,
            cooling=override.cooling or settings.cooling,
            retraction=override.retraction or settings.retraction,
            filament=override.filament or settings.filament,
        )
    return _SlotResolution(
        settings=settings,
        source=source,
        readback=readback,
    )


def settings_for_slot(
    settings: PrintSettings,
    profile: Profile,
    slot: MaterialSlot,
    setup: SlicerSetup | None = None,
    *,
    foundation: manufacturer.Foundation | None = None,
) -> PrintSettings:
    """Die Einstellungen, mit denen dieser eine Slot fährt (§20, §29)."""
    return _resolve_slot(settings, profile, slot, setup, foundation=foundation).settings


@dataclass(frozen=True, slots=True)
class SlotProcess:
    """Womit eine Spule eines Körpers druckt (§20, §29)."""

    slot: MaterialSlot
    """Die Spule, mit dem gewählten Filamentprofil, wo eines gewählt ist."""
    profile: Profile
    """Drucker und Material dieser Spule, bezogen auf das Druckraster."""
    settings: PrintSettings
    """Die Einstellungen, mit denen diese Spule fährt (:func:`settings_for_slot`)."""


def slot_processes(
    body: SceneObject,
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    slot_profiles: Mapping[threemf.SlotKey, str],
) -> tuple[SlotProcess, ...]:
    """Jede Spule, die dieser Körper wirklich benutzt, mit Profil und Einstellungen.

    Der Rat fragt je Spule und nicht nur nach Slot 0: Ein Griff aus TPU auf
    einem Gehäuse aus PLA verlangt die langsame Außenwand, obwohl das Gehäuse
    PLA ist. ``slot_profiles`` ordnet der Identität der ungewählten Spule
    (:func:`threemf.slot_identity`) das gewählte Filamentprofil zu.

    Druckdialog und Export fragen dieselbe Funktion (Konzept Herstellerprofil,
    Entscheidung G): Solange der Export je Teil nur das Material von Slot 0
    kannte, bekam ein Teil mit einer zweiten Spule einen übernommenen
    Vorschlag nicht, den der Dialog für genau dieses Teil gezeigt hatte.
    """
    mesh = as_mesh_data(body.mesh)
    own_profile = profiles.for_object(profile, body)
    foundation: manufacturer.Foundation | None = None
    present = set(used_slots(mesh))
    processes: list[SlotProcess] = []
    for original in threemf.assembly_slots(
        threemf.AssemblyPart(mesh=mesh, slots=threemf.slots_for_object(body))
    ):
        if original.index not in present:
            continue
        chosen = slot_profiles.get(threemf.slot_identity(original), "")
        slot = replace(original, material=chosen) if chosen else original
        material = profiles.material_id_for_type(slot_material_type(slot, setup))
        material_profile = (
            replace(own_profile, material=profiles.material(material)) if material else own_profile
        )
        if foundation is None and setup is not None and setup.flavour == "orca" and slot.material:
            foundation = manufacturer.base_settings(profile, settings.quality, setup)
        effective = settings_for_slot(settings, profile, slot, setup, foundation=foundation)
        processes.append(
            SlotProcess(
                slot, profiles.for_process(material_profile, effective, effective=True), effective
            )
        )
    return tuple(processes)


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
                    "Gespeicherte Filamentwerte passen zu keinem aktuellen Material und bleiben "
                    "ungenutzt. Die Werte der Spule öffnen und übernehmen oder ersetzen."
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
                "Diese Übergabe verwendet nur das erste Filament, weitere Farben und Materialien "
                "werden nicht gedruckt. OrcaSlicer oder Bambu Studio können mehrere."
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


def bind_object_profiles(settings: PrintSettings, objects: Sequence[SceneObject]) -> PrintSettings:
    """Bindet alte Profilplätze vor dem Weglassen unbemalter Spulen.

    Die vollständige ursprüngliche Szene bestimmt die alte Reihenfolge.
    Danach folgen die Profile ihrer Filamentidentität, auch bei einer anderen
    Plattenauswahl und Werkzeugnummer. Die Eingaben bleiben unverändert.
    """
    if settings.slot_profile_bindings is not None:
        return settings
    slots = (
        threemf.merge_slots(
            [
                threemf.AssemblyPart(
                    as_mesh_data(entry.mesh), slots=threemf.slots_for_object(entry)
                )
                for entry in objects
            ],
            include_unused=True,
        )
        if settings.slot_profiles
        else ()
    )
    return bind_slot_profiles(settings, slots)


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


def chosen_slot_profiles(
    objects: Sequence[SceneObject], settings: PrintSettings
) -> dict[threemf.SlotKey, str]:
    """Welches Filamentprofil jede Spule des Auftrags bekommt, nach der Identität
    der ungewählten Spule — die Zuordnung, die :func:`slot_processes` liest.

    Über alle Körper des Auftrags zusammengelegt wie die Extruderliste der
    Datei, denn gespeicherte Profile ohne Bindung zählen nach der Stelle in
    dieser Liste (:func:`configured_slots`).
    """
    settings = bind_object_profiles(settings, objects)
    merged = threemf.merge_slots(
        [
            threemf.AssemblyPart(as_mesh_data(entry.mesh), slots=threemf.slots_for_object(entry))
            for entry in objects
        ]
    )
    return {
        threemf.slot_identity(original): configured.material
        for original, configured in zip(merged, configured_slots(merged, settings), strict=True)
        if configured.material
    }


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


#: Die Stichprobe der Grundlage bei PrusaSlicer (Entscheidung K), wie
#: :data:`FOUNDATION_SAMPLE` für die Orca-Familie.
PRUSA_FOUNDATION_SAMPLE: Final = frozenset(
    {"layer_height", "perimeters", "support_material_threshold"}
)
#: Woran die Gegenprobe sieht, dass Drucker und Startcode des Bündels
#: darunter lagen: das Modell, das die Firmware mit ``M862.3`` prüft, und der
#: Startcode selbst mit Bettvermessung und Spüllinie (Entscheidung K).
PRUSA_IDENTITY: Final = ("printer_model", "printer_settings_id", "start_gcode")


def prusa_values(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    slots: Sequence[MaterialSlot] = (),
    *,
    console: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    """Was PrusaSlicer bekommt — und was davon die Gegenprobe hält.

    **Mit Drucker und Prozess aus PrusaSlicers Bestand** (Konzept
    Herstellerprofil, Stufe C) steht die ganze Kette in der Datei, wie
    PrusaSlicer sie druckt, wenn man die drei im Fenster wählt
    (:func:`manufacturer.prusa_chain`), und darüber nur die Abweichung: die
    eigene Wahl, der übernommene Vorschlag, das Gemessene. Bis dahin bekam
    PrusaSlicer 63 Schlüssel über seinen eingebauten Vorgaben — ohne
    Bettvermessung, Spüllinie, Druckerprüfung und Pressure Advance, mit
    ``reprap`` statt ``marlin2`` und 4000 statt 500 mm/s² in der ersten Schicht.

    Technisch nötig kommt dazu: die Namen der drei Profile, damit das Fenster
    sie wiederfindet und nur Solidons Abweichung als „geändert" zeigt;
    ``support_material_auto``, sobald Solidon Stützen einschaltet, denn Prusas
    Vorgabe stützt nur an gemalten Verstärkern (Entscheidung J); der Rückzug
    auch am Filament, wo das Filament ihn sonst überstimmte; und für den
    Konsolenlauf ``binary_gcode = 0``, weil Solidon die Druckdatei als Text
    liest. Die 3MF behält das binäre Format des Herstellers.

    **Ohne Drucker des Bestands** bleibt es bei Solidons vollständigem Satz
    samt Maschine (:func:`_machine_keys`), Zeitschätzung
    (:func:`_prusa_time_estimate`) und dem, was Prusas Bündel jedem Prozess
    mitgibt (:data:`PRUSA_WITHOUT_BUNDLE`). Der Filamenttyp der Spule geht mit
    (:func:`_spool_filament_type`): Ohne ihn ging PETG als PLA hinaus
    (Prüfbericht Prusa, B11).

    **Beides nur mit Schlüsseln, die das Programm lesen kann**
    (:func:`slicer_keys.for_program`): SuperSlicer stürzte an der Schrägnaht
    aus PrusaSlicer 2.9 ab (RM-459).
    """
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    written, expected = _prusa_values(
        settings, profile, setup, slots, console=console, program=program
    )
    return (
        slicer_keys.for_program(written, "prusa", program),
        slicer_keys.for_program(expected, "prusa", program),
    )


def _prusa_values(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    slots: Sequence[MaterialSlot],
    *,
    console: bool,
    program: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """:func:`prusa_values` vor dem Filter auf die Schlüssel des Programms."""
    effective = settings_for_handover(settings, profile, "prusa", slots, setup)
    chain: manufacturer.PrusaChain | None = None
    if setup is not None:
        try:
            chain = manufacturer.prusa_chain(profile, setup)
        except ExternalToolError as problem:
            # Den Grund nennt der Befund der Grundlage (``slicer.process_unreadable``).
            _log.warning("Prusa profile unreadable, writing Solidon's table: %s", problem)
    if setup is None or chain is None:
        flat = values_for(effective, profile, "prusa", program=program)
        for key, default in slicer_keys.QUIET_AT_DEFAULT["prusa"].items():
            if flat.get(key) == default:
                del flat[key]
        flat.update(_speed_roles({}, flat, "prusa", program=program))
        flat.update(PRUSA_WITHOUT_BUNDLE)
        flat.update(_prusa_time_estimate(flat))
        flat["filament_type"] = _spool_filament_type(slots[0] if slots else None, profile, "prusa")
        return flat, flat
    foundation = manufacturer.base_settings(profile, settings.quality, setup)
    preserve_native_adhesion = effective.adhesion.kind == "auto" and foundation.has_profile
    native_kinds = native_adhesion_kinds(effective, profile, "prusa", foundation)
    effective = effective_adhesion(effective, profile, "prusa", foundation)
    paths = manufacturer.written_paths(effective, foundation) or frozenset()
    if slots:
        # Die erste Spule fährt den Satz (``settings_for_shared_slicer``), und
        # was sie ausdrücklich anders will, gehört mit hinaus.
        paths = _for_the_slot(paths, settings, slots[0], profile, setup) or paths
    if not chain.filament:
        paths |= frozenset(
            path for path in print_settings.all_paths() if manufacturer._material_path(path)
        )
    if preserve_native_adhesion:
        # Auto heißt bei einem Prusa-Prozess: seine gültige Kombination gilt.
        # Die Profilart kann zugleich Skirt und Brim führen; würde der Marker
        # ``adhesion.kind`` die drei Maße mitbringen, nullte die Ein-Art-Logik
        # diese native Kombination. Einzelne ausdrücklich gewählte Maße
        # bleiben als eigene Abweichung in ``paths``.
        paths = paths - {"adhesion.kind"}
    own = _followers_not_faster(
        {**manufacturer.prusa_defaults(program), **chain.values},
        as_mapping(effective, "prusa", paths, native_adhesion_kinds=native_kinds, program=program),
        _suggested_speed_keys(effective, "prusa"),
        followers=_PRUSA_FOLLOWERS,
    )
    own.update(_speed_roles(chain.values, own, "prusa", program=program))
    own.update(_acceleration_roles(chain.values, own, "prusa", effective))
    document = dict(chain.values)
    document.update(_with_automatic_prusa_support(dict(own)))
    for key in ("retract_length", "retract_speed", "retract_lift", "wipe"):
        if key in own:
            document[f"filament_{key}"] = own[key]
    if chain.filament:
        document["filament_settings_id"] = chain.filament
    else:
        document["filament_type"] = _spool_filament_type(
            slots[0] if slots else None, profile, "prusa"
        )
    document["printer_settings_id"] = chain.printer
    document["print_settings_id"] = chain.process
    if console:
        document["binary_gcode"] = "0"
    expected = {key: document[key] for key in own}
    for key in (*PRUSA_FOUNDATION_SAMPLE, *PRUSA_IDENTITY):
        if key in document:
            expected[key] = document[key]
    return document, expected


def _spool_filament_type(
    slot: MaterialSlot | None, profile: Profile, flavour: SlicerFlavour
) -> str:
    """Die Materialart, unter der eine Spule beim Slicer ankommt.

    Die Art der Spule, ohne Spule oder ohne Art das Material des Projekts, in
    der Schreibweise der Familie. Die Orca-Familie fragt es je Spule
    (:func:`_orca_filament`), PrusaSlicer für die erste, die seinen einen Satz
    fährt (:func:`settings_for_shared_slicer`) — deren Temperaturen und Dichte
    stehen dann schon darin.
    """
    material = slot.material_type if slot is not None and slot.material_type else ""
    return slicer_keys.filament_type(material or profile.material.id, flavour)


#: Der Schalter der Orca-Familie für die eigene Stützschichthöhe (RM-583).
_FREE_SUPPORT_LAYERS: Final = "independent_support_layer_height"


#: Wo die Orca-Familie den Stützabstand schreibt, oben und unten.
_SUPPORT_GAP_KEYS: Final = ("support_top_z_distance", "support_bottom_z_distance")


def written_support_gaps(
    plate: PrintSettings, parts: Iterable[Mapping[str, str]] = ()
) -> list[float]:
    """Die Stützabstände, die Solidon tatsächlich schreibt (RM-583): der der Platte,
    wo Solidon ihn setzt (gewählt oder übernommen), und die Objektwerte der Teile.
    Der Abstand des Herstellers steht hier nicht — ihn rundet der Slicer, wie
    der Hersteller es eingestellt hat."""
    gaps = [plate.support.z_gap] if "support.z_gap" in plate.chosen | plate.accepted else []
    for keys in parts:
        gaps += _object_gaps(keys)
    return gaps


def _object_gaps(keys: Mapping[str, str]) -> list[float]:
    """Die Stützabstände unter den Objektwerten eines Teils."""
    return [number for key in _SUPPORT_GAP_KEYS if (number := _as_float(keys.get(key))) is not None]


def support_gaps_by_style(
    plate: PrintSettings,
    parts: Sequence[tuple[Mapping[str, str], PrintSettings | None]] = (),
    organic: Collection[str] = (),
) -> tuple[list[float], list[float]]:
    """Die geschriebenen Stützabstände (:func:`written_support_gaps`), getrennt nach
    der Art, mit der jedes Teil stützt: unter organischen Bäumen (``organic``,
    :func:`organic_styles`) und sonst (RM-622).

    ``parts`` sind je Teil seine Objektwerte und die Einstellungen, mit denen es
    druckt; ohne eigenen Abstand druckt es den der Platte, ohne Teile gilt die
    Platte allein. Unter organischen Bäumen rundet jedes Programm den Abstand,
    dort hilft keine eigene Stützschichthöhe (:func:`frees_support_layers`) —
    sie wäre eine Abweichung vom Herstellerprofil ohne Wirkung."""
    common = written_support_gaps(plate)
    trees: list[float] = []
    others: list[float] = []
    for keys, effective in parts or (({}, None),):
        style = (effective or plate).support.style
        if style == "none":
            continue
        (trees if style in organic else others).extend(_object_gaps(keys) or common)
    return trees, others


def frees_support_layers(gaps: Iterable[float], layer: float, flavour: SlicerFlavour) -> bool:
    """Ob die Stütze eine eigene Schichthöhe braucht, damit diese Abstände gelten
    (RM-583).

    Ohne ``independent_support_layer_height`` rundet die Orca-Familie den
    Abstand auf ganze Schichten (``Slicing.cpp``), und Elegoos Prozesse für C2
    und CC2 schalten sie ab: Aus 0,28 mm für PETG wurden im ElegooSlicer 0,2.
    Gefragt wird nur, wenn ein geschriebener Abstand keine ganze Schicht ist
    (:func:`written_support_gaps`). Mit Reinigungsturm schaltet die
    Orca-Familie die eigene Höhe selbst wieder ab (:func:`tower_cause`).
    """
    from app.core.slice import advise

    if not slicer_keys.has_independent_support_layers(flavour) or layer <= 0.0:
        return False
    return any(not advise.in_whole_layers(gap, layer) for gap in gaps if gap > 0.0)


def _native_process(setup: SlicerSetup | None) -> Mapping[str, object]:
    """Der aufgelöste Herstellerprozess der Orca-Familie, ohne Solidons Werte.

    Eine Kette, die sich nicht auflösen lässt, sagt hier nichts: Gefragt wird
    nach Turm und Stützschichthöhe, und der Druckdialog verlor sonst seinen
    ganzen Rat (Review RM-622). Was an der Kette fehlt, meldet die Grundlage
    (``manufacturer.base_settings``).
    """
    if setup is None or setup.flavour != "orca" or not setup.base_process:
        return {}
    source = profile_file(setup.base_process, setup, "process")
    if source is None:
        return {}
    try:
        return slicer_profiles.resolve_values(source, roots=_profile_roots(setup))
    except ExternalToolError as problem:
        _log.warning("cannot resolve the process %s: %s", setup.base_process, problem.title)
        return {}


def _switched_on(value: object) -> bool:
    return str(_printed(value)).strip().casefold() in ("1", "true")


def tower_cause(
    setup: SlicerSetup | None, *, filaments: int, objects: int
) -> Literal["filaments", "process"] | None:
    """Warum der Herstellerprozess auf einer Platte einen Reinigungsturm baut.

    Mit Turm schaltet die Orca-Familie die eigene Stützschichthöhe ab und
    rundet den Stützabstand (``PrintConfig.cpp``, ``normalize_fdm_2``).
    Mehrere Filamente bauen ihn, außer „je Objekt“ mit mehreren Objekten;
    glatter Zeitraffer und Wicklungserkennung bauen ihn immer. ``None``: kein
    Turm.
    """
    native = _native_process(setup)
    if not _switched_on(native.get("enable_prime_tower", "0")):
        return None
    if str(_printed(native.get("timelapse_type", "0"))).strip() == "1" or _switched_on(
        native.get("enable_wrapping_detection", "0")
    ):
        return "process"
    by_object = str(_printed(native.get("print_sequence", ""))).strip() == "by object"
    if filaments > 1 and not (by_object and objects > 1):
        return "filaments"
    return None


#: Stile der Orca-Familie, unter denen ``tree(…)`` ein organischer Baum ist
#: (``TreeSupport.cpp``: nur ``smsTreeOrganic`` geht in den organischen Generator;
#: ``default`` heißt beim Baum organisch). ``tree_hybrid``, ``tree_slim`` und
#: ``tree_strong`` planen eigene Stützebenen (``plan_layer_heights``).
_ORGANIC_ORCA_STYLES: Final = frozenset({"", "default", "organic"})

#: Der Hybridstil der Orca-Familie: Bäume an den Details, normale Stütze unter
#: großen flachen Decken (RM-584).
_HYBRID_ORCA_STYLE: Final = "tree_hybrid"


def tree_over_hybrid(
    native: Mapping[str, object], style: str, written: Mapping[str, str]
) -> dict[str, str]:
    """Ein gewählter Baum druckt als Baum, auch über einem Hybridprozess (RM-584).

    Solidon schreibt ``support_style`` nur für Hybrid; die übrigen Arten lassen
    den Stil des Herstellers. Über einem Prozess mit ``tree_hybrid`` liest die
    Grundlage Hybrid (``manufacturer._support_style``), und wer dort Baum
    wählte, bekam ohne Stil wieder Hybrid — der Dialog zeigte, was nicht
    gedruckt wurde (Konzept Herstellerprofil, Entscheidung H). Dann geht
    ``default`` hinaus, beim Baum organisch (:data:`_ORGANIC_ORCA_STYLES`).
    Gefragt nur, wo die Stützart geschrieben wird (``support_type``)."""
    if style != "tree" or "support_type" not in written or "support_style" in written:
        return {}
    native_style = str(_printed(native.get("support_style", ""))).strip().casefold()
    return {"support_style": "default"} if native_style == _HYBRID_ORCA_STYLE else {}


def organic_styles(
    setup: SlicerSetup | None,
    profile: Profile | None = None,
    program: str = "",
    *,
    flavour: SlicerFlavour | None = None,
) -> frozenset[str]:
    """Welche Stützarten Solidons dieses Programm als organische Bäume druckt —
    die eine Auskunft für Rat, Übergabe und Befund (RM-622).

    Organische Bäume liegen auf den Schichten des Modells, auch mit
    ``independent_support_layer_height``: An zwei Körpern aus PETG schrieben
    ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print, Anycubic Slicer Next
    und PrusaSlicer 0,28 mm und druckten 0,2, ohne eine Zwischenebene; mit
    Gitter 0,28. Der Stützabstand rundet dort auf ganze Schichten, und Bambu,
    Creality, Anycubic und PrusaSlicer drucken darunter keine untere
    Trennschicht (:func:`ignored_under_trees`).

    Gefragt wird, was das Programm aus der Art macht: ``tree`` ist in der
    Orca-Familie organisch, solange der Herstellerprozess keinen anderen Baumstil
    führt; „automatisch“ ist es, wenn sein ``support_type`` ein Baum ist (Elegoo,
    Bambu). PrusaSlicer schreibt ``tree`` als ``organic``, „automatisch“ nach dem
    Stil seines Prozesses. SuperSlicer kennt keine Bäume (Ersatz Gitter), Cura
    rundet ohnehin (:data:`advise.WHOLE_LAYER_GAP_FLAVOURS`).

    **Ohne Programm gilt die Familie** (``flavour``, die der Datei): Alle
    gemessenen Programme der Orca-Familie und PrusaSlicer drucken ``tree``
    organisch, ohne Prozess bleibt „automatisch“ offen. Ein Abstand in ganzen
    Schichten gilt unter jeder Stütze genau, einer dazwischen nur mit Gitter.
    """
    family = setup.flavour if setup is not None else flavour
    if family not in ("orca", "prusa"):
        return frozenset()
    if setup is None:
        return frozenset({"tree"})
    program = program or slicer_keys.program_of(setup.executable)
    if slicer_keys.substitute("support.style", "tree", program) is not None:
        return frozenset()
    if family == "prusa":
        styles = {"tree"}
        if profile is not None and _prusa_process_style(setup, profile) == "organic":
            styles.add("auto")
        return frozenset(styles)
    native = _native_process(setup)
    style = str(_printed(native.get("support_style", ""))).strip().casefold()
    # Über einem Hybridprozess schreibt ein gewählter Baum ``default``
    # (:func:`tree_over_hybrid`), „automatisch“ bleibt Hybrid.
    if style == _HYBRID_ORCA_STYLE:
        return frozenset({"tree"})
    if style not in _ORGANIC_ORCA_STYLES:
        return frozenset()
    kind = str(_printed(native.get("support_type", ""))).strip()
    return frozenset({"tree", "auto"} if kind.startswith("tree") else {"tree"})


def tree_styles(
    setup: SlicerSetup | None,
    profile: Profile | None = None,
    program: str = "",
    *,
    flavour: SlicerFlavour | None = None,
) -> frozenset[str] | None:
    """Welche Stützarten Solidons dieses Programm als Bäume druckt (RM-584) —
    organisch, schlank, kräftig oder als Hybrid; ``None`` ohne Programm.

    Curas Antwort hängt an keinem Bestand — ``support_structure`` kennt nur
    ``tree`` und ``normal`` —, sie gilt deshalb auch ohne gefundenes Programm,
    wenn die Datei für Cura geschrieben wird (``flavour``). Sonst schlug der Rat
    dort Hybrid vor (Nachprüfung RM-584, N1).

    Der Rat fragt hier, ob „automatisch“ Bäume heißt — nur dann hängt eine
    große flache Decke darunter zwischen Baumspitzen durch, und Gitter oder
    Hybrid lohnt —, und ob die Wände der Bäume etwas drucken. Eine Art, die das
    Programm ersetzt (:data:`slicer_keys.NOT_OFFERED_BY_PROGRAM`), zählt mit
    ihrem Ersatz: Hybrid ist bei PrusaSlicer und Cura Gitter, SuperSlicer kennt
    keine Bäume. „Automatisch“ fragt den Herstellerprozess
    (:func:`manufacturer.auto_prints_trees`, wie das Zeitmodell); Cura schreibt
    dafür ``normal``, PrusaSlicer ohne Bündel seine Vorgabe ``grid``. Lässt
    sich der Prozess der Orca-Familie nicht lesen, zählt „automatisch“ als
    Baum: Ohne Auskunft bleibt der Rat vorsichtig, wie ohne Programm.
    """
    if (setup.flavour if setup is not None else flavour) == "cura":
        return frozenset({"tree"})
    if setup is None or setup.flavour not in ("orca", "prusa"):
        return None
    program = program or slicer_keys.program_of(setup.executable)
    styles = {
        style
        for style in ("tree", "hybrid")
        if slicer_keys.substitute("support.style", style, program) is None
    }
    if setup.flavour == "orca":
        native = _native_process(setup)
        if not native or manufacturer.auto_prints_trees(native, "orca"):
            styles.add("auto")
    elif setup.flavour == "prusa":
        style = _prusa_process_style(setup, profile) if profile is not None else ""
        chosen = style or manufacturer.prusa_defaults(program).get("support_material_style", "")
        if manufacturer.auto_prints_trees({"support_material_style": chosen}, "prusa"):
            styles.add("auto")
    return frozenset(styles)


def _prusa_process_style(setup: SlicerSetup, profile: Profile) -> str:
    """``support_material_style`` des gewählten Prusa-Prozesses, leer ohne Kette."""
    try:
        chain = manufacturer.prusa_chain(profile, setup)
    except ExternalToolError:
        return ""
    if chain is None:
        return ""
    return str(chain.values.get("support_material_style", "")).strip().casefold()


def ignored_under_trees(
    style: str, organic: Collection[str], program: str, *, hollow: bool = False
) -> frozenset[str]:
    """Pfade, die dieses Programm unter Bäumen nicht druckt
    (:data:`slicer_keys.IGNORED_UNDER_TREES_BY_PROGRAM`) — leer, wo die Stützart
    ``style``, mit der das Teil druckt (:func:`advise.printed_style`), keine
    organischen Bäume sind (``organic``, :func:`organic_styles`). Ein Vorschlag
    darauf änderte nichts am Druck. Druckdialog und Export fragen hier je Körper
    (RM-622). Hohle Bäume (``hollow``, :func:`hollow_trees`) bestehen aus ihren
    Wänden, und die Wandzahl wirkt (RM-584)."""
    ignored = slicer_keys.IGNORED_UNDER_TREES_BY_PROGRAM.get(program, frozenset())
    if not ignored or style not in organic:
        return frozenset()
    return ignored - {"support.tree_walls"} if hollow else ignored


#: Die Grundmuster, unter denen die Orca-Familie organische Bäume hohl druckt:
#: ``default`` heißt beim Baum hohl, ein fehlender Schlüssel ebenso.
_HOLLOW_TREE_PATTERNS: Final = frozenset({"", "default", "hollow"})


def hollow_trees(setup: SlicerSetup | None) -> bool:
    """Druckt der Herstellerprozess organische Bäume hohl, nur aus Wänden (RM-584)?

    Dann wirkt die Wandzahl auch unter organischen Bäumen. Gemessen am
    ElegooSlicer an einem Turm von 40 mm mit Insel (09.10.2026): Der Prozess
    des Neptune 4 (``support_base_pattern`` ``default``) druckte mit zwei
    Wänden 13 234 statt 12 211 Bewegungen, auch ohne eigene Stützschichthöhe.
    Derselbe Prozess mit ``rectilinear`` und der des Centauri Carbon 2
    (``rectilinear``) druckten mit einer und zwei Wänden denselben G-Code.
    Solidon schreibt das Muster nur für Gitter und Hybrid. Ohne lesbaren
    Prozess ``False``, wie am Centauri Carbon 2 gemessen.

    **Organisch bleiben sie** (:func:`organic_styles`): Am Neptune 4 druckten
    0,28 mm Abstand oben bei 0,2 mm Schicht dieselben Bewegungen wie 0,2 mm,
    0,4 mm andere — der Slicer rundet auf ganze Schichten wie unter gefüllten
    Bäumen, auch mit eigener Stützschichthöhe.
    """
    native = _native_process(setup)
    pattern = str(_printed(native.get("support_base_pattern", ""))).strip().casefold()
    return bool(native) and pattern in _HOLLOW_TREE_PATTERNS


def support_layers_findings(setup: SlicerSetup | None, free: bool) -> list[Finding]:
    """Sagt, wenn Solidon die eigene Stützschichthöhe gegen den Herstellerprozess
    einschaltet (RM-583): Die Stütze liegt dann auch auf eigenen Höhen, nicht
    nur auf denen des Modells. Wie bei der gehobenen Baumspitze erfährt der
    Kunde die Abweichung vom Herstellerprofil mit ihrem Grund."""
    if not free or setup is None:
        return []
    native = _native_process(setup)
    if _FREE_SUPPORT_LAYERS not in native or _switched_on(native[_FREE_SUPPORT_LAYERS]):
        return []
    return [
        Finding(
            code="slicer.support_layers_freed",
            severity="info",
            message=_(
                "Damit der *Abstand oben und unten* gilt, druckt {slicer} die Stütze in "
                "eigener Schichthöhe. Das Herstellerprofil hatte das abgeschaltet.",
                slicer=setup.name,
            ),
            values={"setting": _FREE_SUPPORT_LAYERS, "slicer": setup.name},
        )
    ]


def _frees_in_project(models: Sequence[Path]) -> bool | None:
    """Was die Beilage einer Solidon-3MF zur eigenen Stützschichthöhe sagt.

    Der Konsolenlauf lädt seinen Prozess über die Beilage hinweg; er muss
    dasselbe schreiben, was :func:`app.core.export.writer.write_assembly` aus
    den Werten der Teile entschieden hat. ``None``, wo keine Beilage es sagt."""
    for model in models:
        if model.suffix.casefold() != ".3mf" or not model.is_file():
            continue
        try:
            with zipfile.ZipFile(model) as container:
                if threemf.PROJECT_SETTINGS_PATH not in container.namelist():
                    continue
                embedded = json.loads(container.read(threemf.PROJECT_SETTINGS_PATH))
        except zipfile.BadZipFile, OSError, ValueError:
            # Keine lesbare Beilage: Dann sagt sie auch nichts dazu.
            continue
        if isinstance(embedded, dict) and _FREE_SUPPORT_LAYERS in embedded:
            return _switched_on(embedded[_FREE_SUPPORT_LAYERS])
    return None


def write_config(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    directory: Path,
    slots: Sequence[MaterialSlot] = (),
    *,
    free_support_layers: bool = False,
) -> SlicerConfig:
    """Schreibt die Profile, die der Slicer gleich lädt.

    ``slots`` sind die Materialslots der Platte (§20). Je Slot entsteht ein
    Filamentprofil, denn ein Slot *ist* ein Filament — zwei Farben sind zwei
    Spulen, und die fahren verschieden. Trägt ein Slot einen eigenen
    Profilnamen (``MaterialSlot.material``), wird der als Unterlage genommen;
    sonst gilt für alle das eine aus dem ``setup``. ``free_support_layers``
    sagt :func:`frees_support_layers` an den geschriebenen Abständen von Platte
    und Teilen außerhalb organischer Bäume (:func:`support_gaps_by_style`), beim
    Konsolenlauf aus der Beilage.
    """
    _refuse_untranslated(setup)
    setup = replace(setup, machine_profile=machine_for(setup, profile))
    program = slicer_keys.program_of(setup.executable)

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
        # Befehl, den niemand gesetzt hat. Die Werte des Bündels tragen ihre
        # Umbrüche maskiert (``\n``), wie PrusaSlicer selbst sie schreibt.
        flat, expected = prusa_values(settings, profile, setup, slots, console=True)
        _without_line_break(flat, setup.name)
        lines = [f"# {_one_line(settings.title)} — von Solidon geschrieben, nicht von Hand"]
        lines += [f"{key} = {value}" for key, value in sorted(flat.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SlicerConfig(process=target, written=expected)

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
        split = by_section(settings, setup.flavour, program=program)
        deviating = by_section(settings, setup.flavour, paths, program=program)
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
            foundation=foundation,
            nozzle=profile.printer.nozzle_diameter,
        )
        if free_support_layers:
            process_document[_FREE_SUPPORT_LAYERS] = "1"
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
            # Je Slot seine eigenen Werte: Temperaturen, Kühlung,
            # Rückzug und Materialkennwerte dürfen sich unterscheiden,
            # denn sie hängen an der Spule. Was der Slot nicht setzt,
            # kommt aus dem Projekt — deshalb wird die Aufteilung hier
            # noch einmal gerechnet und nicht die von oben genommen.
            resolution = _resolve_slot(settings, profile, slot, setup, foundation=foundation)
            mine = resolution.settings
            own = (
                replace(setup, base_filament="")
                if resolution.variant_unresolved
                else replace(setup, base_filament=slot.material)
                if slot.material
                else setup
            )
            part = split if mine is settings else by_section(mine, setup.flavour, program=program)
            own_paths = _for_the_slot(
                paths,
                settings,
                slot,
                profile,
                setup,
                foundation=foundation,
                resolution=resolution,
            )
            filament_documents.append(
                _orca_filament(
                    part.get("filament", {}),
                    mine,
                    profile,
                    own,
                    slot,
                    deviating=by_section(mine, setup.flavour, own_paths, program=program).get(
                        "filament", {}
                    ),
                    plate=plate or None,
                    chamber_control=foundation.chamber_control,
                    nozzle_type=foundation.nozzle_type,
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
        expected = {}
        for key, value in process_document.items():
            if key not in own_process and key not in FOUNDATION_SAMPLE:
                continue
            printed_value = _printed_variant(
                value,
                process_document,
                "print_extruder_variant",
                "print_extruder_id",
                foundation,
            )
            if printed_value is not None:
                expected[key] = printed_value
        if plate:
            expected["curr_bed_type"] = plate
        if "enable_support" in own_process or "raft_layers" in own_process:
            # Mit den Stützen geprüft: die Baumspitze, die Solidon gehoben hat.
            for key in (ORGANIC_TIP, ORGANIC_BRANCH):
                if key in process_document:
                    expected[key] = _printed(process_document[key])
        firmware = machine_document.get("gcode_flavor")
        if isinstance(firmware, str):
            expected["gcode_flavor"] = firmware
        filament_keys = {
            slicer_keys.native_key(entry.key, program)
            for entry in slicer_keys.TABLES[setup.flavour]
            if entry.section == "filament"
        }
        filament_keys.add("activate_chamber_temp_control")
        for key in sorted(filament_keys):
            if not all(key in document for document in filament_documents):
                continue
            # Ein Wert je Spule, wie der G-Code sie führt. Die Filamentwerte
            # des Herstellers bleiben ganz in der Gegenprobe: an ElegooSlicer,
            # Bambu Studio, Creality Print und OrcaSlicer kam jeder an.
            printed_values = [
                _printed_variant(
                    document[key],
                    document,
                    "filament_extruder_variant",
                    "filament_extruder_id",
                    foundation,
                )
                for document in filament_documents
            ]
            if all(value is not None for value in printed_values):
                expected[key] = ",".join(value for value in printed_values if value is not None)
        # Eine eigene Betttemperatur steht unter dem Schlüssel der aufliegenden
        # Platte (``_on_the_plate``), nicht unter ``hot_plate_temp`` — geprüft
        # wird sie dort (Review Stufe A+B, H3).
        bed_key = manufacturer.PLATE_TEMPERATURES.get(plate) if plate else None
        if bed_key is not None:
            for key in (bed_key, f"{bed_key}_initial_layer"):
                if all(key in document for document in filament_documents):
                    plate_values = [
                        _printed_variant(
                            document[key],
                            document,
                            "filament_extruder_variant",
                            "filament_extruder_id",
                            foundation,
                        )
                        for document in filament_documents
                    ]
                    if all(value is not None for value in plate_values):
                        expected[key] = ",".join(
                            value for value in plate_values if value is not None
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
    limited = _cura_limit_findings(flat, machine.settings, paths=settings.explicit)
    flat |= machine.settings
    if machine.from_printer:
        # Die Druckerdefinition ist die Maschine (RM-330): Ihr Ursprung gilt,
        # Ecke oder Mitte, und ein Versatz für einen anderen entfällt.
        width, depth, _height = profile.printer.build_volume
        for key in ("mesh_position_x", "mesh_position_y"):
            flat.pop(key, None)
        corner = (width / 2.0, depth / 2.0)
        flat |= _cura_seam(depth, (0.0, 0.0) if machine.origin_at_centre else corner)
    flat |= machine.switches
    _without_line_break(flat, setup.name)
    target.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(flat.items())) + "\n",
        encoding="utf-8",
    )
    return SlicerConfig(process=target, written=flat, cura_machine=machine, findings=tuple(limited))


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
    *,
    free_support_layers: bool = False,
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

    program = slicer_keys.program_of(setup.executable)
    split = by_section(settings, setup.flavour, program=program)
    # Dieselbe Grundlage wie im Konsolenlauf (:func:`write_config`): auf dem
    # Herstellerprofil nur die Abweichung, dazu die Druckplatte.
    foundation = manufacturer.base_settings(profile, settings.quality, setup)
    paths = _deviating(settings, foundation)
    deviating = by_section(settings, setup.flavour, paths, program=program)
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
            foundation=foundation,
            nozzle=profile.printer.nozzle_diameter,
        )
    )
    if free_support_layers:
        document[_FREE_SUPPORT_LAYERS] = "1"
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
        resolution = (
            None
            if slot is None
            else _resolve_slot(settings, profile, slot, setup, foundation=foundation)
        )
        mine = settings if resolution is None else resolution.settings
        own = (
            replace(setup, base_filament="")
            if resolution is not None and resolution.variant_unresolved
            else replace(setup, base_filament=slot.material)
            if slot is not None and slot.material
            else setup
        )
        slot_values = by_section(mine, setup.flavour, program=program).get("filament", {})
        slot_paths = (
            paths
            if slot is None
            else _for_the_slot(
                paths,
                settings,
                slot,
                profile,
                setup,
                foundation=foundation,
                resolution=resolution,
            )
        )
        filament_documents.append(
            _orca_filament(
                slot_values,
                mine,
                profile,
                own,
                slot,
                deviating=by_section(mine, setup.flavour, slot_paths, program=program).get(
                    "filament", {}
                ),
                plate=plate or None,
                chamber_control=foundation.chamber_control,
                nozzle_type=foundation.nozzle_type,
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

    def project_value(key: str, value: object, entry: Mapping[str, Any]) -> object | None:
        """Löst nur ausdrücklich variantengebundene Werte je Profil auf."""
        if key not in BAMBU_FILAMENT_VARIANT_SETTINGS:
            return value
        variants = manufacturer._variant_entries(entry.get("filament_extruder_variant"))
        if (
            isinstance(value, list)
            and len(value) > 1
            and (variants is None or len(value) != len(variants))
        ):
            return value
        return _printed_variant(
            value,
            entry,
            "filament_extruder_variant",
            "filament_extruder_id",
            foundation,
        )

    resolved: dict[str, object] = dict(document)
    for key in filament_keys:
        filament_values = [entry.get(key, "") for entry in filament_documents]
        vectors = [
            value for value in filament_values if isinstance(value, list) and len(value) != 1
        ]
        if vectors:
            # Variantengebundene Werte werden anhand des jeweiligen Profils
            # je Slot auf die aktive Variante abgebildet. Andere Profilvektoren
            # bleiben vollständig; verschiedene Vektoren kann das Projektformat
            # nicht je Slot ausdrücken.
            resolved_values = [
                project_value(key, value, entry)
                for entry, value in zip(filament_documents, filament_values, strict=True)
            ]
            if any(value is None for value in resolved_values):
                _log.warning("not writing unresolved multi-value filament key %s", key)
                continue
            projected_values = [value for value in resolved_values if value is not None]
            projected_vectors = [
                value for value in projected_values if isinstance(value, list) and len(value) != 1
            ]
            if projected_vectors:
                stated = [value for value in projected_values if value not in ("", [])]
                if not stated:
                    resolved[key] = []
                elif all(value == stated[0] for value in stated):
                    resolved[key] = stated[0]
                else:
                    _log.warning("not writing incompatible multi-value filament key %s", key)
            else:
                resolved[key] = projected_values
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
        resolved["printer_settings_id"] = _source_profile_name(
            setup.machine_profile, setup, "machine"
        )
    resolved["print_settings_id"] = f"Solidon {settings.title}"
    resolved["filament_settings_id"] = [
        str(entry.get("name", f"Solidon {settings.title}")) for entry in filament_documents
    ]
    resolved.setdefault("printer_model", profile.printer.title)
    resolved.setdefault("nozzle_diameter", [str(profile.printer.nozzle_diameter)])
    # Das Fenster warnt sonst beim Öffnen: „Invalid values found in the 3MF“.
    return _within_console_limits(resolved, program)


def _within_console_limits(document: dict[str, object], program: str) -> dict[str, object]:
    """Ein Herstellerwert, den die Konsole ablehnt, geht als Vorgabe des Programms hinaus.

    Sonst schneidet die Konsole gar nichts: OrcaSlicer am Kobra S1 Max bricht
    an Anycubics ``retraction_distances_when_cut = 0`` und
    ``filament_flush_temp = nil`` ab, mit und ohne Stützen
    (``slicer_keys.CONSOLE_LIMITS``). Der Befund dazu steht an der Grundlage
    (``slicer.profile_value_replaced``).
    """
    for key, (_old, new) in slicer_keys.console_replacements(document, program).items():
        document[key] = new
    return document


def window_findings(setup: SlicerSetup) -> list[Finding]:
    """Was das Fenster dieses Slicers beim Öffnen der Übergabe fragt und selbst nimmt.

    Creality Print öffnet eine 3MF, die es nicht selbst schrieb, mit der
    Frage nach dem Drucker, vorgewählt ist der dort eingestellte
    (``ChoosePresetDlg``, Quelltext Creality Print). Prozess und Filament
    nimmt es aus dem Bestand dieses Druckers, nicht aus der Datei. Gemessen
    am 29.09.2026 mit 7.2.2 und 7.3.0: Nach dem Schneiden im Fenster stand in
    ``full_print_config.json`` der ganze Prozess des gewählten Druckers, vier
    gewählte Wände und 37 % Füllung kamen nicht an, auch nicht mit
    ``different_settings_to_system``, das ``Check3mfVendor::get3mfConfig``
    liest (RM-164). Mit Solidons Einstellungen rechnet *Slicen*.
    """
    if not _is_creality_print(setup):
        return []
    printer = (
        _source_profile_name(setup.machine_profile, setup, "machine")
        if setup.machine_profile
        else ""
    )
    message = (
        _(
            "{slicer} fragt beim Öffnen nach dem Drucker. Wählen Sie dort „{printer}“. "
            "Die Druckeinstellungen nimmt es aus seinen eigenen Profilen; mit Solidons "
            "Einstellungen rechnet „Slicen“.",
            slicer=setup.name,
            printer=printer,
        )
        if printer
        else _(
            "{slicer} fragt beim Öffnen nach dem Drucker. Wählen Sie dort Ihren Drucker. "
            "Die Druckeinstellungen nimmt es aus seinen eigenen Profilen; mit Solidons "
            "Einstellungen rechnet „Slicen“.",
            slicer=setup.name,
        )
    )
    return [
        Finding(
            code="slicer.window_asks_for_the_printer",
            severity="info",
            message=message,
            values={"slicer": setup.name, "printer": printer},
        )
    ]


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


def _source_profile_name(
    reference: str, setup: SlicerSetup, kind: slicer_profiles.ProfileKind
) -> str:
    """Die Kennung bleibt eindeutig; die Datei liefert den Namen für den Slicer."""
    source = profile_source(reference, setup, kind)
    if isinstance(source, slicer_profiles.SlicerProfile):
        return source.name
    if source is not None:
        profile = slicer_profiles._read(source, kind, False)
        if profile is not None:
            return profile.name
    # Auch ohne lesbare Quelle bleibt höchstens ein Name, nie der Rechnerpfad.
    return _profile_name(reference)


def _machine_name(setup: SlicerSetup) -> str:
    """Der Name, unter dem Solidons eigenes Maschinenprofil läuft.

    An einer Stelle festgelegt, weil zwei Dateien ihn brauchen: Das
    Maschinenprofil trägt ihn als ``name``, das Prozessprofil daneben als
    ``compatible_printers``. Gehen die beiden auseinander, nimmt der Slicer
    den Auftrag nicht an, und die Meldung nennt den Drucker — nicht die
    Ursache.
    """
    printer = (
        _source_profile_name(setup.machine_profile, setup, "machine")
        if setup.machine_profile
        else ""
    )
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
    return _within_console_limits(document, slicer_keys.program_of(setup.executable))


#: Schlüssel, die ein Solidon-Feld nur mitbedient, weil Solidon sie nicht eigens
#: führt: die Lückenfüllung mit der Innenwand, die innere Vollfüllung mit der
#: Füllung (``slicer_keys``). Solidons eigener Satz braucht für sie einen Wert;
#: über einem Herstellerprozess hat der Hersteller sie eigens abgestimmt.
_ORCA_FOLLOWERS: Final = frozenset({"gap_infill_speed", "internal_solid_infill_speed"})
#: Dieselben zwei bei PrusaSlicer: Lückenfüllung und volle Füllung.
_PRUSA_FOLLOWERS: Final = frozenset({"gap_fill_speed", "solid_infill_speed"})


#: Rollen, die ein Herstellerprozess mit eigenem Tempo über ein Solidon-Tempo
#: legt: je Schlüssel der Rolle das Tempo, das sie überschreibt, und das Tempo,
#: auf das sich eine Prozentangabe bezieht. Kleine Umfänge (Bohrungen, Stiele)
#: fuhren sonst schneller als eine gebremste Außenwand (RM-463).
_ORCA_ROLES: Final = {"small_perimeter_speed": ("outer_wall_speed", "outer_wall_speed")}
_PRUSA_ROLES: Final = {"small_perimeter_speed": ("external_perimeter_speed", "perimeter_speed")}


def _speed_roles(
    base: Mapping[str, object],
    own: Mapping[str, str],
    flavour: SlicerFlavour,
    *,
    program: str = "",
) -> dict[str, str]:
    """Kleine Schleifen folgen auch je Teil den gewählten Wandtempi.

    Prusas Kleinperimeterrolle überlagert Außen- und Innenwände. Sind beide
    gewählt, gilt das kleinere Tempo; die Rolle wird nie schneller gemacht.
    Prozentwerte beziehen sich weiterhin auf das innere Wandtempo.

    Fehlt die Rolle im geschriebenen Prusa-Satz, gilt die gemessene Vorgabe
    des Programms. Ohne belegte Programmmarke müssen beide Familienmitglieder
    die Obergrenze halten, ohne die langsamere Vorgabe zu beschleunigen.
    """
    roles = _ORCA_ROLES if flavour == "orca" else _PRUSA_ROLES if flavour == "prusa" else {}
    if flavour == "prusa" and "perimeter_speed" in own:
        leaders = (key for key in ("external_perimeter_speed", "perimeter_speed") if key in own)
        leader = min(leaders, key=lambda key: _as_float(own[key]) or float("inf"))
        roles = {"small_perimeter_speed": (leader, "perimeter_speed")}
    alternatives: Sequence[Mapping[str, object]] = ()
    if flavour == "prusa" and "small_perimeter_speed" not in base:
        programs = (
            (program,)
            if program in {"prusaslicer", "superslicer"}
            else ("prusaslicer", "superslicer")
        )
        candidates = [{**manufacturer.prusa_defaults(entry), **base} for entry in programs]
        base, *alternatives = candidates
    return _roles_not_faster(base, own, roles, alternatives=alternatives)


def _roles_not_faster(
    base: Mapping[str, object],
    own: Mapping[str, str],
    roles: Mapping[str, tuple[str, str]],
    *,
    alternatives: Sequence[Mapping[str, object]] = (),
) -> dict[str, str]:
    """Eine Rolle mit eigenem Tempo fährt nie schneller als das Tempo, das Solidon schreibt.

    Gemessen in PrusaSlicer 2.9.6 an der MK4S (G-Code-Prüfung 02.10.2026):
    Solidon schrieb die Außenwand mit 160 mm/s, der Stiel lief mit 170, denn
    das Herstellerbündel führt ``small_perimeter_speed = 170`` absolut. Seit
    0.5.1 die Herstellergrundlage trägt, galt das für jedes Bündel mit
    absolutem Wert; in 0.5.0 lief die Außenwand nie schneller als gewählt.
    Gedeckelt wird nur, wo Solidon das Leittempo schreibt; schneller wird
    keine Rolle.
    """
    capped: dict[str, str] = {}
    for key, (leader, reference) in roles.items():
        if leader not in own or key in own:
            continue
        limit = _as_float(own[leader])
        speeds = []
        for source in (base, *alternatives):
            written = _printed(source.get(key, "")).strip()
            if written.endswith("%"):
                share = _as_float(written[:-1])
                basis = _as_float(own.get(reference) or _printed(source.get(reference, "")))
                speed = share / 100.0 * basis if share is not None and basis is not None else None
            else:
                speed = _as_float(written)
            if speed is not None:
                speeds.append(speed)
        if limit is not None and any(speed > limit for speed in speeds):
            capped[key] = f"{min(limit, *speeds):g}"
    return capped


def _acceleration_roles(
    base: Mapping[str, object],
    own: Mapping[str, str],
    flavour: SlicerFlavour,
    settings: PrintSettings,
    foundation: manufacturer.Foundation | None = None,
) -> dict[str, str]:
    """Eine kleinere Grundbeschleunigung erreicht auch geerbte Druckrollen.

    Eigene Außenwandwerte und langsamere Herstellerrollen bleiben erhalten.
    Erste Schicht und Leerfahrt besitzen unabhängige Vorgaben. Ein Prozentwert
    bezieht sich bereits auf die neue Grundbeschleunigung.
    """
    keys = slicer_keys.ACCELERATION_ROLES[flavour]
    if "speed.outer_wall_acceleration" in settings.explicit:
        keys = tuple(
            key
            for key in keys
            if key not in {"external_perimeter_acceleration", "outer_wall_acceleration"}
        )
    source: Mapping[str, object] = base
    if foundation is not None:
        source = {
            key: _printed_variant(
                value, base, "print_extruder_variant", "print_extruder_id", foundation
            )
            for key, value in base.items()
        }
    return _roles_not_faster(
        source, own, dict.fromkeys(keys, ("default_acceleration", "default_acceleration"))
    )


def _followers_not_faster(
    base: Mapping[str, object],
    deviating: Mapping[str, str],
    suggested: frozenset[str] = frozenset(),
    followers: frozenset[str] = _ORCA_FOLLOWERS,
    *,
    foundation: manufacturer.Foundation | None = None,
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
    for key in (followers | suggested) & kept.keys():
        printed = (
            _printed_variant(
                base.get(key, ""),
                base,
                "print_extruder_variant",
                "print_extruder_id",
                foundation,
            )
            if foundation is not None
            else _printed(base.get(key, ""))
        )
        vendor = _as_float(printed) if printed is not None else None
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


#: Die Schlüssel der organischen Bäume, die :func:`organic_tree_fitted` hebt.
ORGANIC_TIP: Final = "tree_support_tip_diameter"
ORGANIC_BRANCH: Final = "tree_support_branch_diameter_organic"


def organic_tree_fitted(values: Mapping[str, object], nozzle: float) -> dict[str, str]:
    """Baumspitze und Ast, so weit gehoben, dass die Orca-Familie stützt.

    Wo gestützt wird (``enable_support`` oder ein Raft) und die Stütze ein
    organischer Baum ist (``tree(…)`` mit Stil ``default`` oder ``organic``),
    verweigert jedes Orca-Programm den Schnitt, sobald die Spitze schmaler ist
    als die Stützbahn oder der Ast schmaler als zwei Bahnen oder die Spitze
    (``Print.cpp``, ``Print::validate``). Anycubic und OrcaSlicer liefern das
    für dreizehn bzw. sechs Prozesse an 0,8er-Düsen so aus — Kobra S1 Max 0,8:
    Spitze 0,8 mm, Stützbahn 0,82 mm (Anycubic-Matrix, B4). Die Bahn ist
    ``support_line_width``, ohne sie ``line_width``, ohne beide die Düse
    (``Flow.cpp``); Prozente beziehen sich auf die Düse. Ohne Schlüssel gelten
    Orcas Vorgaben (Spitze 0,8 mm, Ast 2 mm, Stütze ``normal(auto)``).
    """

    def text(key: str, default: str) -> str:
        value = values.get(key)
        return (_printed(value) if value is not None else default).strip().strip('"')

    supported = text("enable_support", "0") == "1" or (_as_float(text("raft_layers", "0")) or 0) > 0
    style = text("support_style", "default") or "default"
    if not supported or not text("support_type", "normal(auto)").startswith("tree"):
        return {}
    if style not in ("default", "organic") or nozzle <= 0.0:
        return {}
    width = nozzle
    for key in ("support_line_width", "line_width"):
        raw = text(key, "0")
        number = _as_float(raw.removesuffix("%"))
        if number is not None and number > 0.0:
            width = number * nozzle / 100.0 if raw.endswith("%") else number
            break
    tip = _as_float(text(ORGANIC_TIP, "0.8"))
    branch = _as_float(text(ORGANIC_BRANCH, "2"))
    if tip is None or branch is None:
        return {}
    fitted: dict[str, str] = {}
    if tip < width - EPS_GEOM:
        tip = width
        fitted[ORGANIC_TIP] = f"{width:g}"
    if branch < max(2.0 * width, tip) - EPS_GEOM:
        fitted[ORGANIC_BRANCH] = f"{max(2.0 * width, tip):g}"
    return fitted


def widened_tree_findings(
    keys: Mapping[str, object], object_id: ObjectId | None = None
) -> list[Finding]:
    """Sagt, wo Solidon die Baumspitze gehoben hat (:func:`organic_tree_fitted`).

    Eine Abweichung vom Herstellerprofil braucht einen Grund, und der Kunde
    erfährt ihn — an der Platte oder am Teil, das die Stütze einschaltet.
    """
    value = keys.get(ORGANIC_TIP)
    width = _as_float(_printed(value)) if value is not None else None
    if width is None:
        return []
    return [
        Finding(
            code="slicer.tree_tip_widened",
            severity="info",
            message=_(
                "Die Baumspitze im Profil ist schmaler als die Stützbahn, das lehnt der Slicer "
                "ab. Solidon setzt sie auf {value}.",
                value=format_length(width),
            ),
            values={"setting": ORGANIC_TIP, "value": _printed(value)},
            object_id=object_id,
        )
    ]


def plate_tree_findings(
    settings: PrintSettings, profile: Profile, setup: SlicerSetup | None
) -> list[Finding]:
    """Ob die Platte ihre Baumspitze gehoben bekommt — dieselbe Frage wie im
    Prozessprofil (:func:`_orca_process`), am Herstellerprozess samt Abweichung."""
    if setup is None or setup.flavour != "orca":
        return []
    if settings.support.style == "none" and "raft" not in print_settings.adhesion_kinds(
        settings.adhesion.kind
    ):
        # Ohne Stütze und Raft prüft der Slicer keine Bäume — und die Grundlage
        # kostet je Export eine Zehntelsekunde.
        return []
    foundation = manufacturer.base_settings(profile, settings.quality, setup)
    program = slicer_keys.program_of(setup.executable)
    values = _part_native_values(settings, profile, setup, foundation, "orca") or as_mapping(
        settings, "orca", program=program
    )
    return widened_tree_findings(organic_tree_fitted(values, profile.printer.nozzle_diameter))


def _orca_process(
    values: dict[str, str],
    settings: PrintSettings,
    setup: SlicerSetup,
    *,
    deviating: Mapping[str, str] | None = None,
    plate: str = "",
    suggested: frozenset[str] = frozenset(),
    foundation: manufacturer.Foundation | None = None,
    nozzle: float = 0.0,
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
    own = (
        values
        if base is None or deviating is None
        else _followers_not_faster(document, deviating, suggested, foundation=foundation)
    )
    if "brim_object_gap" in own:
        own = dict(own)
        foot = foundation.brim_foot_offset if foundation is not None else None
        if "brim" not in print_settings.adhesion_kinds(settings.adhesion.kind):
            own.pop("brim_object_gap")
        elif foot is not None or "adhesion.brim_gap" in settings.explicit:
            own["brim_object_gap"] = manufacturer.native_brim_gap(
                settings.adhesion.brim_gap, foot, slicer_keys.program_of(setup.executable)
            )
        else:
            # Ohne eigene Wahl bleibt der native Abstand unberührt, auch wenn
            # eine fehlende Fußkorrektur seine Rücklesung verhindert.
            own.pop("brim_object_gap")
    document.update(own)
    document.update(tree_over_hybrid(document, settings.support.style, own))
    if base is not None:
        document.update(_speed_roles(document, own, "orca"))
        document.update(_acceleration_roles(document, own, "orca", settings, foundation))
    # Stützt die Platte mit organischen Bäumen, deren Spitze das Profil schmaler
    # nennt als die Stützbahn, sagte der Slicer ab — gehoben wird auf die Bahn.
    document.update(organic_tree_fitted(document, nozzle))
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
    return _within_console_limits(document, slicer_keys.program_of(setup.executable))


def _orca_filament(
    values: dict[str, str],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slot: MaterialSlot | None = None,
    *,
    deviating: Mapping[str, str] | None = None,
    plate: str | None = None,
    chamber_control: bool | None = None,
    nozzle_type: str = "",
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
        and slicer_keys.normalise_filament_type(slot.material_type)
        != slicer_keys.filament_type(profile.material.id)
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
        "filament_type": [_spool_filament_type(slot, profile, "orca")],
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
    program = manufacturer.program(setup)
    inherited: dict[str, object] = {}
    if base is not None:
        inherited = slicer_keys.normalise_chamber(
            slicer_profiles.resolve_values(base, roots=_profile_roots(setup)), program
        )
        # Der Grundwert ist, was an dieser Düse gedruckt wird: Anycubic Slicer
        # Next ersetzt ihn beim Schneiden durch die Düsenart-Fassung.
        inherited = slicer_keys.for_the_nozzle(inherited, program, nozzle_type)
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
            slicer_keys.native_key(orca, program)
            for solidon, orca, _kind in slicer_profiles.FILAMENT_READBACK
            if slicer_keys.native_key(orca, program) in inherited
            and (override is None or getattr(override, solidon.partition(".")[0]) is None)
        }
        own_values = {
            key: value for key, value in own_values.items() if key not in from_the_material
        }
    document.update(own_values)
    if program == "bambustudio":
        document.pop("activate_chamber_temp_control", None)
    else:
        temperatures = document.get("chamber_temperature")
        if isinstance(temperatures, list) and (
            "chamber_temperature" in own_values
            or "activate_chamber_temp_control" not in document
            or chamber_control is not True
        ):
            document["activate_chamber_temp_control"] = [
                "1" if chamber_control is True and (_as_float(str(value)) or 0.0) > 0.0 else "0"
                for value in temperatures
            ]
    # Die ausdrücklich gewählte Spule gewinnt zuletzt. Eine lokale PLA-Spule
    # hat einen Typ, aber kein eigenes Herstellerprofil. Ein geerbter
    # ``filament_type`` darf die sichtbare Wahl nicht überschreiben.
    if slot is not None and slot.material_type:
        document["filament_type"] = [_spool_filament_type(slot, profile, "orca")]
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
    # Ein eigener Wert geht in jede Düsenart-Fassung — sonst druckt der
    # Slicer die Fassung des Herstellers statt der Wahl.
    document.update(slicer_keys.with_nozzle_kinds(document, program, own_values))
    _within_console_limits(document, program)
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

    Für einfache Listen nimmt der Slicer den ersten Eintrag. Bambu-Listen, die
    parallel zu den Düsenvarianten stehen, gehen über :func:`_printed_variant`.
    """
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _printed_variant(
    value: object,
    document: Mapping[str, Any],
    variant_key: str,
    extruder_key: str,
    foundation: manufacturer.Foundation,
) -> str | None:
    """Prüft eine Liste anhand der Variantenliste ihres eigenen Profils."""
    variants = manufacturer._variant_entries(document.get(variant_key))
    if variants is None:
        return _printed(value)
    position = manufacturer._variant_index(
        document,
        variant_key,
        extruder_key,
        foundation.variant_name,
        foundation.variant_id,
    )
    if position is None:
        return None if isinstance(value, list) else _printed(value)
    index, count = position
    if isinstance(value, list) and len(value) == count:
        return str(value[index])
    return _printed(value)


def _deviating(
    settings: PrintSettings, foundation: manufacturer.Foundation
) -> frozenset[str] | None:
    """Was vom Herstellerprofil abweichen soll — ``None`` heißt alles."""
    return manufacturer.written_paths(settings, foundation)


def _for_the_slot(
    paths: frozenset[str] | None,
    settings: PrintSettings,
    slot: MaterialSlot,
    profile: Profile | None = None,
    setup: SlicerSetup | None = None,
    *,
    foundation: manufacturer.Foundation | None = None,
    resolution: _SlotResolution | None = None,
) -> frozenset[str] | None:
    """Die Abweichungen eines Slots: die des Projekts und was seine Spule
    ausdrücklich anders will als ihre Grundlage — das gehört ihr, nicht dem
    Hersteller (§20).

    Übersteuert wird gruppenweise (:class:`SlotOverride`), vorbelegt mit den
    Werten, die ohne die Übersteuerung gälten. Geschrieben wird nur, was davon
    abweicht: Wer an einer Spule die Düsentemperatur ändert, schreibt nicht
    Bett, erste Schicht und Kammer mit über das Herstellerfilament (Review
    Stufe A+B, H15). Ohne Drucker zum Vergleich bleibt es bei der ganzen Gruppe.
    """
    if profile is not None and resolution is None:
        resolution = _resolve_slot(settings, profile, slot, setup, foundation=foundation)
    if resolution is not None and resolution.variant_unresolved:
        # Ohne sichere Zuordnung darf das gebundene Profil keine Werte erben;
        # die Projektgrundlage wird vollständig in das Ausgabefilament geschrieben.
        return None
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
    candidates = frozenset(
        path for path in print_settings.all_paths() if path.partition(".")[0] in groups
    )
    if profile is None:
        return paths | candidates
    without = replace(
        settings,
        slot_overrides=tuple(entry for entry in settings.slot_overrides if entry is not override),
    )
    base = _resolve_slot(without, profile, slot, setup, foundation=foundation).settings
    mine = (
        resolution.settings
        if resolution is not None
        else _resolve_slot(settings, profile, slot, setup, foundation=foundation).settings
    )
    return paths | frozenset(
        path
        for path in candidates
        if not print_settings.same_value(read_path(mine, path), read_path(base, path))
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
    limited = slicer_keys.LIMITED[flavour]
    findings = []
    for path in sorted(slicer_keys.NOT_TAKEN_BY[flavour] | limited):
        message = slicer_keys.limitation(flavour, path, settings)
        if message is None:
            continue
        # Was je nach Wert angenähert ankommt, ändert der Kunde am Feld; was
        # nie ankommt, nur im Profil seines Slicers (RM-583).
        findings.append(
            Finding(
                code="slicer.setting_not_transferred",
                severity="warning",
                message=message,
                values={"path": path, "field": path} if path in limited else {"path": path},
                suggestions=(OPEN_PRINT_SETTINGS,) if path in limited else (CHECK_SLICER_PROFILE,),
            )
        )
    return findings


def substituted_choices(settings: PrintSettings, program: str) -> list[Finding]:
    """Wahlen, die dieses Programm nicht kennt und als Ersatz bekommt (RM-480).

    :func:`offered_settings` schreibt den Ersatz; hier steht, dass es einer
    ist — vor dem Öffnen wie nach dem Slicen, denn die Druckdatei bestätigt
    den Ersatz, nicht die Wahl.
    """
    return [
        Finding(
            code="slicer.choice_substituted",
            severity="warning",
            message=replaced.reason,
            values={"path": path},
            suggestions=(OPEN_PRINT_SETTINGS, CHOOSE_SLICER),
        )
        for path, table in slicer_keys.NOT_OFFERED_BY_PROGRAM.get(program, {}).items()
        if (replaced := table.get(read_path(settings, path))) is not None
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
        if not _same(
            str(value),
            ours,
            unescape_gcode_quotes=key.casefold().endswith("_gcode"),
        ):
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


#: Das Programm, mit dem ein Slicer als Flatpak auf der Kommandozeile rechnet,
#: je Familie in der Reihenfolge der Suche, relativ zu seinem ``/app``.
_FLATPAK_CLI: Final[dict[SlicerFlavour, tuple[str, ...]]] = {
    "prusa": ("bin/prusa-slicer",),
}


def _cli_program(setup: SlicerSetup) -> list[str]:
    """Womit der Slicer auf der Kommandozeile rechnet: gewöhnlich die
    Programmdatei selbst.

    **Ein Slicer als Flatpak rechnet nicht immer über seinen Starter.** Das
    Startskript von PrusaSlicer auf Flathub ruft das Programm im Hintergrund auf
    und kehrt sofort zurück (``exec /app/bin/prusa-slicer "$@" &``) — Solidon
    wartete auf nichts, und es entstand keine Druckdatei. Der Aufruf geht deshalb
    mit ``--command`` an das Programm im Paket. Orca und Bambu Studio rufen im
    Vordergrund auf und behalten ihren Starter samt dessen Umgebung
    (``LC_NUMERIC=C``). Gemessen am Runner mit den Flathub-Paketen (RM-064).

    **Cura bleibt hier beim Starter**, der nur das Fenster öffnet: Sein Paket ist
    ein AppImage aus appimage-builder, und CuraEngine nennt seinen Lader relativ
    (``lib64/ld-linux-x86-64.so.2``). Ein Aufruf mit ``--command`` auf
    CuraEngine scheiterte am Runner mit „required file not found“; gerechnet
    wird über den Lader, den :func:`cura_linux.engine` für die Dauer des Laufs
    bereitstellt.
    """
    app = discover.flatpak_app(setup.executable)
    inner = _FLATPAK_CLI.get(setup.flavour, ())
    if not app or not inner:
        return [str(setup.executable)]
    files = discover.flatpak_files(app)
    found = next(
        (entry for entry in inner if files is None or (files / entry).is_file()),
        None,
    )
    if found is None:
        return [str(setup.executable)]
    return ["flatpak", "run", f"--command=/app/{found}", app]


def _command(
    setup: SlicerSetup,
    models: Sequence[Path],
    config: SlicerConfig,
    output: Path,
    keep_arrangement: bool = False,
    *,
    findings: list[Finding] | None = None,
    program: Sequence[str] | None = None,
) -> list[str]:
    """Die Kommandozeile dieses Slicers. Eine Liste, nie eine Zeichenkette —
    ein Dateiname mit Leerzeichen ist sonst zwei Argumente.

    Mehrere Modelle gehen zusammen hinein: die Slicer ordnen sie selbst auf der
    Platte an, und das ist ihre Aufgabe. Eines nach dem anderen zu slicen
    ergäbe ebenso viele Druckdateien, von denen jede so tut, als sei sie der
    ganze Auftrag.

    ``program`` ersetzt :func:`_cli_program`, wenn der Lauf das Programm selbst
    bereitstellt — CuraEngine über Curas Lader (:func:`cura_linux.engine`).
    """
    binary, *inside = program or _cli_program(setup)
    files = [str(entry) for entry in models]

    if setup.flavour == "prusa":
        # SuperSlicer ordnet auf der Konsole ohne ``--dont-arrange`` selbst an,
        # bis an den Bettrand und ohne Platz für die Skirt (RM-312: MINI,
        # Skirt bei y = -1,4 mm). PrusaSlicer hält die Lage auch so und nimmt
        # den Schalter an. Gesetzt wie ``--arrange 0`` nur bei haltender
        # Anordnung (:func:`app.core.export.writer.arrangement_holds`).
        return [
            binary,
            *inside,
            "--export-gcode",
            *(["--dont-arrange"] if keep_arrangement else []),
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
        # Creality Print ab 7.3 rechnet nur mit ``--cli`` auf der Konsole
        # (:func:`_creality_cli`).
        arguments = [
            binary,
            *inside,
            *(["--cli"] if _creality_cli(setup) else []),
            "--load-settings",
        ]
        arguments.append(settings_arg)
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
        if keep_arrangement and not _creality_cli(setup):
            # Ohne diesen Schalter ordnet die Orca-Familie **immer** neu an,
            # egal in welchen Koordinaten die Teile ankommen — gemessen an zwei
            # Läufen derselben Szene, die denselben G-Code ergaben. Damit war
            # alles folgenlos, was Solidon über die Platte weiß: `arrange_bed`,
            # der Haftungsrand, die Plattenzuordnung. Gesetzt wird er nur, wenn
            # die Anordnung wirklich eine ist (siehe
            # :func:`app.core.export.writer.arrangement_holds`) — sonst
            # druckten zwei Teile übereinander. Creality Print mit ``--cli``
            # kennt den Schalter nicht und ordnet selbst an (:func:`_creality_cli`).
            arguments += ["--arrange", "0"]
        if _creality_cli(setup):
            # Ohne ihn legt 7.3 die Druckdatei nur in sein eigenes Temp-Projekt,
            # nicht nach ``--outputdir`` (``SliceCommand``: ``need_gcode_file``).
            arguments.append("--need-gcode-file")
        return [*arguments, "--slice", "0", "--outputdir", str(output), *files]

    # **Ohne ``-v``.** Das ausführliche Protokoll nennt jede Schicht und
    # jeden Arbeitsschritt; am Eiffelturm aus dem Korpus (313 000 Dreiecke)
    # waren das 12,3 MB, über der Sammelgrenze :data:`SLICER_OUTPUT_LIMIT`,
    # und der Lauf endete ohne Druckdatei (RM-252). Ohne den Schalter bleiben
    # Warnungen und Fehler, 50 kB — mehr liest die Übergabe nicht daraus.
    arguments = [binary, *inside, "slice"]
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
            limited = _cura_limited_accelerations(mesh.settings, engine.settings)
            if findings is not None:
                findings.extend(_cura_limit_findings(mesh.settings, limited, file=mesh.path.name))
            for key, value in limited.items():
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
    """Eine Definition dieser Cura: neben dem Programm, sonst unter ihrem Bestand.

    Der Flatpak-Starter und das AppImage haben nichts neben sich; ihre
    Definitionen liegen im ``/app`` des Pakets oder in der Kopie aus dem Abbild
    (:func:`slicer_profiles.install_root`).
    """
    folders = [
        executable.parent / "share" / "cura" / "resources" / "definitions",
        executable.parent / "resources" / "definitions",
    ]
    for folder in folders:
        found = folder / filename
        if found.is_file():
            return str(found)
    if not cura_linux.needs_loader(executable):
        return ""
    root = slicer_profiles.install_root(executable)
    if root is None:
        return ""
    stocked = slicer_profiles.cura_resources(root) / "definitions" / filename
    return str(stocked) if stocked.is_file() else ""


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
        _cura_raft_overlap({}, values, setup.name)
        return CuraMachine()
    own = _cura_printer_definition(setup.executable, profile.printer)
    definition = Path(own or base)
    roots = _profile_roots(setup)
    source = profile_source(setup.machine_profile, setup, "machine")
    if source is None:
        source, _process = slicer_profiles.match(
            slicer_profiles.find_profiles(setup.executable, "cura", ("machine",)),
            profile.printer,
            source=discover.program_mark(setup.executable.name),
        )
        if source is None and profile.printer.id.startswith("slicer-cura-"):
            raise _cura_instance_error(
                setup,
                profile.printer.title,
                missing=not slicer_profiles.cura_instance_is_present(
                    setup.executable, profile.printer
                ),
            )
    raft_contact: dict[str, Any] = {}
    if isinstance(source, slicer_profiles.SlicerProfile):
        definition = source.path
        own = str(definition)
        try:
            chain = slicer_profiles.resolve_profile(
                source, roots, cura_motion=True, cura_raft_contact=raft_contact
            )
        except ExternalToolError as problem:
            if source.cura_instance is None:
                raise
            raise _cura_instance_error(setup, profile.printer.title, missing=False) from problem
    else:
        chain = slicer_profiles.resolve_values(
            definition, roots, cura_motion=True, cura_raft_contact=raft_contact
        )
    hardware = (
        _cura_hardware_values(chain, values)
        if (isinstance(source, slicer_profiles.SlicerProfile) and source.cura_instance is not None)
        else {}
    )
    hardware |= _cura_motion_values(chain, values, profile.printer)
    hardware |= _cura_raft_overlap(raft_contact, values, setup.name)
    # **Der Ursprung gehört der Maschine** (RM-330). Eine Druckerdefinition
    # oder Instanz mit ``machine_center_is_zero`` misst von der Bettmitte —
    # Curas Deltas etwa —, und CuraEngine verschiebt das Modell dann nicht.
    # Solidons ``false`` aus :func:`_machine_keys` gilt nur ohne Definition.
    # Geschrieben wird der Wert ausdrücklich, auch wo die Definition ihn als
    # Formel führt, denn die Konsole liest nur ``default_value``.
    centred = bool(own) and str(chain.get("machine_center_is_zero", "")).strip().lower() == "true"
    if own:
        hardware["machine_center_is_zero"] = "true" if centred else "false"
    width, depth, _height = profile.printer.build_volume
    known = _placeholder_values(chain, {**values, **hardware})
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
        settings=hardware,
        name=str(chain.get("machine_name") or ""),
        origin_at_centre=centred,
        shift=(((0.0, 0.0) if centred else (width / 2.0, depth / 2.0)) if own else None),
    )


def _cura_raft_overlap(
    contact: Mapping[str, Any], values: Mapping[str, str], tool: str
) -> dict[str, str]:
    """Curas belegte Kopplung oder seinen festen Wert an die Konsole geben."""
    gap = _as_float(values.get("raft_airgap"))
    if gap is None:
        return {}
    raw = contact.get("layer_0_z_overlap")
    fixed = _as_float(str(raw)) if not isinstance(raw, bool) else None
    if fixed is not None and fixed >= 0.0:
        return {"layer_0_z_overlap": f"{fixed:g}"}
    if isinstance(raw, str) and "".join(raw.split()) == "raft_airgap/2":
        return {"layer_0_z_overlap": f"{gap / 2.0:g}"}
    raise ExternalToolError(
        tool=tool,
        detail=_(
            "Der gewählte Raft-Abstand hängt in diesem Cura-Profil von einer unbekannten "
            "Einstellung ab. Verwenden Sie die Vorgabe des Slicers oder ändern Sie den "
            "Abstand in Cura."
        ),
        values={"constraint": "raft_gap_dependency", "field": "adhesion.raft_gap"},
        suggestions=(OPEN_PRINT_SETTINGS,),
    )


def _cura_instance_error(setup: SlicerSetup, printer: str, *, missing: bool) -> ExternalToolError:
    """Den fehlenden Cura-Stapel vom vorhandenen, unvollständigen trennen."""
    if missing:
        return ExternalToolError(
            tool=setup.name,
            title=_("Der Drucker ist in Cura nicht eingerichtet."),
            detail=_(
                "Die Druckerinstanz „{printer}“ ist in Cura nicht eingerichtet. Richten Sie sie "
                "in Cura ein oder wählen Sie in Solidon einen anderen Drucker.",
                printer=printer,
            ),
            suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER),
            values={"printer": printer},
        )
    return ExternalToolError(
        tool=setup.name,
        title=_("Solidon kann das Cura-Druckerprofil nicht vollständig auswerten."),
        detail=_(
            "Solidon kann das Cura-Druckerprofil „{printer}“ nicht vollständig auswerten. "
            "Prüfen Sie seine Profilwerte und Vorlagen in Cura oder wählen Sie in Solidon "
            "einen anderen Drucker.",
            printer=printer,
        ),
        suggestions=(CHECK_SLICER_PROFILE, CHOOSE_PRINTER),
        values={"printer": printer},
    )


def _cura_hardware_values(
    chain: Mapping[str, object], written: Mapping[str, str]
) -> dict[str, str]:
    """Native Hardware behalten; bewusst geänderte Projektmaße und Düse gehen vor."""
    dimensions = {
        "machine_width",
        "machine_depth",
        "machine_height",
        "machine_nozzle_size",
        "machine_extruder_count",
    }
    hardware = {
        key: str(value).lower() if isinstance(value, bool) else _printed(value)
        for key, value in chain.items()
        if (key.startswith(("machine_", "extruder_")) or key == "gantry_height")
        and key not in MACHINE_CODES
        and not (key in dimensions and key in written)
        and isinstance(value, (str, int, float, bool))
    }
    return hardware


def _cura_limited_accelerations(
    values: Mapping[str, str], machine: Mapping[str, str]
) -> dict[str, str]:
    """Prozesswerte auf die belegte X-/Y-Grenze deckeln, auch je Netz."""
    limits = [
        number
        for axis in ("x", "y")
        if (number := _as_float(machine.get(f"machine_max_acceleration_{axis}"))) is not None
        and math.isfinite(number)
        and number > 0.0
    ]
    result = dict(values)
    if not limits:
        return result
    limit = min(limits)
    for key, value in values.items():
        if not (key.startswith("acceleration_") or key.endswith("_acceleration")):
            continue
        number = _as_float(value)
        if number is not None and math.isfinite(number) and number > limit:
            result[key] = f"{limit:g}"
    return result


def _cura_limit_findings(
    requested: Mapping[str, str],
    written: Mapping[str, str],
    *,
    paths: frozenset[str] | None = None,
    object_id: str | None = None,
    file: str = "",
) -> list[Finding]:
    """Eine gekürzte Wahl bleibt als strukturierter Befund erhalten, auch je Teil.

    Nur die im Dialog angebotenen Wurzeln zählen, nicht deren Cura-Spiegel.
    Für die Platte gelten die eigenen und übernommenen Wahlen; ein Netz
    trägt bereits nur seine Abweichungen und nennt deshalb jede Kürzung.
    """
    findings: list[Finding] = []
    for entry in slicer_keys.TABLES["cura"]:
        if entry.key not in ("acceleration_print", "acceleration_wall_0"):
            continue
        if paths is not None and entry.path not in paths:
            continue
        before = _as_float(requested.get(entry.key))
        after = _as_float(written.get(entry.key))
        if before is None or after is None or not before > after:
            continue
        findings.append(
            Finding(
                code="slicer.acceleration_limited",
                severity="warning",
                message=_(
                    "Für Cura wird die Beschleunigung auf die Grenze des Druckers begrenzt. "
                    "Prüfen Sie den Wert im Druckdialog."
                ),
                object_id=object_id,
                values={
                    "setting": entry.path,
                    "requested": before,
                    "actual": after,
                    **({"file": file} if file else {}),
                },
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        )
    return findings


def cura_acceleration_findings(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    parts: Mapping[str, Mapping[str, str]],
    *,
    for_window: bool = False,
) -> list[Finding]:
    """Der Exportbericht nennt dieselben Kürzungen wie der CuraEngine-Lauf."""
    if setup.flavour != "cura":
        return []
    requested = values_for(settings, profile, setup.flavour)
    motion = (
        cura_window_motion(setup, profile)
        if for_window
        else _cura_machine(setup, profile, requested).settings
    )
    limited = _cura_limited_accelerations(requested, motion)
    # Beim Fenster meldet der Profilschreiber die Platte erst beim Schreiben,
    # einschließlich der einzelnen Spulen. Hier reisen dann nur Objektwerte.
    findings = (
        [] if for_window else _cura_limit_findings(requested, limited, paths=settings.explicit)
    )
    for object_id, original in parts.items():
        limited = _cura_limited_accelerations(original, motion)
        findings.extend(_cura_limit_findings(original, limited, object_id=object_id))
    return findings


def _cura_motion_values(
    chain: Mapping[str, object], written: Mapping[str, str], printer: PrinterProfile
) -> dict[str, str]:
    """Numerische Maschinenwerte der Definitionskette für CuraEngine auflösen.

    CuraEngine liest nur ``default_value``. Der Profilauflöser liefert auch
    numerisches ``value``, lässt Formeln aber aus. Grenzen bleiben deshalb
    Herstellerdaten; die Stufenvorgabe ersetzt nie eine unbekannte Grenze.
    """
    motion: dict[str, str] = {}
    for key, value in chain.items():
        if key != "machine_acceleration" and not key.startswith(
            ("machine_max_acceleration_", "machine_max_feedrate_", "machine_max_jerk_")
        ):
            continue
        number = _as_float(str(value))
        if number is not None and math.isfinite(number) and number >= 0.0:
            motion[key] = f"{number:g}"
    # Vor dem Endcode setzt CuraEngine diese Beschleunigung erneut mit M204.
    # Auch die Rückstellung muss innerhalb der unveränderten Achsgrenzen liegen.
    motion = _cura_limited_accelerations(motion, motion)
    enabled = str(chain.get("jerk_enabled", "")).casefold()
    if enabled in {"true", "false"}:
        motion["jerk_enabled"] = enabled
        if enabled == "true":
            for key, value in chain.items():
                if key.startswith("jerk_") or key.endswith("_jerk"):
                    motion[key] = (
                        str(value).lower() if isinstance(value, bool) else f"{float(str(value)):g}"
                    )
        motion.update(
            (key, value)
            for key, value in written.items()
            if key.startswith("jerk_") or key.endswith("_jerk")
        )
    if written.get("acceleration_enabled") != "true":
        return motion

    process_values = {
        key: value
        for key, value in written.items()
        if key.startswith("acceleration_") or key.endswith("_acceleration")
    }
    printing = process_values.get("acceleration_print", motion.get("machine_acceleration"))
    if printing is not None:
        process_values.setdefault("acceleration_print", printing)
        process_values.setdefault("acceleration_wall_0", printing)
        for source, targets in slicer_keys.CURA_MIRRORED.items():
            if source in process_values:
                for target in targets:
                    process_values.setdefault(target, process_values[source])
    travel = _as_float(str(chain.get("acceleration_travel", "")))
    if travel is not None and math.isfinite(travel) and travel > 0.0:
        process_values["acceleration_travel"] = f"{travel:g}"
    process_values = _cura_limited_accelerations(process_values, motion)
    acceleration = _as_float(process_values.get("acceleration_print"))
    if acceleration:
        first = min(printer.first_layer_acceleration or _FIRST_LAYER_ACCELERATION, acceleration)
        process_values["acceleration_layer_0"] = f"{first:g}"
        for key in slicer_keys.CURA_MIRRORED["acceleration_layer_0"]:
            process_values[key] = f"{first:g}"
        travel = _as_float(process_values.get("acceleration_travel")) or acceleration
        process_values["acceleration_travel_layer_0"] = f"{first * travel / acceleration:g}"
    return motion | process_values


def cura_machine_differences(
    analysis: gcode.GcodeAnalysis, machine: CuraMachine | None
) -> list[str]:
    """Hat CuraEngine mit der Maschine gerechnet, die Solidon übergab?

    Die Gegenprobe der Werte (:func:`verify_settings`) sieht es nicht:
    CuraEngine schreibt keine Einstellungen in die Druckdatei. Ohne die
    Maschine druckte der Drucker ohne die Bettvermessung oder das Startmakro
    seines Herstellers (``M420 S1``, ``START_PRINT``). Geprüft werden der Name im
    Kopf (``;TARGET_MACHINE.NAME``) und, der Reihe nach, jeder Befehl des
    übergebenen Startcodes vor der ersten Schicht (Konzept Herstellerprofil,
    Entscheidung K). Ohne Druckerdefinition gibt es nichts zu vergleichen, dort
    spricht :func:`machine_missing`.
    """
    if machine is None or not machine.from_printer:
        return []
    differences: list[str] = []
    found = analysis.settings.get("machine_name")
    if machine.name and found is not None and found != machine.name:
        differences.append(f"machine_name: {machine.name} → {found}")
    position = 0
    for line in machine.codes.get("machine_start_gcode", "").splitlines():
        command = line.split(";", 1)[0].strip()
        if not command:
            continue
        try:
            position = analysis.start.index(command, position) + 1
        except ValueError:
            differences.append(f"machine_start_gcode: {command} → —")
            break
    return differences


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
    *,
    finished: Callable[[], bool] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Führt den Slicer aus — abbrechbar, und mit der Zeitgrenze als Antwort.

    ``subprocess.run`` wartete blind: Eine Zeitüberschreitung flog als roher
    ``TimeoutExpired`` aus dem Arbeits-Thread, der fing nur ``AppError`` —
    der Dialog stand dauerhaft auf „Der Slicer rechnet …" (Regel 17, §2.8).
    Und abzubrechen gab es nichts: der Kindprozess lief, bis er fertig war,
    gleich was der Nutzer wollte.

    ``finished`` sagt, ob der Slicer sein Ergebnis abgelegt hat
    (:func:`_result_written`); endet er danach nicht, beendet ihn
    :func:`app.core.process.run_limited`.
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
            finished=finished,
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
    origin_at_centre: bool = False,
    shift: tuple[float, float] | None = None,
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
    PrusaSlicer schreiben ihre Bettform in die Datei; dann gilt das darin
    angegebene Bett aus ``gcode.analyze(...).bed``. Sonst gilt die wirksame
    Druckfläche des Druckerprofils einschließlich seiner Sperrflächen. Das
    trifft insbesondere CuraEngine, dem Solidon die Maße selbst gegeben hat.
    Dessen Bett liegt um den Nullpunkt des Druckers
    (``build_area.machine_shift``, meist ab der Ecke), an einer
    Cura-Druckerdefinition mit Ursprung in der Mitte um 0
    (``origin_at_centre``, aus :attr:`SlicerConfig.origin_at_centre`): Dort
    schrieb CuraEngine richtig um 0, und die Prüfung gegen 0 bis Breite
    meldete jedes Teil links oder vor der Mitte (RM-330). Am Dremel 3D45
    reicht das Bett von -127,5 bis 97,5 (RM-424).
    Der erste Anlauf maß
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

    Eine unbrauchbare Bettkontur bleibt als Warnung sichtbar. Liegt zusätzlich
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
    note: TranslatableText | None = None
    area = _usable_area(analysis.bed_outline) if analysis.bed_outline else None
    if area is None:
        if analysis.bed_outline:
            _log.warning("the bed outline of the print file has no area; using the profile")
            note = _(
                "Die Bettkontur der Druckdatei hat keine nutzbare Fläche; "
                "geprüft wurde gegen das Druckerprofil."
            )
        area = build_area.printable_area(profile.printer)
        if wants_bed_coordinates(flavour) and not origin_at_centre:
            # Um den Nullpunkt des Druckers, nicht immer ab der Ecke (RM-424);
            # eine Cura-Druckerdefinition sagt ihren selbst (``shift``).
            across, along = (
                shift if shift is not None else build_area.machine_shift(profile.printer)
            )
            area = translate(area, xoff=across, yoff=along)
    # Jede Sperrfläche ist ein Rechteck mit Fläche (``gcode.exclusion_areas``),
    # so wie der Slicer sie liest; ohne Fläche hätte er sie schon übergangen.
    # Nennt die Datei Sperrflächen, die sich nicht lesen lassen (``None``),
    # wird ohne sie geprüft, und der Prüfbericht sagt es — „keine“ wäre eine
    # Entwarnung für eine Bahn, die mitten durch eine fährt.
    if analysis.excluded_areas is None:
        unread = _("Die Sperrflächen der Druckdatei sind unlesbar, geprüft wurde ohne sie.")
        note = unread if note is None else _("{bed} {exclusions}", bed=note, exclusions=unread)
    for (left, front), _right_front, (right, back), _left_back in analysis.excluded_areas or ():
        area = area.difference(box(left, front, right, back))
    warning = None
    if note is not None:
        warning = Finding(
            code="gcode.invalid_build_area",
            severity="warning",
            message=_("{detail} Prüfen Sie die Druckfläche im Slicer.", detail=note),
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

#: Creality Print vor 7.3, das ``--cli`` nicht kennt (siehe :func:`_creality_cli`).
_REFUSES_THE_CLI_FLAG: Final[set[Path]] = set()


def _creality_cli(setup: SlicerSetup) -> bool:
    """Ob dieser Lauf Creality Print mit ``--cli`` rechnen lässt.

    **Ab 7.3 startet Creality Print ohne ``--cli`` die Oberfläche**, gleich
    welche Schalter folgen, und der Lauf wartete bis zum Zeitlimit (gemessen am
    29.09.2026 mit 7.3.0.6149, ``CrealityPrint.cpp``:
    ``parse_application_arguments``). Dieselbe Konsole kennt ``--arrange`` nicht
    mehr; die Druckdatei schreibt sie nur mit ``--need-gcode-file`` in den
    Ausgabeordner.

    **Eine einzelne Platte ordnet sie selbst an** (RM-331, gemessen am
    02.10.2026 mit 7.3.0.6149 an einer Ender-3 V3 SE mit Creality-Profilen, je
    Platte eine 3MF wie bei *Slicen*): Ring mit Kern, ein schwebendes Teil,
    eines über den Rand und zwei überlappende Teile lagen in der Druckdatei
    getrennt, abgesetzt und mittig auf dem Bett, ohne Absage und ohne
    ``gcode.off_the_bed``. Eine Platte, deren Anordnung nicht hält, geht
    deshalb wie bei den übrigen Programmen der Familie ohne Vorgabe hinaus.
    Dieselbe Messung rückte auch eine haltende Anordnung zur Mitte, mit und
    ohne ``plate``-Block.
    Version 7.2 lehnt ``--cli`` als unbekannten Schalter ab; dann läuft der
    Aufruf ohne ihn, gemerkt je Programm.
    """
    return _is_creality_print(setup) and setup.executable not in _REFUSES_THE_CLI_FLAG


#: So viele Ebenen fragt :func:`_printable_above` je Teil höchstens ab. Fehlt
#: mehr Höhe, liegt Material von Bahnbreite fast immer schon an der untersten.
TOP_PROBE_LAYERS: Final = 64


def too_short(
    payload: str | gcode.GcodeAnalysis,
    model_height: float,
    settings: PrintSettings,
    *,
    meshes: Sequence[Mesh] = (),
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

    **Was schmaler als eine Bahn ist, fehlt nicht.** Läuft ein Teil oben als
    Schneide aus, legt ein Slicer mit festen Bahnbreiten dort keine Bahn — an
    ``bottom-single.stl`` (Slicer-Matrix, RM-312) endeten ElegooSlicer, Bambu
    Studio und SuperSlicer bei 78,0 statt 78,49 mm, und dieser Befund schickte
    den Kunden mit *Auf das Bett legen* zu einem Teil, das auf dem Bett lag.
    Mit den Netzen der Platte (``meshes``) zählt deshalb nur, was über der
    gedruckten Höhe noch eine Bahnbreite trägt (:func:`_printable_above`);
    ohne sie bleibt der Vergleich der Höhen.
    """
    analysis = payload if isinstance(payload, gcode.GcodeAnalysis) else gcode.analyze(payload)
    extent = analysis.extent
    if extent is None or model_height <= 0.0:
        return None
    printed_height = float(extent.maximum[2])
    allowance = 2.0 * settings.layers.layer_height
    # Die Grenze zählt mit (Regel 6): An „Rack system for Filament.3mf“ stand
    # 21,6 mm Druck gegen 22,000000000000014 mm Modell, und der Befund kam aus
    # der letzten Stelle der Netzhöhe.
    if printed_height >= model_height - allowance - EPS_GEOM:
        return None
    if meshes and not _printable_above(meshes, printed_height + allowance, settings):
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


def _printable_above(meshes: Sequence[Mesh], height: float, settings: PrintSettings) -> bool:
    """Trägt ein Teil über ``height`` (gemessen von seinem Fuß) noch eine Bahnbreite?

    Gefragt wird am Querschnitt, ob nach innen um eine halbe Bahnbreite
    versetzt etwas übrig bleibt — dann passt dort eine ganze Bahn. Die Ebenen
    stehen im Schichtabstand von ``height`` aufwärts, je Teil höchstens
    :data:`TOP_PROBE_LAYERS`; die unterste mit Material von Bahnbreite beendet
    die Frage. Jedes Teil steht im Slicer auf dem Bett, darum zählt die Höhe
    von seinem eigenen Fuß.
    """
    from app.core.slice.analysis import cross_sections

    inset = settings.layers.line_width / 2.0
    step = settings.layers.layer_height
    for mesh in meshes:
        data = as_mesh_data(mesh)
        bottom = float(data.bounds.minimum[2])
        top = float(data.bounds.maximum[2])
        start = bottom + height
        if start >= top:
            continue
        count = min(TOP_PROBE_LAYERS, max(1, math.ceil((top - start) / step)))
        spacing = (top - start) / count
        heights = [start + spacing * index for index in range(count)]
        for section in cross_sections(data, heights):
            if section is not None and not section.buffer(-inset).is_empty:
                return True
    return False


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
    material_slots = tuple(slots) or (MaterialSlot(index=0, name=""),)
    foundation = (
        manufacturer.base_settings(profile, settings.quality, setup)
        if setup.flavour == "orca" and any(slot.material for slot in material_slots)
        else None
    )
    effective = (
        tuple(
            settings_for_slot(settings, profile, slot, setup, foundation=foundation)
            for slot in material_slots
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


def _orca_cli_tower_position(
    config: SlicerConfig, setup: SlicerSetup, models: Sequence[Path]
) -> SlicerConfig:
    """Initialisiert fehlende Turmkoordinaten der Orca-Konsolen (RM-476).

    Crealitys bekannter Platzierungsmodus bleibt maßgeblich. Ohne Modus
    beginnt der Turm unten mit Abstand zum Rand, statt bei der festen
    Konsolenvorgabe 15/220, und neben den Sperrflächen der Maschine
    (:func:`_beside_the_exclusions`). Bei 90 Grad wächst seine Tiefe nach links.
    Gespeicherte Koordinaten gewinnen immer, auch aus einer 3MF-Beilage.
    Native Breite und Brim begrenzen den Start; erst die G-Code-Gegenprobe
    kennt die wirkliche Fläche einschließlich Rippen und Reinigungsvolumen.
    """
    if (
        setup.flavour != "orca"
        or discover.program_mark(setup.executable.name)
        not in {"crealityprint", "orcaslicer", "elegooslicer", "bambustudio", "anycubicslicernext"}
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
        mode = str(values.get("prime_tower_position_type", "")).strip()
        horizontal, _, vertical = mode.partition(" ")
        if mode and (
            discover.program_mark(setup.executable.name) != "crealityprint"
            or horizontal not in {"Left", "Middle", "Right"}
            or vertical not in {"Upper", "Center", "Below"}
        ):
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
        if not mode:
            brim = float(values.get("prime_tower_brim_width", ORCA_TOWER_DEFAULT_BRIM))
            if not math.isfinite(brim) or brim < 0.0:
                return config
            margin = side + brim
            across, along = right - left, top - bottom
            if not is_zero(rotation):
                across, along = along, across
            if width + 2 * margin > across or 2 * margin >= along:
                return config
            start = _beside_the_exclusions(
                values.get("bed_exclude_area"),
                left + margin if is_zero(rotation) else bottom + margin,
                width,
                margin,
                vertical=not is_zero(rotation),
            )
            if start is None:
                return config
            if is_zero(rotation):
                if start + width + margin > right:
                    return config
                x, y = start, bottom + margin
            else:
                if start + width + margin > top:
                    return config
                x, y = right - margin, start
            placed = dict(zip(coordinates, (str(x), str(y)), strict=True))
        elif is_zero(rotation):
            xs = {
                "Left": left + side,
                "Middle": (left + right - width) / 2,
                "Right": right - width - side,
            }
            ys = {"Upper": top - upper, "Center": (bottom + top) / 2, "Below": bottom + side}
        else:
            xs = {"Left": left + upper, "Middle": (left + right) / 2, "Right": right - side}
            ys = {"Upper": top - width - side, "Center": (bottom + top) / 2, "Below": bottom + side}
        if mode:
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


def _beside_the_exclusions(
    raw: object, start: float, width: float, margin: float, *, vertical: bool
) -> float | None:
    """Wo der Turm quer zu seiner Tiefe beginnt, ohne eine Sperrfläche zu berühren.

    Bambu P1S, P1P, X1 und X1 Carbon sperren vorn links 18 mal 28 mm
    (``bed_exclude_area``); dort begann der Turm aus RM-476 und reichte in
    die Sperrfläche (Slicer-Matrix RM-312, P1S mit Bambu Studio). Die Tiefe
    des Turms kennt erst der Slicer — sie wächst mit der Spülmenge —, deshalb
    gilt jede Sperrfläche, deren Ausdehnung quer zur Tiefe die Turmbreite samt
    Rand (``margin``, Herstellerabstand und Brim) überlappt, gleich wo sie in
    der Tiefe liegt: Der Anfang rückt hinter sie, mit demselben Rand wie am
    Bettrand. ``vertical`` heißt, die Breite läuft entlang y (90 Grad).
    Unlesbare Sperrflächen sind keine Auskunft: dann ``None``, und die Lage
    bleibt beim Slicer.
    """
    if isinstance(raw, list) and all(isinstance(point, str) for point in raw):
        raw = ",".join(raw)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return start
    if not isinstance(raw, str):
        return None
    # Je vier Punkte ein Rechteck, wie der Slicer liest; Orcas Vorgabe „0x0“
    # sperrt nichts und hielt den Turm bis zum 05.10.2026 trotzdem an.
    areas = gcode.exclusion_areas(raw)
    if areas is None:
        return None
    spans: list[tuple[float, float]] = []
    for contour in areas:
        shape = _usable_area(contour)
        if shape is None:
            return None
        low_x, low_y, high_x, high_y = shape.bounds
        spans.append((low_y, high_y) if vertical else (low_x, high_x))
    for _round in range(len(spans) + 1):
        blocking = [
            high for low, high in spans if low < start + width + margin and high > start - margin
        ]
        if not blocking:
            return start
        start = max(blocking) + margin
    return None


def _meshes_from_files(models: Sequence[Path], setup: SlicerSetup) -> tuple[MeshData, ...]:
    """Liest Druckteile über die vorhandenen begrenzten Leser; Hilfsnetze zählen nicht."""
    from app.core.ingest import loader
    from app.core.ingest.threemf import read_objects as read_3mf_objects

    parts: list[MeshData] = []
    for model in models:
        inputs = (
            [
                entry.path
                for entry in cura_meshes(model)
                if entry.settings.get("anti_overhang_mesh", "false").casefold() not in {"true", "1"}
            ]
            if setup.flavour == "cura"
            else [model]
        )
        for source in inputs:
            payload = loader.read_bounded_payload(source)
            if source.suffix.lower() == ".3mf":
                loader.check_unpacked(payload)
                parts.extend(part.mesh for part in read_3mf_objects(payload, printable_only=True))
            else:
                try:
                    parts.append(loader.read_model(payload, source.suffix))
                except ValidationError as problem:
                    if problem.constraint not in {
                        "unreadable",
                        "no_geometry",
                        "unsupported_format",
                    }:
                        raise
                    # Unlesbares belegt keine bestimmte Bauraumursache.
    return tuple(parts)


def _check_plate(
    meshes: Sequence[Mesh],
    profile: Profile,
    setup: SlicerSetup,
    cancelled: CancelToken | None = None,
) -> None:
    """Bekannte Bauraumgründe halten vor dem externen Prozess an."""
    from app.core.export.writer import arrangement_holds
    from app.core.geom.prepare import arrange_on_bed

    resize = replace(SCALE_TO_FIT, label=_("Verkleinern …"))
    for index, mesh in enumerate(meshes):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        height = float(mesh.bounds.size[2])
        limit = build_area.printable_height(profile.printer)
        if height > limit + EPS_GEOM:
            raise ExternalToolError(
                tool=setup.name,
                title=SLICER_FAILED,
                detail=_("Ein Teil ist höher, als dieser Drucker drucken kann."),
                values={
                    "height_mm": height,
                    "limit_mm": limit,
                    "constraint": "slicer_build_volume",
                    "part_index": index,
                },
                suggestions=(SPLIT_MODEL, resize, CHOOSE_PRINTER, CANCEL),
            )
        excess = build_area.size_excess(mesh, profile.printer)
        if excess > build_area.size_excess_uncertainty(mesh) + EPS_GEOM:
            raise ExternalToolError(
                tool=setup.name,
                title=SLICER_FAILED,
                detail=_("Ein Teil ist größer als die Druckfläche, auch wenn es gedreht wird."),
                values={
                    "excess_mm": excess,
                    "constraint": "slicer_build_volume",
                    "part_index": index,
                },
                suggestions=(SPLIT_MODEL, resize, CHOOSE_PRINTER, CANCEL),
            )
    if len(meshes) > 1:
        data = [as_mesh_data(mesh) for mesh in meshes]
        if not arrangement_holds(data, profile):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            planned = arrange_on_bed(data, profile)
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            if any(finding.code == "arrange.needs_more_plates" for finding in planned.findings):
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Für diese Teile wurde keine Anordnung auf einer Druckplatte gefunden. "
                        "Sie können alle Teile des Projekts neu auf Platten anordnen "
                        "oder einen größeren Drucker wählen."
                    ),
                    suggestions=(ARRANGE_ON_BED, CHOOSE_PRINTER, resize, CANCEL),
                    values={"constraint": "slicer_build_volume"},
                )


def _prepare_cura_cli(
    command: list[str], workspace: Path, cancelled: CancelToken | None
) -> list[str]:
    """Curas Dateileser bekommt technische Namen, auch für Vorlagen und Blocker.

    Die Definitionen bleiben vollständig: Nur ihre Dateiverweise ändern sich.
    Curas Suchreihenfolge gilt dabei weiter, einschließlich der Verzeichnisse,
    die beim Laden einer Definition hinzukommen. Originale bleiben unberührt.

    Alles vor ``slice`` ist das Programm und bleibt, wie es ist — unter Linux
    auch Curas Lader samt Bibliothekspfad (:func:`cura_linux.engine`). Weil
    danach jeder Dateipfad im Arbeitsordner liegt, braucht ein Cura-Flatpak
    keine übersetzten ``/app``-Pfade, nur die Freigabe dieses Ordners.
    """
    roots = [
        Path(entry)
        for entry in os.environ.get("CURA_ENGINE_SEARCH_PATH", "").split(os.pathsep)
        if entry
    ]
    for index, argument in enumerate(command[:-1]):
        if argument == "-d":
            roots = [Path(entry) for entry in command[index + 1].split(os.pathsep)]
            break
    roots = [path if path.is_absolute() else workspace / path for path in roots]
    definitions = workspace / "definitions"
    copied: dict[Path, str] = {}
    active: set[Path] = set()

    def invalid(path: Path) -> ExternalToolError:
        return ExternalToolError(
            tool="CuraEngine",
            detail=_(
                "Das Slicer-Profil „{name}“ ist unvollständig. "
                "Prüfen Sie seine Vorlagen im Slicer.",
                name=path.name,
            ),
            values={"name": path.name},
            suggestions=(CHECK_SLICER_PROFILE, CHOOSE_SLICER, EXPORT_ONLY),
        )

    def reference(name: object, source: Path) -> str:
        if not isinstance(name, str) or not name or Path(name).name != name or "\\" in name:
            raise invalid(source)
        for root in roots:
            candidate = root / f"{name}.def.json"
            if candidate.is_file():
                return definition(candidate)
        raise invalid(source)

    def definition(source: Path) -> str:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        source = source.resolve()
        if source in active or len(active) >= slicer_profiles.MAX_INHERITANCE:
            raise invalid(source)
        if source in copied:
            return copied[source]
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as problem:
            raise invalid(source) from problem
        if not isinstance(data, dict):
            raise invalid(source)
        roots.append(source.parent)
        active.add(source)
        name = f"definition-{len(copied)}"
        copied[source] = name
        if "inherits" in data:
            data["inherits"] = reference(data["inherits"], source)
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise invalid(source)
        trains = metadata.get("machine_extruder_trains", {})
        if not isinstance(trains, dict):
            raise invalid(source)
        for key, value in trains.items():
            trains[key] = reference(value, source)
        (definitions / f"{name}.def.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        active.remove(source)
        return name

    index = command.index("slice") + 1
    staged = [*command[:index], "-d", str(definitions)]
    mesh_count = 0
    try:
        definitions.mkdir()
        while index < len(command):
            flag = command[index]
            if flag in {"-d", "-j", "-l", "-o", "-s"}:
                value = command[index + 1]
                if flag == "-d":
                    index += 2
                    continue
                if flag == "-j":
                    value = str(definitions / f"{definition(Path(value))}.def.json")
                elif flag == "-l":
                    target = workspace / f"model-{mesh_count}.stl"
                    _copy_print_file(Path(value), target, cancelled=cancelled)
                    value = str(target)
                    mesh_count += 1
                elif flag == "-o":
                    value = str(workspace / OUTPUT_NAME)
                staged.extend((flag, value))
                index += 2
            else:
                staged.append(flag)
                index += 1
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or workspace), detail=str(problem.strerror or problem)
        ) from problem
    return staged


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
    model_meshes: Sequence[Mesh] | None = None,
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
    if not discover.is_file_on_host(setup.executable):
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der eingestellte Slicer liegt nicht mehr an seinem Pfad."),
            suggestions=(INSTALL_MISSING, EXPORT_ONLY),
        )

    meshes = model_meshes if model_meshes is not None else _meshes_from_files(models, setup)
    _check_plate(meshes, profile, setup, cancelled)

    started_perf_counter = time.perf_counter()
    # Gefragt an der Wahl vor der Trennung: Ein Ersatz gilt der Platte wie dem
    # Teil, das den Wert als Objektwert trägt (RM-480).
    substituted = substituted_choices(settings, slicer_keys.program_of(setup.executable))
    # **Dieselbe Platte wie in der Datei** (Entscheidung G): Was je Teil gilt,
    # trägt das Modell aus ``write_assembly`` als Objektwert oder Netzwert.
    settings = split_for_parts(settings, profile, setup, setup.flavour).plate
    # Die eigene Stützschichthöhe hat der Export aus den Werten der Teile
    # entschieden; ohne seine Beilage gilt der Abstand der Platte (RM-583),
    # unter organischen Bäumen keiner (RM-622).
    free_support_layers = (
        _frees_in_project(models)
        if slicer_keys.has_independent_support_layers(setup.flavour)
        else False
    )
    if free_support_layers is None:
        free_support_layers = frees_support_layers(
            support_gaps_by_style(settings, organic=organic_styles(setup, profile))[1],
            settings.layers.layer_height,
            setup.flavour,
        )
    # Ein Slicer als Flatpak sieht unser ``/tmp`` nicht
    # (``discover.workspace_for``).
    with discover.workspace_for(setup.executable, "solidon-slice-", ascii_only=True) as workspace:
        cli_models = (
            [
                _creality_cli_input(entry, workspace / f"model_{index}.3mf", cancelled)
                for index, entry in enumerate(models)
            ]
            if _is_creality_print(setup)
            else models
        )
        if setup.flavour != "cura":
            cli_models = [
                (
                    entry
                    if entry.parent == workspace
                    else _copy_print_file(
                        entry, workspace / f"model-{index}{entry.suffix}", cancelled=cancelled
                    )
                )
                for index, entry in enumerate(cli_models)
            ]
        config = write_config(
            settings, profile, setup, workspace, slots, free_support_layers=free_support_layers
        )
        limited_settings = list(config.findings)
        requested_values = config.written
        config = _orca_cli_tower_position(config, setup, cli_models)
        densities, diameters = _readback_materials(config, settings, profile, setup, slots)
        # Aus demselben Grund wie die Modellpfade: der Slicer schreibt sonst
        # neben sein Arbeitsverzeichnis statt dorthin, wo die Datei erwartet
        # wird — und ``_find_gcode`` sucht an der leeren Stelle.
        # Alle CLI-Dateipfade bleiben im privaten Arbeitsordner. Der Rückweg
        # ins gewünschte Unicode-Ziel läuft nach dem Lesen über Python.
        target = workspace
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
        # Ab wann eine Ergebnisdatei zu diesem Lauf gehört (``_result_refusal``).
        result_started_at = time.time()
        # **Bambu Studio endet manchmal nicht** nach seiner ``result.json``:
        # Druckdatei geschrieben, Prozess steht (Gesamtprüfung, 27.09.2026).
        # Ob die Datei dieses Laufs da ist, fragt :func:`_result_written`.
        with ExitStack() as engine_scope:
            # Cura unter Linux rechnet über seinen eigenen Lader; ein AppImage
            # bleibt dafür bis zum Ende des Laufs eingehängt (RM-521).
            program = (
                engine_scope.enter_context(
                    cura_linux.engine(setup.executable, workspace, setup.name, cancelled)
                )
                if setup.flavour == "cura"
                else None
            )
            command = _command(
                setup,
                cli_models,
                config,
                target,
                wanted_arrangement,
                findings=limited_settings,
                program=program,
            )
            if setup.flavour == "cura":
                command = _prepare_cura_cli(command, workspace, cancelled)
            outputs_before = _output_files(target)
            result_before = _result_signature(target)
            completed = _run_slicer(
                command,
                workspace,
                timeout,
                setup,
                cancelled,
                finished=_result_written(target) if setup.flavour == "orca" else None,
            )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Nur die Dateien dieses Versuchs zählen. Auch die selbst benennende
        # Orca-Familie muss eine einzelne vollständige Druckdatei liefern.
        expected = "" if names_its_own_output(setup.flavour) else OUTPUT_NAME
        produced = _find_gcode(target, expected, before=outputs_before, tool=setup.name)
        if (
            produced is None
            and _creality_cli(setup)
            and _refuses_option(_tail(completed.stdout, completed.stderr), "--cli")
        ):
            # Creality Print vor 7.3 kennt ``--cli`` nicht und rechnet ohne ihn
            # auf der Konsole (:func:`_creality_cli`).
            _REFUSES_THE_CLI_FLAG.add(setup.executable)
            outputs_before = _output_files(target)
            result_before = _result_signature(target)
            completed = _run_slicer(
                _command(setup, cli_models, config, target, wanted_arrangement),
                workspace,
                timeout,
                setup,
                cancelled,
                finished=_result_written(target),
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            produced = _find_gcode(target, expected, before=outputs_before, tool=setup.name)
        # Creality Print 7.3 rückt auf der Konsole jede Platte selbst zur Mitte,
        # auch eine haltende Anordnung (RM-414, :func:`_creality_cli`) — dann
        # gilt Solidons Plattenbelegung dort nie, und das steht dabei.
        arranged_by_slicer = keep_arrangement and (not wanted_arrangement or _creality_cli(setup))
        # **Der Familienname bleibt hier stehen, und das ist gemessen.** Die
        # anderen Vergleiche dieser Datei sind am 07.09.2026 auf benannte
        # Prädikate gestellt (`takes_a_machine_profile`); dieser meint eine
        # eigene Eigenschaft — „bei dieser Familie lohnt ein zweiter Versuch
        # ohne die Anordnungsvorgabe" —, und die wird sonst nirgends gefragt.
        # Ein Prädikat für eine einzige Stelle ist Zierat; es entsteht, wenn
        # die zweite dazukommt oder ein Fork hier abweicht.
        if (
            produced is None
            and wanted_arrangement
            and setup.flavour == "orca"
            and not _creality_cli(setup)
            # Die Temperaturprüfung hängt nicht an der Anordnung (RM-620).
            and not orca_refused(
                _exit_code(completed, _result_refusal(target, result_started_at, result_before)),
                ORCA_MIXED_TEMPERATURES,
            )
        ):
            refused_flag = _refuses_option(_tail(completed.stdout, completed.stderr), "arrange")
            # Die Rückfallstufe: einmal ohne die Anordnungsvorgabe — dieselbe
            # Bauart wie bei den Booleschen Ops, und wie dort wird die
            # benutzte Stufe ausgewiesen statt verschwiegen. Ein Slicer, der
            # auch so nichts schreibt, läuft in die Fehlerbehandlung darunter,
            # mit derselben Meldung wie bisher.
            outputs_before = _output_files(target)
            result_before = _result_signature(target)
            completed = _run_slicer(
                _command(setup, cli_models, config, target, False),
                workspace,
                timeout,
                setup,
                cancelled,
                finished=_result_written(target),
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            produced = _find_gcode(target, expected, before=outputs_before, tool=setup.name)
            if produced is not None:
                if refused_flag:
                    _REFUSES_THE_ARRANGE_FLAG.add(setup.executable)
                arranged_by_slicer = True
        if produced is None:
            first_layer_error = _empty_first_layer_error(setup, completed.stdout, completed.stderr)
            if first_layer_error is not None:
                if _first_layer_narrower_than_a_line(meshes, settings):
                    raise _narrow_first_layer_error(setup, first_layer_error.values)
                raise first_layer_error
            # Beide Ströme: die Orca-Familie protokolliert auf stdout und
            # lässt stderr leer. Nur stderr zu zeigen hieße, einen Fehler
            # ohne Text zu melden — und das ist schlimmer als keiner.
            output = _tail(completed.stdout, completed.stderr)
            # Eine Absage in ``result.json`` ist kein Absturz, auch wenn Solidon
            # den Slicer danach beenden musste (:func:`_exit_code`).
            refusal = _result_refusal(target, result_started_at, result_before)
            reason = _result_reason(refusal)
            exit_code = _exit_code(completed, refusal)
            if reason:
                _log.info("%s refused the job: %s", setup.name, reason)
                output = "\n".join(part for part in (output, reason) if part)
            # Ein bekannter Bauraumgrund hat Vorrang vor dem Absturzstatus.
            # Ohne belegte Ursache nennt der Status weiterhin nur den Absturz.
            # Der Rückgabewert gehört ins Protokoll, nicht in den Satz: Unter
            # Windows kam -50 als 4294967246 beim Kunden an (KUNDE-09).
            _log.info(
                "%s ended without a print file, exit code %d",
                setup.name,
                signed_exit_code(exit_code),
            )
            if _says_outside_the_volume(output):
                raise _outside_the_volume(setup, profile, output, model_height)
            if refusal is None and crashed(exit_code, wrapped=_wrapped(setup)):
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
            if setup.flavour == "orca" and orca_refused(exit_code, ORCA_OFF_THE_PLATE):
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
            if setup.flavour == "orca" and orca_refused(exit_code, ORCA_PATHS_CROSS):
                # OrcaSlicer sagt dazu auf der Konsole nur „found error“, Creality
                # Print nennt im Protokoll Turm und Teil, Bambu Studio den Turm in
                # ``result.json``. Der Turm ist der häufigste Fall, nicht der
                # einzige; der Satz nennt beide, die Ausgabe sagt welcher.
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Im Slicer kreuzen sich die Bahnen zweier Teile oder eines Teils "
                        "und des Reinigungsturms. Geben Sie den Teilen mehr Platz, etwa auf "
                        "einer weiteren Platte, oder verschieben Sie den Turm im Slicer."
                    ),
                    values={"output": output},
                    suggestions=(ARRANGE_ON_BED, EXPORT_ONLY, SHOW_SLICER_OUTPUT),
                )
            if setup.flavour == "orca" and orca_refused(exit_code, ORCA_MIXED_TEMPERATURES):
                # Anycubic Slicer Next sagt auf der Konsole nichts dazu; die Zahl
                # allein ließ den Kunden „keine Druckdatei“ lesen (RM-620).
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Der Slicer druckt diese Filamente nicht zusammen, ihre "
                        "Temperaturbereiche passen in seinen Profilen nicht. Verteilen Sie "
                        "die Teile auf Platten oder wählen Sie andere Filamente."
                    ),
                    values={"output": output},
                    # Anordnen legt verschiedene Filamente auf eigene Platten, wo der
                    # Drucker sie nicht zusammen druckt (``prepare.filament_groups``).
                    suggestions=(ARRANGE_ON_BED, CHOOSE_SLICER, EXPORT_ONLY, SHOW_SLICER_OUTPUT),
                )
            if setup.flavour == "cura" and "failed to load model" in output.casefold():
                raise ExternalToolError(
                    tool=setup.name,
                    title=SLICER_FAILED,
                    detail=_(
                        "Der Slicer konnte eine Modelldatei nicht lesen. "
                        "Übergeben Sie das Modell erneut oder wählen Sie einen anderen Slicer."
                    ),
                    values={"output": output},
                    suggestions=(RETRY, CHOOSE_SLICER, SHOW_SLICER_OUTPUT, EXPORT_ONLY),
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
            # Die Orca-Familie nennt eine leere erste Schicht nicht, sie endet
            # mit -100 und „found error“. Die Geometrie belegt die Ursache:
            # ElegooSlicer an ``Cat_2.stp`` (RM-312), mit Arachne druckte er.
            if setup.flavour == "orca" and _first_layer_narrower_than_a_line(meshes, settings):
                raise _narrow_first_layer_error(setup, {"output": output})
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
            first_layer_error = _empty_first_layer_error(setup, completed.stdout, completed.stderr)
            if first_layer_error is not None:
                if _first_layer_narrower_than_a_line(meshes, settings):
                    raise _narrow_first_layer_error(setup, first_layer_error.values)
                raise first_layer_error
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
        if setup.flavour == "prusa":
            metrics = replace(
                metrics,
                warnings=_merged_warnings(
                    metrics.warnings,
                    _print_warnings(completed.stdout, completed.stderr),
                ),
            )
        produced_path = produced

        # Und die zweite Gegenprobe, an der Geometrie statt an den Werten:
        # steht in dieser Datei ein Druck, der auf das Bett passt?
        def replay_gcode() -> Iterable[str]:
            """Öffnet dieselbe Datei bei Bedarf für die genaue Konturprüfung erneut."""
            with produced_path.open("r", encoding="utf-8", errors="replace") as stream:
                yield from stream

        beyond = off_the_bed(
            analysis,
            profile,
            setup.flavour,
            replay=replay_gcode,
            cancelled=cancelled,
            origin_at_centre=config.origin_at_centre,
            shift=config.machine_shift,
        )
        # Die dritte: Ist überhaupt das ganze Modell darin? ``None`` heißt
        # „der Aufrufer kennt die Höhe nicht" — dann entfällt der Vergleich,
        # er wird nie geraten.
        short = (
            too_short(analysis, model_height, settings, meshes=meshes)
            if model_height is not None
            else None
        )
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
        ignored = verify_settings(
            analysis.settings,
            written,
            cura_machine_differences(analysis, config.cura_machine),
            flavour=setup.flavour,
            program=slicer_keys.program_of(setup.executable),
        )
        if output_dir is None:
            # Der Ordner verschwindet gleich; die Datei muss den Aufrufer noch
            # erreichen können, also wandert sie neben das Modell.
            produced = _kept_beside(models[0], produced, cancelled=cancelled)
        else:
            produced = _copy_print_file(
                produced, output_dir.resolve() / produced.name, cancelled=cancelled
            )

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Ohne Einstellungen: Was nur je nach Wert angenähert ankommt, beurteilt
    # nach dem Slicen die Druckdatei selbst (``fan_in_off_layers``).
    findings = [
        *setting_limitations(setup.flavour),
        *substituted,
        *profile_differences(settings, setup),
        *unknown_keys(settings, profile, setup),
        *unreachable_overrides(settings, setup, slots, profile=profile),
        # **Auch hier und nicht nur beim Export.** Der Befund entstand für
        # ``write_assembly``; der Kunde, der auf *Slicen* klickt, geht aber gar
        # nicht dort vorbei. Sein Lauf gelingt dann mit den Vorgaben des
        # Slicers statt mit den Werten aus Solidon — oder er scheitert, und die
        # Orca-Familie sagt dazu nur „process not compatible with printer".
        *machine_missing(setup, profile),
        *foundation_findings(settings, profile, setup, slots=slots),
        *limited_settings,
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
                    "Dieser Slicer hat die Teile selbst angeordnet, die Plattenbelegung aus "
                    "Solidon gilt für diese Druckdatei nicht."
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
        seconds=time.perf_counter() - started_perf_counter,
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

    **Zurück kommt die Datei, wie sie heißt.** Auf einem Dateisystem ohne
    Unterscheidung der Schreibweise (APFS, NTFS) trifft ``is_file`` auch
    ``Ultimaker-Cura``, wo ``UltiMaker-Cura`` liegt; der zusammengesetzte Name
    war dann ein Pfad, den es so nicht gibt. Gelesen wird deshalb der Ordner.
    """
    names = _WINDOW_SIBLINGS.get(executable.stem.casefold())
    if names is None:
        return executable
    # Im Mac-Bündel liegt Curas Fenster in ``Contents/MacOS``, die
    # Rechenmaschine in ``Contents/Resources`` (``discover.parts_for``).
    bundle = next((parent for parent in executable.parents if parent.suffix == ".app"), None)
    folders = [executable.parent]
    if bundle is not None:
        folders.append(bundle / "Contents" / "MacOS")
    for folder in folders:
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for name in names:
            wanted = name + executable.suffix
            spelled = [entry for entry in entries if entry.name.casefold() == wanted.casefold()]
            # Die genaue Schreibweise zuerst: Auf einem Dateisystem mit
            # Unterscheidung können beide nebeneinander liegen.
            spelled.sort(key=lambda entry: entry.name != wanted)
            found = next((entry for entry in spelled if entry.is_file()), None)
            if found is not None:
                return found
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
    if not discover.is_file_on_host(program):
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


def cura_window_motion(setup: SlicerSetup, profile: Profile) -> Mapping[str, str]:
    """Belegte Grenzen der aktiven Cura-Instanz, auf die das Fenster importiert."""
    if not _cura_base(setup.executable):
        return {}
    active = slicer_profiles.cura_active_machine(setup.executable)
    if active is None:
        return {}
    roots = _profile_roots(setup)
    chosen = slicer_profiles.chosen_machine("cura", setup.executable)
    source = (
        slicer_profiles.profile_by_name(setup.executable, "cura", chosen, "machine")
        if chosen
        else None
    )
    if chosen and source is None:
        raise _cura_instance_error(setup, active.name, missing=False)
    chain = (
        slicer_profiles.resolve_profile(source, roots, cura_motion=True)
        if source is not None
        else slicer_profiles.resolve_values(active.definition, roots, cura_motion=True)
    )
    return _cura_motion_values(chain, {}, profile.printer)


def for_the_cura_window(
    values: Mapping[str, str], *, machine: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Werte in der Schreibweise von Curas Fenster: Wahrheitswerte als
    ``True``/``False``, wie sein eigener Schreiber sie ablegt; die Konsole
    liest ``true``/``false`` (:func:`values_for`)."""
    native = {
        key: value
        for key, value in (machine or {}).items()
        if key.startswith("jerk_") or key.endswith("_jerk")
    }
    limited = _cura_limited_accelerations(native | dict(values), machine or {})
    return {
        key: {"true": "True", "false": "False"}.get(value, value) for key, value in limited.items()
    }


def _without_curas_own_fan_curve(
    values: Mapping[str, str], settings: PrintSettings
) -> dict[str, str]:
    """Das Fenster rechnet unteres Ende und Schwelle der Lüfterkurve selbst (RM-228).

    Die Konsole liest nur Vorgabewerte und bekommt deshalb, was die
    Druckerdefinition sagt (:func:`manufacturer.cura_fan_curve`). Das Fenster
    rechnet Formel und Qualitätsstufe der aktiven Maschine; ein importiertes
    Profil überschriebe sie. Es nennt die beiden deshalb nur als eigene Wahl.
    """
    dropped = {
        slicer_keys.native_key(entry.key, "")
        for entry in slicer_keys.TABLES["cura"]
        if entry.path in manufacturer.CURA_FAN_PATHS and entry.path not in settings.explicit
    }
    return {key: value for key, value in values.items() if key not in dropped}


def cura_profile_beside(
    model: Path,
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    slots: Sequence[MaterialSlot] = (),
    *,
    findings: list[Finding] | None = None,
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
                "In Cura ist kein Drucker eingerichtet, zu dem das Profil passt. Nach dem "
                "Einrichten noch einmal „Im Slicer öffnen“ wählen."
            ),
            values={"slicer": setup.name},
            suggestions=(CHOOSE_SLICER,),
        )
    wanted = float(settings.layers.layer_height)
    quality = min(sorted(qualities), key=lambda kind: abs(qualities[kind] - wanted))
    definition = slicer_profiles.cura_quality_definition(setup.executable, active.definition)
    name = _one_line(model.stem) or "solidon"
    motion = cura_window_motion(setup, profile)

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
        limited = for_the_cura_window(
            _without_curas_own_fan_curve(values, settings), machine=motion
        )
        if findings is not None:
            findings.extend(_cura_limit_findings(values, limited, paths=settings.explicit))
        for key, value in sorted(limited.items()):
            lines.append(f"{key} = {value}")
        return "\n".join(lines) + "\n"

    resolved = settings_for_handover(settings, profile, "cura", slots, setup)
    shared = _cura_accelerations(as_mapping(resolved, "cura"), resolved, profile)
    _without_line_break(shared, setup.name)
    entries = [("solidon", container(shared, None))]
    if len(slots) > 1:
        for position, slot in enumerate(slots):
            resolved = settings_for_slot(settings, profile, slot, setup)
            own = _cura_accelerations(as_mapping(resolved, "cura"), resolved, profile)
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
    }
)


def verify(
    text: str,
    written: Mapping[str, str],
    *,
    flavour: SlicerFlavour | None = None,
    program: str = "",
) -> list[Finding]:
    """Kam an, was Solidon geschrieben hat? (§28.2)

    Die Slicer schreiben ihre wirksame Konfiguration als Kommentare in die
    Druckdatei. Das ist die einzige Auskunft darüber, ob eine Zuordnung
    stimmt — und sie kommt von dem Programm selbst, nicht aus einer
    Dokumentation, die für die installierte Version womöglich nicht gilt.

    Prusa und Orca schreiben vollständige Konfigurationsblöcke: Ein fehlender
    Druckwert wurde nicht übernommen. Ohne bekannte Familie wird nur mit den
    vorhandenen Werten verglichen, etwa bei einem einzelnen Kommentarblock.
    """
    return verify_settings(gcode.analyze(text).settings, written, flavour=flavour, program=program)


def _verification_values(written: Mapping[str, str], program: str) -> Mapping[str, str]:
    """SuperSlicers belegte Lüfterumbenennung, einschließlich ausgeschalteter Plätze.

    In 2.5.59.13 heißt ``min_fan_speed`` intern ``default_fan_speed``;
    ``fan_always_on=0`` setzt diesen Wert auf null (PrintConfig.cpp,
    ``handle_legacy``). Die beiden Prusa-Schlüssel stehen nicht im G-Code.
    """
    if program != "superslicer" or "min_fan_speed" not in written:
        return written
    minimum = re.split(r"[,;]", written["min_fan_speed"].strip().strip("[]"))
    switches = re.split(r"[,;]", written.get("fan_always_on", "1").strip().strip("[]"))
    switches = [value.strip().strip('"') for value in switches]
    if len(switches) != len(minimum) or any(value not in {"0", "1"} for value in switches):
        return written
    native = dict(written)
    native.pop("min_fan_speed")
    native.pop("fan_always_on", None)
    native["default_fan_speed"] = ",".join(
        value.strip().strip('"') if switch == "1" else "0"
        for value, switch in zip(minimum, switches, strict=True)
    )
    return native


#: Nur diese Orca-Materialfelder heben als ``nil`` keine Maschinenvorgabe auf.
_INHERITED_MATERIAL_OVERRIDES: Final = frozenset(
    {"filament_retraction_length", "filament_retraction_speed", "filament_z_hop", "filament_wipe"}
)


def verify_settings(
    found: Mapping[str, str],
    written: Mapping[str, str],
    differences: Sequence[str] = (),
    *,
    flavour: SlicerFlavour | None = None,
    program: str = "",
) -> list[Finding]:
    """Vergleicht bereits ausgelesene Einstellungen mit den geschriebenen.

    ``differences`` sind Abweichungen, die sich nicht als Wert vergleichen
    lassen — bei CuraEngine Maschine und Startcode
    (:func:`cura_machine_differences`). Sie stehen im selben Befund.
    """

    ignored: list[str] = list(differences)
    pairs: list[tuple[str, str, str]] = []
    for key, wanted in _verification_values(written, program).items():
        if key in _RECOMPUTED:
            continue
        if (
            flavour == "orca"
            and key in _INHERITED_MATERIAL_OVERRIDES
            and all(
                value.strip().strip('"') == "nil"
                for value in re.split(r"[,;]", wanted.strip().strip("[]"))
            )
        ):
            continue
        actual = found.get(key.casefold())
        if actual is None:
            if flavour not in {"prusa", "orca"}:
                continue
            if slicer_keys.omitted_from_gcode(key, wanted, program):
                continue
            ignored.append(f"{key}: {wanted} → —")
            pairs.append((key, wanted, "—"))
            continue
        if _same(
            actual,
            wanted,
            unescape_gcode_quotes=key.casefold().endswith("_gcode"),
        ):
            continue
        ignored.append(f"{key}: {wanted} → {actual}")
        pairs.append((key, wanted, actual))

    if not ignored:
        return []
    _log.warning("slicer ignored %d setting(s): %s", len(ignored), "; ".join(ignored[:5]))
    return [
        Finding(
            code="slicer.setting_ignored",
            severity="warning",
            message=_ignored_message(
                len(ignored),
                # Ein Wert vor einem Startcode: der passt in einen Satz.
                min(pairs, key=lambda pair: (pair[0].endswith("_gcode"), pair)) if pairs else None,
                flavour,
            ),
            values={"count": len(ignored), "settings": "; ".join(sorted(ignored)[:10])},
            source="gcode",
            # Der eigene Wert steht im Druckdialog, der des Herstellers im Profil.
            suggestions=(OPEN_PRINT_SETTINGS, CHECK_SLICER_PROFILE),
        )
    ]


#: Wie viele Zeichen eines Werts im Satz der Gegenprobe stehen.
_SHOWN_VALUE: Final = 40


def _ignored_message(
    count: int, first: tuple[str, str, str] | None, flavour: SlicerFlavour | None
) -> TranslatableText:
    """Der Satz der Gegenprobe: was der Slicer statt des Geschriebenen druckt.

    Genannt wird das Feld des Druckdialogs, sonst der Schlüssel des Slicers,
    mit beiden Werten — „anders übernommen“ allein ließ offen, was und wie
    (Anycubic-Matrix, B6).
    """
    if first is None:
        return _("Der Slicer hat Einstellungen anders übernommen, als Solidon sie geschrieben hat.")
    key, wanted, actual = first
    path = next(
        (
            entry.path
            for entry in slicer_keys.TABLES.get(flavour or "other", ())
            if entry.key == key
        ),
        None,
    )
    field = print_fields.field_of(path) if path is not None else None
    setting: TranslatableText | str = field.title if field is not None else key
    # Ein Startcode bleibt in den Werten des Befunds, im Satz steht sein Anfang.
    wanted, actual = (
        text if len(text) <= _SHOWN_VALUE else text[: _SHOWN_VALUE - 1] + "…"
        for text in (wanted, actual)
    )
    if count == 1:
        return _(
            "Der Slicer druckt „{setting}“ mit {actual} statt {wanted}.",
            setting=setting,
            actual=actual,
            wanted=wanted,
        )
    return _(
        "Der Slicer druckt {count} Einstellungen anders als geschrieben, darunter "
        "„{setting}“ mit {actual} statt {wanted}.",
        count=count,
        setting=setting,
        actual=actual,
        wanted=wanted,
    )


def _same(
    actual: str,
    wanted: str,
    *,
    unescape_gcode_quotes: bool = False,
) -> bool:
    """Ob zwei Werte dasselbe meinen.

    Verglichen wird nachsichtig: ``0.2`` und ``0.20``, ``15%`` und ``15``,
    eine Liste aus einem Element gegen dieses Element. Nur bei G-Code-Werten
    werden maskierte Anführungszeichen mit ihrer Schreibweise im G-Code
    verglichen. Sonst meldete die Gegenprobe Unterschiede, die keine sind,
    und würde nach dem dritten Mal weggesehen.
    """
    if unescape_gcode_quotes:
        actual = actual.replace(r"\"", '"')
        wanted = wanted.replace(r"\"", '"')
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
#: Der Rückgabewert, mit dem die Orca-Familie eine fertig geschnittene Platte
#: verwirft, weil sich Bahnen kreuzen (Bambus ``CLI_GCODE_PATH_CONFLICTS``).
#: Gemessen an chufang.3mf (Slicer-Matrix RM-312): OrcaSlicer 2.4 und Creality
#: Print 7.3 nach eigener Anordnung, Reinigungsturm gegen ein Teil.
ORCA_PATHS_CROSS: Final = -101
#: Der Rückgabewert, mit dem die Orca-Familie Filamente mit zu weit
#: auseinanderliegenden Temperaturen auf einer Platte ablehnt (Orcas
#: ``CLI_FILAMENTS_DIFFERENT_TEMP``). Gemessen an Anycubic Slicer Next 2.0 mit
#: PLA und PETG am Kobra 2 (RM-620); ElegooSlicer, OrcaSlicer, Bambu Studio und
#: Creality Print rechneten dieselbe Platte. Ab OrcaSlicer 2.4.2 heißt derselbe
#: Code auch „ungültiger empfohlener Düsentemperaturbereich“ — das Urteil
#: gehört dem Slicer und seinen Profilen.
ORCA_MIXED_TEMPERATURES: Final = -62
#: Der Titel, wenn der Slicer gelaufen ist und keine brauchbare Druckdatei
#: hinterließ. ``ExternalToolError`` sagt sonst „hat nicht geantwortet" — der
#: Slicer hat aber geantwortet, nur mit einem Fehler.
SLICER_FAILED: Final = _("Der Slicer hat den Auftrag nicht gerechnet.")


def _refuses_option(output: str, option: str) -> bool:
    """Erkennt eine ausdrückliche Ablehnung der CLI-Option, keinen Druckfehler."""
    return any(
        option in line
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


def _outside_the_volume(
    setup: SlicerSetup, profile: Profile, output: str, model_height: float | None
) -> ExternalToolError:
    """Die Absage „außerhalb des Bauraums", mit dem Grund, den Solidon kennt.

    PrusaSlicer sagt denselben Satz, gleich ob ein Teil neben dem Bett liegt
    oder zu hoch ist. Am Minigolf-Auftrag auf dem MINI war es ein Teil von
    200 mm bei 180 mm Bauhöhe (27.09.2026), und der Rat „Anordnen" half dort
    nicht. Ist das höchste Teil höher als der Bauraum, sagt die Meldung das
    und bietet Teilen, Verkleinern und einen anderen Drucker an.
    """
    limit = profile.printer.build_volume[2]
    if model_height is not None and model_height > limit + EPS_GEOM:
        return ExternalToolError(
            tool=setup.name,
            title=SLICER_FAILED,
            detail=_("Ein Teil ist höher, als dieser Drucker drucken kann."),
            values={"output": output, "height_mm": model_height, "limit_mm": limit},
            suggestions=(SPLIT_MODEL, SCALE_TO_FIT, CHOOSE_PRINTER, SHOW_SLICER_OUTPUT),
        )
    return ExternalToolError(
        tool=setup.name,
        title=SLICER_FAILED,
        detail=_("Der Slicer sagt, die Teile liegen außerhalb seines Bauraums."),
        values={"output": output},
        suggestions=(ARRANGE_ON_BED, SCALE_TO_FIT, SHOW_SLICER_OUTPUT),
    )


def _empty_first_layer_error(setup: SlicerSetup, *streams: bytes) -> ExternalToolError | None:
    """Ordnet die native Erstschichtabsage ihrem unveränderten Exportnamen zu.

    Der Prozess begrenzt die gesamte Ausgabe bereits auf SLICER_OUTPUT_LIMIT.
    Namen werden vor der Kürzung und nur im selben Ausgabestrom gelesen.
    Mehrere verschiedene oder unlesbare Namen erlauben keine Objektbindung.
    """
    if setup.flavour != "prusa":
        return None
    cause = b"There is an object with no extrusions in the first layer."
    prefix = b"Object name: "
    names: set[str | None] = set()
    for stream in streams:
        lines = stream.splitlines()
        for index, line in enumerate(lines):
            if line.strip() != cause:
                continue
            name = None
            if index + 1 < len(lines) and lines[index + 1].startswith(prefix):
                raw_name = lines[index + 1][len(prefix) :]
                with suppress(UnicodeDecodeError):
                    name = raw_name.decode("utf-8") or None
            names.add(name)
    if not names:
        return None
    part_name = next(iter(names)) if len(names) == 1 else None
    values: dict[str, Any] = {
        "constraint": "empty_first_layer",
        "field": "adhesion.kind",
        "output": "\n".join(
            stream.decode("utf-8", errors="replace") for stream in streams if stream
        ),
    }
    if part_name is not None:
        values["part_name"] = part_name
        detail = _(
            "Die erste Schicht des Teils „{name}“ ist leer. Setzen Sie das Teil "
            "auf das Bett oder prüfen Sie Brim, Raft und die Höhe der ersten Schicht.",
            name=part_name,
        )
    else:
        detail = _(
            "Die erste Schicht eines Teils ist leer. Prüfen Sie die Lage auf dem "
            "Bett sowie Brim, Raft und die Höhe der ersten Schicht."
        )
    return ExternalToolError(
        tool=setup.name,
        title=SLICER_FAILED,
        detail=detail,
        values=values,
        suggestions=(
            SHOW_LOCATIONS,
            PLACE_ON_BED,
            replace(OPEN_PRINT_SETTINGS, label=_("Brim oder Raft prüfen …")),
            SHOW_SLICER_OUTPUT,
        ),
    )


def _first_layer_narrower_than_a_line(meshes: Sequence[Mesh], settings: PrintSettings) -> bool:
    """Trägt die erste Schicht eines Teils keine Bahn fester Breite?

    Gefragt am Querschnitt auf halber Höhe der ersten Schicht: Ist das Teil
    dort nirgends anderthalb Erstschichtbahnen breit (nach innen um drei
    Viertel einer Bahn versetzt bleibt nichts), schließen Wände mit fester
    Bahnbreite (``classic``) keine Schleife, und der Slicer sagt ab. Gemessen
    an ``Cat_2.stp`` (Slicer-Matrix RM-312): bei 0,1 mm 79 mm² Fläche in
    Stegen von höchstens 0,6 mm; ElegooSlicer (Erstschichtbahn 0,5 mm) endete
    mit -100, SuperSlicer (0,42 mm) mit „no extrusions in the first layer“,
    beide druckten mit Arachne. Mit veränderlicher Bahnbreite ist das keine
    belegte Ursache. Gefragt wird erst nach einer Absage.
    """
    if settings.shell.wall_generator != "classic":
        return False
    from app.core.slice.analysis import cross_sections

    inset = 0.75 * settings.layers.first_layer_line_width
    for mesh in meshes:
        data = as_mesh_data(mesh)
        if not data.triangle_count:
            continue
        height = float(data.bounds.minimum[2]) + settings.layers.first_layer_height / 2.0
        section = cross_sections(data, [height])[0]
        if section is None or section.buffer(-inset).is_empty:
            return True
    return False


def _narrow_first_layer_error(setup: SlicerSetup, values: Mapping[str, Any]) -> ExternalToolError:
    """Die Absage einer ersten Schicht, die schmaler ist als eine Bahn — mit dem Weg dorthin.

    Dieselbe Bindung wie :func:`_empty_first_layer_error` (``constraint``,
    ``part_name``), aber das Feld ist die Wandbahn: Auf das Bett legen hilft
    einem Teil nicht, das darauf liegt.
    """
    part_name = values.get("part_name")
    detail = (
        _(
            "Die erste Schicht des Teils „{name}“ ist schmaler als eine Bahn; mit fester "
            "Bahnbreite legt der Slicer dort nichts. Stellen Sie die Wandbahnen auf Arachne "
            "oder geben Sie dem Teil einen Raft.",
            name=part_name,
        )
        if isinstance(part_name, str)
        else _(
            "Die erste Schicht eines Teils ist schmaler als eine Bahn; mit fester Bahnbreite "
            "legt der Slicer dort nichts. Stellen Sie die Wandbahnen auf Arachne oder geben "
            "Sie dem Teil einen Raft."
        )
    )
    return ExternalToolError(
        tool=setup.name,
        title=SLICER_FAILED,
        detail=detail,
        values={**values, "constraint": "empty_first_layer", "field": "shell.wall_generator"},
        suggestions=(
            SHOW_LOCATIONS,
            replace(OPEN_PRINT_SETTINGS, label=_("Wandbahnen prüfen …")),
            SHOW_SLICER_OUTPUT,
        ),
    )


def _says_outside_the_volume(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass nichts im Bauraum liegt?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in OUTSIDE_THE_VOLUME)


def _says_no_layers(output: str) -> bool:
    """Sagt die Ausgabe des Slicers, dass keine druckbare Schicht entstand?"""
    lowered = output.lower()
    return any(phrase in lowered for phrase in NO_LAYERS)


def orca_refused(exit_code: int, code: int) -> bool:
    """Hat die Orca-Familie mit diesem Fehlercode abgelehnt — auf jeder Plattform?

    Ihr Programm endet mit ``return CLI().run(...)``: Windows liefert den
    Rückgabewert als DWORD (-62 als 4294967234), Linux und macOS als Byte (194).
    Mit :func:`signed_exit_code` allein griff die Erkennung dort nie (RM-620).
    """
    return exit_code in {code, code & 0xFFFFFFFF, code & 0xFF}


def signed_exit_code(exit_code: int) -> int:
    """Ein Rückgabewert mit Vorzeichen — Windows liefert ``-50`` als DWORD 4294967246."""
    return exit_code - (1 << 32) if exit_code >= (1 << 31) else exit_code


#: Signale, an denen ein Programm stirbt, statt aufzugeben: SIGILL, SIGABRT,
#: SIGBUS, SIGFPE, SIGKILL und SIGSEGV in Linux' Zählung — einen Starter, der
#: einen Signaltod als 128 + Signal meldet, gibt es nur dort.
_FATAL_SIGNALS: Final = frozenset({4, 6, 7, 8, 9, 11})


def crashed(exit_code: int, *, wrapped: bool = False) -> bool:
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

    **Hinter einem Starter** (``wrapped``, :func:`_wrapped`) kommt ein
    Signaltod als 128 + Signal an: ``flatpak run`` endet in bwrap
    (``bubblewrap.c``, ``propagate_exit_status``), ``flatpak-spawn --host``
    ebenso (``flatpak-spawn.c``). Ein SIGSEGV käme dort als 139 an, und der
    Kunde läse „keine Druckdatei geschrieben“ (RM-621, am Quelltext
    hergeleitet). **Gezählt werden nur die Signale, an denen ein Programm
    stirbt** (:data:`_FATAL_SIGNALS`): Die Orca-Absagen reichen von -1 bis -105
    (``src/libslic3r/Utils.hpp`` der fünf Programme), in Byteform 151 bis 255,
    und manche davon sind genau 128 + Signal — -100 kommt als 156, also
    128 + SIGWINCH.
    """
    if exit_code < 0:
        return True
    if wrapped and exit_code - 128 in _FATAL_SIGNALS:
        return True
    # MS-ERREF §2.3: Schwere 11, N-Bit 0; das Customer-Bit bleibt frei,
    # damit auch nicht abgefangene C++-Ausnahmen (0xE06D7363) erkannt werden.
    return exit_code <= 0xFFFFFFFF and exit_code & 0xD0000000 == 0xC0000000


def _wrapped(setup: SlicerSetup) -> bool:
    """Startet der Slicer hinter ``flatpak run`` oder ``flatpak-spawn --host``?

    Dann meldet der Starter einen Signaltod als 128 + Signal
    (:func:`crashed`): ein Slicer als Flatpak oder Solidon selbst im Flatpak,
    das jeden Start über :func:`discover.on_host` nach draußen reicht. Das
    ist dieselbe Frage wie die nach der Sandbox (:func:`discover.sandboxed`):
    Ein Flatpak auf einer der beiden Seiten ist zugleich Sandbox und Starter.
    """
    return discover.sandboxed(setup.executable)


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


def _result_reason(refusal: tuple[int, str] | None) -> str:
    """Was der Slicer in ``result.json`` über einen gescheiterten Lauf sagt.

    **Bambu Studio sagt seine Absage nicht auf der Konsole.** Gemessen an
    Version 2.3 (RM-163, Durchsicht 0.5.0): Ein Projekt für einen Drucker, den
    Bambu nicht kennt, endet mit Rückgabewert -17 und leerer Ausgabe; der
    Grund steht nur hier — „The selected printer is not compatible with the
    process preset in the 3mf." Der Kunde las „Der Slicer hat keine
    Druckdatei geschrieben", und *Ausgabe des Slicers anzeigen* zeigte ein
    leeres Feld. Orca und Elegoo schrieben die Datei bei denselben Fehlern
    nicht; für sie ändert sich nichts.

    Gelesen von :func:`_result_refusal`; ohne Grund im Text sagt sie nichts.
    """
    if refusal is None or not refusal[1]:
        return ""
    code, text = refusal
    return f"{text} (return_code {code})"


def _result_refusal(
    directory: Path, since: float, before: tuple[int, int] | None
) -> tuple[int, str] | None:
    """Rückgabewert und Grund einer Absage aus der ``result.json`` dieses Laufs
    (:func:`_result_reason`); ``None`` ohne Absage.

    Nur eine Datei dieses Laufs zählt (Änderungszeit ab ``since``) — der
    Zielordner kann der des Kunden sein, mit dem Ergebnis eines älteren
    Laufs —, und nur eine, die dieser Versuch geschrieben hat: ``before`` ist
    ihre Signatur vor seinem Start (:func:`_result_signature`). Beim zweiten
    Versuch ohne Anordnungsvorgabe liegt sonst die Absage des ersten daneben
    und gälte für ihn. Nur eine Absage zählt (``return_code`` ungleich null);
    was sich nicht lesen lässt, sagt nichts.
    """
    path = directory / RESULT_FILE
    if _result_signature(directory) == before:
        return None
    try:
        info = path.stat()
        if info.st_mtime < since - _MTIME_SLACK_S or info.st_size > _RESULT_LIMIT:
            return None
        data = json.loads(path.read_bytes())
    except OSError, ValueError:
        return None
    if not isinstance(data, dict):
        return None
    code = data.get("return_code")
    text = data.get("error_string")
    if not isinstance(code, int) or isinstance(code, bool) or code == 0:
        return None
    return code, text.strip() if isinstance(text, str) else ""


def _exit_code(
    completed: subprocess.CompletedProcess[bytes], refusal: tuple[int, str] | None
) -> int:
    """Der Rückgabewert, nach dem ein Lauf ohne Druckdatei beurteilt wird.

    Steht eine Absage in der ``result.json`` dieses Laufs
    (:func:`_result_refusal`), zählt ihr Code, und ein Absturz ist es nicht:
    Endet der Slicer danach nicht, beendet Solidon ihn
    (``process.FINISHED_LINGER_SECONDS``), und der Prozess meldet Solidons
    Signal — :func:`crashed` hielt das für einen Absturz, und die Absage ging
    unter.
    """
    return completed.returncode if refusal is None else refusal[0]


def _result_written(directory: Path) -> Callable[[], bool]:
    """Die Frage, ob der Slicer die ``result.json`` dieses Laufs abgelegt hat.

    Bambu Studio schreibt sie als Letztes, nach der Druckdatei — auch bei
    einer Absage (:func:`_result_reason`). Gefragt wird nach einer **anderen**
    Datei als der beim Start: Der Zielordner kann der des Kunden sein, mit
    dem Ergebnis eines älteren Laufs, und beim zweiten Versuch ohne
    Anordnungsvorgabe liegt die des ersten daneben. Halb geschrieben zählt sie
    nicht — erst, wenn sie sich als JSON mit ``return_code`` lesen lässt.
    """
    path = directory / RESULT_FILE
    before = _result_signature(directory)

    def written() -> bool:
        now = _result_signature(directory)
        if now is None or now == before or not 0 < now[1] <= _RESULT_LIMIT:
            return False
        try:
            data = json.loads(path.read_bytes())
        except OSError, ValueError:
            return False
        return isinstance(data, dict) and isinstance(data.get("return_code"), int)

    return written


def _result_signature(directory: Path) -> tuple[int, int] | None:
    """Änderungszeit und Größe der ``result.json`` in diesem Ordner, ``None`` ohne sie."""
    try:
        info = (directory / RESULT_FILE).stat()
    except OSError:
        return None
    return info.st_mtime_ns, info.st_size


def _warning_boundary(line: str) -> bool:
    """Die Steuerzeilen der nativen Prusa-Kommandozeile."""
    return (
        re.match(r"^(?:print(?:_object)? warning:|\d+ => |Slicing result exported to )", line)
        is not None
    )


def _print_warnings(*streams: bytes) -> tuple[str, ...]:
    """Warnblöcke vollständig aus dem gemeinsamen Prozessbudget lesen.

    Prusas Stabilitätsmeldung enthält je Absatz zwei freie Zeilen: Objekt
    und Ursachen oder Ursache und Objektliste. Beide sind Nutztext, auch
    wenn ein Name wie eine Fortschrittszeile heißt. Erst außerhalb dieser
    Absätze begrenzen Steuerzeilen den Block. Das Format kommt aus
    ``Print.cpp`` / ``PrintBase.cpp`` von PrusaSlicer 2.9.6.
    """
    warnings: list[str] = []
    remaining = SLICER_OUTPUT_LIMIT
    lines: list[str] = []

    def finish() -> None:
        warning = "\n".join(lines).strip()
        if warning:
            warnings.append(warning)
        lines.clear()

    for stream in streams:
        text = stream[:remaining].decode("utf-8", errors="replace")
        remaining -= min(len(stream), remaining)
        output = text.replace("\r\n", "\n").split("\n")
        active = False
        stability = False
        opaque = 0
        for index, line in enumerate(output):
            if active and opaque:
                lines.append(line)
                opaque -= 1
                continue
            start = re.match(r"^print(?:_object)? warning: ?(.*)$", line)
            if start is not None:
                finish()
                lines.append(start.group(1))
                active = True
                stability = start.group(1) == "Detected print stability issues:"
            elif _warning_boundary(line):
                finish()
                active = False
                stability = False
            elif active:
                lines.append(line)
                if stability and not line:
                    following = output[index + 1 : index + 3]
                    # Die Schlusszeile ist frei stehender Rat. Ein gleich
                    # benanntes Objekt hat danach noch seine Ursachenzeile.
                    closing = bool(
                        following
                        and following[0] == "Consider enabling supports."
                        and (
                            len(following) == 1
                            or not following[1]
                            or following[1] == "Also consider enabling brim."
                            or _warning_boundary(following[1])
                        )
                    )
                    if closing:
                        stability = False
                    else:
                        opaque = 2
        finish()
    return tuple(warnings)


def _merged_warnings(*groups: Sequence[str]) -> tuple[str, ...]:
    """Vollständige Blöcke behalten, ihre kurzen Kommentare ersetzen.

    Leerraum innerhalb von Namen bleibt bedeutend. Zwei verschiedene
    mehrzeilige Texte werden nie über ihre flache Schreibweise vereinigt.
    Nur ein einzeiliger Kommentar darf dem vollständigen Block weichen.
    """
    unique = dict.fromkeys(
        warning.replace("\r\n", "\n").strip() for group in groups for warning in group
    )
    summaries = {
        summary
        for warning in unique
        if "\n" in warning
        for summary in (
            warning.split("\n", 1)[0],
            " ".join(line for line in warning.split("\n") if line),
        )
    }
    return tuple(
        warning for warning in unique if warning and ("\n" in warning or warning not in summaries)
    )


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
    return _copy_print_file(produced, model.with_suffix(".gcode"), cancelled=cancelled)


def _copy_print_file(produced: Path, target: Path, *, cancelled: CancelToken | None = None) -> Path:
    """Kopiert vollständig und abbrechbar, bevor die Zieldatei ersetzt wird."""
    temporary: Path | None = None
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
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


def _output_files(directory: Path) -> dict[Path, tuple[int, int]]:
    """Bestand vor einem Versuch, einschließlich leerer angefangener Dateien."""
    outputs = {}
    for entry in directory.iterdir():
        if entry.is_file() and (
            entry.suffix.casefold() in GCODE_SUFFIXES or entry.name == RESULT_FILE
        ):
            info = entry.stat()
            outputs[entry] = info.st_mtime_ns, info.st_size
    return outputs


def _find_gcode(
    directory: Path,
    expected: str = "",
    *,
    before: Mapping[Path, tuple[int, int]] | None = None,
    tool: str = "Slicer",
) -> Path | None:
    """Genau eine neue Druckdatei, nie eine Auswahl aus mehreren Platten.

    Jeder Versuch hat seinen eigenen Vorbestand. Reste einer Absage oder
    fremde alte Dateien zählen weder als Erfolg noch als weitere Platte.
    ``result.json`` kann mehrere Platten auch dann belegen, wenn nur noch
    eine Druckdatei auffindbar ist. Ohne diesen Beleg bleibt mehr als eine
    neue Druckdatei ebenfalls uneindeutig — auch bei gleichem Inhalt.
    """
    outputs = {
        entry: signature
        for entry, signature in _output_files(directory).items()
        if before is None or before.get(entry) != signature
    }
    result_path = directory / RESULT_FILE
    plate_count = 0
    if result_path in outputs and outputs[result_path][1] <= _RESULT_LIMIT:
        try:
            result = json.loads(result_path.read_bytes())
        except OSError, ValueError:
            result = None
        if isinstance(result, dict) and isinstance(result.get("return_code"), int):
            if result["return_code"] != 0:
                return None
            plates = result.get("sliced_plates")
            if isinstance(plates, list):
                plate_count = len(plates)
    # Leer zählt nicht: Cura legt die Zieldatei schon vor dem Rechnen an.
    candidates = [
        entry
        for entry, signature in outputs.items()
        if entry.suffix.casefold() in GCODE_SUFFIXES and signature[1] > 0
    ]
    if len(candidates) > 1 or plate_count > 1:
        raise ExternalToolError(
            tool=tool,
            title=SLICER_FAILED,
            detail=_(
                "Der Slicer hat mehrere Druckdateien oder Druckplatten ausgegeben. "
                "Solidon kann daraus keine einzelne vollständige Druckdatei übernehmen. "
                "Ordnen Sie die Teile neu an oder öffnen Sie die exportierten Modelle im Slicer."
            ),
            suggestions=(ARRANGE_ON_BED, EXPORT_ONLY, CANCEL),
        )
    if not candidates:
        return None
    if expected and candidates[0].name != expected:
        _log.warning(
            "the slicer wrote no %s in %s — using its only new print file",
            expected,
            directory,
        )
    return candidates[0]
