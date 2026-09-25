"""Die Befehlspalette (Bauplan §2.6, §19.2).

Der universelle Weg hinein: alles aus dem Register, per Tippen erreichbar. Das
Kürzel steht neben jedem Eintrag — so lernt man die Kürzel, ohne dass jemand
eine Tabelle davon liest.
"""

from __future__ import annotations

from typing import Final, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import PaletteEntry, menu_twins, palette_entries, variant_members
from app.core.registry.search import STEM_LENGTH, stem_of, synonyms_for

# Ausdrücklich weitergereicht: Die Faltung lebt seit dem 25.09.2026 in
# ``registry.search``, und das Hauptfenster liest sie noch von hier.
from app.core.registry.search import fold as fold
from app.i18n import tr


def native_key(shortcut: str) -> str:
    """Eine Taste, wie sie auf der Tastatur heißt: „Strg+B", nicht „Ctrl+B".

    Hier stand die Rohform — bei den Operationen die Deklaration aus dem
    Register, bei den Fensterbefehlen ``action.shortcut().toString()`` ohne
    ``NativeText``. Gemessen mit installiertem Qt-Katalog: fünf Operationen und
    37 Fensterbefehle sprachen damit englisch, während das Menü daneben deutsch
    sprach — dieselbe Handlung stand an zwei Stellen mit zwei verschiedenen
    Tasten, „Del" hier und „Entf" dort.

    Das ist nicht bloß unsauber: Die Palette ist laut §19.2 der Ort, an dem die
    Kürzel nebenbei gelernt werden, und sie lehrte eine Schreibweise, die auf
    keiner deutschen Tastatur steht. Derselbe Fehler war in der Kürzelübersicht
    schon einmal behoben; hier lag er noch.

    Eine Folge, die Qt nicht versteht, bleibt stehen, wie sie ist — sie
    wegzuwerfen wäre schlimmer als sie englisch zu zeigen.
    """
    if not shortcut:
        return ""
    return QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText) or shortcut


def rank(entry: PaletteEntry, query: str) -> int:
    """Wie gut ein Eintrag zur Anfrage passt — kleiner ist besser.

    **Ein Treffer im Titel wiegt schwerer als einer in der Beschreibung.** Ohne
    diese Ordnung stand bei „bohren" das „An Merkmal ausrichten" vorn, weil
    dessen Beschreibung das Wort Bohrung enthält, und „Bohrung setzen" auf
    Platz drei. Wer tippt, meint fast immer den Namen.

    **Ein Synonym wiegt schwerer als ein Wortstamm.** Es ist eine bewusste
    Zuordnung — jemand hat aufgeschrieben, dass dieses Kundenwort diese
    Operation meint. Ein Stammtreffer ist dagegen eine Rechnung, und die trifft
    auch daneben: „oeffnen" fand über den Stamm das *Deckel erzeugen* (dessen
    Beschreibung „offen" enthält) und stellte es **vor** das *Modell laden*,
    für das das Wort ausdrücklich eingetragen ist. Wer „öffnen" tippt, will
    eine Datei öffnen.

    Sortiert wird **stabil**, damit die Reihenfolge aus ``applies_to`` innerhalb
    derselben Güte erhalten bleibt: Was zur Auswahl passt, steht weiter vorn
    (Gebietsregel, „Was zur Auswahl passt, steht vorn").
    """
    parts = fold(query).split()
    if not parts:
        return 0
    title = fold(str(entry.title))
    name = fold(str(entry.name))
    in_title = all(part in title for part in parts)
    in_synonyms = all(part in synonyms_for(str(entry.name)) for part in parts)
    # **Titel *und* Synonym schlägt Titel allein.** Solange nur eine Operation
    # „Bemalen" hieß, war „färben" eindeutig. Seit beide das Wort im Titel
    # tragen („Filament zuweisen", „Filament auf eine Fläche"), bekamen beide denselben Rang,
    # und bei Gleichstand entschied die Reihenfolge im Register — der Kunde
    # bekam die Fläche, wo er das Teil meinte. Das Synonym ist die bewusste
    # Zuordnung und bricht den Gleichstand; ohne diese Stufe bliebe es
    # wirkungslos, sobald das Wort auch im Titel steht.
    if in_title and in_synonyms:
        return 0
    if in_title:
        return 1
    if all(part in name for part in parts):
        return 2
    if in_synonyms:
        return 3
    if all(stem_of(part) in title for part in parts if len(part) >= STEM_LENGTH):
        return 4
    return 5


