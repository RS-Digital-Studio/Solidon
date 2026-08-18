"""Fragen und Fehler, wie der Bauplan sie beschreibt (Bauplan §2.7, §21.3).

Ein Fehler nennt, in dieser Reihenfolge, was nicht ging, warum, und was jetzt
möglich ist — als Knöpfe, nicht als Prosa. Der Stapelabzug geht ins Protokoll,
nie in den Dialog.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, APP_VERSION, COPYRIGHT, SUPPORT_ADDRESS, WEBSITE_URL
from app.core import activation
from app.core.backends import keys, llm
from app.core.errors import CANCEL, REPORT_ERROR, SHOW_DETAILS, Action, AppError
from app.core.knowledge import calibration, licences, profiles
from app.core.log import get_logger
from app.core.scene import expressions
from app.i18n import tr
from app.ui.labels import deadline_date
from app.ui.style import set_level

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
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Der Knopf trägt die Antwort, nicht „OK". Auf die Frage „Welchen soll
        # ich abziehen?" ist „OK" keine Antwort — es ist die Aufforderung, sie
        # sich aus der Liste danebenzudenken. Derselbe Grundsatz wie im Dialog
        # *Ungesicherte Änderungen*: der Knopf sagt, was er tut.
        self._accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.list.currentItemChanged.connect(lambda *_: self._name_the_choice())
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
            editor = QDoubleSpinBox(self)
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


class ParameterDialog(QDialog):
    """Ein Projektmaß von Hand anlegen (Bauplan §13, §2.3).

    Anlegen konnte bisher nur der Agent über sein Werkzeug. §2.3 verspricht
    aber, dass ohne KI alles außer dem Chat funktioniert — und Weg 2 lebt von
    benannten Maßen. Die Leiste ändert Werte; das hier ist das Gegenstück,
    das den Namen vergibt.

    Geprüft wird inline, nicht modal: ein Fehlerdialog auf einem Dialog ist
    eine Sackgasse mit Vorgeschichte. Trägt das Ausdrucksfeld etwas, gehört
    der Wert dem Ausdruck — das Wertfeld sagt das, indem es sich abschaltet.
    """

    def __init__(
        self,
        parameters: Mapping[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Parameter anlegen"))
        self.setMinimumWidth(420)
        self._existing = set(parameters)
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
        self.value_field = QDoubleSpinBox(self)
        self.value_field.setDecimals(3)
        self.value_field.setRange(-100_000.0, 100_000.0)
        self.unit_field = QLineEdit("mm", self)
        self.expression_field = QLineEdit(self)
        self.expression_field.setPlaceholderText(tr("optional — zum Beispiel =@breite/2 + 5"))
        # Der Ausdruck besitzt den Wert (§13) — dieselbe Regel, nach der die
        # Leiste abgeleitete Werte zeigt statt sie zu öffnen.
        self.expression_field.textChanged.connect(
            lambda text: self.value_field.setEnabled(not text.strip())
        )

        form = QFormLayout()
        form.addRow(tr("Name"), self.name_field)
        form.addRow(tr("Wert"), self.value_field)
        form.addRow(tr("Einheit"), self.unit_field)
        form.addRow(tr("Ausdruck"), self.expression_field)

        self.problem = QLabel("", self)
        self.problem.setWordWrap(True)
        self.problem.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            # Der Knopf sagt, was er tut — wie in jedem Operationsdialog.
            ok.setText(tr("Anlegen"))
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
        expression = self.expression_field.text().strip()
        if expression:
            try:
                self._value = expressions.evaluate(expression, self._values)
            except AppError as error:
                return str(error.detail or error.title)
        return None

    def _accept(self) -> None:
        problem = self.validation_problem()
        if problem is not None:
            self.problem.setText(problem)
            self.problem.setVisible(True)
            return
        self.accept()

    def parameter(self) -> Any:
        """Was angelegt werden soll — erst nach einem angenommenen Dialog
        sinnvoll."""
        from app.core.types import Parameter

        expression = self.expression_field.text().strip() or None
        return Parameter(
            name=self.name_field.text().strip(),
            value=self._value if expression else self.value_field.value(),
            unit=self.unit_field.text().strip() or "mm",
            expression=expression,
        )


class _ToolProbeWorker(QThread):
    """Die Werkzeugprobe, abseits des Oberflächen-Threads.

    Sie macht einen echten Zug gegen das Modell und lädt es dabei — Sekunden
    bis Minuten. Genau deshalb steht sie hier und nicht im Dialog selbst.
    """

    done = Signal(object)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model

    def run(self) -> None:
        self.done.emit(llm.ollama_tool_check(self._model))


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

        state = {
            "keychain": tr("Ein Schlüssel liegt im Schlüsselbund."),
            "environment": tr("Ein Schlüssel kommt aus der Umgebung."),
            "none": tr("Es ist kein Schlüssel hinterlegt."),
        }[keys.source(account)]

        explanation = QLabel(
            f"{state} {self._what_answers()}\n\n"
            + tr(
                "Der Schlüssel wird im Schlüsselbund des Systems abgelegt und reist "
                "nicht mit der Projektdatei mit. Ohne Schlüssel bleibt alles außer "
                "dem Chat nutzbar."
            ),
            self,
        )
        explanation.setWordWrap(True)

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
        layout.addWidget(explanation)
        layout.addWidget(self.field)
        layout.addWidget(self._local_model_section())
        layout.addWidget(buttons)

    def _what_answers(self) -> str:
        """Was gerade antwortet — die Frage, mit der jemand herkommt.

        „Es ist kein Schlüssel hinterlegt" allein liest sich wie „der Chat geht
        nicht", und das kann falsch sein: läuft ein Modell auf diesem Rechner,
        geht er. Der Satz nennt darum den Weg, der gerade trägt, nicht bloß den
        Zustand des Schlüssels.
        """
        backend = llm.first_available()
        if backend is None:
            return tr("Der Chat ist damit abgeschaltet — es antwortet gerade nichts.")
        if backend.id == "ollama":
            return tr("Der Chat läuft trotzdem: über das lokale Modell.")
        return tr("Der Chat läuft darüber.")

    def _local_model_section(self) -> QWidget:
        """Der zweite Weg: ein Modell auf diesem Rechner, statt eines Schlüssels."""
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

        self.model_field = QLineEdit(llm.configured_ollama_model(), section)
        self.model_field.setPlaceholderText(llm.DEFAULT_OLLAMA_MODEL)

        self.probe_button = QPushButton(tr("Werkzeuge prüfen"), section)
        self.probe_button.clicked.connect(self._probe_tools)

        self.probe_result = QLabel("", section)
        self.probe_result.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(self.model_field)
        row.addWidget(self.probe_button)

        inner = QVBoxLayout(section)
        inner.setContentsMargins(0, 12, 0, 0)
        inner.addWidget(note)
        inner.addLayout(row)
        inner.addWidget(self.probe_result)
        return section

    def _probe_tools(self) -> None:
        model = self.model_field.text().strip() or llm.DEFAULT_OLLAMA_MODEL
        self.probe_button.setEnabled(False)
        self.probe_result.setText(tr("Das Modell wird geladen und gefragt — das dauert."))
        set_level(self.probe_result, "info")

        worker = _ToolProbeWorker(model)
        worker.done.connect(self._probe_done)
        worker.finished.connect(lambda done=worker: self._probe_finished(done))
        self._probe = worker
        worker.start()

    def _probe_done(self, usable: object) -> None:
        self.probe_button.setEnabled(True)
        if usable is None:
            self.probe_result.setText(
                tr("Ollama hat nicht geantwortet. Läuft es? „ollama serve“ startet es.")
            )
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

    def _probe_finished(self, worker: object) -> None:
        # Wer einen Arbeiter startet, hält ihn fest, bis er wirklich fertig ist:
        # `finished` kommt, während Qt ihn noch abräumt.
        if self._probe is worker:
            self._probe = None

    def _save(self) -> None:
        llm.remember_ollama_model(self.model_field.text())
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
        """Kein Arbeiter überlebt seinen Dialog."""
        if self._probe is not None:
            self._probe.wait()
            self._probe = None
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

    def _show_state(self) -> None:
        state = activation.state()
        if state.licence is not None:
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

    def _remember(self) -> None:
        text = self.field.toPlainText().strip()
        if not text:
            self.reject()
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
        + tr("Die aktuelle Fassung gibt es auf {url}.").format(url=WEBSITE_URL)
        + "\n\n"
        + tr(
            "Ihre Projekte sind davon nicht betroffen. Sie liegen, wo Sie sie "
            "gespeichert haben, und eine Projektdatei ist ein ZIP-Archiv mit JSON "
            "darin — lesbar auch ohne dieses Programm, und die nächste Fassung "
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
    """
    offered = [action for action in error.suggestions if action.id in handlers]
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
    """
    return [str(action.label) for action in error.suggestions if action.id not in handlers]


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
    lines.extend(f"{key}: {value}" for key, value in error.values.items())
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


def _licence_line() -> str:
    """Der Freischaltzustand als ein Satz — für den Über-Dialog (H2)."""
    state = activation.state()
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
