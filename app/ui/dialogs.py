"""Fragen und Fehler, wie der Bauplan sie beschreibt (Bauplan §2.7, §21.3).

Ein Fehler nennt, in dieser Reihenfolge, was nicht ging, warum, und was jetzt
möglich ist — als Knöpfe, nicht als Prosa. Der Stapelabzug geht ins Protokoll,
nie in den Dialog.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, APP_VERSION, COPYRIGHT
from app.core.backends import keys
from app.core.errors import Action, AppError
from app.core.knowledge import calibration, licences, profiles
from app.core.log import get_logger
from app.i18n import tr

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
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(prompt)
        layout.addWidget(self.list)
        layout.addWidget(buttons)

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
                "Alle bestehenden Projekte rechnen danach mit den neuen Werten."
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
            editor.setDecimals(3)
            editor.setRange(-1.0, 5.0)
            editor.setSingleStep(0.01)
            editor.setSuffix(" mm" if name != "shrinkage" else "")
            editor.setValue(float(getattr(current, name)))
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
        """Was eingetragen wurde, als anwendungsfertige Kalibrierung."""
        return calibration.from_measurements(
            self.material, **{name: editor.value() for name, editor in self.editors.items()}
        )


class KeyDialog(QDialog):
    """Wo der Nutzer seinen eigenen Schlüssel hinlegt (Bauplan §27).

    Der Schlüssel geht in den System-Schlüsselbund und sonst nirgends — nicht
    in die Einstellungen, nicht ins Projekt. Das Feld ist ein Passwortfeld, und
    der Dialog zeigt einen gespeicherten Schlüssel nie zurück: er sagt, ob
    einer da ist.
    """

    def __init__(self, account: str = "anthropic", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account = account
        self.setWindowTitle(tr("Zugang zum Sprachmodell"))
        self.setMinimumWidth(420)

        state = {
            "keychain": tr("Ein Schlüssel liegt im Schlüsselbund."),
            "environment": tr("Ein Schlüssel kommt aus der Umgebung."),
            "none": tr("Es ist kein Schlüssel hinterlegt."),
        }[keys.source(account)]

        explanation = QLabel(
            f"{state}\n\n"
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
        layout.addWidget(buttons)

    def _save(self) -> None:
        key = self.field.text().strip()
        if not key:
            self.reject()
            return
        if not keys.store(self.account, key):
            QMessageBox.information(
                self,
                tr("Zugang zum Sprachmodell"),
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


def show_error(error: AppError, parent: QWidget | None = None) -> Action | None:
    """Zeigt einen Fehler als Vorschlag und gibt die gewählte Handlung zurück."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("Das hat so nicht funktioniert"))
    box.setText(str(error.title))
    if error.detail:
        box.setInformativeText(str(error.detail))

    buttons: dict[Any, Action] = {}
    for action in error.suggestions:
        role = (
            QMessageBox.ButtonRole.AcceptRole
            if action.primary
            else QMessageBox.ButtonRole.ActionRole
        )
        buttons[box.addButton(str(action.label), role)] = action

    box.exec()
    return buttons.get(box.clickedButton())


class AboutDialog(QDialog):
    """Version, Rechteinhaber und die Drittanbieter-Lizenzen (§36, §37.2)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Über"))
        self.setMinimumSize(520, 460)

        heading = QLabel(f"{APP_NAME} {APP_VERSION}", self)
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")

        rights = QLabel(f"{COPYRIGHT}. {tr('Alle Rechte vorbehalten.')}", self)
        rights.setWordWrap(True)

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
        layout.addWidget(exceptions)
        layout.addWidget(QLabel(tr("Fremde Bestandteile"), self))
        layout.addWidget(third_party, stretch=1)
        layout.addWidget(buttons)


def _third_party_text() -> str:
    """Die Abhängigkeitstabelle, gelesen in dem Moment, in dem sie gezeigt
    wird.
    """
    try:
        return licences.notices()
    except Exception as problem:  # pragma: no cover - Metadaten sind maschinenabhängig
        _log.warning("could not build the licence list: %s", problem)
        return tr("Die Liste der Fremdbestandteile ließ sich nicht lesen.")


def confirm_discard(count: int, parent: QWidget | None = None) -> bool:
    """Die eine Frage, die sich zu stellen lohnt: mehr als einen Schritt
    wegzuwerfen (§15.4).
    """
    if count <= 1:
        return True
    answer = QMessageBox.question(
        parent,
        tr("Abgeschnittene Schritte verwerfen?"),
        tr("Diese Änderung verwirft {count} zurückgenommene Schritte.").replace(
            "{count}", str(count)
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return answer == QMessageBox.StandardButton.Yes
