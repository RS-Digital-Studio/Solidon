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
from pathlib import Path

import pytest

from app.core.export import slicer_profiles as sp
from app.core.knowledge import profiles
from app.core.types import PrinterProfile


def _write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_the_loaded_filaments_carry_profile_colour_and_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    config = user.parent.parent / "ElegooSlicer.conf"
    _write(
        config,
        {
            "presets": {"machine": "Elegoo Centauri Carbon 2 0.4 nozzle"},
            "elegoo_presets": [
                {
                    "machine": "Elegoo Centauri Carbon 2 0.4 nozzle",
                    "filament": "Elegoo PETG PRO @ECC2",
                    "filament_colors": "#9AA0A6",
                }
            ],
        },
    )
    monkeypatch.setattr(sp, "install_root", lambda _executable: installed)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user])

    assert sp.configured_filaments("orca", executable) == (
        sp.SlicerFilament(
            profile="Elegoo PETG PRO @ECC2",
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
    _write(installed, {"type": "filament", "name": name, "filament_type": ["PETG"]})
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
