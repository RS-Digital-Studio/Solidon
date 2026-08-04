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

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMenu,
    QMenuBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


def entries(menu_bar: QMenuBar | None) -> list[tuple[str, str, str]]:
    """Gruppe, Titel und Kürzel — aus der Menüleiste, so wie sie dasteht.

    Gelesen wurden vorher zwei Quellen: die Befehlstabelle des Fensters und das
    Register. Beide zusammen sind nicht alles. Die fünfzehn Tasten für
    Darstellung (``1`` bis ``6``) und Kameravorgaben (``Strg+0`` bis
    ``Strg+6``) gehen
    weder durch die eine noch durch die andere — sie standen in keiner
    Übersicht, obwohl sie im Menü daneben stehen.

    Die Menüleiste kennt sie alle, denn dort landet jede Aktion, die ein
    Mensch findet. Und sie liefert die Gruppe gleich mit: das Menü, in dem der
    Eintrag steht, ist die Gruppe, die der Nutzer sieht.

    Was kein Kürzel hat, steht nicht darin: eine Kürzelübersicht mit leeren
    Zeilen ist eine Liste aller Befehle, und die ist die Befehlspalette.
    """
    found: list[tuple[str, str, str]] = []
    if menu_bar is None:
        return found
    for action in menu_bar.actions():
        submenu = action.menu()
        if isinstance(submenu, QMenu):
            _collect(submenu, _plain(action.text()), found)
    return sorted(found)


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

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("Befehl"), tr("Taste")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)

        current = ""
        for group, title, shortcut in entries(menu_bar):
            if group != current:
                current = group
                heading = QTreeWidgetItem([group, ""])
                font = heading.font(0)
                font.setBold(True)
                heading.setFont(0, font)
                heading.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tree.addTopLevelItem(heading)
            self.tree.addTopLevelItem(QTreeWidgetItem([f"    {title}", shortcut]))
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
        layout.addWidget(self.tree, stretch=1)
        layout.addWidget(note)
        layout.addWidget(buttons)
