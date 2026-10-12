"""Fensterfunde des Prüfstands (RM-737, Funktionsdurchgang D0-P).

Was der Prüfstand beim Lauf über den Wortschatz an der Anwendung fand: der
Abriss des Objektbaums nach der Suche einer Zeile, der Überstand der linken
Karte über ihren Abschnitt und die halb abgeschnittene Zeile. Die Auflösung
des Wortschatzes selbst prüft ``tests/test_guide_targets.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations

load_operations()


def _settle(qt_app: Any, rounds: int = 20) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


#: Der Kindprozess des Abrisstests: Anwendung wie beim Kunden, Szene vom
#: Startbildschirm öffnen, die Zeile über den Wortschatz suchen und bis zum Ende
#: der Runde halten, dann neu öffnen. ``SOLIDON_PROBE_ITERATOR=1`` setzt die
#: frühere Suche über ``QTreeWidgetItemIterator`` ein — die Gegenprobe.
_TREE_ROUNDS = r"""
import os
import sys
import time
from pathlib import Path
import app.ui
from app.core.bootstrap import load_operations
load_operations()
from app.ui.app import build_application
from app.ui import guide_targets
application, window = build_application([])
window.resize(1920, 1032)
window.show()
if os.environ.get('SOLIDON_PROBE_ITERATOR'):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItemIterator
    original = guide_targets._row

    def _row(window, kind, rest, name):
        if kind != 'tree.row':
            return original(window, kind, rest, name)
        tree = window.object_tree.tree
        object_id, feature_id = guide_targets._object_and_feature(rest)
        iterator = QTreeWidgetItemIterator(tree)
        while (item := iterator.value()) is not None:
            if item.data(0, Qt.ItemDataRole.UserRole) == object_id and (
                item.data(1, Qt.ItemDataRole.UserRole) == feature_id
            ):
                return tree, item
            iterator += 1
        raise guide_targets.MissingTargetError(name)

    guide_targets._row = _row


