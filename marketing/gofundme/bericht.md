# Bericht: GoFundMe-Kampagne Solidon3D überarbeiten

Auftrag Robert, 23.09.2026: Kampagnenseite und Spenden optimieren, bis jetzt
kaum Spenden. Dieser Bericht wird nach jedem Arbeitsschritt fortgeschrieben.
Er hält Quellen, Zahlen mit Beleg, Entscheidungen mit Begründung und die
offenen Fragen an Robert fest.

Eingestellt wird alles von Robert selbst. In diesem Ordner wurde nichts
veröffentlicht, nichts gesendet und kein Konto benutzt.

---

## 1. Ausgangslage (öffentlich gelesen am 23.09.2026)

Kampagne: <https://www.gofundme.com/f/solidon3d-stl-anpassen-ohne-cad-bis-version-10>
(Kurzlink in App und Website: `https://gofund.me/08c5f0edb`, `app/branding.py`).

| Feld | Stand 23.09.2026 | Quelle |
|---|---|---|
| Titel | „Solidon3D: STL anpassen ohne CAD – bis Version 1.0“ (50 Zeichen) | Seite, `<title>` |
| Ziel / gesammelt | 5.000 € / 51 €, Fortschrittsring zeigt 2 % (mobil 0 %) | Seite |
| Spenden | 3 Eingänge (26 €, 20 €, 5 €), alle vom 14.09. | Seite |
| Erstellt | 13.09.2026, Kategorie „Unternehmen“, Ort Bamberg | Seite |
| Medien | 3 (Titelbild und zwei weitere), kein Video | Seite, `alt`-Texte „1 von 3“ |
| Updates | keine | Seite |
| Text | rund 4.500 Zeichen, ohne jede Formatierung | DOM der Seite (`innerText`) |

Robert sprach von zwei Spenden (Zahntechniker und ein Freund); GoFundMe führt
drei Eingänge. Für die Arbeit hier ändert das nichts.

### Was an der Seite messbar schiefläuft

1. **Der Text kommt ohne Formatierung an.** Im DOM stehen nur `<div>`-Zeilen
   und `<br>`, kein einziges `<b>`. Die Zwischenüberschriften („Was
   Solidon3D ist“, „Wofür das Geld ist“) sehen aus wie normaler Text. Die
   Aufzählungspunkte sind getippte `•`.
2. **Der erste Absatz ist der Teilen-Text, und er ist leer an Inhalt.**
   GoFundMe setzt `og:description` und `description` aus dem ersten Absatz
   der Geschichte plus „… Robert Schneider braucht deine Unterstützung für
   <Titel>“ zusammen (gemessen an den Meta-Tags der Seite). Heute steht dort
   nur der Satz „Das Loch ist 0,2 mm zu klein, und ich habe kein CAD.“ Wer
   den Link in WhatsApp oder Facebook sieht, erfährt nicht, wer um was bittet.
3. **Das Titelbild wird auf jedem Gerät anders beschnitten.** Gemessen am
   23.09.2026:
   - Desktop (ab 1024 px Breite): GoFundMe liefert eine 720×405-Fassung und
     zeigt sie mit `object-fit: cover` in einem Rahmen von 605×423 Punkten.
     Sichtbar sind rund 80 % der Breite.
   - Telefon (375 px): GoFundMe liefert eine 1200×900-Fassung (4:3) und zeigt
     sie in 375×478 Punkten. Sichtbar sind nur **rund 44 % der Breite** des
     Originals, mittig. Darüber liegen oben links der Name des Organisators,
     ab etwa 60 % Höhe das Etikett, der Titel in Weiß und die Punkte der
     Bildreihe.
   - Weitere erzeugte Zuschnitte: 1200×800, 720×480, 640×480 und 960×960.
     Alle sind mittig geschnitten; der Schwerpunkt steht auf 52 % / 34 %
     (über „Zuschneiden“ gesetzt).
   Das alte Bild hat seinen Text links. Auf dem Telefon ist davon nichts zu
   lesen, auf dem Desktop nur das halbe Wort.
4. **„Monatliche Unterstützung benötigt“** steht mobil als Etikett auf dem
   Bild. Es kommt aus den Spendeneinstellungen (monatliche Spenden sind
   eingeschaltet). Das Förderkonzept (`konzepte/konzept-foerdermodell.md`
   §6.2) erlaubt wiederkehrende Zahlungen, sagt aber auch: „Einen bestimmten
   Rhythmus bewirbt Solidon3D nicht.“ Entscheidung liegt bei Robert (Frage 6).