def hidden_from_the_menu() -> frozenset[str]:
    """Die Operationen, die im Menü keinen eigenen Eintrag haben.

    **Eine Regel, nicht zwei**, und das ist der Punkt dieser Funktion: Es gibt
    inzwischen zwei Wege, einen Eintrag zusammenzulegen — den Zwilling in
    einem zweiten Rechenkern (:data:`MENU_TWINS`, seit P2.8 der Netz-Quader
    hinter dem exakten „Quader anlegen") und die Variantengruppe
    (:func:`variant_members`, die Erzeugungs- und Schnittarten unter „Aus
    Skizze erzeugen …"). Für die Palette ist der Unterschied gleichgültig: Beide
    Male steht die Handlung anderswo, und beide Male soll sie nicht ein
    zweites Mal ungefragt in der Liste stehen.

    Die Menüleiste stellt dieselbe Frage in zwei getrennten Zeilen
    (``main_window.py``, beim Aufbau der Kategorien). Wer eines Tages die
    dritte Art hinzufügt, soll hier **eine** Stelle finden und nicht zwei —
    sonst wächst mit jedem Mechanismus die Zahl der Orte, an denen er
    vergessen werden kann.
    """
    return frozenset(menu_twins()) | variant_members()


def matches(entry: PaletteEntry, query: str, *, stem: bool = False, any_word: bool = False) -> bool:
    """Teilstring-Suche über Titel, Name und Dokumentation.

    Gefaltet (siehe :func:`fold`), damit „aushoehlen" das Aushöhlen findet —
    vorher gab es darauf **null Treffer**, und dasselbe galt für „groesse".

    ``stem`` sucht nach dem Wortstamm statt nach dem ganzen Wort und ist die
    zweite Runde: „bohren" fand nichts, weil die Operation „Bohrung setzen"
    heißt — ein Fall, den keine Synonymtabelle je vollständig abdeckt und den
    die ersten vier Buchstaben lösen. Gelockert wird erst, wenn die genaue
    Suche leer ausgeht (siehe ``CommandPalette._refilter``): Sonst stünde
    zwischen guten Treffern immer auch Ungefähres.

    **Ohne Suchtext fehlt, was im Menü keinen eigenen Eintrag hat**
    (:func:`hidden_from_the_menu`), und das ist der einzige Fall, in dem diese
    Funktion etwas weglässt.

    Der Grund steht in der Liste, die der Kunde sonst sieht: Wer „quader"
    suchte, bekam „Exakten Quader anlegen" **vor** „Quader anlegen" — die
    Sonderform vor der Normalform, alphabetisch nach dem Bauart-Wort sortiert,
    und der Unterschied stand nur im Tooltip. Im Menü ist dieselbe Sache seit
    §35 gelöst: ein Eintrag, und der Haken im Dialog wählt den Kern.

    **Was das nicht antastet, ist die Erreichbarkeit.** §2.6 sagt „alles aus
    dem Register **per Suche**", und genau das gilt weiter: Ab dem ersten
    getippten Zeichen ist der Zwilling wieder da, über Titel, Namen, ``doc``
    und Synonyme. Gefiltert wird die **Anzeige**, nicht der Bestand —
    :func:`app.core.registry.palette_entries` gibt unverändert jede Operation
    zurück, und sein Docstring sagt zu Recht zu, dass es „eine Reihenfolge und
    keine Auswahl" ist: Diese Zusage gilt der Quelle, und
    ``tests/test_acceptance_p0.py`` hält sie dort fest.

    Dieselbe Lockerung hat das Menü längst: Das Abnahmekriterium aus §40 nennt
    Ops „sichtbar in Menü, Palette", und für zusammengelegte Zwillinge ist das
    im Menü seit der ersten Zusammenlegung nicht mehr wörtlich erfüllt,
    sondern durch „erreichbar über den Partner" ersetzt.
    """
    if not query:
        return entry.name not in hidden_from_the_menu()
    if any_word:
        return word_hits(entry, query) > 0
    haystack = fold(f"{entry.title} {entry.name} {entry.doc} {synonyms_for(entry.name)}")
    parts = fold(query).split()
    if not stem:
        return all(part in haystack for part in parts)
    return all(stem_of(part) in haystack for part in parts if len(part) >= STEM_LENGTH)


