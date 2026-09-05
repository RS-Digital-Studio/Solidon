# Konzept — eine zweite Hand an der Kamera

Stand 30.08.2026. **Entwurf und Messauftrag, keine Bau-Ansage** — Roberts
„wäre schon spannend" führt `ROADMAP.md` selbst ausdrücklich als Interesse.

**Nachtrag 05.09.2026.** Gebaut ist es seit dem 02.09.2026 (Windows, am
Gerät bestätigt). Der erste Mac-Bericht eines Kunden brachte die zweite
Bauart: Dort hält 3DxWare das Gerät exklusiv, rohes HID bleibt leer, und der
Weg führt durch das Framework des Treibers (`DriverReader`, Abschnitt 7,
Falle 2 und Abschnitt 10). Was offen ist, steht im Register von `ROADMAP.md`.

Anlass: Die Kundenanfrage aus dem Dentalbereich (R. W. D., 30.08.2026). Ein
Zahntechniker, der acht Stunden am Tag in exocad die linke Hand auf einer
SpaceMouse liegen hat, steckt sie in Solidon ein und drückt — und das Bild
steht still. Er will keine neue Funktion; er will, dass die Handbewegung, die
er nicht mehr denken muss, beim Programmwechsel nicht aufhört zu wirken.
**Wer kein Gerät hat, darf davon nichts merken** — das ist die ganze Sache.

Dieses Dokument beantwortet nicht, ob wir es bauen, sondern **was es wäre und
woran die Entscheidung hängt**. Zum Namen: Datei und Oberfläche sagen
„3D-Maus" — „SpaceMouse" ist ein Markenname; in der Oberfläche einmal
„3D-Maus (SpaceMouse)", danach nur noch „3D-Maus".

Bezug: Bauplan §2.9 (Navigation), §18 (Viewport), §31, §35, §36; P15 §4 E10;
AGENTS.md Regel 2 und 22. „§" meint den Bauplan.

---

## 1. Welcher der vier Wege — keiner, und das ist die Antwort

Die 3D-Maus gehört zu keinem Hauptweg aus §2.2, weil sie **unter** allen
vieren liegt: Sie fasst die Kamera an, und die Kamera teilen alle vier. Den
größten Nutzen hat sie in Weg 1 (man dreht das Teil, um die störende Stelle
zu finden — genau der Meshmixer-Nachfolge-Weg des Kunden) und Weg 4 (linke
Hand hält das Modell, rechte Hand malt). Es entsteht **keine Op, kein
Kernmodul, kein §9-Vertrag** — die Stelle ist der `Viewport`, und dort nur
die Kamera.

## 2. Die E10-Revision — welche Prämisse gefallen ist

P15 §4 E10 begründete die Ablehnung dreifach. Zwei Gründe stehen, einer ist
gefallen:

| Prämisse | Stand heute |
|---|---|
| „Nischengerät" | **steht** — und muss sich nicht ändern |
| „kleine Zielgruppe" | **steht der Zahl nach, nicht dem Gewicht nach:** Der erste Umsatz des Projekts (10 €, 30.08.2026) kam aus genau dieser Gruppe, mit der Ansage, Solidon Dentalkunden zu empfehlen. Ein Multiplikator ist keine Zahl — er erzeugt sie |
| „eigene Treiberprobleme je Plattform" | **gefallen, und nur diese:** E10 rechnete mit 3DxWare. Über rohes HID gibt es keinen Treiber mehr — aus der Treiberfrage ist eine **Rechtefrage** geworden (macOS-Eingabeüberwachung, Linux-udev), ein anderes Risiko mit anderen Gegenmitteln |

Der Satz, der die Revision trägt, ist nicht „es ist jetzt einfacher":

> **E10 fragte, wie viele das Gerät haben. Die richtige Frage ist, was es
> die kostet, die es nicht haben.** Ist die ehrliche Antwort null, ist
> „Nischengerät" kein Ablehnungsgrund mehr, sondern eine Größenangabe.

Der Ehrlichkeit halber daneben: P15 §1.1 führte SindriCADs
SpaceMouse-Unterstützung ausdrücklich unter „was wir nicht kopieren".
Umgestimmt hat nicht der Wettbewerber, sondern ein Kunde — der bessere
Anlass, und der einzige. Und E10 lehnte die Snapmaker-U1-Bindung ab, **weil
Robert das Gerät nicht hat** — für die SpaceMouse gilt derselbe Satz
wörtlich (Entscheidung 1).

