"""Die Werkzeuge, die etwas wegräumen oder hinausschicken: ``link_memory``,
``to_main``, ``upload_website``.

Alle drei gegen temporäre Bestände, keines gegen das Repository, das
Nutzerprofil oder einen Server — die Proben des Gesamtreviews vom 05.09.2026
(R19, R20, R21), als Zusicherung festgehalten.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tools import link_memory, to_main
from tools import upload_website as upload

# --- link_memory -----------------------------------------------------------------


def test_the_memory_move_keeps_every_local_file(tmp_path: Path) -> None:
    """R19: Beim Umzug wurden nur Markdown-Dateien der obersten Ebene
    übernommen, und nur die, deren Name im Repository fehlte — danach fiel
    das ganze lokale Verzeichnis. Eine lokal ergänzte ``topic.md`` verschwand
    ersatzlos, sobald im Repository eine andere lag; Unterordner und
    Nicht-Markdown-Dateien gleich mit."""
    local, shared = tmp_path / "local", tmp_path / "shared"
    local.mkdir()
    shared.mkdir()
    (local / "topic.md").write_text("Nur lokal vorhandene Erkenntnis", encoding="utf-8")
    (shared / "topic.md").write_text("Andere vorhandene Erkenntnis", encoding="utf-8")
    (local / "gleich.md").write_text("beide gleich", encoding="utf-8")
    (shared / "gleich.md").write_text("beide gleich", encoding="utf-8")
    (local / "unten").mkdir()
    (local / "unten" / "tief.md").write_text("aus dem Unterordner", encoding="utf-8")
    (local / "notiz.txt").write_text("kein Markdown", encoding="utf-8")

    with (
        patch.object(link_memory, "IN_REPO", shared),
        patch.object(link_memory, "harness_dir", return_value=local),
        patch.object(link_memory, "link"),
    ):
        status = link_memory.main([])

    assert status == 0
    assert not local.exists(), "der lokale Ort ist geräumt — weil alles einen Ort hat"
    assert (shared / "topic.md").read_text(encoding="utf-8") == "Andere vorhandene Erkenntnis"
    assert (shared / "topic.dieser-maschine.md").read_text(encoding="utf-8") == (
        "Nur lokal vorhandene Erkenntnis"
    ), "die abweichende Fassung liegt daneben"
    assert (shared / "unten" / "tief.md").read_text(encoding="utf-8") == "aus dem Unterordner"
    assert (shared / "notiz.txt").read_text(encoding="utf-8") == "kein Markdown"
    assert not (shared / "gleich.dieser-maschine.md").exists(), "gleich heißt nichts zu tun"


def test_the_memory_move_stops_before_deleting_what_it_could_not_keep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gelöscht wird erst, wenn jede Datei nachweislich einen Ort hat. Fällt
    das Übernehmen aus, bleibt das Nutzerprofil stehen."""
    local, shared = tmp_path / "local", tmp_path / "shared"
    local.mkdir()
    shared.mkdir()
    (local / "topic.md").write_text("wertvoll", encoding="utf-8")
    monkeypatch.setattr(link_memory.shutil, "copy2", lambda *_args, **_kwargs: None)

    with (
        patch.object(link_memory, "IN_REPO", shared),
        patch.object(link_memory, "harness_dir", return_value=local),
        patch.object(link_memory, "link"),
    ):
        status = link_memory.main([])

    assert status == 2
    assert (local / "topic.md").read_text(encoding="utf-8") == "wertvoll", "nichts ist weg"


# --- to_main ---------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout.strip()


