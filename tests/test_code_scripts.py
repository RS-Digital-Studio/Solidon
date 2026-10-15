"""Ein Skript in einer Zeichenkette, das ``python -c`` ausführt, ist für den Auflöser Code (CS-18).

**Warum es diese Datei gibt.** ``tests/test_core_isolation.py`` und andere starten einen eigenen
Python-Prozess mit einem Skript als Text. Ein Name, den ein Schnitt verschiebt, bricht dort erst,
wenn der Prozess läuft; W5 sah den Text nicht, ``references()`` nannte ihn nicht, also schrieb
das Verschiebewerkzeug ihn nicht um. ``tools/code_scripts.py`` liest jedes solche Skript wie ein
Modul: Importe und Bezüge zählen als ``script:<art>`` an der Stelle des Skripts im Aufruf, ein
fehlender Name ist ein W5-Fund. Leser zur Aufrufzeit liefert ein Skript nicht — einen anderen
Prozess erreicht kein Patch (W2 d bleibt, wie sie war). ``git -c``, ``sh -c`` und
``-m pytest -c`` sind kein Skript.
"""

from __future__ import annotations

from tests.code_index_helpers import build_index
from tools.code_index import Index

HEAD = "import subprocess\nimport sys\nimport textwrap\nfrom app import mod\n\n\n"


def _index(body: str, path: str = "tests/test_probe.py") -> Index:
    return build_index({path: HEAD + body})


def _references(index: Index, name: str) -> set[tuple[str, str, int]]:
    return {(r.kind, r.path, r.line) for r in index.references("app.mod", name)}


def _missing(index: Index) -> set[tuple[str, str, str, int]]:
    return {(u.kind, u.module, u.name, u.line) for u in index.unresolved()}


def test_a_script_for_python_c_is_read_like_a_module() -> None:
    index = _index(
        "def test_run():\n"
        "    subprocess.run([sys.executable, '-c', 'from app.mod import target\\ntarget()\\n'])\n"
    )
    assert ("script:from", "tests/test_probe.py", 8) in _references(index, "target")
    # Ein anderer Prozess: Das Skript liest ``target`` nicht zur Aufrufzeit eines Moduls.
    assert {r.qualname for r in index.readers("app.mod", "target")} == {"read"}
    assert index.counts["scripts.read"] == 1


def test_a_missing_name_in_a_script_is_a_w5_finding() -> None:
    index = _index(
        "SCRIPT = 'import app.mod\\napp.mod.MISSING\\nfrom app.gone import thing\\n'\n\n"
        "def test_run():\n"
        "    subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', SCRIPT])\n"
    )
    assert _missing(index) == {
        ("script:attribute", "app.mod", "MISSING", 10),
        ("script:from", "app.gone", "thing", 10),
    }
    texts = {u.text for u in index.unresolved()}
    assert "app.mod.MISSING (Skript, Zeile 2)" in texts


def test_a_script_built_from_parts_is_read_with_its_open_values_as_placeholders() -> None:
    """``textwrap.dedent`` eines f-Strings mit ``{pfad!r}``, ``"; ".join`` und ``+=`` — der
    offene Teil wird ein Platzhalter, der Rest bleibt lesbar."""
    index = _index(
        "def test_dedented(tmp_path):\n"
        "    script = textwrap.dedent(\n"
        "        f'''\n"
        "        import sys\n"
        "        sys.path.insert(0, {str(tmp_path)!r})\n"
        "        from app.mod import FIRST\n"
        "        '''\n"
        "    )\n"
        "    subprocess.run([sys.executable, '-c', script])\n\n"
        "def test_joined():\n"
        "    code = '; '.join(('import app.mod', 'app.mod.SECOND()'))\n"
        "    subprocess.run([sys.executable, '-c', code])\n\n"
        "def test_grown(flag):\n"
        "    source = 'import sys\\n'\n"
        "    source += 'from app.mod import THIRD\\n'\n"
        "    subprocess.run([sys.executable, '-c', source])\n\n"
        "def test_block(header):\n"
        "    subprocess.run([sys.executable, '-c', header + 'from app.mod import FOURTH\\n'])\n"
    )
    assert {(kind, name) for kind, _module, name, _line in _missing(index)} == {
        ("script:from", "FIRST"),
        ("script:attribute", "SECOND"),
        ("script:from", "THIRD"),
        ("script:from", "FOURTH"),
    }
    assert index.counts["scripts.template"] == 2
    assert index.counts.get("scripts.open", 0) == 0


