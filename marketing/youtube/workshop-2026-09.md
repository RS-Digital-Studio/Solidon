# YouTube-Produktion: STL passend machen

Produktionsauftrag (Robert, 13.09.2026): zehn Tage mit fünf Tutorials und fünf
ergänzenden Shorts, jedes Thema auf Deutsch und Englisch, verständlich für
Neueinsteiger und auf Reichweite getrimmt. Die Termine unten sind der lokale
Anschlussplan; ob sie in YouTube Studio stehen, sagt der Abschnitt
„Stand" am Ende.

## Kalender

Alle Zeiten Europe/Berlin. Beide Sprachen erscheinen zusammen, Tutorials um
12:00 Uhr, Shorts am folgenden Tag um 18:00 Uhr. Der vorherige lokale
[Veröffentlichungsplan](publication-plan-2026-09.md) nennt den 14. September
als letzten bereits eingeplanten Short-Tag.

| Datum | Format | Thema | Produktionskennung |
|---|---|---|---|
| 15.09.2026 | Tutorial DE + EN | Löcher vergrößern und verschieben, ohne neu zu zeichnen | `bohrung-anpassen` |
| 16.09.2026 | Short DE + EN | STL passt fast? Löcher ändern, Teil behalten | `bohrung-anpassen` |
| 17.09.2026 | Tutorial DE + EN | Eine Zahl ändern, beide Löcher folgen (benannte Maße) | `stl-varianten` |
| 18.09.2026 | Short DE + EN | Eine STL, zwei Zahlen, neue Variante | `stl-varianten` |
| 19.09.2026 | Tutorial DE + EN | Aus einem Loch wird ein Langloch | `langloch` |
| 20.09.2026 | Short DE + EN | Schraube soll verstellbar sein? Loch zum Langloch | `langloch` |
| 21.09.2026 | Tutorial DE + EN | Kanten abrunden und anfasen, direkt am fertigen Modell | `stl-kanten` |
| 22.09.2026 | Short DE + EN | Scharfe Kanten an der STL? Abrunden statt neu zeichnen | `stl-kanten` |
| 23.09.2026 | Tutorial DE + EN | Zwei Teile zusammenstecken: Stift und Loch in einem Schritt | `gegenstuecke` |
| 24.09.2026 | Short DE + EN | Zwei Teile verbinden: Stift und Loch in einem Schritt | `gegenstuecke` |

## Der gezeigte Weg

**Der einfache Kundenweg, nicht die Befehlspalette** (Robert, 13.09.2026).
Die erste Fassung der Aufnahmen (Codex, Nacht auf den 13.09.) öffnete jede
Operation über Bearbeiten → Befehlspalette → Suche → Enter. Das ist ein
Weg, den ein Kunde nicht nimmt. Seitdem zeigen die Filme:

| Handlung | Weg im Film |
|---|---|
| Bohrung ändern, Langloch | Loch anklicken → Karte rechts: Zahl tippen → Knopf *Übernehmen* unten |
| Verrunden, Fase, Fügeweg prüfen | Teil anklicken → Handlungsliste rechts → Dialog |
| Verschieben | Werkzeugleiste unten *Bewegen* → X tippen → Enter |
| Benanntes Maß in einen Schritt | Doppelklick auf den Schritt im Verlauf → *fx* am Feld → `@name` |
| Gegenstücke | Menü *Gegenstücke setzen* (der Dialog gehört dem Menü) |
| Rückgängig, Speichern, Öffnen | Menü, wie bisher |

**Kamera:** Nach jeder Änderung eine Nahaufnahme auf das Detail (Blickpunkt
auf die Bohrung, die Ecke, den Stift; 60 bis 130 mm Abstand, so dass der Rand
des Teils mit im Bild steht) und eine kurze Kamerafahrt um den Punkt. Nach dem
Import und am Ende eine Fahrt um das ganze Teil. Die Shorts nehmen dieselben
Nahaufnahmen (`shot(..., focus=...)`).

Die Suchfragen bestimmen den Einstieg, der konkrete App-Ablauf liefert den
Beleg. Die [Recherche](workshop-2026-09-research.md) trennt echte Suchsignale
von Vermutungen. Eine weltweite Alleinstellung wird nicht behauptet.

Komplexe Werte und Ergebnisse bekommen längere Lesedauer als ein einfacher
Klick (7 bis 13 Sekunden). Die Shorts verdichten jeweils einen Nutzen. Musik
wird wie in den bisherigen Filmen lokal erzeugt. Es gibt keinen Sprecher.

## Texte

