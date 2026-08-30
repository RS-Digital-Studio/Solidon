"""Schreibt die Grenzfälle der Börsenprüfung als Dateien samt Sollwerten.

**Eine gemeinsame Regelliste macht zwei Prüfer nicht gleich.** Beide lesen
``shared-rules.json``, und trotzdem kann PHP ein `` www. `` finden, wo Python
keins sieht, oder eine Länge in Bytes zählen, wo die andere Seite Zeichen
zählt. Die Liste sagt, *was* gilt; sie sagt nicht, dass beide sie gleich
anwenden.

Deshalb dieses Werkzeug: Es legt je Fall eine Datei ab, wie sie jemand
hochladen würde, dazu ein ``erwartet.json`` mit dem Urteil der Anwendung. Die
Server-Seite fährt dieselben Dateien durch ihre Prüfung und vergleicht — ein
Fall, bei dem die zwei Urteile auseinandergehen, ist genau der Fall, den
niemand von Hand gefunden hätte.

Aufruf::

    .venv\\Scripts\\python.exe tools/make_shared_cases.py

Der Ordner liegt unter ``.claude/.state/`` und wird **eingecheckt** — dort
steht die Begründung schon in ``.gitignore``: An diesem Projekt arbeiten drei
Maschinen, und was nur auf einer liegt, ist auf den anderen nicht fortsetzbar.
Für diese Fälle ist das kein Nebeneffekt, sondern der Zweck: Wer die
Server-Seite prüft, sitzt nicht zwangsläufig an dem Rechner, der sie erzeugt
hat.

Ein eingechecktes Erzeugnis altert aber, sobald sein Erzeuger nicht mehr läuft
— genau die Falle, die am 27.08.2026 einen Paketbau gekostet hat. Deshalb hält
``tests/test_shared.py`` beides zusammen: Das abgelegte Urteil muss dem
entsprechen, was :func:`app.core.knowledge.parts.shared.inspect` **heute**
sagt. Ein Fall, der sein eigenes Urteil erfindet, wäre ein Vergleichsmaßstab,
der nichts vergleicht.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge.parts.shared import (  # noqa: E402
    MAX_DOC_CHARS,
    MAX_TITLE_CHARS,
    MAX_UPLOAD_BYTES,
    inspect,
)

#: Wohin die Fälle geschrieben werden.
TARGET = ROOT / ".claude" / ".state" / "boersen-grenzfaelle"


def _base() -> dict[str, Any]:
    """Ein Rezept, wie die Anwendung es schreibt."""
    from app.core.scene.migrations import FORMAT_VERSION as DOCUMENT_VERSION

    return {
        "name": "halter",
        "title": "Kabelhalter",
        # **Der Schlüssel, nicht der Anzeigename.** „Befestigung" stand hier
        # von Anfang an und war nie gültig: ``GROUPS`` führt `mounting` als
        # Schlüssel und „Befestigung" als seine deutsche Beschriftung. Solange
        # ``inspect`` die Gruppe nicht prüfte, fiel es nicht auf — der ganze
        # Korpus bestand aus Dateien, die kein Empfänger hätte laden können,
        # und der Test hieß trotzdem „ein Rezept, das die Anwendung geschrieben
        # hat".
        "group": "mounting",
        "document": {
            "format_version": DOCUMENT_VERSION,
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


def _with(**changes: Any) -> bytes:
    data = _base()
    data.update(changes)
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def cases() -> dict[str, bytes]:
    """Die Fälle, je Name eine Datei.

    Die Namen sind Sätze und keine Kennungen: Wer den Vergleich fährt, liest
    eine Abweichung als „``titel-zu-lang`` geht auseinander" und muss nicht
    erst nachschlagen, was Fall sieben war.

    **Die guten Fälle stehen mit drin, und das ist keine Vollständigkeitsgeste.**
    Ein Vergleich, der nur Abweisungen enthält, ist von einer Server-Seite, die
    stumpf alles abweist, nicht zu unterscheiden.
    """
    grenzwertig = "x" * MAX_TITLE_CHARS
    return {
        "gut-schlicht": _with(),
        "gut-titel-genau-an-der-grenze": _with(title=grenzwertig),
        "gut-liste-von-zahlen": _with(
            document={
                "format_version": _base()["document"]["format_version"],
                "ops": [{"id": 1, "op": "create_box", "params": {"sizes": [1.0, 2.0, 3.0]}}],
            }
        ),
        # Der Gedankenstrich steht als Escape, weil ruff ihn im Quelltext für
        # einen verrutschten Bindestrich hält. In der Datei landet er als das,
        # was er ist — und darum geht es dem Fall: PHP soll ihn genauso zählen.
        "gut-umlaute-und-anfuehrung": _with(doc="Für „schmale“ Kanten \u2013 3 mm stark."),
        "gut-lizenz-und-autor": _with(license="CC-BY-4.0", author="R. Schneider, rs-digital.de"),
        "schlecht-kein-json": b"{ das ist kaputt",
        "schlecht-liste-statt-objekt": b"[1, 2, 3]",
        "schlecht-leere-datei": b"",
        "schlecht-formatversion-zu-neu": _with(format_version=99),
        "schlecht-unbekannter-schluessel": _with(__class__="os.system"),
        "schlecht-unbekannte-operation": _with(
            document={
                "format_version": _base()["document"]["format_version"],
                "ops": [{"id": 1, "op": "run_shell_command", "params": {"cmd": "rm -rf /"}}],
            }
        ),
        "schlecht-verschachtelter-parameter": _with(
            document={
                "format_version": _base()["document"]["format_version"],
                "ops": [{"id": 1, "op": "create_box", "params": {"length": {"$ref": "x"}}}],
            }
        ),
        "schlecht-titel-ein-zeichen-zu-lang": _with(title=grenzwertig + "x"),
        "schlecht-text-zu-lang": _with(doc="y" * (MAX_DOC_CHARS + 1)),
        "schlecht-link-im-text": _with(doc="Mehr davon auf https://beispiel.test"),
        "schlecht-www-ohne-schema": _with(doc="Siehe www.beispiel.test"),
        "schlecht-auszeichnung-im-text": _with(doc="<script>irgendwas</script>"),
        "schlecht-zwei-gruende-auf-einmal": _with(doc="www.beispiel.test " + "y" * MAX_DOC_CHARS),
        "schlecht-fremde-lizenz": _with(license="WTFPL"),
        "schlecht-auszeichnung-im-autor": _with(author="R. <b>Schneider</b>"),
        "schlecht-anhang-kein-base64": _with(payloads={"netz": "kein base64!!"}),
        # Die drei Aufnahmebedingungen (3a, 31.08.2026, erster
        # Ende-zu-Ende-Lauf): Dateien, die jede Börsenprüfung bestanden und
        # beim ersten Empfänger scheiterten. Sie können nicht aus unserer
        # Anwendung stammen — dort erzwingt ``capture`` alle drei — und genau
        # deshalb gehören sie hierher: Eine Börsendatei kommt nicht von uns.
        "schlecht-name-kein-snake-case": _with(name="Probeklotz"),
        "schlecht-unbekannte-gruppe": _with(group="eigene"),
        "schlecht-ohne-merkmal": _with(features={}),
        # Der Größenfall steht bewusst **nicht** hier: Er wäre eine Datei von
        # 26 MB neben zwanzig, die zusammen keine 20 KB wiegen, und der Ordner
        # wird eingecheckt. Wie er zu bauen ist, sagt ``hinweise.md`` — die
        # Grenze selbst lesen ohnehin beide Seiten aus ``shared-rules.json``,
        # und ``tests/test_shared.py`` prüft sie an der Anwendung.
    }


#: Der Fall, der zu groß ist, um abgelegt zu werden — als Bauanleitung.
OVERSIZE = f"""# Der Größenfall

