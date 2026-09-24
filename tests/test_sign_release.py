"""Das lokale Signierwerkzeug fährt die CI-Übergabe prüfsummengebunden zu Ende.

Signiert wird auf Roberts Rechner, nicht in GitHub Actions — die CI liefert
nur das gebundene Archiv. Diese Tests stellen signtool, ISCC und das Archiv
nach und prüfen, dass jede Abweichung die Kette anhält, **bevor** ein
Zertifikat ins Spiel kommt.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tools import make_installer, sign_release

APP = make_installer.APP_NAME
THUMBPRINT = "AB" * 20
SUBJECT = "CN=Beispiel Herausgeber, O=Beispiel"


def _certificate() -> sign_release.Certificate:
    """Liefert eine zeitlich stabile öffentliche Zertifikatsattrappe ohne Schlüssel."""
    now = datetime.now(UTC)
    return sign_release.Certificate(
        THUMBPRINT,
        SUBJECT,
        now - timedelta(days=1),
        now + timedelta(days=1),
        True,
        ("1.3.6.1.5.5.7.3.3",),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _product_tree(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Baut einen kleinen Windows-Bau und lässt make_installer die Übergabe schreiben."""
    source = root / "dist" / APP
    packaging = root / "packaging"
    build = packaging / "build"
    for path, content in (
        (source / f"{APP}.exe", b"Programm"),
        (source / "_internal" / "python313.dll", b"Python-Laufzeit"),
        (source / "_internal" / f"{APP}.cdx.json", b"{}"),
        (source / "THIRD-PARTY-NOTICES.md", b"Lizenzbeilage"),
        (packaging / "solidon3d.iss", b"Skript"),
        (packaging / "eula.txt", b"Vertrag"),
        (packaging / "solidon3d.ico", b"Symbol"),
        (build / "licence.manifest", b"Manifest"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    handoff = build / "windows-signing.json"
    monkeypatch.setattr(make_installer, "ROOT", root)
    monkeypatch.setattr(make_installer, "SOURCE_DIR", source)
    monkeypatch.setattr(make_installer, "OUTPUT_DIR", root / "dist")
    monkeypatch.setattr(make_installer, "SCRIPT", packaging / "solidon3d.iss")
    monkeypatch.setattr(make_installer, "SIGNING_HANDOFF", handoff)
    monkeypatch.setattr(make_installer, "_licence_file", lambda: packaging / "eula.txt")
    monkeypatch.setattr(make_installer, "stale_reason", lambda: "")
    assert make_installer.write_signing_handoff() == 0
    return root


def _pack(tree: Path, target_dir: Path) -> Path:
    """Packt den Baum so, wie der Paketjob es tut: Archiv plus Prüfsummenzeile."""
    archive = target_dir / sign_release.ARCHIVE_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(tree).as_posix())
    _write_checksum(archive)
    return archive


def _write_checksum(archive: Path) -> None:
    line = f"{_sha256(archive)}  {archive.name}\n"
    archive.with_name(archive.name + ".sha256").write_text(line, encoding="ascii")


class FakeTools:
    """Stellt signtool, ISCC und gh nach und merkt sich jeden Aufruf."""

    SIGNATURE = b"\n<<signiert>>"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.verify_fails = False
        self.verify_warns = False
        self.evidence_fails = False
        self.application_signed_when_packed: bool | None = None
        self.installer_files: dict[str, bytes] = {}
        self.application_archive: Path | None = None
        self.downloads: list[list[str]] = []
        self.signature_checks: list[tuple[Path, str]] = []

    def __call__(self, command: list[str], *, check: bool) -> subprocess.CompletedProcess[bytes]:
        assert check is False
        name = Path(command[0]).name.lower()
        if name == "gh" and command[1:3] == ["run", "download"]:
            self.downloads.append(command)
            folder = Path(command[command.index("-D") + 1])
            artifact = command[command.index("-n") + 1]
            if artifact == sign_release.ARTIFACT_NAME:
                assert self.application_archive is not None
                for path in (
                    self.application_archive,
                    self.application_archive.with_suffix(".zip.sha256"),
                ):
                    if not path.exists():
                        return subprocess.CompletedProcess(command, 1)
                    (folder / path.name).write_bytes(path.read_bytes())
                return subprocess.CompletedProcess(command, 0)
            assert artifact == sign_release.INSTALLER_ARTIFACT_NAME
            for filename, content in self.installer_files.items():
                (folder / filename).write_bytes(content)
            return subprocess.CompletedProcess(command, 0)
        self.calls.append(list(command))
        if len(command) > 1 and command[1].endswith("make_licence_notices.py"):
            if self.evidence_fails:
                return subprocess.CompletedProcess(command, 1)
            if command[2] == "--write-evidence":
                evidence = Path(command[command.index("--release-evidence") + 1])
                kind, _, package = command[command.index("--package") + 1].partition("=")
                assert kind == "windows-installer"
                assert Path(package).parent == evidence.parent, (
                    "Paket muss in der Evidenzablage liegen"
                )
                evidence.write_text(json.dumps({"package": Path(package).name}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)
        if name == "signtool.exe" and command[1] == "sign":
            target = Path(command[-1])
            target.write_bytes(target.read_bytes() + self.SIGNATURE)
            return subprocess.CompletedProcess(command, 0)
        if name == "signtool.exe" and command[1] == "verify":
            assert command[2:-1] == ["/pa", "/all", "/tw", "/v"]
            signed = Path(command[-1]).read_bytes().endswith(self.SIGNATURE)
            return subprocess.CompletedProcess(
                command, 2 if self.verify_warns else (0 if signed and not self.verify_fails else 1)
            )
        if name == "iscc.exe":
            defines = dict(part[2:].split("=", 1) for part in command[1:-1])
            source = Path(defines["SourceDir"])
            application = source / f"{APP}.exe"
            self.application_signed_when_packed = application.read_bytes().endswith(self.SIGNATURE)
            setup = Path(defines["OutputDir"]) / f"{APP}-Setup-{defines['AppVersion']}.exe"
            setup.write_bytes(b"Setup:" + application.read_bytes())
            return subprocess.CompletedProcess(command, 0)
        raise AssertionError(f"unerwarteter Aufruf: {command}")

    def verify_identity(self, target: Path, expected_thumbprint: str) -> None:
        """Stellt die zweite Windows-Prüfung dar, ohne einen echten Zertifikatspeicher zu lesen."""
        assert target.read_bytes().endswith(self.SIGNATURE)
        assert expected_thumbprint == THUMBPRINT or expected_thumbprint == "CD" * 20
        self.signature_checks.append((target, expected_thumbprint))


def _ci_record(run_id: str, workflow: str) -> dict[str, object]:
    """Ein vollständig beendeter Lauf aus demselben Commit und Repository."""
    return {
        "id": int(run_id),
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "path": workflow,
        "head_sha": "12" * 20,
        "repository": {"full_name": sign_release.REPOSITORY},
        "head_repository": {"full_name": sign_release.REPOSITORY},
    }


def test_an_identical_installer_commit_needs_no_remote_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unveränderte Quellen brauchen keine Ausnahme und keinen zusätzlichen API-Aufruf."""
    monkeypatch.setattr(sign_release, "_github_metadata", lambda path: pytest.fail(path))
    sign_release.verify_installer_source("12" * 20, "12" * 20)


def _tree_api_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes=None):
    """Git selbst berechnet die Baum-SHAs; der Prüfer liefert nicht seinen eigenen Sollwert."""
    repository = tmp_path / "git"
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    leaves = dict.fromkeys(
        sign_release.INSTALLER_ORCHESTRATION_FILES, ("blob", "100644", "11" * 20)
    )
    leaves.update(
        {
            "app/model.py": ("blob", "100644", "22" * 20),
            "packaging/solidon3d.iss": ("blob", "100644", "33" * 20),
            "constraints.txt": ("blob", "100644", "44" * 20),
            "tools/make_installer.py": ("blob", "100644", "55" * 20),
            "ä.txt": ("blob", "100644", "66" * 20),
            "app.txt": ("blob", "100644", "77" * 20),
            "link": ("blob", "120000", "88" * 20),
            "submodule": ("commit", "160000", "99" * 20),
        }
    )

    def tree(values):
        result = []

        def folder(prefix):
            children = {}
            for path, value in values.items():
                if not path.startswith(prefix):
                    continue
                name, slash, _rest = path[len(prefix) :].partition("/")
                if slash:
                    children.setdefault(name, None)
                else:
                    children[name] = value
            records = []
            for name, value in sorted(children.items()):
                if value is None:
                    value = ("tree", "040000", folder(prefix + name + "/"))
                kind, mode, sha = value
                result.append({"path": prefix + name, "type": kind, "mode": mode, "sha": sha})
                records.append(f"{mode} {kind} {sha}\t{name}\0")
            return subprocess.run(
                ["git", "mktree", "--missing", "-z"],
                cwd=repository,
                input="".join(records),
                capture_output=True,
                encoding="utf-8",
                check=True,
            ).stdout.strip()

        root = folder("")
        return {"sha": root, "truncated": False, "tree": result}

    original = tree(leaves)
    amended = leaves.copy()
    if changes:
        changes(amended)
    replacement = tree(amended)
    responses = {
        f"compare/{'12' * 20}...{'34' * 20}": {
            "status": "ahead",
            "base_commit": {"sha": "12" * 20},
            "merge_base_commit": {"sha": "12" * 20},
        },
        f"git/commits/{'12' * 20}": {"sha": "12" * 20, "tree": {"sha": original["sha"]}},
        f"git/commits/{'34' * 20}": {"sha": "34" * 20, "tree": {"sha": replacement["sha"]}},
        f"git/trees/{original['sha']}?recursive=1": original,
        f"git/trees/{replacement['sha']}?recursive=1": replacement,
    }
    monkeypatch.setattr(sign_release, "_github_metadata", lambda path: responses[path])
    return responses, replacement


def test_only_the_named_orchestration_blobs_may_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch geänderte Elternbaum-SHAs und UTF-8-Pfade werden gegen echte Gitobjekte geprüft."""

    def change(leaves):
        for path in sign_release.INSTALLER_ORCHESTRATION_FILES:
            leaves[path] = ("blob", "100644", "ab" * 20)

    _tree_api_fixture(tmp_path, monkeypatch, change)
    sign_release.verify_installer_source("12" * 20, "34" * 20)


@pytest.mark.parametrize(
    "problem",
    [
        "app",
        "package",
        "dependency",
        "tool",
        "new",
        "deleted",
        "mode",
        "symlink",
        "gitlink",
        "allowed_deleted",
        "allowed_mode",
        "allowed_symlink",
    ],
)
def test_changed_product_or_tree_structure_never_reaches_the_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    def change(leaves):
        path = {
            "app": "app/model.py",
            "package": "packaging/solidon3d.iss",
            "dependency": "constraints.txt",
            "tool": "tools/make_installer.py",
            "gitlink": "submodule",
            "symlink": "link",
        }.get(problem, "app/model.py")
        if problem.startswith("allowed_"):
            path = "tools/sign_release.py"
        if problem in {"deleted", "allowed_deleted"}:
            del leaves[path]
        elif problem == "new":
            leaves["unknown.py"] = ("blob", "100644", "ab" * 20)
        elif problem in {"mode", "allowed_mode"}:
            leaves[path] = ("blob", "100755", leaves[path][2])
        elif problem == "allowed_symlink":
            leaves[path] = ("blob", "120000", "ab" * 20)
        else:
            leaves[path] = (*leaves[path][:2], "ab" * 20)

    _tree_api_fixture(tmp_path, monkeypatch, change)
    with pytest.raises(sign_release.SigningError):
        sign_release.verify_installer_source("12" * 20, "34" * 20)


@pytest.mark.parametrize(
    "problem",
    [
        "truncated",
        "missing",
        "duplicate",
        "parent",
        "mode",
        "path",
        "root_sha",
        "commit_sha",
        "no_tree",
        "unrelated",
        "wrong_merge_base",
    ],
)
def test_incomplete_or_foreign_git_evidence_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    replies, tree = _tree_api_fixture(tmp_path, monkeypatch)
    comparison = replies[f"compare/{'12' * 20}...{'34' * 20}"]
    commit = replies[f"git/commits/{'34' * 20}"]
    if problem == "truncated":
        tree["truncated"] = True
    elif problem == "missing":
        tree["tree"].pop()
    elif problem == "duplicate":
        tree["tree"].append(tree["tree"][0].copy())
    elif problem == "parent":
        tree["tree"] = [entry for entry in tree["tree"] if entry["path"] != "app"]
    elif problem == "mode":
        tree["tree"][0]["mode"] = "777777"
    elif problem == "path":
        tree["tree"][0]["path"] = "../foreign.py"
    elif problem == "root_sha":
        tree["sha"] = "ab" * 20
    elif problem == "commit_sha":
        commit["sha"] = "ab" * 20
    elif problem == "no_tree":
        del commit["tree"]
    elif problem == "unrelated":
        comparison["status"] = "diverged"
    else:
        comparison["merge_base_commit"]["sha"] = "ab" * 20
    with pytest.raises(sign_release.SigningError):
        sign_release.verify_installer_source("12" * 20, "34" * 20)


@pytest.fixture
def signing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    tree = _product_tree(tmp_path / "ci", monkeypatch)
    archive = _pack(tree, tmp_path / "download")
    tools = FakeTools()
    tools.application_archive = archive
    monkeypatch.setattr(sign_release, "_run", tools)
    monkeypatch.setattr(sign_release, "find_signtool", lambda explicit=None: Path("signtool.exe"))
    monkeypatch.setattr(make_installer, "find_compiler", lambda: Path("ISCC.exe"))
    monkeypatch.setattr(sign_release, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(sign_release.sys, "platform", "win32")
    monkeypatch.setattr(sign_release, "read_certificates", lambda: [_certificate()])
    monkeypatch.setattr(sign_release, "verify_signature_identity", tools.verify_identity)
    monkeypatch.setattr(sign_release, "verify_ci_run", _ci_record)
    original_which = sign_release.shutil.which
    monkeypatch.setattr(
        sign_release.shutil, "which", lambda name: "gh" if name == "gh" else original_which(name)
    )
    monkeypatch.setattr(
        sign_release, "build_installer", lambda *args: pytest.fail("Lokaler CI-Bau")
    )
    return {
        "archive": archive,
        "stage": tmp_path / "stage",
        "output": tmp_path / "out",
        "application_output": tmp_path / "application-output",
        "evidence": tmp_path / "repo" / "build" / "release-evidence.json",
        "tools": tools,
        "tree": tree,
    }


def _application_phase(signing: dict[str, object], **overrides: object) -> dict[str, object]:
    """Signiert die Anwendung und stellt die getrennte Antwort des CI-Installerbaus her."""
    arguments: dict[str, object] = {
        "stage": signing["stage"],
        "subject": "Beispiel Herausgeber",
        "thumbprint": None,
        "timestamp_url": sign_release.TIMESTAMP_URL,
        "signtool": None,
        "run_id": "123",
        "output_dir": signing["application_output"],
    }
    arguments.update(overrides)
    application = sign_release.sign_application(**arguments)  # type: ignore[arg-type]
    metadata = json.loads((application.parent / sign_release.APPLICATION_METADATA).read_text())
    content = b"CI Setup:" + application.read_bytes()
    setup_name = f"{APP}-Setup-{make_installer.APP_VERSION}.exe"
    digest = hashlib.sha256(content).hexdigest()
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    tools.application_signed_when_packed = application.read_bytes().endswith(FakeTools.SIGNATURE)
    tools.installer_files = {
        setup_name: content,
        setup_name + ".sha256": f"{digest}  {setup_name}\n".encode("ascii"),
        sign_release.INSTALLER_METADATA: json.dumps(
            {
                **metadata,
                "installer_sha256": digest,
                "installer_commit": "12" * 20,
                "installer_run_id": "456",
            }
        ).encode(),
    }
    arguments.pop("run_id")
    arguments.update(
        installer_run_id="456", evidence=signing["evidence"], output_dir=signing["output"]
    )
    return arguments


def _go(signing: dict[str, object], **overrides: object) -> Path:
    return sign_release.sign_installer(**_application_phase(signing, **overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize("allowed", [False, True])
def test_the_local_installer_phase_checks_the_actual_successor_tree(
    signing, tmp_path, monkeypatch, allowed
):
    """Der lokale Rückweg benutzt denselben echten Baumprüfer wie die Installer-CI."""
    arguments = _application_phase(signing)
    tools = signing["tools"]
    metadata = json.loads(tools.installer_files[sign_release.INSTALLER_METADATA])
    metadata["installer_commit"] = "34" * 20
    tools.installer_files[sign_release.INSTALLER_METADATA] = json.dumps(metadata).encode()

    def run(run_id, workflow):
        result = _ci_record(run_id, workflow)
        if workflow == sign_release.INSTALLER_WORKFLOW:
            result["head_sha"] = "34" * 20
        return result

    monkeypatch.setattr(sign_release, "verify_ci_run", run)
    path = "tools/sign_release.py" if allowed else "app/model.py"
    _tree_api_fixture(
        tmp_path, monkeypatch, lambda leaves: leaves.update({path: ("blob", "100644", "ab" * 20)})
    )
    if allowed:
        assert sign_release.sign_installer(**arguments).is_file()
    else:
        with pytest.raises(sign_release.SigningError, match=r"app/model\.py"):
            sign_release.sign_installer(**arguments)
        assert [call[1] for call in tools.calls] == ["sign", "verify"]


@pytest.mark.parametrize("field", ["installer_commit", "installer_run_id"])
def test_installer_return_cannot_forge_its_actual_run_or_commit(signing, field):
    arguments = _application_phase(signing)
    tools = signing["tools"]
    metadata = json.loads(tools.installer_files[sign_release.INSTALLER_METADATA])
    metadata[field] = "99" * 20 if field == "installer_commit" else "999"
    tools.installer_files[sign_release.INSTALLER_METADATA] = json.dumps(metadata).encode()
    with pytest.raises(sign_release.SigningError, match="CI-Installer"):
        sign_release.sign_installer(**arguments)
    assert len([call for call in tools.calls if call[1] == "sign"]) == 1


def _repack(signing: dict[str, object], mutate: object) -> None:
    """Ändert den Baum nach der Übergabe und packt ihn erneut — ein manipuliertes Archiv."""
    tree = signing["tree"]
    assert isinstance(tree, Path)
    mutate(tree)  # type: ignore[operator]
    archive = signing["archive"]
    assert isinstance(archive, Path)
    _pack(tree, archive.parent)


def test_the_chain_signs_the_application_before_the_installer_and_binds_everything(
    signing: dict[str, object],
) -> None:
    """Zwei lokale Signierphasen um den CI-Bau; das lokale Werkzeug baut nie selbst."""
    result = _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)

    steps = [
        ("notices", call[2])
        if call[1].endswith("make_licence_notices.py")
        else (Path(call[0]).name.lower(), call[1])
        for call in tools.calls
    ]
    assert steps == [
        ("signtool.exe", "sign"),
        ("signtool.exe", "verify"),
        ("signtool.exe", "verify"),
        ("signtool.exe", "sign"),
        ("signtool.exe", "verify"),
        ("notices", "--write-evidence"),
        ("notices", "--release-check"),
    ]
    assert tools.application_signed_when_packed is True, (
        "die Setup-Datei packte eine unsignierte Anwendung"
    )

    sign_call = tools.calls[0]
    assert sign_call[1:9] == [
        "sign",
        "/fd",
        "SHA256",
        "/tr",
        sign_release.TIMESTAMP_URL,
        "/td",
        "SHA256",
        "/sha1",
    ]
    assert sign_call[9] == THUMBPRINT
    setup_sign_call = tools.calls[3]
    assert setup_sign_call[9] == THUMBPRINT
    assert "/n" not in sign_call and "/a" not in sign_call
    assert sign_call[-1].endswith(f"{APP}.exe")

    assert result.name == f"{APP}-Setup-{make_installer.APP_VERSION}.exe"
    assert result.read_bytes().endswith(FakeTools.SIGNATURE)
    checksum = result.with_name(result.name + ".sha256").read_text(encoding="ascii")
    assert checksum == f"{_sha256(result)}  {result.name}\n"

    stage = signing["stage"]
    assert isinstance(stage, Path)
    rebound = json.loads((stage / sign_release.HANDOFF_NAME).read_text(encoding="utf-8"))
    application = stage / f"dist/{APP}/{APP}.exe"
    assert rebound["input_sha256"][f"dist/{APP}/{APP}.exe"] == _sha256(application)

    evidence = signing["evidence"]
    assert isinstance(evidence, Path)
    assert json.loads(evidence.read_text(encoding="utf-8")) == {"package": result.name}
    packaged = evidence.parent / result.name
    assert packaged.read_bytes() == result.read_bytes(), (
        "die Evidenz muss den signierten Installer nennen, nicht den aus der CI"
    )


def test_a_tampered_archive_stops_before_any_signature(signing: dict[str, object]) -> None:
    """Die Prüfsummenzeile gehört zum Archiv; passt sie nicht, wird nichts entpackt."""
    archive = signing["archive"]
    assert isinstance(archive, Path)
    archive.write_bytes(archive.read_bytes() + b"\0")

    with pytest.raises(sign_release.SigningError, match="Geändertes Übergabearchiv"):
        _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []
    stage = signing["stage"]
    assert isinstance(stage, Path)
    assert not stage.exists()


def test_a_changed_file_inside_the_archive_stops_before_any_signature(
    signing: dict[str, object],
) -> None:
    """Ein gültiges Archiv um einen ausgetauschten Baum ist genauso wenig ein Signiereingang."""
    _repack(
        signing,
        lambda tree: (tree / "dist" / APP / "_internal" / "python313.dll").write_bytes(b"fremd"),
    )

    with pytest.raises(sign_release.SigningError, match="Geänderter Signiereingang"):
        _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []


def test_an_extra_file_in_the_archive_is_refused(signing: dict[str, object]) -> None:
    """Was die Übergabe nicht nennt, kommt nicht in den Installer."""
    _repack(signing, lambda tree: (tree / "dist" / APP / "extra.dll").write_bytes(b"dazu"))

    with pytest.raises(sign_release.SigningError, match="zu viel"):
        _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []


def test_an_archive_path_that_escapes_the_stage_is_refused(signing: dict[str, object]) -> None:
    """Ein Eintrag mit ``..`` schreibt nirgendwohin — er beendet den Lauf vor dem Entpacken."""
    archive = signing["archive"]
    assert isinstance(archive, Path)
    with zipfile.ZipFile(archive, "a") as zip_file:
        zip_file.writestr("../ausbruch.txt", b"draussen")
    _write_checksum(archive)

    with pytest.raises(sign_release.SigningError, match="Archivpfad"):
        _go(signing)
    stage = signing["stage"]
    assert isinstance(stage, Path)
    assert not stage.exists()
    assert not (stage.parent / "ausbruch.txt").exists()


def test_a_foreign_product_is_refused_even_with_matching_checksums(
    signing: dict[str, object],
) -> None:
    """Das Zertifikat signiert Solidon3D und nichts, was nur so heißt."""

    def foreign(tree: Path) -> None:
        handoff = tree / sign_release.HANDOFF_NAME
        document = json.loads(handoff.read_text(encoding="utf-8"))
        document["app_id"] = "de.fremd.produkt"
        handoff.write_text(json.dumps(document), encoding="utf-8")

    _repack(signing, foreign)

    with pytest.raises(sign_release.SigningError, match="app_id"):
        _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []


def test_an_invalid_application_signature_stops_before_the_installer_is_built(
    signing: dict[str, object],
) -> None:
    """Eine Setup-Datei um eine schlecht signierte Anwendung entsteht gar nicht erst."""
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    tools.verify_fails = True

    with pytest.raises(sign_release.SigningError, match=r"Signatur .* ungültig"):
        _go(signing)
    assert [call[1] for call in tools.calls] == ["sign", "verify"]
    assert tools.application_signed_when_packed is None
    output = signing["output"]
    assert isinstance(output, Path)
    assert not output.exists()


def test_a_failing_release_check_stops_before_the_installer_is_delivered(
    signing: dict[str, object],
) -> None:
    """RM-115: Die Releaseakte hält an, wie in der CI — kein signierter Installer
    ohne vollständige Belege. Bis 0.5.0 warnte sie nur."""
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    tools.evidence_fails = True

    with pytest.raises(sign_release.SigningError, match="Release-Evidenz"):
        _go(signing)

    output = signing["output"]
    assert isinstance(output, Path)
    assert not output.exists() or not list(output.glob("*.exe"))
    assert [call[2] for call in tools.calls if call[1].endswith("make_licence_notices.py")] == [
        "--write-evidence"
    ], "nach einer nicht geschriebenen Evidenz gibt es nichts zu prüfen"


def test_an_existing_stage_is_never_overwritten(signing: dict[str, object]) -> None:
    """Ein alter Arbeitsordner könnte einen alten Bau enthalten — er wird genannt, nicht geräumt."""
    stage = signing["stage"]
    assert isinstance(stage, Path)
    stage.mkdir()
    (stage / "alt.txt").write_bytes(b"vorher")

    with pytest.raises(sign_release.SigningError, match="schon da"):
        _go(signing)
    assert (stage / "alt.txt").read_bytes() == b"vorher"


def test_the_certificate_must_be_named_before_anything_is_touched(
    signing: dict[str, object],
) -> None:
    """Ohne --subject oder --thumbprint gibt es keinen Aufruf, den signtool erraten müsste."""
    with pytest.raises(sign_release.SigningError, match="--subject"):
        _go(signing, subject=None)
    stage = signing["stage"]
    assert isinstance(stage, Path)
    assert not stage.exists()


def test_a_thumbprint_replaces_the_subject_name(signing: dict[str, object]) -> None:
    """Bei zwei Zertifikaten auf denselben Namen entscheidet der Fingerabdruck."""
    _go(signing, subject=None, thumbprint="ab" * 20)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert "/sha1" in tools.calls[0]
    assert "/n" not in tools.calls[0]


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing", "Kein passendes Zertifikat"),
        ("expired", "Kein aktuell gültiges"),
        ("future", "Kein aktuell gültiges"),
        ("public-only", "HasPrivateKey"),
        ("wrong-usage", "Code-Signing"),
        ("ambiguous", "Mehrere gültige"),
    ],
)
def test_unusable_certificates_stop_before_extraction_and_signing(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch, failure: str, message: str
) -> None:
    """Ein ungeeigneter Speicherbestand verlangt eine Korrektur vor jeder Dateimutierung."""
    certificate = _certificate()
    now = datetime.now(UTC)
    certificates = {
        "missing": [],
        "expired": [
            replace(
                certificate, not_before=now - timedelta(days=2), not_after=now - timedelta(days=1)
            )
        ],
        "future": [replace(certificate, not_before=now + timedelta(hours=1))],
        "public-only": [replace(certificate, has_private_key=False)],
        "wrong-usage": [replace(certificate, enhanced_key_usage=("1.3.6.1.5.5.7.3.1",))],
        "ambiguous": [certificate, replace(certificate, thumbprint="CD" * 20)],
    }[failure]
    monkeypatch.setattr(sign_release, "read_certificates", lambda: certificates)
    with pytest.raises(sign_release.SigningError, match=message):
        _go(signing)
    assert not Path(signing["stage"]).exists()  # type: ignore[arg-type]
    assert not Path(signing["output"]).exists()  # type: ignore[arg-type]
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []


def test_a_thumbprint_resolves_two_current_certificates(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der ausdrückliche Fingerabdruck wählt bei gleichem Namen genau das gewünschte Zertifikat."""
    chosen = replace(_certificate(), thumbprint="CD" * 20)
    monkeypatch.setattr(sign_release, "read_certificates", lambda: [_certificate(), chosen])
    _go(signing, subject=None, thumbprint="\u200e" + ":".join(["cd"] * 20) + " ")
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    calls = [call for call in tools.calls if call[1] == "sign"]
    assert len(calls) == 2
    assert all(call[call.index("/sha1") + 1] == chosen.thumbprint for call in calls)


def test_expired_names_do_not_obscure_the_one_valid_code_signing_certificate(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein abgelaufener Vorgänger ist keine zweite verwendbare Identität."""
    current = _certificate()
    expired = replace(
        current,
        thumbprint="CD" * 20,
        not_before=current.not_before - timedelta(days=2),
        not_after=current.not_before,
    )
    monkeypatch.setattr(sign_release, "read_certificates", lambda: [expired, current])
    result = sign_release.check_prerequisites(subject="beispiel herausgeber", thumbprint=None)
    assert result.certificate == current


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--subject", " "],
        ["--thumbprint", ""],
        ["--thumbprint", "AB" * 19],
        ["--thumbprint", "AG" * 20],
        ["--subject", "Beispiel", "--thumbprint", THUMBPRINT],
    ],
)
def test_invalid_selectors_stop_before_a_download(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    """Auch --run beginnt bei einer unklaren Identität noch keinen Download."""

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Ungültige Auswahl hat eine externe Aktion erreicht")

    monkeypatch.setattr(sign_release, "download_handoff", forbidden)
    monkeypatch.setattr(sign_release, "check_prerequisites", forbidden)
    assert sign_release.main(["--run", "123", *arguments]) == 1


def test_the_local_phases_do_not_need_inno(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nur die CI benötigt den Paketierer; lokal wird dessen Suche nie ausgelöst."""
    monkeypatch.setattr(make_installer, "find_compiler", lambda: pytest.fail("Lokale Inno-Suche"))
    _go(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert not any(Path(call[0]).name.lower() == "iscc.exe" for call in tools.calls)


def test_check_reads_prerequisites_without_an_archive_or_file_changes(
    signing: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Der lokale Vorabcheck liest Werkzeuge und Metadaten, selbst wenn kein Archiv existiert."""

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("--check hat die Archiv- oder Signierkette erreicht")

    for name in ("verify_archive", "extract_archive", "download_handoff", "sign_file", "run"):
        monkeypatch.setattr(sign_release, name, forbidden)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    capsys.readouterr()
    assert (
        sign_release.main(
            [
                "--check",
                "--subject",
                "Beispiel Herausgeber",
            ]
        )
        == 0
    )
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
    text = capsys.readouterr().out
    assert "kein Cloud-Signiertest" in text
    assert "HasPrivateKey" in text
    assert THUMBPRINT in text
    assert not Path(signing["stage"]).exists()  # type: ignore[arg-type]
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == []


def test_check_refuses_a_ci_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der reine Check darf nicht versehentlich mit --run nach außen greifen."""

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("--check --run darf keine Aktion ausführen")

    monkeypatch.setattr(sign_release, "download_handoff", forbidden)
    monkeypatch.setattr(sign_release, "check_prerequisites", forbidden)
    assert sign_release.main(["--check", "--run", "123", "--thumbprint", THUMBPRINT]) == 1


def test_check_requires_windows(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch eine scheinbar vorhandene Werkzeugkette ersetzt keinen Windows-Zertifikatspeicher."""
    monkeypatch.setattr(sign_release.sys, "platform", "linux")
    with pytest.raises(sign_release.SigningError, match="Windows"):
        sign_release.check_prerequisites(subject=None, thumbprint=THUMBPRINT)


def test_check_requires_signtool(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fehlendes Signierwerkzeug lässt auch den reinen Check rot werden."""

    def missing(explicit: Path | None = None) -> Path:
        raise sign_release.SigningError("Windows SDK installieren")

    monkeypatch.setattr(sign_release, "find_signtool", missing)
    assert sign_release.main(["--check", "--thumbprint", THUMBPRINT]) == 1


def test_a_missing_timestamp_warning_blocks_the_installer(signing: dict[str, object]) -> None:
    """SignTools Warnexit 2 ist bei /tw ein Halt, auch wenn die Signatur selbst gültig ist."""
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    tools.verify_warns = True
    with pytest.raises(sign_release.SigningError, match="Zeitstempel"):
        _go(signing)
    assert [call[1] for call in tools.calls] == ["sign", "verify"]
    assert tools.application_signed_when_packed is None


def _certificate_record() -> dict[str, object]:
    """Bildet die feste JSON-Ausgabe von Windows PowerShell nach."""
    certificate = _certificate()
    return {
        "Thumbprint": certificate.thumbprint,
        "Subject": certificate.subject,
        "NotBefore": certificate.not_before.isoformat(),
        "NotAfter": certificate.not_after.isoformat(),
        "HasPrivateKey": certificate.has_private_key,
        "EnhancedKeyUsage": list(certificate.enhanced_key_usage),
    }


def test_certificate_reader_uses_only_a_fixed_read_only_powershell_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Namen sind Daten; auch Shellzeichen eines Subjects gelangen nie in den PS-Befehl."""
    record = _certificate_record()
    record["Subject"] = "CN=Beispiel; $(Write-Output fremd)"
    calls: list[list[str]] = []

    def process(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "encoding": "utf-8",
            "timeout": 30,
            "env": None,
        }
        return subprocess.CompletedProcess(command, 0, json.dumps([record]))

    monkeypatch.setattr(sign_release, "_run", process)
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "powershell.exe")
    records = sign_release.read_certificates()
    assert len(records) == 1
    assert records[0].subject == record["Subject"]
    assert records[0].has_private_key is True
    assert records[0].enhanced_key_usage == ("1.3.6.1.5.5.7.3.3",)
    assert calls == [
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            sign_release._CERTIFICATE_SCRIPT,
        ]
    ]
    script = calls[0][-1]
    assert "Cert:\\CurrentUser\\My" in script
    assert str(record["Subject"]) not in script
    assert ".PrivateKey" not in script
    assert "Export-Certificate" not in script and "Import-Certificate" not in script


@pytest.mark.parametrize(
    ("result", "status"),
    [
        ("not JSON", 0),
        ("null", 0),
        ('{"Thumbprint": "AB"}', 0),
        ("[{}]", 0),
        ("[]", 1),
    ],
)
def test_certificate_reader_rejects_failed_or_malformed_responses(
    monkeypatch: pytest.MonkeyPatch, result: str, status: int
) -> None:
    """Ein leeres Ergebnis ist nur bei erfolgreichem Lesen eine gültige Auskunft."""
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "powershell.exe")
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], status, result),
    )
    with pytest.raises(sign_release.SigningError, match="PowerShell"):
        sign_release.read_certificates()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("HasPrivateKey", "False"),
        ("EnhancedKeyUsage", "1.3.6.1.5.5.7.3.3"),
        ("NotBefore", "2026-01-01T00:00:00"),
        ("NotAfter", "invalid"),
        ("Thumbprint", "not a hash"),
    ],
)
def test_certificate_reader_rejects_malformed_metadata(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    """Strings werden weder als Schlüsselbesitz noch als Datum oder Fingerabdruck geraten."""
    record = {**_certificate_record(), key: value}
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "powershell.exe")
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps([record])),
    )
    with pytest.raises(sign_release.SigningError):
        sign_release.read_certificates()


