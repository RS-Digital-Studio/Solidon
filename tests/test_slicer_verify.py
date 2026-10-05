"""Die Gegenprobe erkennt verworfene Werte in vollständigen Slicerblöcken."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from app.core.export import handover
from app.core.knowledge import print_settings, profiles


@pytest.mark.parametrize("flavour", ["prusa", "orca"])
def test_complete_configuration_reports_a_discarded_key(flavour: str) -> None:
    """Ein vollständiger Block muss jeden geschriebenen Druckwert bestätigen."""
    findings = handover.verify(
        "; layer_height = 0.2\n", {"chamber_temperature": "35"}, flavour=flavour
    )
    assert len(findings) == 1
    assert findings[0].code == "slicer.setting_ignored"
    assert findings[0].source == "gcode"
    assert findings[0].values == {"count": 1, "settings": "chamber_temperature: 35 → —"}


def test_a_discarded_value_is_named_with_both_values_and_a_way() -> None:
    """„Der Slicer hat Einstellungen anders übernommen“ nannte weder Wert noch
    Ausweg (Anycubic-Matrix, B6). Der Satz nennt jetzt das Feld des
    Druckdialogs, das Geschriebene und das Gedruckte; die Knöpfe führen in den
    Druckdialog und zum Slicerprofil (Regel 17)."""
    from app.core.errors import CHECK_SLICER_PROFILE, OPEN_PRINT_SETTINGS
    from app.core.knowledge import print_fields
    from app.i18n import source_text

    one = handover.verify_settings(
        {"nozzle_temperature": "210"}, {"nozzle_temperature": "235"}, flavour="orca"
    )
    many = handover.verify_settings(
        {"nozzle_temperature": "210", "slow_down_layer_time": "8", "top_shell_layers": "5"},
        {"nozzle_temperature": "235", "slow_down_layer_time": "20", "top_shell_layers": "5"},
        flavour="orca",
    )

    title = source_text(print_fields.field_of("temperature.nozzle").title)
    assert source_text(one[0].message) == f"Der Slicer druckt „{title}“ mit 210 statt 235."
    assert one[0].suggestions == (OPEN_PRINT_SETTINGS, CHECK_SLICER_PROFILE)
    assert many[0].values["count"] == 2
    assert "2 Einstellungen" in source_text(many[0].message)
    assert f"„{title}“ mit 210 statt 235" in source_text(many[0].message)
    unknown = handover.verify_settings({"odd_key": "1"}, {"odd_key": "2"}, flavour="orca")
    assert "„odd_key“ mit 1 statt 2" in source_text(unknown[0].message), "sonst der Schlüssel"
    start = "G28\\nG29\\n" + "M117 Solidon\\n" * 20
    coded = handover.verify_settings(
        {"layer_height": "0.3", "machine_start_gcode": "G28"},
        {"layer_height": "0.2", "machine_start_gcode": start},
        flavour="orca",
    )
    text = source_text(coded[0].message)
    assert "0.3 statt 0.2" in text, "ein Wert geht einem Startcode vor"
    assert start in coded[0].values["settings"], "der ganze Startcode bleibt in den Werten"
    lone = handover.verify_settings(
        {"machine_start_gcode": "G28"}, {"machine_start_gcode": start}, flavour="orca"
    )
    assert start not in source_text(lone[0].message) and "…" in source_text(lone[0].message)


@pytest.mark.parametrize("flavour", [None, "cura"])
def test_partial_configuration_has_no_missing_key_claim(flavour: str | None) -> None:
    """Cura und einzelne Vergleichswerte versprechen keinen vollständigen Block."""
    assert handover.verify_settings({}, {"layer_height": "0.2"}, flavour=flavour) == []


@pytest.mark.parametrize(
    "key,wanted,actual",
    [
        ("brim_type", "outer_only", "no_brim"),
        ("wall_sequence", "outer wall/inner wall", "inner wall/outer wall"),
        ("support_type", "tree(auto)", "normal(auto)"),
    ],
)
def test_enumerated_choices_are_verified(key: str, wanted: str, actual: str) -> None:
    """Die drei gemessenen Aufzählungswerte sind keine Neuberechnung des Slicers."""
    assert handover.verify_settings({key: wanted}, {key: wanted}) == []
    findings = handover.verify_settings({key: actual}, {key: wanted})
    assert len(findings) == 1
    assert findings[0].values["settings"] == f"{key}: {wanted} → {actual}"


@pytest.mark.parametrize(
    "switch,minimum,actual",
    [("1", "50", "50"), ("0", "70", "0"), ("1,0", "50,70", "50;0")],
)
def test_superslicer_fan_alias_matches_its_actual_setting(
    switch: str, minimum: str, actual: str
) -> None:
    """SuperSlicer 2.5.59.13 fasst Schalter und Untergrenze zu default_fan_speed zusammen."""
    written = {"fan_always_on": switch, "min_fan_speed": minimum}
    assert (
        handover.verify_settings(
            {"default_fan_speed": actual}, written, flavour="prusa", program="superslicer"
        )
        == []
    )
    for found in ({}, {"default_fan_speed": "80"}):
        findings = handover.verify_settings(found, written, flavour="prusa", program="superslicer")
        assert len(findings) == 1
        assert findings[0].values["count"] == 1
        assert "default_fan_speed" in findings[0].values["settings"]


@pytest.mark.parametrize("program", ["prusaslicer", ""])
def test_superslicer_alias_does_not_hide_missing_prusa_values(program: str) -> None:
    """PrusaSlicer schreibt weiterhin beide ursprünglichen Schlüssel."""
    written = {"fan_always_on": "1", "min_fan_speed": "50"}
    findings = handover.verify_settings(
        {"default_fan_speed": "50"}, written, flavour="prusa", program=program
    )
    assert len(findings) == 1
    assert findings[0].values["count"] == 2


@pytest.mark.parametrize(
    "key",
    ["filament_retraction_length", "filament_retraction_speed", "filament_z_hop", "filament_wipe"],
)
def test_empty_material_override_is_not_a_requested_value(key: str) -> None:
    """Nur nil bedeutet Vererbung; ein Zahlenwert bleibt auch in gemischten Listen verbindlich."""
    for wanted in ("nil", '["nil", "nil"]'):
        assert handover.verify_settings({}, {key: wanted}, flavour="orca") == []
    for wanted in ("0.4", "nil,0.4"):
        findings = handover.verify_settings({}, {key: wanted}, flavour="orca")
        assert len(findings) == 1
        assert findings[0].values["count"] == 1
    assert handover.verify_settings({}, {key: "nil"}, flavour="prusa")


def test_nil_does_not_exempt_arbitrary_unknown_settings() -> None:
    """Ein unbekannter Schlüssel wird durch den Wert nil nicht zur erlaubten Ausnahme."""
    assert handover.verify_settings({}, {"discarded_setting": "nil"}, flavour="orca")


@pytest.mark.parametrize(
    "program", ["orcaslicer", "elegooslicer", "crealityprint", "anycubicslicernext"]
)
def test_bambu_scarf_switch_is_consumed_only_in_bambu(program: str) -> None:
    """Die verwandten Programme haben diesen belegten Bambu-Schalter nicht."""
    written = {"override_filament_scarf_seam_setting": "1"}
    assert handover.verify_settings({}, written, flavour="orca", program=program) == []
    assert handover.verify_settings({}, written, flavour="orca", program="bambustudio")
    assert handover.verify_settings({}, written, flavour="orca")


def test_anycubic_takes_no_ironing_without_writing_it() -> None:
    """Anycubic Slicer Next nimmt „no ironing“ an und lässt die Zeile im
    Konfigurationsblock weg (gemessen an 2.0.0.3); gebügelt steht sie da.
    Ein anderer Wert, der fehlt, bleibt ein Befund."""
    program = "anycubicslicernext"
    off = {"ironing_type": "no ironing"}
    assert handover.verify_settings({}, off, flavour="orca", program=program) == []
    assert handover.verify_settings({}, off, flavour="orca", program="orcaslicer")
    on = {"ironing_type": "top"}
    assert handover.verify_settings({}, on, flavour="orca", program=program)
    assert (
        handover.verify_settings({"ironing_type": "top"}, on, flavour="orca", program=program) == []
    )


def test_slice_model_passes_the_family_and_exact_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Kundenweg erkennt Verlust und vermeidet zugleich den falschen Aliasbefund."""
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "SuperSlicer.exe"
    executable.touch()
    config_path = tmp_path / "settings.ini"
    config_path.write_text("", encoding="utf-8")
    config = handover.SlicerConfig(
        process=config_path,
        written={"fan_always_on": "1", "min_fan_speed": "50", "layer_height": "0.2"},
    )
    monkeypatch.setattr(handover, "write_config", lambda *_args, **_kwargs: config)

    def write_gcode(
        command: list[str], *_args: object, **_kwargs: object
    ) -> CompletedProcess[bytes]:
        Path(command[command.index("--output") + 1]).write_text(
            "G90\nM82\nG1 Z0.2 F300\nG1 X1 Y0 E0.1\nG1 X5 Y0 E0.2\n; default_fan_speed = 50\n",
            encoding="utf-8",
        )
        return CompletedProcess([], 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", write_gcode)
    profile = profiles.make_profile()
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(executable=executable, flavour="prusa"),
        output_dir=tmp_path,
    )
    ignored = [finding for finding in outcome.findings if finding.code == "slicer.setting_ignored"]
    assert len(ignored) == 1
    assert ignored[0].values == {"count": 1, "settings": "layer_height: 0.2 → —"}
