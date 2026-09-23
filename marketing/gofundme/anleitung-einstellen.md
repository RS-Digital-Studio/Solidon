# Anleitung: die Kampagne in GoFundMe umstellen

Alles hier macht Robert selbst, angemeldet in seinem GoFundMe-Konto. Dauer:
rund 45 Minuten, das eigene Foto nicht mitgerechnet.

Die Bedienwege stammen aus GoFundMes Hilfe-Center, Stand 23.09.2026 (Links je
Schritt). Die Hilfe beschreibt zwei Wege: einen für Kampagnen in den USA und
einen für **alle anderen Länder**. Für Solidon3D gilt der zweite. Die
Bezeichnungen der Knöpfe stehen dort auf Englisch; in der deutschen Oberfläche
können sie anders übersetzt sein. In Klammern steht jeweils der englische
Begriff zum Wiederfinden.

---

## Vor dem Start

1. **Die früheren Prüfstellen sind aufgelöst** (Roberts Angaben vom
   23.09.2026): Downloadzahl „über 1.700“ bleibt stehen, zur
   Windows-Signierung steht kein Zeitpunkt, bei den Kosten steht nur die
   Zahl für die Werkzeuge (rund 400 €) und „dazu Gewerbe, Webspace und
   Domain“.
2. **Preise:** Stehen die Preise der Version 1.0 schon auf solidon3d.de? Nur
   dann den vorbereiteten Preissatz einsetzen (`kampagne-de.md`, unter der
   Geschichte).
3. **Kopiervorlage neu erzeugen**, falls an den Texten etwas geändert wird:
   `.venv\Scripts\python.exe marketing/gofundme/make_kopiervorlage.py`.
   Alternativ direkt in `kopiervorlage.html` im Browser ändern (wird nicht
   gespeichert).

---

## Schritt 1: Bearbeiten öffnen

