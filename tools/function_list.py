"""Die Funktionsliste des Funktionsdurchgangs (Konzept §3 und §6, RM-737).

Erzeugt, nicht geschrieben: Jede Zeile kommt aus einer Quelle, die die
Anwendung selbst benutzt, und trägt eine stabile Kennung. Ein Qt-Fenster
entsteht hier nicht; Module aus ``app/ui`` werden nur importiert.

* **Operationen** aus dem Register nach ``load_operations()``. Die Kacheln des
  Bausteinkatalogs (``registry.surfaces.catalogue_operations``) sind **eine**
  Zeile ``part:*`` mit einem Lauf über alle (Konzept §3).
* **Bedienflächen**: die Dialog- und Fensterklassen unter ``app/ui``
  (rekursiv gelesen, transitiv über eigene Basen), die festen Ziele des
  Wortschatzes (``guides.TARGETS``), die Handlungen der Befunde
  (``panels.FINDING_ACTIONS``), der Hauptaktion *Modell nachbauen*
  (``selection_operations.REBUILD``) und die Einträge des Kontextmenüs im
  Verlauf (Objektnamen ``history.*``).
* **Fensterbefehle** entstehen erst mit der Menüleiste am gebauten Fenster;
  der Prüfstand liest sie dort und gibt sie :func:`command_rows`.

Dazu je Zeile das Paket (Konzept §6), die Anforderung an die Startszene und die
Szene aus ``tests/data/function_scenes.toml`` (Bauplan D0 §2.5). Eine Zeile,
die keinem Paket zugeordnet werden kann, und eine Operation, deren Anforderung
keine Szene hat, sind Fehler: Sie halten die Liste an, statt still zu fehlen.

Den Quelltext der Oberfläche liest ``tools/function_scan.py``, den Szenenkatalog
liest, baut und prüft ``tools/function_scenes.py``.

    python tools/function_list.py --paket D4 --format md
    python tools/function_list.py --check
    python tools/function_list.py --szenen --out <ordner außerhalb des Baums> [--schwer]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.function_scan import UiScan, scan_ui, statements  # noqa: E402
from tools.function_scenes import (  # noqa: E402
    DATA,
    EXACT,
    MESH,
    FunctionListError,
    Scene,
    load_scenes,
    registry,
    save_scenes,
    validate_scenes,
)

if TYPE_CHECKING:
    from app.core.registry import OperationSpec, Registry

UI: Final = ROOT / "app" / "ui"
#: Klassen, deren Module eine Suche unter ``app/ui`` finden muss: das Hauptfenster, die
#: Ansicht und ein Dialog. Fehlt eines, prüft die Liste nichts — eine Zählprobe bliebe
#: dabei grün, auch wenn gerade die größte Datei fehlt.
UI_CLASSES: Final[tuple[str, ...]] = ("MainWindow", "Viewport", "SettingsDialog")
ROW_SPECS: Final = DATA / "function_rows"

PACKAGES: Final[tuple[str, ...]] = tuple(f"D{number}" for number in range(1, 13))
ROW_KINDS: Final[tuple[str, ...]] = ("operation", "fensterbefehl", "bedienflaeche")
ROW_SOURCES: Final[tuple[str, ...]] = (
    "register",
    "menueleiste",
    "dialogklasse",
    "wortschatz",
    "befundhandlung",
    "merkmalfenster",
    "verlauf",
    "fensteraktion",
    "startablauf",
    "werkzeugzeile",
    "kontextmenue",
    "einstellungen",
    "meldungsfenster",
)

#: Die Zeile, die für alle Kacheln des Bausteinkatalogs steht (Konzept §3).
CATALOGUE_ROW: Final = "part:*"
#: Der erste Eintrag unter „Zuletzt geöffnet“ auf dem Startbildschirm — eine Zeile
#: für die Liste (``start.recent:<n>``).
RECENT_ROW: Final = "start.recent:1"
#: Die Hauptaktion *Modell nachbauen* (``selection_operations.REBUILD``).
REBUILD_ROW: Final = "selection.rebuild"

# --- Paketzuordnung (Konzept §6) ------------------------------------------------

#: Paket je Kategorie des Registers. Jede Kategorie aus ``CATEGORIES`` steht
#: hier; eine neue ohne Eintrag hält die Liste an.
CATEGORY_PACKAGES: Final[dict[str, str]] = {
    "import": "D1",
    "export": "D1",
    "primitive": "D2",
    "parts": "D2",
    "variants": "D2",
    "boolean": "D3",
    "transform": "D3",
    "shaping": "D3",
    "surface": "D3",
    "holes": "D4",
    "repair": "D5",
    "mesh": "D5",
    "sketch": "D7",
    "scene": "D8",
    "prepare": "D8",
    "colour": "D10",
    "label": "D10",
    "fits": "D10",
    "parameters": "D10",
}

#: Die einzige Ausnahme von der Kategorie: Operationen mit Gestenparameter —
#: Formen und Skelett — prüft D6 mit eigenen Leisten und eigenem Rückgängig.
GESTURE_KINDS: Final[frozenset[str]] = frozenset({"strokes", "armature"})
GESTURE_PACKAGE: Final = "D6"

#: Dialogklassen, die genau einer Operation dienen: Sie gehen mit ihr in deren
#: Paket und übernehmen ihre Anforderung (Konzept §6). Gelesen wird nach
#: Klassenname, nicht nach Modulpfad, damit ein Umzug in ein Paket nichts ändert.
DIALOG_OPERATIONS: Final[dict[str, str]] = {
    # Der Dichtweg ist ein eigener Editor nur für ``create_seal`` (op_dialog: SealPathField).
    "SealPathDialog": "create_seal",
    # Konturauswahl beim Import einer flachen Zeichnung (``contours``).
    "OutlineDialog": "load_outline",
    # Körperwahl einer STEP-Baugruppe (``step_bodies``).
    "StepBodiesDialog": "load_step",
    # Örtliche Erkennung um eine angeklickte Stelle.
    "LocalRecognitionDialog": "detect_region",
    # Fachaufteilung des Organizers (``organizer``).
    "OrganizerDialog": "create_organizer",
}

#: Die übrigen Dialogklassen nach ihrem Bereich: Paket und Anforderung an die
#: Startszene. Eine Klasse, die hier und in :data:`DIALOG_OPERATIONS` fehlt,
#: hält die Liste an — eine Zeile nachtragen.
DIALOG_SURFACES: Final[dict[str, tuple[str, str]]] = {
    "MainWindow": ("D12", "leer"),
    "OperationDialog": ("D12", "koerper:1"),
    "AskDialog": ("D12", "leer"),
    "AiDisclosureDialog": ("D12", "leer"),
    "LocalPrivacyDialog": ("D12", "leer"),
    "PrintDisclosureDialog": ("D12", "leer"),
    "FirstRunDialog": ("D12", "start"),
    "InstallDialog": ("D12", "leer"),
    "KeyDialog": ("D12", "leer"),
    "ActivationDialog": ("D12", "leer"),
    "OfflineActivationDialog": ("D12", "leer"),
    "SettingsDialog": ("D12", "leer"),
    "ShortcutsWindow": ("D12", "leer"),
    "ManualWindow": ("D12", "leer"),
    "SupportDialog": ("D12", "leer"),
    "UpdateDialog": ("D12", "leer"),
    "ChangesDialog": ("D12", "leer"),
    "DonationDialog": ("D12", "leer"),
    # Eine Meldung mit eigenem Ausweg (Zahlungslink kopieren).
    "DonationOpenErrorDialog": ("D12", "leer"),
    # Die Meldung im Hausstil (FD-21): Fehler, Einzelheiten, Hinweise. Ihre
    # Fenster tragen ``message:<sache>`` wie zuvor die rohen.
    "MessageDialog": ("D12", "leer"),
    # Die Eingabe im Hausstil (FD-22): Modelladresse, Dienstadresse. Ihre Fenster
    # tragen ``message:<sache>`` wie zuvor die rohen ``QInputDialog``.
    "InputDialog": ("D12", "leer"),
    "AboutDialog": ("D12", "leer"),
    "PartCatalog": ("D2", "leer"),
    "GenerateDialog": ("D2", "leer"),
    "ComfySetupDialog": ("D2", "leer"),
    "VariantsDialog": ("D2", "koerper:1"),
    "RebuildDialog": ("D2", "koerper:1"),
    "SketchEditorDialog": ("D7", "leer"),
    "ExpressionDialog": ("D7", "leer"),
    "PointDialog": ("D7", "leer"),
    "NewPlaneDialog": ("D7", "leer"),
    "StepValuesDialog": ("D8", "leer"),
    "BodyChoiceDialog": ("D8", "befund"),
    "PrintSettingsDialog": ("D9", "koerper:1"),
    "FilamentOverrideDialog": ("D9", "koerper:1"),
    "SlicerSpoolDialog": ("D9", "leer"),
    "NewFilamentDialog": ("D9", "leer"),
    "UsageDialog": ("D9", "koerper:1"),
    "SlicerFilamentDialog": ("D10", "koerper:1"),
    "ParameterDialog": ("D10", "leer"),
    "BindingDialog": ("D10", "merkmal:hole"),
    "CalibrationDialog": ("D10", "leer"),
    "CounterpartDialog": ("D10", "koerper:2"),
    "RecipeDialog": ("D10", "koerper:1"),
    "_PanelWindow": ("D11", "leer"),
}

#: Feste Ziele des Wortschatzes: Paket und Anforderung, nach dem genauen Namen.
#: Ein festes Ziel ohne Eintrag hält die Liste an.
TARGET_SURFACES: Final[dict[str, tuple[str, str]]] = {
    "tree": ("D11", "koerper:1"),
    "history": ("D11", "koerper:1"),
    "history.last": ("D11", "koerper:1"),
    "viewport": ("D11", "leer"),
    "toolbar": ("D11", "leer"),
    "tools": ("D11", "koerper:1"),
    "selection": ("D11", "koerper:1"),
    "header": ("D12", "leer"),
    "statusbar": ("D12", "leer"),
    "parameters": ("D10", "leer"),
    "parameters.first": ("D10", "parameter"),
    # Der Prüfbericht ist eine Ansicht der Szene, keine Handlung an einer Auswahl:
    # Er braucht einen Körper, aber keinen gewählten (Probelauf F-33, Z3).
    "report": ("D8", "ansicht"),
    "report.action": ("D8", "befund"),
    # Der letzte Meter steht im Bericht und gehört zur Übergabe an den Slicer.
    "report.slicer": ("D9", "koerper:1"),
    "selection.parts": ("D2", "merkmal:face"),
    REBUILD_ROW: ("D2", "koerper:1"),
    "filament.section": ("D10", "koerper:1"),
    "filament.picker": ("D10", "koerper:1"),
    "print.printer": ("D9", "koerper:1"),
    "print.slice": ("D9", "koerper:1"),
    "print.save": ("D9", "koerper:1"),
    "start.drop": ("D1", "start"),
    "start.new": ("D1", "start"),
    "start.model": ("D1", "start"),
    "start.project": ("D1", "start"),
    "start.manual": ("D1", "start"),
    RECENT_ROW: ("D1", "start"),
    "dialog": ("D12", "koerper:1"),
    "dialog.accept": ("D12", "koerper:1"),
    "dialog.naming": ("D12", "koerper:1"),
    "dialog.more": ("D12", "koerper:1"),
    # Die Bewegen-Leiste dient Verschieben, Drehen und Skalieren — alle drei in D3.
    "transform.values": ("D3", "koerper:1"),
    "toolbar.draw": ("D7", "leer"),
    "sketch.done": ("D7", "leer"),
    # Übernehmen, *Im Bild einstellen* und *Auf alle N gleichartigen anwenden*
    # im Merkmalfenster: erkannte Merkmale ändern ist D4.
    "feature.apply": ("D4", "merkmal:hole"),
    "feature.in_view": ("D4", "merkmal:hole"),
    "feature.every": ("D4", "gleichartig"),
    # *Bezug ändern* in der Maßgruppe: Sie setzt Erzeuger und Bausteine auf eine
    # Fläche, und alle Operationen mit Flächenbindung sind D2.
    "measure.reference": ("D2", "merkmal:face"),
    # *Übernehmen* derselben Maßgruppe (D0, N2).
    "measure.apply": ("D2", "merkmal:face"),
    "search": ("D11", "koerper:1"),
    # Chat und Tour, die Seiten der rechten Karte neben Auswahl und Bericht.
    "chat": ("D12", "leer"),
    "tour": ("D12", "leer"),
    "toolbar.search": ("D11", "leer"),
    # *Abbrechen* steht nur während einer langen Rechnung.
    "progress.cancel": ("D12", "langsam"),
    "preview.banner": ("D11", "koerper:1"),
}

#: Wortschatznamen mit Art, die Zeilen tragen: Präfix → Paket und Anforderung.
#: Die erste passende Zeile gilt.
TARGET_PREFIXES: Final[tuple[tuple[str, str, str], ...]] = (
    ("history:", "D11", "koerper:1"),
    ("finding.action:", "D8", "befund"),
)

#: Hauptmenü → Paket der Fensterbefehle darunter (Konzept §6).
MENU_PACKAGES: Final[dict[str, str]] = {
    "Datei": "D1",
    "Bearbeiten": "D11",
    "Erzeugen": "D2",
    "Ansicht": "D11",
    "Hilfe": "D12",
}

#: Fensterbefehle, deren Bereich ein anderes Paket ist als ihr Hauptmenü —
#: nach der Quelle ihrer Menüzeile (die Kennung ist ``menubar_name`` davon).
COMMAND_PACKAGES: Final[dict[str, str]] = {
    "Einstellungen …": "D12",
    "Parameter anlegen …": "D10",
    "Material kalibrieren …": "D10",
    "G-Code gegenprüfen …": "D9",
    "An den Slicer übergeben …": "D9",
    "Filamentlager …": "D9",
    "Bausteinkatalog …": "D2",
    "Modell erzeugen …": "D2",
    "Varianten erzeugen …": "D2",
    "Gegenstücke setzen …": "D10",
    "Chat einrichten …": "D12",
    # Konzept §6 nennt die Beispiele bei D1 (Datei und Projekt).
    "Beispiele": "D1",
}

#: Fensteraktionen in der Auswahlkarte (``SelectionOperationsPanel.add_window_action``):
#: Befehle ohne Registereintrag, die nicht in der Menüleiste stehen, nach ihrer
#: Kennung aus ``window_commands``. *Automatisch teilen* ist ein Ablauf über
#: mehrere Operationen und steht unter *Vorbereiten*.
WINDOW_ACTION_PACKAGES: Final[dict[str, str]] = {
    "edit.auto_split": "D8",
}

#: Die Werkzeuge der Zeile unter der Ansicht (``….tools.add("<schlüssel>", …)``) nach
#: Paket. Bewegen dient Verschieben, Drehen und Skalieren (D3); Teilen, Analyse und
#: Schichten (Schichtanalyse, §22) sind Druckvorbereitung (D8); Schnitt, Messen und
#: Explosion sind Ansicht (D11).
TOOL_PACKAGES: Final[dict[str, str]] = {
    "section": "D11",
    "measure": "D11",
    "transform": "D3",
    "analysis": "D8",
    "layers": "D8",
    "explode": "D11",
    "split": "D8",
}

#: Benannte Kontextaktionen von Baum und Parameterleiste (W's Objektnamen) nach
#: Paket und Anforderung. *Auf dieser Fläche zeichnen* führt in den Zeichenmodus (D7).
CONTEXT_PACKAGES: Final[dict[str, tuple[str, str]]] = {
    # *Diesen Schritt ändern* steht an einem erzeugten Merkmal (panels: Baumkontext).
    "tree.step": ("D11", "merkmal:hole"),
    "tree.sketch": ("D7", "merkmal:face"),
    "tree.visibility": ("D11", "koerper:1"),
    "tree.isolate": ("D11", "koerper:2"),
    "parameters.edit": ("D10", "parameter"),
}

SETTINGS_PACKAGE: Final = "D12"


#: Funktionen, die ein Meldungsfenster bauen — roh oder im Hausstil (``MessageDialog``) —,
#: beim Namen (Zeile ``meldung:<name>``; eine Kennung nennt die Sache, nie ihr Modul),
#: nach Paket und Anforderung. Konzept §6:
#: Wiederherstellen und Speicherfrage in D1, die Löschnachfrage im Verlauf (Ausnahme zu
#: Regel 19) in D11.
RAW_WINDOW_PACKAGES: Final[dict[str, tuple[str, str]]] = {
    "open_link": ("D12", "leer"),
    "show_expired_demo": ("D12", "start"),
    "show_error": ("D12", "leer"),
    "show_details": ("D12", "leer"),
    "confirm_unsaved": ("D1", "koerper:1"),
    # Die Vorabfrage mit Befunden vor Export und Übergabe (confirm_export,
    # confirm_handover); der Export ist D1, die Übergabe prüft D9 am Druckdialog.
    "_go_on_despite": ("D1", "koerper:1"),
    "confirm_generation_loss": ("D2", "leer"),
    "confirm_discard": ("D11", "koerper:1"),
    "_pick_colour": ("D10", "koerper:1"),
    "_replacement_slot": ("D10", "koerper:1"),
    "_choose_address": ("D12", "leer"),
    "_show_details": ("D12", "leer"),
    "action_import_url": ("D1", "leer"),
    "remove_history_operations": ("D11", "koerper:1"),
    "_assign_inventory_spool": ("D9", "koerper:1"),
    "action_counterpart": ("D10", "koerper:2"),
    "_ask_recovery": ("D1", "start"),
    "_choose": ("D9", "koerper:1"),
    "_show_slicer_output": ("D9", "koerper:1"),
    "change_constraint_value": ("D7", "leer"),
}
#: Kennungen, die nicht ``meldung:<name>`` heißen. „Demo abgelaufen“ (``over``)
#: startet die Anwendung nicht — eine eigene Zeile des Startablaufs, kein Lauf je
#: Funktion; U liest sie unter diesem Namen.
RAW_WINDOW_IDS: Final[dict[str, str]] = {"show_expired_demo": "startup.expired_demo"}

# --- Anforderung und Szene (Bauplan D0 §2.5) ----------------------------------

#: Merkmalsarten, die es nur am Netz gibt: Ein exakter Körper ist immer
#: geschlossen, eine offene Randkante hat er nicht.
MESH_ONLY_KINDS: Final[frozenset[str]] = frozenset({"edge_loop"})

#: Anforderung → Szene; ``{kernel}`` wird ``exakt`` oder ``netz``.
#: ``merkmal:<art>`` führt zu ``merkmal.<art>.{kernel}``.
REQUIREMENT_SCENES: Final[dict[str, str]] = {
    "start": "startbildschirm",
    "leer": "leer",
    "szene": "zwei_koerper.{kernel}",
    # Eine Ansicht der Szene ohne Auswahl (der Prüfbericht).
    "ansicht": "quader.{kernel}",
    "koerper:1": "quader.{kernel}",
    "koerper:2": "zwei_koerper.{kernel}",
    # Vier Eingänge nimmt nur *Einlagen für neues Profil*: die zwei Schalen und
    # zwei Einlagen eines Profilklemmensatzes, den es nur als Netz gibt.
    "koerper:4": "profilklemme.netz",
    "kante": "kante.{kernel}",
    "zustand:open": "offen.netz",
    "zustand:parts": "mehrteilig.netz",
    "zustand:cavity": "hohlraum.{kernel}",
    "baustein": "baustein.{kernel}",
    "befund": "unter_dem_bett.netz",
    # Netzoperationen (Glätten, Ausdünnen, Formen, Skelett) an einem fein vernetzten
    # Körper statt an zwölf Dreiecken.
    "netzkoerper": "kugel.netz",
    # Parameterleiste und ihr Kontextmenü brauchen ein Maß im Projekt.
    "parameter": "parameter.{kernel}",
    # Die Handlungen einer Textur gibt es nur an einem Schritt *Textur aufbringen*,
    # und der macht aus jedem Körper ein Netz.
    "textur": "merkmal.pattern.netz",
    "langsam": "langsam_2s",
    # *Auf alle N gleichartigen anwenden* steht erst ab zwei gleichen Merkmalen.
    "gleichartig": "gleiche_bohrungen.exakt",
}
FEATURE_REQUIREMENT: Final = "merkmal:"
FEATURE_SCENE: Final = "merkmal.{kind}.{kernel}"


@dataclass(frozen=True, slots=True)
class Row:
    """Eine Zeile der Funktionsliste (Bauplan D0 §2.3)."""

    id: str
    kind: str
    source: str
    package: str
    requirement: str
    start_scene: str
    target: str
    menu_path: str = ""
    shortcut: str = ""
    covers: tuple[str, ...] = ()
    """Die Operationen hinter einer Sammelzeile (``part:*``) oder einer Zeile, deren
    Eingang eine zweite Operation mitträgt (:data:`SAME_ENTRY`), sonst leer."""
    route: tuple[Mapping[str, str], ...] = ()
    """Die Klicks, die die Auswahl der Anforderung herstellen (:func:`selection_route`) —
    ``{target, button, modifier}``; ``next_click`` wählt nichts aus, er nennt nur den
    nächsten Klick zum Ziel. Eine Spezifikation ergänzt ihren ``route`` danach."""
    spec: Mapping[str, Any] | None = None
    """Die Zeilenspezifikation aus ``tests/data/function_rows/`` — leer heißt ungeprüft."""


def ui_sources(root: Path = UI) -> dict[str, str]:
    """Jede Python-Datei unter ``app/ui``, rekursiv — auch in Unterpaketen."""
    found = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
    }
    _require_definitions(found, UI_CLASSES, root)
    return found


def missing_definitions(sources: Mapping[str, str], names: Iterable[str]) -> list[str]:
    """Die genannten Klassen, die in keinem der Quelltexte definiert sind."""
    defined: set[str] = set()
    for text in sources.values():
        defined.update(re.findall(r"^[ \t]*class[ \t]+(\w+)", text, flags=re.MULTILINE))
    return [name for name in names if name not in defined]


def _require_definitions(sources: Mapping[str, str], names: Iterable[str], root: Path) -> None:
    """Hält an, wenn die Suche unter ``root`` das Modul einer der Klassen nicht fand."""
    if missing := missing_definitions(sources, names):
        raise FunctionListError(
            [
                f"{name}: keine Definition unter {root} — die Suche fand ihr Modul nicht, "
                "dann prüft die Liste nichts"
                for name in missing
            ]
        )


# --- Operationen -----------------------------------------------------------------


def package_of_operation(spec: OperationSpec) -> str:
    """Konzept §6: Gestenparameter vor der Kategorie, sonst die Kategorie."""
    if any(entry.kind in GESTURE_KINDS for entry in spec.params.spec()):
        return GESTURE_PACKAGE
    try:
        return CATEGORY_PACKAGES[spec.category]
    except KeyError:
        raise FunctionListError(
            [f"{spec.name}: Kategorie {spec.category!r} hat kein Paket (CATEGORY_PACKAGES)"]
        ) from None


def _edge_operations() -> frozenset[str]:
    from app.core.perceive.actions import EDGE_OPERATIONS

    return frozenset(name for name, _measure in EDGE_OPERATIONS)


def requirement_of(spec: OperationSpec) -> str:
    """Was die Startszene mitbringen muss, aus der Deklaration der Operation (§2.5).

    Die Folge zählt: Wer nichts nimmt, beginnt leer; wer die Szene oder zwei
    Körper nimmt, zwei Körper; ein Körperzustand (offen, mehrteilig, Hohlraum)
    ist eine härtere Forderung als eine Merkmalsart; dann die erste Art aus
    ``applies_to``, dann eine Kante, sonst ein Körper.
    """
    from app.core.registry import needed_inputs

    if spec.whole_scene:
        return "szene"
    needed = needed_inputs(spec)
    if spec.consumes == 0 and needed == 0:
        return "leer"
    if needed >= 2:
        return f"koerper:{needed}"
    if spec.requires_body:
        return f"zustand:{spec.requires_body}"
    if spec.applies_to:
        return f"{FEATURE_REQUIREMENT}{spec.applies_to[0]}"
    if spec.name in _edge_operations():
        return "kante"
    if spec.category == "mesh" and spec.requires_kind != "brep" and needed == 1:
        return "netzkoerper"
    return "koerper:1"


def kernel_of(spec: OperationSpec | None, requirement: str) -> str:
    """``exakt``, wenn nichts ein Netz verlangt (§2.5) — sonst ``netz``."""
    if spec is not None and spec.requires_kind == "mesh":
        return MESH
    kind = requirement.removeprefix(FEATURE_REQUIREMENT)
    if requirement.startswith(FEATURE_REQUIREMENT) and kind in MESH_ONLY_KINDS:
        return MESH
    return EXACT


def scene_for(requirement: str, kernel: str) -> str:
    """Der Szenenschlüssel einer Anforderung — leer, wenn die Tabelle sie nicht kennt."""
    if requirement.startswith(FEATURE_REQUIREMENT):
        return FEATURE_SCENE.format(
            kind=requirement.removeprefix(FEATURE_REQUIREMENT), kernel=kernel
        )
    pattern = REQUIREMENT_SCENES.get(requirement)
    return pattern.format(kernel=kernel) if pattern is not None else ""


def _start_scene(requirement: str, kernel: str, scenes: Mapping[str, Scene]) -> str:
    key = scene_for(requirement, kernel)
    return key if key in scenes else ""


#: Operationen ohne eigenen Eingang: Sie stehen im Dialog ihrer Gastgeberin, und
#: der Körper entscheidet, welche rechnet. Eine Zeile mit beiden (``covers``).
SAME_ENTRY: Final[dict[str, str]] = {"drill_brep_hole": "drill_hole"}


def _edge_rows_of_operations() -> frozenset[str]:
    """Die Operationen, die an einer angeklickten Kante ihre eigene Zeile haben."""
    from app.core.guides import action_key
    from app.core.perceive.actions import edge_actions

    return frozenset(
        str(action.op) for action in edge_actions("probe") if action_key(action) == action.op
    )


def operation_target(name: str, edged: frozenset[str] | None = None) -> str:
    """Wo der Kunde eine Operation bedient — das Ziel ihrer Zeile (Probelauf F-21).

    Eine Handlung des Merkmalfensters (``perceive.actions.ACTION_ORDER``) ist
    seine Zeile ``feature:<op>``, eine Kantenoperation mit eigener Zeile an der
    angeklickten Kante (``perceive.actions.edge_actions``) diese Zeile
    ``edge:<op>``, eine Färbung der Filamentwähler
    (``selection_operations.PICKER_HANDLES``), sonst der Knopf oder die
    Menüzeile ``operation:<op>``. Vorher hieß jede ``operation:<op>``, und an
    *Merkmal versetzen* fand der Sprachfall „kein Knopf … gilt an dieser
    Auswahl nicht“ — an der gewählten Kante ebenso *Verrunden* (Durchsicht
    welle4 C-M4). ``edged`` sind die Operationen mit Kantenzeile, einmal je Liste
    gerechnet (:func:`_edge_rows_of_operations`).
    """
    from app.core.perceive.actions import ACTION_ORDER
    from app.ui.selection_operations import PICKER_HANDLES

    if any(name in group for group in ACTION_ORDER):
        return f"feature:{name}"
    if name in (edged if edged is not None else _edge_rows_of_operations()):
        return f"edge:{name}"
    if name in PICKER_HANDLES:
        return "filament.picker"
    return f"operation:{name}"


def operation_rows(source: Registry, scenes: Mapping[str, Scene]) -> list[Row]:
    """Je Operation eine Zeile, die Katalogkacheln als eine (``part:*``)."""
    from app.core.registry.surfaces import catalogue_operations, menu_path

    catalogue = catalogue_operations()
    guests: dict[str, list[str]] = {}
    for guest, host in SAME_ENTRY.items():
        if source.has(guest) and source.has(host):
            guests.setdefault(host, []).append(guest)
    rows: list[Row] = []
    edged = _edge_rows_of_operations()
    for spec in sorted(source.all(), key=lambda entry: entry.name):
        if spec.name in catalogue or (
            spec.name in SAME_ENTRY and source.has(SAME_ENTRY[spec.name])
        ):
            continue
        requirement = requirement_of(spec)
        kernel = kernel_of(spec, requirement)
        rows.append(
            Row(
                id=spec.name,
                kind="operation",
                source="register",
                package=package_of_operation(spec),
                requirement=requirement,
                start_scene=_start_scene(requirement, kernel, scenes),
                target=operation_target(spec.name, edged),
                menu_path=menu_path(spec, source),
                shortcut=spec.shortcut or "",
                covers=tuple(sorted({spec.name, *guests[spec.name]}))
                if spec.name in guests
                else (),
            )
        )
    covered = tuple(sorted(name for name in catalogue if source.has(name)))
    if covered:
        rows.append(
            Row(
                id=CATALOGUE_ROW,
                kind="operation",
                source="register",
                package=CATEGORY_PACKAGES["parts"],
                requirement="leer",
                start_scene=_start_scene("leer", EXACT, scenes),
                target="dialog:part_catalog",
                covers=covered,
            )
        )
    return rows


# --- Bedienflächen ---------------------------------------------------------------


def dialog_rows(
    classes: Mapping[str, Sequence[str]], source: Registry, scenes: Mapping[str, Scene]
) -> list[Row]:
    """Je Dialog- oder Fensterklasse eine Zeile ``dialog:<name>``.

    Der Name kommt aus ``guides.dialog_name`` — derselben Quelle, mit der die
    Auflösung das offene Fenster sucht.
    """
    from app.core.guides import dialog_name

    problems: list[str] = []
    rows: list[Row] = []
    for name in sorted(classes):
        if len(classes[name]) > 1:
            problems.append(
                f"{name}: Klassenname in mehreren Modulen ({', '.join(classes[name])}) — "
                "die Zuordnung geht nach dem Namen, also einen umbenennen"
            )
            continue
        if name in DIALOG_OPERATIONS:
            operation = DIALOG_OPERATIONS[name]
            if not source.has(operation):
                problems.append(f"{name}: Operation {operation!r} fehlt im Register")
                continue
            spec = source.get(operation)
            package = package_of_operation(spec)
            requirement = requirement_of(spec)
            kernel = kernel_of(spec, requirement)
        elif name in DIALOG_SURFACES:
            package, requirement = DIALOG_SURFACES[name]
            kernel = kernel_of(None, requirement)
        else:
            problems.append(
                f"{name} ({classes[name][0]}): unbekannte Dialogklasse — eine Zeile in "
                "DIALOG_OPERATIONS oder DIALOG_SURFACES nachtragen"
            )
            continue
        rows.append(
            Row(
                id=f"dialog:{dialog_name(name)}",
                kind="bedienflaeche",
                source="dialogklasse",
                package=package,
                requirement=requirement,
                start_scene=_start_scene(requirement, kernel, scenes),
                target=f"dialog:{dialog_name(name)}",
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


def surface_of(name: str) -> tuple[str, str] | None:
    """Paket und Anforderung eines Wortschatznamens — ``None``, wenn keine Tabelle ihn kennt."""
    if name in TARGET_SURFACES:
        return TARGET_SURFACES[name]
    for prefix, package, requirement in TARGET_PREFIXES:
        if name.startswith(prefix):
            return package, requirement
    return None


KERNEL: Final = ROOT / "app" / "core"
#: Klassen, deren Module die Suche nach Handlungen unter ``app/core`` finden muss: die
#: Handlung selbst, der Verlauf und das Register.
KERNEL_CLASSES: Final[tuple[str, ...]] = ("Action", "History", "Registry")

#: Handler des Fensters, die nur ein Fehlerdialog anbietet — nie ein Befund im Bericht.
#: Sie sind der Fehlerweg (Prüfpunkt 7) der Zeilen, deren Fehler sie tragen, und
#: gehören dem Paket ihres Bereichs (Konzept §6). Ein Handler, der weder hier steht
#: noch an einem Befund ankommen kann, hält die Liste an.
ERROR_DIALOG_ACTIONS: Final[dict[str, str]] = {
    # Aktivierung: Lizenzfehler wirft ``activation.require`` vor jeder Auswertung.
    "activate_offline": "D12",
    "activate_online": "D12",
    "buy_licence": "D12",
    "enter_licence_key": "D12",
    "deactivate_device": "D12",
    # Chat (``backends.llm``), Update (``updates``), Fehlerbericht.
    "set_up_chat": "D12",
    "try_key_again": "D12",
    "open_download_page": "D12",
    "report_error": "D12",
    # Speichern: Erneut und Anderer Ort gibt es nur nach einem gescheiterten
    # Schreiben; *Im Browser öffnen* nur beim Laden aus dem Netz.
    "save_elsewhere": "D1",
    "retry": "D1",
    "open_in_browser": "D1",
    # Übergabe an den Slicer (``export.handover``, ``slice.gcode``).
    "check_profile": "D9",
    "choose_slicer": "D9",
    "export_only": "D9",
    "show_output": "D9",
    "open_settings": "D9",
    # Eine laufende Teilung und das Ausschalten mit abhängigen Schritten im Verlauf.
    "cancel_split": "D8",
    "suppress_along": "D11",
}

#: Befundhandlungen ohne Startszene, je mit dem Grund — leer, und der Test hält es so:
#: Jede Befundhandlung beginnt in einer Szene, deren Befund sie trägt
#: (``promises.actions``). Hierher käme nur eine Handlung, die keine Eingabe erreicht,
#: bis über ihr Entfernen entschieden ist.
FINDING_ACTIONS_WITHOUT_SCENE: Final[dict[str, str]] = {}


def kernel_action_ids(root: Path = KERNEL) -> frozenset[str]:
    """Jede Handlung, die der Kern einem Befund oder Fehler mitgeben kann: jedes
    ``Action("<id>", …)`` und ``Action(id="<id>", …)`` unter ``app/core`` (rekursiv)."""
    found: set[str] = set()
    texts: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        text = texts[path.as_posix()] = path.read_text(encoding="utf-8")
        if "Action(" not in text:
            continue
        for node in ast.walk(ast.parse(text, filename=str(path))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Action"
            ):
                continue
            first = node.args[0] if node.args else None
            named = next((item.value for item in node.keywords if item.arg == "id"), None)
            for value in (first, named):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found.add(value.value)
    _require_definitions(texts, KERNEL_CLASSES, root)
    return frozenset(found)


def report_handlers(sources: Mapping[str, str] | None = None) -> frozenset[str]:
    """Die Handlungen, die das Hauptfenster ausführt: die Schlüssel des Wörterbuchs in
    ``MainWindow.error_handlers``, ohne Fenster gelesen. Was dort fehlt, bietet weder
    der Prüfbericht noch ein Fehlerdialog an (``panels.handled_actions``)."""
    found: set[str] = set()
    for module, text in (sources if sources is not None else ui_sources()).items():
        if "def error_handlers" not in text:
            continue
        for node in statements(ast.parse(text, filename=module)):
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name == "error_handlers":
                        for inner in ast.walk(method):
                            if isinstance(inner, ast.Dict):
                                found.update(
                                    key.value
                                    for key in inner.keys
                                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                                )
    if not found:
        raise FunctionListError(["MainWindow.error_handlers nicht gefunden"])
    return frozenset(found)


def finding_action_ids(sources: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Die Handlungen an Befunden: was ``panels.FINDING_ACTIONS`` nennt und was Befunde
    und Fehler des Kerns mitbringen — soweit das Fenster sie ausführt und sie nicht nur
    ein Fehlerdialog anbietet (:data:`ERROR_DIALOG_ACTIONS`).

    Ein Handler, der keines davon ist, und ein Eintrag der Fehlerdialogtabelle ohne
    Handler halten an.
    """
    from app.ui.panels import FINDING_ACTIONS

    table = {action.id for actions in FINDING_ACTIONS.values() for action in actions}
    handled = report_handlers(sources)
    known = kernel_action_ids() | table
    dialog_only = set(ERROR_DIALOG_ACTIONS)
    problems = [
        f"{name}: Handler des Fensters ohne Einordnung — Befundhandlung des Kerns oder "
        "ERROR_DIALOG_ACTIONS"
        for name in sorted(handled - known - dialog_only)
    ]
    problems += [
        f"{name}: steht in ERROR_DIALOG_ACTIONS, das Fenster führt ihn nicht aus"
        for name in sorted(dialog_only - handled)
    ]
    if problems:
        raise FunctionListError(problems)
    return tuple(sorted((known & handled) - dialog_only))


