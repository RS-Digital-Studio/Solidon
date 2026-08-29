"""Die Befehlspalette (Bauplan §2.6, §19.2).

Der universelle Weg hinein: alles aus dem Register, per Tippen erreichbar. Das
Kürzel steht neben jedem Eintrag — so lernt man die Kürzel, ohne dass jemand
eine Tabelle davon liest.
"""

from __future__ import annotations

from typing import Final, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import MENU_TWINS, PaletteEntry, palette_entries, variant_members
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
    # tragen („Teil färben", „Fläche färben"), bekamen beide denselben Rang,
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


#: Wörter, die ein Kunde tippt, und die Operationen, die er damit meint.
#:
#: **Gemessen, nicht geraten.** Am 23.08.2026 wurden 42 Wörter durchprobiert,
#: wie sie jemand tippt, der noch nie in unserem Register gelesen hat —
#: Alltagswörter, Slicer-Wörter, und die aus anderen CAD-Programmen. Zehn
#: davon fanden **nichts**: nicht das Falsche, sondern gar nichts, und die
#: Palette antwortete „Kein Befehl passt".
#:
#: Der Docstring unten sagt, eine Synonymtabelle decke so etwas „nie
#: vollständig" ab. Das stimmt und ist kein Grund, sie wegzulassen: Die
#: Faltung und der Wortstamm tragen weit — „aushoehlen" findet das Aushöhlen,
#: „bohren" die Bohrung —, aber sie tragen nicht über die Wortgrenze. „Fase
#: anbringen" und „Kante brechen" haben keinen gemeinsamen Buchstabenanfang,
#: und keine Rechnung der Welt findet das eine über das andere.
#:
#: **Nur wo das gemeinte Wort im Titel nicht vorkommt.** „Spiegeln" steht
#: nicht hier, weil die Operation so heißt; „bohren" auch nicht, weil der
#: Stamm es findet. Was hier steht, ist der Rest.
#:
#: ``tests/test_theme_and_palette.py`` prüft beides: dass jedes Wort seine
#: Operation findet, und dass jedes Ziel im Register existiert — ein Synonym,
#: dessen Operation umbenannt wurde, zeigt sonst stumm ins Leere.
SYNONYMS: Final[dict[str, tuple[str, ...]]] = {
    "fillet_edges": ("abrunden", "rundung", "radius"),
    "chamfer_edges": ("kante brechen", "abschraegen", "45 grad"),
    "pattern": ("array", "vervielfaeltigen", "wiederholen"),
    "split_pinned": ("zerschneiden", "halbieren", "durchschneiden"),
    "union_objects": ("zusammenfuegen", "verschmelzen", "verbinden"),
    "subtract_objects": ("ausschneiden", "aussparen", "wegnehmen"),
    "label_text": ("gravieren", "beschriften", "praegen"),
    "decimate_mesh": ("vereinfachen", "reduzieren", "leichter machen"),
    "hollow_object": ("aushoehlen", "leer machen", "exakt", "brep", "echte kanten"),
    # Versteckter Zwilling (``MENU_TWINS``): kein Menüeintrag, also ist die
    # Palette neben dem Verlauf sein einziger direkter Weg.
    "shell_exact": ("exakt aushoehlen", "brep aushoehlen"),
    # **„exakt" gehört an beide Hälften eines Paares**, seit die Grundliste den
    # Zwilling nicht mehr auflistet (:func:`matches`). Wer das Wort tippt, will
    # zwei Wege sehen: die Direktwahl des exakten Kerns **und** den Eintrag,
    # dessen Dialog den Haken trägt — und der ist meist der bessere, weil er
    # alle Felder zeigt. Ohne diese Zeilen fände er nur den ersten.
    #
    # „echte kanten" steht daneben, weil es das Wort ist, mit dem die
    # ``doc``-Sätze den Unterschied erklären, ohne „exakt" zu benutzen: „Legt
    # einen Quader mit echten Kanten an."
    # **Nur diese drei Wörter, keine Zugaben.** Der erste Anlauf hängte
    # „loch bohren" an ``drill_hole`` — und machte damit die Suche nach
    # „bohren" zu einem *genauen* Treffer. Daran hing ein fremder Test: Der
    # Wortstamm-Rückfall greift laut ``_refilter`` erst, wenn die genaue Suche
    # leer ausgeht, und „bohren" gegen „Bohrung setzen" war sein Prüffall. Ein
    # Synonym, das der Stamm ohnehin schon findet, bringt nichts und nimmt
    # einer Zusicherung ihren Fall.
    "create_box": ("exakt", "brep", "echte kanten"),
    "create_brep_box": ("exakt", "brep", "echte kanten"),
    "create_cylinder": ("exakt", "brep", "echte kanten"),
    "create_brep_cylinder": ("exakt", "brep", "echte kanten"),
    "drill_hole": ("exakt", "brep", "echte kanten"),
    "drill_brep_hole": ("exakt", "brep", "echte kanten"),
    "repair_mesh": ("loecher schliessen", "reparieren", "flicken"),
    # **Die gewöhnlichsten Wörter fehlten**, und das fiel niemandem auf, weil
    # niemand sie sucht, der das Register kennt: „kopieren" und „loeschen"
    # führten ins Leere, obwohl es beides gibt. Gemessen an vierzig Wörtern,
    # mit denen ein Kunde suchen würde — sechs fanden nichts, und keines davon
    # war ein Fachbegriff.
    "duplicate_object": ("kopieren", "klonen", "zweites teil"),
    "delete_object": ("loeschen", "wegwerfen", "rauswerfen"),
    "load": ("oeffnen", "importieren", "stl", "datei"),
    # Beide heißen seit dem Filament-Umbau „färben" und stehen im Menü
    # nebeneinander; die Suchwörter trennen sie nach dem, was der Kunde
    # meint — das ganze Teil oder die eine Fläche. „Pinseln" und „anmalen"
    # sind geblieben: Wer sie tippt, sucht das, was der Pinsel einmal tat,
    # und findet jetzt die Füllung.
    "assign_slot": ("faerben", "einfaerben", "farbe zuweisen", "ganzes teil"),
    # **Ohne jedes „faerben", auch nicht in einem längeren Wort.** Seit der
    # Umbenennung tragen beide Titel das Wort („Teil färben", „Fläche
    # färben"), also entscheidet es nichts mehr — und als Synonym stand es
    # zusätzlich an beiden. Wer „färben" tippte, bekam die Fläche, weil bei
    # Gleichstand die Reihenfolge im Register zählt.
    #
    # Gestrichen wurde deshalb auch „flaeche einfaerben": Gesucht wird per
    # Teilzeichenkette, und darin **steckt** „faerben". Ein Synonym, das das
    # gesuchte Wort enthält, ohne es zu meinen, wirkt wie eines, das es meint.
    # Das Wort allein gehört dem Teil; die Fläche findet, wer „flaeche" tippt.
    "paint_slot": ("anmalen", "pinseln", "flaeche"),
    # Ein Logo ist ein Bild, und ein Bild wird hier zu einer Höhe. Beide Wörter
    # stehen im Kopf dessen, der es aufbringen will, und keines im Titel.
    "displace_image": ("logo", "foto", "bild aufbringen"),
}


