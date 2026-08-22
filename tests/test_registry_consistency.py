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
from typing import Any

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


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_a_parameter_set_can_always_be_taken_apart(spec: OperationSpec) -> None:
    """``fields()`` warf bei einer parameterlosen Operation.

    *Objekt löschen* braucht keine Parameter, und ihr Parametersatz ist deshalb
    ``BaseParams`` selbst — keine Dataclass. ``dataclasses.fields`` wirft dort
    ein nacktes ``TypeError``, das weder ein ``AppError`` ist noch einen
    Handlungsvorschlag trägt (Regel 17); zu beheben gibt es dabei nichts, denn
    „kein Parameter" ist eine gültige Antwort. Wer über das Register läuft — die
    Baustein-Operationen tun es (§24.1) — traf damit auf einen Abbruch statt auf
    eine leere Liste.

    Und die Felder gehören zum Schema: Was das eine kennt, kennt das andere.
    """
    entries = spec.params.fields()
    assert {entry.name for entry in entries} >= {entry.name for entry in spec.params.spec()}, (
        f"{spec.name}: das Schema nennt Parameter, die als Feld fehlen"
    )


def test_one_spelling_for_the_angle() -> None:
    """Sechsundzwanzig Winkel trugen „grad", vier trugen „°".

    Im Dialog las sich das als „Winkel [grad]" in *Senken* und „Winkel [°]" in
    *Formschräge anstellen* — zwei Schreibweisen derselben Einheit im selben
    Produkt. „grad" ist obendrein ein roher deutscher Schlüssel: Er steht in
    keinem Katalog, also stand er auch in der englischen Oberfläche so da.

    Geprüft wird über das ganze Register, denn eine Vereinbarung hält nur bis
    zum nächsten Winkelparameter. Erlaubt sind Millimeter und
    :data:`DEGREE_UNIT`; wer eine dritte Einheit braucht, trägt sie hier ein und
    entscheidet damit bewusst.
    """
    from app.core.units import DEGREE_UNIT

    allowed = {"mm", DEGREE_UNIT}
    found: dict[str, list[str]] = {}
    for spec in registered():
        for entry in spec.params.spec():
            if entry.unit and entry.unit not in allowed:
                found.setdefault(entry.unit, []).append(f"{spec.name}.{entry.name}")
    assert not found, f"unbekannte Einheiten im Register: {found}"

    angles = [
        f"{spec.name}.{entry.name}"
        for spec in registered()
        for entry in spec.params.spec()
        if entry.unit == DEGREE_UNIT
    ]
    assert len(angles) > 20, f"nur {len(angles)} Winkelparameter — prüft dieser Test noch etwas?"


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


def test_every_detected_feature_kind_offers_an_operation() -> None:
    """Ein angeklicktes Merkmal führt zu einer Handlung — oder es steht im
    Ausnahmeverzeichnis unten (§2.6, §18.5).

    **Warum das eine eigene Prüfung braucht.** ``applies_to`` sagt, welche
    Merkmale eine Operation annimmt; die Gegenrichtung sagt niemand. Sie fiel
    beim Nachfahren von Weg 1 auf: ``edge_loop`` ist das Merkmal für eine
    offene Stelle im Netz — genau das, was der Prüfbericht als „Das Modell ist
    an drei Stellen offen" meldet — und das Kontextmenü daran bot nichts an.
    Dabei gibt es ``repair`` („Schließt Löcher"), es hatte sich nur für kein
    Merkmal angemeldet. §2.6 nennt das Kontextmenü „den kürzesten Weg vom
    Sehen zum Tun"; für den häufigsten Defekt führte er ins Leere.

    Geprüft werden nur Arten, die auch **entstehen**: ``FEATURE_KINDS`` kommt
    aus dem Typ und führt Vorrat, der noch keinen Erzeuger hat. Ein Merkmal,
    das niemand anklicken kann, braucht kein Menü.
    """
    from app.core.registry import REGISTRY

    #: Erzeugt, aber ohne Operation — mit dem Grund, warum das offen ist.
    #: Beim Lösen hier streichen, nicht die Prüfung aufweichen.
    known_gaps = {
        # Der Gewinde-Baustein gibt dieses Merkmal zurück
        # (knowledge/parts/build.py). Welche Operation fachlich auf ein
        # fertiges Gewinde gehört, entscheidet der Bauplan und nicht diese
        # Prüfung — offener Punkt in der ROADMAP.
        "thread",
    }
    produced = {"hole", "face", "edge_loop", "pin", "cone", "thread"}

    empty = {kind for kind in produced if not REGISTRY.for_feature(kind)}
    assert empty <= known_gaps, (
        f"Merkmale ohne jede Operation im Kontextmenü: {sorted(empty - known_gaps)} — "
        "ein Klick darauf endet in einem Menü aus Ausblenden (§2.6)"
    )
    assert produced >= known_gaps, (
        f"Ausnahme für ein Merkmal, das nicht entsteht: {sorted(known_gaps - produced)}"
    )


