"""Eigene Bausteine als Rezept (§24.5, Konzept Befestigungssysteme §16–§19).

Ein Rezept ist ein Ausschnitt des Op-Stapels plus die Beschreibung seiner
Parameter — Daten, kein Code. Geprüft werden die Zusagen des Formats: die
runde Reise, der Hash als Version, die Auswertung mit eingesetzten Werten,
die Abweisungen aus Konzept §18 (genau ein Körper, benannte Merkmale) und
der Weg vom Ordner bis ins Register.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import profiles
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts import recipe
from app.core.knowledge.parts.registry import PartRegistry
from app.core.knowledge.parts.user import travelling_parts
from app.core.registry.registry import Registry
from app.core.types import Document, Operation, Parameter, Profile


@pytest.fixture(scope="module")
def profile() -> Profile:
    load_operations()
    return profiles.make_profile("centauri-carbon-2", "petg")


def _document(width: float = 30.0) -> Document:
    """Ein Quader, dessen Breite am Projektparameter ``w`` hängt (§13)."""
    return Document(
        format_version=1,
        app_version="test",
        parameters={"w": Parameter(name="w", value=width)},
        ops=[
            Operation(
                id=1,
                op="create_box",
                outputs=("obj_1",),
                params={
                    "width": "@w",
                    "depth": 20.0,
                    "height": 8.0,
                    "anchor": "corner",
                    "name": "",
                },
            )
        ],
    )


def _recipe(profile: Profile, name: str = "probe_halter") -> recipe.Recipe:
    return recipe.capture(
        _document(),
        {},
        name=name,
        title="Probehalter",
        group="structure",
        op_ids=(1,),
        exposed=(
            recipe.ExposedParam(name="w", title="Breite", default=30.0, minimum=10.0, maximum=90.0),
        ),
        features={"top": "face_top"},
        profile=profile,
    )


# --- Das Format (E2) --------------------------------------------------------------


def test_a_recipe_survives_the_round_trip_and_keeps_its_hash(profile: Profile) -> None:
    """Der Hash ist die Version (§24.4) — er muss die Rundreise überleben.

    Sonst meldete jedes Öffnen eines Projekts einen geänderten Baustein, den
    niemand geändert hat.
    """
    made = _recipe(profile)
    back = recipe.from_data(recipe.to_data(made))
    assert recipe.fingerprint(back) == recipe.fingerprint(made)
    assert back.exposed == made.exposed
    assert back.features == made.features


def test_a_changed_recipe_is_a_different_version(profile: Profile) -> None:
    """Jede Änderung an den Daten ist eine andere Version — per Bauart, ohne
    dass jemand einen Änderungsverlauf pflegt (Konzept §18f)."""
    import dataclasses

    made = _recipe(profile)
    changed = dataclasses.replace(made, doc="ein anderer Satz")
    assert recipe.fingerprint(changed) != recipe.fingerprint(made)


def test_saving_twice_writes_the_same_file(profile: Profile, tmp_path: Path) -> None:
    """Gleiche Daten, gleiche Datei — dieselbe Zusage, die §15.1 der
    Auswertung und ``project.save`` dem Container macht."""
    made = _recipe(profile)
    first = recipe.save(made, tmp_path).read_bytes()
    second = recipe.save(made, tmp_path).read_bytes()
    assert first == second


# --- Die Auswertung (E5) ----------------------------------------------------------


def test_building_with_a_value_moves_the_geometry(profile: Profile) -> None:
    """Parameter hinein, Körper heraus — und der Wert wirkt bis ins Volumen.

    Der Dialogwert ersetzt Wert **und** Ausdruck des Projektparameters; ein
    stehengebliebener Ausdruck wäre die stärkere Quelle, und der Dialog täte
    nichts.
    """
    made = _recipe(profile)
    built = recipe.build(made, {"w": 50.0}, profile=profile)
    assert as_mesh_data(built.mesh).volume == pytest.approx(50.0 * 20.0 * 8.0)
    assert list(built.features) == ["top"], "das Merkmal trägt seinen öffentlichen Namen"

    default = recipe.build(made, profile=profile)
    assert as_mesh_data(default.mesh).volume == pytest.approx(30.0 * 20.0 * 8.0)


def test_a_value_the_recipe_does_not_expose_is_refused(profile: Profile) -> None:
    """Nur freigegebene Parameter sind setzbar — alles andere wäre ein Griff
    am Dialog vorbei in ein fremdes Rezept."""
    made = _recipe(profile)
    with pytest.raises(ValidationError) as caught:
        recipe.build(made, {"depth": 99.0}, profile=profile)
    assert caught.value.suggestions, "auch diese Abweisung schlägt eine Handlung vor"


def test_a_slice_with_two_bodies_is_refused_at_capture(profile: Profile) -> None:
    """Konzept §18a: Ein Baustein ist eine Funktion auf genau einen Körper.

    Abgewiesen wird beim **Speichern** und nicht später halb gebaut — der
    Fehler gehört an die Stelle, an der er behebbar ist.
    """
    document = _document()
    document.ops.append(
        Operation(
            id=2,
            op="create_box",
            outputs=("obj_2",),
            params={"width": 5.0, "depth": 5.0, "height": 5.0, "anchor": "corner", "name": ""},
        )
    )
    with pytest.raises(ValidationError) as caught:
        recipe.capture(
            document,
            {},
            name="zwei_koerper",
            title="Zwei Körper",
            group="structure",
            op_ids=(1, 2),
            exposed=(),
            features={"top": "face_top"},
            profile=profile,
        )
    assert caught.value.constraint == "one_body"


def test_a_recipe_without_named_features_is_refused_at_capture(profile: Profile) -> None:
    """Konzept §18d und §24.1: ohne benannte Merkmale reißt die
    Provenienzkette — und der Fehler hieße sonst erst „beim Laden"."""
    with pytest.raises(ValidationError) as caught:
        recipe.capture(
            _document(),
            {},
            name="ohne_merkmal",
            title="Ohne Merkmal",
            group="structure",
            op_ids=(1,),
            exposed=(),
            features={},
            profile=profile,
        )
    assert caught.value.constraint == "empty"


