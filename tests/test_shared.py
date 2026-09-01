"""Die lokale Bausteindatei — Format-, Import- und Exportgrenzen."""

from __future__ import annotations

import base64
import io
import json
import socket
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.shared import (
    MAX_DOC_CHARS,
    MAX_FILE_BYTES,
    MAX_TITLE_CHARS,
    export_bytes,
    import_file,
    inspect,
    read_recipe_file,
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
            "ops": [{"id": 1, "op": "create_box", "params": {"length": 20.0, "width": 10.0}}],
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
    """Von Hand geführt wäre sie beim nächsten Zuwachs falsch (Konzept §3.1).

    Die Dateiprüfung wiese dann Rezepte ab, die die Anwendung selbst erzeugt hat — und
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
        "ops": [{"id": 1, "op": "create_box", "params": {"length": {"$ref": "irgendwas"}}}],
    }
    assert "check_value_not_allowed" in codes(inspect(recipe(document=nested))), (
        "ein verschachtelter Parameterwert kam durch"
    )

    plain = {
        "format_version": 19,
        "ops": [{"id": 1, "op": "create_box", "params": {"sizes": [1.0, 2.0, 3.0]}}],
    }
    assert inspect(recipe(document=plain)) == [], "eine Liste von Zahlen ist ein gültiger Parameter"


def test_an_overlong_text_and_a_link_are_both_refused() -> None:
    """Werbung braucht Platz und einen Link (Konzept §3.2).

    Beides ist begrenzt, und beides wird einzeln gemeldet: Wer einen zu langen
    Text **mit** Link weitergibt, soll nicht zweimal nachbessern müssen, um beide
    Gründe zu erfahren.
    """
    long_title = inspect(recipe(title="x" * (MAX_TITLE_CHARS + 1)))
    assert "check_field_too_long" in codes(long_title), long_title
    # Die Zahlen gehören zur Zusage: Der Vergleich beider Prüfseiten hängt an
    # ihnen, seit die Sätze aus einer gemeinsamen Quelle kommen.
    assert long_title[0].values == {
        "field": "title",
        "length": MAX_TITLE_CHARS + 1,
        "limit": MAX_TITLE_CHARS,
    }, long_title[0].values

    linked = inspect(recipe(doc="Mehr davon auf https://beispiel.test"))
    assert "check_field_has_link" in codes(linked), linked

    marked_up = inspect(recipe(doc="<script>irgendwas</script>"))
    assert "check_field_has_link" in codes(marked_up), marked_up

    both = inspect(recipe(doc="www.beispiel.test " + "y" * MAX_DOC_CHARS))
    assert len(both) >= 2, f"nur ein Grund genannt, dabei sind es zwei: {both}"


def test_a_file_over_the_size_limit_is_refused_before_anything_else() -> None:
    """Fünfundzwanzig Megabyte, und die Grenze steht vor der Inhaltsprüfung
    (§3.6).

    Payloads reisen base64-kodiert und wachsen dabei um ein Drittel. Die Grenze
    zuerst zu prüfen ist keine Optimierung, sondern die Zusage: Eine Datei, die
    zu groß ist, wird nicht erst geparst.
    """
    huge = b'{"name": "x", "title": "' + b"z" * (MAX_FILE_BYTES + 10) + b'"}'
    findings = inspect(huge)
    assert codes(findings) == {"file_too_large"}, findings


def test_reading_stops_one_byte_after_the_file_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine fremde Datei bekommt keine unbegrenzte Speicherzusage."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import shared

    monkeypatch.setattr(shared, "MAX_FILE_BYTES", 64)
    requested: list[int] = []

    class RecordingStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            requested.append(size)
            return super().read(size)

    stream = RecordingStream(b"x" * 1000)

    def opened(_path: Path, mode: str) -> io.BytesIO:
        assert mode == "rb"
        return stream

    monkeypatch.setattr(Path, "open", opened)

    with pytest.raises(ValidationError) as refused:
        read_recipe_file("beliebig.json")

    assert requested == [65]
    assert refused.value.constraint == "part_file_invalid"


def test_a_payload_that_is_not_base64_is_refused() -> None:
    """Anhänge werden gemessen, nicht ausgeführt — aber sie müssen lesbar sein.

    Ein Anhang, der kein base64 ist, kommt nie bei einem Empfänger an; ihn
    anzunehmen hieße, eine Datei weiterzugeben, die beim ersten Öffnen
    scheitert.
    """
    good = base64.b64encode(b"solid netz\n").decode("ascii")
    assert inspect(recipe(payloads={"src_1": good})) == []

    findings = inspect(recipe(payloads={"src_1": "das ist kein base64!!"}))
    assert "check_payload_not_base64" in codes(findings), findings


def test_every_finding_is_reported_at_once() -> None:
    """Eine Ablehnung, die nach jedem Berichtigen eine neue nennt, ist eine
    Kette ohne Ende.

    Der Kunde bekommt seine Datei einmal zurück, mit allem, was daran fehlt.
    """
    findings = inspect(
        recipe(
            title="x" * (MAX_TITLE_CHARS + 1),
            doc="siehe https://beispiel.test",
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
    zwei Enden derselben Kette: Was die Dateiprüfung sieht, sind Bytes; was der
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


def test_the_share_file_comes_out_of_one_door_and_that_door_checks() -> None:
    """Der gute Fall — und ohne ihn wäre der Test darunter wertlos.

    Ein Wächter „nichts Verbotenes kommt heraus" ist über einer Tür, die
    **immer** zuschlägt, genauso grün wie über einer, die richtig prüft. Also
    steht hier zuerst die Zusicherung, dass überhaupt etwas herauskommt: echte
    Bytes, gültiges JSON, und von der Prüfung selbst nicht beanstandet.
    """
    payload = export_bytes(a_recipe())

    assert payload, "aus einem gültigen Rezept muss eine Datei entstehen"
    assert json.loads(payload)["name"] == "halter"
    assert inspect(payload) == [], "die Tür gibt heraus, was ihre eigene Prüfung ablehnt"


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("Baustein mit Leerzeichen.json", id="Windows-Leerzeichen"),
        pytest.param("größe_µ.json", id="Linux-Unicode"),
        pytest.param("Größe.json", id="macOS-Normalform"),
    ],
)
def test_local_export_import_round_trip_is_portable_and_never_uses_the_network(
    filename: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bytes hinaus, lokale Datei hinein — ohne Konto, URL oder Netzaufruf."""
    from app.core.knowledge.parts.recipe import IMPORTED_SOURCE
    from app.core.knowledge.parts.registry import PartRegistry
    from app.core.registry import Registry

    def network_forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Der lokale Bausteindatei-Weg hat das Netzwerk aufgerufen.")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", network_forbidden)

    target = tmp_path / filename
    target.write_bytes(export_bytes(a_recipe()))
    parts, registry = PartRegistry(), Registry()

    assert import_file(target, parts, registry) == []
    assert parts.get("halter").source == IMPORTED_SOURCE


