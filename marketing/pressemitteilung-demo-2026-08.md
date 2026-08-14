# Pressemitteilung — Demo-Start Solidon3D

Zur Veröffentlichung ab **20.08.2026**. Ansprache: Fachpresse 3D-Druck
(3Druck.com, All3DP, Fabbaloo, Tom's Hardware, drucktipps3d), dazu die
Foren-Threads, in denen gerade über CAD für 3D-Druck gesprochen wird. Kurze
Fassung zuerst — wer mehr will, findet darunter Faktenblock und Bilder.

**Regieanweisung, nicht zum Mitschicken.** Der Text unterhalb der
Trennlinie geht hinaus, dieser Block nicht. Zwei Dinge davor:

* **Die Zahlen im Faktenblock sind ausgelesen, nicht gepflegt** — sie
  ändern sich, während weiterentwickelt wird.
  `tests/test_press_release.py` hält sie gegen die Quellen; vor dem
  Versand einmal die Suite laufen lassen, dann stimmen sie.
* **Kein Fachjargon, keine Dateipfade unterhalb der Trennlinie.** Der
  Empfänger hat keinen Zugriff auf das Projekt und liest kein Programm.
  Was sich nicht in einem Satz erklären lässt, gehört nicht hinein — der
  Test prüft auch das.

---

## Das heruntergeladene Teil passt nicht: Solidon3D macht es passend — Demo bis 30. Oktober kostenlos

**Amberg, 20. August 2026.** Der häufigste Satz am 3D-Drucker ist nicht
„ich will konstruieren", sondern „ich habe hier ein STL, und es passt
nicht". Die Programme, die dafür gebaut wurden, sind verschwunden:
Meshmixer wird seit Jahren nicht mehr gepflegt, Microsofts 3D Builder ist
abgekündigt. Solidon3D besetzt genau diese Lücke — eine
Desktop-Anwendung, die fremde Modelle repariert, ändert und passend
macht, und die vor dem Slicen sagt, was beim Drucken schiefgehen wird.
Ab heute steht eine vollständige, kostenlose Demo bereit; sie läuft bis
zum 30. Oktober 2026, ohne Konto und ohne Registrierung.

**Druckbarkeit vor dem Slicen, mit Begründung.** Solidon3D analysiert die
Schichten, bevor ein Slicer die Datei sieht: Überhänge gegen den Winkel
des Materials, Inseln ohne Verbindung nach unten, Brückenweiten, die
dünnste Wand gegen die Düse des eingestellten Druckers. Aus der Geometrie
leitet es Druckeinstellungen ab — und nennt zu jedem Wert den Grund.
Slicer prüfen, ob eine Datei kaputt ist; Solidon3D sagt, ob das Teil
gedruckt werden kann, solange es noch änderbar ist.

**Das Spiel einer Passung wird gemessen, nicht geraten.** Wie viel Luft
zwischen Zapfen und Loch bleiben muss, damit beides zusammengeht, hängt
am Drucker und am Material. In Solidon3D steht an dieser Stelle deshalb
keine feste Zahl im Modell, sondern der Satz „nimm das Spiel, das für
dieses Material gemessen wurde". Gemessen wird es einmal: Die Anwendung
erzeugt ein kleines Prüfstück mit abgestuften Spielmaßen, der Nutzer
druckt es und probiert durch, welche Stufe saugend passt — und trägt
diesen einen Wert ein. Von da an rechnen alle Teile damit, auch die, die
vorher entstanden sind. Ein Deckel, der zu stramm sitzt, wird nicht neu
konstruiert; eine Zahl ändert sich, und er passt.

**Eine KI, die nichts erfindet — und die nachgemessen wird.** Wer möchte,
beschreibt seine Änderung im Chat. Die KI führt sie aber nicht selbst
aus: Sie darf nur dieselben Arbeitsschritte auslösen, die auch in den
Menüs stehen. Gerechnet wird die Geometrie vom Programm, nie vom
Sprachmodell — es kann also keine Maße erfinden. Was die KI vorschlägt,
kommt außerdem als **ein** Schritt an, den ein einziges Rückgängig
vollständig zurücknimmt; es bleibt nichts halb Gebautes stehen.

Und das Verhalten ist keine Zusage, sondern eine Messung: 39 typische
Anfragen laufen als feste Prüfstrecke gegen jede Änderung am Programm.
Stand 8. August, mit einem Sprachmodell mittlerer Größe, das auf dem
eigenen Rechner läuft und keine Verbindung nach außen braucht: 28 der 39
Aufgaben gut gelöst, 98 Prozent der Befehle, die das Modell an die
Anwendung schickte, auf Anhieb gültig — und jede mehrdeutige Anfrage
endet in einer Rückfrage statt in einer Vermutung.

Dieselben Arbeitsschritte lassen sich auch von außen ansteuern, etwa aus
Entwicklerwerkzeugen wie Claude Code. Die Schnittstelle dafür ist
standardmäßig abgeschaltet und hört, wenn man sie einschaltet, nur auf
dem eigenen Rechner.

**Anschluss statt Wettlauf.** Wer sein Modell von einem KI-Generator wie
Meshy, Tripo oder Rodin erzeugen lässt, bekommt eine Oberfläche, keine
Konstruktion — meist mit Löchern im Netz und ohne brauchbare Maße.
Solidon3D tritt dahinter an: Es schließt die Löcher, sagt im Prüfbericht,
was noch im Weg steht, ordnet die Farben des Modells den tatsächlich
eingelegten Filamenten zu und zerlegt zu große Teile so, dass sie mit
eingesetzten Stiften wieder zusammenfinden — mit dem gemessenen Spiel des
eigenen Materials. Was herauskommt, geht als fertige Datei an den Slicer.

**Lokal, ohne Konto, Einmalkauf.** Solidon3D läuft vollständig auf dem
eigenen Rechner: keine Cloud, keine Datensammlung, kein Abo. Die KI
arbeitet wahlweise auf dem eigenen Rechner oder über einen selbst
hinterlegten Zugang zu einem Anbieter — und wer auf beides verzichtet,
verliert nur den Chat; alles andere bleibt benutzbar. Nach der Demo
erscheint Solidon3D als Einmalkauf zu 49 Euro (Einführungspreis, alle
1.x-Updates enthalten).

### Faktenblock

| | |
|---|---|
| Demo | 20.08.–30.10.2026, kostenlos, vollständig, ohne Konto |
| Plattformen | Windows 10/11, macOS, Linux |
| Sprachen | Deutsch, Englisch, Spanisch, Französisch, Italienisch, Portugiesisch |
| Umfang | 85 Arbeitsschritte, 17 geprüfte Bausteine, 40 Normteilmaße, 16 Druckerprofile, 9 Beispielprojekte |
| Formate | liest STL, 3MF, OBJ, GLB/GLTF, PLY, OFF, STEP, SVG, DXF — schreibt STL, 3MF, OBJ, PLY, GLB, STEP |
| Slicer-Übergabe | PrusaSlicer, OrcaSlicer, Cura — mit fertigem Profil, und die entstandene Druckdatei wird zur Gegenprobe zurückgelesen |
| KI | auf dem eigenen Rechner oder über einen selbst hinterlegten Zugang; von außen ansteuerbar, standardmäßig abgeschaltet |
| Preis nach der Demo | 49 € Einmalkauf zur Einführung, später 79 €; kein Konto, kein Abo |
| Website | https://solidon3d.de (deutsch), https://solidon3d.de/en/ (englisch) |

### Pressematerial

Bildschirmfotos in Druckqualität liegen unter
https://solidon3d.de/handbuch.html — es sind die Abbildungen des
Handbuchs, alle aus der laufenden Anwendung aufgenommen; auf Anfrage
auch als Paket. Dazu ein Kurzfilm vom Weg „heruntergeladenes Teil →
passend", knapp unter einer Minute, in Deutsch und Englisch, jeweils im
Querformat (1080p) und im Hochformat für die Kurzvideo-Plattformen. Auf
Anfrage stellen wir ihn ohne Sprecherstimme und ohne Beschriftung
bereit, wenn Sie ihn selbst vertonen möchten.

### Über RS Digital

RS Digital entwickelt Solidon3D in Deutschland. Die Anwendung entsteht
mit einem ungewöhnlichen Anspruch an Nachprüfbarkeit: 22 Regeln, die sich
das Projekt selbst gegeben hat, sind keine Absichtserklärung, sondern
automatische Prüfungen — sie laufen bei jeder Änderung mit und schlagen
fehl, wenn eine Regel verletzt wird. Dazu gehören das Verbot, dass die KI
Geometrie berechnet, ebenso wie die Zusicherung, dass keine Sprachfassung
unvollständig ausgeliefert werden kann.

**Pressekontakt:** support@solidon3d.de
