# Videos bis zum Verkaufsstart: was entstehen soll

Stand 23.09.2026. **Das ist der Text vor der Produktion.** Es wird nichts
aufgenommen, bevor Robert die einzelnen Videos freigegeben hat. Jedes Video
hat eine Kennung (V1 bis V7); eine Freigabe genügt als Zeile „V1 ja, V3
nein“.

Die Zahlen, aus denen die Reihenfolge folgt, stehen in
[`analyse-und-plan.md`](analyse-und-plan.md). Kurz: Englische Shorts
erreichen viermal so viele Leute wie deutsche, und fast jeder Aufruf endet
nach rund 3,6 Sekunden. Die Filme verlieren die Leute im ersten Bild.

---

## 1. Wie die bisherigen Filme entstanden sind

| Teil | Weg | Werkzeug |
|---|---|---|
| Aufnahme | Die echte Anwendung wird ferngesteuert: echte Dateidialoge, echte Klicks, echte Eingabefelder, isolierte Nutzerverzeichnisse, ein Prozess je Thema und Sprache. Jede Einstellung wird gegen den Modellzustand geprüft. | `tools/make_workshop_videos.py`, `tools/make_longform_video.py`, `tools/make_video.py` |
| Shorts | aus denselben Aufnahmen hochkant geschnitten, Texte an belegte App-Zustände gebunden | `tools/make_workshop_shorts.py` mit `short_shots.json` |
| Text | Einblendungen im Bild, Titel oben, Detail darunter; keine Sprache | Schnittpläne `*.timeline.json` |
| Ton | lokal erzeugte Musik, je Film ein eigenes Stück | `_write_longform_music` in `make_longform_video.py` |
| Stimme | **keine**, mit einer Ausnahme (unten) | |
| Kodierung | ffmpeg, 1080p, gedrosselt auf vier Kerne | `marketing/video/workshop-2026-09/run_encodes.ps1` |
| Abnahme | Bildgröße, Bildrate, Tonspur, Dauer, Geometriebelege, Uploadtexte mit Kapiteln | `marketing/video/workshop-2026-09/verify_production.py` |

**Die Ausnahme:** Das Vorstellungsvideo vom 09.08.2026
(`marketing/video/solidon3d-de-quer-1080p.mp4` und die Hochkant- und
EN-Fassungen) ist mit einer synthetischen Stimme vertont: Chatterbox, ein
künstlicher Sprecher mit festem Startwert 1234, ausgewählt aus acht
Kandidaten (`tools/speak_chatterbox.py`, Tonproben in `marketing/tonproben/`).
Es ist nicht Roberts Stimme. Chatterbox setzt ein unhörbares Wasserzeichen,
das die Stimme maschinell als synthetisch erkennbar macht. Für die
Merkmals-Shorts wurde die Stimme danach bewusst weggelassen; im Quelltext
steht als Begründung: „Eine künstliche Stimme, die als solche auffällt,
schwächt ausgerechnet einen Beweisfilm.“

## 2. Kostet eine synthetische Stimme Vertrauen?

Ehrlich: **ja, bei Solidon mehr als bei den meisten Produkten.**

- Die Website verkauft ausdrücklich eine Person: „Es antwortet ein Mensch“,
  „Kein Team“, „Eine Person: Robert Schneider“. Eine künstliche Stimme sagt
  das Gegenteil, bevor der erste Satz zu Ende ist.
- Die Stimme ist als synthetisch erkennbar; das Team hat das beim Hören
  selbst festgestellt. Wer sie erkennt, fragt sich als Nächstes, was in dem
  Film sonst noch nicht echt ist. Bei einem Werkzeug, dessen Kern „Geometrie
  rechnet Code, nie das Modell“ ist, ist das der falsche Gedanke.
- Rechtlich ist die Lage auf YouTube nicht eindeutig: Das Klonen der eigenen
  Stimme muss nicht gekennzeichnet werden, realistische Inhalte, die täuschen
  könnten, schon; eine fremde synthetische Erzählerstimme ist in den
  Beispielen nicht genannt. Im Zweifel würde ich kennzeichnen, und dann steht
  unter dem Video „künstlich erzeugt“.
