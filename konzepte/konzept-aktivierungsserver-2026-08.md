# Konzept: Aktivierungsserver

> **Stand: ENTWURF, 26.08.2026 — in Ausarbeitung durch alle vier Sitzungen.**
> Entschieden von Robert ist das *Ob* und die Reihenfolge; offen ist das *Wie*.
> Dieses Dokument sammelt die Ausarbeitung; verbindlich wird davon nichts,
> bevor es Robert abgenommen und der Bauplan (§8/§36) nachgezogen ist.
> Gebaut wird **nicht vor 0.2.0**.

## Die Entscheidungen, von denen dieses Konzept ausgeht

Beide von Robert am 26.08.2026:

1. **Die Testphase ist eine harte Grenze.** Nach den 14 Tagen läuft nichts
   mehr, was einen weiterbringt; Testphase und Kauf laufen über Lizenzen.
   Die lokale Härtung dafür ist gebaut (signierter Marker an zwei Orten,
   `3ef11e6e`) und bleibt auch mit Server die Verteidigung in der Tiefe.
2. **Es kommt ein echter Aktivierungsserver** — auf dem eigenen Webserver
   (netcup, solidon3d.de). Zuerst dieses Konzept, gemeinsam ausgearbeitet.

## Was ein Server kann, was lokal nicht geht

| Fähigkeit | lokal (heute) | mit Server |
|---|---|---|
| Marker editieren erkennen | ja (Unterschrift) | ja |
| Einen Marker-Ort löschen | ja (zweiter Ort heilt) | ja |
| Beide Orte löschen → neue 14 Tage | **nein** (Restgrenze) | ja — Server erinnert die Maschine |
| Geteilten/geleakten Schlüssel begrenzen | nein | ja — Aktivierungen je Schlüssel zählen |
| Erstatteten Schlüssel widerrufen | nein | ja |

## Die Zusage, an der alles hängt: §2

„Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat benutzbar"
steht in `AGENTS.md`, auf der Website und sinngemäß in der EULA. Ein
Aktivierungsserver muss daran vorbeikommen, ohne sie zu brechen. Der Rahmen,
der auszuarbeiten ist:

- **Aktivierung braucht einmal Kontakt, Betrieb nie.** Nach der Aktivierung
  läuft alles offline weiter; keine wiederkehrende Prüfpflicht, kein
  Heartbeat, kein stilles Nach-Hause-Telefonieren (die Telemetrie-Grenze aus
  `kern.md` gilt unverändert: einen Netzzugriff löst der Kunde aus, oder es
  gibt ihn nicht — die bestehende Update-Prüfung beim Start ist deklariert
  und abschaltbar, sie ist die einzige Ausnahme und bleibt es).
- **Ein Offline-Weg existiert** für Kunden ohne Netz am Arbeitsrechner:
  Challenge-Response über einen zweiten Rechner oder E-Mail (Code hin,
  signierte Antwort zurück). Ohne diesen Weg bräche §2 wirklich.
- **Fällt der Server aus, verliert kein Kunde etwas.** Eine einmal erteilte
  Aktivierung gilt lokal weiter; der Server wird nur für *neue* Aktivierungen
  gebraucht. Was passiert, wenn es die Firma nicht mehr gibt, gehört
  beantwortet (Notfall-Freischaltung als signierte Datei auf der Website?).

## Teil A — Kern-Integration (3d-druck-46, ausgearbeitet)

**Zustandsmodell.** `Activation` kennt heute `licence`, `days_left`,
`damaged`, `deadline`. Dazu käme ein maschinengebundenes **Aktivierungs-
zertifikat**: eine vom Server signierte Aussage „Schlüssel K ist auf Maschine
M aktiviert, ausgestellt am T". Die App prüft es offline gegen einen
eingebauten öffentlichen Schlüssel — derselbe ed25519-Weg wie beim
Lizenzschlüssel selbst. `unlocked` verlangte dann Lizenz **und** Zertifikat
(mit Übergangsregel für Bestandsschlüssel, siehe unten).

**Schlüsselkette — der private Hauptschlüssel bleibt offline.** Der Server
darf **nie** den Schlüssel halten, der Lizenzen signiert: Ein gehacktes
Shared Hosting dürfte sonst Lizenzen ausstellen. Stattdessen ein eigenes
Server-Schlüsselpaar nur für Aktivierungszertifikate; sein öffentlicher Teil
reist in der App neben dem bestehenden. Kompromittierung des Servers
erlaubt dann schlimmstenfalls das Ausstellen von Aktivierungen für gültige
Schlüssel — nicht das Erfinden von Lizenzen. Widerruf des Serverschlüssels
über ein App-Update.