Titel, Beschreibungen und Tags stehen in
[workshop-2026-09-copy.json](workshop-2026-09-copy.json). Sie sind für
Neueinsteiger geschrieben: zuerst das Problem („Löcher passen nicht?"), dann
die Lösung, „STL bearbeiten" / „edit STL" als Suchwort vorn, Demo-Link,
Hinweis auf die Einsteiger-Playlist, Aufnahmeherkunft und Verfügbarkeit, drei
Hashtags, zehn bis zwölf Tags. Keine Fremdmarken in Titeln oder Tags.
Kapitel ergänzt der Prüfer aus den wirklich aufgenommenen Zeitpunkten.

## Versionsbezug

Die Filme wurden am 13.09.2026 mit einem Entwicklungsstand von 0.4.1
aufgenommen. Öffentlich war damals 0.4.0; deshalb trugen die ursprünglichen
Texte den Zusatz „Vorschau“. Diese Aufnahmeherkunft bleibt erhalten.

Seit dem 15.09.2026 ist **0.4.2 veröffentlicht**. Die gezeigten Funktionen,
einschließlich Langloch, Verrunden und Fase an eingelesenen Netzen, sind darin
verfügbar. Die lokalen Titel und Beschreibungen sind entsprechend aktualisiert.
Das ändert keine Aufnahme und keinen bereits in YouTube Studio gespeicherten
Text; die dortige Übernahme dieser Textfassung steht noch aus.

## Dateien und Abnahme

Ausgabeordner: `marketing/video/workshop-2026-09/`, je Thema und Sprache ein
Unterordner mit Langfilm, Short, Titelbild, Schnittplänen und Belegen.
`verify_production.py` dort ist das lokale Tor: 20 Dateien, Zeitleisten,
Geometriebelege, unabhängig nachgemessene STL-Querschnitte, Uploadtexte mit
Kapiteln (`*.upload.txt`).

Ein Film gilt erst als fertig, wenn der Aufnahmeprozess sauber beendet wurde,
der gezeigte Modellzustand geprüft ist und die MP4 Bildgröße, Bildrate, Tonspur
und Dauer erfüllt. Erstellung und YouTube-Veröffentlichung bleiben getrennte
Angaben.

## Ergebnis-STLs und Beispielarchiv

Die bei der Produktion gefundenen offenen Nähte nach Bohrungsänderung,
Merkmalverschiebung, Verrunden und Fase an eingelesenen STLs sind in 0.4.2
behoben. Export und erneuter Import werden für diesen Kundenweg geprüft;
der Nachweis und die verbleibenden Aufgaben stehen unter
[RM-166](../../ROADMAP.md#rm-166).

Das Beispielarchiv der Werkstattfilme ist davon getrennt: Seine erneute
Erzeugung und Prüfung stehen weiterhin aus. Die Filmaufnahmen bleiben
unverändert.

## Stand

13.09.2026: Alle zwanzig Dateien sind aufgenommen, kodiert, vom Prüfer
abgenommen (20/20, `production-status.json`) und im YouTube Studio des Kanals
Solidon3D hochgeladen und terminiert. Sichtbarkeit „Geplant", Zeitzone
Europe/Berlin (GMT+0200); die Kennungen stehen auch in
[workshop-2026-09-copy.json](workshop-2026-09-copy.json) unter `youtube`.

| Termin | Thema | Deutsch | Englisch |
|---|---|---|---|
| 15.09.2026, 12:00 | Tutorial `bohrung-anpassen` | [OnUbdoI1YC0](https://youtu.be/OnUbdoI1YC0) | [FM1pPvrZZsw](https://youtu.be/FM1pPvrZZsw) |
| 16.09.2026, 18:00 | Short `bohrung-anpassen` | [-leBJmhdN30](https://youtube.com/shorts/-leBJmhdN30) | [y6m3KCd_L_o](https://youtube.com/shorts/y6m3KCd_L_o) |
| 17.09.2026, 12:00 | Tutorial `stl-varianten` | [CXlCAj0aBn4](https://youtu.be/CXlCAj0aBn4) | [1L3HyDscorY](https://youtu.be/1L3HyDscorY) |
| 18.09.2026, 18:00 | Short `stl-varianten` | [qRPYPTuId24](https://youtube.com/shorts/qRPYPTuId24) | [qdYjLeW0c6w](https://youtube.com/shorts/qdYjLeW0c6w) |
| 19.09.2026, 12:00 | Tutorial `langloch` | [WmxIqxm25e8](https://youtu.be/WmxIqxm25e8) | [rPFXvbmTDNo](https://youtu.be/rPFXvbmTDNo) |
| 20.09.2026, 18:00 | Short `langloch` | [PTh2JGc-dWk](https://youtube.com/shorts/PTh2JGc-dWk) | [yhGHWTftAtA](https://youtube.com/shorts/yhGHWTftAtA) |
| 21.09.2026, 12:00 | Tutorial `stl-kanten` | [qp_fEbsEPns](https://youtu.be/qp_fEbsEPns) | [w82aomXiBdg](https://youtu.be/w82aomXiBdg) |
| 22.09.2026, 18:00 | Short `stl-kanten` | [vdjoGMgdst0](https://youtube.com/shorts/vdjoGMgdst0) | [aTkUtLzYyrw](https://youtube.com/shorts/aTkUtLzYyrw) |
| 23.09.2026, 12:00 | Tutorial `gegenstuecke` | [s9PHIx4Jd00](https://youtu.be/s9PHIx4Jd00) | [17bsD2XhEJk](https://youtu.be/17bsD2XhEJk) |
| 24.09.2026, 18:00 | Short `gegenstuecke` | [5OuouH9JDz0](https://youtube.com/shorts/5OuouH9JDz0) | [snureno6po4](https://youtube.com/shorts/snureno6po4) |

Je Tutorial gesetzt: Titelbild aus dem Produktionsordner, Titel, Beschreibung
mit Kapiteln aus `*.upload.txt`, Tags, „nicht für Kinder", Videosprache,
Playlist der Sprache. Je Short zusätzlich der Link zum Tutorial in der
Beschreibung und als „Ähnliches Video" das öffentliche Montagehalter-Tutorial
derselben Sprache; das eigene Tutorial war beim Hochladen selbst noch geplant.
Nach dem 15.09. lässt sich die Verknüpfung auf das eigene Tutorial umstellen.
Die Sprachquerverweise (`cross_language_line`) sind nicht eingetragen, weil
die Kennungen erst beim Hochladen entstanden; sie können nach der
Veröffentlichung nachgetragen werden.

Nicht Teil dieser Produktion: die erneute Erzeugung und Prüfung des Archivs
der Beispiel-STLs zu RM-166 (Abschnitt oben); die Kanalseite selbst ist unverändert.
