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
import operator
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


#: Rechenzeichen, die zwischen zwei Zahlen noch einen festen Wert ergeben.
#:
#: Kein ``eval`` (Regel 10): Aufgelöst wird ein Syntaxbaum aus Zahlen und
#: diesen Zeichen, und ein Name darin bricht die Auswertung ab.
ARITHMETIC: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}


def value_of(node: ast.expr) -> object | None:
    """Der feste Wert hinter einem Ausdruck — Literal oder Rechnung darüber.

    **``literal_eval`` allein reicht nicht, und das hat diesen Test blind
    gemacht.** Eine Größenangabe schreibt niemand als ``65536``; sie steht als
    ``64 * 1024``, und daran scheitert ``ast.literal_eval`` mit ``ValueError``
    — die Konstante fiel damit aus der Erhebung, ohne dass jemand es merkte.
    Gefunden wurde die Lücke am 27.08.2026 über einen Zwilling, den der Test
    hätte melden müssen: ``MAX_ANSWER_BYTES`` stand in ``updates.py`` und
    ``support.py``, beide Male ``64 * 1024``.

    Das ist die Fehlerrichtung, vor der ``.claude/rules/tests.md`` warnt: Zu
    wenig zu finden erzeugt die Gewissheit, es sei nichts da — und ein Prüfer,
    der schweigt, sieht aus wie einer, der nichts findet.

    Ein Aufruf (``math.tan(...)``) bleibt draußen, und das ist weiter richtig:
    Er *ist* die Ableitung, um die es hier geht.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        pass
    if isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC:
        left, right = value_of(node.left), value_of(node.right)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            try:
                return ARITHMETIC[type(node.op)](left, right)
            except (ZeroDivisionError, OverflowError):
                return None
    return None


def _constants() -> dict[str, list[tuple[str, object]]]:
    """Jede Konstante des Kerns mit den Dateien, die sie definieren.

    Gelesen werden Zuweisungen auf **Modulebene** mit einem Namen in
    Großbuchstaben und einem Wert, den :func:`value_of` ohne Ausführung
    ermitteln kann.
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
                value = value_of(node.value)
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
