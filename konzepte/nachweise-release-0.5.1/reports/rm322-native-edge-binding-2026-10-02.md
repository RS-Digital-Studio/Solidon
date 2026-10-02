# RM-322: Netzkanten mit belegter Herkunft am exakten Körper zuordnen

Fachnachweise vom 02.10.2026 am gemeinsam bearbeiteten Quellstand. Die
gezielten Geometrie-, Kunden-, Cache- und Berichtsfälle sind grün; der
unabhängige Algorithmusreview hat keine offenen Produktbefunde. Die gezielte
Statikprüfung und alle 32 Dokumentwächter sind grün. Das zentrale Zweitreview,
Entwicklungstor und die tatsächliche Übernahme bleiben bis zu ihren eigenen
Belegen offen.
Die Cacheversionen von `fillet_edges` und `chamfer_edges` steigen auf **14**.

## Was die Zuordnung belegt

`edit.native_edges_of_chains` bindet ausgewählte Netzzüge über die tatsächliche
Dreiecksherkunft an gemeinsame native Kanten. Ein gemeinsames Flächenpaar
allein reicht nicht: Mehrere Kanten können dieselben zwei Flächen trennen.
Zusätzlich werden der räumliche Kurvenverlauf, Eindeutigkeit und vollständige
Abdeckung geprüft. Ein fehlender oder gescheiterter nativer Kurvensampler
liefert keine Ersatzzuordnung nur anhand seiner Endpunkte.

Die Abdeckung wird in beiden Richtungen durch zusammenhängende Intervalle
belegt. Eine Teilwahl darf keine ganze native Kante freigeben. Fallen bei der
Bandprüfung Züge heraus, wird die verbleibende Zuordnung erneut bis zu einem
stabilen Ergebnis geprüft. Unmittelbar gemessene Engstellen und dadurch
mittelbar verlorene Zuordnungen behalten unterschiedliche Begründungen.
Der Abbruch wird durch die Herkunfts-, Kurven- und Abdeckungsarbeit geführt.

Eine leere zulässige Gruppe sagt ausdrücklich ab. Sie fällt nicht mehr über
`None` auf sämtliche nativen Kanten zurück. Ausgelassene Netzzüge werden mit
ihrer Zahl und sämtlichen Kontursegmenten gemeldet; der Ansprung liegt auf
einem tatsächlich ausgelassenen Segment. Fehler behalten diese Ortsdaten
auch im Abschlussbericht. Es findet keine stillschweigende Umwandlung des
exakten Körpers in ein Netz statt.

## Präzisierung des ursprünglichen Kundenfalls

Untersucht wurde `pegboard-gs-100-v2.step` aus dem unveränderten Kundenkorpus:

- SHA-256: `3199743b2915a73174a4680000dfa4f2592493b9039831cbf5666103824bc3f9`.
- Eingangsvolumen: 34646,081384294266 mm³; geschlossen und wasserdicht.
- Das untersuchte Netz hat 3768 Dreiecke; der exakte Körper besitzt
  18 senkrechte Kanten.
- Die Netzgruppierung wählt bei R1 und R2 jeweils zehn Züge.

Vier lange Züge von etwa 38,29 beziehungsweise 39 mm liegen zwischen zwei
verschiedenen nativen Flächen. Die tatsächlichen Flächenpaare sind 9/15,
9/13, 13/23 und 15/30; ihre gemeinsamen Kanten tragen die nativen Nummern
33, 35, 46 und 51. Für diese vier Stellen beträgt die gemessene Grenze
jeweils 0,8535533905932737 mm. R1 und R2 sind dort zu groß.

Die übrigen sechs kurzen Züge liegen vollständig innerhalb einer einzigen
nativen Fläche, je drei in Fläche 40 und 42. Ihre Längen betragen etwa
0,337 bis 0,411 mm. Sie haben keinen nativen Kantenpartner. Damit ist keine
Glattheit dieser Flächen bewiesen: Auch ein Knick innerhalb einer C0-Fläche
kann ohne eigene Topologiekante vorliegen.

Die frühere Aussage über sechs passende exakte Rundungen war deshalb zu
weitgehend. Der ursprüngliche Netzversuch bleibt in
`laeufe/kanten-gruppe-brep2.txt` unverändert erhalten. Für den exakten Körper
ist bei R1/R2 eine begründete Absage mit allen zehn Stellen richtig. R0,3
liefert dagegen einen echten Teilerfolg mit den vier nachgewiesenen Kanten.

## Nachlauf am Kundenmodell

