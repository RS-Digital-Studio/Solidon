"""Registerkonsistenz über die Operationen, die die Anwendung wirklich
ausliefert (§35).

Jede Operation erscheint in jeder Oberfläche, trägt ein Schema, übersetzte Texte
und einen Test; Kürzel sind eindeutig; nicht-deterministische Operationen
benutzen einen Startwert.

Solange der Katalog noch gefüllt wird, laufen diese Prüfungen über wenige
Operationen — sie beißen in dem Moment, in dem eine unvollständig hinzukommt.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.core.registry import (
    CATEGORIES,
    FEATURE_KINDS,
    REGISTRY,
    OperationSpec,
    cli_commands,
    documentation,
    menu_tree,
    palette_entries,
    tool_schemas,
)

TESTS_DIR = Path(__file__).parent


def registered() -> list[OperationSpec]:
    return list(REGISTRY.all())


def ids(spec: OperationSpec) -> str:
    return spec.name


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_operation_is_completely_declared(spec: OperationSpec) -> None:
    assert str(spec.title).strip(), f"{spec.name} has no title"
    assert str(spec.doc).strip(), f"{spec.name} has no documentation text"
    assert spec.category in CATEGORIES
    assert all(kind in FEATURE_KINDS for kind in spec.applies_to)
    assert spec.params.spec() is not None


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_parameter_says_what_it_does(spec: OperationSpec) -> None:
    """Ein Titel ist eine Beschriftung, keine Erklärung (§2.4).

    „Spiel [mm]" über einem Zahlenfeld sagt nicht, wovon dieses Spiel abgezogen
    wird und was passiert, wenn es null ist. Der Satz dahinter wird zum Tooltip
    im Dialog und zur Spalte *Bedeutung* im Handbuch — beide leer zu lassen ist
    die stille Art, eine Operation unbenutzbar zu machen.
    """
    for entry in spec.params.spec():
        text = str(entry.doc or "")
        assert text.strip(), f"{spec.name}.{entry.name} has no help text"
        assert text.strip() != str(entry.title).strip(), (
            f"{spec.name}.{entry.name} only repeats its title"
        )


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_no_user_text_carries_a_paragraph_number(spec: OperationSpec) -> None:
    """Der Nutzer hat den Bauplan nicht.

    „(§39)", „(§30)", „(§32)" standen in Dialogtexten und Befunden — für den
    Leser Ballast, für den Suchenden ein Verweis auf ein Dokument, das er nicht
    hat. Im Quelltext sind die Verweise richtig und bleiben; was durch ``_()``
    geht, ist Oberfläche.
    """
    texts = [str(spec.title), str(spec.doc)]
    texts.extend(str(entry.doc or "") for entry in spec.params.spec())
    texts.extend(str(entry.title) for entry in spec.params.spec())
    for text in texts:
        assert "§" not in text, f"{spec.name}: §-Verweis im Nutzertext — {text[:60]}"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_no_user_text_addresses_the_agent(spec: OperationSpec) -> None:
    """Was die Operation dem Sprachmodell sagt, ist nicht, was sie dem Nutzer
    sagt.

    Im ``doc`` von *Quader anlegen* stand „Erst in der Bausteinbibliothek
    suchen" — eine Regel aus ``rules.toml``, gelandet in dem Feld, das der
    Nutzer im Dialog liest. Wer auf „Quader anlegen" klickt, hat sich
    entschieden.

    Geprüft wird gegen die Regelsammlung selbst: taucht ein ganzer Regelsatz in
    einem Dialogtext auf, ist er dort falsch.
    """
    from app.core.knowledge.rules import load

    doc = " ".join(str(spec.doc).split())
    for rule in load().rules:
        for sentence in rule.text.split("."):
            trimmed = " ".join(sentence.split())
            if len(trimmed) < 25:
                continue
            assert trimmed not in doc, f"{spec.name}: Agentenregel im Nutzertext — {trimmed[:60]}"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_non_deterministic_operations_use_a_seed(spec: OperationSpec) -> None:
    if spec.deterministic:
        return
    source = inspect.getsource(spec.fn)
    assert "seed" in source, f"{spec.name} is marked non-deterministic but never reads ctx.seed"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_operation_has_a_test(spec: OperationSpec) -> None:
    """Eine neue Operation ohne Test ist nicht fertig (AGENTS.md, Checkliste)."""
    mentions = [
        path.name
        for path in TESTS_DIR.rglob("test_*.py")
        if path.name != Path(__file__).name and spec.name in path.read_text(encoding="utf-8")
    ]
    assert mentions, f"no test mentions {spec.name}"


def test_shortcuts_are_unique() -> None:
    shortcuts = [spec.shortcut.casefold() for spec in registered() if spec.shortcut]
    assert len(shortcuts) == len(set(shortcuts))


def test_every_operation_reaches_every_surface() -> None:
    names = {spec.name for spec in registered()}
    assert {spec.name for section in menu_tree() for spec in section.entries} == names
    assert {entry.name for entry in palette_entries()} == names
    assert {command.name for command in cli_commands()} == names
    assert {schema["name"] for schema in tool_schemas()} == names
    text = documentation()
    assert all(f"`{name}`" in text for name in names)


def test_the_shared_placement_names_match_the_parts_library() -> None:
    """Das Register erklärt die geteilten Ortsangaben der Bausteine einmal am
    Kategoriekopf und filtert sie aus den Einzeltabellen — über eine eigene
    Namensliste, weil es die Bausteinbibliothek nicht importieren darf.
    Driftet eine der beiden Seiten, verschwinden Parameter aus dem Handbuch
    oder stehen wieder doppelt.
    """
    from app.core.knowledge.parts.ops import _PLACEMENT
    from app.core.registry.surfaces import PART_PLACEMENT_PARAMS

    assert tuple(name for name, _kind, _spec in _PLACEMENT) == PART_PLACEMENT_PARAMS
