"""Die Sperrklinke für Dateigrößen (W1, Konzept Codestruktur 4.1) an Fällen mit bekanntem Ausgang.

`tools/size_ratchet.py` hält Regel 6: Eine Datei über 2 000 Zeilen bekommt keine
neue Definition, und keine neue Datei wächst über die Grenze. Ein Wächter, der
zu wenig zählt, schweigt — deshalb zuerst die Zählung an gepflanzten Quellen,
dann jede Art Verstoß an einem synthetischen Baum (die Gegenproben aus Plan
2.1), die Schreibwege ``--lower``, ``--raise`` und ``--init`` an einer Attrappe
in ``tmp_path`` und zuletzt der Baum selbst gegen ``tests/data/size_ratchet.toml``.
"""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path

import pytest

from tools import size_ratchet
from tools.size_ratchet import LIMIT, LIST

ROOT = Path(__file__).resolve().parent.parent

#: Jede Stelle, an der eine Definition stehen kann, dazu eine Lambda und eine
#: Definition in einer Zeichenkette, die beide nicht zählen.
TRICKY = """\
class Outer:
    def method(self):
        def inner():
            pass
        return lambda: 1

    class Nested:
        async def run(self):
            pass

if True:
    def in_if():
        pass
try:
    def in_try():
        pass
except ValueError:
    def in_handler():
        pass
else:
    def in_else():
        pass
finally:
    def in_finally():
        pass
try:
    pass
except* OSError:
    def in_star():
        pass
with open("x") as handle:
    def in_with():
        pass
for item in ():
    def in_for():
        pass
while False:
    def in_while():
        pass
match 1:
    case 1:
        def in_case():
            pass
SCRIPT = "def in_string():\\n    pass"
"""


def _module(lines: int, definitions: int) -> str:
    """Eine Quelle mit genau ``lines`` Zeilen und ``definitions`` Funktionen."""
    assert lines >= 2 * definitions
    body = "".join(f"def f{index}():\n    pass\n" for index in range(definitions))
    return body + "# Füllzeile\n" * (lines - 2 * definitions)


def test_every_definition_counts_nested_ones_too_but_no_lambda() -> None:
    """Methoden, geschachtelte Funktionen und Klassen in jedem Block zählen, Lambdas nicht."""
    names = size_ratchet.definition_names(TRICKY)

    assert names == [
        "Outer",
        "Outer.method",
        "Outer.method.<locals>.inner",
        "Outer.Nested",
        "Outer.Nested.run",
        "in_if",
        "in_try",
        "in_handler",
        "in_else",
        "in_finally",
        "in_star",
        "in_with",
        "in_for",
        "in_while",
        "in_case",
    ]
    # Der Gang über Anweisungen findet dieselbe Zahl wie ``ast.walk`` über alles.
    walked = ast.walk(ast.parse(TRICKY))
    assert len(names) == sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in walked
    )


def test_lines_are_line_breaks_not_every_separator_splitlines_knows() -> None:
    """``\\x0c`` und ``\\u2028`` in einer Zeichenkette sind keine Zeile (``wc -l``)."""
    source = "x = ' '\ny = '\x0c'\n"

    assert len(source.splitlines()) == 4
    assert size_ratchet.line_count(source) == 2
    assert size_ratchet.line_count("a\r\nb") == 2
    assert size_ratchet.line_count("") == 0
    assert size_ratchet.line_count(_module(LIMIT, 3)) == LIMIT


def test_a_tree_that_keeps_the_ratchet_is_green() -> None:
    """Der Fall ohne Verstoß: gelistet und gleich, ungelistet genau an der Grenze."""
    sizes = size_ratchet.measure_sources(
        {"app/big.py": _module(LIMIT + 1, 3), "tests/test_edge.py": _module(LIMIT, 1)}
    )

    assert size_ratchet.check(sizes, {"app/big.py": 3}) == []
    assert sizes["tests/test_edge.py"].definitions is None