@pytest.mark.parametrize(
    ("payload", "named"),
    [
        pytest.param(
            lambda: json.dumps({**json.loads(recipe()), "__class__": "os.system"}).encode(),
            "__class__",
            id="unbekannter Schlüssel",
        ),
        pytest.param(
            lambda: recipe(
                document={
                    "format_version": 19,
                    "ops": [{"id": 1, "op": "run_shell_command", "params": {}}],
                }
            ),
            "run_shell_command",
            id="unbekannte Operation",
        ),
    ],
)
def test_import_rejects_unknown_content_before_registration(
    payload: Any,
    named: str,
    tmp_path: Path,
) -> None:
    """Eine abgelehnte Datei erzeugt weder Katalogeintrag noch Erfolgslage."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts.registry import PartRegistry
    from app.core.registry import Registry

    target = tmp_path / "fremd.json"
    target.write_bytes(payload())
    parts, registry = PartRegistry(), Registry()

    with pytest.raises(ValidationError) as refused:
        import_file(target, parts, registry)

    assert named in refused.value.values["findings"]
    assert not parts.has("halter")


def test_import_keeps_the_local_recipe_and_marks_the_arriving_copy(tmp_path: Path) -> None:
    """„Lokal gewinnt" bleibt wahr; die fremde Fassung steht erkennbar daneben."""
    from app.core.knowledge.parts.recipe import IMPORTED_SOURCE, fingerprint, register
    from app.core.knowledge.parts.registry import PartRegistry
    from app.core.registry import Registry

    parts, registry = PartRegistry(), Registry()
    local = a_recipe(doc="lokaler Stand")
    register(local, parts, registry)
    local_mark = fingerprint(local)

    target = tmp_path / "anderer Stand.json"
    target.write_bytes(export_bytes(a_recipe(doc="importierter Stand")))
    assert import_file(target, parts, registry) == []

    assert parts.get("halter").version == local_mark
    assert parts.get("halter_imported").source == IMPORTED_SOURCE


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"doc": "Mehr dazu auf http://beispiel.invalid/halter"}, id="Link im Text"),
        pytest.param({"title": "Kabelhalter <b>neu</b>"}, id="Auszeichnung im Titel"),
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
        export_bytes(faulty)

    assert refused.value.values["findings"], "die Absage nennt den Grund nicht"
    assert refused.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“ (Regel 17)"


# --- Lizenz und Autor: die zwei Felder, die eine Weitergabe erlauben ----------


def test_the_licences_come_from_the_recipe_core_not_from_a_second_list() -> None:
    """Die Wertemenge gehört dem Kern; die Dateiprüfung leitet sie daraus ab.

    Andersherum — der Dateiprüfer führt die Liste, der Kern liest sie — wäre der
    Kern vom Austauschformat abhängig. Der Test hält die
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
        pytest.param({"author": "R. <b>Schneider</b>"}, False, id="Autor mit Auszeichnung"),
        pytest.param({"author": "R" * (MAX_TITLE_CHARS + 1)}, False, id="Autor zu lang"),
    ],
)
def test_the_check_asks_whether_a_value_is_allowed_never_whether_it_is_there(
    changes: dict[str, Any], expected: bool
) -> None:
    """Beide Felder sind freiwillig — und ein Autor darf sagen, wo man ihn findet.

    Zwei Zusagen in einem Test, weil sie dieselbe Naht betreffen. **Abwesend
    ist kein Fehler:** Ein Rezept ohne Lizenz schreibt den Schlüssel gar nicht
    erst; eine Prüfung auf Anwesenheit wiese damit jedes zweite Rezept ab. Und
    **eine Adresse ist keine Werbung:** ``Recipe.author`` ist ausdrücklich „ein
    Name, ein Kürzel, eine Adresse", also gilt dort das Link-Verbot aus
    ``FORBIDDEN_TEXT`` nicht — das ``<`` verbietet ein eigenes Muster weiter,
    denn fremde Dateien können das Feld in der Oberfläche anzeigen.

    Ein gemeinsames Muster für Titel und Autor hätte eines von beiden falsch
    entschieden, und zwar still.
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
