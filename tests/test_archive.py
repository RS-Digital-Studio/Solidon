"""Ein Modell aus einem ZIP-Archiv (Bauplan §16.3, §17.1, §32).

Modellseiten liefern ihre Teile als ZIP. Geprüft wird, was das Auflösen
zusagt: das eine Modell kommt heraus, bei mehreren wird gefragt, und weder
Pfadtricks noch eine Zip-Bombe noch ein Eintrag, der mehr entpackt, als er
ankündigt, kommen durch. Die Archive entstehen hier im Speicher; die
Modelle darin stammen aus dem Referenzkorpus.
"""

from __future__ import annotations

import base64
import io
import json
import struct
import zipfile
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.ingest import archive
from app.core.ingest.loader import MAX_ARCHIVE_ENTRIES, read_model
from app.core.ingest.plan import import_plan

MESHES = Path(__file__).parent / "data" / "meshes"
CUBE = (MESHES / "cube_clean.stl").read_bytes()


def packed(entries: dict[str, bytes], *, method: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Ein Archiv mit genau diesen Einträgen."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=method) as container:
        for name, data in entries.items():
            container.writestr(name, data)
    return buffer.getvalue()


def nobody(question: str, choices: list[str]) -> str:
    raise AssertionError(f"niemand hätte gefragt werden dürfen: {question} {choices}")


def test_a_single_model_comes_out_without_a_question() -> None:
    payload = packed(
        {"Halter/halter.stl": CUBE, "Halter/foto.jpg": b"\xff\xd8", "LIESMICH.txt": b"x"}
    )

    name, data = archive.model_from_archive("halter.zip", payload, nobody)

    assert name == "halter.stl"
    assert data == CUBE
    plan = import_plan("src_1", name, data)
    assert plan.draft.op == "load", "was herauskommt, geht den gewöhnlichen Einleseweg"


def test_several_models_ask_and_the_answer_decides() -> None:
    """Regel 21: bei mehreren Modellen wählt der Kunde, nicht die Reihenfolge."""
    other = (MESHES / "plate_holes.stl").read_bytes()
    payload = packed({"teile/deckel.stl": other, "teile/boden.stl": CUBE, "b/deckel.stl": CUBE})
    asked: list[tuple[str, list[str]]] = []

    def answer(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return "teile/deckel.stl"

    name, data = archive.model_from_archive("set.zip", payload, answer)

    assert asked and asked[0][1] == ["b/deckel.stl", "teile/boden.stl", "teile/deckel.stl"], (
        "gleichnamige Dateien in zwei Ordnern bleiben unterscheidbar"
    )
    assert (name, data) == ("deckel.stl", other)


def test_without_anyone_to_ask_several_models_are_a_refusal_not_the_first() -> None:
    payload = packed({"a.stl": CUBE, "b.stl": CUBE})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("set.zip", payload, None)

    assert raised.value.values["constraint"] == "choices"
    assert "a.stl" in raised.value.values["files"]
    assert raised.value.suggestions


def test_an_answer_that_was_not_offered_is_refused() -> None:
    payload = packed({"a.stl": CUBE, "b.stl": CUBE})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("set.zip", payload, lambda _q, _c: "../../boot.ini")

    assert raised.value.values["constraint"] == "choices"


def test_an_archive_without_a_model_names_the_formats() -> None:
    payload = packed({"anleitung.pdf": b"%PDF", "bild.png": b"\x89PNG"})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("nur-bilder.zip", payload, nobody)

    assert raised.value.values["constraint"] == "no_model"
    assert "STL" in raised.value.values["formats"]
    assert raised.value.suggestions


@pytest.mark.parametrize(
    "trick",
    [
        "../aussen.stl",
        "ordner/../../aussen.stl",
        "/absolut.stl",
        "C:/Windows/wurzel.stl",
        "..\\rueckwaerts.stl",
        "__MACOSX/teile/._halter.stl",
        "teile/._halter.stl",
    ],
)
def test_entries_that_point_out_of_the_archive_are_passed_over(trick: str) -> None:
    """Entpackt wird nichts auf die Platte — ein solcher Name kommt trotzdem nicht in die Wahl."""
    payload = packed({trick: CUBE, "teile/halter.stl": CUBE})

    name, _data = archive.model_from_archive("mit-trick.zip", payload, nobody)

    assert name == "halter.stl", f"{trick} stand zur Wahl oder wurde genommen"


def test_a_zip_bomb_is_refused_before_anything_is_unpacked() -> None:
    """Dieselben Grenzen wie beim 3MF: ein Eintrag, der sich 1000-fach aufbläst."""
    payload = packed({"bombe.stl": b"\x00" * (8 * 1024 * 1024)})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("bombe.zip", payload, nobody)

    assert raised.value.values["constraint"] == "file_too_large"


def test_too_many_entries_are_named_as_a_zip_not_as_a_3mf() -> None:
    payload = packed({f"leer/{index}.txt": b"" for index in range(MAX_ARCHIVE_ENTRIES + 1)})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("viele.zip", payload, nobody)

    assert raised.value.values["constraint"] == "file_too_large"
    assert "3MF" not in str(raised.value.detail), "der Kunde hat ein ZIP abgelegt"


def test_an_entry_that_unpacks_more_than_it_announces_is_refused() -> None:
    """``file_size`` ist eine Angabe des Archivs, kein Beweis."""
    payload = bytearray(packed({"halter.stl": CUBE}, method=zipfile.ZIP_STORED))
    wrong = len(CUBE) - 100
    # Die Größe im lokalen Kopf (Offset 22) und im Zentralverzeichnis
    # (Offset 24 hinter seiner Signatur) kleiner angeben, als der Eintrag ist.
    struct.pack_into("<I", payload, 22, wrong)
    struct.pack_into("<I", payload, 18, wrong)
    central = payload.rfind(b"PK\x01\x02")
    struct.pack_into("<I", payload, central + 20, wrong)
    struct.pack_into("<I", payload, central + 24, wrong)

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("gelogen.zip", bytes(payload), nobody)

    assert raised.value.values["constraint"] in {"unreadable", "file_too_large"}


def test_an_encrypted_model_says_how_to_get_at_it() -> None:
    payload = bytearray(packed({"geheim.stl": CUBE}, method=zipfile.ZIP_STORED))
    # Das Verschlüsselungsbit in lokalem Kopf und Zentralverzeichnis setzen.
    payload[6] |= 0x1
    central = payload.rfind(b"PK\x01\x02")
    payload[central + 8] |= 0x1

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("geheim.zip", bytes(payload), nobody)

    assert raised.value.values["constraint"] == "encrypted"
    assert raised.value.suggestions


def test_something_that_is_no_zip_is_a_sentence_not_a_crash() -> None:
    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("kaputt.zip", b"PK\x03\x04 nur der Anfang", nobody)

    assert raised.value.suggestions


def _gltf(buffer_uri: str) -> bytes:
    """Ein Dreieck als GLTF mit externem Puffer."""
    positions = struct.pack("<9f", 0, 0, 0, 10, 0, 0, 0, 10, 0)
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"uri": buffer_uri, "byteLength": len(positions)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(positions)}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [10, 10, 0],
            }
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    return json.dumps(document).encode("utf-8")


