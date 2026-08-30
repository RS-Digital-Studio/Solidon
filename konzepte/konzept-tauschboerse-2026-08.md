# Konzept: die Baustein-Tauschbörse

**Stand:** entschieden, nichts gebaut · 30.08.2026 · **Anlass:** Roberts Idee
vom 30.08.2026, erweitert am selben Tag um Liken, Kommentieren und eine
gestaltete Galerie · **Alle fünf offenen Fragen sind beantwortet** (§7) ·
**Register:** ROADMAP.md, Zeile T1

Kunden exportieren eigene Bausteine, laden sie auf der Website hoch, andere
importieren sie. Diese Notiz beantwortet die Fragen, die vor dem ersten
Baustein zu beantworten sind — nicht danach.

---

## 1. Warum das kein neues Fundament braucht

Die Grundlage steht, und sie steht seit dem 24.08.2026 aus einem anderen
Grund. **Ein eigener Baustein ist ein Rezept** (`konzept-befestigungssysteme`
§16): eine Liste registrierter Operationsnamen mit Werten, dazu Parameter,
Merkmalsnamen und ein Beschreibungssatz. Er führt nichts aus. Seine
Sicherheitslage ist die einer Projektdatei, und deshalb hat Robert entschieden,
dass er mitreisen darf, während ein Baustein als `.py` dort bleibt, wo er liegt
(AGENTS.md, Regel 13).

Was daraus schon gebaut ist:

| Stück | Wo | Was es tut |
|---|---|---|
| Rezept als Datenklasse | `knowledge/parts/recipe.py:126` | `name`, `title`, `group`, `document`, `payloads`, `exposed`, `features`, `doc`, `format_version` |
| Verpacken | `recipe.for_container(document)` | je benutztem Rezept sein JSON-Text |
| Aufnehmen | `recipe.adopt_payload(raw, entry)` | liest, prüft, gibt **Befunde** statt abzubrechen |
| Transport | `scene/project.py:338` und `:406` | Rezepte reisen heute in jeder Projektdatei mit |
| Vorrang | gebaute Regel | **lokal schlägt mitgereist**, immer |
| Editor | `ui/recipe_dialog.py` | Titel, Gruppe, Parameter mit Grenzen und Vorgaben |
| Vorschaubild | `parts/preview.py` | wird **gerendert**, nicht gepflegt |

**Der Export ist damit fast nur Dateiarbeit.** `for_container` liefert bereits
genau den JSON-Text, den eine `.solrec`-Datei enthalten würde; `adopt_payload`
nimmt ihn bereits entgegen und meldet eine beschädigte Beilage als Befund statt
das Ganze abzubrechen (Regel 17). Was fehlt, ist ein Dateidialog an beiden
Enden und ein Eintrag im Katalog.

Das ist die kleine Hälfte. Die große ist die Börse — und die ist keine
Erweiterung der Anwendung, sondern ein Stück Website.

---

## 2. Die zwei Teile, und warum sie getrennt bleiben

**(a) Rezept als eigenständige Datei.** In der Anwendung: „Baustein
exportieren …" und „Baustein einlesen …" im Katalog. Eine Datei, ein Baustein.
Kein Netz, kein Konto, kein Server.

**(b) Die Börse auf der Website.** Ein gestalteter Bereich im Stil der übrigen
Seiten: Kacheln mit Vorschaubild, Kategorien und Suche wie im Katalog der
Anwendung, damit beide Orte dieselbe Sprache sprechen. Hochladen, Herunterladen,
Liken, Kommentieren. PHP nach dem Muster von `api/support.php`.

**Die Trennung ist keine Bequemlichkeit, sondern die Zusage aus §2:** Nach der
Freischaltung bleibt Solidon ohne Netz und ohne Konto vollständig nutzbar.
Getauscht wird deshalb **im Browser**, importiert wird **per Datei**. Die
Anwendung bekommt keinen Knopf, der etwas hochlädt, und keinen, der einen
Katalog aus dem Netz zieht. Wer das später will, entscheidet es dann — heute
wäre es ein Bruch mit einem Versprechen, das auf der Website steht.

Nebenwirkung, die für die Sache spricht: Die Börse funktioniert auch für
jemanden, der Solidon gar nicht besitzt. Er sieht, was damit gebaut wird, und
das ist die beste Werbung, die eine Bausteinbibliothek haben kann.

---

## 3. Die harten Fragen

