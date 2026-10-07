"""Die Werkzeuge, die etwas wegräumen oder hinausschicken: ``link_memory``
und ``upload_website``.

Beide gegen temporäre Bestände, keines gegen das Repository, das Nutzerprofil
oder einen Server — die Proben des Gesamtreviews vom 05.09.2026 (R19, R21),
als Zusicherung festgehalten.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tools import link_memory
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


def test_the_memory_returns_from_history_without_overwriting(tmp_path: Path) -> None:
    """`.claude/memory/` steht in `.gitignore`. Der Pull, der die Dateien aus
    dem Index nahm, löscht sie auf den anderen Maschinen; ihr Inhalt steht im
    Elternteil dieses Commits. Zurück kommt, was fehlt — eine Notiz, die dort
    weitergeschrieben wurde, bleibt, wie sie ist."""
    git = ["git", "-C", str(tmp_path), "-c", "user.name=Probe", "-c", "user.email=p@x.invalid"]

    def run(*arguments: str) -> None:
        subprocess.run([*git, *arguments], check=True, capture_output=True)

    run("init", "-q")
    notes = tmp_path / ".claude" / "memory"
    notes.mkdir(parents=True)
    (notes / "MEMORY.md").write_text("Index", encoding="utf-8")
    (notes / "notiz.md").write_text("aus der Historie", encoding="utf-8")
    run("add", ".")
    run("commit", "-q", "--no-verify", "-m", "Erinnerungen")
    run("rm", "-r", "-q", "--cached", ".claude/memory")
    run("commit", "-q", "--no-verify", "-m", "Erinnerungen bleiben auf der Maschine")
    # Was der Pull auf einer anderen Maschine hinterlässt: der Index ist weg,
    # die Notiz wurde dort inzwischen weitergeschrieben.
    (notes / "MEMORY.md").unlink()
    (notes / "notiz.md").write_text("dort weitergeschrieben", encoding="utf-8")

    assert link_memory.restore_from_history(tmp_path) == ["MEMORY.md"]
    assert (notes / "MEMORY.md").read_text(encoding="utf-8") == "Index"
    assert (notes / "notiz.md").read_text(encoding="utf-8") == "dort weitergeschrieben"
    assert link_memory.restore_from_history(tmp_path) == [], "ein zweiter Lauf tut nichts"


def test_without_the_removal_there_is_nothing_to_restore(tmp_path: Path) -> None:
    """Ein Verzeichnis ohne diesen Commit — oder ganz ohne Git — bleibt unberührt."""
    assert link_memory.restore_from_history(tmp_path) == []
    assert not (tmp_path / ".claude").exists()


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


def test_a_note_written_for_an_older_release_is_not_accepted() -> None:
    """Der Hinweistext driftete zwei Veröffentlichungen weit (Robert, 12.09.2026).

    Er ist das einzige Feld der ``version.json``, das ein Mensch schreibt und
    das ``write_version`` deshalb ausdrücklich in Ruhe lässt — und genau das
    hat ihn von 0.3.0 bis 0.4.0 mitreisen lassen, samt der Behauptung „Das
    bisher größte Update" und einer Neuerung aus der Fassung davor. Was ihn
    hält, ist ``notes_version``: Steht er auf einer anderen Fassung als die
    Datei, gehört er zu einer anderen Veröffentlichung.
    """
    from tools.upload_website import StrictJsonError, _validate_remote_version

    payload = json.loads((upload.LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
    _validate_remote_version(payload)

    # **Die eingecheckte Datei trägt das Feld noch nicht**, und das ist kein
    # Versäumnis: Sie ist unterschrieben, und die Unterschrift deckt jedes Feld
    # außer sich selbst. Eingetragen wird es mit dem Satz der nächsten Fassung,
    # und dann wird neu unterschrieben (``tools/sign_version.py``). Bis dahin
    # hält ``write_version`` den Bau an, statt den alten Satz mitzunehmen.
    _validate_remote_version(dict(payload, notes_version=payload["version"]))

    stale = dict(payload, notes_version="0.3.0")
    with pytest.raises(StrictJsonError) as caught:
        _validate_remote_version(stale)
    assert "notes_version" in str(caught.value)


def test_the_download_build_stops_at_a_note_from_a_former_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Riegel gehört an den Anfang des Baus, nicht ans Ende der Kette.

    Die Prüfung beim Hochladen fängt es auch — aber dann liegen die Pakete
    schon gebaut da und der Kasten der Seite ist geschrieben.
    ``write_version`` hält an, solange der Satz für eine ältere Fassung
    geschrieben ist, und sagt, was zu tun ist (Regel 17).
    """
    from tools import make_download

    target = tmp_path / "version.json"
    payload = json.loads((upload.LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
    target.write_text(json.dumps(dict(payload, notes_version="0.3.0")), encoding="utf-8")
    monkeypatch.setattr(make_download, "VERSION_FILE", target)

    with pytest.raises(SystemExit) as stopped:
        make_download.write_version([])

    said = str(stopped.value)
    assert "0.3.0" in said and make_download.APP_VERSION in said
    assert "notes_version" in said, "ohne den Feldnamen sucht der Leser"


# --- make_download ---------------------------------------------------------------


def test_the_download_store_takes_the_new_bytes_even_at_the_same_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-15: Eine schon liegende Datei wurde nur bei abweichender Größe
    ersetzt — ein neu gebautes Paket derselben Länge blieb liegen, und die
    Prüfsumme darunter belegte das alte."""
    import hashlib

    from tools import make_download, sign_release

    store = tmp_path / "dl"
    store.mkdir()
    source = tmp_path / "Solidon3D-x86_64.AppImage"
    source.write_bytes(b"NEW_CONTENT")
    (store / source.name).write_bytes(b"OLD_CONTENT")
    monkeypatch.setattr(make_download, "STORE", store)
    monkeypatch.setattr(make_download, "refuse_wrong_delivery", lambda _paths: None)
    monkeypatch.setattr(sign_release, "find_signtool", lambda: pytest.fail("kein Windows-Paket"))

    packages = make_download.read_packages([source])

    assert (store / source.name).read_bytes() == b"NEW_CONTENT"
    assert packages[0].hash_ == hashlib.sha256(b"NEW_CONTENT").hexdigest()
    assert not list(store.glob("*.part")), "keine halbe Kopie bleibt liegen"


def _download_inputs(root: Path) -> list[Path]:
    """Fünf Auslieferungsplätze, absichtlich mit Windows als letzter Datei."""
    names = (
        "Solidon3D-x86_64.AppImage",
        "Solidon3D-x86_64.flatpak",
        "Solidon3D-macos-arm64.pkg",
        "Solidon3D-macos-x86_64.pkg",
        "Solidon3D-Setup.exe",
    )
    paths = [root / name for name in names]
    for path in paths:
        path.write_bytes(b"NEW_CONTENT")
    return paths


@pytest.mark.parametrize("existing_store", [False, True])
@pytest.mark.parametrize("problem", ["missing", "unsigned", "invalid", "timestamp", "unreadable"])
def test_the_download_build_keeps_every_file_when_windows_verification_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing_store: bool,
    problem: str,
) -> None:
    """Auch ein spätes Windows-Paket sperrt den gesamten Lauf vor der ersten Kopie."""
    from tools import make_download, sign_release

    sources = _download_inputs(tmp_path)
    website = tmp_path / "website"
    store = website / "dl"
    if existing_store:
        store.mkdir(parents=True)
        for source in sources:
            (store / source.name).write_bytes(b"OLD_CONTENT")
    for name in (*make_download.PAGES, "version.json"):
        path = website / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"published {name}", encoding="utf-8")
    before = {
        path.relative_to(website): path.read_bytes()
        for path in website.rglob("*")
        if path.is_file()
    }
    tool = tmp_path / "signtool.exe"
    checked: list[Path] = []

    def find_tool() -> Path:
        if problem == "missing":
            raise sign_release.SigningError("SignTool fehlt; Windows SDK installieren.")
        return tool

    def run_verify(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command == [str(tool), "verify", "/pa", "/all", "/tw", "/v", str(sources[-1])]
        assert kwargs == {"check": False}
        checked.append(Path(command[-1]))
        if problem == "unreadable":
            raise OSError("SignTool lässt sich nicht starten.")
        return subprocess.CompletedProcess(command, 2 if problem == "timestamp" else 1)

    monkeypatch.setattr(make_download, "WEBSITE", website)
    monkeypatch.setattr(make_download, "STORE", store)
    monkeypatch.setattr(make_download, "VERSION_FILE", website / "version.json")
    monkeypatch.setattr(sign_release, "find_signtool", find_tool)
    monkeypatch.setattr(sign_release, "_run", run_verify)
    monkeypatch.setattr(sys, "argv", ["make_download.py", *(str(path) for path in sources)])

    with pytest.raises(SystemExit) as stopped:
        make_download.main()

    after = {
        path.relative_to(website): path.read_bytes()
        for path in website.rglob("*")
        if path.is_file()
    }
    assert after == before, "Downloadbestand, Seiten und Manifest bleiben bytegleich"
    assert store.exists() is existing_store, (
        "auch der Downloadordner entsteht erst nach der Prüfung"
    )
    assert checked == ([] if problem == "missing" else [sources[-1]])
    assert "signieren" in str(stopped.value) and "SignTool" in str(stopped.value)


def test_the_download_store_accepts_verified_windows_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der gemeinsame Prüfer gibt gültige Windows-Bytes vor jeder Mutation frei."""
    from tools import make_download, sign_release

    sources = _download_inputs(tmp_path)
    store = tmp_path / "dl"
    tool = tmp_path / "signtool.exe"
    checked: list[Path] = []

    def run_verify(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command == [str(tool), "verify", "/pa", "/all", "/tw", "/v", str(sources[-1])]
        assert kwargs == {"check": False}
        assert not store.exists(), "die Prüfung steht vor STORE.mkdir"
        checked.append(Path(command[-1]))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(make_download, "STORE", store)
    monkeypatch.setattr(sign_release, "find_signtool", lambda: tool)
    monkeypatch.setattr(sign_release, "_run", run_verify)

    packages = make_download.read_packages(sources)

    assert checked == [sources[-1]]
    assert {package.name for package in packages} == {source.name for source in sources}
    assert all((store / source.name).read_bytes() == source.read_bytes() for source in sources)


def test_withdrawing_downloads_needs_no_windows_signing_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der vorhandene leere Aufruf zieht das Angebot auch ohne Windows-Werkzeuge zurück."""
    from tools import make_download, sign_release

    written: list[str] = []

    def pages(packages: list[make_download.Package]) -> None:
        assert packages == []
        written.append("pages")

    def version(packages: list[make_download.Package]) -> None:
        assert packages == []
        written.append("version")

    monkeypatch.setattr(sys, "argv", ["make_download.py"])
    monkeypatch.setattr(make_download, "write_pages", pages)
    monkeypatch.setattr(make_download, "write_version", version)
    monkeypatch.setattr(make_download, "write_changelog_pages", list)
    monkeypatch.setattr(sign_release, "find_signtool", lambda: pytest.fail("kein Windows-Paket"))

    assert make_download.main() == 0
    assert written == ["pages", "version"]


# --- check_new_texts -------------------------------------------------------------


def _text_guard_git(root: Path, *arguments: str) -> str:
    """Git nur im Prüfkorpus, ohne die Hooks und Signierung der Maschine."""
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=unused-hooks",
            "-c",
            "commit.gpgsign=false",
            *arguments,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=15,
    ).stdout


@pytest.fixture
def text_guard_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Echter Index und davon unabhängiger Arbeitsbaum, ausschließlich unter tmp_path."""
    from tools import check_new_texts

    for name in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(check_new_texts, "ROOT", tmp_path)
    _text_guard_git(tmp_path, "init", "-q")
    _text_guard_git(tmp_path, "config", "user.name", "Test")
    _text_guard_git(tmp_path, "config", "user.email", "test@example.invalid")
    _text_guard_git(tmp_path, "config", "core.quotePath", "true")
    (tmp_path / "app").mkdir()
    source = 'TEXT = tr("Alter Text")\n' + "VALUE = 1\n" * 30
    (tmp_path / "app" / "message.py").write_text(source, encoding="utf-8")
    catalogs = tmp_path / "app" / "i18n" / "locales"
    catalogs.mkdir(parents=True)
    (catalogs / "en.json").write_text("{}\n", encoding="utf-8")
    _text_guard_git(tmp_path, "add", ".")
    _text_guard_git(tmp_path, "commit", "-qm", "Ausgangsstand")
    return tmp_path


@pytest.mark.parametrize("staged_translation", [False, True])
def test_the_commit_guard_uses_staged_translations_only(
    text_guard_repo: Path, staged_translation: bool
) -> None:
    """Ungestagte Übersetzungen verdecken keinen Fehler und erzeugen keinen falschen."""
    from tools import check_new_texts

    root = text_guard_repo
    source = root / "app" / "message.py"
    source.write_text(source.read_text(encoding="utf-8") + 'tr("Neuer Text")\n', encoding="utf-8")
    _text_guard_git(root, "add", "app/message.py")
    catalog = root / "app" / "i18n" / "locales" / "en.json"
    catalog.write_text(json.dumps({"Neuer Text": "New text"}), encoding="utf-8")
    if staged_translation:
        _text_guard_git(root, "add", "app/i18n/locales/en.json")
        catalog.write_text("{}\n", encoding="utf-8")

    assert check_new_texts.added_texts() == ["Neuer Text"]
    assert check_new_texts.main() == (0 if staged_translation else 1)


@pytest.mark.parametrize("staged_catalog", [False, True])
def test_the_commit_guard_takes_its_language_list_from_the_index(
    text_guard_repo: Path, staged_catalog: bool
) -> None:
    """Ein neuer Indexkatalog wird geprüft, ein nur lokaler Katalog bleibt draußen."""
    from tools import check_new_texts

    root = text_guard_repo
    catalog = root / "app" / "i18n" / "locales" / "fr.json"
    catalog.write_text("{}\n", encoding="utf-8")
    if staged_catalog:
        _text_guard_git(root, "add", "app/i18n/locales/fr.json")
        catalog.unlink()

    gaps = check_new_texts.missing(["Neuer Text"])

    assert gaps == {
        language: ["Neuer Text"] for language in (["en", "fr"] if staged_catalog else ["en"])
    }


def test_the_commit_guard_fails_without_any_catalog_in_the_index(
    text_guard_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RM-349 (E-N2): Ohne Katalog fehlt nichts — das ist kein bestandener Fall."""
    from tools import check_new_texts

    root = text_guard_repo
    _text_guard_git(root, "rm", "-q", "--cached", "app/i18n/locales/en.json")
    source = root / "app" / "message.py"
    source.write_text(source.read_text(encoding="utf-8") + 'tr("Neuer Text")\n', encoding="utf-8")
    _text_guard_git(root, "add", "app/message.py")

    with pytest.raises(check_new_texts.NoCatalogError):
        check_new_texts.missing(["Neuer Text"])
    assert check_new_texts.main() == 1
    assert "kein Katalog" in capsys.readouterr().out


@pytest.mark.parametrize("new_text", [False, True])
def test_the_commit_guard_compares_both_names_of_a_renamed_source(
    text_guard_repo: Path, new_text: bool
) -> None:
    """Nur neue Texte einer Umbenennung zählen, auch bei Umlaut und Leerraum im Pfad."""
    from tools import check_new_texts

    root = text_guard_repo
    destination = "tools/ Neuer Name ö.py"
    (root / "tools").mkdir()
    _text_guard_git(root, "mv", "app/message.py", destination)
    if new_text:
        path = root / destination
        path.write_text(path.read_text(encoding="utf-8") + 'tr("Neuer Text")\n', encoding="utf-8")
        _text_guard_git(root, "add", destination)
    # Die Erkennung gehört dem Wächter, nicht einer persönlichen Git-Einstellung.
    _text_guard_git(root, "config", "diff.renames", "false")

    assert check_new_texts.added_texts() == (["Neuer Text"] if new_text else [])
    assert check_new_texts.main() == int(new_text)


def test_the_commit_guard_stops_at_a_staged_file_it_cannot_read(
    text_guard_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine gestagte Fassung, die Python nicht liest, hält den Commit an.

    ``bbd41ff2d`` ging mit einer ``panels.py`` durch, deren Einrückung
    verschoben war: Der Wächter las die gestagte Fassung, ``ast.parse``
    scheiterte, und die Datei galt als textlos — ihre sechs neuen Texte prüfte
    niemand, und jeder Import der Datei scheiterte am HEAD. Der Kopf des Hooks
    verspricht, dass eine nicht auswertbare Prüfung anhält.
    """
    from tools import check_new_texts

    root = text_guard_repo
    source = root / "app" / "message.py"
    before = source.read_text(encoding="utf-8")
    source.write_text(before + 'def f():\nreturn tr("Neuer Text")\n', encoding="utf-8")
    _text_guard_git(root, "add", "app/message.py")
    broken = len(before.splitlines()) + 2  # die Zeile ohne Einrückung unter ``def``

    assert check_new_texts.main() == 2
    said = capsys.readouterr().out
    assert "app/message.py" in said and f"Zeile {broken}" in said, said


def _commit_hook_with(
    tmp_path: Path,
    *,
    language_exit: int = 0,
    language_output: str = "1 passed",
    catalog_exit: int = 0,
    staged_paths: tuple[str, ...] = ("app/ui/owned.py",),
    source_paths: tuple[str, ...] = ("app/ui/foreign.py",),
    git_exit: int = 0,
    have_interpreter: bool = True,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    """Den echten Hook mit Git- und Interpreter-Doubles durch Bash ausführen.

    Das Interpreter-Doppel protokolliert jeden Auftrag, startet aber weder
    pytest noch Qt. Die Index-/AST-Prüfung selbst hat ihre Gegenproben unten;
    hier zählt, wann der Hook sie aufruft und welchen Ausgang er übernimmt.
    """
    from tests.helpers import bash_executable

    bash = bash_executable()
    if bash is None:
        pytest.skip("ohne Bash lässt sich der echte Commit-Hook nicht ausführen")
    for relative in {*staged_paths, *source_paths}:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "staged.bin").write_bytes(
        b"".join(path.encode("utf-8") + b"\0" for path in staged_paths)
    )
    (tmp_path / "staged.txt").write_text("\n".join(staged_paths), encoding="utf-8")
    interpreter = tmp_path / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$HOOK_ROOT/calls.txt"
case "${1:-}" in
  -m)
    printf '%s\\n' "$HOOK_LANGUAGE_OUTPUT"
    exit "$HOOK_LANGUAGE_EXIT" ;;
  tools/check_new_texts.py)
    if [ "$HOOK_CATALOG_EXIT" -ne 0 ]; then
      printf '%s\\n' 'en: 1 neue Texte ohne Übersetzung, z. B. Eigener neuer Text'
    fi
    exit "$HOOK_CATALOG_EXIT" ;;
  *) printf '%s\\n' 'Unerwarteter Interpreterauftrag' >&2; exit 91 ;;
esac
""",
        encoding="utf-8",
        newline="\n",
    )
    interpreter.chmod(0o755)
    if not have_interpreter:
        interpreter.unlink()
    runner = tmp_path / "run-hook.sh"
    runner.write_text(
        """git() {
  case "$1" in
    diff)
      [ "$HOOK_GIT_EXIT" -eq 0 ] || return "$HOOK_GIT_EXIT"
      case " $* " in
        *' -z '*) cat "$HOOK_ROOT/staged.bin" ;;
        *) cat "$HOOK_ROOT/staged.txt" ;;
      esac ;;
    rev-parse) printf '%s/.git\\n' "$HOOK_ROOT" ;;
    *) printf '%s\\n' 'Unerwarteter Git-Auftrag' >&2; return 92 ;;
  esac
}
source "$HOOK_FILE"
""",
        encoding="utf-8",
        newline="\n",
    )
    environment = dict(os.environ)
    environment.pop("SOLIDON_KEIN_TOR", None)
    environment.update(
        HOOK_ROOT=tmp_path.as_posix(),
        HOOK_FILE=(Path(__file__).resolve().parents[1] / ".githooks" / "pre-commit").as_posix(),
        HOOK_LANGUAGE_EXIT=str(language_exit),
        HOOK_LANGUAGE_OUTPUT=language_output,
        HOOK_CATALOG_EXIT=str(catalog_exit),
        HOOK_GIT_EXIT=str(git_exit),
    )
    result = subprocess.run(
        [str(bash), str(runner)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=tmp_path,
        timeout=20,
    )
    call_log = tmp_path / "calls.txt"
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    return result, [call.split() for call in calls]


def test_the_commit_hook_checks_new_catalog_texts_after_clean_core_language_tests(
    tmp_path: Path,
) -> None:
    """Grüne Bezeichner überspringen keine Katalogprüfung und starten keine Fensterdatei."""
    result, calls = _commit_hook_with(tmp_path)

    assert result.returncode == 0, result.stderr
    assert [argument for call in calls for argument in call if argument.startswith("tests/")] == [
        "tests/test_language_rules.py"
    ]
    assert calls[-1] == ["tools/check_new_texts.py"]


@pytest.mark.parametrize("foreign_language_failure", [False, True])
def test_the_commit_hook_stops_for_its_own_new_catalog_gap(
    tmp_path: Path, foreign_language_failure: bool
) -> None:
    """Eine eigene Kataloglücke blockiert sowohl bei grünen als auch fremden roten Bezeichnern."""
    result, calls = _commit_hook_with(
        tmp_path,
        language_exit=int(foreign_language_failure),
        language_output=(
            "FAILED tests/test_language_rules.py::test_identifiers_are_english[app/ui/foreign.py]"
            if foreign_language_failure
            else "1 passed"
        ),
        catalog_exit=1,
    )

    assert result.returncode == 1, result.stderr
    assert calls[-1] == ["tools/check_new_texts.py"]
    assert "Eigener neuer Text" in result.stderr


@pytest.mark.parametrize(
    "failed_file, expected_exit", [("app/ui/owned.py", 1), ("app/ui/foreign.py", 0)]
)
def test_the_commit_hook_attributes_only_failed_language_files(
    tmp_path: Path, failed_file: str, expected_exit: int
) -> None:
    """Ein grüner gestagter Dateiname macht einen fremden Befund nicht zum eigenen."""
    result, calls = _commit_hook_with(
        tmp_path,
        language_exit=1,
        language_output=(
            "tests/test_language_rules.py::test_identifiers_are_english[app/ui/owned.py] PASSED\n"
            f"FAILED tests/test_language_rules.py::test_identifiers_are_english[{failed_file}]"
        ),
    )

    assert result.returncode == expected_exit, result.stderr
    assert calls[-1] == ["tools/check_new_texts.py"]


@pytest.mark.parametrize("language_exit", [2, 3, 4, 5, 127, 139])
def test_the_commit_hook_stops_when_the_language_runner_fails(
    tmp_path: Path, language_exit: int
) -> None:
    """Unterbrechung, Sammelfehler, Konfiguration und Prozessabsturz sind keine fremden Befunde."""
    result, _calls = _commit_hook_with(
        tmp_path, language_exit=language_exit, language_output="ERROR: pytest konnte nicht prüfen"
    )

    assert result.returncode == 1, result.stderr
    assert "ERROR: pytest konnte nicht prüfen" in result.stderr


@pytest.mark.parametrize(
    "language_output",
    [
        "",
        "E ValueError: keine verwertbare Zusammenfassung",
        "FAILED tests/test_language_rules.py::test_module_names_are_english",
        "FAILED tests/test_language_rules.py::test_identifiers_are_english[foreign.py]",
        "FAILED tests/test_language_rules.py::test_identifiers_are_english[app/ui/missing.py]",
        "FAILED tests/test_language_rules.py::test_identifiers_are_english[app/ui/foreign.py]\n"
        "ERROR tests/test_language_rules.py::test_module_names_are_english - setup failed",
        "FAILED tests/test_language_rules.py::test_identifiers_are_english[app/ui/foreign.py]\n"
        "FAILED tests/test_language_rules.py::test_module_names_are_english",
    ],
)
def test_the_commit_hook_stops_for_unattributable_language_results(
    tmp_path: Path, language_output: str
) -> None:
    """Nur ausschließlich zuordenbare fremde Fehler dürfen einen roten Lauf passieren lassen."""
    result, _calls = _commit_hook_with(tmp_path, language_exit=1, language_output=language_output)

    assert result.returncode == 1, result.stderr


@pytest.mark.parametrize(
    "staged_path, failed_path",
    [
        ("app/ui/owned.py", "app/ui/not_owned.py"),
        ("app/ui/owned.py", "app/core/owned.py"),
        ("tools/owned.py", "app/ui/owned.py"),
        ("app/ui/with space.py", "app/core/with space.py"),
    ],
)
def test_the_commit_hook_compares_the_entire_failed_path(
    tmp_path: Path, staged_path: str, failed_path: str
) -> None:
    """Weder derselbe Dateiname noch ein Namenssuffix gehört automatisch zum Commit."""
    result, calls = _commit_hook_with(
        tmp_path,
        staged_paths=(staged_path,),
        source_paths=(failed_path,),
        language_exit=1,
        language_output=(
            f"FAILED tests/test_language_rules.py::test_identifiers_are_english[{failed_path}]"
            " - AssertionError: Bezeichner"
        ),
    )

    assert result.returncode == 0, result.stderr
    assert calls[-1] == ["tools/check_new_texts.py"]


@pytest.mark.parametrize("staged_path", ["app/ui/with space.py", "app/ui/ö.py"])
def test_the_commit_hook_keeps_non_ascii_and_space_paths_as_one_name(
    tmp_path: Path, staged_path: str
) -> None:
    """Git liefert unveränderte NUL-Pfade; pytest kann Umlaute in Parameter-IDs maskieren."""
    pytest_path = staged_path.encode("unicode_escape").decode("ascii")
    result, _calls = _commit_hook_with(
        tmp_path,
        staged_paths=("README.md", staged_path),
        language_exit=1,
        language_output=(
            f"FAILED tests/test_language_rules.py::test_identifiers_are_english[{pytest_path}]"
        ),
    )

    assert result.returncode == 1, result.stderr


def test_the_commit_hook_stops_when_the_text_guard_cannot_read_a_staged_file(
    tmp_path: Path,
) -> None:
    """Rückgabe 2 des Textwächters ist eine nicht auswertbare Prüfung, kein Kataloglückenbefund."""
    result, _calls = _commit_hook_with(tmp_path, catalog_exit=2)

    assert result.returncode == 1, result.stderr
    assert "ABGEBROCHEN" in result.stderr, result.stderr
    assert "Die Textprüfung konnte eine gestagte Datei nicht lesen." in result.stderr
    assert "[neue Texte ohne Übersetzung]" not in result.stderr


@pytest.mark.parametrize("git_exit, have_interpreter", [(128, True), (0, False)])
def test_the_commit_hook_stops_if_its_prerequisites_are_unavailable(
    tmp_path: Path, git_exit: int, have_interpreter: bool
) -> None:
    """Ohne Index oder Projektinterpreter kann kein sauberer Commit nachgewiesen werden."""
    result, calls = _commit_hook_with(
        tmp_path, git_exit=git_exit, have_interpreter=have_interpreter
    )

    assert result.returncode == 1, result.stderr
    assert not calls


def _guard_with(monkeypatch: pytest.MonkeyPatch, *, before: str, after: str) -> list[str]:
    """Den Wächter über zwei erfundene Fassungen einer Datei laufen lassen.

    Attrappiert wird genau das, was er von git will: die Liste der gestagten
    Dateien und je Fassung ihr Quelltext.
    """
    from types import SimpleNamespace

    from tools import check_new_texts

    def fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        if args[1] == "diff":
            return SimpleNamespace(stdout="M\0app/ui/panels.py\0", returncode=0)
        return SimpleNamespace(stdout=before if args[2].startswith("HEAD") else after, returncode=0)

    monkeypatch.setattr(check_new_texts.subprocess, "run", fake_run)
    return check_new_texts.added_texts()


def test_the_commit_guard_reads_escapes_like_python_and_keeps_the_umlauts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R18: ``text.encode().decode("unicode_escape")`` las die UTF-8-Bytes eines
    Umlauts als einzelne Codepunkte, sobald daneben eine Escape-Folge stand —
    aus „Wählen" wurde „WÃ¤hlen", und die vorhandene Übersetzung galt als
    fehlend. Der Wächter hielt damit korrekt übersetzte Commits an."""
    neu = _guard_with(
        monkeypatch,
        before="x = 1\n",
        after='tr("Wählen Sie eine Datei.\\nErneut versuchen.")\n_("Gerade")\n',
    )

    assert neu == ["Gerade", "Wählen Sie eine Datei.\nErneut versuchen."]


