"""Das Verschiebewerkzeug im Komponentenmodus (Konzept Codestruktur 3.3, Plan 2.7 Punkt 8, E6).

Positiv: Der Schnitt erzeugt den von Hand geschriebenen Sollbaum Byte für Byte — jede Rolle der
Ersetzungsliste im verschobenen Rumpf, der Wirt greift über die Komponente zu, Leser in ``app/``,
``tools/`` und ``tests/`` ziehen mit (erklärt, laut Auflöser oder eindeutig), ein angewandter
Schnitt wird erkannt. Gegenproben: Jeder Mutant des Sollbaums ist rot, jeder unzulässige Schnitt
wird vor dem Schreiben abgewiesen.

**Lebensdauer ist ein eigener Nachweis:** Ein Laufzeittest am geschriebenen Baum (echtes
``QObject``, ohne Fenster, im eigenen Prozess) verlangt, dass nach ``release()`` kein Signal die
Komponente erreicht und der Wirt ohne ``gc.collect`` fort ist. Zwei Gerüste, deren Schnitt der
Beweis grün nennt, sind dort rot: ein ``release()``, das nichts trennt, und ein Wirt, den die
Komponente über einen Abschluss stark hält.
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
TOOLS = "app/ui/board_tools.py"
TESTS = "tests/test_board.py"

#: Der Laufzeitnachweis der Lebensdauer, im eigenen Prozess am geschriebenen Baum.
LIFETIME = '''\
"""Lebensdauer der Komponente: Signal nach release, Wirt ohne gc.collect fort."""

import json
import sys
import weakref

tree = sys.argv[1]
sys.path.insert(0, tree)
import app

assert app.__file__ is not None and app.__file__.startswith(tree), app.__file__
from app.ui.board import Board
from app.ui.session import Session

session = Session()
window = Board(session)
area = window.area
area.attach()
session.changed.emit()
after_emit = area.count
window.release()
session.changed.emit()
after_release = area.count
ref = weakref.ref(window)
del window
freed = ref() is None
try:
    area._host
    host_error = ""
except RuntimeError as error:
    host_error = str(error)
print(json.dumps({
    "after_emit": after_emit,
    "after_release": after_release,
    "freed": freed,
    "host_error": host_error,
}))
'''


def _run(
    tmp_path: Path, files: dict[str, str] = fx.COMPONENT_OLD, cut_text: str = fx.COMPONENT_CUT
) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut_text.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _expected_bytes(files: dict[str, str]) -> dict[str, bytes]:
    return {path: fx.text_of(text).encode("utf-8") for path, text in files.items()}


def _prove(
    tmp_path: Path, new_files: dict[str, str], old_files: dict[str, str] = fx.COMPONENT_OLD
) -> move_proof.Proof:
    old = fx.write_tree(tmp_path / "old", old_files)
    new = fx.write_tree(tmp_path / "new", new_files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(fx.COMPONENT_CUT, encoding="utf-8")
    return move_proof.prove(move_cut.load(cut_file), old, new)


def _lifetime(tmp_path: Path, root: Path) -> dict[str, object]:
    script = tmp_path / "lifetime.py"
    script.write_text(LIFETIME, encoding="utf-8")
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPATH", None)
    done = subprocess.run(
        [sys.executable, str(script), str(root)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    result: dict[str, object] = json.loads(done.stdout.strip().splitlines()[-1])
    return result


# ------------------------------------------------------------------------------ positiv


def test_the_component_cut_writes_the_hand_written_tree(tmp_path: Path) -> None:
    """K+1 bis K+4: fünf Methoden, jede Rolle, Wirt, Leser, Klassenbezug, Pfad als Text."""
    root, result = _run(tmp_path)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)
    assert result.proof is not None
    assert result.proof.counts["methods"] == 5
    assert result.proof.counts["changed_files"] == 5
    assert result.proof.counts["registry_bytes"] > 0


def test_the_proof_names_every_replacement(tmp_path: Path) -> None:
    """Das Protokoll nennt je Methode die erklärten Ersetzungen und den Grund je Leserstelle."""
    proof = _prove(tmp_path, EXPECTED)
    assert proof.ok, proof.text()
    text = proof.text()
    assert (
        "Methode Board.refresh → Area.refresh: ast-gleich nach 7 erklärten Ersetzungen "
        "(self → self._parent (Qt-Elternteil (erklärt)); self.document → self._host.document; "
        "self.document → self._host.document; self.findChild → self._parent.findChild; "
        "self.statusBar → self._host.statusBar; self.session → self._host.session; "
        "Board.notify → Area.notify)"
    ) in text
    assert "window → window.area (erklärt in accesses)" in text
    assert "window → window.area (Name nur am Wirt definiert)" in text
    assert "Der Laufzeitnachweis (kein Signal nach release, Wirt ohne gc.collect fort)" in text


def test_the_written_component_lets_go(tmp_path: Path) -> None:
    """K+5, Lebensdauer am geschriebenen Baum: Nach ``release()`` kommt kein Signal mehr an,
    der Wirt ist ohne ``gc.collect`` fort, und die Komponente sagt es laut."""
    root, result = _run(tmp_path)
    assert result.status == "written", result.problems
    found = _lifetime(tmp_path, root)
    assert found["after_emit"] == 2  # Wirt und Komponente zählen je einmal
    assert found["after_release"] == found["after_emit"]
    assert found["freed"] is True
    assert found["host_error"] == "Der Wirt des Bereichs ist fort"


@pytest.mark.parametrize(
    ("label", "old", "new", "broken"),
    [
        (
            "release-trennt-nichts",
            "        self._host.session.disconnect(self)\n",
            "        return None\n",
            "after_release",
        ),
        (
            "wirt-im-abschluss",
            "        self._host_ref = weakref.ref(host)\n",
            "        self._host_ref = lambda: host\n",
            "freed",
        ),
    ],
)
def test_a_proven_cut_can_still_hold_on_and_only_the_runtime_check_sees_it(
    tmp_path: Path, label: str, old: str, new: str, broken: str
) -> None:
    """K−7: Der Beweis vergleicht Rümpfe, nicht Lebensdauer — beide Gerüste schneidet das
    Werkzeug grün, und erst der Laufzeitnachweis ist rot."""
    files = fx.edit(fx.COMPONENT_OLD, AREA, old, new)
    root, result = _run(tmp_path, files)
    assert result.status == "written", (label, result.problems)
    found = _lifetime(tmp_path, root)
    if broken == "after_release":
        assert found["after_release"] != found["after_emit"], label
    else:
        assert found["freed"] is False, label


def test_the_cut_repeated_on_a_newer_state_carries_the_change(tmp_path: Path) -> None:
    newer = fx.edit(
        fx.COMPONENT_OLD,
        BOARD,
        "    def bump(self) -> None:\n        self.count += 1",
        "    def bump(self) -> None:\n        self.count += 3",
    )
    root, result = _run(tmp_path, newer)
    assert result.status == "written", result.problems
    expected = fx.edit(
        EXPECTED,
        AREA,
        "        self.count += 1\n\n    def attach",
        "        self.count += 3\n\n    def attach",
    )
    assert fx.tree_bytes(root) == _expected_bytes(expected)


def test_an_applied_component_cut_is_recognised(tmp_path: Path) -> None:
    root, result = _run(tmp_path, EXPECTED)
    assert result.status == "applied", result.problems
    assert fx.tree_bytes(root) == _expected_bytes(EXPECTED)


# ------------------------------------------------------------------------------ Mutanten


def _mutants() -> list[tuple[str, dict[str, str], str]]:
    return [
        (
            "qt-eltern-als-besitzer",
            fx.edit(EXPECTED, AREA, "QMenu(self._parent)", "QMenu(self)"),
            "_parent",
        ),
        (
            "qt-eltern-als-wirt",
            fx.edit(EXPECTED, AREA, "QMenu(self._parent)", "QMenu(self._host)"),
            "_parent",
        ),
        (
            "ererbtes-über-komponente",
            fx.edit(EXPECTED, AREA, "self._parent.findChild(QObject)", "self.findChild(QObject)"),
            "_parent.findChild",
        ),
        (
            "fluss-beim-wirt-zur-komponente",
            fx.edit(EXPECTED, AREA, "Flow(self._host).start()", "Flow(self).start()"),
            "Wirt eines Flusses, der beim Wirt bleibt",
        ),
        (
            "fluss-der-komponente-zum-wirt",
            fx.edit(EXPECTED, AREA, "self._flow = Flow(self)", "self._flow = Flow(self._host)"),
            "Wirt eines Flusses, der in die Komponente zieht",
        ),
        (
            "besitzer-an-den-wirt",
            fx.edit(EXPECTED, AREA, "WorkerLeash(self)", "WorkerLeash(self._host)"),
            "Besitzer",
        ),
        (
            "filter-an-den-wirt",
            fx.edit(EXPECTED, AREA, "installEventFilter(self)", "installEventFilter(self._host)"),
            "Ereignisfilter",
        ),
        (
            "geteiltes-ohne-wirt",
            fx.edit(EXPECTED, AREA, "self._host.changed.emit()", "self.changed.emit()"),
            "self._host.changed",
        ),
        (
            "innerer-schatten",
            fx.edit(EXPECTED, AREA, "            return self\n", "            return self._host\n"),
            AREA,
        ),
        (
            "nur-die-klasse",
            fx.edit(EXPECTED, TOOLS, "Area.refresh(window.area)", "Area.refresh(window)"),
            "window.area",
        ),
        (
            "äußeres-setzen-vergessen",
            fx.edit(EXPECTED, TOOLS, "window.area.count = 2", "window.count = 2"),
            "app/ui/board_tools.py:11 (Leser): erwartet window.area",
        ),
        (
            "fremdes-member-umgestellt",
            fx.edit(EXPECTED, TOOLS, 'toast.notify("x")', 'toast.area.notify("x")'),
            TOOLS,
        ),
        (
            "methode-bleibt-im-wirt",
            fx.edit(
                EXPECTED,
                BOARD,
                "    def _on_changed(self) -> None:\n",
                "    def bump(self) -> None:\n        self.count += 1\n\n"
                "    def _on_changed(self) -> None:\n",
            ),
            "bump steht noch im Wirt",
        ),
        (
            "import-fehlt",
            fx.edit(
                EXPECTED,
                AREA,
                "from app.ui.leash import WorkerLeash, weak_slot\n",
                "from app.ui.leash import weak_slot\n",
            ),
            "WorkerLeash",
        ),
        (
            "fremder-import",
            fx.edit(EXPECTED, AREA, "import weakref\n", "import json\nimport weakref\n"),
            "gehört nicht zu den verschobenen Methoden",
        ),
        (
            "pfad-am-alten-ziel",
            fx.edit(EXPECTED, TESTS, '"app.ui.board_area.Area.bump"', '"app.ui.board.Board.bump"'),
            TESTS,
        ),
        (
            "kopfkommentar-fehlt",
            fx.edit(
                EXPECTED, AREA, "    # Kopfkommentar: gehört zu refresh und wandert mit.\n", ""
            ),
            "Kommentar",
        ),
        (
            "fremde-datei",
            fx.edit(EXPECTED, "app/core/other.py", "    return 2", "    return 2  # anders"),
            "app/core/other.py",
        ),
    ]


@pytest.mark.parametrize(
    ("label", "files", "where"), _mutants(), ids=[mutant[0] for mutant in _mutants()]
)
def test_every_mutant_of_the_component_cut_is_red(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    proof = _prove(tmp_path, files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


def test_the_component_mutant_list_is_not_empty() -> None:
    assert len(_mutants()) >= 15


#: Eine Testdatei, die das Brett über eine Instanz patcht und befragt (Review RM-M1).
INSTANCE_READER = (
    '"""Instanzpatch und Zugriff am Brett."""\n\n'
    "from app.ui import board\nfrom app.ui.session import Session\n\n\n"
    "def test_extra(monkeypatch):\n"
    "    window = board.Board(Session())\n"
    '    monkeypatch.setattr(window, "bump", lambda: None)\n'
    "    assert window.refresh() > 0\n"
)


def _unchanged() -> list[tuple[str, dict[str, str], dict[str, str], str]]:
    """Ein Leser, der in einer **unveränderten** Datei steht: Der Beweis vergleicht jede Datei,
    die einen verschobenen Namen nennt, nicht nur die geänderten (Konzept 4.1, W5)."""
    probe = "tools/board_probe.py"
    return [
        ("leser-in-app", fx.COMPONENT_OLD, EXPECTED | {TOOLS: fx.COMPONENT_OLD[TOOLS]}, TOOLS),
        ("leser-in-tools", fx.COMPONENT_OLD, EXPECTED | {probe: fx.COMPONENT_OLD[probe]}, probe),
        (
            "instanzpatch-in-tests",
            fx.COMPONENT_OLD | {"tests/test_extra.py": INSTANCE_READER},
            EXPECTED | {"tests/test_extra.py": INSTANCE_READER},
            "tests/test_extra.py:9",
        ),
        (
            "zeichenkette-ohne-erklärung",
            fx.COMPONENT_OLD | {"tests/test_names.py": 'NAMES = ("bump",)\n'},
            EXPECTED | {"tests/test_names.py": 'NAMES = ("bump",)\n'},
            "tests/test_names.py:1: Zeichenkette 'bump'",
        ),
        (
            "pfad-als-text",
            fx.COMPONENT_OLD | {"tests/test_names.py": 'TARGET = "app.ui.board.Board.refresh"\n'},
            EXPECTED | {"tests/test_names.py": 'TARGET = "app.ui.board.Board.refresh"\n'},
            "tests/test_names.py:1: Pfad als Text 'app.ui.board.Board.refresh'",
        ),
    ]


@pytest.mark.parametrize(
    ("label", "old_files", "new_files", "where"), _unchanged(), ids=[u[0] for u in _unchanged()]
)
def test_a_forgotten_reader_in_an_unchanged_file_is_red(
    tmp_path: Path, label: str, old_files: dict[str, str], new_files: dict[str, str], where: str
) -> None:
    """RM-M1: Ein Leser, den der Planer übersah oder der nach dem Planen dazukam, bleibt nicht
    grün, nur weil seine Datei unverändert ist."""
    proof = _prove(tmp_path, new_files, old_files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


def _padded(files: dict[str, str], lines: int) -> dict[str, str]:
    """Die Komponente im Gerüst mit ``lines`` Kommentarzeilen mehr."""
    head = "\n\nclass AreaHost(Protocol):"
    return fx.edit(files, AREA, head, "\n" + "# Platz\n" * lines + head)


def test_a_component_over_the_line_limit_is_rejected_and_red(tmp_path: Path) -> None:
    """RM-M14: Die Komponente steht unter 2 000 Zeilen (Konzept 4.5); sie ist eine Datei aus dem
    Gerüst-Commit, also prüft das Werkzeug sie eigens — Planer und Beweis."""
    old = _padded(fx.COMPONENT_OLD, 1925)
    assert fx.text_of(old[AREA]).count("\n") < 2000
    message = _rejected(tmp_path / "plan", old)
    assert "app/ui/board_area.py: 20" in message and "Zeilen, mehr als 2000" in message
    proof = _prove(tmp_path / "proof", _padded(EXPECTED, 1925), old)
    assert any("app/ui/board_area.py: 20" in error for error in proof.errors), proof.errors


# ------------------------------------------------------------------ Typ aus dem Wirtsmodul

HOST_HEAD = "\n\nclass Board(QObject):"
BUMP = "    def bump(self) -> None:\n        self.count += 1"
SESSION_TYPE = "    from app.ui.session import Session\n"


def _typed(files: dict[str, str], path: str) -> dict[str, str]:
    """``bump`` nimmt einen Typ aus dem Modul des Wirts an (``Mode``), nur in der Annotation."""
    files = fx.edit(files, BOARD, HOST_HEAD, "\n\nclass Mode:\n    pass\n" + HOST_HEAD)
    typed = "    def bump(self, mode: Mode | None = None) -> None:\n        self.count += 1"
    return fx.edit(files, path, BUMP, typed)


TYPED_OLD = _typed(fx.COMPONENT_OLD, BOARD)
#: Der Sollbaum: ``Mode`` steht in der Komponente nur unter ``TYPE_CHECKING`` (kein Kreis).
TYPED_NEW = fx.edit(
    _typed(EXPECTED, AREA), AREA, SESSION_TYPE, "    from app.ui.board import Mode\n" + SESSION_TYPE
)


def test_a_host_type_in_an_annotation_moves_under_type_checking(tmp_path: Path) -> None:
    """RM-M3: Der Planer legt den Typ unter ``TYPE_CHECKING`` der Komponente, und der Beweis
    nimmt genau das an — die Bindungen des Blocks gelten als Typprüfung."""
    root, result = _run(tmp_path, TYPED_OLD)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(TYPED_NEW)
    assert result.proof is not None
    assert "Mode: Typ aus dem Wirtsmodul unter TYPE_CHECKING" in result.proof.text()


def _runtime_reads() -> list[tuple[str, dict[str, str], dict[str, str], str]]:
    step_old = fx.edit(
        fx.edit(fx.COMPONENT_OLD, BOARD, HOST_HEAD, "\n\nSTEP = 2\n" + HOST_HEAD),
        BOARD,
        BUMP,
        BUMP.replace("+= 1", "+= STEP"),
    )
    step_new = fx.edit(
        fx.edit(
            fx.edit(EXPECTED, BOARD, HOST_HEAD, "\n\nSTEP = 2\n" + HOST_HEAD),
            AREA,
            BUMP,
            BUMP.replace("+= 1", "+= STEP"),
        ),
        AREA,
        SESSION_TYPE,
        "    from app.ui.board import STEP\n" + SESSION_TYPE,
    )
    runtime_import = fx.edit(
        fx.edit(TYPED_NEW, AREA, "    from app.ui.board import Mode\n", ""),
        AREA,
        "from app.ui.flow import Flow\n",
        "from app.ui.board import Mode\nfrom app.ui.flow import Flow\n",
    )
    return [
        ("wert-nur-zur-typprüfung", step_old, step_new, "STEP meint vorher"),
        ("typ-zur-laufzeit-importiert", TYPED_OLD, runtime_import, "Mode meint vorher"),
    ]


@pytest.mark.parametrize(
    ("label", "old_files", "new_files", "where"),
    _runtime_reads(),
    ids=[case[0] for case in _runtime_reads()],
)
def test_a_host_definition_read_at_runtime_is_red_for_that_reason(
    tmp_path: Path, label: str, old_files: dict[str, str], new_files: dict[str, str], where: str
) -> None:
    """RM-M3: Ein Wert des Wirtsmoduls zur Laufzeit, aber nur unter ``TYPE_CHECKING`` importiert
    (danach ``NameError``), und ein Typ, zur Laufzeit importiert (ein Kreis): rot, weil der Name
    an dieser Stelle nachher etwas anderes meint — nicht über einen Nebenbefund."""
    proof = _prove(tmp_path, new_files, old_files)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    assert any(where in error for error in proof.errors), (label, proof.errors)


# ------------------------------------------------------------------------------ abgewiesen


def _rejected(
    tmp_path: Path, files: dict[str, str] = fx.COMPONENT_OLD, cut_text: str = fx.COMPONENT_CUT
) -> str:
    root, result = _run(tmp_path, files, cut_text)
    assert result.status == "rejected", (result.status, result.proof and result.proof.text())
    assert fx.tree_bytes(root) == _expected_bytes(files), "abgewiesen, aber geschrieben"
    assert all(" — " in problem for problem in result.problems), result.problems
    return "\n".join(result.problems)


@pytest.mark.parametrize(
    ("label", "old", "new", "where"),
    [
        (
            "nacktes-self-ohne-rolle",
            '[[self_roles]]\nscope = "Board.refresh"\ncall = "QMenu"\nargument = 0\n'
            'role = "qt_parent"\n',
            "",
            "nacktes self in Board.refresh an QMenu(…) Argument 0 ohne Rolle",
        ),
        (
            "member-ohne-rolle",
            'host_members = ["document", "session", "changed", "statusBar"]',
            'host_members = ["session", "changed", "statusBar"]',
            "self.document in Board.refresh hat keine Rolle",
        ),
        (
            "mehrdeutig-ohne-entscheidung",
            '[[accesses]]\npath = "app/ui/board_tools.py"\nscope = "ring"\nmember = "notify"\n'
            'decision = "component"\n',
            "",
            "Zugriff auf notify (ring) — 'notify' gibt es auch in app/ui/toast.py",
        ),
        (
            "erklärung-trifft-nichts",
            'scope = "shout"',
            'scope = "schreien"',
            "accesses (app/ui/board_tools.py, schreien, notify) trifft keine Stelle",
        ),
        (
            "rolle-trifft-nichts",
            'role = "qt_parent"\n',
            'role = "qt_parent"\n\n[[self_roles]]\nscope = "Board.refresh"\ncall = "QDialog"\n'
            'argument = 0\nrole = "qt_parent"\n',
            "self_roles[1] (Board.refresh, QDialog, 0) trifft kein nacktes self",
        ),
        (
            "member-in-zwei-rollen",
            'own_attributes = ["count", "_leash", "_flow"]',
            'own_attributes = ["count", "_leash", "_flow", "bump"]',
            "",
        ),
    ],
)
def test_a_declaration_that_does_not_fit_is_rejected(
    tmp_path: Path, label: str, old: str, new: str, where: str
) -> None:
    assert old in fx.COMPONENT_CUT, label
    cut = fx.COMPONENT_CUT.replace(old, new)
    if not where:
        with pytest.raises(move_cut.CutError):
            _rejected(tmp_path, cut_text=cut)
        return
    assert where in _rejected(tmp_path, cut_text=cut), label


def _with(path: str, text: str) -> dict[str, str]:
    return fx.COMPONENT_OLD | {path: text}


@pytest.mark.parametrize(
    ("label", "files", "where"),
    [
        (
            "super",
            fx.edit(
                fx.COMPONENT_OLD,
                BOARD,
                "        self.count += 1\n\n    def attach",
                "        super().deleteLater()\n\n    def attach",
            ),
            "super() in Board.bump",
        ),
        (
            "definition-des-wirtsmoduls",
            fx.edit(
                fx.edit(
                    fx.COMPONENT_OLD,
                    BOARD,
                    "\n\nclass Board(QObject):",
                    "\nSTEP = 2\n\n\nclass Board(QObject):",
                ),
                BOARD,
                "        self.count += 1\n\n    def attach",
                "        self.count += STEP\n\n    def attach",
            ),
            "liest STEP aus dem Modul des Wirts",
        ),
        (
            "gepatchter-name-des-wirtsmoduls",
            _with(
                "tests/test_patch.py",
                "from app.ui import board\n\n\n"
                "def test_timer(monkeypatch):\n"
                '    monkeypatch.setattr(board, "QTimer", object)\n',
            ),
            "liest QTimer, den ein Test auf app.ui.board patcht",
        ),
        (
            "hasattr",
            _with(
                "tools/board_probe.py",
                'def probe(window: object) -> bool:\n    return hasattr(window, "refresh")\n',
            ),
            "hasattr(…, 'refresh') auf ein verschobenes Member",
        ),
        (
            "zeichenkette",
            _with("tests/test_names.py", 'NAMES = ("bump",)\n'),
            "Zeichenkette 'bump' (<module>) nennt ein verschobenes Member",
        ),
        (
            "kein-release",
            fx.edit(
                fx.COMPONENT_OLD,
                AREA,
                "    def release(self) -> None:\n"
                '        """Trennt, was der Bereich mit der Sitzung verbunden hat."""\n'
                "        self._host.session.disconnect(self)\n",
                "",
            ),
            "kein release()",
        ),
        (
            "wirt-ruft-release-nicht",
            fx.edit(fx.COMPONENT_OLD, BOARD, "        self.area.release()\n", ""),
            "Board.release ruft self.area.release() nicht",
        ),
        (
            "wirt-stark-gehalten",
            fx.edit(
                fx.COMPONENT_OLD,
                AREA,
                "self._host_ref = weakref.ref(host)",
                "self._host_ref = host",
            ),
            "hält host stark",
        ),
        (
            "vor-dem-bau",
            fx.edit(
                fx.COMPONENT_OLD,
                BOARD,
                "        self.area = Area(self, self)\n        self.count = 0\n",
                "        self.count = 0\n        self.area = Area(self, self)\n",
            ),
            "nutzt verschobene Member vor dem Bau",
        ),
        (
            "protokoll-ohne-member",
            fx.edit(fx.COMPONENT_OLD, AREA, "    document: str\n", ""),
            "AreaHost nennt document nicht",
        ),
        (
            "klassenmethode",
            fx.edit(
                fx.COMPONENT_OLD,
                BOARD,
                "    def bump(self) -> None:",
                "    @classmethod\n    def bump(self) -> None:",
            ),
            "bump ist @classmethod",
        ),
    ],
)
def test_a_component_cut_that_cannot_be_proven_is_rejected(
    tmp_path: Path, label: str, files: dict[str, str], where: str
) -> None:
    assert where in _rejected(tmp_path, files), label
