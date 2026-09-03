"""Der Filamentwähler: Name, Typ und Farbe statt einer Zahl von 0 bis 7.

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
  Regal liegen. Wer eine davon wählt, bekommt den nächsten freien Slot; Name,
  Typ, Farbe und Herstellerprofil füllt der Wähler in die Nachbarfelder,
  sichtbar und weiter änderbar.
* **Was übrig bleibt**: die freien Nummern, damit niemand eingesperrt ist,
  der genau Slot 5 meint (§2.1 — keine Sackgassen).

Und ganz unten *Neues Filament …*: Name, Typ und Farbe einmal angelegt, stehen
sie über :func:`app.core.knowledge.filaments.remember` in jedem Projekt zur
Wahl.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import discover, tools
from app.core.export import slicer_keys, slicer_profiles
from app.core.export.handover import detect
from app.core.knowledge import filaments, profiles
from app.core.types import MaterialSlot, PrintSettings
from app.i18n import tr
from app.ui.overlay import rows_height
from app.ui.panels import MAX_ROWS, least_height_of, row_height_of, view_chrome
from app.ui.style import TIGHT, make_primary, set_level
from app.ui.theme import current_theme, slot_colour, viewport_colours

#: Kantenlänge des Farbfelds vor einem Eintrag, in Bildpunkten.
#:
#: Groß genug, um eine Farbe zu erkennen, klein genug, dass die Zeile eine
#: Zeile bleibt. Dieselbe Größe wie im Bausteinkatalog.
SWATCH_PIXELS = 14

#: Der Wert, unter dem „Neues Filament …" in der Liste steht. Kein gültiger
#: Slot: Die Auswahl springt sofort zurück, sobald der Dialog geschlossen ist.
NEW_FILAMENT = -1

#: Die Farbe des unbemalten Teils — Slot 0 in einer Liste von Filamenten.
#:
#: Aus dem Thema geholt und nicht danebengeschrieben: Es ist die Farbe, die
#: ein Körper in der Ansicht ohnehin trägt (``viewport_colours(...)["object"]``,
#: dieselbe Quelle wie ``Viewport.set_theme``).
#:
#: **Aus dem geltenden Thema, nicht fest aus dem dunklen.** Hier stand die
#: dunkle Farbe mit der Begründung, ein Farbfeld von vierzehn Bildpunkten
#: trage den Unterschied nicht. Gemessen sind es ``#7d8894`` im Viewport gegen
#: ``#b9c4d0`` im Wähler — zwei klar unterscheidbare Grautöne, und das Feld
#: verspricht daneben „Ohne Filament — Farbe des Teils". Es zeigte im hellen
#: Thema nicht die Farbe des Teils. Eine zutreffend klingende Begründung, die
#: niemand nachgemessen hatte.


def unpainted_colour() -> str:
    """Die Körperfarbe des geltenden Themas."""
    return viewport_colours(current_theme())["object"]


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


def shown_colour(index: int, colour: tuple[float, float, float] | None = None) -> str:
    """Die Farbe, in der ein Filament erscheint — **nie leer**.

    Drei Quellen in dieser Reihenfolge, und es ist dieselbe Kette, die der
    Viewport für seine Farbtabelle geht (``Viewport._slot_colours``):

    1. die eigene Farbe des Slots, wenn er eine hat,
    2. sonst die Grauleiter (:func:`theme.slot_colour`) — der Stand vor der
       ersten Farbwahl,
    3. für Slot 0 die **Körperfarbe**: Er ist das unbemalte Teil, und das ist
       genau die Farbe, die es in der Ansicht schon hat.

    Vorher endete die Kette in der Oberfläche nach Schritt 1: Wo keine Farbe
    im Dokument stand, blieb das Feld **leer** — im Filamentwähler, der
    daneben „Ohne Filament — Farbe des Teils" schrieb, und im Panel. Ein
    leeres Kästchen ist aber keine Auskunft über eine Farbe, sondern über
    ihre Abwesenheit, und die gibt es hier nicht: Jedes Filament hat eine
    Farbe im Bild, auch bevor jemand eine wählt (Robert, 27.08.2026). Der
    Viewport hatte diese Kette schon; die Oberfläche daneben nicht.
    """
    own = hex_of(colour)
    if own:
        return own
    return slot_colour(index) or unpainted_colour()


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


#: Wie viele Treffer die Liste zeigt. Der Bestand geht in die Tausende, und
#: eine Liste, die alles zeigt, ist so unbrauchbar wie eine leere — wer mehr
#: sieht, als er lesen kann, filtert weiter statt zu blättern.
MAX_HITS = 300


def known_material_types() -> tuple[str, ...]:
    """Die Materialarten, die Solidon führt, in der Schreibweise des Slicers."""
    return tuple(
        slicer_keys.filament_type(identifier) for identifier in profiles.material_profiles()
    )


class SlicerFilamentDialog(QDialog):
    """Ein Filamentprofil aus dem Bestand des Slicers wählen (§29).

    **Warum ein Dialog und keine Auswahlliste.** Gemessen an einem
    ElegooSlicer-Bestand hält der Slicer **5962** Filamentprofile aus 48
    Herstellern. In eine Auswahlliste passt das nicht; wer dort das
    „Elegoo PLA @EC" sucht, sucht es in zweitausend Zeilen fremder Hersteller.

    **Warum es ihn überhaupt braucht.** Bis zum 03.09.2026 bekam eine Spule
    ihr Herstellerprofil ausschließlich bei der Ersteinrichtung, aus der
    Übernahme der im Slicer eingerichteten Filamente. Danach gab es keinen Weg
    mehr, eines zuzuordnen: Das Feld im Anlegen-Dialog war schreibgeschützt.
    Wer im Slicer dasselbe Material mehrfach mit verschiedenen Werten anlegt —
    und das ist der übliche Weg, wenn eine Spule anders fährt als die
    Grundausführung —, konnte in Solidon nicht sagen, welche Ausführung gilt.
    Der Unterschied ist messbar: Ein Slot mit ``Elegoo PLA @EC`` bringt 30
    Werte mehr in die übergebene Datei.

    Gefiltert wird nach dem, was jedes Profil wirklich trägt: Hersteller
    (:func:`slicer_profiles.vendor_of`), Materialart
    (:func:`slicer_profiles.material_of`) und der Name selbst.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        entries: Sequence[slicer_profiles.SlicerProfile] = (),
        chosen: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Slicer-Profil wählen"))
        self.setMinimumSize(520, 460)
        self._entries = list(entries)
        self._known = known_material_types()

        layout = QVBoxLayout(self)
        layout.setSpacing(TIGHT)

        form = QFormLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("etwa „PLA Matte“"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refill)
        form.addRow(tr("Suche"), self.search)

        self.vendor = QComboBox(self)
        self.vendor.addItem(tr("Alle Hersteller"), "")
        for name in sorted({slicer_profiles.vendor_of(entry) for entry in self._entries} - {""}):
            self.vendor.addItem(name, name)
        self.vendor.currentIndexChanged.connect(self._refill)
        form.addRow(tr("Hersteller"), self.vendor)

        self.material = QComboBox(self)
        self.material.addItem(tr("Alle Materialien"), "")
        for name in sorted({entry for entry in self._known if entry}):
            self.material.addItem(name, name)
        self.material.currentIndexChanged.connect(self._refill)
        form.addRow(tr("Material"), self.material)
        layout.addLayout(form)

        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Gefundene Profile"))
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.list.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.list, 1)

        self.count = QLabel(self)
        set_level(self.count, "caption")
        layout.addWidget(self.count)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self._ok_button is not None
        make_primary(self._ok_button)

        # **Die Vorwahl steuert den Filter, nicht nur die Markierung.** Wer mit
        # „Elegoo PLA @EC" hereinkommt, soll nicht erst den Hersteller suchen,
        # unter dem seine Wahl liegt.
        if chosen:
            found = next((e for e in self._entries if e.name == chosen), None)
            if found is not None:
                vendor = slicer_profiles.vendor_of(found)
                position = self.vendor.findData(vendor)
                if position >= 0:
                    self.vendor.setCurrentIndex(position)
        self._refill()
        if chosen:
            for row in range(self.list.count()):
                if self.list.item(row).data(Qt.ItemDataRole.UserRole) == chosen:
                    self.list.setCurrentRow(row)
                    break
        self._selection_changed(self.list.currentItem(), None)

    def _matching(self) -> list[slicer_profiles.SlicerProfile]:
        """Die Treffer der drei Filter, nach Namen sortiert."""
        wanted = self.search.text().strip().casefold()
        vendor = str(self.vendor.currentData() or "")
        material = str(self.material.currentData() or "")
        found = []
        for entry in self._entries:
            if vendor and slicer_profiles.vendor_of(entry) != vendor:
                continue
            if material and slicer_profiles.material_of(entry, self._known) != material:
                continue
            if wanted and wanted not in entry.name.casefold():
                continue
            found.append(entry)
        return sorted(found, key=lambda entry: entry.name)

    def _refill(self) -> None:
        """Die Liste neu füllen und sagen, wie viele es sind."""
        found = self._matching()
        self.list.clear()
        for entry in found[:MAX_HITS]:
            item = QListWidgetItem(entry.name, self.list)
            item.setData(Qt.ItemDataRole.UserRole, entry.name)
            item.setToolTip(str(entry.path))
        if self.list.count() and self.list.currentRow() < 0:
            # **Der erste Treffer steht ausgewählt da.** Ohne das ist nach jedem
            # Tastendruck im Suchfeld nichts gewählt, der Übernehmen-Knopf grau,
            # und wer den einen Treffer will, muss ihn noch einmal anklicken.
            self.list.setCurrentRow(0)
        if not found:
            # Keine Sackgasse (§2.1): Der Satz sagt, was zu tun ist, und die
            # Liste bleibt leer statt zu schweigen.
            self.count.setText(tr("Kein Profil passt zu dieser Auswahl — Filter weiter öffnen."))
        elif len(found) > MAX_HITS:
            self.count.setText(
                tr("{shown} von {total} Profilen — enger filtern, um den Rest zu sehen.").format(
                    shown=MAX_HITS, total=len(found)
                )
            )
        else:
            self.count.setText(tr("{total} Profile").format(total=len(found)))
        self._selection_changed(self.list.currentItem(), None)

    def _selection_changed(self, current: object, _previous: object) -> None:
        """Ohne gewähltes Profil gibt es nichts zu übernehmen — und der Knopf
        sagt es, statt grau dazustehen.

        Zwei Lagen führen hierher, und der Satz trennt sie: eine Liste, in der
        nichts markiert ist, und eine Liste, in der nichts steht. Die zweite
        ist der häufigere Fall — ein Rechner ohne installierten Slicer bringt
        keine Profile mit, und dort ist „wählen Sie eines" ein Rat ins Leere.
        """
        why = ""
        if current is None:
            why = str(
                tr("Kein Profil gewählt.")
                if self.list.count()
                else tr("Dieser Slicer bringt keine Filamentprofile mit.")
            )
        self._ok_button.setEnabled(not why)
        self._ok_button.setToolTip(why)
        self._ok_button.setStatusTip(why)
        self._ok_button.setAccessibleDescription(why)

    def chosen_profile(self) -> str:
        """Der Name des gewählten Profils — nie ein Pfad (Regel 12)."""
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""


