"""Jeder §-Verweis im Quelltext zeigt auf einen Abschnitt, den der Bauplan hat.

`CLAUDE.md` sagt: **„Eine Aussage ohne §-Beleg ist eine Vermutung."** Ein Verweis
auf einen Abschnitt, den es nicht gibt, ist genau das — nur schwerer zu
erkennen als eine fehlende Angabe, weil er nach Beleg aussieht.

Gemessen am 24.08.2026: **2214 Verweise auf 110 Abschnitte**, davon zeigten
sieben ins Leere. Fünf waren Verweise auf andere Dokumente (RFC 8032 bei der
Ed25519-Umsetzung, ein Konzeptpapier bei der Skelettsitzung) und sind hier
ausgenommen, weil sie ihr Dokument nennen. Zwei blieben übrig, und die stehen
unten in `BEKANNT_OFFEN`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

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
