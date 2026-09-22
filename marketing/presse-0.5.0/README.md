# Presseansprache Solidon3D 0.5.0

**Direkt zum Versand:** [`VERSAND.html`](VERSAND.html) enthält für jeden
Empfänger einen eigenen Link auf den vollständig ausgefüllten E-Mail-Entwurf.

Der Verteiler ist derselbe wie bei 0.3.3 — dieselben fünfundzwanzig
Redaktionen, dieselben Adressen, dieselbe Sprachverteilung. Was neu ist, sind
die Texte: Sie sind für 0.5.0 geschrieben und nicht umgeschrieben.

> **Diese Entwürfe sind nicht versandt, und sie dürfen es noch nicht sein.**
> Es sind drei Bedingungen, und jede ist prüfbar:
>
> 1. **0.5.0 ist veröffentlicht** — Pakete unter `website/dl/`, `version.json`
>    auf dem Server, Changelog-Seite und Bilder öffentlich auf dem beworbenen
>    Stand. Eine Redaktion, die einem Link folgt, muss finden, was die Mail
>    verspricht.
> 2. **RM-188 ist abgeschlossen.** Der Kern dieser Welle ist der durchgehend
>    exakte Körper, und mehrere Pakete waren am 22.09.2026 noch offen (P3.1
>    bis P3.5, P4.0 bis P4.3, P6.1 bis P6.7, P7.1 bis P7.4, P5.1 bis P5.3).
>    Jede Mail nennt nur, was zu ihrem Versandtag gebaut *und* abgenommen ist;
>    die Abschnitte unter „Was als Nächstes kommt" sind als Ausblick
>    gekennzeichnet und dürfen nicht als Funktion gelesen werden.
> 3. **Die Zahlen stimmen.** Seit der Überarbeitung vom 22.09.2026 steht in
>    keinem Entwurf mehr eine Änderungszahl: Eine Redaktion liest eine
>    Geschichte, keine Messreihe (Entscheidung Robert). Der Wächter
>    `tests/test_changelog.py::test_the_press_drafts_count_the_same_changes`
>    bleibt scharf für den Fall, dass wieder eine hineinkommt. Erlaubt wären
>    dann genau zwei Werte, die Punkte dieser Fassung und die Summe über alle.

## Die Geschichte dieser Welle

**Bei 0.3.3 war die Nachricht: ein erkanntes Merkmal lässt sich bearbeiten.
Bei 0.5.0 ist sie: aus dem Netz wird ein Körper.**

Der Unterschied ist für eine Redaktion in einem Satz erklärbar und in fünf
Minuten nachmessbar. Eine heruntergeladene STL speichert Dreiecke. Solidon
erkannte darin schon bisher Bohrungen, Zapfen und Senkungen und konnte sie
ändern — aber das Ergebnis blieb ein Netz, und wer es als STEP in ein CAD trug,
bekam wieder Dreiecke. Jetzt entstehen Grundkörper mit echten Flächen und
Kanten, Bohrung, Langloch, Senkung, Zapfen, Wulst, Kehle und Gewinde bleiben am
exakten Körper exakt, wenn man sie versetzt, verdoppelt, dreht oder entfernt,
und STEP geht sauber hinein und hinaus.

Der Haken *„Flächen und Kanten später bearbeiten"* ist dabei **gefallen**, und
das ist der eigentliche Punkt: Es gibt keine Kernwahl mehr in der Oberfläche.
Der Kunde entscheidet nicht zwischen zwei Betriebsarten, er arbeitet einfach;
Solidon hält den exakten Körper, solange es geht, und sagt es, wenn es nicht
geht. Alte Projekte rechnen unverändert weiter.

**Die zweite Ebene ist das Muster, und sie ist die bildstärkste.** Ein
Wabenmuster, ein Rändel, Rippen, Wellen oder Noppen standen im Objektbaum
bisher als Hunderte einzelner Flächen — unbrauchbar. Jetzt stehen sie als *ein*
Muster mit Teilung, Zellbreite und Tiefe, auch um einen Griff herum. Mit einem
Klick entfernt, mit drei Zahlen neu gesetzt, und die Zellen bleiben, wo sie
waren. Eine Textur um einen Zylinder folgt der Rundung: Rillen sind überall
gleich tief, und ein Muster um den ganzen Umfang schließt ohne Naht — die
Teilung rückt dafür auf das Maß, das aufgeht. Das ist der Punkt, an dem ein
Bildschirmfoto die Meldung trägt.