def slicer_filaments() -> tuple[slicer_profiles.SlicerProfile, ...]:
    """Die Filamentprofile des eingerichteten Slicers, oder nichts.

    Kein Slicer ist kein Fehler: Solidon läuft ohne, und dann gibt es hier
    nichts zu wählen. Die Suche kostet gemessen 0,8 Sekunden über 5962
    Profile — genug für einen Wartezeiger, zu wenig für einen Arbeiter (§2.8).
    """
    found = discover.find_programs("slicer", tools.SLICERS)
    remembered = discover.remembered_path("slicer")
    chosen = next((entry for entry in found if str(entry) == remembered), None) or (
        found[0] if found else None
    )
    if chosen is None:
        return ()
    try:
        flavour = detect(chosen).flavour
        return tuple(slicer_profiles.find_profiles(chosen, flavour, kinds=("filament",)))
    except Exception:  # ein fremder Bestand scheitert auf viele Arten
        return ()


class NewFilamentDialog(QDialog):
    """Name, Typ, Farbe und optionales Slicerprofil eines Filaments.

    Mit ``name``/``colour`` derselbe Dialog fürs **Ändern**: Ein Filament ist
    sein Name (:func:`filaments.remember` überschreibt die Farbe eines
    vorhandenen), also ist „Farbe ändern" dasselbe Formular mit ausgefüllten
    Feldern und nicht ein zweites daneben.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        name: str = "",
        colour: str = "",
        material_type: str = "",
        slicer_profile: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Filament ändern") if name else tr("Neues Filament"))
        self.setMinimumWidth(380)
        layout = QFormLayout(self)

        self.name = QLineEdit(self)
        self.name.setPlaceholderText(tr("etwa „PETG Rot“"))
        self.name.setText(name)
        layout.addRow(tr("Name"), self.name)

        self.material_type = QComboBox(self)
        self.material_type.setEditable(True)
        self.material_type.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # Kein Spulentyp wird geraten. Die bekannte Liste bleibt sofort
        # erreichbar, und wer einen anderen Typ auf der Spule liest, darf ihn
        # weiterhin eintippen.
        self.material_type.addItem(tr("Unbekannt"), "")
        for identifier, entry in profiles.material_profiles().items():
            self.material_type.addItem(str(entry.title), slicer_keys.filament_type(identifier))
        if material_type:
            position = next(
                (
                    index
                    for index in range(self.material_type.count())
                    if str(self.material_type.itemData(index)).casefold()
                    == material_type.casefold()
                ),
                -1,
            )
            if position >= 0:
                self.material_type.setCurrentIndex(position)
            else:
                self.material_type.setCurrentText(material_type)
        material_help = tr("Materialart des Filaments, etwa PLA oder PETG.")
        self.material_type.setToolTip(material_help)
        self.material_type.setAccessibleDescription(material_help)
        layout.addRow(tr("Typ"), self.material_type)

        self._colour = colour or "#808080"
        self.colour = QPushButton(self)
        self.colour.setIcon(swatch(self._colour))
        self.colour.setText(self._colour)
        self.colour.clicked.connect(self._pick_colour)
        layout.addRow(tr("Farbe"), self.colour)

        # **Wählbar, nicht nur anzeigbar.** Bis zum 03.09.2026 stand hier ein
        # schreibgeschütztes Feld mit dem Platzhalter „wird bei Übernahme aus
        # dem Slicer gesetzt" — und die Übernahme lief ausschließlich in der
        # Ersteinrichtung. Wer danach im Slicer eine Spule anlegte, konnte sie
        # in Solidon nie zuordnen, obwohl die Übergabe sie sofort verwendet
        # hätte (30 Werte mehr in der Datei).
        self.slicer_profile = QLineEdit(self)
        self.slicer_profile.setText(slicer_profile)
        self.slicer_profile.setReadOnly(True)
        self.slicer_profile.setPlaceholderText(tr("kein Profil aus dem Slicer"))
        self.choose_profile = QPushButton(tr("Wählen …"), self)
        self.choose_profile.clicked.connect(self._choose_slicer_profile)
        self.clear_profile = QPushButton(tr("Entfernen"), self)
        self.clear_profile.clicked.connect(self._clear_slicer_profile)
        self._show_clear_state(bool(slicer_profile.strip()))
        profile_row = QHBoxLayout()
        profile_row.setSpacing(TIGHT)
        profile_row.addWidget(self.slicer_profile, 1)
        profile_row.addWidget(self.choose_profile)
        profile_row.addWidget(self.clear_profile)
        self._slicer_profile_label = QLabel(tr("Slicer-Profil"), self)
        layout.addRow(self._slicer_profile_label, profile_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self._ok_button is not None
        make_primary(self._ok_button)
        self._ok_button.setEnabled(bool(name.strip()))
        # Gebundene Methode statt Lambda — dasselbe Ring-Muster wie in
        # ``install_dialog._Row``: Das Lambda fing ``self`` am eigenen Kind.
        self.name.textChanged.connect(self._name_changed)
        self.name.setFocus()

    def _name_changed(self, text: str) -> None:
        self._ok_button.setEnabled(bool(text.strip()))

    def _choose_slicer_profile(self) -> None:
        """Den Bestand des Slicers aufschlagen und eines auswählen."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            entries = slicer_filaments()
        finally:
            QApplication.restoreOverrideCursor()
        if not entries:
            # Regel 17: Ein Fehlschlag endet nie mit „geht nicht".
            self.slicer_profile.setPlaceholderText(
                tr("Kein Slicer eingerichtet — unter Datei → Einstellungen eintragen.")
            )
            return
        dialog = SlicerFilamentDialog(self, entries, self.slicer_profile.text().strip())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.chosen_profile()
            self.slicer_profile.setText(chosen)
            self._show_clear_state(bool(chosen))

    def _show_clear_state(self, has_profile: bool) -> None:
        """Der Entfernen-Knopf sagt, warum er nichts zu tun hat.

        Ohne eingetragenes Profil ist er gesperrt, und das ist richtig — er
        stand nur wortlos da. Alle drei Kanäle (Regel 18); der Grund nennt den
        Zustand und nicht die Handlung, denn was fehlt, ist das Profil.
        """
        why = "" if has_profile else str(tr("Es ist kein Profil eingetragen."))
        self.clear_profile.setEnabled(has_profile)
        self.clear_profile.setToolTip(why)
        self.clear_profile.setStatusTip(why)
        self.clear_profile.setAccessibleDescription(why)

    def _clear_slicer_profile(self) -> None:
        """Ohne Herstellerprofil ist auch eine Antwort — die Werte kommen dann
        aus Solidon allein."""
        self.slicer_profile.clear()
        self._show_clear_state(False)

    def _pick_colour(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._colour), self, tr("Farbe des Filaments"))
        if not chosen.isValid():
            return
        self._colour = chosen.name()
        self.colour.setIcon(swatch(self._colour))
        self.colour.setText(self._colour)

    def filament(self) -> tuple[str, str, str, str]:
        """Die vollständige Vorwahl, wie sie im Katalog landet."""
        shown_type = self.material_type.currentText().strip()
        # Bei einem editierbaren Kombinationsfeld bleibt ``currentIndex``
        # während des Tippens auf dem alten Eintrag. Darum wird der sichtbare
        # Text selbst aufgelöst: „PLA" im Feld darf nie die unsichtbaren Daten
        # des vorherigen ABS-Eintrags speichern.
        position = next(
            (
                index
                for index in range(self.material_type.count())
                if shown_type.casefold()
                in {
                    self.material_type.itemText(index).casefold(),
                    str(self.material_type.itemData(index) or "").casefold(),
                }
            ),
            -1,
        )
        material_type = self.material_type.itemData(position) if position >= 0 else shown_type
        return (
            self.name.text().strip(),
            self._colour,
            str(material_type or "").strip(),
            self.slicer_profile.text().strip(),
        )