def test_certificate_reader_reports_an_empty_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein erreichbarer leerer Speicher bleibt von einer kaputten Abfrage unterscheidbar."""
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "powershell.exe")
    monkeypatch.setattr(
        sign_release, "_run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "[]")
    )
    assert sign_release.read_certificates() == []


def test_certificate_reader_turns_a_timeout_into_a_next_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein hängender Speicherzugriff bleibt begrenzt und endet ohne Traceback."""
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "powershell.exe")

    def process(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("powershell.exe", 30)

    monkeypatch.setattr(sign_release, "_run", process)
    with pytest.raises(sign_release.SigningError, match="--check erneut"):
        sign_release.read_certificates()


def test_windows_powershell_reads_native_certificate_eku_without_touching_the_store() -> None:
    """Ein öffentlicher Prüf-DER belegt den echten PowerShell-EKU-Datentyp ohne Nutzerzertifikat."""
    if sys.platform != "win32" or shutil.which("powershell.exe") is None:
        pytest.skip("Windows PowerShell erforderlich")
    fixture = r"""
$ErrorActionPreference = 'Stop'
$testKey = [System.Security.Cryptography.RSACng]::new(2048)
$testRequest = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    'CN=Isolierter EKU-Test', $testKey,
    [System.Security.Cryptography.HashAlgorithmName]::SHA256,
    [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
)
$testOids = [System.Security.Cryptography.OidCollection]::new()
[void]$testOids.Add([System.Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.3'))
$testEku = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new(
    $testOids, $false
)
$testRequest.CertificateExtensions.Add($testEku)
$testSigned = $testRequest.CreateSelfSigned(
    [DateTimeOffset]::UtcNow.AddDays(-1), [DateTimeOffset]::UtcNow.AddDays(1)
)
$testCertificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
    $testSigned.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
)
"""
    script = (
        fixture
        + sign_release._CERTIFICATE_SCRIPT.replace(
            "Get-ChildItem -LiteralPath 'Cert:\\CurrentUser\\My'", "$testCertificate"
        )
        + "\n$testCertificate.Dispose(); $testSigned.Dispose(); $testKey.Dispose()"
    )
    records = sign_release._read_powershell_json(script)
    assert len(records) == 1
    assert records[0]["EnhancedKeyUsage"] == ["1.3.6.1.5.5.7.3.3"]
    assert records[0]["HasPrivateKey"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("id", 999),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("event", "push"),
        ("event", "pull_request"),
        ("head_branch", "release"),
        ("path", ".github/workflows/other.yml"),
        ("head_sha", "not-a-commit"),
        ("repository", {"full_name": "foreign/repo"}),
        ("head_repository", {"full_name": "foreign/repo"}),
    ],
)
def test_ci_run_requires_the_exact_successful_manual_main_workflow(
    monkeypatch: pytest.MonkeyPatch, key: str, value: object
) -> None:
    """Ein fremder oder nur teilfertiger Lauf kann keine lokale Signatur autorisieren."""
    record = {**_ci_record("123", sign_release.BUILD_WORKFLOW), key: value}
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "gh")
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(record)),
    )
    with pytest.raises(sign_release.SigningError, match="CI-Lauf"):
        sign_release.verify_ci_run("123", sign_release.BUILD_WORKFLOW)