### 3.1 Nur Rezepte, nie Code — und die Prüfung steht auf dem Server

Ein Rezept ist harmlos, **weil** es nur Namen und Zahlen enthält. Diese Aussage
gilt aber nur für eine Datei, die tatsächlich eines ist. Eine Datei, die der
Client für ein Rezept hält, ist keine Zusage — der Client gehört dem
Hochladenden.

**Die Prüfung gehört deshalb auf den Server, und sie prüft nicht auf
Verbotenes, sondern auf Erlaubtes.** Eine Sperrliste („kein `import`, kein
`eval`") ist der falsche Schnitt: Sie muss vollständig sein, um zu wirken, und
niemand kann sie vollständig halten. Eine Erlaubnisliste dagegen ist
abgeschlossen:

* Die Datei ist gültiges JSON und trägt genau die Schlüssel, die
  `Recipe`-Feldern entsprechen — jeder andere Schlüssel wird abgewiesen.
* `format_version` liegt im bekannten Bereich.
* Jeder Eintrag in `ops` nennt einen Operationsnamen aus einer **Liste, die der
  Server kennt**, und Werte, die Zahl, Zeichenkette, Wahrheitswert oder Liste
  davon sind.
* `payloads` sind base64 und werden nach der Dekodierung nur auf Größe und
  Dateiart geprüft, nicht ausgeführt — siehe 3.6.

Diese Liste der Operationsnamen muss von der Anwendung kommen, nicht von Hand
gepflegt werden. Das Register kann sie erzeugen (`REGISTRY.all()`), und der
Baulauf legt sie neben die PHP-Dateien. **Ein von Hand geführtes Verzeichnis
wäre beim nächsten Zuwachs falsch** — dieselbe Falle, die `requires_kind` schon
einmal gestellt hat.

Was der Server damit *nicht* leistet: Er kann nicht wissen, ob die Werte
sinnvoll sind. Ein Rezept mit `length = 1e9` ist formal gültig und praktisch
Unsinn. Das fängt die Anwendung beim Aufnehmen, mit ihren Parametergrenzen —
und dort gehört es hin.

### 3.2 Kunden laden automatisch hoch — was das für die Moderation heißt

**Entschieden von Robert am 30.08.2026: „automatisches hochladen durch
kunden".** Ein Upload ist sofort in der Galerie. Keine Sichtung davor, kein
Klick, der wartet.

Der Entwurf schlug hier einen gestaffelten Weg vor — sofort teilbar, in der
Galerie erst nach einer Sichtung. Der ist zurückgenommen, und die Begründung
dagegen ist gut: Eine Sichtung, die eine Person leisten muss, ist bei zehn
Uploads am Tag nichts und bei zweihundert eine Aufgabe, die dann liegen bleibt.
Ein Nadelöhr, das sich zusetzt, ist schlechter als keines — es hält die Börse
an und niemanden ab.

**Was dadurch die Last trägt, sind drei automatische Stufen und ein Rückweg.**
Sie ersetzen die Person nicht, sie machen sie entbehrlich für den Normalfall:

1. **Die Formatprüfung aus 3.1.** Sie ist ohne Sichtung nicht mehr die zweite
   Verteidigungslinie, sondern die erste und einzige vor der Veröffentlichung.
   Deshalb die Erlaubnisliste: Was der Server nicht kennt, kommt nicht durch.
2. **Grenzen, die eine Flut teuer machen.** Rate je Absender (`support.php`
   fährt zwölf je Stunde), Größe je Datei, Zahl der Uploads je Mailadresse und
   Tag. Eine Börse geht nicht an einem bösen Upload zugrunde, sondern an
   tausend.
3. **Textprüfung an Titel, Beschreibung und Kommentar.** Keine Links, keine
   HTML-Zeichen, Länge begrenzt — dieselbe Behandlung wie in 3.3. Das meiste,
   was eine offene Börse an Müll bekommt, ist Werbung, und Werbung braucht
   einen Link.

**Der Melden-Weg ist damit kein Nachgedanke mehr, sondern der Hauptmechanismus.**
Er steht an jeder Kachel und an jedem Kommentar, er schreibt eine Mail über
dieselbe Mechanik wie `support.php`, und er nennt beim Absenden, was passiert.
Robert bleibt dabei die letzte Instanz — nur nicht mehr vor jedem Upload,
sondern bei dem einen, den jemand meldet.

**Eine Empfehlung, die ich trotzdem aufschreibe**, weil sie den Unterschied
zwischen automatisch und unbeaufsichtigt ausmacht: eine schlichte
Betreiberliste, in der die letzten Uploads mit Vorschaubild untereinander
stehen, und ein Knopf „entfernen" daneben. Kein Freigabe-Nadelöhr — nur der
Blick, den man einmal am Tag über eine Seite wirft. Die Mechanik dafür gibt es
schon: `api/operator.php` nimmt die lokale Support-Verwaltung mit externem
Token an, und dieselbe Tür trägt auch diese Liste.

### 3.3 Kommentare sind Text von Fremden

Das ist der Teil, der die Börse von einem Dateiablageort unterscheidet, und der
Teil mit den meisten Wegen, es falsch zu machen.

* **Gespeichert wird roh, ausgegeben wird maskiert.** Nicht umgekehrt: Wer beim
  Speichern maskiert, hat den Originaltext verloren und maskiert beim zweiten
  Bearbeiten doppelt. `markup.py` geht in der Anwendung denselben Weg.
* **Kein Markup, kein HTML, keine Links.** Ein Kommentar ist ein Absatz Text.
  Wer Bilder oder Formatierung zulässt, hat eine zweite Angriffsfläche und eine
  zweite Moderationsaufgabe.
* **Melden an jedem Kommentar**, und zwar vom ersten Tag. Nachgerüstete
  Meldewege sind der Grund, warum Foren untergehen.
* **Länge begrenzt** (Vorschlag: 1000 Zeichen), Rate begrenzt wie in
  `support.php` (dort 12 Sendungen je Stunde).

### 3.4 Die Identitäts-Hürde — und warum sie niedrig bleiben darf

Likes ohne jede Identität sind beliebig manipulierbar: Wer sie zählt, zählt
Klicks, und Klicks kann man wiederholen. Kommentare ohne Identität sind
schlimmer, weil niemand für sie einsteht.

**Die Anwendung darf dabei nicht helfen.** Sie ist konto- und netzfrei, und ein
Konto einzuführen, um Likes zu zählen, wäre der teuerste denkbare Preis für das
kleinste Feature.

Drei Hürden, aufsteigend:

| Hürde | Kosten für den Kunden | Was sie hält |
|---|---|---|
| gar keine | null | nichts — eine Zahl, die jeder erhöhen kann |
| Browser-Kennung (Cookie/LocalStorage) | null | den ehrlichen Fall; ein Klick je Browser |
| Bestätigung per E-Mail-Adresse | eine Mail | den unehrlichen Fall, bis jemand es ernst meint |

**Entschieden (Robert, 30.08.2026: „die sinnvollste Lösung"): Browser-Kennung
für Likes, E-Mail-Bestätigung für Kommentare und Uploads.**

Das war schon vorher der Vorschlag, und die Entscheidung aus 3.2 macht ihn
zwingend: **Ohne Sichtung vor der Veröffentlichung ist die Mailadresse die
einzige Hürde, die überhaupt noch zwischen einem Upload und der Galerie
steht.** Sie hält niemanden auf, der etwas beitragen will, und sie kostet jeden,
der es hundertmal tun will, hundert Adressen. Das Like ist eine Stimmung, keine Währung — es darf ungefähr sein.
Ein Kommentar und ein Upload sind Beiträge, für die jemand einstehen soll, und
eine Mailadresse ist die leichteste Form davon, die nicht null ist. Die Adresse
wird nicht angezeigt, sie dient dem Melden-Weg und der Rücknahme.

**Was ausdrücklich nicht kommt: ein Konto.** Kein Passwort, keine Anmeldung,
keine Profilseite. Wer seinen Upload später ändern will, bekommt beim Hochladen
einen Link mit einem langen Schlüssel — dieselbe Mechanik, mit der ein
Aktivierungsserver ohne Konto auskommt.

**Und der Datenschutz zieht mit — nicht hinterher** (Auflage aus der Review,
30.08.2026). Beides, was hier entsteht, ist eine Datenverarbeitung: eine
gespeicherte Mailadresse und eine Browser-Kennung. Beides gehört in die
Datenschutzerklärung, bevor der erste Kommentar geschrieben wird, und zwar mit
Zweck, Dauer und Weg zur Löschung. Die Kette dafür existiert:
`tools/make_legal.py` erzeugt `website/datenschutz.html` aus den Quelltexten,
und ein Absatz dort ist derselbe Aufwand wie ein Absatz hier.

Das ist keine Formalie am Rand. Eine Mailadresse zu speichern, ohne es zu
sagen, wäre der einzige Punkt dieses Konzepts, an dem die Anwendung ihr eigenes
Versprechen bräche — sie sammelt nichts, und die Börse darf nicht der Ort
werden, an dem das stillschweigend aufhört.

### 3.5 Lizenz: der Hochladende wählt, und die Wahl steht an der Kachel

Ohne Lizenzangabe ist ein hochgeladener Baustein rechtlich unbrauchbar — der
Herunterladende weiß nicht, was er damit darf. Die Frage gehört deshalb in das
Upload-Formular, mit einer kleinen Auswahl statt eines Freitextfelds:

* **CC0** — „nimm es, ohne Bedingungen"
* **CC BY** — „nenne mich"
* **CC BY-SA** — „nenne mich, und gib Änderungen unter derselben Lizenz weiter"

**Entschieden (Robert, 30.08.2026: „das beste").** Drei genügen, und alle drei
sind bekannt — mehr wäre Auswahl-Lähmung an einer Stelle, an der niemand lange
nachdenken will. CC0 für „nimm es", CC BY für „nenne mich", CC BY-SA für „gib
es unter denselben Bedingungen weiter": Das deckt die drei Haltungen ab, die es
zu dieser Frage gibt. Die Wahl ist Pflicht, sie steht an
der Kachel und reist in der Datei mit — ein neues Feld im Rezept
(`licence`, `author`), das die Anwendung anzeigt, wenn man einen fremden
Baustein einliest.

**Damit kommt eine Format-Änderung dazu**, und die hat ihre eigene Checkliste
(AGENTS.md, „Dateiformat ändern"): `format_version` erhöhen, Migration
schreiben, alte Beispieldatei einchecken.

### 3.6 Ein Rezept kann fremde Geometrie tragen — und trägt sie trotzdem mit

`Recipe.payloads` ist ein Wörterbuch von Bytes, und der Docstring sagt, wofür:
„Ein Rezept aus einem eingelesenen Modell trägt sein Netz mit — Daten, kein
Code."

**Robert hat das am 30.08.2026 entschieden: „die bausteine sollen einfach
sauber exportiert und importiert werden können ohne etwas zu verlieren".** Der
Dateiweg trägt also alles, was zum Baustein gehört, `payloads` eingeschlossen.
Ein Export, der stillschweigend etwas weglässt, wäre die schlechtere Antwort:
Der Empfänger bekäme einen Baustein, der bei ihm anders aussieht als beim
Absender, und niemand sagte ihm, warum.

Der ursprüngliche Entwurf schlug an dieser Stelle das Gegenteil vor — die Börse
solle Rezepte mit eingebetteten Quellen abweisen. Das ist zurückgenommen. Die
zwei Gründe dafür verschwinden damit nicht, sie brauchen nur andere Antworten
als ein Verbot.

**Der erste ist die Größe, und der ist rechenbar.** Payloads werden
base64-kodiert in JSON gelegt (`+33 %`); ein 5-MB-Netz wird zu knapp 7 MB
Datei. Für den Dateiweg ist das gleichgültig — eine Datei ist eine Datei. Für
die Börse ist es eine Grenze, die genannt werden muss, statt am Server
unvermittelt zuzuschlagen:

* Eine Obergrenze je Upload (Vorschlag: **25 MB**, `support.php` liegt bei 14
  für eine Mail), und der Upload-Bereich nennt sie, **bevor** jemand eine Datei
  wählt.
* Die Kachel zeigt die Größe. Wer über eine Mobilverbindung lädt, entscheidet
  selbst.
* Wird es zu viel, ist das eine Server-Frage und keine Formatfrage: Dann
  begrenzt man die Zahl der Uploads je Person, nicht den Inhalt eines
  Bausteins.

**Der zweite ist das Urheberrecht, und der bleibt.** Wer ein heruntergeladenes
STL einliest und als Rezept hochlädt, verbreitet fremde Geometrie — womöglich
unter einer Lizenz, die ihm nicht gehört, und einer Sichtung ist das nicht
anzusehen. Das Verbot hätte diesen Fall ausgeschlossen; ohne Verbot braucht es
drei Stufen, die zusammen tragen:

1. **Die Frage beim Hochladen, nicht im Kleingedruckten.** Trägt das Rezept
   `payloads`, erscheint eine zusätzliche Bestätigung: *„Dieser Baustein
   enthält eingelesene Geometrie. Bestätige, dass sie von dir stammt oder dass
   ihre Lizenz die Weitergabe erlaubt."* Ein Haken, der nur dann auftaucht,
   wenn er nötig ist, wird gelesen — einer, der immer dasteht, nicht.
2. **Die Kachel sagt es.** Ein Baustein mit eingebetteter Geometrie ist
   gekennzeichnet, und die Lizenzangabe aus 3.5 steht daneben. Wer ihn
   herunterlädt, weiß, was er bekommt.
3. **Der Melden-Weg aus 3.2 bleibt der Rückweg.** Er ist gegen diesen Fall
   ohnehin die einzige wirksame Stelle, denn nur der Rechteinhaber erkennt sein
   Werk.

Das ist schwächer als ein Verbot und stärker als Schweigen. Und es hat einen
Vorteil, den das Verbot nicht hatte: Ein Kunde, der ein eigenes Netz einliest —
seinen Scan, sein Foto-Modell — und daraus einen Baustein baut, kann ihn
teilen. Das Verbot hätte ihn mit ausgeschlossen, und er ist der häufigere Fall.

### 3.7 Namenskollisionen und fehlende Operationen

Beides ist im Kern schon entschieden, und beides gehört in die Notiz, weil die
Börse es sichtbar macht.

**Kollision:** „Lokal schlägt mitgereist" ist gebaute Regel. Wer einen fremden
Baustein einliest, der so heißt wie einer seiner eigenen, behält seinen — und
bekommt einen Befund, keinen stillen Tausch. Für den Import aus einer Datei
gilt dasselbe; der Dialog bietet einen anderen Namen an, statt abzulehnen.

**Fehlende Operation:** Ein Rezept nennt Operationsnamen. Hat der Empfänger
eine ältere Fassung, gibt es die Operation nicht, und `adopt` meldet es als
Befund. Für die Börse folgt daraus eine Anzeige: **Die Kachel nennt, ab welcher
Fassung der Baustein läuft.** Die Zahl kann der Server aus den Operationsnamen
ableiten, wenn die Liste aus 3.1 die Fassung mitführt, in der jede Operation
dazukam.

---

## 4. Die Galerie

Robert hat gesagt: „auch die Webseite dann dafür gestalten". Das heißt, der
Bereich ist ein Stück der Website und kein Formular mit Tabelle.

* **Kacheln mit Vorschaubild.** Das Bild rendert die Anwendung ohnehin
  (`parts/preview.py`); es reist als PNG in der Datei mit oder wird beim Upload
  aus ihr erzeugt. Ohne Bild keine Kachel — ein Katalog aus Textzeilen ist der
  Grund, warum der Bausteinkatalog der Anwendung selbst einen Befund hat
  (Design-Durchsicht, „zehn Sekunden Textwüste").
* **Kategorien und Suche wie im Katalog der Anwendung.** Dieselben Gruppen,
  dieselben Wörter. Wer in der Anwendung „Befestigung" sucht, soll auf der
  Website nicht „Fasteners" lesen.
* **Sortierung:** neu, meistgeladen, meistgemocht. Drei genügen.
* **Der Stil kommt aus dem W1-Entwurf, nicht aus den heutigen Seiten.** Robert
  hat am 30.08.2026 die Neugestaltung beauftragt und noch am selben Abend
  klargestellt, was „Website" dabei heißt: **die komplette, von oben bis
  unten** — keine neue Startseite über alten Unterseiten (Register W1,
  Recherche läuft). Eine Galerie im alten Kleid zu bauen hieße, sie zweimal
  zu bauen — und beim zweiten Mal unter Zeitdruck. Wer die Börse angeht, wartet
  auf den Entwurf oder baut sie so, dass die Gestaltung austauschbar bleibt.

---

## 5. Was nicht gebaut wird

Der Bauplan schließt drei Dinge aus, die hier in Reichweite liegen, und alle
drei bleiben ausgeschlossen:

* **Kein Plugin-System.** Genau deshalb Rezepte: Was getauscht wird, sind Daten,
  keine Erweiterungen der Anwendung.
* **Keine Cloud-Ablage von Projekten.** Die Börse trägt Bausteine, keine
  Projekte. Ein Projekt ist die Arbeit des Kunden und bleibt bei ihm.
* **Kein Konto in der Anwendung.** Siehe 3.4. Die Anwendung bleibt netz- und
  kontofrei; getauscht wird im Browser.

Eine vierte Grenze stand im Entwurf und ist **zurückgenommen**: Der erste
Vorschlag wollte eingelesene Geometrie aus der Börse heraushalten. Robert hat
am 30.08.2026 anders entschieden — exportiert und importiert wird, ohne etwas
zu verlieren (3.6). Was an ihre Stelle tritt, sind Kennzeichnung, Größengrenze
und die Bestätigung beim Hochladen.

---

## 6. Schnitt

**Erste Hälfte — die Anwendung.** Export und Import einer Rezept-Datei über den
Katalog, mit den zwei neuen Feldern aus 3.5 (`licence`, `author`) und der
Format-Migration dazu. Klein, prüfbar, für sich nützlich: Wer einen Baustein an
einen Kollegen weitergeben will, kann es danach, auch ohne Börse.

**Zweite Hälfte — die Website.** Upload mit serverseitiger Prüfung (3.1) und
den drei automatischen Stufen, die ohne Sichtung die Last tragen (3.2), Galerie
im W1-Stil (4), Likes und Kommentare mit ihren Hürden (3.3, 3.4). PHP nach dem
Muster von `api/support.php` — Größenbegrenzung, Ratenbegrenzung,
`header_safe`, Rate-Datei. Dazu die Betreiberliste aus 3.2, die kein Nadelöhr
ist, sondern der tägliche Blick.

Die Reihenfolge ist nicht beliebig: Die zweite Hälfte braucht das Dateiformat
der ersten, und die erste ist auch ohne die zweite ein fertiges Stück. **Beide
gehen in 0.2.3** (Robert, 30.08.2026 — 0.2.2 ist seit dem Mittag draußen); die
zweite wartet zusätzlich auf den W1-Entwurf, damit die Galerie nicht zweimal
gebaut wird.

---

## 7. Was Robert entschieden hat

Alle fünf Fragen sind am 30.08.2026 beantwortet — vier von Robert selbst, zwei
davon als Auftrag zurück an den Entwurf.

| | Frage | Antwort |
|---|---|---|
| 1 | Eingebettete Geometrie in der Börse? | **Ja, alles reist mit** — „ohne etwas zu verlieren". Das Verbot aus dem Entwurf ist zurückgenommen; an seine Stelle treten Kennzeichnung, Größengrenze und die Bestätigung beim Hochladen (3.6) |
| 2 | Sichtung vor der Veröffentlichung? | **Nein** — „automatisches hochladen durch kunden". Drei automatische Stufen und der Melden-Weg tragen die Last, dazu eine Betreiberliste als täglicher Blick (3.2) |
| 3 | Identitäts-Hürde? | **„die sinnvollste Lösung"** → Browser-Kennung für Likes, Mailadresse für Kommentare und Uploads. Ohne Sichtung ist sie die einzige Hürde, die bleibt (3.4) |
| 4 | Lizenzen? | **„das beste"** → drei zur Wahl: CC0, CC BY, CC BY-SA (3.5) |
| 5 | Zeitpunkt? | **0.2.3**, beide Hälften — 0.2.2 ist seit dem 30.08. draußen (6) |

**Zwei Entscheidungen haben den Entwurf an seiner wichtigsten Stelle
umgeschrieben, und beide in dieselbe Richtung:** weniger Verbot, mehr
Verantwortung beim Hochladenden. Der Entwurf hatte an zwei Stellen die sichere
Wahl vorgeschlagen — kein fremdes Netz, keine unbesehene Veröffentlichung — und
beide Male die Kosten unterschätzt, die sie auf der anderen Seite verursacht:
Das Verbot hätte den ehrlichen Fall mit ausgeschlossen (den eigenen Scan), und
die Sichtung wäre die Aufgabe gewesen, die als Erste liegen bleibt.

Was daraus für den Bau folgt, steht in 3.1, 3.2 und 3.6: **Die Formatprüfung
auf dem Server ist jetzt die einzige Instanz vor der Veröffentlichung.** Sie
war im Entwurf die zweite Verteidigungslinie und ist die erste geworden. Wer
die Börse baut, fängt bei ihr an.

**Offen bleibt eine Auflage aus der Review**, die keine Frage an Robert ist,
sondern Arbeit: Der Datenschutz zieht mit (3.4) — Mailadresse und
Browser-Kennung gehören in `website/datenschutz.html`, bevor der erste
Kommentar geschrieben wird. Die Kette dafür ist `tools/make_legal.py`.
