"""Profile des installierten Slicers finden und zuordnen (Bauplan §29).

Gegen einen nachgebauten Bestand im Temp-Ordner, nicht gegen ein installiertes
Programm: die Suite muss auf einem Bauserver dasselbe Ergebnis liefern wie auf
einem Rechner, auf dem drei Slicer liegen.

Der Aufbau ist der echte, samt der Eigenheiten, die das Bauen gekostet haben —
uneinheitliche Ordnertiefe, geerbte Verträglichkeit, selbst angelegte Profile
ohne ``type``.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import slicer_profiles as sp
from app.core.knowledge import profiles
from app.core.types import PrinterProfile, Profile


def _write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.fixture
def unknown_printers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Eine echte Profilkette einer nicht in Solidon eingebauten Maschine."""
    root = tmp_path / "resources" / "profiles"
    folder = root / "Acme" / "machine"
    _write(
        folder / "base.json",
        {
            "name": "Acme base",
            "instantiation": "false",
            "printable_area": ["10x20", "210x20", "210x170", "110x170", "110x220", "10x220"],
            "printable_height": "240",
            "nozzle_diameter": ["0.6", "0.6"],
            "bed_exclude_area": ["10x20", "30x20", "30x40", "10x40"],
        },
    )
    _write(
        folder / "new.json",
        {
            "name": "Acme Unbekannt 0.6 nozzle",
            "instantiation": "true",
            "type": "machine",
            "printer_model": "Acme Unbekannt",
            "inherits": "Acme base",
        },
    )
    monkeypatch.setattr(sp, "install_root", lambda _executable: root)
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    return root


