"""Ein Projektmaß von Hand anlegen oder ändern (Bauplan §13, §2.3).

Herausgelöst aus ``dialogs.py`` (Codestruktur, Regel 6): Der Dialog bekam
Ablehnung am Feld, Zolleingabe und Feldsätze, und ``dialogs.py`` nimmt keine
neue Definition mehr auf. ``dialogs.ParameterDialog`` bleibt als Name stehen.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Collection, Mapping
from contextlib import suppress
from itertools import pairwise
from typing import Any, Final

from PySide6.QtCore import QLocale, Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core import expressions, guides
from app.core.errors import AppError
from app.core.units import decimals_for, from_mm, to_mm
from app.i18n import tr
from app.ui.form_fields import explain_row, name_rows
from app.ui.labels import (
    NumberSpin,
    display_unit,
    fill_parameter_units,
    localised_value,
    wheel_needs_focus,
)
from app.ui.leash import weak_slot
from app.ui.parameter_length import LENGTH_CODE, is_length
from app.ui.style import (
    NORMAL,
    SPACE,
    TIGHT,
    WIDE,
    ContentFitIntent,
    ContentHeight,
    DialogScrollArea,
    make_primary,
    set_role,
)

#: Formelsymbole sind keine übersetzbaren Wörter. Als Namen statt als Literale
#: in ``setText`` erkennt auch die Oberflächenprüfung, dass hier kein deutscher
#: Text am Katalog vorbeiläuft.
FORMULA_MARKER = "fx"
PARAMETER_MARKER = expressions.REFERENCE_PREFIX

#: Wie ein Umlaut in einem Namen aussieht, den ``@name`` lesen kann — dieselbe
#: Umschrift wie bei Dateinamen (``export.writer.safe_name``).
_SPELLED_OUT: Final = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}


def shown_number(value_mm: float, code: str) -> float:
    """Eine gespeicherte Zahl, wie das Feld sie zeigt — eine Länge in der Anzeigeeinheit."""
    return from_mm(value_mm, display_unit()) if is_length(code) else value_mm


def stored_number(shown: float, code: str) -> float:
    """Eine getippte Zahl, wie das Dokument sie speichert — eine Länge in Millimetern.

    Ein Feld, das niemand berührt hat, fragt vorher den gespeicherten Wert
    (``ParameterDialog._stored``, ``recipe_dialog._ParamRow._stored``) — sonst
    käme aus 40 mm über 1,5748 in 39,99992 mm zurück.
    """
    return to_mm(shown, display_unit()) if is_length(code) else shown


def number_places(code: str, least: int) -> int:
    """Wie viele Stellen ein Feld für diese Bedeutung braucht — Zoll braucht mehr."""
    if is_length(code):
        return max(least, decimals_for(display_unit()))
    return least


def usable_name(name: str) -> bool:
    """Ob sich der Name in einem Ausdruck als ``@name`` schreiben lässt."""
    try:
        expressions.check(f"{PARAMETER_MARKER}{name}")
    except AppError:
        return False
    return True


def suggested_name(typed: str, taken: Collection[str]) -> str | None:
    """Ein freier, schreibbarer Name aus dem Getippten — der Weg aus der Ablehnung.

    „Breite Platte“ wird ``Breite_Platte``, „Höhe“ ``Hoehe``, „3fach“
    ``_3fach``; ein vergebener Name bekommt ``_2``, ``_3`` angehängt. Ohne
    einen einzigen lesbaren Buchstaben gibt es keinen Vorschlag.
    """
    spelled = "".join(_SPELLED_OUT.get(character, character) for character in typed.strip())
    plain = unicodedata.normalize("NFKD", spelled).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", plain).strip("_")
    if not stem:
        return None
    if stem[0].isdigit():
        stem = f"_{stem}"
    candidate, number = stem, 2
    while candidate in taken or not usable_name(candidate):
        if number > 99:
            return None
        candidate, number = f"{stem}_{number}", number + 1
    return candidate


class _ParameterValueSpin(NumberSpin):
    """Projektwerte mit mindestens zwei, aber ohne unehrliche Nullstellen.

    ``QDoubleSpinBox`` zeigt immer genau ``decimals`` Stellen. Drei sind für
    ein Feinmaß wie 0,075 nötig, lassen eine einfache Zwölf aber als 12,000
    erscheinen. Hier bleibt die dritte Stelle nur stehen, wenn sie etwas sagt:
    12,00 · 12,50 · 0,075.
    """

    def textFromValue(self, value: float) -> str:  # noqa: N802 - Qt gibt den Namen
        text = super().textFromValue(value)
        separator = QLocale().decimalPoint()
        head, found, fraction = text.partition(separator)
        if not found:
            return f"{text}{separator}00"
        fraction = fraction.rstrip("0").ljust(2, "0")
        return f"{head}{separator}{fraction}"


class ParameterDialog(QDialog):
    """Ein Projektmaß von Hand anlegen **oder ändern** (Bauplan §13, §2.3).

    Anlegen konnte bisher nur der Agent über sein Werkzeug. §2.3 verspricht
    aber, dass ohne KI alles außer dem Chat funktioniert — und Weg 2 lebt von
    benannten Maßen. Die Leiste ändert Werte; das hier ist das Gegenstück,
    das den Namen vergibt.

    **Und derselbe Dialog ändert, was er angelegt hat.** Grenzen waren
    anlegbar und nie änderbar: Die Leiste liest ``minimum``/``maximum`` als
    Spinbox-Grenzen und bietet nichts zum Bearbeiten an, und ein zweiter Anlauf
    über *Parameter anlegen …* endete an „Diesen Namen gibt es schon". Wer eine
    Obergrenze auf 100 gesetzt hatte und später 150 brauchte, saß fest: Das
    Feld klemmte ohne Erklärung, und einen dritten Weg gab es nicht — eine
    Sackgasse (§2.1). Aufgerufen wird die Änderung aus dem Kontextmenü der
    Zeile in der Parameterleiste; zurück ins Dokument geht sie als
    Transaktion, also rücknehmbar (§15.5).

    **Der Name bleibt beim Ändern stehen.** Er ist der Schlüssel, unter dem
    jeder Ausdruck und jede Operation ihn nennt (``@breite``); ihn hier
    umzuschreiben, hieße, all diese Verweise mitzuziehen — das ist eine eigene
    Handlung und nicht die, um die es hier geht. Abgelehnt wird er trotzdem
    nicht mehr: Der eigene Name ist beim Ändern kein vergebener.

    Geprüft wird inline, nicht modal: ein Fehlerdialog auf einem Dialog ist
    eine Sackgasse mit Vorgeschichte. Trägt das Ausdrucksfeld etwas, gehört
    der Wert dem Ausdruck — das Wertfeld sagt das, indem es sich abschaltet.
    """

    def __init__(
        self,
        parameters: Mapping[str, Any],
        parent: QWidget | None = None,
        existing: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._editing = existing is not None
        self._height = ContentHeight()
        self.setWindowTitle(tr("Parameter ändern") if self._editing else tr("Parameter anlegen"))
        self.setMinimumWidth(420)
        # Der eigene Name ist beim Ändern kein vergebener — sonst weist der
        # Dialog genau den Parameter ab, den er gerade bearbeitet.
        self._existing = set(parameters) - ({existing.name} if existing is not None else set())
        self._title = existing.title if existing is not None else None
        try:
            self._values: dict[str, float] = dict(expressions.resolve(parameters))
        except AppError:
            # Ein kaputter Bestandsausdruck ist nicht das Problem dieses
            # Dialogs — dann prüft erst das Anlegen den neuen Ausdruck.
            self._values = {}
        self._value: float = 0.0

        content = QWidget(self)
        explanation = QLabel(
            tr(
                "Ein Parameter ist ein benanntes Maß. Operationen und Skizzen "
                "verweisen mit @name darauf, und an der Zahl zu drehen baut "
                "das Modell neu."
            ),
            content,
        )
        explanation.setWordWrap(True)

        self.name_field = QLineEdit(content)
        self.name_field.setPlaceholderText(tr("zum Beispiel breite"))
        # **Eine Länge in der Anzeigeeinheit** (FD-125): Wer in Zoll arbeitet,
        # tippt Zoll; gespeichert wird in Millimetern (``stored_number``). Was im
        # Feld steht, gilt in der Einheit, die die Auswahl daneben nennt.
        code = str(existing.unit or "") if existing is not None else LENGTH_CODE
        self._given_code = code
        self.value_field = _ParameterValueSpin(content)
        self.value_field.setDecimals(number_places(code, 3))
        self.value_field.setRange(-100_000.0, 100_000.0)
        self.unit_field = QComboBox(content)
        fill_parameter_units(self.unit_field, code, display_unit())
        self.unit_field.setAccessibleName(tr("Einheit"))
        # Die Schreibseite der Grenzen (Gesamtreview B-15): Die Leiste liest
        # minimum/maximum seit je als Spinbox-Grenzen und fiel immer auf
        # ±100 000 zurück, weil keine Stelle der Anwendung sie je setzte.
        # Textfelder statt Spinboxen, weil „leer" hier ein Wert ist: keine
        # Grenze. Was aus Ausdrücken hinausläuft, meldet die Auswertung als
        # Befund — hier wird nur die Eingabe abgelehnt (§10).
        self.minimum_field = QLineEdit(content)
        self.minimum_field.setPlaceholderText(tr("optional — leer heißt: keine"))
        self.maximum_field = QLineEdit(content)
        self.maximum_field.setPlaceholderText(tr("optional — leer heißt: keine"))
        self.expression_field = QLineEdit(content)
        self.expression_field.setPlaceholderText(tr("zum Beispiel =@breite/2"))
        # Die Felder als Ziele im Wortschatz (``field:<feld>``), unter den
        # Namen der Felder eines Projektparameters (RM-737).
        for key, editor in (
            ("name", self.name_field),
            ("value", self.value_field),
            ("unit", self.unit_field),
            ("minimum", self.minimum_field),
            ("maximum", self.maximum_field),
            ("expression", self.expression_field),
        ):
            editor.setProperty(guides.TARGET_PROPERTY, f"field:{key}")

        # Die zwei sichtbaren Werkzeuge entsprechen dem Operationsdialog:
        # ``fx`` schaltet eine Formel ein, ``@`` nimmt einen vorhandenen Namen.
        # Wer CAD und Ausdruckssyntax nicht kennt, muss dadurch weder das
        # Gleichheitszeichen noch einen internen Parameternamen erraten.
        self.fx_button = QToolButton(content)
        self.fx_button.setText(FORMULA_MARKER)
        self.fx_button.setCheckable(True)
        self.fx_button.setAutoRaise(True)
        self.fx_button.setToolTip(
            tr("Statt einer festen Zahl rechnen lassen — zum Beispiel die halbe Breite.")
        )
        self.fx_button.setAccessibleName(tr("Parameterausdruck"))

        self.parameter_button = QToolButton(content)
        self.parameter_button.setText(PARAMETER_MARKER)
        self.parameter_button.setAutoRaise(True)
        self.parameter_button.setToolTip(tr("@name setzt einen Projektparameter ein."))
        self.parameter_button.setAccessibleName(tr("Parameter"))
        parameter_menu = QMenu(self.parameter_button)
        own_name = str(existing.name) if existing is not None else ""
        for name, parameter in parameters.items():
            if name == own_name:
                continue
            title = str(parameter.title or "").strip()
            label = f"@{name}" if not title or title == name else f"@{name} — {title}"
            action = parameter_menu.addAction(label)
            action.setData(name)
        parameter_menu.triggered.connect(
            weak_slot(self, ParameterDialog._insert_parameter, forward=True)
        )
        self.parameter_button.setMenu(parameter_menu)
        self.parameter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.parameter_button.setEnabled(not parameter_menu.isEmpty())

        value_row = QWidget(content)
        value_layout = QHBoxLayout(value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(NORMAL)
        value_layout.addWidget(self.value_field, 1)
        value_layout.addWidget(self.fx_button)

        self.expression_row = QWidget(content)
        expression_layout = QHBoxLayout(self.expression_row)
        expression_layout.setContentsMargins(0, 0, 0, 0)
        expression_layout.setSpacing(NORMAL)
        expression_layout.addWidget(self.expression_field, 1)
        expression_layout.addWidget(self.parameter_button)

        # **Der Ausdruck unter dem Wert, den er ersetzt.** *fx* in der
        # Wertzeile blendet ihn ein und sperrt die Zahl; er stand drei Zeilen
        # tiefer, unter Einheit und Grenzen.
        form = QFormLayout()
        form.setHorizontalSpacing(NORMAL)
        form.setVerticalSpacing(NORMAL)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.addRow(tr("Name"), self.name_field)
        # **Die Ablehnung des Namens steht am Namensfeld** (FD-155) — mit dem
        # Weg: ein freier Name aus dem Getippten als Knopf. Sie stand unter
        # „Weitere Einstellungen“, das Feld unmarkiert, und der Kunde suchte.
        # Der Knopf steht unter dem Satz, nicht daneben: Nebeneinander machten
        # beide die Feldspalte breiter als den Dialog, der Rollbereich wich zur
        # Seite und schnitt die Beschriftungen ab.
        self.name_refusal = QWidget(content)
        refusal_layout = QVBoxLayout(self.name_refusal)
        refusal_layout.setContentsMargins(0, 0, 0, 0)
        refusal_layout.setSpacing(TIGHT)
        self.name_note = QLabel(self.name_refusal)
        self.name_note.setWordWrap(True)
        refusal_layout.addWidget(self.name_note)
        self.name_suggestion = QPushButton(self.name_refusal)
        self.name_suggestion.clicked.connect(weak_slot(self, ParameterDialog._take_suggestion))
        refusal_layout.addWidget(self.name_suggestion, 0, Qt.AlignmentFlag.AlignLeft)
        self._suggested: str | None = None
        form.addRow(QLabel(content), self.name_refusal)
        form.addRow(tr("Wert"), value_row)
        form.addRow(tr("Ausdruck"), self.expression_row)
        form.addRow(tr("Einheit"), self.unit_field)
        self._form = form
        # **Vorn nur Name, Wert, Einheit** (§2.4, RM-359 F11). Die Grenzen
        # stehen hinter *Weitere Einstellungen*; offen, wenn das Maß schon
        # welche hat — sonst sähe ein Änderungsdialog aus, als gäbe es keine.
        # Erst hier: ``dialogs`` reicht diesen Dialog weiter, und ``panels``
        # liest ``dialogs`` — auf Modulebene schlösse sich der Kreis.
        from app.ui.dialogs import align_to_the_front
        from app.ui.panels import collapsible

        self._limits = QWidget(content)
        limits_form = QFormLayout(self._limits)
        limits_form.setContentsMargins(0, 0, 0, 0)
        limits_form.setHorizontalSpacing(NORMAL)
        limits_form.setVerticalSpacing(NORMAL)
        limits_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        limits_form.addRow(tr("Untergrenze"), self.minimum_field)
        limits_form.addRow(tr("Obergrenze"), self.maximum_field)
        # Eine Beschriftungskante für Wert und Grenzen (RM-518).
        align_to_the_front(form, limits_form)
        # Jedes Feld heißt wie seine Zeile (FD-94): Ohne Namen las ein
        # Vorleser „breite“ und „40,00“ statt „Name“ und „Wert“.
        name_rows(form, limits_form)
        # **Jedes Feld sagt, was es tut** (FD-11) — an beiden Hälften der Zeile
        # und am Vorleser. Wofür eine Grenze gut ist, musste man raten.
        name_sentence = (
            tr(
                "Der Name ist der Schlüssel, mit dem Ausdrücke und "
                "Operationen auf das Maß zeigen (@name). Zum Umbenennen "
                "legen Sie ein neues Maß an."
            )
            if existing is not None
            else tr("So heißt das Maß in Ausdrücken, etwa @breite.")
        )
        # Dieselben Sätze, mit denen der Agent die Grenzen kennt (``agent/tools``).
        below = tr("Kleinster Wert, den die Parameterleiste annimmt.")
        above = tr("Größter Wert, den die Parameterleiste annimmt.")
        self._name_sentence = str(name_sentence)
        for row_form, field, sentence in (
            (form, self.name_field, name_sentence),
            (form, value_row, tr("Mit dieser Zahl rechnet jede Operation, die das Maß nennt.")),
            (form, self.expression_row, tr("Rechnet den Wert aus anderen Maßen, etwa =@breite/2.")),
            (form, self.unit_field, tr("Ob das Maß eine Länge, ein Winkel oder eine Anzahl ist.")),
            (limits_form, self.minimum_field, below),
            (limits_form, self.maximum_field, above),
        ):
            explain_row(row_form, field, str(sentence))
        bounded = existing is not None and (
            existing.minimum is not None or existing.maximum is not None
        )
        self._limits_section = collapsible(
            tr("Weitere Einstellungen"),
            self._limits,
            open_now=bounded,
            contents=tr("Untergrenze und Obergrenze"),
        )
        chain = (
            self.name_field,
            self.name_suggestion,
            self.value_field,
            self.fx_button,
            self.expression_field,
            self.parameter_button,
            self.unit_field,
            self.minimum_field,
            self.maximum_field,
        )
        for before, after in pairwise(chain):
            QWidget.setTabOrder(before, after)

        self.fx_button.toggled.connect(
            weak_slot(self, ParameterDialog._set_expression_mode, forward=True)
        )
        self.expression_field.textChanged.connect(
            weak_slot(self, ParameterDialog._expression_typed, forward=True)
        )
        self._set_expression_mode(False)
        form.setRowVisible(self.name_refusal, False)
        # Wer am Namen tippt, hat die Ablehnung gelesen; sie galt dem alten Text.
        self.name_field.textEdited.connect(weak_slot(self, ParameterDialog._clear_name_refusal))

        if existing is not None:
            # Vorbelegt mit dem heutigen Stand — ein Änderungsdialog, der leer
            # aufgeht, verlangt vom Kunden, sich zu erinnern, was dasteht.
            # In der Schreibweise der Oberfläche (``localised_value``): Hier
            # stand „0.5" neben „12,50 mm" im Wertfeld. ``_bounds`` liest das
            # Komma wie den Punkt, der Rückweg bleibt also derselbe.
            self.name_field.setText(str(existing.name))
            self.name_field.setReadOnly(True)
            self.value_field.setValue(shown_number(float(existing.value), code))
            for field, bound in (
                (self.minimum_field, existing.minimum),
                (self.maximum_field, existing.maximum),
            ):
                if bound is not None:
                    shown = shown_number(float(bound), code)
                    field.setText(localised_value(f"{shown:g}"))
            self.expression_field.setText(str(existing.expression or ""))
        # Was das Feld beim Öffnen zeigte, und der gespeicherte Wert dahinter —
        # ein unberührtes Feld gibt den gespeicherten zurück, nicht seine Anzeige.
        self._given: dict[str, tuple[str, float]] = {}
        if existing is not None:
            self._given["value"] = (self.value_field.text(), float(existing.value))
            for key, field, bound in (
                ("minimum", self.minimum_field, existing.minimum),
                ("maximum", self.maximum_field, existing.maximum),
            ):
                if bound is not None:
                    self._given[key] = (field.text(), float(bound))

        self.problem = QLabel("", content)
        self.problem.setWordWrap(True)
        self.problem.setVisible(False)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(NORMAL)
        content_layout.addWidget(explanation)
        content_layout.addLayout(form)
        content_layout.addWidget(self._limits_section)
        content_layout.addWidget(self.problem)
        content_layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            # Der Knopf sagt, was er tut — wie in jedem Operationsdialog.
            ok.setText(tr("Übernehmen") if self._editing else tr("Anlegen"))
            make_primary(ok)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(self._fit_soon)
        self.fx_button.toggled.connect(weak_slot(self, ParameterDialog._fit_soon, "explicit"))
        # Die Klappe ist eine Geste: Zugeklappt gibt der Dialog die Höhe zurück,
        # die das passive Nachmessen nie zurückgäbe (FD-198).
        flap = self._limits_section.findChild(QToolButton, "sectionHeading")
        if flap is not None:
            flap.toggled.connect(weak_slot(self, ParameterDialog._fit_soon, "explicit"))
        wheel_needs_focus(self.value_field)
        wheel_needs_focus(self.unit_field)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(buttons)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        self._fit_soon("initial")

    def _fit_soon(self, intent: ContentFitIntent = "passive") -> None:
        QTimer.singleShot(0, self, weak_slot(self, ParameterDialog._fit_content, intent))

    def _fit_content(self, intent: ContentFitIntent) -> None:
        """Misst nach dem Auslöser; manuelle Breite und Höhe bleiben maßgeblich."""
        self._height.fit(self, self._scroll, intent=intent)

    def _reveal_problem(self) -> None:
        """Rollt die nach der Eingabe sichtbare Fehlermeldung ins Sichtfeld."""
        self._scroll.ensureWidgetVisible(self.problem, 0, NORMAL)

    def name_problem(self) -> str | None:
        """Was am Namen nicht geht — oder None. Steht am Namensfeld (FD-155)."""
        name = self.name_field.text().strip()
        if not name:
            return tr("Der Parameter braucht einen Namen.")
        if name in self._existing:
            return tr("Diesen Namen gibt es schon.")
        if not usable_name(name):
            return tr(
                "Der Name muss sich in einem Ausdruck als @name schreiben "
                "lassen — Buchstaben, Ziffern und Unterstriche."
            )
        return None

    def validation_problem(self) -> str | None:
        """Was dem Anlegen im Weg steht — oder None. Eigene Funktion, weil
        sie sich ohne modales Fenster prüfen lassen muss."""
        named = self.name_problem()
        if named is not None:
            return named
        expression = self.expression_field.text().strip() if self.fx_button.isChecked() else ""
        if self.fx_button.isChecked() and not expression:
            return tr("Ein Ausdruck beginnt mit = und rechnet in Millimetern.")
        if expression:
            try:
                # ``=`` und ``@`` darf der Kunde weglassen (``expressions.canonical``).
                self._value = expressions.evaluate(
                    expressions.canonical(expression, self._values), self._values
                )
            except AppError as error:
                return str(error.detail or error.title)
        bounds = self._bounds()
        if bounds is None:
            return tr("Eine Grenze muss eine Zahl sein — oder das Feld bleibt leer.")
        low, high = bounds
        if low is not None and high is not None and low > high:
            return tr("Die Untergrenze liegt über der Obergrenze.")
        value = self._value if expression else self._typed_value()
        if (low is not None and value < low) or (high is not None and value > high):
            return tr("Der Wert liegt außerhalb der eigenen Grenzen.")
        return None

    def _code(self) -> str:
        """Die gewählte Bedeutung, wie das Dokument sie schreibt (``mm``, ``°``, leer)."""
        code = self.unit_field.currentData()
        return str(code) if code is not None else LENGTH_CODE

    def _stored(self, key: str, shown: float, text: str) -> float:
        """Eine Zahl aus dem Feld ``key`` im Maß des Dokuments (FD-125).

        Unberührt — derselbe Text, dieselbe Bedeutung — gilt der gespeicherte
        Wert, sonst die Umrechnung der Anzeige.
        """
        given = self._given.get(key)
        if given is not None and given[0] == text and self._code() == self._given_code:
            return given[1]
        return stored_number(shown, self._code())

    def _typed_value(self) -> float:
        """Die Zahl im Wertfeld, gespeichert wie das Dokument sie führt."""
        return self._stored("value", self.value_field.value(), self.value_field.text())

    @staticmethod
    def _limit_problems() -> tuple[str, ...]:
        """Die Sätze, die eine Grenze meinen — sie klappen die Grenzen auf."""
        return (
            tr("Eine Grenze muss eine Zahl sein — oder das Feld bleibt leer."),
            tr("Die Untergrenze liegt über der Obergrenze."),
            tr("Der Wert liegt außerhalb der eigenen Grenzen."),
        )

    def _bounds(self) -> tuple[float | None, float | None] | None:
        """Die eingetragenen Grenzen im Maß des Dokuments — oder ``None``, wenn
        eine keine Zahl ist.

        Leer heißt: keine Grenze. Das Komma gilt wie der Punkt, denn die
        Felder daneben nehmen beide an. Getippt wird in der Einheit der
        Auswahl, eine Länge also in der Anzeigeeinheit (FD-125).
        """
        found: list[float | None] = []
        for key, field in (("minimum", self.minimum_field), ("maximum", self.maximum_field)):
            raw = field.text().strip().replace(",", ".")
            if not raw:
                found.append(None)
                continue
            try:
                number = float(raw)
            except ValueError:
                return None
            # ``float`` nimmt „inf" und „nan" an, die Projektdatei nicht: Der
            # Parameter kam ins Dokument, und *Speichern* scheiterte ohne
            # Meldung (Gesamtreview 05.09.2026, UI-26).
            if not math.isfinite(number):
                return None
            found.append(self._stored(key, number, field.text()))
        return found[0], found[1]

    def _expression_typed(self, text: str) -> None:
        """Ein eingefügter Ausdruck schaltet ``fx`` von selbst ein.

        Als Methode und nicht als Lambda: Der Abschluss fing ``self``, hing am
        eigenen Eingabefeld und hielt den Dialog fest — zehn von zehn
        überlebten ihr Loslassen.
        """
        if text.strip() and not self.fx_button.isChecked():
            self.fx_button.setChecked(True)

    def _set_expression_mode(self, enabled: bool) -> None:
        """Zeigt genau die Eingabe, die beim Übernehmen gelten wird."""
        self._form.setRowVisible(self.expression_row, enabled)
        # Der Ausdruck besitzt den Wert (§13) — dieselbe Regel, nach der die
        # Leiste abgeleitete Werte zeigt statt sie zu öffnen.
        self.value_field.setEnabled(not enabled)
        if enabled:
            self.expression_field.setFocus()

    def _insert_parameter(self, action: Any) -> None:
        """Setzt oder ersetzt den im @-Menü gewählten Parameternamen.

        Die häufigste Korrektur ist eine zweite Auswahl: Wer erst „Breite" und
        dann „Tiefe" anklickt, meint nicht zwei Namen ohne Rechenzeichen. Ein
        angefangener oder gerade ausgewählter ``@name`` wird deshalb ersetzt;
        in einem zusammengesetzten Ausdruck bleibt das Menü ein Einfügewerkzeug.
        """
        name = str(action.data() or "")
        if not name:
            return
        self.fx_button.setChecked(True)
        reference = f"@{name}"
        entered = self.expression_field.text()
        if not entered.strip():
            self.expression_field.setText(f"={reference}")
            self.expression_field.setCursorPosition(len(self.expression_field.text()))
            return
        if not entered.lstrip().startswith("="):
            entered = f"={entered}"
            self.expression_field.setText(entered)
            self.expression_field.setCursorPosition(len(entered))
        cursor = self.expression_field.cursorPosition()
        head = entered[:cursor]
        start = head.rfind("@")
        if start >= 0:
            typed = head[start + 1 :]
            if not typed or typed.replace("_", "").isalnum():
                self.expression_field.setText(f"{entered[:start]}{reference}{entered[cursor:]}")
                self.expression_field.setCursorPosition(start + len(reference))
                return
        self.expression_field.insert(reference)

    def _accept(self) -> None:
        named = self.name_problem()
        if named is not None:
            self.problem.setVisible(False)
            self._refuse_name(str(named))
            return
        self._clear_name_refusal()
        problem = self.validation_problem()
        if problem is not None:
            if problem in self._limit_problems():
                # Der Satz nennt eine Grenze; die Felder dazu gehören ins Bild.
                from app.ui.panels import open_section

                open_section(self._limits)
            self.problem.setText(problem)
            self.problem.setVisible(True)
            self._fit_soon()
            QTimer.singleShot(0, self, self._reveal_problem)
            return
        self.accept()

    def _refuse_name(self, sentence: str) -> None:
        """Die Ablehnung am Namensfeld: Satz und Zeichen darunter, Feld markiert, Fokus.

        Der Weg ist ein Knopf mit einem freien Namen aus dem Getippten
        (:func:`suggested_name`); ohne getippten Text gibt es keinen, dann sagt
        der Satz, was fehlt.
        """
        typed = self.name_field.text()
        self._suggested = suggested_name(typed, self._existing) if typed.strip() else None
        set_role(self.name_note, "warning", sentence)
        if self._suggested is not None:
            way = tr("„{name}“ verwenden", name=self._suggested)
            self.name_suggestion.setText(way)
            self.name_suggestion.setAccessibleDescription(sentence)
        self.name_suggestion.setVisible(self._suggested is not None)
        self._form.setRowVisible(self.name_refusal, True)
        self.name_field.setAccessibleDescription(sentence)
        self.name_field.setToolTip(sentence)
        self.name_field.setFocus()
        self.name_field.selectAll()
        self._fit_soon()
        QTimer.singleShot(0, self, self._reveal_name_refusal)

    def _reveal_name_refusal(self) -> None:
        """Rollt die Ablehnung am Namen ins Sichtfeld."""
        self._scroll.ensureWidgetVisible(self.name_refusal, 0, NORMAL)

    def _clear_name_refusal(self) -> None:
        """Nimmt die Ablehnung vom Namensfeld; das Feld sagt wieder, wofür es da ist."""
        if not self._form.isRowVisible(self.name_refusal):
            return
        self._form.setRowVisible(self.name_refusal, False)
        self._suggested = None
        self.name_field.setAccessibleDescription(self._name_sentence)
        self.name_field.setToolTip(self._name_sentence)
        self._fit_soon()

    def _take_suggestion(self) -> None:
        """Der vorgeschlagene Name kommt ins Feld; danach steht nichts mehr im Weg."""
        if self._suggested is None:
            return
        self.name_field.setText(self._suggested)
        self._clear_name_refusal()
        self.name_field.setFocus()

    def parameter(self) -> Any:
        """Was angelegt oder übernommen werden soll — erst nach einem
        angenommenen Dialog sinnvoll.

        **Der Titel reist mit, obwohl der Dialog ihn nicht fragt.** Er kommt
        aus dem Agentenwerkzeug und beschriftet die Zeile in der
        Parameterleiste; ihn beim Ändern der Grenzen fallen zu lassen, hieße,
        dass eine Obergrenze von 150 nebenbei „Breite" wieder in „breite"
        verwandelt.
        """
        from app.core.types import Parameter

        expression = (
            self.expression_field.text().strip() or None if self.fx_button.isChecked() else None
        )
        if expression:
            # Gespeichert wird die Form mit ``=`` und ``@`` — wie getippt, nur ergänzt.
            with suppress(AppError):
                expression = expressions.canonical(expression, self._values)
        low, high = self._bounds() or (None, None)
        return Parameter(
            name=self.name_field.text().strip(),
            value=self._value if expression else self._typed_value(),
            unit=self._code(),
            title=self._title,
            minimum=low,
            maximum=high,
            expression=expression,
        )
