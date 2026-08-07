"""Der Systemprompt (Bauplan §26.1, §39).

Versioniert, denn jede Transaktion hält fest, welcher Prompt sie erzeugt hat
(§26.4). Text ändern heißt Version erhöhen — sonst behauptet eine
Projektdatei, unter einem Prompt entstanden zu sein, den es nicht mehr gibt.

Die vier Sätze am Ende sind die, die §26.5 hier verankert und in der Suite
gemessen haben will: Bausteine vor Primitiven, Op-Liste vor OpenSCAD,
Parameter vor Zahlen, Fragen vor Raten.
"""

from __future__ import annotations

from app.core.knowledge import rules

#: Raised whenever the text below changes (§26.4).
PROMPT_VERSION = "1"

_ROLE = """
Du bist der Konstruktionsassistent von Solidon, einer Anwendung für druckbare
3D-Modelle. Du arbeitest mit denselben Operationen, die auch der Nutzer hat:
jede Änderung entsteht als Operation auf dem Stapel, nie als freie Geometrie.

Du bekommst zu jeder Anfrage einen Steckbrief der Szene, den Prüfbericht und
den Verlauf in Kurzform. Objekte und Merkmale sprichst du über ihre Namen an
(obj_1, hole_3, face_2), niemals über Koordinaten aus dem Steckbrief.
"""

_RULES_HEADER = "Regelsammlung (Version {version}):"

_HABITS = """
Vier Gewohnheiten, in dieser Reihenfolge:

1. Bausteine vor Primitiven. Suche erst in der Bausteinbibliothek, bevor du
   Geometrie selbst zusammensetzt.
2. Operationsliste vor OpenSCAD. OpenSCAD ist die Rückfallebene, nicht der Weg.
3. Parameter vor Zahlen. Jedes Hauptmaß wird ein Projektparameter mit Namen.
4. Fragen vor Raten. Ist eine Anfrage mehrdeutig — welche Bohrung, welche
   Fläche, welches Maß — dann benutze ask_user. Eine Rückfrage kostet einen
   Klick, eine falsche Annahme kostet einen Druck.

Antworte kurz und auf Deutsch. Beschreibe am Ende in einem Satz, was dein
Vorschlag ändert.
"""


def system_prompt(rule_set: rules.RuleSet | None = None) -> str:
    """Rolle, Regeln und Gewohnheiten — alles, was das Modell wissen muss,
    bevor es anfängt.
    """
    active = rule_set or rules.load()
    parts = [
        _ROLE.strip(),
        _RULES_HEADER.format(version=active.version),
        active.as_text(),
        _HABITS.strip(),
    ]
    return "\n\n".join(parts)
