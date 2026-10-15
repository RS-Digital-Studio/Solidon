"""Ein Fall verträgt jeden Bericht der Suite."""

import ast
from pathlib import Path

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
