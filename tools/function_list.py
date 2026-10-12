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

    python tools/function_list.py --paket D4 --format md
    python tools/function_list.py --check
    python tools/function_list.py --szenen --out <ordner außerhalb des Baums> [--schwer]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from app.core.registry import OperationSpec, Registry
    from app.core.scene.evaluate import EvaluationResult
    from app.core.scene.project import Project

UI: Final = ROOT / "app" / "ui"
DATA: Final = ROOT / "tests" / "data"
SCENES: Final = DATA / "function_scenes.toml"
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
    # Ein ``QMessageBox`` mit eigenem Ausweg (Zahlungslink kopieren).
    "DonationOpenErrorDialog": ("D12", "leer"),
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
    "parameters.first": ("D10", "leer"),
    "report": ("D8", "koerper:1"),
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
    "search": ("D11", "koerper:1"),
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
}

#: Fensteraktionen in der Auswahlkarte (``SelectionOperationsPanel.add_window_action``):
#: Befehle ohne Registereintrag, die nicht in der Menüleiste stehen, nach ihrer
#: Kennung aus ``window_commands``. *Automatisch teilen* ist ein Ablauf über
#: mehrere Operationen und steht unter *Vorbereiten*.
WINDOW_ACTION_PACKAGES: Final[dict[str, str]] = {
    "edit.auto_split": "D8",
}

# --- Anforderung und Szene (Bauplan D0 §2.5) ----------------------------------

EXACT: Final = "exakt"
MESH: Final = "netz"
KERNELS: Final[tuple[str, ...]] = (EXACT, MESH)

#: Merkmalsarten, die es nur am Netz gibt: Ein exakter Körper ist immer
#: geschlossen, eine offene Randkante hat er nicht.
MESH_ONLY_KINDS: Final[frozenset[str]] = frozenset({"edge_loop"})

#: Anforderung → Szene; ``{kernel}`` wird ``exakt`` oder ``netz``.
#: ``merkmal:<art>`` führt zu ``merkmal.<art>.{kernel}``.
REQUIREMENT_SCENES: Final[dict[str, str]] = {
    "start": "startbildschirm",
    "leer": "leer",
    "szene": "zwei_koerper.{kernel}",
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
    # Die Handlungen einer Textur gibt es nur an einem Schritt *Textur aufbringen*,
    # und der macht aus jedem Körper ein Netz.
    "textur": "merkmal.pattern.netz",
    "langsam": "langsam_2s",
    # *Auf alle N gleichartigen anwenden* steht erst ab zwei gleichen Merkmalen.
    "gleichartig": "gleiche_bohrungen.exakt",
}
FEATURE_REQUIREMENT: Final = "merkmal:"
FEATURE_SCENE: Final = "merkmal.{kind}.{kernel}"

#: Was eine Szene zusagen darf (``promises``).
PROMISE_KEYS: Final[frozenset[str]] = frozenset(
    {"objects", "kinds", "body", "findings", "stops", "triangles_over", "seconds_over"}
)
BODY_STATES: Final[tuple[str, ...]] = ("closed", "open", "parts", "cavity")