def word_hits(entry: PaletteEntry, query: str) -> int:
    """Wie viele Wörter der Anfrage diesen Eintrag treffen — ganz oder am Stamm.

    Die dritte Runde der Suche (siehe ``CommandPalette._refilter``): Wer
    „ecke abrunden" tippt, meint das *Verrunden*, und „abrunden" allein fand
    es — beide Wörter zusammen fanden nichts, weil :func:`matches` alle
    verlangt (Bedienweg-Durchsicht 14.09.2026: sieben von 71 Kundenwörtern
    leer, darunter „zu viele dreiecke" und „gerade stellen"). Gezählt und
    nicht nur gefragt, damit die Liste nach Trefferzahl sortiert werden kann.
    """
    haystack = fold(f"{entry.title} {entry.name} {entry.doc} {synonyms_for(entry.name)}")
    return sum(
        part in haystack or (len(part) >= STEM_LENGTH and stem_of(part) in haystack)
        for part in fold(query).split()
    )


#: Wie weit die Tastenspalte vom rechten Rand einrückt.
SHORTCUT_MARGIN: Final = 12


def first_sentence(text: str) -> str:
    """Der erste Satz eines ``doc``-Texts — für die zweite Zeile eines Zwillings."""
    head, dot, _rest = text.partition(". ")
    return f"{head}." if dot else text


