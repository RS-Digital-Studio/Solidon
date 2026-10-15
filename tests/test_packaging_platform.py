"""Was die Linux- und Mac-Pakete zusätzlich halten, vom Bau bis zum ersten Start.

Die Linux-Grenze an jeder Hülle, die das Paket verlässt; die Erprobung des
Fensterstarts auf dem Intel-Mac samt ihrer Ergebniszeile; keine Pipe in einen
Leser, der vor dem Ende aufhört und unter ``pipefail`` den Schritt abbricht;
das Flatpak ohne installierte Pakete; das 3D-Maus-Modul der Spec; ein
macOS-Paket, das nicht umzieht, keine Bibliothek des Läufers mitnimmt und seine
Bundle-Version trägt. Die CI-Blöcke laufen dabei in der bash von Git, nie im
Starter von WSL.

Die Prüfungen stehen neben ``tests/test_packaging.py`` in eigener Datei: Jene
hat über 2 000 Zeilen und bekommt in der Sperrklinke keine neue Definition mehr
(Codestruktur, Regel 6). Orte und gemeinsame Helfer kommen aus
``tests/packaging_helpers.py``, Jobs und Schritte der Workflows aus
``tests/workflow_helpers.py``.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Final

import pytest

from tests.packaging_helpers import ROOT, SPEC, WORKFLOW, start_report, workflow_shell
from tests.shell_helpers import bash_executable
from tests.workflow_helpers import job_block, step_block


def test_the_spec_packs_the_hid_module_the_spacemouse_reader_chooses() -> None:
    """Unter Linux ``hidraw`` und kein ``hid`` (libusb fällt damit aus dem Paket).

    Dieselbe Wahl wie ``app.ui.spacemouse.hid_module_name``; ein Paket ohne das
    gewählte Modul ließe die 3D-Maus still.
    """
    from app.ui.spacemouse import hid_module_name

    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    choice = ast.unparse(
        ast.parse('"hidraw" if sys.platform.startswith("linux") else "hid"', mode="eval").body
    )
    hidden = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "hiddenimports" for t in node.targets)
    )
    assert isinstance(hidden, ast.List)
    assert choice in [ast.unparse(element) for element in hidden.elts]
    assert ast.unparse(hidden).count("'hid'") == 1, "hid steht zusätzlich fest in der Liste"
    analysis = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Analysis"
    )
    excludes = next(word.value for word in analysis.keywords if word.arg == "excludes")
    assert "*(['hid'] if sys.platform.startswith('linux') else [])" in ast.unparse(excludes)
    for platform, module in (("linux", "hidraw"), ("win32", "hid"), ("darwin", "hid")):
        assert hid_module_name(platform) == module


def _assert_linux_floor_is_checked(workflow: str) -> None:
    """Die Linux-Grenze hält jeden Baum, bevor er eingepackt oder ausgeliefert wird."""
    package = job_block(workflow, "package")
    step = step_block(package, "Linux-Grenze prüfen (glibc und Bibliotheken des Rechners)")
    assert "        if: runner.os == 'Linux'\n" in step
    assert "run: python tools/check_glibc_floor.py dist/Solidon3D\n" in step
    assert "continue-on-error" not in step
    names = re.findall(r"(?m)^      - name: (.+)$", package)
    floor = names.index("Linux-Grenze prüfen (glibc und Bibliotheken des Rechners)")
    for later in ("Archiv packen (Linux)", "AppImage bauen (Linux)"):
        assert floor < names.index(later), f"{later} packt einen ungeprüften Baum"
    flatpak = job_block(workflow, "linux-flatpak")
    assert "python tools/check_glibc_floor.py dist/Solidon3D\n" in step_block(
        flatpak, "Gebauten Baum auspacken"
    )
    release = step_block(
        job_block(workflow, "linux-release-check"), "Releasebelege fail-closed prüfen"
    )
    # Ein Kommentar sichert nichts zu — nur ausgeführte Zeilen zählen.
    release = "".join(
        line for line in release.splitlines(keepends=True) if not line.lstrip().startswith("#")
    )
    assert 'python tools/check_glibc_floor.py "$artifact"\n' in release
    assert "python tools/check_glibc_floor.py appimage-content/squashfs-root\n" in release
    assert "continue-on-error" not in job_block(workflow, "linux-release-check")


def test_the_linux_floor_is_checked_on_the_tree_and_on_every_shell() -> None:
    """Baum im Paketjob, derselbe Baum vor dem Flatpak, Archiv und AppImage in der Releaseakte."""
    _assert_linux_floor_is_checked(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("        run: python tools/check_glibc_floor.py dist/Solidon3D\n", "        run: true\n"),
        (
            '          python tools/check_glibc_floor.py "$artifact"\n',
            '          # python tools/check_glibc_floor.py "$artifact"\n',
        ),
        ("          python tools/check_glibc_floor.py appimage-content/squashfs-root\n", ""),
        ("          python tools/check_glibc_floor.py dist/Solidon3D\n", ""),
        (
            "- name: Linux-Grenze prüfen (glibc und Bibliotheken des Rechners)\n",
            "- name: Linux ansehen\n",
        ),
    ],
)
def test_the_linux_floor_guard_rejects_a_weakened_workflow(before: str, after: str) -> None:
    """Gegenproben: Schritt leer, Prüfung auskommentiert, eine Hülle ausgelassen, umbenannt."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert before in workflow
    with pytest.raises((AssertionError, ValueError)):
        _assert_linux_floor_is_checked(workflow.replace(before, after, 1))


