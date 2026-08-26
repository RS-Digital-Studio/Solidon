"""Der Filamentwähler: Farbe und Name statt einer Zahl von 0 bis 7.

Das Feld hinter ``kind="filament"`` (Konzept „Filamente statt nummerierter
Slots", 26.08.2026). Der Kern rechnet weiter mit der Slotnummer — sie ist es,
die in der Projektdatei steht und aus der der 3MF-Export seinen Farbwechsel
baut. Was sich ändert, ist die Frage, die der Dialog stellt: nicht mehr
„welche Nummer", sondern „welches Filament".

Der Anlass steht im Konzept und ist eine Frage, die die Oberfläche nicht
beantworten konnte: *Welche Farbe hat Slot 1?* Neben dem Zahlenfeld stand
nichts, und wer es wissen wollte, malte einmal und sah nach.

Drei Quellen speisen die Liste, in dieser Reihenfolge:

* **Was der Körper schon trägt.** Ein belegter Slot steht mit seinem Namen
  und seiner Farbe da — das ist die Antwort auf die Frage oben.
* **Die Vorwahl** (:mod:`app.core.knowledge.filaments`): die Spulen, die im
  Regal liegen. Wer eine davon wählt, bekommt den nächsten freien Slot; Name
  und Farbe füllt der Wähler in die Nachbarfelder, sichtbar und weiter
  änderbar.
* **Was übrig bleibt**: die freien Nummern, damit niemand eingesperrt ist,
  der genau Slot 5 meint (§2.1 — keine Sackgassen).

Und ganz unten *Neues Filament …*: Name und Farbe einmal angelegt, stehen sie
über :func:`app.core.knowledge.filaments.remember` in jedem Projekt zur Wahl.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.i18n import tr
from app.ui.theme import slot_colour

#: Kantenlänge des Farbfelds vor einem Eintrag, in Bildpunkten.
#:
#: Groß genug, um eine Farbe zu erkennen, klein genug, dass die Zeile eine
#: Zeile bleibt. Dieselbe Größe wie im Bausteinkatalog.
SWATCH_PIXELS = 14

#: Der Wert, unter dem „Neues Filament …" in der Liste steht. Kein gültiger
#: Slot: Die Auswahl springt sofort zurück, sobald der Dialog geschlossen ist.
NEW_FILAMENT = -1


def hex_of(colour: tuple[float, float, float] | None) -> str:
    """Eine Dokumentfarbe als ``#RRGGBB``.

    Das Dokument führt Farben als drei Anteile von null bis eins, die
    Oberfläche zeigt Hexwerte — dieselbe Umrechnung, die vor dem Ausbau in der
    Pinselleiste stand. Sie ist hier und nicht in ``theme``, weil sie eine
    Frage an das Dokument beantwortet und keine an das Farbschema.
    """
    if colour is None:
        return ""
    return "#" + "".join(f"{max(0, min(255, round(channel * 255))):02x}" for channel in colour)


def swatch(colour: str | None) -> QIcon:
    """Ein Farbfeld als Symbol — leer, wo es keine Farbe gibt.

    Ein leeres Feld statt eines weißen: „keine Farbe" und „weißes Filament"
    sind zwei Aussagen, und ein weißes Kästchen wäre die falsche von beiden.
    """
    image = QPixmap(SWATCH_PIXELS, SWATCH_PIXELS)
    if not colour:
        image.fill(QColor(0, 0, 0, 0))
        return QIcon(image)
    image.fill(QColor(colour))
    painter = QPainter(image)
    # Eine Umrandung, damit ein sehr helles Filament vor hellem Grund nicht
    # verschwindet — dieselbe Vorsicht wie beim Farbknopf der Einstellungen.
    painter.setPen(QColor(0, 0, 0, 90))
    painter.drawRect(0, 0, SWATCH_PIXELS - 1, SWATCH_PIXELS - 1)
    painter.end()
    return QIcon(image)


class NewFilamentDialog(QDialog):
    """Name und Farbe eines neuen Filaments — mehr ist ein Filament nicht."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Neues Filament"))
        layout = QFormLayout(self)

        self.name = QLineEdit(self)
        self.name.setPlaceholderText(tr("etwa „PETG Rot“"))
        layout.addRow(tr("Name"), self.name)

        self._colour = "#808080"
        self.colour = QPushButton(self)
        self.colour.setIcon(swatch(self._colour))
        self.colour.setText(self._colour)
        self.colour.clicked.connect(self._pick_colour)
        layout.addRow(tr("Farbe"), self.colour)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _pick_colour(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._colour), self, tr("Farbe des Filaments"))
        if not chosen.isValid():
            return
        self._colour = chosen.name()
        self.colour.setIcon(swatch(self._colour))
        self.colour.setText(self._colour)

    def filament(self) -> tuple[str, str]:
        """Name und Farbe, wie sie im Katalog landen."""
        return self.name.text().strip(), self._colour


