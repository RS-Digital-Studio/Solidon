"""Ein Fall verträgt jeden Bericht der Suite und hinterlässt den Prozess, wie er ihn fand."""

import ast
from pathlib import Path
from typing import Any

import pytest

TESTS = Path(__file__).parent

#: Fixtures, die pytest nur in einen JUnit-Bericht der Familie ``xunit1``
#: schreibt. Die Läufe mit Bericht schreiben ``xunit2`` (``--junitxml`` ohne
#: Familie in ``tools/run_suite_isolated.py`` und ``build.yml``); dort lehnt
#: pytest sie mit einer Warnung ab, unter ``filterwarnings = error`` ein
#: Setup-Fehler (RD-9). Befunddaten nimmt ``record_trace`` aus ``conftest.py``.
XUNIT1_ONLY = frozenset({"record_property", "record_xml_attribute"})


def xunit1_requests(source: str) -> list[int]:
    """Zeilen, an denen Quelltext eine dieser Fixtures anfordert.

    Als Parameter einer Funktion oder als Zeichenkette in einem Aufruf
    (``getfixturevalue``, ``usefixtures``).
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments = node.args
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                if argument.arg in XUNIT1_ONLY:
                    found.append(argument.lineno)
        elif isinstance(node, ast.Call):
            for value in node.args:
                if isinstance(value, ast.Constant) and value.value in XUNIT1_ONLY:
                    found.append(value.lineno)
    return sorted(found)


def test_no_case_requests_a_fixture_the_junit_report_rejects() -> None:
    """RD-9: Kein Fall der Suite fordert ``record_property`` oder ``record_xml_attribute`` an."""
    offenders = {
        path.name: lines
        for path in sorted(TESTS.glob("*.py"))
        if (lines := xunit1_requests(path.read_text(encoding="utf-8")))
    }
    assert not offenders, (
        "Im xunit2-Bericht der CI ein Setup-Fehler; Befunddaten über record_trace "
        f"(conftest.py) ablegen: {offenders}"
    )


def test_the_scan_finds_every_way_of_requesting_them() -> None:
    """Gegenprobe: Parameter, ``getfixturevalue`` und ``usefixtures`` fallen auf."""
    planted = (
        "def test_a(record_property):\n"
        "    pass\n"
        'request.getfixturevalue("record_xml_attribute")\n'
        "@pytest.mark.usefixtures('record_property')\n"
        "def test_b(*, record_xml_attribute): pass\n"
        "def test_c(record_trace, record_testsuite_property): pass\n"
    )
    assert xunit1_requests(planted) == [1, 3, 4, 5]


#: Das Aussehen der Anwendung vor dem ersten der beiden folgenden Fälle.
_FOUND: list[tuple[object, ...]] = []


def _look(application: Any) -> tuple[object, ...]:
    from PySide6.QtGui import QFont, QPalette

    from app.ui import theme

    return (
        application.style().name(),
        QPalette(application.palette()),
        application.styleSheet(),
        QFont(application.font()),
        application.property("solidonTheme"),
        theme.current_theme(),
    )


def test_a_case_may_leave_theme_style_and_font_changed(qt_app: Any) -> None:
    """Erster Teil: dunkles Thema, fremder Stil und große Schrift, ohne Rückgabe.

    So hinterließ ``customer_theme`` (``test_feature_front_contract.py``) das
    dunkle Thema für jeden Nachfolger im Prozess.
    """
    from PySide6.QtGui import QFont

    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    _FOUND[:] = [_look(qt_app)]
    target = "light" if _FOUND[0][-1] == "dark" else "dark"
    apply_theme(qt_app, target)
    apply_style(qt_app, target)
    font = QFont(qt_app.font())
    font.setPointSize(font.pointSize() + 7 if font.pointSize() > 0 else 23)
    qt_app.setFont(font)
    changed = _look(qt_app)
    assert all(new != old for new, old in zip(changed[1:], _FOUND[0][1:], strict=True))


def test_the_next_case_finds_the_look_its_predecessor_found(qt_app: Any) -> None:
    """Zweiter Teil: Der Nachfolger findet alles so, wie der erste Teil es vorfand."""
    if not _FOUND:
        pytest.skip("aussagekräftig nur nach dem ersten Teil im selben Prozess")
    found = _look(qt_app)
    names = ("Stil", "Palette", "Stylesheet", "Schrift", "Themenmerker", "Thema")
    left = [name for name, now, then in zip(names, found, _FOUND[0], strict=True) if now != then]
    assert not left, f"Vom Vorgänger stehen geblieben: {left}"


def test_no_case_reaches_the_keyring_of_the_user() -> None:
    """Die Suite fragt nie den Schlüsselbund des Systems (§38).

    Wer über den Kern liest oder schreibt — LLM-Schlüssel und Gerätekennung —,
    landet im Speicher der Suite, und der nächste Fall findet ihn leer.
    """
    import keyring

    from app.core.activation import device
    from app.core.backends import keys

    suite = keyring.get_keyring()
    assert type(suite).__name__ == "SuiteKeyring", type(suite)
    assert device._load_keyring().get_keyring() is suite, "auch die Gerätekennung"
    assert not suite.values, "jeder Fall beginnt leer"
    assert keys.store("anthropic", "sk-probe")
    assert suite.values == {(keys.SERVICE, "anthropic"): "sk-probe"}
    assert keys.read("anthropic") == "sk-probe"
