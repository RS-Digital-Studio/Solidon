"""Eine Buchung aus 0.6.0 für einen Körper aus eigenem Rezept bleibt derselbe Druck (FD-232).

Der Buchungsabdruck aus gespeicherten Eingängen nimmt je Schritt die Fassung des
Bausteins (``filament_usage._part_versions``), bei einem eigenen Rezept dessen
Hash. Bis FD-212 stand darin die Formatversion des Rezeptdokuments, in 0.6.0
also 52; seither rechnet der Hash ohne sie. Derselbe Druck hieß in 0.6.0 deshalb
anders als heute, die Buchung von damals war kein Kandidat mehr, und im Modus
*Ohne Rückfrage buchen* zog die Anwendung denselben Druck still ein zweites Mal
ab. Heute steht der Abdruck von 0.6.0 als Vorabdruck da (``verbrauch.md``: nie
still ersetzen).

``data/projects/usage_own_part_v52.p3d`` hat der Code von Tag ``v0.6.0``
geschrieben (Review I, ``gen_own_part.py``): ein Quader mit dem eigenen Rezept
``werkstatt_halter``, ohne Drucker, Material und Druckeinstellungen.
:data:`BOOKED_060` hat ebenfalls der Code von ``v0.6.0`` gerechnet, aus
``git archive v0.6.0`` auf demselben Weg wie die Anwendung
(``buchung060.py`` im Fixbericht): Sollwert von außen.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core import filament_usage as usage
from app.core.export import manufacturer
from app.core.knowledge import filaments, profiles
from app.core.knowledge.parts.registry import PARTS
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import MaterialSlot
from app.ui import filament_usage as ui

PROJECT = Path(__file__).parent / "data" / "projects" / "usage_own_part_v52.p3d"
#: Der Abdruck, unter dem 0.6.0 diesen Druck gebucht hat.
BOOKED_060 = "si1-783938a16ab805cb5c760d58a070fb41"
#: Die Fassung des Rezepts, wie 0.6.0 sie rechnete (Format 52 im Hash).
VERSION_060 = "1ac66d32c23dc3d639c8113be233f8de63673d79e18eaa76a1e4b2608c52ee75"


@pytest.fixture(autouse=True)
def _forget_adopted_parts() -> Iterator[None]:
    """Das mitgereiste Rezept geht mit dem Fall aus beiden Registern."""
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


def _request() -> usage.UsageRequest:
    """Derselbe Druck nach dem Update, auf dem Weg der Anwendung ohne Slicer."""
    project = load(PROJECT)
    document = project.document
    # Wie ``Session.open_project``: Ohne Drucker und Material gelten die Vorgaben.
    document.printer = document.printer or profiles.DEFAULT_PRINTER
    document.material = document.material or profiles.DEFAULT_MATERIAL
    profile = profiles.make_profile(document.printer, document.material)
    stored = document.print_settings
    quality = stored.quality if stored is not None else "standard"
    settings = manufacturer.effective(stored, manufacturer.base_settings(profile, quality, None))
    sources = ProjectSources(project)
    result = evaluate(document, profile, sources=sources)
    return usage.prepare(
        list(result.scene.objects.values()),
        settings,
        profile,
        "Halter",
        inputs=usage.StoredInputs(document, sources, result.stopped_at),
    )[0]


def test_the_part_version_of_060_is_recomputed() -> None:
    document = load(PROJECT).document
    insert = next(entry for entry in document.ops if entry.op.startswith("insert_"))
    assert usage._part_versions(insert, part_format=usage.PART_FORMAT_060) == [VERSION_060]
    assert usage._part_versions(insert) != [VERSION_060]


def test_the_booking_of_060_is_the_same_print() -> None:
    request = _request()

    assert request.fingerprint != BOOKED_060, "der Abdruck rechnet heute ohne Formatversion"
    assert BOOKED_060 in request.former_fingerprints
    assert BOOKED_060 in request.identities


def test_the_booking_of_060_is_found_and_not_booked_twice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Kundenweg: Die Buchung aus 0.6.0 liegt im Lager; nach dem Update findet
    die Ausgabe sie als denselben Druck, statt ihn ein zweites Mal abzuziehen."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    spool = filaments.save(
        filaments.CatalogueFilament("PLA", "#ffffff", "PLA", remaining_grams=500)
    )
    line = usage.UsageLine(
        MaterialSlot(0, "PLA", (1.0, 1.0, 1.0), material_type="PLA"), 12.0, spool.identifier
    )
    position = filaments.BookingPosition(
        spool.identifier, 12.0, "internal", ui._note(line), filament_key=ui._line_key(line)
    )
    filaments.book("druck-aus-060", BOOKED_060, [position], project_name="Halter")

    request = _request()

    previous = ui._previous(request, filaments.read_snapshot())
    assert [one.operation_id for one in previous] == ["druck-aus-060"]