**Die dritte ist die Bedienung am Modell selbst.** Wer eine Bohrung anklickt,
bekommt ihre Maße im Bild: Abstände zu den Kanten, Mitte, Durchmesser, als
Zahlenfelder zum Tippen, mit Vorschau. Der Bezug eines Maßes lässt sich per
Rechtsklick wechseln oder im Modell anklicken. Kein vorgelagerter Dialog, keine
doppelten Felder im Panel.

**Dazu, für die Werkstatt:** Resin-Drucker sind da — zwei allgemeine Geräte
nach Bauraum, ein eigenes mit Pixelgröße und Mindestwand anlegbar, und ein
Resin-Projekt bekommt keine Ratschläge mehr zu Düse, Brim oder Brücken. Exakte
Körper werden für einen Resin-Drucker so fein vernetzt, wie seine Pixel es
verlangen; der Prüfbericht nennt das Maß.

**Und was man nicht sieht, aber merkt:** Ein Modell mit 200 000 Dreiecken zu
verschieben oder zu drehen antwortet in einer halben Sekunde statt in acht.
Rückgängig antwortet sofort. Eine Lochplatte mit 200 000 Dreiecken ist in einer
Sekunde erkannt, eine glatte Freiform, die vorher Minuten brauchte, in
Sekunden. Solidon startet in der Hälfte der Zeit. Und ein Modell mit offenen
Stellen wird beim Einlesen geschlossen, statt nur gemeldet zu werden — Löcher
im Netz, umgekehrte Flächen, Kanten mit drei Flächen; eine große Öffnung nennt
der Prüfbericht eigens, damit der Nutzer nachsehen kann.

## Was in den Mails nicht steht

- **Keine geschlossene Sicherheits- oder Lizenzlücke.** Dieselbe Regel wie im
  Changelog: Der Satz erzählt jedem, der eine ältere Fassung hat, wo der Hebel
  sitzt.
- **Keine Änderungszahlen und keine Messwerte.** Millisekunden und
  Dreieckszahlen gehören in den Changelog, nicht in eine Pressemail; sie
  verwirren mehr, als sie belegen (Robert, 22.09.2026).
- **Keine Testlizenzen.** Bis Ende Oktober läuft die Demo, kostenlos und
  vollständig. Jeder Entwurf sagt das und verweist darauf, statt etwas
  anzubieten, das es in dieser Phase gar nicht gibt.
- **Keine Ankündigung als Funktion.** Was noch nicht abgenommen ist, steht als
  Ausblick und heißt auch so.

## Was jeder Entwurf enthält

Seit der Überarbeitung vom 22.09.2026 tragen alle fünfundzwanzig dieselben
vier Dinge, je Empfänger anders formuliert:

1. **Was Solidon3D ist**, und zwar als Handlung statt als Kategorie: Bohrung
   anklicken, Maße stehen am Modell, 8 statt 6 tippen, die Senkung geht mit,
   Passung wählen, Prüfbericht lesen, Datei an den eigenen Slicer.
2. **Warum es das sonst nicht gibt**: Fusion nimmt eine STL an, aber die
   CAD-Werkzeuge greifen an Dreiecken nicht. Meshmixer und der 3D Builder sind
   eingestellt. Die Parametrisierer brauchen einen Autor, der den Parameter
   vorgesehen hat.
3. **Der Vorteil über die Neuerung hinaus**: Der Prüfbericht nennt den Grund,
   solange sich am Teil noch etwas ändern lässt, und eine Toleranz ist ein
   Verweis auf das Material statt einer Zahl, mit Profilen, die sich am
   eigenen Drucker kalibrieren lassen.
4. **Die Demo**, kostenlos und vollständig bis Ende Oktober, statt eines
   Lizenzangebots.

## Verteiler

Derselbe wie bei 0.3.3; die Adressprüfung von damals (29./31.08.2026) gilt
fort und ist **vor dem Versand erneut zu prüfen** — eine Redaktionsadresse
altert schneller als eine Software.

