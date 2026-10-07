"""Hält den Auslieferungsweg an unveränderlichen, knapp berechtigten Eingängen.

Windows wird hier gebaut und **nicht** signiert: Die CI übergibt den
gebundenen App-Baum, und ``tools/sign_release.py`` signiert ihn auf Roberts
Rechner mit dem Certum-Cloud-Zertifikat. Kein Job dieses Workflows darf
deshalb ein OIDC-Token anfordern oder ``signtool`` aufrufen.
"""

from __future__ import annotations

import plistlib
import re
import shlex
import textwrap
from itertools import pairwise
from pathlib import Path

from tests.workflow_helpers import job_block

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
BUILD_WORKFLOW = WORKFLOWS / "build.yml"


def _workflow() -> str:
    return BUILD_WORKFLOW.read_text(encoding="utf-8")


def _job(name: str) -> str:
    """Liefert genau einen Jobblock aus dem Bauworkflow."""
    return job_block(_workflow(), name)


def test_every_external_action_is_pinned_to_a_full_commit() -> None:
    """Ein bewegliches Tag darf zwischen Prüfung und Auslieferung keinen Code tauschen."""
    actions: list[tuple[str, str]] = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        for reference in re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", path.read_text("utf-8")):
            if reference.startswith("./"):
                continue
            actions.append((path.name, reference))

    assert actions, "kein einziger externer Action-Aufruf gefunden"
    moving = [
        f"{path}: {reference}"
        for path, reference in actions
        if not re.search(r"@[0-9a-f]{40}$", reference)
    ]
    assert not moving, "bewegliche Action-Referenzen:\n" + "\n".join(moving)


def test_checkout_never_leaves_a_repository_credential_behind() -> None:
    """Kein nachfolgender Bau- oder Testschritt braucht schreibenden Git-Zugriff."""
    workflow = _workflow()
    checkouts = workflow.count("uses: actions/checkout@")

    assert checkouts > 0
    assert workflow.count("persist-credentials: false") == checkouts


def test_signing_secrets_are_never_job_or_workflow_environment() -> None:
    """Geheimnisse gehören nur in den tatsächlich signierenden Schritt."""
    workflow = _workflow()
    broad = re.findall(r"(?m)^ {0,6}[A-Z][A-Z0-9_]*:\s*\$\{\{\s*secrets\.", workflow)

    assert not broad, "Signiergeheimnis ist workflow- oder jobweit sichtbar"
    assert not re.search(r"(?m)^\s*if:.*secrets\.", workflow), (
        "eine Bedingung darf kein Geheimnis auswerten; dafür gibt es geschützte Variablen"
    )


def test_no_job_can_request_an_oidc_token() -> None:
    """Ohne Azure gibt es keinen Grund mehr für ein kurzlebiges Token — nirgends."""
    workflow = _workflow()

    assert "id-token: write" not in workflow
    assert "id-token:" not in workflow


def test_protected_signers_never_run_repository_or_handoff_code() -> None:
    """Mit entsperrtem Schlüssel laufen nur fest definierte Signierbefehle."""
    for name in ("macos-app-sign", "macos-installer-sign"):
        job = _job(name)
        assert "environment: production-signing" in job
        assert "actions/checkout@" not in job
        assert "make_installer.py" not in job
        assert "make_macos_package.py" not in job
        assert "ISCC" not in job and "& $compiler" not in job
        assert not re.search(r"\bpython\b", job)

    windows_builder = _job("windows-installer")
    assert "environment: production-signing" not in windows_builder
    assert "id-token: write" not in windows_builder
    assert "secrets." not in windows_builder
    assert "ISCC" in windows_builder

    macos_builder = _job("macos-package")
    assert "environment: production-signing" not in macos_builder
    assert "secrets." not in macos_builder
    assert "from tools import make_macos_package" in macos_builder

    package = _job("package")
    assert "MACOS_SIGNING_MODE -notin @('signed', 'notarized', 'unsigned')" in package
    assert "WINDOWS_SIGNING_MODE" not in _workflow(), (
        "Windows hat keinen Signiermodus mehr — die Signatur entsteht lokal"
    )


