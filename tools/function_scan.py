"""Der Quelltext der Oberfläche, gelesen statt ausgeführt (Funktionsliste, RM-737).

Ein Lauf über die Python-Dateien unter ``app/ui`` (:func:`scan_ui`) findet, was die
Funktionsliste als Bedienfläche aufnimmt: Dialog- und Fensterklassen (transitiv über
eigene Basen), Verlaufseinträge, Fensteraktionen, die Werkzeugzeile, benannte
Kontextaktionen, die Abschnitte der Einstellungen und rohe Meldungsfenster samt der
Ziele, die sie selbst setzen, dazu die übersetzbaren Texte. Kein Qt wird geladen;
die Dateien liest ``function_list.ui_sources``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cache, lru_cache
from pathlib import Path
from typing import Any, Final

CONTEXT_PREFIXES: Final[tuple[str, ...]] = ("tree.", "parameters.")


#: Das Modul der Einstellungen; ein Abschnitt ist dort ein ``collapsible(tr("…"), …)``.
SETTINGS_MODULE: Final = "app/ui/settings_dialog.py"


#: Rohe Qt-Fenster: Klassen und die Fabrikfunktionen, die eines bauen.
RAW_CLASSES: Final[frozenset[str]] = frozenset({"QMessageBox", "QInputDialog", "QColorDialog"})
RAW_FACTORIES: Final[frozenset[str]] = frozenset(
    {
        "about",
        "critical",
        "information",
        "question",
        "warning",
        "getColor",
        "getDouble",
        "getInt",
        "getItem",
        "getText",
    }
)


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


def statements(tree: ast.Module) -> Iterator[ast.stmt]:
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


def _object_names(node: ast.AST) -> tuple[str, ...]:
    """``x.setObjectName("<name>")`` → die Namen, die der Aufruf setzen kann."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setObjectName"
        and node.args
    ):
        return _texts(node.args[0])
    return ()


def _tool_key(node: ast.AST) -> str | None:
    """``….tools.add("section", …)`` → ``section``, sonst ``None``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "tools"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _section_title(node: ast.AST, builders: Iterable[str] = ("collapsible",)) -> str:
    """``collapsible(tr("Anwendung"), …)`` → ``Anwendung``, sonst leer; ebenso der
    Aufruf eines der genannten Abschnittsbauer."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in builders
        and node.args
    ):
        title = node.args[0]
        if (
            isinstance(title, ast.Call)
            and isinstance(title.func, ast.Name)
            and title.func.id in {"tr", "_"}
            and title.args
        ):
            title = title.args[0]
        if isinstance(title, ast.Constant) and isinstance(title.value, str):
            return title.value
    return ""


