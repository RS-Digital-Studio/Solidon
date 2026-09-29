"""Die CI baut nur aus dem gebundenen Hauptlauf und der geprüften lokalen Signatur."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools import sign_release
from tools import windows_signed_installer as tool

REPOSITORY = sign_release.REPOSITORY
RUN_ID = "1234"
COMMIT = "ab" * 20
RELEASE_ID = "5678"
DIGEST = "cd" * 32


def _run_record() -> dict[str, Any]:
    return {
        "id": int(RUN_ID),
        "path": ".github/workflows/build.yml",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": COMMIT,
        "event": "workflow_dispatch",
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


def _release_record() -> dict[str, Any]:
    return {
        "id": int(RELEASE_ID),
        "draft": True,
        "published_at": None,
        "target_commitish": COMMIT,
        "assets": [
            {"id": 1, "name": "Solidon3D.exe", "state": "uploaded"},
            {"id": 2, "name": tool.APPLICATION_RECORD, "state": "uploaded"},
        ],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 999),
        ("path", ".github/workflows/other.yml"),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("head_branch", "feature"),
        ("head_sha", "00" * 20),
        ("repository", {"full_name": "other/Solidon"}),
        ("head_repository", {"full_name": "attacker/Solidon"}),
        ("event", "pull_request"),
        ("event", "push"),
    ],
)
def test_another_source_cannot_reach_the_installer(
    field: str, value: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run_record()
    run[field] = value
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(run)),
    )
    with pytest.raises(sign_release.SigningError):
        tool.verify_source_run(RUN_ID, COMMIT)


@pytest.mark.parametrize("annotated", [False, True])
@pytest.mark.parametrize("same_commit", [False, True])
def test_a_real_release_tag_reaches_only_its_own_installer_commit(
    monkeypatch: pytest.MonkeyPatch, annotated: bool, same_commit: bool
) -> None:
    """Auch der Tag-Hauptbau bleibt an den identischen Installer-Quellstand gebunden."""
    tag = f"v{tool.APP_VERSION}"
    run = {**_run_record(), "event": "push", "head_branch": tag}
    replies = {
        f"repos/{REPOSITORY}/actions/runs/{RUN_ID}": run,
        f"repos/{REPOSITORY}/git/ref/tags/{tag}": {
            "ref": f"refs/tags/{tag}",
            "object": {
                "type": "tag" if annotated else "commit",
                "sha": "34" * 20 if annotated else COMMIT,
            },
        },
        f"repos/{REPOSITORY}/git/tags/{'34' * 20}": {
            "sha": "34" * 20,
            "tag": tag,
            "object": {"type": "commit", "sha": COMMIT},
        },
    }
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: "gh")
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, json.dumps(replies[command[2]])
        ),
    )
    if same_commit:
        tool.verify_source_run(RUN_ID, COMMIT)
    else:
        with pytest.raises(sign_release.SigningError, match="verschiedene Commits"):
            tool.verify_source_run(RUN_ID, "56" * 20)


def test_the_successful_main_run_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        sign_release,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(_run_record())),
    )
    tool.verify_source_run(RUN_ID, COMMIT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 99),
        ("draft", False),
        ("published_at", "2026-09-23T18:00:00Z"),
        ("target_commitish", "main"),
        ("assets", []),
    ],
)
def test_release_or_unbound_input_is_rejected(field: str, value: Any) -> None:
    release = _release_record()
    release[field] = value
    with pytest.raises(sign_release.SigningError):
        tool.select_assets(release, RELEASE_ID, COMMIT)


def test_the_draft_must_not_contain_ambiguous_application_assets() -> None:
    release = _release_record()
    release["assets"].append(release["assets"][0].copy())
    with pytest.raises(sign_release.SigningError, match="mehrfach"):
        tool.select_assets(release, RELEASE_ID, COMMIT)


@pytest.mark.parametrize(
    "key,value",
    [
        ("run_id", "123; Write-Host bad"),
        ("release_id", "../123"),
        ("repository", "example/Solidon/../../other"),
        ("commit", "main"),
        ("digest", "sha256:" + DIGEST),
        ("version", "999.0.0"),
    ],
)
def test_untrusted_identifiers_never_reach_the_transport(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv("GITHUB_SHA", COMMIT)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    request = {
        "repository": REPOSITORY,
        "run_id": RUN_ID,
        "commit": COMMIT,
        "version": tool.APP_VERSION,
        "release_id": RELEASE_ID,
        "digest": DIGEST,
    }
    request[key] = value
    with pytest.raises(sign_release.SigningError):
        tool.validate_request(**request)


@pytest.mark.parametrize(
    "key,value", [("GITHUB_SHA", "00" * 20), ("GITHUB_REF", "refs/heads/other")]
)
def test_workflow_code_is_bound_to_the_actual_main_checkout(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv("GITHUB_SHA", COMMIT)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ID", "6789")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setattr(tool, "_checkout_commit", lambda: COMMIT)
    monkeypatch.setenv(key, value)
    with pytest.raises(sign_release.SigningError):
        tool.validate_request(REPOSITORY, RUN_ID, COMMIT, tool.APP_VERSION, RELEASE_ID, DIGEST)


@pytest.fixture
def ci_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Verwendet den vorhandenen echten Übergabeerzeuger mit kleinen Produktdateien."""
    from tests.test_sign_release import _pack, _product_tree

    monkeypatch.setenv("GITHUB_SHA", COMMIT)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ID", "6789")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setattr(tool, "_checkout_commit", lambda: COMMIT)
    tree = _product_tree(tmp_path / "product", monkeypatch)
    archive = _pack(tree, tmp_path / "artifact")
    unsigned = tree / "dist/Solidon3D/Solidon3D.exe"
    signed = unsigned.read_bytes() + b" SIGNED"
    signed_digest = hashlib.sha256(signed).hexdigest()
    record = {
        "schema_version": 1,
        "app_version": tool.APP_VERSION,
        "source_run_id": RUN_ID,
        "source_commit": COMMIT,
        "source_archive_sha256": sign_release._sha256(archive),
        "unsigned_application_sha256": sign_release._sha256(unsigned),
        "signed_application_sha256": signed_digest,
        "certificate_thumbprint": tool.CERTIFICATE_THUMBPRINT,
    }
    state: dict[str, Any] = {
        "record": record,
        "signed": signed,
        "checks": [],
        "release": _release_record(),
        "archive": archive,
    }

    def api(repository: str, suffix: str) -> Any:
        assert repository == REPOSITORY
        if suffix == f"actions/runs/{RUN_ID}":
            return _run_record()
        if suffix.endswith("artifacts?per_page=100"):
            return {
                "total_count": 1,
                "artifacts": [{"name": sign_release.ARTIFACT_NAME, "expired": False}],
            }
        assert suffix == f"releases/{RELEASE_ID}"
        return state["release"]

    def transport(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command[:3] == ["gh", "run", "download"]
        target = Path(command[-1])
        shutil.copytree(archive.parent, target, dirs_exist_ok=True)
        if state.get("extra_download"):
            (target / "extra.exe").write_bytes(b"unexpected")
        return subprocess.CompletedProcess(command, 0, "")

    def download(repository: str, asset: dict[str, Any], target: Path) -> None:
        if asset["name"] == "Solidon3D.exe":
            target.write_bytes(state["signed"])
        else:
            target.write_text(json.dumps(record), encoding="utf-8")

    monkeypatch.setattr(tool, "_api", api)

    def verified_run(run_id: str, workflow: str) -> dict[str, Any]:
        assert run_id == RUN_ID and workflow == sign_release.BUILD_WORKFLOW
        return _run_record()

    monkeypatch.setattr(sign_release, "verify_ci_run", verified_run)
    monkeypatch.setattr(tool, "_download_asset", download)
    monkeypatch.setattr(sign_release, "_run", transport)
    monkeypatch.setattr(sign_release.shutil, "which", lambda name: name)
    monkeypatch.setattr(sign_release, "find_signtool", lambda: Path("signtool.exe"))
    monkeypatch.setattr(
        sign_release, "verify_file", lambda *args: state["checks"].append("timestamp")
    )
    monkeypatch.setattr(
        sign_release,
        "verify_signature_identity",
        lambda *args: state["checks"].append("identity"),
    )
    state["args"] = {
        "repository": REPOSITORY,
        "run_id": RUN_ID,
        "commit": COMMIT,
        "version": tool.APP_VERSION,
        "release_id": RELEASE_ID,
        "signed_digest": signed_digest,
        "work": tmp_path / "work",
    }
    return state


@pytest.mark.parametrize("installer_commit", [COMMIT, "cd" * 20])
def test_only_the_exe_changes_and_the_return_contains_exactly_three_files(
    ci_input: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    installer_commit: str,
) -> None:
    monkeypatch.setenv("GITHUB_SHA", installer_commit)
    monkeypatch.setattr(tool, "_checkout_commit", lambda: installer_commit)
    checked = []
    monkeypatch.setattr(
        sign_release,
        "verify_installer_source",
        lambda source, actual: checked.append((source, actual)),
    )
    tool.prepare(**ci_input["args"])
    assert checked == [(COMMIT, installer_commit)]
    work = ci_input["args"]["work"]
    stage = work / "stage"
    handoff = sign_release.load_handoff(stage)
    sign_release.verify_inputs(stage, handoff)
    assert (stage / "dist/Solidon3D/Solidon3D.exe").read_bytes() == ci_input["signed"]
    assert ci_input["checks"] == ["timestamp", "identity"]
    assert (stage / "dist/Solidon3D/_internal/python313.dll").read_bytes() == b"Python-Laufzeit"
    monkeypatch.setattr(tool.make_installer, "compiler_version", lambda compiler: "7.1.0")

    def compiler(stage: Path, handoff: dict[str, Any], executable: Path) -> Path:
        result = stage / "dist" / handoff["setup_filename"]
        result.write_bytes(b"INSTALLER WITH SIGNED APP")
        return result

    monkeypatch.setattr(sign_release, "build_installer", compiler)
    output = tmp_path / "output"
    tool.build(work, Path("ISCC.exe"), output)
    setup_name = f"Solidon3D-Setup-{tool.APP_VERSION}.exe"
    assert {path.name for path in output.iterdir()} == {
        setup_name,
        setup_name + ".sha256",
        tool.INSTALLER_RECORD,
    }
    result = json.loads((output / tool.INSTALLER_RECORD).read_text(encoding="utf-8"))
    assert result == {
        **ci_input["record"],
        "installer_sha256": sign_release._sha256(output / setup_name),
        "installer_commit": installer_commit,
        "installer_run_id": "6789",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_REPOSITORY", "foreign/repo"),
        ("GITHUB_RUN_ID", "not-a-run"),
        ("GITHUB_SHA", "main"),
    ],
)
def test_real_installer_context_is_required_before_any_archive(ci_input, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(sign_release.SigningError):
        tool.prepare(**ci_input["args"])
    assert not ci_input["args"]["work"].exists()


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "app_version",
        "source_run_id",
        "source_commit",
        "source_archive_sha256",
        "unsigned_application_sha256",
        "signed_application_sha256",
        "certificate_thumbprint",
    ],
)
def test_each_signature_record_binding_is_required(ci_input: dict[str, Any], field: str) -> None:
    ci_input["record"][field] = "wrong"
    with pytest.raises(sign_release.SigningError, match=r"Signaturakte|Signierherkunft"):
        tool.prepare(**ci_input["args"])
    assert ci_input["checks"] == []


