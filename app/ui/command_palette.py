"""Die Befehlspalette (Bauplan §2.6, §19.2).

Der universelle Weg hinein: alles aus dem Register, per Tippen erreichbar. Das
Kürzel steht neben jedem Eintrag — so lernt man die Kürzel, ohne dass jemand
eine Tabelle davon liest.
"""

from __future__ import annotations

from typing import Final, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import PaletteEntry, palette_entries
from app.i18n import tr

#: Wie ein Umlaut auf einer Tastatur ohne Umlaute geschrieben wird.
#:
#: Beide Richtungen zählen, und deshalb wird auf **beiden** Seiten gefaltet:
#: Wer „aushoehlen" tippt, meint „Aushöhlen"; wer „Größe" tippt, soll auch das
#: finden, was im Register „groesse" heißt. Gefaltet wird nur der Vergleich —
#: angezeigt bleibt, was dasteht.
#:
#: **Nicht dasselbe wie ``i18n.sort_key``**, und das ist Absicht: Sortiert wird
#: nach DIN 5007-1, wo „ä" wie „a" zählt, damit „Ändern" zwischen „Analyse" und
#: „Anordnen" steht. Gesucht wird nach der Ersatzschreibweise der Tastatur, wo
#: „ä" zu „ae" wird. Eine Tabelle für beides täte einer von beiden Aufgaben
#: unrecht.
_FOLDED: Final[dict[str, str]] = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "á": "a",
    "à": "a",
    "â": "a",
    "é": "e",
    "è": "e",
    "ê": "e",
    "í": "i",
    "ì": "i",
    "î": "i",
    "ó": "o",
    "ò": "o",
    "ô": "o",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ç": "c",
    "ñ": "n",
}


