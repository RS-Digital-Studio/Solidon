"""Komponentenmodus: Umgeschrieben wird nur, wo der Empfänger nachweislich der Wirt ist (Review 2
über Paket M, RM-M18; ``tools/move_receivers.py``).

Der Fund: Ein verschobenes Member, dessen Name im Baum nur am Wirt definiert ist, galt bei
unbekanntem Empfänger als Zugriff auf den Wirt — ``timer.stop()`` wurde ``timer.area.stop()``,
auch bei ``timer: QTimer``. Fremde Typen tragen dieselben Namen, ohne dass der Baum sie
definiert. Jetzt gilt: Auflöser, dann Annotation; was offen bleibt, verlangt eine Entscheidung in
``[[accesses]]``, und eine Erklärung, die dem Nachweis widerspricht oder nichts entscheidet, ist
selbst ein Fund. Je Fall Planer und Beweis (am Baum, den die alte Regel schrieb).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names, move_proof

EXPECTED = fx.changed_tree(fx.COMPONENT_OLD, fx.COMPONENT_NEW)
BOARD = "app/ui/board.py"
AREA = "app/ui/board_area.py"
TOOL = "tools/timer_tool.py"
FILTER_HEAD = "    def eventFilter(self, watched: QObject, event: object) -> bool:\n"
STOP = "    def stop(self) -> None:\n        self.count = 0\n"
#: ``stop`` wandert mit; im Baum definiert nur der Wirt ein Member ``stop``.
STOP_OLD = fx.edit(fx.COMPONENT_OLD, BOARD, FILTER_HEAD, STOP + "\n" + FILTER_HEAD)
STOP_NEW = fx.edit(EXPECTED, AREA, FILTER_HEAD, STOP + "\n" + FILTER_HEAD)
STOP_CUT = fx.COMPONENT_CUT.replace('"attach", "eventFilter"]', '"attach", "eventFilter", "stop"]')
HEAD = '"""Zeitgeber anhalten."""\n\n'


def _run(
    tmp_path: Path, files: dict[str, str], cut: str = STOP_CUT, *, check: bool = False
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, check=check, work=work, cache=False)


def _rejected(tmp_path: Path, files: dict[str, str], cut: str = STOP_CUT) -> str:
    root, result = _run(tmp_path, files, cut)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in files.items()}
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


def _prove(
    tmp_path: Path, old: dict[str, str], new: dict[str, str], cut: str = STOP_CUT
) -> move_proof.Proof:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut, encoding="utf-8")
    return move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", new),
    )


# ------------------------------------------------------------------ offen: Entscheidung nötig

#: (Name, Werkzeug, Stelle, Baum nach der alten Regel): Der Empfänger ist nicht nachweislich der
#: Wirt. Die ersten drei sind die Sonde k5 des Reviews (ohne Annotation, aus einer Tabelle); die
#: übrigen eigene Gegenproben derselben Klasse: eine Basis des Wirts, ``Any``, ``object`` und ein
#: Attribut eines Objekts lassen es offen.
OPEN_CASES = [
    (
        "k5-parameter",
        "def halt(timer) -> None:\n    timer.stop()\n",
        "tools/timer_tool.py:4: Zugriff auf stop (halt)",
        "timer.area.stop()",
    ),
    (
        "k5-aus-tabelle",
        "def halt(timers: dict[str, object]) -> None:\n    timers['main'].stop()\n",
        "tools/timer_tool.py:4: Zugriff auf stop (halt)",
        "timers['main'].area.stop()",
    ),
    (
        "basis-des-wirts",
        "from PySide6.QtCore import QObject\n\n\ndef halt(item: QObject) -> None:\n"
        "    item.stop()\n",
        "tools/timer_tool.py:7: Zugriff auf stop (halt) — Empfänger nicht nachweislich der Wirt "
        "(PySide6.QtCore.QObject ist eine Basis des Wirts)",
        "item.area.stop()",
    ),
    (
        "any",
        "from typing import Any\n\n\ndef halt(item: Any) -> None:\n    item.stop()\n",
        "tools/timer_tool.py:7: Zugriff auf stop (halt) — Empfänger nicht nachweislich der Wirt "
        "(typing.Any lässt jeden Typ zu)",
        "item.area.stop()",
    ),
    (
        "object",
        "def halt(item: object) -> None:\n    item.stop()  # type: ignore[attr-defined]\n",
        "tools/timer_tool.py:4: Zugriff auf stop (halt) — Empfänger nicht nachweislich der Wirt "
        "(builtins.object lässt jeden Typ zu)",
        "item.area.stop()",
    ),
    (
        "attribut-eines-objekts",
        "class Holder:\n    def halt(self) -> None:\n        self.timer.stop()\n",
        "tools/timer_tool.py:5: Zugriff auf stop (Holder.halt)",
        "self.timer.area.stop()",
    ),
]
OPEN_IDS = [case[0] for case in OPEN_CASES]


@pytest.mark.parametrize(("label", "tool", "where", "naive"), OPEN_CASES, ids=OPEN_IDS)
def test_an_open_receiver_needs_a_decision(
    tmp_path: Path, label: str, tool: str, where: str, naive: str
) -> None:
    """Ohne Erklärung hält der Schnitt an — mit Stelle und Ausweg (``[[accesses]]`` oder eine
    Annotation, die es nachweist)."""
    message = _rejected(tmp_path, STOP_OLD | {TOOL: HEAD + tool})
    assert where in message, (label, message)
    assert "in [[accesses]] entscheiden" in message, message


@pytest.mark.parametrize(("label", "tool", "where", "naive"), OPEN_CASES, ids=OPEN_IDS)
def test_the_proof_is_red_where_the_old_rule_rewrote(
    tmp_path: Path, label: str, tool: str, where: str, naive: str
) -> None:
    """Der Beweis von außen: Der Baum, den die alte Regel schrieb (``x.area.stop()``), und der
    Baum, in dem die Stelle stehen blieb, sind beide rot — keiner ist nachgewiesen."""
    old = STOP_OLD | {TOOL: HEAD + tool}
    rewritten = HEAD + tool.replace(naive.replace(".area", ""), naive)
    assert rewritten != HEAD + tool, label
    for name, text in (("umgeschrieben", rewritten), ("stehen-geblieben", HEAD + tool)):
        proof = _prove(tmp_path / name, old, STOP_NEW | {TOOL: text})
        assert not proof.ok, f"{label}/{name}: Beweis grün\n{proof.text()}"
        assert any("nicht nachweislich der Wirt" in e for e in proof.errors), proof.errors


def test_an_open_receiver_follows_its_decision(tmp_path: Path) -> None:
    """Die Entscheidung gilt: ``component`` schreibt ``timer.area.stop()``, ``keep`` lässt es."""
    tool = "def halt(timer) -> None:\n    timer.stop()\n"
    declared = '\n[[accesses]]\npath = "tools/timer_tool.py"\nscope = "halt"\nmember = "stop"\n'
    for decision, expected in (("component", "timer.area.stop()"), ("keep", "timer.stop()")):
        root, result = _run(
            tmp_path / decision,
            STOP_OLD | {TOOL: HEAD + tool},
            STOP_CUT + declared + f'decision = "{decision}"\n',
        )
        assert result.status == "written", (decision, result.problems)
        assert f"    {expected}\n" in (root / TOOL).read_text(encoding="utf-8"), decision


# ------------------------------------------------------------------ nachgewiesen

#: (Name, Werkzeug, erwarteter Text danach): Der Nachweis entscheidet ohne Erklärung. ``k5``
#: ist die Sonde des Reviews (``timer: QTimer`` wurde umgeschrieben); die übrigen eigene.
PROVEN = [
    (
        "k5-annotiert-qtimer",
        "from PySide6.QtCore import QTimer\n\n\ndef halt(timer: QTimer) -> None:\n"
        "    timer.stop()\n",
        "    timer.stop()\n",
    ),
    (
        "liste",
        "def tally(items: list[int]) -> int:\n    return items.count(1)\n",
        "    return items.count(1)\n",
    ),
    (
        "fremde-klasse-gleichen-namens",
        "class Board:\n    def stop(self) -> None:\n        pass\n\n"
        "    def again(self) -> None:\n        self.stop()\n",
        "        self.stop()\n",
    ),
    (
        "wirt-oder-none",
        "from app.ui.board import Board\n\n\ndef halt(window: Board | None) -> None:\n"
        "    if window is not None:\n        window.stop()\n",
        "        window.area.stop()\n",
    ),
    (
        "rückgabe-annotiert",
        "from app.ui.board import Board\nfrom app.ui.session import Session\n\n\n"
        "def make() -> Board:\n    return Board(Session())\n\n\n"
        "def halt() -> None:\n    make().stop()\n",
        "    make().area.stop()\n",
    ),
    (
        "annotierte-variable",
        "from app.ui.board import Board\n\n\ndef halt(found: object) -> None:\n"
        "    window: Board = found  # type: ignore[assignment]\n    window.stop()\n",
        "    window.area.stop()\n",
    ),
]


@pytest.mark.parametrize(("label", "tool", "expected"), PROVEN, ids=[p[0] for p in PROVEN])
def test_a_proven_receiver_needs_no_decision(
    tmp_path: Path, label: str, tool: str, expected: str
) -> None:
    root, result = _run(tmp_path, STOP_OLD | {TOOL: HEAD + tool})
    assert result.status == "written", (label, result.problems)
    text = (root / TOOL).read_text(encoding="utf-8")
    assert expected in text, (label, text)
    if ".area." not in expected:
        assert text == HEAD + tool, label


def test_the_proof_is_red_for_a_rewritten_foreign_receiver(tmp_path: Path) -> None:
    """Sonde k5 von außen: ``timer.area.stop()`` bei ``timer: QTimer`` ist rot."""
    tool = PROVEN[0][1]
    proof = _prove(
        tmp_path,
        STOP_OLD | {TOOL: HEAD + tool},
        STOP_NEW | {TOOL: HEAD + tool.replace("timer.stop()", "timer.area.stop()")},
    )
    assert not proof.ok, proof.text()
    assert any("tools/timer_tool.py:7" in e and "timer.area" in e for e in proof.errors), (
        proof.errors
    )


# ------------------------------------------------------------------ Erklärungen


@pytest.mark.parametrize(
    ("label", "decision", "where"),
    [
        ("widerspricht", "keep", "erklärt als keep, aber laut Annotation Board"),
        ("überflüssig", "component", "erklärt als component, doch das steht schon fest"),
    ],
)
def test_a_declaration_on_a_proven_access_is_rejected(
    tmp_path: Path, label: str, decision: str, where: str
) -> None:
    """Eine Erklärung gilt nur, wo der Nachweis offen bleibt: Widerspricht sie ihm, wäre der
    Schnitt falsch; stimmt sie mit ihm überein, entscheidet sie nichts."""
    tool = (
        "from app.ui.board import Board\n\n\ndef halt(window: Board) -> None:\n    window.stop()\n"
    )
    cut = (
        STOP_CUT
        + '\n[[accesses]]\npath = "tools/timer_tool.py"\nscope = "halt"\nmember = "stop"\n'
        + f'decision = "{decision}"\n'
    )
    message = _rejected(tmp_path, STOP_OLD | {TOOL: HEAD + tool}, cut)
    assert where in message, (label, message)


# ------------------------------------------------------------------ Unterklassen


#: Eine Unterklasse des Wirts über eine Zwischenklasse in einer Datei, die weder den Wirt noch
#: ein verschobenes Member nennt (der Planer liest sie nicht): Die Abweisung aus RM-M8 folgt den
#: Basen jetzt selbst (``Receivers.class_kind``).
MIDDLE = {
    "tests/board_middle.py": '"""Erste Stufe."""\n\nfrom app.ui.board import Board\n\n\n'
    "class Middle(Board):\n    pass\n",
    "tests/board_second.py": '"""Zweite Stufe, ohne den Namen des Wirts."""\n\n'
    "from tests.board_middle import Middle\n\n\nclass Second(Middle):\n    pass\n",
    "tests/board_deep.py": '"""Dritte Stufe überschreibt ein verschobenes Member."""\n\n'
    "from tests.board_second import Second\n\n\nclass Deep(Second):\n"
    "    def bump(self) -> None:\n        pass\n",
}


def test_a_subclass_through_an_unread_file_is_still_found(tmp_path: Path) -> None:
    message = _rejected(tmp_path, fx.COMPONENT_OLD | MIDDLE, fx.COMPONENT_CUT)
    assert "tests/board_deep.py:6: Deep erbt von Board und definiert bump" in message, message


# ------------------------------------------------------------------ offene Namen (RM-M20)

NAMES = "tools/board_names.py"
NAMES_HEAD = '"""Namen."""\n\n'
#: (Name, Werkzeug, Meldung): k6 und k7 sind die Sonde des Reviews (offener Name auf einen
#: Parameter ohne Annotation, Namensraum); die übrigen eigene Gegenproben derselben Klasse.
OPEN_NAMES = [
    (
        "k6-offener-name-vorgabe",
        "def pick(window, name):\n    return getattr(window, name, None)\n\n\n"
        'def refresh_of(window):\n    return pick(window, "refre" + "sh")\n',
        "liest über einen offenen Namen einen Empfänger, der der Wirt sein kann",
    ),
    (
        "k6-offener-name-ohne-vorgabe",
        "def call(window, name):\n    return getattr(window, name)()\n",
        "liest über einen offenen Namen einen Empfänger, der der Wirt sein kann",
    ),
    (
        "k7-namensraum",
        'def counted(window):\n    return vars(window).get("count")\n',
        "liest über einen offenen Namen einen Empfänger, der der Wirt sein kann",
    ),
    (
        "offener-name-am-wirt",
        "from app.ui.board import Board\n\n\ndef pick(window: Board, name: str) -> object:\n"
        "    return getattr(window, name, None)\n",
        "liest den Wirt über einen offenen Namen",
    ),
    (
        "namensraum-des-wirts",
        "from app.ui.board import Board\n\n\ndef names(window: Board) -> object:\n"
        "    return window.__dict__\n",
        "liest den Wirt über einen offenen Namen",
    ),
    (
        "gefalteter-name",
        'NAME = "refresh"\n\n\ndef pick(window):\n    return getattr(window, NAME)\n',
        "fragt über einen gefalteten Namen nach refresh",
    ),
    (
        "alias-mit-festem-namen",
        "from app.ui.board import Board\n\nhas = hasattr\n\n\ndef probe(window: Board) -> bool:\n"
        '    return has(window, "refresh")\n',
        "hasattr(…, 'refresh') auf ein verschobenes Member",
    ),
]


@pytest.mark.parametrize(("label", "tool", "where"), OPEN_NAMES, ids=[o[0] for o in OPEN_NAMES])
def test_an_open_name_on_a_possible_host_is_rejected(
    tmp_path: Path, label: str, tool: str, where: str
) -> None:
    """Ein offener Name lässt sich nicht umschreiben: auf den Wirt abgewiesen, auf einen
    Empfänger, der es sein kann, abgewiesen mit dem Ausweg ``member = "*"``."""
    message = _rejected(tmp_path, fx.COMPONENT_OLD | {NAMES: NAMES_HEAD + tool}, fx.COMPONENT_CUT)
    assert where in message, (label, message)


@pytest.mark.parametrize(
    ("label", "tool", "where"), OPEN_NAMES[:5], ids=[o[0] for o in OPEN_NAMES[:5]]
)
def test_an_open_name_left_standing_is_red(
    tmp_path: Path, label: str, tool: str, where: str
) -> None:
    files = {NAMES: NAMES_HEAD + tool}
    proof = _prove(tmp_path, fx.COMPONENT_OLD | files, EXPECTED | files, fx.COMPONENT_CUT)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in e for e in proof.errors), (label, proof.errors)


def test_an_open_name_declared_keep_moves_and_a_foreign_receiver_needs_nothing(
    tmp_path: Path,
) -> None:
    """``member = "*"`` mit ``keep`` erklärt, dass der Empfänger nicht der Wirt ist; ein
    nachweislich fremder Empfänger (``toast: Toast``) braucht keine Erklärung; ``component``
    lässt sich für einen offenen Namen nicht erklären."""
    tool = NAMES_HEAD + OPEN_NAMES[1][1]
    declared = (
        f'\n[[accesses]]\npath = "{NAMES}"\nscope = "call"\nmember = "*"\ndecision = "keep"\n'
    )
    _root, result = _run(
        tmp_path / "keep", fx.COMPONENT_OLD | {NAMES: tool}, fx.COMPONENT_CUT + declared
    )
    assert result.status == "written", result.problems
    foreign = NAMES_HEAD + (
        "from app.ui.toast import Toast\n\n\ndef pick(toast: Toast, name: str) -> object:\n"
        "    return getattr(toast, name, None)\n"
    )
    _root, result = _run(tmp_path / "fremd", fx.COMPONENT_OLD | {NAMES: foreign}, fx.COMPONENT_CUT)
    assert result.status == "written", result.problems
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(
        fx.COMPONENT_CUT + declared.replace('"keep"', '"component"'), encoding="utf-8"
    )
    with pytest.raises(move_cut.CutError, match="nur mit"):
        move_cut.load(cut_file)