class FunctionListError(Exception):
    """Die Liste lässt sich nicht vollständig zuordnen — mit allen Fundstellen."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = tuple(problems)


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
    """Die Operationen hinter einer Sammelzeile (``part:*``), sonst leer."""
    route: tuple[Mapping[str, str], ...] = ()
    """Die Klicks, die die Auswahl der Anforderung herstellen (:func:`selection_route`) —
    ``{target, button, modifier}``; ``next_click`` wählt nichts aus, er nennt nur den
    nächsten Klick zum Ziel. Eine Spezifikation ergänzt ihren ``route`` danach."""
    spec: Mapping[str, Any] | None = None
    """Die Zeilenspezifikation aus ``tests/data/function_rows/`` — leer heißt ungeprüft."""


# --- Dialogklassen ---------------------------------------------------------------

#: Qt-Klassen, deren Unterklassen ein eigenes Fenster sind. ``QMessageBox`` und
#: die übrigen Standarddialoge erben von ``QDialog``; wer von ihnen ableitet,
#: baut ebenfalls einen Dialog.
QT_WINDOW_BASES: Final[frozenset[str]] = frozenset(
    {
        "QDialog",
        "QMainWindow",
        "QMessageBox",
        "QFileDialog",
        "QInputDialog",
        "QColorDialog",
        "QFontDialog",
        "QProgressDialog",
        "QErrorMessage",
        "QWizard",
    }
)


def _base_names(node: ast.ClassDef) -> tuple[str, ...]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return tuple(names)


def _statements(tree: ast.Module) -> Iterator[ast.stmt]:
    """Jede Anweisung, auch in Funktionen, Klassen, Verzweigungen und Ausnahmen.

    Eine Klasse ist immer eine Anweisung; Ausdrücke brauchen ihre Suche nicht
    zu sehen, und ohne sie ist der Gang ein Bruchteil von ``ast.walk``.
    """
    pending: list[ast.stmt] = list(tree.body)
    while pending:
        node = pending.pop()
        yield node
        for name in ("body", "orelse", "finalbody"):
            pending.extend(
                child for child in getattr(node, name, ()) if isinstance(child, ast.stmt)
            )
        for handler in getattr(node, "handlers", ()):
            pending.extend(handler.body)
        for case in getattr(node, "cases", ()):
            pending.extend(case.body)


def _texts(node: ast.AST) -> tuple[str, ...]:
    """Die Zeichenketten, die ein Ausdruck ergeben kann: eine Konstante oder beide
    Zweige eines ``a if b else c`` (``"history.up" if upwards else "history.down"``)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.IfExp):
        return (*_texts(node.body), *_texts(node.orelse))
    return ()


def _history_names(node: ast.AST) -> tuple[str, ...]:
    """``x.setObjectName("history.<name>")`` → ``(<name>,)``; sonst leer."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setObjectName"
        and node.args
    ):
        return tuple(
            text.removeprefix("history.")
            for text in _texts(node.args[0])
            if text.startswith("history.")
        )
    return ()


def _window_action(node: ast.AST) -> str | None:
    """``….add_window_action("edit.auto_split", …)`` → ``edit.auto_split``, sonst ``None``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_window_action"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


@dataclass(frozen=True, slots=True)
class UiScan:
    """Was ein Gang durch die Quelltexte der Oberfläche findet."""

    classes: Mapping[str, tuple[str, ...]]
    """Klassenname → Module, für jede Dialog- oder Fensterklasse."""
    history: tuple[str, ...]
    """Die Einträge des Kontextmenüs im Verlauf (Objektnamen ``history.<x>``)."""
    window_actions: tuple[str, ...] = ()
    """Die Kennungen, unter denen ``add_window_action`` Befehle in die Auswahlkarte hängt."""


