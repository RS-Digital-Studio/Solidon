# Programm 2026-10: Stand

Eine Sitzung, die übernimmt, liest zuerst diese Datei und dann das Konzept der
laufenden Phase. Neueste Zeile oben unter „Verlauf“.

## Auftrag Robert (11. bis 13.10.2026), verbindlich

Drei Konzepte in fester Reihenfolge, jedes bis zu seiner Abnahme (Abschnitt
„Abnahme“ im Konzept). Was dort als Entscheidung Robert steht, gilt.

| Konzept | Unterlagen |
|---|---|
| 0.6.1 (RM-734, RM-735) | `konzepte/konzept-suche-und-palette-2026-10.md`, `konzepte/nachweise-palette-2026-10/`; Auftrag und Einzelstand in der Git-Historie (`git log --diff-filter=D -- .claude/.state/rm-734-735`) |
| Funktionsdurchgang | `konzepte/konzept-funktionsdurchgang-2026-10.md`, `konzepte/nachweise-funktionsdurchgang-2026-10/`; RM-736 bis RM-749; Funddatei und Abhakliste entstehen mit D0 unter `.claude/.state/funktionsdurchgang-2026-10/` |
| Codestruktur | `konzepte/konzept-codestruktur-2026-10.md`, `konzepte/konzept-codestruktur-funde-2026-10.md`; RM-722 bis RM-733 |

Koordination der laufenden Pakete (örtlich, nicht versioniert):
`F:\3D Druck\output\konsolidierung-2026-10-12\KOORDINATION.md`.

**Nach main** erst, wenn Robert „main steht“ sagt; dann `origin/main` per
Merge hereinholen. Den Kopf `## 0.6.1` im Changelog legt diese Arbeit selbst
an, in allen Sprachen. Release, Version und Tag nur auf Auftrag.

**Phase 1:** 0.6.1 — RM-734, dann RM-735 auf main; Robert Bescheid geben.

**Phase 2:** Funktionsdurchgang nach `LIESMICH.md` ablegen, RM-736 (Programm)
und RM-737 bis RM-749 (Pakete D0 bis D12) ins Register. Dann D0 (Prüfstand).
Dann Codestruktur Schritt 0 mit den Funden, die es vorher behebt (CS-2, CS-9,
CS-10, CS-11, CS-12, die `raising=False`).

**Zwischenrelease nach Phase 2** (Robert, 13.10.2026): Nach vollständig
abgeschlossenem D0 und Codestruktur Schritt 0 wird **Version 0.6.1 erstellt,
geprüft und veröffentlicht**. Die Veröffentlichung ist ausdrücklich beauftragt;
Version, Tag und Upload werden erst nach diesen beiden Abschlüssen und den
Releaseprüfungen aus `/erzeugen` ausgeführt. Danach folgen Phase 3 und 4
weiterhin vollständig und gründlich.

**0.6.2 vor Phase 3** (Robert, 17.10.2026: „okay dann machen wir 0.6.1 wie
geplant und nacha abarbeiten aller punkte 0.6.2“): Direkt nach 0.6.1 werden
alle eingetragenen Funde aus RM-812 und die offenen Codestruktur-Funde aus
RM-813 (CS-28, CS-29, CS-41 bis CS-46) behoben und als 0.6.2 ausgeliefert;
Codestruktur Schritt 1 und die Kundenpakete folgen danach in Phase 3.

**Wettbewerb: hochwertigste Website, beste App bis 1.0** (Robert, 17.10.2026: „wir
wollen die hochwertigste webseite haben von allen und bis 1.0 auch die beste app“,
„die lücken in der app dann in den phasen abarbeiten“, „sollten ja schon alle
beheben“). Grundlage `konzepte/durchsicht-wettbewerb-2026-10.md`. Ab 01.12. kein
kostenloser Einstieg, gehostete KI erst nach 1.0 (Entscheidungen Robert). Website
RM-822 parallel zum Release; App: RM-818 (Laptop mit 125 %) in 0.6.2, RM-819
(Zahnrad, Gridfinity), RM-820 (Nummern und Montageplan beim Teilen) und RM-821
(Erkennungsquote an echten Downloads, nach D1) in Phase 3. Ein weiterer Fund aus
dem Wettbewerb wird ebenso behoben, nicht nur eingetragen.

**Die vier Phasen laufen ohne Datum in ihrer festen Reihenfolge, jede sauber bis zu
Ende** (Robert, 12.10.2026): Keine Phase wartet auf einen Termin, kein Schritt
wird für einen Termin gekürzt. Der Verkaufsstart in RM-061 ist ein
Geschäftstermin und keine Bedingung dieses Programms.