## 3. Die Spannung: ein Profigerät für Kunden ohne CAD-Kenntnisse

Roberts Leitsatz ist der Maßstab, an dem der Vorschlag zuerst scheitern
kann. Die These, und sie hält: **Eine 3D-Maus ist kein CAD-Begriff, sondern
ein Gegenstand, den man schiebt.** Nichts zu lernen, nichts zu wählen, kein
Modus. Damit das keine Behauptung bleibt, fünf Auflagen:

1. **Kein Gerät, keine Spur.** Kein Menüeintrag, kein Umschalter, keine
   sichtbare Einstellungszeile, keine Meldung. Ohne Gerät ist die Anwendung
   Zeile für Zeile dieselbe.
2. **Gerät, und es geht — ohne Einrichtung.** Einstecken, schieben, das
   Bild folgt. Kein Freischalt-Häkchen, das man erst finden müsste.
3. **Es fährt die Kamera und sonst nichts.** Keine Operation, keine
   Auswahl, keine Geometrie — Regel 2 wird nicht berührt, weil nichts ins
   Dokument gelangt (Abnahme 8 beweist das).
4. **Die Maus behält alles.** Nichts ist nur mit dem Gerät erreichbar; die
   3D-Maus ist eine zweite Hand, nie die einzige.
5. **Es ist kein Modus.** Kein fünfter Eintrag unter *Ansicht → Navigation*
   — die vier Schemata beantworten „welche Maustaste dreht", und die Frage
   stellt sich hier nicht.

Gegen §35 gerechnet: Menüs +0, Menüzeilen +0, Werkzeugzeile +0 (sie ist mit
8/8 voll — der Platz existiert gar nicht), Dialogfelder +0. **Die einzige
Stelle, die wächst, ist der Einstellungsdialog** — eine selbstgesetzte
Grenze: **eine Zeile, nicht eine Gruppe** (Abschnitt 6).

Und eine Chance, als Hypothese gekennzeichnet: Was Slicer-Kunden am
CAD-Viewport am meisten stört, ist Orientierungsverlust. Eine 3D-Maus ist
stetig und in derselben Bewegung zurücknehmbar — sie hilft dem Anfänger
womöglich strukturell mehr als dem Profi. Belegen kann das nur ein Kunde
mit Gerät.

## 4. Umfang: Kamera ja, Objekt nein, eine Taste

**Nur Kamera**, vier Gründe absteigender Härte: (1) Ein stetiger 6DoF-Schub
am Objekt müsste eine aus Parametern reproduzierbare Op werden — möglich,
aber ein zweites Vorhaben mit eigener Undo-Semantik. (2) „Kamera oder
Objekt" wäre eine Betriebsart — steht wörtlich auf der Nicht-Liste. (3) Den
Weg gibt es schon (Direktzug, Transformleiste), und er wird gerade in neun
Paketen umgebaut — ein Parallelweg wäre die Doppelung aus
`konzept-varianten-zusammenlegen`. (4) Auch der Präzedenzfall (Abschnitt 5)
macht es nicht.

**Gerätetasten:** In Runde eins genau eine, fest verdrahtet — *Alles
einpassen* (häufigste Belegung, gebaute Handlung, kostet keine Oberfläche).
Eine Belegungstabelle wird nicht gebaut: Sie wäre ein zweites
`shortcut_schemes.py` für ein Gerät, das fast niemand hat, und Tasten auf
Operationen verstießen gegen Auflage 4.

## 5. Der Vergleichsmaßstab — gemessen, nicht erinnert

Aus der Erinnerung, **vor jeder Zusage nachzumessen** (beide Programme
liegen lokal, Notiz `slicer-lokal-zum-gegenmessen`): Fusion fährt die Kamera
über den Herstellertreiber; **PrusaSlicer hat einen eigenen HID-Leser ohne
Hersteller-SDK, mit Einstellungen nur bei angeschlossenem Gerät.** Falls
sich das bestätigt, gibt es den Präzedenzfall in genau dem Programm, aus dem
die Zielgruppe kommt — die Spannung aus Abschnitt 3 wäre nicht theoretisch
aufgelöst, sondern belegt. Cura/Orca/Bambu: vermutlich nichts.

## 6. Bauform

