"""Das Register der ROADMAP auf den Stand dieser Sitzung bringen."""

from __future__ import annotations

from pathlib import Path

SECTION = "Die Oberflächendurchsicht, zweiter Teil (20.08.2026)"

OLD_KEYS = (
    "| Nackte Tasten gehören dem Fokus | "
    + SECTION
    + " | eine Regel, die Pos1 an die Liste gibt, ohne den Ziffern 1 bis 6 ihre Wirkung zu "
    "nehmen — der Viewport hat `NoFocus` und kann sie nicht halten |\n"
)
OLD_SPLIT = (
    "| Der Trennen-Bereich und seine 130 Punkte Totraum | "
    + SECTION
    + " | die echte Plattform — offscreen rechnet Qt ohne Schriftfamilien andere Metriken und "
    "liefert das Gegenteil |\n"
)
NEW_ROW = (
    "| Ein Höhenbudget für den Startbildschirm | "
    + SECTION
    + " | eine Entscheidung darüber, **was** kleiner wird — Kachelhöhe, Ablagefläche oder die "
    "Liste der zuletzt geöffneten Projekte; Umschichten ist ausgereizt |\n"
)

path = Path("ROADMAP.md")
text = path.read_text(encoding="utf-8")
assert text.count(OLD_KEYS) == 1, "die Zeile zu den nackten Tasten steht nicht so da"
assert text.count(OLD_SPLIT) == 1, "die Zeile zum Trennen-Bereich steht nicht so da"
text = text.replace(OLD_KEYS, NEW_ROW).replace(OLD_SPLIT, "")
path.write_text(text, encoding="utf-8")
print("Register aktualisiert")
