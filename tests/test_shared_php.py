"""Beide Prüfseiten der Börse fällen dasselbe Urteil über dieselbe Datei.

**Warum dieser Test der wichtigste der Börse ist.** Robert hat entschieden,
dass Kunden ohne Sichtung hochladen; damit ist die Formatprüfung die einzige
Instanz vor der Veröffentlichung, und sie steht an zwei Orten: in der App
(``app.core.knowledge.parts.shared``) und auf dem Server
(``website/api/shared_common.php``). Sagen die beiden Verschiedenes, sucht der
Kunde den Fehler bei sich — die App nimmt seine Datei an, der Server wirft sie
weg, und niemand kann ihm erklären, warum.

72s Beleg dazu, aus einem gemessenen Fall am selben Abend: Skizzenlöser und
Serializer führten dieselben Bedingungsarten in zwei Listen. Beim Einbau von
``radius`` wurde nur eine ergänzt, und die eine ließ durch, was die andere
verwarf.

**Eine gemeinsame Regeldatei allein reicht dagegen nicht.** Sie sorgt dafür,
dass beide dieselben *Namen* kennen; ob sie daraus dasselbe *Urteil* bauen,
sagt sie nicht. Geprüft wird deshalb das Ergebnis, an derselben Nutzlast,
Befund für Befund.

Ohne PHP überspringt sich der Test — dann prüft die CI ihn nicht, und das ist
hingenommen: Die Alternative wäre ein Nachbau der PHP-Prüfung in Python, und
der prüfte den Nachbau.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts import shared

TREIBER = Path(__file__).parent / "data" / "check_shared.php"

#: Ein Rezept, das durchgehen muss. Ohne diesen Fall sagte der Test nichts:
#: Eine Prüfung, die alles ablehnt, bestünde jede Ablehnungsprobe.
GUT: dict[str, Any] = {
    "format_version": 1,
    "name": "werkbank_halter",
    "title": "Halter für die Werkbank",
    "doc": "Zwei Einhänger, Rückwand 120 mm.",
    "author": "RS Digital",
    "license": "CC-BY-4.0",
    "document": {
        "ops": [
            {"op": "create_box", "params": {"width": 120.0, "depth": 60.0, "height": 45.0}},
            {"op": "insert_pegboard_hook", "params": {"count": 2, "steps": 2, "latch": True}},
        ]
    },
}


def _mit(**änderungen: Any) -> bytes:
    """Das gute Rezept mit geänderten Feldern — als Bytes, wie es ankäme."""
    daten = {**GUT, **änderungen}
    for schlüssel, wert in list(daten.items()):
        if wert is None:
            del daten[schlüssel]
    return json.dumps(daten, ensure_ascii=False).encode("utf-8")


#: Die Fälle. Jeder trägt seinen Namen, damit ein Fehlschlag ihn nennt.
FAELLE: list[tuple[str, bytes]] = [
    ("das gute Rezept", _mit()),
    ("kein JSON", b"{ das ist keins"),
    ("eine Liste statt eines Objekts", b"[1, 2, 3]"),
    ("unbekannter Schlüssel", _mit(schmuggel="hier")),
    ("falsche Formatversion", _mit(format_version=99)),
    ("fehlende Formatversion", _mit(format_version=None)),
    ("Titel zu lang", _mit(title="ä" * 200)),
    ("Titel mit Link", _mit(title="Halter, siehe https://beispiel.de")),
    ("Titel mit Auszeichnung", _mit(doc="Ein <script>Halter</script>")),
    ("Titel ist kein Text", _mit(title=42)),
    ("Autor mit Auszeichnung", _mit(author="<b>RS</b>")),
    ("Autor zu lang", _mit(author="x" * 200)),
    ("Autor ist eine Adresse", _mit(author="RS Digital, post@beispiel.de")),
    ("unerlaubte Lizenz", _mit(license="WTFPL")),
    ("Lizenz ist kein Text", _mit(license=7)),
    ("keine Lizenz angegeben", _mit(license=None)),
    (
        "unbekannte Operation",
        _mit(document={"ops": [{"op": "rm_minus_rf", "params": {}}]}),
    ),
    (
        "Operation ohne Namen",
        _mit(document={"ops": [{"params": {}}]}),
    ),
    (
        "Schritt ist kein Objekt",
        _mit(document={"ops": ["create_box"]}),
    ),
    (
        "verschachtelter Parameterwert",
        _mit(document={"ops": [{"op": "create_box", "params": {"w": {"a": 1}}}]}),
    ),
    (
        "Liste von Listen als Parameter",
        _mit(document={"ops": [{"op": "create_box", "params": {"w": [[1, 2], [3]]}}]}),
    ),
    (
        "Liste von Zahlen als Parameter",
        _mit(document={"ops": [{"op": "create_box", "params": {"w": [1, 2, 3]}}]}),
    ),
    ("ops ist keine Liste", _mit(document={"ops": {"eins": "create_box"}})),
    ("document ist kein Objekt", _mit(document=[1, 2])),
    (
        "Anhang ist kein base64",
        _mit(payloads={"netz.stl": "das ist kein base64!!!"}),
    ),
    (
        "Anhang ist base64",
        _mit(payloads={"netz.stl": base64.b64encode(b"solid test").decode("ascii")}),
    ),
    ("Anhang ist keine Zeichenkette", _mit(payloads={"netz.stl": 5})),
    ("payloads ist kein Objekt", _mit(payloads=["netz.stl"])),
    (
        "zwei Fehler zugleich",
        _mit(title="ä" * 200, license="WTFPL"),
    ),
]


def _php_befunde(nutzlast: bytes, tmp_path: Path) -> list[str]:
    """Was die PHP-Seite über diese Nutzlast sagt."""
    php = shutil.which("php")
    assert php is not None  # skipif hat es geprüft, mypy weiß das nicht

    datei = tmp_path / "rezept.json"
    datei.write_bytes(nutzlast)

    # Ohne ``php.ini`` sucht PHP seine Erweiterungen unter dem einkompilierten
    # Standardpfad; bei einer entpackten Installation liegen sie neben der
    # ausführbaren Datei. Dasselbe Vorgehen wie in ``test_support``.
    optionen = ["-d", "extension=mbstring"]
    erweiterungen = Path(php).parent / "ext"
    if erweiterungen.is_dir():
        optionen[:0] = ["-d", f"extension_dir={erweiterungen}"]

    lauf = subprocess.run(
        [php, *optionen, str(TREIBER), str(datei)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert lauf.returncode == 0, f"PHP brach ab: {lauf.stderr}"
    return list(json.loads(lauf.stdout))


@pytest.mark.skipif(shutil.which("php") is None, reason="ohne PHP nicht prüfbar")
@pytest.mark.parametrize(("name", "nutzlast"), FAELLE, ids=[fall[0] for fall in FAELLE])
def test_both_checks_agree_on_the_same_file(name: str, nutzlast: bytes, tmp_path: Path) -> None:
    """Dieselbe Datei, zwei Prüfer, dasselbe Urteil — Befund für Befund.

    Verglichen werden die **Texte** und nicht nur die Anzahl: Zwei Prüfungen,
    die beide „ein Fehler" sagen und verschiedene meinen, sind nicht einig.
    """
    load_operations()
    kern = shared.inspect(nutzlast)
    server = _php_befunde(nutzlast, tmp_path)

    assert server == kern, (
        f"{name}: die beiden Prüfungen sind uneins.\n"
        f"  Kern  ({len(kern)}): {kern}\n"
        f"  PHP   ({len(server)}): {server}"
    )


@pytest.mark.skipif(shutil.which("php") is None, reason="ohne PHP nicht prüfbar")
def test_the_good_recipe_passes_on_both_sides(tmp_path: Path) -> None:
    """Und die Gegenprobe, ohne die alles andere nichts sagte.

    Eine Prüfung, die jede Datei ablehnt, besteht jeden Ablehnungsfall. Dieser
    Test ist der einzige, der behauptet, dass überhaupt etwas durchkommt —
    72 hat dieselbe Gegenprobe auf der Kernseite eingebaut, aus demselben
    Grund.
    """
    load_operations()
    nutzlast = _mit()

    assert shared.inspect(nutzlast) == [], "der Kern lehnt ein gültiges Rezept ab"
    assert _php_befunde(nutzlast, tmp_path) == [], "der Server lehnt ein gültiges Rezept ab"


@pytest.mark.skipif(shutil.which("php") is None, reason="ohne PHP nicht prüfbar")
def test_the_endpoint_is_valid_php() -> None:
    """Die Datei läuft nie hier — also sieht sie hier auch niemand an.

    Sie liegt im Repository, geht per FTPS auf den Server und läuft erst dort.
    Ein Tippfehler fiele frühestens dem ersten Kunden auf, der etwas hochlädt.
    """
    php = shutil.which("php")
    assert php is not None  # für mypy — skipif hat es geprüft
    for datei in (Path("website/api/shared_common.php"), TREIBER):
        lauf = subprocess.run([php, "-l", str(datei)], capture_output=True, text=True, timeout=30)
        assert lauf.returncode == 0, f"{datei}: {lauf.stdout}\n{lauf.stderr}"