**Schichtgrenze:** Ein HID-Leser ist `app/ui`-Gebiet — eine Kamerastellung
steht in keiner Projektdatei und hat keinen §9-Vertrag. Neue Datei
`app/ui/spacemouse.py` (nicht an die 8 700 Zeilen `viewport.py` anbauen),
und sie zerfällt in zwei Teile: das **Lesen** (HID, Gerätetabelle, Rechte —
eine Klasse) und das **Abbilden** (sechs Achsen in [−1, 1] + Einstellungen +
dt → neue Kamerastellung — **reine Funktion auf Modulebene**, nach dem
Formvorbild `camera_for_plane`). In der Abbildung sitzt jeder künftige
Fehler (Achsen, Vorzeichen, Bezugssystem); sie kennt kein Qt, kein VTK, kein
HID und ist damit offscreen vollständig prüfbar — die Bedingung, nicht eine
Bequemlichkeit.

**Takt:** Ein `QTimer` im Hauptthread mit nicht blockierendem Lesen
(~60 Hz), kein Thread — kein `crashed`-Signal, keine Kamera aus dem falschen
Thread. **Zu messen, bevor das gilt:** dass das Lesen wirklich nicht
blockiert; sonst Thread mit den Auflagen aus `wartezeit.md`. Drei Zusagen
des Takts: Unter der Totzone wird nichts gerendert (kein Leerlauf-Rendern);
es stauen sich keine Bilder (nach dem Loslassen steht die Kamera, wo die
Hand aufhörte); gelesen wird nur, wenn das Fenster vorn ist.

**Einstellungen:** Eine aufklappbare Zeile in der Gruppe „Anwendung" mit
genau drei Feldern — An/Aus, **ein** Empfindlichkeitsregler, „Richtung
umkehren". Ausdrücklich nicht: drei getrennte Regler (der Kunde weiß nicht,
ob „Translation" das ist, was sich falsch anfühlt — das Verhältnis gehört
uns), keine Totzone-Zeile (Hardware-Tatsache, feste gemessene Konstante),
keine sechs Achsen-Häkchen. **Sichtbarkeitsfalle:** „nur bei erkanntem
Gerät" klingt richtig und hat zwei Löcher — wer das Gerät abzieht, findet
die Einstellung nicht wieder, und die Handbuch-Bildererzeugung sieht die
Zeile nie (auf der Baumaschine steckt kein Gerät). Vorschlag: Merker
`spacemouse_seen` — die Zeile erscheint ab dem ersten gesehenen Gerät und
bleibt (Entscheidung 6).

## 7. Der Kandidat und seine drei Fallen

`pyspacemouse` — MIT, rohes HID, kein 3DxWare. Alle Angaben aus der
Erinnerung, am installierten Paket nachzumessen.

**Falle 1, die teuerste — die Abhängigkeitskette:** `pyspacemouse` hängt an
`easyhid`, und das galt auf PyPI lange als veraltet (Anleitung empfahl einen
Git-Fork). **Eine Git-URL lässt sich nicht in `constraints.txt`
festschreiben** — damit wäre der Kandidat in dieser Form nicht baubar
(Checkliste neue Abhängigkeit, Leitprinzip 4). Drei Ausgänge in Prüffolge:
(1) aktuelles pyspacemouse zieht PyPI-`hidapi`/`hid` → gut; (2) nein →
eigener Leser über `hid` (der PrusaSlicer-Weg, ~200 Zeilen — Preis: die
Gerätetabelle gehört dann uns, für immer); (3) beides trägt nicht → E10
bleibt, ehrliche Absage an den Kunden. **Diese Messung kostet zehn Minuten
und kommt vor allem anderen.**

**Falle 2 — Plattformrechte:** Windows: lesbar; zu messen, ob ein
installiertes 3DxWare doppelt einspeist. macOS: Eingabeüberwachung nötig —
Regel 17 verlangt den Satz mit Weg und Knopf; **und die Erlaubnis hängt an
der Paketsignatur** — ohne stabile Signatur ist sie nach jedem Update weg.
Linux: `/dev/hidraw*` braucht eine udev-Regel, die weder AppImage noch
Flatpak installieren dürfen; das Flatpak bräuchte `--device=all` (breite
Berechtigung, sichtbar auf Flathub) **und** die udev-Regel trotzdem.
**Linux ist die schwächste Plattform dieses Vorschlags — das gehört gesagt
statt versprochen** (Entscheidung 7).

