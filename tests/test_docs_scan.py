"""Das Unterlagenwerkzeug an Fällen, deren Ausgang bekannt ist.

`tools/docs_scan.py` misst, was eine Sitzung an Prosa mitliest, bevor sie eine
Zeile Code sieht. Wie jedes Suchwerkzeug hat es die gefährlichste Fehlerart
eines Messwerkzeugs: **es schweigt.** Zu
wenig zu finden sieht aus wie nichts zu finden.

Geprüft wird deshalb an gepflanzten Fällen, dass es findet, wofür es gebaut
wurde — und an zwei Fällen aus dem Bestand, dass es die Fallen kennt, die es
beim ersten Lauf am 18.09.2026 selbst gestellt hat: die Kommentarzeile im
`paths:`-Block, mit der eine Regel begründet, warum ein Pfad dazukam, und der
Verweis auf eine Datei, die zur Laufzeit im Nutzerordner entsteht.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools import docs_scan


def test_maps_ignore_local_copies_but_include_new_unicode_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lokale Kopien verfälschen die Kartenmenge nicht; neue Karten zählen sofort."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/Prüfreste/\n", encoding="utf-8")
    behalten = [tmp_path / "CLAUDE.md", tmp_path / "neuer Bereich ä" / "CLAUDE.md"]
    for pfad in [*behalten, tmp_path / "Prüfreste" / "alt" / "CLAUDE.md"]:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("Karte", encoding="utf-8")
    monkeypatch.setattr(docs_scan, "ROOT", tmp_path)

    assert docs_scan.maps() == sorted(behalten)


def test_an_extracted_tree_does_not_use_its_parent_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch unter einem fremden Git-Baum bleibt ein ausgepackter Quellbaum lesbar."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/extracted/\n", encoding="utf-8")
    root = tmp_path / "extracted"
    root.mkdir()
    karte = root / "CLAUDE.md"
    karte.write_text("Karte", encoding="utf-8")
    monkeypatch.setattr(docs_scan, "ROOT", root)

    assert docs_scan.maps() == [karte]


def test_dead_references_are_not_hidden_by_local_copies_or_other_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein alter Sicherungsbaum und ein gleicher Dateiname heilen keinen falschen Pfad."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/output/\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Regeln", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(
        "`app/removed.py`, `lost.py`, `app/wrong.py`, `core/current.py`, "
        "`current.py`, `guide.md` und `MEMORY.md`.",
        encoding="utf-8",
    )
    for name in (
        "output/removed.py",
        "output/lost.py",
        "tools/wrong.py",
        "app/core/current.py",
        "guide.md",
    ):
        pfad = tmp_path / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text("", encoding="utf-8")
    monkeypatch.setattr(docs_scan, "ROOT", tmp_path)

    docs_scan.report_dead(10)

    ausgabe = capsys.readouterr().out
    for verweis in ("app/removed.py", "lost.py", "app/wrong.py"):
        assert f"nennt `{verweis}`" in ausgabe
    assert "nennt `current.py`" not in ausgabe
    assert "nennt `core/current.py`" not in ausgabe
    assert "nennt `guide.md`" not in ausgabe
    assert "nennt `MEMORY.md`" not in ausgabe
    assert "3 Verweise gehen ins Leere" in ausgabe


def test_a_scope_is_read_past_the_comments_that_explain_it(tmp_path: Path) -> None:
    """Die Muster einer Regel — und die Begründungen dazwischen zählen nicht mit.

    `ansicht.md` trägt zwischen ihren Pfaden vier Kommentarzeilen, die
    erzählen, warum das Renderer-Paket und die 3D-Maus nachgetragen wurden.
    Ein Leser, der sie für Muster hält, misst einen Geltungsbereich, den es
    nicht gibt.
    """
    regel = tmp_path / "beispiel.md"
    regel.write_text(
        '---\ndescription: "eine Regel"\npaths:\n'
        "  # Nachgetragen am 07.09.2026, weil sonst niemand sie sah:\n"
        '  - "app/ui/viewport.py"\n'
        '  - "app/ui/render/**/*.py"\n'
        "---\n\n# Regeln\n\nText.\n",
        encoding="utf-8",
    )

    assert docs_scan.scopes(regel) == ["app/ui/viewport.py", "app/ui/render/**/*.py"]


def test_a_rule_without_a_scope_is_no_error(tmp_path: Path) -> None:
    """Fehlt der Block, ist die Antwort leer — nicht eine Ausnahme."""
    regel = tmp_path / "ohne.md"
    regel.write_text('---\ndescription: "ohne Pfade"\n---\n\n# Regeln\n', encoding="utf-8")

    assert docs_scan.scopes(regel) == []


def test_a_pattern_finds_the_files_it_promises() -> None:
    """Ein Muster aus dem Bestand trifft die Dateien, die es meint."""
    getroffen = docs_scan.matched("app/core/geom/*.py")

    assert (docs_scan.ROOT / "app" / "core" / "geom" / "ops.py") in getroffen
    assert (docs_scan.ROOT / "app" / "ui" / "viewport.py") not in getroffen


def test_a_pattern_that_matches_nothing_says_so() -> None:
    """Ein leerer Geltungsbereich ist ein Fund, kein Absturz.

    `druckteile.md` zeigt auf `3D Drucker/**` — einen Ordner mit eigenem
    Repository, der hier in `.gitignore` steht. Der leere Treffer ist richtig
    und muss trotzdem sichtbar werden.
    """
    assert docs_scan.matched("dieses/verzeichnis/gibt/es/nicht/**/*.py") == set()


def test_only_prose_counts_as_a_paragraph(tmp_path: Path) -> None:
    """Tabellen, Überschriften und Aufzählungen sind keine Absätze.

    Sonst meldete jede zweite Tabellenzeile eine Wiederholung: Zwei Karten,
    die beide `| Datei | Zweck |` schreiben, sagen nichts doppelt.
    """
    unterlage = tmp_path / "karte.md"
    unterlage.write_text(
        "# Überschrift\n\n"
        "| Spalte | Zweite |\n|---|---|\n| a | b |\n\n"
        "- eine Aufzählung, die lang genug wäre, um als Absatz zu zählen, "
        "wenn die Vorschrift sie nicht ausnähme, was sie tut\n\n"
        "Dies ist ein wirklicher Absatz aus Fließtext, und er ist lang genug, "
        "dass die Vorschrift ihn zählt und nicht als Redewendung verwirft.\n",
        encoding="utf-8",
    )

    gefunden = docs_scan.paragraphs(unterlage)

    assert len(gefunden) == 1
    assert gefunden[0].startswith("Dies ist ein wirklicher Absatz")


def test_a_reference_to_source_counts_and_a_runtime_file_does_not() -> None:
    """Die Schärfung vom 18.09.2026, an ihren eigenen Falschalarmen geprüft.

    Beim ersten Lauf meldete die Frage zehn Verweise ins Leere, und alle zehn
    waren richtig: `feedback.json` und `trial.json` entstehen zur Laufzeit im
    Nutzerordner, `fdmprinter.def.json` liegt beim Kunden in seinem Cura.
    """
    treffer = docs_scan.REFERENCE.findall(
        "Die Karte nennt `app/ui/viewport.py` und `kern.md`, dazu `feedback.json` "
        "und `fdmprinter.def.json`."
    )

    assert treffer == ["app/ui/viewport.py", "kern.md"]


def test_the_load_of_a_known_file_carries_its_own_map_and_rules() -> None:
    """Was beim Anfassen einer bekannten Datei mitlädt.

    `app/ui/viewport.py` zieht die Karte seines Verzeichnisses und jede Regel,
    deren Geltungsbereich ihn trifft — das ist der Fall, für den das Werkzeug
    gebaut wurde.
    """
    regeln = {
        regel: set().union(*(docs_scan.matched(muster) for muster in docs_scan.scopes(regel)))
        for regel in docs_scan.rule_files()
    }

    geladen, gewicht = docs_scan.load_for(docs_scan.ROOT / "app" / "ui" / "viewport.py", regeln)
    namen = {pfad.name for pfad in geladen}

    assert "ansicht.md" in namen, "die Ansichtsregeln gelten für den Viewport"
    assert "oberflaeche.md" in namen, "und die allgemeinen Oberflächenregeln zusätzlich"
    assert "AGENTS.md" in namen and "CLAUDE.md" in namen
    assert gewicht > 100, f"nur {gewicht} KB gemessen — liest die Zählung noch die Dateien?"


def test_an_empty_shelf_is_an_error_and_not_a_result() -> None:
    """Die Mindestzählung: unter der Grenze ist der Lauf keine Messung."""
    assert len(docs_scan.documents()) >= docs_scan.FLOOR