def _scene_offering(action: str, scenes: Mapping[str, Scene]) -> str:
    """Die erste Szene, die zusagt, dass ihr Bericht diese Handlung anbietet
    (``promises.actions``) — eine leichte vor einer schweren."""
    for heavy in (False, True):
        for key, scene in scenes.items():
            if scene.heavy == heavy and action in scene.promises.get("actions", {}):
                return key
    return ""


def surface_rows(
    targets: Iterable[str],
    history: Iterable[str],
    actions: Iterable[str],
    scenes: Mapping[str, Scene],
) -> list[Row]:
    """Feste Ziele, Verlaufseinträge, Befundhandlungen und *Modell nachbauen*.

    Eine Befundhandlung beginnt in der ersten Szene, deren zugesagter Befund sie
    anbietet; trägt keine Szene einen solchen Befund, bleibt die Startszene
    leer, und die Spezifikation der Zeile nennt sie.
    """
    named: list[tuple[str, str]] = [(name, "wortschatz") for name in sorted(targets)]
    named.append((RECENT_ROW, "wortschatz"))
    named += [(f"history:{entry}", "verlauf") for entry in history]
    named += [(f"finding.action:{entry}", "befundhandlung") for entry in actions]
    problems: list[str] = []
    rows: list[Row] = []
    for name, origin in named:
        found = surface_of(name)
        if found is None:
            problems.append(
                f"{name}: kein Paket — eine Zeile in TARGET_SURFACES oder "
                "TARGET_PREFIXES nachtragen"
            )
            continue
        package, requirement = found
        if name.startswith("finding.action:"):
            start = _scene_offering(name.removeprefix("finding.action:"), scenes)
        else:
            start = _start_scene(requirement, kernel_of(None, requirement), scenes)
        rows.append(
            Row(
                id=name,
                kind="bedienflaeche",
                source=origin,
                package=package,
                requirement=requirement,
                start_scene=start,
                target=name,
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


#: Schlüsselfamilien des Merkmalfensters ohne eigene Operation: Paket und Anforderung.
#: Die Bausteinhandlungen gelten jedem Baustein, und alle Bausteine sind D2.
FEATURE_KEY_SURFACES: Final[dict[str, tuple[str, str]]] = {
    "part": ("D2", "baustein"),
}

#: Schlüsselfamilien, die genau einer Operation dienen (Konzept §6): Sie gehen mit
#: ihr in deren Paket.
FEATURE_KEY_OPERATIONS: Final[dict[str, tuple[str, str]]] = {
    "texture": ("apply_texture", "textur"),
}


def feature_rows(source: Registry, scenes: Mapping[str, Scene]) -> list[Row]:
    """Die Handlungen des Merkmalfensters ohne eigene Operation (Konzept §3).

    Bausteinhandlungen (``PART_ACTION_KEYS``), Texturhandlungen
    (``TEXTURE_ACTION_KEYS``) und die Kantenvarianten (``EDGE_VARIANT_KEYS``,
    ``<op>.<mode>``) — die Schlüssel, die ``FeatureAction.key`` trägt. Eine
    Handlung mit eigener Operation steht als deren Zeile in der Liste.
    """
    from app.core.guides import action_key, action_target
    from app.core.perceive.actions import PART_ACTION_KEYS, TEXTURE_ACTION_KEYS, edge_actions

    problems: list[str] = []
    rows: list[Row] = []
    for key in (*PART_ACTION_KEYS, *TEXTURE_ACTION_KEYS):
        family = key.split(".")[0]
        if family in FEATURE_KEY_OPERATIONS:
            operation, requirement = FEATURE_KEY_OPERATIONS[family]
            package = package_of_operation(source.get(operation))
        elif family in FEATURE_KEY_SURFACES:
            package, requirement = FEATURE_KEY_SURFACES[family]
        else:
            problems.append(f"feature:{key}: Schlüsselfamilie {family!r} ohne Paket")
            continue
        rows.append(
            Row(
                id=f"feature:{key}",
                kind="bedienflaeche",
                source="merkmalfenster",
                package=package,
                requirement=requirement,
                start_scene=_start_scene(requirement, kernel_of(None, requirement), scenes),
                target=f"feature:{key}",
            )
        )
    # Die Zeilen an einer angeklickten Kante, wie das Merkmalfenster sie benennt
    # (``guides.action_target``); die mit eigener Operation stehen als deren Zeile.
    for action in edge_actions("probe"):
        if action_key(action) == action.op or action.op is None:
            continue
        rows.append(
            Row(
                id=action_target(action),
                kind="bedienflaeche",
                source="merkmalfenster",
                package=package_of_operation(source.get(action.op)),
                requirement="kante",
                start_scene=_start_scene("kante", EXACT, scenes),
                target=action_target(action),
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


# --- Fensterbefehle --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """Eine Zeile der Menüleiste, wie der Prüfstand sie am Fenster liest.

    Das Format von ``menubar.json`` gehört hierher (:meth:`to_json`,
    :meth:`from_json`, :func:`write_menubar`, :func:`read_menubar`); Prüfstand und
    Urteile importieren es, statt es nachzubauen.
    """

    object_name: str
    path: tuple[str, ...]
    """Die Texte in der Quellsprache, vom Hauptmenü **bis zur Zeile selbst** — ohne die
    Zeile bekäme jeder Fensterbefehl die Kennung seines Menüs."""
    shortcut: str = ""
    """Das Kürzel in Qts ``PortableText``, leer ohne Kürzel."""

    def to_json(self) -> dict[str, Any]:
        """``{object_name, path, shortcut}``, ``path`` als Liste."""
        return {"object_name": self.object_name, "path": list(self.path), "shortcut": self.shortcut}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> MenuEntry:
        """Die Umkehrung von :meth:`to_json`; ein anderes Format hält an."""
        if set(data) - {"object_name", "path", "shortcut"} or not {"object_name", "path"} <= set(
            data
        ):
            raise FunctionListError(
                [
                    f"menubar.json: Zeile {dict(data)} hat nicht das Format "
                    "{object_name, path, shortcut}"
                ]
            )
        path = tuple(str(part) for part in data["path"])
        if not path:
            raise FunctionListError([f"menubar.json: {data['object_name']} ohne Weg"])
        return cls(
            object_name=str(data["object_name"]),
            path=path,
            shortcut=str(data.get("shortcut", "")),
        )


def menubar_of(window: Any) -> list[MenuEntry]:
    """Die Menüleiste eines gebauten Fensters, gelesen über W's
    ``guide_targets.menubar_entries`` — der Weg bis zur Zeile samt ihrem Text.

    Gerufen im Prozess, der das Fenster schon hat (Prüfstand, Fenstertest); die
    Liste selbst baut keines.
    """
    from app.i18n import SOURCE_LANGUAGE, get_language

    if get_language() != SOURCE_LANGUAGE:
        raise FunctionListError(
            [
                f"menubar_of: Sprache {get_language()!r} — der Weg einer Menüzeile ist ihre "
                f"Quelle, gelesen wird nur in {SOURCE_LANGUAGE!r}"
            ]
        )
    from app.ui.guide_targets import menubar_entries

    return [
        MenuEntry(
            object_name=name,
            path=(*menus, action.text()),
            shortcut=action.shortcut().toString(),
        )
        for name, menus, action in menubar_entries(window)
    ]


def write_menubar(path: Path, entries: Iterable[MenuEntry]) -> None:
    """``menubar.json``: eine Liste von :meth:`MenuEntry.to_json`, UTF-8, eingerückt."""
    path.write_text(
        json.dumps([entry.to_json() for entry in entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def variant_group_package(title: str) -> str | None:
    """Das Paket der Variantengruppe mit diesem Menütitel (``registry.VARIANT_GROUPS``):
    das ihrer Operationen — ``None``, wenn keine Gruppe so heißt."""
    from app.core.registry import VARIANT_GROUPS

    source = registry()
    for group in VARIANT_GROUPS:
        if group.title.msgid != title:
            continue
        packages = {package_of_operation(source.get(name)) for name in group.members}
        if len(packages) != 1:
            raise FunctionListError(
                [f"{title}: Variantengruppe über mehrere Pakete {sorted(packages)}"]
            )
        return packages.pop()
    return None


def command_package(entry: MenuEntry) -> str:
    """Paket eines Fensterbefehls: eine Variantengruppe nach ihren Operationen, eine
    Ausnahme nach der Zeile, sonst das Hauptmenü."""
    if entry.path and (grouped := variant_group_package(entry.path[-1])) is not None:
        return grouped
    if entry.path and entry.path[-1] in COMMAND_PACKAGES:
        return COMMAND_PACKAGES[entry.path[-1]]
    if entry.path and entry.path[0] in MENU_PACKAGES:
        return MENU_PACKAGES[entry.path[0]]
    raise FunctionListError(
        [f"{'/'.join(entry.path)}: Hauptmenü ohne Paket — MENU_PACKAGES ergänzen"]
    )


def command_rows(
    entries: Iterable[MenuEntry], source: Registry, scenes: Mapping[str, Scene]
) -> list[Row]:
    """Die Fensterbefehle aus der Menüleiste; Operationen darin haben ihre Zeile schon.

    Eine Aktion an zwei Orten der Leiste (*Bausteinkatalog …* unter *Datei* und
    unter *Erzeugen*) ist **eine** Funktion: eine Zeile mit dem ersten Pfad als
    Kennung, ``menu_path`` nennt beide Orte. Zwei Zeilen unter einem Namen mit
    verschiedenem Text sind zwei Funktionen — das hält an, ebenso eine Zeile ohne
    Namen.
    """
    titles = {str(spec.title) for spec in source.all()}
    problems: list[str] = []
    rows: dict[str, Row] = {}
    for entry in entries:
        if not entry.path or entry.path[-1] in titles:
            continue
        place = " → ".join(entry.path)
        if not entry.object_name:
            problems.append(f"{'/'.join(entry.path)}: Menüzeile ohne Objektnamen")
            continue
        if entry.object_name in rows:
            known = rows[entry.object_name]
            if known.id.rsplit("/", 1)[-1] != entry.path[-1]:
                problems.append(
                    f"menu:{entry.object_name}: zwei Zeilen ({known.id}, {'/'.join(entry.path)})"
                    " unter einem Namen"
                )
                continue
            rows[entry.object_name] = replace(known, menu_path=f"{known.menu_path}; {place}")
            continue
        try:
            package = command_package(entry)
        except FunctionListError as error:
            problems.extend(error.problems)
            continue
        rows[entry.object_name] = Row(
            id="/".join(entry.path),
            kind="fensterbefehl",
            source="menueleiste",
            package=package,
            requirement="leer",
            start_scene=_start_scene("leer", EXACT, scenes),
            target=f"menu:{entry.object_name}",
            menu_path=place,
            shortcut=entry.shortcut,
        )
    if problems:
        raise FunctionListError(problems)
    return list(rows.values())


def window_action_rows(keys: Iterable[str], scenes: Mapping[str, Scene]) -> list[Row]:
    """Befehle, die das Fenster nur in die Auswahlkarte hängt (``add_window_action``).

    Sie stehen in keiner Menüzeile und in keinem Register; ohne diese Zeilen
    fehlte *Automatisch teilen* in der Liste.
    """
    problems: list[str] = []
    rows: list[Row] = []
    for key in keys:
        if key not in WINDOW_ACTION_PACKAGES:
            problems.append(f"command:{key}: Fensteraktion ohne Paket (WINDOW_ACTION_PACKAGES)")
            continue
        rows.append(
            Row(
                id=f"command:{key}",
                kind="fensterbefehl",
                source="fensteraktion",
                package=WINDOW_ACTION_PACKAGES[key],
                requirement="koerper:1",
                start_scene=_start_scene("koerper:1", EXACT, scenes),
                target=f"command:{key}",
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


def tool_rows(keys: Iterable[str], scenes: Mapping[str, Scene]) -> list[Row]:
    """Die Werkzeuge unter der Ansicht als Zeilen ``tool:<schlüssel>``."""
    problems: list[str] = []
    rows: list[Row] = []
    for key in keys:
        if key not in TOOL_PACKAGES:
            problems.append(f"tool:{key}: Werkzeug ohne Paket (TOOL_PACKAGES)")
            continue
        rows.append(
            Row(
                id=f"tool:{key}",
                kind="bedienflaeche",
                source="werkzeugzeile",
                package=TOOL_PACKAGES[key],
                requirement="koerper:1",
                start_scene=_start_scene("koerper:1", EXACT, scenes),
                target=f"tool:{key}",
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


def context_rows(names: Iterable[str], scenes: Mapping[str, Scene]) -> list[Row]:
    """Die benannten Kontextaktionen von Baum und Parameterleiste als Zeilen ``menu:``."""
    problems: list[str] = []
    rows: list[Row] = []
    for name in names:
        if name not in CONTEXT_PACKAGES:
            problems.append(f"menu:{name}: Kontextaktion ohne Paket (CONTEXT_PACKAGES)")
            continue
        package, requirement = CONTEXT_PACKAGES[name]
        rows.append(
            Row(
                id=f"menu:{name}",
                kind="bedienflaeche",
                source="kontextmenue",
                package=package,
                requirement=requirement,
                start_scene=_start_scene(requirement, kernel_of(None, requirement), scenes),
                target=f"menu:{name}",
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


def settings_rows(
    titles: Iterable[str], targets: Mapping[str, str], scenes: Mapping[str, Scene]
) -> list[Row]:
    """Konzept §3: eine Zeile je Abschnitt der Einstellungen, mit dem Ziel, das sein
    Abschnittsbauer setzt (``function_scan._settings_sections``) — sonst ohne Ziel.

    Die Kennung ist ``setting.section:<name>`` aus dem Titel (``guides.name_part``),
    wie das Ziel, das ein Abschnitt trägt — ohne Modul und Klasse.
    """
    from app.core.guides import name_part

    return [
        Row(
            id=f"setting.section:{name_part(title)}",
            kind="bedienflaeche",
            source="einstellungen",
            package=SETTINGS_PACKAGE,
            requirement="leer",
            start_scene=_start_scene("leer", EXACT, scenes),
            target=targets.get(title, ""),
        )
        for title in titles
    ]


def raw_window_rows(scan: UiScan, scenes: Mapping[str, Scene]) -> list[Row]:
    """Jede Funktion, die ein rohes Meldungsfenster baut, als Zeile — Wiederherstellen,
    Speicherfrage, Löschnachfrage, der Start nach abgelaufener Demo und die übrigen.

    Ein rohes Fenster hat keine eigene Klasse; sein Ziel ist das Kennzeichen, das
    seine Funktion im Quelltext setzt (``function_scan._own_target``), sonst hat es
    keines. Die Kennung ist der Funktionsname; zwei gleichnamige Meldungsfunktionen
    halten an, statt sich eine Zeile zu teilen.
    """
    problems = [
        f"meldung:{name}: zwei Meldungsfunktionen heißen so ({', '.join(places)}) — eine "
        "umbenennen, die Kennung nennt nur den Namen"
        for name, places in sorted(scan.raw_places.items())
        if len(places) > 1
    ]
    targets = scan.raw_targets
    rows: list[Row] = []
    for key in scan.raw_windows:
        if key not in RAW_WINDOW_PACKAGES:
            problems.append(f"{key}: Meldungsfenster ohne Paket (RAW_WINDOW_PACKAGES)")
            continue
        package, requirement = RAW_WINDOW_PACKAGES[key]
        rows.append(
            Row(
                id=RAW_WINDOW_IDS.get(key, f"meldung:{key}"),
                kind="bedienflaeche",
                source="startablauf" if key in RAW_WINDOW_IDS else "meldungsfenster",
                package=package,
                requirement=requirement,
                start_scene=_start_scene(requirement, kernel_of(None, requirement), scenes),
                target=targets.get(key, ""),
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


def read_menubar(path: Path) -> list[MenuEntry]:
    """Die Menüleiste aus :func:`write_menubar` zurück."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [MenuEntry.from_json(item) for item in data]


# --- Die ganze Liste -------------------------------------------------------------


def rows(menubar: Iterable[MenuEntry] = (), *, with_specs: bool = True) -> list[Row]:
    """Alle Zeilen der Funktionsliste.

    Ohne ``menubar`` fehlen die Fensterbefehle — sie entstehen erst am
    gebauten Fenster. ``with_specs`` hängt die Zeilenspezifikationen an.
    """
    from app.core.guides import TARGETS

    source = registry()
    scenes = load_scenes()
    scan = scan_ui(ui_sources())
    issues: list[str] = []
    collected: list[Row] = []
    builders: tuple[Callable[[], list[Row]], ...] = (
        lambda: operation_rows(source, scenes),
        lambda: dialog_rows(scan.classes, source, scenes),
        lambda: surface_rows(TARGETS, scan.history, finding_action_ids(), scenes),
        lambda: feature_rows(source, scenes),
        lambda: window_action_rows(scan.window_actions, scenes),
        lambda: tool_rows(scan.tools, scenes),
        lambda: context_rows(scan.context_actions, scenes),
        lambda: settings_rows(scan.settings_sections, scan.settings_targets, scenes),
        lambda: raw_window_rows(scan, scenes),
        lambda: command_rows(menubar, source, scenes),
    )
    for build in builders:
        try:
            collected.extend(build())
        except FunctionListError as error:
            issues.extend(error.problems)
    issues += duplicate_ids(collected)
    if issues:
        raise FunctionListError(issues)
    collected = [replace(row, route=selection_route(row, scenes)) for row in collected]
    if not with_specs:
        return collected
    specs = load_specs()
    return [
        replace(row, spec=specs[row.id].values if row.id in specs else None) for row in collected
    ]


def duplicate_ids(found: Iterable[Row]) -> list[str]:
    """Jede Kennung, die mehr als eine Zeile trägt — gemeldet, nie still aussortiert."""
    seen: set[str] = set()
    issues: list[str] = []
    for row in found:
        if row.id in seen:
            issues.append(f"{row.id}: zwei Zeilen mit derselben Kennung")
        seen.add(row.id)
    return issues


#: Anforderungen, deren Auswahl ein Merkmal ist — gewählt wird ``Scene.select``.
FEATURE_SELECTIONS: Final[frozenset[str]] = frozenset({"baustein", "textur", "gleichartig"})
#: Die Anforderung, deren Auswahl eine Kante ist: erst der Körper, dann ein Klick ins Bild.
EDGE_SELECTION: Final = "kante"
#: Anforderungen, deren Auswahl der erste Körper ist — bei der Kante als erster Klick.
BODY_SELECTIONS: Final[frozenset[str]] = frozenset(
    {EDGE_SELECTION, "zustand:open", "zustand:parts", "zustand:cavity", "netzkoerper"}
)


def _click(target: str, modifier: str = "") -> dict[str, str]:
    return {"target": target, "button": "left", "modifier": modifier}


def selection_route(row: Row, scenes: Mapping[str, Scene]) -> tuple[dict[str, str], ...]:
    """Die Klicks, mit denen der Kunde in der Startszene wählt, was die Anforderung verlangt.

    Abgeleitet aus der Anforderung, nicht je Zeile geschrieben: ein Körper ist
    seine Baumzeile, mehrere Körper die Baumzeilen mit Strg dazu, ein Merkmal die
    Baumzeile, die die Szene in ``select`` nennt, ein Befund seine Zeile im
    Bericht — bei einer Befundhandlung der Befund, an dem sie steht. Eine Kante
    wählt nur ein Klick ins Bild: erst die Baumzeile des Körpers, dann
    ``view.edge:`` auf eine seiner Kanten. Eine Operation über die ganze Szene
    steht am gewählten ersten Körper. Ohne Auswahl (leer, Startbildschirm,
    Ansicht) ist der Weg leer.
    """
    action = row.id.removeprefix("finding.action:") if row.id.startswith("finding.") else ""
    return route_for(row.requirement, row.start_scene, scenes, action)


def route_for(
    requirement: str, scene_key: str, scenes: Mapping[str, Scene], action: str = ""
) -> tuple[dict[str, str], ...]:
    """:func:`selection_route` für eine Anforderung und eine Szene — auch für die
    Kundenziele (``common_goals.toml``), die dieselben Wörter benutzen.

    Bei einem Befund ist es der Befund, an dem die Szene die Handlung ``action``
    zusagt (``promises.actions``), ohne Handlung der erste zugesagte Befund.
    """
    scene = scenes.get(scene_key)
    if scene is None:
        return ()
    if requirement == "befund":
        offered: Mapping[str, str] = scene.promises.get("actions", {})
        if action:
            return (_click(f"finding:{offered[action]}"),) if action in offered else ()
        findings = scene.promises.get("findings", ())
        return (_click(f"finding:{findings[0]}"),) if findings else ()
    if requirement.startswith(FEATURE_REQUIREMENT) or requirement in FEATURE_SELECTIONS:
        return (_click(f"tree.row:{scene.select}"),) if scene.select else ()
    if requirement.startswith("koerper:"):
        count = int(requirement.removeprefix("koerper:"))
        return tuple(
            _click(f"tree.row:obj_{number}", "" if number == 1 else "ctrl")
            for number in range(1, count + 1)
        )
    if requirement == EDGE_SELECTION:
        # Eine Kante wählt der Klick ins Bild am gewählten Körper (§18.5,
        # ``guide_targets.edge_point_for``; Durchsicht welle4 C-M4).
        return (_click("tree.row:obj_1"), _click("view.edge:obj_1"))
    if requirement in BODY_SELECTIONS:
        return (_click("tree.row:obj_1"),)
    if requirement == "szene":
        # Eine Operation über die ganze Szene steht in der Karte am gewählten
        # Körper (selection_operations.body_operations) — ohne Auswahl fand
        # der Sprachfall *Druckoptimal ausrichten* nicht (Probelauf F-32).
        return (_click("tree.row:obj_1"),)
    return ()


def missing_selections(found: Iterable[Row]) -> list[str]:
    """Zeilen, deren Anforderung eine Auswahl verlangt, ohne Auswahlweg — die Szene nennt
    kein ``select`` oder keinen passenden Befund."""
    selecting = ("koerper:", FEATURE_REQUIREMENT, "zustand:")
    return [
        f"{row.id}: Anforderung {row.requirement!r} in {row.start_scene}, aber kein Auswahlweg"
        for row in found
        if row.start_scene
        and not row.route
        and (
            row.requirement.startswith(selecting)
            or row.requirement in FEATURE_SELECTIONS | BODY_SELECTIONS | {"befund"}
        )
    ]


def missing_scenes(found: Iterable[Row]) -> list[str]:
    """Operationen, deren Anforderung keine Szene hat — der einzige Rotfall der Szenen (§2.5).

    Eine Bedienfläche ohne Szene ist kein Fehler: Ihre Spezifikation nennt die
    Startszene, und ohne Spezifikation bleibt sie ungeprüft.
    """
    return [
        f"{row.id}: Anforderung {row.requirement!r} hat keine Szene "
        f"({scene_for(row.requirement, EXACT) or 'keine Tabellenzeile'})"
        for row in found
        if row.kind == "operation" and not row.start_scene
    ]


def problems(menubar: Iterable[MenuEntry] = ()) -> list[str]:
    """Alles, was die Liste unvollständig macht — leer, wenn sie steht."""
    try:
        found = rows(menubar, with_specs=False)
    except FunctionListError as error:
        return list(error.problems)
    issues = missing_scenes(found)
    issues += missing_selections(found)
    scenes = load_scenes()
    issues += validate_scenes(scenes)
    issues += scene_precondition_problems(scenes)
    issues += validate_specs(found, load_specs(), scenes)
    return issues


def scene_precondition_problems(scenes: Mapping[str, Scene]) -> list[str]:
    """Vorbedingungen einer Szene gibt es nur aus :data:`PRECONDITIONS`, ohne Lizenz
    und Druckart — die gehören der Zeile, nicht ihrer Startszene."""
    return [
        f"Szene {key}: Vorbedingung {name} = {state!r} gibt es nicht"
        for key, scene in scenes.items()
        for name, state in scene.preconditions.items()
        if name in ("licence", "printer") or state not in PRECONDITIONS.get(name, ())
    ]


# --- Zeilenspezifikationen (Bauplan D0 §2.4) -----------------------------------

SPEC_KEYS: Final[frozenset[str]] = frozenset(
    {
        "criteria",
        "start_scene",
        "route",
        "example_goal",
        "inputs",
        "search_probes",
        "questions",
        "expectation",
        "fault_case",
        "preconditions",
        "not_applicable",
        "budget_s",
        "budget_ref",
    }
)
PROBE_ORIGINS: Final[tuple[str, ...]] = ("slicer", "cad", "fragebogen")
BUTTONS: Final[tuple[str, ...]] = ("left", "right", "double")
MODIFIERS: Final[tuple[str, ...]] = ("", "ctrl", "shift")
#: Welche Absage ein erzwungener Fehlfall erwartet (Prüfpunkt 7).
FAULT_KINDS: Final[tuple[str, ...]] = ("sperrgrund", "grenzablehnung", "befund", "meldung")
#: Die Schlüssel eines Fehlfalls: Weg und Eingaben wie in der Spezifikation, eine
#: eigene Startszene, wenn der Fehlfall einen anderen Stand braucht, und ``during``:
#: wann die Handlung geklickt wird — ``rechnung`` heißt, während die nach Weg und
#: Eingaben angestoßene Rechnung läuft.
FAULT_KEYS: Final[frozenset[str]] = frozenset(
    {"start_scene", "route", "inputs", "during", "expected"}
)
FAULT_MOMENTS: Final[tuple[str, ...]] = ("", "rechnung")
#: Die Prüfpunkte des Konzepts (§4), als Schlüssel von ``not_applicable`` geschrieben
#: wie ``"4"``.
CHECKPOINT_NUMBERS: Final[tuple[int, ...]] = tuple(range(1, 20))
#: Die 35 Kriterien (Konzept §4: Einfachheit, Verständlichkeit, Gestaltung, zeitgemäß,
#: innovativ). Werte von ``criteria`` und Schlüssel von ``not_applicable``.
CRITERION_IDS: Final[tuple[str, ...]] = (
    *(f"E{number}" for number in range(1, 8)),
    *(f"V{number}" for number in range(1, 7)),
    *(f"G{number}" for number in range(1, 10)),
    *(f"Z{number}" for number in range(1, 8)),
    *(f"I{number}" for number in range(1, 7)),
)
#: Die geschlossene Liste der Gründe für *entfällt* (Konzept §4, „Urteil und
#: Schwere“). Ein anderer Grund ist eine ungültige Spezifikation.
NOT_APPLICABLE_REASONS: Final[dict[str, str]] = {
    "ohne_rechnung": "Operation ohne Rechnung",
    "ohne_auswahlbezug": "ohne Auswahlbezug",
    "ohne_dialog": "ohne Dialog",
    "ohne_agentenwerkzeug": "ohne Agentenwerkzeug",
    "nur_stufe_c": "nur Stufe C",
}
#: Die Lizenzzustände eines Laufs: Eigenschaften von ``app.core.activation.Activation``,
#: deren Namen die Zustände sind. ``over`` (Demo abgelaufen) ist kein Lauf je
#: Funktion, sondern die Vorbedingung der Startzeile ``startup.expired_demo``.
LICENCE_STATES: Final[tuple[str, ...]] = (
    "sale_without_trial",
    "needs_activation",
    "licensed",
    "expired",
)
STARTUP_LICENCE: Final = "over"
#: Die eine Zeile, an der ``over`` als Vorbedingung gilt.
STARTUP_ROW: Final = "startup.expired_demo"


def licence_states() -> tuple[str, ...]:
    """Die erreichbaren Zustände: ohne ``store.TRIAL_FROM`` (Verkaufsversion) gibt es
    keinen Testlauf und also keinen abgelaufenen, mit ihm keine Verkaufsversion ohne Test."""
    from app.core.activation.store import TRIAL_FROM

    first = "sale_without_trial" if TRIAL_FROM is None else "expired"
    return (first, "needs_activation", "licensed")


PRECONDITIONS: Final[dict[str, tuple[str, ...]]] = {
    "ki": ("vorhanden", "fehlt"),
    "comfyui": ("vorhanden", "fehlt"),
    "slicer": ("vorhanden", "fehlt"),
    # Der zweite Kern; ohne ihn sagen exakte Schritte ab (``brep.kernel.BRepUnavailable``).
    "opencascade": ("vorhanden", "fehlt"),
    # Alle Zustände; welche ein Lauf erreicht, hängt am Paket (:func:`licence_states`).
    "licence": (*LICENCE_STATES, STARTUP_LICENCE),
    "printer": ("filament", "resin"),
}


@dataclass(frozen=True, slots=True)
class SpecEntry:
    """Eine Zeilenspezifikation mit ihrer Herkunft: Paket und Datei getrennt von den
    Werten, die die Zeile trägt (``Row.spec``)."""

    package: str
    file: str
    values: Mapping[str, Any]


_SPEC_FILE: Final = re.compile(r"d(\d+)\.toml")


def load_specs(directory: Path = ROW_SPECS) -> dict[str, SpecEntry]:
    """Kennung → Spezifikation aus ``function_rows/d<N>.toml``. Ein anderer Dateiname
    und dieselbe Kennung in zwei Dateien halten an."""
    found: dict[str, SpecEntry] = {}
    problems: list[str] = []
    for path in sorted(directory.glob("*.toml")):
        match = _SPEC_FILE.fullmatch(path.name)
        if match is None:
            problems.append(f"{path.name}: heißt nicht d<N>.toml")
            continue
        package = f"D{int(match.group(1))}"
        for row_id, values in (
            tomllib.loads(path.read_text(encoding="utf-8")).get("row", {}).items()
        ):
            if row_id in found:
                problems.append(f"{row_id}: in {found[row_id].file} und {path.name}")
                continue
            found[row_id] = SpecEntry(package, path.name, dict(values))
    if problems:
        raise FunctionListError(problems)
    return found


def _field_problem(name: str, source: Registry) -> str | None:
    """``feature.field:<schlüssel>.<feld>`` gegen die Parameter der Operation des Schlüssels.

    ``field:<feld>`` prüft hier nur das Muster des Wortschatzes; ob ein offener Dialog
    das Feld trägt, zeigt erst der Prüfstand.
    """
    if not name.startswith("feature.field:"):
        return None
    key, _dot, field_name = name.removeprefix("feature.field:").rpartition(".")
    operation = key.split(".")[0]
    if not source.has(operation):
        return None
    names = {entry.name for entry in source.get(operation).params.spec()}
    if field_name not in names:
        return f"Feld {field_name!r} gibt es an {operation} nicht"
    return None


def validate_specs(
    found: Sequence[Row], specs: Mapping[str, SpecEntry], scenes: Mapping[str, Scene]
) -> list[str]:
    """Jede Spezifikation trifft eine erzeugte Zeile ihres Pakets, Ziele aus dem
    Wortschatz, Szenen aus dem Katalog und Felder des Registers.

    Fensterbefehle entstehen erst am gebauten Fenster; ohne Menüleiste wird
    eine Kennung mit ``/`` nur gegen Hauptmenü und Zeilentext der Quelle geprüft
    (:func:`command_texts`).
    """
    from app.core.guides import is_target

    source = registry()
    by_id = {row.id: row for row in found}
    have_commands = any(row.source == "menueleiste" for row in found)
    texts = command_texts() if not have_commands else frozenset()
    issues: list[str] = []
    for row_id, entry in specs.items():
        spec = entry.values
        where = f"{entry.file} [{row_id}]"
        row = by_id.get(row_id)
        if row is None and "/" in row_id and not have_commands:
            parts = row_id.split("/")
            if parts[0] not in MENU_PACKAGES or parts[-1] not in texts:
                issues.append(f"{where}: kein Menüpfad der Quelle")
            package = COMMAND_PACKAGES.get(parts[-1], MENU_PACKAGES.get(parts[0], ""))
        elif row is None:
            issues.append(f"{where}: keine erzeugte Zeile trägt diese Kennung")
            continue
        else:
            package = row.package
        if package != entry.package:
            issues.append(f"{where}: gehört zu {package}, steht aber in {entry.file}")
        unknown = set(spec) - SPEC_KEYS
        if unknown:
            issues.append(f"{where}: unbekannte Schlüssel {sorted(unknown)}")
        start = spec.get("start_scene", row.start_scene if row is not None else "")
        if not start or start not in scenes:
            issues.append(f"{where}: Startszene {start!r} gibt es nicht")
        for step in spec.get("route", ()):
            if not is_target(str(step.get("target", ""))):
                issues.append(f"{where}: Weg zu {step.get('target')!r} ist kein Ziel")
            if step.get("modifier", "") not in MODIFIERS:
                issues.append(f"{where}: Zusatztaste {step.get('modifier')!r} unbekannt")
            if step.get("button", "left") not in BUTTONS:
                issues.append(f"{where}: Taste {step.get('button')!r} unbekannt")
        if "inputs" in spec and not spec.get("example_goal"):
            issues.append(f"{where}: Eingaben ohne Beispielziel")
        for name in spec.get("inputs", {}):
            if not is_target(name):
                issues.append(f"{where}: Eingabe {name!r} ist kein Ziel")
            problem = _field_problem(name, source)
            if problem:
                issues.append(f"{where}: {problem}")
        for probe in spec.get("search_probes", ()):
            if not probe.get("word") or probe.get("origin") not in PROBE_ORIGINS:
                issues.append(f"{where}: Suchprobe {probe} ohne Wort oder Herkunft")
        for measure, expected in spec.get("expectation", {}).items():
            if not {"value", "tolerance", "origin"} <= set(expected):
                issues.append(f"{where}: Erwartung {measure} ohne value, tolerance oder Herkunft")
            elif not float(expected["tolerance"]) > 0.0:
                # Regel 6: kein Gleitkommavergleich mit ==.
                issues.append(f"{where}: Erwartung {measure} mit Toleranz {expected['tolerance']}")
        fault = spec.get("fault_case")
        if fault is not None:
            extra = set(fault) - FAULT_KEYS
            if extra:
                issues.append(f"{where}: Fehlfall mit unbekannten Schlüsseln {sorted(extra)}")
            if fault.get("expected") not in FAULT_KINDS:
                issues.append(f"{where}: Fehlfall erwartet {fault.get('expected')!r}")
            if fault.get("during", "") not in FAULT_MOMENTS:
                issues.append(f"{where}: Fehlfall während {fault.get('during')!r} unbekannt")
            if "start_scene" in fault and fault["start_scene"] not in scenes:
                issues.append(
                    f"{where}: Fehlfall-Startszene {fault['start_scene']!r} gibt es nicht"
                )
            elif "start_scene" in fault and start in scenes:
                # Beide Szenen laufen in einem Fall (``function_scenes.row_scenes``):
                # Ihre Vorbedingungen müssen zusammen gelten (C-L4).
                mine = scenes[start].preconditions
                theirs = scenes[fault["start_scene"]].preconditions
                clash = sorted(key for key in set(mine) & set(theirs) if mine[key] != theirs[key])
                if clash:
                    issues.append(
                        f"{where}: Fehlfall-Startszene verlangt {', '.join(clash)} anders"
                        " als die Startszene"
                    )
            for step in fault.get("route", ()):
                if not is_target(str(step.get("target", ""))):
                    issues.append(f"{where}: Fehlfall-Weg zu {step.get('target')!r} ist kein Ziel")
                if step.get("modifier", "") not in MODIFIERS:
                    issues.append(
                        f"{where}: Fehlfall-Zusatztaste {step.get('modifier')!r} unbekannt"
                    )
                if step.get("button", "left") not in BUTTONS:
                    issues.append(f"{where}: Fehlfall-Taste {step.get('button')!r} unbekannt")
            for name in fault.get("inputs", {}):
                if not is_target(name):
                    issues.append(f"{where}: Fehlfall-Eingabe {name!r} ist kein Ziel")
                problem = _field_problem(name, source)
                if problem:
                    issues.append(f"{where}: Fehlfall: {problem}")
        for key, value in spec.get("preconditions", {}).items():
            if key == "licence":
                reachable = licence_states() + ((STARTUP_LICENCE,) if row_id == STARTUP_ROW else ())
                if value not in reachable:
                    issues.append(
                        f"{where}: Vorbedingung licence: Lizenzzustand {value!r} ist hier nicht "
                        f"erreichbar (erreichbar: {', '.join(reachable)})"
                    )
            elif value not in PRECONDITIONS.get(key, ()):
                issues.append(f"{where}: Vorbedingung {key} = {value!r} unbekannt")
        for point, reason in spec.get("not_applicable", {}).items():
            known = point in CRITERION_IDS or (point.isdigit() and int(point) in CHECKPOINT_NUMBERS)
            if not known:
                issues.append(f"{where}: Prüfpunkt oder Kriterium {point!r} gibt es nicht")
            if reason not in NOT_APPLICABLE_REASONS:
                issues.append(f"{where}: Grund {reason!r} steht nicht in der geschlossenen Liste")
        for criterion in spec.get("criteria", ()):
            if criterion not in CRITERION_IDS:
                issues.append(f"{where}: Kriterium {criterion!r} gibt es nicht")
        if "budget_s" in spec and not spec.get("budget_ref"):
            issues.append(f"{where}: Budget ohne Beleg aus §31")
    return issues


def command_texts() -> frozenset[str]:
    """Die übersetzbaren Texte der Oberfläche — ohne Fenster.

    Gelesen werden die Zeichenketten in ``tr(…)`` und ``_(…)`` aller Module unter
    ``app/ui`` (ein Umzug von ``main_window.py`` in ein Paket ändert nichts); ein
    Menüpfad einer Spezifikation muss dort seinen letzten Text finden.
    """
    return scan_ui(ui_sources()).texts


# --- Ausgabe ---------------------------------------------------------------------


def as_markdown(selected: Sequence[Row]) -> str:
    """Eine Übersicht für die Zeilenspezifikation eines Pakets."""
    lines = [
        "| Kennung | Art | Quelle | Anforderung | Szene | Ziel | Ort | Spezifikation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in selected:
        lines.append(
            f"| `{row.id}` | {row.kind} | {row.source} | {row.requirement} | "
            f"{row.start_scene or '—'} | `{row.target}` | {row.menu_path or '—'} | "
            f"{'ja' if row.spec else 'ungeprüft'} |"
        )
    return "\n".join(lines)


def _iter_json(selected: Sequence[Row]) -> Iterator[dict[str, Any]]:
    for row in selected:
        entry = asdict(row)
        entry["covers"] = list(row.covers)
        yield entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--paket", dest="package", choices=PACKAGES, help="nur dieses Paket")
    parser.add_argument("--format", dest="output", choices=("md", "json"), default="md")
    parser.add_argument(
        "--menueleiste", dest="menubar", type=Path, help="menubar.json des Prüfstands"
    )
    parser.add_argument("--check", action="store_true", help="nur prüfen; Ausgang 1 bei Befund")
    parser.add_argument("--szenen", dest="scenes", action="store_true", help="Szenen bauen")
    parser.add_argument("--schwer", dest="heavy", action="store_true", help="auch schwere Szenen")
    parser.add_argument("--out", type=Path, help="Ordner außerhalb des Baums für --szenen")
    args = parser.parse_args(argv)
    if args.scenes and args.out is None:
        parser.error("--szenen braucht --out")
    try:
        return _run(args)
    except FunctionListError as error:
        for issue in error.problems:
            print(issue, file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    """Der Rumpf von :func:`main`; jede :class:`FunctionListError` endet dort als Meldung."""
    menubar = read_menubar(args.menubar) if args.menubar else []
    if args.scenes:
        for path in save_scenes(args.out, heavy=args.heavy):
            print(path)
        return 0
    if args.check:
        issues = problems(menubar)
        for issue in issues:
            print(issue)
        return 1 if issues else 0
    selected = [row for row in rows(menubar) if args.package is None or row.package == args.package]
    if args.output == "json":
        print(json.dumps(list(_iter_json(selected)), ensure_ascii=False, indent=2))
    else:
        print(as_markdown(selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