class FilamentField(QComboBox):
    """Der Wähler selbst. Sein Wert ist die Slotnummer — wie eh und je.

    ``currentData()`` gibt sie zurück, und damit liest der Operationsdialog
    ihn wie jede andere Auswahlliste: Das Feld musste dafür nichts Neues
    lernen (:meth:`OperationDialog.values`).
    """

    #: Identität des gewählten Filaments — der Dialog trägt sie in die
    #: Nachbarfelder ein. Ein Signal und kein Griff in fremde Widgets: Wer
    #: die Felder besitzt, ist der Dialog, und er entscheidet, ob es sie gibt.
    filamentChosen = Signal(str, str, str, str)

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
            shown = shown_colour(index, entry.colour)
            self.addItem(
                swatch(shown),
                self._label(index, str(entry.name), str(entry.material_type or "")),
                index,
            )
            self.setItemData(self.count() - 1, shown, _COLOUR_ROLE)
            self.setItemData(self.count() - 1, str(entry.name), _NAME_ROLE)
            self.setItemData(self.count() - 1, str(entry.material_type or ""), _MATERIAL_TYPE_ROLE)
            self.setItemData(self.count() - 1, str(entry.material or ""), _PROFILE_ROLE)

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
                self._label(free, filament.name, filament.material_type),
                free,
            )
            self.setItemData(self.count() - 1, filament.colour, _COLOUR_ROLE)
            self.setItemData(self.count() - 1, filament.name, _NAME_ROLE)
            self.setItemData(self.count() - 1, filament.material_type, _MATERIAL_TYPE_ROLE)
            self.setItemData(self.count() - 1, filament.slicer_profile, _PROFILE_ROLE)

        # 3. Was danach noch frei ist — für den, der genau eine Nummer meint.
        for index in range(self._limit):
            if index in taken:
                continue
            # **Mit der Farbe, die es bekommen wird**, nicht mit einem leeren
            # Kästchen: „Filament 1 — noch keines" ist per Vorgabe gewählt,
            # sobald jemand eine Fläche färbt, und stand bis jetzt farblos da.
            self.addItem(swatch(shown_colour(index)), self._label(index, ""), index)

        self.addItem(tr("Neues Filament …"), NEW_FILAMENT)

        position = self.findData(start)
        if position >= 0:
            self.setCurrentIndex(position)

    def _label(self, index: int, name: str, material_type: str = "") -> str:
        """Wie ein Eintrag dasteht: Nummer und Name, oder was davon es gibt."""
        if index == 0 and not name:
            # Slot 0 ist kein Filament, sondern seine Abwesenheit: das Teil in
            # der Farbe, die es ohnehin hat. „Filament 0" hätte behauptet,
            # dort läge eine Spule.
            return tr("Ohne Filament — Farbe des Teils")
        if not name:
            return tr("Filament {number} — noch keines").format(number=index)
        suffix = (
            f" · {material_type}"
            if material_type and material_type.casefold() not in name.casefold()
            else ""
        )
        return f"{index} — {name}{suffix}"

    def _free_slot(self, taken: set[int]) -> int | None:
        """Die nächste Nummer, die niemand hat. Null bleibt frei: Sie ist das
        unbemalte Teil und keine Spule."""
        for index in range(1, self._limit):
            if index not in taken:
                return index
        return None

    def _chosen(self, position: int) -> None:
        """Ein Eintrag ist gewählt — seine ganze Identität weitersagen."""
        if self.itemData(position) == NEW_FILAMENT:
            self._make_one(position)
            return
        name = self.itemData(position, _NAME_ROLE)
        colour = self.itemData(position, _COLOUR_ROLE)
        if name:
            self.filamentChosen.emit(
                str(name),
                str(colour or ""),
                str(self.itemData(position, _MATERIAL_TYPE_ROLE) or ""),
                str(self.itemData(position, _PROFILE_ROLE) or ""),
            )

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
        name, colour, material_type, slicer_profile = dialog.filament()
        if not name:
            self.setCurrentIndex(before)
            return
        filaments.remember(name, colour, material_type, slicer_profile)
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


