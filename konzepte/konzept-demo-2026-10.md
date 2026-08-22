# Konzept: Öffentliche Demo bis 30.10.2026

Stand 12.08.2026, nachrecherchiert am 19.08.2026. Baut auf `konzept-veroeffentlichung-1.0.md` auf und
ändert dessen §7-Entscheidung „keine Beta-Version" — mit Begründung, siehe §2 A.
Dieses Dokument ist die fachliche SSOT der Demo-Phase; alles, was den späteren
Verkauf betrifft, bleibt im Veröffentlichungskonzept.

Der Auftrag in einem Satz: **eine kostenlose, vollständige Version
veröffentlichen, die am 30.10.2026 endet — danach fällt die Entscheidung
zwischen einer zweiten Demo und dem Verkauf von 1.0.**

**Vorgaben vom 12.08.2026 (Robert), im Text eingearbeitet:** Start am
**20.08.2026**. Kein Schlüssel, keine Eingabe — herunterladen, installieren,
es läuft. Download über die Website. Nach neuen Versionen wird **von Hand**
gesucht; automatisch beim Start bleibt eine Option. `support@solidon3d.de`
gibt es bereits.

---

## §1 Ist-Zustand — was schon steht

Der Abstand zur Auslieferung ist kleiner, als er sich anfühlt. Belegt:

| Bereich | Stand | Beleg |
|---|---|---|
| Anwendung | P0–P15 durch, 77 Operationen, drei Hauptwege als Ende-zu-Ende-Tests | `ROADMAP.md` |
| Prüfkern | Ed25519 in reinem Python, RFC-8032-Vektoren, Schlüssel erzeugen/prüfen | `app/core/activation/`, V3 |
| Lizenzgrenze | vier Stellen im Datenpfad rufen `require()`, Fall für Fall geprüft | `tests/test_licence_boundary.py`, V4 |
| Grenze an der Oberfläche | ausgegraute Einträge mit Grund, Freischaltdialog, Über-Dialog | V4b |
| Härtung | Prüfmodul mit Cython kompiliert, signiertes Manifest über vier Grenzdateien, **am Paket belegt** | V4c |
| Paketierung | PyInstaller-Spec, Inno-Setup-Skript, Symbol, tar.gz für Linux; AppImage- und Flatpak-Rezepte ungebaut (20.08.) | `packaging/` |
| CI | drei Plattformen, Matrix bei Tag und Handstart, erster echter Lauf hat vier Funde geliefert und sie sind behoben | `.github/workflows/build.yml` |
| Website | live auf `solidon3d.de`, HTTPS (Let's Encrypt bis 06.11.2026), deutsch und englisch, Handbuch erzeugt | netcup, 08.08.2026 |
| Rechtstexte | Impressum und Datenschutz mit echten Angaben, EULA/AGB/Widerruf als Entwurf mit Warnhinweis | `website/*.html` |
| Handbuch | 33 Seiten, 28 Abbildungen, beide Sprachen, als PDF im Releases-Ordner | `tools/make_manual.py` |

**Was heißt: es fehlt kein Baustein der Anwendung.** Was fehlt, ist der Weg
vom fertigen Programm zum fremden Rechner — und ein Zeitmodell, das es heute
nicht gibt.

### 1.1 Die drei echten Lücken

1. **Der Stichtag existiert nicht.** `store.TRIAL_DAYS = 14` zählt ab dem
   ersten Start. Eine Demo, die am 30.10. für alle endet, ist ein anderes
   Modell und heute nirgends abgebildet — auch der Lizenzschlüssel kennt kein
   Ablaufdatum (`Licence` trägt Hauptversion, Kaufdatum, Bestellkennung,
   Käufer — kein `expires_on`).
2. **Es ist nie ein Paket auf einem fremden Rechner gelaufen.** V6 Punkt 3 aus
   dem Veröffentlichungskonzept ist offen. Der Satz dort gilt unverändert:
   dieser Punkt findet erfahrungsgemäß mehr als alle Tests zusammen.
3. **Es gibt keinen Weg, von Hand nach einer neuen Version zu sehen.**
   `updates.check()` läuft heute nur beim Start und nur, wenn
   `settings.check_for_updates` an ist (Vorgabe: aus) — und meldet sich nur,
   wenn etwas Neueres da ist (`main_window.py:4202` und `:4222`). Ein
   Menüeintrag fehlt, und ohne Rückmeldung in allen drei Fällen (neuer, aktuell,
   nicht erreichbar) wirkt ein solcher Klick tot.

Nicht mehr offen, Stand 12.08.2026: `support@solidon3d.de` ist eingerichtet.
Zu prüfen bleiben SPF/DMARC gegen eine Testmail von außen und der
Auftragsverarbeitungsvertrag bei netcup.

### 1.2 Was der zweite, gründliche Durchgang gefunden hat (12.08.2026)

Der erste Durchgang hat den Stand aus den Unterlagen gelesen. Dieser hier hat
ihn gegen GitHub, den Webserver und die Paketierung geprüft — und dabei fünf
Dinge gefunden, von denen drei den Start am 20.08. betreffen.

**a) Das Repository ist öffentlich.** `RS-Digital-Studio/Formwerk` steht auf
`PUBLIC`. Das Veröffentlichungskonzept sagt an drei Stellen das Gegenteil
(§2 H „privat und soll es bleiben", §3 „keine öffentliche Quelloffenlegung"),
und die Härtungsstufe H5 — das Prüfmodul kompiliert ausliefern, damit niemand
den Bytecode um ein `return True` ergänzt — ist gegenstandslos, solange
derselbe Quelltext daneben zum Lesen liegt. H1 hält weiter (ohne den privaten
Schlüssel entsteht kein gültiger Schlüssel), der Rest nicht. **Das ist eine
Entscheidung, keine Aufgabe** — aber sie gehört getroffen, bevor die Demo
Aufmerksamkeit bringt.

**b) Der Name der Ablage ist noch der alte.** Das Remote zeigt auf
`Formwerk`, nicht auf `Solidon`. Kosmetik, solange das Repository privat wäre;
öffentlich ist es die erste Google-Antwort auf den Produktnamen.

**c) 205 Commits sind nicht gepusht, und der Stand dort ist rot.** `origin/main`
steht auf dem 06.08. Der letzte grüne Lauf war am **02.08.**; seither scheitert
die Suite auf dem Ubuntu-Runner mit einem **Segmentierungsfehler** (Rückgabe
139) in `app/ui/panels.py::show_document`, ausgelöst aus
`tests/test_operation_ui.py`. Lokal läuft dieselbe Datei durch; es ist ein
Qt-Absturz unter der Offscreen-Plattform, kein fehlgeschlagener Test.

