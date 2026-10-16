"""Übereinstimmung zweier Prüfer im Funktionsdurchgang (RM-737, Konzept §4 und §10).

Ein zweiter Prüfer urteilt einen Teil der Zeilen unabhängig. Gemessen wird je
Prüfpunkt und Kriterium, wie viele Zellen beide gleich urteilen; unter 90 %
wird das Kriterium geschärft.

* **Die Runde ist die Grundmenge** (FD-145, Entscheidung Koordinator
  15.10.2026): Bindend ist die Übereinstimmung über alle Pakete einer
  Urteilsrunde — alle Urteilsdateien, die denselben Laufordner nennen. Bei
  zwei bis drei Zweitprüferzeilen je Paket hieße 90 % sonst „keine
  Abweichung“, und das ist keine Messung. Die Werte je Paket stehen zur
  Auskunft in der Abhakliste.
* **Zellen ohne Gegenurteil werden gezählt, nicht verschwiegen** (FD-144): An
  einer Zeile, die der Zweitprüfer urteilt, ist jede Zelle mit nur einem der
  beiden Urteile ausgewiesen. Ein Prüfpunkt, an dem es nur solche gibt, hat
  keinen Übereinstimmungswert — er ist nicht gemessen, nie erfüllt.

Aufgerufen aus ``tools/function_report.py`` (Paketwerte und Abhakliste).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from tools.function_checks import AGREEMENT

#: Die zwei Prüfer, deren Urteile verglichen werden (Konzept §4).
FIRST: Final = "stufe_b"
SECOND: Final = "zweitpruefer"


@dataclass(frozen=True)
class Share:
    """Ein gemessener Anteil gegen seine Schwelle."""

    hits: int
    total: int
    threshold: float

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None

    @property
    def flagged(self) -> bool:
        """Unter der Schwelle — oder gar nicht gemessen, was nie „erfüllt“ heißt."""
        return self.value is None or self.value < self.threshold

    def text(self) -> str:
        if self.value is None:
            return "nicht gemessen"
        return f"{self.value:.0%} ({self.hits} von {self.total})"


def subject_of(entry: Mapping[str, Any]) -> int | str | None:
    """Prüfpunkt oder Kriterium eines Urteils — die eine Quelle für Prüfung und Übereinstimmung.

    Ein Prüfpunkt ist eine ganze Zahl; was keine ist, ist kein Prüfpunkt (``None``).
    """
    if "point" in entry:
        point = entry["point"]
        return point if isinstance(point, int) else None
    criterion = entry.get("criterion")
    return str(criterion) if criterion is not None else None


def subject_order(subject: int | str) -> tuple[int, int, str]:
    """Prüfpunkte nach Nummer, dann Kriterien in der Reihenfolge E, V, G, Z, I."""
    if isinstance(subject, int) or str(subject).isdigit():
        return (0, int(subject), "")
    key = str(subject)
    return (1, "EVGZI".find(key[:1]), key)


def _cells(entries: Iterable[Mapping[str, Any]]) -> tuple[dict[tuple[str, str], str], ...]:
    """Die Urteile beider Prüfer je Zelle (Zeile, Prüfpunkt)."""
    first: dict[tuple[str, str], str] = {}
    second: dict[tuple[str, str], str] = {}
    for entry in entries:
        key = (str(entry.get("row")), str(subject_of(entry)))
        if entry.get("reviewer") == FIRST:
            first[key] = str(entry.get("verdict"))
        elif entry.get("reviewer") == SECOND:
            second[key] = str(entry.get("verdict"))
    return first, second


def agreement(entries: Iterable[Mapping[str, Any]]) -> dict[str, Share]:
    """Übereinstimmung von Stufe B und Zweitprüfer je Prüfpunkt und Kriterium.

    Gezählt werden die Zellen, die beide geurteilt haben. Ein Prüfpunkt, der an
    den Zeilen des Zweitprüfers nur Zellen ohne Gegenurteil hat, steht mit
    „nicht gemessen“ da (0 von 0) — er braucht Paare, sonst ist er nicht
    gemessen (FD-144).
    """
    first, second = _cells(entries)
    pairs: dict[str, list[bool]] = {}
    for key in sorted(set(first) & set(second)):
        pairs.setdefault(key[1], []).append(first[key] == second[key])
    for _row, subject in unpaired_cells(first, second):
        pairs.setdefault(subject, [])
    return {
        subject: Share(sum(same), len(same), AGREEMENT)
        for subject, same in sorted(pairs.items(), key=lambda item: subject_order(item[0]))
    }


def unpaired_cells(
    first: Mapping[tuple[str, str], str], second: Mapping[tuple[str, str], str]
) -> list[tuple[str, str]]:
    """Zellen an Zeilen des Zweitprüfers, die nur einer der beiden geurteilt hat."""
    reviewed = {row for row, _subject in second}
    return sorted(key for key in set(first) ^ set(second) if key[0] in reviewed)


def unpaired(entries: Iterable[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Je Prüfpunkt die Zeilen, an denen nur ein Prüfer urteilte (FD-144).

    Nur an Zeilen des Zweitprüfers: Dort sollten beide jede Zelle urteilen, die
    an der Zeile gilt. Wer nur eine Seite hat, fehlt in der Übereinstimmung —
    und das steht in der Abhakliste, statt still herauszufallen.
    """
    first, second = _cells(entries)
    found: dict[str, list[str]] = {}
    for row, subject in unpaired_cells(first, second):
        side = FIRST if (row, subject) in first else SECOND
        found.setdefault(subject, []).append(f"{row} (nur {side})")
    return {
        subject: tuple(rows)
        for subject, rows in sorted(found.items(), key=lambda item: subject_order(item[0]))
    }


