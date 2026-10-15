"""Der Abbau der Qt-Wurzeln, die ein Fenstertest ohne Elternteil baut.

Eine Fixture für mehrere Testdateien, wie ``release_signing.accept_test_signatures``.
Wer sie braucht, bindet sie im Modul an ihren Namen (``roots = qt_roots.roots``),
und pytest findet sie dort. Nicht ``from tests.qt_roots import roots``: Die Tests
tragen ``roots`` als Parameter, und ruff meldet den importierten Namen dann als
neu definiert (F811). Ein eigenes Modul statt ``conftest.py``, ``helpers.py`` oder
``ui_helpers.py``: Eine Änderung hier wählt nur die Dateien, die es importieren,
und nicht die Suite oder Dutzende Fensterdateien (``.claude/rules/tests.md``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, TypeVar

import pytest

_Root = TypeVar("_Root")


@pytest.fixture
def roots(qt_app: Any) -> Iterator[Callable[[_Root], _Root]]:
    """Nimmt die Wurzeln eines Tests, die ohne Elternteil entstehen, und baut sie am
    Testende ab: ``panel = roots(HistoryPanel())``.

    Ein Widget ohne Elternteil ist eine Qt-Wurzel. Dem Sammler überlassen stirbt
    sie in dessen nächstem Lauf, mitten im Bau eines späteren Tests:
    ``test_bench_findings.py``, ``test_overlay.py`` und ``test_tab_windows.py``
    im selben Prozess brachen im Abbau eines gezeigten ``OverlayHost`` nativ ab.
    Abgebaut wird wie in den Fixtures der Suite (``tests/CLAUDE.md``,
    „Stolperfallen“): schließen, ``deleteLater`` vormerken und
    ``DeferredDelete`` zustellen, solange die Hüllen hier noch gehalten werden.
    """
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid

    built: list[Any] = []

    def keep(widget: _Root) -> _Root:
        built.append(widget)
        return widget

    yield keep
    for widget in built:
        if isValid(widget):
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    built.clear()
