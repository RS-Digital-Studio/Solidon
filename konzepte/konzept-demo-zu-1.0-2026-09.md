# Konzept: Übergang von der Demo zu Solidon3D 1.0

**Stand: 16.09.2026. Untersucht: Commit `d20104b0`.**

**Bestätigte Produktentscheidungen:** Die öffentliche Demo läuft einschließlich
30.10.2026. Der **31.10. ist für letzte Optimierungen reserviert** (Robert,
16.09.2026). **Verkaufsstart ist der 01.11.2026 um 10:00 Uhr Europe/Berlin**
(Robert, 16.09.2026). Die Verkaufsversion startet ohne kostenlose Testphase.

**Dokumentstatus:** Der Ist-Zustand in §2 ist am Code geprüft; §18 nennt die
ausgeführten Nachweise. Die mit **Vorschlag** gekennzeichneten Entscheidungen
und Abläufe sind ein Entwurf zur Umsetzung, keine bereits gebauten Funktionen.
Die bestätigten Termine sind keine Behauptung, dass der Verkauf schon technisch
eingerichtet oder rechtlich freigegeben wäre. Die ursprüngliche Konzeptfassung
beschreibt die geplanten Änderungen. **Nachtrag vom selben
Tag:** Auf Roberts anschließenden Auftrag wurde die konkret reproduzierte
Uhr-Rückstelllücke I03a im Quellcode behoben; Umfang und Nachweise stehen in
§7.1 und §18. Die übrigen vorgeschlagenen Funktionen bleiben Entwurf.