def test_changed_signed_application_never_reaches_signature_or_compiler(
    ci_input: dict[str, Any],
) -> None:
    ci_input["signed"] += b"changed"
    with pytest.raises(sign_release.SigningError, match="Prüfsumme"):
        tool.prepare(**ci_input["args"])
    assert ci_input["checks"] == []


def test_archive_corruption_stops_before_the_executable_is_replaced(
    ci_input: dict[str, Any],
) -> None:
    archive = ci_input["archive"]
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(sign_release.SigningError, match="Geändertes Übergabearchiv"):
        tool.prepare(**ci_input["args"])
    assert not (ci_input["args"]["work"] / "stage").exists()
    assert ci_input["checks"] == []


def test_additional_download_payload_is_not_silently_ignored(ci_input: dict[str, Any]) -> None:
    ci_input["extra_download"] = True
    with pytest.raises(sign_release.SigningError, match="Unbekannte Dateien"):
        tool.prepare(**ci_input["args"])
    assert ci_input["checks"] == []


@pytest.mark.parametrize("asset_id", [0, -1, True, "1; anything"])
def test_asset_ids_are_validated_before_creating_a_file(asset_id: object, tmp_path: Path) -> None:
    target = tmp_path / "Solidon3D.exe"
    with pytest.raises(sign_release.SigningError, match="Asset-ID"):
        tool._download_asset(REPOSITORY, {"id": asset_id, "state": "uploaded"}, target)
    assert not target.exists()


