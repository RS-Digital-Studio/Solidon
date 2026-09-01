"""Hält den Auslieferungsweg an unveränderlichen, knapp berechtigten Eingängen."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
BUILD_WORKFLOW = WORKFLOWS / "build.yml"


def _workflow() -> str:
    return BUILD_WORKFLOW.read_text(encoding="utf-8")


def _job(name: str) -> str:
    """Liefert genau einen Jobblock aus dem Bauworkflow."""
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        _workflow(),
    )
    assert match is not None, f"Workflow-Job fehlt: {name}"
    return match.group(0)


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


def test_oidc_exists_only_in_the_two_protected_azure_signing_jobs() -> None:
    """Bau, PFX-Wege und unsignierte Wege können kein OIDC-Token anfordern."""
    workflow = _workflow()
    azure_jobs = ("windows-app-sign-azure", "windows-installer-sign-azure")

    assert workflow.count("id-token: write") == len(azure_jobs)
    for name in azure_jobs:
        job = _job(name)
        assert "id-token: write" in job
        assert "environment: production-signing" in job
        assert "actions/checkout@" not in job
        assert not re.search(r"\bpython\b", job)
        assert "ISCC" not in job and "& $compiler" not in job

    for name in (
        "package",
        "windows-app-sign-pfx",
        "windows-installer",
        "windows-installer-sign-pfx",
        "macos-app-sign",
        "macos-package",
        "macos-installer-sign",
    ):
        assert "id-token: write" not in _job(name), name


def test_protected_signers_never_run_repository_or_handoff_code() -> None:
    """Mit OIDC oder entsperrtem Schlüssel laufen nur fest definierte Signierbefehle."""
    for name in (
        "windows-app-sign-azure",
        "windows-app-sign-pfx",
        "windows-installer-sign-azure",
        "windows-installer-sign-pfx",
        "macos-app-sign",
        "macos-installer-sign",
    ):
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
    assert "WINDOWS_SIGNING_MODE -notin @('azure', 'pfx', 'unsigned')" in package
    assert "MACOS_SIGNING_MODE -notin @('signed', 'notarized', 'unsigned')" in package


def test_the_windows_handoff_is_an_exact_contained_product_tree() -> None:
    """Der Signierer lehnt Zusatzdateien, Pfadausbruch und andere Produkte ab."""
    for name in ("windows-app-sign-azure", "windows-app-sign-pfx", "windows-installer"):
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


def test_pfx_and_apple_keys_are_removed_inside_the_fixed_signing_step() -> None:
    """Nach Schlüsselimport darf kein späterer Repositoryschritt den Schlüssel sehen."""
    for name in ("windows-app-sign-pfx", "windows-installer-sign-pfx"):
        job = _job(name)
        assert "finally" in job
        assert "Remove-Item -LiteralPath $pfx" in job

    for name in ("macos-app-sign", "macos-installer-sign"):
        job = _job(name)
        assert "trap cleanup EXIT" in job
        assert 'security delete-keychain "$keychain"' in job


def test_licence_notice_precedes_every_package_and_release_gate() -> None:
    """Notice/SBOM reisen einmal mit; Schema-Akten bleiben außerhalb des Kundenbaums."""
    package = _job("package")
    notice = "python tools/make_licence_notices.py `"

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


def test_both_windows_signature_checks_stop_the_protected_job() -> None:
    """Eine ungültige Signatur darf trotz PowerShell-Pipeline nicht weiterlaufen."""
    for name, target, message in (
        ("windows-app-sign-azure", "$env:ARTIFACT_APP", "Die Signatur der Anwendung ist ungültig."),
        ("windows-app-sign-pfx", "$env:ARTIFACT_APP", "Die Signatur der Anwendung ist ungültig."),
        (
            "windows-installer-sign-azure",
            "$env:ARTIFACT_SETUP",
            "Die Signatur des Installers ist ungültig.",
        ),
        (
            "windows-installer-sign-pfx",
            "$env:ARTIFACT_SETUP",
            "Die Signatur des Installers ist ungültig.",
        ),
    ):
        job = _job(name)
        assert f"signtool verify /pa /v {target}" in job
        assert message in job


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