5. **Der Titel veraltet in fünf Wochen.** „bis Version 1.0“ endet am
   01.11.2026, die laufenden Kosten nicht.
6. **Die Zahlen im Text stimmen nicht mehr** (0.4.0, 108 Operationen,
   27 Bausteine), und zwei Posten sind erledigt: Die Mac-Pakete sind seit
   0.4.1 notarisiert, Apple-Konto und Certum-Zertifikat sind bezahlt.

---

## 2. Zahlen mit Beleg

Alle Zahlen am 23.09.2026 aus dem Code oder aus Git gelesen. Veröffentlicht
ist 0.4.4; der Arbeitsbaum trägt 0.5.0 (`app/branding.py`,
`APP_VERSION = "0.5.0"`), die noch nicht draußen ist. Wo beide abweichen,
steht beides da.

| Zahl | 0.4.4 (Download) | 0.5.0 (in Arbeit) | Beleg |
|---|---|---|---|
| Operationen | 132 | 136 | `load_operations(); len(REGISTRY.all())`, 0.4.4 aus `git archive v0.4.4 app` in einem Temp-Ordner gezählt (`app.__file__` geprüft) |
| Bausteine | 35 | 35 | `PARTS` in `app/core/knowledge/parts/registry.py` |
| Normteilmaße | 51 | 51 | Summe der `*_sizes()` in `app/core/knowledge/standards.py` |
| Druckerprofile | 16 | 18 (16 FDM + 2 Resin) | Tabellen in `app/core/knowledge/data/printers.toml` |
| Beispielprojekte | 11 | 11 | `app/examples/*.p3d` |
| Sprachen | 6 | 6 | Deutsch als Quelle + 5 Kataloge in `app/i18n/locales/` |
| Veröffentlichte Version | 0.4.4 vom 19.09.2026 | | `website/version.json`, Download-Kasten `website/index.html` |

Versionen seit dem Kampagnenstart (13.09.2026), Tag im Download-Kasten laut
Git-Log von `website/version.json`, Umfang laut `website/changelog.html`
(`data-announcement`):

| Version | im Download | Neuerungen |
|---|---|---|
| 0.4.1 | 14.09.2026 | 96 |
| 0.4.2 | 15.09.2026 | 48 |
| 0.4.3 | 18.09.2026 | 19 |
| 0.4.4 | 19.09.2026 | 22 |
| **zusammen** | vier Versionen in sechs Tagen | **185** |

0.5.0 steht in `changelog/de.md` mit 74 Punkten, ohne Termin. Die Texte
nennen daraus nur Belegtes und nie ein Datum.

Weitere Zahlen, die die Texte verwenden:

| Zahl | Wert | Beleg | Status |
|---|---|---|---|
| Demo-Downloads | über 1.700 bis 20.09.2026 | Roberts Ablesung vom Website-Dashboard, `.claude/memory/verkaufsphase-preise-und-demo-zahlen.md` | **vor dem Einstellen aktualisieren** (Frage 3) |
| Demo-Ende | 30.10.2026 | `website/index.html`, `README.md` (`DEMO_UNTIL`) | belegt |
| Verkaufsstart 1.0 | 01.11.2026, 10:00 Uhr | Robert, 23.09.2026 | belegt (Robert) |
| Preise ab 1.0 | privat 69 €, ab Februar 99 €; gewerblich 199 €, ab Februar 249 € | Robert, 23.09.2026 (ersetzt die Angabe vom 19.09.) | noch nicht auf der Website, siehe Abschnitt 5 |
| Mac notarisiert | ab 0.4.1 | `changelog/de.md` 0.4.1, `website/index.html` | belegt |
| Windows-Signierung | Certum-Zertifikat gekauft, Verifikation lief am 18.09. noch | Robert; `ROADMAP.md` RM-001 | Stand erfragen (Frage 2) |
| Presse | 3Druck.com und VoxelMatters, Ende August | Links in `marketing/presse-*/README.md` | belegt |
| YouTube | Reihe „STL passend machen“, 5 Tutorials DE/EN, 15.–23.09. | `marketing/youtube/workshop-2026-09.md`, oEmbed am 23.09. geprüft: öffentlich | belegt |