def scan_ui(sources: Mapping[str, str]) -> UiScan:
    """Ein Gang je Modul: Dialog- und Fensterklassen und die Verlaufseinträge.

    ``sources`` ordnet einen Modulpfad seinem Quelltext zu. Basen werden über
    die eigenen Klassen aufgelöst, gleich in welchem Modul sie stehen, auch
    verschachtelte Klassen zählen.
    """
    bases: dict[str, set[tuple[str, ...]]] = {}
    modules: dict[str, list[str]] = {}
    history: set[str] = set()
    window_actions: set[str] = set()
    for module, text in sources.items():
        tree = ast.parse(text, filename=module)
        for node in _statements(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).add(_base_names(node))
                modules.setdefault(node.name, []).append(module)
        # Ausdrücke nur dort durchgehen, wo ein gesuchter Aufruf überhaupt steht.
        if "history." in text or "add_window_action(" in text:
            for expression in ast.walk(tree):
                history.update(_history_names(expression))
                if (key := _window_action(expression)) is not None:
                    window_actions.add(key)

    @cache
    def is_window(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in QT_WINDOW_BASES:
            return True
        if name in seen or name not in bases:
            return False
        return any(is_window(base, seen | {name}) for variant in bases[name] for base in variant)

    classes = {name: tuple(sorted(modules[name])) for name in bases if is_window(name)}
    return UiScan(
        classes=classes,
        history=tuple(sorted(history)),
        window_actions=tuple(sorted(window_actions)),
    )


def window_classes_in(sources: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Klassenname → Module, für jede Klasse, die (transitiv) einen Dialog oder ein Fenster baut."""
    return dict(scan_ui(sources).classes)


def history_entries(sources: Mapping[str, str]) -> tuple[str, ...]:
    """Die Objektnamen ``history.<x>`` aus ``setObjectName``-Aufrufen — die Einträge
    des Kontextmenüs im Verlauf, unter denen Anleitung und Prüfstand sie finden."""
    return scan_ui(sources).history


def ui_sources(root: Path = UI) -> dict[str, str]:
    """Jede Python-Datei unter ``app/ui``, rekursiv — auch in Unterpaketen."""
    found = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
    }
    if len(found) < 50:
        raise FunctionListError([f"nur {len(found)} Module unter {root} — dann prüft das nichts"])
    return found


# --- Operationen -----------------------------------------------------------------


def registry() -> Registry:
    """Das geladene Register der Anwendung."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    return REGISTRY


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


def operation_rows(source: Registry, scenes: Mapping[str, Scene]) -> list[Row]:
    """Je Operation eine Zeile, die Katalogkacheln als eine (``part:*``)."""
    from app.core.registry.surfaces import catalogue_operations, menu_path

    catalogue = catalogue_operations()
    rows: list[Row] = []
    for spec in sorted(source.all(), key=lambda entry: entry.name):
        if spec.name in catalogue:
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
                target=f"operation:{spec.name}",
                menu_path=menu_path(spec, source),
                shortcut=spec.shortcut or "",
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


def finding_action_ids() -> tuple[str, ...]:
    """Die Handlungen, die der Prüfbericht an Befunden anbietet (``panels.FINDING_ACTIONS``),
    dazu *Eingabe korrigieren*, das jeder Befund aus einer Operation trägt (``actions_for``)."""
    from app.core.errors import CORRECT_INPUT
    from app.ui.panels import FINDING_ACTIONS

    found = {action.id for actions in FINDING_ACTIONS.values() for action in actions}
    found.add(CORRECT_INPUT.id)
    return tuple(sorted(found))


def offered_at(code: str) -> frozenset[str]:
    """Die Handlungen, die der Prüfbericht an einem Befund dieser Kennung zeigt.

    Gefragt wird ``panels.actions_for`` selbst — dieselbe Auskunft wie im
    Bericht, samt der Regel für Befunde aus einer Operation (``op.…``).
    """
    from app.core.types import Finding
    from app.ui.panels import actions_for

    probe = Finding(code=code, severity="warning", message="", object_id="obj_1", op_id=1)
    return frozenset(action.id for action in actions_for(probe))


def _scene_offering(action: str, scenes: Mapping[str, Scene]) -> str:
    """Die erste Szene, deren zugesagter Befund diese Handlung anbietet — eine
    leichte vor einer schweren."""
    for heavy in (False, True):
        for key, scene in scenes.items():
            if scene.heavy != heavy:
                continue
            if any(action in offered_at(code) for code in scene.promises.get("findings", ())):
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
    # *Modell nachbauen* ist keine Operation, sondern eine Hauptaktion der
    # Auswahlkarte (``selection_operations.REBUILD``, ein Dialog).
    named.append((REBUILD_ROW, "merkmalfenster"))
    problems: list[str] = []
    rows: dict[str, Row] = {}
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
        if name in rows:
            continue
        rows[name] = Row(
            id=name,
            kind="bedienflaeche",
            source=origin,
            package=package,
            requirement=requirement,
            start_scene=start,
            target=name,
        )
    if problems:
        raise FunctionListError(problems)
    return list(rows.values())


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
    from app.core.perceive.actions import (
        EDGE_VARIANT_KEYS,
        PART_ACTION_KEYS,
        TEXTURE_ACTION_KEYS,
    )

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
    for key in EDGE_VARIANT_KEYS:
        operation = key.split(".")[0]
        if not source.has(operation):
            problems.append(f"edge:{key}: Operation {operation!r} fehlt im Register")
            continue
        rows.append(
            Row(
                id=f"edge:{key}",
                kind="bedienflaeche",
                source="merkmalfenster",
                package=package_of_operation(source.get(operation)),
                requirement="kante",
                start_scene=_start_scene("kante", EXACT, scenes),
                target=f"edge:{key}",
            )
        )
    if problems:
        raise FunctionListError(problems)
    return rows


# --- Fensterbefehle --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """Eine Zeile der Menüleiste, wie der Prüfstand sie am Fenster liest."""

    object_name: str
    path: tuple[str, ...]
    """Die Texte in der Quellsprache, vom Hauptmenü bis zur Zeile."""
    shortcut: str = ""


def command_package(entry: MenuEntry) -> str:
    """Paket eines Fensterbefehls: Ausnahme nach der Zeile, sonst das Hauptmenü."""
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
    Kennung, ``menu_path`` nennt beide Orte.
    """
    titles = {str(spec.title) for spec in source.all()}
    problems: list[str] = []
    rows: dict[str, Row] = {}
    for entry in entries:
        if not entry.path or entry.path[-1] in titles:
            continue
        place = " → ".join(entry.path)
        if entry.object_name in rows:
            known = rows[entry.object_name]
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


def read_menubar(path: Path) -> list[MenuEntry]:
    """Die Menüleiste aus einer Datei des Prüfstands: ``[{object_name, path, shortcut}]``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        MenuEntry(
            object_name=str(item["object_name"]),
            path=tuple(str(part) for part in item["path"]),
            shortcut=str(item.get("shortcut", "")),
        )
        for item in data
    ]


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
        lambda: command_rows(menubar, source, scenes),
    )
    for build in builders:
        try:
            collected.extend(build())
        except FunctionListError as error:
            issues.extend(error.problems)
    seen: dict[str, Row] = {}
    for row in collected:
        if row.id in seen:
            issues.append(f"{row.id}: zwei Zeilen mit derselben Kennung")
        seen[row.id] = row
    if issues:
        raise FunctionListError(issues)
    collected = [replace(row, route=selection_route(row, scenes)) for row in collected]
    if not with_specs:
        return collected
    specs = load_specs()
    return [replace(row, spec=specs.get(row.id)) for row in collected]


