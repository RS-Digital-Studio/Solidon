"""Ein Wert als Literal für TOML und OpenSCAD — eine Schreibweise für beide.

Der Quelltext-Export (``scad.py``) und die Kalibrierdatei
(``knowledge/calibration.py``) schrieben Werte mit zwei wortgleichen
Funktionen; jetzt mit einer (RA-11). Beide Formate lesen ``true``/``false``,
Zahlen wie Python sie schreibt, Listen in eckigen Klammern und Zeichenketten
mit denselben Fluchtzeichen wie JSON.
"""

from __future__ import annotations

import json


def literal(value: object) -> str:
    """``value`` als Literal: Wahrheitswert klein, Liste in Klammern, Text maskiert."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(literal(entry) for entry in value) + "]"
    if isinstance(value, str):
        # Wie JSON maskiert: Ein Anführungszeichen im Materialtitel — „PLA "matt"" —
        # machte die Kalibrierdatei sonst unlesbar, und ein Freitextfeld eines
        # Bausteins bräche den Quelltext am ersten Anführungszeichen.
        return json.dumps(value, ensure_ascii=False)
    return f"{value}"
