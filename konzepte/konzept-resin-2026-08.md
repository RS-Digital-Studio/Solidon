# Konzept — die Vorstufe vor dem Resin-Slicer

Stand 30.08.2026. **Entwurf, nichts davon gebaut.**

Anlass: Eine Kundenanfrage aus dem Dentalbereich (R. W. D., 30.08.2026 —
exocad/3shape beruflich, FDM- und Resindrucker privat) fragte nach einer
„Integration von Resin-Druckern". Seine Präzisierung vom selben Vormittag
verschiebt die Frage: Sein Kernproblem ist nicht fehlende Resin-Analyse,
sondern die **Vorbereitung nicht perfekter Dateien vor dem Hersteller-Slicer**
— viele Resin-Drucker arbeiten nur mit dem eigenen, rudimentären Slicer
(Chitubox oft unmöglich), und die Lücke füllten bisher Meshmixer und Co.:
wenig selbsterklärend, teils eingestellt. Solidon als Vorstufe ist für ihn
die Lösung; Resin-Prüfungen nennt er das Sahnehäubchen.

Dieses Dokument beantwortet, **was Resin-Unterstützung in Solidon wäre und in
welcher Reihenfolge sie trägt** — damit Roberts Entscheidung an Zahlen hängt.
Gemessen gegen den Arbeitsstand vom 30.08.2026 (nach `d4cea5fd`).