*Nachtrag 05.09.2026 zu macOS:* Das Hindernis ist ein anderes als die
Eingabeüberwachung. 3DxWare öffnet das Gerät auf dem Mac **exklusiv**, und
`hidapi` öffnet seinerseits exklusiv — wer den Treiber installiert hat (und
der Zahntechniker aus dem Anlass hat ihn, exocad braucht ihn), bekommt über
HID keinen Bericht. Der Kunde meldete genau das: „die Maus tut nichts". Der
Weg ist dort der, den Blender, FreeCAD und PrusaSlicer gehen: das
`3DconnexionClient`-Framework des installierten Treibers zur Laufzeit laden,
als Client mit Platzhalter anmelden und die Zustandsmeldungen lesen, die der
Treiber an das vorderste Programm richtet. `app/ui/spacemouse.py` tut das
in `DriverReader`; ohne Treiber bleibt HID. Am Gerät gemessen ist der
Mac-Weg nicht — die Rückmeldung des Kunden prüft ihn.

**Falle 3 — Gerätevielfalt:** Rund ein Dutzend Modelle in der Tabelle; was
nicht drinsteht, tut nichts. Der Kunde hat ein konkretes Gerät — **ihn
fragen kostet eine Mail**, das „Sie hören von mir" steht ohnehin an, und es
macht aus „etwa ein Dutzend" ein Ja oder Nein (Entscheidung 9).

## 8. Testbarkeit ohne Gerät

Vier Ebenen: (1) Die Abbildung ist eine reine Funktion — gewöhnliche Tests.
(2) Der Leser bekommt eine **Naht**, keine HID-Attrappe (die prüfte sich
selbst). (3) **Eine aufgezeichnete Lesung wird Korpusdatei**: eine Stunde am
echten Gerät, je Achse ein langsamer Schub, roh nach `tests/data/` — danach
sind Achsen, Vorzeichen und Totzone für immer ohne Gerät prüfbar (dieselbe
Idee wie der Referenzkorpus). (4) **Mutationsprobe:** Ein umgedrehtes
Vorzeichen muss genau einen Test rot machen. Nicht prüfbar bleibt, ob sich
die Schubrichtung richtig **anfühlt** — dafür braucht es das Gerät genau
einmal (Entscheidung 1).

## 9. Was es an anderer Stelle kostet

Auswertung, Op-Stack, Projektdatei, Steckbrief, Prüfbericht,
Agenten-Kontext: **null** — keine Op, kein Schema, die 39 Referenzanfragen
bewegen sich nicht (selten und erwähnenswert). Real: 6–10 Texte × 5
Kataloge; ein Handbuch-Absatz in sechs Sprachen samt der Sichtbarkeitsfalle
aus Abschnitt 6; Changelog (sechs Dateien); Lizenzliste + 
`THIRD-PARTY-NOTICES` + die `RUNTIME_EXTRAS`-Entscheidung; Paketierung
(`solidon3d.spec` binaries für die native hidapi, Flatpak-`finish-args`,
macOS-Signatur); Karten und Regeln (`app/ui/CLAUDE.md`, `ansicht.md`);
Website-Merkmalsliste **plus Gegensuche** nach Sätzen, die die Abwesenheit
versprechen („nur Maus und Tastatur" — gesucht wird die Verneinung, nicht
der Name der neuen Sache). §31 bekommt keine neue Zeile — die
Viewport-Navigation ist „im Tor nicht messbar"; stattdessen Handmessung:
Kosten je Takt im Leerlauf, Bildrate bei 1 Mio. Dreiecken.

## 10. Verworfene Alternativen

**3DxWare-SDK:** proprietär, je Plattform ein Installer, ein
Herstellertreiber als Voraussetzung in einem Programm mit der Zusage „ohne
Konto, ohne Netz" — die Freigabeliste hat dafür keine Zeile und soll keine
bekommen. *(Nachtrag 05.09.2026: Das gilt für das SDK als Abhängigkeit. Auf
dem Mac ist der Treiber des Kunden die einzige Tür zum Gerät, und Solidon
lädt sein Framework dort zur Laufzeit, wenn es da ist — mitgeliefert und
vorausgesetzt wird nichts, Abschnitt 7, Falle 2.)* **Objektmanipulation:**
Abschnitt 4. **Fünftes
Navigationsschema:** Kategorienfehler und Betriebsart. **Eigener HID-Leser
als erste Wahl:** bleibt der Rückfall (Falle 1), nicht die Vorgabe. **Gar
nicht bauen:** die ehrlichste Alternative, ausgesprochen statt versteckt —
die neun Pakete der Grundsteuerung (Registerzeile 135) bedienen 100 Prozent
der Kunden, die 3D-Maus einen Bruchteil eines Prozents; wenn es eine
Arbeitseinheit gibt, gehört sie den neun Paketen. Deshalb Entscheidung 2.