@pytest.mark.parametrize(
    ("sources", "listed", "kind"),
    [
        ({"app/big.py": _module(LIMIT + 1, 4)}, {"app/big.py": 3}, "new_definition"),
        ({"tools/new.py": _module(LIMIT + 1, 1)}, {}, "too_long"),
        ({"app/big.py": _module(LIMIT - 1, 3)}, {"app/big.py": 3}, "release"),
        ({"app/big.py": _module(LIMIT, 3)}, {"app/big.py": 3}, "release"),
        ({}, {"app/big.py": 3}, "release"),
        ({"app/big.py": _module(LIMIT + 1, 2)}, {"app/big.py": 3}, "not_lowered"),
    ],
    ids=[
        "neue Definition",
        "ungelistet 2001",
        "gelistet 1999",
        "gelistet 2000",
        "Datei fehlt",
        "nicht gesenkt",
    ],
)
def test_every_kind_of_violation_is_red(
    sources: dict[str, str], listed: dict[str, int], kind: str
) -> None:
    """Die Gegenproben aus Plan 2.1, je eine Art Verstoß an einem synthetischen Baum."""
    [violation] = size_ratchet.check(size_ratchet.measure_sources(sources), listed)

    assert violation.kind == kind
    if kind in {"new_definition", "too_long"}:
        assert "Regel 6" in violation.message
        assert "Regel 9" in violation.message
        assert "Codestruktur 3.1" in violation.message
    else:
        assert "--lower" in violation.message


def test_lower_only_lowers_and_releases() -> None:
    """``--lower`` senkt und trägt aus; Gewachsenes bleibt rot, Neues kommt nie dazu."""
    sizes = size_ratchet.measure_sources(
        {
            "app/shrunk.py": _module(LIMIT + 1, 2),
            "app/grown.py": _module(LIMIT + 1, 5),
            "app/short.py": _module(LIMIT - 1, 1),
            "tests/test_new.py": _module(LIMIT + 1, 1),
        }
    )
    listed = {"app/shrunk.py": 3, "app/grown.py": 4, "app/short.py": 1, "app/gone.py": 7}

    after = size_ratchet.lowered(sizes, listed)

    assert after == {"app/shrunk.py": 2, "app/grown.py": 4}
    assert [violation.kind for violation in size_ratchet.check(sizes, after)] == [
        "new_definition",
        "too_long",
    ]


def _write(root: Path, sources: dict[str, str]) -> None:
    """Legt eine Attrappe des Baums an, mit LF wie im Repository."""
    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def _window(methods: list[str]) -> str:
    """Eine gelistete Datei: die Klasse ``Window`` mit diesen Methoden, über der Grenze."""
    body = "".join(f"    def {name}(self):\n        pass\n" for name in methods)
    return "class Window:\n" + body + "# Füllzeile\n" * LIMIT


def _ordered_window(root: Path, methods: list[str]) -> None:
    """Ein Ordnungsschritt an ``Window``: der Stand mit ``m0``–``m2`` ist HEAD, danach
    stehen ``methods`` in der Datei."""
    _repo(root, {"app/window.py": _window(["m0", "m1", "m2"])})
    _write(root, {"app/window.py": _window(methods)})


ORDERED = ["m0", "m1", "m2", "build_file", "build_edit"]


@pytest.mark.parametrize(
    ("methods", "sections", "expected"),
    [
        (ORDERED, ["Window.build_file", "Window.build_edit"], 6),
        (["m0a", "m0b", "m1", "m2"], ["Window.m0a", "Window.m0b"], 5),
    ],
    ids=["zwei neue Abschnitte", "eine Methode in zwei geteilt"],
)
def test_raise_lifts_by_exactly_the_named_sections(
    tmp_path: Path, methods: list[str], sections: list[str], expected: int
) -> None:
    """Ein Ordnungsschritt hebt um genau die Abschnitte, die er gegenüber HEAD neu anlegt
    (Konzept 4.3, 4c); geteilt heißt zwei neue und eine weniger."""
    _ordered_window(tmp_path, methods)

    after = size_ratchet.raised(tmp_path, {"app/window.py": 4}, "app/window.py", 2, sections)

    assert after == {"app/window.py": expected}


