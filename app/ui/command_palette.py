"""Die Befehlspalette (Bauplan §2.6, §19.2).

Der universelle Weg hinein: alles aus dem Register, per Tippen erreichbar. Das
Kürzel steht neben jedem Eintrag — so lernt man die Kürzel, ohne dass jemand
eine Tabelle davon liest.
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from typing import Final, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QFontMetricsF, QKeyEvent, QKeySequence, QPainter, QPalette
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
from app.core.registry.search import (
    STEM_LENGTH,
    customer_phrases,
    rank_entries,
    search_fields,
    starts_a_word,
    stem_of,
    synonyms_for,
)

# Ausdrücklich weitergereicht: Die Faltung lebt seit dem 25.09.2026 in
# ``registry.search``, und das Hauptfenster liest sie noch von hier.
from app.core.registry.search import fold as fold
from app.core.registry.surfaces import first_sentence as first_sentence
from app.i18n import tr
from app.ui.shortcut_schemes import return_opens
from app.ui.style import NORMAL, TIGHT, WIDE


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
    # **Am Wortanfang, nicht mitten im Wort.** „Stützen" stellte *Hilfe:
    # Solidon3D unterstützen …* vor alles andere, weil das Wort in
    # „unterstützen" steckt; ein Titeltreffer mitten im Wort zählt deshalb erst
    # nach den Kundenwörtern (Durchsicht 0.5.1, 26.09.2026). Eine
    # Zusammensetzung bleibt findbar — nur nicht vor dem, was gemeint ist.
    at_title_start = in_title and all(starts_a_word(part, title) for part in parts)
    # **Eine Wendung, am Wortanfang.** Die Wörter der Anfrage müssen in
    # *einer* Kundenwendung stehen, nicht verstreut über alle: „Loch machen"
    # fand sonst *Bohrung ändern* vor *Bohrung setzen*, weil dessen Wendungen
    # „Loch größer" und „größer machen" beide Wörter enthielten; und „move
    # hole" fand *Bohrung verschließen*, weil „move" in „remove hole" steckt.
    # Wer die Wendung ganz tippt, hat genau sie gemeint — das wiegt mehr als
    # eine, die sie nur enthält.
    phrases = customer_phrases(str(entry.name))
    typed = " ".join(parts)
    said_exactly = typed in phrases
    in_phrase = said_exactly or any(
        all(starts_a_word(part, phrase) for part in parts) for phrase in phrases
    )
    # **Titel *und* Synonym schlägt Titel allein.** Solange nur eine Operation
    # „Bemalen" hieß, war „färben" eindeutig. Seit beide das Wort im Titel
    # tragen („Filament zuweisen", „Filament auf eine Fläche"), bekamen beide denselben Rang,
    # und bei Gleichstand entschied die Reihenfolge im Register — der Kunde
    # bekam die Fläche, wo er das Teil meinte. Das Synonym ist die bewusste
    # Zuordnung und bricht den Gleichstand; ohne diese Stufe bliebe es
    # wirkungslos, sobald das Wort auch im Titel steht.
    if at_title_start and in_phrase:
        return 0
    if at_title_start:
        return 1
    if all(part in name for part in parts):
        return 2
    if said_exactly:
        return 3
    if in_phrase:
        return 4
    if in_title:
        return 5
    if all(stem_of(part) in title for part in parts if len(part) >= STEM_LENGTH):
        return 6
    return 7


#: Ab welcher Güte aus :func:`rank` ein Treffer ungenau ist — eine Wendung,
#: die die Wörter nur enthält, ein Titel mitten im Wort, ein Stamm, die
#: Beschreibung. Darunter ordnet die Palette stabil, darüber nach der Wertung
#: der Wortsuche (``registry.search.rank_entries``).
LOOSE_RANK: Final = 4


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


def _haystack(entry: PaletteEntry) -> str:
    """Titel, Name, Beschreibung und Kundenwörter eines Eintrags, gefaltet."""
    return _folded_haystack(
        str(entry.title), str(entry.name), str(entry.doc), synonyms_for(str(entry.name))
    )


@lru_cache(maxsize=2048)
def _folded_haystack(title: str, name: str, doc: str, synonyms: str) -> str:
    """Die Faltung je Zeile einmal statt je Tastendruck.

    Sie lief für jede der gut zweihundert Zeilen bei jedem Zeichen zweimal —
    im Filter und in der Sortierung —, über Beschreibungen von mehreren hundert
    Zeichen. Geschlüsselt über die Texte selbst, die übersetzten
    eingeschlossen: Ein Sprachwechsel ist ein anderer Schlüssel.
    """
    return fold(f"{title} {name} {doc} {synonyms}")


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
    haystack = _haystack(entry)
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
    haystack = _haystack(entry)
    return sum(
        part in haystack or (len(part) >= STEM_LENGTH and stem_of(part) in haystack)
        for part in fold(query).split()
    )


#: Wie weit die Tastenspalte vom rechten Rand einrückt.
SHORTCUT_MARGIN: Final = 12


class _Rows(QStyledItemDelegate):
    """Zeichnet Titel links und Kürzel **rechtsbündig** in einer Spalte.

    Vorher hing das Kürzel mit einem Tabulator am Titel, und Qt setzt dafür
    ein festes Tabstopp-Raster: Bei „Abziehen" begann die Taste an einer
    anderen Stelle als bei „Auf dem Bett anordnen" — zwei Spalten, zwischen
    denen die Augen springen, obwohl beide dasselbe sagen. Wer die Kürzel
    nebenbei lernen soll (§19.2), muss sie untereinander finden.

    Titel und Erklärung bekommen eigene Zeichenbereiche. Der native Stil
    zeichnet Zeilenumbrüche sonst je nach Plattform als einzeiligen Text.
    Die vollständige Erklärung bleibt bei gekürzter Anzeige im Tooltip.
    """

    def __init__(self, parent: QWidget, *, shortcuts: tuple[str, ...] = ()) -> None:
        super().__init__(parent)
        self._shortcuts = shortcuts

    def sizeHint(  # noqa: N802 — Qt-Name
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        plain = QStyleOptionViewItem(option)
        self.initStyleOption(plain, index)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        lines = 2 if "\n" in text else 1
        height = lines * plain.fontMetrics.height() + (lines - 1) * TIGHT + 2 * TIGHT
        # Die Liste gibt die Breite vor, der Text darf sie nicht aufziehen.
        return QSize(0, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        plain = QStyleOptionViewItem(option)
        self.initStyleOption(plain, index)
        # Qts Stiloption ersetzt Zeilenumbrüche durch Unicode-Zeilentrenner.
        # Die Felder kommen deshalb aus dem unveränderten Modelltext.
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        first_line, separator, detail = text.partition("\n")
        title, _tab, shortcut = first_line.partition("\t")
        plain.text = ""
        widget = option.widget or cast(QWidget, self.parent())
        widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, plain, painter, widget)

        painter.save()
        painter.setClipRect(option.rect)
        painter.setFont(plain.font)
        group = (
            QPalette.ColorGroup.Disabled
            if not plain.state & QStyle.StateFlag.State_Enabled
            else plain.palette.currentColorGroup()
        )
        role = (
            QPalette.ColorRole.HighlightedText
            if plain.state & QStyle.StateFlag.State_Selected
            else QPalette.ColorRole.Text
        )
        painter.setPen(plain.palette.color(group, role))
        area = option.rect.adjusted(NORMAL, TIGHT, -SHORTCUT_MARGIN, -TIGHT)
        metrics = plain.fontMetrics
        line_height = metrics.height()
        text_height = 2 * line_height + TIGHT if separator else line_height
        area.setTop(area.top() + max(0, (area.height() - text_height) // 2))
        title_area = QRect(area.left(), area.top(), area.width(), line_height)
        # **Gebrochen gemessen und aufgerundet.** ``QFontMetrics`` gibt ganze
        # Pixel und rundet zur nächsten, das Kürzen rechnet mit der echten Breite: Mit
        # Cocoas gebrochenen Metriken bekam „Ctrl+B“ 38 Pixel für 38,4 und
        # stand als „Ctrl…“ in der Palette (RM-531).
        exact = QFontMetricsF(plain.font)
        shortcut_width = min(
            max(
                (math.ceil(exact.horizontalAdvance(key)) for key in (*self._shortcuts, shortcut)),
                default=0,
            ),
            max(0, area.width() // 2),
        )
        if shortcut_width:
            title_area.setWidth(max(0, title_area.width() - shortcut_width - NORMAL))
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        painter.drawText(
            title_area,
            flags,
            metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_area.width()),
        )
        if shortcut:
            shortcut_area = QRect(
                area.right() - shortcut_width + 1, area.top(), shortcut_width, line_height
            )
            painter.drawText(
                shortcut_area,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(shortcut, Qt.TextElideMode.ElideRight, shortcut_width),
            )
        if separator:
            detail_area = QRect(
                area.left(), area.top() + line_height + TIGHT, area.width(), line_height
            )
            painter.drawText(
                detail_area,
                flags,
                metrics.elidedText(
                    " ".join(detail.splitlines()), Qt.TextElideMode.ElideRight, detail_area.width()
                ),
            )
        painter.restore()


class CommandPalette(QDialog):
    """Tippen, wählen, ausführen."""

    def __init__(
        self,
        entries: list[PaletteEntry] | None = None,
        parent: QWidget | None = None,
        *,
        query: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("Befehle"))
        # Breite **und** Höhe. Nur die Breite stand hier, und ohne Höhe nimmt
        # das Layout seine kleinste: 248 Bildpunkte, also sieben Zeilen von
        # hundertfünfundvierzig. Die Palette ist der Weg, auf dem alles
        # erreichbar sein soll (§19.2) — sieben Zeilen machen daraus eine
        # Suchmaske, in der man tippen *muss*, statt eine Liste, in der man
        # blättern *kann*. Ein Eintrag kann zwei Zeilen hoch sein (Titel plus
        # Erklärung), 480 zeigen also zwölf bis sechzehn.
        self.setMinimumSize(520, 480)
        self._entries = entries if entries is not None else list(palette_entries())
        # Die Suchtexte der Wortsuche im Kern, einmal je Palette — sie ordnet
        # die dritte Runde (:meth:`_refilter`).
        self._fields = search_fields(
            (str(entry.name), entry.title, entry.doc) for entry in self._entries
        )

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Befehl suchen …"))
        self.search.setAccessibleName(tr("Befehl suchen"))
        self.search.textChanged.connect(self._refilter)
        self.search.returnPressed.connect(self.accept)

        self.list = QListWidget(self)
        # Die Tastenspalte flieht rechts, statt dem Titel zu folgen (:class:`_Rows`).
        self.list.setItemDelegate(
            _Rows(
                self.list,
                shortcuts=tuple(
                    native_key(entry.shortcut) for entry in self._entries if entry.shortcut
                ),
            )
        )
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemActivated.connect(self.accept)
        # Am Mac meldet Qt Return in der Liste nicht als Aktivierung.
        return_opens(self.list, sys.platform)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        # Ein Suchtext von außen — „In allen Funktionen suchen“ unter der Karte
        # der Auswahl (RM-506): dasselbe Wort, jetzt über alles.
        self.search.setText(query)
        self._refilter(query)

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
        # Unterschied stand nur im Tooltip. Die Erklärungszeile steht nun bei
        # jedem Befehl; so lassen sich auch gleiche Titel direkt unterscheiden.
        # **Die dritte Runde ordnet die Wortsuche des Kerns** — dieselbe, mit
        # der der Agent seine Werkzeuge wählt (``registry.search``). Nach der
        # bloßen Trefferzahl stand bei „Teil kleiner machen" *Fläche
        # unterteilen* vorn, weil „teil" und „machen" in ihrer Beschreibung
        # stehen; die Wertung wiegt Kundenwörter als Wendung und seltene Wörter
        # schwerer als häufige.
        #
        # **Und in den ersten beiden Runden bricht sie den Gleichstand** einer
        # ungenauen Güte (ab :data:`LOOSE_RANK`): Bei „Teil kleiner machen"
        # standen *Teilen* und *Skalieren* in derselben Stufe, und die
        # Reihenfolge der Liste entschied. Bei einem Titel- oder Wendungstreffer
        # bleibt es bei der stabilen Reihenfolge — dort steht vorn, was zur
        # Auswahl passt (``palette_entries(for_feature=…)``).
        scores = dict(rank_entries([query], self._fields)) if query.strip() else {}

        def order(entry: PaletteEntry) -> tuple[float, int, int, bool, float]:
            good = rank(entry, query)
            score = scores.get(str(entry.name), 0.0)
            return (
                -score if loosened else 0.0,
                -word_hits(entry, query) if loosened else 0,
                good,
                entry.name in hidden_names,
                -score if good >= LOOSE_RANK else 0.0,
            )

        found.sort(key=order)
        offset = 0
        if loosened:
            # Nicht wählbar und ohne Daten, wie die leere Antwort unten:
            # ``chosen()`` gibt darüber None zurück, die Vorauswahl übergeht sie.
            heading = QListWidgetItem(
                tr("Kein Befehl passt auf alle Wörter — das Folgende passt auf einzelne.")
            )
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            heading.setToolTip(heading.text())
            self.list.addItem(heading)
            offset = 1
        for entry in found:
            label = str(entry.title)
            if entry.shortcut:
                label = f"{label}\t{native_key(entry.shortcut)}"
            detail = first_sentence(str(entry.doc)).strip()
            # Fensterbefehle tragen den Titel als Suchtext, nicht als eigene
            # Erklärung. Eine zweite Zeile mit demselben Wort wäre redundant.
            if detail == str(entry.title).strip():
                detail = ""
            if not entry.available and entry.reason:
                # Der Grund als zweite Zeile: das Ausgrauen allein wäre die
                # halbe Antwort (Regel 18) — und über die Palette stand die
                # modale Sackgasse offen, die das Menü längst beseitigt hat.
                reason = str(entry.reason).strip()
                detail = f"{detail} — {reason}" if detail else reason
            if detail:
                label = f"{label}\n{detail}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry.name)
            tooltip_lines: list[str] = []
            where = str(entry.where).strip()
            for text in (
                str(entry.title),
                str(entry.reason) if not entry.available else "",
                str(entry.doc),
                # Der Ort, wie das Kürzel: nebenbei gelernt (RM-506).
                tr("Ort: {place}", place=where) if where else "",
            ):
                text = text.strip()
                if text and text not in tooltip_lines:
                    tooltip_lines.append(text)
            item.setToolTip("\n".join(tooltip_lines))
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, "\n".join(tooltip_lines[1:]))
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
            nothing.setToolTip(nothing.text())
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