def test_a_main_that_cannot_be_fast_forwarded_is_not_pushed(tmp_path: Path) -> None:
    """R20: Der Rückgabewert von ``git merge --ff-only`` wurde ignoriert. Trug
    das lokale ``main`` einen eigenen Commit, scheiterte das Vorspulen, der
    Push danach gelang trotzdem — draußen war ein ungeprüftes ``main``, und
    das Werkzeug meldete Erfolg für den geprüften Branch."""
    remote, working = tmp_path / "origin.git", tmp_path / "working"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    _git("init", "-b", "main", str(working), cwd=tmp_path)
    _git("config", "user.name", "Prüfstand", cwd=working)
    _git("config", "user.email", "pruefstand@example.invalid", cwd=working)
    _git("config", "core.hooksPath", str(tmp_path / "keine-hooks"), cwd=working)
    _git("remote", "add", "origin", str(remote), cwd=working)
    (working / "base.txt").write_text("base", encoding="utf-8")
    _git("add", "base.txt", cwd=working)
    _git("commit", "-m", "Basis", cwd=working)
    _git("push", "-u", "origin", "main", cwd=working)
    base = _git("rev-parse", "HEAD", cwd=working)
    _git("switch", "-c", "feature", cwd=working)
    (working / "feature.txt").write_text("feature", encoding="utf-8")
    _git("add", "feature.txt", cwd=working)
    _git("commit", "-m", "Geprüfte Arbeit", cwd=working)
    _git("switch", "main", cwd=working)
    (working / "other.txt").write_text("other", encoding="utf-8")
    _git("add", "other.txt", cwd=working)
    _git("commit", "-m", "Ungeprüfter Stand auf main", cwd=working)
    _git("switch", "feature", cwd=working)

    def local_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=working, capture_output=True, text=True, encoding="utf-8"
        )

    with (
        patch.object(to_main, "git", side_effect=local_git),
        patch.object(to_main, "gate_passes", return_value=True),
    ):
        status = to_main.deliver("pruefstand", False)

    assert status != 0, "ein nicht vorspulbares main ist kein Erfolg"
    assert _git("rev-parse", "refs/heads/main", cwd=remote) == base, "draußen steht die Basis"
    assert _git("rev-parse", "--abbrev-ref", "HEAD", cwd=working) == "feature", "zurück am Branch"


# --- upload_website --------------------------------------------------------------


class _FakeFTP:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    def cwd(self, path: str) -> None:
        pass

    def storbinary(self, command: str, stream: object) -> None:
        self.sent.append((command, stream.read()))  # type: ignore[attr-defined]

    def quit(self) -> None:
        pass


def test_the_missing_files_mode_does_not_pass_an_unsigned_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R21: Bei ``--fehlend`` war die Dateiliste während der Signaturprüfung
    noch leer; gefüllt wurde sie danach aus dem Serverabgleich und unverändert
    hochgeladen. Eine ohne Unterschrift geschriebene ``version.json`` ersetzte
    so die gültige — und jede Installation verwarf das Manifest still."""
    payload = json.loads((upload.LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
    payload.pop("signature", None)
    local = tmp_path / "website"
    local.mkdir()
    (local / "version.json").write_text(json.dumps(payload), encoding="utf-8")
    remote = {"dl/" + entry["file"]: entry["size"] for entry in payload["packages"].values()}
    ftp = _FakeFTP()
    monkeypatch.setattr(sys, "argv", ["upload_website.py", "--fehlend"])

    with (
        patch.object(upload, "LOCAL_ROOT", local),
        patch.object(upload.asset_rights, "require_website_assets_cleared"),
        patch.object(upload, "read_access", return_value=dict(upload.TEMPLATE)),
        patch.object(upload, "connect", return_value=ftp),
        patch.object(upload, "remote_index", return_value=remote),
        pytest.raises(SystemExit) as stopped,
    ):
        upload.main()

    assert stopped.value.code not in (0, None)
    assert not [name for name, _body in ftp.sent if "version.json" in name], (
        "die unsignierte Datei ging nicht hinaus"
    )


# --- gate_lock -------------------------------------------------------------------


def test_an_unreadable_old_lock_file_does_not_block_the_gate_forever(tmp_path: Path) -> None:
    """R17: Eine leere Sperrdatei ließ ``_read`` ``None`` liefern, das
    ``open("x")`` darunter scheiterte an ihr in jeder Runde, und das Tor
    stand für jeden weiteren Lauf endlos. Alt und unlesbar heißt: ein Rest
    ohne Halter, und der wird geräumt."""
    import json
    import os
    import time

    from tools import gate_lock

    lock = tmp_path / "tor.lock"
    lock.write_bytes(b"")
    old = time.time() - 60.0
    os.utime(lock, (old, old))

    foreign = gate_lock._acquire(lock, "pruefstand", wait=0.0)

    assert foreign is None, "das Schloss wurde genommen"
    assert json.loads(lock.read_text(encoding="utf-8"))["wer"] == "pruefstand"


# --- make_download ---------------------------------------------------------------


def test_the_download_store_takes_the_new_bytes_even_at_the_same_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-15: Eine schon liegende Datei wurde nur bei abweichender Größe
    ersetzt — ein neu gebautes Paket derselben Länge blieb liegen, und die
    Prüfsumme darunter belegte das alte."""
    import hashlib

    from tools import make_download

    store = tmp_path / "dl"
    store.mkdir()
    source = tmp_path / "Solidon3D-Setup.exe"
    source.write_bytes(b"NEW_CONTENT")
    (store / source.name).write_bytes(b"OLD_CONTENT")
    monkeypatch.setattr(make_download, "STORE", store)
    monkeypatch.setattr(make_download, "refuse_wrong_delivery", lambda _paths: None)

    packages = make_download.read_packages([source])

    assert (store / source.name).read_bytes() == b"NEW_CONTENT"
    assert packages[0].hash_ == hashlib.sha256(b"NEW_CONTENT").hexdigest()
    assert not list(store.glob("*.part")), "keine halbe Kopie bleibt liegen"


