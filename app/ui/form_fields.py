"""Jedes Formularfeld trägt seinen Namen und seinen Satz — ein Weg für alle Formulare.

Ein ``QFormLayout`` verbindet Beschriftung und Feld nicht (``oberflaeche.md``,
„Ein Feld ohne Namen“). Ohne Namen las ein Bildschirmleser den Inhalt vor —
„breite“, „40,00“ im Parameterdialog (FD-94) — oder gar nichts. Die Lücken
lagen an zwei Stellen: Ein Feld, das selbst der Editor ist (Auswahl, Haken),
bekam keinen Namen, und in einem Behälter (Zahl mit *fx*) nur das erste Kind.

Die Regel, die jedes Formular hier holt:

* **Name** ist der sichtbare Text der Beschriftung (:func:`name_rows`) — am
  Feld selbst, wenn es ein Eingabefeld ist, sonst an jedem namenlosen
  Eingabefeld darin. Ein Haken mit eigenem Text heißt wie dieser Text. Ein
  schon gesetzter Name bleibt: Er trägt oft die Handlung mit („Vorgabe ·
  Breite“), die die Beschriftung allein nicht nennt.
* **Satz** ist, was der Wert bewirkt (:func:`explain`) — als Kurzhilfe an
  beiden Hälften der Zeile und als ``accessibleDescription`` an jedem
  Eingabefeld darin.
* **Wächter** ist :func:`unnamed_inputs`: Er zählt dieselben Arten wie der
  Prüfstand (``function_capture._input_widgets``).
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from app.core import guides

#: Was ein Bildschirmleser als Eingabefeld ansteuert — dieselben Arten, die der
#: Prüfstand als Feld zählt.
INPUT_KINDS: tuple[type[QWidget], ...] = (
    QAbstractSpinBox,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPlainTextEdit,
    QTextEdit,
)


def _is_input(widget: QWidget) -> bool:
    """Ein Eingabefeld, aber nicht die Textzeile in einer Zahl oder Auswahl."""
    if not isinstance(widget, INPUT_KINDS):
        return False
    return not (
        isinstance(widget, QLineEdit)
        and isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox))
    )


def inputs_of(field: QWidget) -> list[QWidget]:
    """Die Eingabefelder einer Zeile: das Feld selbst oder die darin, in Bauordnung."""
    if _is_input(field):
        return [field]
    return [widget for widget in field.findChildren(QWidget) if _is_input(widget)]


def caption_text(caption: QWidget | None) -> str:
    """Der sichtbare Text einer Beschriftung, ohne das Kürzelzeichen."""
    if isinstance(caption, (QLabel, QAbstractButton)):
        return caption.text().replace("&&", "\0").replace("&", "").replace("\0", "&").strip()
    return ""


def name_inputs(field: QWidget, caption: str) -> None:
    """Gibt jedem namenlosen Eingabefeld der Zeile einen Namen.

    Ein Haken heißt wie sein eigener Text, alles andere wie die Zeile.
    """
    for widget in inputs_of(field):
        if widget.accessibleName():
            continue
        own = widget.text() if isinstance(widget, QCheckBox) else ""
        name = own.strip() or caption
        if name:
            widget.setAccessibleName(name)


def name_rows(*forms: QFormLayout) -> None:
    """Jede Zeile der Formulare: Name an die Felder, Beschriftung an das erste Feld.

    Wiederholbar — ein Neuaufbau ruft es erneut, gesetzte Namen bleiben.
    """
    for form in forms:
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            caption = label_item.widget() if label_item is not None else None
            field = field_item.widget() if field_item is not None else None
            if field is None:
                continue
            text = caption_text(caption)
            name_inputs(field, text)
            inputs = inputs_of(field)
            # ``addRow(text, field)`` setzt den Behälter als Ziel; das Kürzel der
            # Beschriftung soll aber im Eingabefeld landen, nicht davor.
            if isinstance(caption, QLabel) and inputs and caption.buddy() in (None, field):
                caption.setBuddy(inputs[0])


def explain(field: QWidget, caption: QWidget | None, sentence: str) -> None:
    """Ein Satz an das Feld, an seine Beschriftung und an den Bildschirmleser.

    Ein inneres Feld mit eigenem Satz (eine Ablehnung, eine Grammatik) behält
    ihn; ein Feld ohne Namen heißt danach wie die Zeile.
    """
    inherited = field.accessibleDescription()
    field.setToolTip(sentence)
    field.setAccessibleDescription(sentence)
    if caption is not None:
        caption.setToolTip(sentence)
        caption.setAccessibleDescription(sentence)
    for widget in inputs_of(field):
        if widget is not field:
            if not widget.toolTip():
                widget.setToolTip(sentence)
            if widget.accessibleDescription() in ("", inherited):
                widget.setAccessibleDescription(sentence)
    name_inputs(field, caption_text(caption))


def explain_row(form: QFormLayout, field: QWidget, sentence: str) -> None:
    """:func:`explain` für eine Zeile, deren Beschriftung das Formular kennt."""
    explain(field, form.labelForField(field), sentence)


def unnamed_inputs(root: QWidget) -> list[str]:
    """Die Eingabefelder unter ``root`` ohne zugänglichen Namen — für den Wächter.

    Je Fund die Klasse und, wo es einen gibt, der Objektname oder das
    Ziel des Prüfstands, damit die Meldung die Stelle nennt.
    """
    return [
        _described(widget)
        for widget in root.findChildren(QWidget)
        if _is_input(widget) and not widget.accessibleName().strip()
    ]


def repeated_names(root: QWidget, ignore: Iterable[QWidget] = ()) -> list[str]:
    """Zugängliche Namen, die zwei Eingabefelder unter ``root`` tragen."""
    skipped = {id(widget) for widget in ignore}
    seen: dict[str, int] = {}
    for widget in root.findChildren(QWidget):
        if id(widget) in skipped or not _is_input(widget):
            continue
        name = widget.accessibleName().strip()
        if name:
            seen[name] = seen.get(name, 0) + 1
    return sorted(name for name, count in seen.items() if count > 1)


def _described(widget: QWidget) -> str:
    target = widget.property(guides.TARGET_PROPERTY)
    where = widget.objectName() or (str(target) if target else "")
    return f"{type(widget).__name__}({where})" if where else type(widget).__name__
