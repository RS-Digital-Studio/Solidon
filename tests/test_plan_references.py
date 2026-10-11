"""Jeder §-Verweis im Quelltext zeigt auf einen Abschnitt, den der Bauplan hat.

`CLAUDE.md` sagt: **„Eine Aussage ohne §-Beleg ist eine Vermutung."** Ein Verweis
auf einen Abschnitt, den es nicht gibt, ist genau das — nur schwerer zu
erkennen als eine fehlende Angabe, weil er nach Beleg aussieht.

Gemessen am 24.08.2026: **2214 Verweise auf 110 Abschnitte**, davon zeigten
sieben ins Leere. Fünf waren Verweise auf andere Dokumente (RFC 8032 bei der
Ed25519-Umsetzung, ein Konzeptpapier bei der Skelettsitzung) und sind hier
ausgenommen, weil sie ihr Dokument nennen. Zwei blieben übrig, und die stehen
unten in `BEKANNT_OFFEN`.

Dazu hält diese Datei den **Codeblock aus §9** am Code: Jede Dataclass dort hat
in `app/core/types.py` dieselben Felder in derselben Folge, mit denselben
Typen, Vorgaben und Schaltern von `@dataclass` und `field()`; Typaliase und
Funktionssignaturen gleichen ihrem Gegenstück im Code. Der Auszug lässt Importe
und Methoden weg, keine Felder — ein Feld, das nur der Code trägt, steht mit
Grund in `CODE_ONLY`. Eine Anweisung im Block, die der Test nicht liest, ist rot.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from app.core import types as contracts

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "3d-agent-bauplan.md"

#: Eine numerierte Überschrift des Bauplans: ``## 25. Operationskatalog``,
#: ``### 33.1 Ausnahmehierarchie``. Die Nummer ist, was ein „§" meint.
HEADING = re.compile(r"^#{2,5}\s+(\d+(?:\.\d+)*)\.?\s")

#: Ein Verweis im Quelltext: ``§31``, ``§ 17.2``, ``§§ 22.5``, ``(§2.4)``.
REFERENCE = re.compile(r"§+\s?(\d+(?:\.\d+)*)")

#: Zeilen, die ein **anderes** Dokument nennen, meinen nicht den Bauplan.
#:
#: Die Ed25519-Umsetzung verweist auf RFC 8032 (§5.1.4 Punktaddition, §5.1.5
#: Skalar, §5.1.6 Signieren, §7.1 Testvektoren), und die Skelettsitzung auf ein
#: Konzeptpapier („Konzept P16 §7.5"). Beide sagen in derselben Zeile, welches
#: Dokument gemeint ist — daran, und nicht an der Nummer, sind sie zu erkennen.
OTHER_DOCUMENT = re.compile(r"\bRFC\b|\bKonzept\b|\bISO\b|\bDIN\b|\bRFC\d+", re.IGNORECASE)

#: Verweise, die ins Leere zeigen und noch nicht entschieden sind.
#:
#: **Eine kuratierte Liste, kein Freibrief** — dasselbe Muster wie `KNOWN_OPEN`
#: in `test_core_isolation.py`. Der Bauplan wird nur mit Ansage geändert
#: (`CLAUDE.md`), also kann diese Sitzung die fehlenden Abschnitte nicht
#: anlegen; die Verweise umzubiegen wäre geraten, denn welcher Abschnitt
#: gemeint war, steht nirgends.
#:
#: ``33.3`` — fünfmal genannt, zweimal ausdrücklich als „Bauplan §33.3"
#: (`core/report.py`, `core/support.py`). §33 hat 33.1 (Ausnahmehierarchie) und
#: 33.2 (Protokoll), sonst nichts; die Sache selbst — der Fehlerbericht als
#: Ordner — steht in §37.2.
#:
#: ``25.4`` — einmal, am ``caveat`` eines Bausteins. §25 (Operationskatalog)
#: hat überhaupt keine Unterabschnitte, und die Zeile darüber verweist auf
#: §24.1; bei einem **Baustein** wäre §24 die richtige Familie. Ein Zahlendreher
#: ist wahrscheinlich, aber nicht belegt.
BEKANNT_OFFEN: frozenset[str] = frozenset()


def plan_sections() -> set[str]:
    sections = set()
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        found = HEADING.match(line)
        if found:
            sections.add(found.group(1))
    return sections


def sources() -> list[Path]:
    out: list[Path] = []
    for folder in ("app", "tools"):
        out += [
            path
            for path in sorted((ROOT / folder).rglob("*.py"))
            if "__pycache__" not in path.parts and "comfyui" not in path.parts
        ]
    return out


def references() -> dict[str, list[str]]:
    """Jeder Bauplan-Verweis mit den Stellen, die ihn nennen."""
    found: dict[str, list[str]] = defaultdict(list)
    for path in sources():
        relative = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OTHER_DOCUMENT.search(line):
                continue
            for hit in REFERENCE.finditer(line):
                found[hit.group(1)].append(f"{relative}:{number}")
    return found


def test_the_plan_has_numbered_sections() -> None:
    """Ohne diese Zusicherung prüfte alles darunter gegen eine leere Menge."""
    sections = plan_sections()

    assert len(sections) > 100, f"nur {len(sections)} Abschnitte gefunden — das Muster greift nicht"
    for expected in ("2.4", "17.2", "24.1", "31", "39"):
        assert expected in sections, f"§{expected} sollte es geben"


def test_every_reference_points_at_a_section_that_exists() -> None:
    sections = plan_sections()
    used = references()

    assert len(used) > 50, f"nur {len(used)} Verweise gefunden — das Muster greift nicht"

    missing = {
        section: places
        for section, places in used.items()
        if section not in sections and section not in BEKANNT_OFFEN
    }
    assert not missing, "§-Verweise ohne Abschnitt im Bauplan:\n" + "\n".join(
        f"  §{section} ({len(places)}x) — {places[0]}"
        for section, places in sorted(missing.items())
    )


def test_the_known_gaps_are_still_gaps() -> None:
    """Wer einen Abschnitt anlegt, streicht ihn hier — sonst altert die Liste.

    Dieselbe Falle wie bei jeder Ausnahmeliste: Sie wird eingetragen, der Mangel
    wird behoben, und der Eintrag bleibt stehen und deckt den nächsten Fall mit.
    """
    sections = plan_sections()

    behoben = sorted(BEKANNT_OFFEN & sections)
    assert not behoben, (
        f"Der Bauplan hat jetzt {', '.join('§' + s for s in behoben)} — "
        "aus BEKANNT_OFFEN streichen, damit die Liste nicht mehr deckt als sie muss"
    )


def test_the_check_would_catch_a_broken_reference() -> None:
    """Gegenprobe: Ein erfundener Abschnitt darf nicht durchgehen."""
    sections = plan_sections()

    assert "999.7" not in sections
    assert "999.7" not in BEKANNT_OFFEN


# --- Die Verträge aus §9 gegen den Code --------------------------------------

#: Die Überschriften, zwischen denen §9 steht.
CONTRACTS_FROM = "## 9. "
CONTRACTS_TO = "## 10. "

#: Wo Typaliase und Dataclasses aus §9 stehen, und wo jede Funktion.
TYPES_HOME = "app/core/types.py"
FUNCTION_HOMES: dict[str, str] = {"solve_sketch": "app/core/sketch/solver.py"}

#: Die Schalter von ``@dataclass`` mit ihren Vorgaben, aus der Signatur gelesen
#: — so kommt ein neuer Schalter einer späteren Python-Fassung von selbst dazu.
CLASS_FLAGS: dict[str, object] = {
    name: parameter.default
    for name, parameter in inspect.signature(dataclasses.dataclass).parameters.items()
    if parameter.kind is inspect.Parameter.KEYWORD_ONLY
}

#: Die Schalter von ``field()``, die ein Feld trägt; ``kw_only`` erbt die Klasse.
FIELD_FLAGS: dict[str, object] = {"init": True, "repr": True, "hash": None, "compare": True}

#: Felder, die der Code trägt und §9 bewusst nicht zeigt — je mit Grund.
#:
#: **Eine benannte Liste, kein Filter**: Ein Unterstrich oder ``init=False``
#: allein entschuldigt kein Feld, sonst rutschte das nächste private Feld, das
#: doch zum Vertrag gehört, ungesehen durch.
CODE_ONLY: dict[tuple[str, str], str] = {
    ("SliceContour", "_area"): (
        "Merker von slice.analysis.piece_area für die einmal gerechnete Fläche "
        "(init=False, compare=False): weder Konstruktor noch Gleichheit sehen ihn"
    ),
}


class PlanField(NamedTuple):
    """Ein Feld, wie §9 es zeigt; Typ und Vorgabe als normierter Quelltext."""

    name: str
    annotation: str
    default: str | None
    flags: dict[str, object]


class PlanContract(NamedTuple):
    """Eine Dataclass aus §9: Dekoratorschalter und Felder in ihrer Folge."""

    flags: dict[str, object]
    fields: tuple[PlanField, ...]


class PlanContracts(NamedTuple):
    """Alles, was der Codeblock aus §9 festlegt, nach Art getrennt."""

    classes: dict[str, PlanContract]
    aliases: dict[str, str]
    functions: dict[str, str]


def contract_section() -> str:
    """Der Text von §9 bis zur nächsten Hauptüberschrift."""
    text = PLAN.read_text(encoding="utf-8")
    start = text.index("\n" + CONTRACTS_FROM)
    return text[start : text.index("\n" + CONTRACTS_TO, start)]


def contract_source(section: str) -> str:
    """Die Python-Blöcke aus §9 als ein Quelltext."""
    return "\n".join(re.findall(r"```python\n(.*?)```", section, flags=re.DOTALL))


def shown_names(section: str) -> list[str]:
    """Jede Klasse und Funktion, die §9 zeigt — gezählt am Text, nicht am Parser.

    Die zweite Zählung fängt, was der Parser nicht sieht: einen Block mit
    anderem Zaun, eine Klasse in Prosa, einen Namen zweimal.
    """
    return re.findall(r"^(?:class|def) (\w+)", section, flags=re.MULTILINE)


def _normal(annotation: str) -> str:
    """Ein Typ als Quelltext in der Schreibweise von ``ast.unparse``."""
    return ast.unparse(ast.parse(annotation, mode="eval"))


def _names(node: ast.expr, name: str) -> bool:
    """``name`` oder ``dataclasses.name``."""
    if isinstance(node, ast.Name):
        return node.id == name
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == "dataclasses"
    )


def _flags(call: ast.Call | None, defaults: Mapping[str, object], where: str) -> dict[str, object]:
    """Die Schalter eines Aufrufs über ihren Vorgaben; ein fremder Schalter ist rot."""
    flags = dict(defaults)
    for keyword in call.keywords if call is not None else ():
        assert keyword.arg in flags and isinstance(keyword.value, ast.Constant), (
            f"{where}: {ast.unparse(keyword)} vergleicht dieser Test noch nicht"
        )
        flags[keyword.arg] = keyword.value.value
    return flags


def _plan_class(node: ast.ClassDef) -> PlanContract:
    decorators = [
        decorator
        for decorator in node.decorator_list
        if _names(decorator.func if isinstance(decorator, ast.Call) else decorator, "dataclass")
    ]
    assert decorators, f"{node.name}: steht in §9 ohne @dataclass, und so liest der Test sie nicht"
    call = decorators[0] if isinstance(decorators[0], ast.Call) else None
    class_flags = _flags(call, CLASS_FLAGS, f"{node.name}: @dataclass")

    fields: list[PlanField] = []
    for item in node.body:
        assert isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name), (
            f"{node.name}: §9 zeigt nur Felder, nicht {ast.unparse(item).splitlines()[0]}"
        )
        name = item.target.id
        default = None if item.value is None else ast.unparse(item.value)
        flags: dict[str, object] = {**FIELD_FLAGS, "kw_only": class_flags["kw_only"]}
        if isinstance(item.value, ast.Call) and _names(item.value.func, "field"):
            options = ast.Call(item.value.func, [], [])
            default = None
            for keyword in item.value.keywords:
                if keyword.arg == "default":
                    default = ast.unparse(keyword.value)
                elif keyword.arg == "default_factory":
                    default = f"field(default_factory={ast.unparse(keyword.value)})"
                else:
                    options.keywords.append(keyword)
            flags = _flags(options, flags, f"{node.name}.{name}: field()")
        fields.append(PlanField(name, _normal(ast.unparse(item.annotation)), default, flags))
    return PlanContract(class_flags, tuple(fields))


def _signature(node: ast.FunctionDef) -> str:
    returns = "" if node.returns is None else f" -> {ast.unparse(node.returns)}"
    return f"({ast.unparse(node.args)}){returns}"


def read_contracts(source: str) -> PlanContracts:
    """Jede Anweisung des Codeblocks aus §9 — was der Test nicht liest, ist rot."""
    found = PlanContracts({}, {}, {})
    seen: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef):
            name = node.name
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
        else:
            raise AssertionError(
                f"§9: {ast.unparse(node).splitlines()[0]} liest dieser Test nicht — "
                "lesen oder aus dem Vertrag nehmen"
            )
        assert name not in seen, f"{name} steht zweimal in §9"
        seen.add(name)
        if isinstance(node, ast.ClassDef):
            found.classes[name] = _plan_class(node)
        elif isinstance(node, ast.FunctionDef):
            found.functions[name] = _signature(node)
        elif isinstance(node, ast.Assign):
            found.aliases[name] = ast.unparse(node.value)
    return found


def plan_contracts() -> PlanContracts:
    return read_contracts(contract_source(contract_section()))


def _module_definitions(path: str) -> dict[str, str]:
    """Typaliase und Funktionssignaturen einer Datei, als Quelltext wie in §9."""
    found: dict[str, str] = {}
    for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef):
            found[node.name] = _signature(node)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            found[node.targets[0].id] = ast.unparse(node.value)
    return found


def _code_default(item: dataclasses.Field[Any]) -> str | None:
    """Die Vorgabe eines Codefeldes in der Schreibweise von §9."""
    if item.default is not dataclasses.MISSING:
        return repr(item.default)
    if item.default_factory is not dataclasses.MISSING:
        factory = item.default_factory
        return f"field(default_factory={getattr(factory, '__name__', repr(factory))})"
    return None


def _class_differences(name: str, contract: PlanContract) -> list[str]:
    cls = getattr(contracts, name, None)
    if not isinstance(cls, type) or not dataclasses.is_dataclass(cls):
        return [f"{name}: in §9 eine Dataclass, in {TYPES_HOME} nicht"]
    found: list[str] = []
    params = cls.__dataclass_params__  # type: ignore[attr-defined]
    for flag, value in contract.flags.items():
        if getattr(params, flag) != value:
            found.append(
                f"{name}: @dataclass {flag} in §9 {value}, im Code {getattr(params, flag)}"
            )

    code = {item.name: item for item in dataclasses.fields(cls)}
    listed = {item.name: item for item in contract.fields}
    for field_name in code:
        if field_name not in listed and (name, field_name) not in CODE_ONLY:
            found.append(f"{name}.{field_name}: im Code, fehlt in §9")
    for field_name, shown in listed.items():
        if field_name not in code:
            found.append(f"{name}.{field_name}: in §9, fehlt im Code")
            continue
        actual = code[field_name]
        if not isinstance(actual.type, str):
            found.append(
                f"{name}.{field_name}: Typ im Code kein Quelltext ({actual.type!r}) — "
                f"fehlt in {TYPES_HOME} `from __future__ import annotations`?"
            )
        elif shown.annotation != (annotation := _normal(actual.type)):
            found.append(f"{name}.{field_name}: Typ in §9 {shown.annotation}, im Code {annotation}")
        default = _code_default(actual)
        if shown.default != default:
            found.append(
                f"{name}.{field_name}: Vorgabe in §9 {shown.default or 'keine'}, "
                f"im Code {default or 'keine'}"
            )
        for flag, value in shown.flags.items():
            if getattr(actual, flag) != value:
                found.append(
                    f"{name}.{field_name}: field {flag} in §9 {value}, "
                    f"im Code {getattr(actual, flag)}"
                )

    plan_order = [field_name for field_name in listed if field_name in code]
    code_order = [field_name for field_name in code if field_name in listed]
    if plan_order != code_order:
        found.append(f"{name}: Feldfolge in §9 {plan_order}, im Code {code_order}")
    return found


def contract_differences(plan: PlanContracts) -> list[str]:
    """Jede Abweichung zwischen §9 und dem Code, je mit Klasse und Feld oder Name."""
    found: list[str] = []
    for name, contract in sorted(plan.classes.items()):
        found += _class_differences(name, contract)

    homes = dict.fromkeys(plan.aliases, TYPES_HOME) | {
        name: FUNCTION_HOMES.get(name, "") for name in plan.functions
    }
    for name, shown in sorted(plan.aliases.items() | plan.functions.items()):
        if not homes[name]:
            found.append(f"{name}: §9 zeigt die Funktion, FUNCTION_HOMES kennt ihre Datei nicht")
            continue
        actual = _module_definitions(homes[name]).get(name)
        if actual is None:
            found.append(f"{name}: in §9, fehlt in {homes[name]}")
        elif actual != shown:
            found.append(f"{name}: in §9 {shown}, in {homes[name]} {actual}")
    return found


def test_the_plan_shows_the_core_contracts() -> None:
    """Ohne diese Zusicherung verglich alles darunter eine leere Menge.

    Gezählt wird zweimal: am Text jede Zeile ``class``/``def`` und im Parser,
    was er liest. Weichen beide ab, hat der Parser etwas übersehen.
    """
    section = contract_section()
    plan = read_contracts(contract_source(section))
    shown = shown_names(section)

    read = sorted([*plan.classes, *plan.functions])
    assert shown, "keine Klasse und keine Funktion in §9 — das Muster greift nicht"
    assert sorted(shown) == read, (
        "§9 zeigt andere Klassen und Funktionen, als der Test liest:\n"
        f"  im Text   {sorted(shown)}\n  gelesen   {read}"
    )
    for expected in ("Feature", "SceneObject", "OpContext", "OpResult", "LayerInfo", "Sketch"):
        assert expected in plan.classes, f"§9 sollte {expected} zeigen"
        assert plan.classes[expected].fields, f"§9 zeigt {expected} ohne Felder"
    assert "OpFn" in plan.aliases and "solve_sketch" in plan.functions


def test_every_contract_in_the_plan_matches_the_code() -> None:
    differences = contract_differences(plan_contracts())

    assert not differences, (
        "Bauplan §9 und der Code weichen ab — den Vertrag in §9 nachziehen "
        "(Bauplanänderung mit Ansage) oder den Code zurück auf den Vertrag:\n"
        + "\n".join(f"  {line}" for line in differences)
    )


def test_the_code_only_fields_are_still_code_only() -> None:
    """Wer ein Feld in §9 aufnimmt oder streicht, streicht es auch hier."""
    plan = plan_contracts().classes

    stale = []
    for (name, field_name), reason in sorted(CODE_ONLY.items()):
        assert reason, f"{name}.{field_name} steht ohne Grund in CODE_ONLY"
        cls = getattr(contracts, name)
        if field_name not in {item.name for item in dataclasses.fields(cls)}:
            stale.append(f"{name}.{field_name}: nicht mehr im Code")
        elif name in plan and field_name in {item.name for item in plan[name].fields}:
            stale.append(f"{name}.{field_name}: steht jetzt in §9")
    assert not stale, "CODE_ONLY deckt mehr, als es muss:\n" + "\n".join(stale)


def test_the_contract_check_would_catch_a_drift() -> None:
    """Gegenprobe: Jede Art Abweichung an einer echten Klasse wird gemeldet."""
    plan = plan_contracts()
    layer = plan.classes["LayerInfo"]
    last = layer.fields[-1]
    first = layer.fields[0]
    with_default = next(item for item in layer.fields if item.default is not None)

    def drifted(fields: tuple[PlanField, ...], **flags: object) -> list[str]:
        changed = PlanContract({**layer.flags, **flags}, fields)
        return contract_differences(plan._replace(classes={**plan.classes, "LayerInfo": changed}))

    assert contract_differences(plan) == []
    assert drifted(layer.fields[:-1]) == [f"LayerInfo.{last.name}: im Code, fehlt in §9"]
    assert drifted((*layer.fields, PlanField("invented", "float", None, first.flags))) == [
        "LayerInfo.invented: in §9, fehlt im Code"
    ]
    assert drifted(
        tuple(
            item._replace(default="12.5") if item is with_default else item for item in layer.fields
        )
    ) == [f"LayerInfo.{with_default.name}: Vorgabe in §9 12.5, im Code {with_default.default}"]
    assert drifted((first._replace(annotation="int"), *layer.fields[1:])) == [
        f"LayerInfo.{first.name}: Typ in §9 int, im Code {first.annotation}"
    ]
    assert drifted(tuple(reversed(layer.fields)))[0].startswith("LayerInfo: Feldfolge")
    for flag in ("frozen", "kw_only", "order"):
        assert drifted(layer.fields, **{flag: not layer.flags[flag]}) == [
            f"LayerInfo: @dataclass {flag} in §9 {not layer.flags[flag]}, "
            f"im Code {layer.flags[flag]}"
        ]
    for flag in ("compare", "init"):
        hidden = first._replace(flags={**first.flags, flag: False})
        assert drifted((hidden, *layer.fields[1:])) == [
            f"LayerInfo.{first.name}: field {flag} in §9 False, im Code True"
        ]
    changed = contract_differences(plan._replace(functions={"solve_sketch": "(sketch: Sketch)"}))
    assert len(changed) == 1
    assert changed[0].startswith(
        "solve_sketch: in §9 (sketch: Sketch), in app/core/sketch/solver.py (sketch: Sketch, "
    )
    assert contract_differences(plan._replace(aliases={"OpFn": "Callable[[], None]"})) == [
        "OpFn: in §9 Callable[[], None], in app/core/types.py Callable[[OpContext], OpResult]"
    ]


def test_the_parser_leaves_nothing_in_the_plan_unread() -> None:
    """Gegenprobe: Was der Parser nicht liest, verschwindet nicht, sondern ist rot."""
    section = contract_section()
    source = contract_source(section)
    plain = "@dataclass(frozen=True, slots=True)\nclass Sketch:"
    assert plain in source

    spelled = read_contracts(source.replace(plain, "@dataclasses." + plain[1:]))
    assert spelled.classes["Sketch"] == read_contracts(source).classes["Sketch"]

    for addition, message in (
        ("class Unread:\n    x: int\n", "Unread: steht in §9 ohne @dataclass"),
        ("@dataclass\nclass LayerInfo:\n    z: float\n", "LayerInfo steht zweimal"),
        ("def solve_sketch() -> None: ...\n", "solve_sketch steht zweimal"),
        ("import os\n", "import os liest dieser Test nicht"),
        ("@dataclass(weird=1)\nclass Odd:\n    x: int\n", "weird=1 vergleicht"),
        ("@dataclass\nclass Odd:\n    x: int = field(doc='x')\n", "doc='x' vergleicht"),
    ):
        with pytest.raises(AssertionError, match=re.escape(message)):
            read_contracts(source + "\n\n" + addition)

    fenced = section.replace("```python", "```py")
    assert read_contracts(contract_source(fenced)).classes == {}
    assert shown_names(fenced) == shown_names(section) != []