def test_no_operation_calls_its_core_function_with_an_argument_it_refuses() -> None:
    """Eine Operation ruft nur, was ihre Kernfunktion annimmt.

    **Der Fund, der diese Prüfung veranlasst hat.** ``plug_hole`` übergab
    ``profile=ctx.profile`` an ``plug()``, und ``plug()`` hatte diesen
    Parameter nicht. Die Operation „Loch verschließen" konnte damit mit keinem
    Wert durchlaufen: Der ``TypeError`` wurde zum ``InternalError``, und der
    Nutzer bekam „Im Programm ist ein unerwarteter Fehler aufgetreten" samt
    Knopf für den Fehlerbericht — auf einen Klick, an dem nichts falsch war.

    **Warum die Suite geschwiegen hat.** ``tests/test_missing_ops.py`` prüft
    ``plug()`` — die Funktion, direkt, mit den richtigen Argumenten. Sie ist in
    Ordnung. Geprüft hat niemand die Zeile *zwischen* Register und Funktion.
    Genau diesen Blindfleck beschreibt ``errors.py`` bei
    ``PROGRAMMING_ERRORS``: „ihr Test übersprang sich aus demselben Grund, und
    der Hinweispfad war zwei Phasen lang tot — hinter einer grünen Suite."

    Geprüft wird statisch und nicht durch Fahren: Ein Lauf über 86 Operationen
    braucht Eingangskörper, die zu jeder passen, und eine Operation, die aus
    einem anderen Grund anhält, verdeckt diesen hier. Der Syntaxbaum kennt die
    Aufrufe, ``inspect`` die Signaturen — das genügt und kostet nichts.

    **Die Bausteine gehen mit.** Sie rufen dieselben Kernfunktionen und stehen
    in einem eigenen Register; der Fehler von ``plug_hole`` wäre dort genauso
    möglich und genauso unsichtbar. Gemessen sind sie heute sauber — geprüft
    waren sie nicht.
    """
    import ast
    import textwrap

    from app.core.knowledge.parts.registry import PARTS

    # **Die Module, nicht nur die eintragenden Funktionen.** Erst prüfte diese
    # Stelle ``spec.fn`` allein, und eine Gegenprobe zeigte, was das wert ist:
    # ein erfundenes Schlüsselwort in einer Hilfsfunktion von ``fasteners.py``
    # blieb unentdeckt. ``plug_hole`` fiel nur auf, weil der falsche Aufruf
    # zufällig in der Operation selbst stand. Geprüft wird deshalb jedes Modul,
    # das eine Operation oder einen Baustein hält — mit allem, was darin steht.
    both: list[Any] = [*registered(), *PARTS.all()]
    modules = {module for spec in both if (module := inspect.getmodule(spec.fn)) is not None}
    offenders: list[str] = []
    for module in sorted(modules, key=lambda entry: entry.__name__):
        namespace = vars(module)
        try:
            source = textwrap.dedent(inspect.getsource(module))
            tree = ast.parse(source)
        except (OSError, SyntaxError, TypeError):  # pragma: no cover - Vorsicht
            continue
        where = module.__name__

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            target = namespace.get(node.func.id)
            # Nur echte Funktionen dieses Projekts: Klassen nehmen über
            # ``__init__`` an, C-Funktionen haben keine lesbare Signatur, und
            # ein Name, den das Modul nicht kennt, ist ein lokaler.
            if not inspect.isfunction(target):
                continue
            try:
                parameters = inspect.signature(target).parameters
            except (TypeError, ValueError):  # pragma: no cover - Vorsicht
                continue
            if any(p.kind is p.VAR_KEYWORD for p in parameters.values()):
                continue
            for keyword in node.keywords:
                if keyword.arg and keyword.arg not in parameters:
                    offenders.append(
                        f"{where}:{node.lineno} → {node.func.id}(…, {keyword.arg}=…) "
                        f"— {node.func.id} nimmt {sorted(parameters)}"
                    )

    assert not offenders, "Operationen rufen ihre Kernfunktion falsch auf:\n" + "\n".join(offenders)


def test_every_expression_example_in_the_register_actually_evaluates() -> None:
    """**Ein Beispiel, das der eigene Auswerter ablehnt, ist schlechter als
    keines.**

    Der Hilfetext von ``create_box --width`` nannte ``=breite*2``. Genau so
    getippt antwortet der Auswerter „Unbekannter Name im Ausdruck. Parameter
    werden mit @ geschrieben." — der Kunde wird aufgefangen, aber er wurde
    vorher falsch losgeschickt. Gefunden beim Lesen der
    Kommandozeilenhilfe.

    Geprüft wird jeder Text des Registers, der wie ein Ausdrucksbeispiel
    aussieht: Er muss sich gegen einen Parameter dieses Namens wirklich
    ausrechnen lassen.
    """
    import re

    from app.core.scene import expressions
    from app.core.types import Parameter

    #: Was in einem Dokumentationstext ein Ausdrucksbeispiel ist: ein
    #: Gleichheitszeichen, dahinter etwas ohne Leerzeichen. Der Satzpunkt
    #: gehört nicht dazu.
    muster = re.compile(r"=[^\s,;.]+")

    texte: list[tuple[str, str]] = []
    for spec in REGISTRY.all():
        texte.append((spec.name, str(spec.doc or "")))
        for entry in spec.params.spec():
            texte.append((f"{spec.name}.{entry.name}", str(entry.doc or "")))
            texte.append((f"{spec.name}.{entry.name} (Titel)", str(entry.title or "")))

    geprueft = 0
    for wo, text in texte:
        for treffer in muster.findall(text):
            # Namen der Parameter im Beispiel einsammeln und mit Werten
            # belegen — der Test prüft die Form, nicht die Zahl.
            namen = re.findall(r"@([A-Za-z_][A-Za-z_0-9]*)", treffer)
            werte = {name: Parameter(name=name, value=2.0, unit="mm") for name in namen}
            werte["_probe"] = Parameter(name="_probe", value=0.0, unit="mm", expression=treffer)
            try:
                expressions.resolve(werte)
            except Exception as problem:
                raise AssertionError(
                    f"{wo}: das Beispiel „{treffer}“ lässt sich nicht ausrechnen — "
                    f"{type(problem).__name__}: {problem}"
                ) from problem
            geprueft += 1

    assert geprueft, "es gibt Ausdrucksbeispiele im Register, und sie werden geprüft"