@pytest.mark.parametrize("step", ["verify_file", "verify_signature_identity"])
def test_failed_authenticode_timestamp_or_identity_keeps_the_original_exe(
    ci_input: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    step: str,
) -> None:
    def reject(*args: Any) -> None:
        raise sign_release.SigningError("Ungültige Signatur — nicht weiterbauen.")

    monkeypatch.setattr(sign_release, step, reject)
    with pytest.raises(sign_release.SigningError, match="Signatur"):
        tool.prepare(**ci_input["args"])
    application = ci_input["args"]["work"] / "stage/dist/Solidon3D/Solidon3D.exe"
    assert sign_release._sha256(application) == ci_input["record"]["unsigned_application_sha256"]


def test_inno_six_cannot_build_this_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(tool.make_installer, "compiler_version", lambda compiler: "6.7.3")
    with pytest.raises(sign_release.SigningError, match=r"7\.1\.0"):
        tool.build(tmp_path, Path("ISCC.exe"), tmp_path / "output")


def test_workflow_only_transports_public_evidence_and_uses_pinned_tools() -> None:
    workflow = Path(".github/workflows/windows-signed-installer.yml").read_text(encoding="utf-8")
    assert "self-hosted" not in workflow and "secrets." not in workflow
    assert "id-token:" not in workflow and "write-all" not in workflow
    permissions = workflow.split("jobs:", 1)
    assert "contents: read" in permissions[0] and "contents: write" not in permissions[0]
    assert "    permissions:\n      contents: write\n      actions: read" in permissions[1]
    assert "ref: ${{ github.sha }}" in workflow
    assert "windows-signed-installer" in workflow
    assert "0362a383ed217d4c4239b5933866dd96d3eb2102737da92f80f6057a4b40df2f" in workflow
    assert f"name: {tool.ARTIFACT_NAME}" in workflow
    assert "retention-days: 7" in workflow
    for block in workflow.split("run: |")[1:]:
        shell = block.split("\n      -", 1)[0]
        assert "${{ inputs." not in shell