@pytest.mark.parametrize(
    ("listed", "methods", "sections", "said"),
    [
        ({}, ORDERED, ["Window.build_file", "Window.build_edit"], "nicht in der"),
        ({"app/window.py": 4}, ORDERED, ["Window.build_file"], "Abschnitte"),
        ({"app/window.py": 4}, ORDERED, ["Window.m0", "Window.m0"], "Abschnitte"),
        ({"app/window.py": 4}, ORDERED, ["Window.build_file", "build"], "neu"),
        ({"app/window.py": 4}, ORDERED, ["Window.build_file", "Window.m0"], "neu"),
        ({"app/window.py": 3}, ORDERED, ["Window.build_file", "Window.build_edit"], "HEAD"),
    ],
    ids=[
        "ungelistet",
        "zu wenig benannt",
        "doppelt",
        "kein Abschnitt",
        "alte Definition genannt",
        "Liste unter HEAD",
    ],
)
def test_raise_refuses_what_the_step_does_not_name(
    tmp_path: Path, listed: dict[str, int], methods: list[str], sections: list[str], said: str
) -> None:
    """Jede Abweichung zwischen Benennung und dem, was gegenüber HEAD neu ist, hält
    ``--raise`` an — auch eine alte Methode statt einer neuen (Durchsicht W13, Fund 3)."""
    _ordered_window(tmp_path, methods)

    with pytest.raises(size_ratchet.RatchetError, match=said):
        size_ratchet.raised(tmp_path, listed, "app/window.py", 2, sections)


def test_raise_refuses_a_file_that_head_does_not_have(tmp_path: Path) -> None:
    """Ohne Stand an HEAD gibt es nichts, wogegen „neu“ gemessen würde."""
    _repo(tmp_path, {"app/other.py": "x = 1\n"})
    _write(tmp_path, {"app/window.py": _window(ORDERED)})

    with pytest.raises(size_ratchet.RatchetError, match="HEAD"):
        size_ratchet.raised(
            tmp_path,
            {"app/window.py": 4},
            "app/window.py",
            2,
            ["Window.build_file", "Window.build_edit"],
        )


def _commit(root: Path) -> None:
    """Hält den Stand der Attrappe als Commit fest."""
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    who = ["-c", "user.name=Probe", "-c", "user.email=probe@example.invalid"]
    subprocess.run(["git", *who, "commit", "-q", "-m", "Stand"], cwd=root, check=True)


def _repo(root: Path, sources: dict[str, str]) -> None:
    """Eine Git-Attrappe des Baums mit einem ersten Commit."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _write(root, {"tests/data/README.md": "Korpus\n", **sources})
    _commit(root)


def test_the_command_line_runs_init_check_and_lower_on_a_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der Weg bei Schritt 0 und eines Schritts danach, mit den Exit-Codes."""
    _repo(tmp_path, {"app/big.py": _module(LIMIT + 1, 3)})
    run = ["--root", str(tmp_path)]

    assert size_ratchet.main([*run, "--check"]) == 2
    assert "--init" not in capsys.readouterr().err
    assert size_ratchet.main([*run, "--init"]) == 0
    assert "app/big.py" in capsys.readouterr().out
    assert tomllib.loads((tmp_path / LIST).read_text(encoding="utf-8")) == {"app/big.py": 3}
    assert size_ratchet.main([*run, "--init"]) == 2
    assert size_ratchet.main(run) == 0

    _write(tmp_path, {"app/big.py": _module(LIMIT + 1, 4)})
    assert size_ratchet.main(run) == 1
    assert size_ratchet.main([*run, "--lower"]) == 1
    assert "Regel 6" in capsys.readouterr().out

    _write(tmp_path, {"app/big.py": _module(LIMIT + 1, 1)})
    assert size_ratchet.main(run) == 1
    assert size_ratchet.main([*run, "--lower"]) == 0
    assert "app/big.py: 3 → 1" in capsys.readouterr().out
    assert size_ratchet.read_list(tmp_path / LIST) == {"app/big.py": 1}


