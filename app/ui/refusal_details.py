"""Was eine Absage dem Kunden zeigt: Einzelheiten, Schrittwerte, der Weg ins Feld.

Herausgelöst aus ``dialogs.py`` (Codestruktur, Regel 6). Eine Absage spricht in
den Wörtern des Fensters, nicht in denen des Kerns.

* *Eingabe korrigieren* stand im offenen Operationsdialog als Satz, obwohl der
  Dialog selbst die Eingabe ist (FD-95). :func:`field_ways` macht daraus den
  Sprung ins Feld, das der Kern nennt; ohne Feld fällt der Satz weg.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any, Final

from PySide6.QtWidgets import QDialog, QWidget

from app.core.errors import CORRECT_INPUT, PICK_PLANE, AppError

#: Wege, die im offenen Eingabedialog nur eines heißen können: den Cursor in
#: das Feld setzen, das der Kern nennt (``values["field"]``). *Eine andere
#: Ebene wählen* ist am Skizzenschritt derselbe Weg zum Ebenenfeld.
FIELD_WAYS: Final = frozenset({CORRECT_INPUT.id, PICK_PLANE.id})


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

    Der Rückruf hält den Dialog nur schwach: Er hängt am Hinweis, und der
    Hinweis ist ein Kind des Dialogs (``wartezeit.md``, Rückrufe).
    """
    field = str(error.values.get("field") or "")
    if owner is None or not field:
        return {}
    held = weakref.ref(owner)
    wanted = {action.id for action in error.suggestions}

    def jump(_error: AppError) -> None:
        dialog = held()
        if dialog is not None:
            dialog.focus_field(field)

    return dict.fromkeys(FIELD_WAYS & wanted, jump)


def silent_ways(error: AppError, owner: Any | None) -> frozenset[str]:
    """Die Wege, die im offenen Eingabedialog ohne Feld nichts zu sagen haben."""
    if owner is None or error.values.get("field"):
        return frozenset()
    return frozenset(FIELD_WAYS & {action.id for action in error.suggestions})
