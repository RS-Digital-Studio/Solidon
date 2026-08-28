"""Fragen und Fehler, wie der Bauplan sie beschreibt (Bauplan §2.7, §21.3).

Ein Fehler nennt, in dieser Reihenfolge, was nicht ging, warum, und was jetzt
möglich ist — als Knöpfe, nicht als Prosa. Der Stapelabzug geht ins Protokoll,
nie in den Dialog.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from PySide6.QtCore import QLocale, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import (
    APP_NAME,
    APP_VERSION,
    COPYRIGHT,
    DONATION_URL,
    SUPPORT_ADDRESS,
    WEBSITE_URL,
)
from app.core import activation, expressions, tools
from app.core.backends import keys, llm
from app.core.errors import (
    CANCEL,
    REPORT_ERROR,
    SHOW_DETAILS,
    Action,
    AppError,
    InstallationDamaged,
)
from app.core.knowledge import calibration, licences, profiles
from app.core.log import get_logger
from app.i18n import format_decimal, tr
from app.ui.labels import (
    UNEXPECTED_CRASH,
    NumberSpin,
    deadline_date,
    fill_parameter_units,
    value_line,
)
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash, weak_slot
from app.ui.style import make_primary, set_level

#: Ein Zeilenumbruch als Name — im Quelltext ist eine Escape-Folge hier
#: schlechter lesbar als ein Wort.
umbruch = chr(10)

#: Formelsymbole sind keine übersetzbaren Wörter. Als Namen statt als Literale
#: in ``setText`` erkennt auch die Oberflächenprüfung, dass hier kein deutscher
#: Text am Katalog vorbeiläuft.
FORMULA_MARKER = "fx"
PARAMETER_MARKER = expressions.REFERENCE_PREFIX

_log = get_logger(__name__)


class AskDialog(QDialog):
    """Mehrdeutigkeit hält an und fragt — über ``ctx.ask``, nie aus dem Kern
    heraus.
    """

    def __init__(self, question: str, choices: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Rückfrage"))
        self.setMinimumWidth(360)

        prompt = QLabel(question, self)
        prompt.setWordWrap(True)
        self.list = QListWidget(self)
        self.list.addItems(choices)
        self.list.setCurrentRow(0)
        # Kein Lambda: Es fängt ``self`` in seiner Zelle, der Sender gehört
        # ``self``, und damit steht der Ring. Gemessen am 23.08.2026: zehn
        # losgelassene ``AskDialog`` überlebten alle zehn.
        self.list.itemDoubleClicked.connect(weak_slot(self, AskDialog.accept))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Der Knopf trägt die Antwort, nicht „OK". Auf die Frage „Welchen soll
        # ich abziehen?" ist „OK" keine Antwort — es ist die Aufforderung, sie
        # sich aus der Liste danebenzudenken. Derselbe Grundsatz wie im Dialog
        # *Ungesicherte Änderungen*: der Knopf sagt, was er tut.
        self._accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.list.currentItemChanged.connect(weak_slot(self, AskDialog._name_the_choice))
        self._name_the_choice()

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(prompt)
        layout.addWidget(self.list)
        layout.addWidget(buttons)

    def _name_the_choice(self) -> None:
        """Was gewählt ist, steht auf dem Knopf.

        Ohne Auswahl bleibt es bei „OK": ein leerer Knopf wäre schlimmer als
        ein nichtssagender.
        """
        chosen = self.chosen()
        self._accept.setText(chosen or tr("OK"))

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        return item.text() if item is not None else None


class CalibrationDialog(QDialog):
    """Gemessene Werte eintragen (Bauplan §28.3).

    Schritt zwei von dreien: den Prüfkörper drucken, ihn messen, und die Zahlen
    kommen hier hinein. Sie landen im Materialprofil, nicht in einem Modell —
    und weil Toleranzen im Stapel Verweise sind (§12), folgt danach jedes
    bestehende Projekt. Der Dialog sagt das, denn es ist der Teil, der Leute
    überrascht.
    """

    def __init__(self, material: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.material = material
        self.setWindowTitle(tr("Material kalibrieren"))
        self.setMinimumWidth(420)

        current = profiles.material(material)
        state = tr("kalibriert") if current.calibrated else tr("Startwert")
        explanation = QLabel(
            f"{material} — {state}\n\n"
            + tr(
                "Gemessene Werte gehören ins Materialprofil, nicht ins Modell. "
                "Alle bestehenden Projekte rechnen danach mit den neuen Werten.\n\n"
                "Gemessen wird an einem gedruckten Prüfkörper: der Toleranz-Testkörper "
                "aus dem Bausteinkatalog bringt Zapfen und Bohrungen mit gestaffeltem "
                "Spiel auf eine Platte."
            ),
            self,
        )
        explanation.setWordWrap(True)

        self.editors: dict[str, QDoubleSpinBox] = {}
        form = QFormLayout()
        for name, title in (
            ("clearance", tr("Spiel für Schiebesitz")),
            ("press", tr("Übermaß für Presssitz")),
            ("hole_compensation", tr("Lochkorrektur")),
            ("elephant_foot", tr("Elefantenfuß")),
            ("shrinkage", tr("Schwindung")),
        ):
            editor = NumberSpin(self)
            # Die Schwindung ist ein Anteil, kein Maß: „0,004" trug deshalb
            # als Einziges keine Einheit und sagte niemandem etwas. Als
            # Prozentwert liest sie sich — 0,4 % ist eine Zahl, die man aus
            # einem Datenblatt kennt.
            percent = name == "shrinkage"
            editor.setDecimals(2 if percent else 3)
            editor.setRange(-100.0 if percent else -1.0, 500.0 if percent else 5.0)
            editor.setSingleStep(0.1 if percent else 0.01)
            editor.setSuffix(" %" if percent else " mm")
            value = float(getattr(current, name))
            editor.setValue(value * 100.0 if percent else value)
            self.editors[name] = editor
            form.addRow(title, editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def measured(self) -> calibration.Calibration:
        """Was eingetragen wurde, als anwendungsfertige Kalibrierung.

        Die Schwindung steht im Feld als Prozentwert und im Profil als Anteil —
        umgerechnet wird hier, an der einen Stelle, an der beide sich treffen.
        """
        return calibration.from_measurements(
            self.material,
            **{
                name: editor.value() / 100.0 if name == "shrinkage" else editor.value()
                for name, editor in self.editors.items()
            },
        )


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

        explanation = QLabel(
            tr(
                "Ein Parameter ist ein benanntes Maß. Operationen und Skizzen "
                "verweisen mit @name darauf, und an der Zahl zu drehen baut "
                "das Modell neu."
            ),
            self,
        )
        explanation.setWordWrap(True)

        self.name_field = QLineEdit(self)
        self.name_field.setPlaceholderText(tr("zum Beispiel breite"))
        self.value_field = _ParameterValueSpin(self)
        self.value_field.setDecimals(3)
        self.value_field.setRange(-100_000.0, 100_000.0)
        self.unit_field = QComboBox(self)
        fill_parameter_units(
            self.unit_field,
            str(existing.unit or "") if existing is not None else "mm",
        )
        self.unit_field.setAccessibleName(tr("Einheit"))
        # Die Schreibseite der Grenzen (Gesamtreview B-15): Die Leiste liest
        # minimum/maximum seit je als Spinbox-Grenzen und fiel immer auf
        # ±100 000 zurück, weil keine Stelle der Anwendung sie je setzte.
        # Textfelder statt Spinboxen, weil „leer" hier ein Wert ist: keine
        # Grenze. Was aus Ausdrücken hinausläuft, meldet die Auswertung als
        # Befund — hier wird nur die Eingabe abgelehnt (§10).
        self.minimum_field = QLineEdit(self)
        self.minimum_field.setPlaceholderText(tr("optional — leer heißt: keine"))
        self.maximum_field = QLineEdit(self)
        self.maximum_field.setPlaceholderText(tr("optional — leer heißt: keine"))
        self.expression_field = QLineEdit(self)
        self.expression_field.setPlaceholderText(tr("zum Beispiel =@breite/2"))

        # Die zwei sichtbaren Werkzeuge entsprechen dem Operationsdialog:
        # ``fx`` schaltet eine Formel ein, ``@`` nimmt einen vorhandenen Namen.
        # Wer CAD und Ausdruckssyntax nicht kennt, muss dadurch weder das
        # Gleichheitszeichen noch einen internen Parameternamen erraten.
        self.fx_button = QToolButton(self)
        self.fx_button.setText(FORMULA_MARKER)
        self.fx_button.setCheckable(True)
        self.fx_button.setAutoRaise(True)
        self.fx_button.setToolTip(tr("Statt einer Zahl einen Parameterausdruck eintragen."))
        self.fx_button.setAccessibleName(tr("Parameterausdruck"))

        self.parameter_button = QToolButton(self)
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

        value_row = QWidget(self)
        value_layout = QHBoxLayout(value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.addWidget(self.value_field, 1)
        value_layout.addWidget(self.fx_button)

        self.expression_row = QWidget(self)
        expression_layout = QHBoxLayout(self.expression_row)
        expression_layout.setContentsMargins(0, 0, 0, 0)
        expression_layout.addWidget(self.expression_field, 1)
        expression_layout.addWidget(self.parameter_button)

        form = QFormLayout()
        form.addRow(tr("Name"), self.name_field)
        form.addRow(tr("Wert"), value_row)
        form.addRow(tr("Einheit"), self.unit_field)
        form.addRow(tr("Untergrenze"), self.minimum_field)
        form.addRow(tr("Obergrenze"), self.maximum_field)
        form.addRow(tr("Ausdruck"), self.expression_row)
        self._form = form

        self.fx_button.toggled.connect(
            weak_slot(self, ParameterDialog._set_expression_mode, forward=True)
        )
        self.expression_field.textChanged.connect(
            weak_slot(self, ParameterDialog._expression_typed, forward=True)
        )
        self._set_expression_mode(False)

        if existing is not None:
            # Vorbelegt mit dem heutigen Stand — ein Änderungsdialog, der leer
            # aufgeht, verlangt vom Kunden, sich zu erinnern, was dasteht.
            # ``localised`` bleibt hier draußen: Die zwei Grenzfelder nehmen
            # Punkt und Komma an, und was hier hineingeschrieben wird, liest
            # ``_bounds`` gleich wieder.
            self.name_field.setText(str(existing.name))
            self.name_field.setReadOnly(True)
            self.name_field.setToolTip(
                tr(
                    "Der Name ist der Schlüssel, mit dem Ausdrücke und "
                    "Operationen auf das Maß zeigen (@name). Zum Umbenennen "
                    "legen Sie ein neues Maß an."
                )
            )
            self.value_field.setValue(float(existing.value))
            if existing.minimum is not None:
                self.minimum_field.setText(f"{float(existing.minimum):g}")
            if existing.maximum is not None:
                self.maximum_field.setText(f"{float(existing.maximum):g}")
            self.expression_field.setText(str(existing.expression or ""))

        self.problem = QLabel("", self)
        self.problem.setWordWrap(True)
        self.problem.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            # Der Knopf sagt, was er tut — wie in jedem Operationsdialog.
            ok.setText(tr("Übernehmen") if self._editing else tr("Anlegen"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addLayout(form)
        layout.addWidget(self.problem)
        layout.addWidget(buttons)

    def validation_problem(self) -> str | None:
        """Was dem Anlegen im Weg steht — oder None. Eigene Funktion, weil
        sie sich ohne modales Fenster prüfen lassen muss."""
        name = self.name_field.text().strip()
        if not name:
            return tr("Der Parameter braucht einen Namen.")
        if name in self._existing:
            return tr("Diesen Namen gibt es schon.")
        try:
            expressions.check(f"@{name}")
        except AppError:
            return tr(
                "Der Name muss sich in einem Ausdruck als @name schreiben "
                "lassen — Buchstaben, Ziffern und Unterstriche."
            )
        expression = self.expression_field.text().strip() if self.fx_button.isChecked() else ""
        if self.fx_button.isChecked() and not expression:
            return tr("Ein Ausdruck beginnt mit = und rechnet in Millimetern.")
        if expression:
            try:
                self._value = expressions.evaluate(expression, self._values)
            except AppError as error:
                return str(error.detail or error.title)
        bounds = self._bounds()
        if bounds is None:
            return tr("Eine Grenze muss eine Zahl sein — oder das Feld bleibt leer.")
        low, high = bounds
        if low is not None and high is not None and low > high:
            return tr("Die Untergrenze liegt über der Obergrenze.")
        value = self._value if expression else self.value_field.value()
        if (low is not None and value < low) or (high is not None and value > high):
            return tr("Der Wert liegt außerhalb der eigenen Grenzen.")
        return None

    def _bounds(self) -> tuple[float | None, float | None] | None:
        """Die eingetragenen Grenzen — oder ``None``, wenn eine keine Zahl ist.

        Leer heißt: keine Grenze. Das Komma gilt wie der Punkt, denn die
        Felder daneben nehmen beide an.
        """
        found: list[float | None] = []
        for field in (self.minimum_field, self.maximum_field):
            raw = field.text().strip().replace(",", ".")
            if not raw:
                found.append(None)
                continue
            try:
                found.append(float(raw))
            except ValueError:
                return None
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
        """Setzt den im @-Menü gewählten Parameternamen an den Cursor."""
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
        self.expression_field.insert(reference)

    def _accept(self) -> None:
        problem = self.validation_problem()
        if problem is not None:
            self.problem.setText(problem)
            self.problem.setVisible(True)
            return
        self.accept()

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
        low, high = self._bounds() or (None, None)
        unit = self.unit_field.currentData()
        return Parameter(
            name=self.name_field.text().strip(),
            value=self._value if expression else self.value_field.value(),
            unit=str(unit) if unit is not None else "mm",
            title=self._title,
            minimum=low,
            maximum=high,
            expression=expression,
        )


class _ToolProbeWorker(Worker):
    """Die Werkzeugprobe, abseits des Oberflächen-Threads.

    Sie macht einen echten Zug gegen das Modell und lädt es dabei — Sekunden
    bis Minuten. Genau deshalb steht sie hier und nicht im Dialog selbst.

    Gemessen wird beides in einem Gang: **ob** das Modell Werkzeuge aufruft
    und **wie schnell** dieser Rechner es tut. Die zweite Frage kostet fast
    nichts, weil das Modell nach der ersten schon geladen ist — und sie ist die
    wichtigere von beiden, wenn keine Grafikkarte mitspielt.
    """

    done = Signal(object, object)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model

    def work(self) -> None:
        usable = llm.ollama_tool_check(self._model)
        self.done.emit(usable, llm.ollama_speed(self._model))


@dataclass(frozen=True, slots=True)
class ChatState:
    """Was über den Chat auf diesem Rechner zu erfahren ist.

    Gemessen kostete das zusammen 2,7 Sekunden — davon 2,07 allein die Frage
    nach den installierten Modellen. Der Dialog wartete darauf, bevor er
    erschien.
    """

    answers: str
    """Der Satz darüber, was gerade antwortet."""
    service: tools.ToolState | None
    installed: tuple[str, ...]


class _Look(Worker):
    """Nachsehen: Schlüsselbund, Dienst, installierte Modelle."""

    done = Signal(object)

    def work(self) -> None:
        tool = tools.by_id("ollama")
        self.done.emit(
            ChatState(
                answers=_what_answers(),
                service=tools.state_of(tool) if tool is not None else None,
                installed=llm.installed_models(),
            )
        )


class _StartWorker(Worker):
    """Ollama starten und warten, bis sein Port antwortet."""

    done = Signal(bool)

    def __init__(self, tool: tools.ExternalTool) -> None:
        super().__init__()
        self._tool = tool

    def work(self) -> None:
        self.done.emit(tools.start(self._tool))


class _PullWorker(Worker):
    """Ein Modell holen — fünf bis neun Gigabyte.

    Mit Abbrechen, und das ist keine Höflichkeit: Ollama behält, was schon
    geladen ist, ein zweiter Versuch setzt fort. Ein Vorgang dieser Länge ohne
    Ausgang wäre die Sackgasse, die §2.8 verbietet.
    """

    done = Signal(object)
    step = Signal(str, float)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def work(self) -> None:
        self.done.emit(
            llm.pull_model(
                self._model,
                progress=lambda status, share: self.step.emit(status, share),
                cancelled=lambda: self._stop,
            )
        )


def _what_answers() -> str:
    """Was gerade antwortet — die Frage, mit der jemand herkommt.

    „Es ist kein Schlüssel hinterlegt" allein liest sich wie „der Chat geht
    nicht", und das kann falsch sein: läuft ein Modell auf diesem Rechner, geht
    er. Der Satz nennt darum den Weg, der gerade trägt, nicht bloß den Zustand
    des Schlüssels.

    Eine Modulfunktion, weil der Arbeiter sie braucht: ``first_available``
    fragt ein Backend, und das ist ein HTTP-Aufruf.
    """
    backend = llm.first_available()
    if backend is None:
        return tr("Der Chat ist damit abgeschaltet — es antwortet gerade nichts.")
    if backend.id == "ollama":
        return tr("Der Chat läuft trotzdem: über das lokale Modell.")
    return tr("Der Chat läuft darüber.")


class KeyDialog(QDialog):
    """Wo der Nutzer den Chat einrichtet (Bauplan §27).

    Zwei Wege, ein Dialog: der eigene Schlüssel gegen ein gehostetes Modell,
    und das lokale Modell über Ollama. Der Schlüssel geht in den
    System-Schlüsselbund und sonst nirgends — nicht in die Einstellungen, nicht
    ins Projekt. Das Feld ist ein Passwortfeld, und der Dialog zeigt einen
    gespeicherten Schlüssel nie zurück: er sagt, ob einer da ist.

    Der Modellname dagegen ist kein Geheimnis und steht offen da. Neben ihm
    steht die Probe, und sie steht dort aus einem Grund: ob ein Modell
    Werkzeuge wirklich aufruft, sieht man ihm nicht an. Weder seine Größe noch
    die Fähigkeit, die Ollama meldet, sagen es — nur ein Zug.

    **Der Dialog heißt überall gleich, und das war er nicht.** Der
    Erstlaufbildschirm bot ihn als *Chat einrichten* an, das Menü als *Zugang
    zum Sprachmodell*: derselbe Dialog unter zwei Namen, und wer den einen
    gesehen hatte, suchte den anderen nicht. Geblieben ist der, der die Sache
    aus Sicht des Nutzers nennt — er sieht den Chat, nicht das Sprachmodell
    dahinter —, und der beide Wege aus §27 trägt: Ein Schlüssel *und* ein
    lokales Modell sind zwei Arten, den Chat zum Laufen zu bringen. Was
    darunter passiert, sagt der Erklärtext im Dialog.
    """

    def __init__(self, account: str = "anthropic", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account = account
        self.setWindowTitle(tr("Chat einrichten"))
        self.setMinimumWidth(460)
        self._probe: _ToolProbeWorker | None = None
        self._starter: _StartWorker | None = None
        self._pull: _PullWorker | None = None
        self._leash = WorkerLeash(self)
        """Hält den ausgelaufenen Prüf-Arbeiter, bis Qt mit ihm durch ist —
        das Warum steht in :mod:`app.ui.leash`."""

        state = {
            "keychain": tr("Ein Schlüssel liegt im Schlüsselbund."),
            "environment": tr("Ein Schlüssel kommt aus der Umgebung."),
            "none": tr("Es ist kein Schlüssel hinterlegt."),
        }[keys.source(account)]

        # Der Satz darüber, was antwortet, kommt nachgereicht: Er fragt ein
        # Backend, und das ist ein HTTP-Aufruf (:class:`_Look`).
        self._key_state = state
        self.explanation = QLabel(
            f"{state} {tr('Wird nachgesehen …')}\n\n"
            + tr(
                "Der Schlüssel wird im Schlüsselbund des Systems abgelegt und reist "
                "nicht mit der Projektdatei mit. Ohne Schlüssel bleibt alles außer "
                "dem Chat nutzbar."
            ),
            self,
        )
        self.explanation.setWordWrap(True)

        self.field = QLineEdit(self)
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText(tr("Schlüssel einfügen"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.forget_button = buttons.addButton(
            tr("Löschen"), QDialogButtonBox.ButtonRole.DestructiveRole
        )
        self.forget_button.clicked.connect(self._forget)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.explanation)
        layout.addWidget(self.field)
        layout.addWidget(self._local_model_section())
        layout.addWidget(buttons)

        self._look: _Look | None = None
        self.look()

    # --- nachsehen --------------------------------------------------------------

    def look(self) -> None:
        """Nachsehen, was auf diesem Rechner ist. Beim Aufbau und nach jedem
        Schritt.

        **Im Arbeiter**, weil es gemessen 2,7 Sekunden kostet: die Frage nach
        den installierten Modellen allein 2,07. Der Dialog wartete darauf,
        bevor er erschien — und das an der Stelle, an der jemand seinen Chat
        überhaupt erst einrichtet (§2.8, §38).
        """
        if self._look is not None and self._look.isRunning():
            return
        worker = _Look()
        worker.done.connect(self._show_state)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._worker_finished(done))
        self._look = worker
        self._leash.start(worker)

    def wait_for_look(self, milliseconds: int = 30_000) -> bool:
        """Auf die Erhebung warten. Beim Schließen und in Tests."""
        worker = self._look
        return worker.wait(milliseconds) if worker is not None else True

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        **Ein Name für den Aufräumbefehl, auf allen Klassen, die Arbeiter
        halten.** Es waren fünf — ``release``, ``wait_for_workers``,
        ``wait_for_survey``, ``wait_for_look``, ``wait_for_setup`` —, und wer
        eine Testfixture darauf baute, sammelte sie nacheinander ein: erst
        zwei, dann drei, dann vier. Der fünfte fehlte, und der Prozess starb
        beim Abbau an einem Thread, der sein Fenster überlebt hatte.

        Der fachliche Name daneben bleibt: ``wait_for_look`` gibt einen Wahrheitswert zurück
        und steht in
        ``reject``, wo der Dialog seine eigene Frage stellt.

        **Die Frist der fachlichen Methode bleibt ihre eigene.** Hier stand
        zuerst ``wait_for_look(timeout_ms)`` — und damit bekam eine Erhebung, für die
        30 Sekunden vorgesehen sind, die 2 Sekunden, die für das Einsammeln
        der Leine gedacht sind. Gemessen an ``test_chat_ui``: zwei von vier
        Läufen starben danach beim Abbau, gegen null von vier davor. Der
        Parameter gilt der Leine, nicht der Sache.
        """
        self.wait_for_look()
        self._leash.wait_all(timeout_ms)

    def _show_state(self, found: object) -> None:
        """Die Antworten eintragen."""
        assert isinstance(found, ChatState)
        self.state = found
        text = self.explanation.text().split("\n\n", 1)
        rest = text[1] if len(text) > 1 else ""
        self.explanation.setText(f"{self._key_state} {found.answers}\n\n{rest}")
        self._show_service(found.service)
        self._fill_models(found.installed)

    def reject(self) -> None:
        self.wait_for_look()
        super().reject()

    def _local_model_section(self) -> QWidget:
        """Der zweite Weg: ein Modell auf diesem Rechner, statt eines Schlüssels.

        **Drei Schritte, und zwei davon fehlten hier.** Ollama installieren
        konnte man aus der Liste der zusätzlichen Programme; danach stand der
        Chat weiterhin still, denn Ollama muss laufen und braucht ein Modell.
        Beides stand nur in Sätzen — „«ollama serve» startet es" und „«ollama
        pull» mit dem Modellnamen holt es" —, gerichtet an jemanden, der in
        einem Fenster sitzt. Jetzt steht an jedem der drei Schritte der Knopf,
        der ihn tut.
        """
        section = QWidget(self)
        note = QLabel(
            tr(
                "Statt eines Schlüssels geht auch ein Modell über Ollama. Ob es "
                "Werkzeuge wirklich aufruft, sagt weder seine Größe noch der "
                "Anbieter — nur die Probe."
            ),
            section,
        )
        note.setWordWrap(True)

        #: Läuft Ollama, ist es nur installiert, oder fehlt es? Ein Satz und
        #: der Knopf, der zu diesem Satz gehört.
        self.service_state = QLabel(section)
        self.service_state.setWordWrap(True)
        self.service_button = QPushButton(tr("Ollama starten"), section)
        self.service_button.clicked.connect(self._start_ollama)

        # Ein Aufklappfeld statt eines Textfelds: Wer den Namen tippen soll,
        # muss ihn kennen. Editierbar bleibt es — ein Modell, das wir nicht
        # empfehlen, ist keines, das wir verbieten.
        self.model_field = QComboBox(section)
        self.model_field.setEditable(True)
        self._fill_models()

        self.pull_button = QPushButton(tr("Modell holen"), section)
        self.pull_button.clicked.connect(self._pull_model)
        self.probe_button = QPushButton(tr("Werkzeuge prüfen"), section)
        self.probe_button.clicked.connect(self._probe_tools)

        self.pull_progress = QProgressBar(section)
        self.pull_progress.setVisible(False)
        self.pull_progress.setTextVisible(False)

        self.probe_result = QLabel("", section)
        self.probe_result.setWordWrap(True)

        service_row = QHBoxLayout()
        service_row.addWidget(self.service_state, stretch=1)
        service_row.addWidget(self.service_button)

        row = QHBoxLayout()
        row.addWidget(self.model_field, stretch=1)
        row.addWidget(self.pull_button)
        row.addWidget(self.probe_button)

        inner = QVBoxLayout(section)
        inner.setContentsMargins(0, 12, 0, 0)
        inner.addWidget(note)
        inner.addLayout(service_row)
        inner.addLayout(row)
        inner.addWidget(self.pull_progress)
        inner.addWidget(self.probe_result)
        # Bis die Erhebung antwortet, steht hier ein Satz und kein Zustand,
        # den niemand nachgesehen hat.
        self.service_state.setText(tr("Wird nachgesehen …"))
        self.service_button.setVisible(False)
        self.pull_button.setEnabled(False)
        self.probe_button.setEnabled(False)
        return section

    # --- der Dienst -------------------------------------------------------------

    def _ollama(self) -> tools.ExternalTool | None:
        return tools.by_id("ollama")

    def _show_service(self, state: tools.ToolState | None) -> None:
        """Der Zustand von Ollama als Satz, und der passende Knopf daneben.

        Der Zustand kommt von außen: Ihn zu erheben heißt, eine Datei zu
        suchen und einen Port zu fragen, und das gehört in den Arbeiter.
        """
        if state is None:
            self.service_state.setText("")
            self.service_button.setVisible(False)
            return
        if state.running:
            self.service_state.setText(tr("Ollama läuft."))
            set_level(self.service_state, "ok")
            self.service_button.setVisible(False)
        elif state.installed:
            self.service_state.setText(tr("Ollama ist installiert, läuft aber nicht."))
            set_level(self.service_state, "warning")
            self.service_button.setText(tr("Ollama starten"))
            self.service_button.setVisible(True)
        else:
            self.service_state.setText(
                tr("Ollama ist nicht installiert — ohne es geht der Weg über einen Schlüssel.")
            )
            set_level(self.service_state, "info")
            self.service_button.setText(tr("Zusätzliche Programme …"))
            self.service_button.setVisible(True)
        self.pull_button.setEnabled(state.running)
        self.probe_button.setEnabled(state.running)

    def _start_ollama(self) -> None:
        """Starten, oder — wenn es fehlt — dorthin, wo es herkommt."""
        tool = self._ollama()
        if tool is None:
            return
        if not tools.state_of(tool).installed:
            from app.ui.install_dialog import InstallDialog

            InstallDialog(self).exec()
            self.look()
            return
        self.service_button.setEnabled(False)
        self.service_state.setText(tr("Ollama wird gestartet …"))
        set_level(self.service_state, "info")
        worker = _StartWorker(tool)
        worker.done.connect(self._started)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._worker_finished(done))
        self._starter = worker
        self._leash.start(worker)

    def _started(self, running: bool) -> None:
        self.service_button.setEnabled(True)
        self.look()
        if running:
            return
        self.service_state.setText(
            tr("Ollama ließ sich nicht starten. Von Hand geht es mit „ollama serve“.")
        )
        set_level(self.service_state, "warning")

    # --- das Modell -------------------------------------------------------------

    def _fill_models(self, here: tuple[str, ...] = ()) -> None:
        """Was installiert ist, und was sich bewährt hat.

        Die installierten stehen oben und ohne Zusatz — sie sind einen Klick
        entfernt. Die empfohlenen darunter mit Größe und dem Satz, der sagt,
        was sie leisten: Zwischen 5 und 9 Gigabyte liegt eine Entscheidung.

        Was installiert ist, kommt von außen: Die Frage danach kostete
        gemessen 2,07 Sekunden und läuft im Arbeiter.
        """
        chosen = self._chosen_model() if self.model_field.count() else llm.configured_ollama_model()
        self.model_field.clear()
        for name in here:
            # **Auch das installierte Modell sagt, was es kann.** Hier stand
            # nur der Name — „sie sind einen Klick entfernt" —, und damit sah
            # ein unbrauchbares Modell aus wie ein gutes. Wer ``mistral-nemo``
            # liegen hat, soll lesen, dass es Werkzeuge nicht aufruft, bevor
            # er einen Zug abwartet, der nichts tut.
            note = llm.known_model_note(name)
            self.model_field.addItem(f"{name} — {note}" if note else name, name)
        for name, gigabytes, what in llm.OLLAMA_SUGGESTIONS:
            if name in here:
                continue
            # „GB" ist keine Beschriftung, sondern die Einheit selbst — und
            # die Zahl bekommt ihr Komma aus der aktiven Sprache (§13).
            size = f"{format_decimal(gigabytes, 1)} GB"
            self.model_field.addItem(f"{name} — {size}, {what}", name)
        if not self.model_field.count():
            self.model_field.addItem(llm.DEFAULT_OLLAMA_MODEL, llm.DEFAULT_OLLAMA_MODEL)
        self._select_model(chosen)

    def _select_model(self, wanted: str) -> None:
        index = self.model_field.findData(wanted)
        if index >= 0:
            self.model_field.setCurrentIndex(index)
        else:
            self.model_field.setEditText(wanted)

    def _chosen_model(self) -> str:
        """Der Modellname — nicht die Zeile, in der er steht.

        Ein Eintrag trägt Größe und Bewertung hinter dem Namen; als Modellname
        weitergegeben wäre das ein Name, den Ollama nicht kennt.
        """
        data = self.model_field.currentData()
        if isinstance(data, str) and data == self.model_field.currentText().split(" — ")[0]:
            return data
        typed = self.model_field.currentText().strip()
        if isinstance(data, str) and typed.startswith(f"{data} — "):
            return data
        return typed.split(" — ")[0] or llm.DEFAULT_OLLAMA_MODEL

    def _pull_model(self) -> None:
        """Neun Gigabyte, mit Balken und Abbrechen statt eines Terminals."""
        if self._pull is not None and self._pull.isRunning():
            self._pull.cancel()
            return
        model = self._chosen_model()
        self.pull_progress.setRange(0, 0)
        self.pull_progress.setVisible(True)
        self.pull_button.setText(tr("Abbrechen"))
        self.probe_button.setEnabled(False)
        self.probe_result.setText(f"{tr('Wird geholt')}: {model}")
        set_level(self.probe_result, "info")

        worker = _PullWorker(model)
        worker.step.connect(self._pull_step)
        worker.done.connect(self._pull_done)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._worker_finished(done))
        self._pull = worker
        self._leash.start(worker)

    def _pull_step(self, status: str, share: float) -> None:
        """Ollamas Zustandszeile, und der Anteil, wenn es einen gibt."""
        if share < 0.0:
            self.pull_progress.setRange(0, 0)
        else:
            self.pull_progress.setRange(0, 100)
            self.pull_progress.setValue(int(share * 100))
        percent = f" — {int(share * 100)} %" if share >= 0.0 else ""
        self.probe_result.setText(f"{status}{percent}")

    def _pull_done(self, problem: object) -> None:
        self.pull_progress.setVisible(False)
        self.pull_button.setText(tr("Modell holen"))
        self.look()
        if problem is None:
            # **Und es gilt sofort, nicht erst beim Speichern.** Wer ein Modell
            # holt und den Dialog danach mit *Abbrechen* schließt — weil er
            # keinen Schlüssel eintragen will —, hätte neun Gigabyte geladen
            # und einen Chat, der weiter auf das alte Modell zeigt. Das
            # Herunterladen ist eine Tatsache; nur die Eingabefelder warten
            # auf eine Entscheidung.
            llm.remember_ollama_model(self._chosen_model())
            self.probe_result.setText(
                tr("Das Modell liegt jetzt hier. Die Probe sagt, ob es taugt.")
            )
            set_level(self.probe_result, "ok")
            return
        self.probe_result.setText(str(problem))
        set_level(self.probe_result, "warning")

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand.

        Vier Arbeiter enden hier, und alle vier hinterlassen sonst einen
        Dialog, der stillsteht: „Wird nachgesehen …", „Ollama wird gestartet
        …", ein laufender Balken über einem Download. Ein ``run``, das eine
        Ausnahme durchlässt, sendet sein Ergebnissignal nie.
        """
        _log.warning("chat setup worker crashed: %s", detail)
        self.pull_progress.setVisible(False)
        self.pull_button.setText(tr("Modell holen"))
        self.service_button.setEnabled(True)
        self.probe_button.setEnabled(True)
        self.probe_result.setText(f"{UNEXPECTED_CRASH!s} {detail}")
        set_level(self.probe_result, "warning")

    def _worker_finished(self, worker: object) -> None:
        """Wer einen Arbeiter startet, hält ihn fest — siehe :mod:`app.ui.leash`."""
        if self._starter is worker:
            self._starter = None
        if self._pull is worker:
            self._pull = None
        if self._look is worker:
            self._look = None
        self._leash.hold_until_done(worker)

    def _probe_tools(self) -> None:
        model = self._chosen_model()
        self.probe_button.setEnabled(False)
        self.probe_result.setText(tr("Das Modell wird geladen und gefragt — das dauert."))
        set_level(self.probe_result, "info")

        worker = _ToolProbeWorker(model)
        worker.done.connect(self._probe_done)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._probe_finished(done))
        self._probe = worker
        self._leash.start(worker)

    def _probe_done(self, usable: object, speed: object) -> None:
        self.probe_button.setEnabled(True)
        if usable is None:
            self.probe_result.setText(
                tr("Ollama hat nicht geantwortet. Läuft es? „ollama serve“ startet es.")
            )
            set_level(self.probe_result, "warning")
            return
        # **Die Geschwindigkeit schlägt die Werkzeugfrage.** „Das Modell ruft
        # Werkzeuge auf" ist wahr und nutzlos, wenn eine Antwort einundvierzig
        # Minuten braucht — gemessen auf einer Maschine mit Intel-Arc-Grafik,
        # die Ollama nicht anspricht. Der Kunde soll das erfahren, bevor er es
        # als Fehler der Anwendung erlebt.
        slow = self._speed_text(speed)
        if slow:
            self.probe_result.setText(slow)
            set_level(self.probe_result, "warning")
            return
        if usable:
            self.probe_result.setText(tr("Das Modell ruft Werkzeuge auf. Es ist brauchbar."))
            set_level(self.probe_result, "ok")
            return
        self.probe_result.setText(
            tr(
                "Das Modell schreibt seine Aufrufe als Text, statt sie zu tun — der "
                "Chat antwortet damit, führt aber nichts aus. Ein anderes Modell hilft."
            )
        )
        set_level(self.probe_result, "warning")

    @staticmethod
    def _speed_text(speed: object) -> str:
        """Der gemessene Satz samt Zahlen — oder leer, wenn nichts zu sagen ist.

        Die Zahlen setzt die Oberfläche ein und nicht der Kern: Dort steht der
        Satz mit seinen Platzhaltern, hier stehen Sprache und Rundung (§33.1,
        dasselbe Muster wie ``AppError.values``).
        """
        if not isinstance(speed, llm.Speed):
            return ""
        warning = llm.speed_warning(speed)
        if warning is None or speed.prompt_minutes is None:
            return ""
        return str(warning).format(
            rate=round(speed.tokens_per_second or 0.0, 1),
            minutes=round(speed.prompt_minutes),
        )

    def _probe_finished(self, worker: object) -> None:
        # Wer einen Arbeiter startet, hält ihn fest, bis er wirklich fertig
        # ist: `finished` kommt, während Qt ihn noch abräumt — das Loslassen
        # übernimmt die Halteleine, nicht dieses Feld.
        if self._probe is worker:
            self._probe = None
        self._leash.hold_until_done(worker)

    def _save(self) -> None:
        # Der Name, nicht die Zeile: Ein Eintrag der Empfehlungsliste trägt
        # Größe und Bewertung hinter dem Namen, und die gehören nicht in die
        # Einstellung.
        llm.remember_ollama_model(self._chosen_model())
        key = self.field.text().strip()
        if not key:
            # Kein Schlüssel heißt nicht „nichts zu tun": der Modellname
            # darüber ist eine eigene Einstellung und gilt schon.
            self.accept()
            return
        if not keys.store(self.account, key):
            QMessageBox.information(
                self,
                tr("Chat einrichten"),
                tr(
                    "Auf diesem Rechner gibt es keinen Schlüsselbund. "
                    "Der Schlüssel kann über die Umgebungsvariable übergeben werden."
                ),
            )
            self.reject()
            return
        self.accept()

    def _forget(self) -> None:
        keys.forget(self.account)
        self.field.clear()
        self.accept()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 — Qt gibt den Namen vor
        """Kein Arbeiter überlebt seinen Dialog.

        **Über die Halteleine, nicht mit eigenem Warten.** Hier stand
        ``self._probe.wait()`` ohne Grenze, und die Probe dauert laut ihrem
        eigenen Docstring „Sekunden bis Minuten" — abbrechen lässt sie sich
        nicht, sie hängt an einer Antwort von Ollama. Wer den Dialog währenddessen
        schloss, hatte eine eingefrorene Anwendung, bis das Modell fertig war.

        Schlimmer war die Zeile danach: ``self._probe = None`` gab die einzige
        Referenz auf, und wäre das Warten je vorzeitig zurückgekommen, hätte der
        Speicherbereiniger das QThread-Objekt unter dem laufenden Thread
        weggeräumt — die Zugriffsverletzung, gegen die es die Leine gibt.
        ``retire`` tut beides richtig: Es hält ihn, und ``wait_all`` wartet mit
        Frist und schreibt auf, wenn sie reißt.
        """
        if self._probe is not None:
            probe, self._probe = self._probe, None
            self._leash.retire(probe)
        self._leash.wait_all()
        super().closeEvent(event)


class ActivationDialog(QDialog):
    """Wo ein Lizenzschlüssel eingetragen wird (Konzept §2 B, §2 C).

    Anders als beim Schlüssel des Sprachmodells ist das Feld **kein**
    Passwortfeld und der Dialog zeigt den abgelegten Schlüssel: er ist nicht
    geheim, er ist personalisiert. Wer ihn sehen will, um ihn auf einen zweiten
    Rechner zu übertragen, soll ihn sehen.

    Er ist mehrzeilig, weil ein personalisierter Offline-Schlüssel lang ist und
    aus einer E-Mail über mehrere Zeilen kommt. Das Lesen räumt Umbrüche,
    Leerzeichen und Kleinschreibung selbst weg.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Solidon freischalten"))
        self.setMinimumWidth(520)

        self.state_label = QLabel(self)
        self.state_label.setWordWrap(True)

        self.field = QPlainTextEdit(self)
        self.field.setPlaceholderText(tr("SOLIDON3D-1-…"))
        self.field.setFixedHeight(90)
        # Sonst ist der Dialog eine Tastenfalle: Ein mehrzeiliges Feld nimmt den
        # Tabulator als Zeichen, und wer ohne Maus arbeitet, kommt aus dem Feld
        # nicht mehr heraus — ausgerechnet dort, wo ein Schlüssel eingegeben
        # wird, den viele aus einer Mail kopieren.
        self.field.setTabChangesFocus(True)
        if stored := activation.read_key():
            self.field.setPlainText(stored)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.check_button = buttons.addButton(
            tr("Eintragen"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.check_button.clicked.connect(self._remember)
        # **Ohne Schlüssel kann er nichts eintragen, und sagt es vorher.**
        # „Eintragen" mit leerem Feld rief ``reject()``: Der Dialog verschwand
        # wortlos — genau in dem Zustand, in dem jemand nicht weiter weiß, und
        # als Antwort auf den einen Knopf, der etwas versprach. Ausgegraut mit
        # Grund ist die Regel dieses Hauses (Regel 19, §2.7).
        self.field.textChanged.connect(self._follow_field)
        self.forget_button = buttons.addButton(
            tr("Schlüssel entfernen"), QDialogButtonBox.ButtonRole.DestructiveRole
        )
        self.forget_button.clicked.connect(self._forget)
        self.buy_button = buttons.addButton(
            tr("Solidon kaufen"), QDialogButtonBox.ButtonRole.HelpRole
        )
        self.buy_button.clicked.connect(open_website)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.state_label)
        layout.addWidget(self.field)
        layout.addWidget(buttons)
        self._show_state()
        self._follow_field()

    def _show_state(self) -> None:
        state = activation.state()
        if state.damaged:
            # **Die beschädigte Installation kommt vor dem Schlüssel.** Sie
            # liest ihn nämlich (``Activation.damaged`` sagt, warum), und wer
            # bezahlt hat, sah deshalb „Freigeschaltet für kaeufer@…" in einem
            # Fenster, dessen schreibende Seite zu ist — den wahren Grund
            # erfuhr er beim ersten Änderungsversuch. Das ist Regel 17 an der
            # Anzeige: Der Zustand nennt sich selbst, nicht erst die Absage.
            self.state_label.setText(damaged_line())
            set_level(self.state_label, "warning")
        elif state.licence is not None:
            self.state_label.setText(
                tr("Freigeschaltet für {holder} (Bestellung {order}).").format(
                    holder=state.licence.holder or tr("diesen Rechner"),
                    order=state.licence.order,
                )
            )
            set_level(self.state_label, "info")
        elif state.in_demo:
            # Für die Demo gibt es keinen Schlüssel — das ist keine Lücke,
            # sondern die Bauart: sie läuft ohne Eingabe und endet an einem
            # Datum. Ohne diesen Satz stünde hier ein Eingabefeld, das
            # niemand füllen kann, und der Nutzer suchte den Fehler bei sich.
            self.state_label.setText(
                tr("Demo — noch {days} Tage, bis zum {date}.").format(
                    days=state.days_left, date=deadline_date(state)
                )
                + " "
                + tr(
                    "Für die Demo gibt es keinen Schlüssel: sie läuft vollständig und "
                    "ohne Eingabe. Danach lässt sie sich nicht mehr starten — die "
                    "Vollversion und ihr Schlüssel kommen über die Website."
                )
            )
            set_level(self.state_label, "info")
        elif state.in_trial:
            self.state_label.setText(
                tr("Testzeitraum: noch {days} Tage.").format(days=state.days_left)
                + " "
                + tr(
                    "Danach bleiben Öffnen, Ansehen, Messen und Speichern nutzbar; "
                    "Ändern, Exportieren und die Übergabe an den Slicer brauchen "
                    "einen Schlüssel."
                )
            )
            set_level(self.state_label, "info")
        else:
            self.state_label.setText(
                tr(
                    "Der Testzeitraum ist abgelaufen. Projekte lassen sich weiter "
                    "öffnen und ansehen."
                )
            )
            set_level(self.state_label, "warning")
        if state.licence is None and (problem := activation.stored_problem()) is not None:
            # Ein abgelegter Schlüssel steht im Feld und zählt trotzdem nicht —
            # ohne den Grund daneben bliebe das unerklärt.
            self.state_label.setText(
                f"{self.state_label.text()}\n\n{problem.detail or problem.title}"
            )
            set_level(self.state_label, "warning")

    def _follow_field(self) -> None:
        """„Eintragen" kann nur, wenn etwas im Feld steht — und wenn es hilft.

        Der Grund steht am Knopf, nicht erst hinterher: Ein Dialog, der sich auf
        einen Klick hin wortlos schließt, hat die Frage nicht beantwortet,
        sondern weggeräumt.

        **Bei gebrochenem Manifest (H4) können beide Knöpfe nichts.**
        ``damaged`` schlägt jeden Schlüssel (``Activation.unlocked``), also
        schaltet *Eintragen* nichts frei — und *Solidon kaufen* schickt in
        beiden Lagen an die falsche Stelle: Wer bezahlt hat, soll nicht noch
        einmal kaufen, und wer nicht bezahlt hat, bekommt mit einem Kauf
        trotzdem keine heile Installation. Zwei Knöpfe, die nichts bewirken
        können, sind zwei Sackgassen; grau mit Grund ist die Regel dieses
        Hauses.

        *Schlüssel entfernen* bleibt bedienbar — es tut, was es sagt, und
        hängt nicht an der Freischaltung.

        Der Grund ist derselbe Satz wie in der Zeile darüber
        (:func:`damaged_line`, Quelle ist ``InstallationDamaged``), und er
        steht dreifach da: sichtbar im ``state_label``, im Tooltip und über
        ``accessibleDescription`` für den, der den Bildschirm nicht liest.
        Grau allein wäre eine Aussage über die Farbe (Regel 18).
        """
        damaged = activation.state().damaged
        filled = bool(self.field.toPlainText().strip())
        self.check_button.setEnabled(filled and not damaged)
        self.buy_button.setEnabled(not damaged)
        locked = damaged_line() if damaged else ""
        self.check_button.setToolTip(
            locked
            or ("" if filled else str(tr("Fügen Sie den Schlüssel aus der Bestellmail ein.")))
        )
        self.buy_button.setToolTip(locked)
        for button in (self.check_button, self.buy_button):
            button.setStatusTip(button.toolTip())
            button.setAccessibleDescription(button.toolTip())

    def _remember(self) -> None:
        text = self.field.toPlainText().strip()
        if not text:
            # Erreichbar bleibt das über die Tastatur; geschlossen wird deshalb
            # nicht, sondern gesagt, was fehlt.
            self._follow_field()
            return
        try:
            activation.remember(text)
        except activation.LicenceKeyError as problem:
            # Über show_error, damit „Solidon kaufen" mitkommt: die Vorschläge
            # des Fehlers sind die halbe Regel 17.
            show_error(problem, self)
            return
        if activation.read_key() is None:
            QMessageBox.information(
                self,
                tr("Solidon freischalten"),
                tr(
                    "Der Schlüssel gilt für diese Sitzung, ließ sich aber nicht "
                    "ablegen — beim nächsten Start wird er wieder gebraucht."
                ),
            )
        self.accept()

    def _forget(self) -> None:
        """Nimmt den abgelegten Schlüssel weg — vor dem Verkauf des Rechners."""
        activation.forget_key()
        self.field.clear()
        self._show_state()


def open_website() -> None:
    """Öffnet die Produktseite — dieselbe Adresse, die auch der Installer nennt."""
    QDesktopServices.openUrl(QUrl(WEBSITE_URL))


def open_donation(parent: QWidget | None = None) -> None:
    """Öffnet den PayPal-Zahlungsweg erst nach dem ausdrücklichen Klick."""
    if QDesktopServices.openUrl(QUrl(DONATION_URL)):
        return
    QMessageBox.warning(
        parent,
        tr("PayPal ließ sich nicht öffnen"),
        tr(
            "Der Standardbrowser hat den Zahlungslink nicht angenommen. Öffnen Sie "
            "{url} selbst oder wenden Sie sich an {address}."
        ).format(url=DONATION_URL, address=SUPPORT_ADDRESS),
    )


def expired_demo_text(state: activation.Activation) -> str:
    """Was eine abgelaufene Demo zu sagen hat — der Text ohne Fenster darum.

    Getrennt vom Dialog, weil dieselben Sätze auch die Kommandozeile braucht;
    zwei Formulierungen desselben Endes wären zwei verschiedene Auskünfte.

    Drei Dinge stehen darin, und jedes aus einem Grund (Demo-Konzept §2 B2):
    was abgelaufen ist — sonst wirkt ein Programm, das nicht mehr startet, wie
    ein defektes. Wo es weitergeht — ein Ende ohne Fortsetzung ist eine
    Sackgasse, und Regel 17 verbietet sie auch hier. Und was aus der eigenen
    Arbeit wird: das ist die Frage, die jemand als erste stellt, und die
    Antwort nimmt ihr die Schärfe.
    """
    return (
        tr("Diese Demo von {app} lief bis zum {date} und lässt sich nicht mehr starten.").format(
            app=APP_NAME, date=deadline_date(state)
        )
        + "\n\n"
        + tr("Die aktuelle Version gibt es auf {url}.").format(url=WEBSITE_URL)
        + "\n\n"
        + tr(
            "Ihre Projekte sind davon nicht betroffen. Sie liegen, wo Sie sie "
            "gespeichert haben, und eine Projektdatei ist ein ZIP-Archiv mit JSON "
            "darin — lesbar auch ohne dieses Programm, und die nächste Version "
            "öffnet sie unverändert."
        )
    )


def show_expired_demo(state: activation.Activation) -> None:
    """Die Verabschiedung der Demo, mit einem Weg nach vorn.

    Ein Fenster und kein stiller Nichtstart: Wer doppelt klickt und nichts
    geschieht, sucht den Fehler bei sich oder hält das Programm für kaputt.
    """
    box = QMessageBox()
    box.setWindowTitle(tr("Die Demo ist abgelaufen"))
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(expired_demo_text(state))
    website = box.addButton(tr("Website öffnen"), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Close)
    box.exec()
    if box.clickedButton() is website:
        open_website()


#: Handlungen, die ohne die Kennung ihres Schrittes nichts tun können.
#:
#: *Eingabe korrigieren* öffnet den Schritt wieder, dessen Werte nicht gingen
#: (``MainWindow.edit_operation``). Ein Fehler ohne ``op_id`` — beim Lesen einer
#: Datei, beim Schreiben eines Exports — hat keinen solchen Schritt, und ein
#: Knopf, der nichts tut, ist schlimmer als keiner.
#:
#: *Werte ansehen* steht aus demselben Grund daneben: Es zeigt die Parameter
#: **eines** Schritts, und ohne seine Kennung gibt es nichts zu zeigen.
NEEDS_OP: Final = frozenset({"correct_input", "show_step_values"})


class StepValuesDialog(QDialog):
    """Die rohen Werte eines Schritts, den diese Fassung nicht rechnen kann.

    **Der einzige Weg zu einer Arbeit, die sonst in der Datei eingeschlossen
    wäre.** Eine Projektdatei aus einer früheren Fassung kann einen Schritt
    tragen, den es hier nicht mehr gibt (§16.2) — bei einer Datei aus 0.1.3
    ist das der OpenSCAD-Quelltext, den jemand geschrieben hat. Der Schritt
    bleibt stehen und seine Werte mit ihm; rechnen lässt er sich nicht, und
    öffnen auch nicht, denn der Operationsdialog wird aus einem
    Registereintrag gebaut, den es nicht gibt.

    Ohne diesen Dialog wäre der Prüfbericht eine Sackgasse: ein Befund, der
    sagt „Ihre Werte bleiben erhalten", und kein Weg, an sie heranzukommen.

    **Die Werte stehen roh da, mit Punkt statt Komma, und das ist Absicht.**
    Sonst gilt in der Oberfläche das Gegenteil (``labels.localised``) — hier
    aber ist der Text zum **Kopieren** gedacht: Er geht in ein anderes
    Programm oder dient als Vorlage zum Nachbauen. Eine lokalisierte Zahl wäre
    dort falsch, dieselbe Begründung wie bei ``measured_expression``.
    """

    def __init__(self, operation: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Werte dieses Schritts"))
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        hint = QLabel(
            tr(
                "Diesen Schritt kann Solidon nicht rechnen — seine Werte stehen "
                "aber unverändert in der Datei. Sie lassen sich hier "
                "herauskopieren."
            ),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(QLabel(str(operation.op), self))

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setPlainText(step_values_text(operation))
        layout.addWidget(self.text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        copy = buttons.addButton(tr("Kopieren"), QDialogButtonBox.ButtonRole.ActionRole)
        make_primary(copy)
        copy.clicked.connect(self._copy)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _copy(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.text.toPlainText())


def step_values_text(operation: Any) -> str:
    """Die Parameter eines Schritts als lesbarer Block.

    Ein mehrzeiliger Wert — ein Quelltext, eine Skizze — bekommt seine eigenen
    Zeilen; alles andere steht in einer. Ohne diese Unterscheidung stünde ein
    ganzes Programm hinter einem Gleichheitszeichen auf einer einzigen Zeile.
    """
    lines: list[str] = []
    for name, value in sorted(dict(operation.params).items()):
        text = str(value)
        if umbruch in text:
            lines.append(f"{name}:")
            lines.extend(f"    {line}" for line in text.splitlines())
        else:
            lines.append(f"{name} = {text}")
    return umbruch.join(lines) if lines else tr("Dieser Schritt hat keine Werte.")


def handlers_of(widget: QWidget | None) -> Mapping[str, Callable[[AppError], None]]:
    """Die Fehlerhandlungen des Fensters, in dem dieser Dialog steckt.

    Damit muss ein Dialog sie nicht durchreichen: die Druckeinstellungen und
    der Variantendialog zeigen Fehler, und ihre Knöpfe sollen dasselbe tun wie
    die des Fensters. Ein vergessenes Argument wäre sonst wieder ein Dialog
    voller Knöpfe ohne Wirkung.
    """
    while widget is not None:
        source = getattr(widget, "error_handlers", None)
        if callable(source):
            found: Mapping[str, Callable[[AppError], None]] = source()
            return found
        widget = widget.parentWidget()
    return {}


def offered_actions(
    error: AppError, handlers: Mapping[str, Callable[[AppError], None]]
) -> list[Action]:
    """Welche Vorschläge ein Fehlerdialog zeigt (§2.7).

    Eigene Funktion, weil sie sich prüfen lassen muss: ein Test, der dafür
    den Dialog aufmacht, hängt am modalen Fenster — dieselbe Falle steht
    schon im Kopf von ``tests/test_ui.py``.

    Angeboten wird, wofür es einen Handler gibt. Bleibt nichts übrig — weder
    ein Knopf noch ein Rat zum Lesen —, tritt der Fehlerbericht ein: sonst
    stünde am Ende ein Fenster mit „Abbrechen", und das ist „fehlgeschlagen"
    mit mehr Worten (Regel 17).

    **Und wofür der Fehler mitbringt, was der Handler braucht.** *Eingabe
    korrigieren* öffnet den Schritt, dessen Werte nicht gingen — ohne
    ``op_id`` gibt es keinen, den es öffnen könnte, und der Knopf wäre wieder
    einer von denen, die nichts tun.
    """
    offered = [
        action
        for action in error.suggestions
        if action.id in handlers and not (action.id in NEEDS_OP and error.op_id is None)
    ]
    if offered:
        return offered
    if unhandled_advice(error, handlers):
        # Der Rat steht im Text, und der Fehlerbericht wäre daneben die
        # lauteste Antwort auf einen Bedienfehler. Er gehört dem
        # ``InternalError`` (errors.py), nicht einer fehlenden Auswahl.
        return [entry for entry in (SHOW_DETAILS,) if entry.id in handlers]
    return [entry for entry in (SHOW_DETAILS, REPORT_ERROR) if entry.id in handlers]


def unhandled_advice(
    error: AppError, handlers: Mapping[str, Callable[[AppError], None]]
) -> list[str]:
    """Die Vorschläge ohne Handler — als Sätze zum Lesen statt als Knopf.

    **Der Rat war da und kam nie an.** Von 48 Kennungen, die der Kern in
    ``Action(...)`` vergibt, sind zehn verdrahtet; die übrigen wurden
    stillschweigend verworfen, und an ihrer Stelle stand „Fehlerbericht
    erstellen" als Hauptknopf — auf einen reinen Bedienfehler. Dabei sind es
    gerade die selbst formulierten, die konkret helfen: „Schreiben Sie das Ziel
    als obj_2:hole_1.", „Wählen Sie das Merkmal im Objektbaum aus."

    Sie werden nicht zu Knöpfen: Ein Knopf ohne Wirkung ist schlimmer als
    keiner, und daran ändert sich nichts. Sie werden zu Text — damit hält §2.7
    sein Versprechen („was jetzt möglich ist"), ohne eines zu geben, das die
    Oberfläche nicht einlösen kann.

    **Außer „Abbrechen".** Jede Ausnahme in ``errors.py`` führt es unter ihren
    Vorschlägen, für keine gibt es einen Handler — es stand also in *jedem*
    Fehlerdialog als Ratschlag im Text, direkt über dem Abbrechen-Knopf. Der
    Grundsatz dazu stand längst daneben, bei den Knöpfen: „das Schließen ist
    kein Vorschlag, es steht ohnehin da" (:func:`offered_actions`). Der Textpfad
    hatte ihn nur nicht übernommen.
    """
    return [
        str(action.label)
        for action in error.suggestions
        if action.id not in handlers and action.id != CANCEL.id
    ]


def show_error(
    error: AppError,
    parent: QWidget | None = None,
    handlers: Mapping[str, Callable[[AppError], None]] | None = None,
) -> Action | None:
    """Zeigt einen Fehler als Vorschlag und **führt die gewählte Handlung aus**.

    Der Rückgabewert gab es von Anfang an, und keiner der Aufrufer las ihn:
    jeder Knopf schloss ein Fenster und tat sonst nichts. „Reparieren und
    erneut versuchen" war ein Versprechen, das die Oberfläche nicht hielt —
    Regel 17 war damit optisch erfüllt und funktional hohl.

    Angeboten wird nur, wofür es einen Handler gibt (§2.7). Lieber ein Knopf
    weniger als einer, der nichts tut. Damit nie nur „Abbrechen" übrig bleibt,
    kommt der Fehlerbericht dazu — er geht immer.
    """
    known = dict(handlers if handlers is not None else handlers_of(parent))
    offered = offered_actions(error, known)

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("Das hat so nicht funktioniert"))
    box.setText(str(error.title))
    # Erst was nicht ging, dann was jetzt möglich ist (§2.7). Der zweite Teil
    # fehlte für jeden Vorschlag ohne Handler — siehe :func:`unhandled_advice`.
    spoken = [str(error.detail)] if error.detail else []
    spoken.extend(unhandled_advice(error, known))
    if spoken:
        box.setInformativeText("\n".join(spoken))

    buttons: dict[Any, Action] = {}
    for action in offered:
        role = (
            QMessageBox.ButtonRole.AcceptRole
            if action.primary
            else QMessageBox.ButtonRole.ActionRole
        )
        buttons[box.addButton(str(action.label), role)] = action
    box.addButton(str(CANCEL.label), QMessageBox.ButtonRole.RejectRole)

    box.exec()
    chosen = buttons.get(box.clickedButton())
    if chosen is not None:
        known[chosen.id](error)
    return chosen


def show_details(error: AppError, parent: QWidget | None = None) -> None:
    """Was der Fehler an Zahlen mitbringt — ohne Stapelabzug (§2.7, §33.1)."""
    lines = [str(error.detail)] if error.detail else []
    # Nicht der rohe Schlüssel: „open_edges: 6" ist ein Bezeichner, kein Satz
    # (Regel 20). ``value_line`` setzt Beschriftung, Einheit und das
    # Dezimaltrennzeichen der Anzeigesprache.
    lines.extend(value_line(key, value) for key, value in error.values.items())
    if error.object_id:
        lines.append(f"{tr('Objekt')}: {error.object_id}")
    if error.op_id is not None:
        lines.append(f"{tr('Operation')}: {error.op_id}")

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(tr("Einzelheiten"))
    box.setText(str(error.title))
    box.setDetailedText("\n".join(lines) or tr("Keine weiteren Angaben."))
    box.exec()


class DonationDialog(QDialog):
    """Der freiwillige Förderweg — lokal erklärt, erst danach geht es hinaus."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = tr("{app} unterstützen").format(app=APP_NAME)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)

        heading = QLabel(title, self)
        set_level(heading, "title")

        intro = QLabel(
            tr(
                "Wenn Ihnen {app} hilft, können Sie die Weiterentwicklung, Tests und "
                "die nächste Version mit einer freiwilligen Zahlung unterstützen."
            ).format(app=APP_NAME),
            self,
        )
        intro.setWordWrap(True)

        terms = QLabel(
            tr(
                "Die Zahlung ist freiwillig. Sie ist keine Bestellung, begründet keine "
                "Gegenleistung und wird nicht auf einen späteren Kauf angerechnet. Eine "
                "Spendenbescheinigung können wir nicht ausstellen."
            ),
            self,
        )
        terms.setWordWrap(True)

        self.browser_note = QLabel(
            tr(
                "PayPal verarbeitet Ihre Daten erst nach dem Klick. Dann öffnet sich die "
                "Zahlungsseite von PayPal direkt in Ihrem Standardbrowser; die Website "
                "von {app} wird nicht geöffnet."
            ).format(app=APP_NAME),
            self,
        )
        self.browser_note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.support_button = buttons.addButton(
            tr("Mit PayPal unterstützen"), QDialogButtonBox.ButtonRole.ActionRole
        )
        make_primary(self.support_button)
        self.support_button.clicked.connect(self._open_donation)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(intro)
        layout.addWidget(terms)
        layout.addWidget(self.browser_note)
        layout.addWidget(buttons)

    def _open_donation(self) -> None:
        open_donation(self)


class AboutDialog(QDialog):
    """Version, Rechteinhaber und die Drittanbieter-Lizenzen (§36, §37.2)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Über"))
        self.setMinimumSize(520, 460)

        heading = QLabel(f"{APP_NAME} {APP_VERSION}", self)
        set_level(heading, "title")

        rights = QLabel(f"{COPYRIGHT}. {tr('Alle Rechte vorbehalten.')}", self)
        rights.setWordWrap(True)

        support = QLabel(f"{tr('Support und Kontakt')}: {SUPPORT_ADDRESS}", self)
        support.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # §2 I H2: der Über-Dialog nennt den Freischaltzustand beim Namen.
        # Wer einen personalisierten Schlüssel weitergibt, gibt seinen Namen
        # mit — und der steht hier, nicht versteckt in einem Untermenü.
        licensed = QLabel(_licence_line(), self)
        licensed.setWordWrap(True)

        exceptions = QLabel(
            tr(
                "Bausteinbibliothek und Referenzkorpus stehen unter der MIT-Lizenz, "
                "weil ihr Inhalt in den Ergebnissen der Nutzer landet."
            ),
            self,
        )
        exceptions.setWordWrap(True)

        third_party = QTextBrowser(self)
        third_party.setMarkdown(_third_party_text())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(rights)
        layout.addWidget(support)
        layout.addWidget(licensed)
        layout.addWidget(exceptions)
        layout.addWidget(QLabel(tr("Fremde Bestandteile"), self))
        layout.addWidget(third_party, stretch=1)
        layout.addWidget(buttons)


def damaged_line() -> str:
    """Was eine beschädigte Installation (H4) über sich sagt — an einer Stelle.

    **Der Wortlaut kommt aus dem Kern und wird hier nicht zum zweiten Mal
    erfunden.** :class:`InstallationDamaged` trägt Titel und Grund samt der
    beiden Wege (neu installieren, sonst Support); zwei Formulierungen
    derselben Auskunft wären zwei Gelegenheiten, auseinanderzulaufen — und die
    Meldung ist der Satz, den derselbe Kunde beim ersten Änderungsversuch
    ohnehin zu lesen bekommt.

    Ein *Satz*, keine Handlungsvorschläge: Der Freischaltdialog hat seine
    eigene Knopfleiste, und die Fassung mit Knöpfen zeigt ``report_error``,
    wenn eine gesperrte Funktion wirklich angefasst wird.

    **Öffentlich, weil es vier Leser gibt**: die Zeile im Freischaltdialog, der
    Grund an seinen zwei gesperrten Knöpfen, der Über-Dialog und die
    Ersteinrichtung — die versprach sonst „Die ersten 14 Tage ist alles frei"
    an eine Installation, die schon in der ersten Sekunde nichts freigibt.
    """
    problem = InstallationDamaged()
    return f"{problem.title} {problem.detail}"


def _licence_line() -> str:
    """Der Freischaltzustand als ein Satz — für den Über-Dialog (H2)."""
    state = activation.state()
    if state.damaged:
        # Dieselbe Auskunft wie im Freischaltdialog, und aus demselben Grund
        # zuerst: Der Schlüssel wird auch bei gebrochenem Manifest gelesen,
        # also stand hier „Lizenziert für …" über einer Installation, die
        # nichts freischaltet.
        return damaged_line()
    if state.licence is not None:
        return tr("Lizenziert für {holder} (Bestellung {order}).").format(
            holder=state.licence.holder or tr("diesen Rechner"),
            order=state.licence.order,
        )
    if state.in_demo:
        return tr("Demo — noch {days} Tage, bis zum {date}.").format(
            days=state.days_left, date=deadline_date(state)
        )
    if state.in_trial:
        return tr("Testzeitraum: noch {days} Tage.").format(days=state.days_left)
    return tr("Der Testzeitraum ist abgelaufen — Änderungen brauchen einen Lizenzschlüssel.")


def _third_party_text() -> str:
    """Die Abhängigkeitstabelle, gelesen in dem Moment, in dem sie gezeigt
    wird.
    """
    try:
        return licences.notices()
    except Exception as problem:  # pragma: no cover - Metadaten sind maschinenabhängig
        _log.warning("could not build the licence list: %s", problem)
        return tr("Die Liste der Fremdbestandteile ließ sich nicht lesen.")


def confirm_unsaved(title: str, parent: QWidget | None = None) -> str:
    """Vor dem Wegwerfen eines geänderten Dokuments fragen (§2.1, Regel 19).

    Regel 19 verbietet Rückfragen vor **rücknehmbaren** Handlungen. Ein
    Dokument zu verwerfen ist keine: nach dem Schließen holt kein Undo es
    zurück. Die Frage hat deshalb drei Antworten und nicht zwei — „Wirklich?"
    mit Ja und Nein zwingt den Nutzer, das Speichern selbst zu erledigen und
    von vorn anzufangen.

    Gibt ``save``, ``discard`` oder ``cancel`` zurück.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(tr("Ungesicherte Änderungen"))
    box.setText(tr("Dieses Projekt hat Änderungen, die noch nicht gespeichert sind."))
    box.setInformativeText(title)
    save = box.addButton(tr("Speichern"), QMessageBox.ButtonRole.AcceptRole)
    discard = box.addButton(tr("Verwerfen"), QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(tr("Abbrechen"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(save)
    box.exec()

    clicked = box.clickedButton()
    if clicked is save:
        return "save"
    return "discard" if clicked is discard else "cancel"


def confirm_discard(count: int, names: Sequence[str] = (), parent: QWidget | None = None) -> bool:
    """Die eine Frage, die sich zu stellen lohnt: mehr als einen Schritt
    wegzuwerfen (§15.4).

    Die Knöpfe heißen nach ihrer Handlung und nicht „Ja"/„Nein" — wie der
    Dialog *Ungesicherte Änderungen* es an derselben Stelle vorbildlich macht.
    „Ja" verlangt, die Frage im Kopf zu behalten; „Verwerfen" nicht.

    Und die Schritte werden benannt. Eine Zahl sagt, wie viel weg ist, nicht
    was.
    """
    if count <= 1:
        return True
    box = QMessageBox(parent)
    box.setWindowTitle(tr("Abgeschnittene Schritte verwerfen?"))
    box.setText(
        tr("Diese Änderung verwirft {count} zurückgenommene Schritte.").replace(
            "{count}", str(count)
        )
    )
    if names:
        box.setInformativeText("\n".join(f"· {name}" for name in names))
    discard = box.addButton(tr("Verwerfen"), QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(tr("Abbrechen"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(discard)
    box.exec()
    return box.clickedButton() is discard