def test_a_gltf_brings_its_buffer_from_the_same_archive() -> None:
    positions = struct.pack("<9f", 0, 0, 0, 10, 0, 0, 0, 10, 0)
    payload = packed(
        {"modell/szene.gltf": _gltf("daten/puffer.bin"), "modell/daten/puffer.bin": positions}
    )

    name, data = archive.model_from_archive("gltf.zip", payload, nobody)

    embedded = json.loads(data)["buffers"][0]["uri"]
    assert name == "szene.gltf"
    assert embedded.startswith("data:")
    assert base64.b64decode(embedded.split(",", 1)[1]) == positions
    assert read_model(data, ".gltf").triangle_count == 1, "das eingebettete Modell liest sich"


@pytest.mark.parametrize(
    ("uri", "constraint"),
    [
        ("../aussen.bin", "absolute_path"),
        ("https://example.invalid/puffer.bin", "scheme"),
        ("fehlt.bin", "missing_file"),
    ],
)
def test_a_gltf_in_an_archive_keeps_the_folder_boundary(uri: str, constraint: str) -> None:
    payload = packed({"modell/szene.gltf": _gltf(uri), "aussen.bin": b"\x00" * 36})

    with pytest.raises(ValidationError) as raised:
        archive.model_from_archive("gltf.zip", payload, nobody)

    assert raised.value.values["constraint"] == constraint


def test_only_the_import_list_names_the_archive() -> None:
    """Ein ZIP ist ein Umschlag, nie eine Projektquelle."""
    from app.core.ingest.plan import MODEL_SUFFIXES

    assert ".zip" in archive.IMPORT_SUFFIXES
    assert ".zip" not in MODEL_SUFFIXES
    assert archive.is_archive("Teile.ZIP")
    assert not archive.is_archive("baugruppe.3mf"), "ein 3MF ist ein ZIP, aber kein Umschlag"