- Was eine synthetische Stimme kann: sechs Sprachen ohne Aufwand, immer
  gleicher Klang. Das zählt bei Tutorials, nicht beim ersten Eindruck.

**Empfehlung:**

- **Roberts eigene Stimme** für den Kanaltrailer (V1), das Release-Video (V5)
  und den Start (V6). **Roberts Gesicht** für das GoFundMe-Video (V2) und
  zehn Sekunden am Ende von V1. Ein fränkischer oder deutscher Akzent im
  Englischen schadet nicht, er passt zu „ein Mann in Bamberg baut das“.
- **Keine Stimme, nur Text und Musik** für die Shorts. Das ist heute schon so
  und bleibt so, weil ein Short in 20 Sekunden mit Bild und großer Schrift
  auskommt und so in jeder Sprache gleich funktioniert.
- **Keine synthetische Stimme mehr** in veröffentlichten Filmen.
- Spricht Robert kein Englisch vor der Kamera: Deutsch sprechen, englische
  Untertitel, und im englischen Trailer Text statt Stimme. Das ist eine offene
  Frage an ihn.

## 3. Was sich an allen neuen Shorts ändert

Gilt für V3, V4 und alle Shorts danach. Grund sind die 3,6 Sekunden.

1. **Das erste Bild zeigt das Ergebnis in Bewegung.** Kein Titelkarton,
   keine sechs Sekunden Text. Die Kamera fährt um das fertige Teil, oder die
   Zahl im Feld ändert sich und das Loch wächst mit.
2. **Das Modell füllt das Bild.** Nicht ein kleines Programmfenster mit
   Detailansicht darunter, sondern die 3D-Ansicht bildfüllend, die Zahl, um
   die es geht, groß daneben.
3. **Oben höchstens fünf Wörter**, mindestens 64 px hoch, Problem oder
   Ergebnis: „Screw doesn't fit?“, „Round hole → slot“.
4. **Kein Versionshinweis im Bild.** Die Version steht in der Beschreibung.
5. **Vorher kurz, nachher lang.** Vorher höchstens zwei Sekunden, dann der
   Weg in echter Geschwindigkeit oder sichtbar beschleunigt, dann das
   Ergebnis von nah.
6. **Am Ende ein Satz auf das verknüpfte Video**: „Full tutorial: link
   below“, weil Links in Shorts nicht anklickbar sind, das verknüpfte Video
   aber schon.
7. **20 bis 30 Sekunden**, nicht länger.
8. **Englisch zuerst.** Die deutsche Fassung geht auf Facebook und Instagram
   und einmal pro Woche auf YouTube.

**Technisch:** Das braucht ein neues Layout in `tools/make_workshop_shorts.py`
(heute: Kicker „SOLIDON3D · PREVIEW 0.4.1“, kleine Szene oben, Detailansicht
unten, Fortschrittsbalken). Neu: Viewport bildfüllend aus der Aufnahme
geschnitten, Text oben, Ergebnis zuerst. Für eine scharfe Hochkant-Fassung
wird mit 2560 × 1440 aufgenommen und der Viewport quadratisch
ausgeschnitten, statt eine 1920er Aufnahme hochzuskalieren. Die Änderung am
Werkzeug gehört in eine eigene Sitzung (`tools/`), nicht in diese.

---

## 4. Die Videos

Reihenfolge nach Nutzen und Abhängigkeit: V4 zuerst (schnell, misst die
Annahme), dann V1, V2 nach der Kampagnenaktualisierung, V3 nach Klärung der
Lizenzen, V5 zum Release, V6 zum Start.

### V4 — Drei vorhandene Themen neu geschnitten (Test)

