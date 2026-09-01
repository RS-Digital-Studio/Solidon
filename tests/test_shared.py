"""Die Formatprüfung lokaler Bausteindateien — Missbrauchs- und Grenzfälle."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.shared import (
    MAX_DOC_CHARS,
    MAX_EXPOSED,
    MAX_FILE_BYTES,
    MAX_OPERATIONS,
    MAX_PARAMETER_LIST_ITEMS,
    MAX_PARAMS_PER_OPERATION,
    MAX_PART_FILE_JSON_DEPTH,
    MAX_PAYLOADS,
    MAX_PROJECT_PARAMETERS,
    MAX_SOURCES,
    MAX_TITLE_CHARS,
    MAX_TOTAL_OPERATION_PARAMS,
    MAX_VALUE_CHARS,
    for_export,
    inspect,
    rules,
)


@pytest.fixture(autouse=True)
def _the_whole_registry() -> None:
    """Ohne ``load_operations()`` ist die Erlaubnisliste leer.

    Und eine leere Erlaubnisliste weist **alles** ab — der Test wäre grün, weil
    er nichts durchlässt, und niemand erführe, dass die Liste gar nicht steht.
    Dieselbe Zusicherung wie bei den Oberflächengrenzen, aus demselben Grund.
    """
    load_operations()


def recipe(**changes: Any) -> bytes:
    """Ein Rezept, wie die Anwendung es schreibt — mit gezielten Abweichungen."""
    base: dict[str, Any] = {
        "name": "halter",
        "title": "Kabelhalter",
        "group": "mounting",
        "document": {
            "format_version": 19,
            "ops": [{"id": 1, "op": "create_box", "params": {"width": 20.0, "depth": 10.0}}],
        },
        "payloads": {},
        "exposed": [],
        # Ein Baustein ohne benanntes Merkmal lässt sich nicht einsetzen
        # (§24.1) — ein leeres Wörterbuch war hier nie ein gültiger Wert.
        "features": {"top": "face_top"},
        "doc": "Hält ein Kabel an der Tischkante.",
        "format_version": 1,
    }
    base.update(changes)
    return json.dumps(base, ensure_ascii=False).encode("utf-8")


def codes(findings: list) -> set[str]:
    """Die Schlüssel einer Befundliste.

    **Geprüft wird der Schlüssel und nicht der Satz.** Ein Test auf „kein
    gültiges JSON" wird bei jeder Umformulierung rot, ohne dass sich am
    Verhalten etwas geändert hätte — und er ist zugleich zu weich, weil eine
    Teilzeichenkette zufällig zutreffen kann („2" steht auch in „2,40 mm").
    Der Schlüssel ist die Entscheidung; der Satz ist ihre Anzeige.
    """
    return {finding.code for finding in findings}


def test_the_list_of_allowed_operations_comes_from_the_registry() -> None:
    """Von Hand geführt wäre sie beim nächsten Zuwachs falsch.

    Der lokale Import wiese dann Rezepte ab, die die Anwendung selbst erzeugt hat — und
    der Kunde sähe nur, dass sein Baustein verschwindet. Deshalb ist die Liste
    abgeleitet und nicht aufgezählt.
    """
    from app.core.registry import REGISTRY

    known = rules()
    assert known["operations"], "die Erlaubnisliste ist leer — dann weist sie alles ab"
    assert set(known["operations"]) == {entry.name for entry in REGISTRY.all()}
    # Und die Rezeptschlüssel ebenso: Wer ein Feld an ``Recipe`` hängt, ändert
    # die Liste, ohne sie anzufassen.
    assert "payloads" in known["recipe_keys"]
    assert "document" in known["recipe_keys"]


def test_a_recipe_the_application_wrote_is_accepted() -> None:
    """Die Gegenprobe zu allem darunter: Der Normalfall kommt durch.

    Ohne sie prüfte diese Datei nur, dass **irgendetwas** abgewiesen wird — und
    eine Erlaubnisliste, die nichts durchlässt, erfüllt das mühelos.
    """
    assert inspect(recipe()) == []


def test_a_broken_file_is_named_as_broken() -> None:
    """Kein JSON, kein Objekt, keine Version — drei Wege, gar nicht erst
    anzufangen."""
    assert "check_not_json" in codes(inspect(b"{ das ist kaputt"))
    assert "check_not_json" in codes(inspect(b"\xff\xfe\x00"))
    assert "check_not_object" in codes(inspect(b"[1, 2, 3]"))
    assert "check_bad_version" in codes(inspect(recipe(format_version=99)))


def test_an_unknown_key_does_not_slip_through() -> None:
    """Die Erlaubnisliste ist abgeschlossen — was nicht daraufsteht, kommt nicht
    durch.

    Der Fall ist der Kern von §3.1: Eine Sperrliste müsste jeden denkbaren
    Schlüssel kennen, eine Erlaubnisliste nur die eigenen. Ein Feld namens
    ``__class__`` oder ``eval`` fällt damit ohne eigene Regel.
    """
    # Über ein Wörterbuch und nicht als Schlüsselwort: ``__class__`` ist ein
    # gültiger JSON-Schlüssel und kein gültiger Python-Bezeichner — und genau
    # so käme er auch in einer hochgeladenen Datei an.
    smuggled = json.loads(recipe())
    smuggled["__class__"] = "os.system"
    findings = inspect(json.dumps(smuggled).encode("utf-8"))
    assert "check_unknown_keys" in codes(findings), findings
    # Der Schlüssel sagt die Art, der Wert sagt **welcher** — beides gehört zur
    # Zusage: Eine Meldung, die den Namen nicht nennt, schickt den Kunden auf
    # die Suche.
    assert any("__class__" in str(one.values.get("keys", "")) for one in findings), findings


def test_an_unregistered_operation_is_refused() -> None:
    """Ein Schritt, den die Anwendung nicht kennt, wird nicht ausgeführt — und
    nicht angenommen.

    Das ist die Stelle, an der ein Rezept aufhört, „nur Namen und Zahlen" zu
    sein: Ein Name, den niemand kennt, ist ein Versprechen an einen Empfänger,
    das niemand einlösen kann.
    """
    document = {
        "format_version": 19,
        "ops": [{"id": 1, "op": "run_shell_command", "params": {"cmd": "rm -rf /"}}],
    }
    findings = inspect(recipe(document=document))
    assert "check_step_unknown_op" in codes(findings), findings
    assert any(one.values.get("name") == "run_shell_command" for one in findings), findings


def test_a_parameter_that_is_not_a_plain_value_is_refused() -> None:
    """Zahl, Text, Wahrheitswert, Liste davon — und nichts sonst.

    Ein Wörterbuch als Parameterwert ist die Form, in der sich eine
    verschachtelte Struktur einschmuggelt; kein Parameter des Registers braucht
    eine. Eine Liste von Zahlen dagegen ist alltäglich und muss durchkommen.
    """
    nested = {
        "format_version": 19,
        "ops": [{"id": 1, "op": "create_box", "params": {"width": {"$ref": "irgendwas"}}}],
    }
    assert "check_value_not_allowed" in codes(inspect(recipe(document=nested))), (
        "ein verschachtelter Parameterwert kam durch"
    )

    plain = {
        "format_version": 19,
        "ops": [{"id": 1, "op": "sculpt_strokes", "params": {"strokes": [1.0, 2.0, 3.0]}}],
    }
    assert inspect(recipe(document=plain)) == [], "eine Liste von Zahlen ist ein gültiger Parameter"


def test_text_is_bounded_but_plain_content_is_preserved() -> None:
    """Dateien begrenzen Textmengen, verändern ihren Inhalt aber nicht."""
    long_title = inspect(recipe(title="x" * (MAX_TITLE_CHARS + 1)))
    assert "check_field_too_long" in codes(long_title), long_title
    # Die Zahlen gehören zur Zusage: Der Vergleich beider Prüfseiten hängt an
    # ihnen, seit die Sätze aus einer gemeinsamen Quelle kommen.
    assert long_title[0].values == {
        "field": "title",
        "length": MAX_TITLE_CHARS + 1,
        "limit": MAX_TITLE_CHARS,
    }, long_title[0].values

    assert inspect(recipe(doc="Mehr davon auf https://beispiel.test")) == []
    assert inspect(recipe(doc="<script>bleibt gewöhnlicher Text</script>")) == []


def test_a_file_over_the_size_limit_is_refused_before_anything_else() -> None:
    """Fünfundzwanzig Megabyte, und die Grenze steht vor der Inhaltsprüfung
    (§3.6).

    Payloads reisen base64-kodiert und wachsen dabei um ein Drittel. Die Grenze
    zuerst zu prüfen ist keine Optimierung, sondern die Zusage: Eine Datei, die
    zu groß ist, wird nicht erst geparst.
    """
    huge = b'{"name": "x", "title": "' + b"z" * (MAX_FILE_BYTES + 10) + b'"}'
    findings = inspect(huge)
    assert "file_too_large" in codes(findings), findings


def test_a_payload_that_is_not_base64_is_refused() -> None:
    """Anhänge werden gemessen, nicht ausgeführt — aber sie müssen lesbar sein.

    Ein Anhang, der kein base64 ist, kommt nie bei einem Empfänger an; ihn
    anzunehmen hieße, eine Kachel zu veröffentlichen, die beim ersten Öffnen
    scheitert.
    """
    good = base64.b64encode(b"solid netz\n").decode("ascii")
    assert inspect(recipe(payloads={"src_1": good})) == []

    findings = inspect(recipe(payloads={"src_1": "das ist kein base64!!"}))
    assert "check_payload_not_base64" in codes(findings), findings


@pytest.mark.parametrize(
    ("changes", "field"),
    (
        (
            {
                "document": {
                    "ops": [],
                    "parameters": {f"p{i}": {} for i in range(MAX_PROJECT_PARAMETERS + 1)},
                }
            },
            "parameters",
        ),
        (
            {"document": {"ops": [], "sources": {f"s{i}": {} for i in range(MAX_SOURCES + 1)}}},
            "sources",
        ),
        ({"payloads": {f"p{i}": "" for i in range(MAX_PAYLOADS + 1)}}, "payloads"),
        ({"exposed": [{} for _ in range(MAX_EXPOSED + 1)]}, "exposed"),
    ),
)
def test_resource_collections_have_hard_limits(changes: dict[str, Any], field: str) -> None:
    """Kleine Einträge dürfen die Prüfung nicht grenzenlos vervielfachen."""

    findings = inspect(recipe(**changes))

    assert any(
        finding.code == "check_too_many_entries" and finding.values.get("field") == field
        for finding in findings
    ), findings


def test_operations_and_their_parameters_have_individual_and_total_limits() -> None:
    """Die Dateigröße allein begrenzt die Bauarbeit eines Rezepts nicht."""

    too_many_steps = {
        "ops": [{"op": "create_box", "params": {}} for _ in range(MAX_OPERATIONS + 1)]
    }
    assert "check_too_many_entries" in codes(inspect(recipe(document=too_many_steps)))

    too_many_in_one = {
        "ops": [
            {
                "op": "create_box",
                "params": {f"p{i}": i for i in range(MAX_PARAMS_PER_OPERATION + 1)},
            }
        ]
    }
    assert "check_too_many_params" in codes(inspect(recipe(document=too_many_in_one)))

    params_per_step = MAX_PARAMS_PER_OPERATION
    step_count = MAX_TOTAL_OPERATION_PARAMS // params_per_step + 1
    too_many_total = {
        "ops": [
            {
                "op": "create_box",
                "params": {f"p{i}": i for i in range(params_per_step)},
            }
            for _ in range(step_count)
        ]
    }
    assert "check_too_many_total_params" in codes(inspect(recipe(document=too_many_total)))


def test_parameter_strings_and_lists_have_hard_limits() -> None:
    """Ein einzelner Parameter darf keine zweite große Nutzlast verstecken."""

    document = {
        "ops": [
            {
                "op": "create_box",
                "params": {
                    "text": "x" * (MAX_VALUE_CHARS + 1),
                    "items": list(range(MAX_PARAMETER_LIST_ITEMS + 1)),
                },
            }
        ]
    }
    findings = inspect(recipe(document=document))

    assert sum(finding.code == "check_value_not_allowed" for finding in findings) == 2


def test_operation_edges_and_range_failures_have_hard_limits() -> None:
    """Auch Metadaten neben den Parametern dürfen die Datei nicht unbeschränkt aufblasen."""

    step = {
        "op": "create_box",
        "params": {},
        "in": [f"i{i}" for i in range(rules()["max_operation_inputs"] + 1)],
        "out": [f"o{i}" for i in range(rules()["max_operation_outputs"] + 1)],
        "matches": {f"m{i}": {} for i in range(rules()["max_matches_per_operation"] + 1)},
        "translatable": [f"t{i}" for i in range(rules()["max_translatable_per_operation"] + 1)],
    }
    failures = [{} for _ in range(rules()["max_range_failures"] + 1)]
    findings = inspect(recipe(document={"ops": [step]}, range_report={"failures": failures}))

    limited_fields = {
        finding.values.get("field")
        for finding in findings
        if finding.code == "check_too_many_entries"
    }
    assert {
        "ops.1.in",
        "ops.1.out",
        "ops.1.matches",
        "ops.1.translatable",
        "range_report.failures",
    } <= limited_fields


def test_unknown_operation_parameters_and_nonfinite_numbers_are_rejected() -> None:
    """Parameter müssen zum registrierten Schema gehören; NaN ist kein JSON-Wert."""

    unknown = {"ops": [{"op": "create_box", "params": {"geheim": 1}}]}
    assert "check_unknown_params" in codes(inspect(recipe(document=unknown)))
    assert "check_not_json" in codes(inspect(b'{"format_version": 1, "value": NaN}'))


def test_lone_utf16_surrogates_are_invalid_but_non_bmp_text_is_valid() -> None:
    """Import und Export müssen dieselbe UTF-8-Grenze ziehen."""

    encoded = recipe().decode("utf-8")
    invalid_value = encoded.replace('"title": "Kabelhalter"', '"title": "\\ud800"')
    invalid_key = encoded.replace('"title": "Kabelhalter"', '"\\udfff": "Kabelhalter"')
    assert "check_not_json" in codes(inspect(invalid_value.encode()))
    assert "check_not_json" in codes(inspect(invalid_key.encode()))

    valid = recipe(title="Prüfrezept mit \U00020000")
    assert inspect(valid) == []


def test_json_nesting_has_a_hard_limit_before_schema_processing() -> None:
    """Viele kleine Container dürfen keinen tiefen Parserpfad erzwingen."""

    depth = MAX_PART_FILE_JSON_DEPTH + 8
    nested = b"[" * depth + b"0" + b"]" * depth
    payload = recipe()[:-1] + b', "too_deep": ' + nested + b"}"

    assert codes(inspect(payload)) == {"check_not_json"}


def test_imported_origin_is_closed() -> None:
    """Eine Dateiherkunft ist lesbar, aber nicht frei erweiterbar."""

    valid = {
        "source_sha256": "b" * 64,
        "imported_at": "2026-08-31T15:16:17Z",
    }
    assert inspect(recipe(imported_origin=valid)) == []

    cases = (
        ("kein Objekt", "check_imported_origin_not_object"),
        ({**valid, "path": "C:/privat/teil.json"}, "check_imported_origin_keys"),
        ({**valid, "source_sha256": "B" * 64}, "check_imported_origin_sha256"),
        ({**valid, "imported_at": "gestern"}, "check_imported_origin_imported_at"),
    )
    for value, expected in cases:
        assert expected in codes(inspect(recipe(imported_origin=value)))


def test_every_finding_is_reported_at_once() -> None:
    """Eine Ablehnung, die nach jedem Berichtigen eine neue nennt, ist eine
    Kette ohne Ende.

    Der Kunde bekommt seine Datei einmal zurück, mit allem, was daran fehlt.
    """
    findings = inspect(
        recipe(
            title="x" * (MAX_TITLE_CHARS + 1),
            doc="y" * (MAX_DOC_CHARS + 1),
            format_version=99,
            document={"format_version": 19, "ops": [{"id": 1, "op": "gibt_es_nicht"}]},
        )
    )
    assert len(findings) >= 4, f"vier Gründe, gemeldet wurden {len(findings)}: {findings}"


# --- Der Anschluss: die Anwendung weist ab, was die Prüfung abweist -----------


def a_recipe(**changes: Any) -> Any:
    """Ein Rezept als Objekt — so, wie die Anwendung es vor dem Teilen hält.

    Der Baukasten oben (:func:`recipe`) baut die **Datei**; dieser baut das
    **Objekt**, aus dem sie entsteht. Beide werden gebraucht, und zwar an den
    zwei Enden derselben Kette: Was der Dateileser sieht, sind Bytes; was der
    Kunde in der Hand hat, ist ein ``Recipe``.
    """
    from app.core.knowledge.parts.recipe import Recipe
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.types import Document, Operation

    document = Document(
        format_version=FORMAT_VERSION,
        app_version="test",
        ops=[
            Operation(
                id=1,
                op=changes.pop("op", "create_box"),
                outputs=("obj_1",),
                params={"width": 20.0, "depth": 10.0, "height": 8.0},
            )
        ],
    )
    fields: dict[str, Any] = {
        "name": "halter",
        "title": "Kabelhalter",
        "group": "mounting",
        "document": document,
        "doc": "Hält ein Kabel an der Tischkante.",
        # Ohne benanntes Merkmal ließe sich der Baustein nicht einsetzen
        # (§24.1), und ``inspect`` weist ihn ab — der Objekt-Baukasten muss
        # dasselbe liefern wie der für die Datei.
        "features": {"top": "face_top"},
    }
    fields.update(changes)
    return Recipe(**fields)


def test_the_part_file_comes_out_of_one_door_and_that_door_checks() -> None:
    """Der gute Fall — und ohne ihn wäre der Test darunter wertlos.

    Ein Wächter „nichts Verbotenes kommt heraus" ist über einer Tür, die
    **immer** zuschlägt, genauso grün wie über einer, die richtig prüft. Also
    steht hier zuerst die Zusicherung, dass überhaupt etwas herauskommt: echte
    Bytes, gültiges JSON, und von der Prüfung selbst nicht beanstandet.
    """
    payload = for_export(a_recipe())

    assert payload, "aus einem gültigen Rezept muss eine Datei entstehen"
    assert json.loads(payload)["name"] == "halter"
    assert inspect(payload) == [], "die Tür gibt heraus, was ihre eigene Prüfung ablehnt"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"title": "H" * (MAX_TITLE_CHARS + 1)}, id="Titel zu lang"),
        pytest.param({"doc": "H" * (MAX_DOC_CHARS + 1)}, id="Text zu lang"),
        pytest.param({"op": "erfinde_mir_was"}, id="unbekannte Operation"),
    ],
)
def test_the_application_refuses_to_hand_out_what_the_check_refuses(
    changes: dict[str, Any],
) -> None:
    """Nicht „die Prüfung kann prüfen", sondern „die Anwendung weist ab".

    Der Unterschied ist der ganze Punkt. ``inspect`` stand eine Stunde lang
    vollständig da — zwölf Grenzfälle und drei Wächter — und hatte **keinen
    einzigen Aufrufer**: gemessen mit
    ``grep`` über den ganzen Baum, ein Treffer, und der galt ``rules``. Eine
    Kette endet am letzten Glied, und das letzte Glied fehlte.

    Deshalb wird hier **beides** gemessen und nicht eines: dass die Prüfung
    den Fall findet, **und** dass der Ausgabeweg ihn nicht herausgibt. Wären
    es zwei Tests, könnte einer grün bleiben, während der andere aufhört zu
    gelten — genau die Naht, an der es schon einmal auseinanderging.
    """
    from app.core.errors import ValidationError

    faulty = a_recipe(**changes)

    with pytest.raises(ValidationError) as refused:
        for_export(faulty)

    assert refused.value.values["findings"], "die Absage nennt den Grund nicht"
    assert refused.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“ (Regel 17)"


# --- Lizenz und Autor: die zwei Felder, die eine Weitergabe erlauben ----------


def test_the_licences_come_from_the_recipe_core_not_from_a_second_list() -> None:
    """Die Wertemenge gehört dem Kern; der Dateiweg liest sie von dort.

    Andersherum — das Austauschformat führt die Liste, der Kern liest sie —
    wäre der Kern von seinem Transport abhängig, und das ist die falsche Richtung. Der Test hält die
    Richtung fest, nicht die Werte: Wer eine vierte Lizenz zulässt, ändert eine
    Zeile in ``recipe.py`` und diese Liste zieht nach.
    """
    from app.core.knowledge.parts.recipe import RECIPE_LICENSES

    assert RECIPE_LICENSES, "eine leere Lizenzliste ließe jeden Wert durch"
    assert rules()["licenses"] == list(RECIPE_LICENSES)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        pytest.param({"license": "CC0-1.0"}, True, id="erlaubte Lizenz"),
        pytest.param({"license": "WTFPL"}, False, id="fremde Lizenz"),
        pytest.param({"license": 7}, False, id="Lizenz ist keine Zeichenkette"),
        pytest.param({"author": "R. Schneider, rs-digital.de"}, True, id="Autor mit Adresse"),
        pytest.param({"author": "R. <b>Schneider</b>"}, True, id="Autor mit spitzen Klammern"),
        pytest.param({"author": "R" * (MAX_TITLE_CHARS + 1)}, False, id="Autor zu lang"),
    ],
)
def test_the_check_asks_whether_a_value_is_allowed_never_whether_it_is_there(
    changes: dict[str, Any], expected: bool
) -> None:
    """Beide Felder sind freiwillig — und ein Autor darf sagen, wo man ihn findet.

    Zwei Zusagen in einem Test, weil sie dieselbe Naht betreffen. **Abwesend
    ist kein Fehler:** Ein Rezept ohne Lizenz schreibt den Schlüssel gar nicht
    erst; eine Prüfung auf Anwesenheit wiese damit jedes zweite Rezept ab.
    Autor und Beschreibung bleiben gewöhnlicher Text und werden nicht als
    Auszeichnung interpretiert.
    """
    findings = inspect(recipe(**changes))

    assert (findings == []) is expected, f"unerwartet: {findings}"


def test_a_recipe_without_licence_or_author_passes() -> None:
    """Die Grundmenge des Tests darüber — ohne sie prüft er die falsche Sache.

    Wäre schon das Rezept **ohne** die zwei Felder beanstandet, wäre jedes
    „False" oben aus dem falschen Grund richtig, und das „True" bei der
    erlaubten Lizenz wäre der einzige Fall, der überhaupt etwas sagt.
    """
    assert "license" not in json.loads(recipe())
    assert inspect(recipe()) == []


def test_export_marks_missing_distribution_rights_explicitly() -> None:
    """Eine Austauschdatei macht aus fehlenden Angaben keine Erlaubnis."""

    exported = json.loads(for_export(a_recipe()))

    assert exported["author"] == ""
    assert exported["license"] == ""