#: Anforderungen, deren Auswahl ein Merkmal ist — gewählt wird ``Scene.select``.
FEATURE_SELECTIONS: Final[frozenset[str]] = frozenset({"baustein", "textur", "gleichartig"})
#: Anforderungen, deren Auswahl der erste Körper ist.
BODY_SELECTIONS: Final[frozenset[str]] = frozenset(
    {"kante", "zustand:open", "zustand:parts", "zustand:cavity"}
)


def _click(target: str, modifier: str = "") -> dict[str, str]:
    return {"target": target, "button": "left", "modifier": modifier}


def selection_route(row: Row, scenes: Mapping[str, Scene]) -> tuple[dict[str, str], ...]:
    """Die Klicks, mit denen der Kunde in der Startszene wählt, was die Anforderung verlangt.

    Abgeleitet aus der Anforderung, nicht je Zeile geschrieben: ein Körper ist
    seine Baumzeile, mehrere Körper die Baumzeilen mit Strg dazu, ein Merkmal die
    Baumzeile, die die Szene in ``select`` nennt, ein Befund seine Zeile im
    Bericht — bei einer Befundhandlung der Befund, an dem sie steht. Eine Kante
    wählt nur ein Klick ins Bild; hier steht der Körper davor, den Klick auf die
    Kante nennt die Spezifikation. Ohne Auswahl (leer, Startbildschirm, ganze
    Szene) ist der Weg leer.
    """
    scene = scenes.get(row.start_scene)
    if scene is None:
        return ()
    requirement = row.requirement
    if requirement == "befund":
        action = row.id.removeprefix("finding.action:") if row.id.startswith("finding.") else ""
        for code in scene.promises.get("findings", ()):
            if not action or action in offered_at(code):
                return (_click(f"finding:{code}"),)
        return ()
    if requirement.startswith(FEATURE_REQUIREMENT) or requirement in FEATURE_SELECTIONS:
        return (_click(f"tree.row:{scene.select}"),) if scene.select else ()
    if requirement.startswith("koerper:"):
        count = int(requirement.removeprefix("koerper:"))
        return tuple(
            _click(f"tree.row:obj_{number}", "" if number == 1 else "ctrl")
            for number in range(1, count + 1)
        )
    if requirement in BODY_SELECTIONS:
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
    issues += validate_scenes(load_scenes())
    issues += validate_specs(found, load_specs(), load_scenes())
    return issues