def test_the_commit_guard_sees_a_text_that_runs_over_several_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Fall vom 10.09.2026 — und der teuerste, den dieser Wächter kennt.

    Ein Commit formulierte drei Absagen um, jede über vier Zeilen implizit
    zusammengesetzt. Der Wächter las die ``+``-Zeilen **einzeln**, fand in 1068
    Zeilen genau einen Text (den einzigen einzeiligen) und ließ den Commit
    durch; die Übersetzungsprüfung stand danach für jeden rot, der das Tor
    fuhr. Blind war er ausgerechnet für die langen, erklärenden Sätze.

    Der zweite Text hier ist die Gegenprobe zur naheliegenden Reparatur: Wer
    stattdessen den Diff über mehrere Zeilen absucht, findet bei einer
    geänderten Schlusszeile ein **Bruchstück** — und ein Bruchstück steht in
    keinem Katalog, also hielte er an, ohne dass etwas fehlt. Gelesen wird
    deshalb die Datei und nicht der Diff.
    """
    lang = (
        "tr(\n"
        '    "Ein Gewinde ist eine Wendelfläche und trägt kein "\n'
        '    "einzelnes Maß, das sich ändern ließe."\n'
        ")\n"
    )
    unveraendert = '_("Diesen Schritt ändern")\n'

    neu = _guard_with(monkeypatch, before=unveraendert, after=unveraendert + lang)

    assert neu == [
        "Ein Gewinde ist eine Wendelfläche und trägt kein einzelnes Maß, das sich ändern ließe."
    ], "der zusammengesetzte Text zählt als einer, und der unveränderte gehört nicht dazu"


def test_the_commit_guard_reads_a_text_with_context_under_its_catalog_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Text mit ``context=`` steht im Katalog als ``Kontext\\x04Text``.

    Durchsicht 0.5.1: Die Kundenwörter der Befehlspalette tragen den Kontext
    „Suchwörter“. Der Wächter suchte sie ohne ihn — „Ball“ statt
    „Suchwörter\\x04Ball“ —, fand sie in keinem Katalog und hielt einen
    vollständig übersetzten Commit an. Gefragt wird der Schlüssel, unter dem
    ``TranslatableText`` nachschlägt; ohne Kontext bleibt es der Text selbst.
    """
    neu = _guard_with(
        monkeypatch,
        before="x = 1\n",
        after='_("Ball", context="Suchwörter")\ntr("Nach oben", context="Verlauf")\n_("Gerade")\n',
    )

    assert neu == ["Gerade", "Suchwörter\x04Ball", "Verlauf\x04Nach oben"]


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


