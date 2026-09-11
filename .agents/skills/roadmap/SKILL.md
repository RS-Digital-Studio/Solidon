---
name: roadmap
description: >
  Zeigt den Stand der Arbeitsliste und schlägt den nächsten sinnvollen Schritt vor
  — offene Punkte der aktuellen Phase, Funde aus den Durchsichten, Abnahmekriterien
  aus Bauplan §40. Benutzen bei „was als Nächstes?".
argument-hint: "[optional: Phase oder Thema]"
allowed-tools: Read, Grep, Bash, Glob
---

# Roadmap: Angaben aus der aktuellen Anfrage

## Lesen

**Erst das Register.** Gleich unter der Legende steht der Abschnitt *Was offen
ist*: jeder offene Punkt mit seinem Abschnitt und dem, worauf er wartet.
`tests/test_roadmap.py` prüft, ob Register und offene Kästchen je Abschnitt
zusammenpassen. Das belegt ihre Vollständigkeit, **nicht ihren fachlichen
Stand**: Den prüfst du gegen aktuellen Code, Tests und Git-Verlauf.

Das Register nennt aber nur *dass* etwas offen ist. **Die Begründung steht am
Punkt selbst**, und dorthin gehst du, bevor du ihn vorschlägst. Von dort führt
ein Verweis zu den bisherigen Messungen und Versuchen im Archiv.

`ROADMAP.md` enthält das Register, kurze Phasenstände P0 bis P16 und die offenen
Aufgaben nach Themen. Jede Aufgabe hat eine feste `RM-`-Kennung und eine
Sprungmarke. Phasenstand, Umsetzung und noch fehlende Abnahme sind getrennt:
Ein gebauter Weg ist ohne den geforderten Feldnachweis noch nicht abgenommen.

**Die Geschichte steht in `ROADMAP-ARCHIV.md`**: frühere Durchsichten, Funde,
zurückgenommene Behauptungen und gemessene Irrwege, dazu ein datiertes
Verzeichnis am Kopf. Dort stehen keine offenen Kästchen. Bei fortgeführten
Themen verweist der historische Befund auf die aktuelle Aufgabe. Wer an einer
Stelle arbeitet, an der schon jemand war, spart mit diesen Belegen
Tage. **Sieh dort nach, bevor du etwas vorschlägst** — ein „das haben wir
gemessen und es trug nicht" steht nur da.

Zwei Fallen dabei:

- **„Offen" in historischer Prosa ist kein aktueller Arbeitsauftrag.** Der
  Punkt kann inzwischen erledigt, überholt oder unter einer gemeinsamen
  Aufgabe fortgeführt sein. Maßgeblich ist die verlinkte aktuelle Aufgabe;
  der Abgleich im Archiv erklärt Zusammenführungen und Abschlüsse.
- **Ein offener Punkt ohne Kästchen zählt nicht.** Am 22.08.2026 lagen vier
  Punkte als Prosa in kästchenlosen Abschnitten, einer davon 163 Zeilen tief.
  Wer einen Fund festhält, gibt ihm ein `- [ ]`.

Dazu `git log --oneline -15`: was zuletzt passiert ist, sagt oft mehr über den
Stand als eine Liste, in der ein Haken fehlt.

## Vorschlagen

Nenne drei Dinge, nicht zwanzig:

1. **Was offen ist** — die konkreten Punkte, mit ihrer Stelle in der Roadmap.
2. **Was du als Nächstes empfiehlst**, mit Begründung: Was blockiert anderes?
   Was ist ein Fund aus einer Durchsicht und damit ein bekannter Fehler? Was
   fehlt einer Phase zur Abnahme nach Bauplan §40?
3. **Was es kostet** — grob, und was es an anderer Stelle nach sich zieht.

Ein bekannter Fehler schlägt ein neues Feature. Ein Punkt, der eine Phase
abschließt, schlägt einen, der eine neue anfängt.

## Fortschreiben

Eine reine Status- oder Empfehlungsfrage verändert die Dateien nicht.
Die folgenden Schritte gelten beim beauftragten Fortschreiben oder als
Dokumentation einer tatsächlich erledigten Arbeitseinheit.

Wird ein Punkt erledigt, gehört er in der Roadmap nachgezogen — und ein neuer
Fund gehört dort ergänzt, mit dem, was er gekostet hat. **Beides an zwei
Stellen**: am Punkt selbst und im Register oben. Vergisst du die zweite, wird
`tests/test_roadmap.py` rot und sagt dir, welcher Abschnitt nicht mehr passt.

Neues wird in `ROADMAP.md` geschrieben, nie ins Archiv. Neue Kennungen werden
fortlaufend nach der höchsten bereits vergebenen Kennung in Roadmap **und**
Archiv vergeben; entfernte Kennungen werden nicht wiederverwendet. Ist eine
Aufgabe abgeschlossen, wandert sie mit dem konkreten Nachweis ins Archiv.
Ein zusammengeführter Punkt verweist dort auf seine weiter offene Zielaufgabe;
er wird nicht als behobener Fehler ausgegeben. Jeder neue Archivabschnitt
bekommt eine Zeile im Verzeichnis am Archivkopf.

`ROADMAP.md` und `ROADMAP-ARCHIV.md` sind zusammen die Stelle, an der die
Geschichte dieses Projekts steht; `CLAUDE.md` und `AGENTS.md` sind es
ausdrücklich nicht. Das **Warum** einer Entscheidung steht in `konzepte/` —
dort ist der Index, der sagt, welchem Dokument man noch glauben darf.