class _Rows(QStyledItemDelegate):
    """Zeichnet Titel links und Kürzel **rechtsbündig** in einer Spalte.

    Vorher hing das Kürzel mit einem Tabulator am Titel, und Qt setzt dafür
    ein festes Tabstopp-Raster: Bei „Abziehen" begann die Taste an einer
    anderen Stelle als bei „Auf dem Bett anordnen" — zwei Spalten, zwischen
    denen die Augen springen, obwohl beide dasselbe sagen. Wer die Kürzel
    nebenbei lernen soll (§19.2), muss sie untereinander finden.

    Der zweizeilige Fall bleibt, wie er war: Ein gesperrter Eintrag trägt
    seinen Grund als zweite Zeile, und der gehört unter den Titel, nicht in
    die Tastenspalte.
    """

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if "	" not in text:
            super().paint(painter, option, index)
            return

        first_line, separator, detail = text.partition("\n")
        title, shortcut = first_line.split("	", 1)
        plain = QStyleOptionViewItem(option)
        self.initStyleOption(plain, index)
        plain.text = f"{title}{separator}{detail}"
        style = option.widget.style() if option.widget else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, plain, painter, option.widget)
        else:  # pragma: no cover - ohne Stil zeichnet Qt selbst
            super().paint(painter, option, index)

        painter.save()
        painter.setPen(
            plain.palette.color(plain.palette.currentColorGroup(), plain.palette.ColorRole.Text)
        )
        area = QRect(option.rect)
        area.setRight(area.right() - SHORTCUT_MARGIN)
        if separator:
            line_height = plain.fontMetrics.height()
            text_height = line_height + plain.text.count("\n") * plain.fontMetrics.lineSpacing()
            area.setTop(area.top() + max(0, (area.height() - text_height) // 2))
            area.setHeight(line_height)
        painter.drawText(
            area,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            shortcut,
        )
        painter.restore()


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
        # Die Tastenspalte flieht rechts, statt dem Titel zu folgen (:class:`_Rows`).
        self.list.setItemDelegate(_Rows(self.list))
        self.list.itemActivated.connect(self.accept)

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
        # **Und eine dritte für mehrwortige Fragen.** „ecke abrunden" fand
        # nichts, obwohl „abrunden" das *Verrunden* findet; „zu viele
        # dreiecke" nichts, obwohl „dreiecke" auf *Dreiecke verringern* führt
        # (Bedienweg-Durchsicht 14.09.2026, sieben von 71 Kundenwörtern
        # leer). Erst wenn kein Eintrag auf alle Wörter passt, genügt eines —
        # sortiert nach Trefferzahl und mit einer Zeile darüber, die das sagt:
        # Eine Liste, die stillschweigend weniger prüft, sieht aus wie eine
        # genaue.
        loosened = False
        if not found and len(query.split()) > 1:
            found = [entry for entry in self._entries if matches(entry, query, any_word=True)]
            loosened = bool(found)
        # Stabil nach Güte: Titel vor Name vor Beschreibung, und innerhalb
        # derselben Güte bleibt die Reihenfolge aus ``applies_to`` stehen.
        #
        # **Und der Zwilling zuletzt, bei gleicher Güte.** Sonst kommt die
        # Verwirrung eine Ebene später wieder: Gemessen stand nach dem Tippen
        # von „quader" wieder „Exakten Quader anlegen" **vor** „Quader
        # anlegen" — alphabetisch richtig und für den Kunden falsch, denn das
        # ist die Sonderform vor der Normalform. Die Grundliste zeigt den
        # Zwilling gar nicht (:func:`matches`); wer ihn sucht, findet ihn, aber
        # er drängt sich nicht vor seinen Partner.
        hidden_names = hidden_from_the_menu()
        # Vier Paare tragen wörtlich denselben Titel („Quader anlegen" zweimal)
        # — im Menü unsichtbar, in der Suche stehen sie untereinander, und der
        # Unterschied stand nur im Tooltip. Beide Zwillinge bekommen ihren
        # ``doc``-Satz als zweite Zeile, so wie der gesperrte Fall seinen Grund
        # (Review 02.09.2026).
        twins = menu_twins().keys() | menu_twins().values()
        found.sort(
            key=lambda entry: (
                -word_hits(entry, query) if loosened else 0,
                rank(entry, query),
                entry.name in hidden_names,
            )
        )
        offset = 0
        if loosened:
            # Nicht wählbar und ohne Daten, wie die leere Antwort unten:
            # ``chosen()`` gibt darüber None zurück, die Vorauswahl übergeht sie.
            heading = QListWidgetItem(
                tr("Kein Befehl passt auf alle Wörter — das Folgende passt auf einzelne.")
            )
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(heading)
            offset = 1
        for entry in found:
            label = str(entry.title)
            if entry.shortcut:
                label = f"{label}\t{native_key(entry.shortcut)}"
            if not entry.available and entry.reason:
                # Der Grund als zweite Zeile: das Ausgrauen allein wäre die
                # halbe Antwort (Regel 18) — und über die Palette stand die
                # modale Sackgasse offen, die das Menü längst beseitigt hat.
                label = f"{label}\n{entry.reason}"
            elif entry.name in twins:
                label = f"{label}\n{first_sentence(str(entry.doc))}"
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
            #
            # **Aber nur unter den gleich guten Treffern.** Gesucht wird auch in
            # der Beschreibung, und die Sperre überspringt: Wer „Verrund" tippte
            # und nichts gewählt hatte, bekam *Quader anlegen* vorgewählt — es
            # steht in der Liste, weil sein Satz „Verrundungen" enthält, und war
            # der erste Eintrag ohne Sperre. Enter legte einen Quader an
            # (gemessen am 13.09.2026 am laufenden Fenster). Ein Klick, der
            # nichts tut, ist ärgerlich; einer, der etwas anderes tut, ist
            # schlimmer. Findet sich in der besten Güte nichts Ausführbares,
            # bleibt die Wahl auf deren erstem Eintrag: Er sagt, was ihm fehlt.
            best = rank(found[0], query) if found else 0
            chosen_row = offset
            for row in range(offset, self.list.count()):
                item = self.list.item(row)
                if item is None or rank(found[row - offset], query) != best:
                    break
                if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                    chosen_row = row
                    break
            self.list.setCurrentRow(chosen_row)
        elif query.strip():
            # Eine leere Liste sagt nicht, ob nichts passt oder ob die Palette
            # kaputt ist. Der Eintrag ist nicht wählbar und trägt keine Daten —
            # ``chosen()`` gibt darüber weiter None zurück, und die Eingabe
            # kann nicht versehentlich einen Befehl auslösen. Er ist damit auch
            # für die Vorauswahl darüber unsichtbar.
            nothing = QListWidgetItem(
                tr(
                    "Kein Befehl passt zu „{term}“. Gesucht wird in Titel, Name und Beschreibung."
                ).format(term=query.strip())
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
