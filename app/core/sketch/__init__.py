"""Skizzen mit Zwangsbedingungen (Bauplan §30.1).

Das Datenmodell steht als Vertrag in ``app.core.types`` (§9); hier lebt der
Solver. Kein Qt, keine Dialoge — der Kern rechnet, die Oberfläche fragt.
"""

from app.core.sketch.solver import solve_sketch

__all__ = ["solve_sketch"]
