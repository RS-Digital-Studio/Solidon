"""Was eine Absage dem Kunden zeigt: Einzelheiten, Schrittwerte, der Weg ins Feld.

Herausgelöst aus ``dialogs.py`` (Codestruktur, Regel 6). Drei Funde, ein Gedanke:
Eine Absage spricht in den Wörtern des Fensters, nicht in denen des Kerns.

* *Einzelheiten* nannten „Objekt: obj_1“, „Operation: 3“ und eine Stelle als
  rohes Tupel mit sechzehn Nachkommastellen (FD-105). :func:`where_lines`
  schreibt Körpername, Schrittnummer mit Titel und die Stelle in der
  Anzeigeeinheit.
* *Werte ansehen* zeigte „paint_slot“ und „radius = 12.0“ in einem Fenster für
  zwanzig Zeilen (FD-105, FD-118). :class:`StepValuesDialog` nennt Titel und
  Feldnamen und misst seine Höhe am Inhalt.
* *Eingabe korrigieren* stand im offenen Operationsdialog als Satz, obwohl der
  Dialog selbst die Eingabe ist (FD-95). :func:`field_ways` macht daraus den
  Sprung ins Feld, das der Kern nennt, wo der Dialog es führt (FD-182);
  sonst fällt der Satz weg.
"""

from __future__ import annotations

import json
import math
import weakref
from collections.abc import Callable, Sequence
from typing import Any, Final

from PySide6.QtCore import QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import CORRECT_INPUT, FIELD_WAYS, AppError
from app.core.registry import REGISTRY
from app.core.units import DEGREE_UNIT
from app.i18n import tr
from app.ui.labels import (
    choice_label,
    length,
    localised_value,
    plain_number,
    step_number,
    value_label,
)
from app.ui.style import NORMAL, SPACE, WIDE, make_primary, set_level

#: Ein Zeilenumbruch als Name, wie in ``dialogs``.
newline = chr(10)

#: Was davon ohne erreichbares Feld wegfällt, statt als Rat zu stehen.
QUIET_WITHOUT_FIELD: Final = frozenset({CORRECT_INPUT.id})

#: Wie breit das Wertefenster höchstens von selbst wird; längere Zeilen brechen um.
STEP_VALUES_WIDTH: Final = (420, 720)

#: Welcher Anteil der Bildschirmhöhe dem Wertetext höchstens zusteht; der Rest rollt.
STEP_VALUES_SCREEN_SHARE: Final = 0.6


def input_dialog_of(widget: QWidget | None) -> Any | None:
    """Der Dialog, der selbst die Eingabe ist — erkennbar an ``focus_field``.

    Gefragt wird nur bis zum nächsten Dialog: Ein Hinweis im Hauptfenster
    sucht kein Feld in einem fremden Panel.
    """
    while widget is not None:
        if isinstance(widget, QDialog):
            return widget if callable(getattr(widget, "focus_field", None)) else None
        widget = widget.parentWidget()
    return None


def field_ways(error: AppError, owner: Any | None) -> dict[str, Callable[[AppError], None]]:
    """*Eingabe korrigieren* als Sprung ins genannte Feld des offenen Dialogs.

    Nur, wo der Sprung landet: *Objekt umbenennen* bot auf eine Ebenenabsage
    „Eine andere Ebene wählen“ an, ohne Ebenenfeld — ein Knopf, der nichts
    tat und den Dialog verbreiterte (FD-182). Gefragt wird ``focus_field``
    selbst, damit Angebot und Sprung dieselbe Antwort geben.

    Der Rückruf hält den Dialog nur schwach: Er hängt am Hinweis, und der
    Hinweis ist ein Kind des Dialogs (``wartezeit.md``, Rückrufe).
    """
    field = str(error.values.get("field") or "")
    if not _reaches(owner, field):
        return {}
    held = weakref.ref(owner)
    wanted = {action.id for action in error.suggestions}

    def jump(_error: AppError) -> None:
        dialog = held()
        if dialog is not None:
            dialog.focus_field(field)

    return dict.fromkeys(FIELD_WAYS & wanted, jump)


def _reaches(owner: Any | None, field: str) -> bool:
    """Ob der offene Dialog den Cursor in ``field`` setzen könnte."""
    return owner is not None and bool(field) and bool(owner.focus_field(field, check_only=True))


def silent_ways(error: AppError, owner: Any | None) -> frozenset[str]:
    """Die Wege, die im offenen Eingabedialog ohne sein Feld nichts zu sagen haben.

    Das ist nur *Eingabe korrigieren*: Die Eingabe steht darüber (FD-95).
    *Eine andere Ebene wählen* sagt dagegen auch ohne Ebenenfeld, was zu tun
    ist, und bleibt als Rat stehen — ohne Knopf, der nichts täte (FD-182).
    """
    if owner is None or _reaches(owner, str(error.values.get("field") or "")):
        return frozenset()
    return frozenset(QUIET_WITHOUT_FIELD & {action.id for action in error.suggestions})


