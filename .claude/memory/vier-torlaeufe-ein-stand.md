---
name: vier-torlaeufe-ein-stand
description: "Das Tor sind vier Läufe, und ihr Ergebnis gilt nur zusammen für denselben Stand — wer sie zu verschiedenen Zeitpunkten fährt und als ein Ergebnis meldet, berichtet über einen Stand, den es nie gab."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-27T16:48:43.569Z
---

„Tor grün" ist eine Aussage über **einen** Stand. Sie setzt sich aus vier
Läufen zusammen — `ruff check`, `ruff format --check`, `mypy` und die Suite —,
und die vier laufen unterschiedlich lange. Genau daraus entsteht die Falle:
Man fährt sie im Arbeitsfluss, jeden zu seiner Zeit, und fasst sie am Ende zu
einem Satz zusammen.

Am 27.08.2026 so passiert: mypy lief vor dem vorletzten Commit, die Suite nach
dem letzten. Der Bericht sagte „ruff, format, mypy gegen alle drei Plattformen
grün, 4246 passed" — und `origin/main` trug einen mypy-Fehler, den der letzte
Commit eingeführt hatte. Gefunden hat ihn eine andere Sitzung.

**Die Suite fängt diese Klasse grundsätzlich nicht.** Ein Name, der über ein
Modul durchgereicht statt exportiert wird (`no_implicit_reexport`), läuft zur
Laufzeit einwandfrei; 4246 grüne Tests sagen darüber nichts. mypy ist der
einzige der vier Läufe, der ihn sieht — und er kostet zwanzig Sekunden.

Zwei Sätze:

- **Der letzte Commit entscheidet, welcher Lauf zählt.** Verschiebt er
  Importe, Konstanten oder Modulgrenzen, ist mypy der wichtigste und nicht die
  Suite.
- **Ein Torergebnis wird am Stand gemessen, den man meldet** — nicht an dem,
  an dem der Lauf zufällig gestartet ist. Läuft danach noch ein Commit, gilt
  das Ergebnis nicht mehr.

Verwandt: [[messung-traegt-nur-am-ort-ihrer-messung]] (dort der Ort, hier der
Zeitpunkt), [[geteilter-baum-misst-zeitpunkt]] (dort ändert ein anderer den
Stand, hier man selbst), [[mypy-prueft-die-laufende-plattform]].