**Phase 3:** D1, D9, D8; dann Codestruktur Schritte 1, 2, 3 (prepare_ops,
panels, features); dann D3 und D4. Daneben die vom Umbau unabhängigen Funde
CS-3, CS-6, CS-13, CS-14, CS-15.

**Phase 4, direkt nach Phase 3:** CS-16, dann Schritte 4a bis 4d, 5
und 6 (Komponenten von MainWindow und den übrigen großen Fensterklassen), dann
Schritt 7 (weitere große Dateien; Bauplanänderung bei `analysis.py`,
Neunachweis der Befestiger bei `geom/prepare.py`), zuletzt Schritt 8
(`handover.py` und Grenzdateien, mit `solidon3d-auslieferung`). Dazu D2, D5,
D6, D7, D10; D11 und D12 jeweils nach den Komponenten der Klassen, die sie
berühren.

**Funde:** mit Art, Schwere und Beleg in die Funddatei des Konzepts. Schwer
sofort, mittel vor dem Ende der Phase, je eigene Commits; leicht als
Registerpunkt, spätestens in Phase 4. Am Ende jeder Phase kein Fund ohne Commit
oder Registerpunkt.

**Fertig** ist ein Konzept mit erfüllter Abnahme: Status in
`konzepte/README.md`, Nachweise und Funddatei unter `konzepte/`, Zustandsordner
unter `.claude/.state/` entfernt, eigene Worktrees und Zweige abgebaut.

**Arbeitsweise:** je Registerpunkt Test zuerst, betroffene Tests, ruff, format,
mypy; Review mit `solidon3d-review`, Funde beheben, bei mehreren mittleren oder
schweren Nachprüfung; Tor vor jedem Stand nach main; Merge, Commit, Push;
Agentenberichte sofort als Datei. Lokale Fenstertests nur, wo die Konzepte es
erlauben (Codestruktur-Oberflächenschritte: was `tools/ci_selection.py` für den
Diff nennt; Durchgang: je Fund die eine Datei). Bescheid an Robert am Ende
jeder Phase, nach D1 (Durchgang) und nach Schritt 4d (Codestruktur) mit neuer
Schätzung, und vor Stufe C (braucht Roberts Bildschirm und Freigabe). Fragen nur bei Geld,
Veröffentlichung, Rechten, schwer Umkehrbarem oder einer Alternative größer als
das Konzept.

**Gestaltung eigenständig prüfen** (Robert, 13.10.2026): Die Oberfläche
selbstständig auf zeitgemäße Gestaltung prüfen, über die reine Funktion
hinaus. Maßgeblich sind tatsächlich gelesene Originalbilder im hellen und
dunklen Thema: Platzbedarf, verbleibende Modellfläche, Schrift und visuelle
Hierarchie gehören gleichermaßen dazu. Das Raster im hellen Thema ist
ausdrücklich mitzuprüfen. Bestätigte Funde stehen in der Funddatei;
ein neues Bild wird nach einer Korrektur erneut tatsächlich gelesen.

## Verlauf

- 17.10.2026, Phase 2 abgeschlossen: Schlusslauf am echten Fenster (L1 bis
  L6; L4 69/69 und L5 15/15 an `d9f7a81f9`, 63 Vorhersagen vor dem Klick
  gebunden, beide versiegelt); Nachurteile in den Runden A, B, C1, C2a und C3
  mit drei Prüfern — jede Zeile von D4, D8 und D10 hat ihr Urteil, alle 53
  Prüfpunkte liegen bei mindestens 90 %, `report` ohne Abweisung. Fixe, die am
  echten Lauf nicht hielten (FD-99-Rest, FD-235, FD-88, FD-90, FD-20,
  FD-109/110) und der Fokus nach dem Ladeschleier sind vor 0.6.1 behoben, die
  Bildanleitungen laufen wieder in sechs Sprachen. Neue Funde FD-204 bis FD-323
  stehen in RM-812 für 0.6.2. Releasetor am Code grün (Sammelgruppe 31 440,
  Fenstergruppe 6 576, ruff, format, mypy; Spätfixe 15 607 betroffene Tests),
  Review der Spätfixe integrierbar, Version 0.6.1. **Als Nächstes:** nativer
  Endblock (Fix-Nachweis, Bildanleitungen, Handbuch- und Verkaufsbilder),
  Handbuch, Leistungslauf, main, CI, Tag, Pakete, Upload; dann 0.6.2.