| | |
|---|---|
| Ziel | Messen, ob der neue Schnitt (Abschnitt 3) mehr Leute hält als der alte, bei gleichem Inhalt |
| Format | Short, 9:16, 20 bis 25 s |
| Sprache | EN; DE danach nur für Facebook und Instagram |
| Themen | `langloch`, `bohrung-anpassen`, `stl-kanten` |
| Stimme | keine, Text und Musik |
| Neue Aufnahme | nein, aus den vorhandenen Aufnahmen in `marketing/video/workshop-2026-09/` |

Aufbau am Beispiel Langloch:

| Zeit | Bild | Text oben |
|---|---|---|
| 0,0–1,5 s | Nahaufnahme, Kamera fährt um das fertige Langloch (`shots/slot.png` bzw. die Kamerafahrt aus der Aufnahme) | Round hole → slot |
| 1,5–3,0 s | dieselbe Stelle vorher, rundes Loch | The STL only has a round hole |
| 3–12 s | Loch anklicken, rechts Länge 20 eintippen, Richtung 0°, Übernehmen (echte Aufnahme, sichtbar beschleunigt) | Click. Type 20 mm. Apply. |
| 12–18 s | Ergebnis nah, Länge im Feld auf 28 geändert | Change it later: 28 mm |
| 18–22 s | Teil ganz, langsame Drehung | Full tutorial: link below |

Bohrung: Einstieg mit dem 9-mm-Loch, dann 6 mm vorher. Kanten: Einstieg mit
der gerundeten Ecke in Drehung, dann die scharfe Ecke.

Nach sechs Tagen wird „Angesehen vs. weggewischt“ der drei neuen gegen die
drei alten Shorts desselben Themas verglichen.

### V1 — „Solidon3D in einer Minute“ (Kanaltrailer)

| | |
|---|---|
| Ziel | Wer auf den Kanal kommt, versteht in einer Minute, wofür Solidon ist, und sieht, wer dahintersteht |
| Format | 16:9, 55–60 s (Trailer); daraus 9:16, 30 s für Shorts, Reels und Instagram |
| Sprache | DE und EN getrennt |
| Stimme | Robert, im Off; die letzten zehn Sekunden Robert im Bild |
| Gezeigt | nur Funktionen aus 0.4.4, aus Beispielprojekten, die mit der Demo ausgeliefert werden |

| Zeit | Bild | Robert sagt (DE) |
|---|---|---|
| 0–4 s | Eine Bohrung wächst in der Vorschau, groß im Bild; Text „Loch zu klein?“ | „Das Modell ist heruntergeladen, und die Schraube passt nicht.“ |
| 4–14 s | Bohrung anklicken, rechts Durchmesser eintragen, Übernehmen | „In Solidon3D klicke ich die Bohrung an und tippe den neuen Durchmesser ein. Neu zeichnen muss ich nichts.“ |
| 14–24 s | Prüfbericht mit einem echten Befund, Klick darauf zeigt die Stelle | „Bevor es an den Drucker geht, zeigt mir der Prüfbericht, was schiefgehen würde.“ |
| 24–34 s | Automatisch teilen an `aushoehlen-und-teilen.p3d`: Schnitt, Passstifte, Explosionsansicht | „Zu groß fürs Bett? Dann teilt Solidon3D das Teil und setzt die Passstifte gleich mit.“ |
| 34–44 s | Rollenhalter aus `weg2`: Parameter Rollenbreite von 55 auf 90 mm, das Teil folgt | „Wer selbst baut, ändert eine Zahl, und das ganze Teil rechnet sich neu.“ |
| 44–50 s | Knopf „An den Slicer übergeben“ | „Am Ende geht die Datei an deinen Slicer.“ |
| 50–60 s | Robert am Schreibtisch, Endkarte mit solidon3d.de | „Ich bin Robert und baue Solidon3D allein in Bamberg. Die Demo ist bis zum 30. Oktober kostenlos, der Link steht unten.“ |

EN, gleiche Bilder:

