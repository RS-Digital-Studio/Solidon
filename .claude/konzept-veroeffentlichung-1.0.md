# Konzept: Erste Veröffentlichung (Solidon 1.0)

Stand 06.08.2026. Deckt ROADMAP-P8 ab und geht darüber hinaus: die Website
nennt seit ihrer Entstehung ein Bezahlmodell, für das im Code nichts existiert.

Dieses Dokument ist die fachliche SSOT der Veröffentlichung. Der Umsetzungsplan
in §4 referenziert die §§, statt sie zu wiederholen. Jede Ist-Aussage in §1 ist
am Code belegt — die Belegstelle steht dabei.

> **Nachgetragen am 08.08.2026.** Drei Aussagen des Ist-Zustands sind
> überholt, und zwar zum Guten. Sie stehen unten im Wortlaut, damit die
> Begründung nachvollziehbar bleibt; was sich geändert hat, steht als Marke
> daneben.
>
> | §1 sagt | Stand 08.08.2026 |
> |---|---|
> | `constraints.txt` ist nicht im Repository (§1.2) | **erledigt** — versioniert, die CI findet sie |
> | Bezahlung, Testlauf, Aktivierung: es gibt nichts davon (§1.3) | **erledigt** — `app/core/activation/`, `b5b5096`, `TRIAL_DAYS = 14` |
> | Kein EULA, keine AGB, keine Widerrufsbelehrung (§1.3) | **erledigt** — `EULA.md`, `AGB.md`, `WIDERRUF.md`, `6456a95` |
> | Handbuch: achtzehn Seiten (§1.1) | jetzt dreiunddreißig, achtundzwanzig Abbildungen |
> | Anschrift, Hoster, Zahlungsdienstleister fehlen | **weiterhin offen** — die drei Platzhalter tragen einen Entwurfshinweis, den ein Test erzwingt |

---

## §1 Ist-Zustand

### 1.1 Was trägt

| Bereich | Stand | Beleg |
|---|---|---|
| Anwendung | P0–P12 abgeschlossen, drei Hauptwege als Ende-zu-Ende-Tests | `ROADMAP.md` |
| Paketierung | PyInstaller-Spec vollständig, optionale Kerne als `hiddenimports` | `packaging/solidon3d.spec` |
| Installer | Inno-Setup-Skript ohne eigene Werte, Defines aus `branding.py` | `packaging/solidon3d.iss`, `tools/make_installer.py` |
| Symbol | SVG-Quelle, rastert nach ICO und Website-Favicon | `tools/make_icon.py` |
| CI | drei Jobs, Matrix nur bei Tag und Handstart, Signierschritt vorhanden | `.github/workflows/build.yml` |
| Lizenzprüfung | Abhängigkeiten gegen Freigabeliste, Drittlizenzen gepflegt | `tests/test_licences.py`, `THIRD-PARTY-NOTICES.md` |
| Update-Hinweis | fragt `version.json`, lädt nie, standardmäßig aus | `app/core/updates.py` |
| Fehlerbericht | legt Ordner an, verschickt nichts | P8, `ROADMAP.md` |
| Website | zwei Startseiten, Handbuch erzeugt, Stil hell/dunkel | `website/` |
| Beispielprojekte | **acht** (das achte neu und uncommittet) | `app/core/examples.py:66` |
| Handbuch | achtzehn Seiten, Referenzhälfte aus dem Register | `app/core/manual.py` |
| Das Tor | **grün am 06.08.2026**: 2872 Tests, 10 übersprungen, 11 abgewählt; ruff, format und mypy ohne Fund | eigener Lauf |

Das Repository liegt auf GitHub: `RS-Digital-Studio/Solidon`. **Damit ist die
ROADMAP-Aussage „es gibt kein Remote" veraltet** (`ROADMAP.md:526`). 13 lokale
Commits sind nicht gepusht; `origin/main` steht auf `4700309`. Ob die CI dort je
grün gelaufen ist, ließ sich von dieser Maschine aus nicht feststellen — `gh`
ist nicht installiert. **Das ist die erste zu klärende Unbekannte.**

### 1.2 Was im Baum liegt und nicht im Repository

35 geänderte Dateien, drei unversionierte. Zwei davon sind Blocker:

* **`constraints.txt` ist nicht im Repository.** Nicht ignoriert — nur nie
  hinzugefügt (`git check-ignore` findet keine Regel). `CLAUDE.md` nennt die
  Datei für den Erstaufbau, `build.yml` installiert in **fünf** Schritten mit
  `-c constraints.txt`. Auf dem Runner existiert sie nicht: jeder dieser
  Schritte scheitert an einer fehlenden Datei. **Die CI kann in ihrer heutigen
  Form auf `origin/main` nicht grün sein.**
* **Das achte Beispielprojekt** (`dose-mit-deckel.p3d/.svg`) ist unversioniert,
  während `app/core/examples.py` es schon führt. `README.md:41` sagt „sieben
  Beispielprojekte".

### 1.3 Bezahlung, Testlauf, Aktivierung — es gibt nichts davon

Das ist der größte Fund. Die Website verkauft bereits:

> „**14 Tage kostenlos testen**, danach Einmalkauf: **49 € zur Einführung**,
> später 79 € — kein Abo, kein Konto, alle 1.x-Updates inklusive."
> — `website/index.html:31`

Im Code existiert dazu **keine einzige Zeile**. Verifiziert: `licence`/`license`
kommt in `app/` an zehn Stellen vor, alle betreffen die *Abhängigkeits*-Lizenzen
nach §36 (`app/core/knowledge/licences.py`) oder den Dateikopf. Kein
Lizenzschlüssel, keine Frist, keine Kaufabwicklung, kein Ort, an dem ein
Schlüssel gespeichert würde.

Ebenso fehlt der rechtliche Rahmen eines Verkaufs:

* `LICENSE` ist eine Urheberrechtsnotiz („alle Rechte vorbehalten"), **kein
  Endnutzer-Lizenzvertrag**. Was der Käufer für 49 € erwirbt — auf wie vielen
  Geräten, übertragbar oder nicht, welche Updates inbegriffen sind — steht
  nirgends. Der Installer zeigt genau diesen Text als Lizenzseite
  (`solidon3d.iss:27`).
* `website/impressum.html` ist ein Entwurf mit `[STRASSE UND HAUSNUMMER]` und
  `[PLZ UND ORT]`. Eine Anschrift ist nach § 5 DDG Pflicht.
* `website/datenschutz.html` hat `[HOSTER EINTRAGEN]` und kennt keine
  Zahlungsabwicklung.
* Es gibt keine AGB und keine Widerrufsbelehrung.

### 1.4 Was die ROADMAP als offen führt

Nicht veröffentlichungsrelevant, aber der Vollständigkeit wegen: Plattenvorschlag
in der Oberfläche, Bügeln aus der Passung, Prusa/Cura am echten Programm
(`ROADMAP.md:345–353`), Schichtanalyse 1,05 s statt 300 ms (§31, festgehalten,
kein Rückschritt möglich), AppImage und Flatpak fehlen.

**`ROADMAP.md:2033` ist keine offene Stelle mehr**, nur eine nicht abgehakte:
`aa48f10` legt den `Fit` über ein neues `fits`-Feld an `OpResult` an und vergibt
`lid_cavity` und `lid_collar` als Merkmalsnamen. Die Zeile gehört auf `[x]`.

**Keiner dieser Punkte hindert eine 1.0.** Die Leistungslücke wird eine
bekannte Grenze; die drei Funktionslücken sind 1.1-Material.

---

## §2 Design-Entscheidungen

### A — Das Bezahlmodell bleibt, wie die Website es sagt

14 Tage Testlauf, dann Einmalkauf 49 € zur Einführung, später 79 €, alle
1.x-Updates inbegriffen, kein Abo, kein Konto. Es steht öffentlich und ist
stimmig zur Haltung des Produkts.

**Begründung:** Ein Abo bräuchte eine wiederkehrende Prüfung, und die bräuchte
einen Server. „Kein Konto, keine Cloud" (`README.md:29`) ist kein Marketingsatz,
sondern eine Architekturentscheidung, die im ganzen Kern durchgezogen ist.

**Folge für 1.x:** „alle 1.x-Updates inklusive" heißt, der Schlüssel muss eine
Hauptversion binden, nicht eine Punktversion.

### B — Aktivierung offline, über einen signierten Schlüssel

Der Käufer bekommt eine Zeichenkette. Er trägt sie einmal ein. Die Anwendung
prüft die Signatur **auf dem Rechner** und fragt niemanden.

```
SOLIDON3D-1-<base32(nutzlast)>-<base32(signatur)>
Nutzlast: Hauptversion · Kaufdatum · Bestellkennung · Käuferkennung
```

Der private Schlüssel bleibt beim Verkäufer, der öffentliche steht in der
Anwendung.

**Begründung:** Jede Online-Aktivierung bricht ein ausdrückliches Versprechen
(§1.3, `datenschutz.html:39` — „sendet von sich aus keine Daten"), verlangt einen
Dienst mit Verfügbarkeit und macht die Anwendung von seinem Fortbestehen
abhängig. Für ein Einmalkauf-Werkzeug ist das die falsche Seite der Abwägung.

**Verfahren: Ed25519, Verifikation in reinem Python** (~90 Zeilen nach RFC 8032).
Weder `cryptography` noch `pynacl` liegen heute im Baum (geprüft gegen
`constraints.txt` und `licences.toml`); mit dem Eigencode entfällt der
Regel-22-Vorgang, das Paket wächst nicht, und — der eigentliche Grund — der Code
lässt sich mit dem Rest des Prüfmoduls kompilieren (§2 I, H5), was eine
Fremdbibliothek als eigene `.pyd` nicht täte. Seitenkanalfestigkeit ist hier
gleichgültig: auf dem Nutzerrechner liegt nur der *öffentliche* Schlüssel.
Passt zur Haltung von `app/core/paths.py:5` („ohne Zusatzabhängigkeit aufgelöst,
damit die Lizenzliste kurz bleibt").

Geprüft wird gegen die Testvektoren aus RFC 8032 — eine eigene Krypto-Umsetzung
ohne die ist unverantwortlich.

### C — Nach Ablauf bleibt, was liest. Was schreibt, braucht einen Schlüssel

14 Tage ab erstem Start. Danach ist Solidon ein vollständiger Betrachter seiner
eigenen Projekte und nichts weiter.

**Die Linie in einem Satz:** *Was das Dokument ändert oder ein Ergebnis
herausgibt, braucht einen Schlüssel. Was nur liest, nicht.*

Diese Formulierung ist nicht bloß erklärbar, sie ist **an vier Stellen im Kern
prüfbar** statt an einundsiebzig Menüeinträgen — und alle vier liegen im
Datenpfad, nicht an der Oberfläche. Das ist die Voraussetzung für §2 I.

| Nach Ablauf frei | Braucht einen Schlüssel |
|---|---|
| Projekt öffnen, ansehen, navigieren | jede Operation — also jede Transaktion |
| Darstellungsmodi, Schnittebene, Explosionsansicht | Parameter drehen, Passung anlegen, Material setzen |
| Messen und Bemaßen (liegt in der Ansicht, nicht im Dokument) | Export in jedes Format (STL, 3MF, STEP, OBJ, PLY) |
| Prüfbericht, Steckbrief, Analysekarten | Übergabe an den Slicer und Druckdatei speichern |
| Schichtanalyse und Schichtenvorschau | der Chat mit dem Agenten |
| Bausteinkatalog ansehen | einen Baustein setzen |
| Speichern, Undo, Redo | Modell erzeugen (Weg 3) |
| Handbuch, Über-Dialog, Fehlerbericht | |

**Warum Speichern, Undo und Redo frei bleiben:** Eine Testfassung, die
gespeicherte Arbeit einschließt, erzeugt einen verärgerten Nicht-Käufer statt
eines späteren. Wer nichts mehr ändern kann, kann auch nichts kaputt speichern —
die Freigabe kostet nichts und nimmt dem Ablauf die Härte an der einen Stelle,
an der sie niemandem nützt.

**Warum Messen frei bleibt:** Bemaßungen stehen nicht im `Document` (geprüft:
`types.py` kennt kein Bemaßungsfeld, `DocumentChange` führt Parameter,
Passungen, Drucker, Material). Messen ist damit technisch eine Lesefunktion —
und ein Betrachter, der nicht messen darf, ist ein schlechter Betrachter.

**Wie es sich anfühlt (Regel 17, Regel 19):** Die Oberfläche graut gesperrte
Einträge aus und sagt im Hinweistext, warum. Wer es trotzdem auslöst, bekommt
keinen Abbruch, sondern `LicenceRequired` mit zwei Handlungen — „Schlüssel
eintragen" und „Solidon kaufen". Kein Dialog beim Start, keine Zählung im
Fenstertitel, keine Erinnerung am dritten Tag: **einmal** eine Zeile in der
Statusleiste, wenn weniger als drei Tage übrig sind.

### I — Härtung: was erreichbar ist und was nicht

Die Anforderung heißt „nicht knackbar". Das ist bei einer Anwendung, die
vollständig auf dem Rechner des Nutzers läuft und keinen Server fragt, **nicht
vollständig erreichbar** — und zwar nicht, weil Python dekompilierbar ist,
sondern grundsätzlich: wer die Maschine besitzt, auf der der Code läuft, kann
den Code ändern. Das gilt für Photoshop und für jedes Spiel ohne
Online-Zwang. Wer es ausschließen will, braucht eine Serverbindung — und die
widerspricht §2 B und dem Produktversprechen.

Was **vollständig** erreichbar ist, ist die Unmöglichkeit eines Keygens. Das ist
in der Praxis der Unterschied: ein einzelner gepatchter Bau, den jemand
weitergibt, ist ein begrenzter Schaden; ein Schlüsselgenerator im Netz ist das
Ende des Verkaufs. Sechs Stufen, von hart nach abschreckend:

| | Maßnahme | Härte |
|---|---|---|
| **H1** | **Ed25519-Signatur.** Ohne den privaten Schlüssel lässt sich kein gültiger Schlüssel erzeugen — er ist nicht im Paket, also auch nicht daraus zu holen. **Ein Keygen ist unmöglich, nicht schwer.** | kryptografisch |
| **H2** | **Personalisierung.** Der Schlüssel trägt Bestellkennung und Käuferkennung; der Über-Dialog zeigt „Lizenziert für …". Wer teilt, teilt seinen Namen — gegen den realen Fall (Schlüssel im Forum) wirkt das erfahrungsgemäß besser als Technik. | sozial |
| **H3** | **Keine zentrale Weiche.** Vier unabhängige Prüfstellen im Kern, jede holt den Zustand selbst und wirft selbst. Die Oberfläche graut nur vorher aus — sie ist Freundlichkeit, nicht die Hürde. Ein Patch an der Oberfläche bringt nichts. | Aufwand |
| **H4** | **Signiertes Manifest über die eigene Auslieferung.** Die Prüfung deckt die Module, die sie schützt (`history.py`, `writer.py`, `handover.py`, `session.py`) — ein Patch an einer von ihnen fällt auf. | Aufwand |
| **H5** | **Das Prüfmodul wird kompiliert ausgeliefert.** `licence.py` und die Manifestprüfung gehen mit Cython nach C. Damit liegt kein `.pyc` im Paket, das man dekompiliert und um ein `return True` ergänzt; der Angriff wird Binär-Reversing. Neue **Bau**-Abhängigkeit, keine Laufzeitabhängigkeit. | Aufwand |
| **H6** | **Sperrliste.** Bekannt gewordene Schlüssel werden in der nächsten Punktversion abgelehnt — die Liste reist mit dem Update, kein Netz nötig. | laufend |

**Was das zusammen bedeutet:** Kein Keygen (H1, endgültig). Kein
Ein-Byte-Patch am Bytecode (H4, H5). Kein Umgehen an der Oberfläche (H3).
Weitergabe wird unattraktiv und im Wiederholungsfall wirkungslos (H2, H6). Was
bleibt: ein entschlossener Reverse-Engineer mit Werkzeugen und einigen Stunden
kommt an einem gebauten Paket vorbei. Diese Person hätte auch nicht gekauft.

**Was ausdrücklich nicht gebaut wird**, obwohl es „mehr Schutz" wäre: Prüfungen
über das Netz, Hardware-Bindung an die Maschine (bestraft jeden
Rechnerwechsel), versteckte Marker außerhalb des Nutzerprofils, absichtlich
irreführender Code. Der letzte Punkt ist eine Haltungsfrage: ein Programm, das
seinen eigenen Nutzer täuscht, tut es an einer Stelle nicht zum letzten Mal.

**Der Testlaufmarker bleibt umgehbar.** Er liegt im Nutzerprofil, und wer ihn
löscht, hat wieder 14 Tage. Das zu verhindern bräuchte Verstecke im System —
also genau das Verhalten, das Solidon nirgends zeigt. Die Frist ist eine
Erinnerung; die Schwelle für den *dauerhaften* Gebrauch ist H1, und die hält.

### D — Zahlungsabwicklung über einen Merchant of Record

Empfohlen: **Paddle** oder **Lemon Squeezy** (heute Teil von Stripe, weiter als
MoR betrieben). Nicht Stripe direkt.

**Begründung:** Ein MoR wird rechtlich selbst der Verkäufer. Er schuldet die
Umsatzsteuer im Land des Käufers, meldet sie, stellt die Rechnung, klärt die
Widerrufsfrage im Checkout und prüft die Karte gegen Betrug. Bei Direktverkauf
digitaler Güter an Verbraucher in der EU liegt all das beim Verkäufer — samt
OSS-Registrierung und der Frage, wie die Kleinunternehmerregelung sich zu
grenzüberschreitenden B2C-Leistungen verhält. Das ist für einen ersten
Produktverkauf die falsche Baustelle.

**Preis dieser Wahl:** rund 5 % plus Transaktionsgebühr, gegen etwa 1,5 % bei
Stripe. Bei 49 € sind das ungefähr 1,70 € Unterschied je Verkauf — bezahlt für
weggenommene Steuer- und Rechtsarbeit.

**Wie der Schlüssel entsteht:** Der MoR ruft nach dem Kauf eine Adresse auf
(Webhook), oder — ohne jeden Server — man erzeugt vorab einen Vorrat Schlüssel
und lässt den MoR sie ausliefern (Paddle und Lemon Squeezy können das). Der
zweite Weg ist für 1.0 ausreichend und braucht **keine Infrastruktur**.

> ⚠️ Steuer und Recht sind hier nach bestem Wissen zusammengefasst, aber das ist
> keine Rechts- oder Steuerberatung. AGB, Widerrufsbelehrung, EULA und die
> steuerliche Einordnung gehören einmal vor fachliche Augen — der Betrag dafür
> ist gegen das Risiko einer Abmahnung klein.

### E — Signierung: der Schritt in der CI passt nicht mehr zur Wirklichkeit

`build.yml:132` signiert mit `signtool sign /f <pfx> /p <passwort>`, also mit
einer Zertifikatsdatei aus einem Repository-Secret. **Seit Juni 2023 geben die
Zertifizierungsstellen keine Code-Signing-Schlüssel mehr als exportierbare
Datei heraus** — sie liegen auf einem Hardware-Token oder in einem Cloud-HSM.
Ein PFX in einem GitHub-Secret ist damit für ein neu gekauftes Zertifikat kein
möglicher Weg mehr.

Drei Optionen, und keine davon ist gratis:

| Weg | Kosten (Größenordnung, zu prüfen) | SmartScreen |
|---|---|---|
| **Unsigniert** | 0 € | „Unbekannter Herausgeber", Warnung bei jedem Nutzer |
| **Azure Trusted Signing** | ~10 $/Monat | signiert; Reputation baut sich auf. Verlangt Nachweise zum Unternehmen |
| **OV-Zertifikat auf Token/HSM** | ~250–400 €/Jahr | signiert; Reputation baut sich auf. Der Token muss beim Signieren erreichbar sein — CI wird damit unbequem |

**Empfehlung:** Azure Trusted Signing ansehen, weil es ohne Hardware in die CI
passt. Wenn die Voraussetzungen nicht erfüllt sind, für 1.0 **unsigniert
ausliefern und es auf der Download-Seite erklären** — ein Satz „Diese Datei ist
noch nicht signiert, deshalb warnt Windows; hier ist die SHA-256-Prüfsumme"
kostet nichts und ist ehrlicher als eine Warnung ohne Erklärung.

**Der Signierschritt in `build.yml` muss so oder so angefasst werden**: heute
überspringt er sich ohne Secret und wäre mit einem heutigen Zertifikat falsch.

### F — Linux bleibt für 1.0 ein tar.gz

AppImage und Flatpak kommen nach 1.0. Grund: das tar.gz ist gebaut und
funktioniert, die beiden anderen sind je ein eigenes Format mit eigener
Fehlersuche — und die Zielgruppe der ersten Fassung ist Windows.

### G — Version wird 1.0.0

`APP_VERSION` steht auf `"0.0.1"` (`app/branding.py:35`), `pyproject.toml:7`
ebenso. Beide gehen auf `1.0.0`. Das ist eine Zwei-Zeilen-Änderung, hat aber
Folgen: die Zahl reist in **jede** Projektdatei als `app_version` und der
Update-Hinweis vergleicht gegen sie.

### H — Auslieferung der Datei über den eigenen Webspace

Die Setup-Datei liegt auf `solidon3d.de`, nicht als
GitHub-Release-Artefakt. Grund: Das Repository ist privat und soll es bleiben —
ein Release-Anhang daraus wäre nicht öffentlich abrufbar. Die CI hebt das Paket
sieben Tage als Artefakt auf (`build.yml:179`); von dort geht es von Hand auf
den Webspace.

**Bei rund 255 MB je Fassung ist der Platz auf dem Webspace zu prüfen**, bevor
die zweite Fassung dazukommt.

**Berichtigt am 06.08.2026: die Domain existierte nicht.** Der Plan nannte hier
`solidon3d.rsdigital.de` — eine Adresse, die nie jemandem gehört hat. Es gibt
genau eine Domain, `rs-digital.org`, zugleich die primäre Domain des Google
Workspace. Alles läuft jetzt über `solidon3d.rs-digital.org`; damit teilen
Produktseite und Support-Adresse einen Namen, was für den Käufer der
eigentliche Gewinn ist: zwei Domains nebeneinander lesen sich wie Phishing,
besonders bei einer Anwendung, die beim ersten Start ohnehin eine Warnung
auslöst.

**Nachgezogen am 08.08.2026: es wird `solidon3d.de`.** Eine eigene Domain
statt einer Subdomain der Firmendomain — der Gedanke oben bleibt richtig, die
Ausführung wird nur einfacher. Die Zone von `rs-digital.org` liegt in Google
Cloud DNS, die Registrierung bei Squarespace, und keines der beiden Häuser
bietet eine Oberfläche für einen freien A-Record; die Subdomain hätte an
dieser Stelle festgesteckt. Die eigene Domain wird beim Webspace-Anbieter
registriert und dort verwaltet. Die Support-Adresse zieht mit
(`support@solidon3d.de`) — geteilter Name, jetzt der des Produkts.

**Google Workspace liefert keine Dateien aus.** Es ist Mail und
Zusammenarbeit — kein Webspace, kein FTP, kein Ort für eigene HTML-Dateien.
Google Sites (in Workspace enthalten) scheidet ebenfalls aus: es nimmt kein
fertiges HTML entgegen, das erzeugte Handbuch müsste bei jeder Neuerzeugung von
Hand übertragen werden, `version.json` ließe sich nicht unter fester Adresse als
rohes JSON ausliefern, und 255 MB sind kein Anhang. **Ein Webspace ist damit
eine offene Anschaffung, kein vorhandenes Mittel** — siehe §7.

---

## §3 Nicht-Ziele dieser Veröffentlichung

Ausdrücklich **nicht** Teil von 1.0, damit niemand sie nachträglich hineinliest:

* **Kein Konto, kein Nutzerbereich, kein Login.** Ein Schlüssel ist kein Konto.
* **Keine Online-Aktivierung, keine Nutzungszählung, keine Telemetrie.** Auch
  nicht „nur zum Zählen der Installationen".
* **Kein macOS.** Beglaubigung und ein Apple-Programm für 99 $/Jahr, für eine
  Plattform ohne bekannte Nachfrage.
* **Kein automatisches Update.** Der Hinweis bleibt ein Hinweis (§37.2).
* **Kein AppImage, kein Flatpak** (Entscheidung F).
* **Kein Erreichen des Schichtanalyse-Budgets.** 1,05 s statt 300 ms wird eine
  dokumentierte Grenze, kein Blocker.
* **Keine öffentliche Quelloffenlegung.** Das Repository bleibt privat.

---

## §4 Umsetzungsplan

Jedes Paket endet mit grüner Suite und einem Commit. Verifikation je Paket
konkret benannt. Umfang: **S** unter einem halben Tag, **M** ein Tag, **L**
zwei bis drei Tage, **XL** mehr.

### V0 — Hausputz: was im Baum liegt, kommt ins Repository (S)

Das muss zuerst passieren, sonst prüft jeder folgende CI-Lauf einen anderen
Stand als den lokalen.

1. `constraints.txt` hinzufügen (§1.2 — **der eigentliche Blocker**)
2. `dose-mit-deckel.p3d/.svg` hinzufügen
3. `README.md:41` von „sieben" auf „acht Beispielprojekte" ziehen, Tabellenzeile
   ergänzen
4. Die 35 geänderten Dateien in logischen Einheiten committen
5. `ROADMAP.md:526` berichtigen — es gibt ein Remote

**Verifikation:** `/pruefen` grün · `git status` sauber · in einem frischen
Klon in einen Temp-Ordner läuft `pip install -c constraints.txt -e ".[dev,geom,ui,agent,brep]"`
durch.

### V1 — Die CI zum ersten Mal grün sehen (S–M, abhängig von V0)

1. Pushen, den Lauf ansehen. `gh` installieren (`winget install GitHub.cli`) oder
   die Weboberfläche benutzen
2. `workflow_dispatch` von Hand starten: das ist der Lauf, der die
   Drei-Plattform-Matrix **und** die Paketierung anfasst — beides ist nie
   gelaufen
3. Was auftaucht, beheben. Erwartbar: Systembibliotheken auf macOS,
   PyInstaller-Funde auf Linux, Pfadtrennzeichen

**Verifikation:** ein `workflow_dispatch`-Lauf grün über alle drei Plattformen ·
beide Artefakte (Setup-Datei und tar.gz) heruntergeladen und geöffnet.

> Vor V1 ist jede Aussage über die Auslieferung eine Vermutung. Deshalb steht es
> so früh.

### V2 — Rechtstexte und der Kanal (M, davon das meiste Wartezeit)

1. Anschrift in `impressum.html`, USt-IdNr. oder deren Wegfall
2. Hoster in `datenschutz.html`; Abschnitt zur Zahlungsabwicklung ergänzen
   (welcher MoR, welche Daten, welche Rechtsgrundlage) — hängt an D
3. **EULA schreiben** (§1.3): Nutzungsumfang, Geräteanzahl, Weitergabe,
   inbegriffene Updates, Haftung. Er wird die Lizenzseite des Installers und
   liegt auf der Website
4. **AGB und Widerrufsbelehrung** für den Verkauf. Bei einem MoR gelten
   überwiegend dessen Bedingungen — was davon bleibt, ist mit ihm zu klären
5. `support@solidon3d.de` anlegen bzw. Zustellung prüfen. Die Adresse steht an
   fünf Stellen (`branding.py:29`, Über-Dialog, Fehlerbericht, beide
   Startseiten)
6. Die Texte fachlich prüfen lassen (§2 D, Warnkasten)

**Verifikation:** keine `[PLATZHALTER]` mehr in `website/` · Testmail an die
Adresse kommt an · der Installer zeigt den EULA-Text, nicht die
Urheberrechtsnotiz.

### V3 — Der Prüfkern (M)

> **Gebaut am 08.08.2026** (`b5b5096`), mit drei Abweichungen von diesem Plan:
>
> * Das Modul heißt **`app/core/activation/`**, nicht `licence/`. Eine
>   Begründung dafür ist nirgends festgehalten; naheliegend ist die Nähe zu
>   `knowledge/licences.py`, das die *Abhängigkeits*-Lizenzen nach §36 prüft.
> * **`integrity.py` (H4) fehlt** — es stand von Anfang an unter „Aufwand".
> * Der Testlauf liegt in `tests/test_activation.py`, nicht `test_licence.py`.
>
> **Und die Grenze greift noch nicht.** `require()` steht, hat aber keinen
> Aufrufer: ein abgelaufener Testlauf sperrt heute nichts. Das sagt der
> Modulkopf offen, und es ist der Punkt, der vor dem ersten Verkauf zu
> schließen ist — die Startseite verspricht „14 Tage kostenlos testen, danach
> Einmalkauf".

Neues Modul `app/core/activation/`. Kein Qt, keine Dialoge, keine Netzanfrage —
die Kernregeln gelten unverändert.

```
app/core/activation/__init__.py    state(), Licence, LicenceRequired
app/core/activation/ed25519.py     Verifikation nach RFC 8032, reines Python
app/core/activation/key.py         Schlüsselformat: lesen, prüfen, zerlegen
app/core/activation/store.py       Ablage und Testlaufmarker
app/core/activation/integrity.py   signiertes Manifest über die Auslieferung (H4)
```

1. **Ed25519-Verifikation** nach §2 B, gegen die RFC-8032-Testvektoren
2. **Schlüsselformat** nach §2 B; Ablehnung ist immer `LicenceRequired`, nie ein
   nackter `False` — Regel 17 gilt auch hier
3. **`Licence`**: Hauptversion, Kaufdatum, Bestellkennung, Käuferkennung
4. **Ablage: als Datei in `user_config_dir()`** — *Abweichung vom ersten
   Entwurf*, der den System-Schlüsselbund mit Datei-Rückfall vorsah. Zwei
   Gründe, beide beim Bauen aufgefallen: der Lizenzschlüssel ist nicht geheim,
   er ist personalisiert; und ein gesperrter Schlüsselbund fragt beim Start nach
   einem Passwort, wofür ein Lizenzschlüssel der falsche Anlass ist. Der
   Schlüsselbund bleibt dem API-Schlüssel des Nutzers, der wirklich geheim ist
5. **Testlaufmarker** in `user_config_dir()`, erster Start und Restlaufzeit.
   Eine rückwärts gestellte Systemuhr verlängert nichts: gespeichert wird auch
   der höchste je gesehene Zeitpunkt
6. **`state()`** gibt genau drei Zustände: `trial(rest)`, `licensed(licence)`,
   `expired`. Ergebnis wird je Prozess einmal ermittelt und gehalten
7. **Keine Hintertür.** Keine Umgebungsvariable, kein Schalter, keine
   Freigabedatei — die Suite setzt den Zustand über eine Fixture, die das Modul
   patcht. Ein eingebauter Umschalter wäre genau das, was ein Angreifer sucht
8. **`integrity.py`**: signiertes Manifest über die vier geschützten Module (H4)
9. **`tools/make_licence_keys.py`** erzeugt Schlüsselvorräte. Der private
   Schlüssel liegt **nie** im Repository; sein Ablageort steht in §9

**Verifikation:** neue Datei `tests/test_licence.py` —
RFC-8032-Testvektoren gehen durch · gültiger Schlüssel angenommen · um ein
Zeichen verändert abgelehnt · Schlüssel für Hauptversion 2 in 1.x abgelehnt ·
Frist läuft mit gestellter Uhr ab, rückwärts gestellte Uhr verlängert nicht ·
kein Netzzugriff (`socket` blockiert) · `LicenceRequired` trägt zwei
Handlungsvorschläge (`tests/test_errors.py` erfasst es automatisch) ·
`tests/test_core_isolation.py` und `tests/test_licences.py` bleiben grün.

### V4 — Die Grenze im Datenpfad (M)

Die vier Prüfstellen aus §2 C und §2 I H3. Jede holt den Zustand selbst.

1. `scene/history.py` — `apply()` lehnt ab, wenn `expired`. Das deckt **jede**
   Dokumentänderung, weil nichts daran vorbeischreibt (Kernregel)
2. `export/writer.py` — jeder Export
3. `export/handover.py` — Slicer-Übergabe und Druckdatei
4. `agent/session.py` — der Chat
5. `licence/integrity.py` prüft beim ersten Zustandsabruf genau diese vier
   Dateien gegen das Manifest (H4)

**Verifikation:** neue Datei `tests/test_licence_boundary.py` — mit `expired`
lehnen alle vier ab und tragen Vorschläge; **öffnen, auswerten, messen,
Prüfbericht, Analysekarten, Schichtanalyse, speichern, undo/redo laufen
weiter** (das ist die eigentliche Zusicherung aus §2 C, und sie wird Fall für
Fall geprüft) · mit `licensed` verhält sich alles wie heute · die ganze übrige
Suite bleibt grün.

### V4b — Lizenzierung an der Oberfläche (M)

1. Dialog „Solidon freischalten": Feld, Einfügen, Prüfen. Texte über `tr()`,
   beide Sprachen
2. Gesperrte Menüeinträge und Werkzeuge ausgegraut, mit Grund im Hinweistext —
   **vor** dem Klick, nicht danach (§2 C)
3. `LicenceRequired` erscheint mit seinen zwei Handlungen, wenn doch etwas
   auslöst
4. Statusleiste: eine Zeile, wenn weniger als drei Tage übrig sind. Kein
   Startdialog, keine Zählung im Titel
5. Über-Dialog nennt Zustand und „Lizenziert für …" (H2)
6. Die Ersteinrichtung erwähnt den Testlauf in einem Satz — sie fragt nicht nach
   einem Schlüssel, das wäre eine Hürde vor dem ersten Blick

**Verifikation:** `tests/test_ui.py` offscreen — Dialog nimmt an und lehnt ab,
gesperrte Einträge sind ausgegraut · `tests/test_translations.py` grün (Regel
20) · `tests/test_interface_limits.py` weiter gehalten · von Hand: mit
abgelaufener Frist öffnet ein Projekt, dreht sich, misst sich und speichert —
und verliert nichts.

### V4c — Kompilierte Auslieferung des Prüfmoduls (S–M)

H5 aus §2 I. Steht bewusst nach V4b: erst richtig, dann hart.

1. Cython als Bauabhängigkeit (`dev`-Extra), `licence/` als Erweiterung
   übersetzt
2. `packaging/solidon3d.spec` nimmt die Erweiterung statt der Python-Quellen; die
   `.py`-Dateien dürfen **nicht** zusätzlich im Paket landen
3. Manifest beim Bau erzeugen und signieren (H4)

**Verifikation:** im gebauten Paket liegt kein `licence/*.pyc` und keine
`licence/*.py` · ein von Hand verändertes `writer.py` im Paket führt zur
Ablehnung · die Suite läuft weiter gegen die Python-Quellen (Entwicklung bleibt
Python).

### V5 — Kaufabwicklung (M, viel Wartezeit beim Anbieter)

1. Anbieter nach §2 D auswählen und einrichten (Nachweise, Bankverbindung,
   Steuerangaben — das dauert Tage, **also früh anfangen**)
2. Produkt anlegen: 49 € Einführungspreis, MwSt-Behandlung, Widerrufshinweis im
   Checkout
3. Schlüsselvorrat erzeugen und einstellen (§2 D, zweiter Weg)
4. Kaufmail: Schlüssel, Downloadlink, Einlöseanleitung, Supportadresse
5. Einen Kauf durchspielen und Schlüssel einlösen

**Verifikation:** ein echter Testkauf mit eigener Karte, danach storniert · der
gelieferte Schlüssel schaltet ein gebautes Paket frei · die Rechnung enthält
die geforderten Angaben.

### V6 — Bauen, signieren, Installer (S–M)

1. Version auf `1.0.0` (§2 G): `app/branding.py:35` und `pyproject.toml:7`
2. Signierung nach §2 E entscheiden und `build.yml` entsprechend ändern
3. Setup-Datei bauen und **auf einem anderen Rechner** installieren — einem
   ohne Python, ohne die venv, ohne Entwicklerwerkzeuge
4. Dort die drei Wege durchgehen: Beispielprojekt öffnen, exportieren, an den
   Slicer übergeben. Und ohne OpenSCAD/Ollama/ComfyUI prüfen, dass die
   Anwendung das sagt statt zu scheitern
5. SHA-256 der Setup-Datei notieren

**Verifikation:** Installation und Deinstallation auf einem fremden Windows ·
Startmenüeintrag, Symbol, Deinstallationseintrag stimmen · die acht
Beispielprojekte sind da und rechnen · das Handbuch öffnet mit F1.

> Dieser Punkt findet erfahrungsgemäß mehr als alle Tests zusammen: die
> Paketierung sah OCP und V-HACD zuletzt nicht (`ROADMAP.md:515`), und ein
> paketierter Bau kann nichts nachinstallieren.

### V7 — Website fertigstellen (M)

1. Download-Kasten in beiden `index.html` auf die echten Dateien umstellen,
   Prüfsummen daneben, und den Warnhinweis, falls unsigniert (§2 E)
2. Kaufknopf zum MoR-Checkout
3. Eine Seite „Kaufen" oder ein Abschnitt: was man bekommt, was der Testlauf
   kann, wie ein Schlüssel eingelöst wird, EULA verlinkt
4. Subdomain nach `website/README.md:20` einrichten: Subdomain, HTTPS,
   Hochladen, prüfen
5. `version.json` auf `1.0.0` mit `notes`
6. Handbuch neu erzeugen (`tools/make_manual.py`) — die Bilder haben sich
   geändert, und mit dem achten Beispiel auch der Text

**Verifikation:** `https://solidon3d.de/` und `/en/` laden ·
`/version.json` liefert rohes JSON · Download startet und die Prüfsumme stimmt ·
alle Links in beiden Sprachen angeklickt · Update-Hinweis in einer Anwendung mit
`APP_VERSION` 0.9 zeigt 1.0.0 an.

### V8 — Doku nachziehen (S)

1. `README.md`: Version, acht Beispiele, ein Abschnitt zu Testlauf und Kauf
2. `ROADMAP.md`: P8 abschließen, was aus §1.4 bleibt, nach 1.1 verschieben
3. `AGENTS.md`/`CLAUDE.md` nur, wenn V3 ein Muster einführt (Lizenzzustand
   abfragen), dann als Gebietsregel

**Verifikation:** `/pruefen` grün · `/regelcheck` ohne Verstoß.

### V9 — Veröffentlichen (S)

1. Alles committen und pushen, `workflow_dispatch`-Lauf grün
2. Tag `v1.0.0` setzen und pushen — er löst Matrix und Paketierung aus
3. Artefakte holen, Prüfsummen gegen V6 vergleichen, auf den Webspace legen
4. `version.json` **zuletzt** hochladen: vorher zeigte der Update-Hinweis auf
   eine Datei, die noch nicht liegt
5. Selbst kaufen wie ein Kunde: Website, Checkout, Mail, Download, Installation,
   Freischaltung

**Verifikation:** der Kaufweg einmal vollständig von außen gegangen, mit einem
Rechner, der Solidon nie gesehen hat.

### V10 — Danach (nicht Teil von 1.0)

AppImage und Flatpak (§2 F) · die vier offenen Funktionen aus §1.4 · macOS, wenn
jemand fragt · die Leistungslücke der Schichtanalyse, wenn ein kompilierter Kern
gebaut wird.

---

## §5 Reihenfolge

Zwei Ketten, die parallel laufen können — die eine ist Arbeit, die andere
Wartezeit:

```
Technik:  V0 ─▶ V1 ─▶ V3 ─▶ V4 ─▶ V4b ─▶ V4c ─▶ V6 ─▶ V7 ─▶ V8 ─▶ V9
Papier:   V2 ──────────────────────────────────────┘
Anbieter: V5 ─────────────────────────────────────────┘
```

**V0 zuerst, ohne Ausnahme** — solange `constraints.txt` fehlt, prüft die CI
etwas anderes als die Maschine hier.

**V2 und V5 am selben Tag anfangen wie V0.** Postfach, Anbieterprüfung,
Zertifikatsentscheidung und die fachliche Durchsicht der Texte sind Wartezeit,
nicht Arbeit; sie werden zum Blocker, wenn man sie hinten anstellt.

| Paket | Umfang | Blockiert von |
|---|---|---|
| V0 Hausputz | S | — |
| V1 CI grün | S–M | V0 |
| V2 Rechtstexte | M (+ Wartezeit) | Entscheidung D |
| V3 Prüfkern | M | — (B entschieden) |
| V4 Grenze im Datenpfad | M | V3 |
| V4b Oberfläche | M | V4 |
| V4c Kompiliert ausliefern | S–M | V4b |
| V5 Kaufabwicklung | M (+ Wartezeit) | D, V3 |
| V6 Bauen und Installer | S–M | V1, V4c, E |
| V7 Website | M | V6, V2, V5 |
| V8 Doku | S | V4b |
| V9 Veröffentlichen | S | alle |

Summe der Arbeit: rund **zwölf bis sechzehn Arbeitstage**. Die Wartezeiten bei
Anbieter, Zertifikat und fachlicher Durchsicht liegen daneben und bestimmen den
frühesten Termin — realistisch **drei bis fünf Wochen**, wenn V2 und V5 sofort
anlaufen.

---

## §6 Risiken

| Risiko | Wirkung | Rückfalloption |
|---|---|---|
| CI stolpert auf macOS/Linux (nie gelaufen) | V1 dauert länger | Matrix auf Windows+Linux kürzen; macOS ist ohnehin kein Ziel (§3) |
| Kein Signierzertifikat verfügbar (§2 E) | SmartScreen-Warnung schreckt Käufer ab | unsigniert ausliefern, Prüfsumme und Erklärung auf die Download-Seite; nachsignieren in 1.0.1 |
| MoR lehnt ab oder braucht Wochen | V5 blockiert V7 | Verkauf zunächst auf Anfrage per Rechnung, Schlüssel von Hand — die Website nennt die Adresse schon |
| Ein Schlüssel wird öffentlich geteilt | Umsatzverlust | Sperrliste in der nächsten Punktversion; bewusste Folge von §2 C, kein Fehler |
| Reines Python für Ed25519 hat einen Fehler | Falsche Annahme oder Ablehnung | Testvektoren aus RFC 8032 in `tests/test_licence.py`; sonst auf `cryptography` umstellen (Weg 2) |
| Webspace zu klein für 255 MB je Fassung | Download fällt aus | nur die jeweils aktuelle Fassung halten; Objektspeicher prüfen |
| Erster Käufer findet einen Absturz | Ruf beim ersten Eindruck | V6 auf einem fremden Rechner ist genau dagegen; Fehlerbericht ist gebaut |

---

## §7 Entscheidungen und was offen bleibt

**Entschieden am 06.08.2026:**

* **Krypto** (§2 B): Ed25519 in reinem Python, mit RFC-8032-Testvektoren.
  Kompilierbar mit dem Prüfmodul, keine neue Laufzeitabhängigkeit.
* **Härte** (§2 I): sechs Stufen H1–H6. Keygen unmöglich, Bytecode-Patch
  erkannt, Prüfmodul kompiliert. Ausdrücklich nicht: Netzprüfung,
  Hardware-Bindung, irreführender Code.
* **Umfang nach Ablauf** (§2 C): Was liest, bleibt frei — inklusive Messen,
  Speichern und Undo. Was das Dokument ändert oder ein Ergebnis herausgibt,
  braucht einen Schlüssel.

**Entschieden am 06.08.2026, nach einer erwogenen und verworfenen Beta-Stufe:**

* **Keine Beta-Fassung. 1.0 ist die erste öffentliche Fassung.** Erwogen war
  eine 0.9 mit Schlüsseln auf Hauptversion 0 — der Riegel dafür wäre gratis
  gewesen, weil `key.parse` die Hauptversion ohnehin prüft und ein 0er-Schlüssel
  in 1.0.0 von selbst abgelehnt worden wäre. Verworfen aus zwei Gründen. Erstens:
  **der Testlauf ist die Beta schon** — vierzehn Tage kostenlos, danach
  Betrachter; jeder Erstnutzer ist zwei Wochen lang ein Tester, der nichts
  gezahlt hat. Eine eigene Stufe wäre eine zweite Umsetzung derselben Idee, mit
  eigenem Bau, eigener Version und eigenem Schlüsselkreis. Zweitens: Sobald die
  Beta öffentlich über die Website läuft — und anders wollte sie niemand —,
  werden Impressum, Datenschutz und die Signierfrage ohnehin fällig. Gespart
  hätte sie damit nur V5, und dafür den Verkauf um Wochen verschoben.
* **Was die Beta geleistet hätte, leistet stattdessen ein leiser Start.** Seite
  online, Verkauf scharf, aber die ersten Wochen nicht beworben: gezielt ein
  paar Leute darauf, zusehen, 1.0.1 nachschieben, erst dann in die Foren. Das
  fängt genau das ab, was 2913 Tests nicht abdecken — ob jemand anderes die
  Anwendung bedienen kann — und kostet nichts.

**Noch offen:**

1. **Zahlungsanbieter** (§2 D): Paddle, Lemon Squeezy — oder Verkauf auf Anfrage
   für die erste Fassung? *Blockiert V5 und den Kaufknopf in V7.*
2. **Signierung** (§2 E): Azure Trusted Signing, OV-Zertifikat auf Token — oder
   1.0 unsigniert mit Prüfsumme und Erklärung? *Blockiert V6.* **Dringlicher als
   zunächst angenommen:** SmartScreen-Reputation baut sich über Zeit und
   Downloadzahl auf. Wer erst zum Verkaufsstart signiert, fängt bei null an,
   genau wenn Geld fließt — und die Vorsichtigen, deren Urteil am meisten wert
   ist, brechen an „Unbekannter Herausgeber" ab. Bei rund 10 $/Monat für Azure
   Trusted Signing ist das die günstigste Fassung dieser Entscheidung.

3. **Webspace** (§2 H, neu am 06.08.2026): Google Workspace liefert nichts aus,
   und einen Hoster für `rs-digital.org` gibt es bisher nicht nachweislich.
   Gebraucht wird gewöhnlicher Webspace mit SFTP, HTTPS für die Domain und
   Platz für rund 255 MB je Fassung. Die 255 MB schließen die üblichen
   Statik-Dienste aus — Cloudflare Pages deckelt bei 25 MB je Datei, Netlify
   ähnlich. Klassischer Webspace kann es; sonst Seite und Setup-Datei trennen
   und letztere in einen Objektspeicher legen. *Blockiert V7.*

Alle drei sind Einkaufsentscheidungen, keine technischen — die Umsetzung V0–V4c
läuft ohne sie.

---

## §8 Der private Schlüssel

Das einzige Geheimnis des ganzen Verfahrens. Geht er verloren, kann niemand mehr
Schlüssel ausstellen; wird er bekannt, ist H1 wertlos und es braucht eine neue
Hauptversion mit neuem öffentlichen Schlüssel.

* **Nie im Repository.** Kein Ausnahmefall, keine verschlüsselte Fassung „nur
  zum Bauen".
* **Ablage:** Passwortmanager plus eine ausgedruckte Papierfassung an einem
  zweiten Ort. Ein einzelnes Speichermedium ist zu wenig.
* **Er wird nur zum Erzeugen von Schlüsselvorräten gebraucht** — nie beim Bauen,
  nie in der CI. `tools/make_licence_keys.py` liest ihn aus einer Datei, deren
  Pfad als Argument kommt.
* Der öffentliche Schlüssel steht im Quelltext und darf überall stehen.

---

## §9 Fortschritt

| Paket | Status | Commit |
|---|---|---|
| V0 Hausputz | **fertig** — `constraints.txt` und das achte Beispiel liegen im Repository, README auf acht gezogen, vier ROADMAP-Stellen berichtigt | |
| V1 CI grün | offen | |
| V2 Rechtstexte | offen | |
| V3 Prüfkern | **fertig**, Tor grün (2913 Tests) | |
| V4 Grenze im Datenpfad | **fertig** — die vier Prüfstellen rufen `require`, Fall für Fall in `tests/test_licence_boundary.py`; `integrity.py` prüft das Manifest beim ersten Zustandsabruf | c6b5eea |
| V4b Oberfläche | **fertig** — ausgegraute Einträge mit Grund, Chat-Sperre mit Freischalten-Knopf, Statuszeile unter drei Tagen, Über-Dialog „Lizenziert für …", ein Satz in der Ersteinrichtung | 7fe8cb9 |
| V4c Kompiliert ausliefern | **fertig, am Paket belegt** — `tools/build_licence_module.py` (Cython + Bau-Manifest), Spec nimmt die Erweiterungen und legt die Grenzdateien als Quelltext, `build.yml` ruft es vor dem Paketieren. Lokaler PyInstaller-Bau geprüft: kein `activation`-Python im Paket oder PYZ, Manifest deckt die vier Grenzdateien, die Anwendung startet — und ein von Hand verändertes `writer.py` startet gesperrt (kein Testlaufmarker entsteht) | |
| V5 Kaufabwicklung | offen | |
| V6 Bauen und Installer | offen — Version auf 1.0.0; `PUBLIC_KEY` ist seit dem 08.08.2026 gesetzt, der private Teil liegt nach §8 | 19fe09b |
| V7 Website | offen | |
| V8 Doku | offen | |
| V9 Veröffentlichen | offen | |

**Stand nach V4c (08.08.2026):** Die Grenze greift, und sie hält am gebauten
Paket. Ein Schlüssel lässt sich erzeugen, eintragen und prüfen; ein
abgelaufener Testlauf sperrt die vier Stellen im Datenpfad und lässt alles
Lesende offen — beides Fall für Fall in `tests/test_licence_boundary.py`. Der
echte öffentliche Schlüssel steht im Quelltext, der private liegt nach §8
außerhalb. Der Beweis am Paket ist lokal erbracht: kein `activation`-Python
im Ordner oder PYZ, das Manifest deckt die vier Grenzdateien, die Anwendung
startet aus dem Paket — und mit einem von Hand veränderten `writer.py`
startet sie gesperrt, messbar daran, dass kein Testlaufmarker entsteht. Was
bleibt, ist V6 auf einem fremden Rechner ohne Python — der Test der
Paketierung, nicht mehr der Lizenzgrenze.

Zwei Dinge, die beim Bauen aufgefallen sind und im Code als Kommentar stehen:

* **Ein Vorgabewert bindet beim Import.** `parse(text, public_key=PUBLIC_KEY)`
  fror den Schlüssel ein, gegen den geprüft wird — die Suite hat es sofort
  gezeigt. Jetzt `None` und zur Laufzeit gelesen.
* **`WEBSITE_URL` stand an zwei Stellen.** `tools/make_installer.py` trug die
  Adresse selbst, obwohl §37.1 sagt, dass alles Namensbezogene in
  `app/branding.py` steht. Jetzt dort, und der Kaufknopf liest dieselbe.
