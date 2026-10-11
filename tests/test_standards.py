"""Normteilmaße werden geprüft, bevor sie die Reihenfolge der Auswahl bestimmen."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import standards


@pytest.mark.parametrize(
    ("table_name", "field", "values"),
    [
        (
            "screws",
            "nominal",
            {
                "nominal": 4.0,
                "clearance": 4.5,
                "tap": 3.3,
                "head": 7.0,
                "head_height": 4.0,
                "countersink": 8.0,
                "hex": 7.0,
                "pitch": 0.7,
            },
        ),
        ("inserts", "hole", {"thread": "M4", "outer": 6.0, "length": 8.0, "hole": 5.0}),
        ("bearings", "inner", {"inner": 5.0, "outer": 10.0, "width": 3.0}),
    ],
)
@pytest.mark.parametrize("invalid", ["5.0", []], ids=["text", "list"])
def test_invalid_leading_dimensions_are_reported_before_sorting(
    tmp_path: Path, table_name: str, field: str, values: dict, invalid: object
) -> None:
    """Ein zweiter Eintrag darf aus dem Profilfehler keinen rohen Sortierfehler machen."""
    path = tmp_path / "standards.toml"
    lines = []
    for name, dimensions in (("invalid", {**values, field: invalid}), ("valid", values)):
        lines.extend([f"[[{table_name}]]", f"size = {json.dumps(name)}"])
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in dimensions.items())
    path.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        standards.load(path)

    assert caught.value.field == f"{table_name}.invalid.{field}_number"
    assert caught.value.values["file"] == str(path)
    assert caught.value.suggestions


def test_valid_leading_dimensions_keep_numeric_order_and_name_ties(tmp_path: Path) -> None:
    """Die kleinste passende Größe kommt zuerst, gleiche Maße bleiben stabil sortiert."""
    path = tmp_path / "standards.toml"
    path.write_text(
        "\n".join(
            f'[[bearings]]\nsize = "{name}"\ninner = {inner}\nouter = 12.0\nwidth = 3.0'
            for name, inner in (("large", 9.0), ("second", 5.0), ("first", 5.0))
        ),
        encoding="utf-8",
    )

    assert tuple(standards.load(path).bearings) == ("first", "second", "large")


@pytest.mark.parametrize("value", ['"false"', "0", "[]"])
def test_profile_taper_requires_a_boolean(tmp_path: Path, value: str) -> None:
    """Die Zeichenkette false darf keine konische Nutfeder einschalten."""
    path = tmp_path / "standards.toml"
    source = standards._DATA_FILE.read_text(encoding="utf-8")
    assert "taper_to_slot = true" in source
    path.write_text(
        source.replace("taper_to_slot = true", f"taper_to_slot = {value}", 1), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as caught:
        standards.load(path)

    assert caught.value.field.endswith("taper_to_slot_boolean")
    assert caught.value.suggestions


@pytest.mark.parametrize(
    ("diameter", "pitch"),
    [(1.0, 0.35), (6.5, 1.0), (8.0, 1.25), (9.99, 1.25), (10.0, 1.5), (60.0, 5.5), (66.6, 6.0)],
)
def test_the_regular_pitch_follows_the_largest_size_the_diameter_reaches(
    diameter: float, pitch: float
) -> None:
    """Ein Gewinde mit eigenem Maß bekommt die Steigung der Normgröße, die es erreicht.

    Unter M1.6 die von M1.6, zwischen zwei Größen die der kleineren, über M64
    die 6 mm der M64 — dieselbe Reihe, nach der die Schraubentabelle gebaut ist.
    """
    assert standards.regular_pitch(diameter) == pytest.approx(pitch)
    assert standards.regular_pitch(1000.0) == pytest.approx(6.0)


def test_the_regular_pitch_never_falls_along_the_screws(tmp_path: Path) -> None:
    """Fiele die Steigung, bekäme ein größeres eigenes Maß einen feineren Gang als ein kleineres."""
    source = standards._DATA_FILE.read_text(encoding="utf-8")
    screws = list(standards.load().screws.values())
    assert [entry.nominal for entry in screws] == sorted(entry.nominal for entry in screws)
    assert all(b.pitch >= a.pitch for a, b in itertools.pairwise(screws))

    falling = tmp_path / "falling.toml"
    falling.write_text(
        source + '\n[[screws]]\nsize = "M68"\nnominal = 68.0\nclearance = 74.0\ntap = 64.0\n'
        "head = 102.0\nhead_height = 68.0\ncountersink = 136.0\nhex = 50.0\npitch = 4.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as caught:
        standards.load(falling)
    assert caught.value.field == "screws.M68.pitch_rises"
    assert caught.value.suggestions


@pytest.mark.parametrize("table_name", ["nuts", "washers"])
def test_a_nut_or_washer_belongs_to_a_screw_of_the_table(tmp_path: Path, table_name: str) -> None:
    """Ein eigenes Maß leitet Mutter und Scheibe vom Nennmaß ihrer Schraube ab."""
    entry = (
        '[[nuts]]\nsize = "M7"\nwidth = 11.0\nheight = 5.5\n'
        if table_name == "nuts"
        else '[[washers]]\nsize = "M7"\ninner = 7.4\nouter = 14.0\nthickness = 1.6\n'
    )
    orphan = tmp_path / "orphan.toml"
    orphan.write_text(
        standards._DATA_FILE.read_text(encoding="utf-8") + "\n" + entry, encoding="utf-8"
    )
    with pytest.raises(ValidationError) as caught:
        standards.load(orphan)
    assert caught.value.field == f"{table_name}.M7.known_screw"


# --- Die metrische Reihe M1.6 bis M64 (Tabellenversion 13) --------------------------

#: Der Stand der Version 12, abgeschrieben aus ihr: Kein Wert davon darf sich
#: geändert haben, sonst rechnete ein altes Projekt still anders (§24.4).
#: Schraube: Nennmaß, Durchgang mittel, Kernloch, Kopf, Kopfhöhe, Senkkopf,
#: Innensechskant, Steigung, Durchgang fein, Durchgang grob.
VERSION_12_SCREWS = {
    "M2": (2.0, 2.4, 1.6, 3.8, 2.0, 4.0, 1.5, 0.4, 2.2, 2.6),
    "M2.5": (2.5, 2.9, 2.05, 4.5, 2.5, 5.0, 2.0, 0.45, 2.7, 3.1),
    "M3": (3.0, 3.4, 2.5, 5.5, 3.0, 6.0, 2.5, 0.5, 3.2, 3.6),
    "M4": (4.0, 4.5, 3.3, 7.0, 4.0, 8.0, 3.0, 0.7, 4.3, 4.8),
    "M5": (5.0, 5.5, 4.2, 8.5, 5.0, 10.0, 4.0, 0.8, 5.3, 5.8),
    "M6": (6.0, 6.6, 5.0, 10.0, 6.0, 12.0, 5.0, 1.0, 6.4, 7.0),
    "M8": (8.0, 9.0, 6.8, 13.0, 8.0, 16.0, 6.0, 1.25, 8.4, 10.0),
}
VERSION_12_PITCHES = {
    "M10": 1.5, "M12": 1.75, "M14": 2.0, "M16": 2.0, "M18": 2.5, "M20": 2.5, "M22": 2.5,
    "M24": 3.0, "M27": 3.0, "M30": 3.5, "M36": 4.0, "M42": 4.5, "M48": 5.0, "M56": 5.5,
    "M64": 6.0,
}  # fmt: skip
VERSION_12_NUTS = {
    "M2": (4.0, 1.6), "M2.5": (5.0, 2.0), "M3": (5.5, 2.4), "M4": (7.0, 3.2),
    "M5": (8.0, 4.7), "M6": (10.0, 5.2), "M8": (13.0, 6.8),
}  # fmt: skip
VERSION_12_WASHERS = {
    "M2": (2.2, 5.0, 0.3), "M2.5": (2.7, 6.0, 0.5), "M3": (3.2, 7.0, 0.5),
    "M4": (4.3, 9.0, 0.8), "M5": (5.3, 10.0, 1.0), "M6": (6.4, 12.0, 1.6),
    "M8": (8.4, 16.0, 1.6),
}  # fmt: skip
VERSION_12_INSERTS = {
    "M2": ("M2", 3.6, 4.0, 3.2), "M2.5": ("M2.5", 4.6, 5.7, 4.0), "M3": ("M3", 4.6, 5.7, 4.0),
    "M3S": ("M3", 4.6, 4.0, 4.0), "M4": ("M4", 6.3, 8.1, 5.6), "M4S": ("M4", 6.3, 4.0, 5.6),
    "M5": ("M5", 7.1, 9.5, 6.4), "M5S": ("M5", 7.1, 5.8, 6.4), "M6": ("M6", 8.7, 12.7, 8.0),
}  # fmt: skip

_SCREW_FIELDS = (
    "nominal",
    "clearance",
    "tap",
    "head",
    "head_height",
    "countersink",
    "hex",
    "pitch",
    "clearance_fine",
    "clearance_coarse",
)


def test_no_value_of_version_12_has_changed() -> None:
    """Die Tabelle weiß mehr, nichts anderes: M2 bis M8, Steigungen und Buchsen wie zuvor."""
    tables = standards.load()
    for size, values in VERSION_12_SCREWS.items():
        screw = tables.screws[size]
        assert tuple(getattr(screw, field) for field in _SCREW_FIELDS) == values, size
    for size, pitch in VERSION_12_PITCHES.items():
        assert tables.screws[size].pitch == pitch, size
    for size, (width, height) in VERSION_12_NUTS.items():
        assert (tables.nuts[size].width, tables.nuts[size].height) == (width, height), size
    for size, values in VERSION_12_WASHERS.items():
        washer = tables.washers[size]
        assert (washer.inner, washer.outer, washer.thickness) == values, size
    for size, values in VERSION_12_INSERTS.items():
        insert = tables.inserts[size]
        assert (insert.thread, insert.outer, insert.length, insert.hole) == values, size


def test_the_metric_series_runs_from_m1_6_to_m64_in_every_table() -> None:
    """Schraube, Mutter und Scheibe führen dieselben 27 ISO-Größen — ohne M60 (keine DIN 912)."""
    tables = standards.load()
    second_choice = ("M33", "M39", "M45", "M52")
    expected = tuple(
        sorted(
            (
                "M1.6",
                "M2",
                "M2.5",
                "M3",
                "M4",
                "M5",
                "M6",
                "M8",
                *VERSION_12_PITCHES,
                *second_choice,
            ),
            key=lambda size: float(size[1:]),
        )
    )
    assert "M60" not in tables.screws
    assert tuple(tables.screws) == expected
    assert set(tables.nuts) == set(expected)
    assert set(tables.washers) == set(expected)
    assert tables.version == "14"


@pytest.mark.parametrize(
    ("table_name", "size", "field", "wanted"),
    [
        # ISO 273, Durchgangsloch mittel: M12 → 13,5.
        ("screws", "M12", "clearance", 13.5),
        ("screws", "M64", "clearance", 70.0),
        # ISO 4762, Kopfdurchmesser dk: M64 → 96, M20 → 30.
        ("screws", "M64", "head", 96.0),
        ("screws", "M20", "head", 30.0),
        # ISO 262, grobe Steigung, und Kernloch d - P.
        ("screws", "M20", "pitch", 2.5),
        ("screws", "M64", "tap", 58.0),
        # ISO 4032, Schlüsselweite: M20 → 30, M10 → 16 (DIN 934 hatte 17).
        ("nuts", "M20", "width", 30.0),
        ("nuts", "M10", "width", 16.0),
        ("nuts", "M64", "height", 51.0),
        # ISO 7089 (fasten.it „DIN EN ISO 7089“), nicht DIN 125.
        ("washers", "M42", "inner", 45.0),
        ("washers", "M42", "outer", 78.0),
        ("washers", "M42", "thickness", 8.0),
        ("washers", "M64", "thickness", 10.0),
        # Zweite Wahl nach ISO 262: Kopf DIN 912 (schraube-mutter.de), Mutter ISO 4032
        # (wermac.org), Durchgang ISO 273 (mechcodex.com, engineeringhardware.com).
        ("screws", "M33", "head", 50.0),
        ("screws", "M39", "hex", 27.0),
        ("screws", "M45", "clearance", 48.0),
        ("screws", "M52", "clearance_coarse", 62.0),
        ("nuts", "M39", "height", 33.4),
        ("nuts", "M52", "width", 80.0),
        ("washers", "M45", "outer", 85.0),
        ("washers", "M20", "outer", 37.0),
        # PreciFast: das Kernloch als Bohrermaß, M12 10,2; M1,6 nach DIN 336 1,25
        # (Wikipedia „Metrisches ISO-Gewinde“ — PreciFast nennt 1,3).
        ("screws", "M12", "tap", 10.2),
        ("screws", "M1.6", "tap", 1.25),
        # DIN 7991 (Aspen Fasteners): Senkkopf dk unter 2·d ab M14.
        ("screws", "M14", "countersink", 27.0),
        ("screws", "M24", "countersink", 39.0),
        # DIN 912 (Aspen Fasteners): Kopf und Innensechskant der M24.
        ("screws", "M24", "head", 36.0),
        ("screws", "M24", "hex", 19.0),
        # Herstellerdatenblätter: Ruthex RX-M8x12,7 d3 = 9,6, CNC Kitchen M10 D2 = 12,0.
        ("inserts", "M8", "hole", 9.6),
        ("inserts", "M10", "hole", 12.0),
        ("inserts", "M3x5x4", "outer", 5.0),
    ],
)
def test_table_values_match_their_published_source(
    table_name: str, size: str, field: str, wanted: float
) -> None:
    """Sollwerte von außen: je ein Katalogmaß mit seiner Herkunft im Kommentar."""
    entry = getattr(standards.load(), table_name)[size]
    assert getattr(entry, field) == pytest.approx(wanted)


@pytest.mark.parametrize("size", list(standards.load().screws))
def test_every_screw_row_agrees_with_a_second_derivation(size: str) -> None:
    """Jede Zeile gegen Regeln, die nicht aus der Tabelle kommen.

    Die Werte stammen aus Katalogtabellen; ein Zahlendreher (46 statt 64)
    fiele in keiner Validierung auf. Die Gegenprobe rechnet aus Nennmaß und
    Steigung nach, was die Normen als Verhältnisse festlegen:

    * Kopfhöhe k = d (ISO 4762); Senkkopf 2·d bis M12, darüber nach DIN 7991
      zwischen 1,6·d und 2·d, und wo die Tabelle ihn rechnet, nach der
      Ableitungsregel aus den genormten Köpfen;
    * Kopf dk = 1,5·d ab M12 auf einen halben Millimeter (M27 hat 40 statt
      40,5 — die Norm rundet auf ganze Millimeter), darunter breiter, bis 1,9·d;
    * Kernloch d − P, oder das Bohrermaß daneben (M8 6,8, M12 10,2);
    * Durchgangsloch mittel 1,06·d bis 1,2·d, grob höchstens 1,3·d;
    * die Scheibenbohrung nach ISO 7089 — aus einer zweiten Norm und einer
      anderen Quelle — ist bis M36 das feine Durchgangsloch, ab M39 das mittlere;
    * Innensechskant zwischen 0,69·d und 0,94·d.
    """
    tables = standards.load()
    screw = tables.screws[size]
    d, pitch = screw.nominal, screw.pitch
    assert screw.head_height == pytest.approx(d)
    if screw.countersink_derived:
        normed = [
            (entry.nominal, (entry.countersink,))
            for entry in tables.screws.values()
            if not entry.countersink_derived
        ]
        assert screw.countersink == pytest.approx(standards._along(normed, d)[0])
    elif d <= 12.0:
        assert screw.countersink == pytest.approx(2.0 * d)
    else:
        assert 1.6 * d <= screw.countersink < 2.0 * d
    if d >= 12.0:
        assert abs(screw.head - 1.5 * d) <= 0.5
    else:
        assert 1.5 * d < screw.head <= 1.9 * d + 1e-9
    assert abs(screw.tap - (d - pitch)) <= 0.05 + 1e-9
    assert 1.06 * d <= screw.clearance <= 1.2 * d + 1e-9
    assert screw.clearance_coarse is not None and screw.clearance_fine is not None
    assert screw.clearance < screw.clearance_coarse <= 1.3 * d + 1e-9
    hole = screw.clearance_fine if d <= 36.0 else screw.clearance
    assert tables.washers[size].inner == hole
    assert 0.69 * d <= screw.hex <= 0.94 * d


@pytest.mark.parametrize("size", list(standards.load().nuts))
def test_every_nut_and_washer_row_agrees_with_a_second_derivation(size: str) -> None:
    """Mutter und Scheibe gegen die Verhältnisse ihrer Normen.

    * Mutter ISO 4032: Schlüsselweite 1,45·d bis 1,6·d ab M10, darunter bis
      2·d; Höhe 0,78·d bis 0,95·d; und sie liegt auf ihrer Scheibe auf —
      die Scheibe ist breiter als die Schlüsselweite.
    * Scheibe ISO 7089: außen 1,75·d bis 2,5·d, Dicke 0,12·d bis 0,27·d.
    """
    tables = standards.load()
    d = tables.screws[size].nominal
    nut = tables.nuts[size]
    washer = tables.washers[size]
    if d >= 10.0:
        assert 1.45 * d <= nut.width <= 1.6 * d + 1e-9
    else:
        assert 1.6 * d <= nut.width <= 2.0 * d + 1e-9
    assert 0.78 * d <= nut.height <= 0.95 * d
    assert nut.width < washer.outer
    assert 1.75 * d <= washer.outer <= 2.5 * d + 1e-9
    assert 0.12 * d <= washer.thickness <= 0.27 * d


def test_a_custom_size_on_a_table_size_is_that_size() -> None:
    """Ø 12 mit eigenem Maß ist die M12 mit ihren Normmaßen, kein abgeleiteter Zwilling."""
    assert standards.derived_screw(12.0) == standards.screw("M12")
    assert standards.derived_nut(20.0) == standards.nut("M20")
    assert standards.derived_washer(64.0) == standards.washer("M64")


def test_a_custom_size_between_two_sizes_lies_between_their_values() -> None:
    """Zwischen zwei Normgrößen liegt jedes Maß auf der Geraden zwischen ihnen.

    Ø 11 liegt in der Mitte von M10 und M12: Durchgangsloch (11 + 13,5) / 2,
    Mutter (16 + 18) / 2. Die Steigung ist die Regelsteigung der M10, das
    Kernloch d − P.
    """
    screw = standards.derived_screw(11.0)
    assert screw.size == ""
    assert screw.clearance == pytest.approx(12.25)
    assert screw.pitch == pytest.approx(1.5)
    assert screw.tap == pytest.approx(9.5)
    assert screw.countersink == pytest.approx(22.0)
    assert not screw.countersink_derived
    assert standards.derived_screw(30.5).countersink_derived, "über M24 kein Senkkopf"
    assert standards.derived_nut(11.0).width == pytest.approx(17.0)
    assert standards.derived_washer(11.0).outer == pytest.approx(22.0)


def test_a_custom_size_beyond_m64_keeps_the_ratios_of_m64() -> None:
    """Über der Reihe bleibt jedes Maß im Verhältnis der größten Normgröße.

    Ø 128 ist die doppelte M64: doppeltes Loch, doppelter Kopf, doppelte
    Mutter — und die Steigung bleibt die 6 mm der M64.
    """
    screw = standards.derived_screw(128.0)
    assert screw.clearance == pytest.approx(140.0)
    assert screw.head == pytest.approx(192.0)
    assert screw.pitch == pytest.approx(6.0)
    nut = standards.derived_nut(128.0)
    assert (nut.width, nut.height) == (pytest.approx(190.0), pytest.approx(102.0))
    assert standards.derived_washer(128.0).thickness == pytest.approx(20.0)


@pytest.mark.parametrize("diameter", [1.6, 1.7, 2.2, 7.0, 9.0, 11.0, 25.0, 60.0, 64.5, 999.0])
def test_a_custom_size_keeps_the_order_of_its_holes(diameter: float) -> None:
    """Kernloch unter dem Nennmaß, darüber fein, mittel, grob — wie jede Tabellenzeile."""
    screw = standards.derived_screw(diameter)
    assert screw.clearance_fine is not None and screw.clearance_coarse is not None
    assert screw.tap < screw.nominal < screw.clearance_fine < screw.clearance
    assert screw.clearance < screw.clearance_coarse
    assert screw.nominal <= screw.head <= screw.countersink
    washer = standards.derived_washer(diameter)
    assert washer.inner < washer.outer
    assert standards.derived_nut(diameter).width < washer.outer


def test_m60_as_a_custom_size_derives_the_iso_values_between_m56_and_m64() -> None:
    """M60 steht nicht in der Tabelle — DIN 912 führt keine Zylinderschraube M60.

    Als eigenes Maß liegt Ø 60 in der Mitte zwischen M56 und M64 und trifft dort
    die Normwerte: Steigung 5,5 (ISO 262), Mutter 90 × 48 (ISO 4032, wermac.org),
    Scheibe 66 × 110 × 10 (ISO 7089, fasten.it), Durchgang 62/66/70 (ISO 273,
    engineeringhardware.com).
    """
    screw = standards.derived_screw(60.0)
    assert screw.pitch == pytest.approx(5.5)
    holes = (screw.clearance_fine, screw.clearance, screw.clearance_coarse)
    assert holes == (pytest.approx(62.0), pytest.approx(66.0), pytest.approx(70.0))
    nut = standards.derived_nut(60.0)
    assert (nut.width, nut.height) == (pytest.approx(90.0), pytest.approx(48.0))
    washer = standards.derived_washer(60.0)
    assert (washer.inner, washer.outer, washer.thickness) == (
        pytest.approx(66.0),
        pytest.approx(110.0),
        pytest.approx(10.0),
    )


def test_a_derived_hexagon_takes_a_wrench_size_of_the_series() -> None:
    """Ein eigenes Maß legt seinen Sechskant auf eine Schlüsselweite (Review RM-532, K-N2).

    Ø 9 bekam 14,5 mm über die Flächen, Ø 13 19,5 mm — dafür gibt es keinen
    Schlüssel. Jetzt nimmt es die nächste Weite der Reihe nach ISO 272; jede
    Mutterweite der Tabelle steht in dieser Reihe, und jenseits bleibt das Maß
    gerechnet.
    """
    tables = standards.load()
    assert {nut.width for nut in tables.nuts.values()} <= set(tables.wrenches)
    assert standards.derived_nut(9.0).width == pytest.approx(15.0)
    assert standards.derived_nut(13.0).width == pytest.approx(19.0)
    assert standards.derived_nut(60.0).width == pytest.approx(90.0)
    for diameter in (2.2, 7.0, 11.0, 25.0, 45.5, 61.0):
        assert standards.derived_nut(diameter).width in tables.wrenches, diameter
    beyond = standards.derived_nut(70.0).width
    assert beyond > max(tables.wrenches) and beyond not in tables.wrenches


# --- Zoll- und Rohrgewinde (Tabellenversion 14, RM-544) ---------------------------

INCH = 25.4


def _rows(family: str) -> list[standards.Thread]:
    return [row for row in standards.load().threads.values() if row.family == family]


@pytest.mark.parametrize(
    ("size", "field", "wanted"),
    [
        # ISO 228-1 nach Wikipedia „British Standard Pipe“: G 1/2 d 20,955, d1 18,631.
        ("G1/2", "nominal", 20.955),
        ("G1/2", "minor", 18.631),
        ("G1", "minor", 30.291),
        # ISO 7-1: R 1/2 hat seine Bezugsebene 8,2 mm über dem kleinen Ende.
        ("R1/2", "gauge", 8.2),
        # ASME B1.1: 1/4-20 UNC hat 0,2500 Zoll außen; #10-32 UNF 0,1900 Zoll.
        ("1/4-20 UNC", "nominal", 0.25 * INCH),
        ("#10-32 UNF", "nominal", 0.19 * INCH),
        # ASME B1.20.1: NPT 1/2 E0 = 0,75843 Zoll, L1 = 0,320 Zoll, D = 0,840 Zoll.
        ("1/2-14 NPT", "pitch_diameter", 0.75843 * INCH),
        ("1/2-14 NPT", "gauge", 0.320 * INCH),
        ("1/2-14 NPT", "outside", 0.840 * INCH),
        # Zweite Quellen (Abgleich RM-544): gewinde-normen.de DIN ISO 228 G 1 1/2 d 47,803;
        # Lehrenhersteller BSPT R 2 d 59,614; mechcodex R 2 Grundmaß 15,9;
        # engineeringtoolbox #3-48 UNC 2,515 mm; machineref NPT 8: E0 8,43359, L1 1,063,
        # D 8,625 Zoll und NPT 24: E0 23,7125, L1 2,375 Zoll.
        ("G1 1/2", "nominal", 47.803),
        ("R2", "nominal", 59.614),
        ("R2", "gauge", 15.9),
        ("#3-48 UNC", "nominal", 2.515),
        ("8-8 NPT", "pitch_diameter", 8.43359 * INCH),
        ("8-8 NPT", "gauge", 1.063 * INCH),
        ("8-8 NPT", "outside", 8.625 * INCH),
        ("24-8 NPT", "pitch_diameter", 23.7125 * INCH),
        ("24-8 NPT", "gauge", 2.375 * INCH),
    ],
)
def test_thread_values_match_their_published_source(size: str, field: str, wanted: float) -> None:
    """Sollwerte von außen, als Zahl der Quelle — nicht aus der Tabelle zurückgelesen."""
    assert getattr(standards.thread(size), field) == pytest.approx(wanted, abs=1e-3)


@pytest.mark.parametrize("size", [row.size for row in _rows("G")])
def test_every_g_row_agrees_with_its_basic_profile(size: str) -> None:
    """ISO 228-1: d1 = d − 2·h mit h = 0,640327·P; die Blätter runden h auf drei Stellen."""
    row = standards.thread(size)
    assert row.minor is not None
    assert row.minor == pytest.approx(row.nominal - 2.0 * 0.640327 * row.pitch, abs=0.0011)


@pytest.mark.parametrize("size", [row.size for row in _rows("R")])
def test_every_r_row_is_its_g_size_in_the_gauge_plane(size: str) -> None:
    """ISO 7-1: In der Bezugsebene hat R die Durchmesser und Gänge von G derselben Größe."""
    row = standards.thread(size)
    parallel = standards.thread("G" + size[1:])
    assert row.nominal == pytest.approx(parallel.nominal)
    assert row.tpi == pytest.approx(parallel.tpi)
    assert 0.0 < row.gauge < row.nominal


@pytest.mark.parametrize("size", [row.size for row in _rows("UNC") + _rows("UNF")])
def test_every_unified_row_is_its_inch_designation(size: str) -> None:
    """ASME B1.1: Der Außendurchmesser steht in der Bezeichnung, #N hat 0,060 + 0,013·N Zoll."""
    row = standards.thread(size)
    name, rest = size.split("-", 1)
    tpi = float(rest.split()[0])
    if name.startswith("#"):
        inches = 0.060 + 0.013 * int(name[1:])
    else:
        whole, _, fraction = name.rpartition(" ") if " " in name else ("", "", name)
        top, _, bottom = fraction.partition("/")
        inches = (float(whole) if whole else 0.0) + (
            float(top) / float(bottom) if bottom else float(top)
        )
    assert row.nominal == pytest.approx(inches * INCH, abs=1e-4)
    assert row.tpi == pytest.approx(tpi)