def _builds_raw_window(node: ast.AST) -> bool:
    """``QMessageBox(…)`` oder ``QInputDialog.getItem(…)`` — ein rohes Qt-Fenster."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in RAW_CLASSES
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in RAW_CLASSES
        and func.attr in RAW_FACTORIES
    )


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
    tools: tuple[str, ...] = ()
    """Die Schlüssel der Werkzeuge unter der Ansicht (``….tools.add``)."""
    context_actions: tuple[str, ...] = ()
    """Die Objektnamen benannter Kontextaktionen (:data:`CONTEXT_PREFIXES`)."""
    settings_sections: tuple[str, ...] = ()
    """Die Abschnitte der Einstellungen, in ihrer Folge im Dialog."""
    raw_windows: tuple[str, ...] = ()
    """Die Funktionen, die ein rohes Meldungsfenster bauen, als ``<modul>.<funktion>``."""
    raw_targets: Mapping[str, str] = field(default_factory=dict)
    """Das Ziel, das ein Meldungsfenster selbst setzt (``setProperty(…TARGET_PROPERTY, …)``
    oder ``raw_window("…")``), je ``<modul>.<funktion>``."""
    settings_targets: Mapping[str, str] = field(default_factory=dict)
    """Das Ziel eines Einstellungsabschnitts, den sein Abschnittsbauer kennzeichnet."""
    texts: frozenset[str] = frozenset()
    """Jeder übersetzbare Text in ``tr(…)`` oder ``_(…)`` (:func:`command_texts`)."""


def scan_ui(sources: Mapping[str, str]) -> UiScan:
    """Ein Gang je Modul: Dialog- und Fensterklassen, Verlaufseinträge, Fensteraktionen,
    Werkzeuge, Kontextaktionen, Einstellungsabschnitte, rohe Meldungsfenster und Texte.

    ``sources`` ordnet einen Modulpfad seinem Quelltext zu. Basen werden über
    die eigenen Klassen aufgelöst, gleich in welchem Modul sie stehen, auch
    verschachtelte Klassen zählen. Das Ergebnis wird je Quelltextstand gemerkt:
    Derselbe Inhalt wird in einem Prozess nur einmal gelesen.
    """
    return _scan(tuple(sorted(sources.items())))


@lru_cache(maxsize=4)
def _scan(items: tuple[tuple[str, str], ...]) -> UiScan:
    bases: dict[str, set[tuple[str, ...]]] = {}
    modules: dict[str, list[str]] = {}
    history: set[str] = set()
    window_actions: set[str] = set()
    tools: set[str] = set()
    contexts: set[str] = set()
    sections: list[str] = []
    raw: set[str] = set()
    raw_targets: dict[str, str] = {}
    settings_targets: dict[str, str] = {}
    texts: set[str] = set()
    for module, text in items:
        tree = ast.parse(text, filename=module)
        stem = Path(module).stem
        raw_here = any(name in text for name in RAW_CLASSES)
        constants = _module_texts(tree)
        for node in statements(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).add(_base_names(node))
                modules.setdefault(node.name, []).append(module)
            elif (
                raw_here
                and isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and any(_builds_raw_window(inner) for inner in _own_nodes(node))
            ):
                raw.add(f"{stem}.{node.name}")
                if marked := _own_target(node, constants):
                    raw_targets[f"{stem}.{node.name}"] = marked
        if module == SETTINGS_MODULE:
            titles, targets = _settings_sections(tree)
            sections.extend(titles)
            settings_targets.update(targets)
        for expression in ast.walk(tree):
            if not isinstance(expression, ast.Call):
                continue
            texts.update(_source_text(expression))
            history.update(_history_names(expression))
            if (key := _window_action(expression)) is not None:
                window_actions.add(key)
            if (tool := _tool_key(expression)) is not None:
                tools.add(tool)
            contexts.update(
                name for name in _object_names(expression) if name.startswith(CONTEXT_PREFIXES)
            )

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
        tools=tuple(sorted(tools)),
        context_actions=tuple(sorted(contexts)),
        settings_sections=tuple(dict.fromkeys(sections)),
        raw_windows=tuple(sorted(raw)),
        raw_targets=raw_targets,
        settings_targets=settings_targets,
        texts=frozenset(texts),
    )


def _module_texts(tree: ast.Module) -> dict[str, str]:
    """Die Textkonstanten der obersten Ebene eines Moduls (``NAME = "…"``)."""
    found: dict[str, str] = {}
    for node in tree.body:
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, node.targets
        elif isinstance(node, ast.AnnAssign):
            value, targets = node.value, [node.target]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            text = value.value
            found.update({name.id: text for name in targets if isinstance(name, ast.Name)})
    return found


def _text_of(node: ast.AST, constants: Mapping[str, str]) -> str:
    """Eine Zeichenkette oder der Name einer Textkonstante des Moduls — sonst leer."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id, "")
    return ""


def _is_target_property(node: ast.AST) -> bool:
    """``TARGET_PROPERTY`` oder ``guides.TARGET_PROPERTY``."""
    name = node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")
    return name == "TARGET_PROPERTY"


