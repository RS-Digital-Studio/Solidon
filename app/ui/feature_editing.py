"""Gemeinsamer Vorderseiten- und Hilfetextvertrag der Merkmalbearbeitung."""

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QPushButton

from app.i18n import tr
from app.ui.style import make_primary

if TYPE_CHECKING:
    from app.ui.op_dialog import ValueField
    from app.ui.panels import FeaturePanel


def advanced_fields(action: Any, coordinates: frozenset[str] = frozenset()) -> frozenset[str]:
    """Die Bohrung zeigt Zielmaß und gemessene Tiefe, ihre Feinheiten stehen dahinter.

    Der Kern holt einen belegten Einlauf ausdrücklich nach vorn. Damit stehen
    höchstens drei Fachfelder da; der separate Sammelhaken ist das vierte.
    Andere Handlungen behalten ihre bestehende Zuordnung der Koordinaten.
    """
    if action.op != "resize_hole":
        return coordinates
    return coordinates | frozenset(
        str(field.name)
        for field in action.fields
        if getattr(field, "placement", "front") == "advanced"
        and not (field.name == "depth" and field.measurement is not None)
    )


def configure_scope(scope: QCheckBox, count: int) -> None:
    """Der Sammelauftrag wird im Bild und rechts mit denselben Worten erklärt."""
    scope.setText(tr("Auf alle {count} gleichartigen anwenden").format(count=count))
    scope.setAccessibleName(scope.text())
    hint = tr(
        "Ändert alle {count} gleichartigen Merkmale dieses Körpers gemeinsam. "
        "Ein Strg+Z nimmt die gesamte Änderung zurück."
    ).format(count=count)
    scope.setToolTip(hint)
    scope.setAccessibleDescription(hint)


def explain_value_help(editor: ValueField) -> None:
    """Feldsatz, Ausdrucksgrammatik und Ablehnung bleiben am fokussierten Innenfeld.

    ValueField schreibt seinen aktuellen Ausdruck samt Grammatik zuerst;
    dieser anschließend gebundene Anschluss stellt die Bedeutung davor.
    """
    text = editor.text
    hint = editor.toolTip()
    current = text.toolTip()
    if hint and not current.startswith(f"{hint}\n"):
        text.setToolTip(f"{hint}\n{current}" if current else hint)
    reason = editor.hint.text() if not editor.toggle.isChecked() and editor.refusal() else ""
    description = "\n".join(part for part in (hint, reason) if part)
    for target in (editor.spin, editor.spin.lineEdit()):
        target.setToolTip(description)
        target.setAccessibleDescription(description)


class FeatureEditPriority(QObject):
    """Der vorhandene Bearbeitungsauftrag führt, auch während seiner Berechnung."""

    def __init__(self, panel: FeaturePanel, catalog: QPushButton) -> None:
        super().__init__(panel)
        self._catalog = catalog
        self._active: bool | None = None
        panel.editingOffered.connect(self.set_active)

    def set_active(self, active: bool) -> None:
        """Akzent und Schriftgewicht wechseln zusammen, ohne Fokusänderung."""
        if self._active is not active:
            self._active = active
            make_primary(self._catalog, leading=not active)
