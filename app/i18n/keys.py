"""Tastenkürzel im Kundentext so, wie die Tastatur des Kunden sie beschriftet.

Die Texte schreiben ein Kürzel so, wie es unter Windows und Linux heißt:
„Strg+Z“, in den Katalogen „Ctrl+Z“. Auf dem Mac ist dieselbe Taste ⌘Z, und
wer dort Control+Z drückt, bekommt nichts — über sechzig Sätze vom
Prüfbericht bis zur Tour führten ihn so ins Leere. Menüs und Palette fragen
Qt (``QKeySequence.toString(NativeText)``); dieser Weg gilt den Sätzen, die
ein Kürzel im Text nennen.

**Ohne Qt**, denn auch der Kern schreibt solche Sätze, und **mit der
Plattform als Argument**: So lässt sich die Mac-Schreibweise auf jeder
Maschine prüfen. Welche Plattform gilt, entscheidet der Start der Anwendung
(``app.ui.app``, ``sys.platform``) über :func:`app.i18n.set_key_platform`;
Werkzeuge, Kommandozeile und Suite schreiben weiter wie die Quelle, damit
Handbuch und Website auf jedem Rechner gleich entstehen.
"""

from __future__ import annotations

import re
from typing import Final

#: Wie der Mac die Umschalttasten beschriftet. „Strg“ ist für Qt die
#: Befehlstaste: Ein Kürzel ``Ctrl+Z`` liegt auf dem Mac auf ⌘Z.
_MAC_GLYPHS: Final[dict[str, str]] = {
    "Alt": "⌥",  # ⌥ Wahltaste
    "Umschalt": "⇧",  # ⇧
    "Shift": "⇧",
    "Strg": "⌘",  # ⌘ Befehlstaste
    "Ctrl": "⌘",
}

#: Die Reihenfolge, in der Qt die Zeichen auf dem Mac schreibt: ⌃⌥⇧⌘.
_MAC_ORDER: Final = "⌃⌥⇧⌘"

#: Dieselbe Handlung, eine andere Taste. *Wiederholen* hängt an
#: ``StandardKey.Redo``, und das ist auf dem Mac ⇧⌘Z — ⌘Y täte nichts.
_MAC_SAME_ACTION: Final[dict[str, str]] = {"⌘Y": "⇧⌘Z"}

#: Umschalttasten mit „+“, dahinter genau eine Taste: ein Buchstabe, eine
#: Ziffer oder F1 bis F12. „Strg+Klick“ und „RAIL++-M“ sind keine Kürzel.
_COMBO: Final = re.compile(
    r"(?<![\w+])((?:(?:Strg|Ctrl|Umschalt|Shift|Alt)\+)+)([A-Z0-9]|F(?:1[0-2]|[1-9]))(?![\w+])"
)


def native_keys(text: str, platform: str) -> str:
    """``text`` mit den Kürzeln in der Schreibweise von ``platform`` (``sys.platform``).

    Außer auf dem Mac (``darwin``) kommt der Text unverändert zurück.
    """
    if platform != "darwin" or "+" not in text:
        return text
    return _COMBO.sub(_on_a_mac, text)


def _on_a_mac(match: re.Match[str]) -> str:
    held = {_MAC_GLYPHS[name] for name in match.group(1).split("+") if name}
    combo = "".join(glyph for glyph in _MAC_ORDER if glyph in held) + match.group(2)
    return _MAC_SAME_ACTION.get(combo, combo)