---

## 3. Kosten und Ziel

### Was Robert genannt hat (23.09.2026)

- Bereits selbst bezahlt: Apple-Entwicklerprogramm, Certum-Code-Signing-Zertifikat.
- Laufend: Claude (Max 20x), Codex über ChatGPT (Pro, „20x“), Gewerbekosten,
  „machende kosten“.

**Annahme:** „machende kosten“ ist ein Tippfehler für „laufende Kosten“, also
Webspace und Domain (netcup) und Ähnliches. **Robert bitte bestätigen**
(Frage 1).

### Listenpreise der beiden Werkzeuge (recherchiert am 23.09.2026)

| Werkzeug | Listenpreis | in Euro | Quelle |
|---|---|---|---|
| Claude Max 20x | 200 US-$ im Monat, zzgl. Steuer | EU-Preisliste: Max „ab 90 €“ zzgl. USt für die 5x-Stufe; die 20x-Stufe kostet in US-$ das Doppelte, also **rund 180 € netto, rund 214 € brutto** (Schluss, nicht abgelesen) | [support.claude.com – What is the Max plan](https://support.claude.com/en/articles/11049741-what-is-the-max-plan) („Max 20x: $200 per month“), [claude.com/pricing](https://claude.com/pricing), EU-Preise in Euro: [kirstenbiema.com, geprüft am 11.09.2026](https://www.kirstenbiema.com/en/blog/was-kostet-claude/) |
| ChatGPT Pro 20x (mit Codex) | 200 US-$ im Monat | **229 € brutto** im deutschen App Store (Stand 03.09.2026), also rund 192 € netto | [OpenAI Help – About ChatGPT Pro tiers](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-tiers) (Pro $200 = „Pro 20x“; Neuabschlüsse seit 10.09.2026 pausiert, laufende Abos unberührt), Euro-Preis: [skill-sprinters.de](https://skill-sprinters.de/blog/tools/chatgpt-go-vs-plus-2026-deutsche-preise/) |

Gegenrechnung über den EZB-Referenzkurs vom 22.09.2026 (1 € = 1,1463 US-$,
<https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml>):
200 US-$ = 174,47 € netto, 207,62 € mit 19 % USt. Beide Wege landen bei
**rund 370 € netto oder rund 440 € brutto für beide Werkzeuge zusammen.**
Ob Robert die Umsatzsteuer als Vorsteuer zurückbekommt, hängt an seiner
steuerlichen Erfassung; deshalb nennt der Kampagnentext gerundet „rund 400 €“,
das stimmt für beide Fälle. **Den genauen Betrag bitte von den Rechnungen
ablesen** (Frage 1).

### Rechnung für das Ziel

| Posten | im Monat | Status |
|---|---|---|
| Claude Max 20x + ChatGPT Pro | rund 400 € | Listenpreise, s. o. |
| Gewerbe, Webspace, Domain | rund 100 € | **Annahme**, Robert bitte beziffern |
| **Summe** | **rund 500 €** | |

GoFundMe-Gebühr in Deutschland: 2,9 % + 0,25 € je Spende, keine
Plattformgebühr ([gofundme.com/de-de/c/pricing](https://www.gofundme.com/de-de/c/pricing)).
Bei 5.000 € aus 200 Spenden à 25 € sind das 145 € + 50 € = 195 €. Netto
bleiben rund 4.800 €, bei 500 € im Monat **knapp zehn Monate**, von Oktober
2026 bis in den Sommer 2027.

### Entscheidung: Gesamtziel 5.000 € bleibt, sichtbar wird eine Etappe

- **5.000 € passen zur Rechnung**: knapp zehn Monate laufende Kosten, also
  über den Verkaufsstart hinaus, bis der Verkauf die Kosten trägt.
  Eine Erhöhung auf die vollen zwölf Monate (rund 6.200 €) würde bei 51 €
  Stand gierig wirken und löst das eigentliche Problem nicht: Es fehlt an
  Reichweite, nicht am Ziel.
- **Sichtbar eingestellt werden 500 € als erste Etappe** („ein Monat“). Heute
  steht der Ring bei 2 %; mit 500 € stünde er bei 10 %, und jede weitere
  Spende bewegt ihn sichtbar. GoFundMe erlaubt, das Ziel jederzeit zu ändern,
  und rät selbst zu automatisch mitwachsenden Zielen („Automated goal
  setting“, [Choosing your goal amount](https://support.gofundme.com/hc/en-us/articles/4405145410331-Choosing-your-goal-amount)).
  Der Text nennt Etappe und Gesamtziel offen; das bleibt ehrlich.
- **Stufen danach:** 1.500 € (drei Monate), 3.000 € (sechs Monate),
  5.000 € (Gesamtziel). Jede erreichte Stufe ist ein Update („Oktober ist
  bezahlt“). Von Hand statt automatisch, weil jede Stufe im Text und im Update
  benannt wird.

---

## 4. Was GoFundMe selbst empfiehlt (gelesen am 23.09.2026)

Hilfe-Center über die öffentliche Zendesk-Schnittstelle gelesen
(`support.gofundme.com/api/v2/help_center/en-us/articles/<id>.json`); die
deutsche Fassung sperrt automatische Abrufe. Jeder Link unten ist die
englische Originalseite.

| Thema | Kernaussage | Quelle |
|---|---|---|
| Vier Schlüsselschritte | Geschichte mit mindestens 100 Wörtern; teilen „in more than one place, multiple times“; Update innerhalb einer Woche; Auszahlung einrichten | [Four key actions](https://support.gofundme.com/hc/en-us/articles/13163352843931-Four-key-actions-for-your-GoFundMe-fundraiser) |
| Erste Sätze | Titel und erste Sätze sollen sagen, warum du um Hilfe bittest und was sie bewirkt; wer, was, wann, wo, warum | ebd. |
| Bilder | „Photos of people tend to appeal better than photos of objects or text.“ | ebd. |
| Titel | 60 Zeichen; Formel Handlung + Wer + Anliegen | [Choosing a title and customizing your link](https://support.gofundme.com/hc/en-us/articles/14232621866267-Choosing-a-title-and-customizing-your-link) |
| Link | nur einmal änderbar | ebd. |
| Geschichte | 2–3 Absätze, mindestens 100 Wörter; wer du bist, was passiert, wie das Geld verwendet wird, Dank und Bitte ums Teilen; fett, kursiv, Absätze nutzen | [Writing your story](https://support.gofundme.com/hc/en-us/articles/4405037683227-Writing-your-story-Sharing-your-need) |
| Titelbild | JPEG, PNG oder BMP, unter 20 MB, empfohlen 720×405 oder größer, quer | [Adding photos](https://support.gofundme.com/hc/en-us/articles/203604584-Adding-photos-to-your-fundraiser) |
| Weitere Bilder | bis zu 5 zusätzlich; daraus erzeugt GoFundMe Teilen-Poster und -Videos | ebd., [Auto-generated sharing](https://support.gofundme.com/hc/en-us/articles/38748476284955-Increase-your-reach-with-auto-generated-sharing-features) |
| Video | nur als öffentliches YouTube-Video; Shorts über `/watch?v=` statt `/shorts/` | [Adding videos](https://support.gofundme.com/hc/en-us/articles/4405106210843-Adding-video-s-to-your-fundraiser) |
| Video-Inhalt | Name, wofür das Geld ist, warum es dir wichtig ist, Bitte ums Teilen; hochkant aufnehmen | [Video fundraising tips](https://support.gofundme.com/hc/en-us/articles/11236950054555-Video-fundraising-tips) |
| Updates | erfolgreiche Kampagnen posten „an update (or more) a week“; Updates gehen per Mail an alle Unterstützer | [How to post an update](https://support.gofundme.com/hc/en-us/articles/12553895153563-How-to-post-a-GoFundMe-update) |
| Erste Spenden | zuerst der engste Kreis, persönlich per Nachricht, Mail, Anruf: „asking them to be the first to donate and share“ | [Four key actions](https://support.gofundme.com/hc/en-us/articles/13163352843931-Four-key-actions-for-your-GoFundMe-fundraiser), [First donations](https://support.gofundme.com/hc/en-us/articles/23373616730011-Tips-for-receiving-your-first-donations) |
| Fremde | „strangers usually don’t donate to strangers“ | [First donations](https://support.gofundme.com/hc/en-us/articles/23373616730011-Tips-for-receiving-your-first-donations) |
| Kreise | innerer Kreis direkt, mittlerer über Gruppen, äußerer über Wiederholung | [Share with the most potential donors](https://support.gofundme.com/hc/en-us/articles/23364638756635-How-to-share-your-fundraiser-with-the-most-potential-donors) |
| Mitorganisatoren | „3x more likely to reach their goal“ | [Strategies](https://support.gofundme.com/hc/en-us/articles/23377826690715-Strategies-to-help-you-meet-your-fundraising-goal) |
| Danke | über den Reiter „Spenden“ → „Danke sagen“, mit Bitte ums Teilen | [Thanking donors](https://support.gofundme.com/hc/en-us/articles/205213077-Thanking-and-managing-donors) |
| Prämien | „GoFundMe does not allow organizers to offer any type of good or service to donors“ | [Raffles, promotions, and giveaways](https://support.gofundme.com/hc/en-us/articles/4406474655899-Raffles-promotions-and-giveaways), [Terms](https://www.gofundme.com/c/terms) |
| Steuer | GoFundMe stellt keine Steuerbelege aus; der Organisator versichert, keine Waren oder Leistungen gegen die Spende zu liefern | [Taxes for organizers](https://support.gofundme.com/hc/en-us/articles/204295498-Taxes-for-GoFundMe-organizers) |
| Monatlich | Spender zahlen bei monatlichen Spenden zusätzlich 5 % | [Recurring donations](https://support.gofundme.com/hc/en-us/articles/28844774144155-Running-your-fundraiser-with-recurring-donations) |
| Bearbeiten | außerhalb der USA: „Bearbeiten“ unter dem Titel → Reiter „Details“ und „Einstellungen“ | [Editing your fundraiser content](https://support.gofundme.com/hc/en-us/articles/360001992687-Editing-your-fundraiser-content) |
| Tempo | die Zahlen oben („3x“, „2,5x“) stammen von GoFundMe und sind nicht unabhängig belegt | [9 Tipps](https://www.gofundme.com/c/fundraising-tips) |

---

## 5. Entscheidungen

### Titel

Empfohlen: **„Solidon3D: STL anpassen ohne CAD – ein Ein-Personen-Projekt“**
(59 Zeichen). Begründung in `kampagne-de.md`, Abschnitt 1. Kern: GoFundMe
baut den Titel selbst in „Spendenaufruf von Robert Schneider: …“ und „…
braucht deine Unterstützung für …“ ein, deshalb ein Substantiv-Titel statt
der Verb-Formel; „bis Version 1.0“ fällt weg, weil die Kosten über den
1. November hinaus laufen. Link bleibt unverändert (nur einmal änderbar,
Kurzlink steht in App, Website und Presse).

### Text

- **Erster Absatz = Teilen-Text.** Er sagt jetzt Problem, wer, was und die
  Bitte in 248 Zeichen; die ersten zwei Sätze tragen allein.
- **Kürzer:** rund 3.100 statt rund 4.500 Zeichen, sieben fette
  Zwischenüberschriften, eine einzige Aufzählung (die Kosten).
- **Kosten ehrlich und passend zu Roberts Angaben:** was selbst bezahlt ist
  (Apple, Certum), was monatlich läuft (Werkzeuge rund 400 €, Gewerbe und
  Webspace rund 100 €), was das Ziel deckt (knapp zehn Monate), was bei
  weniger oder mehr passiert. Die alten Posten Testhardware (1.400 €) und
  Entwicklungszeit (2.000 €) sind nicht mehr drin, weil Robert sie am
  23.09. nicht mehr nennt (Frage 4).
- **Die KI-Werkzeuge werden beim Namen genannt**, mit einem Satz, wozu sie
  dienen, und der Klarstellung, dass im Programm Code rechnet. Wer die
  Kostenliste liest, fragt sonst; verschweigen und später auffliegen wäre
  schlimmer (Frage 5).
- **Harte Grenze** unverändert streng nach Förderkonzept §2: keine
  Gegenleistung, kein Rabatt, keine Anrechnung, kein früherer Zugang, keine
  Spendenquittung; Verweis auf GoFundMes Prämienverbot.
- **Preise ab 1.0 stehen nur als vorbereiteter Satz bereit.** Die Website sagt
  noch „Preis und Vertragsbedingungen werden vor ihrem Angebot
  veröffentlicht“; Kampagne und Website sollen sich nicht widersprechen.
- **Ton:** Du-Form wie Website und bisherige Kampagne. Gegen die sieben
  Merkmale aus `.claude/memory/nicht-nach-ki-klingen.md` gelesen: keine
  Gedankenstriche im Fließtext, keine „nicht X, sondern Y“-Figuren, keine
  Bewertungswörter, kein zusammenfassender Schluss.

### Englisch

Als fett überschriebener Block unter dem deutschen Text, nicht als Update und
nicht als zweite Kampagne (Begründung `kampagne-en.md`, Abschnitt 1).

### Bilder

**Neu aufgenommen nach Roberts Vorgabe vom 23.09.2026** („dass der ganze
Bildschirm verwendet wird und wir nicht nur so eine kleine Szene haben“,
Bildstandard in `F:\3D Druck.review-050\AUFTRAG-BAU.md`). Die erste Fassung
bestand aus kleinen, hochgerechneten App-Ausschnitten auf dunkler Fläche; sie
ist vollständig ersetzt.

**Aufnahme** (`bilder/quellen/aufnahmen.py`):

- das ganze Hauptfenster, maximiert auf dem 2560×1440-Schirm (Arbeitsfläche
  2560×1392, Fensterinhalt **2560×1369**), in nativen Pixeln, Weg
  `tools/make_figures.py` `prepared(hidden=False)` → `work_area()`;
- **die veröffentlichte Demo 0.4.4**, nicht der Arbeitsbaum 0.5.0: Die Dateien
  des Tags liegen per `git archive v0.4.4` in einem Temp-Ordner, das Skript
  lädt `app` nachweislich von dort (`app.__file__` wird geprüft);
- eigene Nutzerverzeichnisse im Temp-Ordner, Roberts Profil bleibt unberührt;
- die Kamera eng am Teil und so verschoben, dass die Handlung dort liegt, wo
  der GoFundMe-Ausschnitt seine Mitte hat (`Capture.aim`, rechnet über
  `world_to_display` nach);
- echte Bedienung im selben Bild: die Karte „Bohrung ändern“ mit getipptem
  Durchmesser und laufender Vorschau („Vorschau — noch nicht übernommen“),
  der Verlauf nach dem Übernehmen, der Prüfbericht mit seiner Warnung, der
  Druckdialog mit „Was dieses Teil verlangt“ und „Im Slicer öffnen“ (dafür
  ist dort „Das Wichtigste“ zugeklappt, wie es ein Kunde mit einem Klick tut).

**Modelle:** der Rollenhalter aus `website/teile/weg1-halter-anpassen.p3d`
(eingelesene STL mit erkannten Bohrungen, Ø 34,09 mm gemessen, auf 38 mm
geändert) und das Beispiel `passung-nach-materialwechsel.p3d`. Beide sind
eigene Modelle mit geklärter Rechtekette in `ASSET-RIGHTS.toml`. Die Dateien in
`F:\3D Dateien` sind fremde Downloads ohne festgehaltene Lizenz; für ein
öffentliches, werbendes Bild kommen sie deshalb nicht in Frage.

**Ausschnitte für GoFundMe** (`bilder/quellen/make_gofundme_images.py`): je
Motiv 1920×1080 **ohne Skalierung** aus der Vollbildaufnahme, bis an den Rand
gefüllt, darüber Überschrift und Unterzeile auf einer weichen Abdunklung.
Die Lage folgt der Messung aus Abschnitt 1:

| Zone | Bereich im Bild | Was dort steht |
|---|---|---|
| überall sichtbar | x 560–1360, y 100–620 | Überschrift, die Handlung (Bohrung, Maßmarke, Dialogkopf) |
| Desktop und Vorschau | x 240–1680 | der Rest des Fensters |

Eine Grenze bleibt, und sie liegt an GoFundMe: Die rechte Leiste mit der
Karte „Bohrung ändern“ sitzt am Fensterrand. GoFundMe blendet auf dem Desktop
die äußeren 10 % und auf dem Handy 56 % der Breite aus; kein Ausschnitt, der
am Fensterrand endet, kann sie dort zeigen. Sie steht deshalb vollständig im
Bild (Link-Vorschau, Vergrößerung, Teilen-Poster), und die Handlung selbst
(Bohrung, Vorschau, Maß) liegt in der Mitte. Wer das Maß auf dem Handy lesen
soll, liest es an der großen Marke „34,09 mm → 38 mm“.

**Maßmarken und Texte in den Bildern** nennen nur, was die Anwendung selbst
anzeigt: 34,09 mm und 38,00 mm am Rollenhalter, den Wortlaut der Warnung „Die
Passung sitzt enger als vorgesehen.“, die Zahl der Neuerungen je Version.

**Geprüft:** alle vierzehn Bilder (sieben Motive, Deutsch und Englisch) in
voller Größe und über die Prüfblätter in `bilder/pruefung/` (Desktop 605×423
aus 720×405, Handy 375×478 aus 1200×900 mit nachgestellter GoFundMe-
Überlagerung, 1:1, 360 Punkte Breite). Korrigiert danach: Titelbild endet an
der Kante der rechten Leiste statt mitten in ihrem Text, die linke Maßmarke
steht ganz außerhalb der Handy-Mitte statt halb angeschnitten, die
Warnungsmarke im Prüfbericht-Bild steht mittig, die Versionsmarken im
Update-Bild stoßen nicht mehr aneinander.

**Schriften:** Archivo und Source Sans 3 aus `website/fonts/`, SIL Open Font
License 1.1. Gerendert mit Chrome ohne Fenster, weil nur ein Browser die
WOFF2-Dateien lädt.

### Ziel

Gesamtziel 5.000 € bleibt, sichtbar wird die erste Etappe 500 €. Herleitung
in Abschnitt 3.

### Updates und Teilen

- Update 1 ist überfällig (GoFundMe: innerhalb der ersten Woche). Es erklärt
  auch den Umbau der Seite und die geänderte Zielanzeige, damit bisherige
  Spender nicht rätseln.
- Danach mittwochs, höchstens zwei pro Woche, Vorlagen A bis H in
  `updates-plan.md`. Nur belegte Inhalte, keine Termine für 0.5.0.
- Teilen in GoFundMes Reihenfolge: engster Kreis persönlich, dann eigenes
  Profil und YouTube-Kanal, dann Gruppen, dort Produkt vor Spende. Auf
  Printables und MakerWorld kein Spendenlink (Regeln verlinkt in
  `teilen.md`); auf Reddit nur mit ausdrücklicher Erlaubnis der
  Subreddit-Regeln.
- Kein Text verspricht eine Gegenleistung, auch nicht der Dank.

### Einstellungen

Monatliche Spenden bleiben möglich, Standard-Spendenart „einmalig“
(Förderkonzept §6.2). Worte der Unterstützung an, vorgeschlagene fremde
Kampagnen aus. Einzelheiten in `anleitung-einstellen.md`, Schritt 6.

---

## 6. Offene Fragen an Robert

1. **Kosten** (aufgelöst am 23.09.): Der Text nennt nur „rund 400 €“ für die
   zwei Werkzeuge und „dazu Gewerbe, Webspace und Domain“ ohne Zahl; das
   Ziel deckt „diese Kosten nach Gebühren rund zehn Monate“. Offen bleibt
   nur, ob „machende kosten“ wirklich die laufenden Kosten meint.
2. **Windows-Signierung** (aufgelöst): kein Zeitpunkt, nur „mit dem auch die
   Windows-Version künftig ohne Warnhinweis startet“; 0.5.0 erscheint noch
   unsigniert.
3. **Downloadzahl** (aufgelöst): „über 1.700“ bleibt, sie kann nur wachsen.
4. **Alte Posten:** Testhardware (Mac, 16-GB-Grafikkarte, 1.400 €) und
   Entwicklungszeit (2.000 €) standen in der alten Kampagne. Sie fehlen in
   deiner Liste vom 23.09. und deshalb im neuen Text, ebenso steht dort als
   Folge „Meine eigene Arbeitszeit rechne ich nicht mit“. Stimmt das so?
5. **KI-Werkzeuge beim Namen:** Der Text nennt Claude Max und ChatGPT Pro mit
   Codex und erklärt in zwei Sätzen, wozu. Einverstanden, oder lieber
   allgemein „zwei Programmierwerkzeuge“? Empfehlung: beim Namen, weil die
   Kostenliste sonst genau diese Frage auslöst.
6. **Monatliche Spenden:** einschalten lassen mit Standard „einmalig“
   (Empfehlung), ganz ausschalten, oder so lassen wie heute mit dem Etikett
   „Monatliche Unterstützung benötigt“ auf dem Handy?
7. **Preise:** Wann stehen die Preise der 1.0 auf der Website? Erst dann kommt
   der vorbereitete Preissatz in die Kampagne.
8. **Beträge der bereits bezahlten Posten:** Sollen Apple-Programm und
   Certum-Zertifikat mit Betrag genannt werden? Heute steht nur „selbst
   bezahlt“.
9. **Foto:** Gibt es ein echtes Foto von dir am Rechner oder Drucker? Es
   gehört nach GoFundMes eigener Aussage auf Platz 1.
10. **Steuer:** Die offene Frage aus dem Förderkonzept (§6.1) gilt für
    GoFundMe-Eingänge genauso wie für PayPal; die Texte versprechen nichts
    dazu. Keine Rechts- oder Steuerberatung.

---

## 7. Arbeitsprotokoll

| Schritt | Ergebnis |
|---|---|
| Unterlagen gelesen | `AGENTS.md`, `CLAUDE.md`, Förderkonzept, `README.md`, `website/index.html`, sechs Erinnerungen |
| Kampagne öffentlich gelesen | Text, Meta-Angaben, Bildzuschnitte, mobile und Desktop-Darstellung (Abschnitt 1) |
| Zahlen aus Code und Git | Abschnitt 2 |
| GoFundMe-Hilfe, Gebühren, Preise der Werkzeuge | Abschnitte 3 und 4 |
| `kampagne-de.md`, `kampagne-en.md` | fertig |
| `update-1-de.md`, `update-1-en.md`, `updates-plan.md` | fertig |
| `teilen.md` | fertig; Reddit-Regeln nicht lesbar (Reddit sperrt automatische Abrufe mit HTTP 403, das Browserfenster der Sitzung lässt Reddit nicht zu), deshalb dort die vorsichtige Fassung und der Auftrag, die Seitenleiste zu lesen |
| Bilder, erste Fassung | kleine App-Ausschnitte auf dunkler Fläche; von Robert verworfen und ersetzt |
| Prüfstellen aufgelöst | Downloads, Windows, Kosten nach Roberts Angaben; Kopiervorlage neu erzeugt |
| Vollbildaufnahmen | 5 Szenen × 2 Sprachen aus der Demo 0.4.4, 2560×1369, `bilder/quellen/aufnahmen/` |
| Bilder | 7 Motive × 2 Sprachen als native Ausschnitte 1920×1080, je PNG, JPG und Prüfblatt; alle angesehen, eine Korrekturrunde |
| `kopiervorlage.html` | erzeugt aus den Markdown-Dateien; Blöcke schwarz auf weiß, damit beim Kopieren keine Farben mitreisen |
| `anleitung-einstellen.md` | fertig, mit Checkliste |
| Prüfung | `ruff check` und `ruff format --check` über `marketing/gofundme/` grün |

---

## 8. Dateien

| Datei | Inhalt |
|---|---|
| `kampagne-de.md` | Titel, erster Absatz, Geschichte, Preissatz, Ziel, Medien |
| `kampagne-en.md` | englische Fassung und wie sie verwendet wird |
| `update-1-de.md`, `update-1-en.md` | erstes Update |
| `updates-plan.md` | Rhythmus, Plan bis 01.11., Vorlagen A bis H |
| `teilen.md` | Texte je Kanal, Danke-Vorlagen |
| `anleitung-einstellen.md` | Schritt für Schritt, Checkliste |
| `kopiervorlage.html` | formatierter Text zum Kopieren; `make_kopiervorlage.py` erzeugt ihn |
| `bilder/*.jpg` | zum Hochladen (1920×1080, je rund 200 KB) |
| `bilder/*.png` | dieselben Bilder verlustfrei |
| `bilder/pruefung/` | Prüfblätter, nicht zum Hochladen |
| `bilder/quellen/aufnahmen.py` | nimmt das maximierte Fenster der Demo 0.4.4 auf |
| `bilder/quellen/aufnahmen/` | die Vollbildaufnahmen (2560×1369) und die gemessenen Fensterkoordinaten |
| `bilder/quellen/make_gofundme_images.py` | schneidet daraus die GoFundMe-Bilder und schreibt die Prüfblätter |