Er liegt nicht als Datei bei: {MAX_UPLOAD_BYTES + 10} Bytes neben zwanzig
Dateien, die zusammen keine 20 KB wiegen, und dieser Ordner wird eingecheckt.

Zum Nachbauen, auf beiden Seiten dieselbe Datei:

    python -c "open('zu-gross.bin','wb').write(b'{{\\"name\\": \\"x\\", \\"title\\": \\"' \\
        + b'z' * {MAX_UPLOAD_BYTES + 10} + b'\\"}}')"

Erwartet wird **eine** Meldung über die Größe, und zwar **bevor** irgendetwas
geparst wird. Das ist die eigentliche Zusage: Eine Datei, die zu groß ist,
wird nicht erst gelesen — wer sie parst und danach die Größe prüft, hat den
Fall nicht abgedeckt, sondern nur seine Meldung.
"""


def verdicts() -> dict[str, list[dict[str, object]]]:
    """Das Urteil der Anwendung je Fall — die Sollwerte des Vergleichs.

    **Schlüssel und Werte, nicht der fertige Satz.** Solange hier Sätze
    standen, verglich die Server-Seite Formulierungen — und seit beide Seiten
    ihre Sätze aus derselben Textquelle holen, wäre das ein Vergleich zweier
    Lesevorgänge derselben Datei gewesen: immer gleich, ganz gleich was die
    Prüfungen darunter gefunden haben.

    Die Werte sind dabei der schärfere Teil. Python zählt Zeichen, PHPs
    ``strlen`` zählt Bytes; bei einem Text mit Umlauten gehen die Zahlen
    auseinander, und der Satz sieht in beiden Fällen gleich aus. Genau dieser
    Fall entscheidet über eine Datei, die auf ein Zeichen genau an der Grenze
    liegt.
    """
    load_operations()
    return {
        name: [{"code": one.code, "values": one.values} for one in inspect(payload)]
        for name, payload in cases().items()
    }


def main() -> int:
    load_operations()
    TARGET.mkdir(parents=True, exist_ok=True)
    # Ein umbenannter Fall ließe seine alte Datei sonst liegen, und die
    # Server-Seite führe einen Fall, den es nicht mehr gibt.
    for old in (*TARGET.glob("*.bin"), *TARGET.glob("*.json"), *TARGET.glob("*.md")):
        old.unlink()

    judged = verdicts()
    for name, payload in cases().items():
        (TARGET / f"{name}.bin").write_bytes(payload)
    (TARGET / "erwartet.json").write_text(
        json.dumps(judged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (TARGET / "hinweise.md").write_text(OVERSIZE, encoding="utf-8", newline="\n")

    refused = sum(1 for findings in judged.values() if findings)
    weight = sum(len(payload) for payload in cases().values())
    print(f"{TARGET}: {len(judged)} Fälle, davon {refused} abgewiesen, {weight} Bytes")
    print("Die Server-Seite fährt dieselben .bin-Dateien und vergleicht gegen erwartet.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
