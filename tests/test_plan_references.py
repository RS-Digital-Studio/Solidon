"""Jeder §-Verweis im Quelltext zeigt auf einen Abschnitt, den der Bauplan hat.

`CLAUDE.md` sagt: **„Eine Aussage ohne §-Beleg ist eine Vermutung."** Ein Verweis
auf einen Abschnitt, den es nicht gibt, ist genau das — nur schwerer zu
erkennen als eine fehlende Angabe, weil er nach Beleg aussieht.

Gemessen am 24.08.2026: **2214 Verweise auf 110 Abschnitte**, davon zeigten
sieben ins Leere. Fünf waren Verweise auf andere Dokumente (RFC 8032 bei der
Ed25519-Umsetzung, ein Konzeptpapier bei der Skelettsitzung) und sind hier
ausgenommen, weil sie ihr Dokument nennen. Zwei blieben übrig, und die stehen
unten in `BEKANNT_OFFEN`.

Dazu hält diese Datei die **Kernverträge aus §9** am Code: Jede Klasse, die §9
als Dataclass zeigt, hat in `app/core/types.py` dieselben Felder in derselben
Folge, mit denselben Typen, Vorgaben und Dekoratorschaltern. Der Auszug lässt
Importe und Methoden weg, keine Felder — ein Feld, das nur der Code trägt,
steht mit Grund in `CODE_ONLY`.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

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


# --- Die Kernverträge aus §9 gegen app/core/types.py -------------------------

#: Die Überschriften, zwischen denen §9 steht.
CONTRACTS_FROM = "## 9. "
CONTRACTS_TO = "## 10. "

#: Die Dekoratorschalter, die §9 zeigen darf, mit der Vorgabe von ``@dataclass``.
FLAG_DEFAULTS: dict[str, bool] = {"frozen": False, "eq": True, "slots": False}

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


class PlanContract(NamedTuple):
    """Eine Dataclass aus §9: Dekoratorschalter und Felder in ihrer Folge."""

    flags: dict[str, bool]
    fields: tuple[PlanField, ...]


def contract_source() -> str:
    """Die Python-Blöcke aus §9 als ein Quelltext."""
    text = PLAN.read_text(encoding="utf-8")
    start = text.index("\n" + CONTRACTS_FROM)
    end = text.index("\n" + CONTRACTS_TO, start)
    return "\n".join(re.findall(r"```python\n(.*?)```", text[start:end], flags=re.DOTALL))


def _normal(annotation: str) -> str:
    """Ein Typ als Quelltext in der Schreibweise von ``ast.unparse``."""
    return ast.unparse(ast.parse(annotation, mode="eval"))


def _dataclass_flags(node: ast.ClassDef) -> dict[str, bool] | None:
    """Die Schalter des ``@dataclass``-Dekorators; ``None``, wenn er fehlt."""
    for decorator in node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = call.func if call is not None else decorator
        if not (isinstance(target, ast.Name) and target.id == "dataclass"):
            continue
        flags = dict(FLAG_DEFAULTS)
        for keyword in call.keywords if call is not None else ():
            assert keyword.arg in flags and isinstance(keyword.value, ast.Constant), (
                f"{node.name}: @dataclass({ast.unparse(keyword)}) vergleicht dieser Test "
                "noch nicht — FLAG_DEFAULTS ergänzen"
            )
            flags[keyword.arg] = bool(keyword.value.value)
        return flags
    return None


def plan_contracts() -> dict[str, PlanContract]:
    """Jede Klasse, die §9 als Dataclass zeigt."""
    found: dict[str, PlanContract] = {}
    for node in ast.parse(contract_source()).body:
        if not isinstance(node, ast.ClassDef):
            continue
        flags = _dataclass_flags(node)
        if flags is None:
            continue
        found[node.name] = PlanContract(
            flags,
            tuple(
                PlanField(
                    item.target.id,
                    _normal(ast.unparse(item.annotation)),
                    None if item.value is None else ast.unparse(item.value),
                )
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ),
        )
    return found


def _code_default(item: dataclasses.Field[Any]) -> str | None:
    """Die Vorgabe eines Codefeldes in der Schreibweise von §9."""
    if item.default is not dataclasses.MISSING:
        return repr(item.default)
    if item.default_factory is not dataclasses.MISSING:
        factory = item.default_factory
        return f"field(default_factory={getattr(factory, '__name__', repr(factory))})"
    return None


def contract_differences(plan: Mapping[str, PlanContract]) -> list[str]:
    """Jede Abweichung zwischen §9 und ``app/core/types.py``, je mit Klasse und Feld."""
    found: list[str] = []
    for name, contract in sorted(plan.items()):
        cls = getattr(contracts, name, None)
        if not isinstance(cls, type) or not dataclasses.is_dataclass(cls):
            found.append(f"{name}: in §9 eine Dataclass, in app/core/types.py nicht")
            continue
        params = cls.__dataclass_params__  # type: ignore[attr-defined]
        code_flags = {
            "frozen": params.frozen,
            "eq": params.eq,
            "slots": "__slots__" in cls.__dict__,
        }
        for flag, value in contract.flags.items():
            if code_flags[flag] != value:
                found.append(f"{name}: @dataclass {flag} in §9 {value}, im Code {code_flags[flag]}")

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
            annotation = _normal(actual.type if isinstance(actual.type, str) else repr(actual.type))
            if shown.annotation != annotation:
                found.append(
                    f"{name}.{field_name}: Typ in §9 {shown.annotation}, im Code {annotation}"
                )
            default = _code_default(actual)
            if shown.default != default:
                found.append(
                    f"{name}.{field_name}: Vorgabe in §9 {shown.default or 'keine'}, "
                    f"im Code {default or 'keine'}"
                )

        plan_order = [field_name for field_name in listed if field_name in code]
        code_order = [field_name for field_name in code if field_name in listed]
        if plan_order != code_order:
            found.append(f"{name}: Feldfolge in §9 {plan_order}, im Code {code_order}")
    return found


def test_the_plan_shows_the_core_contracts() -> None:
    """Ohne diese Zusicherung verglich alles darunter eine leere Menge."""
    plan = plan_contracts()

    assert len(plan) >= 12, f"nur {len(plan)} Dataclasses in §9 — das Muster greift nicht"
    for expected in ("Feature", "SceneObject", "OpContext", "OpResult", "LayerInfo", "Sketch"):
        assert expected in plan, f"§9 sollte {expected} zeigen"
        assert plan[expected].fields, f"§9 zeigt {expected} ohne Felder — das Muster greift nicht"


def test_every_contract_in_the_plan_matches_the_code() -> None:
    differences = contract_differences(plan_contracts())

    assert not differences, (
        "Bauplan §9 und app/core/types.py weichen ab — den Vertrag in §9 nachziehen "
        "(Bauplanänderung mit Ansage) oder den Code zurück auf den Vertrag:\n"
        + "\n".join(f"  {line}" for line in differences)
    )


def test_the_code_only_fields_are_still_code_only() -> None:
    """Wer ein Feld in §9 aufnimmt oder streicht, streicht es auch hier."""
    plan = plan_contracts()

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
    layer = plan["LayerInfo"]
    last = layer.fields[-1]
    first = layer.fields[0]
    with_default = next(item for item in layer.fields if item.default is not None)

    def drifted(fields: tuple[PlanField, ...], **flags: bool) -> list[str]:
        changed = PlanContract({**layer.flags, **flags}, fields)
        return contract_differences({**plan, "LayerInfo": changed})

    assert contract_differences(plan) == []
    assert drifted(layer.fields[:-1]) == [f"LayerInfo.{last.name}: im Code, fehlt in §9"]
    assert drifted((*layer.fields, PlanField("invented", "float", None))) == [
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
    assert drifted(layer.fields, frozen=not layer.flags["frozen"]) == [
        f"LayerInfo: @dataclass frozen in §9 {not layer.flags['frozen']}, "
        f"im Code {layer.flags['frozen']}"
    ]
