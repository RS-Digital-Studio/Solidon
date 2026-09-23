# Bericht: Reichweite YouTube und Facebook

Stand 23.09.2026. Auftrag von Robert vom selben Tag: YouTube und Facebook
weiter optimieren, Neues vorschlagen, bei Videos zuerst ein Text, Beiträge
sofort oder geplant. Eingeplant sind die drei freigegebenen Facebook-Beiträge
(24., 26. und 28.09., Meta Business Suite, je mit Bild, öffentlich, ohne
Bewerbung); sonst wurde nichts veröffentlicht und nichts angemeldet.

## Was hier liegt

| Datei | Inhalt |
|---|---|
| [`analyse-und-plan.md`](analyse-und-plan.md) | Zahlen und was sie bedeuten, belegte Empfehlungen der Plattformen, fehlende Kanäle, Plan bis 01.11. mit Takt, Uhrzeiten, Messpunkten, Roberts eigene Liste |
| [`youtube-optimierung.md`](youtube-optimierung.md) | vierzehn einzelne Änderungen in YouTube Studio mit fertigen Texten DE und EN |
| [`videos-konzept.md`](videos-konzept.md) | sieben Videos (V1 bis V7) zur Freigabe, Szene für Szene, mit ehrlicher Bewertung der synthetischen Stimme |
| `posts/*.md` | dreizehn Beiträge für 24.09. bis 07.10., je Datei Text, Bild, Link, Zeitpunkt, Begründung, Belege |
| `posts/bilder/*.png` | zwölf Beitragsbilder, 1080 × 1350 bzw. 1080 × 1080, jedes ein Ausschnitt in nativen Pixeln aus einer Vollbildaufnahme der Demo 0.4.4 (Bildstandard vom 23.09.2026) |
| `posts/bilder/capture_app.py` | nimmt das maximierte Solidon-Fenster auf dem 2560×1440-Schirm auf, ein Prozess je Motiv und Sprache, Oberfläche aus einem Export von `v0.4.4`, eigene Nutzerverzeichnisse; ruff-sauber |
| `posts/bilder/aufnahmen/` | die zwölf Vollbildaufnahmen (2560 × 1369) mit Beleg je Bild (Version, Schirm, Werte, Lage der Bereiche) |
| `posts/bilder/make_post_images.py` | schneidet die Beitragsbilder aus den Aufnahmen und setzt das Textband; ruff-sauber |

## Die Beiträge im Kalender

| Datum | Zeit | Kanal | Thema | Status |
|---|---|---|---|---|
| Do 24.09. | 19:00 | Facebook | Stift und Loch in einem Schritt | geplant |
| Fr 25.09. | 18:00 | YouTube | Umfrage „STL fast passend“ (EN) | nur falls YouTube Beiträge anbietet |
| Sa 26.09. | 10:00 | Facebook | Frage: welches Teil zuletzt geändert | geplant (letzter Satz hängt an V3, freigegeben) |
| So 27.09. | 11:00 | Instagram | Vorstellung und Profiltext | sobald das Konto existiert |
| Mo 28.09. | 19:00 | Facebook | Größere Schraube, Senkung geht mit | geplant |
| Di 29.09. | 18:00 | YouTube | Bild „Hole too small?“ (EN) | nur falls YouTube Beiträge anbietet |
| Mi 30.09. | 19:00 | Facebook | Warum es kein Konto gibt (Ein-Personen-Projekt) | bereit, besser mit Foto von Robert |
| Fr 02.10. | 19:00 | Facebook | Prüfbericht | bereit |
| Sa 03.10. | 18:00 | YouTube | Bild „Demo until 30 October“ (EN) | nur falls YouTube Beiträge anbietet |
| So 04.10. | 10:00 | Facebook | Demo bis 30. Oktober | bereit |
| Di 06.10. | 19:00 | Facebook | Loch → Langloch | bereit |
| Mi 07.10. | 19:00 | Facebook | GoFundMe | erst nach Kampagnenaktualisierung |
| Mi 07.10. | 19:00 | Facebook | Schraubdose (Ersatz) | falls GoFundMe noch nicht geht |

Jede Facebook-Datei enthält eine Instagram-Fassung. Planen lassen sich
Facebook und Instagram gemeinsam in der Meta Business Suite unter „Planer“.

## Die Bilder nach dem Bildstandard