def _session_of(widget: QWidget | None) -> Any | None:
    """Die Sitzung des Fensters, in dem ``widget`` steckt — oder nichts."""
    while widget is not None:
        session = getattr(widget, "session", None)
        if session is not None and hasattr(session, "project"):
            return session
        widget = widget.parentWidget()
    return None


def operation_title(name: str) -> str:
    """Der Titel einer Operation; eine unbekannte behält ihren Namen."""
    return str(REGISTRY.get(name).title) if REGISTRY.has(name) else name


def where_lines(error: AppError, widget: QWidget | None) -> list[str]:
    """Stelle, Körper und Schritt eines Fehlers in den Wörtern des Fensters.

    Eine Kennung ohne Namen fällt weg — „obj_1“ sagt dem Kunden nichts, und
    die Absage nennt ihren Gegenstand schon im Satz.
    """
    lines: list[str] = []
    location = error.values.get("location")
    if isinstance(location, Sequence) and len(location) == 3:
        point = " / ".join(
            (
                length(float(location[0]), with_unit=False),
                length(float(location[1]), with_unit=False),
                length(float(location[2])),
            )
        )
        lines.append(tr("{name}: {value}", name=tr("Stelle"), value=point))
    session = _session_of(widget)
    if session is None:
        return lines
    result = getattr(session, "last_result", None)
    objects = result.scene.objects if result is not None else {}
    if error.object_id and error.object_id in objects:
        name = str(objects[error.object_id].name)
        lines.append(tr("{name}: {value}", name=tr("Objekt"), value=name))
    if error.op_id is not None:
        document = session.project.document
        step = next((entry for entry in document.ops if entry.id == error.op_id), None)
        if step is not None:
            lines.append(
                tr(
                    "Schritt {step}: {label}",
                    step=step_number(document, error.op_id),
                    label=operation_title(step.op),
                )
            )
    return lines


#: Ab welchem Anteil gleichnamiger Felder im Register ein Titel als *der* Name
#: eines Schlüssels gilt — „x“ und „z“ heißen fast überall „Position X/Z“,
#: „radius“ dagegen hat mehrere Bedeutungen, dort bleibt der allgemeine Name.
BORROWED_TITLE_SHARE: Final = 0.85


def _borrowed(key: str) -> tuple[str, str | None]:
    """Titel und Einheit eines Werts, den das Schema seines Schritts nicht mehr kennt.

    Gefragt wird das Register: Einen Titel gibt es, wo sich gleichnamige Felder
    fast alle einig sind, eine Einheit, wo sie es ganz sind. Sonst der Name
    aus ``labels.value_label`` und keine Einheit — geraten wird nicht.
    """
    titles: dict[str, int] = {}
    units: set[str | None] = set()
    for spec in REGISTRY.all():
        for entry in spec.params.spec():
            if entry.name == key:
                titles[str(entry.title)] = titles.get(str(entry.title), 0) + 1
                units.add(entry.unit)
    total = sum(titles.values())
    common = max(titles, key=lambda title: titles[title], default="")
    title = common if total and titles[common] >= BORROWED_TITLE_SHARE * total else ""
    return title or value_label(key), units.pop() if len(units) == 1 else None


def _shown(entry: Any | None, key: str, value: object, unit: str | None = None) -> str:
    """Ein Wert eines Schritts, wie sein Dialog ihn zeigt."""
    if isinstance(value, bool):
        return str(tr("ja") if value else tr("nein"))
    unit = getattr(entry, "unit", None) if entry is not None else unit
    if isinstance(value, int | float):
        if unit == "mm":
            return length(float(value))
        if unit == DEGREE_UNIT:
            return f"{plain_number(float(value))} {DEGREE_UNIT}"
        return plain_number(float(value))
    if isinstance(value, str) and entry is not None and bool(getattr(entry, "choices", None)):
        return choice_label(value)
    return localised_value(value)


def step_values_text(operation: Any) -> str:
    """Die Werte eines Schritts als lesbarer Block, in der Reihenfolge seines Dialogs.

    Ein mehrzeiliger Wert — ein Quelltext, eine Skizze — bekommt seine eigenen
    Zeilen und bleibt wörtlich; alles andere steht in einer, mit dem Namen
    des Feldes und der Einheit der Anzeige. Ein Wert, den das Schema nicht
    kennt (ein älterer Farbschritt mit Punkt und Radius), heißt wie seine
    Namensvettern im Register (:func:`_borrowed`).
    """
    params = dict(operation.params)
    entries = (
        {entry.name: entry for entry in REGISTRY.get(operation.op).params.spec()}
        if REGISTRY.has(operation.op)
        else {}
    )
    order = [name for name in entries if name in params]
    order += sorted(name for name in params if name not in entries)
    lines: list[str] = []
    for name in order:
        value = params[name]
        entry = entries.get(name)
        title = str(entry.title) if entry is not None else ""
        text = str(value)
        if newline in text:
            lines.append(tr("{name}:", name=title or name))
            lines.extend(f"    {line}" for line in text.splitlines())
        elif entry is not None:
            lines.append(tr("{name}: {value}", name=title, value=_shown(entry, name, value)))
        else:
            borrowed, unit = _borrowed(name)
            shown = _shown(None, name, value, unit)
            lines.append(tr("{name}: {value}", name=borrowed, value=shown))
    return newline.join(lines) if lines else str(tr("Dieser Schritt hat keine Werte."))