**Empfehlung, unter drei Bedingungen: bauen — nach der Grundsteuerung, mit
einem Gerät auf dem Tisch, und nur wenn die Abhängigkeit festschreibbar
ist.** Fällt eine der drei, bleibt E10 stehen, und der Kunde bekommt eine
begründete Absage statt einer Zusage, die niemand einlösen kann.

## 11. Abnahme (Stil §40)

1. Ohne Gerät ist die Anwendung Zeile für Zeile dieselbe;
   `test_interface_limits.py` bleibt unverändert grün.
2. Ohne installiertes Paket startet die Anwendung; kein Text, kein
   Protokolleintrag erwähnt es (die `brep.available()`-Zusage, übertragen).
3. Zwei Läufe derselben aufgezeichneten Lesung ergeben dieselbe
   Kamerafolge, Wert für Wert.
4. Jede der sechs Achsen bewegt, was ihr Name sagt — je Achse ein Test
   gegen die reine Abbildung; ein umgedrehtes Vorzeichen macht genau diesen
   Test rot (Gegenprobe protokolliert).
5. Ein Zug während laufender Auswertung staut keine Bilder — gemessen an
   1 Mio. Dreiecken im echten Fenster, nicht offscreen.
6. Abziehen unter Last bricht nichts; Wiedereinstecken wirkt ohne Neustart.
7. Jede Plattform beantwortet ihre Rechtefrage, bevor der Kunde sie stellt
   — mit Satz, Weg und anklickbarer Handlung, nie „fehlgeschlagen".
8. 500 abgespielte Lesungen erzeugen keinen Verlaufsschritt, keine
   Formatänderung, keinen Befund.
9. **Der Kunde sagt an seinem eigenen Gerät: Es fühlt sich an wie in
   exocad** — die einzige Abnahme, die wirklich zählt, und die einzige, die
   man nicht selbst herstellen kann.

## 12. Offene Entscheidungen für Robert

1. **Gerät kaufen — oder nicht bauen?** (~150 € für eine Compact.) Ohne
   Gerät gibt es kein „fertig", nur „gebaut, Bestätigung offen" — und E10
   lehnte die U1-Bindung mit genau diesem Argument ab.
2. **Reihenfolge:** vor oder nach den neun Grundsteuerungs-Paketen? Die
   bedienen alle Kunden.
3. **Mitliefern oder nachinstallieren?** Empfehlung: mitliefern — ein
   Navigationsmerkmal hinter einer Installationshürde ist keines.
4. **Bibliothek oder eigener Leser?** Hängt an der Zehn-Minuten-Messung
   (Falle 1); wenn beides geht: Bibliothek.
5. **Ein Empfindlichkeitsregler oder drei?** Empfehlung: einer.
6. **Einstellungszeile nur bei erkanntem Gerät oder ab dem ersten
   dauerhaft?** Betrifft auch die Handbuch-Bilder.
7. **Linux:** `--device=all` hinnehmen — oder Linux ausdrücklich ausnehmen
   und es sagen?
8. **Gerätetasten:** eine fest auf *Alles einpassen* — oder erst gar keine?
9. **Den Kunden vorab nach seinem Modell fragen?** Kostet eine Mail, die
   ohnehin zugesagt ist.
10. **Skizzenmodus:** Dreht das Gerät aus der Zeichenebene heraus oder
    schiebt und zoomt es nur in ihr? (An `_sketch_frame` zu klären.)

## 13. Folgen für Bauplan, P15 und Roadmap (nur benannt)

§2.9: die 3D-Maus als zweite Hand an derselben Kamera — kein fünftes
Schema, kein Modus. §18: ein Satz, dass die Kamera einen zweiten Treiber
hat, der keine Op erzeugt (ausdrücklich nicht §18.11 — dort erzeugt jede
Manipulation eine). §35: Entscheidung, ob „Eingabegeräte" eine eigene
Testart-Zeile wird (aufgezeichnete Lesungen statt Gerät). §36: die
HID-Bibliothek. P15: §3 Zeile 294 bekommt eine datierte Fußnote (der Satz
bleibt — er war zu seinem Stichtag richtig); §4 E10 nimmt den
SpaceMouse-Spiegelstrich mit Angabe der gefallenen Prämisse zurück, keine
stille Streichung; §8 streicht „SpaceMouse und" vor der U1-Bindung.
`ansicht.md`: die Regel vom zweiten Kameratreiber und der reinen Abbildung.
`ROADMAP.md`: Registerzeile 130 bekommt ihre Antwort. `konzepte/README.md`:
neue Zeile.
