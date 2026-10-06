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

**Einzeltasten heißen in jeder Sprache anders** (Entf, Del, Supr, Suppr,
Canc), und „Del“ ist im Spanischen und Italienischen ein gewöhnliches Wort.
Wie der Text sie nennt, kommt deshalb mit (:class:`KeyNames`); jede Sprache
trägt ihre Namen im eigenen Katalog (``app.i18n.key_names``), so bleibt eine
neue Sprache eine Datei.
"""

from __future__ import annotations

import functools
import re
from typing import Final, NamedTuple

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


class KeyNames(NamedTuple):
    """Wie ein Text die beiden Einzeltasten nennt, die auf dem Mac anders heißen.

    ``delete`` (Entf) wird dort ⌫: Die Taste „delete“ sendet Backspace und
    löscht überall, wo Entf löscht (``app.ui.shortcut_schemes.delete_keys``).
    ``home`` (Pos1) wird ↖, wie Qt sie dort schreibt, am Laptop fn+←. Einfg
    fehlt mit Absicht: Der Mac hat keine Einfügetaste, ein Satz mit ihr bleibt,
    wie er ist.
    """

    delete: str
    home: str


#: Die Namen der Quelle; eine Übersetzung trägt ihre im Katalog.
SOURCE_KEY_NAMES: Final = KeyNames(delete="Entf", home="Pos1")


@functools.cache
def _single_keys(names: KeyNames) -> re.Pattern[str]:
    """Die beiden Einzeltasten als ein Ausdruck: Gruppe 1 Entf, die übrigen Pos1.

    Der Name von Entf ist in keiner Sprache des Bestands ein Wort, jede
    Fundstelle meint die Taste. Der von Pos1 ist es („Home“ ist auch die
    Startseite, „Origine“ der Ursprung): Er gilt nur in `…` oder Klammern und
    vor dem Namen seiner Handlung, „Pos1 (*Einpassen*)“.
    """
    delete = re.escape(names.delete)
    home = re.escape(names.home)
    return re.compile(
        rf"(?<![\w+])({delete})(?![\w+])"
        rf"|(?<=`)({home})(?=`)"
        rf"|(?<=\()({home})(?=\))"
        rf"|(?<![\w+`(])({home})(?= \(\*)"
    )


def native_keys(text: str, platform: str, names: KeyNames = SOURCE_KEY_NAMES) -> str:
    """``text`` mit den Tasten in der Schreibweise von ``platform`` (``sys.platform``).

    ``names`` sagt, wie ``text`` Entf und Pos1 nennt — nicht die eingestellte
    Sprache, wenn ein Satz unübersetzt aus der Quelle kommt. Außer auf dem Mac
    (``darwin``) kommt der Text unverändert zurück.
    """
    if platform != "darwin":
        return text
    if "+" in text:
        text = _COMBO.sub(_on_a_mac, text)
    return _single_keys(names).sub(_single_on_a_mac, text)


def _single_on_a_mac(match: re.Match[str]) -> str:
    return "⌫" if match.group(1) else "↖"


def _on_a_mac(match: re.Match[str]) -> str:
    held = {_MAC_GLYPHS[name] for name in match.group(1).split("+") if name}
    combo = "".join(glyph for glyph in _MAC_ORDER if glyph in held) + match.group(2)
    return _MAC_SAME_ACTION.get(combo, combo)