Alle zwölf Beitragsbilder sind nach Roberts Vorgabe vom 23.09.2026 neu
aufgenommen: das ganze Solidon-Fenster maximiert auf dem 2560×1440-Schirm,
Stand der Demo 0.4.4, das Teil füllt die 3D-Ansicht, und das Bedienelement der
Handlung steht im selben Bild (Merkmalfenster mit dem neuen Durchmesser,
Dialog „Gegenstücke setzen“ mit Stift und Loch in der Vorschau, Prüfbericht,
Verlauf). Jedes Beitragsbild ist ein zusammenhängender Ausschnitt in nativen
Pixeln, nichts ist vergrößert. Den Demo-Countdown der Statuszeile deckt eine
Fußleiste ab, weil er den Tagesstand der Aufnahme zeigt und die Beiträge Tage
später erscheinen.

Für die drei freigegebenen Facebook-Beiträge:

| Beitrag | Bild | Instagram |
|---|---|---|
| 24.09., Gegenstücke | `posts/bilder/gegenstuecke-de-1080x1350.png` | `posts/bilder/gegenstuecke-en-1080x1080.png` |
| 26.09., Frage | `posts/bilder/frage-teil-anpassen-de-1080x1080.png` | dasselbe Bild |
| 28.09., Senkbohrung | `posts/bilder/bohrung-senkung-de-1080x1350.png` | `posts/bilder/bohrung-senkung-en-1080x1080.png` |

Zwei Dinge dazu. Die Gegenstücke im Bild sind 8 mm dick und 12 mm lang statt
6 und 8 wie im Tutorial, damit der Stift im Bild sichtbar ist; der Beitrag
nennt keine Zahlen. Und aufgenommen wird über `PrintWindow`, nicht vom
Bildschirm: Andere Sitzungen öffnen auf demselben Schirm eigene
Solidon-Fenster, und zwei frühe Bildschirmaufnahmen zeigten deren
Startbildschirm statt des eigenen Fensters. Der Beleg jeder Aufnahme nennt die
Abweichung zwischen beiden Wegen (alle unter 1 von 255).

Das Demo-Bild zeigt jetzt das Elektronikgehäuse mit seinen 24 Schritten statt
vier Galeriebildern; die Texte vom 27.09., 03.10. und 04.10. sind darauf
angepasst. Das Ersatzbild zum Beitrag vom 30.09. ist jetzt der Dialog
„Rückmeldung senden“, das zum GoFundMe-Beitrag der Unterstützungsdialog der App.

## Die wichtigsten Befunde in fünf Sätzen

98 % der YouTube-Aufrufe kommen aus Shorts, englische erreichen viermal so
viele Leute wie deutsche. Im Schnitt dauert ein Aufruf 3,6 Sekunden, also
wischen fast alle nach dem ersten Bild weiter; die Shorts beginnen mit einem
stehenden Titel oder einem kleinen Programmfenster. Die Langvideos zeigen das
Modell erst nach etwa 33 Sekunden, und ihre Beschreibungen in Studio sagen
noch „Vorschau, kann vom Download abweichen“. Community-Beiträge gibt es auf
YouTube in Deutschland laut YouTube-Hilfe derzeit gar nicht. Die Downloads
kamen bisher aus der Presse; die 0.5.0-Presseentwürfe sind deshalb der größte
Hebel vor dem 01.11.

## Womit Robert heute anfangen sollte

In dieser Reihenfolge, zusammen gut eine Stunde:

1. **Zwei-Faktor-Anmeldung** für das Google-Konto einschalten (5 min).
2. **In YouTube prüfen, ob „Erstellen → Beitrag erstellen“ erscheint** (1 min).
   Wenn nicht, entfallen die drei YouTube-Beiträge.
3. **Verknüpfte Videos der 22 Shorts** auf die eigenen Tutorials umstellen,
   Tabelle in `youtube-optimierung.md`, Punkt 1 (15 min). Das ist der einzige
   anklickbare Weg aus einem Short.
4. **Die Beiträge vom 24., 26. und 28.09. freigeben** und in der Business
   Suite planen (10 min).
5. **`videos-konzept.md` lesen** und mit einer Zeile freigeben, welche Videos
   entstehen sollen. Mein Vorschlag: V4 sofort (kostet keine neue Aufnahme
   und misst, ob der neue Schnitt wirkt), V1 diese Woche.

Morgen oder übermorgen: Vorspann der zehn Tutorials kürzen und die
Beschreibungen ersetzen (Punkte 2 und 3, etwa 50 min), Instagram anlegen.

## Offene Fragen an Robert

1. **YouTube-Beiträge:** Erscheint „Beitrag erstellen“?
2. **Standardsprache des Kanals:** Englisch mit deutscher Übersetzung, weil
   80 % der Aufrufe englisch sind, oder Deutsch?
3. **Stimme und Gesicht:** Einverstanden, dass Trailer, Release-Video und
   GoFundMe-Video mit deiner Stimme bzw. vor der Kamera entstehen? Sprichst du
   die englischen Fassungen selbst, oder Deutsch mit englischen Untertiteln?