**Maschinen-ID.** Nötig für „Aktivierungen je Schlüssel zählen", heikel für
den Datenschutz. Vorschlag: kein Hardware-Fingerabdruck, sondern eine beim
ersten Start **zufällig erzeugte** ID im Profil (UUID). Sie identifiziert
keine Hardware und keinen Menschen; wer das Profil neu aufsetzt, ist eine
neue Maschine — und verbraucht eine Aktivierung, was das Limit trägt.
DSGVO-seitig das mildeste Modell (Pseudonym ohne Personenbezug beim
Aktivieren eines anonymen Schlüssels; Personenbezug entsteht erst über die
Bestellnummer — Teil B).

**Trial über den Server?** Vorschlag: **nein, vorerst nicht.** Die
Testphase serverseitig zu registrieren hieße, dass Testen Netz braucht —
der härteste §2-Konflikt für den geringsten Gewinn (die lokale Härtung
deckt den einfachen Fall; wer Profile neu aufsetzt, um alle zwei Wochen 14
Tage zu schummeln, kauft auch mit Server nicht). Offen für die Runde.

**Vorläufig freigeschaltet — die Lücke, die der Abgleich mit Teil D fand.**
D2 sagt richtig: Der Kein-Netz-Fall darf nichts kosten, die ausstehende
Aktivierung ist keine Sperre, „solange etwas anderes freischaltet". Genau
dieses *solange* hat ein Loch: Wer am letzten Testtag kauft (oder nach dem
Ablauf) und kein Netz hat, hat am Tag darauf nichts anderes mehr — ein
zahlender Kunde wäre gesperrt, der Fall, der heute zweimal Befund war.
Deshalb: **Ein lokal gültiger Schlüssel ohne Zertifikat schaltet vorläufig
frei**, befristet (Vorschlag: 14 Tage ab Eintragen — dieselbe Zahl wie der
Testlauf, leicht zu sagen), mit sichtbarem Zustand „Aktivierung ausstehend —
noch N Tage" und den zwei Knöpfen aus D. Die Frist läuft über dieselbe
gehärtete Marker-Mechanik (signiert, zwei Orte). Ein Kauf ist damit nie
schlechter als kein Kauf, und die Aktivierung bleibt trotzdem keine Formsache.

**Bestandskunden-Migration.** Bereits verkaufte Schlüssel funktionieren
offline weiter (die App kann `purchased_on`/`major` lesen): Schlüssel mit
Kaufdatum vor dem Stichtag der Server-Einführung brauchen kein Zertifikat.
Kein Bestandskunde wird nachträglich zur Aktivierung gezwungen.

**Vier Grenzdateien bleiben vier.** Die Zertifikatsprüfung gehört in
`activation/` (im Cython-Prüfmodul), nicht in neue Grenzstellen.

**Warnschild für den Bauer: `Session.apply` meldet, es wirft nicht.** Es
fängt jeden `AppError` und schickt ihn über `failed` an die Oberfläche — ein
`try` um den Aufruf läuft ins Leere. Genau daran ist am 26.08.2026 ein
Fixversuch gescheitert (die liegengebliebene Quelle nach abgelehntem Import,
`1dbddbb4`): Der Aufrufer bekam keine Ausnahme, es entstand keine Operation,
und von außen sah es aus wie „nichts passiert". Wer den Aktivierungspfad an
die Sitzung anschließt und annimmt, eine Ablehnung komme als Ausnahme an,
baut denselben Fehler noch einmal — dann mit einem Netzaufruf dazwischen.
Gefragt wird nach dem **Ergebnis** (ist die Operation entstanden?), nicht
nach dem Grund.

## Teil B — Server, Kauffluss, Recht (3d-druck-a2, offen)

Fragen: Was kann das netcup-Hosting (PHP-Version, sodium/ed25519, MySQL/
SQLite, TLS, Rate-Limits)? Wie kommt heute der Schlüssel zum Kunden
(Kauffluss/Paddle → E-Mail?), und wo klinkt sich die Aktivierung ein?
DSGVO: welche Daten liegen beim Aktivieren an (Schlüssel-Hash, Zufalls-ID,
Zeitstempel, IP im Log?), Datenschutzerklärung/EULA-Erweiterung, AVV mit
netcup? Betrieb: Backup der Aktivierungsdatenbank, Monitoring, Verhalten
bei Ausfall, wer spielt Updates ein?

## Teil C — Sicherheitsarchitektur (3d-druck-ce, ausgearbeitet)

### C1 — Wer der Gegner ist, und was er wert ist

Ein Schutz, der nicht sagt, gegen wen er steht, schützt gegen alles ein
bisschen. Vier Gegner, nach Häufigkeit sortiert — die Reihenfolge ist die
wichtigste Aussage dieses Abschnitts:

| Gegner | Was er tut | Was er kostet | Was ihn aufhält |
|---|---|---|---|
| **Der Vergessliche** | setzt sein Profil neu auf, will keine 14 neuen Tage | nichts — er ist Kunde | nichts soll ihn aufhalten |
| **Der Sparsame** | schummelt sich alle zwei Wochen 14 neue Tage | einen Kauf, den er nie getätigt hätte | die lokale Härtung (`3ef11e6e`) |
| **Der Teiler** | kauft einmal, gibt den Schlüssel an fünf Kollegen | vier Käufe | das Aktivierungslimit |
| **Der Knacker** | patcht die Binärdatei, verteilt sie | alle Käufe, die dieser Fassung folgen | **nichts, und das gehört gesagt** |

**Der vierte ist der wichtigste, weil er sich nicht abwehren lässt.** Eine
Anwendung, die auf dem Rechner des Angreifers läuft, kann jede Prüfung
verlieren, die auf demselben Rechner stattfindet — das gilt für jede Software
und ist keine Schwäche dieses Entwurfs. Wer dagegen baut, baut Kopierschutz
gegen einen Gegner, den er nicht erreicht, und bezahlt es mit Hürden für die
drei anderen, die er erreicht.

**Daraus folgt der Maßstab für alles Weitere:** Der Server richtet sich gegen
den **Teiler** und, in zweiter Linie, gegen den Sparsamen. Er richtet sich
ausdrücklich **nicht** gegen den Knacker. Jede Maßnahme, die den ehrlichen
Kunden etwas kostet und nur den Knacker aufhielte, ist damit abgelehnt, bevor
sie diskutiert wird.

Und der Vergessliche steht mit Absicht an erster Stelle: Er ist der häufigste
von allen, er hat bezahlt, und jede Reibung trifft ihn zuerst.

### C2 — Was ein gehackter Server anrichten darf

Der Server läuft auf Shared Hosting (Teil B). Von dort ist nichts
auszuschließen — die Frage ist nicht, ob ein Einbruch möglich ist, sondern was
er einbringt.

**Die Trennung aus Teil A ist die tragende Entscheidung**, und sie hält: Der
Server hält ein eigenes Schlüsselpaar, das nur Aktivierungszertifikate
signiert. Der Hauptschlüssel, der Lizenzen signiert, liegt offline bei Robert.
Ein Einbrecher kann damit

- **Aktivierungen ausstellen für Schlüssel, die es gibt** — also die
  Maschinenbindung eines gültigen Schlüssels aufheben,
- die Aktivierungsdatenbank lesen (Schlüssel-Hashes, Zufalls-IDs,
  Rechnernamen, Zeitstempel),

und er kann **nicht**

- Lizenzen erfinden (dafür braucht es den Hauptschlüssel),
- den Testzeitraum verlängern (der ist lokal, Teil A),
- die Anwendung eines Kunden verändern (das Manifest hängt am Hauptschlüssel).

**Der Schaden ist damit gedeckelt auf „ein gültiger Schlüssel verliert seine
Bindung".** Das ist genau der Schaden, den der Teiler ohnehin anrichtet — der
Einbruch macht ihn breiter, nicht schlimmer. Die Datenbank enthält absichtlich
nichts, was einen Menschen benennt (Teil A: Zufalls-ID statt
Hardware-Fingerabdruck, Personenbezug erst über die Bestellnummer in Teil B).

### C3 — Der Widerruf, und warum er ohne Datum nie ausgelöst wird

Ein gestohlener Server-Schlüssel muss sich zurücknehmen lassen, sonst ist der
Einbruch dauerhaft. Der Weg dorthin hat drei Fassungen, und die ersten zwei
sind Sackgassen:

**Erste Fassung — kurze Gültigkeit.** Zertifikate laufen nach N Tagen ab, die
App holt ein neues. Damit wird der Server zur **Betriebsvoraussetzung**, und
§2 ist gebrochen: Wer offline arbeitet, verliert seine Freischaltung, ohne
etwas falsch gemacht zu haben. Abgelehnt.

**Zweite Fassung — unbefristet plus Widerrufsliste.** Das Zertifikat gilt
ewig; die App liest beim ohnehin stattfindenden, deklarierten und
abschaltbaren Update-Check eine Widerrufsliste. Die Liste ist mit dem
**Hauptschlüssel** signiert, nicht mit dem Server-Schlüssel — sonst könnte der
gehackte Server seine eigene Sperrung aufheben. Sie transportiert nur
Widerrufe, nie Pflichten: kein „Zertifikat muss alle N Tage bestätigt werden"
durch die Hintertür.

Das ist richtig und trotzdem unbrauchbar, solange der Widerruf einen
**Schlüssel** trifft: Er nimmt jedem ehrlichen Kunden die Aktivierung, der
seit dem letzten Schlüsselwechsel aktiviert hat. Eine Maßnahme, die im
Ernstfall tausend Kunden sperrt, wird nicht ausgelöst — und eine Waffe, die
man nicht benutzen will, wirkt nicht.