Die Umsetzung wird unter [RM-061](../ROADMAP.md#rm-061) geführt. Kaufabwicklung,
Lizenzarten und rechtliche Prüfung bleiben mit RM-092, RM-182 und RM-093
verbunden. Dieses Konzept ist die gemeinsame Beschreibung des Übergangs;
es legt keine zweite Aufgabenliste neben dem Roadmap-Register an.

## §1 Auftrag, Umfang und Vorrang

Das Konzept beantwortet für **bereits installierte Demos**, neue Nutzer und
Käufer: Was startet wann, was bleibt lesbar, wie kommt 1.0 auf den Rechner,
wie wird bezahlt und freigeschaltet, was geschieht mit bestehenden Projekten,
und welcher Weg bleibt bei einem Fehler?

Grundlagen:

- Bauplan §§2, 16, 33, 37.2 und 38: verständliche Abläufe, Projektformat,
  Fehlerbehandlung, signierte Aktualisierungen und lokale Nutzerdaten.
- [Demo-Konzept](konzept-demo-2026-10.md): feste Frist, kein dauerhaft
  weiterlaufender Demo-Betrachter, kein Konto, kein Schlüssel für die Demo.
- [Aktivierungsserver](konzept-aktivierungsserver-2026-08.md): getrennte
  Signierschlüssel, Geräteaktivierung, Dateiweg und Kauf aus einem Schlüsselvorrat.
- [Lizenzarten](konzept-lizenzarten-2026-09.md): private und gewerbliche Lizenz;
  Klarstellung vom 16.09.: gewerblich bis zu zwei Personen gleichzeitig.
- [EULA](../EULA.md), insbesondere Abschnitte 2, 4a, 4b, 5 und 11a;
  [AGB](../AGB.md), insbesondere §§2–4.

Das alte Demo-Konzept enthält historische Passagen über einen Nachfolger bereits
am 30.10., Paddle, einen Alternativtermin 31.12. und standardmäßig ausgeschaltete
Updateprüfungen. Sie werden **nicht** ungeprüft übernommen. Für die hier
beschriebenen Termine gelten Roberts aktuelle Entscheidungen. Für den Ist-Code
gilt §2. Der frühere Veröffentlichungstext ist keine aktuelle Zustandsbeschreibung.

Nicht Gegenstand sind neue Modellierfunktionen, eine automatische Verlängerung
der Demo, eine neue Testphase, Konten, Telemetrie, regelmäßige Lizenzabfragen
oder eine Änderung der Preise. Preise und vorhandene Zusagen werden nur auf
den Übergang angewendet. Eine Veröffentlichung ist ein späterer eigener Auftrag.

## §2 Verifizierter Ist-Zustand

Die Stellen sind durch Pfad und Symbol bezeichnet; Zeilennummern würden beim
nächsten Funktionsausbau rasch altern. Aussagen über Server und Kundenpakete
werden nur gemacht, soweit sie hier tatsächlich geprüft wurden.

| Nr. | Feststellung am Stand `d20104b0` | Beleg und praktische Folge |
|---|---|---|
| I01 | `DEMO_UNTIL = date(2026, 10, 30)`, `TRIAL_FROM = None`. Der letzte Tag zählt mit. | `app/core/activation/store.py`, `days_left`: am 30.10. ein Resttag, ab 31.10. null. |
| I02 | Die Demo rechnet mit `date.today()`. | `store.days_left`: maßgeblich ist das lokale Kalenderdatum des Rechners, kein weltweit identischer UTC-Zeitpunkt. |
| I03 | Der Lizenzzustand wird einmal je Prozess gespeichert. | `app/core/activation/__init__.py`, `state`, `_cached`, `forget_cache`: eine vor Fristende gestartete Sitzung bleibt ohne erneute Zustandsbestimmung offen. Es gibt keinen täglichen Ablaufwächter. |
| I03a | Ein bereits erkannter Demo-Ablauf kann durch Zurückstellen des Datums wieder aufgehoben werden. | `store.days_left`: jeder gespeicherte Tag nach `DEMO_UNTIL` wird als falsche Zukunftsuhr verworfen. Isoliert reproduziert: 29.10. → zwei Resttage, 31.10. → null, zurück auf 29.10. → wieder zwei. Die Korrektur unterscheidet einen echten Ablauf nicht von einem Uhrfehler. |
| I04 | Eine abgelaufene, regulär unlizenzierte Demo erreicht das Hauptfenster nicht. | `app/ui/app.py`, `main`: `state.over` wird vor Hauptfenster, Registeraufbau und Updateprüfung behandelt; Rückgabe 1. |
| I05 | Der Abschiedsdialog bietet Website und Schließen. | `app/ui/dialogs.py`, `expired_demo_text`, `show_expired_demo`: keine Installation aus diesem Dialog, kein Lizenzfeld, keine angezeigte konkrete Projektliste. |
| I06 | Die Kommandozeile hat dieselbe Startsperre. | `app/cli/main.py`, `main`, `_demo_is_over`: Prüfung vor dem normalen Befehlsweg. Eine gesperrte Demo ist kein CLI-Ausweichweg zum Export. |
| I07 | Ein 1.x-Kaufschlüssel wird in 0.x abgewiesen. | `app/core/activation/key.py`, `parse`, `current_major`: Hauptversion muss übereinstimmen. Ein Kauf wandelt die alte Binärdatei nicht um. |
| I08 | Die Verkaufsversion muss gesondert gebaut werden. | `store.py`, `app/branding.py`, `pyproject.toml`, `test_a_sale_version_carries_no_deadline`: 1.x mit `DEMO_UNTIL = None` und `TRIAL_FROM = None`; die Versionsnummer allein reicht nicht. |
| I09 | 1.x ohne Lizenz ist startfähig und hat keine freie Testzeit. | `Activation.sale_without_trial`, `test_a_sale_build_is_never_over`: keine Demo-Startsperre, aber keine Freigabe der geschützten Handlungen. |
| I10 | Öffnen, Auswerten, Projektspeichern und Undo/Redo bleiben im unfreigeschalteten Zustand grundsätzlich möglich; Änderungen, Export, Slicer-Übergabe und Chat sind geschützt. | `tests/test_licence_boundary.py`, `History`, `export/writer.py`, `export/handover.py`, `agent/session.py`. Die Startfreigabe der 1.0 und ihre Bearbeitungsfreigabe sind verschiedene Dinge. |
| I11 | Neue Kaufcodes brauchen ein passendes Gerätezertifikat; ältere Bestandscodes werden gesondert behandelt. | `DEVICE_ACTIVATION_FROM = 2026-11-01`, `Activation.licensed`, `requires_device_activation`, `certificate.load_for`. Die Einstufung hängt am signierten Ausstelltag, nicht an der aktuellen Uhr. |
| I12 | Privat ist ein Geräteplatz vorgesehen, gewerblich zwei. | `key.DEVICE_LIMITS`, `website/api/activation_common.php`, `ACTIVATION_DEVICE_LIMITS`; Nutzerrechte stehen zusätzlich in der EULA. Keine Gleichzeitigkeitserfassung im Netz. |
| I13 | Neue Installationen prüfen standardmäßig beim Start auf Updates; Einstellungen können das verhindern. | `app/ui/settings.py`, `Settings.check_for_updates = True`, `load_settings`; `MainWindow._check_for_updates`. Das alte Konzept mit Vorgabe `False` beschreibt nicht den aktuellen Stand. |
| I14 | Updates müssen signiert sein, Pakete werden geprüft und nur auf Klick installiert. | `app/core/updates.py`, `signature_ok`, `check`, `download`, `start_installer`; `MainWindow._install_update` fragt über `close()` nach ungespeicherter Arbeit. |
| I15 | Der Updateweg aus dem Hauptfenster ist nach Ablauf bei einem neuen Demo-Start nicht erreichbar. | Reihenfolge aus I04 und I13. Ab 31.10. ist die Website der vorhandene verlässliche Weg zur 1.0. |
| I16 | Nutzerverzeichnisse enthalten keine Hauptversionsnummer. | `app/core/paths.py`, `user_config_dir`, `user_data_dir`; Windows-AppId und Installationsname in `packaging/solidon3d.iss`. Ein Update soll vorhandene Einstellungen und Daten wiederfinden. Ein realer Plattformwechsel ist damit noch nicht abgenommen. |
| I17 | Projektversion und App-Version sind getrennt; aktuell ist das Projektformat 25. | `app/core/scene/migrations.py`, `FORMAT_VERSION`, `migrate`; `project.load`, `project.save`. Ein neueres Format wird von einer älteren App gegebenenfalls abgewiesen. |
| I18 | Der Schlüsselgenerator schützt vor versehentlichen aktivierungsfreien Verkaufscodes. | `tools/make_licence_keys.py`, `main`: Art und Archiv sind Pflicht; ein Ausstelltag vor 01.11. benötigt die ausdrückliche Einzelfalloption `--legacy`. `--major` übernimmt ohne Angabe jedoch die eigene App-Hauptversion. |
| I19 | Der Kauf-Webhook mit automatischer Zuteilung ist im Konzept beschrieben, im geprüften `website/api/` aber nicht enthalten. | Inventar der PHP-Endpunkte: Aktivierung, Abmeldung, Operator, Support und Hilfsendpunkte; kein `order.php`. Das lokale `tools/licence_admin.py` ersetzt keinen veröffentlichten automatischen Lieferweg. |
| I20 | Die Website hat einen vorhandenen Startzeitmechanismus, aber keinen belegten vollständigen Demo-zu-Verkauf-Umschalter. | `website/site.js`, `data-release`; aktuelle Startseiten nennen noch den Demo-Start 20.08.2026. `data-demo-until` allein schaltet keinen Checkout frei und baut keine neue App. |
| I21 | Der Aktivierungsdienst erwartet ohne andere Serverkonfiguration Hauptversion 1. | `activation_common.php`, `activation_licence`, `SOLIDON_ACTIVATION_MAJOR`. Der Live-Wert und die Migration für zwei Geräteplätze wurden in dieser Arbeit nicht abgefragt. |

**Abgleich mit 0.4.2:** `git diff v0.4.2 HEAD` zeigt in den untersuchten
Aktivierungs-, CLI-, Update- und Dialogdateien keine Änderung. `app/ui/app.py`
hat zusätzliche Cursor-Einrichtung, aber keine Änderung des Ablaufs der
Demo-Sperre. Das stützt die Beschreibung für den Quellstand von 0.4.2;
es ersetzt keinen Test der tatsächlich installierten signierten Pakete.

**Sonderfälle nicht verschweigen:** Ein gültiger interner 0.x-Bestandsschlüssel
kann den normalen Demo-Zustand überlagern. Eine beschädigte Installation ist
ein eigener Fehlerzustand. Die Datumstabelle unten beschreibt die öffentlich
verteilte Demo ohne einen solchen Sondercode, mit plausibler Systemuhr.

## §3 Entscheidungen für den Übergang

| Kennung | Entscheidung | Status |
|---|---|---|
| A | Demo vollständig bis einschließlich 30.10.2026; kein regulärer Start ab 31.10. | Bestätigter Bestand |
| B | 31.10. ist Optimierungs- und Abnahmetag; öffentliche Pause bleibt bestehen. | Robert, 16.09. bestätigt |
| C | Verkauf und öffentliche 1.0-Freigabe am 01.11.2026 um 10:00 Uhr Europe/Berlin, entsprechend 09:00 UTC. | Robert, 16.09. bestätigt |
| D | Der Demo-Stichtag bleibt ein lokaler Kalendertag wie im bestehenden Code. Keine rückwirkende Umstellung auf einen weltweit gemeinsamen Sperrzeitpunkt. | Vorschlag zur präzisen Fortführung des Bestands |
| E | Es gibt keine automatische Umwandlung, keine automatische Zahlung und keine automatische Installation. Nutzer installieren 1.0 und aktivieren sie bewusst. | Bestand fortführen |
| F | Vor Fristende erscheint ein reguläres letztes 0.x-Update mit klarer Übergangserklärung und sicherer Behandlung laufender Sitzungen. | Vorschlag; noch zu bauen |
| G | Bei Ablauf dürfen keine neuen Bearbeitungen beginnen. Bereits geleistete Arbeit kann gespeichert werden; kein erzwungenes Beenden mit Datenverlust. | Vorschlag; genauer Ablauf §7 |
| H | 1.0 bleibt ohne Testphase startfähig zum Lesen bestehender Projekte; Arbeiten und Exportieren verlangen die passende Aktivierung. | Vorhandenes Modell beibehalten und am Paket abnehmen |
| I | 1.0 wird nicht als gewöhnliches kostenloses Demo-Update angekündigt. Der Hinweis benennt Kauf und Aktivierung vor der Installation. | Vorschlag; für transparente Umstellung erforderlich |
| J | Die angekündigte Uhrzeit öffnet keinen Verkauf an der Abnahme vorbei. Bei einem Blocker wird der Start ausdrücklich verschoben und kommuniziert. | Vorschlag für den Betrieb |
| K | Bestandsschlüssel werden einzeln nach Format, Hauptversion und Ausstelltag inventarisiert; keine pauschale Gratis-Umwandlung oder still geänderte Gerätepflicht. | Vorschlag für die Bestandsbehandlung |

**Die Pause beträgt für einen Rechner in Deutschland 34 Stunden:**
31.10.2026, 00:00 Uhr bis 01.11.2026, 10:00 Uhr. Andere Zeitzonen haben bei
lokalem Demo-Ende entsprechend andere Wartezeiten. Im Kundentext steht deshalb
„Demo bis einschließlich 30. Oktober; Verkaufsstart am 1. November um
10:00 Uhr deutscher Zeit“, nicht „weltweit genau 24 Stunden Pause“.

Eine Website-Uhr darf den Zeitpunkt für den Besucher umrechnen, muss daneben
den eindeutig benannten Referenzzeitpunkt behalten. Die Systemuhr eines Kunden
darf niemals Zahlungsbestätigung oder Lieferberechtigung ersetzen.

## §4 Was geschieht an den drei Tagen?

| Situation | 30.10. | 31.10. | 01.11. vor 10:00 Berlin | Ab 01.11., 10:00 Berlin |
|---|---|---|---|---|
| Installierte 0.x-Demo wird neu gestartet | Voll nutzbar bis zum Ende des lokalen Tages | Ablaufmeldung; Website oder Schließen | Weiterhin Ablaufmeldung | Weiterhin Ablaufmeldung; Website führt zu 1.0 |
| Alte Demo wurde vor Fristende gestartet und nicht beendet | Normal nutzbar | **Ist:** kann wegen gespeichertem Zustand weiterarbeiten. **Entwurf für letztes Update:** keine neue Bearbeitung, Arbeit sichern (§7). | Wie am 31.10. | Wie am 31.10.; keine selbsttätige Verwandlung in 1.0 |
| Jemand versucht einen 1.x-Schlüssel in 0.x | Falsche Hauptversion | Kein Freischaltdialog mehr über den normalen Start | Ebenso | Zuerst 1.0 installieren; nicht einen zweiten Schlüssel kaufen |
| Bestehende Projektdatei auf der Platte | Bleibt unverändert | Bleibt unverändert, Demo öffnet nicht | Bleibt unverändert | In 1.0 öffnen; Migration und Kopie beachten (§10) |
| Öffentliche Website | Demo-Ende und Startdatum erklären | Optimierungs-/Wartetext, kein aktiver Verkauf | Derselbe Wartetext | Nur nach Freigabe: 1.0-Download, Preise und Checkout |
| Öffentliche Zahlung und Auslieferung | Kein Verkauf | Kein Verkauf | Kein Verkauf | Kauf → eigener signierter Schlüssel → Geräteaktivierung |
| Intern vorbereitete 1.0 | Abnahmekandidat, nicht öffentlich angeboten | Letzte Optimierungen und erneute Abnahme | Freigabevorbereitung | Derselbe geprüfte Paketstand wird veröffentlicht |

**Auch am 2. November und später bleibt eine alte Demo eine alte Demo.** Wer
erst Wochen später zurückkehrt, braucht denselben erklärten Weg zur aktuellen
Verkaufsversion. Keine Weiterleitung darf nur am Startwochenende funktionieren.

## §5 Vorlauf und letzte Demo

Die folgenden Vorlaufdaten sind **Planvorschläge**, keine bereits ausgeführten
Veröffentlichungen. Der verbindliche 31.10. bleibt ein voller Optimierungstag.

| Bis wann | Ergebnis | Warum es vorher stehen muss |
|---|---|---|
| 01.10. | Ein zusammenhängender Ablauftext für App, Website, Download und Support; genaue Uhrzeit in sechs Sprachen vorbereitet | Der Nutzer muss vor größeren Projekten wissen, wann die Demo endet. |
| 15.10. | Verkaufsvoraussetzungen und Kauf-/Lieferweg probeweise vollständig durchlaufen; Fristlogik und Datensicherung der letzten Demo gebaut | Ein Checkout-Link und eine Rechnung allein liefern noch keinen nutzbaren Schlüssel. |
| 22.10. | Letztes 0.x-Update mit Übergangshinweisen und Ablaufbehandlung angeboten; ältere Installationen weiterhin berücksichtigt | Ein freiwilliges Update erreicht niemals garantiert alle Nutzer. |
| 24.10. | Prominenter Demo-Download wird wie im bisherigen Konzept durch den bevorstehenden Start erklärt | Niemand soll versehentlich nur noch Stunden Nutzungszeit herunterladen. |
| 25.10. | Installierbarer interner 1.0-Kandidat und vorbereitete Veröffentlichung; Plattform- und Migrationsproben | Der 31.10. soll Verbesserungen und Abschlussprüfung tragen, nicht die erste Integration von Kauf, Aktivierung und Paketbau. |
| 30.10. | Letzter regulärer Demotag, klarer Hinweis auf Speichern und gegebenenfalls Export vor Ablauf | Kein Überraschungsstopp ohne Vorbereitung. |

Das letzte 0.x-Update bleibt eine normale kostenlose Demo mit unverändertem
Enddatum. Es führt keine zusätzliche Betriebsart ein. Seine Anforderungen:

1. Dauerhafte Statuszeile nennt Datum und den Menüweg zur Übergangserklärung.
2. Ab 24.10. erklärt ein ruhiger sichtbarer Hinweis einmal pro Sitzung die
   Pause und den Start von 1.0; keine Folge modaler Kaufaufforderungen.
3. Am 30.10. ist „Heute letzter Demotag“ verständlicher als „noch 1 Tag“.
4. Nutzer können vor dem Ablauf wie bisher Projekte und Exportdateien sichern.
5. Ablaufprüfung berücksichtigt Tageswechsel und Rückkehr aus Standby (§7).
6. Abschiedstext kennt den geplanten Start, ohne dessen tatsächliche Verfügbarkeit
   anhand der Kunden-Uhr zu behaupten.
7. Die Website-Adresse alter Demos bleibt erreichbar. Neue Texte in einer neuen
   Demo reparieren keine bereits ausgelieferte alte Binärdatei.

Kein Newsletter an vermeintlich bekannte Demo-Nutzer: Es gibt kein Demo-Konto
und keinen belegten vollständigen Verteiler. Supportkontakte und Spenden sind
keine automatisch freigegebenen Werbeverteiler. Der normale Informationsweg
bleibt App, Website und ein bewusst beauftragter öffentlicher Hinweis.

## §6 Start einer abgelaufenen Demo und Weg zur 1.0

### 6.1 Bereits ausgelieferte Demo

Der heutige Dialog ist der Bestand: Ablaufdatum, Hinweis auf erhaltene Dateien,
**Website öffnen**, **Schließen**. Er startet weder das Hauptfenster noch einen
Hintergrunddownload. Ein Doppelklick auf eine `.p3d` erreicht diese Sperre
ebenfalls; das Dokument wird dabei nicht gelöscht oder konvertiert.

Deshalb muss die **bestehende Startadresse der Website** am 31.10. den
Wartezustand und ab dem Verkaufsstart den Wechsel erklären. Eine nur auf einer
neuen Unterseite liegende Anleitung reicht für diese Nutzer nicht.

### 6.2 Letztes 0.x-Update – vorgeschlagener Abschied

Titel: **„Die Demo ist beendet“**

Text vor dem geplanten Start:

> Diese Demo war bis einschließlich 30. Oktober nutzbar. Am 31. Oktober
> bereiten wir die Verkaufsversion vor. Solidon3D 1.0 ist für den
> 1. November 2026 um 10:00 Uhr deutscher Zeit geplant.
>
> Ihre gespeicherten Projekte bleiben erhalten. Auf unserer Website finden
> Sie den aktuellen Stand und anschließend die Installation von 1.0.

Text ab dem geplanten Start, auch ohne Netz weiterhin wahr:

> Diese Demo ist beendet. Ob Solidon3D 1.0 bereits verfügbar ist, sehen Sie
> auf unserer Website. Installieren Sie dort die aktuelle Version.
> Zum Bearbeiten und Exportieren benötigen Sie eine Lizenz.
>
> Ihre gespeicherten Projekte bleiben erhalten.

Handlungen: **„Website öffnen“**, **„Schließen“**. Keine vermeintlich sofort
wirksame Schaltfläche „Freischalten“, wenn der eingegebene 1.x-Schlüssel in
dieser 0.x-Binärdatei ohnehin nicht angenommen werden kann.

Die technischen ZIP-/JSON-Erklärungen des bisherigen Texts sind kein Ersatz
für „Ihre Dateien bleiben erhalten“. Sie gehören höchstens in weiterführende
Hilfe. Ein Button zu einem konkreten Projektordner wäre nur zulässig, wenn
dieser tatsächlich bekannt ist; Projekte können an vielen Orten gespeichert sein.

### 6.3 Website-Ablauf ab Verkaufsstart

1. Besucher von einer alten Demo sehen: „Von der Demo zu Solidon3D 1.0“.
2. Kurze Erklärung: neue Installation erforderlich, Projekte bleiben erhalten,
   keine automatische Zahlung, keine neue kostenlose Testphase.
3. Passenden 1.0-Download auswählen oder Lizenz kaufen. Beide Wege sind möglich;
   ein Kauf darf nicht voraussetzen, dass die App schon aktiviert ist.
4. Vorhandene Demo normal schließen, ungespeicherte Arbeit sichern.
5. 1.0 installieren; danach wird die neue App gestartet.
6. Schlüssel eingeben → online oder per Dateiweg aktivieren (§9).
7. Vorhandenes Projekt öffnen; bei erstmaligem Speichern unter 1.0 die
   Bestandskopie erhalten (§10).

Für Offline-Nutzer: Die Website kann auf einem zweiten Rechner besucht werden.
Von dort kommen Installer und Aktivierungsdateien auf den Arbeitsrechner.
„Offline nutzbar“ bedeutet nicht, dass eine erste Freischaltung ohne jeden
Kontakt zum Aktivierungsdienst auf irgendeinem Gerät möglich wäre.

## §7 Laufende Sitzung über Mitternacht: Daten vor Fristdurchsetzung

**Ist-Lücke I03:** Das Programm kennt bisher keinen Wechsel des gespeicherten
Demo-Zustands während derselben Sitzung. Dauerbetrieb kann die Frist überleben;
ein Standby über mehrere Tage hat denselben Effekt. Das Konzept darf weder
„beendet sich exakt um Mitternacht“ noch „jede Demo stoppt sofort“ behaupten.

**Vorgeschlagene Regel für ein neues 0.x-Update:** Ab Ablauf beginnen keine
neuen Bearbeitungen, Chat-Aufträge, Exporte oder Slicer-Übergaben. Die App beendet
sich dabei niemals gewaltsam. Sie erlaubt das Sichern des vorhandenen Projekts.

### 7.1 Zustandsprüfung

- Die teure Signatur-/Geräteprüfung darf weiterhin gespeichert werden. Der
  kalenderabhängige Fristanteil muss beim Tageswechsel neu bestimmt werden.
- Jede geschützte Handlung prüft den aktuellen Fristzustand im Kern. Ein
  Oberflächen-Timer allein ist keine wirksame Grenze für CLI, Chat und Arbeiter.
- Ein UI-Timer und ein Aufwach-/Aktivierungsereignis aktualisieren die Anzeige.
  Vorschlag: spätestens 60 Sekunden nach Tageswechsel oder sofort bei Rückkehr
  in die App; die Handlungssperre gilt schon bei der ersten neuen Anforderung.
- Die Tageskorrektur darf keine Netzverbindung auslösen und keine
  gültige zeitlich unbegrenzte Kaufaktivierung beenden.

**Ergänzung nach Roberts Nachfrage zu Uhrumstellungen, 16.09.:** Die vorhandene
Uhrprüfung genügt nicht, um eine Verlängerung auszuschließen. Normale Sommer-/
Winterzeit ändert am 25.10. das Datum nicht und schenkt keinen zusätzlichen
Demotag. Zeitzonenwechsel nahe Mitternacht können dagegen das lokale Datum
verschieben; sie müssen zusammen mit dem höchsten bereits gesehenen Tag geprüft
werden. Eine über Rechnerneustarts absichtlich auf einem erlaubten Tag gehaltene
Uhr lässt diesen Höchstwert überhaupt nicht voranschreiten.

Die zwei authentisierten Marker helfen gegen einzelne gelöschte oder veränderte
Dateien. Sie liefern keine unabhängige Zeit. Bei Verlust beider Marker begrenzt
`DEMO_FROM` lediglich die angezeigte Zahl auf die gesamte Demodauer; dies
verhindert keinen Neustart dieser Dauer bei ebenfalls zurückgestellter Uhr.
Eine wiederhergestellte komplette Systemkopie kann auch beide Marker zurücksetzen.

**Zusätzliche Anforderungen an P2:**

- Ein erkannter Ablauf darf durch normales Zurückstellen der Uhr nicht wieder
  freigegeben werden. Den bisherigen pauschalen Zukunftsmarker-Rückfall ersetzen;
  echten Ablauf und korrigierbaren Uhrfehler ausdrücklich behandeln.
- Während einer laufenden Sitzung zusätzlich verstrichene monotone Zeit
  berücksichtigen, damit ein festgehaltenes Kalenderdatum die Sitzung nicht
  unbegrenzt verlängert. Standby-Verhalten je Plattform prüfen, nicht voraussetzen.
- Vorwärts-/Rückwärtssprünge, Zeitzonenwechsel, Neustart und fehlende Marker in
  Kombination prüfen. Ein isoliert grüner Rückstelltest genügt nicht.
- Eine versehentlich weit vorgestellte Uhr erhält einen nachvollziehbaren
  Korrekturweg; nicht einfach jedes spätere Zurückstellen als legitim behandeln.
  Die gewünschte Großzügigkeit des bisherigen Tests steht hier im Konflikt mit
  Roberts Anforderung, eine Verlängerung zu verhindern.

**Umgesetzter Teilfix vom 16.09.:** Ein plausibler Ablauf wird jetzt als
erster Tag nach dem Demo-Ende gespeichert und beim Rückstellen beibehalten.
Offensichtlich falsche Zukunftstage jenseits des vorhandenen einjährigen
Horizonts, bezogen auf das Demo-Ende, sperren nur den aktuellen Aufruf und
überschreiben keinen Marker. Damit kann auch ein Zwischenstart mit Uhr auf
2099 einen schon erkannten Ablauf nicht löschen. Alte Zukunftsmarker werden
nur jenseits dieses Horizonts korrigiert; ein plausibler erster Start bleibt
dabei als Untergrenze erhalten. Der Verlust eines der beiden Marker wird
weiter aus dem anderen geheilt.

**Bewusste Verhaltensänderung:** Eine nur wenige Tage falsch vorgestellte
Uhr über dem Demo-Ende löst nun einen bleibenden Ablauf aus; bloßes
Zurückstellen öffnet ihn nicht wieder. Die automatische Korrektur ist für
offensichtlich weit entfernte Zukunftstage vorgesehen. Ohne unabhängigen
Zeitnachweis lässt sich der knappe Irrtum nicht vom absichtlichen Rückstellen
unterscheiden. Noch nicht umgesetzt sind die Aktualisierung während einer
laufenden Sitzung, monotone Zeitmessung und ein zusätzlicher Korrekturweg.

**Offene Produktentscheidung innerhalb RM-061:** Auf einem vollständig vom
Nutzer kontrollierten Offline-Rechner sind echte Zeit, eingefrorene Uhr und
wiederhergestellter Systemzustand nicht zuverlässig allein aus lokalen Daten
zu unterscheiden. Ein strengerer Nachweis benötigt eine unabhängige,
authentisierte Zeitquelle, beispielsweise eine überprüfbare Serverauskunft
oder einen signierten Nachweis per Dateiweg. Eine einmalige Zeitbestätigung
verhindert für sich genommen keine späteren vollständigen Rücksetzungen.
Regelmäßige Onlinepflicht wird hier nicht still eingeführt; sie widerspräche
dem bisherigen Offline-Entwurf und müsste ausdrücklich entschieden werden.
Auch damit gibt es keine absolute Garantie gegen veränderte Programmdateien.
Die ehrliche Zusage bleibt bis zur Entscheidung: lokale Umgehungen erschweren
und bekannte Lücken schließen, keine behauptete vollständige Manipulationssicherheit.

### 7.2 Arbeit, die gerade läuft

Vorschlag: Vor dem Stichtag **bereits verbindlich gestartete** einzelne
Transaktionen oder Dateischreibvorgänge dürfen mit unveränderten Eingaben
sauber fertig werden oder kontrolliert abbrechen. Ihr Ergebnis darf gesichert
werden. Keine neue Vorschauvariation, keine Fortsetzung einer Chat-Werkzeugkette
und kein nachträglich eingereihter Folgeauftrag erbt daraus eine Freigabe.

Die Zulassung ist an genau den laufenden Auftrag gebunden; sie darf nicht als
allgemeiner Lizenzzustand gespeichert werden. Ist diese Begrenzung nicht
nachweisbar, wird der Auftrag kontrolliert verworfen und der letzte vollständige
Dokumentzustand bleibt erhalten. Insbesondere kein gewaltsames Stoppen eines
Threads mitten in einer Geometrie- oder Dateitransaktion.

### 7.3 Abschlussansicht

1. Neue Bearbeitungen werden gesperrt; offene Gestenvorschauen werden nicht
   heimlich zu neuen Verlaufsschritten.
2. Ein laufender zugelassener Auftrag wird mit Fortschritt/Abbrechen beendet.
3. Bei ungespeicherter Arbeit erscheint die begründete Auswahl
   **„Projekt speichern“**, **„Anderen Speicherort wählen“** oder
   **„Ohne Speichern schließen“**. Der letzte Weg verlangt die vorhandene
   Bestätigung vor Datenverlust.
4. Bei Schreibfehler bleibt die Sitzung im Sicherungszustand offen. Kein
   Ablauf-Timer verwirft danach doch das Dokument.
5. Abbruch des Speicherdialogs lässt den Sicherungszustand erhalten, schaltet
   Bearbeiten aber nicht wieder frei. Nach erfolgreichem Speichern kann der
   Nutzer Website oder Schließen wählen.

Diese Abschlussansicht öffnet **keine anderen Projekte** und wird nach einem
Neustart nicht zum dauerhaften kostenlosen Demo-Betrachter. Sie schützt die
bereits begonnene Arbeit. Für ältere Demos ohne dieses Update bleibt I03 eine
nicht nachträglich aus der Ferne reparierbare Eigenschaft; keine heimliche
Fernabschaltung als Ersatz.

## §8 Verhalten von 1.0 vor und nach der Aktivierung

| Zustand | Erlaubt | Sichtbarer nächster Schritt |
|---|---|---|
| 1.0, kein Schlüssel | Bestehende Projekte lesen, betrachten und auswerten; vorhandene freie Speicher-/Undo-/Redo-Wege gemäß I10 | „Zum Bearbeiten und Exportieren Solidon freischalten“; Lizenz eingeben oder kaufen |
| Schlüssel gültig, Gerät noch nicht aktiviert | Lesende Nutzung; keine geschützten Handlungen | „Diesen Rechner aktivieren“; online oder Dateiweg |
| Lizenz und Gerätezertifikat gültig | Voller Funktionsumfang, offline | Lizenzart im Über-Dialog; keine regelmäßige Kaufabfrage |
| Falsche Hauptversion oder ungültiger Schlüssel | Lesende Nutzung, soweit Installation intakt | Konkrete Ursache; richtige App installieren oder Schlüssel korrigieren |
| Beschädigte Installation | Eigener Fehlerzustand, keine Kaufaufforderung als Reparatur | Passendes Originalpaket neu installieren |
| Geräteabmeldung nicht bestätigt | Lokal gesperrte Freigabe bleibt gesperrt | Dieselbe Abmeldung erneut zustellen; kein zusätzlicher Geräteplatz durch Netzfehler |

„Lesend“ ist ein bestehender Lizenzzustand derselben App, keine neue Edition.
Die Detailabnahme muss auch freie Projektspeicherung, Undo/Redo und Antworten
auf Migrations-/Zuordnungsfragen einschließen. Modellimport, neue Dokumente
und jede versteckte schreibende Nebenhandlung müssen am tatsächlichen Datenpfad
geprüft werden; der Begriff „Betrachter“ darf hier keine ungeprüfte Zusage ersetzen.

Ein alter Demo-Marker startet in 1.0 keinen neuen Testzeitraum und blockiert
auch keinen gültigen Kauf. Kein Zurücksetzen aller Einstellungen und kein
Löschen der Marker als Installationsanleitung. Das Datum 01.11. öffnet 1.0
nicht kostenlos; das Ende des Aktionspreises im Februar sperrt sie ebenfalls nicht.

## §9 Kauf, Schlüsselzustellung und Aktivierung

### 9.1 Angebot

Bestätigte Preise: privat 69 €, gewerblich 199 € zum Start; ab 01.02.2027
privat 99 €, gewerblich 249 €. Jeweils Einmalkauf mit den vereinbarten
1.x-Aktualisierungen. Gewerblich bis zu zwei Personen desselben Unternehmens
an zwei freigeschalteten Rechnern, privat eine Person an einem freigeschalteten
Rechner. Beide Lizenzarten haben denselben Funktionsumfang.

Die bestehende Zusage aus EULA §5 bleibt erhalten: erforderliche Sicherheits-
und Funktionserhaltungsaktualisierungen mindestens bis 31.10.2031, für beide
Lizenzarten gleich. Diese Zusage ist nicht auf eine Hauptversion beschränkt;
sie verspricht weder neue Funktionen noch pauschal eine kostenlose Version 2.

Die rechtliche Preisangabe einschließlich Steuerdarstellung muss mit dem
tatsächlichen Checkout zusammenpassen; dieses Konzept entscheidet keine
umsatzsteuerliche Einordnung. Die Support-Antwortfrist gewerblicher Lizenzen
ist keine garantierte Behebung eines Aktivierungsausfalls binnen zwei Tagen.

### 9.2 Lieferkette – noch herzustellen und abzunehmen

Die bestehende Architektur sieht Checkout beim Merchant of Record und eigene
Ed25519-Kaufcodes vor. Lemon Squeezy ist der hier vorgesehene Anbieter;
seine Freischaltung für den realen Betreiber und seine Live-Konfiguration
sind **nicht** durch das Vorhandensein dieser Dokumentation belegt.

Der vollständige Weg:

1. Checkout bestätigt die bezahlte Bestellung über einen authentisierten
   Serverweg; die Rückkehr des Browsers allein gilt nicht als Zahlungsnachweis.
2. Webhook-Signatur über die unveränderte Nutzlast prüfen; nur bekannte
   Anbieter-/Produkt-/Variantenkennungen akzeptieren. Test- und Live-Ereignisse
   strikt trennen.
3. Bestellung und Positionen dauerhaft verbuchen. Je bezahlter Lizenzeinheit
   genau einen passenden privaten oder gewerblichen Code zuteilen. Bei
   Menge zwei werden zwei Lizenzen geliefert, nicht bloß zwei Geräteplätze.
4. Wiederholte oder gleichzeitig zugestellte Ereignisse liefern dieselbe
   Zuordnung. Eine Rückerstattung darf nicht durch ein verspätetes älteres
   Kaufereignis wieder als frischer Kauf erscheinen.
5. Schlüssel, Downloadlink und knappe Aktivierungsanleitung senden; ein
   Versandfehler bleibt als offener Lieferauftrag erhalten. Eine erfolgreiche
   SMTP-Annahme ist noch kein Beleg, dass die Nachricht beim Käufer gelesen wurde.
6. Erneuter Versand verwendet denselben Code. Keine zweite Lizenz als
   Nebenwirkung von „Mail nicht angekommen“.
7. Erst eine gültige lokale Aktivierung öffnet die geschützten App-Handlungen.

Lemon Squeezy dokumentiert Webhooks und die Signaturprüfung mit `X-Signature`
und HMAC-SHA256. Der eigene Code- und Zustellweg ist eine Solidon-Anforderung;
das vom Anbieter angebotene Lizenzsystem wird nicht ungeprüft als Ersatz für
Solidons eigenes Schlüsselformat eingesetzt. Quellen und Abrufdatum in §19.

**Leerer Vorrat:** Jede Lizenzart wird getrennt überwacht. Ein gültig empfangenes
Ereignis darf nur dann erfolgreich bestätigt werden, wenn Bestellung und offener
Lieferauftrag dauerhaft gesichert sind. Andernfalls Fehler zurückgeben, damit
Wiederholung möglich bleibt. Bereits bezahlte Bestellungen bleiben auffindbar.
Neue Verkäufe der betroffenen Variante pausieren; keine falsche Sofortlieferung
versprechen. Warnschwelle aus dem Bestandskonzept: zehn Codes je Art, vor dem
Start gegen erwartete Last und Reaktionszeit überprüfen.

### 9.3 Vorbereitung des Vorrats

- Verkaufscodes müssen **Hauptversion 1** tragen. Aus einem 0.x-Arbeitsbaum
  ist `--major 1` ausdrücklich anzugeben, da sonst Hauptversion 0 verwendet wird.
- Vorab erzeugte Codes erhalten gemäß bestehender Werkzeugregel
  `--purchased-on 2026-11-01`. Das tatsächliche Kaufdatum steht zusätzlich an
  der Bestellung; der Vorratsstempel ist kein Nachweis eines schon erfolgten Kaufs.
- Art explizit `--kind private` oder `--kind commercial`; vollständiges privates
  Archiv außerhalb des Repositorys; getrennte Vorräte und Herkunftsnachweise.
- Kein `--legacy` für den Verkaufsvorrat. Kein Lizenz-Hauptschlüssel auf dem
  Webserver, kein Schlüsselmaterial in Tickets, Protokollen oder diesem Konzept.
- Vorher prüfen: Server akzeptiert Format 2 und Hauptversion 1; aktive
  Datenbank hat die Migration für zwei gewerbliche Geräteplätze. Ein PHP-Diff
  oder eine erfolgreiche private Aktivierung beweist den zweiten Platz nicht.

### 9.4 Online und offline

Online: 1.0 installieren → Schlüssel einfügen → „Online aktivieren“ → gültiges
Gerätezertifikat lokal ablegen → dasselbe offene Projekt weiterbearbeiten.

Offline: 1.0 installieren → Schlüssel einfügen → Anfrage auf Datei schreiben
→ auf einem zweiten Gerät zur vorgesehenen Aktivierungsseite übertragen
→ Antwortdatei zurückbringen → auf dem ursprünglichen Rechner importieren.
Ein Zertifikat eines anderen Geräts muss abgewiesen werden.

Ein Timeout darf keinen zusätzlichen Platz verbrauchen: Wiederholung für
dasselbe Gerät muss dieselbe Belegung wiederfinden. Beide gewerblichen Nutzer
führen den Vorgang an ihren jeweiligen Rechnern aus. Nach erfolgreicher
Aktivierung bleibt die App ohne Netz nutzbar; ein späterer Serverausfall darf
eine vorhandene dauerhafte Aktivierung nicht beenden.

### 9.5 Bestandscodes, Rückerstattung, Gerätewechsel

Vor dem Start gibt es eine private Bestandsliste: Hauptversion, Format, Art,
Ausstelltag, Zweck und bestehende Zusage jedes schon ausgegebenen Codes.
Ein Format-1-Code wird nicht deshalb ungültig, weil Format 2 erscheint. Ein
0.x-Code wird aber auch nicht automatisch zum 1.x-Code. Ersatz oder Freiexemplar
ist eine ausdrückliche Entscheidung mit Zuordnung im Archiv.

Rückerstattungen sperren entsprechend der Vertragsentscheidung künftige
Aktivierungen; ein bereits dauerhaft offline arbeitendes Gerät kann nicht
zuverlässig aus der Ferne abgeschaltet werden. Das ist eine bekannte Grenze
des zugesagten Offline-Modells, kein Anlass für nachträgliche Dauerabfragen.
Gerätewechsel und verlorene Rechner folgen dem vorhandenen Abmelde-/Supportweg.

## §10 Projekte, Einstellungen und Installation

### 10.1 Was erhalten bleiben muss

Projekte am gewählten Speicherort, Wiederherstellungsdateien, zuletzt geöffnete
Projekte, Drucker-/Materialprofile, Filamentbestand, eigene Bausteine,
Oberflächeneinstellungen und Zugangsdaten im System-Schlüsselbund. Ein Update
darf keine Erstinstallation vortäuschen, um seine Lizenzanzeige zu vereinfachen.

Die Datenpfade bleiben dieselben. Insbesondere unter Windows:
`%APPDATA%/RS Digital/Solidon3D` für Einstellungen und
`%LOCALAPPDATA%/RS Digital/Solidon3D` für lokale Daten. Projekte müssen nicht
dort liegen. Flatpak hat seine eigene Sandbox; ein Wechsel von AppImage zu
Flatpak ist deshalb ein zusätzlicher Migrationsfall, nicht automatisch ein
gewöhnliches Update im selben Nutzerverzeichnis.

### 10.2 Projektmigration

Die App-Hauptversion allein erhöht nicht das Dateiformat. Die konkrete
1.0-Dateiformatversion ergibt sich aus den bis dahin tatsächlich nötigen
Migrationen. Alle unterstützten alten Migrationen bleiben erhalten.

Abnahme mit echten Demo-Projekten: Öffnen, vollständige Auswertung,
Projektparameter, Fremdquellen, Bausteine, Materialzuordnung und erneutes
Speichern/Laden. Alte enthaltene OpenSCAD-Schritte werden nach der bestehenden
Migrationspolitik behandelt; das Übergangskonzept verspricht keine Wiederkehr
entfernter Ausführungspfade.

**Vorschlag für die erste Speicherung unter 1.0:** Vor dem Überschreiben einer
älteren Projektdatei eine eindeutige, nicht überschreibende Sicherung der
Originalbytes anlegen. Schlägt sie fehl, „Speichern unter“ anbieten oder abbrechen;
nicht trotzdem das Original ersetzen. Öffnen allein schreibt nichts zurück.
Ein abgebrochener Speichervorgang lässt das Original lesbar.

Eine Rückkehr zur Demo ist nach dem Stichtag kein verlässlicher Rettungsweg,
und eine ältere Version kann ein neueres Dateiformat nicht zwingend lesen.
Die Sicherung ist deshalb vorwärtsgerichteter Datenschutz, kein Versprechen
vollständiger Rückwärtskompatibilität.

### 10.3 Paketmatrix

| Plattform | Übergang | Unverzichtbare reale Probe |
|---|---|---|
| Windows | Bestehende Installation mit unveränderter Produktkennung aktualisieren; App vorher sauber schließen | Nutzerinstallation und Admininstallation, Dateizuordnung, vorhandene Profile, Abbruch bei ungespeicherter Arbeit, Neustart in 1.0 |
| macOS Intel / Apple Silicon | Passendes geprüftes PKG installieren | Signatur/Notarisierung, richtige Architektur, Schlüsselbund, bestehende Einstellungen und Projekt-Doppelklick |
| Linux AppImage | Neue Datei herunterladen und starten; alte Verknüpfung gegebenenfalls ersetzen | Ausführbarkeit, Desktop-Verknüpfung zeigt auf 1.0, ursprüngliche Datenpfade bleiben erhalten |
| Linux Flatpak | Vorhandenes Paket derselben App-ID aktualisieren | Host-Installation, Sandbox-Daten, Datei-/Schlüsselbundzugriff, Neustart |

Nicht anbieten: Deinstallation mit Datenbereinigung als normaler erster Schritt.
Keine Behauptung „unter allen Plattformen geprüft“, wenn nur Python-Tests liefen.

## §11 Website, Updatehinweis und öffentliche Texte

### 11.1 Drei veröffentlichte Zustände

**Vor Ablauf:** Demo bis 30.10., geplante Pause am 31.10., Verkauf ab
01.11. um 10:00 Berlin. Keine Kaufmöglichkeit vortäuschen, solange sie fehlt.

**Pause:** „Die Demo ist beendet. Am 31. Oktober optimieren wir die
Verkaufsversion. Geplanter Start: 1. November, 10:00 Uhr deutscher Zeit.
Ihre gespeicherten Projekte bleiben erhalten.“ Bestehende Hilfe, Support,
Impressum, Datenschutz und Sicherheitskontakt bleiben erreichbar.

**Nach Freigabe:** Download und Kauf der geprüften 1.0, beide Lizenzarten,
Endpreise und der verständliche Wechselweg. Englische, spanische, französische,
italienische und portugiesische Seiten müssen dieselbe Verfügbarkeit nennen.

Bei Verzögerung ersetzt eine konkrete Statusmeldung den abgelaufenen Countdown.
Keine Seite darf allein wegen `Date.now()` „jetzt verfügbar“ behaupten.
JavaScript ist Anzeige, keine Verkaufsfreigabe; auch ohne JavaScript und bei
einem direkten Checkout-Link gelten dieselben serverseitigen Angebotsgrenzen.

### 11.2 Versionsdatei

`website/version.json` bleibt das signierte Register **wirklich verfügbarer**
Pakete. Kein Vorabumschalten auf 1.0, solange Kauf-/Aktivierungsweg und Pakete
nicht abgenommen sind. Jede Änderung wird neu signiert. Paketdateien werden
unter eindeutigen Namen vollständig hochgeladen und geprüft, dann wird die
Versionsdatei veröffentlicht. Unter demselben Namen niemals andere Bytes ersetzen.

Die letzte Demo muss die veröffentlichte Signatur weiterhin prüfen können.
Der aktuelle Prüfer verwendet genau einen `RELEASE_PUBLIC_KEY`; ein beim
Hauptversionswechsel bloß ausgetauschter Signierschlüssel würde diesen Weg
unterbrechen. Den vorhandenen Release-Schlüssel beim Übergang beibehalten;
eine notwendige Schlüsselrotation benötigt vorab einen gesondert geprüften
Übergang für Bestandsinstallationen und gehört zu T29.

Während der Pause wird eine alte Demo nicht dadurch wieder geöffnet, dass
`version.json` weiterhin 0.x nennt. Die Website muss unabhängig davon klarstellen,
dass die Demo beendet ist. Im Update-Hinweis der letzten Demo steht beim
Hauptversionswechsel: „1.0 ist die Verkaufsversion. Zum Bearbeiten und
Exportieren benötigen Sie eine Lizenz.“ Kein unkommentierter Wechsel von
kostenloser Bearbeitung zu gesperrter Bearbeitung.

### 11.3 Rechtstexte und Checkout

Keine neue kostenlose Testphase bedeutet **nicht** automatisch kein gesetzliches
Widerrufsrecht. Für vorzeitige digitale Lieferung müssen der tatsächliche
Checkout und die Vertragsbestätigung die einschlägigen Voraussetzungen tragen;
eine aktivierte Checkbox in einer lokalen HTML-Vorlage beweist das nicht.
Aktueller amtlicher Bezug: §356 Abs. 6 BGB, Abruf 16.09.2026 (§19).

EULA und AGB müssen vor dem Kauf erreichbar und wirksam einbezogen sein;
der bisherige Demo-Hinweis, dass Verkaufstexte noch nicht gelten, wird beim
echten Verkauf passend umgestellt. Datenschutz umfasst den wirklichen
Zahlungs-, Schlüsselzustellungs- und Aktivierungsweg. Bestehende offene
rechtliche Prüfungen bleiben unter RM-093; dieses Konzept erteilt keine Freigabe.

## §12 Der 31. Oktober: Optimieren, bauen, entscheiden

**Der Tag ist kein bereits öffentlicher 1.0-Betrieb.** Es wird an internen
Kandidaten optimiert und geprüft. Bis dahin vorbereitete Abwicklung und Pakete
geben Zeit für genau diesen Zweck.

Vorgeschlagener Tagesablauf:

| Zeitpunkt Europe/Berlin | Arbeit und erforderliches Ergebnis |
|---|---|
| 00:00 | Website-Wartezustand kontrollieren; normaler Demo-Start auf deutschem Rechner endet mit Erklärung. Support und Hilfe bleiben erreichbar. |
| Vormittag | Letzte priorisierte Optimierungen: Fehler, Wartezeiten, unklare Abläufe. Jede Änderung erhält betroffene Tests. Änderungen mit hohem Migrations-/Lizenzrisiko ausdrücklich bewerten. |
| Nachmittag | Den vorgesehenen Stand auf allen angebotenen Plattformen bauen; Änderungen an Grenzdateien verlangen neu gebautes Prüfmodul und Manifest. |
| 18:00 | Zwischenprüfung: Was fehlt noch, welche Laufzeiten haben Tests, Signierung und Upload? Keine automatische Freigabe anhand der Uhr. |
| Abend | Vollständiges Prüftor und reale Installation/Aktivierung/Migration am tatsächlich auszuliefernden Kandidaten. Pakete signieren und Releaseakte vervollständigen. |
| Spätestens vor Veröffentlichung | Eine eindeutig benannte Endfassung mit Commit, Version, Prüfsummen, Signierstatus, Abnahme und Rückfallweg liegt bereit. |

Eine Optimierung nach dem letzten erfolgreichen Pakettest macht das betroffene
Paket wieder zu einem Kandidaten. Die alte Abnahme darf nicht unter ein neu
gebautes Programm geschrieben werden. Wenn Bauzeiten nicht mehr passen,
verschiebt sich die Veröffentlichung; die Abnahme wird nicht verkürzt, um
den Countdown zu erfüllen.

Die genauen Zwischenzeiten sind Planvorschläge. Das feste Ergebnis ist:
Der 31.10. steht für Optimierung bereit, und am 01.11. wird nur ein nachweislich
nutzbarer und kaufbarer Stand angeboten.

## §13 Veröffentlichung am 1. November

Vorgeschlagener Ablauf mit betreutem Start um 10:00 Uhr:

| Zeit Europe/Berlin | Handlung |
|---|---|
| 08:30 | Verantwortlicher verfügbar; Server, Signier-/Uploadzugang, Checkout, Mailzustellung, Vorräte und letzte Abnahmen prüfen. |
| 09:00 | Produktionskonfiguration gegen den freigegebenen Plan vergleichen; Sicherung von Datenbank und öffentlichem Seitenstand bereithalten. |
| 09:30 | Alle vorgesehenen Paketdateien in einem geschützten Bereitstellungsbereich vollständig übertragen und ihre Bytes/Hashes prüfen; öffentliche Zieladressen und Freigabeschritt vorbereiten. |
| 09:45 | Entscheidung „Start freigegeben“ oder „verschoben“ mit konkretem Commit und Paketliste. Direkte Kaufwege sind bis zum Start gesperrt. |
| 10:00 | Paketdateien öffentlich freigeben und Abruf prüfen, geprüfte 1.0-Download-/Übergangsseiten freigeben, Checkout aktivieren, sichtbare Kaufverweise freigeben; zuletzt passende signierte Versionsdatei veröffentlichen. |
| Unmittelbar danach | Alle sechs Sprachseiten, Paketadressen, Downloadgrößen/-Hashes, Checkout und Zustellung von außen gegenprüfen. |
| 10:00–12:00 | Bestellungen, ausstehende Zustellungen und Aktivierungsfehler betreuen; nur erforderliche Betriebsdaten, keine App-Nutzungstelemetrie. |
| Tagesende | Tatsächliche Freigabezeit, Paketstand, Störungen und Maßnahmen in der Releaseakte festhalten. |

Der Übergang zwischen Website und Checkout ist nicht atomar. Deshalb werden
die Reihenfolge und die kurzen Zwischenzustände bewusst geprüft: kein
sichtbarer Kaufknopf auf einen noch unbrauchbaren Lieferweg, kein bezahlter
Schlüssel ohne verfügbares 1.0-Paket. Das Verbergen eines Buttons allein
deaktiviert keinen bereits bekannten direkten Checkout-Link.

Der vorgeschlagene geschützte Bereitstellungsbereich verhindert, dass 1.0 schon
vor 10:00 unter einer bekannten Paketadresse öffentlich heruntergeladen wird.
Bloß schwer erratbare Dateinamen sind kein Zugriffsschutz. Der vorhandene
Uploadweg und der Freigabeschritt müssen dafür vorab geprüft werden; geschütztes
Bereitstellen ist hier ein Plan, kein bereits nachgewiesenes Servermerkmal.
Vor 10:00 wird weder ein öffentlicher Kauf noch eine automatische Installation
ausgelöst. Scheitert der öffentliche Paketabruf um 10:00, bleibt der Checkout
geschlossen, bis ein nutzbarer Lieferweg nachgewiesen ist.

**Keine globale Wartungsabschaltung am 31.10.** Website, Support und bereits
eingerichtete Aktivierungswege bleiben soweit möglich erreichbar. Der
Optimierungstag sperrt die abgelaufene Demo, nicht den gesamten Webspace.

## §14 Fehlerfälle und Rückfallwege

| Fehler | Verhalten für Nutzer | Maßnahme im Betrieb |
|---|---|---|
| 1.0 ist am 01.11. um 10:00 nicht freigabefähig | Statusmeldung mit neuem Prüfzeitpunkt; kein falscher Kaufknopf | Verkauf geschlossen halten, Ursache benennen. Neue Demo-Frist nur nach ausdrücklicher Produktentscheidung und neuem Bau. |
| Nutzer startet eine alte Demo nach Monaten | Ablaufmeldung → dauerhafte Website-Anleitung | Alte Einstiegsadresse nicht entfernen. |
| Kein Internet am Arbeitsrechner | Erklärung bleibt lokal lesbar; Installation und Aktivierung über Zweitgerät | Dateiweg dokumentiert und am echten Paket geprüft. |
| Website vorübergehend nicht erreichbar | Kein Datenverlust; vorhandene aktivierte 1.0 läuft weiter | Öffentliches Hosting wiederherstellen; Supportkanal und lokale Meldung geben keine falsche Verfügbarkeit aus. |
| Zahlung bestätigt, Schlüsselmail fehlt | Nicht erneut kaufen; Bestellung und Supportweg nennen | Denselben zugeordneten Schlüssel erneut senden; offene Lieferaufträge nacharbeiten. |
| Lizenzvorrat leer oder Zustellung gestört | Ehrliche Lieferstatusmeldung | Verkäufe betroffener Art pausieren, bezahlte Aufträge dauerhaft halten und nachliefern. |
| Aktivierungsserver ausgefallen | Neuer Käufer kann noch nicht bearbeiten; bestehende Aktivierungen bleiben nutzbar | Fehler sichtbar melden, Wiederholung anbieten; kein heimlicher Legacy-Schlüssel als Automatismus. |
| Zwei gewerbliche Aktivierungen scheitern am alten Datenbankindex | Konkreter Geräteplatzfehler statt wiederholtem Kauf | Vor Verkaufsstart Migration abnehmen; bei Vorfall Dienst korrigieren, keine zusätzliche Lizenz berechnen. |
| Signatur oder Paket-Hash ungültig | Keine Installation | Falsche Veröffentlichung stoppen; richtige signierte Metadaten und geprüfte Pakete liefern. |
| Installation von 1.0 scheitert | Gespeicherte Projekte bleiben erhalten; konkrete Plattformhilfe | Reparaturpaket oder korrigierten Installer liefern; alte Demo nach Fristende ist kein funktionierender Ersatz. |
| Falsche Systemuhr | Keine Löschung oder Kürzung einer Kaufaktivierung; Uhr prüfen lassen | Demo bleibt lokales Zeitmodell mit begrenzter Manipulationsabwehr, kein vertrauenswürdiger Zeitserver wird nachgerüstet. |
| Schlüsselbund zeitweise gesperrt | Aktivierungsproblem benennen; Wiederholung möglich | Bestehendes Zertifikat nicht als vermeintliche Altlast löschen. |
| Fehlerhafter 1.0-Stand bereits verteilt | Klare Statusmeldung; eigene Projekte sichern | Korrigierte höhere 1.x-Version anbieten oder Kauf pausieren; nicht nur `version.json` auf 0.x zurücksetzen. |
| Rollback des Servers nach echten Bestellungen | Keine Doppelzuteilung, kein Verlust bezahlter Aufträge | Bestellungen und Aktivierungen seit der Sicherung abgleichen; kein blindes Zurückspielen einer alten Datenbank. |

Ein ausgelieferter schlechter 1.0-Bau wird nicht durch Überschreiben derselben
Versionsdatei unter demselben Paketnamen „repariert“. Bereits heruntergeladene
Kopien verschwinden dadurch nicht. Korrigierte Pakete tragen eine höhere
Version und neue Prüfsummen; die Projektformatverträglichkeit ist mitzubelegen.

## §15 Abnahmematrix

Alle folgenden Fälle sind **noch abzunehmende Anforderungen des Übergangs**,
sofern §18 nicht ausdrücklich einen bereits gefahrenen Teilnachweis nennt.
Ein grüner Teiltest ersetzt nicht die reale Installations- oder Kaufprobe.

| ID | Ausgangslage / Handlung | Erwartetes Ergebnis |
|---|---|---|
| T01 | Frischer Demo-Start am 30.10. | Alle normalen Funktionen frei; Datum verständlich angezeigt. |
| T02 | Frischer Demo-Start am 31.10. | Nur Ablaufmeldung, kein Hauptfenster, Dateien unverändert. |
| T03 | Frischer Demo-Start am 01.11. vor und nach 10:00 | Alte Demo bleibt gesperrt; Website ist der Wechselweg. |
| T04 | Laufende letzte Demo über 30.10. → 31.10. | Kein neuer geschützter Auftrag, gespeicherte Zustände aktualisiert. |
| T05 | Standby am 30.10., Aufwachen am 01.11. | Vor erster neuer Handlung Ablauf erkannt. |
| T06 | Ungespeichertes Projekt, offener Gesteneditor und laufender Arbeiter beim Ablauf | Kein Datenverlust; nur definierter Auftrag darf abschließen, keine späte Folgeänderung. |
| T07 | Speichern scheitert / wird abgebrochen | Sicherungszustand bleibt, anderer Zielort möglich, kein erzwungenes Schließen. |
| T08 | CLI wird nach Ablauf neu gestartet / läuft schon über die Grenze | Startsperre beziehungsweise erneute Prüfung vor geschützter Folgehandlung. |
| T09 | Rechner in verschiedenen Zeitzonen, plausible Uhr | Lokaler letzter Demotag; Website benennt denselben globalen Verkaufsstart. |
| T10 | Uhr/Marker-Kombinationsprüfung: Sommer-/Winterzeit, Zeitzonenwechsel, 29.10. → 31.10. → 29.10., eingefrorenes Datum, Neustart, Verlust beider Marker und Systemrücksetzung | Erkannter Ablauf wird durch Rückstellen nicht aufgehoben; laufende Sitzung berücksichtigt verstrichene Zeit; versehentliche Zukunftsuhr hat definierten Korrekturweg. Offline-Grenzen und die dafür noch nötige Produktentscheidung aus §7.1 werden ausdrücklich ausgewiesen. |
| T11 | Ältere unveränderte Demo ohne Übergangsupdate | Alter Website-Button führt noch zur vollständigen Anleitung. |
| T12 | Demo mit ausgeschalteter Updateprüfung | Kein erzwungener Netzabruf; trotzdem lokaler Frist-/Wechselhinweis. |
| T13 | 1.x-Schlüssel wird in 0.x eingegeben | Klare Erklärung zum Installieren der 1.0; kein zweiter Kauf empfohlen. |
| T14 | 1.0 frisch installiert oder über Demo installiert, ohne Schlüssel | Keine kostenlose Testphase; startfähiger lesender Zustand mit Freischaltweg. |
| T15 | Alte Demo-Marker, Zukunftsmarker und beschädigte Marker in 1.0 | Keine neue Testphase; gültige Kaufaktivierung bleibt unabhängig davon. |
| T16 | Privater Kauf und erster Geräteplatz | Genau ein passender 1.x-Code, erfolgreiche Aktivierung und Offline-Neustart. |
| T17 | Gewerblicher Kauf, zwei Rechner, dritte Anfrage | Zwei Geräte funktionieren gleichzeitig; dritter Platz wird erklärbar abgewiesen. |
| T18 | Wiederholte Aktivierung nach Timeout | Kein weiterer Platz verbraucht; vorhandener Platz wird wiedergefunden. |
| T19 | Offline-Dateiweg, falsches Gerät, veränderte Antwort | Richtige Antwort aktiviert nur das ursprüngliche Gerät; falsche wird abgewiesen. |
| T20 | Schlüsselbund vorübergehend gesperrt | Fehler behandelbar, Zertifikat bleibt erhalten. |
| T21 | Kaufwebhook doppelt, parallel, falsche Signatur oder Testmodus | Keine Doppelzuteilung; unberechtigte Ereignisse ohne Wirkung. |
| T22 | Zwei Lizenzen in einer Bestellung / gemischte Produkte | Richtige Anzahl und Art; keine Verwechslung mit Geräteplätzen. |
| T23 | Bezahlt, Vorrat leer / Mailversand gestört | Dauerhafter offener Lieferauftrag; später derselbe Code, Betreiberalarm. |
| T24 | Erstattung vor verspätetem Kaufereignis / nach Aktivierung | Keine Wiederbelebung durch Ereignisreihenfolge; Offline-Grenze bleibt ehrlich. |
| T25 | Echter Demo-Projektkorpus → 1.0 | Öffnen/Auswerten, Parameter, Quellen, Materialien und Speichern/Laden erhalten; Originalkopie vorhanden. |
| T26 | Rückkehr zu älterem Programm nach Speichern in neuerem Format | Verständliche Versionsmeldung; Bestandskopie verfügbar, keine stille Beschädigung. |
| T27 | Windows-Nutzer/Admin, beide Macs, AppImage, Flatpak | Richtige Pakete und Datenpfade; Installation und Aktivierung am fremden System belegt. |
| T28 | Hauptversionsupdate mit ungespeicherter Arbeit | Kaufhinweis vor Installation; Speichern/Abbruch funktioniert; Installer nicht vorschnell gestartet. |
| T29 | Ungültige Release-Signatur, falscher Hash, unvollständiger Download | Kein Start des Installers; definierter Wiederholungsweg. |
| T30 | Alle sechs Sprachseiten, JavaScript aus, direkter alter Link | Gleicher Angebotszustand, kein vorzeitiger Kauf, funktionierende Übergangshilfe. |
| T31 | Freigabe bewusst verzögert, Uhr überschreitet 10:00 | Wartetext bleibt wahr, Checkout geschlossen, keine Veröffentlichung nur durch Countdown. |
| T32 | Live-Kauf nach Start sowie gesicherter Wiederholungs-/Erstattungsfall | Zahlung → eigener Schlüssel → passende Aktivierung → Offline-Neustart vollständig nachgewiesen. |

Für Zeitproben wird eine injizierte Uhr beziehungsweise ein isoliertes
Testsystem verwendet. Die Uhr eines produktiv verwendeten Arbeitsrechners
wird dafür nicht verstellt. Paketprüfungen finden mit getrennten Testprofilen,
Testschlüsseln und eindeutigem Test-/Live-Modus statt.

## §16 Freigabekriterien und Verantwortlichkeiten

Ein Start ist freigegeben, wenn **alle** folgenden Nachweise zum selben
auszuliefernden Stand gehören:

1. Keine offenen bekannten Datenverlust- oder Startblocker der Wechselstrecke.
2. Frist-/Sitzungs-/Projektfälle der letzten Demo erfüllt oder für nicht
   aktualisierbare Altversionen ausdrücklich als Bestandseinschränkung dokumentiert.
3. 1.0 enthält keinen Demo-Stichtag und kein ungeplantes Testangebot.
4. Alle tatsächlich angebotenen Plattformpakete sind gebaut, entsprechend dem
   vorgesehenen Verfahren signiert und auf fremden Zielsystemen geprüft.
5. Produktionsdienst beherrscht beide Lizenzarten einschließlich zweitem
   gewerblichen Geräteplatz; Kauf- und Dateiaktivierung funktionieren.
6. Checkout, eigene Schlüsselzustellung, Vorratsalarm, erneuter Versand und
   Supportweg sind real geprüft; rechtliche Freigaben sind dokumentiert.
7. Projekte und Nutzerdaten bleiben über den Installationswechsel erhalten.
8. Öffentliche Seiten, Pakete und signierte Versionsdatei sind konsistent;
   Freigabe und Rückfall sind von Robert ausführbar.

Robert ist bis zur Benennung einer Vertretung für die Startentscheidung und
Störungsmaßnahmen verantwortlich. Eine Vertretung benötigt vorher geprüfte,
getrennte Zugänge und eine konkrete Aufgabe; kein in einem Konzept genannter
Name ersetzt Bereitschaft. Für den 31.10. und 01.11. müssen Feiertag/Wochenende
und die tatsächliche Verfügbarkeit externer Dienste mitgedacht werden.

Wenn ein zwingender Nachweis fehlt, ist der Zustand **„nicht freigegeben“**.
Eine verlängerte Demo ist eine mögliche spätere ausdrückliche Entscheidung,
aber kein automatisch auszulösender Rückfall. Das Beenden der Demo allein
verpflichtet das System nicht dazu, ungeprüfte Software zu verkaufen.

## §17 Umsetzung in prüfbaren Paketen

Diese Tabelle beschreibt den vorgeschlagenen Zuschnitt; der Arbeitsstatus
bleibt bei RM-061 und den verknüpften Punkten. Die Aufwandsspannen sind relativ:
S klein, L mehrere zusammenhängende Pfade, XL dienst- und plattformübergreifend.
Jedes Paket muss vor einem später beauftragten Commit sein erforderliches
Prüftor erfüllen; dieses Dokument beauftragt keine Implementierung.

| Paket | Umfang / Quelle | Aufwand | Nachweis vor Übergabe | Rückfall |
|---|---|---|---|---|
| P1 | Übergangstexte und letzte Demo, §§5–6/11; sechs Sprachen | L | T01–03, T11–13, T30; echte sichtbare Dialoge | Noch nicht veröffentlichte Texte korrigieren; alte URLs beibehalten |
| P2 | Frist bei Tageswechsel und Sicherungszustand, §7 | L | T04–10 einschließlich realem Arbeiter, Save-Abbruch und Standby | Kandidat nicht ausliefern; keine nachträgliche Fernsperre |
| P3 | 1.0-Bauwerte und Projekt-/Profilübergang, §§8/10 | L | T14–15, T25–28 mit Demo-Dateien und fertigen Paketen | Originaldateien erhalten, korrigierter höherer 1.x-Bau |
| P4 | Kaufzuordnung, Zustellung und Vorräte, §9; RM-092 | XL | T16, T21–24, T32; Dienst-, Wiederholungs- und Ausfallprobe | Verkauf pausieren, offene Bestellungen sicher nachliefern |
| P5 | Produktionsaktivierung beider Lizenzarten; RM-182 | L | T17–20; tatsächliche Datenbankmigration und Dateiweg | Gesicherte, migrationsverträgliche Dienstfassung; bestehende Zertifikate respektieren |
| P6 | Website-/Checkout-/Versionsumschaltung, §§11–14 | L | T29–31; öffentliche Probe ohne echten unbeauftragten Kauf | Warteseiten und geschlossener Checkout; keine alte Bestelldatenbank einspielen |
| P7 | Generalprobe und Endabnahme, §§12–16 | XL | Vollständige Matrix, Freigabeprotokoll und betreuter Start | Explizite Startverschiebung mit Statusmeldung |

**Reihenfolge:** P1/P2 müssen vor dem Demo-Ende bei den Nutzern ankommen können.
P3–P6 werden vor dem 31.10. vorbereitet. Der 31.10. bleibt für letzte Optimierungen
und P7; der eigentliche öffentliche Umschaltpunkt ist erst am 01.11. um 10:00.
Eine Änderung an einem früheren Paket zieht dessen betroffene Nachweise nach.

Übergabeakte je Paket: Commit, tatsächlich geänderte Quellen, betroffene
Akzeptanzfälle, Testausgänge, native Nachweise, noch ungeprüfte Plattformen und
Abweichungen von den Entscheidungen A–K. Keine ausschließlich mündliche
Übergabe zwischen Rechnern; `.webserver.json` und private Signierschlüssel
reisen dabei ausdrücklich nicht im Git-Commit.

## §18 Verifikation dieser Konzeptarbeit

Am 16.09.2026 ausgeführt:

- Git- und Quellvergleich am Stand `d20104b0`, einschließlich Vergleich der
  Ablaufgrenzen mit dem Tag `v0.4.2`.
- `python -m pytest -q tests/test_activation.py tests/test_licence_boundary.py`
  über `.venv/Scripts/python.exe`: **118 bestanden, 2 übersprungen, Exit 0**.
  Die Übersprünge sind im Gesamtergebnis enthalten; sie werden nicht als
  bestandene Plattformnachweise ausgegeben.
- Isolierte Datumsprobe mit gemocktem Markerzugriff, ohne Schreiben in das
  echte Benutzerprofil: 30.10. → `(1, unlocked=True, over=False)`;
  31.10. und 01.11. → `(0, unlocked=False, over=True)`.
- Probe des Zustandszwischenspeichers: Zwei Aufrufe verwenden denselben ersten
  offenen Zustand; der vorbereitete zweite abgelaufene Zustand wird nicht
  abgefragt. Belegt I03, keine simulierte native Mitternachtsabnahme.
- Verkaufskonfiguration mit beiden Fristwerten `None`: null freie Tage.
- Nachprüfung der Uhrkorrektur: `store.days_left` mit im Speicher fortgeschriebenen
  Markern und ohne Profilzugriff für 29.10. → 31.10. → 29.10. aufgerufen.
  Ergebnis **2 → 0 → 2 Resttage**, Prozess Exit 0: reproduzierter Fehler I03a,
  ausdrücklich kein bestandener Schutztest. Bestehende Tests erlauben die
  Zukunftsuhr-Korrektur und begrenzen bei fehlenden Markern nur die Tageszahl;
  sie beweisen keinen Schutz gegen Verlängern der realen Nutzungszeit.
- Anschließender Reparaturauftrag: Elf neue Regressionsfälle waren vor der
  Änderung rot. Nach dem Teilfix bestanden `tests/test_activation.py` und
  `tests/test_licence_boundary.py` zusammen **130 Tests, zwei übersprungen,
  Exit 0**. Geprüft sind auch der öffentliche Aktivierungszustand nach
  Cache-Neustart, beide möglichen einzeln gelöschten Marker, der Umweg über
  eine Uhr auf 2099 sowie alte plausible und unplausible Marker. Diese Tests
  verwenden echte Markerdateien in isolierten Testprofilen.
- Breite Nachprüfung des Teilfixes: Der Importgraph erfasst 253 von 289
  Testdateien. Deshalb wurde der geteilte Gesamtlauf gestartet. Seine erste
  Sammelgruppe endete mit **19 Fehlern, 10.658 bestandenen und 188
  übersprungenen Tests**. Die Fehler betreffen die bereits vor der Reparatur
  aufgefallenen anderen Bereiche, unter anderem Profilklemmungen,
  Bausteinzahlen und Registerbeschreibungen. Der verbleibende Gesamtlauf wurde
  nach diesem Ergebnis beendet; kein grüner Gesamtnachweis und kein neuer
  Leistungslauf. Ruff nach Korrektur einer zu langen Test-Docstring-Zeile,
  Formatprüfung und mypy sind grün. Protokolle:
  `C:/Users/roschneider/AppData/Local/Temp/solidon-demo-clock-a5df43b016344fb38e2774cc0a29f1b7/`.
- Zeitumrechnung mit Windows `TimeZoneInfo`: 01.11.2026 10:00 Europe/Berlin
  entspricht 09:00 UTC; Pause in Deutschland 34 Stunden. Ein erster zusätzlicher
  Versuch mit Python `zoneinfo` scheiterte an fehlendem `tzdata`; die
  Datums-/Cacheprobe wurde anschließend vollständig mit Exit 0 wiederholt.

Nicht ausgeführt: neuer Paketbau, Installation eines 1.0-Kandidaten, Änderung
des Systemdatums, Live-Kauf, Versand an Dritte, Produktionsaktivierung,
Website-Upload oder Freigabe der rechtlichen Texte. Die Tests belegen den
untersuchten Bestand und den genannten Teilfix, **nicht** die übrigen noch
vorgeschlagenen Änderungen. Der früher in
dieser Sitzung abgebrochene vollständige Lauf mit 19 Fehlern des damaligen
Anwendungsstands ist kein grüner Release-Nachweis.

## §19 Externe Quellen und erneute Prüfung vor dem Verkauf

Abgerufen am **16.09.2026**, ausschließlich als Quellen für die jeweils
genannten Teilfragen:

- [Lemon Squeezy: Webhooks](https://docs.lemonsqueezy.com/help/webhooks):
  Ereigniszustellung und erneutes Senden; keine Bestätigung, dass Solidons
  eigener Lieferweg bereits eingerichtet ist.
- [Lemon Squeezy: Signing requests](https://docs.lemonsqueezy.com/help/webhooks/signing-requests):
  Prüfung der Webhook-Nutzlast mit `X-Signature` und HMAC-SHA256.
- [Lemon Squeezy: Webhook requests](https://docs.lemonsqueezy.com/help/webhooks/webhook-requests):
  Anbieter-Verhalten bei Zustellungen; die dauerhafte Solidon-Zuteilung und
  Wiederaufnahme bleiben eigene Anforderungen.
- [Lemon Squeezy: Licensing](https://docs.lemonsqueezy.com/help/licensing):
  anbietereigenes Lizenzsystem; kein Beleg für Kompatibilität mit Solidons
  Ed25519-Schlüsseln.
- [§356 BGB](https://www.gesetze-im-internet.de/bgb/__356.html), insbesondere
  Abs. 6 in der abgerufenen Fassung: Voraussetzungen des Erlöschens bei
  digitalen Inhalten. Checkout und Vertragsbestätigung sind konkret zu prüfen.

Produktfreigabe, Anbieterzulassung, Vertragsfassung, Betriebsbereitschaft und
Plattformnachweise werden vor dem tatsächlichen Start erneut geprüft.
Ein Quellenabruf im September ersetzt keine Produktionsprobe im November.