def test_init_never_runs_again_once_git_knew_the_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gelöschte Liste, gewachsene Datei: ``--init`` lehnt ab, der Rat ist Zurückholen und
    ``--lower`` (Durchsicht W13, Fund 1a). Vorher segnete ``--init`` die sieben Definitionen."""
    _repo(tmp_path, {"app/big.py": _module(LIMIT + 1, 3)})
    run = ["--root", str(tmp_path)]
    assert size_ratchet.main([*run, "--init"]) == 0
    _commit(tmp_path)
    _write(tmp_path, {"app/big.py": _module(LIMIT + 1, 7)})
    (tmp_path / LIST).unlink()
    capsys.readouterr()

    assert size_ratchet.main([*run, "--check"]) == 2
    advice = capsys.readouterr().err
    assert size_ratchet.main([*run, "--init"]) == 2

    assert "git show" in advice and "--lower" in advice and "--init" not in advice
    assert "Git kennt" in capsys.readouterr().err
    assert not (tmp_path / LIST).exists()


def test_init_takes_only_what_git_versions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine unversionierte Datei über der Grenze hält ``--init`` an und steht in der Meldung
    (Durchsicht W13, Fund 1b); außerhalb von Git legt es nichts an."""
    _repo(tmp_path, {"app/big.py": _module(LIMIT + 1, 3)})
    _write(tmp_path, {"tools/scratch_big.py": _module(2500, 9)})

    assert size_ratchet.main(["--root", str(tmp_path), "--init"]) == 2
    assert "tools/scratch_big.py" in capsys.readouterr().err
    assert not (tmp_path / LIST).exists()

    loose = tmp_path / "ohne_git"
    _write(loose, {"app/big.py": _module(LIMIT + 1, 3)})
    assert size_ratchet.main(["--root", str(loose), "--init"]) == 2
    assert not (loose / LIST).exists()


def _moving_window(root: Path, carried: list[str]) -> None:
    """Ein Umzug wie Konzept 4.3, Schritt 4b: ``app/big.py`` mit ``Window`` ist HEAD und
    gelistet, danach liegt ``Window`` mit ``carried`` in ``app/big/window.py``."""
    _repo(root, {"app/big.py": _window(["m0", "m1", "m2"]), "app/other.py": "x = 1\n"})
    (root / "app" / "big.py").unlink()
    _write(root, {"app/big/window.py": _window(carried)})


