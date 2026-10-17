"""Aufrufe mit Attributnamen und Lesungen eines Namensraums über Umwege (Review 2 über Paket M,
RM-M20 und RM-M23; ``tools/move_forms.py``).

Der Fund: Planer und Beweis erkannten ``hasattr``/``getattr`` am Namen im Quelltext, nicht am
Auflöser. ``has = hasattr; has(legacy, "bump")``, ``from builtins import hasattr as has``,
``builtins.hasattr(…)`` und ``get = getattr; get(legacy, "bump", None)`` blieben stehen, der
Beweis war grün, danach antworteten sie still ``False`` oder ``None``; ebenso
``builtins.hasattr(consumer, "operation")`` und ``vars(consumer).get("operation")`` im Modus
``copies``. Je Fall der Planer (umgeschrieben oder abgewiesen) und der Beweis eines Baums, in dem
die Stelle stehen blieb (rot).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import move_fixtures as fx
from tools import move_cut, move_names, move_proof, move_refs

MODULE_EXPECTED = fx.changed_tree(fx.MODULE_OLD, fx.MODULE_NEW)
COPIES_EXPECTED = fx.changed_tree(fx.COPIES_OLD, fx.COPIES_NEW)
QUERY = "tests/test_query.py"
ALIAS = "tests/query_alias.py"


def _run(tmp_path: Path, files: dict[str, str], cut: str) -> tuple[Path, move_names.Result]:
    root = fx.write_tree(tmp_path / "tree", files)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_bytes(cut.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return root, move_names.run(move_cut.load(cut_file), root, work=work, cache=False)


def _prove(tmp_path: Path, old: dict[str, str], new: dict[str, str], cut: str) -> move_proof.Proof:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cut_file = tmp_path / "cut.toml"
    cut_file.write_text(cut, encoding="utf-8")
    return move_proof.prove(
        move_cut.load(cut_file),
        fx.write_tree(tmp_path / "old", old),
        fx.write_tree(tmp_path / "new", new),
    )


# ------------------------------------------------------------------ Modulmodus

#: (Name, Dateien, umgeschriebene Stelle): m1a bis m1d sind die Sonde des Reviews; die übrigen
#: eigene Gegenproben derselben Klasse — ein Alias aus einem anderen Modul (die Datei nennt
#: ``hasattr`` gar nicht) und ``setattr``, das einen fehlenden Namen still anlegte.
MODULE_FORMS = [
    (
        "m1a-alias",
        {
            QUERY: "from app.core import legacy\n\nhas = hasattr\n\n\ndef test_has():\n"
            '    assert has(legacy, "bump")\n'
        },
        'has(state, "bump")',
    ),
    (
        "m1b-from-builtins",
        {
            QUERY: "from builtins import hasattr as has\n\nfrom app.core import legacy\n\n\n"
            'def test_has():\n    assert has(legacy, "bump")\n'
        },
        'has(state, "bump")',
    ),
    (
        "m1c-builtins-attribut",
        {
            QUERY: "import builtins\n\nfrom app.core import legacy\n\n\ndef test_has():\n"
            '    assert builtins.hasattr(legacy, "bump")\n'
        },
        'builtins.hasattr(state, "bump")',
    ),
    (
        "m1d-getattr-alias",
        {
            QUERY: "from app.core import legacy\n\nget = getattr\n\n\ndef test_get():\n"
            '    assert get(legacy, "bump", None) is not None\n'
        },
        'get(state, "bump", None)',
    ),
    (
        "alias-aus-anderem-modul",
        {
            ALIAS: '"""Ein Alias zum Weiterreichen."""\n\nhas = hasattr\n',
            QUERY: "from app.core import legacy\nfrom tests.query_alias import has\n\n\n"
            'def test_has():\n    assert has(legacy, "bump")\n',
        },
        'has(state, "bump")',
    ),
    (
        "setattr-legt-an",
        {
            QUERY: "from app.core import legacy\n\n\ndef test_set():\n"
            '    setattr(legacy, "COUNT", 3)\n'
        },
        'setattr(state, "COUNT", 3)',
    ),
]
MODULE_IDS = [form[0] for form in MODULE_FORMS]


@pytest.mark.parametrize(("label", "extra", "expected"), MODULE_FORMS, ids=MODULE_IDS)
def test_a_query_through_a_detour_follows_the_cut(
    tmp_path: Path, label: str, extra: dict[str, str], expected: str
) -> None:
    """Der Planer schreibt die Stelle wie ``hasattr(M, "N")`` um, und der Beweis bestätigt es."""
    root, result = _run(tmp_path, fx.MODULE_OLD | extra, fx.MODULE_CUT)
    assert result.status == "written", (
        label,
        result.problems,
        result.proof and result.proof.text(),
    )
    text = (root / QUERY).read_text(encoding="utf-8")
    assert expected in text, (label, text)


#: Dazu die Formen, die der Auflöser selbst als Bezug nennt (CS-27): ``hasattr`` und
#: ``getattr`` mit Vorgabe über den eingebauten Namen.
SINGLE_FORMS = [
    *MODULE_FORMS,
    (
        "hasattr",
        {
            QUERY: "from app.core import legacy\n\n\ndef test_has():\n"
            '    assert hasattr(legacy, "bump")\n'
        },
        'hasattr(state, "bump")',
    ),
    (
        "getattr-mit-vorgabe",
        {
            QUERY: "from app.core import legacy\n\n\ndef test_get():\n"
            '    assert getattr(legacy, "bump", None) is not None\n'
        },
        'getattr(state, "bump", None)',
    ),
]


@pytest.mark.parametrize(
    ("label", "extra", "expected"), SINGLE_FORMS, ids=[form[0] for form in SINGLE_FORMS]
)
def test_every_query_is_rewritten_by_exactly_one_way(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    extra: dict[str, str],
    expected: str,
) -> None:
    """Was der Auflöser als Bezug nennt (``getattr``, ``hasattr``, auch über einen Alias derselben
    Datei), stellt die Bezugsschleife um; die Aufrufsuche nur, was er nicht nennt (``setattr``,
    ein Alias aus einem anderen Modul). Jede Stelle wird genau einmal umgestellt — zwei Wege für
    dieselbe Form liefen sonst auseinander (Zwilling)."""
    seen: list[tuple[str, int]] = []
    original = move_refs.FileRewrite.retarget_getattr

    def counted(self: move_refs.FileRewrite, line: int, col: int, *rest: str) -> None:
        seen.append((self.path, line))
        original(self, line, col, *rest)

    monkeypatch.setattr(move_refs.FileRewrite, "retarget_getattr", counted)
    root, result = _run(tmp_path, fx.MODULE_OLD | extra, fx.MODULE_CUT)
    assert result.status == "written", (label, result.problems)
    assert expected in (root / QUERY).read_text(encoding="utf-8"), label
    assert len([line for path, line in seen if path == QUERY]) == 1, (label, seen)


@pytest.mark.parametrize(("label", "extra", "expected"), MODULE_FORMS, ids=MODULE_IDS)
def test_a_query_through_a_detour_left_standing_is_red(
    tmp_path: Path, label: str, extra: dict[str, str], expected: str
) -> None:
    proof = _prove(tmp_path, fx.MODULE_OLD | extra, MODULE_EXPECTED | extra, fx.MODULE_CUT)
    assert not proof.ok, f"{label}: Beweis grün\n{proof.text()}"
    name = "COUNT" if "COUNT" in expected else "bump"
    where = f"{QUERY}:"
    assert any(where in e and f"nach {name}" in e for e in proof.errors), (label, proof.errors)


# ------------------------------------------------------------------ Modus copies

#: (Name, Datei, Meldung): c1a und c1b sind die Sonde des Reviews; die übrigen eigene — ein
#: offener Name, ``__dict__`` und ein Alias im selben Modul.
COPIES_FORMS = [
    (
        "c1a-builtins-attribut",
        "import builtins\n\nfrom app.core import consumer\n\n\ndef test_has():\n"
        '    assert builtins.hasattr(consumer, "operation")\n',
        "fragt nach der Kopie",
        "fragt app.core.consumer nach operation",
    ),
    (
        "c1b-namensraum",
        "from app.core import consumer\n\n\ndef test_has():\n"
        '    assert vars(consumer).get("operation") is not None\n',
        "liest den Namensraum des Halters app.core.consumer",
        "liest den Namensraum eines Halters",
    ),
    (
        "offener-name",
        "from app.core import consumer\n\n\ndef pick(name: str) -> object:\n"
        "    return getattr(consumer, name, None)\n",
        "liest den Namensraum des Halters app.core.consumer",
        "liest den Namensraum eines Halters",
    ),
    (
        "dict-des-halters",
        "from app.core import consumer\n\n\ndef test_has():\n"
        '    assert "operation" in consumer.__dict__\n',
        "liest den Namensraum des Halters app.core.consumer",
        "liest den Namensraum eines Halters",
    ),
    (
        "alias",
        "from app.core import consumer\n\nhas = hasattr\n\n\ndef test_has():\n"
        '    assert has(consumer, "operation")\n',
        "fragt nach der Kopie",
        "fragt app.core.consumer nach operation",
    ),
]
COPIES_IDS = [form[0] for form in COPIES_FORMS]


@pytest.mark.parametrize(("label", "text", "plan", "proof"), COPIES_FORMS, ids=COPIES_IDS)
def test_a_holder_read_through_a_detour_is_rejected(
    tmp_path: Path, label: str, text: str, plan: str, proof: str
) -> None:
    files = fx.COPIES_OLD | {QUERY: text}
    root, result = _run(tmp_path, files, fx.COPIES_CUT)
    assert result.status == "rejected", (label, result.status, result.problems)
    assert any(plan in p and " — " in p for p in result.problems), (label, result.problems)
    assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in files.items()}


@pytest.mark.parametrize(
    "text",
    [
        COPIES_FORMS[0][1],
        COPIES_FORMS[4][1],
        "from app.core import consumer\n\n\ndef test_has():\n"
        '    assert hasattr(consumer, "operation")\n',
    ],
    ids=["builtins-attribut", "alias", "hasattr"],
)
def test_a_query_on_a_copy_is_rejected_by_one_way(tmp_path: Path, text: str) -> None:
    """``hasattr`` auf eine Kopie nennt der Auflöser als Bezug (CS-27): Die Bezugsschleife weist
    es ab, die Aufrufsuche nicht noch einmal — eine Stelle, ein Fund."""
    _root, result = _run(tmp_path, fx.COPIES_OLD | {QUERY: text}, fx.COPIES_CUT)
    found = [p for p in result.problems if p.startswith(f"{QUERY}:")]
    assert len(found) == 1, result.problems
    assert "fragt nach der Kopie" in found[0], found


@pytest.mark.parametrize(("label", "text", "plan", "proof"), COPIES_FORMS, ids=COPIES_IDS)
def test_a_holder_read_through_a_detour_left_standing_is_red(
    tmp_path: Path, label: str, text: str, plan: str, proof: str
) -> None:
    found = _prove(
        tmp_path, fx.COPIES_OLD | {QUERY: text}, COPIES_EXPECTED | {QUERY: text}, fx.COPIES_CUT
    )
    assert not found.ok, f"{label}: Beweis grün\n{found.text()}"
    assert any(proof in e for e in found.errors), (label, found.errors)


def test_the_tree_binds_no_alias_it_does_not_have(tmp_path: Path) -> None:
    """Die Namen, unter denen der Baum die Funktionen ruft, wachsen nur um echte Aliasse: Ein
    beliebiger Import mit ``as`` ist keiner (die Datei würde sonst ohne Grund gelesen)."""
    from tools.code_index import Index
    from tools.move_forms import Calls
    from tools.move_trees import tree_files

    files = fx.MODULE_OLD | {
        ALIAS: '"""Ein Alias zum Weiterreichen."""\n\nhas = hasattr\n',
        QUERY: "from app.core import legacy as lg\nfrom tests.query_alias import has as ask\n",
    }
    root = fx.write_tree(tmp_path, files)
    calls = Calls(Index.build(root, cache=False), tree_files(root))
    assert {"has", "ask"} <= calls.names
    assert "lg" not in calls.names


def test_an_open_holder_read_declared_in_open_names_passes(tmp_path: Path) -> None:
    """``[[open_names]]`` erklärt an Datei und Bereich, dass der offene Name keine Kopie liest
    (die Lage zweier Stellen der K-Trockenprobe); Planer und Beweis nehmen es an. Eine
    Erklärung, die nichts trifft, ist ein Fund."""
    text = COPIES_FORMS[2][1]
    declared = fx.COPIES_CUT + f'\n[[open_names]]\npath = "{QUERY}"\nscope = "pick"\n'
    _root, result = _run(tmp_path / "plan", fx.COPIES_OLD | {QUERY: text}, declared)
    assert result.status == "written", (result.problems, result.proof and result.proof.text())
    found = _prove(
        tmp_path / "proof", fx.COPIES_OLD | {QUERY: text}, COPIES_EXPECTED | {QUERY: text}, declared
    )
    assert found.ok, found.text()
    assert "erklärt in open_names" in found.text()
    _root, result = _run(tmp_path / "leer", fx.COPIES_OLD, declared)
    assert result.status == "rejected", result.problems
    assert any(f"open_names ({QUERY}, pick) trifft keinen" in p for p in result.problems)


# ------------------------------------------------------------------ Skripte für python -c

#: Ein Test, der ``app.core.legacy.bump`` und die Kopie ``app.core.consumer.operation`` nur im
#: Text eines Skripts für ``python -c`` liest (CS-18).
SCRIPT_TEXT = (
    "import subprocess\nimport sys\n\n\ndef test_script():\n"
    "    subprocess.run([sys.executable, '-c', {script!r}])\n"
)


@pytest.mark.parametrize(
    ("label", "old", "cut", "script", "expected"),
    [
        (
            "modul",
            fx.MODULE_OLD,
            fx.MODULE_CUT,
            "from app.core.legacy import bump\nbump()\n",
            "Skript für python -c liest app.core.legacy.bump — vor dem Schnitt im Skripttext "
            "auf app.core.legacy.state.bump umschreiben",
        ),
        (
            "kopie",
            fx.COPIES_OLD,
            fx.COPIES_CUT,
            "from app.core.consumer import operation\noperation(1)\n",
            "Skript für python -c liest die Kopie app.core.consumer.operation — vor dem Schnitt "
            "im Skripttext auf app.core.engine.compute umschreiben",
        ),
    ],
    ids=["modul", "kopie"],
)
def test_a_reference_in_a_script_names_the_script_text(
    tmp_path: Path, label: str, old: dict[str, str], cut: str, script: str, expected: str
) -> None:
    """RR2-7: Im Skripttext ist der Bezug schon ein Import; die Handlung nennt das Skript und
    das Ziel, nicht „als Import oder Attribut schreiben“, und der Baum bleibt, wie er war."""
    files = old | {QUERY: SCRIPT_TEXT.format(script=script)}
    root, result = _run(tmp_path, files, cut)
    assert result.status == "rejected", (label, result.status, result.problems)
    found = [p for p in result.problems if p.startswith(f"{QUERY}:")]
    # Daneben nennt die Zeichenkette im Modus module die alte Quelle — eine eigene Prüfung.
    assert f"{QUERY}:6: {expected}" in found, (label, result.problems)
    assert not [p for p in found if "als Import oder Attribut" in p], (label, found)
    assert fx.tree_bytes(root) == {p: fx.text_of(t).encode("utf-8") for p, t in files.items()}


#: ``getattr(M, "N")`` ohne Vorgabe, über den eingebauten Namen und über einen Alias derselben
#: Datei: Bezug oder W5-Fund entscheidet der Auflöser (CS-27, RR2-8).
GETATTR_WITHOUT_DEFAULT = [
    "from app.core import legacy\n\n\ndef test_get():\n    assert getattr(legacy, 'bump')\n",
    "from app.core import legacy\n\nlook = getattr\n\n\ndef test_get():\n"
    "    assert look(legacy, 'bump')\n",
]


@pytest.mark.parametrize("text", GETATTR_WITHOUT_DEFAULT, ids=["eingebaut", "alias"])
def test_a_getattr_without_default_left_standing_is_reported_once(
    tmp_path: Path, text: str
) -> None:
    """RR2-8: Die Leere von ``getattr(M, "N")`` ohne Vorgabe meldet der Auflöser als W5, über
    den eingebauten Namen wie über einen Alias derselben Datei (CS-27); der Beweis meldet sie
    nicht noch einmal als Abfrage."""
    extra = {QUERY: text}
    proof = _prove(tmp_path, fx.MODULE_OLD | extra, MODULE_EXPECTED | extra, fx.MODULE_CUT)
    found = [error for error in proof.errors if QUERY in error]
    assert len(found) == 1, found
    assert "getattr-Bezug app.core.legacy.bump" in found[0] and "(W5)" in found[0], found


@pytest.mark.parametrize(
    ("text", "counted"),
    [
        *((text, 0) for text in GETATTR_WITHOUT_DEFAULT),
        (
            "from app.core import legacy\n\n\ndef test_get():\n"
            "    assert getattr(legacy, 'bump', None)\n",
            1,
        ),
        (
            "from app.core import legacy\n\n\ndef test_has():\n"
            "    assert hasattr(legacy, 'bump')\n",
            1,
        ),
    ],
    ids=["eingebaut", "alias", "mit-vorgabe", "hasattr"],
)
def test_the_query_ground_set_leaves_a_getattr_without_default_to_the_resolver(
    tmp_path: Path, text: str, counted: int
) -> None:
    """RR2-8, RR2-15: Nach dem Schnitt gibt es ``state.bump``; ein ``getattr`` ohne Vorgabe darauf
    führt der Auflöser als Bezug, auch über einen Alias — die Grundmenge ``queries`` des
    Beweises zählt es nicht ein zweites Mal. Gegenprobe: ``getattr`` mit Vorgabe und ``hasattr``
    zählt sie, deren Leere meldet der Auflöser nicht."""
    _root, result = _run(tmp_path, fx.MODULE_OLD | {QUERY: text}, fx.MODULE_CUT)
    assert result.status == "written", result.problems
    assert result.proof is not None and result.proof.ok, result.proof and result.proof.text()
    assert result.proof.counts["queries"] == counted, result.proof.text()
