---
name: roadmap
description: >
  Zeigt den Stand der Arbeitsliste und schlägt den nächsten sinnvollen Schritt
  vor — offene Punkte aus dem Register von ROADMAP.md, Funde aus den
  Durchsichten, fehlende Abnahmekriterien aus Bauplan §40; schreibt die
  Roadmap auf Auftrag fort. Benutzen bei „was als Nächstes?“.
argument-hint: "[optional: Phase oder Thema]"
allowed-tools: Read, Edit, Grep, Bash, Glob
---

# Roadmap: Angaben aus der aktuellen Anfrage

## Lesen

**Erst das Register.** Gleich unter der Legende steht *Was offen ist*: jeder
offene Punkt mit seinem Abschnitt und dem, worauf er wartet.
`tests/test_roadmap.py` prüft, ob Register und offene Kästchen je Abschnitt
zusammenpassen — das belegt ihre Vollständigkeit, **nicht ihren fachlichen
Stand**. Den prüfst du an Code, Tests und Git-Verlauf.

Das Register sagt nur, *dass* etwas offen ist. **Die Begründung steht am Punkt
selbst**, und dorthin gehst du, bevor du ihn vorschlägst. Jede Aufgabe hat eine
feste `RM-`-Kennung und eine Sprungmarke; Phasenstand, Umsetzung und fehlende
Abnahme sind getrennt — ein gebauter Weg ist ohne den geforderten
Feldnachweis noch nicht abgenommen.

**Die Geschichte steht in `ROADMAP-ARCHIV.md`**: frühere Durchsichten, Funde,
zurückgenommene Behauptungen und gemessene Irrwege, mit einem Verzeichnis am
Kopf. Sieh dort nach, bevor du etwas vorschlägst — ein „das haben wir gemessen,
und es trug nicht“ steht nur da. Das **Warum** einer Entscheidung steht in
`konzepte/`, mit dem Index in `konzepte/README.md`.

Zwei Fallen:

- **„Offen“ in historischer Prosa ist kein Arbeitsauftrag.** Der Punkt kann
  erledigt, überholt oder in einer gemeinsamen Aufgabe aufgegangen sein;
  maßgeblich ist die verlinkte aktuelle Aufgabe.
- **Ein offener Punkt ohne Kästchen zählt nicht.** Wer einen Fund festhält,
  gibt ihm ein `- [ ]` und eine Registerzeile.

Dazu `git log --oneline -15`: Was zuletzt passiert ist, sagt oft mehr über den
Stand als eine Liste, in der ein Haken fehlt.

## Vorschlagen

Drei Dinge, nicht zwanzig:

1. **Was offen ist** — die konkreten Punkte mit ihrer Stelle in der Roadmap.
2. **Was du als Nächstes empfiehlst**, mit Grund: Was blockiert anderes? Was
   ist ein bekannter Fehler aus einer Durchsicht? Was fehlt einer Phase zur
   Abnahme nach §40?
3. **Was es kostet** und was es an anderer Stelle nach sich zieht.

Die Rangfolge steht im Kopf von `ROADMAP.md` („Priorität“): Ein bekannter
Fehler schlägt ein neues Feature. Bei Gleichstand schlägt ein Punkt, der eine
Phase abschließt, einen, der eine neue anfängt.

## Fortschreiben

Eine Status- oder Empfehlungsfrage ändert keine Datei. Fortgeschrieben wird auf
Auftrag oder als Dokumentation einer tatsächlich erledigten Arbeitseinheit.

- **Beheben statt notieren.** Was die Sitzung selbst beheben kann, wird
  behoben, nicht eingetragen; ins Register kommt, was eine Entscheidung von
  Robert oder etwas außerhalb des Repositorys braucht — ein Gerät, ein
  Zertifikat, ein Konto. Eigener Rest ist kein neuer Punkt.
- Erledigtes und neue Funde **an zwei Stellen** nachziehen: am Punkt selbst
  und im Register. Vergisst du die zweite, wird `tests/test_roadmap.py` rot und
  nennt den Abschnitt.
- Neues steht in `ROADMAP.md`, nie im Archiv. Neue Kennungen fortlaufend nach
  der höchsten vergebenen in Roadmap **und** Archiv; entfernte werden nicht
  wiederverwendet.
- Eine abgeschlossene Aufgabe wandert mit ihrem konkreten Nachweis ins Archiv;
  ein zusammengeführter Punkt verweist dort auf seine offene Zielaufgabe und
  gilt nicht als behoben. Jeder neue Archivabschnitt bekommt eine Zeile im
  Verzeichnis am Archivkopf.