@pytest.mark.parametrize("size", [row.size for row in _rows("NPT")])
def test_every_npt_row_agrees_with_the_asme_formulas(size: str) -> None:
    """ASME B1.20.1: E0 = D − (0,05·D + 1,1)·p in Zoll; das Nennmaß in der Bezugsebene
    ist E0 + L1/16 + 0,8·p (Gangtiefe 0,8·p um den Flankendurchmesser)."""
    row = standards.thread(size)
    assert row.outside is not None and row.pitch_diameter is not None
    outside, pitch = row.outside / INCH, 1.0 / row.tpi
    assert row.pitch_diameter / INCH == pytest.approx(
        outside - (0.05 * outside + 1.1) * pitch, abs=2e-5
    )
    assert row.nominal == pytest.approx(
        row.pitch_diameter + row.gauge / 16.0 + 0.8 * row.pitch, abs=1e-3
    )


def test_within_a_series_no_two_threads_lie_within_the_reach() -> None:
    """Die Erkennungsgrenze trennt in jeder Reihe jede zylindrische Größe von jeder anderen.

    Zwischen den Reihen gilt das nicht, und das ist die Mehrdeutigkeit, nach der das
    Gegenstück fragt (``counterpart.AMBIGUOUS_THREAD``, Regel 21): Ein gemessenes
    M2 x 0,4 ist ebenso #1-64 UNC (Ø 1,854 x 0,397) und #2-64 UNF. Die Paare stehen
    hier fest, damit eine neue Größe, die eines dazubringt, auffällt.
    """
    sizes = [
        standards.thread_size(size)
        for size in standards.thread_sizes()
        if not standards.thread_size(size).tapered
    ]
    reach = standards.THREAD_SIZE_REACH
    direct = [
        (first.size, second.size)
        for first, second in itertools.combinations(sizes, 2)
        if abs(first.nominal - second.nominal) <= reach[0]
        and abs(first.pitch - second.pitch) <= reach[1]
    ]
    assert all(
        standards.thread_family(first) != standards.thread_family(second)
        for first, second in direct
    ), direct
    assert direct == [
        ("M2", "#1-64 UNC"),
        ("M2", "#2-64 UNF"),
        ("M2.5", "#3-56 UNF"),
        ("M4", "#8-36 UNF"),
        ("M5", "#10-32 UNF"),
    ]


