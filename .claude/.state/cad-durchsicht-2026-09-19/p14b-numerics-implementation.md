# P1.4b — eingefrorener numerischer Anschluss

Basis: `ee16040e7`. Umsetzung nach dem abgeschlossenen
`p14b-contract-review.md`, insbesondere dessen festem A/R/Q-Vertrag.
Keine Commits oder Pushes durch diesen Agenten.

## Dateien und öffentliche Grenze

- `app/core/perceive/matching.py`
- `app/core/perceive/CLAUDE.md`
- `tests/test_spatial_matching.py`
- neu: `tests/test_matching_competition.py`

`tests/test_matching.py` wurde ausgeführt, aber nicht geändert.
Die Korrektur des Fingerabdruckmaßes steht zusätzlich in
`p14b-answer-contract.md`: Nur relative Positionen sind normiert;
`diameter` bleibt das Rohmaß aus Durchmesser oder ersatzweise Fläche.

Öffentlich neu:

```python
require_injective(mapping: Mapping[str, str]) -> None
```

Ein Doppelziel erzeugt vor jeder Namen- bzw. Erzeugerübernahme einen
`AmbiguityError` mit Handlungsvorschlägen. `match`, `resolve` und die vier
`MatchResult`-Felder behalten ihre Signaturen. Keine Persistenz in diesem
Modul; Root/Schema-Agent besitzen `match_decisions` und `match_records`.
Die Karte benennt diese getrennten Verantwortungen.

## Was die Rechnung belegt

Die gemeinsame Kostenformel und die vollständige SciPy-Solverantwort bleiben
erhalten. `_Assignment` hält deren Zeilen, Spalten, ausgewählte Originalkosten
und den wiederholbaren blockweisen Zugang zu angenommenen Paaren.
Der strikte vollständige Minimumsbeweis aus P1.4a braucht weiterhin keine
globale Matrix; sein globaler Partnersupport besteht genau aus diesen Paaren.
Auch dort werden unzugeteilte alte Ansprüche gegen feste Besitzer geprüft.

Im Rückfall summiert `_hull_limits` die vorhandenen binären Floatkosten mit
`Fraction`. U enthält sämtliche Solverpaare einschließlich Strafpaaren;
L summiert Minima der kleineren vollständigen Solverseite. Die genaue Grenze
`m_r + U - L` wird pro Zeile nach unten in Float umgewandelt. Kein rationaler
Paarvergleich, kein Verlust kleiner Unterschiede beim Abziehen großer
Strafsummen, keine zweite Kostenformel.

`_global_support` richtet ungewählte Hüllenkanten alt→neu und gewählte
angenommene Paare neu→alt. Ein augmentierender Weg zwischen freien alten und
neuen Knoten hält mit `AmbiguityError` an. Vorwärts-/Rückwärtsreichweite und
iterative starke Zusammenhangskomponenten erhalten die kardinalitätserhaltend
möglichen Partner. Es gibt keine Rekursion über lange Merkmalsketten und
keinen zusätzlichen Kostensolver.

`_open_claims` berechnet aus diesem festen Support die unveränderlichen
Referenzoberwerte und daraus die bestehenden Zeilenrivalen R sowie die
Besitzeransprüche Q. `_close_claims` aktiviert Q ausschließlich bei bereits
offenen oder unzugeteilten alten Ansprüchen und führt geöffnete Besitzer bis
zum Fixpunkt vollständig nach. Ein offener Kandidat kann dadurch nicht
gleichzeitig Ziel eines freigegebenen Außenpaares bleiben.

Die Veröffentlichung teilt alte IDs disjunkt in freigegeben, offen und
verwaist. Offene Listen dürfen genau ein neues Ziel enthalten, wenn mehrere
alte Identitäten darum konkurrieren. `fresh` enthält sämtliche Ziele ohne
freigegebenen alten Namen. Die ursprüngliche Vorschlagsreihenfolge bleibt
innerhalb einer offenen Liste eine Anzeigeordnung, keine bestätigte Wahl.
Die geometrischen Listen können wie bisher beim späteren Antwortabschluss
als Herkunfts-/Reservierungsinformation bestehen bleiben.

## Unabhängige Gegenfälle und Ausgänge

Protokollordner:

`C:/Users/rober/AppData/Local/Temp/solidon-p14b-numerics-80e7211dae6942cd8995e0c14bfdd929`

Erster Gegenlauf auf unverändertem Produktcode: `red.txt`, **Exit 1,
6 failed / 1 passed**. Enthalten sind der echte 3→1-Identitätsfall, A–D
des Reviews und beide bislang ungeschützten Übernahmewege. A–D benutzen im
Test `POSITION_TOLERANCE=1`, damit die analytischen Binärbrüche unverändert
durch die echte Kostenformel laufen; der reale 3→1-Fall verwendet die
unveränderte Produktionsgrenze 0,08.

Der abschließende fokussierte Lauf:

```text
python -m pytest tests/test_matching.py tests/test_spatial_matching.py \
  tests/test_matching_competition.py -q --tb=short
153 passed
PYTEST_EXIT=0
```

`final-focused.txt` enthält den unmittelbaren Prozessausgang.
Die 30 neuen Konkurrenzfälle umfassen zusätzlich:

- alle Eingabepermutationen der analytischen A–D-Fälle;
- exakte U-L-Differenz von `2^-60` neben einer Strafsumme von `1e6`;
- einen nach oben gerundeten Floatwert, der aus der Hülle ausgeschlossen
  werden muss;