| # | Redaktion / Kanal | Adresse | Sprache | Aufhänger 0.5.0 |
|---:|---|---|---|---|
| 1 | 3Druck.com | `content@3druck.com` | Deutsch | Folge-Update: aus dem bearbeitbaren Merkmal ist der exakte Körper geworden |
| 2 | 3D-grenzenlos | `pressemitteilung@3d-grenzenlos.de` | Deutsch | ein Wabenmuster ist ein Merkmal, kein Flächenteppich |
| 3 | Make Magazin | `mail@make-magazin.de` | Deutsch | Werkstattversuch: Rändel entfernen, Muster neu setzen, Teil bleibt exakt |
| 4 | Golem.de | `press@golem.de` | Deutsch | keine Kernwahl mehr in der Oberfläche — Netz und exakter Körper tun dasselbe |
| 5 | t3n | `redaktion@t3n.de` | Deutsch | deutsches Indie-Projekt, Einmalkauf, offline, sechs Sprachen |
| 6 | Caschys Blog | `carsten.knobloch@gmail.com` | Deutsch | kurzes Update: STL rein, STEP raus, Maße direkt im Bild |
| 7 | All3DP | `editors@all3dp.com` | Englisch | Fünf-Minuten-Test: Muster entfernen und mit neuer Teilung setzen |
| 8 | Fabbaloo | `info@fabbaloo.com` | Englisch | Produktmeldung: exakte Flächen aus einem Netz, durchgehend |
| 9 | 3D Printing Industry | `info@3dprintingindustry.com` | Englisch | Merkmalsbearbeitung auf exakter Geometrie, ohne Konstruktionshistorie |
| 10 | 3DPrint.com | `info@3dprint.com` | Englisch | ein Muster als ein Objekt: Teilung, Zellbreite, Tiefe |
| 11 | VoxelMatters | `info@voxelmatters.com` | Englisch | Folge-Update: nur der konkrete Zuwachs seit dem Artikel |
| 12 | 3Dprinting.com | `service@3dprinting.com` | Englisch | Ergänzung zum Softwarevergleich: STEP-Rundreise ohne CAD |
| 13 | Hackaday | `tips@hackaday.com` | Englisch | technischer Tipp: ein Muster in der Abwicklung messen und neu zeichnen |
| 14 | Make: | `editor@make.co` | Englisch | Workshop: Knurling neu setzen, Gewinde mit Gegenstück |
| 15 | TCT Magazine | `laura.griffiths@rapidnews.com` | Englisch | Datenherkunft: gemessen, eingepasst oder aus dem Schritt |
| 16 | 3D ADEPT Media | `editor@3dadept.com` | Englisch | begrenzte Erkennung, begrenzte KI, lokal |
| 17 | All Things Additive | `editorial@allthingsadditive.com` | Englisch | exakter Körper bis zur materialbelegten 3MF |
| 18 | CNC Kitchen | `contact@cnckitchen.com` | Deutsch | Testidee: hält ein Gewinde mit erzeugtem Gegenstück im Druck? |
| 19 | Made with Layers | `im2404@toms3d.org` | Deutsch | Testidee: Rändel an einem heruntergeladenen Griff neu setzen |
| 20 | Maker's Muse | `sales@makersmuse.com` | Englisch | manueller Modelliertest, keine KI-Kampagne |
| 21 | 3Dnatives | `contact@3dnatives.com` | Englisch | sechs Sprachen, Oberfläche und Handbuch |
| 22 | Computerbase | `presse@computerbase.de` | Deutsch | Architektur: Einmalkauf, offline, zwei Geometriekerne unter einer Oberfläche |
| 23 | Drucktipps3D | `stephan@drucktipps3d.de` | Deutsch | Fünf-Minuten-Praxistest: Muster und Maße im Bild |
| 24 | OMG! Ubuntu | `contact@omgubuntu.co.uk` | Englisch | natives Linux: Flatpak und AppImage, offline, kein Konto |
| 25 | Italia 3D Print | `3dprint@tech-center.com` | Italienisch | interfaccia e manuale completamente in italiano |
