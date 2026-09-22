"""Legt die getrennten deutschen Committexte für den geprüften Stand bereit."""

from pathlib import Path

state = Path(__file__).parent
folder = Path((state / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
messages = {
    "runner": """Testfilter ändern die Release-Grenze ganzer Fensterdateien nicht

Die Sammlung klassifiziert jede Datei vor der Fallabwahl. Der eigentliche
Kernlauf erhält die gewünschten Namens- und Markerfilter und schließt Leistung
zusätzlich aus. Gemischte Fensterdateien bleiben vollständig beim Release.
Gegenproben prüfen Kommandozeile, Umgebung, Konfiguration und echte Kindprozesse.
""",
    "void": """Geschlossene Innenräume behalten ihre vollständigen Luftgrenzen

Exakte Körper und Netze erkennen getrennte Materialinseln und verschachtelte
Luftkammern. Die Auswahl bindet tatsächliche Quellflächen, lokal die angeklickte
Kammer. Phantombohrungen entfallen; Abbruch und unveränderte Quellen sind geprüft.
Die neue Cacheversion verwirft ältere unvollständige Auskünfte.
""",
    "bore": """Beide Bohrungswege finden eindeutig ihren ursprünglichen Schritt

Merkmalsherkunft und zeitliche Objektkette belegen die Zuordnung. Beide Kerne
übernehmen eindeutige Erzeuger über denselben Helfer. Originalwerte und Ausdrücke
bleiben erhalten; beide Bohrzwillinge teilen Flächensitz und Werkzeugbau.
Mehrdeutige Nachkommen und unbelegte spätere Formänderungen werden abgelehnt.
""",
    "measures": """Bohrungsmaße im Bild bearbeiten einen gemeinsam gebundenen Entwurf

Panel und Bild verwenden dieselben Fachfelder. Erst die Eingabe bindet Ziel und
Umfang; Übernehmen braucht die aktuelle dargestellte Vorschau. Frühes Enter wird
nicht vorgemerkt, Außenklick erhält den Entwurf, Escape verwirft ihn vollständig.
Historische Hilfen erscheinen nur über dem passenden Eingangskörper. Eine
Tiefenänderung prüft den Sitz neu; der Abschluss erhält die Merkmalsauswahl.
Kerntor und Statik sind geprüft. Ergänzte Fensterfälle bleiben gemäß der
dauerhaften Prüfvorgabe bis zur Release-Abnahme ausdrücklich unausgeführt.
""",
}
for scope, message in messages.items():
    (folder / f"{scope}-message.txt").write_text(
        message.strip() + "\n\nCo-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8"
    )
print(folder)