> You downloaded a model, and the screw doesn't fit. In Solidon3D I click the
> hole and type the new diameter. No redrawing. Before it goes to the
> printer, the report shows me what would go wrong. Too big for your bed?
> Solidon3D splits the part and adds the pins. If you build your own, you
> change one number and the whole part follows. Then the file goes to your
> slicer. I'm Robert, and I build Solidon3D on my own in Bamberg, Germany.
> The demo is free until 30 October. The link is below.

Der Satz zum Prüfbericht wird nach der Aufnahme an den tatsächlich gezeigten
Befund angepasst. Ab dem 01.11. wird nur die letzte Szene neu gesprochen.

**Technisch:** Aufnahme über den vorhandenen Recorder wie bei den
Werkstattfilmen, Szenen an Beispielprojekten. Die Stimme nimmt Robert Satz
für Satz auf (eine WAV je Szene, Telefon oder USB-Mikrofon, ruhiger Raum).
`tools/make_video.py` richtet die Szenenlänge schon heute nach der Länge des
gesprochenen Satzes; es braucht nur einen Schalter, der aufgenommene Dateien
statt Chatterbox einliest (kleine Änderung in `tools/`, eigene Sitzung). Die
Untertitel-SRT entsteht dabei mit. Robert im Bild: zehn Sekunden mit dem
Telefon, gleiche Anleitung wie bei V2.

**Roberts Aufwand:** etwa 20 Minuten für die Sprachaufnahme, 10 Minuten für
das Schlussbild.

### V2 — Robert für die GoFundMe-Kampagne

| | |
|---|---|
| Ziel | Der Kampagne ein Gesicht geben. Die Seite hat heute nur Bilder; GoFundMe empfiehlt ein Video, 20 Sekunden bis drei Minuten. |
| Format | 16:9, 60–90 s, als YouTube-Video (öffentlich oder nicht gelistet), in der Kampagne als Hauptvideo eingebunden |
| Sprache | Deutsch gesprochen, englische und deutsche Untertitel |
| Stimme | Robert, vor der Kamera |
| Abhängigkeit | Der neue Kampagnentext aus `marketing/gofundme/` muss stehen; die Zahlen im Video kommen aus diesem Text, nicht von hier |

**Stichpunkte statt Skript** (GoFundMe rät zu vorbereiteten Stichpunkten;
abgelesen klingt es abgelesen):

1. Wer ich bin: Robert Schneider aus Bamberg, ich baue Solidon3D allein.
2. Was es macht, in einem Satz und mit einem Teil in der Hand: ein Programm
   für alle, die drucken und kein CAD können; heruntergeladenes Modell
   öffnen, Loch anklicken, neues Maß, fertig.
3. Warum ich das mache: eine eigene Geschichte, zum Beispiel das Teil, das
   nicht gepasst hat. Nur, was wirklich passiert ist.
4. Wo es steht: Demo seit August kostenlos, bis 30. Oktober; Version 1.0 ist
   für den 1. November geplant.
5. Wofür das Geld ist: die Punkte aus dem neuen Kampagnentext, z. B.
   Signierung, damit Windows nicht mehr warnt, Testgeräte, laufende Kosten.
6. Ehrlich dazu: Es gibt dafür nichts, keine Freischaltung, keine
   Anrechnung. Wer nicht spenden kann: die Demo ausprobieren, mir schreiben,
   was fehlt, oder die Kampagne teilen.
7. Danke.

**So nimmt Robert es mit wenig Aufwand auf:**

- Telefon **quer**, auf Augenhöhe, auf einem Bücherstapel oder Stativ,
  ein bis anderthalb Meter Abstand.
- **Licht von vorn**: vor ein Fenster setzen, nicht mit dem Rücken zum
  Fenster. Keine direkte Sonne im Gesicht.
- **Ruhiger Raum**, Fenster zu, Waschmaschine aus. Wenn vorhanden, ein
  Ansteckmikrofon oder das Headset-Kabelmikrofon; sonst das Telefon näher
  heran.
- Hintergrund: der Arbeitsplatz oder der Drucker, aufgeräumt genug.
- Zehn Sekunden Probe aufnehmen und **mit Kopfhörer anhören**.
- Drei, vier Durchgänge, die Stichpunkte auf einem Zettel hinter dem
  Telefon. Versprecher sind in Ordnung.