R0,3/R1/R2 wurden in `draft` und `fine` gerechnet, jeweils zweimal:
**6 bestanden, 36,26 s, Exit 0**. Quelldaten und Dateihash blieben in allen
sechs Fällen unverändert.

| Radius | Ergebnis in beiden Qualitätsstufen | Gemessenes Endvolumen | Bericht |
|---|---|---:|---|
| 0,3 mm | Vier belegte Kanten bearbeitet | 34645,781884476986 mm³ | Sechs ausgelassene Stellen mit sechs Kontursegmenten |
| 1 mm | Absage am Rundungsschritt; Eingang bleibt erhalten | 34646,081384294266 mm³ | Vier Engstellen und sechs Stellen ohne Partner; zehn Kontursegmente |
| 2 mm | Absage am Rundungsschritt; Eingang bleibt erhalten | 34646,081384294266 mm³ | Vier Engstellen und sechs Stellen ohne Partner; zehn Kontursegmente |

Diese Volumenwerte sind Messwerte der Kundendatei, keine unabhängig
hergeleiteten Sollwerte. Bei R0,3 steigt der kumulierte Cachezähler von 1
auf 3: Der Quellschritt war vorbereitet; beim zweiten Lauf wird auch die
Rundungsoperation wiederverwendet. Bei R1/R2 steigt er von 1 auf 2, weil nur
der vorbereitete Quellschritt aus dem Cache kommt. Ein abgebrochener Lauf
veröffentlicht keinen vermeintlichen Erfolgsstand.

## Analytischer Verlauf und Folgeoperation

Ein C0-Dachkörper hat den Querschnitt
`(0,0), (40,0), (40,20), (30,20), (20,30), (10,20), (0,20)` und 40 mm Höhe.
Sein Volumen ist `(40·20 + 20·10/2)·40 = 36000 mm³`.

Der Erfolgsfall gibt kontrolliert zwei echte untere Netzzüge und einen
tatsächlichen Dachzug ohne nativen Partner als Auswahl vor. Herkunft und
Geometriebau bleiben echt. Auf R1 oder Fase1 folgt die registrierte Bohrung
Ø4 über 40 mm, ausdrücklich ohne Materialausgleich. Geprüft werden beide
Qualitätsstufen und der warme Operationscache: **4 bestanden, 14,43 s,
Exit 0**.

Das unabhängige Sollvolumen lautet für die Rundung
`36000 − 2·40·(1−π/4) − π·2²·40 mm³`, für die Fase
`36000 − 2·40·0,5 − π·2²·40 mm³`. Die vollständige automatische Dachgruppe
ist ein anderer Fall: OpenCASCADE weist sie bei diesem Maß ab. Der Erfolg
der kontrollierten Teilgruppe wird ihr nicht zugeschrieben.

## Unabhängige Reviews und wirkliche Gegenproben

Der erste Produktreview fand zwei Abdeckungslücken. Ein echter 10-mm-Quader
mit dreifach unterteiltem Tessellierungsnetz und erhaltener Dreiecksherkunft
hält beide Fehler fest:

1. Die Teile 0–1,25, 3,75–6,25 und 8,75–10 einer Geraden 0–10 erfüllen die punktuellen
   Rückproben 0/5/10, obwohl große Lücken bleiben. Der kontinuierliche
   Intervallnachweis schließt dies aus.
2. Bei A→e0, B→e0/e1 und C→e1 kann eine Engstelle in A auch B ausschließen.
   Dann darf C nicht die ganze e1 freigeben. Die tatsächliche Zuordnung wird
   nach der Bandfilterung erneut geprüft. Nur die Breitenmessung für A wird
   im Gegenfall kontrolliert vorgegeben; die Bindungen entstehen echt.

Vorher: **2 fehlgeschlagen und 1 positive Kontrolle**, 1,09 s, Exit 1.
Nachher, zusammen mit Kreis-, Linsen- und Abbruchfällen: **10 bestanden**,
0,93 s, Exit 0. Beide Befunde sind im unabhängigen Nachreview geschlossen.

Der Nachreview fand zusätzlich eine kurze Sehne ohne belegendes Intervall:
Bei 0,00005 mm Sehnenlänge und 0,0001 mm Schweißtoleranz ließ die alte
Endbedingung noch `True` durch. Der gültige Rotbeleg hat **1 fehlgeschlagen
und 1 positive Kontrolle**, 1,15 s, Exit 1. Leere Intervallmengen werden nun
vor der Toleranzprüfung abgelehnt. Auch dieser Fix ist unabhängig freigegeben.
Ein vorheriger Testlauf mit falschem Klassenzugriff zählt nicht als
Produktgegenbeweis.

