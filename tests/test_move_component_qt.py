"""Das Verschiebewerkzeug im Komponentenmodus und Qt: was nach einem Schnitt anders wirkte, obwohl
die Rümpfe gleich blieben (Review 1 über Paket M, RM-M2 und RM-M8; ``tools/move_qt.py``).

Je Fall drei Belege: Der Planer weist den Schnitt vor dem Schreiben ab (mit Ausweg); der Beweis ist
an dem von Hand gebauten Baum rot, den die Ersetzungsliste ohne diese Prüfung ergäbe; und eine
Laufzeitsonde (QtCore, ``offscreen``, eigener Prozess, alter gegen diesen Baum) zeigt, dass sich
das Verhalten dort ändert — die Abweisung ist nötig, nicht nur streng. Die erlaubte Form
(``eventFilter`` wandert mit seiner Installation) schreibt das Werkzeug, und die Sonde misst
dasselbe Verhalten wie vorher.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names, move_proof

EXPECTED = fx.changed_tree(fx.COMPONENT_OLD, fx.COMPONENT_NEW)
AREA = "app/ui/board_area.py"
BOARD = "app/ui/board.py"
RECORDER_PATH = "tests/test_recorder.py"
FILTER_HEAD = "    def eventFilter(self, watched: QObject, event: object) -> bool:\n"
CONNECT = "        self.session.changed.connect(self._on_changed)\n"

#: Die Sonde: Qt-Verhalten des Bretts in einem Baum, vorher am Wirt, nachher an der Komponente.
PROBE = '''\
"""Sonde: Qt-Verhalten des Bretts in einem Baum (alt oder geschrieben)."""

import json
import sys

tree, mode = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
import app

assert app.__file__ is not None and app.__file__.startswith(tree), app.__file__
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimerEvent, Signal

from app.ui.board import Board
from app.ui.session import Session

application = QCoreApplication.instance() or QCoreApplication([])
session = Session()


def holder(window, name):
    """Wer ``name`` trägt: nach dem Schnitt die Komponente, vorher der Wirt."""
    area = window.area
    return area if hasattr(type(area), name) or name in vars(area) else window


class Source(QObject):
    fired = Signal()


if mode == "subclass":
    from tests.test_recorder import Recorder

    window = Recorder(session)
    session.changed.emit()
    result = window.calls
else:
    window = Board(session)
    if mode == "sender":
        source = Source()
        source.fired.connect(holder(window, "on_signal").on_signal)
        source.fired.emit()
        result = holder(window, "seen_sender").seen_sender is source
    elif mode == "timer":
        QCoreApplication.sendEvent(window, QTimerEvent(1))
        result = holder(window, "ticks").ticks
    elif mode == "logging":
        import logging

        seen = []

        class Collect(logging.Handler):
            def emit(self, record):
                seen.append(record.getMessage())

        logger = logging.getLogger("move-names.probe")
        logger.propagate = False
        logger.addHandler(Collect())
        logger.addFilter(window)
        logger.warning("durch den Filter?")
        result = not seen
    elif mode == "mixin":
        result = window.run() == 1
    else:
        if mode == "watch":
            holder(window, "watch").watch()
        elif mode == "filter-tool":
            from tools.filter_tool import attach_filter

            attach_filter(window)
        QCoreApplication.sendEvent(session, QEvent(QEvent.Type.User))
        result = holder(window, "filtered").filtered
window.release()
print(json.dumps({"result": result}))
'''

#: Eine Unterklasse des Wirts in den Tests, die eine verschobene Methode überschreibt.
RECORDER = (
    '"""Eine Unterklasse des Bretts, die zählt, wie oft bump gerufen wird."""\n\n'
    "from app.ui.board import Board\n\n\n"
    "class Recorder(Board):\n"
    "    calls = 0\n\n"
    "    def bump(self) -> None:\n"
    "        self.calls += 1\n"
)
#: Dieselbe Überschreibung eine Klasse tiefer.
RECORDER_DEEP = (
    '"""Eine Unterklasse der Unterklasse überschreibt bump."""\n\n'
    "from app.ui.board import Board\n\n\n"
    "class Recorder(Board):\n"
    "    calls = 0\n\n\n"
    "class Deeper(Recorder):\n"
    "    def bump(self) -> None:\n"
    "        self.calls += 1\n"
)


def _cut(
    methods: tuple[str, ...] = (), own: tuple[str, ...] = (), parent: tuple[str, ...] = ()
) -> str:
    """Der Zuschnitt der Attrappe mit weiteren Methoden, eigenen und ererbten Membern."""
    cut = fx.COMPONENT_CUT
    for key, extra in (("methods", methods), ("own_attributes", own), ("parent_members", parent)):
        if not extra:
            continue
        start = cut.index(f"{key} = [")
        end = cut.index("]", start)
        cut = cut[:end] + "".join(f', "{name}"' for name in extra) + cut[end:]
    return cut


def _insert_method(files: dict[str, str], path: str, method: str) -> dict[str, str]:
    """``method`` vor ``eventFilter`` der Klasse in ``path``."""
    return fx.edit(files, path, FILTER_HEAD, method + "\n" + FILTER_HEAD)


def _counting_filter(files: dict[str, str], path: str) -> dict[str, str]:
    return fx.edit(
        files, path, "        return False\n", "        self.filtered += 1\n        return False\n"
    )


#: Sonde k4 aus Review 2 (RM-M17): Ein Werkzeug installiert das Brett über einen Parameter ohne
#: Annotation als Filter — der Auflöser kennt den Empfänger nicht.
FILTER_TOOL_PATH = "tools/filter_tool.py"
FILTER_TOOL = (
    '"""Installiert das Brett als Ereignisfilter seiner Sitzung."""\n\n\n'
    "def attach_filter(window) -> None:\n    window.session.installEventFilter(window)\n"
)
COUNT = "        self.count = 0\n"
AREA_COUNT = "        self.area.count = 0\n"
#: Der Baum vor dem Schnitt mit zählendem Filter und dem Werkzeug.
FILTER_TOOL_OLD = fx.edit(
    _counting_filter(fx.COMPONENT_OLD | {FILTER_TOOL_PATH: FILTER_TOOL}, BOARD),
    BOARD,
    COUNT,
    COUNT + "        self.filtered = 0\n",
)


#: Sonden k3d und k3e aus Review 2 (RM-M19): Überschreibungen einer Basis, die nicht Qt ist.
LOGGING_FILTER = "    def filter(self, record: object) -> bool:\n        return False\n"
MIXIN = (
    "class Mixin:\n    def run(self) -> int:\n        return self.step()\n\n"
    "    def step(self) -> int:\n        return 0\n\n\n"
)
STEP = "    def step(self) -> int:\n        return 1\n"
HOST_CLASS = "class Board(QObject):\n"
SUPER = "        super().__init__()\n"


def _logging_base(files: dict[str, str], anchor: str) -> dict[str, str]:
    """Das Brett erbt zusätzlich von ``logging.Filter`` (``anchor``: die Zeile, vor die der
    Import gehört)."""
    files = fx.edit(files, BOARD, HOST_CLASS, "class Board(QObject, logging.Filter):\n")
    files = fx.edit(files, BOARD, anchor, "import logging\n" + anchor)
    return fx.edit(files, BOARD, SUPER, SUPER + "        logging.Filter.__init__(self)\n")


def _mixin_base(files: dict[str, str]) -> dict[str, str]:
    return fx.edit(files, BOARD, HOST_CLASS, MIXIN + "class Board(QObject, Mixin):\n")


MIXIN_KEEP = (
    '\n[[accesses]]\npath = "app/ui/board.py"\nscope = "Mixin.run"\nmember = "step"\n'
    'decision = "keep"\n'
)


def _cases() -> list[tuple[str, dict[str, str], str, dict[str, str], str, str]]:
    """(Name, alter Baum, Zuschnitt, Baum nach der Ersetzungsliste allein, Sonde, Meldung)."""
    sender = "    def on_signal(self) -> None:\n        self.seen_sender = self.sender()\n"
    timer = "    def timerEvent(self, event: object) -> None:\n        self.ticks += 1\n"
    count = "        self.count = 0\n"
    area_count = "        self.area.count = 0\n"
    return [
        (
            "sender",
            fx.edit(
                _insert_method(fx.COMPONENT_OLD, BOARD, sender),
                BOARD,
                count,
                count + "        self.seen_sender = None\n",
            ),
            _cut(("on_signal",), ("seen_sender",), ("sender",)),
            fx.edit(
                _insert_method(
                    EXPECTED, AREA, sender.replace("self.sender", "self._parent.sender")
                ),
                BOARD,
                area_count,
                area_count + "        self.area.seen_sender = None\n",
            ),
            "sender",
            "self.sender() in Board.on_signal gilt dem Empfänger eines Signals",
        ),
        (
            "qt-überschreibung",
            fx.edit(
                _insert_method(fx.COMPONENT_OLD, BOARD, timer),
                BOARD,
                count,
                count + "        self.ticks = 0\n",
            ),
            _cut(("timerEvent",), ("ticks",)),
            fx.edit(
                _insert_method(EXPECTED, AREA, timer),
                BOARD,
                area_count,
                area_count + "        self.area.ticks = 0\n",
            ),
            "timer",
            "timerEvent überschreibt eine Methode der Qt-Basis",
        ),
        (
            "filter-vom-wirt-installiert",
            _counting_filter(
                fx.edit(
                    fx.COMPONENT_OLD,
                    BOARD,
                    CONNECT,
                    CONNECT
                    + "        self.filtered = 0\n        self.session.installEventFilter(self)\n",
                ),
                BOARD,
            ),
            _cut(own=("filtered",)),
            _counting_filter(
                fx.edit(
                    EXPECTED,
                    BOARD,
                    CONNECT,
                    CONNECT
                    + "        self.area.filtered = 0\n"
                    + "        self.session.installEventFilter(self)\n",
                ),
                AREA,
            ),
            "filter",
            "app/ui/board.py:32: installiert den Wirt Board als Ereignisfilter",
        ),
        (
            "filter-über-offenen-empfänger",
            FILTER_TOOL_OLD,
            _cut(own=("filtered",)),
            fx.edit(
                _counting_filter(EXPECTED | {FILTER_TOOL_PATH: FILTER_TOOL}, AREA),
                BOARD,
                AREA_COUNT,
                AREA_COUNT + "        self.area.filtered = 0\n",
            ),
            "filter-tool",
            "tools/filter_tool.py:5: installiert window als Ereignisfilter, und eventFilter "
            "wandert — ob das der Wirt ist, bleibt offen",
        ),
        (
            "basis-logging-filter",
            _insert_method(
                _logging_base(fx.COMPONENT_OLD, "import weakref\n"), BOARD, LOGGING_FILTER
            ),
            _cut(("filter",)),
            _insert_method(
                _logging_base(EXPECTED, "from typing import TYPE_CHECKING\n"), AREA, LOGGING_FILTER
            ),
            "logging",
            "filter überschreibt logging.Filter",
        ),
        (
            "basis-eigenes-mixin",
            _insert_method(_mixin_base(fx.COMPONENT_OLD), BOARD, STEP),
            _cut(("step",)),
            _insert_method(_mixin_base(EXPECTED), AREA, STEP),
            "mixin",
            "step überschreibt app.ui.board.Mixin",
        ),
        (
            "basis-eigenes-mixin-erklärt",
            _insert_method(_mixin_base(fx.COMPONENT_OLD), BOARD, STEP),
            _cut(("step",)) + MIXIN_KEEP,
            _insert_method(_mixin_base(EXPECTED), AREA, STEP),
            "mixin",
            "step überschreibt app.ui.board.Mixin",
        ),
        (
            "unterklasse",
            fx.COMPONENT_OLD | {RECORDER_PATH: RECORDER},
            fx.COMPONENT_CUT,
            EXPECTED | {RECORDER_PATH: RECORDER},
            "subclass",
            "tests/test_recorder.py:6: Recorder erbt von Board und definiert bump",
        ),
        (
            "unterklasse-tiefer",
            fx.COMPONENT_OLD | {RECORDER_PATH: RECORDER_DEEP},
            fx.COMPONENT_CUT,
            EXPECTED | {RECORDER_PATH: RECORDER_DEEP},
            "",
            "tests/test_recorder.py:10: Deeper erbt von Board und definiert bump",
        ),
    ]


IDS = [case[0] for case in _cases()]


def _run(tmp_path: Path, files: dict[str, str], cut: str) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _probe(tmp_path: Path, root: Path, mode: str) -> object:
    script = tmp_path / "qt_probe.py"
    script.write_text(PROBE, encoding="utf-8")
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPATH", None)
    done = subprocess.run(
        [sys.executable, str(script), str(root), mode],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    found: dict[str, object] = json.loads(done.stdout.strip().splitlines()[-1])
    return found["result"]


@pytest.mark.parametrize(("label", "old", "cut", "naive", "mode", "where"), _cases(), ids=IDS)
def test_a_cut_qt_would_see_differently_is_rejected(
    tmp_path: Path,
    label: str,
    old: dict[str, str],
    cut: str,
    naive: dict[str, str],
    mode: str,
    where: str,
) -> None:
    """Vor dem Schreiben abgewiesen, mit Stelle und Ausweg; der Baum bleibt unverändert."""
    root, result = _run(tmp_path, old, cut)
    assert result.status == "rejected", (label, result.status, result.problems)
    assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in old.items()}
    assert all(" — " in problem for problem in result.problems), result.problems
    assert where in "\n".join(result.problems), (label, result.problems)


@pytest.mark.parametrize(("label", "old", "cut", "naive", "mode", "where"), _cases(), ids=IDS)
def test_the_proof_is_red_on_the_tree_the_replacement_list_alone_gives(
    tmp_path: Path,
    label: str,
    old: dict[str, str],
    cut: str,
    naive: dict[str, str],
    mode: str,
    where: str,
) -> None:
    """Der Beweis sieht dasselbe am fertigen Baum, ohne den Planer."""
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut, encoding="utf-8")
    proof = move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", naive),
    )
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


@pytest.mark.parametrize(
    ("label", "old", "cut", "naive", "mode", "where"),
    [case for case in _cases() if case[4]],
    ids=[case[0] for case in _cases() if case[4]],
)
def test_that_tree_behaves_differently_at_runtime(
    tmp_path: Path,
    label: str,
    old: dict[str, str],
    cut: str,
    naive: dict[str, str],
    mode: str,
    where: str,
) -> None:
    """Die Gegenprobe zur Abweisung: Alter Baum und Baum nach der Ersetzungsliste allein messen
    an der Sonde Verschiedenes — ``sender()`` liefert ``None``, Qt ruft ``timerEvent`` nicht,
    niemand filtert, die Überschreibung der Unterklasse läuft nicht."""
    before = _probe(tmp_path, fx.write_tree(tmp_path / "old", old), mode)
    after = _probe(tmp_path, fx.write_tree(tmp_path / "naive", naive), mode)
    assert before in (True, 1), (label, before)
    assert after != before, (label, before, after)


#: Eigene Gegenproben zu RM-M17: (Name, Werkzeug, Erklärung, Ausgang, Meldung).
FILTER_FORMS = [
    (
        "attribut-eines-objekts",
        '"""Hält Besitzer und Ziel."""\n\n\nclass Attach:\n'
        "    def __init__(self, owner: object, target: object) -> None:\n"
        "        self.owner = owner\n        self.target = target\n\n"
        "    def run(self) -> None:\n"
        "        self.target.installEventFilter(self.owner)  # type: ignore[attr-defined]\n",
        "",
        "rejected",
        "installiert self.owner als Ereignisfilter, und eventFilter wandert — ob das der Wirt "
        "ist, bleibt offen",
    ),
    (
        "annotiert-als-wirt",
        '"""Installiert das Brett."""\n\nfrom app.ui.board import Board\n\n\n'
        "def attach_filter(window: Board) -> None:\n"
        "    window.session.installEventFilter(window)\n",
        "",
        "rejected",
        "installiert den Wirt Board als Ereignisfilter",
    ),
    (
        "annotiert-fremd",
        '"""Installiert eine Meldung."""\n\nfrom app.ui.toast import Toast\n\n\n'
        "def attach_filter(target: object, toast: Toast) -> None:\n"
        "    target.installEventFilter(toast)  # type: ignore[attr-defined]\n",
        "",
        "written",
        "",
    ),
    ("erklärt-kein-wirt", FILTER_TOOL, "keep", "written", ""),
    (
        "erklärt-als-wirt",
        FILTER_TOOL,
        "component",
        "rejected",
        "installiert den Wirt Board als Ereignisfilter",
    ),
]


@pytest.mark.parametrize(
    ("label", "tool", "decision", "status", "where"),
    FILTER_FORMS,
    ids=[form[0] for form in FILTER_FORMS],
)
def test_a_filter_installation_is_judged_never_skipped(
    tmp_path: Path, label: str, tool: str, decision: str, status: str, where: str
) -> None:
    """RM-M17: Wo ein Filter installiert wird, entscheidet der Nachweis (Auflöser, Annotation)
    oder eine Erklärung in ``[[accesses]]`` (Member ``eventFilter``) — was offen bleibt, hält an;
    nur was nachweislich nicht der Wirt ist, lässt ``eventFilter`` wandern."""
    cut = _cut(own=("filtered",))
    if decision:
        cut += (
            f'\n[[accesses]]\npath = "{FILTER_TOOL_PATH}"\nscope = "attach_filter"\n'
            f'member = "eventFilter"\ndecision = "{decision}"\n'
        )
    files = FILTER_TOOL_OLD | {FILTER_TOOL_PATH: tool}
    root, result = _run(tmp_path, files, cut)
    assert result.status == status, (label, result.status, result.problems)
    if status == "rejected":
        assert where in "\n".join(result.problems), (label, result.problems)
        assert all(" — " in problem for problem in result.problems), result.problems
        assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in files.items()}


#: Eigene Gegenproben zu RM-M19: eine eigene Basis über zwei Dateien, ein eigenes Attribut, das
#: auch eine eigene Basis setzt, und eine weitere fremde Basis (``json.JSONEncoder``).
STEP_BASE = {
    "app/ui/steps.py": '"""Erste Stufe."""\n\n\nclass StepBase:\n'
    "    def step(self) -> int:\n        return 0\n",
    "app/ui/steps_middle.py": '"""Zweite Stufe."""\n\nfrom app.ui.steps import StepBase\n\n\n'
    "class Middle(StepBase):\n    pass\n",
}
COUNTER = "class Counter:\n    def reset(self) -> None:\n        self.count = 0\n\n\n"
DEFAULT = "    def default(self, o: object) -> object:\n        return str(o)\n"
BASE_FORMS = [
    (
        "eigene-basis-über-zwei-dateien",
        fx.edit(
            fx.edit(
                _insert_method(fx.COMPONENT_OLD | STEP_BASE, BOARD, STEP),
                BOARD,
                HOST_CLASS,
                "class Board(QObject, Middle):\n",
            ),
            BOARD,
            "from app.ui.flow import Flow\n",
            "from app.ui.flow import Flow\nfrom app.ui.steps_middle import Middle\n",
        ),
        _cut(("step",)),
        "step überschreibt app.ui.steps.StepBase",
    ),
    (
        "eigenes-attribut-der-basis",
        fx.edit(fx.COMPONENT_OLD, BOARD, HOST_CLASS, COUNTER + "class Board(QObject, Counter):\n"),
        fx.COMPONENT_CUT,
        "das eigene Attribut count kennt auch die Basis app.ui.board.Counter",
    ),
    (
        "fremde-basis-json",
        fx.edit(
            fx.edit(
                _insert_method(fx.COMPONENT_OLD, BOARD, DEFAULT),
                BOARD,
                HOST_CLASS,
                "class Board(QObject, json.JSONEncoder):\n",
            ),
            BOARD,
            "import weakref\n",
            "import json\nimport weakref\n",
        ),
        _cut(("default",)),
        "default überschreibt json.JSONEncoder",
    ),
]


@pytest.mark.parametrize(
    ("label", "old", "cut", "where"), BASE_FORMS, ids=[form[0] for form in BASE_FORMS]
)
def test_an_override_of_any_base_is_rejected_and_red(
    tmp_path: Path, label: str, old: dict[str, str], cut: str, where: str
) -> None:
    """RM-M19: Jede Basis zählt — fremd über ``dir``, eigen über ihren Rumpf, auch über eine
    Zwischenklasse in einer anderen Datei. Der Planer weist ab, der Beweis ist rot."""
    _root, result = _run(tmp_path / "plan", old, cut)
    assert result.status == "rejected", (label, result.status, result.problems)
    assert where in "\n".join(result.problems), (label, result.problems)
    assert all(" — " in problem for problem in result.problems), result.problems
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut, encoding="utf-8")
    proof = move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", EXPECTED),
    )
    assert any(where in error for error in proof.errors), (label, proof.errors)


def test_an_event_filter_that_moves_with_its_installation_keeps_filtering(tmp_path: Path) -> None:
    """Installiert eine verschobene Methode den Filter, zieht ``eventFilter`` mit: Das Werkzeug
    schreibt, und die Sonde misst am geschriebenen Baum denselben Filter wie vorher."""
    watch = "    def watch(self) -> None:\n        self.session.installEventFilter(self)\n"
    old = _counting_filter(
        fx.edit(
            _insert_method(fx.COMPONENT_OLD, BOARD, watch),
            BOARD,
            "        self.count = 0\n",
            "        self.count = 0\n        self.filtered = 0\n",
        ),
        BOARD,
    )
    before = _probe(tmp_path, fx.write_tree(tmp_path / "old", old), "watch")
    root, result = _run(tmp_path, old, _cut(("watch",), ("filtered",)))
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert "        self._host.session.installEventFilter(self)\n" in (root / AREA).read_text(
        encoding="utf-8"
    )
    assert before == 1
    assert _probe(tmp_path, root, "watch") == before