def test_the_intel_mac_tries_a_start_with_a_window_after_the_icon_service_is_gone() -> None:
    """Erprobung: Symboldienst aushängen, dann Start mit Fenster und 3D-Ansicht.

    Nur auf dem Intel-Mac, nach dem Pflichtstart ohne Bildschirm, und bis zwei
    Läufe grün waren mit ``continue-on-error``; die Zeile „Ergebnis:“ landet in
    der Zusammenfassung des Laufs.
    """
    job = job_block(WORKFLOW.read_text(encoding="utf-8"), "macos-release-check")
    name = "Installiertes Paket mit Fenster starten (Intel-Mac, Erprobung)"
    step = step_block(job, name)
    names = re.findall(r"(?m)^      - name: (.+)$", job)
    assert names.index("Installiertes Paket starten") < names.index(name)
    assert "        if: matrix.os == 'macos-26-intel'\n" in step
    assert "        continue-on-error: true\n" in step
    code = [line.strip() for line in step.splitlines() if not line.strip().startswith("#")]
    bootout = code.index(
        'launchctl bootout "gui/$UID/com.apple.iconservices.iconservicesagent" || true'
    )
    start = next(i for i, line in enumerate(code) if "check_frozen_start.py" in line)
    assert bootout < start
    assert "--executable /Applications/Solidon3D.app" in code[start]
    assert "--offscreen" not in code[start], "die Erprobung gilt dem Fenster"
    assert any("GITHUB_STEP_SUMMARY" in line and "^Ergebnis:" in line for line in code)