4. **Preise:** Die Website sagt „Preis und Vertragsbedingungen werden vor ihrem
   Angebot veröffentlicht“. Wann stehen sie dort? Bis dahin nennt kein
   Beitrag einen Preis. Zur Sicherheit: Die Erinnerung
   `verkaufsphase-preise-und-demo-zahlen.md` sagt noch, einen 99-€-Tarif gebe
   es nicht; der Auftrag von heute nennt 69 € bis Ende Januar und danach 99 €.
   Die Erinnerung sollte nachgezogen werden, wenn der neue Stand gilt.
5. **Termin für 0.5.0:** Davon hängen Presseversand, V5 und die Wochen 42/43
   ab.
6. **Besenhalter-Video** mit dem sichtbaren Fehler bei 4:02: angepinnter
   Hinweis, „nicht gelistet“ oder so lassen? (`youtube-optimierung.md`,
   Punkt 14)
7. **Website-Dashboard:** Zeigt es, woher die Besucher kommen (Verweise,
   Länder)? Dann lässt sich messen, ob YouTube, Facebook oder Reddit
   überhaupt Downloads bringen.
8. **Gedruckte Teile:** Ist der Gartentor-Adapter aus der Drehanleitung
   gedruckt und montiert? Kannst du für die Reihe V3 einzelne Teile drucken
   und zwei Sekunden filmen?
9. **Designer anschreiben:** Einverstanden, dass für V3 die Designer der
   gezeigten Modelle um Erlaubnis gebeten werden (von deinem Konto)?
10. **Adressen:** Wie lautet die Adresse der Facebook-Seite, und soll
    Instagram „solidon3d“ heißen?
11. **Website:** Soll die Website auf YouTube und Facebook verlinken? Heute
    steht dort kein Kanal. Das wäre eine Änderung für eine andere Sitzung.
12. **Werbebudget:** Gibt es eines? Das Meta-Werbekonto hat eine
    fehlgeschlagene Zahlung. Dieser Plan kommt ohne Anzeigen aus.
13. **Facebook-Gruppen:** In welchen bist du schon Mitglied?

## Was ich nicht geprüft habe oder nicht prüfen konnte

- Die Regeln von r/3Dprinting und anderen Subreddits: Reddit sperrt den
  automatischen Abruf.
- Die MakerWorld-Richtlinien im Original: Die Seite blockt den Abruf; der
  zitierte Wortlaut stammt aus dem Suchergebnis.
- Die Reichweite der vier bisherigen Facebook-Textbeiträge: lag nicht vor.
- Die Zugangsschwelle für Instagram-Test-Reels: Instagram nennt sie im
  Artikel nicht, Dritte nennen unterschiedliche Zahlen.
- Ob GoFundMe die Herkunft einzelner Teilen-Links auswertet.
- Die in `analyse-und-plan.md` genannten Facebook-Gruppen: Namen aus einer
  Suche, Größe, Aktivität und Regeln ungeprüft.

## Quellen

Die Plattformquellen mit Abrufdatum stehen nummeriert am Ende von
[`analyse-und-plan.md`](analyse-und-plan.md). Dazu aus dem Repository:

- `README.md`, `website/index.html` (lokal) und die öffentliche Website
  solidon3d.de (heute gelesen: Download 0.4.4, keine Preise, 132 Operationen,
  16 Druckerprofile; die lokale Seite nennt schon 136 und 18, also den
  kommenden Stand, deshalb nennen die Beiträge keine dieser Zahlen)
- `changelog/de.md` (0.4.1 bis 0.5.0)
- `marketing/youtube/*.md`, `marketing/youtube/workshop-2026-09-copy.json`
- `marketing/video/workshop-2026-09/` (Zeitleisten, Uploadtexte, Standbilder,
  Kodierskript, Abnahmewerkzeug); eigene Kontaktabzüge aus drei Shorts und
  dem Anfang eines Tutorials mit ffmpeg
- `tools/make_video.py`, `tools/speak_chatterbox.py`,
  `tools/make_workshop_shorts.py` (Stimme, Layout der Shorts)
- `marketing/drehanleitung-video-1.md`, `marketing/presse-0.5.0/README.md`
- die öffentliche GoFundMe-Seite (heute: 51 € von 5 000 €, 3 Spender, nur
  Bilder, Text nennt noch 0.4.0 und 108 Operationen)
- Erinnerungen `nicht-nach-ki-klingen`, `aus-kundensicht-perfekt`,
  `verkaufsphase-preise-und-demo-zahlen`,
  `marktwert-zielgruppe-und-firmenvalidierung`,
  `solidon-ist-die-vorstufe-vor-dem-slicer`, `live-durchsicht-solidon3d-2026-08`,
  `verifikation-an-echten-modellen`