def test_a_tapered_thread_without_its_gauge_plane_is_refused(tmp_path: Path) -> None:
    """Ein kegeliges Gewinde ohne Bezugsebene hätte kein Maß, an dem es gilt."""
    broken = tmp_path / "taper.toml"
    broken.write_text(
        standards._DATA_FILE.read_text(encoding="utf-8")
        + '\n[[threads]]\nsize = "R7"\nfamily = "R"\nnominal = 180.0\ntpi = 11\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as caught:
        standards.load(broken)
    assert caught.value.field == "threads.R7.gauge_for_taper"
    assert caught.value.suggestions


def test_the_thread_series_never_get_finer_as_they_grow(tmp_path: Path) -> None:
    """Dieselbe Zusage wie bei den Schrauben: Die Reihe, aus der ein eigenes Zollmaß seine
    Gänge nimmt (``regular_tpi``), wird mit dem Durchmesser nie feiner."""
    broken = tmp_path / "finer.toml"
    broken.write_text(
        standards._DATA_FILE.read_text(encoding="utf-8")
        + '\n[[threads]]\nsize = "G7"\nfamily = "G"\nnominal = 190.0\ntpi = 14\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as caught:
        standards.load(broken)
    assert caught.value.field == "threads.G7.pitch_rises"


def test_every_thread_size_resolves_and_the_series_keep_their_order() -> None:
    """Jede Größe der Auswahl hat Maße; die Reihen stehen metrisch, G, R, UNC, UNF, NPT."""
    sizes = standards.thread_sizes()
    families = [standards.thread_family(size) for size in sizes]
    order = [family for family, _ in itertools.groupby(families)]
    assert order == list(standards.THREAD_FAMILIES)
    assert len(sizes) == 27 + 24 + 15 + 33 + 23 + 24
    for size in sizes:
        entry = standards.thread_size(size)
        assert entry.nominal > 0.0 and entry.pitch > 0.0
        assert entry.tapered == (entry.family in standards.TAPERED_FAMILIES)
