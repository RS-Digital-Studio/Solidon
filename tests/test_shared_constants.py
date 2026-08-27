"""Eine Auskunft wird an einer Stelle hergeleitet, nicht an dreien.

Am 27.08.2026 standen sechs Zahlen mehrfach im Kern, und in vier Fällen sagte
der Kommentar der Kopie es selbst: „wie bei den Farb-Operationen", „dieselbe
Zahl und derselbe Grund wie bei der Beschriftung", „dieselbe Schwelle, an der
die Fleckenbildung trennt". Ein Verweis auf die Kopie ist keine geteilte Sache
— er wandert beim nächsten Anfassen nicht mit.

Solange alle Kopien denselben Wert tragen, kostet das nichts. Der Preis fällt
an, wenn jemand **eine** davon ändert:

* ``MAX_SLOTS`` an zwei von drei Stellen erhöht, und zwei Operationen erlauben
  danach mehr Filamente als die dritte.
* ``OVERHANG_LIMIT_DEGREES`` von 45 auf 50 gesetzt — die Schichtanalyse führte
  dieselbe Linie als Faktor ``1.0``, also *als Winkel gar nicht auffindbar*.
  Die Orientierungssuche hätte danach eine Lage empfohlen, die die
  Schichtanalyse am selben Teil als Überhang meldet.

Der Test prüft die Bauform, nicht die Werte: Eine Konstante des Kerns wird an
genau einer Stelle definiert. Wer sie anderswo braucht, importiert sie.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "app" / "core"

#: Am Bestand gemessen (27.08.2026): 412. Die Zahl darf wachsen und schrumpfen
#: — sie steht hier, damit ein Test über eine **leere** Menge auffällt, statt
#: grün zu melden, dass alles in Ordnung sei (siehe ``.claude/rules/tests.md``).
FLOOR = 300

#: Namen, die absichtlich mehrfach vorkommen. Kuratiert wie ``GERMAN_STEMS`` in
#: :mod:`tests.test_language_rules`: Wer einen Eintrag hinzufügt, schreibt den
#: Grund daneben — und der Grund muss „zwei verschiedene Sachen, die zufällig
#: gleich heißen" sein, nie „ist halt so".
DELIBERATE: dict[str, str] = {}


def _constants() -> dict[str, list[tuple[str, object]]]:
    """Jede Konstante des Kerns mit den Dateien, die sie definieren.

    Gelesen werden Zuweisungen auf **Modulebene** mit einem Namen in
    Großbuchstaben und einem Wert, der sich ohne Ausführung ermitteln lässt.
    Ein abgeleiteter Wert (``math.tan(...)``) fällt damit heraus, und das ist
    richtig: Er *ist* die Ableitung, um die es hier geht.
    """
    found: dict[str, list[tuple[str, object]]] = defaultdict(list)
    for path in sorted(CORE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — nur bei kaputtem Baum
            continue
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                if not (name.isupper() and len(name) > 3) or node.value is None:
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    continue
                found[name].append((path.name, value))
    return found


def test_the_core_defines_each_constant_in_one_place() -> None:
    """Kein Name des Kerns trägt zweimal denselben Wert."""
    found = _constants()
    total = sum(len(places) for places in found.values())
    assert total > FLOOR, f"nur {total} Konstanten gefunden — prüft der Test noch etwas?"

    twins = {
        name: places
        for name, places in found.items()
        if name not in DELIBERATE and len(places) > 1 and len({value for _, value in places}) == 1
    }
    assert not twins, (
        "dieselbe Zahl an mehr als einer Stelle — eine davon wird eines Tages "
        f"allein geändert: {ancestry(twins)}"
    )


def ancestry(twins: dict[str, list[tuple[str, object]]]) -> str:
    """Die Fundstellen in einer Zeile, damit die Meldung ohne Nachschlagen
    trägt."""
    return "; ".join(
        f"{name}={places[0][1]!r} in {sorted(file for file, _ in places)}"
        for name, places in sorted(twins.items())
    )
