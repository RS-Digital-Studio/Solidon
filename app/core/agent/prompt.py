"""The system prompt (Bauplan §26.1, §39).

Versioned, because every transaction records which prompt produced it (§26.4).
Change the text, raise the version — otherwise a project file claims to have
been made under a prompt that no longer exists.

The four sentences at the end are the ones §26.5 wants anchored here and
measured in the suite: parts before primitives, an operation list before
OpenSCAD, parameters before numbers, questions before guessing.
"""

from __future__ import annotations

from app.core.knowledge import rules

#: Raised whenever the text below changes (§26.4).
PROMPT_VERSION = "1"

_ROLE = """
Du bist der Konstruktionsassistent von Formwerk, einer Anwendung für druckbare
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
    """Role, rules and habits — everything the model has to know before it starts."""
    active = rule_set or rules.load()
    parts = [
        _ROLE.strip(),
        _RULES_HEADER.format(version=active.version),
        active.as_text(),
        _HABITS.strip(),
    ]
    return "\n\n".join(parts)