def _tag_run_api(
    monkeypatch: pytest.MonkeyPatch, annotated: bool = False
) -> tuple[dict[str, object], dict[str, object], dict[str, object], list[str]]:
    """Stellt die drei getrennten API-Auskünfte eines echten Release-Tags bereit."""
    tag = f"v{make_installer.APP_VERSION}"
    run = {**_ci_record("123", sign_release.BUILD_WORKFLOW), "event": "push", "head_branch": tag}
    ref: dict[str, object] = {
        "ref": f"refs/tags/{tag}",
        "object": {
            "type": "tag" if annotated else "commit",
            "sha": "34" * 20 if annotated else "12" * 20,
        },
    }
    annotation: dict[str, object] = {
        "sha": "34" * 20,
        "tag": tag,
        "object": {"type": "commit", "sha": "12" * 20},
    }
    replies = {
        f"repos/{sign_release.REPOSITORY}/actions/runs/123": run,
        f"repos/{sign_release.REPOSITORY}/git/ref/tags/{tag}": ref,
        f"repos/{sign_release.REPOSITORY}/git/tags/{'34' * 20}": annotation,
    }
    calls: list[str] = []

    def read(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command[:2] == ["gh", "api"]
        calls.append(command[2])
        return subprocess.CompletedProcess(command, 0, json.dumps(replies[command[2]]))

    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "gh")
    monkeypatch.setattr(sign_release, "_run", read)
    return run, ref, annotation, calls