- vollständige Enumeration aller kleinen maximalen Hüllenmatchings gegen
  SCC/Reichweite, in beiden rechteckigen Richtungen;
- einen verbundenen Hüllennachbarn ohne alternierenden Wechselweg neben
  einem getrennten Hall-Defizit: die festen Identitäten bleiben fest;
- 50 kleine dyadische Kostenmatrizen mit unabhängig exakt aufgezählten
  globalen Optima: jede optimale Partnerschaft bleibt verfügbar, jede
  freigegebene Paarung liegt in sämtlichen Optima, kein offenes Außenziel;
- Q-Nähe zu einem teureren Besitzer, die einen anderweitig festen freien
  Partner ausdrücklich nicht öffnen darf;
- nichtmaximale Solverantwort mit echtem augmentierenden Weg;
- ursprünglicher Abbruch innerhalb Hülle, Reichweite, SCC und Anspruchsschluss.

Für B bleibt c→y mit Kosten 1 bewusst ausgeschlossen: globale y-Grenze 0,75,
Besitzergrenze 0,9875. Trotzdem sind alle drei alten Identitäten über den
alternierenden Weg offen. Das ist im Sollfall ausdrücklich erklärt.

Die P1.4a-Referenz wurde nicht zur neuen Erwartung umgeschrieben:
Ihre vollständige unabhängige Kostenformel liefert zusätzlich die ursprüngliche
Solverantwort. Geänderte Konkurrenzfälle prüfen diese Werte weiterhin exakt,
während die neue Identitätsaussage aus den oben genannten unabhängigen Fällen
kommt. Unveränderte Fälle prüfen weiterhin das gesamte bisherige Ergebnis,
einschließlich rechteckiger Verwaisungsreihenfolge und 1056er Zertifikatsfälle.

Gezielte Statik:

- `ruff.txt`: Ruff für Matcher und drei Testdateien, **Exit 0**.
- `format.txt`: dieselben vier Dateien, **Exit 0**.
- `mypy.txt`: `app/core/perceive/matching.py`, **Exit 0**.

## Grenzen und Freeze

Die Hülle ist konservativ, insbesondere bei Hall-Defiziten. Erhaltene
Kandidaten sind nicht sämtlich als gleich teuer bewiesen. Der Produktdeckel
und ungünstige dichte Fälle bleiben Teil der gesonderten Release-Messung.
Keine Leistungsprüfung, keine Fensterdatei und kein vollständiges Tor liefen
in diesem Paket. Der vollständige Persistenz-/Frage-/native Referenzanschluss
gehört den parallel verantwortlichen Agenten und wird hier nicht als geprüft
ausgegeben.

SHA-256 des eingefrorenen `matching.py`:

`C5A448641B00D24A2C095D1A82AE57D2C84550C39600B09F25CBE920D5636CD6`

Die beiden neuen deutschen Fehlerquellen wurden Root zur Katalogübernahme
gemeldet. Unabhängiger Abschlussreview steht noch aus.
## Vorwärtskorrektur aus dem unabhängigen Antwortreview

Die gezielte Antwortsonde belegte einen NaN-Treffer in `resolve`; ein ungültiger
Rivale konnte abhängig von der Reihenfolge ebenfalls einen gültigen Treffer
freigeben. Der unveränderte rote Anfangslauf der neuen Kernfälle steht in
`resolver-red.txt`: **28 failed, 8 passed, Exit 1**. Der Abschluss ergänzt die
umgekehrte Rivalenreihenfolge: `resolver-final.txt`, **117 passed, Exit 0** für
`test_matching_competition.py` und `test_spatial_matching.py`. Der bisherige
153er Nachweis bleibt als vorheriger Stand erhalten.

`resolve` verwendet nun `match_records.valid_fingerprint(..., legacy=True)`.
Fehlende Referenzlage, ungültige Vektorform, nichtendlicher aktueller Bezugsrahmen,
fehlende aktuelle Merkmalsmitte und nichtendliche Vektoren/Paarkosten lassen
jede Wiedererkennung offen. Das gilt auch für den ungültigen Nichtgewinner.
Der gemeinsame Kostenhelfer, Skalarreduktion und sämtliche Toleranzen bleiben
unverändert. Historisch optionale Achse, Rohmaß und Richtungsflag behalten die
alten Vorgaben; ein positiver direkter Fall belegt ihre Lesbarkeit.

Die ergänzten Fälle prüfen NaN und Unendlichkeit in Lage, Achse und Rohmaß,
falsche Vektorformen, fehlende Lage und Überlauf der Kosten trotz endlicher
Koordinaten. Die bereits vorhandene Abbruchgegenprobe mit echten Paarkosten
läuft mit. Ein erster Mypy-Lauf meldete die mögliche None-Form der optionalen
Mitte; die explizite leere Form für fehlende Mitte beseitigt den Typfehler
und bleibt fachlich unbekannt. `resolver-mypy-final.txt`: **Exit 0**.
Ruff und Format der drei betroffenen Python-Dateien sind ebenfalls grün.

Nur Matcher, neuer Konkurrenztest und eigener Kartenabsatz wurden geändert.
Keine Fenster-, Leistungs- oder breite Verbrauchersuite wurde nachgezogen.
Neuer eingefrorener Matcher-SHA256:

D76E399DB89F5B14BE3EE4EEED03F2F56543DF3D66855358C4ABDF7BE2F2FC95