Bezug: Bauplan §2.2 (Weg 1), §22 (Schichtanalyse, kein Slicer), §29 (Export
und Übergabe), §38 (Profile), §39 (Regelsammlung); AGENTS.md („Was NICHT
gebaut wird", Regel 21). „§" meint hier immer den Bauplan.

---

## 1. Der Registerpunkt heißt falsch

Punkt 131 heißt „Resin-Druck: der Export kann es, das Wissen fehlt". Nach der
Kundenpräzisierung und der Codeprüfung müsste er heißen:

> **Solidon setzt einen FDM-Drucker voraus, ohne je danach zu fragen.**

Das ist kein fehlendes Feature, sondern eine ungefragte Vorgabe — Regel 21 in
ihrer stillsten Form: nicht geraten in einer Ausnahme, sondern geraten als
Voreinstellung. Der Erststart bietet sechzehn FDM-Geräte an und sonst nichts;
ein leerer Drucker wird still durch `DEFAULT_PRINTER = "generic-220"` ersetzt
(`app/ui/session.py:426`, `first_run.py:243`, `print_settings_dialog.py:1608`)
— 0,4-mm-Düse, 0,42-mm-Bahn, 220-mm-Bett. Für einen Dental-Resin-Drucker ist
jede dieser Zahlen falsch, und der Nutzer erfährt nie, dass er sie gewählt hat.

Damit ist Resin-Unterstützung **keine Erweiterung des Produkts, sondern das
Entfernen einer Hürde vor einer Tür, die längst offen steht**: Das
Wettbewerbskonzept führt die Meshmixer-Lücke als „führend — und die am
meisten unterschätzte Position im ganzen Programm"
(`konzept-wettbewerb-2026-08.md` §2.3). Der Dentalkunde bestätigt sie aus
einer Branche, die dort nicht vorkam.

## 2. Was der Bestand schon kann

Gemessen am geladenen Register (95 Operationen): Der gesamte Vorbereitungsweg
ist verfahrensunabhängig gebaut — Einlesen (STL/OBJ/3MF/PLY/GLB/STEP),
Einheitenerkennung mit `ctx.ask`, neun Eingangsbefunde (alle gelten für Resin
unverändert), Reparieren, Netzarbeit (dezimieren, glätten, remeshen),
Anpassen (Bohren, Boolesche, Skalieren, Ausrichten), Teilen, Aushöhlen,
Export mit STL binär als Vorgabe — genau das Format, das jeder
Resin-Hersteller-Slicer nimmt.

**Der Meshmixer-Ersatz existiert im Wesentlichen.** Was fehlt, ist nicht
Fähigkeit, sondern dass die FDM-Annahme sie verstellt.

## 3. Fünf Befunde, an denen Stufe 1 hakt

**B1 — Es gibt keinen Zustand „kein FDM-Drucker".** Siehe Abschnitt 1; die
drei Ersetzungsstellen sind benannt.

**B2 — Die Düse zieht in sieben Kernentscheidungen durch, aber über nur zwei
Eigenschaften.** `Profile.minimum_wall_thickness = 2,0 × extrusion_width` und
`smallest_printable_volume` (`app/core/types.py:440/446`) tragen
`hollow.below_printable_wall`, die Wandstärkenkarte, `lattice`,
`boolean.without_effect`, die Texturgrenzen, die Agenten-Analyse und
`displace`. Die gute Nachricht im schlechten Befund: **zentralisiert an zwei
Stellen** — eine verfahrensabhängige Herleitung dieser zwei genügt, die
sieben Aufrufer bleiben unberührt.

**B3 — Bauraum und Anordnung rechnen gegen ein Bett, das der Kunde nicht
hat.** `check_build_volume`, `arrange_bed`, Auto Split (teilt nicht, wo er
müsste, weil 220 mm mehr Platz vorgaukeln), das Bett im Viewport.

**B4 — Neun Befunde des Prüfberichts sind für Resin irreführend** (aus 156
Codes im Kern): `hollow.wall_below_nozzle`, `settings.wall_below_nozzle`,
`prepare.elephant_foot`/`compensate_first_layer`, `orient.support_likely`
(45°-FDM-Regel), `slice.long_bridge` (Brücken gibt es nicht),
`settings.warping_material_open_printer` (ASA/ABS sind Filamente),
`settings.uncalibrated_material` (die Kalibrierung misst FDM-Passungen),
`arrange.filament_changes`, `arrange.adhesion_too_close` (Skirt/Brim/Raft).
Dazu die gesamte Beratungsachse in `slice/advise.py` (992 Zeilen Düse, Bett,
Lüfter, Rückzug): für Resin nicht falsch justiert, sondern **gegenstandslos**
— und sie erscheint trotzdem. Ein Prüfbericht, in dem neun von zwanzig
Zeilen fürs eigene Verfahren leer laufen, wirkt nicht hochwertig, sondern
unaufmerksam.

**B5 — Die Website sagt dem Resin-Kunden ab, bevor er lädt.**
`website/index.html:155/843` (und en): „gebraucht werden Bauraum, **Düse und
Schichthöhe**" — eine Absage an jeden Resin-Nutzer. Dieselbe Engführung in
der Handbuch-Druckertabelle (`manual.py:1620`) und der
Mindestwandstärken-Abbildung (`figures.py:406/425`). Nach Roberts Vorgabe ist
die Website die Sollliste — der Satz gehört in beide Richtungen geprüft.

## 4. Stufe 1 — aufhören, das Vorhandene zu verstellen

Kein neuer Rechenweg, keine neue Geometrie. Es entsteht:

1. **Ein Verfahren im Druckerprofil**: `technology = "fdm" | "resin"` in
   `printers.toml`, Vorgabe `"fdm"` — bestehende und selbst angelegte
   Profile laufen ohne Migration weiter (zu bestätigen, nicht anzunehmen).
   Felder je Verfahren: `build_volume` gilt beiden (und ist bei Resin der
   wichtigere Wert — die Bauräume sind klein), `layer_height` 0,03–0,1,
   Düse/Bahnbreite entfallen, dazu Pixelgröße XY als „kleinstes Detail" und
   eine **eigene Mindestwandstärke** — bei Resin ist die Grenze Stabilität,
   nicht Auflösung.
2. **Die zwei zentralen Eigenschaften aus B2** leiten sich verfahrensabhängig
   her; die neun Befunde aus B4 bekommen einen Geltungsbereich.
3. **Der Erststart** bietet Resin-Geräte an, nach Verfahren gruppiert —
   der Kunde wählt seine Maschine aus derselben Liste wie alle anderen,
   schaltet nichts um und muss nichts wissen. Einfacher als heute: Heute
   rät er, welcher der sechzehn falschen Drucker am wenigsten schadet.
4. **Die Übergabe per Öffnen** (§29, zweite Übergabeart) funktioniert auch
   für Resin-Slicer — sie braucht kein Profil und kein Rücklesen. Heute
   scheitert sie nur daran, dass `SlicerSetup.flavour` eine Übersetzung
   verlangt, die beim bloßen Öffnen niemand braucht
   (`handover.py:135/2171`). Kleiner, sauber begrenzter Posten.
5. **Website, Handbuch, Abbildungen, sechs Kataloge** ziehen nach (B5).

### Die Druckerprofil-Entscheidung, drei Wege

- **(A) „Kein Drucker" als Zustand** — abgelehnt: macht die Prüfung stumm
  (ohne Profil gibt `below_printable_wall` heute bewusst nichts zurück).
  Statt falscher Warnungen keine — leiser, nicht besser; gegen §2.4
  („eine gute Vorgabe ist mehr wert als eine gute Einstellmöglichkeit").
- **(B) Verfahren im Druckerprofil — empfohlen.** Begründung oben.
- **(C) Ein „Vorbereitungsmodus" ohne Drucker** — abgelehnt: eine
  Betriebsarten-Umschaltung in der Oberfläche, steht wörtlich unter „wird
  nicht gebaut".

## 5. Stufe 2 — Resin-Wissen, drei Stücke

### 5.1 Saugglocken (Cupping)

Eine Insel ist eine Kontur, die **anfängt** — das erkennt `_islands()`
(`slice/analysis.py:848`). Eine Saugglocke ist ein Hohlraum, dessen Öffnung
**aufhört**: ein zur Wanne hin offener Becher, der oben zugeht; beim Anheben
entsteht Unterdruck, das Ergebnis ist ein Abriss oder eine gerissene
FEP-Folie. Es fehlen zwei Dinge: **Ringidentität über die Schichtfolge**
(welcher Innenring der Schicht z ist derselbe in z+1, und wo verschwindet er
ohne Verbindung nach außen) und **eine Druckorientierung** — denn:

> Cupping ist keine Eigenschaft des Körpers, sondern des Paares
> (Körper, Orientierung).

Das ordnet den Befund der Schichtanalyse zu (§22, nicht §21) und macht die
bestehende Orientierungssuche zum natürlichen Ort der Verwertung. **Das
Nebenprodukt ist wertvoller als der Befund:** Um ein Kriterium
„Saugglockenvolumen" erweitert, beantwortet die Suche dem Dentalnutzer die
Frage, die er wirklich hat — *wie lege ich das Ding hin* —, was kein
Hersteller-Slicer kann.

### 5.2 Abflussöffnungen beim Aushöhlen

Der ROADMAP-Vorschlag „die Aushöhlen-Op um eine Abflussbohrung erweitern"
ist zu grob: **Es gibt sie schon.** `hollow_object` hat `vents` (0–6,
Vorgabe 1), `vent_diameter` (4 mm) und `open_top`; `_vent()` bohrt durch den
Boden (`geom/hollow.py:399–462`) — und der Modul-Docstring nennt Resin
bereits ausdrücklich, ohne eine Folge daraus zu ziehen. Was für Resin fehlt,
ist enger: **zwei** Öffnungen statt einer (sonst hält Unterdruck das Harz im
Hohlraum), platziert am tiefsten **und** höchsten Punkt der
**Druckorientierung** (Resinteile stehen geneigt), 2–4 mm. Und der
Schweregrad ist verfahrensabhängig: Bei FDM ist die fehlende Öffnung eine
durchhängende Decke (`warning`), bei Resin ein Teil voll unausgehärtetem
Harz, das beim Nachhärten aufplatzt (`error`) — **nicht suboptimal, sondern
Ausschuss.** Die Platzierung nach Druckorientierung nützt auch FDM, sobald
das Teil gedreht steht.

### 5.3 Der Überhangwinkel gilt nicht — Regeln bekommen einen Geltungsbereich

`OVERHANG_LIMIT_DEGREES = 45.0` steht sauber an einer Stelle
(`knowledge/rules.py:41`) — und trotzdem wäre „für Resin einen anderen Winkel
eintragen" falsch: Der Winkel ist eine Aussage über eine Extrusionsbahn, die
eine Unterlage braucht, und bei Resin gibt es keine Bahn. Die Resin-Kriterien
sind andere: **Querschnittszuwachs je Schicht** (Ablösekraft; große flächige
Querschnitte parallel zur Platte sind bei Resin das Schlimmste und bei FDM
das Beste), Inseln (gleich schlimm, bereits erkannt), Saugglocken (5.1).

> **Ein `technology`-Feld wählt Regeln aus; es verstellt keine Zahlen.**

Die Regelsammlung (§39) führt sieben Regeln, alle sieben sind FDM-Regeln,
und an keiner steht das dran — unabhängig von Resin ein Mangel: ein Produkt
ohne Geltungsbereich ist eine Sammlung von Vermutungen.

## 6. Was nicht gebaut wird — auch für Resin

| Frage | Antwort |
|---|---|
| Eigener Resin-Slicer, `.ctb`/`.pwmx`/`.goo` schreiben | **nein** — §22 gilt verfahrensunabhängig; proprietäre Belichtungsformate wären derselbe Fehler in Grün |
| Belichtungszeiten, Antialiasing, Blooming | **nein** — die Resin-Entsprechung von Temperatur und Lüfter: Slicer-Sache |
| Punktstützen erzeugen | **nein** — §22 wörtlich übertragbar: „fünfzehn Jahre Arbeit anderer Leute"; ein schlecht gestütztes Dentalteil ist maßlich unbrauchbar. Der Ruf danach wird kommen, weil die Hersteller-Slicer schlecht stützen — die richtige Antwort ist, den **Stützbedarf zu senken** (Orientierungssuche, 5.1), nicht das schlechtere Stützwerkzeug zu bauen. Die Grenze in einem Satz: Solidon sagt, wo gestützt werden muss und wie man es vermeidet; es baut die Stütze nicht |
| Harzdatenbank mit Belichtungsprofilen | **nein** |
| Betriebsarten-Schalter „FDM/Resin" in der Oberfläche | **nein** — das Verfahren gehört ins Druckerprofil |
| Vierte Slicer-Familie in `slicer_keys.py` | **nein** — Chitubox/Lychee/Photon Workshop haben keine dokumentierte Kommandozeile und binäre Profile; eine Tabelle ohne Gegenstelle. Die Übergabe per **Öffnen** bleibt (Abschnitt 4, Punkt 4) |

## 7. Bauplan-Verortung (nur benannt, geändert wird mit Ansage)

Stufe 1: §4.2 (Begriffe: Verfahren → `technology`, Saugglocke → `cupping`,
Abflussöffnung → `drain`), §38 (Verfahren im Profil, Felder je Verfahren),
§39 (Geltungsbereich je Regel), §2.3 (Erststart kennt Resin-Geräte), §29
(Formatempfehlung je Verfahren; Öffnen ohne Übersetzung). Stufe 2: §22.2
(Kennzahl „geschlossene Hohlräume gegen die Bauplattform"), §25 (Aushöhlen
mit Öffnungen nach Druckorientierung), §31 (eigene Marke, Abschnitt 8), §40
(Abnahme je Stufe). Als bleibende Grenze zu benennen: Belichtungsparameter,
Stützenerzeugung, Belichtungsformate, Harzdatenbank, Wasch-/Härtezeiten.

## 8. Leistung, gemessen

Bestehende Schichtanalyse gegen Resin-Schichthöhen (Windows, warm):
`clean_figure.stl` 278 → 556 ms (0,2 → 0,05 mm), `dense_1m.stl` 0,62 →
**3,03 s**. Vierfache Schichtzahl kostet Faktor 2–4,9 — gutartig skalierend,
aber die §31-Marke wäre bei Druckschichthöhe vier- bis fünffach gerissen:
ein zu benennender Budgetposten, kein Ausschluss. Die Orientierungssuche
fährt bereits grob (`SEARCH_LAYER_HEIGHT = 1.0`); für Cupping ist 1 mm
gefährlich (eine Saugglocke mit 0,4-mm-Deckel verschwindet). Die
Analyse-Höhe für die Cupping-Suche ist eine eigene Entscheidung (Frage 6).

## 9. Abnahme (Stil §40)

**Stufe 1 fertig, wenn:** (1) Ein Projekt mit Resin-Profil legt sich an,
öffnet, rechnet, speichert; ein Nutzerprofil ohne Verfahrensangabe lädt als
FDM; keine Formatmigration. (2) **Kein Befund der FDM-Achse erscheint an
einem Resin-Projekt** — als Test über den Befundkatalog: die neun aus B4
kommen nachweislich nicht vor. (3) Die Mindestwand kommt aus dem Profil:
0,5 mm Wand meldet am Resin-Profil nichts und am FDM-Profil weiterhin.
(4) Bauraum, Anordnen, Auto Split rechnen gegen den Resin-Bauraum.
(5) Der Erststart bietet Resin-Geräte gruppiert an. (6) Weg 1 läuft Ende zu
Ende mit Resin-Profil ohne eine einzige FDM-Aussage. (7) Der Export lässt
sich ohne Einstellungsübersetzung an ein externes Programm übergeben.
(8) Handbuch, FAQ, Druckertabelle, Abbildung nennen kein Verfahren, das
nicht gilt; sechs Kataloge vollständig.

**Stufe 2 fertig, wenn:** (1) Saugglocken werden mit Ort und Volumen
gemeldet, geprüft **gegen analytische Körper** (Becher kopfüber, Hohlkugel
mit Bohrung, Rohr mit Blindende) mit bekannten Sollzahlen. (2) Derselbe
Körper meldet in anderer Orientierung keine — die Orientierungsabhängigkeit
ist ein Testfall. (3) Die Orientierungssuche bewertet Saugglocken mit und
findet an einem Testkörper die saugglockenfreie Lage. (4) Aushöhlen setzt am
Resin-Profil zwei Öffnungen nach Druckorientierung; ohne Öffnung `error` bei
Resin, `warning` bei FDM. (5) Kein 45°-Befund am Resin-Projekt; an seiner
Stelle das verfahrenseigene Kriterium. (6) Jede Regel trägt einen
Geltungsbereich; **Agenten-Suite vorher und nachher**, beide Quoten
festgehalten. (7) Schichtanalyse bei Resin-Höhe im Budget, eigene Marke.

## 10. Was es an anderer Stelle kostet

Projektdatei (Migration vermeiden — prüfen, nicht annehmen);
`scene/hashing.py:48–55` (Druckereigenschaften im Cache-Schlüssel — ein
neues Feld gehört hinein, sonst rechnet ein umgestelltes Projekt aus dem
Cache); Steckbrief/Agentenkontext (der Agent muss das Verfahren sehen, sonst
schlägt er Elefantenfuß-Ausgleich für einen Resindruck vor); Prüfbericht
(neun Bedingungen, zwei bis drei neue Codes mit Handlungsvorschlag);
Handbuch, Abbildungen, Website, sechs Kataloge; Tests (Ende-zu-Ende Weg 1
mit Resin-Profil, Geometrietests gegen analytische Körper). **Der teuerste
Einzelposten:** die Regelsammlung — jede Änderung verlangt die Agenten-Suite
vorher und nachher, rund anderthalb Stunden und echtes Geld je Modelllauf.

## 11. Offene Entscheidungen für Robert

1. **Wird Stufe 1 gebaut, und vor Stufe 2?** Empfehlung: ja und ja — Stufe 1
   ist, was der Kunde gesagt hat, und ohne Stufe 2 vollständig nutzbar;
   umgekehrt nicht.
2. **Verfahren im Druckerprofil (Weg B)?** A macht die Prüfung stumm, C ist
   ausgeschlossen. Ohne B braucht es einen vierten Weg von dir.
3. **Wie viele Resin-Geräte im Startbestand?** Ein bis zwei generische oder
   die verbreiteten Dentalgeräte namentlich — jede Zahl ändert den
   „sechzehn Profile ab Werk"-Satz der Website mit.
4. **Wer liefert die Gerätezahlen?** Herstellerangaben (Quellenregel wie
   Normteiltabelle); der Kunde hat Hilfe angeboten und wäre eine Quelle.
5. **Website-Positionierung „Meshmixer-Nachfolge im Dentalbereich"?** Eine
   Produktentscheidung mit einem realen Multiplikator dahinter.
6. **Analyse-Schichthöhe für die Cupping-Suche:** Druckhöhe (genau, ~3 s am
   dichten Netz) oder eigene feinere Analysehöhe? Die Zahl gehört gemessen —
   mit vorher festgelegter Definition, was „gefunden" heißt.
7. **Zwei Öffnungen als Vorgabe auch für FDM?** Bei FDM genügt eine.
   Verfahrensabhängige Vorgabe oder überall zwei?
8. **Registerpunkt 131 umformulieren** (Abschnitt 1)? Der heutige Titel
   führt in die falsche Richtung.

## 12. Verworfene Alternativen

**Ein Resin-Zweig neben dem FDM-Zweig** (eigene Ops wie `hollow_resin`,
eigene Befunde): schneller zu bauen, scheitert an „alles genau einmal
deklariert" und „Konsistenz vor Vollständigkeit" — und an der Kundensicht:
zwei Menüeinträge „Aushöhlen", und der Nutzer rät. **Resin als reine
Zahlenparametrierung von FDM** (anderer Winkel, andere Wand): scheitert an
5.3 — eine Regel, die für ein Verfahren gegenstandslos ist, bekommt keinen
anderen Wert, sondern einen Geltungsbereich.

## 13. Aufwand und Nutzen, ehrlich

**Stufe 1: Aufwand mittel, Nutzen hoch, Risiko gering.** Der Bestand
existiert; gebaut wird eine Profileigenschaft, ihre Auswertung an zwei
zentralen Stellen, Bedingungen an neun Befunden, der Erststart, die
Nachpflege in Doku und Katalogen. Das Risiko ist Vollständigkeit, nicht
Technik — wer eine der neun Befundstellen übersieht, hat einen Resin-Nutzer,
der genau dort auf eine Düse trifft (der Fall aus
`reparierter-fehler-hat-zwillinge`). **Stufe 2: Aufwand hoch, Nutzen mittel
bis hoch, Risiko mittel.** Cupping ist echte Arbeit (Ringverfolgung,
analytische Testkörper, Leistungsmarke, Orientierungssuche); die Öffnungen
sind klein; der teuerste Posten ist die Regelsammlung (Agenten-Suite).

**Empfohlene Reihenfolge:** Stufe 1 vollständig, ausliefern, den Kunden
fragen, was fehlt — er ist der beste Prüfstand, den dieses Gebiet bekommen
kann, und er hat angeboten, es zu sein.
