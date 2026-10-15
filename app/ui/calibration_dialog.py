"""Gemessene Werte eines Materials eintragen (Bauplan §28.3).

Schritt zwei von dreien: den Prüfkörper drucken, ihn messen, und die Zahlen
kommen hier hinein. Herausgelöst aus ``dialogs.py``, als der Dialog seine
Rückseite bekam (FD-13): vorn nur, was der Toleranz-Testkörper liefert.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge import calibration, profiles
from app.core.types import Profile
from app.i18n import tr
from app.ui.dialogs import align_to_the_front
from app.ui.fine_length_spin import FineLengthSpin
from app.ui.labels import LengthSpin, NumberSpin, length, printer_title, wheel_needs_focus
from app.ui.leash import weak_slot
from app.ui.panels import collapsible
from app.ui.style import (
    NORMAL,
    SPACE,
    WIDE,
    ContentFitIntent,
    ContentHeight,
    DialogScrollArea,
    make_primary,
    set_level,
)

#: Was der Toleranz-Testkörper liefert — die Werte vorn (§2.4). Elefantenfuß
#: und Schwindung misst man an anderen Proben, sie stehen hinten.
FRONT_FIELDS = ("clearance", "press", "hole_compensation")


class CalibrationDialog(QDialog):
    """Gemessene Werte eintragen (Bauplan §28.3).

    Sie landen im Materialprofil, nicht in einem Modell — und weil Toleranzen
    im Stapel Verweise sind (§12), folgt danach jedes bestehende Projekt. Der
    Satz über dem ersten Feld sagt das, denn es ist der Teil, der Leute
    überrascht; woher die Werte kommen, steht in seiner Kurzhilfe.

    **Vorn steht, was der Prüfkörper liefert** (FD-13, E5): Spiel, Übermaß
    und Lochkorrektur. Elefantenfuß, Schwindung, Mindestwand und Überhang
    stehen hinter *Weitere Einstellungen* — sie stammen aus anderen Proben,
    und Wand und Überhang gelten nur für die genannten Druckbedingungen.
    """

    def __init__(
        self, material: str, parent: QWidget | None = None, *, process: Profile | None = None
    ) -> None:
        super().__init__(parent)
        self.material = material
        self.process = process
        self._height = ContentHeight()
        self.setWindowTitle(tr("Material kalibrieren"))
        self.setMinimumWidth(420)

        current = profiles.material(material)
        # Der Titel, den der Kunde überall sonst liest — nicht die Kennung des
        # Profils —, und ein Stand, der sagt, ob gemessen wurde (FD-8).
        heading = QLabel(f"{current.title} — {calibration.state_text(current)}", self)
        heading.setWordWrap(True)
        set_level(heading, "section")
        # **Ein Satz, der Rest als Kurzhilfe** (FD-13): zwei Absätze über
        # neun Feldern las niemand, der nur sein Spiel nachtragen will.
        explanation = QLabel(
            tr(
                "Was Sie am gedruckten Toleranz-Testkörper messen, gilt danach für jedes "
                "Projekt mit diesem Material."
            ),
            self,
        )
        explanation.setWordWrap(True)
        more = tr(
            "Den Toleranz-Testkörper mit Zapfen und Bohrungen in gestaffeltem Spiel finden "
            "Sie im Bausteinkatalog. Die Werte stehen im Materialprofil, nicht im Modell."
        )
        explanation.setToolTip(more)
        explanation.setAccessibleDescription(more)

        self.editors: dict[str, QDoubleSpinBox] = {}
        self.measured_fields: dict[str, QCheckBox] = {}
        self._original_values: dict[str, float] = {}
        self._edited_fields: set[str] = set()
        front = QFormLayout()
        back = QFormLayout()
        for form in (front, back):
            form.setSpacing(NORMAL)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        back.setContentsMargins(0, 0, 0, 0)
        for name, title, note in (
            (
                "clearance",
                tr("Spiel für Schiebesitz"),
                tr("Der Spalt, mit dem zwei Teile leicht ineinandergleiten."),
            ),
            (
                "press",
                tr("Übermaß für Presssitz"),
                tr("Wie fest ein Zapfen in seiner Bohrung sitzt. Negativ heißt Übergröße."),
            ),
            (
                "hole_compensation",
                tr("Lochkorrektur"),
                tr(
                    "Um so viel fallen gedruckte Bohrungen zu eng aus. Solidon gibt den Wert "
                    "jedem Durchmesser dazu."
                ),
            ),
            (
                "elephant_foot",
                tr("Elefantenfuß"),
                tr("So weit läuft die erste Schicht über die Kontur hinaus."),
            ),
            (
                "shrinkage",
                tr("Schwindung"),
                tr("So stark schrumpft ein Teil beim Abkühlen, in Prozent seiner Größe."),
            ),
        ):
            # Die Schwindung ist ein Anteil, kein Maß: „0,004" trug deshalb
            # als Einziges keine Einheit und sagte niemandem etwas. Als
            # Prozentwert liest sie sich — 0,4 % ist eine Zahl, die man aus
            # einem Datenblatt kennt.
            percent = name == "shrinkage"
            value = float(getattr(current, name))
            self._original_values[name] = value
            editor: QDoubleSpinBox
            if percent:
                editor = NumberSpin(self)
                editor.setDecimals(2)
                editor.setRange(-100.0, 500.0)
                editor.setSingleStep(0.1)
                editor.setSuffix(" %")
                editor.setValue(value * 100.0)
            else:
                # **Eine Länge spricht in der Anzeigeeinheit** (§19.3, FD-176),
                # mit einer Stelle mehr als üblich: Die dritte Stelle eines
                # Feinmaßes (0,075 mm) ist gemessen. Gespeichert wird in mm.
                length_editor = FineLengthSpin(self)
                length_editor.set_range_mm(-1.0, 5.0)
                length_editor.set_step_mm(0.01)
                length_editor.set_value_mm(value)
                editor = length_editor
            # Der Satz an beiden Hälften der Zeile und am Bildschirmleser (V3).
            editor.setAccessibleName(title)
            editor.setToolTip(note)
            editor.setAccessibleDescription(note)
            self.editors[name] = editor
            form = front if name in FRONT_FIELDS else back
            form.addRow(title, editor)
            caption = form.labelForField(editor)
            if caption is not None:
                caption.setToolTip(note)

        explanation_text = tr(
            "Nur aktivieren, wenn Sie die Probe gedruckt und geprüft haben. "
            "Der Überhangwinkel wird von der Senkrechten aus gemessen. "
            "Ohne Auswahl bleiben gespeicherte Messwerte unverändert."
        )
        # Der Haken ist die Beschriftung der Zeile und heißt wie der Wert: So
        # steht er in der Spalte der übrigen, statt die Felder der Rückseite
        # hinter eine zweite Kante zu schieben. Vorgelesen wird der ganze Satz.
        for name, short, title, suffix, maximum in (
            ("minimum_wall", tr("Mindestwand"), tr("Mindestwand übernehmen"), " mm", 50.0),
            (
                "overhang_angle",
                tr("Überhangwinkel"),
                tr("Überhangwinkel übernehmen"),
                " °",
                89.9,
            ),
        ):
            checkbox = QCheckBox(short, self)
            checkbox.setAccessibleName(title)
            checkbox.setEnabled(process is not None)
            if name == "minimum_wall":
                # Die Wand ist eine Länge und folgt der Anzeigeeinheit (FD-176).
                wall = LengthSpin(self)
                wall.set_range_mm(0.01, maximum)
                editor = wall
            else:
                editor = NumberSpin(self)
                editor.setDecimals(2)
                editor.setRange(0.01, maximum)
                editor.setSuffix(suffix)
            # Der Haken heißt nach der Handlung, das Feld nach dem Wert — beide
            # „… übernehmen“ waren für den Vorleser eine Frage ohne Antwort.
            editor.setAccessibleName(short)
            value = getattr(current, name)
            applies = process is not None and process.has_process_calibration and value is not None
            default = (
                process.minimum_wall_thickness
                if name == "minimum_wall" and process is not None
                else process.overhang_limit_degrees
                if process is not None
                else 1.0
            )
            self._original_values[name] = float(value) if applies else default
            if isinstance(editor, LengthSpin):
                editor.set_value_mm(self._original_values[name])
            else:
                editor.setValue(self._original_values[name])
            editor.setEnabled(applies)
            checkbox.setChecked(applies)
            checkbox.toggled.connect(editor.setEnabled)
            for widget in (checkbox, editor):
                widget.setToolTip(explanation_text)
                widget.setAccessibleDescription(explanation_text)
            self.editors[name] = editor
            self.measured_fields[name] = checkbox
            back.addRow(checkbox, editor)

        # Erst nach der Vorbelegung beobachten: Qt rundet schon bei setValue.
        # Auch bewusstes Neueintippen derselben sichtbaren Zahl ist eine Änderung.
        for name, observed_editor in self.editors.items():
            observed_editor.valueChanged.connect(
                lambda _value, field=name: self._edited_fields.add(field)
            )
            line = observed_editor.lineEdit()
            if line is not None:
                line.textEdited.connect(lambda _text, field=name: self._edited_fields.add(field))

        process_note = QLabel(self)
        process_note.setWordWrap(True)
        if process is not None:
            printer = process.printer
            # Der Prozess des Verfahrens: Bei Resin gibt es keine Düse und
            # keine Bahn — dort sind es Schichthöhe und Bildpunkt (RM-071).
            # Längen in der Anzeigeeinheit wie die Felder darüber (FD-176).
            conditions = (
                tr("Schichthöhe")
                + f" {length(printer.layer_height)} · "
                + tr("Pixelgröße")
                + f" {length(printer.pixel_size)}"
                if printer.is_resin
                else tr("Düse")
                + f" {length(printer.nozzle_diameter)} · "
                + tr("Schichthöhe")
                + f" {length(printer.layer_height)} · "
                + tr("Bahnbreite")
                + f" {length(printer.extrusion_width)}"
            )
            process_note.setText(
                tr("Wand und Überhang gelten nur für diese Druckbedingungen:")
                + "\n"
                + f"{printer_title(printer)} · {current.title}\n"
                + conditions
            )
        else:
            process_note.setText(tr("Wählen Sie zuerst den Drucker der Probe im Projekt aus."))

        # Die Rückseite: eine Beschriftungskante mit vorn (RM-518), und was
        # Wand und Überhang bestimmt, steht bei ihnen.
        align_to_the_front(front, back)
        rest = QWidget(self)
        rest_layout = QVBoxLayout(rest)
        rest_layout.setContentsMargins(0, 0, 0, 0)
        rest_layout.setSpacing(NORMAL)
        rest_layout.addLayout(back)
        rest_layout.addWidget(process_note)
        self._more = collapsible(
            tr("Weitere Einstellungen"),
            rest,
            open_now=False,
            contents=tr("Elefantenfuß, Schwindung, Mindestwand und Überhangwinkel"),
            remember="calibration.more",
        )
        flap = self._more.findChild(QToolButton, "sectionHeading")
        if flap is not None:
            flap.toggled.connect(weak_slot(self, CalibrationDialog._fit_soon, "explicit"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        # Die gemessenen Werte zu übernehmen ist die Handlung dieses Fensters.
        # Den Akzent trug der Knopf schon — Qt vergibt ihn beim ersten
        # ``show()`` an den ersten autoDefault-Knopf —, aber ohne die
        # halbfette Schrift daneben (Regel 18).
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            make_primary(save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(NORMAL)
        layout.addWidget(heading)
        layout.addWidget(explanation)
        layout.addLayout(front)
        layout.addWidget(self._more)
        layout.addStretch(1)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(weak_slot(self, CalibrationDialog._fit_soon))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        outer.setSpacing(NORMAL)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(buttons)
        for measurement in self.editors.values():
            wheel_needs_focus(measurement)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        self._fit_soon("initial")

    def _fit_soon(self, intent: ContentFitIntent = "passive") -> None:
        QTimer.singleShot(0, self, weak_slot(self, CalibrationDialog._fit_content, intent))

    def _fit_content(self, intent: ContentFitIntent) -> None:
        """Misst nach dem Auslöser; manuelle Breite und Höhe bleiben maßgeblich."""
        self._height.fit(self, self._scroll, intent=intent)

    def measured(self) -> calibration.Calibration:
        """Was eingetragen wurde, als anwendungsfertige Kalibrierung.

        Die Schwindung steht im Feld als Prozentwert und im Profil als Anteil —
        umgerechnet wird hier, an der einen Stelle, an der beide sich treffen.

        **Nur was eingetragen wurde** (RM-589): Ein unberührtes Feld ist keine
        Messung. Es behält im Profil seinen Wert, aber nicht das Kennzeichen
        „gemessen“ — sonst bliebe nach einer reinen Spielmessung der
        Startwert des Elefantenfußes als gemessen stehen, und der Druckrat
        nähme dem Slicer seinen Einzug nicht ab. Wand und Überhang zählen, wenn
        ihr Haken steht.
        """
        return calibration.from_measurements(
            self.material,
            **{
                name: self._original_values[name]
                if name not in self._edited_fields
                else editor.value() / 100.0
                if name == "shrinkage"
                else editor.value_mm()
                if isinstance(editor, LengthSpin)
                else editor.value()
                for name, editor in self.editors.items()
                if (
                    self.measured_fields[name].isChecked()
                    if name in self.measured_fields
                    else name in self._edited_fields
                )
            },
        )