def test_the_windows_handoff_is_an_exact_contained_product_tree() -> None:
    """Der Signierer lehnt Zusatzdateien, Pfadausbruch und andere Produkte ab."""
    for name in ("windows-installer",):
        job = _job(name)
        assert "input_sha256" in job
        assert "Compare-Object" in job
        assert "[IO.Path]::IsPathRooted" in job
        assert "[IO.Path]::GetFullPath" in job
        assert '"dist/Solidon3D/Solidon3D.exe"' in job
        assert '"dist/Solidon3D"' in job
        assert '"packaging/solidon3d.iss"' in job
        assert job.index("[IO.Compression.ZipFile]::OpenRead") < job.index("Expand-Archive")
        assert "ReparsePoint" in job


def test_apple_keys_are_removed_inside_the_fixed_signing_step() -> None:
    """Nach Schlüsselimport darf kein späterer Repositoryschritt den Schlüssel sehen."""
    for name in ("macos-app-sign", "macos-installer-sign"):
        job = _job(name)
        assert "trap cleanup EXIT" in job
        assert 'security delete-keychain "$keychain"' in job


def test_licence_notice_precedes_every_package_and_release_gate() -> None:
    """Notice/SBOM reisen einmal mit; Schema-Akten bleiben außerhalb des Kundenbaums."""
    package = _job("package")
    # Als Modul, nicht als Skriptpfad: `python tools/x.py` setzt sys.path auf
    # `tools/`, und `from tools import make_sbom` findet dann nichts (Tag-Lauf 10).
    notice = "python -m tools.make_licence_notices `"

    assert notice in package
    assert "--sbom $sbomPath" in package
    assert "--output $noticePath" in package
    assert "--manifest build/third-party-licenses.json" in package
    assert "$manifest.schema -ne 2" in package
    assert 'Resolve-Path "dist/Solidon3D.app"' in package
    assert 'Resolve-Path "dist/Solidon3D"' in package
    notice_index = package.index("Lizenzbeilage aus dem fertigen Kundenartefakt erzeugen")
    for later in (
        "Prüfsummengebundene Signierübergabe erzeugen (Windows)",
        "Archiv packen (Linux)",
        "Unsignierten macOS-App-Eingang packen",
    ):
        assert notice_index < package.index(later)

    assert "--release-check" not in package
    for name in ("linux-release-check", "windows-release-check", "macos-release-check"):
        job = _job(name)
        assert "environment: production-signing" not in job
        assert "--release-check" in job
        assert "--artifact-root" in job and "--sbom" in job
        assert "--release-evidence build/release-evidence.json" in job


def test_macos_checks_archive_paths_and_symlinks_before_key_import() -> None:
    """Ein gebundenes Archiv darf weder ausbrechen noch über Symlinks hinauszeigen."""
    signing = _job("macos-app-sign")

    assert signing.index("zipinfo -1") < signing.index("ditto -x -k")
    assert signing.index("Symlink verlässt App-Baum") < signing.index("APPLE_CERTIFICATE:")
    assert signing.index("App-Baum vor Schlüsselimport unveränderlich prüfen") < signing.index(
        "App mit Developer-ID signieren"
    )


def _code(script: str) -> str:
    """Der Schritt ohne Kommentarzeilen, Fortsetzungen verbunden.

    Ein Kommentar sichert nichts zu — eine auskommentierte Rücklesung zählt nicht.
    """
    lines = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    return re.sub(r"\\\n\s*", " ", "\n".join(lines))


def _commands(code: str, program: str) -> list[tuple[int, list[str]]]:
    """Die Aufrufe eines Programms als Wörter, mit ihrer Position im Code."""
    found: list[tuple[int, list[str]]] = []
    offset = 0
    for line in code.splitlines(keepends=True):
        words = shlex.split(line.strip(), comments=True) if line.strip() else []
        if words and words[0] == program:
            found.append((offset, words))
        offset += len(line)
    return found