Hilfe: [Editing your fundraiser content](https://support.gofundme.com/hc/en-us/articles/360001992687-Editing-your-fundraiser-content)

1. Anmelden, oben rechts im Menü **Deine Spendenaufrufe** („Your
   fundraisers“), die Kampagne wählen.
2. Unter dem Titel **Bearbeiten** („Edit“). In der App: der Stift oben rechts.
3. Es gibt zwei Reiter: **Details** (Titel, Ziel, Hauptbild, Geschichte, Link,
   Kategorie, Ort) und **Einstellungen** („Settings“).

## Schritt 2: Titel

1. Reiter **Details**, neben dem Titel **Bearbeiten**.
2. Einsetzen: **Solidon3D: STL anpassen ohne CAD – ein Ein-Personen-Projekt**
   (59 von 60 Zeichen; der Gedankenstrich ist ein echter Halbgeviertstrich).
3. **Den Link nicht ändern.** GoFundMe lässt ihn nur einmal ändern
   ([Choosing a title and customizing your link](https://support.gofundme.com/hc/en-us/articles/14232621866267-Choosing-a-title-and-customizing-your-link)),
   und der Kurzlink `gofund.me/08c5f0edb` steht in App, Website und Presse.
4. **Speichern**.

## Schritt 3: Bilder und Video

Hilfe: [Adding photos](https://support.gofundme.com/hc/en-us/articles/203604584-Adding-photos-to-your-fundraiser),
[Adding videos](https://support.gofundme.com/hc/en-us/articles/4405106210843-Adding-video-s-to-your-fundraiser)

1. Reiter **Details**, neben **Medien** („Media“) **Bearbeiten**.
2. Hauptbild: **Ersetzen** („Replace“) → `bilder/titelbild-de.jpg`. Alle Bilder
   sind Ausschnitte aus Aufnahmen des ganzen Solidon3D-Fensters der Demo 0.4.4
   (1920×1080, nicht vergrößert).
3. Danach **Zuschneiden** („Crop“) öffnen und den Ausschnitt **mittig**
   lassen. Das alte Bild hatte seinen Schwerpunkt bei 52 % / 34 %; das neue
   Bild ist für die Mitte gebaut.
4. **Bis zu 5 Bilder hinzufügen** („Add up to 5 images“), in dieser
   Reihenfolge:
   1. `bilder/galerie-1-vorher-de.jpg`
   2. `bilder/galerie-2-anklicken-de.jpg`
   3. `bilder/galerie-3-nachher-de.jpg`
   4. `bilder/galerie-4-pruefbericht-de.jpg`
   5. `bilder/galerie-5-drucken-de.jpg`
   Die zwei alten Zusatzbilder über das Drei-Punkte-Menü am Bild löschen.
5. Video: ins Feld **YouTube-Link hinzufügen** („Add a YouTube link“)
   `https://www.youtube.com/watch?v=-leBJmhdN30` einsetzen, **Video
   hinzufügen**. Das ist der eigene Short „STL passt fast? Löcher ändern, Teil
   behalten“. GoFundMe nimmt keine `/shorts/`-Links; die Schreibweise mit
   `/watch?v=` ist GoFundMes eigener Rat. Ein Hochkant-Video passt zur
   Telefonansicht, die hochkant ist.

**Mit eigenem Foto (empfohlen, sobald eins da ist).** GoFundMe: „Photos of
people tend to appeal better than photos of objects or text.“ Dann:
Foto als Hauptbild, `titelbild-de.jpg` als erstes Zusatzbild, das
Drucken-Bild fällt weg. Für das Foto:

- quer, mindestens 1920×1080, hell, ohne Schrift im Bild;
- **das Gesicht in die Mitte und ins obere Drittel.** Auf dem Telefon zeigt
  GoFundMe nur die mittleren 44 % der Breite, und ab etwa 60 % der Höhe liegen
  Titel und Etikett darüber;
- am Schreibtisch mit Solidon3D auf dem Bildschirm oder am Drucker, gern mit
  einem gedruckten Teil in der Hand;
- ein echtes Foto, kein bearbeitetes oder erzeugtes.

**Optional: ein eigenes Video, 60 Sekunden, hochkant.** GoFundMe rät dazu
([Video fundraising tips](https://support.gofundme.com/hc/en-us/articles/11236950054555-Video-fundraising-tips)):
Name, wofür das Geld ist, warum es wichtig ist, Bitte ums Teilen. Kein
Wortlaut zum Ablesen, eher so:

- „Ich bin Robert, ich baue Solidon3D.“ Kamera auf dich, Bildschirm im
  Hintergrund.
- Das Problem mit einem echten Teil in der Hand: Das Loch passt nicht.
- Zehn Sekunden Bildschirm: Loch anklicken, Zahl tippen, fertig.
- Wofür das Geld ist, in einem Satz: die Werkzeuge, mit denen du
  programmierst, bis der Verkauf das trägt.
- „Teilen hilft genauso wie spenden.“

Hochladen auf YouTube, **öffentlich**, dann wie oben einsetzen; es ersetzt
dann den Short als Video.

## Schritt 4: Geschichte

Hilfe: [Writing your story](https://support.gofundme.com/hc/en-us/articles/4405037683227-Writing-your-story-Sharing-your-need)

1. `kopiervorlage.html` im Browser öffnen (Doppelklick).
2. Im Abschnitt **Geschichte** die gelben Stellen prüfen, anpassen und die
   gelbe Markierung löschen.
3. **Markieren und kopieren**.
4. In GoFundMe: Reiter **Details**, neben **Geschichte** („Story“)
   **Bearbeiten**, den alten Text komplett markieren (Strg+A im Textfeld),
   **Strg+V**.
5. Prüfen, bevor gespeichert wird:
   - Die sieben Zwischenüberschriften und **English** sind fett. Kam der
     Fettdruck nicht mit, jede Überschrift markieren und **Strg+B**.
   - Keine Sternchen, keine gelbe Markierung, keine graue oder farbige Schrift.
     Sieht der Text fremd formatiert aus: alles löschen, mit
     **Strg+Umschalt+V** als reinen Text einfügen und die Überschriften mit
     Strg+B fett setzen.
   - Zwischen den Absätzen je eine Leerzeile.
6. Video in die Geschichte (optional, zusätzlich zu Schritt 3): Cursor unter
   den Abschnitt „Worum es geht“, das Bild-Symbol → **YouTube-Video
   hinzufügen** → `https://www.youtube.com/watch?v=-leBJmhdN30`.
7. **Speichern**, dann nochmal **Speichern** für die ganze Seite.

## Schritt 5: Ziel

Hilfe: [Choosing your goal amount](https://support.gofundme.com/hc/en-us/articles/4405145410331-Choosing-your-goal-amount)

1. Auf das Ziel klicken → **Zieleinstellungen bearbeiten** („Edit goal
   settings“).
2. Ziel **500 €**. Automatische Ziele **aus** („opt out of automated goals“),
   weil die Etappen im Text benannt sind.
3. **Speichern**.
4. Später, jeweils sobald eine Etappe erreicht ist: 1.500 € → 3.000 € →
   5.000 €, und dazu ein Update (Vorlage A in `updates-plan.md`).

## Schritt 6: Einstellungen

Reiter **Einstellungen** („Settings“) in Bearbeiten.

| Einstellung | Empfehlung | Warum |
|---|---|---|
| Spenden an | an | |
| Monatliche Spenden | Entscheidung Robert, siehe unten | |
| Worte der Unterstützung („words of support“) | an | Kommentare von Spendern machen die Seite für Fremde glaubwürdig |
| In Suchergebnissen erscheinen | an | |
| Vorgeschlagene andere Spendenaufrufe | aus | lenkt Besucher auf fremde Kampagnen |
| Automatisch erzeugte Teilen-Inhalte („auto-generated sharing“) | an | GoFundMe baut daraus Poster aus Titelbild und Zusatzbildern |
| Benachrichtigungen bei Spenden | an | damit am selben Tag gedankt werden kann |

**Monatliche Spenden:** Heute eingeschaltet, und auf dem Telefon steht deshalb
„Monatliche Unterstützung benötigt“ auf dem Bild. Die Kosten laufen monatlich,
das passt. Das Förderkonzept sagt aber: „Einen bestimmten Rhythmus bewirbt
Solidon3D nicht“ (§6.2), und Spender zahlen bei monatlichen Spenden 5 % extra
an GoFundMe. Empfehlung: einmalig und monatlich zulassen, als
**Standard-Spendenart „einmalig“** wählen. Ob das Etikett dann verschwindet,
ließ sich von außen nicht prüfen; nach dem Speichern auf dem Telefon
nachsehen.

## Schritt 7: Auszahlung prüfen

Hilfe: [Four key actions](https://support.gofundme.com/hc/en-us/articles/13163352843931-Four-key-actions-for-your-GoFundMe-fundraiser)

Im Dashboard unter **Auszahlungen** („Transfers“) nachsehen, ob Bankkonto und
Identität bestätigt sind. GoFundMe nennt eine Frist, bis zu der das erledigt
sein muss; die Prüfung dauert einige Tage.

## Schritt 8: Ansehen, auf dem Telefon und am Rechner

1. Die Kampagnenseite abgemeldet im Browser öffnen (privates Fenster) und auf
   dem eigenen Telefon.
2. Prüfen: Titel, Titelbild (Überschrift, Bohrung und „34,09 mm → 38 mm“ zu sehen),
   Bildreihe in der richtigen Reihenfolge, Geschichte formatiert, Ziel 500 €.
3. Den Link `https://gofund.me/08c5f0edb` an sich selbst per WhatsApp
   schicken: Die Vorschau zeigt das neue Titelbild und den neuen ersten
   Absatz. Zeigt sie noch das alte, liegt es am Zwischenspeicher von WhatsApp
   oder Facebook; das gibt sich nach einiger Zeit.

## Schritt 9: Update 1

Hilfe: [How to post an update](https://support.gofundme.com/hc/en-us/articles/12553895153563-How-to-post-a-GoFundMe-update)

1. Im Dashboard links **Update** → **Neues Update** („New update“).
2. In `kopiervorlage.html` den Abschnitt **Update 1** kopieren, einfügen,
   Fettdruck prüfen wie in Schritt 4.
3. Foto hinzufügen: `bilder/update-1-de.jpg`.
4. **Teilen** („Share“). Das Update geht per E-Mail an alle Unterstützer.
5. Danach an den drei Punkten neben dem Update → **Teilen** → Facebook und
   WhatsApp.

## Schritt 10: Danke sagen

Hilfe: [Thanking and managing donors](https://support.gofundme.com/hc/en-us/articles/205213077-Thanking-and-managing-donors)

1. Dashboard, Reiter **Spenden** („Donations“).
2. Bei jeder der drei Spenden **Danke sagen** („Thank“), Text aus
   `teilen.md`, Abschnitt 10, mit Namen und ein wenig angepasst.

## Schritt 11: Teilen

1. **Angemeldet** auf der Kampagnenseite **Teilen** wählen. So entsteht ein
   eigener Teilen-Link, und im Dashboard steht, welche Spenden darüber kamen
   ([Unique share links](https://support.gofundme.com/hc/en-us/articles/24972788571803-See-your-impact-with-unique-share-links)).
2. Reihenfolge und Texte: `teilen.md`. Zuerst 10 bis 20 Menschen persönlich,
   dann eigenes Profil und YouTube-Kanal, dann Gruppen.
3. **Mitorganisator** (optional): Wer im engsten Kreis gern teilt, kann über
   **Mitorganisatoren einladen** („Invite co-organizers“) helfen, Updates zu
   schreiben und zu danken, ohne Zugriff auf Geld und Geschichte. GoFundMe
   nennt dafür „3x more likely to reach their goal“
   ([Strategies](https://support.gofundme.com/hc/en-us/articles/23377826690715-Strategies-to-help-you-meet-your-fundraising-goal)).

---

## Checkliste

- [ ] Preissatz nur, wenn die Website die Preise zeigt
- [ ] Titel geändert, Link unverändert
- [ ] Titelbild ersetzt, Zuschnitt mittig
- [ ] Fünf Zusatzbilder in der Reihenfolge, alte Zusatzbilder gelöscht
- [ ] Short als Video eingetragen (`/watch?v=-leBJmhdN30`)
- [ ] Geschichte eingefügt, Überschriften fett, keine Sternchen, keine gelbe Markierung
- [ ] Englischer Teil unter dem deutschen, mit fetter Zeile „English“
- [ ] Ziel 500 €, automatische Ziele aus
- [ ] Einstellungen nach der Tabelle, Entscheidung zu monatlichen Spenden getroffen
- [ ] Auszahlung bestätigt
- [ ] Seite auf Telefon und Rechner angesehen, WhatsApp-Vorschau geprüft
- [ ] Update 1 mit Bild gepostet und geteilt
- [ ] Allen bisherigen Spendern gedankt
- [ ] Erste zehn persönliche Nachrichten verschickt
- [ ] Nächstes Update im Kalender (Mittwoch, 30.09.)
