# Pressemitteilung — Demo-Start Solidon3D

Zur Veröffentlichung ab **20.08.2026**. Ansprache: Fachpresse 3D-Druck
(3Druck.com, All3DP, Fabbaloo, Tom's Hardware, drucktipps3d), dazu die
Foren-Threads, in denen gerade über CAD für 3D-Druck gesprochen wird. Kurze
Fassung zuerst — wer mehr will, findet darunter Faktenblock und Bilder.

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

**Toleranzen als Verweis, nicht als Zahl.** Wie viel Spiel eine
Steckpassung braucht, hängt an Drucker und Material — deshalb steht in
Solidon3D an dieser Stelle keine geratene Zahl, sondern ein Verweis:
`auto:PETG`. Der Wert dahinter kommt aus Testkörpern, die der Nutzer
einmal druckt und ausmisst. Ein Teil, das zu stramm sitzt, wird nicht neu
konstruiert — eine Zahl ändert sich, und das ganze Teil stimmt wieder.

**Ein KI-Agent, der nichts erfindet — und gemessen wird.** Der Chat
bedient dieselben Operationen wie die Menüs; Geometrie rechnet Code, nie
das Sprachmodell. Jeder Vorschlag ist genau eine Transaktion, die ein
einziges Undo vollständig zurücknimmt. Und das Verhalten ist gemessen,
nicht versprochen: Eine Suite aus 39 Referenzanfragen läuft gegen jede
Änderung — Stand 8. August, mit einem lokalen 14-Milliarden-Modell ganz
ohne Cloud: 28 von 39 gut beantwortet, 98 Prozent der Werkzeugaufrufe im
ersten Versuch gültig, jede mehrdeutige Anfrage endet in einer Rückfrage.
Über die eingebaute MCP-Schnittstelle steuern auch externe Werkzeuge wie
Claude Code dieselben Operationen fern — standardmäßig aus, nur auf dem
eigenen Rechner.

**Anschluss statt Wettlauf.** Wer mit Meshy, Tripo oder Rodin erzeugt,
bringt das GLB mit: Reparaturkette, Prüfbericht, Farbzuordnung auf die
eigenen Filamente, Zerlegen mit Passstiften — mit Spiel aus dem
kalibrierten Materialprofil statt generischer Verbinder — und Übergabe
als 3MF an den Slicer.

**Lokal, ohne Konto, Einmalkauf.** Solidon3D läuft vollständig auf dem
eigenen Rechner: keine Cloud, keine Telemetrie, kein Abo. Die KI läuft
wahlweise lokal über Ollama oder über einen eigenen API-Schlüssel — und
ohne beides bleibt alles außer dem Chat benutzbar. Nach der Demo
erscheint Solidon3D als Einmalkauf zu 49 Euro (Einführungspreis, alle
1.x-Updates enthalten).

### Faktenblock

| | |
|---|---|
| Demo | 20.08.–30.10.2026, kostenlos, vollständig, ohne Konto |
| Plattformen | Windows 10/11, Linux |
| Sprachen | Deutsch, Englisch, Spanisch, Französisch, Italienisch, Portugiesisch |
| Umfang | 77 Operationen, 16 geprüfte Bausteine, 40 Normteilmaße, 16 Druckerprofile, 8 Beispielprojekte |
| Formate | liest STL, 3MF, OBJ, GLB/GLTF, PLY, OFF, STEP, SVG, DXF — schreibt STL, 3MF, OBJ, PLY, GLB, STEP |
| Slicer-Übergabe | PrusaSlicer, OrcaSlicer, Cura — mit Profil und G-Code-Gegenprobe |
| KI | lokal (Ollama) oder eigener Schlüssel; MCP-Schnittstelle für Claude Code u. a. |
| Preis nach der Demo | 49 € Einmalkauf zur Einführung, später 79 €; kein Konto, kein Abo |
| Website | https://solidon3d.de (deutsch), https://solidon3d.de/en/ (englisch) |

### Pressematerial

Bildschirmfotos in Druckqualität liegen unter
https://solidon3d.de/handbuch.html (Handbuch, alle Abbildungen aus der
laufenden Anwendung) — auf Anfrage auch als Paket. Ein kurzes Video vom
Weg „heruntergeladenes Teil → passend" ist in Arbeit
(`marketing/drehanleitung-video-1.md`).

### Über RS Digital

RS Digital entwickelt Solidon3D in Deutschland. Die Anwendung entsteht
mit einem ungewöhnlichen Anspruch an Nachprüfbarkeit: Jede der 22 harten
Projektregeln — vom Verbot, dass die KI Geometrie rechnet, bis zur
Vollständigkeit jeder Übersetzung — ist ein automatischer Test.

**Pressekontakt:** support@solidon3d.de