def test_move_carries_a_listed_file_to_its_new_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine gelistete Datei zieht um, ihre Definitionen mit ihr: Die Liste trägt den neuen Pfad
    (Durchsicht W13, Fund 2). Vorher blieb nur die Handänderung der Liste."""
    _moving_window(tmp_path, ["m0", "m1", "m2"])
    write = size_ratchet.write_list
    write(tmp_path / LIST, {"app/big.py": 4})
    run = ["--root", str(tmp_path)]

    assert size_ratchet.main(run) == 1
    assert "--move" in capsys.readouterr().out
    assert size_ratchet.main([*run, "--move", "app/big.py", "app/big/window.py"]) == 0
    assert size_ratchet.read_list(tmp_path / LIST) == {"app/big/window.py": 4}


@pytest.mark.parametrize(
    ("carried", "listed", "targets", "said"),
    [
        (["m0", "m1", "m2", "added"], {"app/big.py": 4}, ["app/big/window.py"], "added"),
        (["m0", "m1", "m2"], {"app/big.py": 4}, ["app/other.py"], "HEAD"),
        (["m0", "m1", "m2"], {}, ["app/big/window.py"], "nicht in der"),
        (
            ["m0", "m1", "m2"],
            {"app/big.py": 4, "app/big/window.py": 4},
            ["app/big/window.py"],
            "gelistet",
        ),
        (["m0", "m1", "m2"], {"app/big.py": 4}, ["app/big/missing.py"], "fehlt"),
    ],
    ids=["neue Definition", "in vorhandene Datei", "ALT ungelistet", "NEU gelistet", "NEU fehlt"],
)
def test_move_refuses_anything_but_a_pure_move(
    tmp_path: Path,
    carried: list[str],
    listed: dict[str, int],
    targets: list[str],
    said: str,
) -> None:
    """Was am neuen Ort steht, stand an HEAD in der alten Datei — sonst kein Umzug."""
    _moving_window(tmp_path, carried)
    _write(tmp_path, {"app/other.py": _window(["m0", "m1", "m2"])})

    with pytest.raises(size_ratchet.RatchetError, match=said):
        size_ratchet.moved(tmp_path, listed, "app/big.py", targets)


def test_move_refuses_while_the_old_file_is_still_long_or_the_new_one_short(
    tmp_path: Path,
) -> None:
    """Ein Umzug lässt die alte Datei unter der Grenze zurück; was kurz ist, braucht keinen
    Eintrag."""
    _moving_window(tmp_path, ["m0", "m1", "m2"])
    _write(tmp_path, {"app/big.py": _window(["m0"])})
    with pytest.raises(size_ratchet.RatchetError, match="über"):
        size_ratchet.moved(tmp_path, {"app/big.py": 4}, "app/big.py", ["app/big/window.py"])

    (tmp_path / "app" / "big.py").unlink()
    _write(tmp_path, {"app/big/window.py": "class Window:\n    pass\n"})
    with pytest.raises(size_ratchet.RatchetError, match="keinen Eintrag"):
        size_ratchet.moved(tmp_path, {"app/big.py": 4}, "app/big.py", ["app/big/window.py"])


def test_git_counts_new_files_but_not_ignored_or_deleted_ones(tmp_path: Path) -> None:
    """Eine neue Datei ist vor dem Commit rot; ignorierte Kopien und gelöschte zählen nicht."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("app/copy.py\n", encoding="utf-8")
    _write(
        tmp_path,
        {
            "app/kept.py": "x = 1\n",
            "tests/gone.py": "x = 1\n",
            "tools/new.py": "x = 1\n",
            "app/copy.py": "x = 1\n",
            "app/notes.txt": "x\n",
        },
    )
    subprocess.run(["git", "add", "app/kept.py", "tests/gone.py"], cwd=tmp_path, check=True)
    (tmp_path / "tests" / "gone.py").unlink()

    assert size_ratchet.tree_files(tmp_path) == ["app/kept.py", "tools/new.py"]


def test_a_tree_without_a_single_file_stops(tmp_path: Path) -> None:
    """Eine leere Grundmenge ist der falsche Ordner, kein sauberer Baum."""
    (tmp_path / "app").mkdir()

    with pytest.raises(size_ratchet.RatchetError, match="keine"):
        size_ratchet.measure(tmp_path)


