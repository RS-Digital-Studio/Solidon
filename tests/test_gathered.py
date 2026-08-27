"""Große Sammelwerte im Container (Konzept P16.9, Bauplan §12).

Eine Sculpting-Sitzung mit viertausend Zügen ist ein halbes Megabyte Zahlen in
einer Zeile. Ab einer Grenze wandert so ein Wert in eine eigene Datei im
Container, und im Dokument steht ein Verweis darauf — die Projektdatei bleibt
eine Datei, die man aufmachen und lesen kann.

**Nur beim Speichern und Laden.** Im Arbeitsspeicher ist ein Sammelparameter
immer sein Text. Genau das prüft die erste Hälfte dieser Datei: dass die runde
Reise nichts ändert, was irgendjemand danach sieht.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.geom.sculpt import strokes_to_text
from app.core.scene.gathered import (
    GATHERED_LIMIT,
    GATHERED_PREFIX,
    carry_over,
    externalise,
    gathered_path,
    inline,
    references,
)
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.project import load, new_project, save
from app.core.types import Operation, Stroke


def many_strokes(count: int) -> str:
    """Eine Strichliste, die über die Grenze geht — echte Züge, kein Füllsel."""
    return strokes_to_text(
        [
            Stroke(
                point=(float(index % 40), float(index % 17), float(index % 23)),
                normal=(0.0, 0.0, 1.0),
                radius=4.0,
                strength=0.5,
            )
            for index in range(count)
        ]
    )


def with_strokes(text: str) -> dict:
    """Ein serialisiertes Dokument mit genau einer Formsitzung darin."""
    return {
        "format_version": FORMAT_VERSION,
        "ops": [{"id": 1, "op": "sculpt_strokes", "params": {"strokes": text, "symmetry": "x"}}],
    }


# --- die Grenze -----------------------------------------------------------------


def test_a_small_value_stays_in_the_document() -> None:
    """Bis zur Grenze bleibt der Wert, wo er steht.

    Eine Skizze mit ein paar Kilobyte gehört in die Projektdatei — sie ist
    dort lesbar, und eine zusätzliche Datei je Skizze wäre Aufwand ohne Nutzen.
    """
    data = with_strokes(many_strokes(10))

    payloads = externalise(data, 1)

    assert not payloads
    assert not data["ops"][0]["params"]["strokes"].startswith(GATHERED_PREFIX)


def test_a_large_value_moves_into_its_own_file() -> None:
    """Darüber wandert er hinaus, und im Dokument steht ein Verweis."""
    text = many_strokes(4000)
    assert len(text) > GATHERED_LIMIT, "die Vorlage muss über der Grenze liegen"
    data = with_strokes(text)

    payloads = externalise(data, 1)

    assert list(payloads) == ["gathered_1"]
    assert data["ops"][0]["params"]["strokes"] == f"{GATHERED_PREFIX}gathered_1"
    assert payloads["gathered_1"].decode("utf-8") == text
    assert data["ops"][0]["params"]["symmetry"] == "x", "kleine Werte bleiben unberührt"


def test_the_round_trip_gives_the_text_back() -> None:
    """Was hinausgeht, kommt zurück — sonst wäre die Auslagerung ein
    Datenverlust mit Zwischenschritt.
    """
    text = many_strokes(4000)
    data = with_strokes(text)
    payloads = externalise(data, 1)

    inline(data, payloads)

    assert data["ops"][0]["params"]["strokes"] == text


def test_a_reference_without_content_stops_the_load() -> None:
    """Ein Verweis ohne Inhalt ist kein halbes Dokument, sondern ein kaputtes.

    Die Operation dahinter würde mit dem Text ``source:gathered_3`` rechnen und
    ein leeres Ergebnis liefern, ohne dass irgendwo etwas fehlt — die Sorte
    Fehler, die niemand mit seiner Ursache verbindet.
    """
    data = with_strokes(f"{GATHERED_PREFIX}gathered_9")

    with pytest.raises(ValidationError) as raised:
        inline(data, {})

    assert raised.value.constraint == "missing_gathered"


def test_the_document_says_which_files_it_needs() -> None:
    data = with_strokes(many_strokes(4000))
    externalise(data, 1)

    assert references(data) == {"gathered_1"}


def test_numbers_do_not_collide_with_what_is_already_there() -> None:
    """Zwei Sitzungen in einem Projekt brauchen zwei Dateien."""
    data = {
        "format_version": FORMAT_VERSION,
        "ops": [
            {"id": 1, "op": "sculpt_strokes", "params": {"strokes": many_strokes(4000)}},
            {"id": 2, "op": "sculpt_strokes", "params": {"strokes": many_strokes(4100)}},
        ],
    }

    payloads = externalise(data, 5)

    assert sorted(payloads) == ["gathered_5", "gathered_6"]
    assert data["ops"][0]["params"]["strokes"] != data["ops"][1]["params"]["strokes"]


# --- der Container --------------------------------------------------------------


def test_a_saved_project_keeps_the_big_value_outside(tmp_path: Path) -> None:
    """Der Zweck, an einer echten Datei: Die Strichliste liegt daneben, und
    ``project.json`` bleibt lesbar.
    """
    text = many_strokes(4000)
    project = new_project()
    project.document.ops.append(
        Operation(id=1, op="sculpt_strokes", inputs=(), params={"strokes": text})
    )

    path = save(project, tmp_path / "figur.p3d")

    with zipfile.ZipFile(path) as container:
        names = set(container.namelist())
        assert gathered_path("gathered_1") in names
        written = json.loads(container.read("project.json"))
    assert len(json.dumps(written)) < len(text), "die Zahlenwüste ist nicht mehr darin"
    assert written["ops"][0]["params"]["strokes"].startswith(GATHERED_PREFIX)


def test_the_reopened_project_has_its_strokes_again(tmp_path: Path) -> None:
    """Und im Arbeitsspeicher ist der Wert wieder sein Text.

    Ohne das müsste jede Auswertung, jeder Hash und jeder Vergleich wissen, ob
    der Wert gerade ausgelagert ist — die Auslagerung ist eine Eigenschaft der
    Datei, nicht des Dokuments.
    """
    text = many_strokes(4000)
    project = new_project()
    project.document.ops.append(
        Operation(id=1, op="sculpt_strokes", inputs=(), params={"strokes": text})
    )
    path = save(project, tmp_path / "figur.p3d")

    again = load(path)

    assert again.document.ops[0].params["strokes"] == text


def test_a_small_session_needs_no_extra_file(tmp_path: Path) -> None:
    """Die Gegenprobe — sonst bekäme jede Skizze eine Datei für nichts."""
    project = new_project()
    project.document.ops.append(
        Operation(id=1, op="sculpt_strokes", inputs=(), params={"strokes": many_strokes(10)})
    )

    path = save(project, tmp_path / "klein.p3d")

    with zipfile.ZipFile(path) as container:
        assert not [name for name in container.namelist() if "gathered" in name]


def test_saving_twice_does_not_pile_up_files(tmp_path: Path) -> None:
    """Ein zweites Speichern schreibt denselben Container, nicht einen
    größeren.

    Die Nummer kommt aus den vorhandenen Quellen und nicht aus einem Zähler im
    Dokument — ein Zähler wäre ein Zustand, der beim Rückgängigmachen falsch
    wird.
    """
    project = new_project()
    project.document.ops.append(
        Operation(id=1, op="sculpt_strokes", inputs=(), params={"strokes": many_strokes(4000)})
    )
    path = save(project, tmp_path / "figur.p3d")
    first = path.stat().st_size

    save(load(path), path)

    assert path.stat().st_size == pytest.approx(first, rel=0.05)
    with zipfile.ZipFile(path) as container:
        assert len([name for name in container.namelist() if "gathered" in name]) == 1


# --- die Migration --------------------------------------------------------------


def test_an_older_file_has_nothing_to_carry_over() -> None:
    """7 → 8: Vor Version 8 gab es keine ausgelagerten Werte.

    Der Schritt ist eine Feststellung und keine Umrechnung — und bleibt
    trotzdem eine eigene Funktion, weil die Kette nie zusammengefasst wird.
    """
    data = {"format_version": 7, "ops": [{"id": 1, "op": "drill_hole", "params": {"x": 1.0}}]}

    assert carry_over(dict(data))["ops"][0]["params"] == {"x": 1.0}


def test_an_older_value_that_looks_like_a_reference_is_flagged() -> None:
    """Der einzige Fall, in dem eine alte Datei doch etwas dieser Art enthält.

    Er wäre in Version 8 ein Verweis, und das wäre eine Umdeutung ihrer Daten
    — also hält die Migration an, statt still etwas anderes zu bedeuten.
    """
    data = {
        "format_version": 7,
        "ops": [{"id": 1, "op": "rename_object", "params": {"name": "source:gathered_1"}}],
    }

    with pytest.raises(ValidationError) as raised:
        migrate(data)

    assert raised.value.constraint == "ambiguous_reference"


def test_the_checked_in_seven_still_opens() -> None:
    """Das Regressionsnetz: Die Kette muss von der ersten Version an laufen."""
    project = load(Path(__file__).parent / "data" / "projects" / "example_v7.p3d")

    assert project.document.format_version == FORMAT_VERSION
    assert [entry.op for entry in project.document.ops] == [
        "rename_object",
        "duplicate_object",
    ]