- 16.10.2026, Welle 5 vollständig: `welle5` steht auf `a25ac8cb2` mit
  Codestruktur Schritt 0 (Pakete R, R2, M, Q, P1, P2, W13, Plattform,
  Restpaket CS0 und die Wächterfixe), dem CI-Fix, den Restpaketen A (mit B, D,
  F2a) und C, FD-135, FD-188, FD-197/203, FD-201/202, FD-212, den
  Beispielprojekten in Format 53 und main `fd7952a92`. Robert 15:50: Umfang
  eingefroren — fertig wird, was bis FD-203 und CS-40 vergeben ist; neue Funde
  stehen in RM-812 und kommen nach 0.6.1. Robert 16:05: der native Schlusslauf
  darf nachts laufen, wenn er nicht am Rechner ist. Unterlagen zu Schritt 0
  (Paket U): Karten, Regel 6 in `AGENTS.md`, `/liefern`, Funddatei bis CS-40,
  RM-723 bis RM-727, RM-729 und RM-730 im Archiv, Schritt 1 als RM-813.
  **Als Nächstes:** Funddatei-Nachtrag, Paket K (CS-11), Bereichsnachweis,
  Review der Merge-Auflösungen, nativer Schlusslauf, Nachurteilsrunde, Tor,
  Bescheid an Robert, main, CI; danach Release 0.6.1.

- 15.10.2026, D0 vor der Landung: Robert verlangt Phase 2 vollständig, nichts
  offen — auch die leichten Funde werden vor 0.6.1 behoben; gearbeitet wird
  nur noch auf einem Rechner. Auf `welle4` neu: Statusnachzug von 28 Funden am
  finalen Lauf, FD-84 (Maßfelder im Bild), FD-143 (mehrzeilige Funde in der
  Abhakliste), FD-154 (kein Prozessende unter laufendem Arbeiter), FD-156/157
  (Fenstertests nach drei Fixen, grauer Werkzeuggrund), Urteile relativ zum
  gesiegelten Lauf, Fixe beider Reviews, neu erzeugte Abhaklisten; native
  DE-Maßkartenfolge 62/62 und FD-154 am echten Fenster grün, 032 EN wartet auf
  FD-159. Funddatei bis FD-167. Die Übereinstimmung ≥ 90 % gilt je Prüfpunkt
  gepoolt über eine Urteilsrunde (Entscheidung Koordinator, FD-145). Parallel
  laufen die Fixpakete F2b, F5, F7, F8, F10 und FD-167 sowie CS0 (R, W13, P1,
  P2, Plattform integrierbar; M und Q in der Fixrunde). **Als Nächstes:**
  Schlussreview-Fixe, Nachprüfung, gepinntes Tor, D0 nach main und CI; dann
  `welle5` mit CS0 und allen Fixpaketen, Schlusslauf am echten Fenster,
  Nachurteilsrunde, Tor, main; danach Release 0.6.1.

- 13.10.2026, Maßkarten und sichtbare Schlussfixe: `welle4`/origin steht auf
  `9dc38e79f253a92efde6df55e1dec3c79d64a9f6`. FD69–75 sind normal integriert,
  jeweils ohne manuelle Merge-Auflösung und mit grünen normalen Hooks.
  Maßkarten in DE/EN/ES/FR/IT/PT regulär je 62/62 Bedingungen bestanden:
  zwölf gehaltene Kartenzüge, 18 echte Feldhilfen und vollständiger
  Abbrechen-/Einzel-/Sammel-/Undo-Weg. Alle 192 Originalbilder unabhängig
  einzeln gelesen, 51 eigene Prozessidentitäten beendet. Die dabei sichtbare
  abgeschnittene Statuszeile ist unter FD75 kausal behoben: Original/Fix je
  zwei native Aufbauten, vier gelesene Bilder; der korrigierte Client stimmt
  durchgehend mit Win32/QWindow/PNG überein. Alle eigenen Prozesse beendet.
  Griffmaße und XYZ/S verwenden lesbare Felder; L steht neben freien
  Knöpfen. Endgültige 19-Bilder-Folge Hell/Dunkel regulär grün, alle Bilder
  gelesen, Quellen unverändert. Keine allgemeine Überlappungsfreiheit oder
  zusätzliche native DPR2-Abnahme behauptet. Bettzahlen und helles Raster
  sind nativ belegt. Karten/Regeln und sechs Changelogs werden gemeinsam
  nachgezogen; Funddatei enthält jetzt FD1–75 mit Belegen und Grenzen.
  Als Nächstes: drei frische V4-Vorhersagen vor dem Klick, endgültiger
  48-Fall-Lauf mit den sieben alten Absturzfällen zuerst, unabhängige neue
  Bildurteile, Schlussunterlagen und gepinntes Tor samt Merge-Durchsicht.
  D0 ist noch nicht abgenommen und noch nicht auf main. Danach Codestruktur
  Schritt 0, ausdrücklich beauftragter Release 0.6.1 und Phasen 3/4.