def test_without_an_interpreter_head_the_dash_c_is_no_script() -> None:
    """Gegenprobe: dieselben Texte hinter ``git -c``, ``sh -c`` und ``-m pytest -c``."""
    index = _index(
        "BAD = 'from app.mod import MISSING'\n\n"
        "def test_run():\n"
        "    subprocess.run(['git', '-c', BAD])\n"
        "    subprocess.run(['sh', '-c', BAD])\n"
        "    subprocess.run([sys.executable, '-m', 'pytest', '-c', BAD])\n"
        "    subprocess.run([sys.executable, 'run.py', '-c', BAD])\n"
    )
    assert not _missing(index)
    assert index.counts.get("scripts.sites", 0) == 0


def test_arguments_that_follow_an_interpreter_carry_their_script() -> None:
    """``["-c", text]`` steht hinter einem Interpreter; ein Kopf mit ``python`` ist einer."""
    index = _index(
        "def test_run(python):\n"
        "    arguments = ['-c', 'from app.mod import MISSING']\n"
        "    subprocess.run([sys.executable, *arguments])\n"
        "    subprocess.run([str(python), '-c', 'from app.mod import GONE'])\n"
    )
    assert {name for _kind, _module, name, _line in _missing(index)} == {"MISSING", "GONE"}


def test_a_script_has_its_own_names_apart_from_its_host() -> None:
    """Dieselbe Stelle, derselbe Name: ``value = alias`` in Zeile 2 ist im Test ``app.other``,
    im Skript ``app.mod`` — die Faltung merkt sich beide getrennt, obwohl die Form gleich ist."""
    index = build_index(
        {
            "tests/test_probe.py": "from app import other as alias\n"
            "value = alias\n"
            "value.other()\n"
            "import subprocess, sys\n\n"
            "def test_run():\n"
            "    subprocess.run([sys.executable, '-c', "
            "'from app import mod as alias\\nvalue = alias\\nvalue.MISSING\\n'])\n"
        }
    )
    assert _missing(index) == {("script:attribute", "app.mod", "MISSING", 7)}
    assert ("attribute", "tests/test_probe.py", 3) in {
        (r.kind, r.path, r.line) for r in index.references("app.other", "other")
    }


def test_a_name_from_an_open_part_is_counted_not_reported() -> None:
    """RR2-3: Ein Modul oder Name aus dem Platzhalter einer Vorlage steht erst zur Laufzeit
    fest — offen wie ein ganzes Skript, kein W5-Fund. Der feste Name daneben bleibt ein Fund."""
    index = _index(
        "def test_run(name):\n"
        "    subprocess.run([sys.executable, '-c', f'from app.{name} import target'])\n"
        "    subprocess.run([sys.executable, '-c', f'from app.mod import {name}'])\n"
        "    script = f'import app.mod\\napp.mod.{name}()\\napp.mod.MISSING\\n'\n"
        "    subprocess.run([sys.executable, '-c', script])\n"
    )
    assert _missing(index) == {("script:attribute", "app.mod", "MISSING", 11)}
    assert index.counts["scripts.template"] == 3
    assert index.counts["scripts.open"] == 3


def test_an_open_script_is_counted_not_guessed() -> None:
    index = _index(
        "def run(script):\n    subprocess.run([sys.executable, '-c', script])\n",
        path="tools/runner.py",
    )
    assert not _missing(index)
    assert index.counts["scripts.open"] == 1
