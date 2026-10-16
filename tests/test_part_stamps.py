"""Der Abdruck eines eigenen Bausteins übersteht eine Formaterhöhung (FD-212).

Das Speichern legt je benutztem eigenen Baustein einen Abdruck ins Projekt
(``check.stamp``), beim Öffnen vergleicht ``check.changed_own_parts`` ihn mit
dem heutigen Stand, und ``check.saved_states`` sucht den mitgereisten
gespeicherten Stand. Der Abdruck eines Rezepts war der Hash über seine Daten
**samt Formatversion seines Dokuments** — und die steigt beim Öffnen mit jeder
Migration. Nach dem Schritt 52 → 53 passte kein Abdruck aus 0.6.0 mehr: Ein
unveränderter Baustein galt als geändert, und *Gespeicherten Stand verwenden*
fehlte, obwohl der Stand mitgereist war.

Heute rechnet der Abdruck ohne Formatversion; ein Abdruck aus einer älteren
Datei wird so nachgerechnet, wie er damals entstand (Formatversion der Datei).
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.knowledge.parts import check, recipe
from app.core.knowledge.parts.registry import PARTS, used_parts
from app.core.knowledge.parts.user import FINGERPRINT_KEY
from app.core.knowledge.parts.user import fingerprint as user_fingerprint
from app.core.scene.project import load, project_data, save

DATA = Path(__file__).parent / "data"
#: Geschrieben von welle5 (Format 52), wie 0.6.0 speichert: ein Quader mit dem
#: eigenen Rezept ``werkstatt_halter``, Rezept und Abdruck im Container.
OLD_PROJECT = DATA / "projects" / "own_part_v52.p3d"
#: Derselbe Baustein mit anderem Satz, wie er im Nutzerordner liegt.
LOCAL_CHANGE = DATA / "recipes" / "werkstatt_halter_lokal.json"
NAME = "werkstatt_halter"


@pytest.fixture(autouse=True)
def _forget_adopted_parts() -> Iterator[None]:
    """Was ein Fall aufnimmt (mitgereist, Nutzerordner), geht mit ihm: Das
    Aufnehmen registriert in den Registern des Prozesses, und ``conftest``
    räumt nur ``.py``-Bausteine ab."""
    from app.core.registry import REGISTRY

    parts = {spec.name for spec in PARTS.all()}
    operations = {spec.name for spec in REGISTRY.all()}
    yield
    for spec in PARTS.all():
        if spec.name not in parts:
            PARTS.remove(spec.name)
    for operation in REGISTRY.all():
        if operation.name not in operations:
            REGISTRY.remove(operation.name)
    (recipe.recipes_dir() / f"{NAME}.json").unlink(missing_ok=True)


def _with_local_change() -> None:
    target = recipe.recipes_dir()
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LOCAL_CHANGE, target / f"{NAME}.json")
    loaded = recipe.load_all()
    assert NAME in loaded.loaded


def test_the_old_file_keeps_the_format_its_stamp_was_taken_in() -> None:
    stored = project_data(OLD_PROJECT)
    assert stored["format_version"] == 52
    saved = stored["libs"][f"{FINGERPRINT_KEY}{NAME}"]

    document = load(OLD_PROJECT).document

    assert document.libs[f"{FINGERPRINT_KEY}{NAME}"] == f"{saved}{check.STAMP_FORMAT}52"


def test_an_unchanged_own_part_from_0_6_0_is_not_reported_as_changed() -> None:
    """Ohne lokale Fassung rechnet das Projekt mit dem mitgereisten Rezept — es
    ist derselbe Stand, und das Öffnen meldet keine Änderung."""
    document = load(OLD_PROJECT).document

    assert check.changed_own_parts(document, used_parts(document.ops)) == ()
    assert check.saved_states(document) == {}


def test_the_saved_state_of_a_changed_own_part_is_offered_after_the_update() -> None:
    """Liegt lokal ein anderer Stand, meldet das Öffnen die Änderung und bietet
    den mitgereisten gespeicherten Stand an (``keep_saved_parts``)."""
    _with_local_change()
    document = load(OLD_PROJECT).document

    assert check.changed_own_parts(document, used_parts(document.ops)) == (NAME,)
    states = check.saved_states(document)
    assert list(states) == [NAME]
    assert PARTS.get(states[NAME]).source == recipe.TRAVELLED_SOURCE


def test_a_stamp_saved_today_survives_a_later_format(tmp_path: Path) -> None:
    """Gegenprobe für die nächste Formaterhöhung: Der heutige Abdruck trägt
    keine Formatversion, und derselbe Baustein mit einem Dokument aus einem
    anderen Format gibt denselben Abdruck."""
    project = load(OLD_PROJECT)
    saved = save(project, tmp_path / "heute.p3d")
    stamp = project_data(saved)["libs"][f"{FINGERPRINT_KEY}{NAME}"]
    assert stamp.startswith(check.CONTENT_STAMP)
    assert check.STAMP_FORMAT not in stamp

    spec = PARTS.get(NAME)
    assert spec.recipe_data is not None
    today = recipe.from_data(dict(spec.recipe_data))
    later = replace(
        today,
        format_version=today.format_version + 1,
        document=replace(today.document, format_version=today.document.format_version + 1),
    )
    assert recipe.fingerprint(later) == recipe.fingerprint(today)
    assert spec.version == recipe.fingerprint(today)

    reopened = load(saved).document
    assert check.changed_own_parts(reopened, used_parts(reopened.ops)) == ()


@pytest.mark.parametrize("version", [52, 53])
def test_the_old_formula_is_kept_for_old_stamps(version: int) -> None:
    """Der Abdruck aus 0.6.0 lässt sich mit seiner Formatversion nachrechnen."""
    stored = project_data(OLD_PROJECT)
    saved = stored["libs"][f"{FINGERPRINT_KEY}{NAME}"]
    load(OLD_PROJECT)
    spec = PARTS.get(NAME)
    assert spec.recipe_data is not None
    arrived = recipe.from_data(dict(spec.recipe_data))

    again = recipe.fingerprint(arrived, as_format=version)[: len(saved)]

    assert (again == saved) is (version == 52)


def test_a_stamp_from_0_5_3_still_means_the_same_part(tmp_path: Path) -> None:
    """Gegenprobe nach hinten: Ein Abdruck, den 0.5.3 unter Format 46 nahm, passt
    nach dem Öffnen ebenso — in 0.6.0 meldete er eine Änderung, die keine war."""
    import json
    import zipfile

    from app.core.scene.project import PROJECT_ENTRY

    load(OLD_PROJECT)
    spec = PARTS.get(NAME)
    assert spec.recipe_data is not None
    stamp_46 = recipe.fingerprint(recipe.from_data(dict(spec.recipe_data)), as_format=46)[:12]
    older = tmp_path / "aus_0_5_3.p3d"
    with zipfile.ZipFile(OLD_PROJECT) as source, zipfile.ZipFile(older, "w") as target:
        for entry in source.infolist():
            payload = source.read(entry)
            if entry.filename == PROJECT_ENTRY:
                data = json.loads(payload)
                data["format_version"] = 46
                data["libs"][f"{FINGERPRINT_KEY}{NAME}"] = stamp_46
                payload = json.dumps(data).encode("utf-8")
            target.writestr(entry, payload)
    # Aus beiden Registern, sonst nimmt das zweite Öffnen das Rezept nicht auf
    # („operation registered twice“), und der Vergleich ginge ins Leere
    # (Review I, B-1).
    from app.core.knowledge.parts.ops import op_name
    from app.core.registry import REGISTRY

    for spec_entry in PARTS.all():
        if spec_entry.source == recipe.TRAVELLED_SOURCE:
            PARTS.remove(spec_entry.name)
            REGISTRY.remove(op_name(spec_entry.name))
    assert not PARTS.has(NAME)

    document = load(older).document

    assert PARTS.has(NAME), "das mitgereiste Rezept ist aufgenommen"
    assert user_fingerprint(NAME), "der heutige Abdruck ist da — sonst ist der Vergleich leer"
    assert document.libs[f"{FINGERPRINT_KEY}{NAME}"] == f"{stamp_46}{check.STAMP_FORMAT}46"
    assert check.changed_own_parts(document, used_parts(document.ops)) == ()