# --- Szenenkatalog ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SceneStep:
    """Ein Schritt eines Szenenrezepts: eine Operation mit Eingängen und Werten."""

    op: str
    inputs: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    title: str = ""


@dataclass(frozen=True, slots=True)
class Scene:
    """Ein Rezept aus ``tests/data/function_scenes.toml`` (Bauplan D0 §2.5)."""

    key: str
    summary: str
    ops: tuple[SceneStep, ...] = ()
    base: str = ""
    sources: Mapping[str, str] = field(default_factory=dict)
    """Quellkennung → Pfad relativ zu ``tests/data``."""
    kernel: str = ""
    heavy: bool = False
    project: bool = True
    """``False`` heißt: kein Projekt, der Startbildschirm."""
    promises: Mapping[str, Any] = field(default_factory=dict)
    select: str = ""
    """Das Merkmal, das eine Zeile mit Merkmalsanforderung wählt: ``obj_<n>.<merkmal>``."""


SCENE_KEYS: Final[frozenset[str]] = frozenset(
    {"summary", "ops", "base", "sources", "kernel", "heavy", "project", "promises", "select"}
)
STEP_KEYS: Final[frozenset[str]] = frozenset({"op", "inputs", "params", "title"})


def load_scenes(path: Path = SCENES) -> dict[str, Scene]:
    """Der Szenenkatalog in seiner Reihenfolge. Unbekannte Schlüssel halten an."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    scenes: dict[str, Scene] = {}
    for key, entry in data.get("scene", {}).items():
        unknown = set(entry) - SCENE_KEYS
        if unknown:
            problems.append(f"Szene {key}: unbekannte Schlüssel {sorted(unknown)}")
        steps: list[SceneStep] = []
        for step in entry.get("ops", []):
            extra = set(step) - STEP_KEYS
            if extra or "op" not in step:
                problems.append(f"Szene {key}: Schritt {step} mit {sorted(extra) or 'ohne op'}")
                continue
            steps.append(
                SceneStep(
                    op=step["op"],
                    inputs=tuple(step.get("inputs", ())),
                    params=dict(step.get("params", {})),
                    title=step.get("title", ""),
                )
            )
        scenes[key] = Scene(
            key=key,
            summary=entry.get("summary", ""),
            ops=tuple(steps),
            base=entry.get("base", ""),
            sources=dict(entry.get("sources", {})),
            kernel=entry.get("kernel", ""),
            heavy=bool(entry.get("heavy", False)),
            project=bool(entry.get("project", True)),
            promises=dict(entry.get("promises", {})),
            select=entry.get("select", ""),
        )
    if problems:
        raise FunctionListError(problems)
    return scenes


def recipe(key: str, scenes: Mapping[str, Scene]) -> tuple[dict[str, str], list[SceneStep]]:
    """Quellen und Schritte einer Szene samt ihrer Basis, die Basis zuerst."""
    chain: list[Scene] = []
    current: str = key
    while current:
        if current not in scenes:
            raise FunctionListError([f"Szene {key}: Basis {current!r} gibt es nicht"])
        if any(entry.key == current for entry in chain):
            raise FunctionListError([f"Szene {key}: Basis im Kreis über {current!r}"])
        chain.append(scenes[current])
        current = scenes[current].base
    sources: dict[str, str] = {}
    steps: list[SceneStep] = []
    for scene in reversed(chain):
        sources.update(scene.sources)
        steps.extend(scene.ops)
    return sources, steps


def validate_scenes(scenes: Mapping[str, Scene]) -> list[str]:
    """Was an den Rezepten nicht stimmt, ohne zu rechnen: Basis, Operationen,
    Quellen, Kern, Zusagen."""
    from app.core.registry import FEATURE_KINDS

    source = registry()
    issues: list[str] = []
    for key, scene in scenes.items():
        if not scene.summary:
            issues.append(f"Szene {key}: ohne summary")
        if scene.kernel not in ("", *KERNELS):
            issues.append(f"Szene {key}: Kern {scene.kernel!r} unbekannt")
        for suffix in KERNELS:
            if key.endswith(f".{suffix}") and scene.kernel != suffix:
                issues.append(f"Szene {key}: der Name sagt {suffix}, kernel sagt {scene.kernel!r}")
        try:
            sources, steps = recipe(key, scenes)
        except FunctionListError as error:
            issues.extend(error.problems)
            continue
        for name, relative in sources.items():
            if not (DATA / relative).is_file():
                issues.append(f"Szene {key}: Quelle {name} → {relative} fehlt in tests/data")
        for step in steps:
            if not source.has(step.op):
                issues.append(f"Szene {key}: Operation {step.op!r} gibt es nicht")
        if not scene.project and steps:
            issues.append(f"Szene {key}: ohne Projekt, aber mit Schritten")
        unknown = set(scene.promises) - PROMISE_KEYS
        if unknown:
            issues.append(f"Szene {key}: unbekannte Zusagen {sorted(unknown)}")
        for kind in scene.promises.get("kinds", ()):
            if kind not in FEATURE_KINDS:
                issues.append(f"Szene {key}: Merkmalsart {kind!r} gibt es nicht")
        body = scene.promises.get("body")
        if body is not None and body not in BODY_STATES:
            issues.append(f"Szene {key}: Körperzustand {body!r} unbekannt")
        if scene.heavy and not ({"triangles_over", "seconds_over"} & set(scene.promises)):
            issues.append(f"Szene {key}: schwer, aber ohne Zusage zu Dreiecken oder Sekunden")
    return issues


def build_scene(key: str, scenes: Mapping[str, Scene] | None = None) -> Project:
    """Das Projekt einer Szene, aus ihrem Rezept über die Operationen gebaut.

    Jeder Schritt ist eine Transaktion über ``History.apply`` — derselbe Weg wie
    ``tools/make_examples.py``; ``apply`` prüft Kennungen und Werte, bevor
    etwas geschrieben ist. Gerechnet wird hier nicht.
    """
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Source

    catalogue = scenes if scenes is not None else load_scenes()
    if not catalogue[key].project:
        raise FunctionListError([f"Szene {key}: der Startbildschirm hat kein Projekt"])
    source = registry()
    sources, steps = recipe(key, catalogue)
    project = new_project()
    for name, relative in sources.items():
        project.document.sources[name] = Source(
            id=name, kind="import", path=f"sources/{Path(relative).name}", sha256=""
        )
        project.sources[name] = (DATA / relative).read_bytes()
    history = History(project.document)
    for step in steps:
        title = step.title or source.get(step.op).title
        history.apply(
            title, [OperationDraft(op=step.op, inputs=step.inputs, params=dict(step.params))]
        )
    return project


def evaluate_scene(project: Project) -> EvaluationResult:
    """Das Ergebnis einer gebauten Szene mit dem Vorgabeprofil der Beispiele."""
    from app.core.knowledge import profiles
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    document = project.document
    profile = profiles.make_profile(
        document.printer or "centauri-carbon-2", document.material or "petg"
    )
    return evaluate(document, profile, sources=ProjectSources(project))


def broken_promises(scene: Scene, result: EvaluationResult) -> list[str]:
    """Was die gerechnete Szene von ihren Zusagen nicht hält — leer, wenn alles stimmt."""
    from app.core.geom.mesh import as_mesh_data

    objects = list(result.scene.objects.values())
    promises = scene.promises
    issues: list[str] = []
    stops = bool(promises.get("stops", False))
    if stops != (result.stopped_at is not None):
        issues.append(f"hält an: {result.stopped_at!r}, zugesagt {stops}")
    if "objects" in promises and len(objects) != promises["objects"]:
        issues.append(f"{len(objects)} Körper, zugesagt {promises['objects']}")
    wanted_kind = {"exakt": "brep", "netz": "mesh"}.get(scene.kernel)
    if wanted_kind is not None:
        wrong = [entry.id for entry in objects if entry.kind != wanted_kind]
        if wrong:
            issues.append(f"Kern {scene.kernel}, aber {wrong} sind es nicht")
    shown = {feature.kind for entry in objects for feature in entry.features.values()}
    missing = sorted(set(promises.get("kinds", ())) - shown)
    if missing:
        issues.append(f"Merkmalsarten {missing} fehlen, erkannt {sorted(shown)}")
    body = promises.get("body")
    if body is not None:
        meshes = [as_mesh_data(entry.mesh).raw for entry in objects]
        states = {
            "closed": all(mesh.is_watertight for mesh in meshes),
            "open": any(not mesh.is_watertight for mesh in meshes),
            "parts": any(len(mesh.split(only_watertight=False)) > 1 for mesh in meshes),
            "cavity": "void" in shown,
        }
        if not states[body]:
            issues.append(f"Körperzustand {body} nicht erfüllt")
    codes = {finding.code for finding in result.scene.report.findings}
    missing_findings = sorted(set(promises.get("findings", ())) - codes)
    if missing_findings:
        issues.append(f"Befunde {missing_findings} fehlen, gemeldet {sorted(codes)}")
    if scene.select:
        object_id, _dot, feature_id = scene.select.partition(".")
        chosen = result.scene.objects.get(object_id)
        feature = chosen.features.get(feature_id) if chosen is not None else None
        wanted = scene.key.split(".")[1] if scene.key.startswith("merkmal.") else None
        if feature is None:
            issues.append(f"gewähltes Merkmal {scene.select} gibt es nicht")
        elif wanted is not None and feature.kind != wanted:
            issues.append(f"gewähltes Merkmal {scene.select} ist {feature.kind}, nicht {wanted}")
    if "triangles_over" in promises:
        largest = max((len(as_mesh_data(entry.mesh).raw.faces) for entry in objects), default=0)
        if largest <= promises["triangles_over"]:
            issues.append(f"{largest} Dreiecke, zugesagt über {promises['triangles_over']}")
    return issues


def save_scenes(out: Path, *, heavy: bool = False) -> list[Path]:
    """Baut die Szenen und speichert sie als Projekt nach ``out`` — nie in den Baum."""
    from app.core.scene.project import save

    target = out.resolve()
    if target == ROOT or ROOT in target.parents:
        raise FunctionListError(
            [f"{out}: Erzeugtes wird nicht im Baum abgelegt (tests/data/CLAUDE.md)"]
        )
    target.mkdir(parents=True, exist_ok=True)
    catalogue = load_scenes()
    written: list[Path] = []
    for key, scene in catalogue.items():
        if not scene.project or (scene.heavy and not heavy):
            continue
        path = target / f"{key}.p3d"
        save(build_scene(key, catalogue), path)
        written.append(path)
    return written


# --- Zeilenspezifikationen (Bauplan D0 §2.4) -----------------------------------

SPEC_KEYS: Final[frozenset[str]] = frozenset(
    {
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
PRECONDITIONS: Final[dict[str, tuple[str, ...]]] = {
    "ki": ("vorhanden", "fehlt"),
    "comfyui": ("vorhanden", "fehlt"),
    "slicer": ("vorhanden", "fehlt"),
    "licence": ("demo", "gekauft", "abgelaufen"),
    "printer": ("filament", "resin"),
}
CHECK_POINTS: Final = range(1, 20)


def load_specs(directory: Path = ROW_SPECS) -> dict[str, dict[str, Any]]:
    """Kennung → Spezifikation, mit dem Paket der Datei als ``"package"``."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("d*.toml")):
        package = f"D{int(path.stem.removeprefix('d'))}"
        for row_id, spec in tomllib.loads(path.read_text(encoding="utf-8")).get("row", {}).items():
            found[row_id] = {**spec, "package": package, "file": path.name}
    return found