def _has_option(words: list[str], name: str) -> bool:
    return name in words or any(word.startswith(f"{name}=") for word in words)


def _runs_hardened(words: list[str]) -> bool:
    """``--options runtime``, ``-o runtime`` oder ``--options=runtime,…`` — alles dasselbe."""
    flags = [following for word, following in pairwise(words) if word in ("--options", "-o")] + [
        word.split("=", 1)[1] for word in words if word.startswith(("--options=", "-o="))
    ]
    return any("runtime" in value.split(",") for value in flags)


def test_the_macos_app_may_map_executable_memory_for_libffi() -> None:
    """Ohne die Berechtigung hält das Intel-Paket schon beim Bootstrap an (RM-104).

    CPythons ``_ctypes`` legt beim Laden eine libffi-Closure an, und PyInstallers
    Bootstrap lädt es vor allem anderen. Apples libffi für x86_64 braucht dafür
    ausführbaren Schreibspeicher, den die Hardened Runtime ohne
    ``allow-unsigned-executable-memory`` verweigert; danach kreist libffi auf
    macOS 26 endlos. Kein Mac-Runner zeigt das, deshalb hält der Text des
    Signierschritts die Regel: tief signieren, dann nur das Hauptprogramm mit
    der Liste, und die Rücklesung bricht ab, wenn Schlüssel oder Wert fehlen.
    """
    step = _step(
        _job("macos-app-sign"), "App mit Developer-ID signieren und Schlüssel wieder sperren"
    )
    key = "com.apple.security.cs.allow-unsigned-executable-memory"
    code = _code(step)
    signing = [(at, words) for at, words in _commands(code, "codesign") if "--force" in words]
    outer = [(at, words) for at, words in signing if _has_option(words, "--entitlements")]
    deep = [(at, words) for at, words in signing if "--deep" in words]

    listed = re.search(r"<<'PLIST'\n(.*?\n)\s*PLIST\n", code, re.DOTALL)
    assert listed, "die Berechtigungsliste entsteht im Schritt selbst (kein Repositorycode)"
    assert plistlib.loads(textwrap.dedent(listed.group(1)).encode()) == {key: True}, (
        "die Liste trägt genau diese eine Ausnahme, eingeschaltet"
    )
    assert len(outer) == 1, "genau ein Signierlauf trägt die Berechtigungsliste"
    assert "--deep" not in outer[0][1], (
        "die Berechtigung gehört an das Hauptprogramm, nicht mit --deep an jede Bibliothek"
    )
    assert deep and all(_runs_hardened(words) for _, words in deep + outer), (
        "erst tief mit Hardened Runtime signieren, dann das Bundle — beide mit --options runtime"
    )
    assert max(at for at, _ in signing) == outer[0][0], (
        "der Lauf mit Berechtigung kommt zuletzt — sonst überschreibt ein späterer "
        "Lauf das Hauptprogramm wieder ohne sie"
    )

    # Die Rücklesung: eine Variable aus ``codesign -d --entitlements``, dann ein
    # ``case``, dessen Treffer-Zweig durchlässt und dessen ``*)``-Zweig abbricht.
    readback = re.search(
        r"\b(\w+)=\$\(\s*codesign\b[^\n]*?\s-d\s[^\n]*--entitlements[^\n]*\n", code
    )
    assert readback and readback.start() > outer[0][0], "die signierte App wird zurückgelesen"
    case = re.search(
        rf'case\s+"\${readback.group(1)}"\s+in\n(.*?)\n\s*esac', code[readback.end() :], re.DOTALL
    )
    assert case, "die Rücklesung entscheidet über das Gelesene"
    branches = [branch.strip() for branch in case.group(1).split(";;") if branch.strip()]
    granted = [b for b in branches if f"<key>{key}</key><true/>" in b.split(")", 1)[0]]
    otherwise = [b for b in branches if b.startswith("*)")]
    assert len(granted) == 1 and "exit" not in granted[0].split(")", 1)[1], (
        "Schlüssel mit Wert true lässt durch"
    )
    assert len(otherwise) == 1 and "exit 1" in otherwise[0], "alles andere bricht ab"


