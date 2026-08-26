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

## Teil B — Server, Kauffluss, Recht (3d-druck-a2, offen)

Fragen: Was kann das netcup-Hosting (PHP-Version, sodium/ed25519, MySQL/
SQLite, TLS, Rate-Limits)? Wie kommt heute der Schlüssel zum Kunden
(Kauffluss/Paddle → E-Mail?), und wo klinkt sich die Aktivierung ein?
DSGVO: welche Daten liegen beim Aktivieren an (Schlüssel-Hash, Zufalls-ID,
Zeitstempel, IP im Log?), Datenschutzerklärung/EULA-Erweiterung, AVV mit
netcup? Betrieb: Backup der Aktivierungsdatenbank, Monitoring, Verhalten
bei Ausfall, wer spielt Updates ein?

## Teil C — Sicherheitsarchitektur (3d-druck-ce, offen)

Fragen: Bedrohungsmodell (wer ist der Gegner, was ist er wert)?
Endpunkt-Design (activate/deactivate/status — so wenig wie möglich)?
Was darf ein gehackter Server schlimmstenfalls (und wie hält man das
klein)? Replay/Abuse (Rate-Limit je Schlüssel, Aktivierungslimit — wie
viele Maschinen je Lizenz?)? Offline-Challenge-Response-Verfahren im
Detail? Verifikation: Wie testet die Suite das, ohne Netz zu brauchen
(Testart „Anschluss" — die Isolation deckt das Netz heute nicht)?

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
   möglich).
2. Trial lokal lassen oder serverseitig registrieren (Vorschlag: lokal).
3. Bestandsschlüssel-Stichtag.
4. Notfallplan „Firma weg" (signierte Dauer-Freischaltung hinterlegen?).
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
