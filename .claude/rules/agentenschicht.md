---
paths:
  - "app/core/agent/**/*.py"
  - "app/core/backends/**/*.py"
---

# Regeln für die Agentenschicht und die Backends

Der LLM-Agent steuert denselben Operations-API fern, den auch die Menüs
benutzen. Er bekommt keine Sonderwege.

## Eine Transaktion

**Jeder Agentenvorschlag ist genau eine Transaktion** (Regel 16). Ein Undo
nimmt ihn vollständig zurück. Ablauf: Vorschlag → Berechnung in
Entwurfsqualität → Differenzansicht → Übernahme oder Verwerfen. Iterationslimit
und Kostendeckel sind hart.

Nach jeder Op läuft die Prüfung — wasserdicht, Volumen plausibel, keine
unerwarteten Komponenten, keine verwaisten Referenzen, keine verletzten
Passungen — und der Befund geht zurück in den Kontext.

## Die vier Vorrangregeln

**Bausteine vor Primitiven, Op-Liste vor OpenSCAD, Parameter vor Zahlen,
Fragen vor Raten.** Alle vier im Systemprompt verankert und in der Suite
gemessen. Wer eine davon lockert, misst vorher und nachher.

`ask_user` ist Pflicht, keine Höflichkeit: Die Suite enthält absichtlich
mehrdeutige Anfragen und zählt, ob gefragt statt geraten wurde.

## Kontext

Der Agent sieht Steckbrief (mit Projektparametern und **aktueller Auswahl**),
Prüfbericht samt verwendeter Rückfallstufen, Verlauf in Kurzform, die gültigen
Chatbeiträge und die Regelsammlung in ihrer Version. Nicht den rohen Verlauf.

**Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
sie zurückgenommen, gilt der Beitrag als verworfen und geht höchstens als
„wurde verworfen" mit. Ohne diese Kopplung argumentiert der Agent nach jedem
Undo mit einem Zustand, den es nicht mehr gibt.

Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
Version des Systemprompts, Version der Regelsammlung, Temperatur.

## Sicherheit (§32)

Projektdateien wandern zwischen Leuten — eine fremde Datei darf nichts
ausführen.

- **Kein `eval`.** Parameterausdrücke über den eigenen Auswerter mit
  beschränkter Grammatik, auch nicht „abgesichert".
- **OpenSCAD-Quelltext wird vor jedem Lauf geprüft**: `import`, `include`,
  `use`, `surface` nur mit relativen Pfaden unterhalb des Arbeitsordners. Gilt
  für Quelltext aus Projektdateien **und aus dem LLM**.
- Fester Arbeitsordner je Lauf, Zeit- und Speicherlimit, kein Netzzugriff.
- Beim Import Dreieckszahl und Dateigröße deckeln — klare Meldung statt
  Speicherüberlauf.

## Backends melden sich ab, sie nörgeln nicht

Ohne Schlüssel sind die Agentenfunktionen ausgegraut und die Anwendung bleibt
voll nutzbar. Ein Hinweis an der Chatleiste, mehr nicht — kein Werbebanner,
kein wiederholtes Nachfragen. Dasselbe gilt für OpenSCAD, den Slicer und die
Mesh-Erzeugung: fehlt das Programm, sagt die betroffene Funktion das in einem
Satz mit Hinweis auf die Einstellung.

Die Mesh-Schnittstelle kennt nur `text_to_mesh` und `image_to_mesh`: kein
Nutzercode, keine Dateipfade, kein Zustand.

## Suite

`tools/run_agent_suite.py` ist **kein Testlauf** — er kostet Geld und braucht
einen Schlüssel oder ein lokales Modell. Sein Ergebnis ist eine Quote, kein
Bestanden. Er läuft auf Ansage, nicht nebenbei.
