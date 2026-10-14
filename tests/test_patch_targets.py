"""W2: Jeder Patch in ``tests/`` trifft, was er meint.

**Warum es diese Datei gibt** (Konzept Codestruktur 4.1, Plan Schritt 0, 2.2).
``monkeypatch.setattr(M, "N", …)`` ersetzt den Namen ``N`` in ``M`` — erreicht
aber nur, wer ihn zur Aufrufzeit über ``M`` liest. Ein Modul, das ``N`` beim
Import kopiert hat (``from M import N``), sieht den Patch nie; ein Patch auf
einen Namen, den niemand mehr liest, prüft nichts; ``raising=False`` macht aus
einem Tippfehler einen stillen Erfolg (CS-9, CS-11). Nach einem Schnitt, der
Namen in neue Module verschiebt, wird jeder dieser Fälle häufiger. Geprüft wird
über ``tools/code_index.py``, an jeder Patch-Stelle in ``tests/`` einschließlich
``conftest.py``:

a) Jedes Ziel auf einem Modul aus ``app/`` oder ``tools/`` löst auf: Modul und
   Name existieren.
b) Kein ``raising=False`` auf einem Modul aus ``app/`` oder ``tools/``.
c) Kein Modul in ``app/`` oder ``tools/`` hält eine Kopfkopie eines Namens, den
   ein Test am Original patcht.
d) Die Lesermenge jedes gepatchten ``M.N`` ist nicht leer — zugleich die
   statische Gegenprobe jedes Verbotspatches (Entscheidung E8). Lädt der Test
   ein Modul nach dem Patch mit ``importlib.reload`` neu, zählt auch, was es
   beim Import liest; seine Kopfkopie ist dann kein Fund für c).
e) Ziel und Name lösen sich nach der Konstantenfaltung statisch auf. Was sich
   nicht auflöst, ist ein Fund: Der Test wird umgeschrieben, eine Ausnahmeliste
   gibt es nicht.

Die roten Fälle der Attrappe und die Bekanntfälle stehen in
``test_code_index.py``.

**Scharf schalten.** Die Regeln, deren heutige Funde andere Pakete von Schritt 0
beheben, tragen ``xfail(strict=True)`` mit dem Paket im Grund. Wird eine Regel
grün, macht ``strict`` den Lauf rot (XPASS); wer sie grün gemacht hat, streicht
im selben Commit die Markierung. ``raises=AssertionError`` hält einen Absturz
des Auflösers rot.
"""

from __future__ import annotations

import pytest

from tools.code_index import Finding, Index, shared

#: Die Grundmenge aus dem Plan (2.2): mehr Patch-Stellen als das.
LEAST_PATCH_SITES = 3000


def _index() -> Index:
    return shared()


def _report(findings: tuple[Finding, ...]) -> str:
    lines = [f"{len(findings)} Funde:"]
    lines.extend(f"  {f.path}:{f.line}  {f.module}.{f.name}  {f.detail}" for f in findings)
    return "\n".join(lines)


def test_the_ground_set_holds_every_patch_site() -> None:
    """Ohne Patch-Stellen wäre jede Regel grün, weil nichts geprüft wurde."""
    sites = _index().patch_sites()
    assert len(sites) > LEAST_PATCH_SITES, len(sites)
    own = [t for s in sites for t in s.targets if t.status == "module"]
    assert len(own) > LEAST_PATCH_SITES, len(own)
    assert _index().head_copies(), "keine Kopfkopie gefunden: der Auflöser liest nichts"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="scharf, wenn P1 die Originale discover.unpatched_* und llm.unpatched_backends "
    "als Fixture führt (Plan 1.6, #1 bis #3)",
)
def test_rule_a_every_target_on_an_own_module_exists() -> None:
    """Ein Patch auf einen Namen, den es nicht gibt, legt ihn an — mit ``raising=False``
    still, sonst laut. Beides prüft dann nichts."""
    findings = _index().patch_findings()["a"]
    assert not findings, _report(findings)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="scharf, wenn P1 (9 Stellen) und Q (3 Stellen) raising=False auf app.* "
    "gestrichen haben (Plan 1.6, Entscheidung E2)",
)
def test_rule_b_no_raising_false_on_an_own_module() -> None:
    """``raising=False`` verdeckt, dass ein Name fehlt — nach einem Schnitt der häufigste
    Fall (Konzept 3.1, Regel 3)."""
    findings = _index().patch_findings()["b"]
    assert not findings, _report(findings)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="scharf mit K: move_names copies stellt die Kopfkopien gepatchter Namen auf "
    "Modulzugriff um (CS-11, Entscheidung E1); CS-9a behebt P1",
)
def test_rule_c_no_head_copy_of_a_name_patched_at_its_original() -> None:
    """Eine Kopfkopie hält den alten Wert; der Patch am Original erreicht sie nie."""
    findings = _index().patch_findings()["c"]
    assert not findings, _report(findings)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="scharf, wenn P2 _cost_matrix (CS-9b), P1 configured_spools (CS-9a) und der "
    "Verbotspatch auf sign_release.run (test_sign_release.py:789, neuer Punkt) behoben sind",
)
def test_rule_d_every_patched_name_is_read_by_somebody() -> None:
    """Wer einen Namen patcht, den niemand zur Aufrufzeit liest, prüft nichts — auch ein
    Verbotspatch („darf nicht gerufen werden“) wäre dann grün, ohne dass der Aufruf je
    erreicht wird (Entscheidung E8)."""
    findings = _index().patch_findings()["d"]
    assert not findings, _report(findings)


def test_rule_e_every_target_resolves_statically() -> None:
    """Ein Ziel, das sich nicht statisch auflösen lässt, kann kein Wächter prüfen — und
    nach einem Schnitt kein Werkzeug umschreiben (Konzept 4.1)."""
    findings = _index().patch_findings()["e"]
    assert not findings, _report(findings)