def fold(text: str) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Akzente weg."""
    lowered = text.casefold()
    return "".join(_FOLDED.get(letter, letter) for letter in lowered)


#: Ab wie vielen Zeichen ein Wortstamm als Suchbegriff durchgeht.
#:
#: Vier, weil darunter jedes zweite Wort passt: „ver" fände Verrunden,
#: Vereinigen, Versetzen und Verstiften zugleich.
STEM_LENGTH: Final = 4

#: Wie viele Zeichen eine Beugung höchstens abschneiden darf.
#:
#: Die Untergrenze allein genügt nicht — sie war der Fehler. „gibtsnicht"
#: fand acht Einträge, weil die ersten vier Zeichen „gibt" in acht
#: Beschreibungen stehen; die Zeile „Kein Befehl passt zu …" kam nie zum
#: Vorschein. Ein Stamm ist ein *gekürztes* Wort, kein beliebiger Anfang:
#: „bohren" → „bohr" wirft zwei Zeichen weg, „skalieren" → „skalier" drei.
#: Darüber ist es ein anderes Wort.
STEM_CUT: Final = 3


def stem_of(word: str) -> str:
    """Der Suchstamm eines Wortes — kurz genug für die Beugung, lang genug
    für die Bedeutung.
    """
    return word[: max(STEM_LENGTH, len(word) - STEM_CUT)]


def rank(entry: PaletteEntry, query: str) -> int:
    """Wie gut ein Eintrag zur Anfrage passt — kleiner ist besser.

    **Ein Treffer im Titel wiegt schwerer als einer in der Beschreibung.** Ohne
    diese Ordnung stand bei „bohren" das „An Merkmal ausrichten" vorn, weil
    dessen Beschreibung das Wort Bohrung enthält, und „Bohrung setzen" auf
    Platz drei. Wer tippt, meint fast immer den Namen.

    Sortiert wird **stabil**, damit die Reihenfolge aus ``applies_to`` innerhalb
    derselben Güte erhalten bleibt: Was zur Auswahl passt, steht weiter vorn
    (Gebietsregel, „Was zur Auswahl passt, steht vorn").
    """
    parts = fold(query).split()
    if not parts:
        return 0
    title = fold(str(entry.title))
    name = fold(str(entry.name))
    if all(part in title for part in parts):
        return 0
    if all(part in name for part in parts):
        return 1
    if all(stem_of(part) in title for part in parts if len(part) >= STEM_LENGTH):
        return 2
    return 3


def matches(entry: PaletteEntry, query: str, *, stem: bool = False) -> bool:
    """Teilstring-Suche über Titel, Name und Dokumentation.

    Gefaltet (siehe :func:`fold`), damit „aushoehlen" das Aushöhlen findet —
    vorher gab es darauf **null Treffer**, und dasselbe galt für „groesse".

    ``stem`` sucht nach dem Wortstamm statt nach dem ganzen Wort und ist die
    zweite Runde: „bohren" fand nichts, weil die Operation „Bohrung setzen"
    heißt — ein Fall, den keine Synonymtabelle je vollständig abdeckt und den
    die ersten vier Buchstaben lösen. Gelockert wird erst, wenn die genaue
    Suche leer ausgeht (siehe ``CommandPalette._refilter``): Sonst stünde
    zwischen guten Treffern immer auch Ungefähres.
    """
    if not query:
        return True
    haystack = fold(f"{entry.title} {entry.name} {entry.doc}")
    parts = fold(query).split()
    if not stem:
        return all(part in haystack for part in parts)
    return all(stem_of(part) in haystack for part in parts if len(part) >= STEM_LENGTH)


class CommandPalette(QDialog):
    """Tippen, wählen, ausführen."""

    def __init__(self, entries: list[PaletteEntry] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Befehle"))
        # Breite **und** Höhe. Nur die Breite stand hier, und ohne Höhe nimmt
        # das Layout seine kleinste: 248 Bildpunkte, also sieben Zeilen von
        # hundertfünfundvierzig. Die Palette ist der Weg, auf dem alles
        # erreichbar sein soll (§19.2) — sieben Zeilen machen daraus eine
        # Suchmaske, in der man tippen *muss*, statt eine Liste, in der man
        # blättern *kann*. Ein Eintrag kann zwei Zeilen hoch sein (Titel plus
        # Grund für das Ausgrauen), 480 zeigen also zwölf bis sechzehn.
        self.setMinimumSize(520, 480)
        self._entries = entries if entries is not None else list(palette_entries())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Befehl suchen …"))
        self.search.setAccessibleName(tr("Befehl suchen"))
        self.search.textChanged.connect(self._refilter)
        self.search.returnPressed.connect(self.accept)

        self.list = QListWidget(self)
        self.list.itemActivated.connect(lambda _item: self.accept())

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self._refilter("")

    def _refilter(self, query: str) -> None:
        self.list.clear()
        # **Zwei Runden, und die zweite nur bei Bedarf.** Genau passende
        # Treffer zuerst; findet sich keiner, wird auf den Wortstamm gelockert
        # — „bohren" fand sonst nichts, weil die Operation „Bohrung setzen"
        # heißt. Immer zu lockern hieße, zwischen guten Treffern dauerhaft
        # Ungefähres zu zeigen.
        found = [entry for entry in self._entries if matches(entry, query)]
        if not found and query.strip():
            found = [entry for entry in self._entries if matches(entry, query, stem=True)]
        # Stabil nach Güte: Titel vor Name vor Beschreibung, und innerhalb
        # derselben Güte bleibt die Reihenfolge aus ``applies_to`` stehen.
        found.sort(key=lambda entry: rank(entry, query))
        for entry in found:
            label = str(entry.title)
            if entry.shortcut:
                label = f"{label}\t{entry.shortcut}"
            if not entry.available and entry.reason:
                # Der Grund als zweite Zeile: das Ausgrauen allein wäre die
                # halbe Antwort (Regel 18) — und über die Palette stand die
                # modale Sackgasse offen, die das Menü längst beseitigt hat.
                label = f"{label}\n{entry.reason}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry.name)
            item.setToolTip(str(entry.doc))
            if not entry.available:
                # Sichtbar, aber nicht wählbar — dieselbe Antwort wie im
                # Menü. Die Palette bleibt eine Reihenfolge, keine Auswahl:
                # der Eintrag steht da und sagt, was ihm fehlt.
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.list.addItem(item)
        if self.list.count():
            # Vorgewählt ist der erste Eintrag, der auch ausführbar ist — Enter
            # auf einem ausgegrauten wäre ein Klick, der nichts tut.
            for row in range(self.list.count()):
                item = self.list.item(row)
                if item is not None and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.list.setCurrentRow(row)
                    break
        elif query.strip():
            # Eine leere Liste sagt nicht, ob nichts passt oder ob die Palette
            # kaputt ist. Der Eintrag ist nicht wählbar und trägt keine Daten —
            # ``chosen()`` gibt darüber weiter None zurück, und die Eingabe
            # kann nicht versehentlich einen Befehl auslösen. Er ist damit auch
            # für die Vorauswahl darüber unsichtbar.
            nothing = QListWidgetItem(
                tr(
                    "Kein Befehl passt zu „{begriff}“. Gesucht wird in Titel, Name "
                    "und Beschreibung."
                ).format(begriff=query.strip())
            )
            nothing.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(nothing)

    def chosen(self) -> str | None:
        """Name der gewählten Operation, oder None."""
        # Die Stubs versprechen ein Element; eine leere Liste gibt trotzdem None
        # zurück.
        item = cast(QListWidgetItem | None, self.list.currentItem())
        if item is None:
            return None
        value: str = item.data(Qt.ItemDataRole.UserRole)
        return value

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt name
        """Die Pfeiltasten steuern die Liste, auch während der Cursor im Suchfeld
        steht.
        """
        key = Qt.Key(event.key())
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            step = 1 if key == Qt.Key.Key_Down else -1
            row = self.list.currentRow() + step
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
            return
        super().keyPressEvent(event)
