"""Das lokale Signierwerkzeug fährt die CI-Übergabe prüfsummengebunden zu Ende.

Signiert wird auf Roberts Rechner, nicht in GitHub Actions — die CI liefert
nur das gebundene Archiv. Diese Tests stellen signtool, ISCC und das Archiv
nach und prüfen, dass jede Abweichung die Kette anhält, **bevor** ein
Zertifikat ins Spiel kommt.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools import make_installer, sign_release

APP = make_installer.APP_NAME


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
        self.evidence_fails = False
        self.application_signed_when_packed: bool | None = None

    def __call__(self, command: list[str], *, check: bool) -> subprocess.CompletedProcess[bytes]:
        assert check is False
        self.calls.append(list(command))
        name = Path(command[0]).name.lower()
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
            signed = Path(command[-1]).read_bytes().endswith(self.SIGNATURE)
            return subprocess.CompletedProcess(
                command, 0 if signed and not self.verify_fails else 1
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


@pytest.fixture
def signing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    tree = _product_tree(tmp_path / "ci", monkeypatch)
    archive = _pack(tree, tmp_path / "download")
    tools = FakeTools()
    monkeypatch.setattr(sign_release, "_run", tools)
    monkeypatch.setattr(sign_release, "find_signtool", lambda explicit=None: Path("signtool.exe"))
    monkeypatch.setattr(make_installer, "find_compiler", lambda: Path("ISCC.exe"))
    monkeypatch.setattr(sign_release, "ROOT", tmp_path / "repo")
    return {
        "archive": archive,
        "stage": tmp_path / "stage",
        "output": tmp_path / "out",
        "evidence": tmp_path / "repo" / "build" / "release-evidence.json",
        "tools": tools,
        "tree": tree,
    }


def _go(signing: dict[str, object], **overrides: object) -> Path:
    arguments: dict[str, object] = {
        "archive": signing["archive"],
        "stage": signing["stage"],
        "subject": "Robert Schneider",
        "thumbprint": None,
        "timestamp_url": sign_release.TIMESTAMP_URL,
        "signtool": None,
        "evidence": signing["evidence"],
        "output_dir": signing["output"],
    }
    arguments.update(overrides)
    return sign_release.run(**arguments)  # type: ignore[arg-type]


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
    """Signieren, prüfen, bauen, signieren, prüfen — in dieser Reihenfolge, nichts dazwischen."""
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
        ("iscc.exe", steps[2][1]),
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
        "/n",
    ]
    assert sign_call[9] == "Robert Schneider"
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


def test_a_failing_release_check_warns_but_still_delivers_the_signed_installer(
    signing: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """Kein Release hängt an einer Prüfung, die zum ersten Mal läuft — wie in der CI."""
    tools = signing["tools"]
    assert isinstance(tools, FakeTools)
    tools.evidence_fails = True

    result = _go(signing)

    assert result.is_file() and result.read_bytes().endswith(FakeTools.SIGNATURE)
    output = capsys.readouterr().out
    assert "WARNUNG" in output and "Register" in output
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der Einstieg endet nie mit einem Traceback — die Meldung nennt den nächsten Schritt."""
    code = sign_release.main(
        [
            "--archive",
            str(tmp_path / "fehlt.zip"),
            "--stage",
            str(tmp_path / "stage"),
            "--subject",
            "x",
        ]
    )
    assert code == 1
    assert "--run" in capsys.readouterr().out