def settle(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        application.processEvents()
        time.sleep(0.005)


scene = Path(sys.argv[1])
if sys.argv[2] == 'build':
    from app.core.scene.history import OperationDraft
    window._show_start_screen(False)
    assert window.session.apply('Quader mit Bohrung', [
        OperationDraft(op='create_brep_box'),
        OperationDraft(op='drill_hole', inputs=('obj_1',), params={'diameter': 5.0, 'z': 12.0}),
    ])
    assert window.session.wait_for_idle(60000)
    window.session.save_project(scene)
    print('built', flush=True)
    os._exit(0)
for round in range(5):
    previous = window.session.last_result
    window.session.forget_changes()
    window.open_path(scene)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        settle(0.01)
        result = window.session.last_result
        if result is not None and result is not previous and not window.session.busy:
            break
    settle(0.5)
    held = guide_targets._row(window, 'tree.row', 'obj_1.hole_1', 'tree.row:obj_1.hole_1')
    guide_targets.next_click(window, 'tree.row:obj_1.hole_1')
    settle(0.8)
    held = None
print('tree survived', flush=True)
window.session.forget_changes()
from tools.window_bench import shutdown_window
shutdown_window(window, application)
"""


def _tree_rounds(scene: Path, mode: str, extra: dict[str, str] | None = None) -> Any:
    import os
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", _TREE_ROUNDS, str(scene), mode],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", **(extra or {})},
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_the_tree_survives_new_scenes_after_a_row_was_found(qt_app: Any, tmp_path: Path) -> None:
    """Nach der Suche einer Baumzeile riss ein späteres ``ObjectTree.show_scene``
    beim Leeren des Baums ab (Zugriffsverletzung in ``tree.clear()``), solange
    ``_row`` sie mit ``QTreeWidgetItemIterator`` suchte (Fund D0-P: 8 von 12
    Läufen des Prüfstands). Im eigenen Prozess, damit ein Abriss ein roter Fall
    ist und nicht die Suite beendet; sechs Prozesse zu je fünf Öffnungen, weil
    er nicht jedes Mal kommt (Gegenprobe mit dem Iterator: 3 von 8 Prozessen)."""
    del qt_app
    scene = tmp_path / "szene.p3d"
    built = _tree_rounds(scene, "build")
    assert built.returncode == 0 and "built" in built.stdout, built.stderr[-3000:]
    for attempt in range(6):
        done = _tree_rounds(scene, "rounds")
        assert done.returncode == 0, (attempt, done.returncode, done.stderr[-4000:])
        assert "tree survived" in done.stdout


def tree_iterator_uses(source: str) -> list[int]:
    """Die Zeilen, in denen ``QTreeWidgetItemIterator`` als Name vorkommt — Import,
    Aufruf oder Attribut, nicht im Kommentar."""
    import ast

    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        named = (
            node.id
            if isinstance(node, ast.Name)
            else node.attr
            if isinstance(node, ast.Attribute)
            else node.name
            if isinstance(node, ast.alias)
            else ""
        )
        if named == "QTreeWidgetItemIterator":
            lines.add(getattr(node, "lineno", 0))
    return sorted(lines)


def test_no_tree_item_iterator_in_the_application() -> None:
    """``QTreeWidgetItemIterator`` hinterlässt in PySide Zeilenhüllen, an denen ein
    späteres ``QTreeWidget.clear()`` abreißt (Fund D0-P); Zeilen werden über
    ``topLevelItem``/``child`` gesucht. Rekursiv über ``app/`` und ``tools/``
    (W4): Prüfstand und Aufnahmen laufen im Prozess der Anwendung, ein Iterator
    dort risse denselben Baum ab (Nachprüfung D0-W, N4)."""
    root = Path(__file__).resolve().parents[1]
    found = [
        f"{path.relative_to(root).as_posix()}:{number}"
        for folder in ("app", "tools")
        for path in sorted((root / folder).rglob("*.py"))
        for number in tree_iterator_uses(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_a_tree_item_iterator_turns_the_guard_red() -> None:
    source = (
        "from PySide6.QtWidgets import QTreeWidgetItemIterator\n"
        "# QTreeWidgetItemIterator im Kommentar zählt nicht\n"
        "def walk(tree):\n"
        "    return QtWidgets.QTreeWidgetItemIterator(tree)\n"
    )
    assert tree_iterator_uses(source) == [1, 4]


def test_hidden_rows_take_no_height(qt_app: Any) -> None:
    """Eine versteckte Zeile ist nicht zu sehen und braucht keinen Platz.

    Der Verlauf klappt die Teilschritte einer Transaktion ein, indem er ihre
    Zeilen versteckt. ``overlay.rows_height`` zählte sie trotzdem mit der
    Wunschhöhe einer Zeile, und ``overlay.natural_height`` meldete die linke
    Karte damit um zwei Zeilen zu hoch — so hoch, dass der doppelt abgezogene
    Spaltenkopf des Objektbaums (Fund D0-P) nur bei kurzen Titeln auffiel.
    Ohne Fenster: eine Rechnung über Zeilen."""
    from PySide6.QtWidgets import QListWidget, QTreeWidget, QTreeWidgetItem

    from app.ui.overlay import rows_height

    del qt_app
    one = QListWidget()
    one.addItem("Schritt 1")
    folded = QListWidget()
    for text in ("Schritt 1", "Teil a", "Teil b"):
        folded.addItem(text)
    folded.item(1).setHidden(True)
    folded.item(2).setHidden(True)
    assert rows_height(folded) == rows_height(one)

    single = QTreeWidget()
    single.addTopLevelItem(QTreeWidgetItem(["Körper"]))
    hiding = QTreeWidget()
    for text in ("Körper", "Versteckt"):
        hiding.addTopLevelItem(QTreeWidgetItem([text]))
    hiding.topLevelItem(1).setHidden(True)
    assert rows_height(hiding) == rows_height(single)


def test_the_history_asks_only_for_the_rows_it_shows(qt_app: Any) -> None:
    """Ein eingeklappter Sammelschritt ist im Verlauf eine Zeile, und so viel
    Höhe verlangt der Verlauf auch — nicht die seiner versteckten Teilschritte,
    die der Objektbaum und die Parameter darüber dann nicht bekamen."""
    from app.ui.panels import HistoryPanel, row_height_of, view_chrome

    del qt_app
    panel = HistoryPanel()
    for text in ("1–2  Quader mit Bohrung", "    1  Quader", "    2  Bohrung"):
        panel.list.addItem(text)
    panel.list.item(1).setHidden(True)
    panel.list.item(2).setHidden(True)
    expected = panel._timeline_height() + view_chrome(panel.list) + row_height_of(panel.list)
    assert panel.wanted_height() == expected


#: Der Kindprozess des Überstandstests: Anwendung wie beim Kunden (mit Stilblatt
#: und Einstellungen — im nackten Fenster stand *Vorher/Nachher* nicht da), erst
#: die Fenstergröße, dann ein Körper mit Bohrung, aufgeklappt per Klick.
#: ``SOLIDON_PROBE_OLD_HISTORY=1`` setzt die frühere Höhenmeldung des Verlaufs
#: ohne den Abstand ein, ``SOLIDON_PROBE_OLD_NATURAL=1`` den doppelt
#: abgezogenen Spaltenkopf — die Gegenproben.
_SECTIONS = r"""
import os
import sys
import time
import app.ui
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from app.core.bootstrap import load_operations
load_operations()
from app.ui.app import build_application
application, window = build_application([])
from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.ui import overlay
from app.ui.overlay import extra_height, is_room_taker, living
from app.ui.panels import HistoryPanel
if os.environ.get('SOLIDON_PROBE_OLD_HISTORY'):
    def _old(self):
        if self.compare.isHidden():
            return 0
        return self.compare.sizeHint().height() + (
            self.timeline.sizeHint().height() if self.compare.isChecked() else 0
        )
    HistoryPanel._timeline_height = _old
if os.environ.get('SOLIDON_PROBE_OLD_NATURAL'):
    from PySide6.QtWidgets import QHeaderView
    _natural = overlay.natural_height

    def _with_headers(zone, width=None):
        wanted = _natural(zone, width)
        for view in living(zone, QHeaderView):
            if view.isVisibleTo(zone):
                needs = max(overlay.rows_height(view), view.minimumHeight())
                given = min(
                    max(view.sizeHint().height(), view.minimumHeight()), view.maximumHeight()
                )
                wanted += needs - given
        return wanted
    overlay.natural_height = _with_headers


def settle(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        application.processEvents()
        time.sleep(0.005)


# Wie beim Kunden: erst die Größe, dann ein Körper mit Bohrung, aufgeklappt per
# Klick auf das Dreieck — ohne Größenwechsel danach, der die Karte neu legte.
width, height, body = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
window.resize(width, height)
window.show()
window._show_start_screen(False)
zone = window.overlay.left
tree = window.object_tree.tree
section = window.object_tree.parentWidget()
problems = []
checked = 0


def check(label):
    global checked
    takers = [
        child for child in living(zone, QWidget)
        if is_room_taker(child) and child.isVisibleTo(zone)
    ]
    floors = sum(child.least_height() for child in takers)
    if extra_height(zone) + floors > window.overlay.card_room():
        return
    checked += 1
    for child in takers:
        holder = child.parentWidget()
        if holder.height() < holder.minimumSizeHint().height():
            least = holder.minimumSizeHint().height()
            problems.append((label, type(child).__name__, holder.height(), least))
    bottom = tree.mapTo(section, QPoint(0, tree.height())).y()
    if bottom > section.height():
        problems.append((label, 'Baum', bottom, section.height()))


if REGISTRY.has(body):
    assert window.session.apply('Quader mit Bohrung', [
        OperationDraft(op=body),
        OperationDraft(op='drill_hole', inputs=('obj_1',), params={'diameter': 5.0, 'z': 12.0}),
    ])
    assert window.session.wait_for_idle(60000)
    settle(0.8)
    # Kein Blick vor dem Aufklappen: Wer die Größen der Abschnitte erfragt,
    # poliert den Spaltenkopf, und an dessen frühem Wunsch hing der Fehler.
    item = tree.topLevelItem(0)
    rect = tree.visualItemRect(item)
    arrow = QPoint(rect.left() - tree.indentation() // 2, rect.center().y())
    QTest.mouseClick(
        tree.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, arrow
    )
    settle(1.0)
    check('auf')
print('geprüft', checked, flush=True)
print('probleme', problems, flush=True)
window.session.forget_changes()
from tools.window_bench import shutdown_window
shutdown_window(window, application)
"""


def _sections(size: tuple[int, int], body: str, extra: dict[str, str] | None = None) -> Any:
    import os
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", _SECTIONS, str(size[0]), str(size[1]), body],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", **(extra or {})},
        capture_output=True,
        text=True,
        timeout=600,
    )


#: Die kleinste Fläche (``function_checks.SMALLEST_WINDOW``, 1920 x 1080 logisch
#: maximiert, Taskleiste ab) und eine größere — darunter wird nie gemessen.
_SECTION_SIZES = ((1920, 1032), (2560, 1392))


def test_the_object_tree_stays_inside_its_section_when_the_card_is_tight(qt_app: Any) -> None:
    """Die linke Karte teilt ihre Höhe auf Baum, Parameter und Verlauf; passt das
    Ganze, ragt kein Abschnitt über seinen Platz (Funde D0-P). Zwei Ursachen:
    Der Verlauf nahm den Abstand hinter *Vorher/Nachher*, ohne ihn zu melden, und
    ``overlay.natural_height`` zog den Spaltenkopf des Baums ein zweites Mal ab,
    den die Zeilenhöhe des Baums schon enthält — die Karte war 9 Punkte zu
    niedrig, auch in der Startgröße. Je Größe und Körperart ein Prozess mit der
    Anwendung wie beim Kunden."""
    del qt_app
    checked = 0
    for size in _SECTION_SIZES:
        for body in ("create_box", "create_brep_box"):
            done = _sections(size, body)
            assert done.returncode == 0, done.stderr[-3000:]
            assert "probleme []" in done.stdout, (size, body, done.stdout)
            checked += int(done.stdout.split("geprüft", 1)[1].split()[0])
    assert checked >= 4


#: Der Kindprozess des Teilschritttests: Anwendung wie beim Kunden, je
#: Sammelschritt mehrere Quader in einer Transaktion — der Verlauf zeigt eine
#: Zeile und versteckt die Teilschritte, der Objektbaum zeigt jeden Quader.
#: ``SOLIDON_PROBE_OLD_HIDDEN_ROWS=1`` zählt die versteckten Zeilen wieder mit,
#: in ``HistoryPanel.wanted_height``, ``HistoryPanel._fit`` und
#: ``overlay.rows_height`` — die Gegenprobe.
_HIDDEN_STEPS = r"""
import os
import sys
import time
import app.ui
from PySide6.QtWidgets import QListView
from app.core.bootstrap import load_operations
load_operations()
from app.ui.app import build_application
from app.core.scene.history import OperationDraft
from app.ui import overlay
from app.ui.panels import HistoryPanel, fit_to_rows, row_height_of, view_chrome
if os.environ.get('SOLIDON_PROBE_OLD_HIDDEN_ROWS'):
    def _wanted(self):
        return (
            self._timeline_height()
            + view_chrome(self.list)
            + self.list.count() * row_height_of(self.list)
        )

    def _fit(self):
        empty = self.list.count() == 0
        self._empty.setVisible(empty)
        self.list.setVisible(not empty)
        room = None if self._room is None else max(0, self._room - self._timeline_height())
        fit_to_rows(self.list, self.list.count(), room=room)
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    _rows = overlay.rows_height

    def _with_hidden(view):
        total = _rows(view)
        if isinstance(view, QListView):
            total += sum(
                view.sizeHintForRow(row)
                for row in range(view.model().rowCount())
                if view.isRowHidden(row)
            )
        return total

    HistoryPanel.wanted_height = _wanted
    HistoryPanel._fit = _fit
    overlay.rows_height = _with_hidden
application, window = build_application([])


def settle(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        application.processEvents()
        time.sleep(0.005)


width, height, transactions, per = (int(value) for value in sys.argv[1:5])
window.resize(width, height)
window.show()
window._show_start_screen(False)
for number in range(transactions):
    drafts = [
        OperationDraft(op='create_box', params={'width': 10.0 + number + part})
        for part in range(per)
    ]
    assert window.session.apply(f'Quader {number + 1}', drafts)
    assert window.session.wait_for_idle(60000)
settle(1.5)
listing = window.history_panel.list
tree = window.object_tree.tree
hidden = sum(listing.isRowHidden(row) for row in range(listing.count()))
shown = [row for row in range(listing.count()) if not listing.isRowHidden(row)]
used = sum(listing.visualRect(listing.model().index(row, 0)).height() for row in shown)
print('versteckt', hidden, flush=True)
print('leer', listing.viewport().height() - used, row_height_of(listing), flush=True)
print('rollt', tree.verticalScrollBar().maximum(), flush=True)
window.session.forget_changes()
from tools.window_bench import shutdown_window
shutdown_window(window, application)
"""


def _hidden_steps(size: tuple[int, int], scene: tuple[int, int], old: bool) -> dict[str, list[int]]:
    import os
    import subprocess
    import sys

    extra = {"SOLIDON_PROBE_OLD_HIDDEN_ROWS": "1"} if old else {}
    done = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", _HIDDEN_STEPS, *map(str, (*size, *scene))],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", **extra},
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stderr[-3000:]
    return {
        line.split()[0]: [int(value) for value in line.split()[1:]]
        for line in done.stdout.splitlines()
        if line.split() and line.split()[0] in ("versteckt", "leer", "rollt")
    }


#: Je zulässige Fläche ein Verlauf, der in den neuen Stand gerade passt: Quader
#: je Sammelschritt mal Sammelschritte, gemessen ohne Fenster mit DejaVu Sans.
_HIDDEN_CASES = (((1920, 1032), (4, 2)), ((2560, 1392), (6, 2)))


@pytest.mark.parametrize(("size", "scene"), _HIDDEN_CASES, ids=["1920x1032", "2560x1392"])
def test_folded_steps_take_no_room_from_the_object_tree(
    qt_app: Any, size: tuple[int, int], scene: tuple[int, int]
) -> None:
    """Eingeklappte Teilschritte stehen nicht da und nehmen keinen Platz (Fund D0-P).

    Gezählt mit, meldete der Verlauf Höhe für jede versteckte Zeile: Er stand
    mit fünf bis neun leeren Zeilen da, und der Objektbaum darüber rollte. Die
    Gegenprobe setzt die alte Zählung ein und muss an derselben Fläche genau
    diesen Schaden zeigen; sonst prüft der Fall nichts. Gemessen wird an den
    kleinsten zulässigen Flächen und einer größeren — darunter nie.
    """
    del qt_app
    now = _hidden_steps(size, scene, old=False)
    assert now["versteckt"][0] >= scene[0], (
        "keine eingeklappten Teilschritte — der Fall greift nicht"
    )
    blank, row = now["leer"]
    assert blank < row, f"der Verlauf steht mit {blank} px Leere da"
    assert now["rollt"] == [0], "der Objektbaum rollt, obwohl der Platz reichte"

    before = _hidden_steps(size, scene, old=True)
    assert before["leer"][0] >= 3 * before["leer"][1] and before["rollt"][0] > 0, (
        f"die Gegenprobe zeigt den Schaden nicht: {before}"
    )


def test_a_row_cut_off_by_its_parent_is_reached_by_scrolling(qt_app: Any) -> None:
    """Eine Zeile, deren Liste über ihren Elternteil ragt, ist nur halb zu sehen;
    gefragt wird der sichtbare Teil der Liste, nicht ihr ganzes Rechteck (Fund
    D0-P: die letzte Baumzeile hieß „ziel“, obwohl 8 Punkte abgeschnitten waren)."""
    from PySide6.QtWidgets import QListWidget, QWidget

    from app.ui import guide_targets

    host = QWidget()
    host.resize(240, 100)
    listing = QListWidget(host)
    listing.setGeometry(0, 0, 240, 300)
    # Vierzig Zeilen: Die Liste rollt sicher, auch mit der breiten Schrift
    # ohne Fenster.
    for number in range(40):
        listing.addItem(f"Zeile {number}")
    host.show()
    _settle(qt_app, 5)
    try:
        visible = listing.viewport().visibleRegion().boundingRect()
        cut = next(
            listing.item(row)
            for row in range(listing.count())
            if listing.visualItemRect(listing.item(row)).bottom() > visible.bottom()
            and listing.visualItemRect(listing.item(row)).top() <= visible.bottom()
        )
        step = guide_targets._visible_row_click(listing, cut, "history.row:1", "ziel")
        assert (step.why, step.direction) == ("rollen", 1)
        whole = listing.item(0)
        assert guide_targets._visible_row_click(listing, whole, "history.row:1", "ziel").why == (
            "ziel"
        )
    finally:
        host.close()
        host.deleteLater()


def test_a_list_that_cannot_roll_is_never_told_to(qt_app: Any) -> None:
    """Rollen heißt der Schritt nur, wenn ein Mausrad dort etwas bewegt (Fund
    D0-P). Eine Liste, die so hoch ist wie ihre Zeilen, rollt nicht; ragt sie über
    ihren Elternteil, ist der sichtbare Teil der Zeile das Ziel, und eine Zeile
    ganz außerhalb hat keinen Weg."""
    from PySide6.QtWidgets import QListWidget, QWidget

    from app.ui import guide_targets
    from app.ui.overlay import rows_height

    host = QWidget()
    host.resize(240, 100)
    listing = QListWidget(host)
    for number in range(12):
        listing.addItem(f"Zeile {number}")
    listing.setGeometry(0, 0, 240, 100)
    host.show()
    _settle(qt_app, 5)
    listing.setFixedHeight(rows_height(listing))
    listing.move(0, 0)
    _settle(qt_app, 5)
    try:
        bar = listing.verticalScrollBar()
        assert bar.maximum() == 0, "die Liste ist so hoch wie ihre Zeilen"
        visible = listing.viewport().visibleRegion().boundingRect()
        rows = [listing.item(row) for row in range(listing.count())]
        cut = next(
            item
            for item in rows
            if listing.visualItemRect(item).bottom() > visible.bottom()
            and listing.visualItemRect(item).top() <= visible.bottom()
        )
        step = guide_targets._visible_row_click(listing, cut, "history.row:1", "ziel")
        assert step.why == "ziel"
        shown = listing.viewport().mapToGlobal(visible.topLeft())
        assert step.rect.bottom() <= shown.y() + visible.height() - 1, "nur der sichtbare Teil"
        outside = rows[-1]
        assert listing.visualItemRect(outside).top() > visible.bottom()
        with pytest.raises(guide_targets.MissingTargetError, match="rollt"):
            guide_targets._visible_row_click(listing, outside, "history.row:1", "ziel")
    finally:
        host.close()
        host.deleteLater()