- Die Dateien in einen Ordner legen; Schnitt, Untertitel, Einblendung
  „Robert Schneider, Solidon3D“, zwei bis drei kurze Szenen aus der App und
  die Endkarte mit dem Kampagnenlink mache ich.

GoFundMe nimmt nur normale YouTube-Links, keine Shorts-Links.

**Roberts Aufwand:** 30 Minuten.

### V3 — „Downloaded and adjusted“: Shorts mit echten heruntergeladenen Modellen

| | |
|---|---|
| Ziel | Zeigen, dass Solidon mit echten Modellen aus dem Netz funktioniert, nicht nur mit eigenen Platten; die Zielgruppe erkennt ihre eigenen Downloads wieder |
| Format | Shorts, 9:16, 20–30 s, fünf Folgen, neuer Schnitt nach Abschnitt 3 |
| Sprache | EN zuerst, DE für Facebook und Instagram |
| Stimme | keine |
| Abhängigkeit | Lizenz oder Erlaubnis je Modell, Probelauf jeder Folge in der echten App vor der Aufnahme |

**Lizenzen, bevor irgendetwas aufgenommen wird.** Ein Werbefilm für ein
verkauftes Programm ist eine kommerzielle Nutzung, und das Ändern eines
Modells ist eine Bearbeitung. Deshalb:

| Lizenz | verwendbar? |
|---|---|
| CC0 | ja |
| CC BY 4.0 | ja, mit Namensnennung im Bild und in der Beschreibung |
| CC BY-SA 4.0 | ja mit Namensnennung; die geänderte Datei nur unter derselben Lizenz weitergeben |
| alles mit NC (nicht kommerziell) | nein, außer mit schriftlicher Erlaubnis |
| alles mit ND (keine Bearbeitung) | nein |
| MakerWorld „Standard Digital File License“ | nein: nur privater Druck, keine abgeleiteten Werke, keine Weitergabe |
| ohne Lizenzangabe („alle Rechte vorbehalten“) | nein, außer mit Erlaubnis |

Dazu: **Den Designer immer anschreiben**, auch bei CC BY. Das ist höflich,
und ein Designer, der gefragt wurde, teilt den Film eher. Das Modell nie als
schlecht darstellen: „Ich habe es für meine M4-Schrauben angepasst“, nicht
„Ich habe seinen Fehler behoben“. Das frühere Beispiel
`broomholdervcd_d35mm.stl` wurde wegen seiner nicht-kommerziellen Lizenz
schon einmal aussortiert; die Modelle in `F:\3D Dateien` stammen zum großen
Teil von MakerWorld und brauchen jedes einzeln eine Prüfung.

Folgen (jede nur, wenn sie am gewählten Modell in der App wirklich
durchläuft):

| Folge | Text oben (EN) | Was passiert |
|---|---|---|
| 1 | This bracket wants M3. I have M4. | Bohrung anklicken, neuer Durchmesser, Senkung mitnehmen |
| 2 | The mount needs to slide | rundes Loch → Langloch |
| 3 | Too big for my bed | Automatisch teilen mit Passstiften |
| 4 | Two parts, one pin | Gegenstücke an einem zweiteiligen Modell |
| 5 | Before the print fails | Prüfbericht und Orientierungssuche an einem Modell mit Überhängen |

Aufbau je Folge: 0–1,5 s fertiges Teil in Bewegung mit der Zahl, um die es
geht; 1,5–4 s der Anlass in einem Satz; 4–18 s der Weg; 18–24 s Ergebnis nah;
am Ende Designername, Lizenz und „Full tutorial: link below“. Wenn Robert das
Teil druckt: zwei Sekunden das gedruckte Teil in der Hand, mit der Schraube,
die jetzt passt. Das ist der stärkste Beweis, den ein Short haben kann.

