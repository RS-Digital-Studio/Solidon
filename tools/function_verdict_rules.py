"""Was ein Urteil gegen die Funddatei und die Vorhersage einhalten muss (RM-737, Paket F8).

Zwei Regeln aus der Zweitprüfung am finalen Lauf, die eine Lesart zur Folge
eines Belegs machen (Konzept §4, „Urteil und Schwere“):

* **„Gut nach Fix“ folgt aus der Funddatei** (M-Fix): genau an Zellen, an
  denen ein behobener Fund steht. Ein Prüfpunkt umfasst seine Kriterien
  (:data:`COVERS`): ein Fund an V5 gehört auch der Zelle von Prüfpunkt 7.
  Ein offener Fund an der Zelle hält sie offen — ein „gut“ dort wird
  abgewiesen.
* **V4 nur mit gebundener Vorhersage** (FD-148): ``prediction_bound`` nennt
  die Datei, die vor dem Klick freigegeben wurde, mit ihrem SHA256. Eine
  Vorhersage, die erst nach dem Lauf entstand, ist ein Teilbeleg und kein
  „gut“. Nennt die Bindung diesen Lauf, muss sein Vorhersagetor genau sie
  freigegeben haben (FD-168, ``tools/function_prediction.py``).

Aufgerufen aus ``function_report._verdict_problems``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Final

from tools.function_checks import CHECKPOINTS, DESIGN_PARTS

if TYPE_CHECKING:
    from tools.function_report import Finding

#: Ein Prüfpunkt umfasst seine Kriterien (Konzept §4): Ein Fund an einem
#: Kriterium gehört auch der Zelle des Punkts. 2 trägt den Weg (E1 bis E7, E2
#: als Paketwert), 7 die Meldungen (V5), 8 die Verständlichkeit (V1 bis V6),
#: 19 die Gestaltung (G, Z und I samt dem Paketwert I4).
COVERS: Final[dict[int, tuple[str, ...]]] = {
    2: tuple(sorted({*CHECKPOINTS[2].parts, "E2"})),
    7: CHECKPOINTS[7].parts,
    8: tuple(f"V{number}" for number in range(1, 7)),
    19: (*DESIGN_PARTS, "I4"),
}

#: Ein Fund gilt als behoben, wenn sein Stand so beginnt (Funddatei, Konzept §7).
FIXED_STANDS: Final = ("behoben", "gut nach Fix")

#: Gründe der Abweisung — die Gegenproben verlangen genau diese.
GOOD_OVER_OPEN: Final = "gut trotz offenem Fund an der Zelle"
GOOD_OVER_FIXED: Final = "„gut“, obwohl hier ein Fund behoben ist: gut_nach_fix"
FIX_WITHOUT_CELL: Final = "gut_nach_fix ohne behobenen Fund dieser Zelle"
UNBOUND_PREDICTION: Final = "V4 ohne vor dem Klick gebundene Vorhersage (prediction_bound)"
UNRELEASED_PREDICTION: Final = (
    "prediction_bound nennt keine Vorhersage, die das Vorhersagetor dieses Laufs freigab"
)

_SHA256: Final = re.compile(r"\b[0-9a-f]{64}\b")
_MACHINE_PATH: Final = re.compile(r"(?<!\w)[A-Za-z]:[\\/]")
#: Eine Rundenkennung vor dem Pfad (``v4:cases/…``, Plan D0 §2.9) — kein Laufwerk.
_ROUND_KEY: Final = re.compile(r"^[A-Za-z]\w+:")


def covered(subject: int | str | None) -> frozenset[int | str]:
    """Der Prüfpunkt oder das Kriterium selbst und, bei einem Punkt, seine Kriterien."""
    if subject is None:
        return frozenset()
    return frozenset({subject, *COVERS.get(subject, ())} if isinstance(subject, int) else {subject})


def cell_findings(
    row: str, subject: int | str | None, findings: Mapping[str, Finding]
) -> list[Finding]:
    """Die Funde einer Zelle: dieselbe Zeile und der Punkt selbst oder eines seiner Kriterien."""
    wanted = covered(subject)
    return [
        finding
        for finding in sorted(findings.values(), key=lambda f: f.number)
        if row in finding.rows and wanted & set(finding.subjects)
    ]


def fix_problems(
    entry: Mapping[str, Any], subject: int | str | None, findings: Mapping[str, Finding] | None
) -> list[str]:
    """Warum die Kennzeichnung eines Urteils nicht zur Funddatei passt (M-Fix).

    Gilt für *gut* und *gut nach Fix*; *offen* und *entfällt* nennen ihren Fund
    selbst. Ohne Funddatei wird nichts geprüft.
    """
    verdict = entry.get("verdict")
    if findings is None or verdict not in {"gut", "gut_nach_fix"}:
        return []
    cell = cell_findings(str(entry.get("row") or ""), subject, findings)
    problems = []
    if any(finding.stand.startswith("offen") for finding in cell):
        problems.append(GOOD_OVER_OPEN)
    fixed = sorted(
        (finding for finding in cell if finding.stand.startswith(FIXED_STANDS)),
        key=lambda f: f.number,
    )
    if verdict == "gut" and fixed:
        problems.append(f"{GOOD_OVER_FIXED} ({fixed[0].key})")
    if verdict == "gut_nach_fix" and str(entry.get("finding")) not in {f.key for f in fixed}:
        problems.append(FIX_WITHOUT_CELL)
    return problems


def prediction_problems(entry: Mapping[str, Any], subject: int | str | None) -> list[str]:
    """Warum eine Vorhersage zu V4 kein „gut“ trägt (FD-148).

    ``prediction_bound`` nennt Pfad und SHA256 der Vorhersagedatei, die vor dem
    Klick freigegeben wurde — relativ zum Lauf, ohne Laufwerk.
    """
    if subject != "V4" or entry.get("verdict") not in {"gut", "gut_nach_fix"}:
        return []
    bound = str(entry.get("prediction_bound") or "")
    if not _SHA256.search(bound) or _MACHINE_PATH.search(bound):
        return [UNBOUND_PREDICTION]
    return []


def releases_of(protocols: Iterable[Mapping[str, Any]]) -> dict[str, frozenset[str]]:
    """Je Zeile die Bindungen, die das Vorhersagetor dieses Laufs freigab (FD-168).

    Aus ``prediction.bound`` der Protokolle, Funktions- wie Sprachfall:
    Pfad relativ zum Lauf und SHA256 der Vorhersage vor dem Klick.
    """
    found: dict[str, set[str]] = {}
    for protocol in protocols:
        gate = protocol.get("prediction")
        row = protocol.get("row")
        row_id = str(row.get("id") if isinstance(row, Mapping) else row or "")
        if isinstance(gate, Mapping) and gate.get("bound"):
            found.setdefault(row_id, set()).add(" ".join(str(gate["bound"]).split()))
    return {row: frozenset(bounds) for row, bounds in found.items()}


def release_problems(
    entry: Mapping[str, Any],
    subject: int | str | None,
    releases: Mapping[str, frozenset[str]] | None,
) -> list[str]:
    """Eine Bindung an diesen Lauf muss eine sein, die sein Vorhersagetor freigab (FD-168).

    Eine Bindung mit Rundenkennung davor (``v4:cases/…``) gehört einem anderen
    Lauf; sie prüft hier nur ihre Form (:func:`prediction_problems`). Ohne die
    Protokolle des Laufs (``releases`` ``None``) wird nichts geprüft.
    """
    bound = " ".join(str(entry.get("prediction_bound") or "").split())
    if subject != "V4" or releases is None or not bound:
        return []
    if _ROUND_KEY.match(bound):
        return []
    if bound not in releases.get(str(entry.get("row") or ""), frozenset()):
        return [UNRELEASED_PREDICTION]
    return []


def bound_problems(entry: Mapping[str, Any]) -> list[str]:
    """``prediction_bound`` gehört zu einer Vorhersage an V4 — anderswo ist es ein Fehler."""
    if "prediction_bound" not in entry:
        return []
    problems: list[str] = []
    if entry.get("criterion") != "V4":
        problems.append("prediction_bound an einem Urteil, das nicht V4 ist")
    if not str(entry.get("prediction") or "").strip():
        problems.append("prediction_bound ohne die Vorhersage selbst")
    return problems