def _own_target(
    function: ast.FunctionDef | ast.AsyncFunctionDef, constants: Mapping[str, str]
) -> str:
    """Das Kennzeichen, das ein Meldungsfenster selbst setzt — ``box.setProperty(…TARGET_
    PROPERTY, X)`` oder ``with raw_window(X)`` —, sonst leer."""
    for node in _own_nodes(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setProperty"
            and len(node.args) == 2
            and _is_target_property(node.args[0])
            and (found := _text_of(node.args[1], constants))
        ):
            return found
        if isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                call = item.context_expr
                if (
                    isinstance(call, ast.Call)
                    and _called_name(call) == "raw_window"
                    and call.args
                    and (found := _text_of(call.args[0], constants))
                ):
                    return found
    return ""


def _called_name(call: ast.Call) -> str:
    """``f(…)`` → ``f``, ``modul.f(…)`` → ``f``, sonst leer."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else ""


def _settings_sections(tree: ast.Module) -> tuple[list[str], dict[str, str]]:
    """Die Abschnitte der Einstellungen und ihre Ziele.

    Ein Abschnitt ist ein ``collapsible(tr("…"))`` oder der Aufruf eines Abschnittsbauers
    — einer Funktion des Moduls, die ``collapsible`` ruft. Setzt der Bauer sein
    Kennzeichen als ``f"<präfix>{guides.<name>(title.msgid)}"``, ist das Ziel des
    Abschnitts dieser Ausdruck über seinem Titel.
    """
    from app.core import guides

    builders: dict[str, tuple[str, Any]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        calls = [item for item in _own_nodes(node) if isinstance(item, ast.Call)]
        if not any(_called_name(item) == "collapsible" for item in calls):
            continue
        builders[node.name] = ("", None)
        for item in calls:
            if not (
                isinstance(item.func, ast.Attribute)
                and item.func.attr == "setProperty"
                and len(item.args) == 2
                and _is_target_property(item.args[0])
                and isinstance(item.args[1], ast.JoinedStr)
            ):
                continue
            parts = item.args[1].values
            if (
                len(parts) == 2
                and isinstance(parts[0], ast.Constant)
                and isinstance(parts[1], ast.FormattedValue)
                and isinstance(parts[1].value, ast.Call)
                and isinstance(parts[1].value.func, ast.Attribute)
            ):
                transform = getattr(guides, parts[1].value.func.attr, None)
                builders[node.name] = (str(parts[0].value), transform)
    titles: list[str] = []
    targets: dict[str, str] = {}
    callers = {"collapsible", *builders}
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and (title := _section_title(call, callers))):
            continue
        titles.append(title)
        prefix, transform = builders.get(_called_name(call), ("", None))
        if prefix and callable(transform):
            targets[title] = f"{prefix}{transform(title)}"
    return titles, targets


def _own_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Die Knoten einer Funktion ohne die ihrer eingeschachtelten Funktionen — die
    stehen selbst als Anweisung da und werden für sich gezählt."""
    pending: list[ast.AST] = list(function.body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        pending.extend(ast.iter_child_nodes(node))


def _source_text(node: ast.Call) -> tuple[str, ...]:
    """``tr("…")`` oder ``_("…")`` → der Text, sonst leer."""
    if (
        isinstance(node.func, ast.Name)
        and node.func.id in {"tr", "_"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return (node.args[0].value,)
    return ()


def window_classes_in(sources: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Klassenname → Module, für jede Klasse, die (transitiv) einen Dialog oder ein Fenster baut."""
    return dict(scan_ui(sources).classes)


def history_entries(sources: Mapping[str, str]) -> tuple[str, ...]:
    """Die Objektnamen ``history.<x>`` aus ``setObjectName``-Aufrufen — die Einträge
    des Kontextmenüs im Verlauf, unter denen Anleitung und Prüfstand sie finden."""
    return scan_ui(sources).history