def test_a_vanished_feature_id_is_refused(profile: Profile) -> None:
    """Ein benanntes Merkmal, das es im Ergebnis nicht gibt, ist ein Fehler
    mit Handlungsvorschlag — kein leerer Eintrag im Katalog."""
    with pytest.raises(ValidationError) as caught:
        recipe.capture(
            _document(),
            {},
            name="falsches_merkmal",
            title="Falsches Merkmal",
            group="structure",
            op_ids=(1,),
            exposed=(),
            features={"griff": "face_gibt_es_nicht"},
            profile=profile,
        )
    assert caught.value.constraint == "unknown_feature"


# --- Vom Ordner ins Register (E1/E5) ----------------------------------------------


def test_a_saved_recipe_loads_into_catalog_and_register(profile: Profile, tmp_path: Path) -> None:
    """Der ganze Weg: speichern, laden, im Katalog stehen, eine Operation
    sein — mit demselben Schema, das ein eingebauter Baustein trüge."""
    recipe.save(_recipe(profile), tmp_path)
    parts, registry = PartRegistry(), Registry()
    result = recipe.load_all(tmp_path, parts, registry)

    assert result.loaded == ("probe_halter",)
    assert not result.findings

    spec = parts.get("probe_halter")
    assert spec.source == recipe.RECIPE_SOURCE
    assert spec.features == ("top",)
    entry = next(e for e in spec.params.spec() if e.name == "w")
    assert (entry.minimum, entry.maximum, entry.unit) == (10.0, 90.0, "mm")

    op = registry.get(part_ops.op_name("probe_halter"))
    assert "face" in op.applies_to, "ein Rezept ist ein Anbauteil wie jedes andere"
    built = spec.fn(spec.params(w=40.0))
    assert as_mesh_data(built.mesh).volume == pytest.approx(40.0 * 20.0 * 8.0)
    assert spec.build_with_profile is not None, "das Profil des Kunden erreicht die Auswertung"


def test_a_broken_file_becomes_a_finding_not_a_crash(profile: Profile, tmp_path: Path) -> None:
    """Regel 17, dieselbe Haltung wie bei den ``.py``-Bausteinen: Eine kaputte
    Datei ist ein Befund mit Namen und Grund, der Rest des Katalogs lädt."""
    recipe.save(_recipe(profile), tmp_path)
    (tmp_path / "kaputt.json").write_text("{das ist kein json", encoding="utf-8")

    parts, registry = PartRegistry(), Registry()
    result = recipe.load_all(tmp_path, parts, registry)

    assert result.loaded == ("probe_halter",)
    assert len(result.findings) == 1
    assert result.findings[0].code == "parts.recipe_failed"
    assert result.findings[0].values["file"] == "kaputt.json"


def test_recipes_do_not_trigger_the_travel_warning(profile: Profile, tmp_path: Path) -> None:
    """``travelling_parts`` warnt vor ``.py``-Bausteinen, die nie mitreisen.

    Ein Rezept ist Daten und darf mitreisen (Regel 13, 24.08.2026) — es
    gehört ausdrücklich **nicht** in diese Warnung, und sein ``source`` hält
    es heraus. Wer das ändert, macht aus jedem Rezept eine falsche Warnung
    beim Speichern.
    """
    recipe.save(_recipe(profile), tmp_path)
    parts, registry = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts, registry)
    assert travelling_parts({"probe_halter": "irgendein-hash"}, parts) == ()


