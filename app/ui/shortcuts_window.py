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
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import CATEGORIES, REGISTRY
from app.i18n import tr


def entries(commands: dict[str, tuple[str, str, object]]) -> list[tuple[str, str, str]]:
    """Gruppe, Titel und Kürzel — aus beiden Quellen, ohne Dubletten.

    Was kein Kürzel hat, steht nicht darin: eine Kürzelübersicht mit leeren
    Zeilen ist eine Liste aller Befehle, und die ist die Befehlspalette.
    """
    found: list[tuple[str, str, str]] = []
    for key, (title, shortcut, _slot) in commands.items():
        if shortcut:
            group = key.split(".", 1)[0]
            found.append((_group_title(group), str(title), str(shortcut)))
    for spec in REGISTRY.all():
        if spec.shortcut:
            found.append(
                (str(CATEGORIES.get(spec.category, spec.category)), str(spec.title), spec.shortcut)
            )
    return sorted(found)


def _group_title(group: str) -> str:
    """Der Name einer Befehlsgruppe des Fensters."""
    return {
        "file": tr("Datei"),
        "edit": tr("Bearbeiten"),
        "view": tr("Ansicht"),
        "tool": tr("Werkzeuge"),
        "help": tr("Hilfe"),
    }.get(group, group)


class ShortcutsWindow(QDialog):
    """Alle belegten Tasten, nach Gruppen."""

    def __init__(
        self, commands: dict[str, tuple[str, str, object]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Tastenkürzel"))
        self.resize(520, 620)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("Befehl"), tr("Taste")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)

        current = ""
        for group, title, shortcut in entries(commands):
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

        note = QLabel(tr("Alles ist außerdem über die Befehlspalette erreichbar — Strg+G."), self)
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree, stretch=1)
        layout.addWidget(note)
        layout.addWidget(buttons)