**Dritte Fassung — der Widerruf trägt ein Datum.** Jedes Zertifikat nennt
seinen Ausstellungstag (Teil A: „ausgestellt am T"). Die Liste sagt dann nicht
„Server-Schlüssel S ist tot", sondern **„S ist tot für alles, was nach T
ausgestellt wurde"** — T ist der Einbruchsbeginn aus den Server-Logs. Damit
bleibt jedes Zertifikat vor T gültig, die große Mehrheit merkt nichts, und der
Widerruf wird klein genug, dass man ihn wirklich auslöst.

Zwei Dinge gehören dazu, sonst trägt auch die dritte Fassung nicht:

- **T wird konservativ früh gesetzt.** Wer den Einbruchsbeginn nicht kennt,
  nimmt den frühesten Verdacht. Die wenigen ehrlichen Kunden zwischen T und
  dem Wechsel — Tage, nicht Monate — reaktivieren einmal gegen den sauberen
  Schlüssel.
- **Der Schlüsselwechsel ist ein geübter Vorgang, kein Notfall.** Alte und
  neue Zertifikate gelten während einer Frist parallel, und für den, der von
  allem nichts mitbekommen hat, gibt es denselben Weg wie für jeden anderen:
  den Freischaltdialog aus Teil D. Wer den Ablauf erst im Ernstfall erfindet,
  löst ihn nicht aus.

**Und die Grenze, die bleibt und die ehrlich hingeschrieben gehört:** Die
Liste erreicht nur, wer den Update-Check anhat. Er ist abschaltbar, und das
ist richtig so (§2, `kern.md`). **Die Wirksamkeit des Widerrufs hängt damit an
einer Einstellung, die der Kunde jederzeit umlegen darf.** Wer sie als
lückenlose Abwehr beschreibt, schreibt einen Prospekt. Praktisch trägt sie
trotzdem: Die Population, die einen gestohlenen Schlüssel benutzt, ist nicht
die, die Updates abschaltet — und wer beides tut, ist der Knacker aus C1, den
dieser Entwurf ohnehin nicht erreicht.

### C4 — Drei Endpunkte, und was jeder nicht darf

So wenig Fläche wie möglich. Drei Endpunkte, alle POST, alle über TLS:

| Endpunkt | Nimmt | Gibt | Darf nicht |
|---|---|---|---|
| `activate` | Schlüssel, Zufalls-ID, Rechnername | Zertifikat oder Limit-Liste | keine Daten zurückgeben, die nicht hineingingen |
| `deactivate` | Schlüssel, Zufalls-ID der zu lösenden Maschine | Bestätigung | nicht ohne den Schlüssel arbeiten |
| `list` | Schlüssel | Rechnernamen und Daten der eigenen Aktivierungen | keine fremden Schlüssel sichtbar machen |

**Der Schlüssel ist der Ausweis, und einen zweiten gibt es nicht.** Kein
Konto, kein Passwort, keine Sitzung — das ist die Entscheidung aus Teil D
(„kein Konto, keine Website-Verwaltung"), und sie hat eine Sicherheitsfolge:
Wer den Schlüssel hat, kann alles, was der Besitzer kann, einschließlich
fremde Rechner deaktivieren.

**Das ist bewertet und angenommen** — Teil D fragt ausdrücklich danach. Ein
geteilter Schlüssel führt dazu, dass die Beteiligten sich reihum gegenseitig
hinauswerfen. Das nervt genau die, die ihn teilen, und trifft einen ehrlichen
Kunden nie: Er hat den Schlüssel nur selbst. Ein Schutz dagegen bräuchte ein
Konto, und das kostet jeden ehrlichen Kunden eine Anmeldung — gegen einen
Gegner, der ohnehin schon bezahlt hat.

**Was der Server speichert, steht in Teil B; was er nicht speichert, gehört
hierher:** keine IP über die Log-Rotation hinaus, kein Hardware-Merkmal, kein
Klartext-Schlüssel (nur ein Hash), keine Dateinamen, keine Projektdaten. Ein
Einbrecher soll in der Datenbank nichts finden, was über „dieser anonyme
Schlüssel läuft auf drei anonymen Maschinen" hinausgeht.

### C5 — Replay, Ratenbegrenzung, und der Fall, der keiner ist

**Replay ist hier fast folgenlos**, und das ist eine Eigenschaft des Entwurfs,
nicht ein Zufall: Ein abgefangenes `activate` liefert ein Zertifikat, das auf
**eine bestimmte Zufalls-ID** lautet. Wer es einspielt, schaltet die Maschine
frei, die ohnehin schon freigeschaltet war. Der einzige nutzbare Angriff ist
das Wiedereinspielen eines **alten** Zertifikats nach einem `deactivate` —
dagegen trägt die Widerrufsliste aus C3, und praktisch trägt es sich selbst:
Wer den Platz freigibt und dann das alte Zertifikat behält, hat einen Platz zu
viel und keinen Vorteil, weil das Limit ohnehin nicht bindet, wenn man
deaktivieren kann.

**Ratenbegrenzung** je Schlüssel, nicht je IP: Ein Büro hinter einer Adresse
ist der Normalfall, nicht der Angriff. Vorschlag: fünf `activate` je Schlüssel
und Tag. Wer mehr braucht, hat entweder ein Problem — dann soll er den Support
erreichen und keine Fehlermeldung — oder er probiert Schlüssel durch, und
dafür ist fünf pro Tag zu wenig, um je fündig zu werden.

**Schlüssel zu raten ist ohnehin kein Angriffsweg**, den die Begrenzung tragen
müsste: Ein ed25519-signierter Schlüssel lässt sich nicht erraten, und der
Server prüft die Signatur, bevor er zählt. Die Begrenzung ist gegen Lärm, nicht
gegen Kryptographie.

**Das Aktivierungslimit** ist keine Sicherheits-, sondern eine
Geschäftsentscheidung (offene Frage 1, Vorschlag drei Maschinen). Aus
Sicherheitssicht ist nur eines wichtig: **Es muss sich vom Kunden selbst
auflösen lassen** (Teil D3), sonst wird aus jedem defekten Laptop ein
Support-Fall — und Support-Fälle werden mit Ausnahmen gelöst, und Ausnahmen
sind der Weg, auf dem jede Grenze weich wird.

### C6 — Der Offline-Weg darf weniger

Ohne ihn bräche §2 (siehe oben). Mit ihm entsteht die Gefahr, dass er zum
bequemeren Weg wird — dann ist die Bindung eine Formsache.

**Der Ablauf:** Die App zeigt einen Code, der die Zufalls-ID und den
Schlüssel-Hash trägt. Der Kunde bringt ihn an ein Gerät mit Netz (Website oder
E-Mail an den Support), bekommt eine signierte Antwort und trägt sie ein. Das
ist Challenge-Response, und es ist derselbe Vorgang wie online — nur mit dem
Menschen als Übertragungsweg.

**Drei Eigenschaften halten ihn davon ab, zur Hintertür zu werden:**

1. **Er ist an dieselbe Zufalls-ID gebunden** wie der Online-Weg. Eine
   Offline-Antwort für Maschine M schaltet keine andere frei — sie ist kein
   Generalschlüssel, sondern dasselbe Zertifikat auf einem anderen Weg.
2. **Er zählt gegen dasselbe Limit.** Der Server trägt die Aktivierung ein,
   wenn er die Antwort ausstellt; ob sie per HTTP oder per E-Mail herauskommt,
   ändert daran nichts.
3. **Der Kunde sieht, dass er ihn benutzt hat.** Im Freischaltdialog steht
   „offline freigeschaltet" — nicht als Makel, sondern damit der Zustand
   erklärbar bleibt, wenn später etwas nicht stimmt.

**Was er nicht darf: unbegrenzt gültig sein, ohne dass jemand ihn ausgestellt
hat.** Eine vorsignierte Datei, die auf jeder Maschine schaltet, wäre die
Hintertür — und genau das ist die Bauform, die für „Firma weg" (offene Frage
4) vorgeschlagen wird. **Beides zusammen geht nicht**, und die Entscheidung
gehört Robert: Eine hinterlegte Dauer-Freischaltung ist eine Zusage an Kunden
für den Fall, dass niemand mehr da ist — und zugleich ein Generalschlüssel,
sobald sie existiert. Mein Vorschlag: Sie wird **vorbereitet, aber nicht
ausgeliefert** — als signierte Datei, die im Ernstfall auf die Website kommt.
Solange die Firma da ist, existiert sie nur offline; danach braucht sie
niemand mehr zurückzunehmen.

### C7 — Wie man das prüft, ohne ans Netz zu gehen

**Die Suite darf kein Netz brauchen** (`tests.md`, Isolation). Und sie deckt
es heute nicht ab — das ist ein bekannter Fund: `llm.available()` öffnet in
`test_ui.py` eine echte Verbindung über `socket.create_connection`. Ein
Rechner mit laufendem Ollama misst dort etwas anderes als ein Bauserver. **Wer
einen zweiten Netzpfad baut, baut die Sperre mit**, sonst hat die Suite zwei
Löcher statt einem.

Geprüft wird gegen einen **Doppelgänger** mit der echten API-Oberfläche des
Serverclients — nicht gegen eine Attrappe mit erfundenen Methoden. Der Grund
steht in `oberflaeche.md` bei den pyvista-Widgets: Ein Fake mit `Off()`, das
es nie gab, versteckt den Absturz genauso gut wie die Suite ihn versteckte.

Vier Zusagen, die Tests werden sollen, und jede prüft eine Sache, die sonst
niemand prüft:

1. **Der Kern kommt ohne Netz aus.** `core` importiert und rechnet ohne jeden
   Socket — dieselbe Bauart wie `test_core_isolation.py` für Qt. Ein
   Zertifikat wird **offline** gegen den eingebauten öffentlichen Schlüssel
   geprüft; wenn dafür eine Verbindung nötig wäre, ist der Entwurf falsch.
2. **Genau ein Aufrufer je Endpunkt, und er hängt am Knopf.** Dieselbe Zählung
   wie `tests/test_support.py` sie für `support.send()` macht — was die Grenze
   zur verbotenen Telemetrie hält, ist nicht die Formulierung, sondern diese
   Zahl.
3. **Ein abgelaufenes oder widerrufenes Zertifikat sperrt, ein gültiges
   nicht** — beide Richtungen, wie bei jeder Grenzprüfung in
   `test_licence_boundary.py`. Und: Ein Zertifikat für eine **andere**
   Zufalls-ID schaltet nicht frei.
4. **Der Kein-Netz-Pfad kostet nichts.** Aus Teil D: Der Dialog geht auf, der
   Testzeitraum steht, der Schlüssel liegt abgelegt. Der Konstruktor macht
   keinen Netzaufruf — geprüft mit einem Doppelgänger, der bei Kontakt wirft.

**Und die Testart „Anschluss" ist hier die entscheidende**, nicht die
Einzelprüfung: Was nur an einer Stelle eingelöst wird, wird an dieser Stelle
geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es". Für den
Aktivierungspfad heißt das: Nicht prüfen, dass der Client ein Zertifikat
verarbeiten **kann**, sondern dass die Anwendung nach einem echten
Freischaltvorgang **freigeschaltet ist** — und nach einem abgelehnten nicht.

### C8 — Was dieser Entwurf nicht leistet

Damit es niemand später als Lücke meldet:

- **Gegen einen gepatchten Client hilft nichts davon.** Siehe C1. Wer das
  ändern will, ändert das Produkt, nicht dieses Konzept.
- **Der Widerruf erreicht nur, wer Updates anhat** (C3).
- **Wer den Schlüssel hat, kann fremde Rechner deaktivieren** (C4) — bewusst
  angenommen, weil die Alternative ein Konto wäre.
- **Die Datenbank ist ein Einbruchsziel**, auch wenn wenig darin steht. Was
  darin steht, entscheidet Teil B; was nicht darin stehen soll, steht in C4.
- **Ein Ausfall des Servers verhindert neue Aktivierungen.** Kein laufender
  Kunde verliert etwas (die Zusage aus dem Rahmen oben), aber wer am
  Ausfalltag kauft, wartet — abgefedert durch die vorläufige Freischaltung aus
  Teil A, und das ist der zweite Grund für sie neben dem Kein-Netz-Fall.

## Teil D — Bedienung (3d-druck-43, ausgearbeitet)

**Grundsatz: Der Freischaltdialog bleibt der eine Ort, und das Netz wird ein
Schritt darin — kein Konto, keine Website-Verwaltung.** Der Schlüssel bleibt
das einzige Ausweisdokument; wer ihn hat, kann aktivieren, deaktivieren und
umziehen, alles im Dialog. Eine „Lizenzverwaltung" auf der Website bräuchte
eine Anmeldung, und damit wäre „ohne Konto" gelogen — der Satz steht viermal
auf der Startseite.

### D1 — Der Aktivierungsfluss, Klick für Klick

Heute: einfügen → *Eintragen* → lokale Prüfung, sofort. Mit Server ändert
sich nur, was **nach** der lokalen Prüfung kommt:

1. Kunde fügt den Schlüssel ein (mehrzeiliges Feld, Bestand). *Eintragen*
   bleibt grau mit Grund, bis Text dasteht (Bestand).
2. Klick *Eintragen*: **lokale Prüfungen zuerst** — Format, Unterschrift,
   Hauptversion. Ein Tippfehler erreicht nie das Netz; die bestehenden
   `LicenceKeyError`-Pfade über `show_error` bleiben unverändert.
3. Braucht der Schlüssel ein Zertifikat (Kaufdatum nach Stichtag, Teil A)
   und liegt keines vor: Aktivierung in einem Arbeiter (`leash.Worker`,
   `crashed` verbunden — die Regel aus `oberflaeche.md`). Im `state_label`:
   „Der Schlüssel wird aktiviert …" mit unbestimmtem Balken, **sofort statt
   nach 200 ms** — eine Netzrunde ist sichere Wartezeit, wie beim Schleier
   mit `at_once`. Der Dialog bleibt bedienbar, *Eintragen* ist solange
   gesperrt, *Schließen* bricht ab (eine angefangene Aktivierung ist kein
   halber Export — der Server vollendet oder nicht, die App darf jederzeit
   aufhören zu warten). Zeitbudget ~10 s, dann der Kein-Netz-Pfad.
4. Erfolg: Zertifikat liegt lokal, der Dialog schließt über `accept()` wie
   heute; die Zustandszeile davor zeigt „Freigeschaltet für … (Bestellung …).
   Aktiviert auf diesem Rechner am {date} — {n} von {limit} Rechnern belegt."
   Die Belegungszahl kommt aus der Aktivierungsantwort und wird lokal
   gemerkt, nicht nachgefragt.
5. **Der Dialog telefoniert nie beim Öffnen.** Kein Status-Ping, keine
   Erhebung im Konstruktor: Netzzugriff hängt an genau zwei Knöpfen
   (*Eintragen*, *Diesen Rechner deaktivieren*). Das hält die
   Telemetrie-Grenze messbar — wie bei `support.send()` zählt ein Test die
   Aufrufer je Endpunkt, und es ist je einer, am Knopf.
6. **Kein automatischer Neuversuch beim Start.** Ein abgelegter, noch nicht
   aktivierter Schlüssel ist ein sichtbarer Zustand („Schlüssel eingetragen,
   Aktivierung ausstehend") mit einem Knopf — nicht ein stiller Netzzugriff
   beim Programmstart, den niemand ausgelöst hat.

### D2 — Jeder Fehlerpfad als Handlungsvorschlag (Regel 17)

Alle Texte nach dem Muster des Slicen-Knopfs: `damaged` zuerst, eine
Textquelle je Auskunft, drei Kodierungen an gesperrten Knöpfen.

| Fall | Satzmuster | Handlungen |
|---|---|---|
| Kein Netz / Server weg / Zeit um | „Der Aktivierungsserver war nicht erreichbar — der Schlüssel ist gültig und bleibt eingetragen." | *Erneut versuchen* · *Offline aktivieren …* (Teil C) · *Später* |
| Limit erreicht | „Dieser Schlüssel ist schon auf {limit} Rechnern aktiv." darunter die Liste: Name, Aktivierungsdatum | *{Rechner} deaktivieren* je Zeile — danach läuft die Aktivierung ohne neuen Klick weiter; **keine Bestätigungsfrage** (rücknehmbar, Regel 19) |
| Schlüssel widerrufen | nennt Grund und Bestellnummer | *Support kontaktieren* (Rückmeldedialog) — nicht *Kaufen* als Erstes: wer erstattet hat, weiß es; wer zu Unrecht gesperrt ist, braucht den Support |
| Antwort nicht echt (kaputter Proxy, Manipulation) | „Die Antwort war nicht die des Aktivierungsservers." | *Erneut versuchen* · *Offline aktivieren …* |
| Installation beschädigt | wie heute: `damaged_line()` **vor** allem anderen, Aktivieren gar nicht erst angeboten | Bestand |

Der Kein-Netz-Fall ist der wichtigste: Er darf **nichts kosten**. Der
Schlüssel bleibt abgelegt, der Testzeitraum läuft unverändert weiter, und wer
noch Tage hat, arbeitet einfach weiter — die ausstehende Aktivierung ist ein
Hinweis, keine Sperre, solange etwas anderes freischaltet. Und wenn nichts
anderes mehr freischaltet — Kauf am letzten Testtag, kein Netz —, greift die
**vorläufige Freischaltung** aus Teil A (Entscheidung 8): Der lokal gültige
Schlüssel trägt befristet, der Zustand heißt „Aktivierung ausstehend — noch
N Tage" und zeigt dieselben zwei Knöpfe. Ein Kauf ist damit nie schlechter
als kein Kauf.

### D3 — Umzug und Deaktivieren

- **Beim Aktivieren vergibt der Kunde einen Rechnernamen**, vorbelegt neutral
  („Rechner 2"), frei änderbar — nicht der Hostname als Vorgabe, der trägt
  oft einen Personennamen und läge dann beim Server. Ohne Namen wäre die
  Limit-Liste drei Datumszeilen, und niemand weiß, welcher Eintrag der alte
  Laptop war.
- ***Schlüssel entfernen* wird zu *Diesen Rechner deaktivieren*.** Aus
  Kundensicht ist es eine Handlung („dieser Rechner soll es nicht mehr
  sein"): Sie gibt den Platz beim Server frei **und** entfernt Schlüssel und
  Zertifikat lokal. Ohne Netz tut sie das Lokale und sagt dazu, dass der
  Platz belegt bleibt und sich vom nächsten Rechner aus freigeben lässt —
  kein Blockieren, kein „erst Netz suchen". Zwei getrennte Knöpfe für die
  zwei Hälften wären die sichere Verwechslung.
- **Der tote oder verkaufte alte Rechner braucht keinen Sonderweg:** Der
  Limit-erreicht-Fluss am *neuen* Rechner ist der Weg — Liste ansehen, alten
  Eintrag deaktivieren, Aktivierung läuft weiter. Selbstbedienung mit dem
  Schlüssel als Ausweis; ob das Missbrauch öffnet (geteilter Schlüssel wirft
  reihum den Vorbesitzer raus), bewertet Teil C — aus Bediensicht ist genau
  dieses Wandern das akzeptierte Verhalten eines geteilten Schlüssels, denn
  es nervt beide Beteiligten, ohne einen ehrlichen Kunden je zu treffen.
- **Bestandskunden sehen von allem nichts** (Teil A): Schlüssel vor dem
  Stichtag aktivieren nicht, ihr Dialog verhält sich wie heute.

### D4 — Welche Sätze altern (Fundliste, per Verneinungssuche gemessen)

Die Betriebszusage bleibt wahr — präzisiert wird, dass die **Freischaltung**
einmal Kontakt braucht. Vorschlag für den einen Satz, überall gleich:
„Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat benutzbar;
Netz braucht nur die einmalige Freischaltung (oder ihr Offline-Weg) und die
Update-Prüfung, die Sie selbst auslösen."

| Ort | Satz heute | Was zu tun ist |
|---|---|---|
| `app/core/manual.py:118` | „Ohne Netz, ohne Konto und ohne Sprachmodell …" | präzisieren; erzeugt `website/handbuch.html` und `en/manual.html` mit |
| `AGENTS.md` §2-Fünfzeiler, `README.md` | „Ohne Netz, ohne Konto und ohne KI …" | präzisieren (Doku, kein Katalog) |
| `app/core/activation/store.py` Docstring | „dass Solidon ohne Netz und ohne Konto läuft" | präzisieren, Begründung der Hürde bleibt |
| `website/index.html` (4×: meta, og, JSON-LD, Kacheln) | „ohne Konto, ohne Abo", „ohne Telemetrie" | **bleibt wahr, bleibt stehen** — die Startseite verspricht kein „ohne Netz" |
| Trial-/Demo-Texte im `ActivationDialog` | „… brauchen einen Schlüssel" | bleibt wahr (Schlüssel schließt Aktivierung ein); Handbuchseite „Freischalten" erklärt den Schritt |
| EULA / Datenschutzerklärung | — | Teil B (a2): Aktivierungsdaten benennen |

Dazu eine neue Handbuchseite „Freischalten und Umziehen": Aktivieren,
Offline-Weg Schritt für Schritt, Rechner wechseln, was bei Serverausfall gilt
(nichts — Betrieb läuft lokal weiter).

### Prüfbarkeit (Anschluss an Teil C)

Der Dialog wird gegen eine **Attrappe mit der echten API-Oberfläche** des
Serverclients getestet (die AffineWidget-Lehre: ein Fake mit erfundenen
Methoden versteckt Abstürze). Drei Zusagen als Tests: (1) genau ein Aufrufer
je Netz-Endpunkt, am Knopf — dieselbe Bauart wie `tests/test_support.py`;
(2) der Kein-Netz-Pfad endet mit stehendem Testzeitraum und abgelegtem
Schlüssel; (3) der Konstruktor des Dialogs macht keinen Netzaufruf
(Attrappe, die bei Kontakt wirft).

## Offene Entscheidungen für Robert (nach der Ausarbeitung)

1. Aktivierungslimit je Schlüssel (Vorschlag: 3 Maschinen, Deaktivieren
   möglich). **Teil C5:** Aus Sicherheitssicht ist die Zahl gleichgültig —
   tragend ist allein, dass der Kunde sie selbst auflösen kann. Ein Limit
   ohne Selbstbedienung erzeugt Support-Fälle, und Support-Fälle werden mit
   Ausnahmen gelöst.
2. Trial lokal lassen oder serverseitig registrieren (Vorschlag: lokal).
3. Bestandsschlüssel-Stichtag.
4. Notfallplan „Firma weg" (signierte Dauer-Freischaltung hinterlegen?).
   **Teil C6 schärft die Frage:** Eine Datei, die auf jeder Maschine
   schaltet, ist genau die Hintertür, die der Offline-Weg vermeidet —
   beides zusammen geht nicht. Vorschlag: vorbereiten, aber nicht
   ausliefern; im Ernstfall kommt sie auf die Website.
5. Rechnername beim Aktivieren (Vorschlag: ja, neutral vorbelegt und frei
   änderbar — sonst ist die Limit-Liste drei Datumszeilen ohne Auskunft).
6. *Schlüssel entfernen* und *Deaktivieren* als **ein** Knopf (Vorschlag:
   zusammenlegen, „Diesen Rechner deaktivieren" — ohne Netz nur lokal, mit
   Ansage).
7. Wortlaut der §2-Präzisierung (Vorschlag in Teil D4 — ein Satz, überall
   gleich).
8. Vorläufige Freischaltung ohne Zertifikat (Vorschlag: 14 Tage ab
   Eintragen, sichtbar als „Aktivierung ausstehend" — sonst sperrt der
   Kauf am letzten Testtag ohne Netz einen zahlenden Kunden; Teil A).