Das ist der wichtigste Fund für den Termin: **`package` hängt an `needs:
suite`.** Solange die Suite auf dem Runner stirbt, entsteht kein Artefakt —
also auch kein Download. Der Stand dort ist allerdings 205 Commits alt, und
seither ist an genau diesen Dateien viel gearbeitet worden (unter anderem
„VTK/Qt-Referenzen halten zu lange"). Ob der Absturz noch existiert, weiß
niemand, bevor gepusht wurde. **Deshalb steht der Push jetzt ganz vorn.**

> **Der Push ist nicht mehr das Nadelöhr** (19.08.2026): `git rev-list --count
> origin/main..main` → **0**. Alles ist draußen, `origin/main` steht auf dem
> Tagesstand. Das Repository ist öffentlich und umbenannt
> (`ROADMAP.md:4498–4517`) — die Zusatzbedingung „vorher Fund a) entscheiden"
> ist damit entfallen.
>
> **Der Absturz ist geblieben, aber er sitzt woanders, als hier steht.** Sein
> Ort ist zufällig, weil er kumuliert: Vier Läufe fielen nach 228, 480, 3698
> und 3907 Tests (`ROADMAP.md:5899`, `c1ff696` vom 18.08.). Die Kopftabelle
> der ROADMAP nennt als Rest `tests/test_chat_ui.py`, nicht
> `test_operation_ui.py`. Die Suche nach *der* abstürzenden Datei war deshalb
> falsch angelegt.
>
> Offen bleibt, was zählt: **ein grüner CI-Lauf und ein Artefakt daraus.**
> Ohne grüne Suite kein Paket — dieser Satz gilt unverändert.

**d) Die Setup-Datei ließ sich nicht bauen.** Behoben am 12.08.: Die Spec baute
nach `dist/Solidon`, `tools/make_installer.py` suchte unter `dist/Solidon3D`
und meldete „Kein Bau unter …". Die Umbenennung hatte die Paketierung nie
erreicht — und wäre die Datei entstanden, zeigten Startmenüeintrag und
Deinstallationssymbol auf eine `.exe`, die es unter dem Namen nicht gab. Die
CI trug den alten Namen an vier weiteren Stellen.

**e) Das Handbuch im Paket hatte keine Bilder.** Ebenfalls behoben: Die
Bildschirmfotos unter `app/images/manual/` standen nicht in den `datas`.
`tests/test_packaging.py` hält beide Funde fest — kein zweiter Ort für den
Namen, und jedes Verzeichnis mit Nicht-Python-Dateien muss ins Paket.

### 1.2 Was heute falsch auf der Seite steht

Die Website verkauft „14 Tage kostenlos testen, danach Einmalkauf 49 €". Für
eine Demo bis 30.10. ohne Verkauf ist jede dieser Stellen zu ändern:

```
website/index.html:84, 670        Download-Kasten und Preisliste (deutsch)
website/en/index.html:85, 664     dasselbe englisch
website/agb.html:34, 50           vierzehntägiger Testlauf vor dem Kauf
website/eula.html:39–40           Abschnitt 4 „Testlauf"
website/widerruf.html:28          vierzehn Tage Widerruf — betrifft nur den Kauf
app/ui/first_run.py:119           der Satz in der Ersteinrichtung
app/core/activation/store.py:35   TRIAL_DAYS mit dem Kommentar „steht so auf der Website"
```

---

## §2 Entscheidungen

### A — Die Demo ist die Beta, die am 06.08. verworfen wurde. Sie ist jetzt billiger

Das Veröffentlichungskonzept §7 hat eine 0.9-Beta erwogen und aus zwei Gründen
verworfen: der Testlauf sei die Beta schon, und eine öffentliche Beta mache
Impressum, Datenschutz und Signierfrage ohnehin fällig.

**Der zweite Grund ist seit dem 08.08.2026 entfallen** — Domain, Webspace,
HTTPS, Impressum und Datenschutz stehen. Der erste trägt nicht mehr, sobald
kein Verkauf läuft: ohne Kaufabwicklung ist der Testlauf keine Beta, sondern
eine Sackgasse nach vierzehn Tagen.

Was die Demo dagegen einbringt, ist genau das, was §7 Punkt 2 als dringlich
bezeichnet hat: **SmartScreen-Reputation baut sich über Zeit und Downloadzahl
auf.** Wer erst zum Verkaufsstart signiert und ausliefert, fängt bei null an,
genau wenn Geld fließt. Elf Wochen Demo sind elf Wochen Vorlauf für Reputation,
Feldfunde und die Frage, ob jemand anderes die Anwendung bedienen kann.

### B — Zeitmodell: harter Stichtag, kein Schlüssel, kein Konto

Die Demo endet am **30.10.2026** für alle gleichzeitig. Nicht vierzehn Tage ab
Erststart, nicht verlängerbar, keine Eingabe.

**Herunterladen, installieren, es läuft** — das ist die Vorgabe und zugleich
die Probe für jede Entscheidung in diesem Dokument. Kein Schlüssel, kein
Freischaltfeld beim ersten Start, keine Mail mit einer Zeichenkette darin, kein
Konto. Der Freischaltdialog bleibt im Programm, weil er zu 1.0 gehört; in der
Demo ist er ein Weg, den niemand gehen muss (§2 D nennt, was er dann sagt).

**Begründung:** Ein Stichtag ist die einzige Variante ohne neue Mechanik. Er
ersetzt die Resttageberechnung, nicht die Zustände — `Activation.days_left`
rechnet dann `(30.10. − heute).days`, und alles darüber (`unlocked`,
`in_trial`, `expired`, die vier `require`-Stellen, die ausgegraute Oberfläche)
bleibt unverändert. Ein Ablaufdatum im Schlüsselformat wäre die Alternative;
sie kostet eine Formatversion, ein Erzeugungswerkzeug, eine Verteilung per
Mail und dem Nutzer eine Hürde vor dem ersten Blick — für nichts, was die Demo
braucht.

**Nebenwirkung, die zum Modell passt:** Der Testlaufmarker verliert seine
Bedeutung. Wer `trial.json` löscht, gewinnt in der Demo keinen Tag.

**Wer spät kommt, bekommt weniger.** Das ist ehrlich, solange die Seite den
Stichtag ab Tag eins nennt. Ab dem 24.10. wird der Download durch einen Satz
ersetzt: „Die Demo endet am 30.10. — auf 1.0 warten lohnt sich mehr."

### B2 — Am 31.10. startet die Demo nicht mehr. Kein Betrachtermodus

**Vorgabe vom 12.08.2026.** Das Veröffentlichungskonzept §2 C lässt nach
Ablauf alles Lesende offen — öffnen, drehen, messen, speichern. Für die Demo
gilt das **nicht**: Nach dem 30.10.2026 lässt sie sich nicht mehr starten.