def _field_problem(name: str, source: Registry) -> str | None:
    """``feature.field:<schlüssel>.<feld>`` und ``field:<feld>`` gegen das Register."""
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
    found: Sequence[Row], specs: Mapping[str, Mapping[str, Any]], scenes: Mapping[str, Scene]
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
    for row_id, spec in specs.items():
        where = f"{spec['file']} [{row_id}]"
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
        if package != spec["package"]:
            issues.append(f"{where}: gehört zu {package}, steht aber in {spec['file']}")
        unknown = set(spec) - SPEC_KEYS - {"package", "file"}
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
                issues.append(f"{where}: Erwartung {measure} ohne value, tolerance oder origin")
        fault = spec.get("fault_case")
        if fault is not None:
            if fault.get("expected") not in FAULT_KINDS:
                issues.append(f"{where}: Fehlfall erwartet {fault.get('expected')!r}")
            for name in fault.get("inputs", {}):
                if not is_target(name):
                    issues.append(f"{where}: Fehlfall-Eingabe {name!r} ist kein Ziel")
        for key, value in spec.get("preconditions", {}).items():
            if value not in PRECONDITIONS.get(key, ()):
                issues.append(f"{where}: Vorbedingung {key} = {value!r} unbekannt")
        for point in spec.get("not_applicable", {}):
            if not point.isdigit() or int(point) not in CHECK_POINTS:
                issues.append(f"{where}: Prüfpunkt {point!r} gibt es nicht")
        if "budget_s" in spec and not spec.get("budget_ref"):
            issues.append(f"{where}: Budget ohne Beleg aus §31")
    return issues


def command_texts() -> frozenset[str]:
    """Die übersetzbaren Texte, die ``main_window`` an Menüzeilen gibt — ohne Fenster.

    Gelesen werden die Zeichenketten in ``tr(…)`` und ``_(…)`` des Moduls; ein
    Menüpfad einer Spezifikation muss dort seinen letzten Text finden.
    """
    path = UI / "main_window.py"
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"tr", "_"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return frozenset(found)


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
    menubar = read_menubar(args.menubar) if args.menubar else []
    if args.scenes:
        if args.out is None:
            parser.error("--szenen braucht --out")
        for path in save_scenes(args.out, heavy=args.heavy):
            print(path)
        return 0
    if args.check:
        issues = problems(menubar)
        for issue in issues:
            print(issue)
        return 1 if issues else 0
    try:
        selected = [
            row for row in rows(menubar) if args.package is None or row.package == args.package
        ]
    except FunctionListError as error:
        for issue in error.problems:
            print(issue, file=sys.stderr)
        return 1
    if args.output == "json":
        print(json.dumps(list(_iter_json(selected)), ensure_ascii=False, indent=2))
    else:
        print(as_markdown(selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