def test_discovery_imports_unknown_printer_geometry_and_source_nozzle(
    unknown_printers: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import build_area

    def forbidden_write(*_args, **_kwargs):
        pytest.fail("Die Erhebung darf kein Profil speichern")

    monkeypatch.setattr(profiles, "save_printer", forbidden_write)
    found = sp.discover_printers(unknown_printers / "slicer.exe", "orca")
    assert len(found) == 1
    printer = found[0]
    assert printer.id.startswith("slicer-orca-")
    assert printer.title == "Acme Unbekannt 0.6 nozzle"
    assert printer.build_volume == pytest.approx((200, 200, 240))
    assert printer.nozzle_diameter == pytest.approx(0.6)
    assert printer.nozzles == 2
    assert printer.printable_area[0] == pytest.approx((-100, -100))
    assert build_area.printable_area(printer).area == pytest.approx(35000 - 400)
    assert printer.vendor == "Acme"
    # Die Kontur beginnt bei (10, 20), nicht an der Ecke: Der Nullpunkt der
    # Maschine liegt 110 mm links und 120 mm vor der Bettmitte (RM-424).
    assert printer.bed_origin == pytest.approx((-110.0, -120.0))
    assert build_area.machine_shift(printer) == pytest.approx((110.0, 120.0))


@pytest.mark.parametrize(
    ("area", "origin"),
    [
        # Dremel 3D45 in OrcaSlicer und ElegooSlicer: links weiter als rechts.
        (["-127.5x-77.5", "97.5x-77.5", "97.5x77.5", "-127.5x77.5"], (15.0, 0.0)),
        # Flashforge Guider 2s, die Deltas: das Bett um den Ursprung.
        (["-140x-125", "140x-125", "140x125", "-140x125"], (0.0, 0.0)),
        # Das übliche Bett ab der Ecke behält sein Verhalten ohne Angabe.
        (["0x0", "220x0", "220x220", "0x220"], None),
    ],
)
def test_discovery_keeps_where_the_machine_has_its_origin(
    unknown_printers: Path, area: list[str], origin: tuple[float, float] | None
) -> None:
    """RM-424: ``discover_printers`` zentrierte die Kontur und verlor dabei den
    Ursprung — die Übergabe legte einen Würfel für den Dremel 3D45 auf
    (112,5 / 77,5), am hinteren Rand eines Betts von -127,5 bis 97,5."""
    from app.core import build_area

    base = unknown_printers / "Acme" / "machine" / "base.json"
    document = json.loads(base.read_text(encoding="utf-8"))
    document["printable_area"] = area
    document.pop("bed_exclude_area")
    _write(base, document)
    printer = sp.discover_printers(unknown_printers / "slicer.exe", "orca")[0]

    xs = [float(point.split("x")[0]) for point in area]
    ys = [float(point.split("x")[1]) for point in area]
    width, depth = max(xs) - min(xs), max(ys) - min(ys)
    assert printer.build_volume[:2] == pytest.approx((width, depth))
    assert printer.printable_area[0] == pytest.approx((-width / 2.0, -depth / 2.0))
    if origin is None:
        assert printer.bed_origin is None
    else:
        assert printer.bed_origin == pytest.approx(origin)
    # Solidons Bettmitte liegt in Maschinenkoordinaten in der Mitte der Kontur.
    assert build_area.machine_shift(printer) == pytest.approx(
        ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    )


@pytest.mark.parametrize(
    "change",
    [
        {"printable_height": "nan"},
        {"nozzle_diameter": []},
        {"nozzle_diameter": [True]},
        {"printable_area": ["0x0", "10x10", "0x10", "10x0"]},
        {"printable_area": ["0x0", "infx0", "0x10"]},
        # Eine Zahl statt einer Zeichenkette lädt auch die Orca-Familie nicht
        # (``parse_str_arr``: „should not happen“).
        {"bed_exclude_area": [True]},
        # Das erste Rechteck sperrt das ganze Bett, wie OrcaSlicers Kobra 3.
        {"bed_exclude_area": ["0x0", "300x0", "300x300", "0x300", "0x0", "2x2", "2x298"]},
        {"inherits": "fehlende Basis"},
        {"inherits": "Acme Unbekannt 0.6 nozzle"},
        {"printer_technology": "SLA"},
    ],
)
def test_discovery_never_substitutes_invalid_machine_dimensions(
    unknown_printers: Path,
    change: dict[str, object],
) -> None:
    path = unknown_printers / "Acme" / "machine" / "base.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content.update(change)
    _write(path, content)
    assert sp.discover_printers(unknown_printers / "slicer.exe", "orca") == ()


@pytest.mark.parametrize(
    ("missing", "volume", "nozzle"),
    [
        # Orcas M3D Enabler D8500 nennt keine Druckhöhe.
        ("printable_height", (200, 200, 100), 0.6),
        ("nozzle_diameter", (200, 200, 240), 0.4),
        ("printable_area", (200, 200, 240), 0.6),
    ],
)
def test_orca_discovery_takes_the_slicers_own_default_for_a_missing_key(
    unknown_printers: Path, missing: str, volume: tuple[float, ...], nozzle: float
) -> None:
    """Nennt die Kette einen Maschinenschlüssel gar nicht, rechnet der Slicer mit
    seiner eingebauten Vorgabe (``set_default_value`` in ``PrintConfig.cpp``,
    in allen fünf Orca-Programmen gleich), und Solidon auch (Entscheidung
    Robert, 05.10.2026). Ein vorhandener, unbrauchbarer Wert bleibt eine Absage
    (der Test darüber)."""
    base = unknown_printers / "Acme" / "machine" / "base.json"
    document = json.loads(base.read_text(encoding="utf-8"))
    document.pop(missing)
    if missing == "printable_area":
        document.pop("bed_exclude_area")
    _write(base, document)

    printer = sp.discover_printers(unknown_printers / "slicer.exe", "orca")[0]

    assert printer.build_volume == pytest.approx(volume)
    assert printer.nozzle_diameter == pytest.approx(nozzle)


def test_prusa_discovery_takes_the_slicers_own_default_for_a_missing_key(
    prusa_mini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PrusaSlicers Creality CR-20 nennt kein Bett, Anycubics i3 Mega keine Düse;
    PrusaSlicer rechnet dann mit 200 × 200 × 200 mm und 0,4 mm (``--save``,
    ebenso SuperSlicer). Die Vorlage hier nennt weder Bett noch Höhe."""
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])

    found = sp.discover_printers(prusa_mini, "prusa")

    assert len(found) == 2
    for printer in found:
        assert printer.build_volume == pytest.approx((200, 200, 200))
        assert printer.nozzle_diameter == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("area", "boxes"),
    [
        # Anycubic Kobra 3 in Anycubic Slicer Next: ein Rand von 2,5 mm an jeder Seite.
        (
            [
                *("10x20", "12.5x20", "12.5x220", "10x220"),
                *("10x220", "210x220", "210x217.5", "10x217.5"),
                *("210x220", "207.5x220", "207.5x20", "210x20"),
                *("10x20", "10x22.5", "210x22.5", "210x20"),
            ],
            [
                (10, 20, 12.5, 220),
                (10, 217.5, 210, 220),
                (207.5, 20, 210, 220),
                (10, 20, 210, 22.5),
            ],
        ),
        # Qidi Q1 Pro: zwei Rechtecke und ein überzähliger Punkt, den der Slicer übergeht.
        (
            [
                *("25x210", "25x205", "115x205", "115x210"),
                *("180x210", "180x205", "200x205", "200x210", "180x210"),
            ],
            [(25, 205, 115, 210), (180, 205, 200, 210)],
        ),
        # Qidi Q2: alle Punkte in einem Listeneintrag. Orca hängt die Einträge
        # einer Punktliste mit Komma aneinander (``ConfigBase::load_from_json``).
        (["10x20,21x20,21x36,10x36"], [(10, 20, 21, 36)]),
        # Anycubic Kobra 3 Max: Rechtecke ohne Fläche füllen die Liste und sperren nichts.
        (
            ["10x20", "13x20", "13x220", "10x220", "10x20", "210x20", "210x20", "10x20"],
            [(10, 20, 13, 220)],
        ),
        # Orcas Vorgabe für „keine Sperrzone“.
        (["0x0"], []),
    ],
)
def test_discovery_reads_orca_exclusions_as_rectangles_of_four_points(
    unknown_printers: Path, area: list[str], boxes: list[tuple[float, float, float, float]]
) -> None:
    """Je vier Punkte von ``bed_exclude_area`` sind ein Hüllrechteck, ein Rest zählt nicht.

    So liest die Orca-Familie die Liste (``PartPlate::calc_bounding_boxes``) und
    prüft gegen sie (``PartPlate::check_outside``); als ein Vieleck gelesen
    schnitt sie sich selbst, und Solidon bot Kobra 3, Kobra 3 Max, Qidi Q1 Pro,
    Q2 und X-Plus 4 gar nicht an (05.10.2026).
    """
    base = unknown_printers / "Acme" / "machine" / "base.json"
    document = json.loads(base.read_text(encoding="utf-8"))
    document["bed_exclude_area"] = area
    _write(base, document)

    printer = sp.discover_printers(unknown_printers / "slicer.exe", "orca")[0]

    # Die Kontur der Vorlage reicht von 10/20 bis 210/220, ihre Mitte ist 110/120.
    expected = tuple(
        (
            (left - 110, front - 120),
            (right - 110, front - 120),
            (right - 110, back - 120),
            (left - 110, back - 120),
        )
        for left, front, right, back in boxes
    )
    assert len(printer.bed_exclusions) == len(expected)
    for found, wanted in zip(printer.bed_exclusions, expected, strict=True):
        assert [number for point in found for number in point] == pytest.approx(
            [number for point in wanted for number in point]
        )


def test_profile_management_fields_are_not_values(tmp_path: Path) -> None:
    """``is_custom_defined`` und ``url`` beschreiben ein Profil der Orca-Familie.

    ``ConfigBase::load_from_json`` legt sie wie ``name`` und ``inherits`` als
    Zeichenkette ab und bricht bei einer Liste ab (``type must be string, but
    is array``). Anycubics Filamentprofile tragen ``is_custom_defined``; als
    Wert weitergereicht kam er in Solidons Filamentdatei als Liste, und Anycubic
    Slicer Next rechnete keinen Auftrag (05.10.2026).
    """
    parent = tmp_path / "filament" / "base.json"
    _write(
        parent,
        {
            "name": "Basis",
            "is_custom_defined": "0",
            "url": "https://x",
            "nozzle_temperature": ["210"],
        },
    )
    child = tmp_path / "filament" / "pla.json"
    _write(child, {"name": "PLA", "inherits": "Basis", "is_custom_defined": "0", "url": ""})

    values = sp.resolve_values(child, roots=(tmp_path,))

    assert values["nozzle_temperature"] == ["210"]
    assert "is_custom_defined" not in values
    assert "url" not in values


def test_prusaslicer_knows_no_exclusion_area_and_reads_points_like_its_stream(
    prusa_mini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PrusaSlicer kennt ``bed_exclude_area`` nicht und übergeht den Schlüssel.

    QIDIs Bündel für PrusaSlicer trägt ihn trotzdem; als Sperrzone gelesen ließ
    er X-Plus 4 und Q1 Pro aus der Auswahl fallen. Und ein Punkt wie ``235-0``
    (AnkerMake M5) ist für PrusaSlicer 235 mal 0: Der Wert wird wie aus einem
    ``istringstream`` gelesen, bis zum ersten Zeichen, das keine Zahl mehr ist
    (``ConfigOptionPoints::deserialize``).
    """
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    bundle = prusa_mini.parent / "resources" / "profiles" / "PrusaResearch.ini"
    content = bundle.read_text(encoding="utf-8").replace(
        "[printer:*common*]",
        "[printer:*common*]\nbed_shape = 0x0,235-0,235x235,0x235\nmax_print_height = 250\n"
        "bed_exclude_area = 0x0,0x0,25x230,25x235,115x235,115x230,25x230,0x0",
    )
    bundle.write_text(content, encoding="utf-8")

    found = sp.discover_printers(prusa_mini, "prusa")

    assert len(found) == 2
    for printer in found:
        assert printer.build_volume == pytest.approx((235, 235, 250))
        assert printer.bed_exclusions == ()


@pytest.mark.parametrize("corner", ["1e999x0", "0x1e999", "-1e999x200"])
def test_a_coordinate_beyond_every_number_is_refused_as_text_too(corner: str) -> None:
    """``float("1e999")`` ist unendlich. Als Listenpunkt wurde eine solche
    Koordinate abgelehnt, als Text (``0x0,1e999x0,…``) ging sie seit dem Lesen
    wie ein ``istringstream`` an der Prüfung vorbei: Bett und Sperrfläche trugen
    eine unendliche Ecke, bis eine spätere Prüfung die Kontur mit falschem Grund
    verwarf (Regression gegen 0.5.2, Durchsicht 0.5.3, Fund 7)."""
    shape = f"0x0,{corner},200x200,0x200"
    for written in (shape, [shape]):
        with pytest.raises(ValueError, match="nonfinite"):
            sp._profile_points(written)


def test_discovered_identity_survives_installation_move_and_separates_nozzles(
    unknown_printers: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    first = sp.discover_printers(unknown_printers / "slicer.exe", "orca")[0]
    other_source = sp.discover_printers(unknown_printers / "bambu-studio.exe", "orca")[0]
    assert other_source.id != first.id
    moved = tmp_path / "other-installation"
    shutil.copytree(unknown_printers, moved)
    monkeypatch.setattr(sp, "install_root", lambda _executable: moved)
    assert sp.discover_printers(moved / "slicer.exe", "orca")[0].id == first.id
    _write(
        moved / "Acme" / "machine" / "fine.json",
        {
            "name": "Acme Unbekannt 0.2 nozzle",
            "instantiation": "true",
            "type": "machine",
            "printer_model": "Acme Unbekannt",
            "inherits": "Acme base",
            "nozzle_diameter": ["0.2"],
        },
    )
    found = sp.discover_printers(moved / "slicer.exe", "orca")
    assert len({printer.id for printer in found}) == 2
    assert sorted(printer.nozzle_diameter for printer in found) == pytest.approx([0.2, 0.6])


@pytest.mark.parametrize(
    "title,nozzle,enclosed",
    [
        ("Acme Unbekannt", 0.6, True),
        ("Acme", 0.6, False),
        ("Acme Unbekannt", 0.4, False),
    ],
)
def test_discovery_preserves_hardware_knowledge_only_for_matching_machine_and_nozzle(
    unknown_printers: Path,
    monkeypatch: pytest.MonkeyPatch,
    title: str,
    nozzle: float,
    enclosed: bool,
) -> None:
    known = PrinterProfile(
        id="known",
        title=title,
        build_volume=(220, 220, 200),
        nozzle_diameter=nozzle,
        enclosed=True,
        nozzle_temperature_max=320,
        travel_speed=500,
        flow_factor=1.75,
        printable_height=190,
    )
    monkeypatch.setattr(profiles, "printer_profiles", lambda: {known.id: known})
    printer = sp.discover_printers(unknown_printers / "slicer.exe", "orca")[0]
    assert printer.enclosed is enclosed
    assert printer.build_volume == pytest.approx((200, 200, 240))
    assert printer.printable_height is None
    assert printer.nozzle_diameter == pytest.approx(0.6)
    assert printer.id != known.id
    if enclosed:
        assert printer.nozzle_temperature_max == 320
        assert printer.travel_speed == pytest.approx(500)
        assert printer.flow_factor == pytest.approx(1.75)


def test_discovery_resolves_prusa_bundle_sections(
    prusa_mini: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    bundle = prusa_mini.parent / "resources" / "profiles" / "PrusaResearch.ini"
    content = bundle.read_text(encoding="utf-8").replace(
        "[printer:*common*]",
        "[printer:*common*]\nbed_shape = -90x-90,90x-90,90x90,-90x90\nmax_print_height = 180",
    )
    bundle.write_text(content, encoding="utf-8")
    found = sp.discover_printers(prusa_mini, "prusa")
    assert len(found) == 2
    assert len({printer.id for printer in found}) == 2
    for printer in found:
        assert printer.build_volume == pytest.approx((180, 180, 180))
        assert printer.nozzle_diameter == pytest.approx(0.4)
        assert printer.prusaslicer_printer == printer.title
        # BIBO, die Deltas: Das Bett liegt um den Ursprung (RM-424).
        assert printer.bed_origin == pytest.approx((0.0, 0.0))


def test_discovery_resolves_cura_bed_shape_and_exclusions(
    cura: Path, cura_bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import build_area

    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    _write(
        cura_bestand / "definitions" / "fdmprinter.def.json",
        {
            "version": 2,
            "name": "FDM Drucker",
            "metadata": {"visible": False},
            "settings": {
                "machine": {
                    "children": {
                        "machine_width": {"default_value": 200},
                        "machine_depth": {"default_value": 160},
                        "machine_height": {"default_value": 210},
                        "machine_shape": {"default_value": "elliptic"},
                        "machine_disallowed_areas": {
                            "default_value": [[[-5, -5], [5, -5], [5, 5], [-5, 5]]]
                        },
                    }
                }
            },
        },
    )
    found = sp.discover_printers(cura, "cura")
    assert len(found) == 1
    printer = found[0]
    assert printer.cura_definition == "abax_pri3"
    assert printer.build_volume == pytest.approx((200, 160, 210))
    assert len(printer.printable_area) > 4
    assert printer.bed_exclusions[0][0] == pytest.approx((-5, -5))
    assert 25000 < build_area.printable_area(printer).area < 25100


@pytest.mark.parametrize(
    "key", ["machine_width", "machine_nozzle_size", "machine_disallowed_areas", "machine_shape"]
)
def test_discovery_rejects_cura_formula_even_with_generic_default(
    cura: Path, cura_bestand: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    path = cura_bestand / "definitions" / "abax_pri3.def.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content["overrides"].update(
        {
            "machine_width": {"default_value": 200},
            "machine_depth": {"default_value": 200},
            "machine_height": {"default_value": 200},
        }
    )
    content["overrides"].setdefault(key, {})["value"] = "some_unknown_setting"
    _write(path, content)
    assert sp.discover_printers(cura, "cura") == ()


def test_cura_reads_disallowed_areas_and_shape_like_its_build_volume(
    cura: Path, cura_bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Curas ``BuildVolume`` nimmt von jeder Sperrfläche die konvexe Hülle
    (``Polygon.getMinkowskiHull``) und behandelt jede Form außer ``elliptic``
    als Rechteck. Vertex K8400 Dual führt sein Sperrviereck über Kreuz,
    Leapfrog Creatr HS schreibt ``Rectangular`` — beide bot Solidon nicht an
    (05.10.2026)."""
    from app.core import build_area

    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    path = cura_bestand / "definitions" / "abax_pri3.def.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content["overrides"].update(
        {
            "machine_width": {"default_value": 200},
            "machine_depth": {"default_value": 200},
            "machine_height": {"default_value": 200},
            "machine_shape": {"default_value": "Rectangular"},
            "machine_disallowed_areas": {
                "default_value": [[[-100, 100], [100, 100], [-100, 80], [100, 80]]]
            },
        }
    )
    _write(path, content)

    printer = sp.discover_printers(cura, "cura")[0]

    assert printer.printable_area == ()
    assert sorted(printer.bed_exclusions[0]) == [(-100, 80), (-100, 100), (100, 80), (100, 100)]
    assert build_area.printable_area(printer).area == pytest.approx(200 * 200 - 200 * 20)


@pytest.mark.parametrize(
    ("key", "formula", "blocked"),
    [
        # AnkerMake M5C: für Curas Auswerter ein unbekannter Name, der mit 0
        # endet (``SettingFunction.__call__``) — und 0 ist kein „elliptic“.
        ("machine_shape", "rectangular", 0.0),
        # UltiMaker Method: die Sperrflächen als Listenliteral.
        ("machine_disallowed_areas", "[ [ [-10, -10], [10, -10], [10, 10], [-10, 10] ] ]", 400.0),
    ],
)
def test_cura_reads_a_constant_written_as_formula_without_computing(
    cura: Path,
    cura_bestand: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    formula: str,
    blocked: float,
) -> None:
    """Zwei Hersteller schreiben Konstanten als Formel. Gelesen werden sie, ohne
    dass etwas ausgeführt wird (Regel 10); jede andere Formel an einem
    Maschinenschlüssel bleibt unbekannt (der Test darüber)."""
    from app.core import build_area

    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    path = cura_bestand / "definitions" / "abax_pri3.def.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content["overrides"].update(
        {
            "machine_width": {"default_value": 200},
            "machine_depth": {"default_value": 200},
            "machine_height": {"default_value": 200},
            "machine_disallowed_areas": {"default_value": []},
        }
    )
    content["overrides"].setdefault(key, {})["value"] = formula
    _write(path, content)

    printer = sp.discover_printers(cura, "cura")[0]

    assert printer.printable_area == ()
    assert build_area.printable_area(printer).area == pytest.approx(200 * 200 - blocked)


@pytest.mark.parametrize("own", [False, True])
def test_the_loaded_filaments_carry_profile_colour_and_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, own: bool
) -> None:
    """Die Farbe steht in der Slicer-Konfiguration, der Typ im Profil."""
    executable = tmp_path / "ElegooSlicer" / "elegoo-slicer.exe"
    executable.parent.mkdir()
    executable.write_text("")
    installed = executable.parent / "resources" / "profiles"
    user = tmp_path / "settings" / "ElegooSlicer" / "user" / "default"
    user.mkdir(parents=True)
    _write(
        installed / "Elegoo" / "filament" / "ECC2" / "Elegoo PETG PRO @ECC2.json",
        {
            "type": "filament",
            "name": "Elegoo PETG PRO @ECC2",
            "instantiation": "true",
            "filament_type": ["PETG"],
        },
    )
    chosen = "Elegoo PETG PRO @ECC2"
    if own:
        chosen = "Meine eigene Spule"
        _write(
            user / "filament" / f"{chosen}.json",
            {"name": chosen, "inherits": "Elegoo PETG PRO @ECC2", "from": "User"},
        )
    config = user.parent.parent / "ElegooSlicer.conf"
    _write(
        config,
        {
            "presets": {"machine": "Elegoo Centauri Carbon 2 0.4 nozzle"},
            "elegoo_presets": [
                {
                    "machine": "Elegoo Centauri Carbon 2 0.4 nozzle",
                    "filament": chosen,
                    "filament_colors": "#9AA0A6",
                }
            ],
        },
    )
    monkeypatch.setattr(sp, "install_root", lambda _executable: installed)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user])

    assert sp.configured_filaments("orca", executable) == (
        sp.SlicerFilament(
            profile=chosen,
            colour="#9AA0A6",
            material_type="PETG",
        ),
    )


@pytest.fixture
def bestand(tmp_path: Path) -> Path:
    """Ein Profilbestand, wie ihn ein Orca-Ableger ausliefert."""
    root = tmp_path / "resources" / "profiles"

    # Elegoo legt eine Ebene tiefer als Bambu — genau daran scheiterte die
    # Suche beim ersten Versuch.
    _write(
        root / "Elegoo" / "machine" / "ECC2" / "Centauri.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.4 nozzle",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "nozzle_diameter": ["0.4"],
            "default_print_profile": "0.20mm Standard @CC2",
        },
    )
    _write(
        root / "Elegoo" / "machine" / "ECC2" / "Centauri06.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.6 nozzle",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "nozzle_diameter": ["0.6"],
        },
    )
    _write(
        root / "Anderer" / "machine" / "Fremd.json",
        {
            "type": "machine",
            "name": "Ganz anderes Gerät 0.4 nozzle",
            "instantiation": "true",
            "printer_model": "Ganz anderes Gerät",
            "nozzle_diameter": ["0.4"],
        },
    )

    # Nur das Standardprofil trägt die Liste; die Geschwister erben sie.
    _write(
        root / "Elegoo" / "process" / "ECC2" / "standard.json",
        {
            "type": "process",
            "name": "0.20mm Standard @CC2",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    _write(
        root / "Elegoo" / "process" / "ECC2" / "fein.json",
        {
            "type": "process",
            "name": "0.12mm Fein @CC2",
            "instantiation": "true",
            "inherits": "0.20mm Standard @CC2",
        },
    )
    _write(
        root / "Elegoo" / "process" / "ECC2" / "fremd.json",
        {
            "type": "process",
            "name": "0.20mm Standard @Fremd",
            "instantiation": "true",
            "compatible_printers": ["Ganz anderes Gerät 0.4 nozzle"],
        },
    )
    # Ein Zwischenstück der Erbkette — im Slicer selbst nicht wählbar.
    _write(
        root / "Elegoo" / "process" / "fdm_process_common.json",
        {"type": "process", "name": "fdm_process_common"},
    )
    # Filamente in der Staffelung, die die Hersteller wirklich benutzen: das
    # wählbare Profil setzt drei Werte, alles andere erbt es über zwei Stufen.
    _write(
        root / "Elegoo" / "filament" / "fdm_filament_common.json",
        {
            "type": "filament",
            "name": "fdm_filament_common",
            "filament_type": ["PLA"],
            "nozzle_temperature": ["220"],
            "hot_plate_temp": ["60"],
            "filament_density": ["1.24"],
        },
    )
    _write(
        root / "Elegoo" / "filament" / "BASE" / "petg_base.json",
        {
            "type": "filament",
            "name": "Elegoo PETG @base",
            "inherits": "fdm_filament_common",
            "filament_type": ["PETG"],
            "nozzle_temperature": ["240"],
            "hot_plate_temp": ["70"],
        },
    )
    _write(
        root / "Elegoo" / "filament" / "ECC2" / "petg.json",
        {
            "type": "filament",
            "name": "Elegoo PETG @ECC2",
            "inherits": "Elegoo PETG @base",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    _write(
        root / "Elegoo" / "filament" / "ECC2" / "petg_trans.json",
        {
            "type": "filament",
            "name": "Elegoo PETG Translucent @ECC2",
            "inherits": "Elegoo PETG @base",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
            "nozzle_temperature": ["255"],
            "pressure_advance": ["0.052"],
        },
    )
    _write(
        root / "Elegoo" / "filament" / "ECC2" / "pla.json",
        {
            "type": "filament",
            "name": "Elegoo PLA @ECC2",
            "inherits": "fdm_filament_common",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    return root


@pytest.fixture
def slicer(bestand: Path) -> Path:
    """Die Programmdatei über dem Profilbestand."""
    executable = bestand.parent.parent / "orca-slicer.exe"
    executable.write_bytes(b"")
    return executable


# --- Finden ------------------------------------------------------------------------


def test_the_install_root_is_found_above_the_executable(slicer: Path, bestand: Path) -> None:
    assert sp.install_root(slicer) == bestand


def test_profiles_are_found_at_any_depth(slicer: Path) -> None:
    """Bambu legt die Profile direkt in ``machine/``, Elegoo eine Ebene tiefer.
    Eine feste Tiefe fände nur die eine Hälfte."""
    found = sp.find_profiles(slicer, "orca")

    names = {entry.name for entry in found}
    assert "Elegoo Centauri Carbon 2 0.4 nozzle" in names
    assert "0.12mm Fein @CC2" in names


def test_the_kind_comes_from_the_folder(slicer: Path) -> None:
    found = sp.find_profiles(slicer, "orca")

    assert {entry.kind for entry in found} == {"machine", "process"}
    assert all(entry.kind == "machine" for entry in sp.machines(found))


def test_filaments_and_intermediates_stay_out(slicer: Path) -> None:
    """Ein Zwischenstück der Erbkette ist im Slicer nicht wählbar und hier
    ebenso wenig; Filamente gehören in eine andere Auswahl."""
    names = {entry.name for entry in sp.find_profiles(slicer, "orca")}

    assert "fdm_process_common" not in names
    assert "PLA" not in names


def test_prusa_needs_no_profiles(slicer: Path) -> None:
    """§29: eine PrusaSlicer-ini läuft eigenständig — eine leere Liste ist
    hier die richtige Antwort, kein Mangel."""
    assert sp.find_profiles(slicer, "prusa") == []


def test_a_missing_install_root_is_no_crash(tmp_path: Path) -> None:
    assert sp.find_profiles(tmp_path / "nirgends.exe", "orca") == []


def test_broken_json_is_skipped_not_fatal(slicer: Path, bestand: Path) -> None:
    (bestand / "Elegoo" / "machine" / "kaputt.json").write_text("{ das ist keins", encoding="utf-8")

    found = sp.find_profiles(slicer, "orca")

    assert found, "der Rest muss trotzdem ankommen"


def test_a_user_profile_wins_over_the_installed_profile_with_the_same_name(
    slicer: Path, bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was der Nutzer im Slicer geändert hat, ist seine sichtbare Auswahl."""
    name = "Mein PETG"
    installed = bestand / "Elegoo" / "filament" / f"{name}.json"
    user_root = tmp_path / "user"
    user = user_root / "filament" / f"{name}.json"
    _write(
        installed,
        {"type": "filament", "name": name, "instantiation": "true", "filament_type": ["PETG"]},
    )
    _write(user, {"name": name, "from": "User", "filament_type": ["PCTG"]})
    monkeypatch.setattr(sp, "install_root", lambda _executable: bestand)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user_root])

    assert sp._named_profile(slicer, "orca", name, "filament") == user


# --- Zuordnen ----------------------------------------------------------------------


def _printer(nozzle: float = 0.4) -> PrinterProfile:
    return PrinterProfile(
        id="x",
        title="Elegoo Centauri Carbon 2",
        build_volume=(256.0, 256.0, 256.0),
        nozzle_diameter=nozzle,
    )


def test_the_printer_finds_its_machine_profile(slicer: Path) -> None:
    machine, process = sp.match(sp.find_profiles(slicer, "orca"), _printer())

    assert machine is not None and machine.name == "Elegoo Centauri Carbon 2 0.4 nozzle"
    assert process is not None and process.name == "0.20mm Standard @CC2"


def test_the_nozzle_decides_between_variants(slicer: Path) -> None:
    """Dasselbe Gerät gibt es mit vier Düsen. Das falsche Profil zu nehmen
    hieße, mit der falschen Bahnbreite zu rechnen."""
    machine, _process = sp.match(sp.find_profiles(slicer, "orca"), _printer(nozzle=0.6))

    assert machine is not None and machine.nozzle == pytest.approx(0.6)


def test_nozzle_choices_follow_distinct_variants_of_the_same_printer_model() -> None:
    """Eine Namensvariante zählt nicht doppelt, ein fremdes Modell zählt nicht mit."""
    found = [
        sp.SlicerProfile(
            path=Path("cc2-04.json"),
            name="Elegoo Centauri Carbon 2 0.4 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.4,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("cc2-04-high-speed.json"),
            name="Elegoo Centauri Carbon 2 0.4 High-Speed nozzle",
            kind="machine",
            printer_model="elegoo centauri carbon 2",
            nozzle=0.4000004,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("cc2-02.json"),
            name="Elegoo Centauri Carbon 2 0.2 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.2,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("cc2-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.6,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("cc2-08.json"),
            name="Elegoo Centauri Carbon 2 0.8 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.8,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("neptune-08.json"),
            name="Elegoo Neptune 4 0.8 nozzle",
            kind="machine",
            printer_model="Elegoo Neptune 4",
            nozzle=0.8,
            vendor="Elegoo",
        ),
    ]
    active = sp.machine_for_name(found, "Elegoo Centauri Carbon 2 0.6 nozzle")
    assert active is not None
    assert sp.same_printer_model(found[0], active)
    assert sp.nozzle_sizes_for_machine(found, active) == pytest.approx((0.2, 0.4, 0.6, 0.8))


def test_same_printer_model_keeps_manufacturers_separate() -> None:
    """Ein gleich benanntes Modell eines anderen Herstellers ist keine Variante."""
    elegoo = sp.SlicerProfile(
        path=Path("elegoo-04.json"),
        name="Centauri 0.4 nozzle",
        kind="machine",
        printer_model="Centauri",
        nozzle=0.4,
        vendor="Elegoo",
    )
    other = replace(
        elegoo,
        path=Path("other-06.json"),
        name="Centauri 0.6 nozzle",
        nozzle=0.6,
        vendor="Other",
    )
    unknown_vendor = replace(elegoo, vendor="", from_user=True)

    assert sp.same_printer_model(elegoo, replace(elegoo, nozzle=0.6))
    assert not sp.same_printer_model(elegoo, other)
    assert not sp.same_printer_model(elegoo, unknown_vendor)
    unknown_first = replace(elegoo, vendor="", from_user=True)
    unknown_second = replace(unknown_first, path=Path("user/other-06.json"), nozzle=0.6)
    assert not sp.same_printer_model(unknown_first, unknown_second)


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("Bambu Lab A1 0.4 nozzle", "Bambu Lab A1"),
        ("Creality K1 Max (0.4 nozzle)", "Creality K1 Max"),
        ("Geeetech A10Pro (0.2 mm nozzle)", "Geeetech A10Pro"),
        ("Original Prusa MK4S HF0.4 nozzle", "Original Prusa MK4S HF"),
        ("Prusa CORE One HF 0.4 nozzle", "Prusa CORE One HF"),
        ("Flashforge Guider4 0.4 HF nozzle", "Flashforge Guider4 HF"),
        ("AzteQ Industrial - 0.6 nozzle", "AzteQ Industrial"),
        ("Snapmaker U1 (0.4+0.6 nozzle)", "Snapmaker U1 (0.4+0.6 nozzle)"),
        ("Raise3D Pro3 0.4 nozzle (Dual)", "Raise3D Pro3 0.4 nozzle (Dual)"),
        ("Sovol SV06 0.4 High-Speed nozzle", "Sovol SV06 0.4 High-Speed nozzle"),
        ("Elegoo Centauri Carbon 2", "Elegoo Centauri Carbon 2"),
    ],
)
def test_the_model_name_drops_the_nozzle_and_keeps_the_hotend(name: str, model: str) -> None:
    """Die Schreibweisen der installierten Bestände; was eine andere Maschine
    meint (Dual, zwei Düsen, High-Speed), bleibt unangetastet."""
    assert sp.model_name(name) == model


def _variants(
    vendor: str, model: str, *names_and_nozzles: tuple[str, float], prefix: str = "machine"
) -> list[sp.SlicerProfile]:
    return [
        sp.SlicerProfile(
            path=Path(f"{prefix}/{name}.json"),
            name=name,
            kind="machine",
            printer_model=model,
            nozzle=nozzle,
            vendor=vendor,
        )
        for name, nozzle in names_and_nozzles
    ]


def test_a_pinned_bundle_variant_follows_a_new_nozzle_to_its_sister() -> None:
    """Ein Drucker aus PrusaSlicers Bündel nennt seine Variante beim Namen; nach
    einem Düsenwechsel im Druckdialog meint er die Schwester, nicht nichts."""
    found = _variants(
        "Creality",
        "CR10",
        ("Creality CR-10 (0.4 mm nozzle)", 0.4),
        ("Creality CR-10 (0.6 mm nozzle)", 0.6),
    )
    printer = PrinterProfile(
        id="slicer-prusa-cr10",
        title="Creality CR-10 (0.4 mm nozzle)",
        build_volume=(300.0, 300.0, 400.0),
        nozzle_diameter=0.6,
        vendor="Creality",
        prusaslicer_printer="Creality CR-10 (0.4 mm nozzle)",
    )

    machine, _process = sp.match(found, printer)

    assert machine is not None and machine.name == "Creality CR-10 (0.6 mm nozzle)"
    # Ohne Schwester mit dieser Düse bleibt es leer, wie an einem erkannten
    # Profil (RM-329) — die 0,4er wäre ein Nachbarmaß.
    assert sp.match(found, replace(printer, nozzle_diameter=0.8)) == (None, None)


def test_a_nozzle_change_keeps_the_hotend_of_the_chosen_variant() -> None:
    """Aus „MK4S HF0.4“ wird bei 0,6 „MK4S HF0.6“ — im Druckdialog wie in der
    Übergabe, auch wenn die gewöhnliche Düse im Alphabet vorn steht."""
    found = _variants(
        "PrusaResearch",
        "Original Prusa MK4S",
        ("Original Prusa MK4S 0.4 nozzle", 0.4),
        ("Original Prusa MK4S 0.6 nozzle", 0.6),
        ("Original Prusa MK4S HF0.4 nozzle", 0.4),
        ("Original Prusa MK4S HF0.6 nozzle", 0.6),
    )
    pinned = PrinterProfile(
        id="slicer-prusa-mk4s-hf",
        title="Original Prusa MK4S HF0.4 nozzle",
        build_volume=(250.0, 210.0, 220.0),
        nozzle_diameter=0.6,
        vendor="PrusaResearch",
        prusaslicer_printer="Original Prusa MK4S HF0.4 nozzle",
    )
    named = replace(pinned, id="slicer-orca-mk4s-hf", prusaslicer_printer="")
    hf_04 = sp.machine_for_name(found, "Original Prusa MK4S HF0.4 nozzle")
    assert hf_04 is not None

    for printer in (pinned, named):
        machine, _process = sp.match(found, printer)
        assert machine is not None and machine.name == "Original Prusa MK4S HF0.6 nozzle"
    handed = sp.machine_with_nozzle(
        sp.identity(hf_04), "orca", Path("orca"), named, available=found
    )
    assert handed == sp.identity(found[3])


def test_dialog_and_handover_take_the_same_plain_sister() -> None:
    """Dieselbe Schwester an beiden Stellen: die Grundausführung, nicht die
    High-Speed-Variante, die im Alphabet vorn steht."""
    found = _variants(
        "Sovol",
        "Sovol SV06",
        ("Sovol SV06 0.4 nozzle", 0.4),
        ("Sovol SV06 0.6 nozzle", 0.6),
        ("Sovol SV06 0.6 High-Speed nozzle", 0.6),
    )
    printer = PrinterProfile(
        id="slicer-orca-sv06",
        title="Sovol SV06 0.4 nozzle",
        build_volume=(220.0, 220.0, 250.0),
        nozzle_diameter=0.6,
        vendor="Sovol",
    )

    machine, _process = sp.match(found, printer)
    handed = sp.machine_with_nozzle(
        sp.identity(found[0]), "orca", Path("orca"), printer, available=found
    )

    assert machine is not None and machine.name == "Sovol SV06 0.6 nozzle"
    assert handed == sp.identity(machine)


def test_a_variant_with_a_wrong_model_field_still_belongs_to_its_name() -> None:
    """Bambu Studio führt „Creality K1 0.8 nozzle“ mit dem Modellfeld des
    K1 Max; am K1 gehört die 0,8 trotzdem zur Wahl, am K1 Max bleibt seine."""
    k1 = _variants(
        "Creality",
        "Creality K1",
        ("Creality K1 0.4 nozzle", 0.4),
        ("Creality K1 0.6 nozzle", 0.6),
    )
    misfiled = _variants("Creality", "Creality K1 Max", ("Creality K1 0.8 nozzle", 0.8))
    k1_max = _variants(
        "Creality",
        "Creality K1 Max",
        ("Creality K1 Max 0.4 nozzle", 0.4),
        ("Creality K1 Max 0.8 nozzle", 0.8),
    )
    found = [*k1, *misfiled, *k1_max]

    assert sp.nozzle_sizes_for_machine(found, k1[0]) == pytest.approx((0.4, 0.6, 0.8))
    assert sp.sister_variant(found, k1[0], 0.8) == misfiled[0]
    assert sp.sister_variant(found, k1_max[0], 0.8) == k1_max[1]
    # Nach dem Namen zählt nur, wer eine Düse im Namen trägt.
    plain = _variants("Creality", "", ("Creality K1", 0.4), ("Creality K1", 0.6), prefix="user")
    assert not sp.same_printer_model(plain[0], plain[1])


def test_a_machine_reads_its_nozzle_from_the_profile_it_inherits(unknown_printers: Path) -> None:
    """Steht die Düse allein in der Erbbasis, gehört sie trotzdem zur Maschine
    (RM-524): OrcaSlicers „Rolohaun Delta Flyer Refit 0.4 nozzle“ erbt sie vom
    Rook MK1 LDO. Gelesen als 0, fand der Druckdialog zu ihrem Drucker keine
    Maschine. Nennt die ganze Kette keine, gilt die Vorgabe des Slicers."""
    executable = unknown_printers / "slicer.exe"
    machines = sp.find_profiles(executable, "orca", kinds=("machine",))
    (machine,) = [entry for entry in machines if entry.name == "Acme Unbekannt 0.6 nozzle"]
    (printer,) = sp.discover_printers(executable, "orca")

    assert machine.nozzle == pytest.approx(0.6)
    chosen, _process = sp.match(machines, printer)
    assert chosen is not None and chosen.name == machine.name

    base = unknown_printers / "Acme" / "machine" / "base.json"
    document = json.loads(base.read_text(encoding="utf-8"))
    del document["nozzle_diameter"]
    _write(base, document)
    (machine,) = [
        entry
        for entry in sp.find_profiles(executable, "orca", kinds=("machine",))
        if entry.name == "Acme Unbekannt 0.6 nozzle"
    ]
    assert machine.nozzle == pytest.approx(0.4)


def test_a_bundle_machine_without_a_nozzle_takes_the_slicers_default(prusa_mini: Path) -> None:
    """Anycubics i3 Mega nennt in PrusaSlicers Bündel keine Düse; PrusaSlicer
    rechnet dann mit 0,4 mm, und die Maschine trägt dieselbe Zahl wie der
    Drucker, den die Erhebung daraus macht (RM-524)."""
    bundle = prusa_mini.parent / "resources" / "profiles" / "PrusaResearch.ini"
    content = bundle.read_text(encoding="utf-8")
    assert "nozzle_diameter = 0.4\n" in content
    bundle.write_text(content.replace("nozzle_diameter = 0.4\n", ""), encoding="utf-8")

    machines = sp.find_profiles(prusa_mini, "prusa", kinds=("machine",))

    assert machines
    assert all(entry.nozzle == pytest.approx(0.4) for entry in machines)


def test_cura_native_instance_wins_over_a_same_family_title_match() -> None:
    """Die gespeicherte Cura-Identität geht vor der nur ähnlich benannten Familie."""
    title_match = sp.SlicerProfile(
        path=Path("cura/instance-a.cfg"),
        name="Elegoo Centauri Carbon 2 0.4 nozzle",
        kind="machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        vendor="Elegoo",
        printer_id="slicer-cura-instance-a",
        cura_instance=Path("cura/instance-a.inst.cfg"),
    )
    active_instance = replace(
        title_match,
        path=Path("cura/instance-b.cfg"),
        name="Elegoo Centauri Carbon 2 0.4 nozzle (Werkstatt B)",
        printer_id="slicer-cura-instance-b",
        cura_instance=Path("cura/instance-b.inst.cfg"),
    )
    printer = PrinterProfile(
        id=active_instance.printer_id,
        title=title_match.name,
        build_volume=(256.0, 256.0, 256.0),
        nozzle_diameter=0.4,
    )

    machine, _process = sp.match([title_match, active_instance], printer)

    assert machine is active_instance


def test_imported_orca_handover_uses_only_its_vendor_nozzle_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die gewählte Herstellerdatei bleibt bis zum ausgeschriebenen Startcode eindeutig."""
    from app.core.export import handover

    def machine(vendor: str, nozzle: float) -> sp.SlicerProfile:
        name = f"Elegoo Centauri Carbon 2 {nozzle:.1f} nozzle"
        path = tmp_path / "profiles" / vendor / "machine" / f"{name}.json"
        _write(
            path,
            {
                "type": "machine",
                "instantiation": "true",
                "name": name,
                "printer_model": "Elegoo Centauri Carbon 2",
                "nozzle_diameter": [str(nozzle)],
                "printable_area": ["0x0", "256x0", "256x256", "0x256"],
                "printable_height": "256",
                "machine_start_gcode": f"{vendor.upper()}_START",
            },
        )
        result = sp._read(path, "machine", False)
        assert result is not None
        return result

    source = machine("Elegoo", 0.4)
    elegoo_06 = machine("Elegoo", 0.6)
    other_vendor_06 = machine("Other", 0.6)
    imported = sp._discovered_printer(
        source,
        "orca",
        sp.resolve_profile(source),
        {},
        "OrcaSlicer",
    )
    imported = replace(
        imported,
        nozzle_diameter=0.6,
        extrusion_width=0.63,
    )
    monkeypatch.setattr(
        sp,
        "find_profiles",
        lambda *_args, **_kwargs: [source, elegoo_06, other_vendor_06],
    )
    profile = Profile(printer=imported, material=profiles.material("pla"))

    handover_setup = handover.SlicerSetup(
        Path("orca.exe"), "orca", machine_profile=str(source.path)
    )
    selected = handover.machine_for(handover_setup, profile)
    assert selected == str(elegoo_06.path)
    written_machine = handover._orca_machine(replace(handover_setup, machine_profile=selected))
    assert written_machine["machine_start_gcode"] == "ELEGOO_START"
    assert written_machine["name"] == "Solidon Elegoo Centauri Carbon 2 0.6 nozzle"

    selected_sibling = replace(handover_setup, machine_profile=str(elegoo_06.path))
    assert handover.machine_for(selected_sibling, profile) == str(elegoo_06.path)

    foreign_sibling = replace(handover_setup, machine_profile=str(other_vendor_06.path))
    assert handover.machine_for(foreign_sibling, profile) == ""


def test_an_imported_variant_selects_its_requested_nozzle_only_within_its_family() -> None:
    """Ein Orca-Anzeigename führt zur eigenen Modellfamilie und richtigen Düse."""
    found = [
        sp.SlicerProfile(
            path=Path("elegoo-04.json"),
            name="Elegoo Centauri Carbon 2 0.4 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.4,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("other-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.6,
            vendor="Other",
        ),
        sp.SlicerProfile(
            path=Path("elegoo-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="elegoo centauri carbon 2",
            nozzle=0.6,
            vendor="ELEGOO",
        ),
        sp.SlicerProfile(
            path=Path("other-08.json"),
            name="Other Centauri Carbon 2 0.8 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.8,
            vendor="Other",
        ),
    ]
    imported = sp._discovered_printer(
        found[0],
        "orca",
        {
            "printer_technology": "FFF",
            "printable_area": ["0x0", "256x0", "256x256", "0x256"],
            "printable_height": "256",
            "nozzle_diameter": ["0.4"],
        },
        {},
        "OrcaSlicer",
    )

    assert imported.id.startswith("slicer-orca-")
    assert imported.title == found[0].name
    assert imported.vendor == "Elegoo"

    assert imported.nozzle_diameter == pytest.approx(0.4)
    machine, _process = sp.match(found, replace(imported, nozzle_diameter=0.6))

    assert machine is found[2]
    assert sp.nozzle_sizes_for_machine(found, found[0]) == pytest.approx((0.4, 0.6))


def test_an_imported_variant_does_not_guess_a_different_nozzle_or_vendor() -> None:
    """Ohne passende eigene Variante bleibt die Maschinenwahl offen."""
    found = [
        sp.SlicerProfile(
            path=Path("elegoo-04.json"),
            name="Elegoo Centauri Carbon 2 0.4 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.4,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("other-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.6,
            vendor="Other",
        ),
    ]
    imported = replace(
        _printer(nozzle=0.6),
        id="slicer-orca-728a0359c367ad7652e8",
        title="Elegoo Centauri Carbon 2 0.4 nozzle",
    )

    assert sp.match(found, imported) == (None, None)


def test_machine_with_nozzle_uses_the_selected_profiles_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die gespeicherte Maschinenkennung und neue Düse treffen dieselbe Familie."""
    found = [
        sp.SlicerProfile(
            path=Path("elegoo-04.json"),
            name="Elegoo Centauri Carbon 2 0.4 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.4,
            vendor="Elegoo",
        ),
        sp.SlicerProfile(
            path=Path("other-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.6,
            vendor="Other",
        ),
        sp.SlicerProfile(
            path=Path("elegoo-06.json"),
            name="Elegoo Centauri Carbon 2 0.6 nozzle",
            kind="machine",
            printer_model="elegoo centauri carbon 2",
            nozzle=0.6,
            vendor="ELEGOO",
        ),
    ]
    monkeypatch.setattr(sp, "find_profiles", lambda *_args, **_kwargs: found)

    selected = sp.machine_with_nozzle(
        str(found[0].path), "orca", Path("orca.exe"), _printer(nozzle=0.6)
    )

    assert selected == sp.identity(found[2])


@pytest.mark.parametrize("machine", [None, "unbekannt", "einzelne Variante"])
def test_nozzle_choices_fall_back_to_common_sizes_without_variants(
    machine: str | None,
) -> None:
    """Ohne ein passendes Variantenpaar bleibt eine brauchbare Auswahl."""
    found: list[sp.SlicerProfile] = []
    selected = None
    if machine == "einzelne Variante":
        selected = sp.SlicerProfile(
            path=Path("one.json"),
            name="Centauri 0.4 nozzle",
            kind="machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=0.4,
        )
        found.append(selected)
    assert sp.nozzle_sizes_for_machine(found, selected) == sp.COMMON_NOZZLE_SIZES


def test_the_plain_machine_wins_over_a_variant_with_the_same_nozzle(
    slicer: Path, bestand: Path
) -> None:
    """OrcaSlicer führt den Sovol SV06 als „0.4 nozzle“ und als „0.4 High-Speed
    nozzle“ — dasselbe Gerät, dieselbe Düse. Bis zum 27.09.2026 entschied die
    Reihenfolge im Ordner, und ein gewöhnlicher SV06 bekam den High-Speed-Prozess
    vorgewählt. Die Variante liegt hier absichtlich zuerst im Ordner."""
    _write(
        bestand / "Elegoo" / "machine" / "ECC2" / "0-HighSpeed.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.4 High-Speed nozzle",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "nozzle_diameter": ["0.4"],
        },
    )
    found = sp.find_profiles(slicer, "orca")
    variants = [
        entry.name
        for entry in sp.machines(found)
        if abs(entry.nozzle - 0.4) < 1e-9 and "Centauri" in entry.name
    ]
    assert variants[0].endswith("High-Speed nozzle"), "sonst prüft der Fall nichts"

    machine, _process = sp.match(found, _printer())

    assert machine is not None and machine.name == "Elegoo Centauri Carbon 2 0.4 nozzle"


def _creality(bestand: Path, name: str, model: str, default: str = "") -> None:
    document: dict[str, object] = {
        "type": "machine",
        "name": name,
        "instantiation": "true",
        "printer_model": model,
        "nozzle_diameter": ["0.4"],
    }
    if default:
        document["default_print_profile"] = default
    _write(bestand / "Creality" / "machine" / f"{name}.json", document)


def test_a_printer_does_not_take_a_relatives_machine(slicer: Path, bestand: Path) -> None:
    """OrcaSlicer führt neben dem Creality K1 den K1C, den K1 Max und die
    CFS-Ausführungen, alle mit 0,4er Düse. Der Titel „Creality K1" begann jeden
    dieser Namen, und seit bei gleicher Düse der kürzeste gewinnt, bekam ein K1
    „Creality K1C 0.4 nozzle" — gemessen am 27.09.2026 samt Prozess
    „0.08mm SuperDetail @Creality K1C"."""
    for name, model in (
        ("Creality K1C 0.4 nozzle", "Creality K1C"),
        ("Creality K1 (0.4 nozzle)", "Creality K1"),
        ("Creality K1 Max (0.4 nozzle)", "Creality K1 Max"),
        ("Creality K1_CFS-C 0.4 nozzle", "Creality K1_CFS-C"),
    ):
        _creality(bestand, name, model)
    k1 = PrinterProfile(id="k1", title="Creality K1", build_volume=(220.0, 220.0, 250.0))
    k1_max = PrinterProfile(id="k1max", title="Creality K1 Max", build_volume=(300.0, 300.0, 300.0))
    found = sp.find_profiles(slicer, "orca")
    assert min(len(entry.name) for entry in sp.machines(found) if "K1" in entry.name) == len(
        "Creality K1C 0.4 nozzle"
    ), "sonst prüft der Fall nichts: der K1C muss der kürzeste Name sein"

    machine, _process = sp.match(found, k1)

    assert machine is not None and machine.name == "Creality K1 (0.4 nozzle)"
    known = {"k1": k1, "k1max": k1_max}
    assert sp.printer_for("Creality K1C 0.4 nozzle", known) == ""
    assert sp.printer_for("Creality K1 Max (0.4 nozzle)", known) == "k1max"
    assert sp.printer_for("Creality K1 (0.4 nozzle)", known) == "k1"


def test_a_standard_process_that_is_not_there_is_not_replaced_by_the_first(
    slicer: Path, bestand: Path
) -> None:
    """Orcas Ender-3 V3 nennt „0.20mm Standard @Creality Ender3 V3", der Bestand
    führt „…@Creality Ender-3 V3". Genommen wurde der erste passende Prozess im
    Ordner, „0.12mm Fine" — eine andere Schichthöhe als die des Druckers."""
    _creality(
        bestand,
        "Creality Ender-3 V3 0.4 nozzle",
        "Creality Ender-3 V3",
        default="0.20mm Standard @Creality Ender3 V3",
    )
    for name in ("0.12mm Fine @Creality Ender-3 V3", "0.20mm Standard @Creality Ender-3 V3"):
        _write(
            bestand / "Creality" / "process" / f"{name}.json",
            {
                "type": "process",
                "name": name,
                "instantiation": "true",
                "compatible_printers": ["Creality Ender-3 V3 0.4 nozzle"],
            },
        )
    ender = PrinterProfile(
        id="e3v3", title="Creality Ender-3 V3", build_volume=(220.0, 220.0, 250.0), layer_height=0.2
    )
    found = sp.find_profiles(slicer, "orca")
    fitting = sp.processes(found, sp.match(found, ender)[0])
    assert fitting[0].name.startswith("0.12mm"), "sonst prüft der Fall nichts"

    _machine, process = sp.match(found, ender)

    assert process is not None and process.name == "0.20mm Standard @Creality Ender-3 V3"
    finer = replace(ender, layer_height=0.16)
    finer_process = sp.match(found, finer)[1]
    assert finer_process is not None and finer_process.name == process.name, (
        "die Schichthöhe im genannten Namen ist die Angabe des Herstellers"
    )


def test_a_named_standard_of_another_printer_means_the_standard_of_its_layer(
    slicer: Path, bestand: Path
) -> None:
    """Anycubics Kobra 4 0,8 nennt „0.40mm Standard @Anycubic Kobra X 0.8
    nozzle“. Den gibt es, aber er passt nur zum Kobra X; die Schichthöhe des
    Druckers (0,2 mm) traf keinen der eigenen Prozesse (0,24 bis 0,56 mm), und
    gedruckt wurde still mit Solidons Tabelle (Anycubic-Matrix, B3)."""
    machine = "Anycubic Kobra 4 0.8 nozzle"
    document: dict[str, object] = {
        "type": "machine",
        "name": machine,
        "instantiation": "true",
        "printer_model": "Anycubic Kobra 4",
        "nozzle_diameter": ["0.8"],
        "default_print_profile": "0.40mm Standard @Anycubic Kobra X 0.8 nozzle",
    }
    _write(bestand / "Anycubic" / "machine" / f"{machine}.json", document)
    for name, printer in (
        ("0.24mm Standard @Anycubic Kobra 4 0.8 nozzle", machine),
        ("0.40mm Standard @Anycubic Kobra 4 0.8 nozzle", machine),
        ("0.56mm Standard @Anycubic Kobra 4 0.8 nozzle", machine),
        ("0.40mm Standard @Anycubic Kobra X 0.8 nozzle", "Anycubic Kobra X 0.8 nozzle"),
    ):
        _write(
            bestand / "Anycubic" / "process" / f"{name}.json",
            {
                "type": "process",
                "name": name,
                "instantiation": "true",
                "compatible_printers": [printer],
            },
        )
    kobra = PrinterProfile(
        id="k4",
        title="Anycubic Kobra 4",
        build_volume=(260.0, 260.0, 260.0),
        nozzle_diameter=0.8,
        layer_height=0.2,
    )
    found = sp.find_profiles(slicer, "orca")

    chosen, process = sp.match(found, kobra)

    assert chosen is not None and chosen.name == machine
    assert process is not None and process.name == "0.40mm Standard @Anycubic Kobra 4 0.8 nozzle"
    nameless = replace(chosen, default_process="")
    assert sp.standard_process(sp.processes(found, chosen), nameless, kobra) is None, (
        "ohne genannte Höhe und ohne Prozess der Druckerhöhe bleibt es leer"
    )


def test_an_unknown_printer_gets_no_guess(slicer: Path) -> None:
    """Eine falsche Vorauswahl wäre schlimmer als keine — sie sähe aus wie
    eine Entscheidung."""
    stranger = PrinterProfile(
        id="y", title="Gerät, das es hier nicht gibt", build_volume=(100.0, 100.0, 100.0)
    )

    assert sp.match(sp.find_profiles(slicer, "orca"), stranger) == (None, None)


def test_inherited_compatibility_counts(slicer: Path) -> None:
    """Nur ein Profil je Familie trägt die Verträglichkeitsliste, die
    Geschwister erben sie. Wer nur das eigene Feld liest, findet eines statt
    aller."""
    found = sp.find_profiles(slicer, "orca")
    machine, _process = sp.match(found, _printer())

    fitting = {entry.name for entry in sp.processes(found, machine)}

    assert fitting == {"0.20mm Standard @CC2", "0.12mm Fein @CC2"}
    assert "0.20mm Standard @Fremd" not in fitting


def test_the_search_opens_every_profile_file_once(
    slicer: Path, bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DRUCK-14: Auswahl, Namensindex und Erbkette lesen dieselben Dateien.

    Am ElegooSlicer waren es 25 941 Öffnungen für 11 951 Dateien, und das
    Öffnen ist unter Windows der teure Teil der Suche (3,9 → 2,2 s). Das
    Ergebnis bleibt dasselbe; gezählt wird hier, wie oft jede Datei gelesen
    wird.
    """
    expected = sp.find_profiles(slicer, "orca")
    reads: dict[Path, int] = {}
    original = Path.read_text

    def counted(self: Path, *args: object, **kwargs: object) -> str:
        reads[self] = reads.get(self, 0) + 1
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counted)
    found = sp.find_profiles(slicer, "orca")

    assert found == expected
    assert reads, "the search must read the store at all"
    assert max(reads.values()) == 1, {path.name: count for path, count in reads.items()}


def test_the_kind_is_read_from_the_folder_with_either_separator(tmp_path: Path) -> None:
    """Der schnelle Schnitt in ``_kind_of`` und ``relative_to`` sagen dasselbe."""
    root = tmp_path / "profiles"
    inside = root / "Elegoo" / "machine" / "ECC2" / "a.json"
    assert sp._kind_of(inside, root) == "machine"
    assert sp._kind_of(Path(str(inside).replace("\\", "/")), root) == "machine"
    assert sp._kind_of(root / "Elegoo" / "a.json", root) is None
    assert sp._kind_of(tmp_path / "elsewhere" / "machine" / "a.json", root) is None
    # Ein Nachbarordner mit gleichem Anfang ist nicht die Wurzel.
    assert sp._kind_of(tmp_path / "profiles2" / "machine" / "a.json", root) is None


def test_an_inheritance_loop_does_not_hang(slicer: Path, bestand: Path) -> None:
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "kreis_a.json",
        {"type": "process", "name": "A", "instantiation": "true", "inherits": "B"},
    )
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "kreis_b.json",
        {"type": "process", "name": "B", "instantiation": "true", "inherits": "A"},
    )
    found = sp.find_profiles(slicer, "orca")
    known = {entry.name: entry for entry in found if entry.kind == "process"}

    assert sp.compatible_with(known["A"], known) == ()


# --- Eigene Profile ----------------------------------------------------------------


def test_own_profiles_are_read_and_marked(slicer: Path, bestand: Path) -> None:
    """Selbst angelegte Profile tragen kein ``type`` und kein
    ``instantiation`` — sie erben bloß. Genau die will man in der Liste haben.
    """
    _write(
        bestand / "Elegoo" / "process" / "ECC2" / "eigenes.json",
        {"name": "Meine Version", "from": "User", "inherits": "0.20mm Standard @CC2"},
    )
    found = sp.find_profiles(slicer, "orca")

    own = [entry for entry in found if entry.name == "Meine Version"]
    assert own, "ein eigenes Profil ohne type muss trotzdem erscheinen"
    assert own[0].from_user
    assert "(" in own[0].title("eigenes"), "und es muss als eigenes erkennbar sein"


def test_the_title_says_it_in_words_not_in_a_symbol(slicer: Path) -> None:
    """Regel 18 und §4.1: ein Zeichen als Kennzeichnung liest sich nicht vor
    und überlebt nicht jeden Zeichensatz."""
    found = sp.find_profiles(slicer, "orca")
    plain = next(entry for entry in found if not entry.from_user)

    assert plain.title("eigenes") == plain.name


# --- Filamente ---------------------------------------------------------------------


def test_filaments_stay_out_of_the_way_unless_asked_for(slicer: Path) -> None:
    """Sie vervielfachen den Bestand — beim ElegooSlicer stehen 5962 Filamente
    3887 Maschinen- und Prozessprofilen gegenüber. Der Dialog, der nur den
    Drucker sucht, soll sie nicht mitlesen."""
    ohne = sp.find_profiles(slicer, "orca")
    assert not [entry for entry in ohne if entry.kind == "filament"]

    mit = sp.find_profiles(slicer, "orca", kinds=("machine", "process", "filament"))
    assert [entry for entry in mit if entry.kind == "filament"]


def test_a_filament_profile_resolves_what_it_inherits(slicer: Path) -> None:
    """Das wählbare Profil setzt drei Werte und erbt den Rest über zwei Stufen.

    Wer nur die oberste Datei liest, übergibt ein Bruchstück — beim echten
    Elegoo-PETG wären das drei Werte statt fünfundfünfzig.
    """
    found = sp.find_profiles(slicer, "orca", kinds=("filament",))
    trans = next(entry for entry in found if entry.name == "Elegoo PETG Translucent @ECC2")

    values = sp.resolve_values(trans.path)

    assert values["nozzle_temperature"] == ["255"], "eigener Wert gewinnt"
    assert values["hot_plate_temp"] == ["70"], "von @base geerbt"
    assert values["filament_density"] == ["1.24"], "aus der Wurzel geerbt"
    assert values["pressure_advance"] == ["0.052"]
    assert "inherits" not in values, "beschreibende Felder erben sich nicht weiter"
    assert "name" not in values


def test_the_material_of_a_filament_profile_may_be_inherited(slicer: Path) -> None:
    """``filament_type`` steht meist eine Ebene höher: von 42 verträglichen
    Profilen des ElegooSlicer nennen ihn sieben selbst."""
    found = sp.find_profiles(slicer, "orca", kinds=("filament",))
    petg = next(entry for entry in found if entry.name == "Elegoo PETG @ECC2")

    assert petg.filament_type == "", "die Datei selbst sagt nichts"
    assert sp.type_of(petg) == "PETG", "die Kette schon"


def test_the_filament_default_is_the_plain_one(slicer: Path) -> None:
    """Von einem Material liegen mehrere Ausführungen im Bestand, und sie
    fahren verschieden. Vorgewählt wird die Grundausführung — eine Vorgabe zu
    raten, die genauer aussieht als sie ist, wäre schlechter als die
    einfache."""
    found = sp.find_profiles(slicer, "orca", kinds=("machine", "process", "filament"))
    machine = next(
        entry for entry in sp.machines(found) if entry.name.endswith("Carbon 2 0.4 nozzle")
    )

    chosen = sp.match_filament(found, machine, "PETG")

    assert chosen is not None
    assert chosen.name == "Elegoo PETG @ECC2"
    assert sp.match_filament(found, machine, "PLA") is not None
    assert sp.match_filament(found, machine, "ABS") is None, "was fehlt, wird nicht geraten"


def test_without_a_printer_there_is_no_filament_default(slicer: Path) -> None:
    """Ohne Drucker keine Vorgabe — und vor allem: keine Suche über alles.

    ``type_of`` löst je Profil eine Erbkette aus Dateien auf. Mit Drucker sind
    das die 42 verträglichen Profile, ohne ihn der ganze Bestand: 5962 beim
    installierten ElegooSlicer, gemessen 0,97 Sekunden gegen über zehn
    Minuten. Der Aufruf steht im Qt-Hauptthread, also stand mit ihm die
    Anwendung — und ausgelöst hat es kein Sonderfall, sondern die Vorgabe:
    zum „Allgemeinen FDM-Drucker 220 mm" findet kein Slicer ein Profil.
    """
    found = sp.find_profiles(slicer, "orca", kinds=("machine", "process", "filament"))

    begonnen = time.perf_counter()
    assert sp.match_filament(found, None, "PETG") is None
    assert time.perf_counter() - begonnen < 0.1, "ohne Drucker wird nichts aufgeschlagen"


# --- welchen Drucker der Slicer hat (§2.3, §29) ---------------------------------


def test_the_machine_name_leads_to_the_printer_profile() -> None:
    """Der Name des Slicers trägt die Düse, der von Solidon nicht.

    Verglichen wird deshalb am Anfang — und der längste Titel gewinnt, sonst
    stünde „Elegoo Neptune 4" auch für den Plus.
    """
    known = profiles.printer_profiles()

    assert sp.printer_for("Elegoo Centauri Carbon 2 0.4 nozzle", known) == ("centauri-carbon-2")
    assert sp.printer_for("Elegoo Neptune 4 Plus 0.4 nozzle", known) == ("elegoo-neptune-4-plus")
    assert sp.printer_for("Ratterkiste 3000", known) == "", "was nicht trifft, wird nicht geraten"


@pytest.mark.parametrize(
    ("machine", "printer"),
    [
        ("Creality Ender-3 V3 SE 0.4 nozzle", "creality-ender3-v3-se"),
        ("Creality Ender-3 V3 KE 0.4 nozzle", "creality-ender3-v3-ke"),
        ("Creality Ender-3 V3 0.4 nozzle", "creality-ender3-v3"),
    ],
)
def test_a_v3_se_or_ke_in_the_slicer_is_not_the_corexz_v3(machine: str, printer: str) -> None:
    """„Creality Ender-3 V3" beginnt auch die Namen von SE und KE.

    Solange Solidon nur den V3 kannte, wurde jeder von ihnen ein V3 — ein
    Drucker mit 12 000 statt 2500 mm/s² (Prüfbericht Cura, B8). Der längste
    Titel gewinnt, also genügt der eigene Eintrag.
    """
    assert sp.printer_for(machine, profiles.printer_profiles()) == printer


def test_a_missing_configuration_is_no_suggestion(tmp_path: Path) -> None:
    """Kein Slicer, keine Vorgabe — und kein Fehler."""
    assert sp.chosen_machine("orca", tmp_path / "nirgends.exe") == ""
    assert sp.chosen_machine("prusa", tmp_path / "nirgends.exe") == ""


# --- was ein Filament über sich sagt (§29) --------------------------------------


def test_a_filament_profile_tells_its_own_values(tmp_path: Path) -> None:
    """Solidon kennt „PETG", der Slicer kennt sieben davon.

    Der Startbestand nennt 10 mm³/s bei 80 Grad Bett; Elegoo PETG PRO fährt
    5 mm³/s bei 70. Der Unterschied ist kein Feinschliff — mit dem falschen
    Volumenstrom rechnet die Beratung gegen eine Grenze, die das eingelegte
    Material gar nicht hat, findet nichts einzuwenden und lässt ein Tempo
    stehen, das die Düse nicht flüssig bekommt.

    Gelesen wird über die Erbkette: ein Profil bei Elegoo setzt selbst drei
    Werte und erbt fünfzig.
    """
    (tmp_path / "Basis.json").write_text(
        json.dumps(
            {
                "name": "Basis",
                "nozzle_temperature": ["240"],
                "hot_plate_temp": ["70"],
                "fan_max_speed": ["40"],
                "filament_density": ["1.25"],
                "filament_max_volumetric_speed": ["8"],
            }
        ),
        encoding="utf-8",
    )
    oben = tmp_path / "Spule.json"
    oben.write_text(
        json.dumps({"name": "Spule", "inherits": "Basis", "filament_max_volumetric_speed": ["5"]}),
        encoding="utf-8",
    )

    werte = sp.filament_values(oben)

    assert werte["filament.max_flow"] == 5.0, "der eigene Wert schlägt den geerbten"
    assert werte["temperature.nozzle"] == 240, "und was nur geerbt ist, steht trotzdem da"
    assert werte["temperature.bed"] == 70
    assert werte["filament.density"] == 1.25
    assert werte["cooling.fan_speed"] == 0.4, "Prozent im Profil, Bruch in Solidon"


def test_both_ends_of_the_fan_curve_are_read_back_in_every_format(tmp_path: Path) -> None:
    """Befund Robert, 23.09.2026: Elegoo PLA @ECC2 nennt 50 bis 100 % mit der
    Schwelle bei 80 s. Gelesen wurde nur das obere Ende, und beim Schreiben
    stand der eine Wert an beiden — der Lüfter lief in jeder Schicht voll.
    Dieselbe Frage an alle drei Formate, die Solidon zurückliest."""
    orca = tmp_path / "Elegoo PLA @ECC2.json"
    orca.write_text(
        json.dumps(
            {
                "name": "Elegoo PLA @ECC2",
                "fan_min_speed": ["50"],
                "fan_max_speed": ["100"],
                "fan_cooling_layer_time": ["80"],
            }
        ),
        encoding="utf-8",
    )
    prusa = tmp_path / "filament" / "Prusament PETG.ini"
    prusa.parent.mkdir()
    prusa.write_text(
        "min_fan_speed = 30\nmax_fan_speed = 50\nfan_below_layer_time = 20\n",
        encoding="utf-8",
    )
    cura = tmp_path / "petg.inst.cfg"
    cura.write_text(
        "[general]\nversion = 4\nname = PETG\ndefinition = fdmprinter\n\n"
        "[metadata]\ntype = material\n\n"
        "[values]\ncool_fan_speed = 60\ncool_fan_speed_min = 25\n"
        "cool_min_layer_time_fan_speed_max = 15\n",
        encoding="utf-8",
    )

    werte = sp.filament_values(orca)
    assert werte["cooling.fan_speed"] == pytest.approx(1.0)
    assert werte["cooling.minimum_fan_speed"] == pytest.approx(0.5)
    assert werte["cooling.fan_below_layer_time"] == pytest.approx(80.0)

    werte = sp.filament_values(prusa)
    assert werte["cooling.fan_speed"] == pytest.approx(0.5)
    assert werte["cooling.minimum_fan_speed"] == pytest.approx(0.3)
    assert werte["cooling.fan_below_layer_time"] == pytest.approx(20.0)

    werte = sp.filament_values(cura)
    assert werte["cooling.fan_speed"] == pytest.approx(0.6)
    assert werte["cooling.minimum_fan_speed"] == pytest.approx(0.25)
    assert werte["cooling.fan_below_layer_time"] == pytest.approx(15.0)


def test_what_a_filament_does_not_say_is_not_invented(tmp_path: Path) -> None:
    """Ein Wert, den niemand gesetzt hat, ist keine Angabe des Herstellers.

    ``nil`` steht in den mitgelieferten Profilen für „hier gilt, was das
    Vorgehen sagt". Als Zahl gelesen wäre daraus eine Rückzugslänge von null.
    """
    datei = tmp_path / "Karg.json"
    datei.write_text(
        json.dumps(
            {"name": "Karg", "nozzle_temperature": ["230"], "filament_retraction_length": ["nil"]}
        ),
        encoding="utf-8",
    )

    werte = sp.filament_values(datei)

    assert werte["temperature.nozzle"] == 230
    assert "retraction.length" not in werte, "nil ist keine Zahl"
    assert "filament.max_flow" not in werte, "was fehlt, fehlt"


def test_a_machine_profile_gives_up_what_solidon_cannot_know(tmp_path: Path) -> None:
    """§29: Was nur der Hersteller weiß, wird übernommen statt erfunden.

    Bauraum, Düse und Bauart stehen im eigenen Druckerprofil und werden
    gerechnet. Was hier gelesen wird, ist das andere: wie die Maschine
    anfährt, wie schnell sie beschleunigen darf, wie sie zurückzieht. Ohne
    diese Werte lehnt die Orca-Familie ein Prozessprofil ab, bevor sie das
    Modell ansieht — deshalb hing die Übergabe bisher an einem Herstellerprofil,
    das der Kunde von Hand auswählen musste.

    Über die Erbkette, wie bei den Filamenten: Am echten Elegoo Centauri sind
    es 38 Schlüssel in der eigenen Datei und 83 in der aufgelösten Kette.

    **Ein geratener Anfahrcode fährt die Düse ins Bett.** Was das Profil nicht
    nennt, fehlt deshalb auch hier — die Prüfung darauf steht unten.
    """
    (tmp_path / "Grundlage.json").write_text(
        json.dumps(
            {
                "name": "Grundlage",
                "machine_start_gcode": "G28 ; home",
                "machine_end_gcode": "M104 S0",
                "gcode_flavor": "marlin",
                "machine_max_acceleration_x": ["5000", "5000"],
                "retraction_length": ["0.8"],
                "nozzle_diameter": ["0.4"],
            }
        ),
        encoding="utf-8",
    )
    oben = tmp_path / "Maschine.json"
    oben.write_text(
        json.dumps(
            {
                "name": "Maschine",
                "inherits": "Grundlage",
                "gcode_flavor": "klipper",
                "printer_structure": "corexy",
            }
        ),
        encoding="utf-8",
    )

    werte = sp.machine_values(oben)

    assert werte["gcode_flavor"] == "klipper", "der eigene Wert schlägt den geerbten"
    assert werte["machine_start_gcode"] == "G28 ; home", "und was nur geerbt ist, steht da"
    assert werte["retraction_length"] == ["0.8"], "roh übernommen, nicht übersetzt"
    assert werte["printer_structure"] == "corexy"
    assert "nozzle_diameter" not in werte, (
        "was Solidon selbst kennt, wird gerechnet und nicht übernommen — "
        "sonst gäbe es zwei Wahrheiten über dieselbe Zahl"
    )


def test_a_machine_profile_that_says_nothing_yields_nothing(tmp_path: Path) -> None:
    """Ein Wert, den niemand gesetzt hat, ist keine Angabe des Herstellers.

    Die Gegenrichtung zum Test darüber, und bei G-Code die wichtigere: Eine
    Vorgabe zu erfinden wäre hier nicht bloß ungenau, sondern gefährlich.
    """
    leer = tmp_path / "Leer.json"
    leer.write_text(json.dumps({"name": "Leer"}), encoding="utf-8")

    assert sp.machine_values(leer) == {}


def test_the_vendor_of_a_profile_is_the_folder_above_filament(tmp_path: Path) -> None:
    """Der Hersteller steht nicht in der Datei, sondern im Ablageort.

    Er ist die einzige Angabe, die jedes mitgelieferte Profil trägt: Gemessen
    an einem ElegooSlicer-Bestand sind es 5962 Filamentprofile aus 48
    Herstellern, keines ohne. ``filament_type`` dagegen steht nur bei 888.
    """
    entry = sp.SlicerProfile(
        path=tmp_path / "Elegoo" / "filament" / "Elegoo PLA @EC.json",
        name="Elegoo PLA @EC",
        kind="filament",
    )

    assert sp.vendor_of(entry) == "Elegoo"


def test_an_own_profile_gets_no_invented_vendor(tmp_path: Path) -> None:
    """Unter dem Konto steht der Kontoname, und der ist kein Hersteller.

    Eigene Profile liegen in ``user/<Konto>/filament``. Den Ordner darüber als
    Hersteller auszuweisen wäre eine erfundene Auskunft; ``from_user`` sagt
    ohnehin mehr über sie.
    """
    entry = sp.SlicerProfile(
        path=tmp_path / "user" / "default" / "filament" / "Meine Spule.json",
        name="Meine Spule",
        kind="filament",
        from_user=True,
    )

    assert sp.vendor_of(entry) == ""


def test_the_material_comes_from_the_profile_before_the_name(tmp_path: Path) -> None:
    """Was das Profil selbst sagt, schlägt jede Ableitung aus dem Namen."""
    entry = sp.SlicerProfile(
        path=tmp_path / "Elegoo" / "filament" / "Spule.json",
        name="Elegoo PLA @EC",
        kind="filament",
        filament_type="PETG",
    )

    assert sp.material_of(entry, ("PLA", "PETG")) == "PETG"


def test_a_carbon_filled_filament_is_not_the_plain_material(tmp_path: Path) -> None:
    """``PLA-CF`` ist kein PLA — es fährt anders, und es unter PLA zu zeigen
    führte jemanden zur falschen Spule.

    Erkannt wird deshalb nur eine ganze Wortmarke. Der Preis dafür ist
    gemessen: 4028 der 5962 Profile bekommen so eine Materialart statt 4449
    bei der laxen Suche — die Differenz sind Kohlefaser- und
    Sondermischungen, und die gehören nicht unter das Grundmaterial.
    """
    arten = ("PLA", "PETG", "PETG-CF")

    def profil(name: str) -> sp.SlicerProfile:
        return sp.SlicerProfile(path=tmp_path / f"{name}.json", name=name, kind="filament")

    assert sp.material_of(profil("Elegoo PLA @EC"), arten) == "PLA"
    assert sp.material_of(profil("Generic PLA-CF"), arten) == ""
    assert sp.material_of(profil("Elegoo PETG-CF @EC"), arten) == "PETG-CF", (
        "die längere Marke gewinnt, sonst stünde PETG-CF unter PETG"
    )
    assert sp.material_of(profil("Bambu PA6-CF"), arten) == "", (
        "was Solidon nicht führt, bekommt keine Art — die Suche bleibt der Weg dorthin"
    )


# --- Erben über Baumgrenzen -----------------------------------------------------


def _own_filament(tmp_path: Path, name: str, inherits: str) -> tuple[Path, Path]:
    """Ein im Slicer angelegtes Filament unter ``user/<Konto>/filament/`` —
    setzt nur den Fluss und erbt alles Übrige."""
    user = tmp_path / "settings" / "OrcaSlicer" / "user" / "default"
    own = user / "filament" / f"{name}.json"
    _write(
        own, {"name": name, "from": "User", "inherits": inherits, "filament_flow_ratio": ["0.96"]}
    )
    return user, own


def test_an_own_profile_inherits_from_the_installed_vendor_base(
    slicer: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, CORE-14: Das eigene Profil liegt unter
    ``user/<Konto>/filament/``, seine Basis unter ``resources/profiles/``.
    Die Kette suchte nur im eigenen ``filament/``-Ordner, fand die Basis nie
    und endete ohne Meldung beim Nutzerdelta — das ausgeschriebene Profil
    ging ohne Temperatur und Materialtyp zum Slicer.

    Mit den Wurzeln der Installation reicht die Kette hinüber.
    """
    user, own = _own_filament(tmp_path, "Meine Spule", "Elegoo PETG @base")
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user])

    roots = sp.profile_roots("orca", slicer)
    values = sp.resolve_values(own, roots)

    assert values["filament_flow_ratio"] == ["0.96"], "das eigene Delta gewinnt"
    assert values["hot_plate_temp"] == ["70"], "von der Herstellerbasis geerbt"
    assert values["filament_density"] == ["1.24"], "und aus deren Wurzel"
    assert "inherits" not in values

    profile = sp._read(own, "filament", True)
    assert profile is not None
    assert sp.type_of(profile, roots) == "PETG", "auch der Materialtyp kommt aus der Basis"
    machine = sp.SlicerProfile(Path("machine.json"), "Centauri", "machine")
    assert sp.match_filament([profile], machine, "PETG", roots) == profile
    readback = sp.filament_values(own, roots)
    assert readback["temperature.bed"] == 70
    assert readback["filament.flow_ratio"] == pytest.approx(0.96)


def test_an_own_profile_finds_the_system_copy_beside_its_user_folder(tmp_path: Path) -> None:
    """Die Orca-Familie kopiert die gewählten Herstellerbündel nach
    ``<Programm>/system/`` neben ``user/``. Wer nur die Datei kennt — ohne
    Wurzeln —, findet die Basis dort trotzdem."""
    user, own = _own_filament(tmp_path, "Meine Spule", "Elegoo PETG @base")
    _write(
        user.parent.parent / "system" / "Elegoo" / "filament" / "Elegoo PETG @base.json",
        {"type": "filament", "name": "Elegoo PETG @base", "hot_plate_temp": ["70"]},
    )

    values = sp.resolve_values(own)

    assert values["hot_plate_temp"] == ["70"]
    assert values["filament_flow_ratio"] == ["0.96"]


def test_a_base_that_is_nowhere_is_said_out_loud(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Eine Basis, die es nirgends gibt, bleibt sichtbar: Die Kette endet beim
    Delta, und das Protokoll sagt es — statt still ein halbes Profil
    auszuschreiben."""
    _user, own = _own_filament(tmp_path, "Verwaist", "Gibt es nicht @base")

    with caplog.at_level("WARNING"):
        values = sp.resolve_values(own)

    assert values == {"filament_flow_ratio": ["0.96"]}
    assert any("Gibt es nicht @base" in record.message for record in caplog.records)


def test_the_own_profile_takes_the_place_of_the_installed_one_in_the_list(
    slicer: Path, bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, CORE-15: ``find_profiles`` las zuerst die
    Installation, dann den Nutzerbestand — und hängte das eigene Profil nur
    an, statt das gleichnamige mitgelieferte zu ersetzen. ``profile_file``
    nahm den ersten Treffer und las die Herstellerfassung."""
    name = "Mein PETG"
    installed = bestand / "Elegoo" / "filament" / f"{name}.json"
    user_root = tmp_path / "user"
    user = user_root / "filament" / f"{name}.json"
    _write(
        installed,
        {"type": "filament", "name": name, "instantiation": "true", "filament_type": ["PETG"]},
    )
    _write(user, {"name": name, "from": "User", "filament_type": ["PCTG"]})
    monkeypatch.setattr(sp, "install_root", lambda _executable: bestand)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user_root])

    found = [
        entry
        for entry in sp.find_profiles(slicer, "orca", kinds=("filament",))
        if entry.name == name
    ]

    assert len(found) == 1, "ein Name, ein Eintrag"
    assert found[0].path == user, "und zwar der eigene"
    assert found[0].from_user