@dataclass(frozen=True)
class Round:
    """Die Übereinstimmung einer Urteilsrunde über alle ihre Pakete (FD-145)."""

    run: str
    packages: tuple[str, ...]
    shares: Mapping[str, Share]
    unpaired: Mapping[str, tuple[str, ...]]


def round_agreement(run: str, packages: Mapping[str, Iterable[Mapping[str, Any]]]) -> Round:
    """Die Übereinstimmung gepoolt über alle Pakete eines Laufs — der bindende Wert.

    ``packages`` sind die angenommenen Urteile je Paket, alle zu demselben
    Laufordner ``run``. Zeilenkennungen sind über die Pakete eindeutig; gepoolt
    heißt also: alle Zellen aller Pakete zusammen.
    """
    pooled = [dict(entry) for entries in packages.values() for entry in entries]
    return Round(
        run=run,
        packages=tuple(
            sorted(packages, key=lambda name: int(name[1:]) if name[1:].isdigit() else 0)
        ),
        shares=agreement(pooled),
        unpaired=unpaired(pooled),
    )


def checklist_lines(
    shares: Mapping[str, Share], gaps: Mapping[str, tuple[str, ...]], pooled: Round | None
) -> list[str]:
    """Die Zeilen der Übereinstimmung in den Paketwerten der Abhakliste.

    Bindend und markiert wird der Wert der Runde; ohne Runde ist das Paket
    seine eigene. Die Werte des Pakets stehen daneben als Auskunft, die Zellen
    ohne Gegenurteil der Runde markiert.
    """
    threshold = f"≥ {AGREEMENT:.0%}"
    binding = pooled.shares if pooled is not None else shares
    missing = pooled.unpaired if pooled is not None else gaps
    lines = []
    if pooled is not None:
        lines.append(f"| Runde | {pooled.run}: {', '.join(pooled.packages)} | — | — |")
    if not binding:
        lines.append(f"| Übereinstimmung | keine Doppelprüfung | {threshold} | markiert |")
    for subject, share in binding.items():
        stand = "markiert" if share.flagged else "erfüllt"
        lines.append(
            f"| Übereinstimmung {subject} in der Runde | {share.text()} | {threshold} | {stand} |"
        )
    if pooled is not None:
        lines += [
            f"| Übereinstimmung {subject} im Paket | {share.text()} | Auskunft | — |"
            for subject, share in shares.items()
        ]
    for subject, rows in missing.items():
        cells = "1 Zelle" if len(rows) == 1 else f"{len(rows)} Zellen"
        named = ", ".join(rows).replace("|", "\\|")
        lines.append(
            f"| Ohne Gegenurteil {subject} | {cells}: {named} | Paar je Zelle | markiert |"
        )
    return lines