- 13.10.2026, sichtbare Oberflächenkorrekturen: `welle4`/origin steht auf
  `ce1e95113d5d49d982570dc2d0a626b576d7af42`. FD67-Größenfix, FD68-Raster,
  ruhigere Werkzeugleisten, Maßkarten-Drag-Helfer und sein Flow-Anschluss
  sind normal integriert; ohne manuelle Merge-Auflösung. Raster
  im echten Fenster vorher/nachher jeweils Hell/Dunkel/Hell bestanden,
  Bilder selbst gelesen. Der Helfer hält freie Nutzerorte auch bei
  Größen- und Ursprungswechsel des verfügbaren Platzes; 34 enge Fälle,
  Statik und seine Review-Fixe grün. Der Flow-Anschluss besteht alle 16 Fälle
  einschließlich sechs Sprachkarten, Abbrechen/Neuauswahl und Platzmangel;
  Statik grün, DG-M1/2/3 in der bestehenden Durchsicht geschlossen.
  Neu bestätigt sind FD69 (zu blasse Bettmaßzahlen) und FD70 (Griff- und
  Vorschauflächen verdecken die gewählte Öffnung); beide werden auf dem
  eigenen Viewportzweig gezielt korrigiert. FD70 hat 15 enge Fälle und Statik
  grün, FD69 acht Bettfälle grün und eine Durchsicht ohne Fund. Native Maßkartengesten,
  Griff-/Zahlen-Sichtvergleich, voller 48-Fall-Lauf, endgültige Urteile,
  Kartennachtrag und gepinntes Entwicklungstor bleiben offen. Automatisch
  ermittelte breite Auswahlen sind bis zum gemeinsamen Tor ausdrücklich
  ausstehend; kein D0-Gesamtgrün und noch keine Landung auf main.
  Danach weiterhin Codestruktur Schritt 0, Release 0.6.1, Phasen 3 und 4.
- 13.10.2026, 19:43, Releaseauftrag ergänzt: Nach D0 und Codestruktur
  Schritt 0 wird 0.6.1 erstellt, vollständig geprüft und veröffentlicht;
  danach laufen Phase 3 und 4 weiter. Welle4/origin steht auf
  ece8988f2bdc60436a7bc327ee1b77e8e794a4b7; die gemeinsamen Unterlagen sind
  gesichert. FD61 hat den echten mm/in/mm-Weg in allen sechs Sprachen
  bestanden, zwölf Einstellungswechsel und 18 gelesene Bildschirmbilder.
  Die Maßgruppenprobe hat FD-67 gefunden: Die aufgeklappte Rückseite wächst
  nicht mit, Felder liegen unter der Knopfzeile trotz genügend freiem Platz.
  Robert verlangt zusätzlich, die schwebende Maßgruppe am Titel und freien
  Flächen verschieben zu können; Eingaben und Aktionsknöpfe bleiben bedienbar.
  Die gewählte Position bleibt bei Auf-/Zuklappen und Feldänderung erhalten.
  Enger Vorwärtsfix mit Reproduktion wird auf dem eigenen Maßgruppenzweig
  gebaut; alle nativen Prozesse beendet. Danach Maßgruppenfolge, ganzer
  48-Fall-Lauf, endgültige Urteile/Unterlagen, gepinntes Tor und main/CI.
  Keine D0-Abnahme, kein Versionssprung, Tag oder Upload vorweggenommen.
- 13.10.2026, 19:08, Schlussfixes von D0 integriert: `welle4` auf
  `a100dd99f9d960b5164c12231459c788221207c3`. FD60, FD61, FD7/16/63/64 und FD66
  sind zusammengeführt; FD62/65 war bereits enthalten. Der gemeinsame
  Anschluss mit 126 Fällen ist vollständig grün und an denselben Baum
  gebunden. FD60 hat zusätzlich 14.717 Kernfälle und Original001 am echten
  Fenster bestanden; FD61 222 enge Fälle, das Maßgruppenpaket 44 enge und
  2.861 Kernfälle. FD66 hat 54 Gegenfälle, 142 bestehende Größenfälle und
  FR/IT am echten Fenster grün; der einzige Fehler im breiten 14.777er-Lauf
  lag in einem alten Scroll-Testdouble und ist eng behoben. Historische
  rote Läufe und Originalurteile bleiben erhalten. Die Karten, Regeln und
  sechs Changelogs werden jetzt gesammelt angeschlossen. Noch offen sind
  native FD61-/Maßgruppenfolgen in sechs Sprachen, der ganze 48-Fall-Lauf
  mit den sieben früheren Absturzfällen zuerst, gepinntes Endtor und der
  Schlussanschluss der Merge-Durchsicht. D0 ist noch nicht auf main.
  Danach Codestruktur Schritt 0 vollständig nach plan-cs0.md; R und W13
  sind vorbereitet. Alle Kriterien bleiben gleichrangig, einschließlich
  notwendiger Dialog-/Panelgröße und Modellfläche. Website-Upload nur nach
  Roberts Freigabe. Aktuelle Prozess- und Übergabebelege: KOORDINATION.md.