#: Wo Name, Typ, Profil und Farbe eines Eintrags liegen. Eigene Rollen, weil ``itemData``
#: ohne Rolle den **Wert** trägt — und der ist die Slotnummer.
#:
#: **Ab UserRole + 1, und das ist keine Förmlichkeit:** ``Qt.UserRole`` *ist*
#: 0x0100, und genau dort legt ``addItem(icon, text, data)`` seinen Wert ab.
#: Eine Rolle auf 0x0100 überschreibt ihn — gemessen kam aus ``currentData()``
#: der Filamentname statt der Slotnummer, und die Operation hätte „PETG Rot"
#: als Slot bekommen.
_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_COLOUR_ROLE = int(Qt.ItemDataRole.UserRole) + 2
_SLOT_ROLE = int(Qt.ItemDataRole.UserRole) + 3
_MATERIAL_TYPE_ROLE = int(Qt.ItemDataRole.UserRole) + 4
_PROFILE_ROLE = int(Qt.ItemDataRole.UserRole) + 5


class FilamentPanel(QWidget):
    """Die Filamente auf einen Blick: was das Projekt trägt, was im Regal liegt.

    Die Frage, die dieses Panel beantwortet, hat Robert am 27.08.2026 gestellt
    — „wo wähle ich die Filamente und Farben aus?" — und sie war berechtigt:
    Beide Antworten standen in Dialogen. Das Filamentfeld
    (:class:`FilamentField`) zeigt Name, Typ und Farbe, aber nur solange eine
    Operation offen ist; die Filamentprofile des Slicers stehen in den
    Druckeinstellungen, zugeklappt und erst ab zwei Slots. Wer wissen wollte,
    welche Spulen ein Projekt überhaupt braucht, fand es nirgends.

    **Zwei Hälften, und die Trennung ist die eigentliche Entscheidung:**

    * **Im Projekt** — was die Körper tragen, mit Farbe, Name und der Zahl
      der Körper. Die Zeile öffnet nur Druckwerte dieser Spule. Farbe oder
      Zuordnung zu ändern hieße dagegen, Geometrie außerhalb einer Operation
      anzufassen (Regel 2); der Weg dorthin ist das Kontextmenü am Merkmal,
      und der Hinweis unter der Liste sagt es.
    * **Im Regal** — die Vorwahl (:mod:`app.core.knowledge.filaments`), also
      die Spulen, die wirklich dastehen. Sie gehört keinem Projekt, hängt an
      keinem Körper und ist deshalb hier vollständig bedienbar: anlegen,
      Farbe oder Name ändern, herausnehmen.

    Was im Regal steht, steht in jedem Filamentfeld zur Wahl — das Panel ist
    damit die Stelle, an der man den Vorrat pflegt, und nicht ein zweiter Weg
    zum selben Dialog.
    """

    #: Die Druckwerte gehören dem Projekt, nicht dem Regal. Das Hauptfenster
    #: öffnet den Dialog und schreibt das Ergebnis über die Sitzung zurück.
    overrideRequested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Filamente"))
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)

        self.hint = QLabel(self)
        self.hint.setWordWrap(True)
        set_level(self.hint, "caption")

        self.add_button = QPushButton(tr("Filament anlegen …"), self)
        self.add_button.clicked.connect(self._add)
        self.settings_button = QPushButton(tr("Druckwerte …"), self)
        self.settings_button.setEnabled(False)
        self.settings_button.setToolTip(
            tr("Temperatur, Kühlung, Rückzug und Materialwerte dieser Spule einstellen.")
        )
        self.settings_button.clicked.connect(self._request_override)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TIGHT, TIGHT, TIGHT, TIGHT)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.hint)
        buttons = QHBoxLayout()
        buttons.setSpacing(TIGHT)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.settings_button)
        layout.addLayout(buttons)

        self._used: tuple[tuple[MaterialSlot | None, str, str, int, bool], ...] = ()
        """Slot, Name, Farbe, Zahl der Körper und eigene Druckwerte."""
        self._room: int | None = None
        """Was die Überlagerung dieser Karte zugeteilt hat (``set_room``)."""
        self.show_scene(())

    # -- Höhe: was die Überlagerung fragt --------------------------------

    def _around_the_list(self) -> int:
        """Was fest um die Liste herum steht: Hinweis, Knöpfe, Ränder, Abstände.

        Gerechnet aus den Wunschhöhen und nicht aus den gelegten — dieselbe
        Bedingung, unter der die ganze Verteilung stillsteht (``_share_room``):
        Wer die Höhen liest, die er gerade selbst gesetzt hat, bekommt beim
        nächsten Durchlauf andere Zahlen und die Spalte läuft auf und ab.
        """
        layout = self.layout()
        if layout is None:
            return 0
        margins = layout.contentsMargins()
        gaps = max(layout.count() - 1, 0) * layout.spacing()
        buttons = max(self.add_button.sizeHint().height(), self.settings_button.sizeHint().height())
        return margins.top() + margins.bottom() + gaps + self.hint.sizeHint().height() + buttons

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Spule zu sehen wäre.

        **Ohne diese Methode teilt die Überlagerung der Karte nichts zu.**
        ``_share_room`` fragt nur Kinder, die das ``RoomTaker``-Protokoll
        erfüllen; wer es nicht tut, „behält seine eigene Höhe". Diese Karte tat
        das, und ihre Höhe war die, die Qt einer Liste ohne Zutun gibt: 30
        Bildpunkte bei 266 gewünschten (gemessen am 30.08.2026 im echten
        Fenster, B21). Die Liste brach mitten in einer Zeile ab, während der
        Verlauf daneben 246 Punkte hielt und mit 96 ausgekommen wäre.
        """
        return self._around_the_list() + rows_height(self.list)

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht, was auch zugeteilt wird.

        Derselbe Boden, den ``fit_to_rows`` der Liste ohnehin setzt — die
        Überlagerung muss ihn kennen, sonst verteilt sie unter ihn und das
        Layout drückt die Karte zusammen, bis Zeilen außerhalb liegen.

        **Nie höher als der Wunsch.** Jener Boden sind drei Mindestzeilen, und
        die sollen verhindern, dass eine Liste mit zwanzig Zeilen auf eine
        gedrückt wird. Bei einer Karte, die überhaupt nur eine Zeile *hat* —
        leeres Regal, kein Projektfilament —, forderte er 130 Bildpunkte für
        128 gewünschte: Platz, den die Karte niemandem zeigen kann, während
        die Nachbarn ihn brauchen.
        """
        return min(self._around_the_list() + least_height_of(self.list), self.wanted_height())

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _fit(self) -> None:
        """So hoch wie der Inhalt, höchstens so hoch wie zugeteilt.

        Der Liste bleibt, was nach dem Beiwerk übrig ist: Ein Hinweis und zwei
        Knöpfe stehen unter ihr, und wer ihr die volle Zuteilung gibt, schiebt
        genau die aus der Karte heraus — die Knöpfe sind hier der einzige Weg
        zu einer neuen Spule.

        **Gerechnet wird über ``rows_height`` und nicht über ``fit_to_rows``,
        und das ist der Kern des Befunds.** Jener Helfer nimmt die Höhe der
        *ersten* Zeile mal die Zahl der Zeilen — richtig für einen Baum, in
        dem jede Zeile gleich aussieht, falsch für diese Liste: Zwischen den
        Spulen stehen zwei fette Überschriften („Im Projekt", „Im Regal"), und
        die sind höher als eine Spulenzeile. Gemessen am 30.08.2026 bei fünf
        Zeilen: 172 Punkte gebraucht, 156 gesetzt — die letzte Zeile fehlte,
        und zwar auch dann, wenn die Spalte ihre volle Wunschhöhe bekam und
        ringsum Platz frei war. ``rows_height`` misst jede Zeile einzeln.
        """
        wanted = rows_height(self.list)
        if self._room is None:
            # **Solange niemand zugeteilt hat, gilt derselbe Deckel wie in
            # ``fit_to_rows``.** Er ist für den Augenblick vor dem ersten
            # Zuteilen da: Ein Regal mit hundert Spulen würde die Spalte sonst
            # schon beim Aufbau nehmen, bevor die Überlagerung überhaupt
            # gefragt hat.
            ceiling = view_chrome(self.list) + MAX_ROWS * row_height_of(self.list)
        else:
            ceiling = max(self._room - self._around_the_list(), 0)
        self.list.setFixedHeight(max(least_height_of(self.list), min(wanted, ceiling)))
        # Dieselbe Stelle wie im Verlauf: die Liste ist bemessen, die Karte um
        # sie herum meldete weiter ihre Mindesthöhe und wurde zusammengedrückt.
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    def show_scene(
        self,
        objects: Sequence[object],
        settings: PrintSettings | None = None,
    ) -> None:
        """Trägt ein, welche Filamente die Körper der Szene benutzen.

        Zusammengelegt über Name **und** Farbe — derselbe Schlüssel, über den
        auch der Export die Extruder bildet (``threemf.merge_slots``). Zwei
        Körper in derselben Farbe sind eine Spule, nicht zwei.

        **Ein Körper ohne Slot steht mit dabei**, als „Ohne Filament — Farbe
        des Teils" in der Körperfarbe. Er ist der Normalfall nach jedem
        STL-Import, und ohne ihn zeigte das Panel bei einem frisch geöffneten
        Modell eine leere Projekthälfte — während im Bild ein Körper stand,
        der sehr wohl in einer Farbe gedruckt wird (Robert, 27.08.2026).
        """
        used: dict[tuple[str, str], tuple[MaterialSlot | None, int]] = {}
        for entry in objects:
            slots = getattr(entry, "material_slots", ()) or ()
            if not slots:
                key = (str(tr("Ohne Filament — Farbe des Teils")), unpainted_colour())
                previous = used.get(key, (None, 0))
                used[key] = (None, previous[1] + 1)
                continue
            for slot in slots:
                key = (str(slot.name), shown_colour(int(slot.index), slot.colour))
                previous = used.get(key, (slot, 0))
                used[key] = (slot, previous[1] + 1)
        overrides = {
            entry.key
            for entry in (settings.slot_overrides if settings is not None else ())
            if entry is not None and not entry.empty
        }
        self._used = tuple(
            (
                slot,
                name,
                colour,
                count,
                slot is not None and (slot.name, slot.colour) in overrides,
            )
            for (name, colour), (slot, count) in sorted(used.items())
        )
        self._fill()

    def refresh_catalogue(self) -> None:
        """Liest nur das Filamentregal neu, der Projektzustand bleibt stehen.

        Die Erstinbetriebnahme kann Spulen aus dem Slicer übernehmen, während
        dieses Panel längst gebaut ist. Dafür wird weder die Szene erneut
        ausgewertet noch ihre Zusammenfassung nachgebaut: :attr:`_used` bleibt
        dieselbe, nur die Regalhälfte liest den gemeinsamen Katalog noch einmal.
        """
        self._fill()

    def _fill(self) -> None:
        """Beide Hälften neu schreiben — Überschrift, Zeilen, Hinweis."""
        self.list.clear()
        if self._used:
            self._heading(tr("Im Projekt"))
            for slot, name, colour, count, has_override in self._used:
                label = self._used_label(name, count)
                if has_override:
                    label = f"{label} · {tr('eigene Druckwerte')}"
                item = QListWidgetItem(swatch(colour), label)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if slot is not None:
                    item.setData(_SLOT_ROLE, slot)
                item.setToolTip(
                    tr(
                        "Druckwerte stehen unten. Geändert wird die Farbe eines Körpers "
                        "über das Kontextmenü am Merkmal."
                    )
                )
                self.list.addItem(item)

        self._heading(tr("Im Regal"))
        entries = filaments.catalogue()
        for entry in entries:
            label = (
                f"{entry.name} · {entry.material_type}"
                if entry.material_type
                and entry.material_type.casefold() not in entry.name.casefold()
                else str(entry.name)
            )
            item = QListWidgetItem(swatch(entry.colour), label)
            item.setData(_NAME_ROLE, entry.name)
            item.setData(_COLOUR_ROLE, entry.colour)
            item.setData(_MATERIAL_TYPE_ROLE, entry.material_type)
            item.setData(_PROFILE_ROLE, entry.slicer_profile)
            profile_hint = (
                tr("Slicer-Profil: {profile}").replace("{profile}", entry.slicer_profile)
                if entry.slicer_profile
                else tr("Ohne Slicer-Profil")
            )
            item.setToolTip(f"{tr('Doppelklick ändert Name, Typ und Farbe.')} {profile_hint}")
            self.list.addItem(item)

        if entries:
            self.hint.setText(tr("Was hier steht, steht beim Färben zur Wahl."))
        else:
            # Regel 17 auch ohne Fehler: Ein leeres Regal ist kein Mangel,
            # aber ohne einen Satz sieht es aus wie ein kaputtes Panel.
            self.hint.setText(
                tr("Noch keine Spulen eingetragen. Was Sie anlegen, steht beim Färben zur Wahl.")
            )
        self._selection_changed(self.list.currentItem())
        # Die Zeilenzahl hat sich geändert, also auch die Höhe, die diese
        # Karte will. Ohne diesen Ruf bleibt die Liste auf der Höhe des vorigen
        # Inhalts stehen, bis die Überlagerung das nächste Mal von sich aus
        # verteilt — und das tut sie erst beim nächsten Größenwechsel.
        self._fit()

    def _heading(self, text: str) -> None:
        """Eine Überschrift in der Liste — anwählbar ist sie nicht.

        Zwei Listen übereinander wären zwei Rollbereiche in einem Panel, das
        selten mehr als acht Zeilen hat; eine Liste mit zwei Überschriften ist
        dieselbe Auskunft ohne den zweiten Balken.
        """
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.list.addItem(item)

    @staticmethod
    def _used_label(name: str, count: int) -> str:
        """„PETG Rot — 2 Körper", und im Singular ohne die Eins."""
        if count == 1:
            return f"{name} — {tr('1 Körper')}"
        return f"{name} — {tr('{count} Körper').replace('{count}', str(count))}"

    def _chosen(self) -> filaments.CatalogueFilament | None:
        """Das gewählte Regalfilament, oder nichts.

        Gefragt wird über die Zeilennummer und nicht über ``currentItem()``:
        Die Stubs geben dort ein Element ohne ``None`` zurück, obwohl es bei
        leerer Liste keines gibt — eine Prüfung darauf hielte mypy für
        unerreichbar. ``currentRow() < 0`` sagt dasselbe und ist wahr.
        """
        row = self.list.currentRow()
        if row < 0:
            return None
        item = self.list.item(row)
        name = item.data(_NAME_ROLE)
        if not name:
            return None
        return filaments.CatalogueFilament(
            name=str(name),
            colour=str(item.data(_COLOUR_ROLE) or ""),
            material_type=str(item.data(_MATERIAL_TYPE_ROLE) or ""),
            slicer_profile=str(item.data(_PROFILE_ROLE) or ""),
        )

    def _add(self) -> None:
        dialog = NewFilamentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, colour, material_type, slicer_profile = dialog.filament()
        if not name:
            return
        filaments.remember(name, colour, material_type, slicer_profile)
        self._fill()

    def _on_activated(self, item: QListWidgetItem) -> None:
        if item.data(_SLOT_ROLE) is not None:
            self._request_override()
            return
        if item.data(_NAME_ROLE):
            self._edit()

    def _selection_changed(self, item: QListWidgetItem | None, *_args: object) -> None:
        """Nur Projektfilamente haben eigene Druckwerte."""
        self.settings_button.setEnabled(
            bool(item is not None and item.data(_SLOT_ROLE) is not None)
        )

    def _request_override(self) -> None:
        """Öffnet nichts selbst — das Projekt schreibt nur die Sitzung."""
        row = self.list.currentRow()
        if row < 0:
            return
        slot = self.list.item(row).data(_SLOT_ROLE)
        if isinstance(slot, MaterialSlot):
            self.overrideRequested.emit(slot)

    def _edit(self) -> None:
        chosen = self._chosen()
        if chosen is None:
            return
        dialog = NewFilamentDialog(
            self,
            name=chosen.name,
            colour=chosen.colour,
            material_type=chosen.material_type,
            slicer_profile=chosen.slicer_profile,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        renamed, fresh_colour, material_type, slicer_profile = dialog.filament()
        if not renamed:
            return
        # Ein Filament ist sein Name: Wer ihn ändert, legt kein zweites an —
        # der alte Eintrag geht, der neue kommt.
        if renamed != chosen.name:
            filaments.forget(chosen.name)
        filaments.remember(renamed, fresh_colour, material_type, slicer_profile)
        self._fill()

    def _remove(self) -> None:
        chosen = self._chosen()
        if chosen is None:
            return
        # Keine Rückfrage (Regel 19): Das Regal ist eine Vorwahl, kein
        # Dokument — was hier fehlt, legt man in zwei Klicks wieder an, und
        # kein Projekt verliert dabei etwas.
        filaments.forget(chosen.name)
        self._fill()

    def _on_context_menu(self, where: QPoint) -> None:
        if self._chosen() is None:
            return
        menu = QMenu(self)
        menu.addAction(tr("Ändern …"), self._edit)
        menu.addAction(tr("Aus dem Regal nehmen"), self._remove)
        menu.exec(self.list.viewport().mapToGlobal(where))