@pytest.mark.parametrize("started", [0, 1])
def test_the_window_trial_always_writes_its_outcome_and_ends_with_the_start(
    tmp_path: Path, started: int
) -> None:
    """Auch ein roter Fensterstart schreibt „Ergebnis:“ in die Zusammenfassung (Review 1, G1).

    Der Schritt läuft wie in der CI mit ``set -euo pipefail``; ``launchctl`` und
    der Starttest sind Attrappen. Vorher endete ein roter Start vor dem
    Schreiben der Zeile — die Erprobung sagte dann nicht, wie weit sie kam.
    """
    shell = workflow_shell()
    if shell is None:
        pytest.skip("ohne bash lässt sich der CI-Block nicht ausführen")
    job = job_block(WORKFLOW.read_text(encoding="utf-8"), "macos-release-check")
    step = step_block(job, "Installiertes Paket mit Fenster starten (Intel-Mac, Erprobung)")
    script = textwrap.dedent(step.split("        run: |\n", 1)[1])
    stand_ins = (
        "launchctl() { :; }\n"
        f"python() {{ echo 'Ergebnis: Plattform cocoa'; return {started}; }}\n"
    )
    summary = tmp_path / "summary.md"
    done = subprocess.run(
        [shell, "-c", stand_ins + script],
        cwd=tmp_path,
        env=dict(
            os.environ,
            PATH=os.pathsep.join((str(Path(shell).parent), os.environ.get("PATH", ""))),
            GITHUB_STEP_SUMMARY=str(summary),
            UID="501",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert done.returncode == started, done.stderr
    assert summary.read_text(encoding="utf-8").startswith("Ergebnis: Plattform cocoa")


def test_a_wsl_starter_ahead_of_git_in_the_search_path_never_runs_the_ci_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Steht WSL vor Git im Suchpfad, fahren die Workflowtests ihre Blöcke in der Git-bash.

    ``which("bash")`` liefert dann ``System32\\bash.exe``, den Starter von WSL:
    Ein CI-Block liefe in einem Linux mit eigenem Dateisystem statt in der
    bash, für die er gemessen wird. ``workflow_shell`` fragt dieselbe Quelle wie
    ``bash_executable`` (``tests/shell_helpers.py``) und nimmt die bash neben
    dem installierten Git — die bash selbst, nicht den Starter aus Git, der die
    Attrappen der Tests im ``PATH`` überdeckte (Review 1 CS0 Plattform, RPL-4).
    """
    wsl = tmp_path / "Windows" / "System32" / "bash.exe"
    git = tmp_path / "Git"
    starter, bash = git / "bin" / "bash.exe", git / "usr" / "bin" / "bash.exe"
    for path in (wsl, starter, bash):
        path.parent.mkdir(parents=True)
        path.touch()
    found = {"bash": wsl, "git": git / "cmd" / "git.exe"}

    def which(name: str, *_args: object, **_kwargs: object) -> str | None:
        return str(found[name]) if name in found else None

    monkeypatch.setattr(shutil, "which", which)
    assert bash_executable() == starter
    assert workflow_shell() == str(bash)


def test_only_the_shell_helpers_look_for_bash() -> None:
    """Jede Testdatei, die Skripte fährt, fragt ``bash_executable`` (CS-30).

    ``test_suite_script.py`` suchte die bash ein drittes Mal mit
    ``which("bash")``, ohne Rückfall neben Git und ohne den WSL-Starter zu
    verwerfen: Unter dem ``PATH`` einer PowerShell übersprang es seine Fälle,
    und mit WSL vorn liefe das Tor-Skript in einem Linux.
    """
    asking = sorted(
        path.name
        for path in (ROOT / "tests").glob("*.py")
        if re.search(r"""which\(\s*["']bash["']""", path.read_text(encoding="utf-8"))
        and path.name not in {"shell_helpers.py", Path(__file__).name}
    )
    assert asking == []


def test_the_start_check_says_in_one_line_how_far_the_start_came() -> None:
    """Die Erprobung mit Fenster auf dem Intel-Mac darf rot werden; ihre Zeile sagt, warum."""
    from tools.check_frozen_start import outcome

    drawn = outcome(start_report(platform="cocoa"))
    assert drawn == (
        "Ergebnis: Plattform cocoa · Fenster sichtbar ja · 3D-Ansicht ja (GfxRenderer, "
        "hellster Wert 74)"
    )
    missing = outcome(start_report(platform="cocoa", renderer={"present": False}))
    assert "3D-Ansicht nein" in missing
    hidden = outcome(start_report(window={"visible": False}))
    assert "Fenster sichtbar nein" in hidden
    broken = start_report(renderer={"present": True, "error": "Metal lost"})
    assert "Fehler: Metal lost" in outcome(broken)
    assert outcome(None).startswith("Ergebnis: kein Bericht")


#: Leser, die vor dem Ende ihrer Eingabe aufhören. Hinter einer Pipe bekommt der
#: Erzeuger dann SIGPIPE, endet mit 141, und unter ``pipefail`` (``shell: bash``
#: setzt es) bricht der ganze Schritt ab — gemessen an ``ldconfig -p | awk
#: '… exit'`` (Review 1, S3).
_EARLY_READER: Final = re.compile(
    r"\|\s*(?:head\b"
    r"|read\b"
    r"|grep\b[^|]*\s(?:-[A-Za-z]*[qm][A-Za-z0-9]*\b|--(?:quiet|silent|max-count)\b)"
    r"|awk\b(?:[^|&;)'\"]|'[^']*'|\"[^\"]*\")*?"
    r"(?:'[^']*\bexit\b[^']*'|\"[^\"]*\bexit\b[^\"]*\"|\bexit\b)"
    r"|sed\b[^|]*(?:\s|['\";{])(?:\d+|/[^/]+/)?\s*[qQ](?=\s|['\";}]|$))"
)


def _early_readers(text: str) -> list[str]:
    """Jede ausgeführte Zeile mit einer Pipe in einen früh endenden Leser."""
    return [
        line.strip()
        for line in text.splitlines()
        if not line.lstrip().startswith("#") and _EARLY_READER.search(line)
    ]


def test_no_pipe_in_any_workflow_ends_its_reader_early() -> None:
    """``| head``, ``| grep -q``, ``| awk '… exit'`` und Verwandte enden mit 141 unter pipefail.

    Jeder Workflow, nicht nur ``build.yml``: ``shell: bash`` heißt bei GitHub
    ``-eo pipefail``, und ``slicer-auswahl.yml`` trug dieselbe Bauart.
    """
    paths = sorted(WORKFLOW.parent.glob("*.yml"))
    assert WORKFLOW in paths, "build.yml muss in der geprüften Workflowmenge liegen"
    found = [
        f"{path.name}: {line}"
        for path in paths
        for line in _early_readers(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_the_early_reader_guard_rejects_an_empty_workflow_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein falscher Workflowpfad darf nicht bedeuten, dass alle Pipes sicher sind."""
    monkeypatch.setattr(sys.modules[__name__], "WORKFLOW", tmp_path / "build.yml")
    with pytest.raises(AssertionError, match=r"build\.yml"):
        test_no_pipe_in_any_workflow_ends_its_reader_early()


@pytest.mark.parametrize(
    ("line", "early"),
    [
        ("cxx=$(ldconfig -p | awk '/libstdc/ {print $NF; exit}')", True),
        ('echo "$(ldd --version | head -n 1)"', True),
        ("lipo -archs app | tr ' ' '\\n' | grep -qx 'arm64'", True),
        ("find . -name x | grep -m 1 y", True),
        ("find . -name x | grep -m1 y", True),
        ("find . -name x | grep --silent y", True),
        ("find . -name x | grep --max-count=1 y", True),
        ("find . -name x | grep -im1 y", True),
        ("seq 9 | sed '1q'", True),
        ("seq 9 | sed q", True),
        ("seq 9 | sed Q", True),
        ("seq 9 | sed 1q", True),
        ('seq 9 | sed "1q"', True),
        ("seq 9 | sed '1Q'", True),
        ('seq 9 | sed "1Q"', True),
        ("seq 9 | sed -e 3q", True),
        ("seq 9 | sed -n '1p;3q'", True),
        ("seq 9 | sed '/3/q'", True),
        ("seq 9 | read -r value", True),
        ("seq 9 | awk '$1 == 2 || $1 == 3 {print; exit}'", True),
        ('seq 9 | awk "$1 == 2 || $1 == 3 {print; exit}"', True),
        ("cxx=$(ldconfig -p | awk '/x/ && !found {print $NF; found = 1}')", False),
        ("seq 9 | awk '$1 == 2 || $1 == 3 {print}'", False),
        ("seq 9 | awk '{print}' || exit 1", False),
        ('echo "$(ldd --version | sed -n 1p)"', False),
        ("printf quote | sed 's/quote/x/'", False),
        ('printf quote | sed "s/quote/x/"', False),
        ("find . -name x | grep -c y", False),
        ("find . -name x | grep -l y", False),
        ("find . -name x | grep -L y", False),
        ("lipo -archs app | tr ' ' '\\n' | grep -x 'arm64' > /dev/null", False),
        ("grep -ao 'GLIBCXX' lib | sort -uV | tail -n 1", False),
        ("# ldconfig -p | head -n 1", False),
    ],
)
def test_the_early_reader_guard_knows_the_pattern(line: str, early: bool) -> None:
    """Gegenproben: die Zeilen vor der Fixrunde und ihre Ersatzformen."""
    assert bool(_early_readers(line)) is early


#: Was die Linux-Jobs ohne installierte Abhängigkeiten aufrufen: ``linux-flatpak``
#: (Beschreibungen, Manifest, Grenze, Starttest) und ``linux-release-start``.
_WITHOUT_PACKAGES: Final = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, sys.argv[1])
    from tools import check_frozen_start, check_glibc_floor, make_linux_packages as tool
    for build in (tool.desktop_entry, tool.flatpak_manifest, tool.metainfo,
                  tool.mime_definition, tool.install_script):
        assert build()
    assert "--device=all" in tool.flatpak_manifest()
    print("ohne Pakete")
    """
)


def test_the_flatpak_job_needs_no_installed_package() -> None:
    """``linux-flatpak`` installiert kein Paket — Manifest und Starttest laufen ohne.

    Bis zur Fixrunde las das Manifest die Slicer-Kennungen aus
    ``app.core.tools``, und das zog über die Backends numpy nach; der Job wäre
    am ersten Import gestorben. ``python -S`` lädt keine site-packages.
    """
    done = subprocess.run(
        [sys.executable, "-S", "-c", _WITHOUT_PACKAGES, str(ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert done.returncode == 0 and "ohne Pakete" in done.stdout, done.stderr[-3000:]
    for job in ("linux-flatpak", "linux-release-start"):
        assert "pip install" not in job_block(WORKFLOW.read_text(encoding="utf-8"), job), job


#: Die ``PackageInfo`` des Pakets 0.6.0 (Intel, Tag-Lauf 38170638968), gebaut
#: mit ``pkgbuild --component``: umziehbar und mit Versionssperre.
_RELOCATABLE_PACKAGE_INFO = """<?xml version="1.0" encoding="utf-8"?>
<pkg-info overwrite-permissions="true" relocatable="false"
    identifier="de.rsdigital.solidon3d" postinstall-action="none" version="0.6.0"
    format-version="2" generator-version="InstallCmds-864.12 (25G76)"
    install-location="/Applications" auth="root">
    <payload numberOfFiles="2008" installKBytes="510386"/>
    <bundle id="de.rsdigital.solidon3d" CFBundleShortVersionString="0.6.0" path="./Solidon3D.app"/>
    <bundle-version>
        <bundle id="de.rsdigital.solidon3d"/>
    </bundle-version>
    <upgrade-bundle>
        <bundle id="de.rsdigital.solidon3d"/>
    </upgrade-bundle>
    <update-bundle/>
    <atomic-update-bundle/>
    <strict-identifier>
        <bundle id="de.rsdigital.solidon3d"/>
    </strict-identifier>
    <relocate>
        <bundle id="de.rsdigital.solidon3d"/>
    </relocate>
</pkg-info>"""


def test_the_macos_package_check_rejects_the_relocatable_package_of_0_6_0() -> None:
    """Die Prüfung erkennt am echten Paket, was den Kunden die alte Kopie starten ließ.

    ``<relocate>``: Der Installer aktualisiert eine Kopie gleicher Kennung dort,
    wo sie liegt, und ``/Applications`` bleibt alt. ``<bundle-version>``: Er
    überspringt das Bundle still, wenn am Ziel eine höhere Nummer liegt.
    """
    from tools import make_macos_package as tool

    problems = tool.package_info_problems(_RELOCATABLE_PACKAGE_INFO)
    assert any("<relocate>" in problem for problem in problems), problems
    assert any("<bundle-version>" in problem for problem in problems), problems

    settled = re.sub(
        r"<(relocate|bundle-version)>.*?</\1>", "", _RELOCATABLE_PACKAGE_INFO, flags=re.DOTALL
    )
    assert tool.package_info_problems(settled) == []

    elsewhere = settled.replace('install-location="/Applications"', 'install-location="/tmp"')
    assert tool.package_info_problems(elsewhere), "ein anderes Ziel fiele durch"
    renamed = settled.replace('path="./Solidon3D.app"', 'path="./Other.app"')
    assert tool.package_info_problems(renamed), "ein anderer Bundlepfad fiele durch"


def test_the_macos_package_is_built_from_a_component_list_that_does_not_relocate() -> None:
    """``pkgbuild --component`` nimmt keine Komponentenliste — gebaut wird über ``--root``.

    Jede Ebene der Analyse (das Bundle und seine eingebetteten Frameworks)
    bekommt dieselben Werte; eine Wurzel mit mehr als dem Bundle hält an.
    """
    import inspect

    from tools import make_macos_package as tool

    analysed = [
        {
            "RootRelativeBundlePath": "Solidon3D.app",
            "BundleIsRelocatable": True,
            "BundleIsVersionChecked": True,
            "BundleHasStrictIdentifier": True,
            "BundleOverwriteAction": "upgrade",
            "ChildBundles": [
                {
                    "RootRelativeBundlePath": "Solidon3D.app/Contents/Frameworks/QtCore.framework",
                    "BundleOverwriteAction": "update",
                }
            ],
        }
    ]
    settled = tool.component_settings(analysed)
    assert analysed[0]["BundleIsRelocatable"] is True, "die Eingabe bleibt unberührt"
    for entry in (settled[0], settled[0]["ChildBundles"][0]):
        assert entry["BundleIsRelocatable"] is False
        assert entry["BundleIsVersionChecked"] is False
        assert entry["BundleOverwriteAction"] == "upgrade"
    assert settled[0]["BundleHasStrictIdentifier"] is True

    with pytest.raises(ValueError, match="Nutzlastwurzel"):
        tool.component_settings([*analysed, {"RootRelativeBundlePath": "Fremd.app"}])

    root, plist, component = Path("root"), Path("component.plist"), Path("component.pkg")
    assert tool.analyse_command(root, plist) == [
        "pkgbuild",
        "--analyze",
        "--root",
        str(root),
        str(plist),
    ]
    command = tool.component_command(root, plist, component)
    assert "--component" not in command, "ohne Komponentenliste ist das Paket umziehbar"
    assert command[command.index("--root") + 1] == str(root)
    assert command[command.index("--component-plist") + 1] == str(plist)
    assert command[command.index("--install-location") + 1] == "/Applications"
    assert command[-1] == str(component)

    source = inspect.getsource(tool.build)
    assert "component_command(" in source and "component_settings(" in source
    assert "check_package(target)" in source, "das gebaute Paket wird nicht nachgelesen"


#: Was PyInstaller im Intel-Paketjob von 0.6.0 einsammelte, gekürzt: die
#: Homebrew-Kopie über die ctypes-Analyse von freetype-py, daneben die Räder.
_SITE = "/Users/runner/hostedtoolcache/Python/3.14.8/x64/lib/python3.14/site-packages"
_MAC_BINARIES = [
    ("libfreetype.dylib", "/usr/local/lib/libfreetype.dylib", "BINARY"),
    ("freetype/libfreetype.dylib", f"{_SITE}/freetype/libfreetype.dylib", "BINARY"),
    ("PIL/.dylibs/libfreetype.6.dylib", f"{_SITE}/PIL/.dylibs/libfreetype.6.dylib", "BINARY"),
    ("PIL/.dylibs/libpng16.16.dylib", f"{_SITE}/PIL/.dylibs/libpng16.16.dylib", "BINARY"),
    ("libpng16.16.dylib", "PIL/.dylibs/libpng16.16.dylib", "SYMLINK"),
    ("Python", "/Library/Frameworks/Python.framework/Versions/3.14/Python", "BINARY"),
]


def test_the_macos_bundle_takes_no_library_from_the_runners_package_manager() -> None:
    """Eine Bibliothek aus Homebrew oder MacPorts reist nicht mit.

    Bringt ein Rad dieselbe mit, fällt die Runner-Kopie weg (freetype-py lädt
    zuerst seine eigene); bringt keines sie mit, hält der Bau an, statt eine
    Datei ohne Besitzer und belegte Fassung auszuliefern.
    """
    from tools import make_macos_package as tool

    kept = tool.trim_foreign_macos_binaries(_MAC_BINARIES)
    assert kept == _MAC_BINARIES[1:], "nur die Homebrew-Kopie fällt weg"

    for prefix in ("/opt/homebrew/lib", "/opt/local/lib", "/usr/local/Cellar/libpng/1.6/lib"):
        dependency = ("libpng16.16.dylib", f"{prefix}/libpng16.16.dylib", "BINARY")
        assert dependency not in tool.trim_foreign_macos_binaries([*_MAC_BINARIES, dependency])

    alone = ("libgmp.10.dylib", "/opt/homebrew/lib/libgmp.10.dylib", "BINARY")
    with pytest.raises(ValueError, match=re.escape("libgmp.10.dylib")):
        tool.trim_foreign_macos_binaries([*_MAC_BINARIES, alone])
    outside = [entry for entry in _MAC_BINARIES if not entry[0].startswith("freetype/")]
    outside = [entry for entry in outside if not entry[0].startswith("PIL/.dylibs/libfreetype")]
    with pytest.raises(ValueError, match=re.escape("libfreetype.dylib")):
        tool.trim_foreign_macos_binaries(outside)
    # Nur ein Rad zählt als Besitzer, nicht irgendeine Datei gleichen Namens.
    framework = "/Library/Frameworks/Python.framework/Versions/3.14/lib/libssl.3.dylib"
    named = [
        *_MAC_BINARIES,
        ("libssl.3.dylib", framework, "BINARY"),
        ("libssl.3.dylib", "/usr/local/opt/openssl@3/lib/libssl.3.dylib", "BINARY"),
    ]
    with pytest.raises(ValueError, match=re.escape("openssl@3")):
        tool.trim_foreign_macos_binaries(named)

    spec = SPEC.read_text(encoding="utf-8")
    darwin = spec.split('if sys.platform == "darwin":\n    try:', 1)
    assert len(darwin) == 2, "die Spec filtert den macOS-Bau nicht"
    assert "make_macos_package.trim_foreign_macos_binaries(analysis.binaries)" in darwin[1][:200]
    assert spec.index("trim_foreign_macos_binaries") < spec.index("COLLECT("), (
        "gefiltert wird vor dem Zusammentragen"
    )


def test_the_macos_release_check_installs_next_to_a_copy_and_lands_in_applications() -> None:
    """Die Releaseakte liest die ``PackageInfo`` des signierten Pakets und prüft das Verhalten.

    Die ausgepackte Prüfkopie bleibt beim Installieren liegen — ein umziehbares
    Paket aktualisierte sie, und ``/Applications`` bliebe leer.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    step = workflow.split("- name: Installiertes Paket starten", 1)[1].split("- name:", 1)[0]

    check = step.index('make_macos_package.py --check "$package"')
    decoy = step.index("[ -d release-app/Solidon3D.app ]")
    install = step.index("sudo installer -pkg")
    landed = step.index("/Applications/Solidon3D.app/Contents/Info.plist")
    removed = step.index("rm -rf release-app")
    assert check < install and decoy < install < landed < removed, (
        "die Prüfkopie muss während der Installation liegen und danach erst weg"
    )
    assert '[ "$installed" = "$version" ]' in step
    assert "codesign --verify --deep --strict" in step, "das installierte Siegel bleibt ungeprüft"


def _macos_info_plist() -> dict[str, str]:
    """Die Schlüssel der Info.plist aus dem ``BUNDLE``-Aufruf, je mit ihrem Ausdruck."""
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BUNDLE"
    ]
    assert len(calls) == 1, "genau ein BUNDLE in der Spec"
    plist = next(word.value for word in calls[0].keywords if word.arg == "info_plist")
    assert isinstance(plist, ast.Dict)
    return {
        key.value: ast.unparse(value)
        for key, value in zip(plist.keys, plist.values, strict=True)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def test_the_macos_bundle_carries_its_build_version() -> None:
    """``CFBundleVersion`` fehlte im Paket 0.6.0 (Forensik M3).

    Apples Installer und LaunchServices vergleichen Bundles über diesen
    Schlüssel; PyInstallers ``version=`` setzt nur die angezeigte Nummer. Beide
    kommen aus derselben Quelle, damit sie nie auseinanderlaufen.
    """
    plist = _macos_info_plist()

    assert plist.get("CFBundleShortVersionString") == "APP_VERSION"
    assert plist.get("CFBundleVersion") == "APP_VERSION"