def test_windows_is_built_here_and_signed_nowhere_in_the_workflow() -> None:
    """Kein signtool, kein Azure, kein Schlüsselimport für Windows — nur die Übergabe."""
    workflow = _workflow()

    assert "signtool" not in workflow
    assert "azure/" not in workflow
    assert "artifact-signing" not in workflow
    assert "production-signing" not in _job("windows-installer")
    assert "production-signing" not in _job("windows-release-check")
    for name in _job_names():
        assert not name.startswith("windows-app-sign"), name
        assert not name.startswith("windows-installer-sign"), name

    handoff = _step(_job("package"), "Signiereingang übergeben (Windows)")
    assert "name: solidon3d-windows-signing-input" in handoff
    assert "retention-days: 7" in handoff, (
        "die Übergabe muss lange genug leben, um lokal signiert zu werden"
    )
    assert "name: solidon3d-windows-signing-input" in _job("windows-installer")


def _job_names() -> list[str]:
    return re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\n", _workflow())


def _step(job: str, title: str) -> str:
    """Liefert genau einen Schritt eines Jobblocks."""
    match = re.search(
        rf"(?ms)^      - name: {re.escape(title)}\n.*?(?=^      - |\Z)",
        job,
    )
    assert match is not None, f"Schritt fehlt: {title}"
    return match.group(0)


def test_the_appimage_tool_and_embedded_runtime_are_fixed_and_verified() -> None:
    """Auch der erste Code im AppImage stammt aus einer festen, geprüften Datei."""
    workflow = _workflow()

    assert "/continuous/" not in workflow
    assert "appimagetool/releases/download/1.9.1/" in workflow
    assert "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0" in workflow
    assert "type2-runtime/releases/download/20251108/runtime-x86_64" in workflow
    assert "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d" in workflow
    assert workflow.count("sha256sum --check --strict") >= 2
    assert "APPIMAGETOOL_RUNTIME_FILE=" in workflow
    assert "choco install" not in workflow, (
        "ein ungepinnter Paketmanagerlauf lädt ausführbaren Code"
    )


def test_the_release_gate_blocks_on_every_platform() -> None:
    """RM-115: Die Releaseakte hält den Release an, statt zu warnen.

    Im Tag-Lauf von 0.4.4 (35464068433) war sie auf allen drei Plattformen rot
    und veröffentlichte trotzdem — die Warnung stand im Lauf, gelesen hat sie
    niemand. Jeder Aufruf von ``make_licence_notices`` in den drei Prüfjobs
    muss den Job mit seinem Exit-Code beenden können, und die Prüfumgebung
    trägt die Distribution, aus der der Bootloader-Text kommt.
    """
    for name in ("linux-release-check", "windows-release-check", "macos-release-check"):
        job = _job(name)
        calls = [line for line in job.splitlines() if "tools.make_licence_notices" in line]
        assert calls, name
        assert "nicht blockierend" not in job, name
        assert "$global:LASTEXITCODE = 0" not in job, name
        assert not [line for line in calls if "|| " in line], name
        assert '-e ".[geom,ui,brep]" pyinstaller' in job, name
    windows = _job("windows-release-check")
    assert windows.count("if ($LASTEXITCODE -ne 0) { throw") >= 2


def test_the_linux_gate_checks_the_appimage_content_with_its_runtime() -> None:
    """Das AppImage trägt den Laufzeitkern, Archiv und Flatpak nicht — geprüft
    werden beide Stücklisten, jede mit ihrer Sorte."""
    job = _job("linux-release-check")
    assert "--appimage-extract" in job
    assert "set -euo pipefail" in job
    assert "--release-check --artifact-kind appimage" in job
    assert '--write-evidence --sbom "$appimage_sbom"' in job
    assert job.count("--release-check") == 2