def test_notice_cli_explains_a_missing_sbom_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools import make_licence_notices

    monkeypatch.setattr(
        sys, "argv", ["make_licence_notices", "--sbom", str(tmp_path / "missing.json")]
    )
    assert make_licence_notices.main() == 1
    message = capsys.readouterr().out
    assert "prüfen" in message and "Traceback" not in message


@pytest.mark.parametrize("problem_type", [OSError, zipfile.BadZipFile])
def test_signing_cli_explains_file_errors_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    problem_type: type[Exception],
) -> None:
    from tools import sign_release

    def fail(**_kwargs: object) -> None:
        raise problem_type("broken input")

    monkeypatch.setattr(sign_release, "sign_application", fail)
    assert sign_release.main(["--phase", "application", "--run", "123", "--subject", "test"]) == 1
    message = capsys.readouterr().out
    assert "prüfen" in message and "Traceback" not in message


def test_sbom_cli_explains_an_unwritable_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools import make_sbom

    parent = tmp_path / "file-instead-of-directory"
    parent.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(make_sbom, "build_bom", lambda: {"components": []})
    monkeypatch.setattr(sys, "argv", ["make_sbom", "--output", str(parent / "bom.json")])
    assert make_sbom.main() == 2
    message = capsys.readouterr().err
    assert "prüfen" in message and "Traceback" not in message
    assert parent.read_text(encoding="utf-8") == "existing"