- 13.10.2026, nach Roberts „mach noch weiter soweit du kommst“ wiederaufgenommen:
  Phase 2 bleibt im D0-Abschluss. `welle4`/origin steht auf `f08927d636`;
  main bleibt `6fbe6154f`. Die Korrektur der tatsächlichen Knopffarbe und
  Primärschrift (FD62/65) ist konfliktfrei integriert, vollständiger Baum
  identisch zur geprüften Lieferung: 1.831 Anschlüsse bestanden, 2 übersprungen,
  41 abgewählt, zusätzlich 13 + 31 enge Fälle und ein Aufnahmeanschluss grün.
  Die neuen Funde FD60–66 stehen jetzt in der Funddatei. FD61 hat 192 enge
  und 1.627 kopflose Fälle bestanden; sein Review-Fix ist lesend bestätigt,
  bestehende Qt-Anschlüsse und der echte Einheitenwechsel bleiben offen.
  Das Maßgruppenpaket FD7/16/63/64 hat 43 enge Fälle und Statik bestanden;
  der einzelne Theme-Fixture-Fund ist korrigiert, sein neuer Gegenfall und
  die weiteren Anschlüsse fehlen noch. FD66 besitzt einen konkreten nativen
  Vorherbeleg für unnötige Anfangshöhe, aber noch keinen grünen Fixnachweis.
  **FD60 sperrt weiter:** Im nativen Absturz ist jetzt ein `QWidgetItem` als
  falscher Nicht-QObject-Wrapper nachgewiesen; Entstehung und Korrektur sind
  noch offen. Keine Hardwareursache aus einem Absturzstapel abgeleitet.
  B2 ist mit 848 angenommenen Urteilen versiegelt; der anschließende Vergleich
  über 1.189 Urteile hat 18 Unterschiede, die auf der ursprünglichen Basis
  eingeordnet werden. Die alte 48-Fall-Probe bleibt rot und unverändert.
  Nach den laufenden Fixen: gemeinsame native Nachweise, Karten,
  gepinntes Endtor, Merge-Durchsicht, main/CI, dann Codestruktur Schritt 0.
  R und W13 bleiben vorbereitet; keine neue CS0-Umsetzung vor D0/main.
  Aktuelle Ressourcenfreigaben, Einzelberichte und Sicherungen stehen am
  Ende von `KOORDINATION.md`. Die folgende Pause ist ein historischer Stand,
  keine aktuelle Halteanweisung. Website-Upload weiterhin nur nach Freigabe.
- 13.10.2026, Übergabe auf Roberts Wunsch wegen des nahen Nutzungslimits:
  Keine neue Arbeit, Prüfrunde oder Landung begonnen; alle Agenten angehalten
  und eigene Sonden beendet. Produkt-/Prüfstandsbasis ist `6d063ef064` auf
  `welle4`, weiterhin nicht auf main. Der frische Fensterlauf ist rot:
  48 Fälle, 41 Prozesse Exit 0, sieben native Abstürze; drei getrennte V4-Proben
  sind erfolgreich. FD60 ist reproduziert, seine Ursache bleibt offen.
  FD61 und FD62/65 sind als ungetestete Änderungen vorbereitet; FD7/16/63/64
  ist zusätzlich unvollständig. Die eigenen Worktrees samt vollständigen
  Patches, neuen Quellen, Ausgangsmodulen und nächsten Befehlen sind gesichert.
  Primärurteile D4/D8/D10 sind versiegelt; die unabhängige B2-Auswertung und
  der Prüfervergleich bleiben offen. FD66 ist ein noch nicht diagnostizierter
  Größenfund. **Wiedereinstieg:** zuerst den letzten Abschnitt „ÜBERGABE an
  die nächste Sitzung“ in `output/konsolidierung-2026-10-12/KOORDINATION.md`
  und `WEITER-CODEX-CLAUDE.md` dort lesen; Sicherungsarchiv und Hashmanifest
  liegen im selben Ordner. Keine vorbereitete Testdatei gilt als geprüft.
  Nach Wiederaufnahme D0 fertigstellen, gepinntes Tor/Merge-Durchsicht/main/CI,
  anschließend Codestruktur Schritt 0 vollständig gemäß `plan-cs0.md`.
  Website-Upload wartet weiter auf Roberts Freigabe.
