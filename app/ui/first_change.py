"""Übernehmen vor der ersten Änderung: grau, und ein Satz nennt das erste Feld als Weg.

Eine Regel für jede Fläche mit *Übernehmen* (Entscheidung Koordinator, FD-31
an der Maßgruppe, FD-99 am Operationsdialog und im Merkmalfenster): Solange
nichts geändert ist, gibt es nichts zu übernehmen. Der Knopf ist grau, und
grau trägt einen Grund, der den Weg nennt (``oberflaeche.md``, Regel 18) —
hier das erste offene Feld derselben Fläche. Der Funktionsdurchgang zählt genau diesen Feldtitel als
Ausweg (``tools/function_capture.surface_field_titles``); der Satz nennt
deshalb ein Feld so, wie der Kunde es liest: eines, das offen auf der
Fläche steht, und sonst das erste hinter einer zugeklappten Klappe samt der
Klappe als Weg dorthin (Review F2a, R4). Als Feld zählen auch Haken und
Listen (:data:`FIELD_KINDS`).

Der Aufrufer entscheidet, ob schon etwas geändert ist, setzt den Satz wie
jeden Sperrgrund in Kurzhilfe und Beschreibung (``change_lock.say_refusal``)
und gibt den Knopf mit der ersten Änderung frei.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from app.core.errors import AppError
from app.i18n import tr

#: Was als Feld zählt — auch ein Haken und eine Liste (Review F2a, R4): Wo vorn
#: nur sie standen, war *Übernehmen* vor jeder Änderung frei. Der
#: Funktionsdurchgang liest dieselben Arten (:func:`is_field`).
FIELD_KINDS = (QAbstractSpinBox, QComboBox, QLineEdit, QCheckBox, QAbstractItemView)


def is_field(widget: QObject) -> bool:
    """Ein Eingabefeld — Textfeld und Liste in einem Dreh- oder Auswahlfeld zählen nicht extra."""
    if not isinstance(widget, FIELD_KINDS):
        return False
    if isinstance(widget, QLineEdit) and widget.isReadOnly():
        return False
    parent = widget.parentWidget() if isinstance(widget, QWidget) else None
    while parent is not None:
        if isinstance(parent, QAbstractSpinBox | QComboBox):
            return False
        parent = parent.parentWidget()
    return True


def field_title(field: QWidget, surface: QWidget | None = None) -> str:
    """Der Titel eines Feldes, wie der Kunde ihn liest.

    Der zugängliche Name trägt ihn, an der Maßgruppe nach dem Gedankenstrich
    („Bohrung ändern — Durchmesser“). Ohne Namen gilt die Beschriftung, deren
    Partner das Feld ist, oder seine Zeile im Formular der Fläche.
    """
    name = field.accessibleName().rsplit(" — ", 1)[-1].strip()
    if name:
        return name
    if surface is None:
        return ""
    captions = [label for label in surface.findChildren(QLabel) if label.buddy() is field]
    for form in surface.findChildren(QFormLayout):
        caption = form.labelForField(field)
        if isinstance(caption, QLabel):
            captions.append(caption)
    for caption in captions:
        text = caption.text().replace("&", "").rstrip(":").strip()
        if text:
            return text
    return ""


def first_field(fields: Iterable[QObject], surface: QWidget) -> QWidget | None:
    """Das erste offene Feld mit Titel auf ``surface``, in der Reihenfolge von ``fields``.

    ``fields`` dürfen Behälter sein (ein Wertfeld mit Drehfeld und
    Ausdruckszeile); gefragt wird dann ihr Inhalt. Offen heißt: auf der Fläche
    sichtbar — eine zugeklappte Rückseite zählt nicht — und bedienbar.
    """
    for widget in fields:
        if not isinstance(widget, QWidget):
            continue
        candidates = [widget] if is_field(widget) else widget.findChildren(QWidget)
        for candidate in candidates:
            if (
                is_field(candidate)
                and (candidate is surface or surface.isAncestorOf(candidate))
                and candidate.isVisibleTo(surface)
                and candidate.isEnabled()
                and field_title(candidate, surface)
            ):
                return candidate
    return None


def first_change_sentence(
    fields: Iterable[QObject],
    surface: QWidget,
    flap: QAbstractButton | None = None,
    behind: QWidget | None = None,
) -> str:
    """Der Satz am grauen *Übernehmen* vor der ersten Änderung — leer ohne Feld.

    Steht kein Feld offen auf der Fläche, aber hinter der zugeklappten Klappe
    ``flap`` (Inhalt ``behind``), nennt der Satz das erste Feld dort und die
    Klappe als Weg dahin. Sonst hinge, ob der Knopf wartet, daran, ob die
    Klappe offen ist (*Skelett stellen*, Review F2a, R4).
    """
    fields = list(fields)
    field = first_field(fields, surface)
    if field is not None:
        return str(tr("Erst „{field}“ ändern, dann übernehmen.", field=field_title(field, surface)))
    if flap is None or behind is None or not flap.isVisibleTo(surface):
        return ""
    hidden = first_field(fields, behind)
    if hidden is None:
        return ""
    return str(
        tr(
            "Erst „{field}“ unter „{flap}“ ändern, dann übernehmen.",
            field=field_title(hidden, behind),
            flap=flap.text().replace("&", "").strip(),
        )
    )


#: Feldarten, die einen Stand tragen. Eine Wahl oder ein Haken ist eine
#: Einstellung des Wegs, kein Maß des Merkmals.
_STATES = frozenset({"length", "angle", "count"})


def offered_unchanged(action: Any) -> bool:
    """Ob eine Handlung am Merkmal beim heutigen Stand angeboten wird (FD-99).

    Übernommen ohne Änderung bliebe dann alles, wie es ist: Ein Schritt kommt
    mit seinen gespeicherten Werten, oder jedes Zahlenfeld trägt den heutigen
    Stand (``ActionField.current``). Eine Handlung, deren Vorgabe selbst etwas
    tut — drehen um 90°, eine Kopie daneben —, ist sofort übernehmbar.
    """
    if getattr(action, "step", None) is not None:
        return bool(action.fields)
    states = [field for field in action.fields if field.kind in _STATES]
    return bool(states) and all(field.current for field in states)


def offered_values(action: Any, values: Callable[[], Mapping[str, Any]]) -> dict[str, Any] | None:
    """Die Werte, mit denen eine Handlung beim heutigen Stand dasteht — sonst ``None``.

    ``values`` liest die Felder so, wie der Knopf sie später liest; verglichen
    wird damit Gleiches mit Gleichem, auch nach Rundung und Einheit.
    """
    if not offered_unchanged(action):
        return None
    try:
        return dict(values())
    except AppError:
        return None


def typed(fields: Iterable[QObject]) -> bool:
    """Ob in einem der Felder getippt wurde, was noch nicht gelesen ist.

    Ein Ausdruck oder eine Zahl ohne Mitlesen (``keyboardTracking``) wird erst
    beim Verlassen des Felds zum Wert. Bis dahin ist sie trotzdem eine
    Änderung — sonst stünde *Übernehmen* grau, und der Klick darauf, der das
    Feld verlassen sollte, ginge ins Leere.
    """
    for widget in fields:
        if not isinstance(widget, QWidget):
            continue
        lines = [widget] if isinstance(widget, QLineEdit) else widget.findChildren(QLineEdit)
        if any(line.isModified() for line in lines):
            return True
    return False


def waits_for_change(
    offered: Mapping[str, Any] | None,
    values: Callable[[], Mapping[str, Any]],
    *,
    touched: bool = False,
) -> bool:
    """Ob *Übernehmen* noch auf die erste Änderung wartet.

    Geändert ist, was von den angebotenen Werten abweicht. ``touched`` sagt
    der Aufrufer für das, was kein Wert ist: ein umgeschalteter Sammelhaken
    ändert den Umfang, getippter Text wird erst beim Verlassen gelesen
    (:func:`typed`). Zurück auf den heutigen Stand heißt wieder: nichts zu tun.
    """
    if offered is None or touched:
        return False
    try:
        return dict(values()) == dict(offered)
    except AppError:
        return False


__all__ = [
    "FIELD_KINDS",
    "field_title",
    "first_change_sentence",
    "first_field",
    "is_field",
    "offered_unchanged",
    "offered_values",
    "typed",
    "waits_for_change",
]
