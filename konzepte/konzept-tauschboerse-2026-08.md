# Konzept: die Baustein-Tauschbörse

**Stand:** Entwurf, 30.08.2026 · **Anlass:** Roberts Idee vom 30.08.2026,
erweitert am selben Tag um Liken, Kommentieren und eine gestaltete Galerie ·
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

### 3.2 Moderation: Sichtung vor der Veröffentlichung, aber nicht als Nadelöhr

Drei Wege sind denkbar, und zwei davon scheitern an derselben Stelle.

* **Alles sofort sichtbar, Melden hinterher.** Billig und für einen kleinen
  Anbieter gefährlich: Zwischen dem Hochladen von etwas Rechtswidrigem und dem
  Melden liegt eine Zeit, in der es auf einer Seite steht, die Roberts Namen
  trägt.
* **Jeder Upload wird von Hand gesichtet.** Sicher und unhaltbar — es gibt eine
  Person, und die baut die Anwendung.
* **Gestaffelt.** Der Upload ist sofort da, aber nicht öffentlich: Er bekommt
  eine Adresse, die der Hochladende teilen kann, und erscheint in der Galerie
  erst nach einer Sichtung. Die Sichtung ist ein Klick in einer schlichten
  Liste, und sie kostet Sekunden, weil sie nur zwei Fragen hat: Ist das ein
  Baustein, und ist der Titel in Ordnung?

**Vorschlag: der dritte Weg.** Er hält die Wartezeit für den Hochladenden bei
null — er kann sein Werk sofort weitergeben — und die Galerie bleibt gesichtet.

Der Melden-Weg bleibt trotzdem nötig, denn eine Sichtung sieht dem Rezept nicht
an, ob die Geometrie darin jemandem gehört. Er ist ein Knopf an jeder Kachel
und an jedem Kommentar, und er schreibt eine Mail — dieselbe Mechanik, die
`support.php` schon fährt.

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

**Vorschlag: Browser-Kennung für Likes, E-Mail-Bestätigung für Kommentare und
Uploads.** Das Like ist eine Stimmung, keine Währung — es darf ungefähr sein.
Ein Kommentar und ein Upload sind Beiträge, für die jemand einstehen soll, und
eine Mailadresse ist die leichteste Form davon, die nicht null ist. Die Adresse
wird nicht angezeigt, sie dient dem Melden-Weg und der Rücknahme.

**Was ausdrücklich nicht kommt: ein Konto.** Kein Passwort, keine Anmeldung,
keine Profilseite. Wer seinen Upload später ändern will, bekommt beim Hochladen
einen Link mit einem langen Schlüssel — dieselbe Mechanik, mit der ein
Aktivierungsserver ohne Konto auskommt.

### 3.5 Lizenz: der Hochladende wählt, und die Wahl steht an der Kachel

Ohne Lizenzangabe ist ein hochgeladener Baustein rechtlich unbrauchbar — der
Herunterladende weiß nicht, was er damit darf. Die Frage gehört deshalb in das
Upload-Formular, mit einer kleinen Auswahl statt eines Freitextfelds:

* **CC0** — „nimm es, ohne Bedingungen"
* **CC BY** — „nenne mich"
* **CC BY-SA** — „nenne mich, und gib Änderungen unter derselben Lizenz weiter"

Drei genügen, und alle drei sind bekannt. Die Wahl ist Pflicht, sie steht an
der Kachel und reist in der Datei mit — ein neues Feld im Rezept
(`licence`, `author`), das die Anwendung anzeigt, wenn man einen fremden
Baustein einliest.

