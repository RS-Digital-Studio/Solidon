"""Die Werkzeuge, die etwas wegräumen oder hinausschicken: ``link_memory``
und ``upload_website``.

Beide gegen temporäre Bestände, keines gegen das Repository, das Nutzerprofil
oder einen Server — die Proben des Gesamtreviews vom 05.09.2026 (R19, R21),
als Zusicherung festgehalten.
"""

from __future__ import annotations

import json
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


def _guard_with(monkeypatch: pytest.MonkeyPatch, *, before: str, after: str) -> list[str]:
    """Den Wächter über zwei erfundene Fassungen einer Datei laufen lassen.

    Attrappiert wird genau das, was er von git will: die Liste der gestagten
    Dateien und je Fassung ihr Quelltext.
    """
    from types import SimpleNamespace

    from tools import check_new_texts

    def fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        if args[1] == "diff":
            return SimpleNamespace(stdout="app/ui/panels.py\n", returncode=0)
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

    monkeypatch.setattr(sign_release, "run", fail)
    assert sign_release.main(["--subject", "test"]) == 1
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