def test_operator_cli_explains_a_missing_display(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from types import SimpleNamespace

    from tools import licence_admin

    class DisplayError(Exception):
        pass

    def fail() -> None:
        raise DisplayError("no display")

    monkeypatch.setitem(sys.modules, "tkinter", SimpleNamespace(Tk=fail, TclError=DisplayError))
    assert licence_admin.main([]) == 1
    message = capsys.readouterr().out
    assert "Bildschirm" in message and "starten" in message


def test_delivery_matrix_resumes_only_a_matching_well_formed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    model = tmp_path / "plate.stl"
    output = tmp_path / "matrix"
    script = root / "tools" / "matrix_unit.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(root), str(model), str(output), "heim"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    specification = importlib.util.spec_from_file_location("delivery_matrix_unit", script)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    identity = {
        "code_sha256": "code",
        "plan": "modelle",
        "spec": "heim",
        "model": str(model.resolve()),
        "model_sha256": "model",
    }
    combos = [
        {"slicer": slicer, "printer": printer, "complete": True, "skip": "not part of this probe"}
        for slicer, printer in module.combos("heim")
    ]
    previous = {
        "code": str(root),
        "model": str(model.resolve()),
        "spec": "heim",
        "_matrix_run": identity,
        "combos": combos,
    }

    assert module._can_resume_result(previous, identity)
    assert not module._can_resume_result(previous, None)
    assert not module._can_resume_result({**previous, "_matrix_run": {"plan": "anderer"}}, identity)
    assert not module._can_resume_result({**previous, "load_error": "OSError"}, identity)
    assert not module._can_resume_result(
        {**previous, "combos": [{key: value for key, value in combos[0].items() if key != "skip"}]},
        identity,
    )
    assert not module._can_resume_result(
        {**previous, "combos": [{**combos[0], "skip": ["not a text result"]}]}, identity
    )
    assert not module._can_resume_result({**previous, "combos": [*combos, combos[0]]}, identity)
    assert not module._can_resume_result(
        {**previous, "combos": [*combos, {"slicer": "fremd", "printer": "x", "complete": True}]},
        identity,
    )
    assert not module._can_resume_result([previous], identity)