def test_a_versioned_appimage_still_finds_its_user_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, CORE-16: ``user_roots`` verlangte den ganzen
    Dateistamm als Ordnernamen — ``OrcaSlicer_Linux_V2.1.1.AppImage`` suchte
    nach ``orcaslicerlinuxv2.1.1`` und fand ``~/.config/OrcaSlicer`` nie;
    eigene Profile, gewählter Drucker und Filamente fehlten nach jedem Update."""
    config = tmp_path / "config"
    account = config / "OrcaSlicer" / "user" / "default"
    account.mkdir(parents=True)
    executable = tmp_path / "OrcaSlicer_Linux_V2.1.1.AppImage"
    executable.write_bytes(b"")
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))

    assert sp.user_roots("orca", executable) == [account]
    assert sp.user_roots("orca", tmp_path / "BambuStudio_ubuntu-24.04_v01.09.AppImage") == []


# --- Cura: eigene Ordnernamen, drei Formate ----------------------------------------


@pytest.fixture
def cura_bestand(tmp_path: Path) -> Path:
    """Ein Bestand, wie Cura ihn ausliefert.

    Drei Formate nebeneinander — Drucker als JSON, Qualität als INI, Material
    als XML — und die Ordner heißen anders als bei der Orca-Familie. Genau
    daran fand die gemeinsame Suche bis zum 08.09.2026 nichts.
    """
    root = tmp_path / "share" / "cura" / "resources"

    _write(
        root / "definitions" / "abax_pri3.def.json",
        {
            "version": 2,
            "name": "Abax PRi3",
            "inherits": "fdmprinter",
            "metadata": {"visible": True, "manufacturer": "Abax 3D Technologies"},
            "overrides": {"machine_nozzle_size": {"default_value": 0.4}},
        },
    )
    # Die Wurzel der Erbkette: im Slicer nicht wählbar, hier ebenso wenig.
    _write(
        root / "definitions" / "fdmprinter.def.json",
        {"version": 2, "name": "FDM Drucker", "metadata": {"visible": False}},
    )
    # Ohne Angabe erbt Cura die Sichtbarkeit; ein fälschlich angebotener
    # Drucker ist verschmerzbar, ein fehlender nicht.
    _write(
        root / "definitions" / "ohne_angabe.def.json",
        {"version": 2, "name": "Gerät ohne Angabe", "metadata": {"manufacturer": "Wer auch immer"}},
    )

    quality = root / "quality" / "abax_pri3"
    quality.mkdir(parents=True, exist_ok=True)
    (quality / "apri3_pla_fast.inst.cfg").write_text(
        "[general]\ndefinition = abax_pri3\nname = Fine\nversion = 4\n\n"
        "[metadata]\nmaterial = generic_pla\nquality_type = normal\ntype = quality\n\n"
        "[values]\nlayer_height = 0.1\nspeed_print = 60\n",
        encoding="utf-8",
    )
    # Eine Absicht ist kein Prozessprofil: sie setzt auf einem auf.
    (quality / "apri3_engineering.inst.cfg").write_text(
        "[general]\ndefinition = abax_pri3\nname = Technisch\nversion = 4\n\n"
        "[metadata]\nintent_category = engineering\ntype = intent\n\n"
        "[values]\nwall_thickness = 1.2\n",
        encoding="utf-8",
    )

    materials = root / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / "bestfilament_petg_orange.xml.fdm_material").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fdmmaterial xmlns="http://www.ultimaker.com/material" version="1.3">\n'
        "  <metadata>\n"
        "    <name><brand>Best Filament</brand><material>PETG</material>"
        "<color>Orange</color></name>\n"
        "    <color_code>#FFA500</color_code>\n"
        "  </metadata>\n"
        "  <properties><density>1.27</density><diameter>1.75</diameter></properties>\n"
        "</fdmmaterial>\n",
        encoding="utf-8",
    )
    (materials / "generic_pla.xml.fdm_material").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fdmmaterial xmlns="http://www.ultimaker.com/material" version="1.3">\n'
        "  <metadata>\n"
        "    <name><brand>Generic</brand><material>PLA</material>"
        "<color>Generic</color></name>\n"
        "    <color_code>#ffc924</color_code>\n"
        "  </metadata>\n"
        "  <properties><density>1.24</density><diameter>2.85</diameter></properties>\n"
        "</fdmmaterial>\n",
        encoding="utf-8",
    )
    (materials / "zerrissen.xml.fdm_material").write_text("<fdmmaterial", encoding="utf-8")
    return root


@pytest.fixture
def cura(cura_bestand: Path) -> Path:
    """Die Rechenmaschine über dem Bestand — ``CuraEngine``, nicht das Fenster."""
    executable = cura_bestand.parent.parent.parent / "CuraEngine.exe"
    executable.write_bytes(b"")
    return executable


def test_cura_printers_are_found_and_base_classes_are_not(cura: Path) -> None:
    """Vor dem 08.09.2026 fand Solidon bei Cura 5.13 null von 615 Druckern:
    Gesucht wurde nach Orca-Ordnernamen, und Cura hat andere."""
    found = sp.find_profiles(cura, "cura", kinds=("machine",))
    namen = sorted(entry.name for entry in found)

    assert namen == ["Abax PRi3", "Gerät ohne Angabe"], (
        f"gefunden: {namen} — die Wurzel der Erbkette gehört nicht in die Auswahl"
    )


def test_a_cura_printer_carries_the_id_its_profiles_point_at(cura: Path) -> None:
    """``abax_pri3.def.json`` heißt ``abax_pri3`` — genau darauf zeigt
    ``definition`` in jedem Qualitätsprofil. ``Path.stem`` allein ließe
    ``.def`` stehen, und dann fände kein Profil seinen Drucker."""
    found = next(
        entry
        for entry in sp.find_profiles(cura, "cura", kinds=("machine",))
        if entry.name == "Abax PRi3"
    )

    assert found.printer_model == "abax_pri3"
    assert found.nozzle == pytest.approx(0.4), "die Düse steht in den overrides"


def test_cura_quality_profiles_bind_to_their_printer_and_intents_stay_out(cura: Path) -> None:
    """``[general] definition`` ist Curas ``compatible_printers``. Eine
    Absicht (``type = intent``) ist kein Prozessprofil."""
    found = sp.find_profiles(cura, "cura", kinds=("process",))

    assert [entry.name for entry in found] == ["Fine"]
    assert found[0].compatible_printers == ("abax_pri3",)


def test_a_cura_material_becomes_a_readable_filament(cura: Path) -> None:
    """Marke, Art und Farbe ergeben den Namen, den Cura selbst anzeigt — und
    ein Farbname, der keine Farbe meint, bleibt weg."""
    found = sp.find_profiles(cura, "cura", kinds=("filament",))
    namen = sorted(entry.name for entry in found)

    assert namen == ["Best Filament PETG Orange", "Generic PLA"], (
        f"gefunden: {namen} — die zerrissene Datei fehlt einfach, sie reißt nichts ab"
    )
    petg = next(entry for entry in found if entry.name.startswith("Best"))
    assert petg.filament_type == "PETG"


def test_a_broken_cura_file_is_skipped_not_fatal(cura: Path, cura_bestand: Path) -> None:
    """Dieselbe Haltung wie beim Orca-Leser: eine kaputte Datei im Bestand
    eines fremden Programms ist ein Eintrag weniger."""
    (cura_bestand / "definitions" / "zerrissen.def.json").write_text("{", encoding="utf-8")
    (cura_bestand / "quality" / "abax_pri3" / "zerrissen.inst.cfg").write_text(
        "[general", encoding="utf-8"
    )

    assert len(sp.find_profiles(cura, "cura", kinds=("machine",))) == 2
    assert len(sp.find_profiles(cura, "cura", kinds=("process",))) == 1


def _cura_konfiguration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Curas Konfigurationsordner, wie Cura 5.13 ihn nach dem Einrichten schreibt.

    ``cura.cfg`` nennt die aktive Maschine, je Fach ein Extruderstapel mit
    dem Material an Stelle vier (``_ContainerIndexes.Material``). Die
    Kennung des ersten ist eine Ableitung mit Maschine und Düse, wie Cura sie
    für Drucker mit Düsenvarianten bildet; das zweite Fach trägt ein eigenes
    Material aus dem Konfigurationsordner. Eine zweite Maschine mit anderem
    Material zeigt, dass nur die aktive zählt.
    """
    config = tmp_path / "config"
    root = config / "cura" / "5.13"
    (root / "extruders").mkdir(parents=True)
    (root / "materials").mkdir(parents=True)
    (root / "cura.cfg").write_text(
        "[general]\nversion = 7\n\n[cura]\nactive_machine = Meine Werkstatt\n",
        encoding="utf-8",
    )

    def fach(dateiname: str, maschine: str, position: int, material: str) -> None:
        (root / "extruders" / dateiname).write_text(
            f"[general]\nversion = 4\nname = Extruder {position + 1}\nid = {dateiname}\n\n"
            f"[metadata]\ntype = extruder_train\nmachine = {maschine}\n"
            f"position = {position}\nsetting_version = 27\n\n"
            "[containers]\n0 = empty_user_changes\n1 = empty_quality_changes\n"
            f"2 = empty_intent\n3 = apri3_pla_fast\n4 = {material}\n5 = empty_variant\n"
            "6 = empty_definition_changes\n7 = fdmextruder\n",
            encoding="utf-8",
        )

    fach("meine+werkstatt_1.extruder.cfg", "Meine Werkstatt", 1, "eigenes_petg")
    fach("meine+werkstatt_0.extruder.cfg", "Meine Werkstatt", 0, "generic_pla_abax_pri3_0.4mm")
    fach("andere_0.extruder.cfg", "Andere Maschine", 0, "bestfilament_petg_orange")
    (root / "materials" / "eigenes_petg.xml.fdm_material").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fdmmaterial xmlns="http://www.ultimaker.com/material" version="1.3">\n'
        "  <metadata>\n"
        "    <name><brand>Werkstatt</brand><material>PETG</material>"
        "<color>Blau</color></name>\n"
        "    <color_code>#1e4bd2</color_code>\n"
        "  </metadata>\n"
        "</fdmmaterial>\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(sp.Path, "home", classmethod(lambda cls: tmp_path / "kein_home"))
    return root


