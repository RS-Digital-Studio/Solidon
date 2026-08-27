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
from app.core.scene import foreign
from app.core.types import Document, Operation, Parameter, Profile


@pytest.fixture(scope="module")
def profile() -> Profile:
    load_operations()
    return profiles.make_profile("centauri-carbon-2", "petg")


def _document(width: float = 30.0) -> Document:
    """Ein Quader, dessen Breite am Projektparameter ``w`` hängt (§13).

    ``format_version`` ist die echte: Seit ``from_data`` den Dokumentteil
    durch die Migrationen schickt, hieße eine 1 hier, dass elf
    Umstellungsschritte über modern geformte Daten laufen.
    """
    from app.core.scene.migrations import FORMAT_VERSION

    return Document(
        format_version=FORMAT_VERSION,
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
    second = recipe.save(made, tmp_path, overwrite=True).read_bytes()
    assert first == second


def test_saving_over_a_foreign_recipe_stops_instead_of_replacing(
    profile: Profile, tmp_path: Path
) -> None:
    """Eine vorhandene Rezeptdatei ist Kundenarbeit — ``save`` ersetzt sie nur
    auf ausdrückliche Absicht.

    Der Dialog lief einmal in die stille Fassung: ``register()`` lehnte den
    doppelten Namen ab, nachdem ``save()`` die alte Datei schon überschrieben
    hatte. Die Meldung sprach von einem Fehlschlag, die Platte trug den
    Verlust.
    """
    made = _recipe(profile)
    target = recipe.save(made, tmp_path)
    before = target.read_bytes()

    with pytest.raises(ValidationError) as caught:
        recipe.save(made, tmp_path)

    assert caught.value.values["recipe"] == made.name
    assert caught.value.suggestions, "Regel 17: auch diese Absage trägt einen Vorschlag"
    assert target.read_bytes() == before, "die vorhandene Datei bleibt unangetastet"


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


def test_a_recipe_is_built_in_the_quality_it_is_asked_for(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checkliste „neuer Baustein", Punkt 5: beide Stufen, und hier besonders.

    Ein Rezept rechnet keinen Körper, sondern einen ganzen Stapel durch
    denselben Auswerter, mit der Rückfallkette je Schritt — es ist der teuerste
    Baustein der Bibliothek. ``build_with_profile`` reichte trotzdem keine
    Qualität durch: Die Vorgabe ``fine`` aus :func:`recipe.build` galt für jeden
    Aufruf, auch für den, mit dem der Kunde gerade iteriert.

    Gemessen an dem Wert, der wirklich beim Auswerter ankommt, nicht an dem, der
    hineingegeben wurde — sonst prüfte der Test seinen eigenen Aufruf.
    """
    import importlib

    # Über ``importlib``, weil ``app.core.scene`` den Namen ``evaluate`` als
    # **Funktion** re-exportiert — gepatcht werden muss das Modul, aus dem
    # ``recipe.build`` sie holt.
    evaluate_module = importlib.import_module("app.core.scene.evaluate")

    seen: list[str] = []
    original = evaluate_module.evaluate

    def spy(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        seen.append(str(kwargs.get("quality")))
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluate_module, "evaluate", spy)

    made = _recipe(profile)
    parts, registry = PartRegistry(), Registry()
    recipe.register(made, parts, registry)
    spec = parts.get("probe_halter")
    assert spec.build_with_profile is not None

    # Was Aufnehmen und Registrieren selbst gerechnet haben, gehört nicht zur
    # Frage — gemessen werden die zwei Aufrufe darunter.
    seen.clear()
    spec.build_with_profile(spec.params(w=40.0), profile, "draft")
    spec.build_with_profile(spec.params(w=40.0), profile)

    assert seen == ["draft", "fine"], (
        f"der Auswerter sah {seen} — die Qualitätsstufe kommt nicht bis zum Stapel durch"
    )


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
    assert spec.own, "§24.5: der Katalog kennzeichnet, was dem Kunden gehört — Rezepte auch"
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
    recipe.save(changed, tmp_path, overwrite=True)
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
    recipe.save(checked, tmp_path, overwrite=True)
    parts2, registry2 = PartRegistry(), Registry()
    recipe.load_all(tmp_path, parts2, registry2)
    assert parts2.get("probe_halter").range_passed is True


# --- E6: der Durchlauf, an dem das Ganze gemessen wird ----------------------------


def test_the_whole_way_from_an_imported_model_to_a_reused_and_changed_part(
    profile: Profile, tmp_path: Path
) -> None:
    """Konzept §19 E6, Schritt für Schritt: Ein Kunde legt aus einem
    **eingelesenen Modell** einen eigenen Baustein an, benutzt ihn in einem
    zweiten Projekt, ändert ihn — und das zweite Projekt meldet es beim
    nächsten Öffnen (§24.4, §15.2).

    Der Durchlauf ist die Abnahme: Jede Stufe benutzt die echten Wege —
    Auswertung, Container, Register, Stempel — und keine Attrappe. Was hier
    hakt, ist der Befund.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    meshes = Path(__file__).parent / "data" / "meshes"

    # 1. Das Ursprungsprojekt: ein eingelesenes Netz, ein Maß als Parameter.
    origin = new_project("centauri-carbon-2", "petg")
    origin.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    origin.sources["src_1"] = (meshes / "cube_clean.stl").read_bytes()
    origin.document.parameters["faktor"] = Parameter(name="faktor", value=1.5)
    History(origin.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    History(origin.document).apply(
        "Skalieren",
        [
            OperationDraft(
                op="scale_object",
                inputs=("obj_1",),
                params={"factor": "@faktor"},
            )
        ],
    )

    # 2. „Als Baustein speichern" — der ganze Stapel, wie es der Dialog tut.
    #    Die Merkmals-ID kommt aus der echten Auswertung, wie im Dialog auch:
    #    Ein eingelesenes Netz benennt seine Flächen selbst (perceive), und
    #    welche die Deckfläche ist, sagt ihre Normale — nicht ein geratener
    #    Name.
    first = evaluate(origin.document, profile, sources=ProjectSources(origin))
    first_body = next(iter(first.scene.objects.values()))
    top = next(
        fid
        for fid, feature in first_body.features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[2] > 0.9
    )
    made = recipe.capture(
        origin.document,
        dict(origin.sources),
        name="mein_klotz",
        title="Mein Klotz",
        group="structure",
        op_ids=tuple(entry.id for entry in origin.document.ops),
        exposed=(
            recipe.ExposedParam(
                name="faktor", title="Faktor", default=1.5, unit="", minimum=0.5, maximum=3.0
            ),
        ),
        features={"deckel": top},
        profile=profile,
    )
    made = recipe.range_check(made, profile)
    assert made.range_report is not None and made.range_report.passed
    recipe.save(made, tmp_path)

    # 3. Laden wie beim Anwendungsstart: Katalog **und** Register global —
    #    exakt der Weg von ``bootstrap.load_user_parts``, denn am globalen
    #    Katalog hängt auch der Stempel beim Speichern (§24.4). Der Ausbau am
    #    Ende ist Pflicht: Die Bausteinsweeps anderer Tests parametrisieren
    #    über denselben Katalog und dürfen dieses Rezept nicht erben.
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    loaded = recipe.load_all(tmp_path, None, None)
    assert loaded.loaded == ("mein_klotz",)
    op_name = part_ops.op_name("mein_klotz")
    assert REGISTRY.has(op_name)

    try:
        _run_the_second_project(profile, tmp_path, made, op_name)
    finally:
        # Der Ausbau: die zwei globalen Einträge, die Schritt 3 angelegt hat.
        PARTS._parts.pop("mein_klotz", None)
        REGISTRY._ops.pop(op_name, None)


def _run_the_second_project(
    profile: Profile, tmp_path: Path, made: recipe.Recipe, op_name: str
) -> None:
    """Die Schritte 4 bis 7 des Durchlaufs — ausgelagert, damit der Ausbau
    der globalen Einträge in einem ``finally`` steht statt am Ende eines
    langen Tests, wo ihn der erste Fehlschlag überspringt."""
    import dataclasses

    from app.core.knowledge.parts import check as part_check
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save

    # 4. Das zweite Projekt benutzt ihn — mit einem eigenen Wert, und die
    #    Geometrie folgt dem Wert (20-mm-Würfel, Faktor 2 → 40 mm Kante).
    second = new_project("centauri-carbon-2", "petg")
    History(second.document).apply(
        "Klotz",
        [OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 4.0})],
    )
    History(second.document).apply(
        "Baustein",
        [
            OperationDraft(
                op=op_name,
                inputs=("obj_1",),
                params={"faktor": 2.0, "at_feature": "face_top"},
            )
        ],
    )
    result = evaluate(second.document, profile, sources=ProjectSources(second))
    assert result.stopped_at is None, "der Baustein muss im zweiten Projekt rechnen"
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.bounds.size[0] == pytest.approx(40.0), (
        "der freigegebene Wert muss bis in die Geometrie wirken"
    )
    assert any(name.endswith("deckel") for name in body.features), (
        "das benannte Merkmal muss am Ergebnis stehen (§24.1)"
    )

    # 5. Speichern stempelt den Stand des Rezepts ins Projekt (§24.4).
    target = tmp_path / "zweites.p3d"
    save(second, target)
    stamped = [key for key in second.document.libs if "mein_klotz" in key]
    assert stamped, "ohne Stempel bliebe jede Änderung des Rezepts stumm"

    # 6. Der Kunde ändert sein Rezept — neue Fassung, gleicher Name.
    changed = dataclasses.replace(made, doc="jetzt mit anderer Beschreibung")
    recipe.save(changed, tmp_path, overwrite=True)
    parts2 = PartRegistry()
    # Ein frisches Register, kein ``None``: global stünde ``insert_mein_klotz``
    # schon, ``register`` nähme seit der Atomarität den Katalogeintrag wieder
    # mit zurück — und dieser Test lebte vorher unbemerkt vom halben Zustand.
    recipe.load_all(tmp_path, parts2, Registry())

    # 7. Das zweite Projekt wieder öffnen: die Änderung wird gemeldet —
    #    derselbe Weg, den die Sitzung beim Öffnen nimmt.
    reopened = load(target)
    findings = part_check.check(reopened.document, parts2)
    assert any(
        finding.code == "parts.own_changed" and "mein_klotz" in str(finding.values.get("parts"))
        for finding in findings
    ), "ein geändertes Rezept muss sich beim Öffnen melden (§24.4)"

    # Und die Gegenrichtung: unverändert heißt still.
    parts3 = PartRegistry()
    recipe.save(made, tmp_path, overwrite=True)
    recipe.load_all(tmp_path, parts3, Registry())
    quiet = part_check.check(reopened.document, parts3)
    assert not any(finding.code == "parts.own_changed" for finding in quiet), (
        "ein unverändertes Rezept darf keine Meldung erzeugen"
    )


# --- Die Härtung nach dem Review vom 26.08.2026 -----------------------------------


def test_a_stopped_stack_is_an_error_not_a_half_body(profile: Profile) -> None:
    """``evaluate`` wirft bei einem gescheiterten Schritt nicht — es hält an
    und behält, was bis dahin entstand. Für einen Baustein wäre das ein halber
    Körper, der wie ein ganzer aussieht; ``build`` muss den Riss melden.

    Der Wächter sitzt **vor** der Körperzählung: Damit ist auch der Fall
    gedeckt, in dem ein früher Schritt einen Körper hinterlässt und ein
    späterer scheitert.
    """
    from app.core.errors import GeometryError

    made = _recipe(profile)
    with pytest.raises(GeometryError) as caught:
        recipe.build(made, {"w": -5.0}, profile=profile)
    assert caught.value.values.get("stopped_at") == 1
    assert caught.value.suggestions, "Regel 17: auch dieser Fehler trägt einen Vorschlag"


def test_a_recipe_from_the_future_is_refused(profile: Profile) -> None:
    """Der Dokumentteil erbt die Migrationen der Projektdatei — und damit auch
    die Sperre gegen eine Datei aus einer neueren Version (``too_new``)."""
    data = recipe.to_data(_recipe(profile))
    data["document"] = dict(data["document"])
    data["document"]["format_version"] = int(data["document"]["format_version"]) + 1
    with pytest.raises(ValidationError) as caught:
        recipe.from_data(data)
    assert caught.value.constraint == "too_new"


def test_a_recipe_with_scripted_source_is_flagged_when_loaded(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 13 hält nur mit Regel 11 zusammen: Trägt ein Rezept einen Schritt
    mit fremdem Quelltext, muss der Nutzer es beim Laden erfahren — dieselbe
    Auskunft, die ``foreign.findings_for`` einer Projektdatei gibt."""
    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    made = _recipe(profile)
    made.document.ops.append(
        Operation(
            id=2,
            op="create_from_scad",
            outputs=("obj_9",),
            params={"source": "cube(1);"},
        )
    )
    recipe.save(made, tmp_path)
    parts, registry = PartRegistry(), Registry()
    result = recipe.load_all(tmp_path, parts, registry)
    assert result.loaded == ("probe_halter",)
    flagged = [entry for entry in result.findings if entry.code == "project.scripted_source"]
    assert flagged, "der Quelltext-Hinweis (§32) muss als Befund mitkommen"
    assert flagged[0].values.get("recipe") == "probe_halter"


def test_a_recipe_that_cannot_become_an_operation_leaves_no_catalog_entry(
    profile: Profile, tmp_path: Path
) -> None:
    """Halb registriert ist schlimmer als gar nicht: Ein Katalogeintrag ohne
    Operation ist ein Knopf, dessen Klick in einem ``InternalError`` endet.

    Nachgestellt über ein Register, das die Operation schon trägt — der
    zweite Ladelauf scheitert an ihr, und der Katalog muss leer bleiben.
    """
    recipe.save(_recipe(profile), tmp_path)
    parts, registry = PartRegistry(), Registry()
    first = recipe.load_all(tmp_path, parts, registry)
    assert first.loaded == ("probe_halter",)

    parts2 = PartRegistry()
    second = recipe.load_all(tmp_path, parts2, registry)
    assert second.loaded == ()
    assert second.findings, "der Grund steht als Befund da, nicht nur im Protokoll"
    assert not parts2.has("probe_halter"), "kein Katalogeintrag ohne Operation"


# --- Die Reise in der Projektdatei (Konzept §17.1) --------------------------------


def _clean_globals(*names: str) -> None:
    """Baut die globalen Einträge eines Reisetests wieder aus — wie bei E6:
    Die Bausteinsweeps anderer Tests parametrisieren über denselben Katalog."""
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    for name in names:
        PARTS._parts.pop(name, None)
        REGISTRY._ops.pop(part_ops.op_name(name), None)


def _travelling_project(profile: Profile, tmp_path: Path, prepared: recipe.Recipe | None = None):
    """Ein Rezept global registriert und ein Projekt, das es benutzt.

    ``prepared`` nimmt ein fertiges Rezept entgegen — für den Fall, in dem der
    Bereichstest nicht laufen darf, weil der Ausschnitt OpenSCAD anwerfen
    würde.
    """
    from app.core.scene.project import Project, save

    made = prepared if prepared is not None else recipe.range_check(_recipe(profile), profile)
    recipe.register(made)
    document = _document()
    document.ops.append(
        Operation(
            id=2,
            op=part_ops.op_name(made.name),
            outputs=("obj_2",),
            params={},
        )
    )
    target = tmp_path / "reise.p3d"
    save(Project(document=document), target)
    return made, target


def _scripted_recipe(profile: Profile, name: str = "probe_halter") -> recipe.Recipe:
    """Ein Rezept, dessen Ausschnitt eine quelltextführende Operation trägt.

    **Welche das ist, sagt** :data:`foreign.SCRIPTED_OPS`, und die ist seit dem
    OpenSCAD-Ausbau am 26.08.2026 leer. Hier stand ``create_from_scad``; heute
    steht eine gewöhnliche Operation da, und der Test setzt die Zuordnung. Was
    geprüft wird, ist die **Auskunft** über den Quelltext — nicht sein Lauf und
    nicht der Name der Operation, die ihn trägt.

    Angehängt statt über ``capture`` aufgenommen: Die Probe in ``capture``
    rechnete den Schritt mit.
    """
    made = _recipe(profile, name)
    made.document.ops.append(
        Operation(id=2, op="create_box", outputs=("obj_9",), params={"width": 10.0})
    )
    return made


def _nesting_recipe(inner: str, name: str) -> recipe.Recipe:
    """Ein Rezept, das ein anderes Rezept einsetzt — Ebene zwei.

    Von Hand gebaut und nicht über ``capture``: Die Probe dort rechnete das
    innere Rezept mit, und genau das soll hier niemand tun müssen, um die
    Frage „startet das fremden Quelltext?" zu beantworten.
    """
    document = _document()
    document.ops.append(Operation(id=2, op=part_ops.op_name(inner), outputs=("obj_2",), params={}))
    return recipe.Recipe(
        name=name,
        title="Probehülle",
        group="structure",
        document=document,
        features={"top": "face_top"},
    )


def test_a_recipe_travels_inside_the_project_file(profile: Profile, tmp_path: Path) -> None:
    """Entscheidung Robert, 24.08.2026: Ein Rezept reist mit der Projektdatei.

    Vorher versprachen Handbuch und Regel-13-Text die Reise, und in
    ``app/core/scene`` stand keine Zeile dafür — der Empfänger bekam
    ``parts.missing`` als Stopp, der Absender keine Warnung. Drei Prüfläufe
    des Reviews fanden es unabhängig.
    """
    import zipfile as zf

    from app.core.knowledge.parts import check as part_check
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY
    from app.core.scene.project import load

    try:
        _made, target = _travelling_project(profile, tmp_path)
        with zf.ZipFile(target) as container:
            assert "recipes/probe_halter.json" in container.namelist(), (
                "das benutzte Rezept muss im Container liegen"
            )

        # Die fremde Maschine: kein Rezept im Katalog, keine Operation.
        _clean_globals("probe_halter")
        loaded = load(target)
        spec = PARTS.get("probe_halter")
        assert spec.source == "travelled", "aufgenommen und als mitgereist gekennzeichnet"
        assert spec.range_passed is True, "der Bereichstest-Bericht reist mit (§24.5)"
        assert REGISTRY.has(part_ops.op_name("probe_halter")), (
            "die Auswertung darf nicht bei parts.missing anhalten"
        )
        findings = part_check.check(loaded.document)
        assert any(entry.code == "parts.travelled" for entry in findings)
        assert not any(entry.code == "parts.missing" for entry in findings)
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")


def test_a_local_part_beats_the_travelled_one(profile: Profile, tmp_path: Path) -> None:
    """„Lokal schlägt mitgereist, immer" (Konzept §17.1): Alles andere wäre
    eine Datei, die von außen den Werkzeugkasten des Kunden umschreibt."""
    import dataclasses

    from app.core.knowledge.parts import check as part_check
    from app.core.knowledge.parts.registry import PARTS
    from app.core.scene.project import load

    try:
        made, target = _travelling_project(profile, tmp_path)
        # Die fremde Maschine trägt unter demselben Namen einen anderen Stand.
        _clean_globals("probe_halter")
        local = dataclasses.replace(made, doc="lokal ein anderer Satz")
        recipe.register(local)

        loaded = load(target)
        assert PARTS.get("probe_halter").version == recipe.fingerprint(local), (
            "der lokale Stand bleibt, was er ist"
        )
        arrived = PARTS.get("probe_halter_travelled")
        assert arrived.source == "travelled", "der mitgereiste bekommt einen eigenen Namen"

        findings = part_check.check(loaded.document)
        assert any(entry.code == "parts.travelled_shadowed" for entry in findings), (
            "der Kunde erfährt, dass sein Stand gilt und der mitgereiste daneben steht"
        )
        assert any(entry.code == "parts.own_changed" for entry in findings), (
            "und §24.4 meldet, dass anders gerechnet wird als beim Absender"
        )
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")


def test_the_same_recipe_arrives_silently(profile: Profile, tmp_path: Path) -> None:
    """Gleicher Abdruck heißt dasselbe Rezept — kein Doppel, kein Befund."""
    from app.core.knowledge.parts.registry import PARTS
    from app.core.scene.project import load

    try:
        _made, target = _travelling_project(profile, tmp_path)
        # Lokal liegt exakt derselbe Stand — die Beilage hat nichts zu tun.
        load(target)
        assert not PARTS.has("probe_halter_travelled")
        assert PARTS.get("probe_halter").source == recipe.RECIPE_SOURCE, (
            "der lokale Eintrag wird nicht zum mitgereisten umgestempelt"
        )
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")


def test_a_travelling_recipe_with_source_code_is_announced_when_the_file_opens(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 13 hält nur mit Regel 11 zusammen — auch für ein Rezept, das aus
    einer **fremden** Datei kommt.

    ``load_all`` sagt es für den eigenen Ordner (Test oben), ``adopt`` sagte es
    nicht: Eine gemailte ``.p3d`` mit einem Rezept, dessen Dokumentteil
    fremden Quelltext trägt, meldete beim Öffnen ``parts.travelled`` und
    kein Wort über den Quelltext. Verlangt ist die Auskunft **vor** der ersten
    Auswertung, also im Bericht der geladenen Datei (§32).
    """
    from app.core.knowledge.parts import check as part_check
    from app.core.scene.project import load

    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    try:
        _made, target = _travelling_project(profile, tmp_path, _scripted_recipe(profile))
        # Die fremde Maschine: kein Rezept im Katalog, keine Operation.
        _clean_globals("probe_halter")
        loaded = load(target)

        scripted = [
            entry for entry in loaded.report.findings if entry.code == "project.scripted_source"
        ]
        assert scripted, "der Quelltext des mitgereisten Rezepts gehört in den Bericht der Datei"
        assert scripted[0].values.get("recipe") == "probe_halter", (
            "und der Befund nennt, in welchem Baustein er steckt"
        )
        assert any(
            entry.code == "parts.scripted_recipe" for entry in part_check.check(loaded.document)
        ), "dieselbe Auskunft aus der zweiten Richtung, über den benutzten Baustein"
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")


def test_a_recipe_inside_a_recipe_still_runs_foreign_source(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Prüfung sah genau **eine** Ebene tief.

    ``capture`` nimmt beliebige Operationen auf, also auch ein ``insert_A``.
    Rezept B trug damit den Quelltext mittelbar, und seine Schrittliste
    nannte nur ``insert_A``: über die Leitung angeboten, ohne Rückfrage
    übernehmbar, und ``parts.check`` schwieg dazu.
    """
    from app.core.knowledge.parts import check as part_check
    from app.core.scene.foreign import runs_foreign_source

    monkeypatch.setattr(foreign, "SCRIPTED_OPS", frozenset({"create_box"}))
    parts, registry = PartRegistry(), Registry()
    recipe.register(_scripted_recipe(profile, "probe_kern"), parts, registry)
    recipe.register(_nesting_recipe("probe_kern", "probe_huelle"), parts, registry)

    assert runs_foreign_source(part_ops.op_name("probe_kern"), parts)
    assert runs_foreign_source(part_ops.op_name("probe_huelle"), parts), (
        "mittelbar ist auch ausgeführt — die Frage gilt der Wirkung"
    )

    document = _document()
    document.ops.append(
        Operation(id=2, op=part_ops.op_name("probe_huelle"), outputs=("obj_2",), params={})
    )
    codes = [entry.code for entry in part_check.check(document, parts)]
    assert "parts.scripted_recipe" in codes


def test_a_recipe_that_names_itself_does_not_loop(profile: Profile) -> None:
    """Der Zyklenwächter: Zwei Rezepte, die einander einsetzen, sind eine
    Datei, die ankommen kann — die Prüfung darf daran nicht hängenbleiben."""
    from app.core.scene.foreign import runs_foreign_source

    parts, registry = PartRegistry(), Registry()
    recipe.register(_nesting_recipe("probe_zwei", "probe_eins"), parts, registry)
    recipe.register(_nesting_recipe("probe_eins", "probe_zwei"), parts, registry)

    assert not runs_foreign_source(part_ops.op_name("probe_eins"), parts)


def test_a_broken_recipe_beside_the_document_is_a_finding_and_not_an_abort(
    profile: Profile, tmp_path: Path
) -> None:
    """„Eine kaputte Beilage ist ein Befund, kein Abbruch" (Regel 17).

    Der Kommentar in ``project.load`` sagte es, und das ``json.loads`` stand
    **außerhalb** des ``try`` in ``adopt``: Eine abgeschnittene
    ``recipes/foo.json`` ließ das ganze Projekt mit „Der Projektinhalt ist
    beschädigt" abbrechen, obwohl das Dokument heil war.
    """
    import zipfile as zf

    from app.core.scene.project import load

    try:
        _made, target = _travelling_project(profile, tmp_path)
        _clean_globals("probe_halter")
        damaged = tmp_path / "beschaedigt.p3d"
        with zf.ZipFile(target) as source, zf.ZipFile(damaged, "w") as broken:
            for entry_name in source.namelist():
                payload = source.read(entry_name)
                if entry_name == "recipes/probe_halter.json":
                    payload = payload[: len(payload) // 2]
                broken.writestr(entry_name, payload)

        loaded = load(damaged)

        assert loaded.document.ops, "das Dokument ist heil und öffnet"
        assert any(entry.code == "parts.recipe_failed" for entry in loaded.report.findings), (
            "der Grund steht als Befund da, statt das Öffnen abzubrechen"
        )
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")


def test_replace_is_one_way_for_both_cases(profile: Profile, tmp_path: Path) -> None:
    """„Ersetzen oder anlegen" ist eine Frage der Knopfbeschriftung, nicht des
    Ablaufs: ``replace`` legt an, wo der Name frei ist, und tauscht sonst
    Datei, Katalogeintrag und Operation **zusammen**.

    Die Operation muss dabei wirklich neu gebunden werden — ``register_one``
    hält den Spec als Vorgabewert, ein neuer Katalogeintrag allein rechnet
    mit dem alten Stand weiter (b0s Messung vom 26.08.2026).
    """
    parts, registry = PartRegistry(), Registry()
    made = _recipe(profile)

    first = recipe.replace(made, parts, registry, tmp_path)
    assert first.exists() and parts.has("probe_halter")

    changed = recipe.capture(
        _document(width=40.0),
        {},
        name="probe_halter",
        title="Probehalter",
        group="structure",
        op_ids=(1,),
        exposed=(
            recipe.ExposedParam(name="w", title="Breite", default=40.0, minimum=10.0, maximum=90.0),
        ),
        features={"top": "face_top"},
        profile=profile,
    )
    recipe.replace(changed, parts, registry, tmp_path)
    assert parts.get("probe_halter").version == recipe.fingerprint(changed), (
        "der Katalog trägt den neuen Stand"
    )

    # Und die **Operation** rechnet mit ihm: Die Vorgabe der Breite ist jetzt
    # 40 — der alte gebundene Spec hätte 30 gerechnet.
    spec = parts.get("probe_halter")
    built = spec.fn(spec.params())
    assert as_mesh_data(built.mesh).volume == pytest.approx(40.0 * 20.0 * 8.0), (
        "die neu gebundene Operation rechnet den neuen Stand"
    )

    import json as json_module

    on_disk = json_module.loads((tmp_path / "probe_halter.json").read_text(encoding="utf-8"))
    assert on_disk["exposed"][0]["default"] == 40.0, "und die Platte trägt ihn auch"


def test_replace_rolls_back_when_the_disk_refuses(profile: Profile, tmp_path: Path) -> None:
    """Halb ersetzt wäre die schlimmste Lage: Scheitert das Schreiben, behalten
    Katalog und Register den alten Stand — sonst rechnete die Sitzung mit
    einem Stand, den der nächste Start nicht mehr kennt."""
    import dataclasses

    parts, registry = PartRegistry(), Registry()
    made = _recipe(profile)
    recipe.replace(made, parts, registry, tmp_path)
    old_version = parts.get("probe_halter").version

    changed = dataclasses.replace(made, doc="neuer Stand")
    blocked = tmp_path / "gesperrt"
    blocked.mkdir()
    (blocked / "probe_halter.json").mkdir()  # ein Ordner, wo die Datei hin will

    with pytest.raises(OSError):
        recipe.replace(changed, parts, registry, blocked)

    assert parts.get("probe_halter").version == old_version, (
        "nach dem Fehlschlag gilt wieder der alte Stand"
    )


def test_a_newer_travelled_version_swaps_the_older_one(profile: Profile, tmp_path: Path) -> None:
    """Zwei Projekte, zwei Fassungen desselben fremden Rezepts: Die zuletzt
    geöffnete gilt. Vorher stand hier eine Absage mit dem Rat, das andere
    Projekt zu schließen — ein Mittel ohne Wirkung, denn Schließen meldet
    nichts ab (Fund des Gesamtreviews vom 25.08.2026)."""
    import dataclasses

    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    try:
        made = recipe.range_check(_recipe(profile), profile)
        # Lokal liegt ein eigener Stand — beide Ankömmlinge landen als
        # ``_travelled`` daneben.
        recipe.register(dataclasses.replace(made, doc="lokal"))

        first = dataclasses.replace(made, doc="erste fremde Fassung")
        second = dataclasses.replace(made, doc="zweite fremde Fassung")
        assert recipe.adopt(recipe.file_data(first)) == []
        assert recipe.adopt(recipe.file_data(second)) == [], "kein Befund, ein Tausch"

        arrived = PARTS.get("probe_halter_travelled")
        renamed = dataclasses.replace(second, name="probe_halter_travelled")
        assert arrived.version == recipe.fingerprint(renamed), "die neuere Fassung gilt"
        # Und dieselbe Fassung noch einmal ist ein stiller Kurzschluss, kein Tausch.
        assert recipe.adopt(recipe.file_data(second)) == []
        assert REGISTRY.has(part_ops.op_name("probe_halter_travelled"))
    finally:
        _clean_globals("probe_halter", "probe_halter_travelled")