- 13.10.2026, 14:23, Phase 2 weiterhin D0: Alle Korrekturen bis FD59 sind
  auf `welle4` integriert, zuletzt Kartenbreite/Schriftwechsel als
  `e68ca22cb`. Dialoge und Karten richten ihre notwendigen Maße nach Inhalt,
  aktueller Schrift und den gewählten Größen; die Prüfung umfasst weiterhin
  alle Kriterien gleichrangig. Die gesammelten Karten, Regeln und sechs
  Changelogs sind nachgezogen. Paketnachweise und gezielte gemeinsame
  Anschlüsse sind grün; der erste gemeinsame Kartenlauf ohne geladene
  DejaVu-Schriften bleibt als roter Umgebungsnachweis erhalten. **Als
  Nächstes:** frischer vollständiger Fensterlauf auf MSI MAG271CQR mit
  isolierten Profilen, neue V4-Vorhersagen und unabhängige Bildurteile,
  danach gepinntes Endtor, Abschluss der Merge-Durchsicht und main/CI.
  Die Plattformwelle `6fbe6154f` ist enthalten; deren CI startete wegen der
  von GitHub gemeldeten Zahlungs-/Ausgabenbegrenzung keinen Test. D0 ist noch
  nicht abgenommen. Danach Codestruktur Schritt 0 vollständig gemäß
  `plan-cs0.md`; R und W13 sind bereit, M vorbesprochen. Website-Upload
  bleibt bis zu Roberts Freigabe ausstehend.
- 13.10.2026, 10:50, Phase 2 weiterhin D0: Die alten Fixpakete und die
  Plattformwelle von main sind in `welle4`; letzter integrierter Fix ist
  FD-36 (`f80741556`, Entfernen-Hinweis mit zuerst erreichbarem Abbrechen).
  Karten sind nachgezogen. Der zweite native Probelauf auf `dca24076f`
  lieferte echte Funde und drei native Prüfstandsabbrüche; er ist rot und
  unverändert gesichert. Stufe-B-Urteile und unabhängige Zweitprobe sind
  versiegelt, acht Unterschiede haben eine präzisierte gemeinsame
  Kriterienauslegung ausgelöst. Robert verlangt ausdrücklich alle Kriterien,
  auch notwendige Breite/Höhe, Leerraum und verbleibende Modellfläche.
  Die neuen Fixeinheiten FD-35 bis FD-52 werden auf eigenen Zweigen gebaut
  und geprüft; aktuelle Spitzen, Zuständigkeiten und Nachweise stehen in
  `KOORDINATION.md` und den dort verlinkten Berichten. Keine bestandene
  Gesamtmessung oder Endtor-Abnahme behauptet. **Als Nächstes:** neue
  Fixrunden und erforderliche Nachprüfungen abschließen, integrieren,
  frischer vollständiger Probelauf samt V4 und unabhängigen Bildurteilen,
  gesammelter Kartennachtrag, gepinntes Tor und Merge-Durchsicht, main/CI.
  Codestruktur R (`ceb161a9f`) und W13 (`367142bee`) sind auf ihren Zweigen
  fertig; Integration und die übrigen Pakete von Schritt 0 folgen nach D0
  auf main gemäß `plan-cs0.md`. Website-Upload wartet weiter auf Robert.
- 13.10.2026, 03:50, Phase 2, D0 läuft, Codestruktur Schritt 0 daneben: Die
  Durchsicht über `welle4` vor main ist durch (vier Teile, Berichte in
  `output/konsolidierung-2026-10-12/review-welle4-{a,b,c,d}.md`): ein schwerer
  Fund im Prüfstand (Prüfpunkt 18 galt ohne Messung als erfüllt), mittlere in
  Oberfläche, Kern, Prüfstand und Unterlagen. Sechs Fixagenten beheben sie auf
  eigenen Zweigen (`fix/sperre-vollstaendig`, `fix/zeile-bohrung`,
  `fix/review-oberflaeche`, `fix/review-kern`, `fix/pruefstand-urteile`,
  `fix/pruefstand-flaeche`); die Unterlagenfunde sind auf `welle4`. origin/main
  `a47ff34fc` ist hereingeholt. Die Website nennt in sechs Sprachen 1920 × 1080
  bei 100 % (Upload wartet auf Robert). Fehlermeldungen mit Handlung sind eine
  Z2-Ausnahme. Neben D0 laufen die Pakete R und W13 aus Schritt 0 (nur neue
  Dateien; Konzept Funktionsdurchgang §13 Nr. 2). **Als Nächstes:** Fixe
  integrieren, je eine Nachprüfung, zweiter Probelauf, Karten und Regeln in
  einem Durchgang, Tor, main; dann die übrigen Pakete von Schritt 0.