Der neue Samplerausfall-Test arbeitet an genau der tatsächlich importierten
OCP-Modulansicht und prüft die reale Zuordnung nach Wiederherstellung im
selben Test. Dadurch kann seine kontrollierte Störung keine späteren
Kreisfälle verfälschen. Fehlende Herkunft, Samplerausfall und begrenztes
Plattformrauschen bestanden anschließend gemeinsam mit **5 Fällen**,
1,16 s, Exit 0.

Der abschließende kombinierte Direktlauf enthält sämtliche neuen Gegenfälle,
Abbruch auch über beide registrierten Operationen, Verlauf/Cache sowie
bestehende Dünnwand-, Rundungsgruppen- und Fasenverträge beider Kerne:
**57 bestanden, 995 abgewählt, 38,53 s, Exit 0**.
Die vier analytischen Verlaufsfälle und die genannten direkten Teilläufe
sind darin enthalten; ihre Fallzahlen werden nicht zusätzlich addiert.
Die analytischen Sollvergleiche benennen `abs=EPS_GEOM, rel=0.0`
ausdrücklich. Bereits mit dem zuvor gesetzten `abs` allein verwendete die
lokale pytest-Version ausschließlich die absolute Toleranz.

## Bericht, Bedienanschluss und Übersetzungen

Der bestehende Plain-Test
`test_show_the_place_flies_and_marks_like_the_report_click` führt einen
Fehler mit drei getrennten Kontursegmenten über den tatsächlichen Weg
`_finding_from → as_error → _show_error_place → _show_finding_at`.
Geprüft werden alle Segmente, Zielpunkt mit Darstellungsversatz, Objekt-
und Operationskennung, der angebotene Weg *Stelle zeigen* und unveränderte
ursprüngliche Fehlerwerte. Vorher war dieser Fall rot; nachher grün.
Mit dem Kernfehler- und Transportfall gemeinsam: **2 bestanden, 833
abgewählt, 0,66 s, Exit 0**.

Die drei neuen Meldungen stehen in allen fünf Übersetzungskatalogen.
Ein unabhängiger Wortlautreview entfernte zuvor die zu weitgehende
Behauptung, alle übrigen Kanten seien bearbeitet worden. Die korrigierten
Texte und der UI-Anschluss sind freigegeben. Der erneute Kataloglauf zu
Vollständigkeit, Platzhaltern und Apostrophen ist grün:
**10 bestanden, 206 abgewählt, 10,80 s, Exit 0**.

## Belege und Abnahmegrenze

Die dauerhaft reproduzierbaren Kernfälle stehen in `tests/test_brep.py`
und `tests/test_evaluation.py`, der Bedienanschluss in `tests/test_ui.py`.
Lokale vollständige Ausgaben und Kundensonden liegen unter
`tmp/rm322-20261002/`: `inspect-mapping-before.json`, `absolute-final-direct.txt`,
`coverage-review-red.txt`, `short-coverage-red-valid.txt`,
`binding-boundaries-final.txt`, `registered-partial-exact-diameter.txt`,
`customer-first.txt`, die sechs `customer-r*-*.json`, `customer-partial-final.txt`,
`report-ui-final.txt` und `translations-final.txt`. Die zwei R0,3-Kundenfälle
bestanden beim letzten Nachgang nochmals (14,70 s, Exit 0).

Ruff und Formatprüfung der fünf berührten Python-Dateien, mypy für die drei
Produktdateien sowie die eigene Diffprüfung sind grün. Der Kartenbudgetwächter
bestand nach Kürzung des eigenen neuen Absatzes; fremde Karteninhalte wurden
dabei erhalten. Die Protokolle heißen `ruff-absolute-final.txt`,
`format-absolute-final.txt`, `mypy-reviewed.txt`, `diffcheck-absolute-final.txt`
und `card-budget-final.txt`. Der anschließende gemeinsame Dokumentlauf
`documents-final.txt` bestand mit **32 Fällen, 1,74 s, Exit 0**.

Der Plain-UI-Test verwendet einen kleinen Ein-/Ausgabehost. Er belegt die
tatsächlichen Adapter- und Steuerungsmethoden, keine native Fenster- oder
Rendererabnahme. Fenster-, Renderer- und Leistungsläufe bleiben der
Releaseabnahme zugeordnet. Zentrales Zweitreview, Entwicklungslauf und
Commit-/Pushbeleg werden getrennt ergänzt.