def stored_values_text(operation: Any) -> str:
    """Die Werte eines Schritts, wie die Datei sie speichert — für *Kopieren* (RA-7).

    Schlüssel und Zahl unverändert, in Millimetern und ohne Rundung: Der Dialog
    sagt zu, dass sie sich herauskopieren lassen, und gezeigt wird gerundet in
    der Anzeigeeinheit (:func:`step_values_text`). Ein mehrzeiliger Wert bleibt
    wörtlich unter seinem Schlüssel.
    """
    lines: list[str] = []
    for name, value in dict(operation.params).items():
        if isinstance(value, str) and newline in value:
            lines.append(f"{name} =")
            lines.extend(f"    {line}" for line in value.splitlines())
            continue
        try:
            written = json.dumps(value, ensure_ascii=False)
        except TypeError, ValueError:
            written = str(value)
        lines.append(f"{name} = {written}")
    return newline.join(lines)


class StepValuesDialog(QDialog):
    """Die Werte eines Schritts, den diese Version nicht rechnen kann.

    **Der einzige Weg zu einer Arbeit, die sonst in der Datei eingeschlossen
    wäre.** Eine Projektdatei aus einer früheren Version kann einen Schritt
    tragen, den es hier nicht mehr gibt (§16.2), oder einen älteren Farbschritt,
    der um einen Punkt färbte. Der Schritt bleibt stehen und seine Werte mit
    ihm; ohne diesen Dialog wäre der Prüfbericht eine Sackgasse.

    **Lesbar, nicht roh** (FD-105): Titel der Operation, Namen der Felder,
    Längen in der Anzeigeeinheit. Ein Quelltext bleibt wörtlich. **So hoch wie
    sein Inhalt** (FD-118): Sechs Zeilen standen in einem Fenster für zwanzig.
    """

    def __init__(self, operation: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Werte dieses Schritts"))
        self._fitted = False
        self._stored = stored_values_text(operation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
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
        self.heading = QLabel(operation_title(str(operation.op)), self)
        set_level(self.heading, "section")
        layout.addWidget(self.heading)

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setPlainText(step_values_text(operation))
        self.text.setAccessibleName(tr("Werte dieses Schritts"))
        layout.addWidget(self.text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        copy = buttons.addButton(tr("Kopieren"), QDialogButtonBox.ButtonRole.ActionRole)
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        make_primary(copy)
        copy.clicked.connect(self._copy)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._fit_width()

    def _fit_width(self) -> None:
        """So breit wie die längste Zeile, in den Grenzen von :data:`STEP_VALUES_WIDTH`."""
        metrics = self.text.fontMetrics()
        longest = max(
            (metrics.horizontalAdvance(line) for line in self.text.toPlainText().splitlines()),
            default=0,
        )
        outer = 2 * WIDE
        frame = 2 * (self.text.frameWidth() + int(self.text.document().documentMargin()))
        bar = self.text.verticalScrollBar().sizeHint().width()
        least, most = STEP_VALUES_WIDTH
        self.resize(max(least, min(most, longest + frame + bar + outer)), self.height())

    def text_height(self) -> int:
        """Was der Wertetext in dieser Breite braucht, gedeckelt am Bildschirm.

        Gemessen an den Blöcken, wie das Textfeld sie setzt (Pixel, samt
        Umbruch) — die Zeilenzahl mal Zeilenabstand lag eine Zeile zu knapp.
        """
        document = self.text.document()
        layout = document.documentLayout()
        block = document.begin()
        laid = 0.0
        while block.isValid():
            laid += layout.blockBoundingRect(block).height()
            block = block.next()
        margins = self.text.contentsMargins()
        wanted = (
            math.ceil(laid)
            + 2 * math.ceil(document.documentMargin())
            + 2 * self.text.frameWidth()
            + margins.top()
            + margins.bottom()
        )
        screen = self.screen() or QApplication.primaryScreen()
        return min(wanted, int(screen.availableGeometry().height() * STEP_VALUES_SCREEN_SHARE))

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        if not self._fitted:
            # Erst nach dem Umbruch in der echten Breite steht die Zeilenzahl fest.
            QTimer.singleShot(0, self, self._fit_height)

    def _fit_height(self) -> None:
        self._fitted = True
        self.text.setFixedHeight(self.text_height())
        self.adjustSize()
        # Danach darf der Kunde größer ziehen; der Text nimmt den Platz.
        self.text.setMinimumHeight(self.text.fontMetrics().lineSpacing() * 3)
        self.text.setMaximumHeight(16_777_215)

    def _copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            # Die gespeicherten Werte, nicht die gerundete Anzeige (RA-7).
            clipboard.setText(self._stored)