- 13.10.2026, 00:52, Phase 2, D0 läuft: RM-788 und RM-789 sind vorgezogen auf
  main (`0742a8c50`). Der hängende Slicertest war ein Windows-Fenster „Nicht
  unterstützte 16 Bit-Anwendung“ beim Start einer Datei, die kein Programm ist,
  und traf auch Kunden. ComfyUI startet jetzt hinter der Prozessgrenze. Review,
  Folgerunde und Nachprüfung sind durch, das Tor gepinnt grün (28 150). D0 auf
  `welle4`: Prüfstand, Funktionsliste mit Szenen für jede Befundhandlung,
  Urteile, Wortschatz und die Funde FD-1 bis FD-24 behoben. Offen sind FD-25
  bis FD-30 (zwei Fixagenten laufen), danach zweiter Probelauf, Tor,
  Durchsicht der Merge-Auflösungen, main. RM-790 (einmaliger Abbruch nach
  Rückgängig) steht im Register. **Als Nächstes:** D0 abschließen, dann
  Codestruktur Schritt 0 (Plan und Auftrag liegen in
  `output/konsolidierung-2026-10-12/plan-cs0.md` und `AUFTRAG-cs0.md`).
- 12.10.2026, 14:35, Phase 2: Robert legt fest, dass alle vier Phasen ohne
  Datum direkt hintereinander und sauber bis zu Ende laufen. Der Halt vor
  Phase 4 bis zum 01.12. und der Kandidatentermin am 25.11. als Bedingung
  entfallen, ebenso das Kürzen von Codestruktur-Schritten für einen Termin.
  Register und Konzepte ziehen auf `welle4` nach und landen mit D0.
- 12.10.2026, 14:31, Phase 2, D0 läuft: Der schwere Fund aus D0 ist auf main
  (`e871f6062`). *Text aufbringen*, *Schrift einlegen* und *Gegenform
  einlassen* löschten am exakten Körper alle Merkmale, seit 0.5.0 bzw. 0.5.2.
  Behoben mit Wächter über die Falltabelle, druckgleich und schneller, mit
  Changelog. Review, Fixrunde und Nachprüfung sind durch, das Tor gepinnt
  grün (28 130 bestanden). In der Funddatei stehen FD-1 bis FD-3 auf
  `welle4`. Die Geschwister mit berührten oder geteilten Flächen führt
  RM-787, den Slicertest, der unter Volllast hängt, RM-788; beide werden
  in Phase 2 behoben. D0 steht auf `welle4`: W, L und U sind integriert, die
  Karten nachgezogen, P und die Folgerunden laufen. **Als Nächstes:** P und
  W's Nachtrag integrieren, Probelauf am Fenster, Tor, Durchsicht der
  Merge-Auflösungen, D0 nach main; danach Codestruktur Schritt 0 (RM-722),
  RM-787, RM-788.
- 12.10.2026, 08:37, Phase 2, D0 begonnen: Zuschnitt in fünf Teilpakete
  (W Wortschatz, L Liste und Szenen, P Prüfstand, U Urteile, S Unterlagen) in
  `.claude/.state/funktionsdurchgang-2026-10/plan-d0.md`; Integrationszweig
  `welle4` (Worktree `F:\sl-welle4`), Teilpakete auf `d0/wortschatz`,
  `d0/liste`, `d0/urteile`, `d0/pruefstand` (Worktrees `F:\sl-d0w`, `-d0l`,
  `-d0u`, `-d0p`); S macht der Koordinator. Lizenz „gekauft“ im Prüfstand über
  die Nahtstelle der Suite, ohne private Schlüssel. Stand je Paket in
  `F:\3D Druck\output\konsolidierung-2026-10-12\paket-d0-<kürzel>.md`.