**Technisch:** Aufnahme mit `tools/make_workshop_videos.py` über echte
Dateidialoge aus einem Quellordner mit den heruntergeladenen Dateien, Schnitt
mit dem neuen Layout. Lizenz und Herkunft jeder Datei werden neben der
Aufnahme festgehalten (wie bisher in `ASSET-RIGHTS.toml` für die Website).

**Roberts Aufwand:** Modelle mit auswählen, Designer anschreiben, optional
drucken und zwei Sekunden filmen.

### V5 — Solidon3D 0.5.0 (zum Release)

| | |
|---|---|
| Ziel | Die Pressewelle zu 0.5.0 bekommt einen Film, auf den jede Mail verlinken kann; Käufer sehen vor dem 01.11., was neu ist |
| Format | 16:9, 90–120 s, dazu drei Shorts |
| Sprache | DE und EN |
| Stimme | Robert im Off |
| Abhängigkeit | 0.5.0 veröffentlicht, RM-188 abgeschlossen; nur, was zum Release abgenommen ist (Bedingungen wie in `marketing/presse-0.5.0/README.md`) |

Inhalt nach der Geschichte der Pressemappe, in dieser Reihenfolge:

1. **Muster als ein Merkmal**, das bildstärkste: ein Wabenmuster oder Rändel
   steht im Baum als ein Muster; ein Klick entfernt es, drei Zahlen setzen es
   neu. Modell mit Lizenz nach V3 oder ein eigenes.
2. **Maße im Bild**: Bohrung anklicken, Abstände zu den Kanten stehen am
   Modell, Zahl tippen.
3. **STEP rein und raus**, exakte Körper, ohne Kernwahl.
4. **Merkbar schneller**, ohne Millisekunden: dasselbe große Modell drehen,
   vorher und nachher nebeneinander nur, wenn beide Aufnahmen echt sind.
5. Resin-Drucker in einem Satz.

Shorts: (a) Muster entfernen und neu setzen, (b) Maße im Bild, (c) STL rein,
STEP raus.

### V6 — Start am 01.11.2026

| | |
|---|---|
| Ziel | Der Verkaufsstart in allen Kanälen um 10:00 |
| Format | Short und Reel, 9:16, 15–20 s; dieselbe Aufnahme zusätzlich 16:9 für die Facebook-Seite |
| Sprache | DE und EN |
| Stimme | Robert im Bild |
| Abhängigkeit | Preise auf der Website veröffentlicht, Kauf funktioniert |

Robert, fünf Sekunden: „Die Demo ist vorbei, Solidon3D 1.0 ist da.“ Dann
drei Szenen aus V1, dann Preis und Link, so wie sie auf der Website stehen.

### V7 — Ein gedrucktes Teil, das ein echtes Problem löst (optional)

Die Drehanleitung für den Gartentor-Adapter liegt seit August in
`marketing/drehanleitung-video-1.md`: zwanzig Minuten mit dem Telefon, Tor
mit Kette, Spalt, Prüfstück, Adapter, Einrasten mit Ton. Sie hängt an zwei
offenen Fragen dort (ist der Adapter gedruckt und montiert, hängt die Kette
noch). Wenn ja, ist das der beste Einstieg für einen Short überhaupt, weil
das Problem in der ersten Sekunde ohne Text verständlich ist. Wenn nein,
gilt die Alternative aus der Anleitung (Pool-Filterball-Einsatz, Glasdeckel).

---

## 5. Zeitplan, falls alles freigegeben wird

| Woche | Video |
|---|---|
| KW 40 (28.09.–04.10.) | V4 (drei Shorts, EN), Werkzeugänderung für den neuen Schnitt; V1 aufnehmen |
| KW 41 (05.–11.10.) | V1 veröffentlichen und als Trailer setzen; V2 nach dem Kampagnentext; erste zwei Folgen V3 |
| KW 42 (12.–18.10.) | V5 zum Release (Termin offen); weitere V3-Folgen |
| KW 43–44 | restliche V3-Folgen; V6 vorbereiten; am 01.11. V6 |

Jede Veröffentlichung einzeln nach Roberts Freigabe.