def test_a_lone_carriage_return_is_no_line(tmp_path: Path) -> None:
    """Gelesen wird ohne Zeilenumbruch-Übersetzung: ``\\r\\n`` zählt einmal, ein loses ``\\r``
    gar nicht — wie ``wc -l`` (Durchsicht W13, Fund 5)."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "cr.py").write_bytes(b"a = 1\rb = 2\n")
    (tmp_path / "app" / "crlf.py").write_bytes(b"a = 1\r\nb = 2\r\n")

    sizes = size_ratchet.measure(tmp_path)

    assert sizes["app/cr.py"].lines == 1
    assert sizes["app/crlf.py"].lines == 2


@pytest.mark.parametrize(
    "case",
    ["--raise auf gelöschte Datei", "Syntaxfehler", "kein UTF-8"],
)
def test_a_file_the_tool_cannot_read_stops_with_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    """Was das Werkzeug nicht lesen kann, ist „nicht geprüft“ (Exit 2) und nie ein Verstoß
    (Exit 1) — vorher fiel es als Ausnahme heraus (Durchsicht W13, Fund 8)."""
    _repo(tmp_path, {"app/big.py": _module(LIMIT + 1, 3), "app/small.py": "x = 1\n"})
    size_ratchet.write_list(tmp_path / LIST, {"app/big.py": 3})
    run = ["--root", str(tmp_path)]
    if case == "--raise auf gelöschte Datei":
        (tmp_path / "app" / "big.py").unlink()
        run += ["--raise", "app/big.py", "1", "--sections", "f9"]
    elif case == "Syntaxfehler":
        _write(tmp_path, {"app/big.py": _module(LIMIT + 1, 3) + "def (:\n"})
    else:
        (tmp_path / "app" / "big.py").write_bytes(b"x = '\xff'\n" * (LIMIT + 1))

    assert size_ratchet.main(run) == 2
    assert "nicht geprüft" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    [
        '"app/big.py" = true\n',
        '"app/big.py" = -1\n',
        '"website/big.py" = 3\n',
        '"app/big.txt" = 3\n',
        '"app\\\\big.py" = 3\n',
        '"app/sub\\\\big.py" = 3\n',
        '"app/../big.py" = 3\n',
        "kein toml\n",
    ],
)
def test_a_list_that_carries_anything_but_paths_and_counts_stops(tmp_path: Path, text: str) -> None:
    """Die Liste schreibt nur das Werkzeug; was es nicht geschrieben haben kann, hält an."""
    path = tmp_path / "size_ratchet.toml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(size_ratchet.RatchetError, match="nur dieses Werkzeug"):
        size_ratchet.read_list(path)


def test_the_written_list_reads_back_as_written(tmp_path: Path) -> None:
    """Ohne TOML-Bibliothek geschrieben, mit ``tomllib`` gelesen — auch Umlaut und Anführung."""
    entries = {'tests/test_ä b"c.py': 7, "app/a.py": 0}
    path = tmp_path / "size_ratchet.toml"

    size_ratchet.write_list(path, entries)

    assert size_ratchet.read_list(path) == entries
    assert b"\r\n" not in path.read_bytes()


@pytest.fixture(scope="module")
def tree() -> dict[str, size_ratchet.Size]:
    """Der Baum dieses Repositorys, einmal gemessen für beide Prüfungen."""
    return size_ratchet.measure(ROOT)


def test_the_whole_tree_is_counted(tree: dict[str, size_ratchet.Size]) -> None:
    """Grundmenge nach Plan 2.1: mindestens 900 Dateien, mindestens 100 über der Grenze.

    Gegen eine unabhängige Suche gehalten: Jede ``*.py`` unter den drei Ordnern
    ist gezählt oder von Git ignoriert, und nichts ist gezählt, was nicht da ist.
    """
    found = {
        path.relative_to(ROOT).as_posix()
        for area in size_ratchet.AREAS
        for path in (ROOT / area).rglob("*.py")
    }
    missing = sorted(found - tree.keys())
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=ROOT,
        input="\n".join(missing),
        capture_output=True,
        encoding="utf-8",
        check=False,
    ).stdout.split()

    assert len(tree) >= 900, f"nur {len(tree)} Dateien gezählt"
    assert sum(size.lines > LIMIT for size in tree.values()) >= 100
    assert tree.keys() <= found
    assert sorted(ignored) == missing


def test_the_tree_holds_the_ratchet(tree: dict[str, size_ratchet.Size]) -> None:
    """Der Wächter selbst: Der Baum hält die Liste, und die Liste ist nicht leer."""
    listed = size_ratchet.read_list(ROOT / LIST, ROOT)
    found = size_ratchet.check(tree, listed)

    assert len(listed) >= 100, f"nur {len(listed)} Dateien gelistet"
    assert not found, "\n".join(violation.message for violation in found)