@pytest.mark.parametrize("annotated", [False, True])
def test_a_release_tag_must_resolve_to_the_successful_build_commit(
    monkeypatch: pytest.MonkeyPatch, annotated: bool
) -> None:
    """Leichter und einmal annotierter Tag binden denselben tatsächlichen Baucommit."""
    run, _ref, _annotation, calls = _tag_run_api(monkeypatch, annotated)
    assert sign_release.verify_ci_run("123", sign_release.BUILD_WORKFLOW) == run
    assert len(calls) == (3 if annotated else 2)


@pytest.mark.parametrize(
    "problem",
    [
        "other_version",
        "pull_request",
        "other_workflow",
        "other_repository",
        "other_head_repository",
        "unfinished",
        "failed",
        "branch_instead_of_tag",
        "moved_ref",
        "tree_ref",
        "missing_ref",
        "invalid_sha",
        "annotation_sha",
        "annotation_name",
        "moved_annotation",
        "nested_tag",
        "tree_annotation",
    ],
)
def test_only_the_current_real_release_tag_can_authorise_signing(
    monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    """Ein gleichnamiger Zweig und veränderte oder fremde Tagziele bleiben gesperrt."""
    annotated = problem in {
        "annotation_sha",
        "annotation_name",
        "moved_annotation",
        "nested_tag",
        "tree_annotation",
    }
    run, ref, annotation, _calls = _tag_run_api(monkeypatch, annotated)
    changes: dict[str, tuple[str, object]] = {
        "other_version": ("head_branch", "v99.0.0"),
        "pull_request": ("event", "pull_request"),
        "other_workflow": ("path", ".github/workflows/other.yml"),
        "other_repository": ("repository", {"full_name": "foreign/repo"}),
        "other_head_repository": ("head_repository", {"full_name": "foreign/repo"}),
        "unfinished": ("status", "in_progress"),
        "failed": ("conclusion", "failure"),
    }
    if problem in changes:
        key, value = changes[problem]
        run[key] = value
    elif problem == "branch_instead_of_tag":
        ref["ref"] = f"refs/heads/v{make_installer.APP_VERSION}"
    elif problem == "missing_ref":
        ref.clear()
    elif problem in {"moved_ref", "tree_ref", "invalid_sha"}:
        ref["object"] = {
            "type": "tree" if problem == "tree_ref" else "commit",
            "sha": "bad" if problem == "invalid_sha" else "56" * 20,
        }
    elif problem == "annotation_sha":
        annotation["sha"] = "56" * 20
    elif problem == "annotation_name":
        annotation["tag"] = "v99.0.0"
    else:
        annotation["object"] = {
            "type": {"nested_tag": "tag", "tree_annotation": "tree"}.get(problem, "commit"),
            "sha": "56" * 20,
        }
    with pytest.raises(sign_release.SigningError):
        sign_release.verify_ci_run("123", sign_release.BUILD_WORKFLOW)


@pytest.mark.parametrize(
    "workflow", [sign_release.INSTALLER_WORKFLOW, ".github/workflows/other.yml"]
)
def test_a_tag_never_authorises_the_installer_or_an_unrecognised_workflow(
    monkeypatch: pytest.MonkeyPatch, workflow: str
) -> None:
    """Die Tag-Ausnahme gilt ausschließlich für den Hauptbau."""
    run, _ref, _annotation, _calls = _tag_run_api(monkeypatch)
    run["path"] = workflow
    with pytest.raises(sign_release.SigningError):
        sign_release.verify_ci_run("123", workflow)


@pytest.mark.parametrize("annotated", [False, True])
@pytest.mark.parametrize("problem", ["http", "json", "shape", "timeout", "os"])
def test_an_unreadable_release_tag_stops_before_signing(
    monkeypatch: pytest.MonkeyPatch, annotated: bool, problem: str
) -> None:
    """Jeder fehlende oder unlesbare API-Nachweis hält geschlossen an."""
    _tag_run_api(monkeypatch, annotated)
    original = sign_release._run

    def broken(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        marker = "/git/tags/" if annotated else "/git/ref/"
        if marker not in command[2]:
            return original(command, **kwargs)
        if problem == "timeout":
            raise subprocess.TimeoutExpired("gh", 30)
        if problem == "os":
            raise OSError("API unavailable")
        output = {"http": "{}", "json": "broken", "shape": "[]"}[problem]
        return subprocess.CompletedProcess(command, 1 if problem == "http" else 0, output)

    monkeypatch.setattr(sign_release, "_run", broken)
    with pytest.raises(sign_release.SigningError):
        sign_release.verify_ci_run("123", sign_release.BUILD_WORKFLOW)


def test_ci_metadata_timeout_reports_the_next_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein API-Hänger bleibt ein erklärter Halt, kein Traceback."""
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "gh")

    def timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("gh", 30)

    monkeypatch.setattr(sign_release, "_run", timeout)
    with pytest.raises(sign_release.SigningError, match="gh-Anmeldung"):
        sign_release.verify_ci_run("123", sign_release.BUILD_WORKFLOW)


@pytest.mark.parametrize(
    "problem", ["extra", "missing", "hash", "provenance", "checksum", "encoding"]
)
def test_installer_ci_return_must_match_the_application_provenance(
    signing: dict[str, object], problem: str
) -> None:
    """Unvollständige, veränderte und fremde Rückwege erreichen keine Setup-Signatur."""
    arguments = _application_phase(signing)
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    name = f"{APP}-Setup-{make_installer.APP_VERSION}.exe"
    if problem == "extra":
        tools.installer_files["foreign.dll"] = b"foreign"
    elif problem == "missing":
        del tools.installer_files[name]
    elif problem == "hash":
        tools.installer_files[name] = b"changed"
    elif problem == "provenance":
        metadata = json.loads(tools.installer_files[sign_release.INSTALLER_METADATA])
        metadata["source_run_id"] = "999"
        tools.installer_files[sign_release.INSTALLER_METADATA] = json.dumps(metadata).encode()
    else:
        tools.installer_files[name + ".sha256"] = (
            b"\xff" if problem == "encoding" else b"wrong hash"
        )
    with pytest.raises(sign_release.SigningError):
        sign_release.sign_installer(**arguments)  # type: ignore[arg-type]
    assert len([call for call in tools.calls if call[1] == "sign"]) == 1
    assert not Path(signing["output"]).exists()  # type: ignore[arg-type]


def test_changed_stage_and_rebound_hashes_still_fail_against_the_original_ci_archive(
    signing: dict[str, object],
) -> None:
    """Eine nachträglich passend geschriebene lokale Prüfsumme ersetzt die CI-Herkunft nicht."""
    arguments = _application_phase(signing)
    stage = signing["stage"]
    assert isinstance(stage, Path)
    target = stage / f"dist/{APP}/_internal/python313.dll"
    target.write_bytes(b"changed after application signing")
    handoff_path = stage / sign_release.HANDOFF_NAME
    handoff = json.loads(handoff_path.read_text())
    handoff["input_sha256"][target.relative_to(stage).as_posix()] = _sha256(target)
    handoff_path.write_text(json.dumps(handoff))
    with pytest.raises(sign_release.SigningError, match=r"Arbeitsstand.*CI-Herkunft"):
        sign_release.sign_installer(**arguments)  # type: ignore[arg-type]


def test_installer_run_must_have_the_same_commit(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein erfolgreicher Installerlauf aus einem anderen Commit bleibt ein fremder Rückweg."""
    arguments = _application_phase(signing)
    monkeypatch.setattr(
        sign_release,
        "verify_ci_run",
        lambda run_id, workflow: {**_ci_record(run_id, workflow), "head_sha": "34" * 20},
    )
    with pytest.raises(sign_release.SigningError, match="CI-Commits"):
        sign_release.sign_installer(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("status,identity", [("NotSigned", THUMBPRINT), ("Valid", "CD" * 20)])
def test_authenticode_identity_rejects_an_invalid_or_foreign_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, identity: str
) -> None:
    """Eine gültige fremde Signatur erfüllt die ausdrückliche Zertifikatswahl nicht."""
    monkeypatch.setattr(
        sign_release,
        "_read_powershell_json",
        lambda *args: {"Status": status, "Thumbprint": identity},
    )
    with pytest.raises(sign_release.SigningError, match="gewählten Zertifikat"):
        sign_release.verify_signature_identity(tmp_path / "package.exe", THUMBPRINT)


def test_authenticode_path_is_data_and_never_powershell_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shellzeichen im Dateinamen reisen ausschließlich als Umgebungswert."""
    target = tmp_path / "app '; $(Write-Output foreign).exe"

    def read(script: str, environment: dict[str, str]) -> dict[str, str]:
        assert str(target) not in script
        assert environment["SOLIDON_SIGNATURE_PATH"] == str(target.resolve())
        return {"Status": "Valid", "Thumbprint": THUMBPRINT.lower()}

    monkeypatch.setattr(sign_release, "_read_powershell_json", read)
    sign_release.verify_signature_identity(target, THUMBPRINT)


def test_old_local_build_entry_and_missing_phase_stop_before_any_work(
    signing: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Weder die alte API noch ein unvollständiger CLI-Aufruf baut still lokal."""
    with pytest.raises(sign_release.SigningError, match="CI baut"):
        sign_release.run(subject="Beispiel")
    assert sign_release.main(["--run", "123", "--thumbprint", THUMBPRINT]) == 1
    assert "--phase application" in capsys.readouterr().out
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    assert tools.calls == [] and tools.downloads == []


def test_signtool_is_found_in_the_newest_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne PATH-Eintrag zählt das neueste Windows SDK, und ohne SDK ein Satz mit dem Ausweg."""
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: None)
    monkeypatch.setattr(sign_release, "SDK_BIN", tmp_path / "kits")
    with pytest.raises(sign_release.SigningError, match="Windows SDK"):
        sign_release.find_signtool()

    for version in ("10.0.22621.0", "10.0.26100.0"):
        tool = tmp_path / "kits" / version / "x64" / "signtool.exe"
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"")
    assert (
        sign_release.find_signtool() == tmp_path / "kits" / "10.0.26100.0" / "x64" / "signtool.exe"
    )


def test_the_command_line_reports_a_missing_archive_with_the_way_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], signing: dict[str, object]
) -> None:
    """Der Einstieg endet nie mit einem Traceback — die Meldung nennt den nächsten Schritt."""
    archive = signing["archive"]
    assert isinstance(archive, Path)
    archive.unlink()
    code = sign_release.main(
        [
            "--phase",
            "application",
            "--run",
            "123",
            "--stage",
            str(tmp_path / "stage"),
            "--subject",
            "x",
        ]
    )
    assert code == 1
    assert "Laufnummer prüfen" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["copy", "corrupt", "checksum"])
def test_final_signing_copy_keeps_the_previous_complete_package(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Abbruch und falsche Kopierbytes werden vor dem sichtbaren Paketwechsel erkannt."""
    output = signing["output"]
    assert isinstance(output, Path)
    output.mkdir()
    result = output / f"{APP}-Setup-{make_installer.APP_VERSION}.exe"
    result.write_bytes(b"previous installer")
    checksum = result.with_name(result.name + ".sha256")
    checksum.write_bytes(b"previous checksum")
    original = sign_release.shutil.copy2

    def copy(source: object, target: object, **kwargs: object) -> object:
        destination = Path(target)
        if destination.is_relative_to(output):
            if failure == "copy" or (failure == "checksum" and destination.suffix == ".sha256"):
                destination.write_bytes(b"partial")
                raise OSError("copy failed")
            if failure == "corrupt" and destination.suffix == ".exe":
                destination.write_bytes(b"incorrect bytes")
                return destination
        return original(source, target, **kwargs)

    monkeypatch.setattr(sign_release.shutil, "copy2", copy)
    with pytest.raises((OSError, sign_release.SigningError)):
        _go(signing)
    assert result.read_bytes() == b"previous installer"
    assert checksum.read_bytes() == b"previous checksum"
    assert set(output.iterdir()) == {result, checksum}


def test_final_checksum_replace_failure_removes_an_obsolete_checksum(
    signing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach dem vollständigen Paketwechsel darf keine frühere Prüfsumme stehen bleiben."""
    output = signing["output"]
    assert isinstance(output, Path)
    output.mkdir()
    result = output / f"{APP}-Setup-{make_installer.APP_VERSION}.exe"
    checksum = result.with_name(result.name + ".sha256")
    result.write_bytes(b"previous installer")
    checksum.write_bytes(b"previous checksum")
    original = Path.replace

    def fail(path: Path, target: Path) -> Path:
        if target == checksum:
            raise OSError("rename failed")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(OSError):
        _go(signing)
    assert result.read_bytes().endswith(FakeTools.SIGNATURE)
    assert not checksum.exists()
    assert list(output.iterdir()) == [result]