- 12.10.2026, 08:37, Phase 2, Schritt 1 auf main (`31dd59af1`): Funktionsdurchgang abgelegt
  (Konzept und Prüfberichte unter `konzepte/`, RM-736 bis RM-749 im Register,
  Programmplan als Beleg der Termine in Konzept §9; Paketzuordnung nach §6
  ohne Ausnahme außer D6 — Verrunden, Fase, Fläche versetzen prüft D3).
  Review mit drei mittleren und elf leichten Funden, alle behoben, Nachprüfung
  vor dem Merge. Aufgeräumt: `welle2` (in main) abgebaut; der Worktree
  `F:\solidon-bk-251` trug ungesicherte Arbeit zu RM-251, gesichert als
  `724a153f2` auf `claude/bk-251`, Worktree abgebaut (Vermerk an RM-251). Die
  CI auf main startet nicht, solange das Repository privat ist (Normalzustand,
  Robert 12.10.); ihre Fenstertests laufen in der Release-Phase. **Als
  Nächstes:** D0 (RM-737) nach dem Zuschnitt in
  `.claude/.state/funktionsdurchgang-2026-10/plan-d0.md` (entsteht gerade, der
  beschlossene Zuschnitt kommt danach in RM-737), über den Integrationszweig
  `welle4`; danach Codestruktur Schritt 0 (RM-722).
- 12.10.2026, 07:45, Phase 1 gelandet: 0.6.1 (RM-734, RM-735) per
  `--no-ff` auf main und gepusht; kein Release, keine Version. Review in drei
  Durchgängen (Berichte örtlich unter
  `F:\3D Druck\output\review\rm-734-735-2026-10-11\`), achtzehn Funde, keiner
  schwer, alle behoben (`4fc557327`, `d330cb7f0`, `76faa9be7`; Tabelle im
  Konzept). Tor gepinnt auf `76faa9be7`: 28 120 bestanden, 137 übersprungen,
  Exit 0. Offen allein die Abnahme am echten Fenster beim Release (RM-213).
  Worktree `F:\sl-suche` und Zweig `061/suche-und-palette` werden nach dem
  Merge abgebaut. **Als Nächstes Phase 2, Schritt 1:** Funktionsdurchgang nach
  `LIESMICH.md` auf `origin/doc/funktionsdurchgang` ablegen (Konzept nach
  `konzepte/konzept-funktionsdurchgang-2026-10.md`, Berichte nach
  `konzepte/nachweise-funktionsdurchgang-2026-10/`, Indexzeile, RM-736 und
  RM-737 bis RM-749 ins Register — die Nummern sind auf origin/main frei),
  dann D0, dann Codestruktur Schritt 0.
- 12.10.2026, 05:45, Phase 1, angehalten auf Wunsch Robert (Wechsel in die
  Desktop-App): Changelog `## 0.6.1` in sechs Sprachen steht (`1543a076f`).
  **Offen vor main, in dieser Reihenfolge:** (1) Review mit `solidon3d-review`
  über `git diff origin/main...HEAD` im Worktree `F:\sl-suche` — der erste Lauf
  wurde ohne Bericht gestoppt, also neu starten; Bericht nach
  `F:\3D Druck\output\review\rm-734-735-2026-10-11\review.md`; (2) Funde
  beheben, bei mehreren mittleren oder schweren eine Nachprüfung; (3) volles
  Tor (`bash .claude/scripts/suite-getrennt.sh`, auf diesem i9 gepinnt über
  `start /affinity FFFFF0FF`, Ergebnis aus der Ausgabedatei, nicht aus `$?`),
  ruff, format, mypy; (4) vorher `git fetch` und, falls main weiter ist,
  origin/main erneut hereinmergen; (5) in `F:\3D Druck` auf main
  `git merge --no-ff origin/061/suche-und-palette`, Push; kein Release, kein
  Tag, keine Version; (6) Worktree `F:\sl-suche` und Zweig abbauen, Robert
  Bescheid geben; dann Phase 2. Das Tor vom 11.10. war rot nur durch die
  Maschine und den behobenen `test_orient.py`-Fund; das Frühtor vom 12.10.
  wurde mit dem Halt abgebrochen.
- 12.10.2026, Phase 1: „main steht“ (Robert). origin/main hereingeholt
  (`21d1407e4`), RM-734 und RM-735 im Register (`[~]`, offen die Abnahme am
  echten Fenster, RM-213), Konzept und Nachweise unter `konzepte/`,
  Zustandsordner entfernt. Als Nächstes Changelog `## 0.6.1`, Review, Tor,
  Merge nach main.
- 12.10.2026, Phase 1: RM-734 und RM-735 auf dem Zweig fertig und gepusht
  (bis `023c9c703`); die fünf Funde unterwegs sind behoben (Tabelle am Ende
  von `konzepte/konzept-suche-und-palette-2026-10.md`).
- 11.10.2026, Phase 1: RM-734 auf dem Zweig fertig (`ddd82fb9b`, `5ca7f94cb`),
  RM-735 in Arbeit (Suchfeld der Karte ersetzt die Befehlspalette). Nichts auf
  main. Einzelstand in `.claude/.state/rm-734-735/STAND.md`.
