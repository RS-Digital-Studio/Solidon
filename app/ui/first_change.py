"""Übernehmen vor der ersten Änderung: grau, und ein Satz nennt das erste Feld als Weg.

Eine Regel für jede Fläche mit *Übernehmen* (Entscheidung Koordinator, FD-31
an der Maßgruppe, FD-99 am Operationsdialog): Solange nichts geändert ist, gibt
es nichts zu übernehmen. Der Knopf ist grau, und grau trägt einen Grund, der
den Weg nennt (``oberflaeche.md``, Regel 18) — hier das erste offene Feld
derselben Fläche. Der Funktionsdurchgang zählt genau diesen Feldtitel als
Ausweg (``tools/function_capture.surface_field_titles``); der Satz nennt
deshalb nur ein Feld, das offen auf der Fläche steht, und zwar so, wie der
Kunde es liest.

Der Aufrufer entscheidet, ob schon etwas geändert ist, setzt den Satz wie
jeden Sperrgrund in Kurzhilfe und Beschreibung (``change_lock.say_refusal``)
und gibt den Knopf mit der ersten Änderung frei.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QFormLayout, QLabel, QLineEdit, QWidget

from app.i18n import tr

#: Was als Feld zählt — dieselben Arten, die der Funktionsdurchgang liest.
_FIELDS = (QAbstractSpinBox, QComboBox, QLineEdit)


def _is_field(widget: QObject) -> bool:
    """Ein Eingabefeld — das Textfeld in einem Dreh- oder Auswahlfeld zählt nicht extra."""
    if not isinstance(widget, _FIELDS):
        return False
    if isinstance(widget, QLineEdit):
        return not widget.isReadOnly() and not isinstance(
            widget.parentWidget(), QAbstractSpinBox | QComboBox
        )
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
        candidates = [widget] if _is_field(widget) else widget.findChildren(QWidget)
        for candidate in candidates:
            if (
                _is_field(candidate)
                and (candidate is surface or surface.isAncestorOf(candidate))
                and candidate.isVisibleTo(surface)
                and candidate.isEnabled()
                and field_title(candidate, surface)
            ):
                return candidate
    return None


def first_change_sentence(fields: Iterable[QObject], surface: QWidget) -> str:
    """Der Satz am grauen *Übernehmen* vor der ersten Änderung — leer ohne offenes Feld."""
    field = first_field(fields, surface)
    if field is None:
        return ""
    return str(tr("Erst „{field}“ ändern, dann übernehmen.", field=field_title(field, surface)))


__all__ = ["field_title", "first_change_sentence", "first_field"]