def test_delivery_matrix_report_excludes_legacy_and_mismatched_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "matrix_report.py"
    folder = tmp_path / "matrix"
    nested = folder / "plate-a1b2c3d4"
    nested.mkdir(parents=True)
    identity = {
        "code_root": str(root),
        "code_sha256": "code",
        "plan": "modelle",
        "expected_combos": {"heim": [["orca", "anycubic-kobra-2"]]},
        "models": [{"path": "plate.stl", "sha256": "model", "spec": "heim"}],
    }
    (folder / ".matrix-identity").write_text(json.dumps(identity), encoding="utf-8")
    marker: dict[str, object] = {
        "run_sha256": "",
        "code_sha256": "code",
        "plan": "modelle",
        "spec": "heim",
        "model": "plate.stl",
        "model_sha256": "model",
    }
    specification = importlib.util.spec_from_file_location("delivery_matrix_report", script)
    assert specification is not None and specification.loader is not None
    report = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(report)
    marker["run_sha256"] = report.identity_hash(identity)
    (folder / ".matrix-status").write_text(
        json.dumps({"run_sha256": marker["run_sha256"], "status": "complete"}),
        encoding="utf-8",
    )
    result = {
        "model": marker["model"],
        "code": str(root),
        "spec": "heim",
        "done": True,
        "_matrix_run": marker,
        "combos": [
            {
                "slicer": "orca",
                "printer": "anycubic-kobra-2",
                "complete": True,
                "variants": {"standard": [{"ok": True, "flags": []}]},
            }
        ],
    }
    (nested / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (folder / "legacy.json").write_text(json.dumps(result), encoding="utf-8")
    foreign_folder = folder / "foreign"
    foreign_folder.mkdir()
    foreign = {**result, "_matrix_run": {**marker, "run_sha256": "old"}}
    (foreign_folder / "result.json").write_text(json.dumps(foreign), encoding="utf-8")

    malformed = {
        **identity,
        "expected_combos": {"heim": [["orca", ["nested"]]]},
    }
    assert not report.belongs_to_run(
        {
            **result,
            "_matrix_run": {
                **marker,
                "run_sha256": report.identity_hash(malformed),
            },
        },
        malformed,
    )
    changed_model = {**result, "_matrix_run": {**marker, "model_sha256": "changed"}}
    assert not report.belongs_to_run(changed_model, identity)
    monkeypatch.setattr(sys, "argv", [str(script), str(folder)])
    assert report.main() == 0
    output = capsys.readouterr().out
    assert "1 Modelle gelesen, 1 vollständig." in output
    assert "2 Ergebnisdateien mit fehlerhafter oder fremder Laufkennung ausgelassen." in output
    (folder / ".matrix-status").write_text(
        json.dumps({"run_sha256": marker["run_sha256"], "status": "failed"}),
        encoding="utf-8",
    )
    assert report.main() == 0
    output = capsys.readouterr().out
    assert "0 Modelle gelesen, 0 vollständig." in output
    assert "1 Matrixläufe nicht abgeschlossen" in output

    (folder / ".matrix-status").write_text(
        json.dumps({"run_sha256": marker["run_sha256"], "status": "complete"}),
        encoding="utf-8",
    )
    incomplete = {**result, "done": False}
    (nested / "result.json").write_text(json.dumps(incomplete), encoding="utf-8")
    assert not report.belongs_to_run(incomplete, identity)
    assert report.main() == 0
    output = capsys.readouterr().out
    assert "0 Modelle gelesen, 0 vollständig." in output
    assert "1 Matrixläufe nicht abgeschlossen" in output

    (nested / "result.json").unlink()
    assert report.main() == 0
    output = capsys.readouterr().out
    assert "0 Modelle gelesen, 0 vollständig." in output
    assert "1 Matrixläufe nicht abgeschlossen" in output


def test_delivery_matrix_seal_requires_each_expected_combo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "matrix_driver.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(root), str(tmp_path / "matrix"), "modelle"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    specification = importlib.util.spec_from_file_location("delivery_matrix_driver", script)
    assert specification is not None and specification.loader is not None
    driver = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(driver)

    expected = driver._expected_combos("heim")
    assert len(expected) == len(driver.SLICERS)
    complete = {
        "combos": [
            {"slicer": slicer, "printer": printer, "complete": True, "skip": "probe"}
            for slicer, printer in expected
        ]
    }
    assert len(driver._code_digest(root)) == 64
    assert driver._has_complete_combos(complete, "heim")
    assert not driver._has_complete_combos({"combos": complete["combos"][:-1]}, "heim")
    assert not driver._has_complete_combos(
        {"combos": [*complete["combos"], complete["combos"][0]]}, "heim"
    )
    invalid_terminal = {**complete["combos"][0], "skip": ["probe"]}
    assert not driver._has_complete_combos(
        {"combos": [invalid_terminal, *complete["combos"][1:]]}, "heim"
    )


def test_delivery_matrix_fingerprints_cura_material_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util

    root = tmp_path / "cura-profiles"
    root.mkdir()
    (root / "printer.def.json").write_text("{}", encoding="utf-8")
    (root / "pla.xml.fdm_material").write_text("<fdmmaterial />", encoding="utf-8")
    (root / "readme.xml").write_text("not a profile", encoding="utf-8")

    repo = Path(__file__).resolve().parents[1]
    script = repo / "tools" / "matrix_driver.py"
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "argv", [str(script), str(repo), str(tmp_path / "out"), "modelle"])
    specification = importlib.util.spec_from_file_location("delivery_matrix_profile_files", script)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert [path.name for path in module._profile_files(root)] == [
        "pla.xml.fdm_material",
        "printer.def.json",
    ]


