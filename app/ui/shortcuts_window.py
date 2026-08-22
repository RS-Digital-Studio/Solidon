"""Die Kürzelübersicht (Konzept P15 §7 Etappe 8, D6).

`?` zeigt, was es gibt. SindriCAD hat das, wir hatten es nicht — und ohne eine
solche Liste lernt ein Kürzel nur, wer den Menüeintrag daneben lange genug
ansieht.

**Erzeugt, nicht gepflegt.** Die Liste liest das Register und die Befehlstabelle
des Fensters; eine von Hand geschriebene wäre am Tag nach dem nächsten Kürzel
falsch, und niemand würde es merken. Aus demselben Grund steht sie in beiden
Sprachen, ohne dass jemand sie übersetzt: die Titel kommen dorther, wo sie
ohnehin übersetzt sind.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import TranslatableText, _, tr
from app.ui.tool_strip import strip_title

#: Die Tasten, die am Fenster hängen und in keinem Menü stehen.
#:
#: Es sind fünf, und sie fehlten der Übersicht vollständig: Escape schließt das
#: offene Werkzeug, ``Strg+Tab`` blättert die Auswahl durch, und die
#: Zoom-Tasten sind der Weg durch den Viewport ohne Zeigegerät. Sie sind
#: ``QShortcut`` am Fenster (``MainWindow._install_shortcuts``), und ein
#: ``QShortcut`` trägt keinen Titel — deshalb steht er hier.
#:
#: Eine Tabelle von Hand ist der Preis, und sie driftet. Dagegen steht ein Test:
#: ``tests/test_interface_limits.py`` vergleicht sie mit den ``QShortcut``-Kindern
#: des gebauten Fensters und wird rot, sobald einer dazukommt, der hier fehlt.
#: Das ist der Unterschied zu vorher — vorher fehlten dreizehn, und nichts sagte
#: es.
WINDOW_KEYS: Final[tuple[tuple[str, TranslatableText], ...]] = (
    ("Esc", _("Werkzeug schließen")),
    ("Ctrl+Tab", _("Nächstes Objekt wählen")),
    ("Ctrl+Shift+Tab", _("Voriges Objekt wählen")),
    ("Ctrl++", _("Näher heranzoomen")),
    ("Ctrl+-", _("Weiter herauszoomen")),
)


def entries(menu_bar: QMenuBar | None, window: QWidget | None = None) -> list[tuple[str, str, str]]:
    """Gruppe, Titel und Kürzel — in der Reihenfolge, in der sie dastehen.

    Gelesen wurden vorher zwei Quellen: die Befehlstabelle des Fensters und das
    Register. Beide zusammen sind nicht alles. Die fünfzehn Tasten für
    Darstellung (``1`` bis ``6``) und Kameravorgaben (``Strg+0`` bis
    ``Strg+6``) gehen
    weder durch die eine noch durch die andere — sie standen in keiner
    Übersicht, obwohl sie im Menü daneben stehen.

    **Aber die Menüleiste ist es auch nicht allein**, und hier stand genau diese
    Annahme: „dort landet jede Aktion, die ein Mensch findet". Nachgezählt am
    gebauten Fenster waren es 36 Menütasten gegen 49 belegte — es fehlten die
    acht Werkzeugtasten ``Alt+1`` bis ``Alt+8``, die fünf freien Fenstertasten
    und der ganze Zeichensatz. Ausgerechnet die acht, von denen ein Kommentar in
    ``main_window`` sagt: „Welche Zahl zu welchem Werkzeug gehört, steht im
    Tooltip des Knopfes **und in der Kürzelübersicht**."

    Drei Quellen also: die Menüleiste, die angemeldeten Werkzeuge (``window.tools``
    kennt Titel und Taste) und :data:`WINDOW_KEYS`.

    **Sortiert wird nicht.** Hier stand ``sorted(found)``, und das ordnete nach
    Bytes: „Ändern" landete hinter allem anderen, weil „Ä" hinter „z" steht — die
    größte Gruppe ganz unten. Und innerhalb einer Gruppe stand Alphabet statt
    Menüreihenfolge, sodass die Reihe ``1`` bis ``6`` über die Gruppe verstreut
    war. Wer die Liste neben das Menü legt — und dafür ist sie da —, findet sie
    jetzt an derselben Stelle.

    Was kein Kürzel hat, steht nicht darin: eine Kürzelübersicht mit leeren
    Zeilen ist eine Liste aller Befehle, und die ist die Befehlspalette.
    """
    found: list[tuple[str, str, str]] = []
    if menu_bar is not None:
        for action in menu_bar.actions():
            submenu = action.menu()
            if isinstance(submenu, QMenu):
                _collect(submenu, _plain(action.text()), found)
    if window is None:
        return found
    strip = getattr(window, "tools", None)
    listed = strip.tools() if strip is not None and hasattr(strip, "tools") else {}
    for tool in listed.values():
        if tool.shortcut:
            found.append((strip_title(), _plain(str(tool.title)), _native(tool.shortcut)))
    for sequence, title in WINDOW_KEYS:
        found.append((tr("Fenster"), str(title), _native(sequence)))
    found.extend(_drawing_keys())
    return found


def _drawing_keys() -> list[tuple[str, str, str]]:
    """Die Tasten des Zeichenmodus — vierte Quelle (§30.1).

    **Warum sie nicht über das Fenster kommen.** Der Editor ist ein Dialog,
    seine ``QShortcut`` hängen am ``SketchPanel``, und das Fenster kennt sie
    nicht. Die Prüfung gegen die Fenstertasten sah an dieser Grenze nichts
    mehr: Fünf von fünfzehn standen in der Übersicht, die generischen — es
    fehlten genau die zum Zeichnen. Wer wissen wollte, wie man eine Linie
    zeichnet, fand es allein im Tooltip des Knopfes.

    Sie stehen in einer eigenen Gruppe, weil sie nur im Zeichenmodus gelten.
    Eine Taste, die woanders nichts tut, unter „Fenster" zu führen, wäre eine
    Zusage, die die Anwendung nicht hält.
    """
    from app.ui.sketch_editor import ACTION_KEYS, PLANE_KEYS, TOOL_KEYS, VIEW_KEYS

    group = tr("Zeichnen")
    #: Was die Taste tut, in derselben Sprache wie die Knöpfe daneben.
    #:
    #: **Bestehende Texte, keine neuen.** Jeder dieser Sätze steht schon in den
    #: fünf Katalogen, weil der Editor ihn an seinen Knöpfen und in der
    #: Ebenenwahl führt. Fünfzehn neue Message-IDs hätten fünf Kataloge
    #: nachzuziehen verlangt — und dieselben Wörter zweimal übersetzt.
    titles: dict[str, TranslatableText] = {
        "select": _("Auswählen"),
        "line": _("Linie"),
        "circle": _("Kreis"),
        "arc": _("Bogen"),
        "point": _("Punkt"),
        "spline": _("Spline"),
        "trim": _("Trimmen"),
        "rectangle": _("Rechteck"),
        "distance": _("Abstand"),
        "offset": _("Versetzen"),
        "construction": _("Hilfsgeometrie"),
        "fit": _("Alles einpassen"),
        "plane:xy": _("Draufsicht (XY) — liegend"),
        "plane:xz": _("Vorderansicht (XZ) — stehend, von vorn"),
        "plane:yz": _("Seitenansicht (YZ) — stehend, von der Seite"),
    }
    found: list[tuple[str, str, str]] = []
    for source in (TOOL_KEYS, ACTION_KEYS, VIEW_KEYS, PLANE_KEYS):
        for name, sequence in source.items():
            title = titles.get(name)
            if title is not None:
                found.append((group, str(title), _native(sequence)))
    return found


def _native(sequence: str) -> str:
    """Eine Taste, wie sie auf der Tastatur heißt: „Strg+Z", nicht „Ctrl+Z"."""
    return QKeySequence(sequence).toString(QKeySequence.SequenceFormat.NativeText)


def _collect(menu: QMenu, group: str, found: list[tuple[str, str, str]]) -> None:
    """Sammelt ein Menü und seine Untermenüs unter derselben Gruppe."""
    for action in menu.actions():
        submenu = action.menu()
        if isinstance(submenu, QMenu):
            _collect(submenu, group, found)
            continue
        sequence = action.shortcut()
        if sequence.isEmpty():
            continue
        # ``NativeText`` schreibt die Taste so, wie sie auf der Tastatur heißt
        # und im Menü daneben steht: „Strg+Z", nicht „Ctrl+Z". Vorher stand hier
        # der rohe Deklarationstext, und damit sprach die Übersicht englisch,
        # während das Menü deutsch sprach.
        key = sequence.toString(QKeySequence.SequenceFormat.NativeText)
        found.append((group, _plain(action.text()), key))


def _plain(text: str) -> str:
    """Ein Beschriftungstext ohne Qt-Zutaten: kein „&", kein „…"."""
    return text.replace("&", "").removesuffix("…").strip().removesuffix(" …").strip()


class ShortcutsWindow(QDialog):
    """Alle belegten Tasten, nach Gruppen."""

    def __init__(
        self,
        menu_bar: QMenuBar | None,
        parent: QWidget | None = None,
        palette_key: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Tastenkürzel"))
        self.resize(520, 620)

        # Ein Suchfeld, denn die Liste ist über sechzig Zeilen lang. Die
        # eingebaute Tipp-Suche des Baums springt nur auf Zeilenanfänge der
        # ersten Spalte — wer nach einer *Taste* sucht, findet damit nichts.
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Suchen — Befehl oder Taste"))
        self.search.setAccessibleName(tr("Tastenkürzel durchsuchen"))
        self.search.textChanged.connect(self._refilter)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("Befehl"), tr("Taste")])
        # **Ein Baum und keine Einrückung.** Die Gruppen standen als eigene
        # Zeilen daneben, und die Zugehörigkeit bestand aus vier Leerzeichen im
        # Text — für einen Vorleser eine flache Liste, in der die Gruppe
        # nirgends steht. Jetzt sind die Befehle Kinder ihrer Gruppe: die
        # Einrückung übernimmt Qt, die Struktur steht im Zugänglichkeitsbaum,
        # und einklappen geht auch.
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)

        # Eine Gruppe, zwei Quellen: Die Werkzeugzeile heißt „Ansicht" wie das
        # Menü daneben (``strip_title``), und nacheinander gesammelt gab das
        # zwei Überschriften desselben Namens. Gemerkt statt verglichen — die
        # Reihenfolge bleibt die der Menüleiste, die Gruppe steht einmal da.
        headings: dict[str, QTreeWidgetItem] = {}
        for group, title, shortcut in entries(menu_bar, parent):
            heading = headings.get(group)
            if heading is None:
                heading = QTreeWidgetItem([group, ""])
                font = heading.font(0)
                font.setBold(True)
                heading.setFont(0, font)
                heading.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tree.addTopLevelItem(heading)
                headings[group] = heading
            heading.addChild(QTreeWidgetItem([title, shortcut]))
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)

        # Das Kürzel kommt von der Aktion selbst. Hier stand „Strg+G", und das
        # öffnet „Modell erzeugen" — eine Übersicht über Tastenkürzel, die ein
        # falsches nennt, ist schlimmer als keine.
        note = QLabel(
            tr("Alles ist außerdem über die Befehlspalette erreichbar.")
            + (f" — {palette_key}" if palette_key else ""),
            self,
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.tree, stretch=1)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _refilter(self) -> None:
        """Blendet aus, was nicht passt — über Befehl **und** Taste.

        Eine Gruppe, von der nichts übrig ist, geht mit: eine Überschrift ohne
        Zeilen darunter sieht aus wie ein Treffer, der nichts sagt.
        """
        query = self.search.text().strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            heading = self.tree.topLevelItem(index)
            if heading is None:
                continue
            left = 0
            for row in range(heading.childCount()):
                # Unterhalb von ``childCount`` gibt es jedes Kind. Ob die Stubs
                # das auch sagen, wechselt: Die Version aus `constraints.txt`
                # gibt ``QTreeWidgetItem`` zurück, die neueste
                # ``QTreeWidgetItem | None`` — der wöchentliche Lauf gegen die
                # neuesten Versionen meldete hier zwei ``union-attr``. Ein
                # ``if child is None`` gilt der einen als unerreichbar
                # (``warn_unreachable``), ein ``type: ignore`` der anderen als
                # unbenutzt. Das ``or continue`` ist wahr für beide: eine
                # Prüfung auf den falschen Wert, die keinen toten Zweig
                # aufmacht.
                child = heading.child(row) or None
                if child is None:  # pragma: no cover - hängt an der Stub-Version
                    continue
                haystack = f"{child.text(0)} {child.text(1)}".casefold()
                hidden = bool(query) and query not in haystack
                child.setHidden(hidden)
                left += not hidden
            heading.setHidden(not left)