def synonyms_for(name: str) -> str:
    """Die Kundenwörter dieser Operation, als ein Stück Suchtext.

    Gefaltet gespeichert und gefaltet gesucht — die Tabelle oben schreibt
    „aushoehlen" und nicht „aushöhlen", damit beide Schreibweisen denselben
    Weg nehmen.
    """
    return " ".join(SYNONYMS.get(name, ()))


def hidden_from_the_menu() -> frozenset[str]:
    """Die Operationen, die im Menü keinen eigenen Eintrag haben.

    **Eine Regel, nicht zwei**, und das ist der Punkt dieser Funktion: Es gibt
    inzwischen zwei Wege, einen Eintrag zusammenzulegen — den Zwilling in
    einem zweiten Rechenkern (:data:`MENU_TWINS`, „Exakten Quader anlegen"
    unter dem Haken von „Quader anlegen") und die Variantengruppe
    (:func:`variant_members`, die vier Skizzen-Arten unter „Aus Skizze
    erzeugen …"). Für die Palette ist der Unterschied gleichgültig: Beide
    Male steht die Handlung anderswo, und beide Male soll sie nicht ein
    zweites Mal ungefragt in der Liste stehen.

    Die Menüleiste stellt dieselbe Frage in zwei getrennten Zeilen
    (``main_window.py``, beim Aufbau der Kategorien). Wer eines Tages die
    dritte Art hinzufügt, soll hier **eine** Stelle finden und nicht zwei —
    sonst wächst mit jedem Mechanismus die Zahl der Orte, an denen er
    vergessen werden kann.
    """
    return frozenset(MENU_TWINS) | variant_members()


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
    haystack = fold(f"{entry.title} {entry.name} {entry.doc} {synonyms_for(entry.name)}")
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
        found.sort(key=lambda entry: (rank(entry, query), entry.name in hidden_names))
        for entry in found:
            label = str(entry.title)
            if entry.shortcut:
                label = f"{label}\t{native_key(entry.shortcut)}"
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