def test_delivery_matrix_requires_boolean_completion_and_binds_worker_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "matrix_driver.py"
    model = tmp_path / "plate.stl"
    model.write_bytes(b"model")
    output = tmp_path / "matrix"
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "argv", [str(script), str(root), str(output), "modelle"])
    specification = importlib.util.spec_from_file_location(
        "delivery_matrix_strict_completion", script
    )
    assert specification is not None and specification.loader is not None
    driver = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(driver)

    identity_seed = {"code_sha256": "code", "plan": "modelle"}
    driver.RUN_IDENTITY = identity_seed
    driver.MODEL_DIGESTS[model.resolve()] = driver._file_digest(model)
    monkeypatch.setattr(driver, "_code_digest", lambda _root: "code-hash")
    monkeypatch.setattr(driver, "_slicer_identity", dict)
    monkeypatch.setattr(driver, "_expected_combos", lambda _spec: [("orca", "printer")])
    planned = [(model, "heim")]
    monkeypatch.setattr(driver, "WORKERS", 2)
    two_workers = driver._run_identity(planned)
    monkeypatch.setattr(driver, "WORKERS", 3)
    three_workers = driver._run_identity(planned)
    assert two_workers["schema"] == 2
    assert two_workers["workers"] == 2
    assert three_workers["workers"] == 3
    assert two_workers != three_workers

    driver.RUN_IDENTITY = two_workers
    driver._expected_combos = lambda _spec: [("orca", "printer")]
    result_path = driver.result_of(model)
    result_path.parent.mkdir(parents=True)
    marker = driver._result_identity(model, "heim")
    result = {
        "done": "false",
        "code": str(root),
        "model": str(model.resolve()),
        "spec": "heim",
        "_matrix_run": marker,
        "combos": [
            {
                "slicer": "orca",
                "printer": "printer",
                "complete": True,
                "skip": "probe",
            }
        ],
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    assert not driver.done(model, "heim")
    assert not driver._seal_result(model, "heim")
    result["done"] = 1
    result_path.write_text(json.dumps(result), encoding="utf-8")
    assert not driver.done(model, "heim")
    assert not driver._seal_result(model, "heim")
