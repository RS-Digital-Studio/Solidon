"""Zwei Kürzelbelegungen, eine Quelle (Konzept P15 §7 Etappe 8, E7).

Das Kürzel einer Operation steht im Register (§10, Leitprinzip 3). Diese
Tabelle legt sich darüber, so wie die Menügruppen aus P14 sich über die
Kategorien legen: sie erfindet nichts, sie ordnet um.

**Warum überhaupt zwei.** Wer aus Fusion, Onshape oder SolidWorks kommt, hat
`E` für Extrudieren und `F` für Verrunden in den Fingern; ihn zu zwingen,
`Strg+B` zu lernen, kostet ihn bei jedem Griff eine Zehntelsekunde und uns den
Satz „fühlt sich fremd an". Wer von Solidon kommt, will das Gegenteil. Beide
zu bedienen ist eine Tabelle, keine Weltanschauung.

Die Vorgabe bleibt die heutige. Eine Umstellung ist eine Einstellung, kein
Modus (§2.5) — sie ändert nur, welche Taste welchen Menüeintrag auslöst.
"""

from __future__ import annotations

from typing import Final

from app.i18n import TranslatableText, _

#: Der Fusion-nahe Satz: einzelne Buchstaben für das, was man dauernd tut.
#: Nur Operationen stehen darin — die Fensterbefehle (Speichern, Öffnen,
#: Rückgängig) sind überall dieselben und werden nicht angefasst.
FUSION: Final[dict[str, str]] = {
    "sketch_extrude": "E",
    "push_face": "Q",
    "fillet_edges": "F",
    "chamfer_edges": "C",
    "translate_object": "M",
    "rotate_object": "R",
    "drill_hole": "H",
    "duplicate_object": "Ctrl+D",
    "mirror_object": "Ctrl+M",
    "pattern": "P",
    "shell_exact": "S",
}

#: Die Belegungen mit ihrem Namen. ``default`` ist leer: dort gilt, was im
#: Register steht, und eine Tabelle, die es abschreibt, wäre eine zweite
#: Wahrheit.
SCHEMES: Final[dict[str, tuple[TranslatableText, dict[str, str]]]] = {
    "default": (_("Solidon"), {}),
    "fusion": (_("Wie Fusion und Onshape"), FUSION),
}


def shortcut_for(name: str, declared: str | None, scheme: str) -> str | None:
    """Welche Taste diese Operation in dieser Belegung führt.

    Was die Belegung nicht nennt, behält sein Kürzel aus dem Register — eine
    Belegung ist eine Änderung an einzelnen Tasten, keine vollständige zweite
    Liste, die beim nächsten neuen Kürzel auseinanderläuft.
    """
    table = SCHEMES.get(scheme, SCHEMES["default"])[1]
    return table.get(name, declared)
