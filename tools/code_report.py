"""Berichte des Auflösers als Text: das Inventar (``--inventory``) und der Lesermengenabzug
(``--reach``) von ``tools/code_index.py``. Getrennt vom Auflöser, weil sie nur lesen, was er
beantwortet; ``code_index`` reicht beide unter ihrem alten Namen weiter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tools.code_facts import AREAS, INDEXED

if TYPE_CHECKING:
    from tools.code_index import Index

#: Die Quelle, wie dieser Prozess sie geladen hat; ``tools.code_store`` bildet daraus den
#: Stand des Auflösers, nicht aus der Platte (RR2-1).
_SOURCE = Path(__file__).read_bytes()


def inventory(index: Index) -> str:
    """Das Inventar als Text: Grundmengen, W2 a bis e, W5, Kopfkopien, Laufzeit."""
    sites = index.patch_sites()
    findings = index.patch_findings()
    unresolved = index.unresolved()
    heads = index.head_copies()
    areas = {area: sum(1 for f in index.files.values() if f.area == area) for area in AREAS}
    lines = [f"Codeindex über {index.root}", ""]
    lines.append(
        "Dateien: "
        + ", ".join(f"{area} {count}" for area, count in areas.items())
        + f"; Zeilen {sum(f.lines for f in index.files.values())}"
    )
    lazy = sum(1 for facts in index.modules.values() if facts.exports)
    stubs = sum(1 for facts in index.files.values() if facts.stub)
    names = sum(len(facts.scopes[0].binds) for facts in index.modules.values())
    lines.append(
        f"Module: {len(index.modules)}, Pakete {len(index.packages)}, Lazy-Pakete {lazy}, "
        f"Stubs {stubs}, Namen auf Modulebene {names}"
    )
    imports = [imp for facts in index.files.values() for imp in facts.imports]
    lines.append(
        f"Importe: {len(imports)} (from {sum(i.kind == 'from' for i in imports)}, "
        f"import {sum(i.kind == 'import' for i in imports)}, "
        f"dynamisch {sum(i.kind == 'dynamic' for i in imports)}; "
        f"spät {sum(i.runtime for i in imports)}, "
        f"unter TYPE_CHECKING {sum(i.checking for i in imports)})"
    )
    statuses: dict[str, int] = {}
    forms: dict[str, int] = {}
    for site in sites:
        forms[site.form] = forms.get(site.form, 0) + 1
        for target in site.targets:
            statuses[target.status] = statuses.get(target.status, 0) + 1
    lines.append(
        f"Patch-Stellen in tests/: {len(sites)} ("
        + ", ".join(f"{form} {count}" for form, count in sorted(forms.items()))
        + "); Ziele: "
        + ", ".join(f"{status} {count}" for status, count in sorted(statuses.items()))
    )
    lines.append(f"Gepatchte Namen in app/tools: {len(index.patched_names())}")
    copies_from = sum(c.kind == "from" for c in heads)
    lines.append(
        f"Kopfkopien in app/tools: {len(heads)} (from {copies_from}, "
        f"Zuweisung {len(heads) - copies_from})"
    )
    refs = sum(count for key, count in index.counts.items() if key.startswith("refs."))
    lines.append(
        f"Bezüge auf Namen: {refs - index.counts.get('refs.empty', 0)}, "
        f"davon ohne gefaltete Zeile {index.counts.get('refs.empty', 0)}"
    )
    absent = {key: count for key, count in index.counts.items() if key.startswith("absent.")}
    if absent:
        lines.append(
            "Abfragen auf fehlende Namen, kein W5-Fund: "
            + ", ".join(f"{key[7:]} {count}" for key, count in sorted(absent.items()))
        )
    scripts = {key[8:]: count for key, count in index.counts.items() if key.startswith("scripts.")}
    lines.append(
        f"Skripte für python -c: {scripts.get('sites', 0)} Stellen, "
        f"{scripts.get('read', 0)} Texte gelesen ({scripts.get('template', 0)} Stellen mit "
        f"Platzhalter), {scripts.get('open', 0)} nicht faltbar, "
        f"{scripts.get('unparsed', 0)} kein Python"
    )
    lines.append("")
    for rule in "abcde":
        items = findings[rule]
        lines.append(f"W2 {rule}): {len(items)}")
        if rule == "c":
            originals = {f.detail.rpartition(" von ")[2] for f in items}
            holders = {f.module for f in items}
            by_area = {a: sum(1 for f in items if f.path.startswith(a + "/")) for a in INDEXED}
            lines.append(
                f"   {len(originals)} Originale in {len(holders)} Haltern; "
                f"app {by_area['app']}, tools {by_area['tools']}"
            )
        lines.extend(
            f"   {f.path}:{f.line}  {f.module}.{f.name}  {f.detail}".rstrip() for f in items
        )
    lines.append("")
    kinds: dict[str, int] = {}
    for item in unresolved:
        kinds[item.kind] = kinds.get(item.kind, 0) + 1
    lines.append(
        f"W5: {len(unresolved)} unaufgelöst ("
        + ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items()))
        + ")"
    )
    lines.extend(
        f"   {u.path}:{u.line}  [{u.kind}] {u.module}.{u.name}  {u.text}" for u in unresolved
    )
    lines.append("")
    lines.append(
        f"Laufzeit: Lesen {index.timings.get('read', 0.0):.1f} s "
        f"({index.counts.get('extracted', 0)} Dateien ausgezogen, "
        f"{index.counts.get('cached', 0)} aus dem Zwischenspeicher), "
        f"Auflösen {index.timings.get('resolve', 0.0):.1f} s"
    )
    return "\n".join(lines)


def reach_text(index: Index) -> str:
    """Der Lesermengenabzug als Text, je gepatchtem Namen eine Zeile."""
    return "\n".join(
        f"{module}:{name} <- {', '.join(readers) or '(niemand)'}"
        for (module, name), readers in index.reach_dump().items()
    )
