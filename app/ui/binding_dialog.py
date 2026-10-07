"""Feste Zahlen an Projektmaße binden — die Wahl vor der einen Transaktion (RM-184).

Der Dateiaudit (§4) fand Vorlagen, deren Maße nur einen Teil des Modells
steuern: Am Puppenhaus folgten Wandring und Fenster der Hauslänge nicht, am
Schrank das Scharnier der Korpusbreite nicht. Der Kern findet die festen
Zahlen, die zu Projektmaßen passen (``scene.parameter_binding``); dieser
Dialog zeigt sie je Schritt mit ihren Vorschlägen. Vorgewählt ist nur, was
ohne Zweifel ist — eine Größe mit derselben Zahl wie genau ein Maß
(``BindingSpot.certain``), nie eine Lage. Was zwei Deutungen hat, wählt der
Kunde (Regel 21). Gebunden wird erst mit *Binden*, als eine Transaktion
(``History.bind_parameters``); Strg+Z nimmt alles zurück.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import REGISTRY
from app.core.scene.parameter_binding import BindingSpot
from app.core.types import Document, OpId
from app.i18n import tr
from app.ui.labels import length, step_number, wheel_needs_focus
from app.ui.style import SPACE, DialogScrollArea, fit_dialog_to_screen, make_primary


def spot_title(document: Document, spot: BindingSpot) -> str:
    """Wo die Zahl steht, in den Worten des Verlaufs: Schritt, Handlung, Feld."""
    operation = next((entry for entry in document.ops if entry.id == spot.op_id), None)
    if operation is None:
        return str(spot.op_id)
    spec = REGISTRY.get(operation.op)
    if spot.rectangle is not None:
        field = (
            tr("Rechteck {number} · Breite", number=spot.rectangle + 1)
            if spot.side == "width"
            else tr("Rechteck {number} · Höhe", number=spot.rectangle + 1)
        )
    else:
        field = next(
            (str(entry.title) for entry in spec.params.spec() if entry.name == spot.field),
            spot.field,
        )
    return tr(
        "Operation {number}: {operation} — {field}: {value}",
        number=step_number(document, spot.op_id),
        operation=str(spec.title),
        field=field,
        value=length(spot.value),
    )


class BindingDialog(QDialog):
    """Die passenden festen Zahlen, je eine Zeile: Haken, Ort, Ausdruck."""

    def __init__(
        self,
        document: Document,
        spots: Sequence[BindingSpot],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Zahlen an Maße binden"))
        self._spots = tuple(spots)
        self._checks: list[QCheckBox] = []
        self._choices: list[QComboBox] = []
        outer = QVBoxLayout(self)
        intro = QLabel(
            tr(
                "Diese festen Zahlen passen zu Projektmaßen. Gebunden folgen sie dem Maß, "
                "wenn Sie es ändern; Strg+Z nimmt die Bindung zurück."
            ),
            self,
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)
        sheet = QWidget(self)
        grid = QGridLayout(sheet)
        grid.setHorizontalSpacing(SPACE)
        for row, spot in enumerate(self._spots):
            title = spot_title(document, spot)
            check = QCheckBox(title, sheet)
            check.setChecked(spot.certain)
            check.toggled.connect(self._settle)
            choice = QComboBox(sheet)
            for option in spot.choices:
                choice.addItem(option.expression.removeprefix("="), option.expression)
            choice.setAccessibleName(tr("Ausdruck für {place}", place=title))
            wheel_needs_focus(choice)
            grid.addWidget(check, row, 0)
            grid.addWidget(choice, row, 1)
            self._checks.append(check)
            self._choices.append(choice)
        grid.setColumnStretch(0, 1)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(sheet)
        outer.addWidget(self._scroll, 1)
        self._count = QLabel(self)
        outer.addWidget(self._count)
        buttons = QDialogButtonBox(self)
        self.bind_button = QPushButton(tr("Binden"), self)
        buttons.addButton(self.bind_button, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = QPushButton(tr("Abbrechen"), self)
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        make_primary(self.bind_button)
        outer.addWidget(buttons)
        self._settle()

    def _settle(self) -> None:
        """Zahl der gewählten Zeilen und ob *Binden* etwas zu tun hat."""
        chosen = sum(check.isChecked() for check in self._checks)
        self._count.setText(
            tr("{count} von {total} Zahlen gewählt", count=chosen, total=len(self._checks))
        )
        self.bind_button.setEnabled(chosen > 0)
        reason = "" if chosen else tr("Wählen Sie mindestens eine Zahl.")
        self.bind_button.setToolTip(reason)
        self.bind_button.setAccessibleDescription(reason)

    def chosen(self) -> Mapping[tuple[OpId, str, int, str], str]:
        """Die gewählten Stellen mit ihrem Ausdruck — Schlüssel aus ``BindingSpot.key``."""
        return {
            spot.key: str(choice.currentData())
            for spot, check, choice in zip(self._spots, self._checks, self._choices, strict=True)
            if check.isChecked()
        }

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt gibt den Namen
        super().showEvent(event)
        fit_dialog_to_screen(self)