def test_the_recipe_file_is_data_not_code(profile: Profile, tmp_path: Path) -> None:
    """Die Sicherheitslage eines Rezepts ist die einer Projektdatei (§24.5).

    Die Datei nennt Operationsnamen und Zahlen — nichts darin wird
    ausgeführt. Der Test hält fest, was drinsteht, damit ein künftiges Feld
    mit Code-Charakter auffällt statt durchzurutschen.
    """
    path = recipe.save(_recipe(profile), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {
        "format_version",
        "name",
        "title",
        "group",
        "doc",
        "document",
        "payloads",
        "exposed",
        "features",
    }
    assert data["document"]["ops"][0]["op"] == "create_box"


# --- Der Bereichstest (E3) --------------------------------------------------------


def test_the_range_check_passes_a_healthy_recipe_and_keeps_the_hash(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Bericht hängt am Rezept, nicht im Hash — sonst machte das Prüfen
    aus dem Rezept ein anderes, und jedes Projekt meldete beim Öffnen eine
    Änderung, die keine ist (§24.4)."""
    made = _recipe(profile)
    before = recipe.fingerprint(made)
    seen: list[float] = []

    checked = recipe.range_check(made, profile, progress=lambda f, _t: seen.append(f))

    assert checked.range_report is not None and checked.range_report.passed
    assert checked.range_report.checked == 3, "Minimum, Maximum und Vorgabe je Zahl"
    assert recipe.fingerprint(checked) == before
    assert seen and seen[-1] == 1.0, "der Fortschritt meldet sich bis zum Ende (§2.8)"

    # Und der Bericht übersteht die Ablage — der Katalog liest ihn von dort.
    path = recipe.save(checked, tmp_path)
    loaded = recipe.from_data(json.loads(path.read_text(encoding="utf-8")))
    assert loaded.range_report is not None and loaded.range_report.passed
    assert recipe.fingerprint(loaded) == before


def test_a_breaking_corner_is_named_not_hidden(profile: Profile) -> None:
    """Eine brechende Ecke ist das Ergebnis, kein Absturz — und sie nennt
    die Werte, bei denen es geschah (Regel 17 in Berichtsform)."""
    broken = recipe.capture(
        _document(),
        {},
        name="bricht_unten",
        title="Bricht unten",
        group="structure",
        op_ids=(1,),
        # Minimum 0: eine Breite von null ist ein Quader ohne Volumen — die
        # Auswertung lehnt ihn ab, und genau das muss der Bericht erzählen.
        exposed=(
            recipe.ExposedParam(name="w", title="Breite", default=30.0, minimum=0.0, maximum=90.0),
        ),
        features={"top": "face_top"},
        profile=profile,
    )
    checked = recipe.range_check(broken, profile)

    report = checked.range_report
    assert report is not None and not report.passed
    assert report.checked == 3
    assert any(entry.values.get("w") == 0.0 for entry in report.failures), (
        "die brechende Ecke muss ihre Werte nennen"
    )


def test_a_cancelled_check_never_looks_passed(profile: Profile) -> None:
    """Abbruch ist Abbruch (§15.6): was bis dahin geprüft ist, kommt zurück,
    und ein abgebrochener Lauf sieht nie wie ein bestandener aus."""

    class Sofort:
        @property
        def is_cancelled(self) -> bool:
            return True

        def raise_if_cancelled(self) -> None:
            return None

    made = _recipe(profile)
    checked = recipe.range_check(made, profile, cancelled=Sofort())
    report = checked.range_report
    assert report is not None
    assert report.checked == 0
    assert not report.passed, "null geprüfte Ecken sind kein Bestehen"


# --- §24.4: ein geändertes Rezept meldet sich beim Öffnen -------------------------


def test_a_recipe_gets_stamped_and_a_changed_one_is_noticed(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Abdruck eines Rezepts ist seine Version — und ein geändertes
    Rezept trägt beim nächsten Speichern einen anderen (§24.4, §24.5).

    Für ``.py``-Bausteine liest der Abdruck die Datei; für ein Rezept wäre
    das dieselbe Auskunft, teurer — der Hash über die Daten steht schon als
    Version am Katalogeintrag.
    """
    import dataclasses

    from app.core.knowledge.parts.user import fingerprint as part_fingerprint

    recipe.save(_recipe(profile), tmp_path)
    parts, registry = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts, registry)

    first = part_fingerprint("probe_halter", parts)
    assert first, "ein Rezept muss einen Abdruck haben — sonst schweigt §24.4"

    changed = dataclasses.replace(_recipe(profile), doc="ein anderer Satz")
    recipe.save(changed, tmp_path)
    parts2, registry2 = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts2, registry2)
    assert part_fingerprint("probe_halter", parts2) != first, (
        "ein geändertes Rezept muss einen anderen Abdruck tragen"
    )


def test_the_catalog_learns_whether_the_range_check_passed(
    profile: Profile, tmp_path: Path
) -> None:
    """§24.5 verlangt den Warnhinweis im Katalog — die Auskunft dafür ist
    ``PartSpec.range_passed``: ``None`` heißt „nie gefahren", und genau das
    muss der Katalog von einem ungeprüften Rezept erfahren."""
    made = _recipe(profile)
    recipe.save(made, tmp_path)
    parts, registry = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts, registry)
    assert parts.get("probe_halter").range_passed is None, "ungeprüft heißt None, nicht True"

    checked = recipe.range_check(made, profile)
    recipe.save(checked, tmp_path)
    parts2, registry2 = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts2, registry2)
    assert parts2.get("probe_halter").range_passed is True