def test_cura_names_the_spools_of_its_active_machine(
    cura: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Filamentübernahme las Orca und Prusa, Cura blieb leer (Durchsicht 0.5.0).

    Gelesen wird die aktive Maschine, in Fachreihenfolge: das mitgelieferte
    PLA über seine abgeleitete Kennung, das eigene PETG aus dem
    Konfigurationsordner. Die andere Maschine bleibt draußen.
    """
    _cura_konfiguration(tmp_path, monkeypatch)

    found = sp.configured_filaments("cura", cura)

    assert found == (
        sp.SlicerFilament(profile="Generic PLA", colour="#FFC924", material_type="PLA"),
        sp.SlicerFilament(profile="Werkstatt PETG Blau", colour="#1E4BD2", material_type="PETG"),
    )


def _cura_maschine(root: Path, name: str, definition: str) -> None:
    """Ein Maschinenstapel, wie Cura 5.13 ihn schreibt.

    Der Dateiname ist kodiert, die Kennung steht in ``[general]``, und die
    Druckerdefinition steht an letzter Stelle (``_ContainerIndexes.Definition``).
    """
    place = root / "machine_instances"
    place.mkdir(exist_ok=True)
    (place / f"{name.replace(' ', '+')}.global.cfg").write_text(
        f"[general]\nversion = 5\nname = {name}\nid = {name}\n\n"
        "[metadata]\nsetting_version = 27\ntype = machine\n\n"
        f"[containers]\n0 = {name}_user\n1 = empty_quality_changes\n2 = empty_intent\n"
        f"3 = apri3_pla_fast\n4 = empty_material\n5 = empty_variant\n6 = {name}_settings\n"
        f"7 = {definition}\n",
        encoding="utf-8",
    )


def test_cura_names_its_active_machine_with_nozzle_and_spool(
    cura: Path, cura_bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auf den Drucker, der in Cura aktiv ist, setzt Cura ein importiertes Profil um.

    ``cura.cfg`` nennt ihn, sein Stapel die Definition, das erste Fach Düse und
    Spule — die Spule über ihre abgeleitete Kennung. Die andere Maschine
    bleibt draußen (Prüfbericht Cura, B9).
    """
    root = _cura_konfiguration(tmp_path, monkeypatch)
    _cura_maschine(root, "Andere Maschine", "ohne_angabe")
    _cura_maschine(root, "Meine Werkstatt", "abax_pri3")
    active_instance = next(
        path
        for path in (root / "machine_instances").glob("*.global.cfg")
        if "id = Meine Werkstatt" in path.read_text(encoding="utf-8")
    )
    active_instance.write_text(
        active_instance.read_text(encoding="utf-8").replace(
            "name = Meine Werkstatt", "name = Drucker am Fenster"
        ),
        encoding="utf-8",
    )
    stack = root / "extruders" / "meine+werkstatt_0.extruder.cfg"
    stack.write_text(
        stack.read_text(encoding="utf-8").replace("5 = empty_variant", "5 = abax_pri3_0.4"),
        encoding="utf-8",
    )
    variant = cura_bestand / "variants" / "abax" / "abax_pri3_0.4.inst.cfg"
    variant.parent.mkdir(parents=True)
    variant.write_text(
        "[general]\ndefinition = abax_pri3\nname = 0.4mm Nozzle\nversion = 4\n\n"
        "[metadata]\nhardware_type = nozzle\ntype = variant\n",
        encoding="utf-8",
    )

    assert sp.cura_active_machine(cura) == sp.CuraActiveMachine(
        name="Drucker am Fenster",
        definition=cura_bestand / "definitions" / "abax_pri3.def.json",
        variant="0.4mm Nozzle",
        material_type="PLA",
    )


@pytest.fixture
def cura_configured_printers(
    cura_bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    root = _cura_konfiguration(tmp_path, monkeypatch)
    _write(
        cura_bestand / "definitions" / "fdmprinter.def.json",
        {
            "name": "FDM Drucker",
            "metadata": {"visible": False},
            "overrides": {
                "machine_width": {"default_value": 200},
                "machine_depth": {"default_value": 180},
                "machine_height": {"default_value": 210},
                "machine_extruder_count": {"default_value": 1},
            },
        },
    )
    _write(
        cura_bestand / "definitions" / "fdmextruder.def.json",
        {
            "name": "Extruder",
            "metadata": {"visible": False},
            "settings": {},
        },
    )
    for name in ("Meine Werkstatt", "Andere Maschine"):
        _cura_maschine(root, name, "abax_pri3")
        for folder, suffix, values in (
            ("user", "user", ""),
            (
                "definition_changes",
                "settings",
                "machine_width = 240\nmachine_depth = 230\nmachine_height = 260\n"
                "machine_extruder_count = 2"
                if name == "Meine Werkstatt"
                else "",
            ),
        ):
            target = root / folder / f"{name.replace(' ', '+')}_{suffix}.inst.cfg"
            target.parent.mkdir(exist_ok=True)
            target.write_text(
                f"[general]\nname = {name}_{suffix}\n[values]\n{values}\n", encoding="utf-8"
            )
    stack = root / "extruders" / "meine+werkstatt_0.extruder.cfg"
    stack.write_text(
        stack.read_text(encoding="utf-8").replace("5 = empty_variant", "5 = abax_0.6"),
        encoding="utf-8",
    )
    variant = cura_bestand / "variants" / "abax_0.6.inst.cfg"
    variant.parent.mkdir(exist_ok=True)
    variant.write_text(
        "[general]\nname = 0.6mm Nozzle\n[values]\nmachine_nozzle_size = 0.6\n", encoding="utf-8"
    )
    return root


def test_discovery_reads_all_configured_cura_machines_and_the_actual_nozzle(
    cura: Path,
    cura_configured_printers: Path,
) -> None:
    found = {printer.title: printer for printer in sp.discover_printers(cura, "cura")}
    assert {"Abax PRi3", "Meine Werkstatt", "Andere Maschine"} <= found.keys()
    chosen = found["Meine Werkstatt"]
    assert chosen.build_volume == pytest.approx((240, 230, 260))
    assert chosen.nozzle_diameter == pytest.approx(0.6)
    assert chosen.nozzles == 2
    assert chosen.cura_definition == "abax_pri3"
    assert chosen.id != found["Andere Maschine"].id != found["Abax PRi3"].id
    assert sp.chosen_machine("cura", cura) == "cura-instance:Meine Werkstatt"
    assert sp.chosen_printer("cura", cura, {p.id: p for p in found.values()}) == chosen.id
    machine, _process = sp.match(sp.find_profiles(cura, "cura"), chosen)
    assert machine is not None and machine.cura_instance is not None
    assert sp.identity(machine) == sp.chosen_machine("cura", cura)
    assert machine.nozzle == pytest.approx(chosen.nozzle_diameter)


def test_cura_factory_definition_resolves_only_one_known_solidon_printer(
    cura: Path, cura_configured_printers: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = sp.SlicerProfile(
        path=cura / "share" / "cura" / "resources" / "definitions" / "abax_pri3.def.json",
        name="Abax PRi3",
        kind="machine",
        printer_model="abax_pri3",
    )
    monkeypatch.setattr(sp, "chosen_machine", lambda *_args: "factory")
    monkeypatch.setattr(sp, "profile_by_name", lambda *_args: factory)
    printer = PrinterProfile(
        id="solidon-abax",
        title="Abax PRi3",
        build_volume=(240.0, 230.0, 260.0),
        cura_definition="abax_pri3",
    )
    assert sp.chosen_printer("cura", cura, {printer.id: printer}) == printer.id

    duplicate = replace(printer, id="another-abax-profile", title="Abax angepasst")
    assert sp.chosen_printer("cura", cura, {printer.id: printer, duplicate.id: duplicate}) == ""

    unrelated = replace(printer, cura_definition="other_definition")
    assert sp.chosen_printer("cura", cura, {unrelated.id: unrelated}) == ""

    configured = replace(
        factory,
        printer_id="slicer-cura-active-instance",
        cura_instance=cura_configured_printers / "machine_instances" / "active.global.cfg",
    )
    monkeypatch.setattr(sp, "profile_by_name", lambda *_args: configured)
    other_instance = replace(printer, id="slicer-cura-other-instance")
    assert sp.chosen_printer("cura", cura, {other_instance.id: other_instance}) == ""


def test_same_named_cura_instance_does_not_override_selected_factory_definition(
    tmp_path: Path,
) -> None:
    """Ein freier Instanzname darf keine andere Cura-Definition verdrängen."""
    factory = sp.SlicerProfile(
        path=tmp_path / "resources" / "definitions" / "model_a.def.json",
        name="Modell A 0.4 nozzle",
        kind="machine",
        printer_model="model_a",
        nozzle=0.4,
    )
    other_instance = sp.SlicerProfile(
        path=tmp_path / "user" / "machine_instances" / "machine_b.global.cfg",
        name="Modell A",
        kind="machine",
        printer_model="model_b",
        nozzle=0.6,
        section="Maschine B",
        from_user=True,
        cura_instance=tmp_path / "user" / "machine_instances" / "machine_b.global.cfg",
    )
    printer = PrinterProfile(
        id="solidon-model-a",
        title="Modell A",
        build_volume=(200.0, 180.0, 200.0),
        nozzle_diameter=0.4,
        cura_definition="model_a",
    )

    machine, _process = sp.match([other_instance, factory], printer)

    assert machine is factory


def test_cura_printer_selection_survives_a_display_name_change(
    cura: Path,
    cura_configured_printers: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Alte Nutzer- und Projektkennungen bleiben nach einer Cura-Umbenennung zugeordnet."""
    import hashlib

    from app.core import discover
    from app.core.export import handover
    from app.core.knowledge import print_settings
    from app.core.scene import project

    original_user_profiles_dir = profiles.user_profiles_dir

    def restore_profile_cache() -> None:
        profiles.user_profiles_dir = original_user_profiles_dir
        profiles.reload()

    request.addfinalizer(restore_profile_cache)

    def old_identifier(machine_id: str, title: str) -> str:
        identity = (discover.program_mark(cura.name), "cura", "", machine_id, title)
        digest = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return f"slicer-cura-{digest[:20]}"

    user_profiles = tmp_path / "user-profiles"
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: user_profiles)
    profiles.reload()
    before = {printer.id: printer for printer in sp.discover_printers(cura, "cura")}
    selected = before[sp.chosen_printer("cura", cura, before)]
    other = next(printer for printer in before.values() if printer.title == "Andere Maschine")
    previous_id = old_identifier("Meine Werkstatt", "Meine Werkstatt")
    other_previous_id = old_identifier("Andere Maschine", "Andere Maschine")
    assert previous_id == "slicer-cura-417d70edad598890e4fd"
    assert previous_id != other_previous_id
    saved_printer = profiles.save_printer(replace(selected, id=previous_id))
    profiles.save_printer(replace(other, id=other_previous_id))
    profiles.reload()
    source_mark = discover.program_mark(cura.name)
    primary_entry = next(
        entry
        for entry in sp.find_profiles(cura, "cura", ("machine",))
        if entry.section == "Meine Werkstatt"
    )
    assert sp.matches_saved_cura_printer(primary_entry, saved_printer, source_mark)
    assert not sp.matches_saved_cura_printer(
        primary_entry, replace(saved_printer, title="Werkstatt neu"), source_mark
    )
    assert not sp.matches_saved_cura_printer(
        primary_entry, replace(saved_printer, cura_definition="other.def.json"), source_mark
    )

    profile = Profile(printer=saved_printer, material=profiles.material("pla"))
    native = sp.chosen_machine("cura", cura)
    setup = handover.SlicerSetup(cura, "cura", machine_profile=native)
    implicit_setup = replace(setup, machine_profile="")
    known = {**profiles.printer_profiles(), **before}
    assert sp.chosen_printer("cura", cura, known) == previous_id
    assert handover.machine_for(setup, profile) == native
    assert handover.machine_for(implicit_setup, profile) == native

    project_path = project.save(
        project.new_project(previous_id, profile.material.id), tmp_path / "vor-f04.p3d"
    )
    opened = project.load(project_path)
    assert opened.document.printer == previous_id
    carried_printers = opened.document.carried_profiles.get(profiles.CARRIED_PRINTERS, {})
    assert set(carried_printers) == {previous_id}

    before_directory = tmp_path / "before"
    before_directory.mkdir()
    before_written = handover.write_config(
        print_settings.resolve(profile), profile, setup, before_directory
    )
    assert before_written.cura_machine is not None

    for machine_path in (cura_configured_printers / "machine_instances").glob("*.global.cfg"):
        original = machine_path.read_text(encoding="utf-8")
        machine_id = "Meine Werkstatt" if "id = Meine Werkstatt" in original else "Andere Maschine"
        old_name = machine_id
        renamed = original.replace(f"name = {old_name}", "name = Werkstatt neu", 1)
        assert renamed != original
        machine_path.write_text(renamed, encoding="utf-8")

    after = {printer.id: printer for printer in sp.discover_printers(cura, "cura")}
    renamed = [printer for printer in after.values() if printer.title == "Werkstatt neu"]
    assert len(renamed) == 2
    assert len({printer.id for printer in renamed}) == 2
    known = {**profiles.printer_profiles(), **after}
    assert sp.chosen_printer("cura", cura, known) == previous_id
    assert handover.machine_for(setup, profile) == native
    assert handover.machine_for(implicit_setup, profile) == native
    machine_profiles = sp.find_profiles(cura, "cura", ("machine",))
    matched, _process = sp.match(
        machine_profiles,
        profiles.printer_profiles()[previous_id],
        source=source_mark,
    )
    assert matched is not None and matched.section == "Meine Werkstatt"
    other_matched, _process = sp.match(
        machine_profiles,
        profiles.printer_profiles()[other_previous_id],
        source=source_mark,
    )
    assert other_matched is not None and other_matched.section == "Andere Maschine"
    stale_setup = replace(setup, machine_profile="cura-instance:unknown")
    fallback = handover._cura_machine(stale_setup, profile, {})
    assert fallback.from_printer
    assert fallback.definition.name == "abax_pri3.def.json"

    after_directory = tmp_path / "after"
    after_directory.mkdir()
    written = handover.write_config(
        print_settings.resolve(profile), profile, setup, after_directory
    )
    assert written.cura_machine is not None
    assert written.cura_machine.definition.name == "abax_pri3.def.json"

    restored = profiles.project_profile(
        opened.document.printer,
        opened.document.material,
        opened.document.carried_profiles,
    )
    assert restored.printer.id == previous_id
    assert handover.machine_for(implicit_setup, restored) == native

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path / "second-computer")
    profiles.reload()
    portable = profiles.project_profile(
        opened.document.printer,
        opened.document.material,
        opened.document.carried_profiles,
    )
    assert portable.printer.id == previous_id
    assert handover.machine_for(implicit_setup, portable) == native
    portable_directory = tmp_path / "portable"
    portable_directory.mkdir()
    portable_written = handover.write_config(
        print_settings.resolve(portable), portable, implicit_setup, portable_directory
    )
    assert portable_written.cura_machine is not None


def test_cura_instance_with_factory_name_keeps_its_own_identity(
    cura: Path, cura_configured_printers: Path
) -> None:
    """Der Anzeigename darf die aktive Maschine nicht durch die Werksmaße ersetzen."""
    for path in (cura_configured_printers / "machine_instances").glob("*.global.cfg"):
        text = path.read_text(encoding="utf-8")
        if "id = Meine Werkstatt" in text:
            path.write_text(
                text.replace("name = Meine Werkstatt", "name = Abax PRi3"), encoding="utf-8"
            )
    found = {entry.id: entry for entry in sp.discover_printers(cura, "cura")}
    chosen = found[sp.chosen_printer("cura", cura, found)]
    assert chosen.title == "Abax PRi3"
    assert chosen.build_volume == pytest.approx((240, 230, 260))
    machine, _process = sp.match(sp.find_profiles(cura, "cura"), chosen)
    assert machine is not None and machine.section == "Meine Werkstatt"
    factory = next(
        entry for entry in found.values() if entry.title == "Abax PRi3" and entry.id != chosen.id
    )
    factory_machine, _process = sp.match(sp.find_profiles(cura, "cura"), factory)
    assert factory_machine is not None and factory_machine.cura_instance is None


def test_cura_definition_matches_a_renamed_solidon_printer(cura: Path) -> None:
    printer = PrinterProfile(
        id="werkstatt",
        title="Meine Werkstatt",
        build_volume=(200, 180, 210),
        cura_definition="abax_pri3",
    )
    machine, _process = sp.match(sp.find_profiles(cura, "cura"), printer)
    assert machine is not None and machine.printer_model == "abax_pri3"


def _cura_seam_back(width: float, depth: float, *, centre_is_zero: bool) -> tuple[float, float]:
    """Curas eigene Formel für die Naht „hinten“ (``fdmprinter.def.json``, Cura 5.13).

    ``z_seam_x`` ist bei ``z_seam_position = back`` ``machine_width / 2``,
    ``z_seam_y`` ``machine_depth``; beide abzüglich der halben Bettgröße, wenn
    ``z_seam_relative`` oder ``machine_center_is_zero`` gilt. Solidon schreibt
    ``z_seam_relative`` nicht, es bleibt bei Curas ``false``.
    """
    x = width / 2.0 - (width / 2.0 if centre_is_zero else 0.0)
    y = depth - (depth / 2.0 if centre_is_zero else 0.0)
    return x, y


def test_cura_instance_hardware_and_codes_reach_the_engine(
    cura: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    """Das echte Schreiben übernimmt DefinitionChanges und Nutzercontainer als Daten."""
    from app.core.export import handover
    from app.core.knowledge import print_settings

    path = cura_configured_printers / "user" / "Meine+Werkstatt_user.inst.cfg"
    path.write_text(
        "[general]\nname = Meine Werkstatt\n[values]\n"
        "machine_start_gcode = G28\n  M117 Werkstatt\n  M109 S{material_print_temperature}\n"
        "machine_end_gcode = M84\n  M117 Fertig\n"
        "machine_center_is_zero = true\nmachine_gcode_flavor = RepRap (Marlin/Sprinter)\n",
        encoding="utf-8",
    )
    found = {p.id: p for p in sp.discover_printers(cura, "cura")}
    printer = found[sp.chosen_printer("cura", cura, found)]
    assert printer.bed_origin == (0.0, 0.0), "der Nutzercontainer legt den Ursprung in die Mitte"
    profile = Profile(printer=printer, material=profiles.material("pla"))
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(cura, "cura", machine_profile=sp.chosen_machine("cura", cura))
    written = handover.write_config(settings, profile, setup, tmp_path)
    command = handover._command(setup, [tmp_path / "part.stl"], written, tmp_path)

    assert written.written["machine_width"] == "240"
    assert written.written["machine_depth"] == "230"
    assert written.written["machine_height"] == "260"
    assert written.written["machine_nozzle_size"] == "0.6"
    assert written.written["machine_center_is_zero"] == "true"
    assert written.origin_at_centre
    seam = (float(written.written["z_seam_x"]), float(written.written["z_seam_y"]))
    assert seam == pytest.approx(_cura_seam_back(240.0, 230.0, centre_is_zero=True))
    assert seam == pytest.approx((0.0, 115.0)), "hinten in der Mitte, um die Bettmitte gemessen"
    assert (
        f"machine_start_gcode=G28\nM117 Werkstatt\nM109 S{settings.temperature.nozzle}" in command
    )
    assert "machine_end_gcode=M84\nM117 Fertig" in command
    assert written.cura_machine is not None
    assert written.cura_machine.definition.name == "abax_pri3.def.json"

    # Auch eine alte explizite Auswahl darf keinen fremden Maschinenstapel
    # einschleusen, obwohl seine portable Kennung keinen Modellnamen trägt.
    other = replace(setup, machine_profile="cura-instance:Andere Maschine")
    assert handover.machine_for(other, profile) == ""
    corrected = handover.write_config(settings, profile, other, tmp_path)
    assert corrected.cura_machine is not None
    assert corrected.cura_machine.codes == written.cura_machine.codes


def test_cura_instance_stays_usable_when_solidon_nozzle_changes(
    cura: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    """Die native Instanz bleibt Maschine, auch wenn Solidon eine andere Düse wählt."""
    from app.core.export import handover
    from app.core.knowledge import print_settings

    found = {printer.id: printer for printer in sp.discover_printers(cura, "cura")}
    printer = replace(found[sp.chosen_printer("cura", cura, found)], nozzle_diameter=0.4)
    profile = Profile(printer=printer, material=profiles.material("pla"))
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(cura, "cura")

    written = handover.write_config(settings, profile, setup, tmp_path)

    assert written.cura_machine is not None and written.cura_machine.from_printer
    assert written.written["machine_nozzle_size"] == "0.4"


def test_cura_factory_definition_stays_the_machine_when_solidon_nozzle_changes(
    cura: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    """In Cura ist die Düse ein Wert der Maschine, keine eigene Maschinendatei.

    Die Familienregel aus :func:`sp.match` („ohne passende Variante bleibt die
    Auswahl leer“) gilt Slicern, deren Maschinenprofile je Düse getrennt
    liegen. Eine Cura-Definition hat keine solchen Geschwister — bei anderer
    Düse sagte die Übergabe sonst, der Drucker sei in Cura nicht eingerichtet.
    """
    from app.core.export import handover
    from app.core.knowledge import print_settings

    found = {printer.title: printer for printer in sp.discover_printers(cura, "cura")}
    assert found["Abax PRi3"].nozzle_diameter == pytest.approx(0.4)
    printer = replace(found["Abax PRi3"], nozzle_diameter=0.6)

    machine, _process = sp.match(sp.find_profiles(cura, "cura"), printer)
    assert machine is not None and machine.cura_instance is None
    assert machine.printer_model == "abax_pri3"

    profile = Profile(printer=printer, material=profiles.material("pla"))
    written = handover.write_config(
        print_settings.resolve(profile), profile, handover.SlicerSetup(cura, "cura"), tmp_path
    )
    assert written.cura_machine is not None and written.cura_machine.from_printer
    assert written.cura_machine.definition.name == "abax_pri3.def.json"
    assert written.written["machine_nozzle_size"] == "0.6"


@pytest.mark.parametrize(
    ("file_name", "shown"),
    [
        ("Snapmaker+2.0+A350.global.cfg", "Snapmaker 2.0 A350"),
        ("Snapmaker+2.0+A350_settings.inst.cfg", "Snapmaker 2.0 A350_settings"),
        ("snapmaker_2.0_a350.def.json", "snapmaker_2.0_a350"),
        ("Snapmaker 2.0 A350.json", "Snapmaker 2.0 A350"),
        ("Snapmaker 2.0 A350.ini", "Snapmaker 2.0 A350"),
    ],
)
def test_an_incomplete_profile_keeps_its_whole_name(file_name: str, shown: str) -> None:
    """Der Name im Satz ist der Name des Profils, ohne Curas Doppelendung und Kodierung."""
    error = sp._incomplete_profile(Path("bestand") / file_name)

    assert f"„{shown}“" in str(error.detail)


def _centred_cura_definition(cura_bestand: Path) -> None:
    """Eine Werksdefinition mit dem Ursprung in der Bettmitte, wie Curas Deltas.

    Die Düse erbt sie, wie die Malyan M180 oder die Kossel Mini in Cura 5.13:
    Die eigene Datei nennt keine, und ihr Eintrag trägt deshalb ``nozzle`` 0.
    """
    _write(
        cura_bestand / "definitions" / "zentrum_basis.def.json",
        {
            "version": 2,
            "name": "Zentrum Basis",
            "inherits": "fdmprinter",
            "metadata": {"visible": False},
            "overrides": {"machine_nozzle_size": {"default_value": 0.4}},
        },
    )
    _write(
        cura_bestand / "definitions" / "zentriert.def.json",
        {
            "version": 2,
            "name": "Zentriert Delta",
            "inherits": "zentrum_basis",
            "metadata": {"visible": True, "manufacturer": "Zentrum"},
            "overrides": {"machine_center_is_zero": {"default_value": True}},
        },
    )


def test_cura_definition_with_its_origin_in_the_middle_keeps_it(
    cura: Path, cura_bestand: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    """Der Ursprung gehört der Maschine (RM-330): Eine Definition mit
    ``machine_center_is_zero`` behält ihn, die Naht folgt Curas Formel, und eine
    Definition mit Ursprung an der Ecke bleibt an der Ecke."""
    from app.core.export import handover
    from app.core.knowledge import print_settings

    _centred_cura_definition(cura_bestand)
    found = {printer.title: printer for printer in sp.discover_printers(cura, "cura")}
    for title, centred in (("Zentriert Delta", True), ("Abax PRi3", False)):
        # Auch bei eigener, nur geerbter Düse bleibt die Definition die
        # Maschine. Vor RM-329 fiel so fast jede Cura-Werksdefinition heraus.
        machine, _process = sp.match(sp.find_profiles(cura, "cura"), found[title])
        assert machine is not None and machine.name == title
        # Der Drucker trägt denselben Ursprung wie seine Definition (RM-424).
        assert found[title].bed_origin == ((0.0, 0.0) if centred else None), title
        profile = Profile(printer=found[title], material=profiles.material("pla"))
        width, depth, _height = profile.printer.build_volume
        directory = tmp_path / title
        directory.mkdir()
        written = handover.write_config(
            print_settings.resolve(profile), profile, handover.SlicerSetup(cura, "cura"), directory
        )

        assert written.origin_at_centre is centred, title
        assert written.written["machine_center_is_zero"] == ("true" if centred else "false")
        seam = (float(written.written["z_seam_x"]), float(written.written["z_seam_y"]))
        assert seam == pytest.approx(_cura_seam_back(width, depth, centre_is_zero=centred)), title


def test_centred_cura_machine_measures_the_print_around_its_origin(
    cura: Path, cura_configured_printers: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CuraEngine verschiebt das Modell nur ohne ``machine_center_is_zero`` um
    das halbe Bett (``MeshGroup::finalize``). Ein Quadrat von 20 mm um die
    Mitte liegt an einer zentrierten Maschine bei -10..10 — und das ist auf
    dem Bett. Die Gegenprobe maß bis RM-330 trotzdem gegen 0..Breite."""
    from app.core.export import handover
    from app.core.knowledge import print_settings

    user = cura_configured_printers / "user" / "Meine+Werkstatt_user.inst.cfg"
    user.write_text(
        "[general]\nname = Meine Werkstatt\n[values]\nmachine_center_is_zero = True\n",
        encoding="utf-8",
    )
    found = {printer.id: printer for printer in sp.discover_printers(cura, "cura")}
    printer = found[sp.chosen_printer("cura", cura, found)]
    profile = Profile(printer=printer, material=profiles.material("pla"))
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    square = "G90\nM82\nG1 Z0.2 F300\nG0 X-10 Y-10\n" + "".join(
        f"G1 X{x:g} Y{y:g} E{index + 1}\n"
        for index, (x, y) in enumerate(((10, -10), (10, 10), (-10, 10), (-10, -10)))
    )

    def slices(command: list[str], *_args: object, **_kwargs: object) -> object:
        Path(command[command.index("-o") + 1]).write_text(square, encoding="utf-8")
        return type("Finished", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

    monkeypatch.setattr(handover, "_run_slicer", slices)
    output = tmp_path / "zentriert"
    output.mkdir()
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(cura, "cura"),
        output_dir=output,
    )
    assert not [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]

    # Gegenprobe: Dieselbe Datei an einer Maschine mit Ursprung an der Ecke
    # liegt halb vor und links neben dem Bett.
    user.write_text("[general]\nname = Meine Werkstatt\n[values]\n", encoding="utf-8")
    output = tmp_path / "ecke"
    output.mkdir()
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(cura, "cura"),
        output_dir=output,
    )
    beyond = [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]
    assert beyond and beyond[0].values["excess_mm"] == pytest.approx(10.0)


def test_missing_cura_instance_has_its_own_error_and_keeps_the_full_printer_name(
    cura: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    from app.core.errors import ExternalToolError
    from app.core.export import handover
    from app.core.knowledge import print_settings

    found = {printer.id: printer for printer in sp.discover_printers(cura, "cura")}
    printer = replace(found[sp.chosen_printer("cura", cura, found)], title="Snapmaker 2.0 A350")
    profile = Profile(printer=printer, material=profiles.material("pla"))
    instance = next(
        path
        for path in (cura_configured_printers / "machine_instances").glob("*.global.cfg")
        if "id = Meine Werkstatt" in path.read_text(encoding="utf-8")
    )
    instance.unlink()

    with pytest.raises(ExternalToolError) as caught:
        handover.write_config(
            print_settings.resolve(profile), profile, handover.SlicerSetup(cura, "cura"), tmp_path
        )

    assert "nicht eingerichtet" in str(caught.value.detail).casefold()
    assert "Snapmaker 2.0 A350" in str(caught.value.detail)
    assert "Snapmaker 2 A350" not in str(caught.value.detail)
    assert [action.id for action in caught.value.suggestions] == ["check_profile", "choose_printer"]


def test_same_machine_from_two_slicers_keeps_the_selected_printer(
    unknown_printers: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gleicher Titel ist dasselbe Gerät, aber kein Auftrag zum Wechsel der Quell-ID."""
    from app.core.export import handover

    first = sp.discover_printers(unknown_printers, "orca")[0]
    second = sp.discover_printers(unknown_printers.with_name("BambuStudio.exe"), "orca")[0]
    known = {first.id: first, second.id: second}
    assert first.id != second.id and first.title == second.title
    monkeypatch.setattr(profiles, "printer_profiles", lambda: known)
    monkeypatch.setattr(sp, "chosen_machine", lambda *_args: first.title)
    profile = Profile(printer=second, material=profiles.material("pla"))
    setup = handover.SlicerSetup(unknown_printers, "orca", machine_profile=first.title)
    assert handover._fits_the_printer(first.title, profile)
    assert handover.machine_for(setup, profile) == first.title
    assert handover.machine_for(replace(setup, machine_profile=""), profile) == first.title
    wrong = PrinterProfile(id="wrong", title="Other printer", build_volume=(100, 100, 100))
    assert not handover._fits_the_printer(first.title, replace(profile, printer=wrong))


def test_removed_cura_instance_never_silently_uses_factory_codes(
    cura: Path, cura_configured_printers: Path, tmp_path: Path
) -> None:
    """Fehlt der gespeicherte Stapel, sind Herstellerdefaults kein Ersatz."""
    from app.core.errors import ExternalToolError
    from app.core.export import handover
    from app.core.knowledge import print_settings

    found = {p.id: p for p in sp.discover_printers(cura, "cura")}
    printer = replace(found[sp.chosen_printer("cura", cura, found)], title="Snapmaker 2.0 A350")
    profile = Profile(printer=printer, material=profiles.material("pla"))
    path = cura_configured_printers / "definition_changes" / "Meine+Werkstatt_settings.inst.cfg"
    path.write_text(
        "[general]\nname = Unvollständig\n[values]\nmachine_width = =unknown\n", encoding="utf-8"
    )
    assert sp.match(sp.find_profiles(cura, "cura"), printer) == (None, None)
    with pytest.raises(ExternalToolError) as caught:
        handover.write_config(
            print_settings.resolve(profile), profile, handover.SlicerSetup(cura, "cura"), tmp_path
        )
    assert caught.value.suggestions
    assert "solidon" in str(caught.value.title).casefold()
    assert "nicht vollständig auswerten" in str(caught.value.title).casefold()
    assert "Snapmaker 2.0 A350" in str(caught.value.detail)
    assert "Snapmaker 2 A350" not in str(caught.value.detail)


@pytest.mark.parametrize(
    "change", ["formula", "missing_variant", "missing_extruder", "invalid_count"]
)
def test_incomplete_cura_instance_does_not_fall_back_to_manufacturer_defaults(
    cura: Path,
    cura_configured_printers: Path,
    change: str,
) -> None:
    root = cura_configured_printers
    if change == "formula":
        path = root / "definition_changes" / "Meine+Werkstatt_settings.inst.cfg"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "machine_width = 240", "machine_width = =200 + 40"
            ),
            encoding="utf-8",
        )
    else:
        path = root / "extruders" / "meine+werkstatt_0.extruder.cfg"
        replacements = {
            "missing_variant": ("abax_0.6", "nicht_vorhanden"),
            "missing_extruder": ("fdmextruder", "nicht_vorhanden"),
            "invalid_count": ("position = 0", "position = 3"),
        }
        before, after = replacements[change]
        path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
    names = {printer.title for printer in sp.discover_printers(cura, "cura")}
    assert "Meine Werkstatt" not in names
    assert "Andere Maschine" in names


def test_cura_names_the_bed_of_its_active_machine(
    cura: Path, cura_bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Curas 3MF-Leser zieht beim Öffnen die halbe Bettgröße der aktiven Maschine ab.

    Das Maß steht in der Erbkette der Definition; was der Nutzer in den
    Maschineneinstellungen ändert, steht im Container an Stelle sechs
    (``_ContainerIndexes.DefinitionChanges``) und geht vor.
    """
    root = _cura_konfiguration(tmp_path, monkeypatch)
    _cura_maschine(root, "Meine Werkstatt", "abax_pri3")
    _write(
        cura_bestand / "definitions" / "fdmprinter.def.json",
        {
            "version": 2,
            "name": "FDM Drucker",
            "metadata": {"visible": False},
            "settings": {
                "machine_settings": {
                    "children": {
                        "machine_width": {"default_value": 100},
                        "machine_depth": {"default_value": 100},
                    }
                }
            },
        },
    )
    _write(
        cura_bestand / "definitions" / "abax_pri3.def.json",
        {
            "version": 2,
            "name": "Abax PRi3",
            "inherits": "fdmprinter",
            "metadata": {"visible": True, "manufacturer": "Abax 3D Technologies"},
            "overrides": {"machine_width": {"default_value": 220}},
        },
    )

    found = sp.cura_active_machine(cura)
    assert found is not None
    assert found.bed == (220.0, 100.0), "die Breite vom Drucker, die Tiefe aus der Wurzel"

    changes = root / "definition_changes"
    changes.mkdir()
    (changes / "Meine+Werkstatt_settings.inst.cfg").write_text(
        "[general]\nversion = 4\nname = Meine Werkstatt_settings\ndefinition = abax_pri3\n\n"
        "[metadata]\ntype = definition_changes\nsetting_version = 27\n\n"
        "[values]\nmachine_depth = 250\n",
        encoding="utf-8",
    )
    found = sp.cura_active_machine(cura)
    assert found is not None
    assert found.bed == (220.0, 250.0), "die Maschineneinstellungen des Nutzers gehen vor"


def test_cura_without_a_set_up_printer_names_no_machine(
    cura: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keine aktive Maschine, oder eine ohne Stapel: keine Maschine, kein Fehler."""
    root = _cura_konfiguration(tmp_path, monkeypatch)

    assert sp.cura_active_machine(cura) is None, "cura.cfg nennt eine Maschine ohne Stapel"
    _cura_maschine(root, "Meine Werkstatt", "gibt_es_nicht")
    assert sp.cura_active_machine(cura) is None, "eine Definition, die nirgends liegt"


def test_cura_without_an_active_machine_names_no_spools(
    cura: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne aktive Maschine gibt es keine Belegung — und keinen Fehler."""
    root = _cura_konfiguration(tmp_path, monkeypatch)
    (root / "cura.cfg").write_text("[general]\nversion = 7\n", encoding="utf-8")

    assert sp.configured_filaments("cura", cura) == ()


def test_a_cura_file_that_is_not_utf8_is_skipped_not_fatal(
    cura: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Konfigurationsdatei in fremder Kodierung ist kein Absturz der Filamentsuche.

    ``_read_ini`` fing ``OSError`` und ``configparser.Error``, aber nicht
    ``UnicodeDecodeError`` — eine ``cura.cfg`` in Latin-1 mit einem Umlaut im
    Maschinennamen riss die Suche im Druckdialog ab (Durchsicht 0.5.0).
    """
    root = _cura_konfiguration(tmp_path, monkeypatch)
    (root / "cura.cfg").write_bytes("[cura]\nactive_machine = Gerät\n".encode("latin-1"))

    assert sp.configured_filaments("cura", cura) == ()


def test_cura_knows_which_quality_types_a_machine_offers(cura: Path, cura_bestand: Path) -> None:
    """Ein importiertes Profil muss eine Qualitätsstufe nennen, die es gibt.

    Maschinen ohne eigene Qualitäten nehmen die allgemeinen von
    ``fdmprinter``; eine mit ``has_machine_quality`` die ihrer
    ``quality_definition`` — auch geerbt. Und die Einstellungsversion steht
    in ``fdmprinter.def.json``.
    """
    _write(
        cura_bestand / "definitions" / "fdmprinter.def.json",
        {
            "version": 2,
            "name": "FDM Drucker",
            "metadata": {"visible": False, "setting_version": 27},
        },
    )
    _write(
        cura_bestand / "definitions" / "werkstatt_basis.def.json",
        {
            "version": 2,
            "name": "Werkstatt Basis",
            "inherits": "fdmprinter",
            "metadata": {"visible": False, "has_machine_quality": True},
        },
    )
    _write(
        cura_bestand / "definitions" / "werkstatt_eins.def.json",
        {
            "version": 2,
            "name": "Werkstatt Eins",
            "inherits": "werkstatt_basis",
            "metadata": {"quality_definition": "werkstatt_basis"},
        },
    )
    for folder, definition, kind, height in (
        ("", "fdmprinter", "draft", 0.2),
        ("", "fdmprinter", "normal", 0.1),
        ("werkstatt", "werkstatt_basis", "standard", 0.2),
    ):
        target = cura_bestand / "quality" / folder / f"{definition}_{kind}.inst.cfg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"[general]\ndefinition = {definition}\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\n"
            "setting_version = 27\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )

    assert sp.cura_setting_version(cura) == 27
    assert sp.cura_quality_types(cura, None) == {"draft": 0.2, "normal": 0.1}
    eins = cura_bestand / "definitions" / "werkstatt_eins.def.json"
    assert sp.cura_quality_types(cura, eins) == {"standard": 0.2}
    abax = cura_bestand / "definitions" / "abax_pri3.def.json"
    assert sp.cura_quality_types(cura, abax) == {"draft": 0.2, "normal": 0.1}


def test_cura_offers_only_the_qualities_of_nozzle_and_spool(cura: Path, cura_bestand: Path) -> None:
    """Eine Stufe, die es für Düse und Spule nicht gibt, importiert Cura unsichtbar.

    So erging es dem Profil an Creality und Sovol (Prüfbericht Cura, B9): Die
    allgemeine Stufe mit der passenden Schichthöhe gab es, für 0,4 mm und PLA
    aber kein Profil. Liegt für eine Kombination keines, nimmt Cura die
    allgemeinen — dann bleiben alle.
    """
    _write(
        cura_bestand / "definitions" / "werkstatt_basis.def.json",
        {
            "version": 2,
            "name": "Werkstatt Basis",
            "inherits": "fdmprinter",
            "metadata": {"visible": False, "has_machine_quality": True},
        },
    )
    quality = cura_bestand / "quality" / "werkstatt"
    quality.mkdir(parents=True)
    for kind, height in (("fein", 0.2), ("standard", 0.24)):
        (quality / f"werkstatt_global_{kind}.inst.cfg").write_text(
            f"[general]\ndefinition = werkstatt_basis\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )
    (quality / "werkstatt_0.4_pla_standard.inst.cfg").write_text(
        "[general]\ndefinition = werkstatt_basis\nname = Standard\nversion = 4\n\n"
        "[metadata]\nmaterial = generic_pla\nquality_type = standard\ntype = quality\n"
        "variant = 0.4mm Nozzle\n\n[values]\n",
        encoding="utf-8",
    )
    basis = cura_bestand / "definitions" / "werkstatt_basis.def.json"
    alle = {"fein": 0.2, "standard": 0.24}

    assert sp.cura_quality_types(cura, basis) == alle
    assert sp.cura_quality_types(cura, basis, variant="0.4mm Nozzle", material_type="PLA") == {
        "standard": 0.24
    }
    assert sp.cura_quality_types(cura, basis, variant="0.4mm Nozzle", material_type="PETG") == (
        alle
    ), "für PETG liegt kein eigenes Profil"
    assert sp.cura_quality_types(cura, basis, variant="0.6mm Nozzle", material_type="PLA") == (
        alle
    ), "für eine andere Düse ebenso wenig"


# --- PrusaSlicer: eine Datei, ein kopfloser Anfang ---------------------------------


@pytest.fixture
def prusa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """PrusaSlicer samt seiner Anwendungskonfiguration.

    Der Aufbau ist der echte, samt der Eigenheit, die das Bauen gekostet hat:
    Die Datei beginnt mit Schlüsseln **ohne** Abschnittsüberschrift.
    """
    config = tmp_path / "config"
    folder = config / "PrusaSlicer"
    folder.mkdir(parents=True)
    (folder / "PrusaSlicer.ini").write_text(
        "# generated by PrusaSlicer 2.9.6\n"
        "alert_when_supports_needed = 1\n"
        "version = 2.9.6\n"
        "\n"
        "[presets]\n"
        "filament = Prusament PLA\n"
        "filament_1 = Meine Spule\n"
        "print = 0.20mm SPEED\n"
        "printer = Original Prusa MK4S 0.4 nozzle\n"
        "\n"
        "[recent]\n"
        "config_directory = C:\\irgendwo\n",
        encoding="utf-8",
    )
    # Eine selbst angelegte Spule liegt als eigene Datei daneben — und auch sie
    # trägt ihre Werte ohne Abschnittskopf.
    (folder / "filament").mkdir()
    (folder / "filament" / "Meine Spule.ini").write_text(
        "filament_type = PETG\nfilament_colour = #FFA500\ntemperature = 240\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    return executable


def test_the_loaded_prusa_spools_are_read_from_its_ini(prusa: Path) -> None:
    """Bauplan §20 sagt, die eingelegten Filamente würden als Vorwahl
    übernommen. Bis zum 08.09.2026 galt das nur für die Orca-Familie: Für
    PrusaSlicer kam eine leere Liste zurück, obwohl die Auskunft dasteht."""
    found = sp.configured_filaments("prusa", prusa)

    assert [entry.profile for entry in found] == ["Prusament PLA", "Meine Spule"], (
        "beide Extruder, in ihrer Reihenfolge"
    )


def test_an_own_prusa_spool_brings_its_type_and_colour(prusa: Path) -> None:
    """Was als eigene Datei danebenliegt, sagt Art und Farbe selbst."""
    own = next(
        entry for entry in sp.configured_filaments("prusa", prusa) if entry.profile == "Meine Spule"
    )

    assert own.material_type == "PETG"
    assert own.colour == "#FFA500"


def test_a_vendor_spool_stays_a_name_and_is_not_guessed(prusa: Path) -> None:
    """Ein Herstellerpreset wohnt in einem Bündel mit Zehntausenden
    Abschnitten und einer Erbkette. Der Name ist die sichere Auskunft; eine
    erfundene Materialart wäre schlechter als keine (Regel 21)."""
    vendor = next(
        entry
        for entry in sp.configured_filaments("prusa", prusa)
        if entry.profile == "Prusament PLA"
    )

    assert vendor.material_type == ""
    assert vendor.colour == ""


def test_prusa_says_which_printer_was_set(prusa: Path) -> None:
    """Dieselbe Frage wie bei der Orca-Familie, dieselbe Antwortquelle —
    nur heißt sie hier ``[presets] printer``."""
    assert sp.chosen_machine("prusa", prusa) == "Original Prusa MK4S 0.4 nozzle"


def test_a_prusa_ini_without_its_section_is_no_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne ``[presets]`` gibt es nichts zu melden — und keinen Abbruch."""
    config = tmp_path / "config"
    folder = config / "PrusaSlicer"
    folder.mkdir(parents=True)
    (folder / "PrusaSlicer.ini").write_text("version = 2.9.6\n", encoding="utf-8")
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")

    assert sp.configured_filaments("prusa", executable) == ()
    assert sp.chosen_machine("prusa", executable) == ""


def test_prusa_without_a_configuration_stays_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer PrusaSlicer nie gestartet hat, hat keine Konfiguration."""
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(tmp_path / "leer"))
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")

    assert sp.prusa_config(executable) is None
    assert sp.configured_filaments("prusa", executable) == ()


@pytest.fixture(
    params=["missing", "directory", "utf8", "utf8_value", "syntax", "section", "parent", "cycle"]
)
def broken_selected_prusa(tmp_path: Path, request: pytest.FixtureRequest) -> sp.SlicerProfile:
    """Echte Dateifehler am ausdrücklich gewählten Profil, keine Decoder-Attrappe."""
    path = tmp_path / "print" / "Selected.ini"
    path.parent.mkdir()
    contents = {
        "utf8": b"\xff\xfe\xff",
        "utf8_value": b"notes = damaged \xff value\n",
        "syntax": b"[print:Selected\n",
        "section": b"[print:Other]\nlayer_height = 0.2\n",
        "parent": b"inherits = Missing parent\n",
        "cycle": b"[print:Selected]\ninherits = Selected\n",
    }
    if request.param == "directory":
        path.mkdir()
    elif request.param != "missing":
        path.write_bytes(contents[request.param])
    return sp.SlicerProfile(
        path,
        "Selected",
        "process",
        from_user=True,
        section="print:Selected" if request.param in {"section", "cycle"} else "",
    )


def test_selected_prusa_read_failure_is_an_actionable_error(
    broken_selected_prusa: sp.SlicerProfile,
) -> None:
    """Ein gewähltes fehlendes/kaputtes Profil ist kein gültiges leeres Delta."""
    from app.core.errors import ExternalToolError

    with pytest.raises(ExternalToolError) as caught:
        sp.resolve_profile(broken_selected_prusa, (broken_selected_prusa.path.parent.parent,))
    assert caught.value.tool == broken_selected_prusa.path.name
    assert caught.value.suggestions


def test_selected_prusa_read_failure_reaches_foundation_and_written_fallback(
    broken_selected_prusa: sp.SlicerProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quelle und Befund bleiben benannt; der Rückfall schreibt Maschine und Prozess ganz."""
    from app.core.export import handover, manufacturer

    profile = profiles.make_profile("generic-220", "pla")
    machine = tmp_path / "printer" / "Known.ini"
    machine.parent.mkdir()
    machine.write_text("gcode_flavor = marlin2\nnozzle_diameter = 0.4\n", encoding="utf-8")
    setup = handover.SlicerSetup(
        Path("PrusaSlicer.exe"), "prusa", machine_profile="Known", base_process="Selected"
    )
    monkeypatch.setattr(handover, "machine_for", lambda *_args: "Known")
    monkeypatch.setattr(handover, "_profile_roots", lambda *_args: (tmp_path,))
    monkeypatch.setattr(
        handover,
        "profile_source",
        lambda _name, _setup, kind: machine if kind == "machine" else broken_selected_prusa,
    )
    foundation = manufacturer.base_settings(profile, "standard", setup)
    assert not foundation.has_profile
    assert foundation.unreadable == "Selected"
    findings = handover.foundation_findings(foundation.settings, profile, setup)
    finding = next(item for item in findings if item.code == "slicer.process_unreadable")
    assert finding.values["profile"] == "Selected"
    assert finding.suggestions
    directory = tmp_path / "written"
    directory.mkdir()
    config = handover.write_config(foundation.settings, profile, setup, directory)
    text = config.process.read_text(encoding="utf-8")
    assert "nozzle_diameter = 0.4\n" in text
    assert "bed_shape = 0x0,220x0,220x220,0x220\n" in text
    assert f"perimeters = {foundation.settings.shell.wall_count}\n" in text
    assert "print_settings_id = Selected" not in text
    assert "printer_settings_id = Known" not in text


@pytest.mark.parametrize("kind", ["empty_file", "empty_section", "empty_parent", "parent"])
def test_valid_empty_prusa_deltas_and_inheritance_remain_distinct(
    tmp_path: Path, kind: str
) -> None:
    """Vorhandene gültige Leere ist erlaubt; ein benannter Elternabschnitt trägt seine Werte."""
    path = tmp_path / "print" / "Chosen.ini"
    path.parent.mkdir()
    contents = {
        "empty_file": "",
        "empty_section": "[print:Chosen]\n",
        "empty_parent": "[print:Base]\n[print:Chosen]\ninherits = Base\n",
        "parent": "[print:Base]\nlayer_height = 0.17\n[print:Chosen]\ninherits = Base\n",
    }
    path.write_text(contents[kind], encoding="utf-8")
    source = sp.SlicerProfile(
        path,
        "Chosen",
        "process",
        from_user=True,
        section="" if kind == "empty_file" else "print:Chosen",
    )
    assert sp.resolve_profile(source, (tmp_path,)) == (
        {"layer_height": "0.17"} if kind == "parent" else {}
    )


def test_prusa_discovery_skips_bad_files_and_keeps_good_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Bestandsauflistung darf defekte ungewählte Dateien weiter überspringen."""
    folder = tmp_path / "print"
    folder.mkdir()
    (folder / "Bad.ini").write_bytes(b"notes = bad \xff\n")
    (folder / "Good.ini").write_text("layer_height = 0.17\n", encoding="utf-8")
    monkeypatch.setattr(sp, "profile_roots", lambda *_args: (tmp_path,))
    found = sp.find_profiles(Path("PrusaSlicer.exe"), "prusa", ("process",))
    assert [entry.name for entry in found] == ["Good"]


@pytest.mark.parametrize("location", ["without_roots", "outside_roots", "inside_roots"])
@pytest.mark.parametrize("change", ["broken", "deleted", "empty", "value"])
def test_selected_prusa_file_changes_invalidate_cached_values(
    tmp_path: Path, location: str, change: str
) -> None:
    """Eine zuvor lesbare gewählte Datei bleibt auch außerhalb des Bestands überprüfbar."""
    from app.core.errors import ExternalToolError

    folder = tmp_path / "own" / "print"
    folder.mkdir(parents=True)
    path = folder / "Selected.ini"
    path.write_text("layer_height = 0.17\n", encoding="utf-8")
    stock = tmp_path / "stock"
    stock.mkdir()
    roots = {"without_roots": (), "outside_roots": (stock,), "inside_roots": (folder.parent,)}[
        location
    ]
    assert sp.resolve_values(path, roots) == {"layer_height": "0.17"}
    if change == "deleted":
        path.unlink()
    elif change == "broken":
        path.write_bytes(b"notes = damaged \xff value\n")
    else:
        path.write_text("" if change == "empty" else "layer_height = 0.235\n", encoding="utf-8")
    if change in {"broken", "deleted"}:
        with pytest.raises(ExternalToolError):
            sp.resolve_values(path, roots)
    else:
        assert sp.resolve_values(path, roots) == (
            {} if change == "empty" else {"layer_height": "0.235"}
        )


@pytest.fixture
def prusa_cache_bundle(tmp_path: Path) -> sp.SlicerProfile:
    """Ein echter kleiner Bestand, dessen zwei Profile denselben Cache teilen."""
    path = tmp_path / "Maker.ini"
    path.write_text(
        "[print:Base]\nlayer_height = 0.17\n"
        "[print:First]\ninherits = Base\nperimeters = 3\n"
        "[print:Second]\ninherits = Base\nperimeters = 5\n",
        encoding="utf-8",
    )
    return sp.SlicerProfile(path, "First", "process", section="print:First")


@pytest.mark.parametrize("caller", ["resolve", "listing"])
@pytest.mark.parametrize("new_token", [False, True])
def test_prusa_cached_profiles_do_not_keep_a_previous_cancellation(
    prusa_cache_bundle, monkeypatch, caller, new_token
):
    """Ein beendeter Suchauftrag darf den nächsten Profilabruf nicht abbrechen."""
    from app.core.scene.cancel import CancelSignal

    profile = prusa_cache_bundle
    roots = (profile.path.parent,)
    previous = CancelSignal()
    expected = {"layer_height": "0.17", "perimeters": "3"}
    assert sp.resolve_profile(profile, roots, cancelled=previous) == expected
    previous.cancel()
    current = CancelSignal() if new_token else None
    if caller == "resolve":
        assert sp.resolve_profile(profile, roots, cancelled=current) == expected
    else:
        monkeypatch.setattr(sp, "profile_roots", lambda *_args: roots)
        found = sp._prusa_profiles(Path("PrusaSlicer.exe"), frozenset({"process"}), current)
        assert {entry.name for entry in found} == {"Base", "First", "Second"}


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("when", ["before", "during_signature"])
def test_prusa_current_cancellation_stops_cold_and_warm_reads(
    prusa_cache_bundle, monkeypatch, warm, when
):
    """Auch ein bereits gelesener Bestand gehört dem aktuell abbrechenden Auftrag."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    profile = prusa_cache_bundle
    roots = (profile.path.parent,)
    if warm:
        sp.resolve_profile(profile, roots)
    current = CancelSignal()
    if when == "before":
        current.cancel()
    else:
        original = Path.stat

        def cancel_at_file(path, *args, **kwargs):
            status = original(path, *args, **kwargs)
            if path == profile.path:
                current.cancel()
            return status

        monkeypatch.setattr(Path, "stat", cancel_at_file)
    with pytest.raises(OperationCancelled):
        sp.resolve_profile(profile, roots, cancelled=current)


def test_prusa_interrupted_external_read_can_resolve_again(prusa_cache_bundle, monkeypatch):
    """Abgebrochenes Nachlesen hinterlässt keine Datei ohne ihre Erbabschnitte."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    profile = prusa_cache_bundle
    current = CancelSignal()
    original = sp._read_prusa_ini

    def cancel_after_read(path):
        document = original(path)
        current.cancel()
        return document

    with monkeypatch.context() as patch:
        patch.setattr(sp, "_read_prusa_ini", cancel_after_read)
        with pytest.raises(OperationCancelled):
            sp.resolve_profile(profile, cancelled=current)
    assert sp.resolve_profile(profile, cancelled=CancelSignal()) == {
        "layer_height": "0.17",
        "perimeters": "3",
    }


@pytest.mark.parametrize("cancel_first", [False, True])
def test_concurrent_prusa_reads_only_observe_their_own_cancellation(
    prusa_cache_bundle, monkeypatch, cancel_first
):
    """Zwei echte Aufrufe teilen Dateien und Sperre, aber keinen Abbruchschalter."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    first = prusa_cache_bundle
    second = replace(first, name="Second", section="print:Second")
    roots = (first.path.parent,)
    sp.resolve_profile(first, roots)
    first_token, second_token = CancelSignal(), CancelSignal()
    entered, waiting, release = Event(), Event(), Event()
    original_resolve = sp._PrusaStore.resolve
    original_store = sp._prusa_store

    def held_resolve(store, profile, *args, **kwargs):
        if profile.name == "First":
            entered.set()
            assert release.wait(5)
        return original_resolve(store, profile, *args, **kwargs)

    def seen_store(roots, cancelled=None, **kwargs):
        if cancelled is second_token:
            waiting.set()
        return original_store(roots, cancelled, **kwargs)

    monkeypatch.setattr(sp._PrusaStore, "resolve", held_resolve)
    monkeypatch.setattr(sp, "_prusa_store", seen_store)
    with ThreadPoolExecutor(max_workers=2) as workers:
        first_result = workers.submit(sp.resolve_profile, first, roots, cancelled=first_token)
        try:
            assert entered.wait(5)
            second_result = workers.submit(
                sp.resolve_profile, second, roots, cancelled=second_token
            )
            assert waiting.wait(5)
            (first_token if cancel_first else second_token).cancel()
        finally:
            release.set()
        cancelled_result = first_result if cancel_first else second_result
        active_result = second_result if cancel_first else first_result
        with pytest.raises(OperationCancelled):
            cancelled_result.result(timeout=5)
        assert active_result.result(timeout=5) == {
            "layer_height": "0.17",
            "perimeters": "5" if cancel_first else "3",
        }


# --- Welcher Slicer kennt welchen Drucker ------------------------------------------


@pytest.fixture
def prusa_bestand(tmp_path: Path) -> Path:
    """Ein Herstellerbündel, wie PrusaSlicer es ausliefert.

    Die Modelle stehen als eigene Abschnitte darin, zwischen Zehntausenden
    Filament- und Prozessabschnitten — deshalb wird zeilenweise gelesen.
    """
    root = tmp_path / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[vendor]\nname = Prusa Research\n\n"
        "[printer_model:MK4S]\n"
        "name = Original Prusa MK4S\n"
        "variants = 0.4; 0.6\n"
        "technology = FFF\n\n"
        "[printer_model:MINIIS]\n"
        "name = Original Prusa MINI IS\n"
        "variants = 0.4\n\n"
        "[filament:*common*]\ncooling = 1\n\n"
        "[filament:Prusament PLA]\nfilament_type = PLA\n",
        encoding="utf-8",
    )
    (root / "Anker.ini").write_text(
        "[vendor]\nname = Anker\n\n[printer_model:M5]\nname = AnkerMake M5\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def prusa_installiert(prusa_bestand: Path) -> Path:
    """Die Programmdatei über dem Bündelbestand."""
    executable = prusa_bestand.parent.parent / "prusa-slicer.exe"
    executable.write_bytes(b"")
    return executable


def test_prusa_names_the_printers_it_brings_along(prusa_installiert: Path) -> None:
    """Die Frage „welcher Slicer kann meinen Drucker" beantwortet bei
    PrusaSlicer niemand über Profile — es braucht keine. Die Modelle stehen
    trotzdem da, in den Herstellerbündeln."""
    found = sp.known_printers("prusa", prusa_installiert)

    assert sorted(found) == ["AnkerMake M5", "Original Prusa MINI IS", "Original Prusa MK4S"]


def test_a_slicer_knows_a_printer_by_the_start_of_its_name(prusa_installiert: Path) -> None:
    """Der Slicer nennt Düse und Zusätze, Solidon nicht — verglichen wird am
    Anfang, wie in ``printer_for``."""
    assert sp.supports_printer("prusa", prusa_installiert, "Original Prusa MK4S")
    assert not sp.supports_printer("prusa", prusa_installiert, "Elegoo Centauri Carbon 2")


def test_an_empty_printer_title_matches_nothing(prusa_installiert: Path) -> None:
    """Ein leerer Titel passte sonst auf jede Maschine — und damit hieße
    „kennt deinen Drucker" bei einem unbenannten Profil immer ja."""
    assert not sp.supports_printer("prusa", prusa_installiert, "")


def test_the_orca_family_names_the_model_not_the_profile(slicer: Path) -> None:
    """Ein Orca-Profil heißt „Elegoo Centauri Carbon 2 0.4 nozzle" und trägt
    das Modell daneben. Gefragt ist der Drucker, nicht die Düse."""
    assert "Elegoo Centauri Carbon 2" in sp.known_printers("orca", slicer)


def test_cura_names_the_printer_as_it_shows_it(cura: Path) -> None:
    """Cura kennt kein getrenntes Modellfeld; sein Anzeigename *ist* die
    Auskunft.

    Eigene Fixture und nicht die des Orca-Tests daneben: Beide legen ihren
    Bestand sonst in dasselbe Verzeichnis, und ``install_root`` sieht nach
    ``resources/profiles`` vor ``share/cura`` — CuraEngine fände dann den
    Bestand des Nachbarn. Nebeneinander gibt es die beiden nur im Test.
    """
    assert "Abax PRi3" in sp.known_printers("cura", cura)


def test_a_prusa_installation_without_bundles_is_no_crash(tmp_path: Path) -> None:
    """Ohne Bestand keine Modelle — und kein Abbruch."""
    assert sp.known_printers("prusa", tmp_path / "nirgends.exe") == ()


@pytest.fixture
def prusa_mini(tmp_path: Path) -> Path:
    """PrusaSlicer 2.9.6 führt den MINI zweimal: das abgelöste Profil und das
    mit Input Shaper, das es heute vorwählt — jedes mit seinem Standardprozess."""
    root = tmp_path / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[vendor]\nname = Prusa Research\n\n"
        "[printer_model:MINI]\nname = Original Prusa MINI & MINI+\nvariants = 0.4\n\n"
        "[printer_model:MINIIS]\nname = Original Prusa MINI & MINI+ Input Shaper\n"
        "variants = 0.4\n\n"
        "[printer:*common*]\nprinter_technology = FFF\nnozzle_diameter = 0.4\n\n"
        "[printer:Original Prusa MINI & MINI+]\ninherits = *common*\nprinter_model = MINI\n"
        "default_print_profile = 0.15mm QUALITY @MINI\n\n"
        "[printer:Original Prusa MINI & MINI+ Input Shaper]\ninherits = *common*\n"
        "printer_model = MINIIS\ndefault_print_profile = 0.20mm SPEED @MINIIS 0.4\n\n"
        "[print:0.15mm QUALITY @MINI]\nlayer_height = 0.15\n"
        'compatible_printers = "Original Prusa MINI & MINI+"\n\n'
        "[print:0.20mm SPEED @MINIIS 0.4]\nlayer_height = 0.2\n"
        'compatible_printers = "Original Prusa MINI & MINI+ Input Shaper"\n',
        encoding="utf-8",
    )
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    return executable


def test_a_printer_that_names_its_bundle_profile_gets_it(prusa_mini: Path) -> None:
    """Die Namenssuche traf am MINI das abgelöste Profil samt „0.15mm QUALITY
    @MINI", am XL ebenso, und den SV06 gar nicht, weil Sovols Bündel ihn nur
    „SV06" nennt (27.09.2026). ``prusaslicer_printer`` nennt das Profil, das
    PrusaSlicer selbst vorwählt; fehlt es im Bestand, bleibt die Namenssuche."""
    mini = PrinterProfile(
        id="prusa-mini",
        title="Prusa MINI+",
        build_volume=(180.0, 180.0, 180.0),
        prusaslicer_printer="Original Prusa MINI & MINI+ Input Shaper",
    )
    found = sp.find_profiles(prusa_mini, "prusa", ("machine", "process"))

    machine, process = sp.match(found, mini)

    assert machine is not None and machine.name == "Original Prusa MINI & MINI+ Input Shaper"
    assert process is not None and process.name == "0.20mm SPEED @MINIIS 0.4"
    by_name, _process = sp.match(found, replace(mini, prusaslicer_printer=""))
    assert by_name is not None and by_name.name == "Original Prusa MINI & MINI+", "so war es"
    missing, _process = sp.match(found, replace(mini, prusaslicer_printer="Gibt es nicht"))
    assert missing is not None and missing.name == by_name.name, "die Namenssuche als Rückfall"


_MK4S_HF04 = {
    "printer_model": "MK4S",
    "printer_notes": r"Don't remove!\nPRINTER_VENDOR_PRUSA3D\nPRINTER_MODEL_MK4S\nHF_NOZZLE",
    "nozzle_diameter": "0.4",
    "nozzle_high_flow": "1",
    "single_extruder_multi_material": "0",
}


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        # Wörtlich aus PrusaResearch.ini 2.9.6: das PLA des MK4S und das des MK4,
        # das der MK4S als Standard erbt und das trotzdem nicht zu ihm passt.
        (
            "printer_model=~/(MK4S|MK4SMMU3|MK3.9S|MK3.9SMMU3)/ and nozzle_diameter[0]!=0.8 "
            "and nozzle_diameter[0]!=0.6 and nozzle_diameter[0]!=0.5 and nozzle_high_flow[0]",
            True,
        ),
        (
            "printer_model=~/(MK4|MK4IS|MK4ISMMU3|MK3.9|MK3.9MMU3)/ and nozzle_diameter[0]!=0.8 "
            "and nozzle_diameter[0]!=0.6 and nozzle_diameter[0]!=0.5 and nozzle_high_flow[0]",
            False,
        ),
        ('printer_model=="MK4S" and nozzle_diameter[0]=="0.4"', True),
        ("nozzle_diameter[0]>=0.4 and printer_notes=~/.*MINI.*/", False),
        ("printer_notes=~/.*PRINTER_MODEL_MK4S.*/ and num_extruders==1", True),
        (
            "! (printer_notes=~/.*PRINTER_VENDOR_PRUSA3D.*/ and single_extruder_multi_material)"
            " and printer_notes!~/.*PG.*/",
            True,
        ),
        ("(nozzle_diameter[0]==0.3 or nozzle_diameter[0]==0.4) and not nozzle_high_flow[0]", False),
        ("", True),
    ],
)
def test_prusas_conditions_are_read_without_eval(condition: str, expected: bool) -> None:
    """PrusaSlicer bindet Prozesse und Filamente über Bedingungen an Drucker.
    Solidon las nur die Liste; am MK4S galten 6740 von 6772 Filamenten als
    verträglich (27.09.2026). Ausgewertet wird ohne ``eval`` (Regel 10)."""
    from app.core.export import prusa_conditions

    assert prusa_conditions.holds(condition, _MK4S_HF04) is expected


@pytest.mark.parametrize(
    "condition",
    [
        "printer_model=~",  # endet zu früh
        "nozzle_diameter==0.4",  # Liste ohne Index
        "gibt_es_nicht==1",  # unbekannter Wert
        "printer_model==/MK4S/",  # Muster ohne =~
        "__import__('os')",  # kein Python
        "nozzle_diameter[5]==0.4",  # außerhalb der Liste
    ],
)
def test_an_unreadable_condition_is_an_error_not_a_guess(condition: str) -> None:
    """Was über die Teilmenge der Bündel hinausgeht, ist ein Fehler, und das
    Profil gilt als unverträglich: lieber eine Auswahl zu wenig als eine, die
    nicht passt."""
    from app.core.export import prusa_conditions

    with pytest.raises(prusa_conditions.ConditionError):
        prusa_conditions.holds(condition, _MK4S_HF04)


@pytest.fixture
def prusa_mk4s(tmp_path: Path) -> Path:
    """Ein Bündel mit dem MK4S, zwei Filamenten, die ihn über eine Bedingung
    meinen oder nicht, und einem fremden ohne Angabe."""
    root = tmp_path / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[vendor]\nname = Prusa Research\n\n"
        "[printer_model:MK4S]\nname = Original Prusa MK4S\nvariants = HF0.4\n"
        "default_materials = Prusament PLA @MK4S HF0.4; Prusament PETG @MK4S HF0.4\n\n"
        "[printer:Original Prusa MK4S HF0.4 nozzle]\nprinter_technology = FFF\n"
        "printer_model = MK4S\nnozzle_diameter = 0.4\nnozzle_high_flow = 1\n"
        "default_print_profile = 0.20mm SPEED @MK4S HF0.4\n"
        "default_filament_profile = Prusament PLA @HF0.4\n\n"
        "[print:0.20mm SPEED @MK4S HF0.4]\nlayer_height = 0.2\n"
        'compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]\n\n'
        "[filament:Prusament PLA @HF0.4]\nfilament_type = PLA\n"
        'compatible_printers_condition = printer_model=="MK4" and nozzle_high_flow[0]\n\n'
        "[filament:Prusament PLA @MK4S HF0.4]\nfilament_type = PLA\n"
        'compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]\n\n'
        "[filament:Prusament PETG @MK4S HF0.4]\nfilament_type = PETG\n"
        'compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]\n',
        encoding="utf-8",
    )
    (root / "Sovol.ini").write_text(
        "[vendor]\nname = Sovol\n\n[filament:Generic PLA @SOVOL]\nfilament_type = PLA\n",
        encoding="utf-8",
    )
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    return executable


def test_prusa_filaments_fit_by_condition_and_the_models_suggestion_wins(
    prusa_mk4s: Path,
) -> None:
    """Der MK4S erbt als Standard das PLA des MK4, das laut eigener Bedingung
    nicht zu ihm passt. Ohne Bedingungen gewann danach der kürzeste Name,
    „Generic PLA @SOVOL" aus Sovols Bündel. Das Modell schlägt „Prusament PLA
    @MK4S HF0.4" vor, und das nimmt auch PrusaSlicer (27.09.2026). Sovols
    Filament passt dabei gar nicht: Es gehört einem anderen Hersteller
    (``test_prusa_offers_only_the_printers_own_bundle``)."""
    mk4s = PrinterProfile(
        id="prusa-mk4s",
        title="Prusa MK4S",
        build_volume=(250.0, 210.0, 220.0),
        prusaslicer_printer="Original Prusa MK4S HF0.4 nozzle",
    )
    found = sp.find_profiles(prusa_mk4s, "prusa", ("machine", "process"))
    filaments = sp.find_profiles(prusa_mk4s, "prusa", ("filament",))
    machine, process = sp.match(found, mk4s)
    assert machine is not None and process is not None

    fitting = {entry.name for entry in sp.filaments(filaments, machine)}

    assert fitting == {
        "Prusament PLA @MK4S HF0.4",
        "Prusament PETG @MK4S HF0.4",
    }, "das PLA des MK4 fällt heraus, Sovols gehört einem anderen Hersteller"
    pla = sp.match_filament(filaments, machine, "PLA")
    petg = sp.match_filament(filaments, machine, "PETG")
    assert pla is not None and pla.name == "Prusament PLA @MK4S HF0.4"
    assert petg is not None and petg.name == "Prusament PETG @MK4S HF0.4"


@pytest.mark.parametrize("native,requested", [("FLEX", "TPU"), ("TPU", "FLEX")])
def test_flexible_filament_names_select_the_same_material(
    tmp_path: Path, native: str, requested: str
) -> None:
    """Prusa nennt TPU FLEX; die Vorwahl darf deshalb nicht leer bleiben."""
    root = tmp_path / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[vendor]\nname = Prusa Research\n\n"
        "[printer:Original Prusa MINI]\nprinter_model = MINI\nnozzle_diameter = 0.4\n\n"
        "[filament:Generic FLEX]\n"
        f"filament_type = {native}\nfilament_vendor = Generic\n"
        'compatible_printers_condition = printer_model=="MINI"\n\n'
        "[filament:Generic PETG]\nfilament_type = PETG\nfilament_vendor = Generic\n",
        encoding="utf-8",
    )
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    found = sp.find_profiles(executable, "prusa", ("machine", "filament"))
    machine = next(entry for entry in found if entry.kind == "machine")

    chosen = sp.match_filament(found, machine, requested)

    assert chosen is not None and chosen.name == "Generic FLEX"
    assert sp.match_filament(found, machine, "PET") is None, "PET bleibt von PETG getrennt"


def test_prusa_takes_generic_before_a_foreign_brand_with_a_shorter_name(
    prusa_mk4s: Path,
) -> None:
    """RM-464: Das Modell schlägt kein ABS vor. Danach gewann der kürzeste Name,
    „Esun ABS @MK4S HF0.4“ — ein Fremdfilament mit eigener Temperatur und
    eigenem Lüfter für den ganzen Druck. Generic und die Marke des Druckers
    gehen jeder Fremdmarke vor; erst dann zählt die Namenslänge."""
    root = prusa_mk4s.parent / "resources" / "profiles"
    bundle = root / "PrusaResearch.ini"
    condition = 'compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]\n'
    bundle.write_text(
        bundle.read_text(encoding="utf-8")
        + "\n"
        + "".join(
            f"[filament:{name}]\nfilament_type = ABS\nfilament_vendor = {vendor}\n{condition}\n"
            for name, vendor in (
                ("Esun ABS @MK4S HF0.4", "Esun"),
                ("Buddy3D ABS @MK4S HF0.4", "Buddy3D"),
                ("Prusament ABS Blend @MK4S HF0.4", "Prusa Polymers"),
                ("Generic ABS @MK4S HF0.4", "Generic"),
            )
        ),
        encoding="utf-8",
    )
    mk4s = PrinterProfile(
        id="prusa-mk4s",
        title="Prusa MK4S",
        build_volume=(250.0, 210.0, 220.0),
        prusaslicer_printer="Original Prusa MK4S HF0.4 nozzle",
    )
    found = sp.find_profiles(prusa_mk4s, "prusa", ("machine", "process"))
    filaments = sp.find_profiles(prusa_mk4s, "prusa", ("filament",))
    machine, _process = sp.match(found, mk4s)
    assert machine is not None

    chosen = sp.match_filament(filaments, machine, "ABS")

    assert chosen is not None and chosen.name == "Generic ABS @MK4S HF0.4"


def test_among_foreign_brands_the_plain_spool_wins_over_the_short_name(
    prusa_mk4s: Path,
) -> None:
    """RM-464: Gibt es weder Generic noch die Marke des Druckers, wählte die
    Namenslänge am MK4 „Kimya ABS Kevlar“. Ein Wort neben Marke und Material
    macht eine Spule besonders; die schlichte geht vor."""
    root = prusa_mk4s.parent / "resources" / "profiles"
    bundle = root / "PrusaResearch.ini"
    condition = 'compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]\n'
    bundle.write_text(
        bundle.read_text(encoding="utf-8")
        + "\n"
        + "".join(
            f"[filament:{name}]\nfilament_type = ABS\nfilament_vendor = {vendor}\n{condition}\n"
            for name, vendor in (
                ("Kimya ABS CF @MK4S HF0.4", "Kimya"),
                ("Fiberlogy ABS @MK4S HF0.4", "Fiberlogy"),
            )
        ),
        encoding="utf-8",
    )
    mk4s = PrinterProfile(
        id="prusa-mk4s",
        title="Prusa MK4S",
        build_volume=(250.0, 210.0, 220.0),
        prusaslicer_printer="Original Prusa MK4S HF0.4 nozzle",
    )
    found = sp.find_profiles(prusa_mk4s, "prusa", ("machine", "process"))
    filaments = sp.find_profiles(prusa_mk4s, "prusa", ("filament",))
    machine, _process = sp.match(found, mk4s)
    assert machine is not None

    chosen = sp.match_filament(filaments, machine, "ABS")

    assert chosen is not None and chosen.name == "Fiberlogy ABS @MK4S HF0.4"


def _bambu_bundle(tmp_path: Path, suggested: list[str]) -> Path:
    """Ein Bambu-Bestand der Orca-Familie: das Modell mit ``default_materials``,
    eine Maschine, Filamente von Bambu, Generic und zwei Fremdmarken in
    eigenen Unterordnern — so liegt es in ``BBL/filament/<Marke>/``."""
    root = tmp_path / "resources" / "profiles" / "BBL"
    _write(
        root / "machine" / "Bambu Lab A1.json",
        {
            "type": "machine_model",
            "name": "Bambu Lab A1",
            "default_materials": ";".join(suggested),
        },
    )
    machine = "Bambu Lab A1 0.4 nozzle"
    _write(
        root / "machine" / f"{machine}.json",
        {
            "type": "machine",
            "name": machine,
            "instantiation": "true",
            "printer_model": "Bambu Lab A1",
            "nozzle_diameter": ["0.4"],
            "default_filament_profile": ["Bambu PLA Basic @BBL A1"],
        },
    )
    for folder, name, vendor in (
        ("", "Bambu PLA Basic @BBL A1", "Bambu Lab"),
        ("", "Bambu PETG HF @BBL A1", "Bambu Lab"),
        ("", "Generic PETG @BBL A1", "Generic"),
        ("BETA", "BETA PETG @BBL A1", "BETA"),
        ("addnorth", "addnorth PETG ESD", "addnorth"),
    ):
        _write(
            root / "filament" / folder / f"{name}.json",
            {
                "type": "filament",
                "name": name,
                "instantiation": "true",
                "filament_type": ["PLA" if "PLA" in name else "PETG"],
                "filament_vendor": [vendor],
                "compatible_printers": [machine],
            },
        )
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    return executable


@pytest.mark.parametrize(
    ("suggested", "expected"),
    [
        (
            ["Bambu PLA Basic @BBL A1", "Generic PETG @BBL A1", "Bambu PETG HF @BBL A1"],
            "Generic PETG @BBL A1",
        ),
        (["Bambu PLA Basic @BBL A1", "Bambu PETG HF @BBL A1"], "Bambu PETG HF @BBL A1"),
        (["Bambu PLA Basic @BBL A1"], "Generic PETG @BBL A1"),
    ],
    ids=["modell-nennt-generic", "modell-nennt-bambu", "modell-nennt-kein-petg"],
)
def test_bambu_petg_comes_from_the_model_or_its_brands_never_a_foreign_one(
    tmp_path: Path, suggested: list[str], expected: str
) -> None:
    """RM-464: Am A1 bekam PETG „BETA PETG @BBL A1“, am A1 mini das leitfähige
    „addnorth PETG ESD“. Das Modellprofil der Orca-Familie nennt seine
    Filamente (``default_materials``), und die Marke eines Filaments ist seine
    eigene Angabe, nicht der Herstellerordner ``BBL``, in dem alle liegen."""
    executable = _bambu_bundle(tmp_path, suggested)
    found = sp.find_profiles(executable, "orca", kinds=("machine", "filament"))
    machine = next(entry for entry in sp.machines(found) if entry.name.endswith("0.4 nozzle"))

    chosen = sp.match_filament(found, machine, "PETG", sp.profile_roots("orca", executable))

    assert chosen is not None and chosen.name == expected


def test_prusa_offers_only_the_printers_own_bundle(
    prusa_mk4s: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PrusaSlicers eigene Regel (``is_compatible_with_printer``, 2.9.6): erst
    der Hersteller, dann Liste und Bedingung. Am MK4S HF0.4 standen sonst
    Prozesse von BIBO2, LulzBot, Trimaker und Zonestar zur Wahl — Profile ohne
    Bedingung galten als passend (Gesamtprüfung, 27.09.2026). Vorlagen passen zu
    jedem Hersteller, ein eigenes Profil gehört dem seines Elternprofils, und
    eines ohne Herstellerbasis geht nach Bedingung."""
    root = prusa_mk4s.parent / "resources" / "profiles"
    (root / "BIBO.ini").write_text(
        "[vendor]\nname = BIBO\n\n[print:0.12mm DETAIL @BIBO2]\nlayer_height = 0.12\n",
        encoding="utf-8",
    )
    (root / "Templates.ini").write_text(
        "[vendor]\nname = Templates\ntemplates_profile = 1\n\n"
        "[filament:Generic PETG @Vorlage]\nfilament_type = PETG\n"
        "compatible_printers_condition = nozzle_diameter[0]!=0.8\n",
        encoding="utf-8",
    )
    config = tmp_path / "config" / "PrusaSlicer"
    (config / "print").mkdir(parents=True)
    (config / "print" / "Mein SPEED.ini").write_text(
        "inherits = 0.20mm SPEED @MK4S HF0.4\nperimeters = 3\n", encoding="utf-8"
    )
    (config / "print" / "Mein BIBO.ini").write_text(
        "inherits = 0.12mm DETAIL @BIBO2\nperimeters = 3\n", encoding="utf-8"
    )
    (config / "print" / "Ganz eigen.ini").write_text("layer_height = 0.16\n", encoding="utf-8")
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(tmp_path / "config"))
    mk4s = PrinterProfile(
        id="prusa-mk4s",
        title="Prusa MK4S",
        build_volume=(250.0, 210.0, 220.0),
        prusaslicer_printer="Original Prusa MK4S HF0.4 nozzle",
    )
    found = sp.find_profiles(prusa_mk4s, "prusa", ("machine", "process"))
    filaments = sp.find_profiles(prusa_mk4s, "prusa", ("filament",))
    machine, _process = sp.match(found, mk4s)
    assert machine is not None and machine.vendor == "PrusaResearch"

    processes = {entry.name for entry in sp.processes(found, machine)}
    fitting = {entry.name for entry in sp.filaments(filaments, machine)}

    assert processes == {"0.20mm SPEED @MK4S HF0.4", "Mein SPEED", "Ganz eigen"}
    assert "Generic PETG @Vorlage" in fitting, "Vorlagen passen zu jedem Hersteller"
    assert "Generic PLA @SOVOL" not in fitting


def test_a_bundle_name_with_a_line_break_is_no_name() -> None:
    """Der Name kommt auch aus mitgebrachten Druckern fremder Projektdateien.
    Einer mit Steuerzeichen gleicht keinem Profil und gilt als nicht angegeben."""
    from app.core.knowledge import profiles

    table = {"title": "Fremd", "build_volume": [200.0, 200.0, 200.0]}
    odd = profiles._printer_from_table(
        "fremd", {**table, "prusaslicer_printer": "SV06\n[print:x]"}, Path("fremd.toml")
    )
    plain = profiles._printer_from_table(
        "fremd", {**table, "prusaslicer_printer": " SV06 "}, Path("fremd.toml")
    )

    assert odd.prusaslicer_printer == ""
    assert plain.prusaslicer_printer == "SV06"


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "1e999"])
@pytest.mark.parametrize("key", ["nozzle_temperature", "filament_max_volumetric_speed"])
def test_nonfinite_filament_values_are_rejected_with_a_profile_error(
    tmp_path: Path, key: str, value: str
) -> None:
    """Weder ein roher Integerfehler noch NaN darf in die Beratung gelangen."""
    from app.core.errors import ValidationError

    path = tmp_path / "Filament.json"
    _write(path, {"name": "Filament", key: [value]})
    with pytest.raises(ValidationError) as caught:
        sp.filament_values(path)
    assert caught.value.suggestions
    assert caught.value.values["file"] == path.name


def test_one_name_index_serves_a_whole_kind_instead_of_one_per_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Namensindex wird geteilt, nicht je Profil neu gebaut (Befund Robert, 09.09.2026).

    ``_of_kind`` fragt für jedes Profil ``compatible_with``. Trägt eines die
    Verträglichkeit nicht selbst, löst das über ``binding`` seine Erbkette auf
    — und jede Auflösung baute sich ihren **eigenen** Namensindex. Ein Index
    kostet einen Durchgang durch jede JSON-Datei der Ablage; beim ElegooSlicer
    sind das 16 795, und der Qt-Hauptthread stand damit 49 Sekunden.

    **Angesetzt wird an ``_of_kind`` und nicht an ``find_profiles``**, und das
    ist keine Abkürzung, sondern der Fall selbst: ``find_profiles`` löst die
    Verträglichkeit für alles auf, was es gemeinsam lädt. Die Wiederholung
    entsteht dort, wo ein Profil ohne eigene Angabe hereinkommt — bei einem
    Nutzerprofil, das von einer Herstellerstufe außerhalb der Ladung erbt.
    Genau so sieht der Eingang beim Kunden aus.

    Gezählt wird die **Zahl der Indexläufe**, nicht die Zeit: Eine
    Zeitschranke wäre auf einer schnellen Maschine grün und sagte nichts über
    die Sache.
    """
    ablage = tmp_path / "profiles"
    _write(
        ablage / "basis.json",
        {"type": "process", "name": "0.20mm Basis", "compatible_printers": ["Haus 0.4 nozzle"]},
    )
    maschine = sp.SlicerProfile(ablage / "maschine.json", "Haus 0.4 nozzle", "machine")
    erben = []
    for nummer in range(8):
        pfad = ablage / f"kind{nummer}.json"
        _write(pfad, {"type": "process", "name": f"0.1{nummer}mm Fein", "inherits": "0.20mm Basis"})
        # Ohne ``compatible_printers``: genau der Eingang, der die Erbkette
        # und damit den Namensindex überhaupt erst auslöst.
        erben.append(
            sp.SlicerProfile(pfad, f"0.1{nummer}mm Fein", "process", inherits="0.20mm Basis")
        )

    laeufe: list[tuple[Path, object]] = []
    echtes = sp._names_in

    def gezaehlt(
        wurzel: Path, art: object = None, *, cancelled=None, documents=None
    ) -> dict[str, Path]:
        laeufe.append((wurzel, art))
        return echtes(wurzel, art, cancelled=cancelled, documents=documents)

    monkeypatch.setattr(sp, "_names_in", gezaehlt)
    passende = sp.processes([maschine, *erben], maschine)

    assert len(passende) == len(erben), "alle acht erben dieselbe Verträglichkeit"
    assert laeufe, "ohne einen einzigen Indexlauf prüft die Zusicherung darunter nichts"
    assert len(laeufe) == len(set(laeufe)), (
        f"{len(laeufe)} Indexläufe für {len(set(laeufe))} verschiedene Ablagen — "
        "derselbe Index wird je Profil neu aufgestellt"
    )


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
def test_cancelled_spool_search_does_not_start_discovery(tmp_path, monkeypatch, flavour):
    """Ein bereits beendeter Auftrag startet keine Suche in fremden Dateien."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    cancelled = CancelSignal()
    cancelled.cancel()

    def forbidden(*args, **kwargs):
        pytest.fail("cancelled search still reached profile discovery")

    monkeypatch.setattr(sp, "profile_roots", forbidden)
    with pytest.raises(OperationCancelled):
        sp.configured_filaments(flavour, tmp_path / "slicer.exe", cancelled=cancelled)


def test_cancel_during_inheritance_stops_reading_the_profile_index(tmp_path, monkeypatch):
    """Die Erbsuche liest nach einem Abbruch keine weiteren Herstellerdateien."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    folder = tmp_path / "filament"
    leaf = folder / "z-child.json"
    _write(leaf, {"name": "Child", "inherits": "Base"})
    for index in range(20):
        _write(folder / f"{index:02}.json", {"name": f"Aux {index}"})
    cancelled = CancelSignal()
    original = Path.read_text
    read = []

    def remember(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        read.append(path.name)
        if path.name == "00.json":
            cancelled.cancel()
        return result

    monkeypatch.setattr(Path, "read_text", remember)
    with pytest.raises(OperationCancelled):
        sp.resolve_values(leaf, cancelled=cancelled)
    assert read == ["z-child.json", "00.json"]


def test_cancelled_prusa_spool_search_stops_at_the_read_profile(prusa, monkeypatch):
    """Auch der Prusa-Zweig beendet seinen echten Dateidurchgang kooperativ."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    cancelled = CancelSignal()
    original = sp._read_prusa_ini
    read = []

    def remember(path):
        result = original(path)
        read.append(path.name)
        if path.name == "Meine Spule.ini":
            cancelled.cancel()
        return result

    monkeypatch.setattr(sp, "_read_prusa_ini", remember)
    with pytest.raises(OperationCancelled):
        sp.configured_filaments("prusa", prusa, cancelled=cancelled)
    assert read[-1] == "Meine Spule.ini"


def _processes(*names: str, own: tuple[str, ...] = ()) -> list[sp.SlicerProfile]:
    return [
        sp.SlicerProfile(Path(f"{name}.json"), name, "process", from_user=name in own)
        for name in names
    ]


@pytest.mark.parametrize(
    ("names", "standard", "expected"),
    [
        (
            (
                "0.12mm Fine @CC2",
                "0.16mm Optimal @CC2",
                "0.20mm Standard @CC2",
                "0.20mm Strength @CC2",
                "0.24mm Draft @CC2",
                "0.28mm Extra Draft @CC2",
            ),
            "0.20mm Standard @CC2",
            ("0.12mm Fine @CC2", "0.28mm Extra Draft @CC2", "0.20mm Strength @CC2"),
        ),
        (
            (
                "0.08mm Extra Fine @BBL X1C",
                "0.08mm High Quality @BBL X1C",
                "0.12mm Fine @BBL X1C",
                "0.12mm High Quality @BBL X1C",
                "0.16mm Optimal @BBL X1C",
                "0.20mm Standard @BBL X1C",
                "0.20mm Strength @BBL X1C",
                "0.24mm Draft @BBL X1C",
                "0.28mm Extra Draft @BBL X1C",
            ),
            "0.20mm Standard @BBL X1C",
            ("0.12mm Fine @BBL X1C", "0.28mm Extra Draft @BBL X1C", "0.20mm Strength @BBL X1C"),
        ),
        (
            (
                "0.10mm FAST DETAIL @MK4S 0.4",
                "0.15mm SPEED @MK4S HF0.4",
                "0.15mm STRUCTURAL @MK4S 0.4",
                "0.20mm SPEED @MK4S HF0.4",
                "0.20mm STRUCTURAL @MK4S 0.4",
                "0.25mm STRUCTURAL @MK4S HF0.4",
                "0.28mm DRAFT @MK4S HF0.4",
            ),
            "0.20mm SPEED @MK4S HF0.4",
            (
                "0.10mm FAST DETAIL @MK4S 0.4",
                "0.28mm DRAFT @MK4S HF0.4",
                "0.20mm STRUCTURAL @MK4S 0.4",
            ),
        ),
        (
            ("0.08mm Standard @K1", "0.16mm Standard @K1", "0.20mm Standard @K1"),
            "0.20mm Standard @K1",
            (None, None, None),
        ),
    ],
    ids=["centauri-carbon-2", "bambu-p1s", "prusa-mk4s", "creality-print"],
)
def test_a_stage_names_the_manufacturers_process(
    names: tuple[str, ...], standard: str, expected: tuple[str | None, ...]
) -> None:
    """Entscheidung I, gemessen an den Beständen vom 27.09.2026: Fein, Entwurf
    und Belastbar nehmen den Prozess, dessen Name die Stufe nennt — Fein und
    Entwurf mit der Schichthöhe nächst Solidons 0,12 und 0,28 mm, Belastbar bei
    der des Standards; „0.25mm STRUCTURAL" ist gröber, nicht belastbarer.
    Creality Print nennt jeden Prozess „Standard", und dort bleibt es beim
    Standardprozess."""
    fitting = _processes(*names)
    base = next(entry for entry in fitting if entry.name == standard)

    chosen = [
        sp.stage_process(fitting, base, quality, layer)
        for quality, layer in (("fine", 0.12), ("draft", 0.28), ("strong", 0.20))
    ]

    assert [entry.name if entry else None for entry in chosen] == list(expected)
    assert sp.stage_process(fitting, base, "standard", 0.20) is base


def test_an_own_copy_is_no_stage() -> None:
    """Eine eigene Kopie hat ihren eigenen Zweck: Bei gleicher Schichthöhe
    gilt der mitgelieferte Prozess."""
    fitting = _processes(
        "0.12mm Fine @CC2 - Kopieren",
        "0.12mm Fine @CC2",
        "0.20mm Standard @CC2",
        own=("0.12mm Fine @CC2 - Kopieren",),
    )

    chosen = sp.stage_process(fitting, fitting[2], "fine", 0.12)

    assert chosen is not None and chosen.name == "0.12mm Fine @CC2"


# --- ein Slicer als Flatpak -------------------------------------------------------
#
# Ein Kunde mit Orca als Flatpak bekam keinen seiner Drucker angeboten: Solidon
# suchte den Herstellerbestand über dem Starter in den Exporten und die eigenen
# Drucker in ``~/.config``. Orca als Flatpak hat beides woanders — nachgelesen in
# Orcas Quelltext (``SLIC3R_FHS`` mit ``-DFLATPAK=ON``, ``XDG_CONFIG_HOME`` in
# ``GUI_App.cpp``) und im Flathub-Manifest, nicht angenommen.

_ORCA = "com.orcaslicer.OrcaSlicer"


@pytest.fixture
def orca_flatpak(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Eine Systeminstallation von Orca als Flatpak, wie ``flatpak install`` sie
    hinterlässt, samt einem veralteten ``~/.config/OrcaSlicer`` daneben."""
    from app.core import discover

    system = tmp_path / "var" / "lib" / "flatpak"
    home = tmp_path / "home"
    launcher = system / "exports" / "bin" / _ORCA
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\nexec /usr/bin/flatpak run com.orcaslicer.OrcaSlicer\n")
    files = system / "app" / _ORCA / "current" / "active" / "files"
    vendor = files / "share" / "OrcaSlicer" / "profiles"
    (files / "bin").mkdir(parents=True)
    (files / "bin" / "orca-slicer").write_bytes(b"")
    _write(
        vendor / "Creality" / "machine" / "k1.json",
        {
            "type": "machine",
            "name": "Creality K1 (0.4 nozzle)",
            "instantiation": "true",
            "printer_model": "Creality K1",
            "nozzle_diameter": ["0.4"],
        },
    )
    _write(
        vendor / "Creality" / "process" / "standard.json",
        {
            "type": "process",
            "name": "0.20mm Standard @Creality K1 (0.4 nozzle)",
            "instantiation": "true",
            "compatible_printers": ["Creality K1 (0.4 nozzle)"],
        },
    )
    config = home / ".var" / "app" / _ORCA / "config" / "OrcaSlicer"
    _write(
        config / "user" / "default" / "machine" / "Mein K1.json",
        {"name": "Mein K1", "from": "User", "inherits": "Creality K1 (0.4 nozzle)"},
    )
    (config / "OrcaSlicer.conf").write_text(
        json.dumps({"presets": {"machine": "Mein K1"}}), encoding="utf-8"
    )
    stale = home / ".config" / "OrcaSlicer"
    _write(
        stale / "user" / "default" / "machine" / "Alt.json",
        {"name": "Creality K1 - Custom", "from": "User"},
    )
    (stale / "OrcaSlicer.conf").write_text(
        json.dumps({"presets": {"machine": "Creality K1 - Custom"}}), encoding="utf-8"
    )

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(launcher.parent),))
    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(system),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    monkeypatch.setattr(sp.sys, "platform", "linux")
    return {"launcher": launcher, "files": files, "vendor": vendor, "config": config}


def test_a_flatpak_slicer_brings_its_vendor_profiles(orca_flatpak: dict[str, Path]) -> None:
    """Der Bestand liegt im ``/app`` des Flatpak unter ``share/OrcaSlicer``,
    nicht über dem Starter in ``exports/bin``."""
    assert sp.install_root(orca_flatpak["launcher"]) == orca_flatpak["vendor"]


def test_a_flatpak_slicer_keeps_its_own_printers_in_its_own_folder(
    orca_flatpak: dict[str, Path],
) -> None:
    """``~/.var/app/<Kennung>/config`` statt ``~/.config`` — und ein altes
    ``~/.config/OrcaSlicer`` einer früheren Installation bleibt ungelesen."""
    launcher = orca_flatpak["launcher"]

    assert sp.user_roots("orca", launcher) == [orca_flatpak["config"] / "user" / "default"]
    assert sp.chosen_machine("orca", launcher) == "Mein K1"


def test_a_flatpak_slicer_offers_vendor_and_own_printers(orca_flatpak: dict[str, Path]) -> None:
    """Was der Kunde im Druckdialog sieht: die Drucker des Herstellers und
    seinen eigenen, nicht den einer alten Installation."""
    names = {entry.name for entry in sp.find_profiles(orca_flatpak["launcher"], "orca")}

    assert {
        "Creality K1 (0.4 nozzle)",
        "0.20mm Standard @Creality K1 (0.4 nozzle)",
        "Mein K1",
    } <= names
    assert "Creality K1 - Custom" not in names


def test_the_portal_copy_of_the_launcher_reads_the_same_profiles(
    orca_flatpak: dict[str, Path],
) -> None:
    """So kam der Pfad beim Kunden an: Solidons Dateidialog gab im eigenen
    Flatpak die Portalkopie des Starters zurück."""
    from app.core import discover

    portal = Path("/run/user/2009/doc/d0880632") / _ORCA

    assert discover.host_program(portal) == orca_flatpak["launcher"]
    assert sp.install_root(portal) == orca_flatpak["vendor"]


def test_a_user_installation_and_a_hidden_one_are_told_apart(
    orca_flatpak: dict[str, Path], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Fehlt Solidons eigenem Flatpak die Leseberechtigung, sagt das Protokoll
    es — statt den Bestand still für nicht vorhanden zu halten."""
    from app.core import discover

    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(orca_flatpak["files"].parent),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    monkeypatch.setattr(discover, "_host_test", lambda _flag, _path: True)

    with caplog.at_level("INFO", logger=discover._log.name):
        assert discover.flatpak_files(_ORCA) is None

    assert "hidden from this sandbox" in caplog.text


@pytest.mark.parametrize(
    ("program", "below_share"),
    [
        ("prusa-slicer", ("PrusaSlicer", "profiles")),
        ("AnycubicSlicerNext", ("AnycubicSlicerNext", "resources", "profiles")),
    ],
)
def test_a_distribution_package_keeps_its_profiles_under_share(
    tmp_path: Path, program: str, below_share: tuple[str, ...]
) -> None:
    """``apt install prusa-slicer`` legt nach FHS ab: ``/usr/bin/prusa-slicer``
    und ``/usr/share/PrusaSlicer/profiles``. Dieselbe Ablage nutzt das Flatpak.
    Anycubic Slicer Next legt laut ``md5sums`` seines Pakets 2.0.0.5 eine Ebene
    tiefer ab."""
    prefix = tmp_path / "usr"
    executable = prefix / "bin" / program
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    (prefix / "share" / "applications").mkdir(parents=True)
    profiles = prefix.joinpath("share", *below_share)
    profiles.mkdir(parents=True)

    assert sp.install_root(executable) == profiles


@pytest.mark.parametrize(
    ("program", "below_share"),
    [
        ("prusa-slicer", ("PrusaSlicer", "profiles")),
        ("orca-slicer", ("OrcaSlicer", "profiles")),
    ],
)
def test_a_distribution_package_beside_cura_keeps_its_own_profiles(
    tmp_path: Path, program: str, below_share: tuple[str, ...]
) -> None:
    """Cura aus dem Paketverwalter legt seinen Bestand nach ``/usr/share/cura``.

    Der Ordner gehört Cura. Angeboten wurde er jedem Programm und vor
    ``share/<Programm>``: PrusaSlicer und Orca daneben bekamen Curas Ordner als
    Herstellerbestand und darin keinen ihrer Drucker (Durchsicht 0.5.3, Fund 1).
    """
    prefix = tmp_path / "usr"
    executable = prefix / "bin" / program
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    cura = prefix / "bin" / "cura"
    cura.write_bytes(b"")
    (prefix / "share" / "cura" / "resources" / "definitions").mkdir(parents=True)
    profiles = prefix.joinpath("share", *below_share)
    profiles.mkdir(parents=True)

    assert sp.install_root(executable) == profiles
    assert sp.install_root(cura) == prefix / "share" / "cura", "Cura behält seinen Ordner"


def test_a_mac_bundle_hands_out_its_resources_in_its_own_spelling(tmp_path: Path) -> None:
    """Ein Mac-Bündel trägt seinen Bestand unter ``Contents/Resources/profiles``.

    Gesucht wurde ``resources/profiles``. Auf dem üblichen APFS ohne
    Unterscheidung der Schreibweise traf das, auf einem case-sensitiv
    formatierten Volume nicht — dort fehlte der Herstellerbestand von Orca,
    Bambu, Elegoo, Creality und Anycubic. Verglichen wird der Text: Auf einem
    Dateisystem ohne Unterscheidung nennt ``is_dir`` auch die falsche
    Schreibweise vorhanden, und ``WindowsPath`` vergleicht sie gleich.
    """
    contents = tmp_path / "OrcaSlicer.app" / "Contents"
    executable = contents / "MacOS" / "OrcaSlicer"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    profiles = contents / "Resources" / "profiles"
    profiles.mkdir(parents=True)

    assert str(sp.install_root(executable)) == str(profiles)


@pytest.mark.parametrize(
    ("app_id", "flavour", "inside", "command"),
    [
        ("com.prusa3d.PrusaSlicer", "prusa", "bin/prusa-slicer", "/app/bin/prusa-slicer"),
        ("com.ultimaker.cura", "cura", "cura/CuraEngine", ""),
        ("com.orcaslicer.OrcaSlicer", "orca", "bin/orca-slicer", ""),
    ],
)
def test_a_flatpak_slicer_computes_with_the_program_inside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    app_id: str,
    flavour: str,
    inside: str,
    command: str,
) -> None:
    """Gemessen am Runner mit den Flathub-Paketen: PrusaSlicers Startskript
    ruft das Programm im Hintergrund auf und kehrt sofort zurück, Curas Starter
    öffnet nur das Fenster — beide schrieben keine Druckdatei. Orca ruft im
    Vordergrund auf und behält seinen Starter, Cura ebenso: Seine CuraEngine
    startet nur mit Curas eigenem Lader aus ``runtime/compat``."""
    from app.core import discover
    from app.core.export import handover

    system = tmp_path / "flatpak"
    launcher = system / "exports" / "bin" / app_id
    launcher.parent.mkdir(parents=True)
    launcher.write_text("")
    program = system / "app" / app_id / "current" / "active" / "files" / inside
    program.parent.mkdir(parents=True)
    program.write_bytes(b"")
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(launcher.parent),))
    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(system),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)

    found = handover._cli_program(handover.SlicerSetup(launcher, flavour))  # type: ignore[arg-type]

    expected = ["flatpak", "run", f"--command={command}", app_id] if command else [str(launcher)]
    assert found == expected


def test_cura_as_a_flatpak_reads_its_own_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cura auf Flathub ist ein ausgepacktes AppImage unter ``/app/cura``, und
    seine Druckerstapel liegen in ``~/.var/app/com.ultimaker.cura/data``."""
    from app.core import discover

    cura = "com.ultimaker.cura"
    system = tmp_path / "flatpak"
    home = tmp_path / "home"
    launcher = system / "exports" / "bin" / cura
    launcher.parent.mkdir(parents=True)
    launcher.write_text("")
    resources = system / "app" / cura / "current" / "active" / "files" / "cura" / "share" / "cura"
    (resources / "resources" / "definitions").mkdir(parents=True)
    data = home / ".var" / "app" / cura / "data" / "cura" / "5.11"
    data.mkdir(parents=True)
    (home / ".var" / "app" / cura / "config" / "cura").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(launcher.parent),))
    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(system),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    monkeypatch.setattr(sp.sys, "platform", "linux")

    assert sp.install_root(launcher) == resources
    assert data in sp.user_roots("cura", launcher)


def test_cura_on_a_mac_finds_its_definitions_and_its_window(tmp_path: Path) -> None:
    """Cura 5 legt auf dem Mac seinen Bestand nach ``Contents/Resources/share/cura``
    und die Rechenmaschine daneben (``CuraApplication.py``,
    ``CuraEngineBackend.py``); das Fenster liegt in ``Contents/MacOS``.

    **Das Fenster heißt, wie die Datei heißt.** ``window_program`` setzte den
    Namen aus seiner Liste zusammen und fragte ``is_file``: Auf APFS ohne
    Unterscheidung der Schreibweise traf schon ``Ultimaker-Cura``, und zurück
    kam ein Pfad, den es so nicht gibt (Generalprobe 0.5.3, macOS-Runner).
    Verglichen wird der Text, denn ``WindowsPath`` vergleicht ohne Schreibweise.
    """
    from app.core.export import handover

    contents = tmp_path / "UltiMaker Cura.app" / "Contents"
    engine = contents / "Resources" / "CuraEngine"
    window = contents / "MacOS" / "UltiMaker-Cura"
    shared = contents / "Resources" / "share" / "cura"
    (shared / "resources" / "definitions").mkdir(parents=True)
    window.parent.mkdir(parents=True)
    for program in (engine, window):
        program.write_bytes(b"")

    assert sp.install_root(engine) == shared
    assert str(handover.window_program(engine)) == str(window)


def test_creality_print_keeps_its_printers_below_its_application_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creality Print 7 legt unter ``Creality/Creality Print/<Version>`` ab, mit
    ``Creality.conf`` (``SLIC3R_APP_KEY "Creality"``) — gemessen an 7.3 unter
    Windows. Unter der Programmmarke gesucht, fehlten die eigenen Drucker und
    der zuletzt gewählte auf jeder Plattform."""
    base = tmp_path / "config"
    newest = base / "Creality" / "Creality Print" / "7.3"
    older = base / "Creality" / "Creality Print" / "7.0"
    for version, machine in ((older, "Alt"), (newest, "Creality K1 0.4 nozzle")):
        (version / "user" / "default" / "machine").mkdir(parents=True)
        (version / "Creality.conf").write_text(
            json.dumps({"presets": {"machine": machine}}) + "\n# MD5 checksum 0\n", encoding="utf-8"
        )
    (newest / "Creality.conf.bak").write_text("{}", encoding="utf-8")
    executable = tmp_path / "Creality Print 7.2" / "CrealityPrint.exe"
    monkeypatch.setattr(sp, "config_base", lambda _executable: str(base))

    assert sp.user_roots("orca", executable) == [newest / "user" / "default"]
    assert sp.chosen_machine("orca", executable) == "Creality K1 0.4 nozzle"


def test_an_appimage_offers_the_printers_its_slicer_copied_to_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein AppImage trägt seinen Bestand im Abbild, das nur während seines
    Laufs eingehängt ist. Die Orca-Familie kopiert die Bündel der eingerichteten
    Drucker nach ``system/`` neben ``user/`` — ohne diesen Ort bot Solidon unter
    Linux nur selbst angelegte Drucker an."""
    config = tmp_path / "config" / "OrcaSlicer"
    _write(
        config / "system" / "Creality" / "machine" / "k1.json",
        {
            "type": "machine",
            "name": "Creality K1 (0.4 nozzle)",
            "instantiation": "true",
            "printer_model": "Creality K1",
        },
    )
    _write(
        config / "user" / "default" / "machine" / "Mein K1.json",
        {"name": "Mein K1", "from": "User", "inherits": "Creality K1 (0.4 nozzle)"},
    )
    appimage = tmp_path / "Applications" / "OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.3.1.AppImage"
    appimage.parent.mkdir()
    appimage.write_bytes(b"")
    monkeypatch.setattr(sp, "config_base", lambda _executable: str(config.parent))

    assert sp.install_root(appimage) is None
    names = {entry.name for entry in sp.find_profiles(appimage, "orca")}

    assert {"Creality K1 (0.4 nozzle)", "Mein K1"} <= names