# --- check_new_texts -------------------------------------------------------------


def test_the_commit_guard_reads_escapes_like_python_and_keeps_the_umlauts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R18: ``text.encode().decode("unicode_escape")`` las die UTF-8-Bytes eines
    Umlauts als einzelne Codepunkte, sobald daneben eine Escape-Folge stand —
    aus „Wählen" wurde „WÃ¤hlen", und die vorhandene Übersetzung galt als
    fehlend. Der Wächter hielt damit korrekt übersetzte Commits an."""
    from types import SimpleNamespace

    from tools import check_new_texts

    diff = '+    tr("Wählen Sie eine Datei.\\nErneut versuchen.")\n+    _("Gerade")\n'
    monkeypatch.setattr(
        check_new_texts.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=diff)
    )

    assert check_new_texts.added_texts() == ["Wählen Sie eine Datei.\nErneut versuchen.", "Gerade"]


# --- hold_back_version -------------------------------------------------------------


def test_without_local_packages_the_manifest_size_decides_whether_a_package_is_whole(
    tmp_path: Path,
) -> None:
    """R22: Fehlten die lokalen Pakete — auf jedem anderen Arbeitsrechner der
    Normalfall —, galt jede Datei oben als vollständig, sobald sie da war. Ein
    abgebrochener Upload von einem Byte gab ``version.json`` frei, und jede
    Installation lud sich das halbe Paket."""
    payload = json.loads((upload.LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
    local = tmp_path / "website"
    local.mkdir()
    (local / "version.json").write_text(json.dumps(payload), encoding="utf-8")
    remote = {"dl/" + entry["file"]: 1 for entry in payload["packages"].values()}
    assert remote, "ohne versprochene Pakete prüft dieser Test nichts"

    with (
        patch.object(upload, "LOCAL_ROOT", local),
        patch.object(upload, "remote_index", return_value=remote),
    ):
        kept = upload.hold_back_version(object(), "root", [local / "version.json"])  # type: ignore[arg-type]

    assert kept == [], "ein Byte oben ist kein Paket — die Auskunft bleibt liegen"

    whole = {"dl/" + entry["file"]: entry["size"] for entry in payload["packages"].values()}
    with (
        patch.object(upload, "LOCAL_ROOT", local),
        patch.object(upload, "remote_index", return_value=whole),
    ):
        kept = upload.hold_back_version(object(), "root", [local / "version.json"])  # type: ignore[arg-type]

    assert kept == [local / "version.json"], "stimmt die Größe, geht sie hoch"
