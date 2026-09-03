---
name: saubere-messung-falsche-frage
description: Fünf Bauarten, wie eine korrekt gefahrene Messung trotzdem nichts belegt — Stand, Ebene, Prüfling, eigener Aufbau, Vergleichsschlüssel. Mit den Warnzeichen.
metadata:
  type: feedback
---

Am 03.09.2026 liefen zwischen fünf Sitzungen fünf Messungen sauber und
belegten trotzdem nichts. Keine war falsch gefahren; jede beantwortete eine
andere Frage als die gestellte.

**Der Stand ist weg.** Ich meldete 7f deutsche Bezeichner in `advise.py` — er
hatte sie zwei Stunden vorher umbenannt. Und ich redete a0 einen Wächter aus
mit „36 verworfene Rückgabewerte, null davon eine Auskunft"; die Signatur
`(first, second, _findings)` stand bis eine Stunde vor meiner Messung in
`autosplit.py`. **Null Treffer heißt nicht „kommt nicht vor", sondern „kommt
gerade nicht vor".**

**Die Ebene ist falsch.** Ich fragte einen `Finding` nach seinen Auswegen und
schloss aus der leeren Liste auf einen Fehler ohne Ausweg. Findings tragen
keine Aktionen — die ordnet `panels.actions_for` zu, und für Codes mit `op.`
und Schrittkennung liefert sie `correct_input`. Gemessen wurde der Kern, die
Antwort steht in der Oberfläche. Siehe [[pruefstand-geht-den-weg-der-oberflaeche]].

Diese Bauart kehrt am häufigsten zurück, und 3d-druck-c7 hat gesagt warum:
**Der falsche Weg ist billiger.** Den Kern direkt zu rufen spart den Aufbau
der Anwendung; man tut es, um schnell eine Zahl zu bekommen, und bekommt
eine, die für den Kern gilt und nicht für den Kunden. c7 ist ihr am
03.09.2026 zweimal aufgesessen — einmal bei einer STEP-Datei, die angeblich
nicht lud (`plan.py` fängt STEP vor `read_model` ab), einmal bei einer STL,
die angeblich nicht wasserdicht war (ohne `normalise` ist **keine** STL
wasserdicht, weil jedes Dreieck seine Ecken einzeln trägt) — und hatte sie
dazwischen dreimal bei anderen benannt. Siehe [[benannte-falle-schuetzt-nicht]].

**Der Prüfling trägt das Merkmal nicht.** 7b maß den Kontrast eines
Kontaktschattens in einer selbst gestellten Szene, die gar keinen trug — die
Zahlen waren Rauschen, sauber erhoben. Siehe [[testprojekt-trifft-den-fall-nicht]].

**Der eigene Aufbau erzeugt den Befund.** Ich meldete, eine STL mit NaN friere
die Auswertung ein: acht Minuten ohne Ergebnis. Der Stack zeigte
`ask_from_worker` — die Operation fragte nach der Einheit, und in meinem
Prüfstand beantwortete die Frage niemand. `evaluate_now` blockiert den
Hauptthread, das Signal kann nicht zugestellt werden. Im Fenster steht dort ein
Dialog. **Ein Hänger im Prüfstand ist kein Hänger im Produkt.**

**Der Vergleichsschlüssel ist der falsche.** a0 verglich zwei Schichtlisten
über den **Index**; eine hatte einen Eintrag mehr. Ab der fehlenden Stelle
vergleicht man verschiedene Höhen, und jede weitere „Abweichung" ist nur der
Versatz — aus einer fehlenden Schicht wurden so 158 scheinbare. Nach Höhe
verglichen: 204 gemeinsame Schichten, davon null flächenverschieden, und genau
eine fehlt.

**Woran man sie merkt** — das Nützlichste daran, denn die Ursachen sieht man
erst hinterher, die Zeichen schon:

| Bauart | Warnzeichen im Ergebnis |
|---|---|
| alter Stand | eine Zahl wiederholt sich, obwohl sich etwas geändert hat |
| falsche Ebene | es wird besser, aber nicht gut |
| falsches Ziel | die Zahl ist zu glatt oder zu rund |
| Prüfling ohne das Merkmal | die Zahlen streuen kaum — gemessen wird Rauschen |
| falscher Vergleichsschlüssel | die Abweichungen hören ab einer Stelle nicht mehr auf |

Die letzten beiden sind die tückischsten. Ein Prüfling ohne das Merkmal
**liefert Zahlen**: 1,85 / 1,88 / 1,94 sieht aus wie eine Reihe, die etwas
sagt; entschieden hat es dort erst das Bild, nicht die Zahl. Und ein Versatz
ist **ansteckend**, während eine echte Abweichung punktuell bleibt — wer viele
Abweichungen sieht, sollte zuerst den Schlüssel prüfen und nicht die Werte.

**Why:** Alle fünf fühlten sich beim Messen richtig an, und vier davon fand
nicht der Messende, sondern der Nachbar — der die eigene Erwartung nicht
teilte. Eine Messung, die bestätigt, was man vermutet, wird nicht nachgeprüft;
siehe [[bestaetigung-verstaerkt-die-fehlannahme]] und
[[der-nachbar-findet-den-fehler]].

**How to apply:** Vor dem Melden eines Befundes fünf Fragen — **Stand:** Ist
der Code von jetzt (`git log -3 <datei>`)? **Ebene:** Antwortet die Stelle, die
ich gefragt habe, oder eine darüber? **Prüfling:** Trägt der Gegenstand das
Merkmal, das ich messe? **Aufbau:** Kann mein eigenes Gerüst den Befund
erzeugen? **Schlüssel:** Vergleiche ich über etwas, das in beiden Listen
dasselbe bedeutet? Bei einer Messung, die die eigene Vermutung bestätigt, sind
alle fünf Pflicht. Und: Was der Nachbar widerlegt, wird nachgemessen und nicht
verteidigt.