**Damit kommt eine Format-Änderung dazu**, und die hat ihre eigene Checkliste
(AGENTS.md, „Dateiformat ändern"): `format_version` erhöhen, Migration
schreiben, alte Beispieldatei einchecken.

### 3.6 Was der Auftrag nicht nennt: ein Rezept kann fremde Geometrie tragen

`Recipe.payloads` ist ein Wörterbuch von Bytes, und der Docstring sagt, wofür:
„Ein Rezept aus einem eingelesenen Modell trägt sein Netz mit — Daten, kein
Code." Für den Transport in einer Projektdatei ist das richtig und nötig.

**Für eine öffentliche Börse ist es zwei Probleme.**

Das erste ist die Größe. Payloads werden base64-kodiert in JSON gelegt (`+33 %`);
ein 5-MB-Netz wird zu knapp 7 MB Datei. `support.php` begrenzt bei 14 MB, und
das ist für eine Mail großzügig — für eine Galerie mit hunderten Einträgen ist
es die falsche Größenordnung.

Das zweite wiegt schwerer: **Wer ein heruntergeladenes STL einliest und als
Rezept hochlädt, verbreitet fremde Geometrie** — womöglich unter einer Lizenz,
die ihm nicht gehört. Die Sichtung sieht das einer Datei nicht an.

Vorschlag, und er ist die einfachste Antwort auf beides:

> **Die Börse nimmt nur Rezepte ohne `payloads`.** Der Server weist eine Datei
> mit eingebetteten Quellen ab, mit einem Satz, der den Grund nennt und den Weg
> zeigt: Ein Baustein, der getauscht werden soll, ist konstruiert und nicht
> eingelesen.

Das ist eine echte Einschränkung, und sie ist zugleich die schärfere
Produktaussage: Was in der Börse steht, ist **gebaut**, nicht mitgebracht. Wer
ein eingelesenes Netz weitergeben will, gibt eine Projektdatei weiter — dafür
ist sie da.

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
* **Der Stil kommt aus den bestehenden Seiten** — dieselben Farben, dieselbe
  Schrift, dieselbe Kachelform wie in der Funktionsübersicht.

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

Dazu eine vierte Grenze, die sich aus 3.6 ergibt: **keine eingelesene Geometrie
in der Börse.**

---

## 6. Schnitt

**Erste Hälfte — die Anwendung.** Export und Import einer Rezept-Datei über den
Katalog, mit den zwei neuen Feldern aus 3.5 (`licence`, `author`) und der
Format-Migration dazu. Klein, prüfbar, für sich nützlich: Wer einen Baustein an
einen Kollegen weitergeben will, kann es danach, auch ohne Börse.

**Zweite Hälfte — die Website.** Upload mit serverseitiger Prüfung (3.1),
gestaffelte Sichtung (3.2), Galerie (4), Likes und Kommentare mit ihren Hürden
(3.3, 3.4). PHP nach dem Muster von `api/support.php` — Größenbegrenzung,
Ratenbegrenzung, `header_safe`, Rate-Datei.

Die Reihenfolge ist nicht beliebig: Die zweite Hälfte braucht das Dateiformat
der ersten, und die erste ist auch ohne die zweite ein fertiges Stück.

---

## 7. Was Robert entscheiden muss

Fünf Fragen, die diese Notiz nicht selbst beantworten kann:

1. **Keine eingebettete Geometrie in der Börse** (3.6) — die Einschränkung ist
   sauber begründet, aber sie nimmt etwas weg. Trägt sie?
2. **Gestaffelte Sichtung** (3.2) — sie kostet Robert einen Klick je Upload.
   Bei zehn Uploads am Tag ist das nichts, bei zweihundert ist es eine Aufgabe.
3. **Mailadresse für Kommentare und Uploads** (3.4) — die niedrigste Hürde, die
   nicht null ist. Oder soll auch das ohne gehen?
4. **Drei Lizenzen** (3.5) — genügen CC0, CC BY und CC BY-SA?
5. **Der Zeitpunkt.** Die erste Hälfte ist klein und könnte vor 0.2.2 fallen;
   die zweite ist ein eigenes Vorhaben mit Serverarbeit, Moderation und
   laufender Pflege. Beides zusammen ist kein Nebenbei.