class FilamentField(QComboBox):
    """Der Wähler selbst. Sein Wert ist die Slotnummer — wie eh und je.

    ``currentData()`` gibt sie zurück, und damit liest der Operationsdialog
    ihn wie jede andere Auswahlliste: Das Feld musste dafür nichts Neues
    lernen (:meth:`OperationDialog.values`).
    """

    #: Name und Farbe des gewählten Filaments — der Dialog trägt sie in die
    #: Nachbarfelder ein. Ein Signal und kein Griff in fremde Widgets: Wer
    #: die Felder besitzt, ist der Dialog, und er entscheidet, ob es sie gibt.
    filamentChosen = Signal(str, str)

    def __init__(
        self,
        start: int,
        slots: Sequence[MaterialSlot] = (),
        parent: QWidget | None = None,
        limit: int = 8,
    ) -> None:
        super().__init__(parent)
        self._limit = limit
        self._slots = {int(entry.index): entry for entry in slots}
        self.setToolTip(
            tr(
                "Welches Filament diese Fläche bekommt. Die Vorwahl steht darunter — "
                "was der Körper schon trägt, ganz oben."
            )
        )
        self._fill(int(start))
        self.activated.connect(self._chosen)

    def _fill(self, start: int) -> None:
        """Baut die Liste aus den drei Quellen (siehe Modul-Docstring)."""
        taken: set[int] = set()

        # 1. Was am Körper schon liegt. Slot 0 steht dabei nicht als
        #    „Filament 0" da: Er ist das unbemalte Teil und heißt so.
        for index in sorted(self._slots):
            if index >= self._limit:
                continue
            entry = self._slots[index]
            taken.add(index)
            # ``str(entry.name)`` und nicht der rohe Name: Ein Slotname darf
            # ein ``TranslatableText`` sein, und Qt nimmt nur Zeichenketten.
            shown = hex_of(entry.colour) or (slot_colour(index) or "")
            self.addItem(swatch(shown), self._label(index, str(entry.name)), index)
            self.setItemData(self.count() - 1, shown, _COLOUR_ROLE)
            self.setItemData(self.count() - 1, str(entry.name), _NAME_ROLE)

        # 2. Die Vorwahl — jedes Filament bekommt den nächsten freien Slot.
        for filament in filaments.catalogue():
            if any(entry.name == filament.name for entry in self._slots.values()):
                continue
            free = self._free_slot(taken)
            if free is None:
                break
            taken.add(free)
            self.addItem(
                swatch(filament.colour),
                self._label(free, filament.name),
                free,
            )
            self.setItemData(self.count() - 1, filament.colour, _COLOUR_ROLE)
            self.setItemData(self.count() - 1, filament.name, _NAME_ROLE)

        # 3. Was danach noch frei ist — für den, der genau eine Nummer meint.
        for index in range(self._limit):
            if index in taken:
                continue
            self.addItem(swatch(None), self._label(index, ""), index)

        self.addItem(tr("Neues Filament …"), NEW_FILAMENT)

        position = self.findData(start)
        if position >= 0:
            self.setCurrentIndex(position)

    def _label(self, index: int, name: str) -> str:
        """Wie ein Eintrag dasteht: Nummer und Name, oder was davon es gibt."""
        if index == 0 and not name:
            # Slot 0 ist kein Filament, sondern seine Abwesenheit: das Teil in
            # der Farbe, die es ohnehin hat. „Filament 0" hätte behauptet,
            # dort läge eine Spule.
            return tr("Ohne Filament — Farbe des Teils")
        if not name:
            return tr("Filament {nummer} — noch keines").format(nummer=index)
        return f"{index} — {name}"

    def _free_slot(self, taken: set[int]) -> int | None:
        """Die nächste Nummer, die niemand hat. Null bleibt frei: Sie ist das
        unbemalte Teil und keine Spule."""
        for index in range(1, self._limit):
            if index not in taken:
                return index
        return None

    def _chosen(self, position: int) -> None:
        """Ein Eintrag ist gewählt — Name und Farbe weitersagen."""
        if self.itemData(position) == NEW_FILAMENT:
            self._make_one(position)
            return
        name = self.itemData(position, _NAME_ROLE)
        colour = self.itemData(position, _COLOUR_ROLE)
        if name:
            self.filamentChosen.emit(str(name), str(colour or ""))

    def _make_one(self, position: int) -> None:
        """*Neues Filament …* — anlegen, merken, auswählen.

        Bricht der Dialog ab, springt die Auswahl zurück: Ein Feld, das nach
        einem Abbruch auf „Neues Filament …" stehen bliebe, hätte einen Wert,
        den keine Operation kennt.
        """
        before = max(0, position - 1)
        dialog = NewFilamentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.setCurrentIndex(before)
            return
        name, colour = dialog.filament()
        if not name:
            self.setCurrentIndex(before)
            return
        filaments.remember(name, colour)
        # Neu aufbauen statt einzufügen: Die Nummernvergabe hängt an der
        # ganzen Liste, und eine von Hand eingeschobene Zeile hätte sie
        # doppelt vergeben.
        chosen = self.currentData() if self.currentData() != NEW_FILAMENT else 0
        self.clear()
        self._fill(int(chosen) if isinstance(chosen, int) else 0)
        place = self._position_of(name)
        if place >= 0:
            self.setCurrentIndex(place)
            self._chosen(place)

    def _position_of(self, name: str) -> int:
        for position in range(self.count()):
            if self.itemData(position, _NAME_ROLE) == name:
                return position
        return -1


#: Wo Name und Farbe eines Eintrags liegen. Eigene Rollen, weil ``itemData``
#: ohne Rolle den **Wert** trägt — und der ist die Slotnummer.
#:
#: **Ab UserRole + 1, und das ist keine Förmlichkeit:** ``Qt.UserRole`` *ist*
#: 0x0100, und genau dort legt ``addItem(icon, text, data)`` seinen Wert ab.
#: Eine Rolle auf 0x0100 überschreibt ihn — gemessen kam aus ``currentData()``
#: der Filamentname statt der Slotnummer, und die Operation hätte „PETG Rot"
#: als Slot bekommen.
_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_COLOUR_ROLE = int(Qt.ItemDataRole.UserRole) + 2