**Begründung:** Eine befristete Demo ist ein Angebot auf Zeit, kein
beschnittenes Produkt. Ein Betrachtermodus, der unbegrenzt weiterläuft, ist
eine zweite kostenlose Version, die niemand gepflegt hat — mit einem Stand,
der beim Erscheinen der 1.0 veraltet ist, und mit einem Fehlerbild, für das
später niemand mehr einen Bau nachschiebt.

**Was das kostet, und was dagegen zu tun ist:** Wer in der Demo gearbeitet
hat, kommt am 31.10. nicht mehr an seine Projekte. Drei Auflagen federn das
ab, und sie sind nicht optional:

1. **Der Nachfolger steht am 30.10. bereit** — 1.0 oder die zweite Demo. Der
   Entscheidungspunkt in §6 ist damit verbindlich, nicht beratend: fällt die
   Entscheidung am 10.10. auf „noch nicht", muss 0.9.5 rechtzeitig gebaut sein.
2. **Der Stopp erklärt sich.** Kein stummer Nichtstart, sondern ein Fenster:
   was abgelaufen ist, wo es weitergeht, **wo die eigenen Projekte liegen** und
   dass sie unverändert bleiben. Eine `.p3d` ist eine ZIP-Datei mit JSON darin;
   das gehört in diese Meldung, weil es die Angst herausnimmt.
3. **Die Website sagt es vorher**, im Download-Kasten und in der FAQ — nicht
   erst die Meldung am 31.10.

**Wo die Sperre greift:** Der Kern kennt den Zustand (`Activation.over`), die
Oberfläche und die Kommandozeile beenden sich beim Start mit der Meldung. Die
vier `require`-Stellen sperren ohnehin — sie bleiben, weil die Verkaufsversion
sie braucht.

### C — Der Stichtag steht in `activation/store.py`, nicht in `branding.py`

`branding.py` liegt im Paket als Klartext; `app/core/activation/` geht seit
V4c mit Cython nach C. Ein Stichtag in `store.py` reist damit in der `.pyd`
und nicht in einer lesbaren Datei daneben.

Das ist kein Sicherheitsargument im engeren Sinn — die Demo ist kostenlos, es
gibt nichts zu umgehen. Es ist eins der Sauberkeit: der Ablauf gehört
fachlich dorthin, wo die Frist heute schon gezählt wird.

**Keine Hintertür** (Veröffentlichungskonzept §2 I, V3.7): Der Stichtag kann
nur sperren, nie öffnen. Keine Umgebungsvariable, kein Schalter, keine
Freigabedatei; die Suite setzt den Zustand weiter über die Fixture.

### D — Version 0.1.0, damit 1.0.0 die Verkaufsversion bleibt

`APP_VERSION` geht auf `0.1.0`, nicht auf `1.0.0`. Drei Folgen, alle
erwünscht:

* **Der Update-Hinweis funktioniert als Nachricht.** Sobald `version.json` auf
  `1.0.0` steht, zeigt jede laufende Demo darauf. Das ist der einzige Weg, die
  Demo-Nutzer ohne Konto und ohne Newsletter zu erreichen — und genau der Fall,
  den V7 als Verifikation vorgesehen hat („Update-Hinweis in einer Anwendung
  mit `APP_VERSION` 0.1 zeigt 1.0.0 an").
* **Ein Kaufschlüssel läuft in der Demo nicht.** `key.parse` prüft
  `licence.major` gegen `current_major()`, und das ist bei 0.1.0 eine Null. Wer
  später kauft, lädt 1.0 — was er ohnehin tun soll, weil die Demo einen
  Stichtag trägt. Der Freischaltdialog muss diesen Satz sagen, statt „gilt für
  eine andere Hauptversion" stehen zu lassen.
* **Demo-Projektdateien tragen `app_version: 0.1.0`.** Sie öffnen in 1.0
  unverändert; die Zahl ist Herkunft, kein Format.

**Wie weitergezählt wird** (entschieden am 14.08.2026): Die letzte Stelle
steigt mit **jedem ausgelieferten Bau** um eins — 0.1.0, 0.1.1, 0.1.2. Die
vorderen Stellen bewegen sich nur bei einer größeren Änderung, und das ist
eine Entscheidung und kein Nebenprodukt des Bauens. Für die Mechanik oben
ändert das nichts: alles hängt an der Null vorn, nicht an den Stellen dahinter.

Die Zahl steht an zwei Orten — `app/branding.py` und `pyproject.toml` — und
bis zum 14.08.2026 hielt die beiden nichts zusammen außer Aufmerksamkeit. Wer
eine drehte und die andere vergaß, lieferte ein Paket, dessen Metadaten eine
andere Version nennen als der Über-Dialog.
`test_the_version_is_the_same_in_both_places_that_carry_it` hält sie jetzt
zusammen. Die erzeugten Seiten ziehen ohnehin von selbst nach:
`tools/make_manual.py` liest `APP_VERSION` fürs Deckblatt, `tools/make_legal.py`
holt die Version aus `EULA.md`, und `website/version.json` wird von Hand
gesetzt, weil es die *angebotene* Version nennt und nicht die gebaute.

### E — Vollständig heißt vollständig

Keine Wasserzeichen, keine Exportsperre, keine gesperrte Operation, kein
gedrosseltes Netz. Die Demo ist die Verkaufsversion mit einem Enddatum. Alles
andere wäre eine zweite Auslieferungsvariante mit eigener Fehlersuche — und es
widerspräche dem Satz, der seit dem ersten Tag auf der Seite steht.

**Eine Reibung bleibt und ist keine Beschneidung:** Der Chat braucht ein
Sprachmodell — entweder Ollama lokal oder einen eigenen API-Schlüssel. Für
jemanden, der die Demo aus Neugier lädt, ist das die höchste Schwelle im ganzen
Programm. Die Startseite der Anwendung soll deshalb sagen, was ohne Modell geht
(alles außer dem Chat) und welcher Weg der kürzeste ist (Ollama, ein Befehl).

### F — Sichtbare Restlaufzeit, bewusst abweichend von §2 C des Veröffentlichungskonzepts

Dort steht: keine Zählung im Fenstertitel, eine Zeile in der Statusleiste erst
unter drei Tagen. Das ist für ein Kaufprodukt richtig — eine Frist, die einen
täglich anspricht, ist Druck.

Für eine Demo dreht sich das um: Wer nicht weiß, dass am 30.10. Schluss ist,
fängt am 28.10. ein Projekt an. Deshalb **dauerhaft eine ruhige Zeile in der
Statusleiste** („Demo — noch 47 Tage") und der Stichtag im Über-Dialog. Kein
Startdialog, kein Zähler im Titel, keine Erinnerung, die sich in den Vordergrund
schiebt.

Mit dem harten Stopp aus §2 B2 ist diese Zeile keine Höflichkeit mehr, sondern
die Zusage, dass niemand überrascht wird. Sie ist der Grund, warum es beim
Ablauf keinen Vorwurf gibt: es stand jeden Tag da.

### G — Nach neuen Versionen wird von Hand gesucht; automatisch ist eine Option

`settings.check_for_updates` steht auf `False` und bleibt es. Die Ersteinrichtung
bekommt **keine** zusätzliche Frage — sie wäre genau die Hürde, die „installieren
und es läuft" nicht haben soll.

Stattdessen: ein Menüeintrag **„Nach einer neuen Version sehen"** unter Hilfe,
der jederzeit fragt und in **allen drei** Fällen antwortet — es gibt eine neuere
Version (mit Nummer und Adresse), es gibt keine, oder die Seite war nicht
erreichbar. Heute schweigt die Prüfung in den letzten beiden Fällen
(`main_window.py:4222`); beim automatischen Lauf beim Start ist das richtig, bei
einem Klick wäre es ein toter Knopf.

**Die Folge ist zu benennen:** Wer die Option nicht einschaltet und nicht von
sich aus nachsieht, erfährt vom Erscheinen der 1.0 nichts aus dem Programm.
Deshalb trägt die Demo den Stichtag selbst — dauerhaft in der Statusleiste (§2 F),
im Über-Dialog, und nach dem 30.10. in der Meldung, die jede gesperrte Handlung
auslöst, samt Adresse der Website. Das Programm sagt, woran man ist, ohne zu
fragen und ohne zu funken.

Der Datenschutztext bekommt trotzdem seinen Absatz zur Abfrage: welche Daten
(IP und Zeitpunkt im Server-Log von netcup), wann sie anfallen — nur auf Klick
oder bei eingeschalteter Option —, wie lange sie bleiben.

### H — Kein Verkauf während der Demo. Paddle läuft trotzdem parallel an

Die Demo verkauft nichts. Das entlastet die Rechtsseite erheblich: ohne
entgeltlichen Vertrag greift die Widerrufsbelehrung nicht, und die AGB
beschreiben einen Vorgang, den es noch nicht gibt.

**Trotzdem wird das Paddle-Konto in Woche eins beantragt** (V5). Nachweise,
Bankverbindung und Steuerangaben dauern Tage bis Wochen; wer damit erst am
30.10. anfängt, verschiebt den Verkauf in den Dezember.

---

## §3 Was fehlt — die Arbeitspakete

Umfang wie im Veröffentlichungskonzept: **S** unter einem halben Tag, **M** ein
Tag, **L** zwei bis drei Tage. Jedes Paket endet mit grüner Suite und einem
Commit.

### D0 — Der Stichtag im Kern (S)

1. `store.py`: `DEMO_UNTIL: Final = date(2026, 10, 30)` und `days_left()`, das
   je nach Stichtag die Demo- oder die Testlaufrestzeit liefert.
   `trial_days_left()` bleibt unangetastet, damit die Verkaufsversion ohne
   Rückbau daraus entsteht (`DEMO_UNTIL = None` schaltet auf die Frist zurück)
2. `activation.__init__._determine()` nimmt `days_left()`, wo heute
   `trial_days_left()` steht
3. **`Activation.over`** — wahr, wenn ein Stichtag gesetzt und verstrichen ist
   (§2 B2). Der einzige neue Zustand; `expired` bleibt, was es war, weil die
   Verkaufsversion es unverändert braucht
4. Ein Test koppelt beides an die Version: **eine 1.x-Version darf keinen
   Stichtag tragen.** Sonst liefert ein unachtsamer Bau die Verkaufsversion mit
   Ablaufdatum aus — der teuerste Fehler, den dieses Paket zulässt

**Abnahme:** `tests/test_activation.py` — vor dem Stichtag offen, **am**
Stichtag offen, am Tag darauf `over`; eine zurückgestellte Uhr ändert nichts am
Stichtag; ein gelöschter Testlaufmarker verlängert nichts · mit
`DEMO_UNTIL = None` verhält sich alles wie heute (die Testlauftests laufen
unverändert weiter) · `tests/test_licence_boundary.py` bleibt Fall für Fall
grün, in beide Richtungen.

### D1 — Version und Kennzeichnung (S) — **erledigt, mit anderer Zahl**

`app/branding.py` und `pyproject.toml` auf `0.1.0`. `website/version.json`
bleibt zunächst auf dem Demo-Stand — es wird erst zum Schluss angefasst (§4).

**Abnahme:** `tests/test_website.py` und der Versionstest grün · eine erzeugte
Projektdatei trägt `app_version: 0.1.0`.

> **Hier stand `0.9.0`, und das war seit dem 14.08.2026 überholt.** Robert hat
> die Version auf **0.1.0** heruntergesetzt (`ROADMAP.md:4526`); sie steht
> heute an sieben Stellen so — `app/branding.py:68`, `pyproject.toml:7`,
> `website/version.json`, `README.md:13`, `EULA.md:13` und `:60`.
> `test_the_version_is_the_same_in_both_places_that_carry_it`
> (`tests/test_toolchain.py:108`) hält die beiden Handstellen zusammen.
>
> **Der Widerspruch zog sich durch das ganze Dokument:** §9 Punkt 1 führte die
> Versionsnummer noch als offene Entscheidung („Bis zum Widerspruch wird
> `0.9.0` gebaut"), und D6, §5 und §6 rechnen mit `0.9.1`, `0.9.2` und
> `0.9.5`. Nach der Zählregel aus §2 D heißt der nächste Bau **`0.1.1`**, die
> zweite Demo entsprechend `0.1.5`. Die Ziffern stehen unten, wie sie standen —
> gemeint ist jeweils die nächste Punktversion.

### D2 — Die Texte in der Anwendung (S–M)

1. Ersteinrichtung: der Testlaufsatz wird der Demosatz mit Stichtag
2. Statusleiste: dauerhafte Zeile nach §2 F
3. Über-Dialog: „Demo, endet am 30.10.2026" statt Resttagen
4. Freischaltdialog: erklärt, dass es für die Demo keinen Schlüssel gibt und wo
   1.0 herkommt — statt „gilt für eine andere Hauptversion" (Regel 17)
5. **Die Schlussmeldung** (§2 B2): Oberfläche und Kommandozeile beenden sich
   beim Start, sobald `state().over` gilt. Das Fenster nennt das Ablaufdatum,
   die Adresse der Website, den Ordner mit den eigenen Projekten und den Satz,
   dass eine `.p3d` eine ZIP-Datei mit JSON darin ist und lesbar bleibt
6. Menüeintrag „Nach einer neuen Version sehen" (§2 G) mit Antwort in allen
   drei Fällen; die Prüfung selbst bleibt, wie sie ist
7. Alles über `tr()`, deutsch und englisch

**Abnahme:** `tests/test_translations.py` grün (Regel 20) ·
`tests/test_ui.py` offscreen · von Hand mit gestelltem Datum: am 31.10. öffnet
ein Projekt, dreht sich, misst sich, speichert — und verliert nichts.

### D3 — Rechtstexte auf „kostenlose, befristete Demo" (M, dazu Wartezeit)

1. **EULA** bekommt einen Demo-Abschnitt: befristete, unentgeltliche Nutzung,
   keine Weitergabe der Datei, kein Anspruch auf Fortbestand, Haftung wie bei
   unentgeltlicher Überlassung. Er wird die Lizenzseite des Installers
2. **AGB und Widerrufsbelehrung** bleiben, werden aber sichtbar als „gilt ab
   dem Verkaufsstart" gekennzeichnet — ein Widerrufstext neben einem kostenlosen
   Download verwirrt und ist im Zweifel angreifbar
3. **Datenschutz**: Absatz zur Update-Abfrage (§2 G), Absatz zu den
   Download-Logs
4. Die fachliche Prüfung anstoßen — sie läuft während der Demo und muss vor
   dem Verkauf fertig sein, nicht vor dem Demo-Start

**Abnahme:** kein Entwurfshinweis mehr auf Texten, die für die Demo gelten ·
der Installer zeigt den EULA-Text · beide Sprachen.

### D4 — Website auf die Demo umschreiben (M)

1. Download-Kasten in beiden `index.html`: echte Dateien, SHA-256 daneben,
   Stichtag ausdrücklich genannt, Windows und Linux
2. Der „Früher hineinschauen"-Mailto verschwindet — er war der Platzhalter für
   genau diesen Moment
3. Preisabschnitt: „49 € zur Einführung" bleibt als Ausblick stehen, aber ohne
   Kaufknopf und mit dem Satz, dass die Demo davon unberührt kostenlos ist
4. Neuer Abschnitt oder FAQ-Frage: **Was passiert am 30.10.?** — die Demo
   lässt sich danach nicht mehr starten (§2 B2), nichts wird gelöscht, die
   Projektdateien bleiben und öffnen sich mit 1.0. Dieser Satz steht **vor**
   dem Download, nicht nur in der FAQ
5. Falls unsigniert (§2 E des Veröffentlichungskonzepts): der Satz zur
   SmartScreen-Warnung samt Prüfsumme
6. Handbuch neu erzeugen (`tools/make_manual.py`), beide Sprachen

**Abnahme:** `tests/test_website.py` grün · beide Startseiten von Hand
durchgeklickt · Download startet, Prüfsumme stimmt.

**Stand 20.08.2026 — umgesetzt, mit einer Abweichung von Punkt 2.**

Der Mailto verschwindet nicht aus der Datei, sondern zur Laufzeit: Der Kasten
trägt beide Zustände, und `site.js` schaltet zum Termin um. Der Grund ist der
Ablauf des Tages selbst — wer die Pakete erst am Nachmittag fertig hat, will
nicht dieselbe Datei zweimal anfassen, und eine Seite, die um Punkt achtzehn
Uhr auf ein Paket zeigt, das noch nicht liegt, ist schlechter als eine, die
weiter um Nachricht bittet. Umgeschaltet wird nur, wenn im Kasten wirklich
Verweise stehen.

Eingetragen werden sie von **`tools/make_download.py`**: Es kopiert die Pakete
nach `website/dl/`, rechnet Größe und SHA-256 und schreibt beides in alle
**sechs** Sprachversionen (das Konzept sprach von zweien — inzwischen sind es
sechs). Ohne Argumente räumt es den Kasten wieder leer, falls ein Paket
zurückgezogen werden muss.

    python tools/make_download.py Releases/Solidon3D-0.1.0-Setup.exe \
                                  Releases/Solidon3D-0.1.0-x86_64.AppImage

Punkt 5 steht im Kasten, nicht in der FAQ: der Satz zur SmartScreen-Warnung
und der zur Prüfsumme erscheinen zusammen mit den Dateien. Was noch fehlt, ist
allein das, was ohne die fertigen Pakete nicht geht — sie selbst.

Zwei Tests halten die Verdrahtung: `test_the_download_box_can_switch_from_
waiting_to_loading` je Sprachversion, und `test_the_two_dates_for_the_same_
moment_agree`, weil der Termin zweimal auf der Seite steht — am Zähler und an
der Umschaltung.

### D5 — Rückmeldeweg (S)

Das Postfach steht. Was fehlt, ist der Weg aus der Anwendung dorthin.

1. Testmail von außen an `support@solidon3d.de`, SPF und DMARC gegenprüfen
2. Auftragsverarbeitungsvertrag bei netcup abschließen
3. In der Anwendung ein Menüeintrag **„Rückmeldung senden"**: öffnet eine Mail
   mit Version, Betriebssystem und dem Hinweis, dass das Protokoll angehängt
   werden kann — verschickt selbst nichts, wie der Fehlerbericht auch

**Abnahme:** Testmail kommt an und wird nicht als Spam einsortiert · der
Menüeintrag öffnet eine vorbereitete Mail.

### D6 — Signierung: unsigniert starten, in 0.9.1 nachziehen (S jetzt, M später)

Der Schritt in `build.yml:137` schreibt eine PFX-Datei aus einem Secret. Seit
Juni 2023 gibt es für neu gekaufte Zertifikate keine exportierbare Datei mehr —
der Schritt ist tot, egal wie die Entscheidung ausfällt.

**Mit dem Start am 20.08. ist die Frage entschieden, ob man will oder nicht:**
Azure Trusted Signing verlangt Nachweise zum Unternehmen, und die brauchen
Tage bis Wochen. Also:

1. **Jetzt (S):** unsigniert ausliefern. Auf der Download-Seite ein Satz zur
   SmartScreen-Warnung samt SHA-256 — ehrlicher als eine Warnung ohne
   Erklärung. Den toten Signierschritt in `build.yml` stilllegen, statt ihn
   sich stumm überspringen zu lassen
2. **Parallel:** Azure Trusted Signing beantragen
3. **In 0.9.1 (M):** signieren, sobald es durch ist. Reputation wächst dann ab
   diesem Zeitpunkt — später als gewünscht, aber immer noch vor dem Verkauf,
   und das ist der Punkt aus §2 A

**Abnahme jetzt:** die Download-Seite erklärt die Warnung und nennt die
Prüfsumme · `build.yml` läuft ohne den toten Schritt durch.

### D7 — CI-Bau und Auslieferung (M, war S–M) — **zuerst, nicht zuletzt**

Nach Fund c) ist das kein Abschlusspaket mehr, sondern das mit dem größten
Unbekannten. Es zieht deshalb vor D4.

1. **Pushen** — 205 Commits. Vorher Fund a) entscheiden: bleibt das
   Repository öffentlich?
2. Den Lauf ansehen. Ist der Segmentierungsfehler mit den 205 Commits weg, ist
   dieses Paket klein. Ist er es nicht, gilt Punkt 3
3. **Rückfallweg, falls der Runner weiter stirbt:** die Suite in der CI in
   Portionen fahren (`pytest --forked` oder mehrere Aufrufe), damit ein
   Absturz in einer Datei nicht den ganzen Lauf nimmt. Die Ursache selbst ist
   eine eigene Arbeit und kein Startkriterium — **wohl aber, dass sie benannt
   und eingegrenzt ist**
4. **Zweiter Rückfallweg:** das Paket lokal bauen (`pyinstaller` +
   `tools/make_installer.py`) und von Hand hochladen. Für eine Demo genügt
   das; die CI ist der Weg, nicht das Ziel
5. Beide Artefakte holen, auf den Webspace legen, Platz prüfen (rund 255 MB je
   Version, 75 GB vorhanden)
6. Prüfsummen notieren und auf die Seite schreiben

**Abnahme:** beide Dateien laden von `solidon3d.de` herunter und öffnen sich ·
der Weg, auf dem sie entstanden sind, ist wiederholbar aufgeschrieben.

### D8 — Der fremde Rechner (M) — **der Härtetest**

V6 Punkt 3 aus dem Veröffentlichungskonzept, unverändert gültig:

1. Auf einem Windows ohne Python, ohne venv, ohne Entwicklerwerkzeuge
   installieren
2. Die drei Hauptwege durchgehen: Beispielprojekt öffnen, bearbeiten,
   exportieren, an den Slicer übergeben
3. **Ohne** OpenSCAD, Ollama und ComfyUI prüfen, dass die Anwendung das sagt,
   statt zu scheitern
4. Deinstallieren und nachsehen, was liegen bleibt
5. Dasselbe auf Linux mit dem tar.gz — AppImage und Flatpak bleiben draußen,
   solange kein Bau gelaufen ist (Veröffentlichungskonzept §2 F)

**Abnahme:** Startmenüeintrag, Symbol, Deinstallation stimmen · die acht
Beispielprojekte sind da und rechnen · F1 öffnet das Handbuch · die
Paketierung hat OCP und V-HACD dabei (sie hat sie zuletzt nicht gesehen,
`ROADMAP.md:515`).

### D9 — Doku nachziehen (S)

`README.md` (Version, Demo-Abschnitt, Stichtag), `ROADMAP.md` (P8
fortschreiben), `.claude/rules/kern.md` um den Stichtag ergänzen, dieses
Konzept mit Fortschrittstabelle.

**Abnahme:** `/pruefen` grün · `/regelcheck` ohne Verstoß.

---

## §4 Reihenfolge und Termine

Heute ist der 12.08.2026. Start der Demo: **Donnerstag, 20.08.2026** — zehn
Wochen Laufzeit bis zum 30.10.

```
Arbeit:    D0 ─▶ D1 ─▶ D2 ─▶ D5 ─▶ D4 ─▶ D7 ─▶ D8 ─▶ D9 ─▶ Start
Papier:    D3 ──────────────────────────┘
Wartezeit: Azure, Paddle, Rechtsprüfung ─┘  (blockieren den Start nicht)
```

| Tag | Arbeit | Nebenher |
|---|---|---|
| 12.08. | D0 Stichtag ✓, Paketierung repariert ✓, **D7 Punkt 1–2: pushen und den Lauf ansehen** | Azure-Nachweise, Paddle-Konto und Rechtsprüfung anstoßen; Testmail an das Postfach |
| 13.–14.08. | D1 Version, D2 Texte; was der CI-Lauf gezeigt hat | AV-Vertrag netcup |
| 15.–16.08. | D3 Rechtstexte, D5 Rückmeldeweg | — |
| 17.–18.08. | D4 Website, D6 Punkt 1 (unsigniert erklären), D7 Rest | — |
| 19.08. | **D8 fremder Rechner**, D9 Doku | — |
| 20.08. | Start | — |

Die Reihenfolge hat sich gegenüber dem ersten Entwurf gedreht: **der CI-Lauf
steht vorn, nicht hinten.** Vor ihm ist jede Aussage über die Auslieferung eine
Vermutung — dasselbe Argument, mit dem V1 im Veröffentlichungskonzept vor allem
anderen stand, und diesmal mit einem bekannten roten Lauf dahinter.

Arbeit rund **fünf bis sechs Tage**, und damit ist der Plan eng, aber ohne
Wartezeit im kritischen Pfad — genau deshalb fällt die Signierung aus dem
Startumfang heraus (D6) und der Verkauf ohnehin (§2 H).

**Der einzige Puffer liegt am 19.08.** Findet D8 auf dem fremden Rechner etwas
Großes, wird **nicht** der Stichtag verschoben, sondern der Start um Tage. Der
30.10. steht in den Texten und ist der Anker, an dem die Entscheidung in §6
hängt.

**Was am 19.08. fertig sein muss, sonst startet nichts:** ein Paket, das auf
einem fremden Windows installiert, die drei Wege durchläuft und ohne OpenSCAD,
Ollama und ComfyUI sagt, was fehlt, statt zu scheitern.

---

## §5 Was während der Demo läuft

Die acht Wochen sind keine Wartezeit:

* **Funde beheben und nachschieben.** 0.9.1, 0.9.2 — jede Punktversion mit
  Änderungsliste auf der Seite. **0.9.1 trägt die Signatur**, sobald Azure
  durch ist (D6).
* **Paddle einrichten und einen Testkauf durchspielen** (V5). Der Schlüssel
  für Hauptversion 1 wird gegen ein gebautes 1.0-Paket geprüft, nicht gegen
  die Demo.
* **Rechtstexte fachlich prüfen lassen.** Das ist der Punkt mit der längsten
  und am wenigsten steuerbaren Laufzeit.
* **Die verbleibenden vier ROADMAP-Punkte** nach Nutzen sortieren: weitere
  Sprachkataloge (ES/FR/IT/PT — der billigste Reichweitengewinn, das Gerüst
  steht, es fehlen die Dateien), die Skizzen-Restpunkte aus
  `konzept-bedienung.md` Teil 4, Plattenvorschlag in der Oberfläche.
* **Zählen, was zählbar ist, ohne Telemetrie:** Download-Zahlen aus dem
  Server-Log, Abrufe von `version.json`, eingegangene Rückmeldungen. Mehr wird
  nicht erhoben, und mehr braucht die Entscheidung in §6 auch nicht.

---

## §6 Der Entscheidungspunkt: 10.10.2026

Zwanzig Tage vor Schluss wird entschieden, ob am 30.10. **1.0 erscheint** oder
**eine zweite Demo** folgt. Zwanzig Tage, weil ein Verkaufsstart Paketbau,
Website und einen Testkauf braucht.

**Seit §2 B2 ist dieser Termin verbindlich, nicht beratend.** Am 31.10. startet
keine Demo mehr; wer bis dahin ohne Nachfolger dasteht, sperrt seine
interessiertesten Nutzer aus. Eine dritte Antwort — „wir sehen dann weiter" —
gibt es an diesem Tag nicht.

**1.0 erscheint, wenn alle fünf zutreffen:**

1. Kein offener Absturz und kein offener Datenverlust aus der Demo
2. Die Anwendung ist auf mindestens **zehn fremden Rechnern** gelaufen, und
   von mindestens **fünf verschiedenen Personen** liegt eine Rückmeldung vor,
   die nicht von Robert stammt
3. Paddle ist eingerichtet, ein Testkauf ist durchgelaufen und wurde storniert
4. Die Rechtstexte sind fachlich geprüft, oder die Prüfung hat nichts
   Blockierendes ergeben
5. Die Signierfrage ist beantwortet — signiert oder erklärt

**Sonst eine zweite Demo**, als 0.9.5 mit Stichtag **31.12.2026**. Sie kostet
nur D0 (Datum), D1 (Version), D4 (zwei Sätze auf der Seite) und D7 — ein
halber Tag, weil die Mechanik dann steht. Das ist der eigentliche Grund, warum
der Stichtag eine Konstante an einer Stelle ist.

**Was eine zweite Demo nicht sein darf:** eine Verlängerung, weil es sich noch
nicht fertig anfühlt. Die Kriterien oben sind absichtlich zählbar. Trifft
keines zu und die Demo lief still, ist die Antwort trotzdem 1.0 — dann fehlt
nicht Reife, sondern Sichtbarkeit, und die entsteht nicht durch Warten.

---

## §7 Risiken

| Risiko | Wirkung | Rückfalloption |
|---|---|---|
| **Unsigniert am 20.08.** (eingetreten, siehe D6) | SmartScreen warnt jeden Erstnutzer; die Vorsichtigen brechen ab | Erklärung und Prüfsumme auf der Download-Seite, Nachsignieren in 0.9.1 |
| Der fremde Rechner findet etwas Großes (D8) | Start verschiebt sich um Tage | Start schieben, Stichtag halten, Laufzeit kürzen |
| Acht Tage sind zu wenig für D0–D9 | halbfertige Texte oder ungeprüftes Paket | in dieser Reihenfolge streichen: D6 Punkt 1 (dann nur Prüfsumme), D9, D5 Punkt 3 — **nie D8** |
| Die Demo bleibt unbemerkt | keine Funde, keine Reputation, Entscheidung ohne Daten | §6 Schlusssatz: dann erscheint 1.0; Sichtbarkeit ist eine eigene Aufgabe, keine Entwicklungsaufgabe |
| Jemand patcht den Stichtag | eine kostenlose Version läuft weiter | keine Wirkung — es gibt nichts zu bezahlen; die Schwelle für 1.0 ist die Signatur, und die hält |
| Demo-Nutzer erwarten am 30.10. einen Freischaltweg | Enttäuschung genau bei den Interessiertesten | §2 D: der Freischaltdialog nennt den Weg zu 1.0, statt eine Fehlermeldung zu zeigen |
| **Am 31.10. steht kein Nachfolger bereit** (§2 B2) | Nutzer kommen an ihre eigenen Projekte nicht mehr heran — der teuerste Fehler dieses Plans | Entscheidung am 10.10. (§6), notfalls 0.9.5 mit neuem Stichtag; sie kostet einen halben Tag |
| 255 MB je Version mal mehrere Punktversionen | Webspace läuft voll | nur die aktuelle Version halten |

---

## §8 Was ausdrücklich nicht zur Demo gehört

Damit es niemand nachträglich hineinliest:

* **Kein Verkauf, kein Kaufknopf, keine Zahlungsseite** (§2 H)
* **Keine Beschneidung der Funktionen** (§2 E) — kein Wasserzeichen, keine
  Exportsperre
* **Kein Konto, keine Anmeldung, keine Telemetrie.** Auch nicht „nur zum
  Zählen der Installationen"
* **Kein macOS, kein AppImage, kein Flatpak** — die Rezepte für die beiden
  Linux-Formate stehen seit dem 20.08., gebaut ist keines, und ein ungebautes
  Format ist für eine Demo kein Format
* **Kein Demo-Schlüssel und keine Verlängerung per Eingabe** — eine zweite
  Runde ist ein neuer Bau (§6)
* **Kein Betrachtermodus nach dem 30.10.** (§2 B2). Der bleibt der
  Verkaufsversion, wo er hingehört: dort ist er die Freundlichkeit gegenüber
  jemandem, der vierzehn Tage getestet und noch nicht gekauft hat
* **Keine weiteren Sprachen als Startbedingung.** ES/FR/IT/PT sind Arbeit
  während der Laufzeit, kein Blocker (§5)

---

## §9 Offene Entscheidungen

Entschieden am 12.08.2026: Startdatum (20.08.), Schlüsselfreiheit (§2 B),
harter Stopp am 31.10. (§2 B2), Download über die Website, Update-Suche von
Hand mit Option (§2 G), Signierung (unsigniert starten, D6). Offen bleiben
vier — die ersten beiden neu aus dem zweiten Durchgang:

0. **Bleibt das Repository öffentlich?** (§1.2 a) Öffentlich heißt: der
   Quelltext der Lizenzprüfung liegt neben dem Paket, das ihn kompiliert
   ausliefert, und die Unterlagen — Roadmap, Konzepte, Preisüberlegungen —
   liegen mit. Privat heißt: ein Klick im Repository-Menü, und die Härtung
   H3–H5 bedeutet wieder, was sie bedeuten soll. *Blockiert den Push und damit
   D7.*
0b. **Zieht das Repository auf den Produktnamen um?** (§1.2 b) `Formwerk` →
   `Solidon`. GitHub legt eine Weiterleitung an; das lokale Remote wird
   nachgezogen.

1. **Versionsnummer**: `0.9.0` nach §2 D — oder doch `1.0.0-demo`? Gegen die
   zweite Variante spricht, dass `current_major()` dann eine Eins liest und ein
   Kaufschlüssel in einer abgelaufenen Demo griffe, deren Stichtag ihn nichts
   angeht. Bis zum Widerspruch wird `0.9.0` gebaut; es sind zwei Zeilen.
2. **Rechtsprüfung**: jetzt beauftragen (kostet, läuft parallel) oder erst zum
   Verkauf? Für eine kostenlose Demo ist der Bedarf geringer — für 1.0 nicht,
   und die Laufzeit ist nicht steuerbar.

---

## §10 Fortschritt

| Paket | Status | Commit |
|---|---|---|
| D0 Stichtag im Kern | **fertig** — `store.DEMO_UNTIL = date(2026, 10, 30)`, `Activation.deadline` und `.over` | f8ac8c1 |
| D1 Version | **fertig** — `0.1.0` in `branding.py` und `pyproject.toml`, dazu `website/version.json`, README, EULA und die beiden erzeugten Handbuch-Deckblätter | 7c2e6d6, danach auf 0.1.0 |
| D2 Texte in der Anwendung | **fertig** — Statuszeile dauerhaft, Über-Dialog, Freischaltdialog, Ersteinrichtung, dazu die Abschiedsmeldung nach dem Stichtag (§2 B2) | 1c50fab |
| D3 Rechtstexte | **fertig** — EULA §4a; AGB und Widerruf sagen, dass sie erst ab dem Verkaufsstart gelten | 57d1d7b |
| D4 Website | **fertig** — beide Startseiten führen die Demo, zwei neue Fragen beantworten das Ende | 9a88bfa |
| D5 Postfach und Rückmeldeweg | **fertig** — zwei Menüeinträge: nach einer neuen Version sehen (mit Antwort in allen drei Fällen) und Rückmeldung schreiben | 1c50fab |
| D6 Signierung | **halb** — der tote PFX-Schritt ist stillgelegt und protokolliert statt stumm übersprungen (`build.yml`, „Ohne Signatur bauen"). Die Abnahme fehlt: die Download-Seite erklärt die SmartScreen-Warnung noch nicht und nennt keine Prüfsumme | |
| D7 CI-Bau und Auslieferung | offen | |
| D8 Fremder Rechner | offen | |
| D9 Doku | **halb** — `README.md` trägt Version, Demo-Abschnitt und Stichtag, die `ROADMAP.md` den Demo-Abschnitt, und diese Tabelle ist der letzte Punkt. Offen: `.claude/rules/kern.md` nennt den Stichtag nicht | |

**Die Tabelle stand bis zum 14.08.2026 auf zehnmal „offen"**, während sechs
Pakete gebaut waren — nachgezählt am Code, nicht an der Erinnerung. Wer den
Stand aus dem Konzept statt aus der ROADMAP las, hielt die Demo für
unangefangen. Das ist der Grund, warum D9 diese Tabelle ausdrücklich als
eigenen Punkt führt.

**Zur Version: die Zahl war zweimal eine andere.** Dieses Konzept schrieb
`0.9.0` vor, gebaut wurde am 12.08. `0.7.0`, und am 14.08.2026 steht sie auf
**`0.1.0`** — die Version, mit der die Demo hinausgeht. Für die drei Folgen
oben ändert das nichts, weil alle drei an der Null vorn hängen und nicht an den
Stellen dahinter. Was sich ändert, ist die Zählung dahinter: sie beginnt jetzt
am Anfang statt in der Nähe der 1.0, und der nächste ausgelieferte Bau ist
`0.1.1`.

Sieben Stellen tragen die Zahl, und sie sind nachgezogen: `app/branding.py`,
`pyproject.toml`, `website/version.json`, `README.md`, `EULA.md` (von dort
`website/eula.html` und `packaging/eula.txt` über `tools/make_legal.py`) und
die Deckblätter von `website/handbuch.html` und `website/en/manual.html` über
`tools/make_manual.py`. Demo-Projektdateien tragen entsprechend
`app_version: 0.1.0`.

**Was bis zum Start bleibt:** D7 (die CI grün sehen und die Artefakte holen),
D8 (der fremde Rechner), der Download-Kasten mit echter Datei und Prüfsumme —
der zugleich die Abnahme von D6 ist —, und der Stichtag in `kern.md`.

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen über den eigenen Stand geprüft: **sieben stimmen, sieben sind
überholt, eine ist falsch.** Dieses Dokument ist die SSOT der laufenden
Demo-Phase — von den achtzig Tagen bis zum Stichtag sind noch zweiundsiebzig.

**Der Widerspruch, der sich durch das ganze Dokument zieht:** D1 schreibt
Version `0.9.0` vor, §9 führt sie als offene Entscheidung — entschieden ist seit
dem 14.08.2026 **`0.1.0`**, und sie steht an sieben Stellen so im Code. Die
Folgeziffern (`0.9.1`, `0.9.2`, `0.9.5`) meinen nach der eigenen Zählregel
`0.1.1` und `0.1.5`.

**Was sich zum Guten geändert hat:** Der Push ist erledigt — `origin/main`
steht auf dem Tagesstand, das Repository ist öffentlich und umbenannt. Damit
fällt der Punkt weg, der hier „ganz vorn" stand. Der Segmentierungsfehler
besteht weiter, sitzt aber nicht dort, wo dieses Dokument ihn vermutet: Sein
Ort ist zufällig, weil er kumuliert.

**Was gewachsen ist:** 77 Operationen → 85 · drei Hauptwege → **vier** · acht
Beispielprojekte → neun · zwei Sprachen → sechs · 33 Handbuchseiten → 40. Die
Abbildungszahl war schon am 12.08. falsch: 25, nicht 28.

**Die Außenrecherche trifft dieses Dokument an einer Stelle hart** — D6, die
Signierung:

- **Azure Trusted Signing heißt heute Azure Artifact Signing** und ist für
  Einzelpersonen faktisch verschlossen: Es verlangt eine Organisation mit drei
  Jahren nachweisbarer Existenz und ein zahlendes Azure-Abonnement; die Prüfung
  dauert 1 bis 20 Werktage. Der Plan „in 0.9.1 nachziehen, sobald Azure durch
  ist" hat damit eine Voraussetzung, die dieses Dokument nicht kennt.
- **Der Ersatzweg existiert:** Certum gibt ein Cloud-OV-Zertifikat auf den Namen
  einer Privatperson aus, 139 $ im ersten Jahr, ohne Hardware-Token.
- **EV-Zertifikate umgehen SmartScreen nicht mehr** — auch ein gültig
  signiertes, frisch gebautes Setup löst zunächst die Warnung aus. Der Nutzen
  der Signatur ist der geprüfte Herausgebername, nicht das Ausbleiben der
  Warnung.
- **Ohne Signatur baut sich die Reputation für jede neue Version bei null neu
  auf.** Bei einer Demo, die in Punktversionen nachgeschoben wird, heißt das:
  jede Version warnt von vorn.

**Zwei Fristen von außen, die im Zeitplan fehlen:** Die **CRA-Meldepflichten
greifen ab dem 11.09.2026**, also mitten in der Demo-Phase; die Ausnahme für
freie Software gilt nur bei unentgeltlicher Bereitstellung — für eine
kostenlose Demo, die auf einen Verkauf zielt, ist das zu klären. Und **Artikel
50 des AI Act gilt seit dem 02.08.2026**; er nennt synthetische Bild-, Ton-,
Video- und Textinhalte, **3D-Modelle nicht**.

**Nicht belegbar und deshalb offen gelassen:** ob die CI heute grün läuft und
ob ein Artefakt entsteht. Beides entscheidet sich auf dem Runner, nicht hier —
und es bleibt der kritische Punkt dieses Plans.
