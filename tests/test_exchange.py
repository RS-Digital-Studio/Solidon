"""Die Formatprüfung der Tauschbörse — Missbrauchs- und Grenzfälle.

Seit Kunden ohne Sichtung hochladen (Robert, 30.08.2026), ist diese Prüfung
**die erste und einzige vor der Veröffentlichung**. Was hier durchkommt, steht
in der Galerie.

Jeder Fall hier ist eine Datei, die jemand hochladen könnte — nicht ein
Aufruf, den ein Test sich zurechtlegt. Der Unterschied ist gemessen teuer: Ein
selbst gebautes Projekt enthält, was der Test hineinlegt, ein ausgeliefertes
enthält, was die Anwendung erzeugt, und acht von neun Beispielen fielen einmal
an genau dieser Naht.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts.exchange import (
    MAX_DOC_CHARS,
    MAX_TITLE_CHARS,
    MAX_UPLOAD_BYTES,
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
        "group": "Befestigung",
        "document": {
            "format_version": 19,
            "ops": [{"id": 1, "op": "create_box", "params": {"length": 20.0, "width": 10.0}}],
        },
        "payloads": {},
        "exposed": [],
        "features": {},
        "doc": "Hält ein Kabel an der Tischkante.",
        "format_version": 1,
    }
    base.update(changes)
    return json.dumps(base, ensure_ascii=False).encode("utf-8")


def test_the_list_of_allowed_operations_comes_from_the_registry() -> None:
    """Von Hand geführt wäre sie beim nächsten Zuwachs falsch (Konzept §3.1).

    Die Börse wiese dann Rezepte ab, die die Anwendung selbst erzeugt hat — und
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
    assert "kein gültiges JSON" in " ".join(inspect(b"{ das ist kaputt"))
    assert "kein gültiges JSON" in " ".join(inspect(b"\xff\xfe\x00"))
    assert "ist ein Objekt" in " ".join(inspect(b"[1, 2, 3]"))
    assert "Formatversion" in " ".join(inspect(recipe(format_version=99)))


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
    assert any("Unbekannte Schlüssel" in entry for entry in findings), findings
    assert any("__class__" in entry for entry in findings), findings


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
    assert any("unbekannte Operation" in entry for entry in findings), findings


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
    assert any("nicht erlaubt" in entry for entry in inspect(recipe(document=nested))), (
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
    Text **mit** Link schickt, soll nicht zweimal hochladen müssen, um beide
    Gründe zu erfahren.
    """
    long_title = inspect(recipe(title="x" * (MAX_TITLE_CHARS + 1)))
    assert any("Zeichen lang" in entry for entry in long_title), long_title

    linked = inspect(recipe(doc="Mehr davon auf https://beispiel.test"))
    assert any("Link" in entry for entry in linked), linked

    marked_up = inspect(recipe(doc="<script>irgendwas</script>"))
    assert any("Link oder Auszeichnung" in entry for entry in marked_up), marked_up

    both = inspect(recipe(doc="www.beispiel.test " + "y" * MAX_DOC_CHARS))
    assert len(both) >= 2, f"nur ein Grund genannt, dabei sind es zwei: {both}"


def test_a_file_over_the_size_limit_is_refused_before_anything_else() -> None:
    """Fünfundzwanzig Megabyte, und die Grenze steht vor der Inhaltsprüfung
    (§3.6).

    Payloads reisen base64-kodiert und wachsen dabei um ein Drittel. Die Grenze
    zuerst zu prüfen ist keine Optimierung, sondern die Zusage: Eine Datei, die
    zu groß ist, wird nicht erst geparst.
    """
    huge = b'{"name": "x", "title": "' + b"z" * (MAX_UPLOAD_BYTES + 10) + b'"}'
    findings = inspect(huge)
    assert any("Byte groß" in entry for entry in findings), findings


def test_a_payload_that_is_not_base64_is_refused() -> None:
    """Anhänge werden gemessen, nicht ausgeführt — aber sie müssen lesbar sein.

    Ein Anhang, der kein base64 ist, kommt nie bei einem Empfänger an; ihn
    anzunehmen hieße, eine Kachel zu veröffentlichen, die beim ersten Öffnen
    scheitert.
    """
    good = base64.b64encode(b"solid netz\n").decode("ascii")
    assert inspect(recipe(payloads={"src_1": good})) == []

    findings = inspect(recipe(payloads={"src_1": "das ist kein base64!!"}))
    assert any("kein base64" in entry for entry in findings), findings


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


def test_the_file_beside_the_php_matches_what_the_application_knows() -> None:
    """Die erzeugte Datei ist aktuell — sonst prüfen zwei Seiten Verschiedenes.

    **Eine erzeugte Datei, die niemand neu erzeugt, ist beim nächsten Zuwachs
    falsch.** Genau das ist am 27.08.2026 einem Paketbau passiert: Neun Tests
    fragten eingecheckte Beispiele ab und blieben grün, während das Werkzeug,
    das sie erzeugt, seit fünf Stunden etwas anderes geschrieben hätte.

    Hier wiegt es schwerer als dort. Die PHP-Seite liest diese Datei, und wenn
    sie eine Operation nicht kennt, weist sie ein Rezept ab, das die Anwendung
    selbst geschrieben hat — der Kunde sieht dann nur, dass sein Baustein
    verschwindet, ohne einen Grund, den er beheben könnte.
    """
    import subprocess
    import sys
    from pathlib import Path

    from tools.make_exchange_rules import TARGET, written

    assert TARGET.exists(), (
        f"{TARGET.name} fehlt — einmal `python tools/make_exchange_rules.py` genügt"
    )
    assert TARGET.read_text(encoding="utf-8") == written(), (
        f"{TARGET.name} ist nicht mehr das, was die Anwendung sagt. "
        "Einmal `python tools/make_exchange_rules.py`, dann stimmt es wieder."
    )

    # Und zweimal erzeugen ergibt zweimal dasselbe: Ohne diese Zusage meldete
    # der Wächter oben irgendwann einen Unterschied, den niemand gemacht hat.
    assert written() == written()

    # Das Werkzeug läuft auch als eigener Prozess — die Suite hat das Register
    # schon geladen, ein frischer Aufruf nicht, und genau daran ist die
    # Erlaubnisliste schon einmal leer geblieben.
    root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "make_exchange_rules.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert TARGET.read_text(encoding="utf-8") == written(), (
        "der eigene Prozess schrieb etwas anderes als die Suite — "
        "vermutlich fehlt ihm ein load_operations()"
    )


def test_the_rules_file_carries_what_both_sides_need() -> None:
    """Was in der Datei fehlt, kann die PHP-Seite nicht prüfen.

    Der Wächter darüber hält beide Seiten **gleich**; dieser hier hält sie
    **vollständig**. Eine Regel, die nur im Python steht, ist eine Prüfung, die
    der Server nicht macht — und der Server ist laut Konzept die erste und
    einzige Instanz vor der Veröffentlichung.
    """
    import json as _json
    from pathlib import Path

    from tools.make_exchange_rules import TARGET

    known = _json.loads(Path(TARGET).read_text(encoding="utf-8"))
    for key in (
        "operations",
        "recipe_keys",
        "recipe_format_versions",
        "max_upload_bytes",
        "max_title_chars",
        "max_doc_chars",
    ):
        assert key in known, f"„{key}“ fehlt in der Datei, die der Server liest"
        assert known[key], f"„{key}“ steht leer da — eine leere Regel prüft nichts"

    # Und die Prüfung der Anwendung läuft gegen genau diese Datei: Was hier
    # steht, ist keine zweite Wahrheit, sondern dieselbe.
    assert inspect(recipe(), known=known) == []
    assert inspect(recipe(format_version=99), known=known)
