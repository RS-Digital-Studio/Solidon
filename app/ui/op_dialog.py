"""Operationsdialoge, erzeugt aus dem Parameterschema (Bauplan §10, §2.4).

Gestufte Tiefe: die zwei bis drei Werte, die Leute wirklich ändern, stehen
vorn; Toleranzen und Auflösungen sitzen hinter „Weitere Einstellungen". Was
wohin gehört, kommt aus ``placement`` im Schema — ein Dialog kann also nicht
von der Operation abdriften, zu der er gehört.

Der Dialog lässt sich auf Werten statt auf den Vorgaben öffnen, und diese eine
Ergänzung bedient zwei Dinge, die verschieden aussehen und dasselbe sind: eine
angeklickte Fläche, die einträgt, wohin die Operation gehört (§18.5), und eine
Operation des Stapels, die zum Korrigieren wieder geöffnet wird (§15.4). Beides
ist „hier sind die Werte, frag danach" — ein zweiter Dialog für den zweiten
Fall wäre ein zweiter Ort, an dem sich ein Parameter vergessen lässt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import OperationSpec
from app.core.types import ParamSpec
from app.i18n import tr

#: Werte unterhalb dieser Größenordnung werden feiner angezeigt. Eine Toleranz
#: von 0,075 mm wurde bei zwei Nachkommastellen beim Öffnen des Dialogs zu 0,08
#: — eine stille Änderung an einer Zahl, die jemand gemessen hat.
_FINE_BELOW = 1.0

#: Abstand des Dialogs zu Rand und Oberkante des Viewports. Weit genug, dass er
#: als eigenes Fenster erkennbar bleibt, nah genug, dass er zur Ansicht gehört.
DIALOG_MARGIN = 16


def _decimals_for(entry: ParamSpec) -> int:
    """Wie fein ein Feld sein muss, damit sein Wertebereich hineinpasst (§11.2).

    Zwei Stellen genügen für Längen und Winkel; Toleranzen und Spiele leben
    unter einem Millimeter, und dort ist die zweite Stelle die letzte, die noch
    etwas unterscheidet.
    """
    bounds = [abs(value) for value in (entry.minimum, entry.maximum) if value]
    if bounds and max(bounds) <= _FINE_BELOW:
        return 3
    return 2


class OperationDialog(QDialog):
    """Ein Dialog für eine Operation, gebaut aus ihrem Schema."""

    valuesChanged = Signal()
    """Ein Wert hat sich geändert — die Live-Vorschau (§18.7) hört zu."""

    def __init__(
        self,
        spec: OperationSpec,
        objects: Mapping[str, str] | Sequence[str],
        parent: QWidget | None = None,
        values: Mapping[str, Any] | None = None,
        sources: Mapping[str, str] | None = None,
        parameter_values: Mapping[str, float] | None = None,
        features: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        self._editors: dict[str, QWidget] = {}
        self._parameter_values = dict(parameter_values or {})
        """Aufgelöste Projektparameter — der Skizzeneditor rechnet
        Maßausdrücke damit (§13, §30.1)."""
        given = dict(values or {})
        # Der Dialog spricht in Namen, das Dokument in Kennungen. Wer nur eine
        # Liste übergibt, bekommt die Kennungen zu sehen.
        names = dict(objects) if isinstance(objects, Mapping) else {key: key for key in objects}
        # Quellen sind keine Objekte. Sie standen hier trotzdem in derselben
        # Liste — wer „Modell laden" im Verlauf wieder öffnete, bekam eine
        # Auswahl aus Körpern angeboten, wo eine Datei gemeint war.
        self._sources = dict(sources or {})
        self._features = dict(features or {})
        """Die erkannten Merkmale des gewählten Körpers, Kennung auf
        Beschriftung — dieselbe, die im Objektbaum und über dem Modell steht."""

        front = QFormLayout()
        advanced = QFormLayout()
        for entry in spec.params.spec():
            editor = self._editor_for(entry, names, given.get(entry.name))
            self._editors[entry.name] = editor
            self._watch(editor)
            label = f"{entry.title}"
            if entry.unit:
                label = f"{label} [{entry.unit}]"
            # Ein eingetragener Wert gehört vor den Nutzer, auch wenn das Schema ihn
            # nach hinten legt: er ist der, der gerade entschieden wurde.
            target = front if entry.placement == "front" or entry.name in given else advanced
            target.addRow(label, editor)
            if entry.doc:
                editor.setToolTip(str(entry.doc))

        layout = QVBoxLayout(self)
        if spec.doc:
            description = QLabel(str(spec.doc), self)
            description.setWordWrap(True)
            layout.addWidget(description)
        layout.addLayout(front)

        if advanced.rowCount():
            # Eine ankreuzbare Gruppe graut ihre Felder aus, statt sie
            # wegzuklappen — die gestufte Tiefe aus §2.4 war damit gedacht und
            # nicht gebaut: die hinteren Werte standen weiter da, nur grau, und
            # das Häkchen las sich wie ein Schalter, der etwas bewirkt.
            inner = QWidget(self)
            inner.setLayout(advanced)
            inner.setVisible(False)
            self.advanced = QToolButton(self)
            self.advanced.setText(tr("Weitere Einstellungen"))
            self.advanced.setCheckable(True)
            self.advanced.setAutoRaise(True)
            self.advanced.setArrowType(Qt.ArrowType.RightArrow)
            self.advanced.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

            def unfold(open_now: bool, inner: QWidget = inner) -> None:
                inner.setVisible(open_now)
                self.advanced.setArrowType(
                    Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow
                )
                self.adjustSize()

            self.advanced.toggled.connect(unfold)
            layout.addWidget(self.advanced)
            layout.addWidget(inner)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Der Knopf benennt die Handlung: „Bohrung setzen" statt „OK". Was
        # gleich passiert, steht damit dort, wo entschieden wird — der
        # Fenstertitel ist beim Klicken nicht mehr im Blick.
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(str(spec.title))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _watch(self, editor: QWidget) -> None:
        """Verbindet das Änderungssignal des Editors mit ``valuesChanged``.

        Je Editorsorte eines — die Vorschau will von jedem Feld wissen, nicht
        nur von den Zahlen.
        """
        from app.ui.sketch_editor import SketchField

        if isinstance(editor, SketchField):
            editor.changed.connect(self.valuesChanged)
        elif isinstance(editor, QCheckBox):
            editor.toggled.connect(self.valuesChanged)
        elif isinstance(editor, QSpinBox | QDoubleSpinBox):
            editor.valueChanged.connect(self.valuesChanged)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(self.valuesChanged)
        elif isinstance(editor, QLineEdit):
            editor.textChanged.connect(self.valuesChanged)

    def _editor_for(
        self, entry: ParamSpec, objects: Mapping[str, str], given: Any = None
    ) -> QWidget:
        """Ein Editor. ``given`` schlägt die Vorgabe des Schemas, wo es gesetzt
        ist.
        """
        start = entry.default if given is None else given
        if entry.kind == "bool":
            editor = QCheckBox(self)
            editor.setChecked(bool(start))
            return editor
        if entry.kind == "int":
            spin = QSpinBox(self)
            spin.setMinimum(int(entry.minimum) if entry.minimum is not None else -1_000_000)
            spin.setMaximum(int(entry.maximum) if entry.maximum is not None else 1_000_000)
            if start is not None:
                spin.setValue(int(start))
            return spin
        if entry.kind == "float":
            number = QDoubleSpinBox(self)
            number.setDecimals(_decimals_for(entry))
            number.setMinimum(entry.minimum if entry.minimum is not None else -1_000_000.0)
            number.setMaximum(entry.maximum if entry.maximum is not None else 1_000_000.0)
            if start is not None:
                number.setValue(float(start))
            return number
        if entry.kind == "enum" or entry.choices:
            combo = QComboBox(self)
            combo.addItems(list(entry.choices))
            if start is not None and start in entry.choices:
                combo.setCurrentText(str(start))
            return combo
        if entry.kind == "sketch":
            # §30.1 Stufe zwei: der Text ist ein Speicherformat, keine
            # Eingabe — gezeichnet wird im Editor, das Feld fasst zusammen.
            from app.ui.sketch_editor import SketchField

            return SketchField(str(start or ""), self._parameter_values, self)
        if entry.kind == "feature":
            # Aus demselben Grund wie unten eine Liste, nur mit dem schärferen
            # Fall: „face_2" tippt niemand, der es nicht vorher irgendwo
            # abgelesen hat — und abzulesen war es nur im Objektbaum, wo die
            # Namen bei Standardbreite abgeschnitten sind. Der doc-Satz dieses
            # Parameters versprach das Anklicken im Fenster; das Feld daneben
            # war leer und blieb es.
            combo = QComboBox(self)
            combo.addItem(tr("— keines —"), "")
            for identifier, label in self._features.items():
                combo.addItem(label, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        if entry.kind in ("object", "source"):
            # Der Name steht da, die Kennung reist mit. Ein frei beschreibbares
            # Feld war hier ein Weg, „obj_12" falsch zu tippen — und der Baum
            # nebenan zeigt ohnehin Namen, keine Nummern.
            choices = self._sources if entry.kind == "source" else objects
            combo = QComboBox(self)
            for identifier, name in choices.items():
                combo.addItem(name, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    # Ein Wert, den die Liste nicht kennt, wird gezeigt statt
                    # ersetzt: eine Datei aus einem Projekt, dessen Quellen
                    # hier gerade nicht vorliegen, darf nicht stillschweigend
                    # zu einer anderen werden.
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        line = QLineEdit(self)
        if start:
            line.setText(str(start))
        return line

    def take_feature(self, feature_id: str, label: str) -> bool:
        """Trägt ein angeklicktes Merkmal ein, wenn der Dialog eines erwartet.

        Der ``doc``-Satz dieses Parameters versprach das seit je — „wird beim
        Anklicken im Fenster eingetragen" —, und einzulösen war es nicht: der
        Dialog sperrte das Fenster, es gab also kein Anklicken, solange er
        offen war. Seit er das nicht mehr tut, ist der kürzeste Weg zu einer
        Fläche wieder der, auf sie zu zeigen.

        Gibt zurück, ob etwas gesetzt wurde — der Aufrufer weiß sonst nicht, ob
        sein Klick angekommen ist.
        """
        taken = False
        for entry in self.spec.params.spec():
            if entry.kind != "feature":
                continue
            editor = self._editors.get(entry.name)
            if not isinstance(editor, QComboBox):
                continue
            index = editor.findData(feature_id)
            if index < 0:
                editor.addItem(label or feature_id, feature_id)
                index = editor.count() - 1
            editor.setCurrentIndex(index)
            taken = True
        return taken

    def take_point(self, point: tuple[float, float, float]) -> bool:
        """Trägt einen angeklickten Punkt in die Positionsfelder ein.

        Dieselbe Sache wie oben für die Koordinaten: ein Dialog, der nach
        Position X, Y und Z fragt, öffnete auf 0,00 — und der Ursprung liegt
        bei einer geladenen Platte an einer Ecke. Wer dort bohrte, kratzte
        einen Span von der Kante, und niemand sagte etwas dazu.

        §11 bleibt gewahrt: die Zahl ist die Wahrheit, das Zeigen nur die
        bequeme Eingabe. Was der Klick einträgt, steht danach lesbar da und
        lässt sich ändern.
        """
        fields = {entry.name for entry in self.spec.params.spec()}
        if not {"x", "y", "z"} <= fields:
            return False
        for name, value in zip(("x", "y", "z"), point, strict=True):
            editor = self._editors.get(name)
            if isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(value))
        return True

    def place_beside(self, anchor: QWidget | None) -> None:
        """Setzt den Dialog an den Rand statt in die Bildmitte.

        Ein Operationsdialog trägt eine Live-Vorschau (§18.7): was er zeigt,
        entsteht während des Tippens im Viewport. Qt setzt Dialoge mittig zum
        Elternfenster — und die Mitte des Fensters ist genau die Stelle, an der
        die Kamera das Modell zeigt. Die Vorschau entstand hinter dem Dialog,
        der sie ausgelöst hat.

        Angelegt wird oben rechts im übergebenen Bereich, mit demselben Abstand
        zu Rand und Kante. Passt der Dialog dort nicht, bleibt er, wo Qt ihn
        hingesetzt hat — ein Dialog außerhalb des Bildschirms wäre schlimmer
        als einer in der Mitte.
        """
        if anchor is None:
            return
        area = anchor.rect()
        size = self.sizeHint()
        if size.width() + 2 * DIALOG_MARGIN > area.width():
            return
        corner = anchor.mapToGlobal(area.topRight())
        self.move(corner.x() - size.width() - DIALOG_MARGIN, corner.y() + DIALOG_MARGIN)

    def values(self) -> dict[str, Any]:
        """Was der Nutzer eingetragen hat, fertig für die Operationsparameter."""
        from app.ui.sketch_editor import SketchField

        collected: dict[str, Any] = {}
        for entry in self.spec.params.spec():
            editor = self._editors[entry.name]
            if isinstance(editor, SketchField):
                collected[entry.name] = editor.text()
            elif isinstance(editor, QCheckBox):
                collected[entry.name] = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                collected[entry.name] = editor.value()
            elif isinstance(editor, QDoubleSpinBox):
                collected[entry.name] = float(editor.value())
            elif isinstance(editor, QComboBox):
                # Objekt- und Quellenwähler tragen die Kennung als Daten, die
                # übrigen Aufklappmenüs sind ihr eigener Wert.
                data = editor.currentData()
                collected[entry.name] = editor.currentText() if data is None else str(data)
            elif isinstance(editor, QLineEdit):
                collected[entry.name] = editor.text()
        return collected
