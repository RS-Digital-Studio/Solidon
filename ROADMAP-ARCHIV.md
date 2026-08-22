# ROADMAP — Archiv

Die abgeschlossenen Abschnitte der Arbeitsliste: Durchsichten, Bedienläufe,
Reviews und die Funde daraus. **Kein offener Punkt steht hier** — das prüft
`tests/test_roadmap.py`. Was offen ist, steht in `ROADMAP.md`.

Das ist nicht Ballast, sondern das Teuerste, was diese Datei hat: Wer an
einer Stelle arbeitet, an der schon jemand war, findet hier die Messwerte,
die Irrwege und die zurückgenommenen Behauptungen. Gesucht wird über den
Text, das Verzeichnis unten ist nur die Abkürzung.

**Was ein Abschnitt hier über sich sagt, gilt für seinen Stichtag.** Ein
Messwert vom 8. August ist am 22. August nicht falsch, sondern datiert — und wo
ein Text im Präsens steht, beschreibt er den Tag, an dem er geschrieben wurde.

**Und wo „offen" steht, ist es nicht mehr offen.** Einige Abschnitte führen
Prosalisten unter Überschriften wie „Bewusst offen" — die stehen hier, weil kein
Kästchen darin ist, und genau deshalb hat sie nie ein Register gesehen. Beim
Schnitt am 22.08.2026 wurden vier solche Punkte gefunden und nach `ROADMAP.md`
übernommen; was danach hier noch „offen" sagt, ist entweder erledigt, dort
geführt oder eine Grenze aus „Was NICHT gebaut wird". Der einzige Ort, dem man
für den Rückstand glauben darf, ist das Register in `ROADMAP.md`.

| Datum | Abschnitt |
|---|---|
| ohne Datum | [Gegen echte Modelle geprüft](#gegen-echte-modelle-geprüft) |
| ohne Datum | [Referenzkorpus und Passungen vervollständigt](#referenzkorpus-und-passungen-vervollständigt) |
| ohne Datum | [Durchsicht nach P12 — was noch offen ist](#durchsicht-nach-p12--was-noch-offen-ist) |
| ohne Datum | [Aus dem Modellordner abgeleitet](#aus-dem-modellordner-abgeleitet) |
| ohne Datum | [Eine Szene ist nicht ein Material](#eine-szene-ist-nicht-ein-material) |
| ohne Datum | [Deckel aus der Öffnung — und ein Fehler, der darunter lag](#deckel-aus-der-öffnung--und-ein-fehler-der-darunter-lag) |
| ohne Datum | [Aus der Struktur des Modellordners](#aus-der-struktur-des-modellordners) |
| ohne Datum | [Auswahl, Ort und Änderbarkeit](#auswahl-ort-und-änderbarkeit) |
| ohne Datum | [Tiefes Review](#tiefes-review) |
| ohne Datum | [Ein echtes Modell als Prüfstein](#ein-echtes-modell-als-prüfstein) |
| ohne Datum | [Aus der Frage nach der Veröffentlichung](#aus-der-frage-nach-der-veröffentlichung) |
| ohne Datum | [Website](#website) |
| ohne Datum | [Aus der Frage nach dem Handbuch](#aus-der-frage-nach-dem-handbuch) |
| ohne Datum | [Aus der Übersetzungsrunde](#aus-der-übersetzungsrunde) |
| ohne Datum | [Durchsicht: Politur, die man auf jedem Bild sieht](#durchsicht-politur-die-man-auf-jedem-bild-sieht) |
| ohne Datum | [Die zweite Bedienrunde — was das Fenster versprach und nicht hielt](#die-zweite-bedienrunde--was-das-fenster-versprach-und-nicht-hielt) |
| ohne Datum | [Die zwei bekannten Lücken sind zu](#die-zwei-bekannten-lücken-sind-zu) |
| ohne Datum | [Der erste echte CI-Lauf](#der-erste-echte-ci-lauf) |
| ohne Datum | [Die Beispiele wurden Touren](#die-beispiele-wurden-touren) |
| ohne Datum | [Ein frischer Klon war rot, ohne dass sich Code geändert hatte](#ein-frischer-klon-war-rot-ohne-dass-sich-code-geändert-hatte) |
| ohne Datum | [Live gegen Fusion und den ElegooSlicer](#live-gegen-fusion-und-den-elegooslicer) |
| ohne Datum | [Paket 2 der Durchsicht: die Platte kommt an](#paket-2-der-durchsicht-die-platte-kommt-an) |
| ohne Datum | [Paket 3 und 4 der Durchsicht — und die Bohrung, die daneben lag](#paket-3-und-4-der-durchsicht--und-die-bohrung-die-daneben-lag) |
| ohne Datum | [Das Audit vom 06.08.2026 — und was unter dem Code lag](#das-audit-vom-06082026--und-was-unter-dem-code-lag) |
| 2026-08-07 | [Durchsicht: was außerhalb der Anwendung läuft (07.08.2026)](#durchsicht-was-außerhalb-der-anwendung-läuft-07082026) |
| 2026-08-07 | [Jeder Workflow einzeln durchgefahren (07.08.2026)](#jeder-workflow-einzeln-durchgefahren-07082026) |
| 2026-08-07 | [Die Wege einmal von Hand gefahren (07.08.2026)](#die-wege-einmal-von-hand-gefahren-07082026) |
| ohne Datum | [Jeden Weg einzeln durchgespielt (07.08.2026, zweiter Durchgang)](#jeden-weg-einzeln-durchgespielt-07082026-zweiter-durchgang) |
| 2026-08-07 | [Puppenhaus: beide Wege an einem Stück (07.08.2026)](#puppenhaus-beide-wege-an-einem-stück-07082026) |
| 2026-08-07 | [Gewürzdeckel: der Fehler saß im Deckel, nicht im Becher (07.08.2026)](#gewürzdeckel-der-fehler-saß-im-deckel-nicht-im-becher-07082026) |
| 2026-08-07 | [Vollständige Verifikation des Gewürzsets (07.08.2026)](#vollständige-verifikation-des-gewürzsets-07082026) |
| 2026-08-08 | [Aus Kundensicht vollständig nachgefahren (08.08.2026)](#aus-kundensicht-vollständig-nachgefahren-08082026) |
| 2026-08-08 | [Handbuch, Website und Rechtstexte durchgesehen (08.08.2026)](#handbuch-website-und-rechtstexte-durchgesehen-08082026) |
| 2026-08-08 | [Die Lizenzgrenze greift (08.08.2026)](#die-lizenzgrenze-greift-08082026) |
| 2026-08-08 | [Gizmo und Direktmanipulation durchgesehen (08.08.2026)](#gizmo-und-direktmanipulation-durchgesehen-08082026) |
| 2026-08-08 | [Der Schatten im Viewport durchgesehen (08.08.2026)](#der-schatten-im-viewport-durchgesehen-08082026) |
| 2026-08-08 | [Drei Meldungen aus der Bedienung (08.08.2026)](#drei-meldungen-aus-der-bedienung-08082026) |
| 2026-08-08 | [Agent und Chat vertiefen (08.08.2026) — Konzept steht](#agent-und-chat-vertiefen-08082026--konzept-steht) |
| 2026-08-09 | [Die Agent-Vertiefung durchgesehen und behoben (09.08.2026)](#die-agent-vertiefung-durchgesehen-und-behoben-09082026) |
| 2026-08-09 | [Der Erzeugen-Einstieg, aufgeräumt (09.08.2026)](#der-erzeugen-einstieg-aufgeräumt-09082026) |
| 2026-08-09 | [Nachgesehen, was davon stimmt (09.08.2026)](#nachgesehen-was-davon-stimmt-09082026) |
| 2026-08-09 | [Alle Operationen und die fremden Programme aus Kundensicht (09.08.2026)](#alle-operationen-und-die-fremden-programme-aus-kundensicht-09082026) |
| 2026-08-09 | [Das Zeichnen im Handbuch und auf der Website (09.08.2026)](#das-zeichnen-im-handbuch-und-auf-der-website-09082026) |
| 2026-08-09 | [Das Zeichnen-Kapitel Satz für Satz gegen den Code (09.08.2026)](#das-zeichnen-kapitel-satz-für-satz-gegen-den-code-09082026) |
| 2026-08-09 | [Dasselbe noch einmal, gründlicher (09.08.2026)](#dasselbe-noch-einmal-gründlicher-09082026) |
| 2026-08-09 | [Der ganze Bestand durch die laufende Oberfläche (09.08.2026)](#der-ganze-bestand-durch-die-laufende-oberfläche-09082026) |
| 2026-08-12 | [Das Erzeugen-und-Agent-Konzept abgearbeitet (12.08.2026)](#das-erzeugen-und-agent-konzept-abgearbeitet-12082026) |
| 2026-08-14 | [Die Konzepte gegen den Code gehalten (14.08.2026)](#die-konzepte-gegen-den-code-gehalten-14082026) |
| 2026-08-14 | [Trennen, wo man hinzeigt — und vier Wörter weniger (14.08.2026)](#trennen-wo-man-hinzeigt--und-vier-wörter-weniger-14082026) |
| 2026-08-14 | [Die offenen Punkte abgearbeitet (14.08.2026)](#die-offenen-punkte-abgearbeitet-14082026) |
| 2026-08-14 | [Der eigene Änderungssatz im Review (14.08.2026)](#der-eigene-änderungssatz-im-review-14082026) |
| 2026-08-14 | [Alles Offene abgearbeitet (14.08.2026)](#alles-offene-abgearbeitet-14082026) |
| 2026-08-15 | [Drei Funde aus der Slicer-Übergabe (15.08.2026)](#drei-funde-aus-der-slicer-übergabe-15082026) |
| ohne Datum | [Die große Durchsicht vom 16.08.2026 — Code, Oberfläche, Wettbewerb](#die-große-durchsicht-vom-16082026--code-oberfläche-wettbewerb) |
| 2026-08-17 | [Die Oberfläche im Bild durchgesehen (17.08.2026)](#die-oberfläche-im-bild-durchgesehen-17082026) |
| 2026-08-20 | [Die Bedienverträge durchgesehen (20.08.2026)](#die-bedienverträge-durchgesehen-20082026) |
| 2026-08-20 | [Die eigene Arbeit im Review (20.08.2026)](#die-eigene-arbeit-im-review-20082026) |
| 2026-08-20 | [Die Slicer-Übergabe gegen die echten Slicer geprüft (20.08.2026)](#die-slicer-übergabe-gegen-die-echten-slicer-geprüft-20082026) |
| 2026-08-20 | [Die Werkzeugleiste zeigt nur noch Zeichen (20.08.2026)](#die-werkzeugleiste-zeigt-nur-noch-zeichen-20082026) |
| 2026-08-20 | [Die Rückmeldung geht jetzt raus (20.08.2026)](#die-rückmeldung-geht-jetzt-raus-20082026) |
| 2026-08-20 | [Der Erzeuger steht jetzt auf einer Lizenz, die hier gilt (20.08.2026)](#der-erzeuger-steht-jetzt-auf-einer-lizenz-die-hier-gilt-20082026) |
| 2026-08-20 | [Die zwei Historien zusammengeführt (20.08.2026)](#die-zwei-historien-zusammengeführt-20082026) |
| 2026-08-20 | [Preis, und eine Zahl über die Besucher (20.08.2026)](#preis-und-eine-zahl-über-die-besucher-20082026) |
| 2026-08-20 | [Ein Durchgang durchs Haus, und was dabei liegen blieb (20.08.2026)](#ein-durchgang-durchs-haus-und-was-dabei-liegen-blieb-20082026) |
| 2026-08-21 | [Die Bedienung an der Uhr gemessen (21.08.2026)](#die-bedienung-an-der-uhr-gemessen-21082026) |
| 2026-08-21 | [Die Zusatzsoftware aus Kundensicht (21.08.2026)](#die-zusatzsoftware-aus-kundensicht-21082026) |
| 2026-08-21 | [Dieselben neun Modelle, diesmal nachgebaut (21.08.2026)](#dieselben-neun-modelle-diesmal-nachgebaut-21082026) |
| 2026-08-21 | [Die Richtung steht am Parameter, die Untergrenze im Profil (21.08.2026)](#die-richtung-steht-am-parameter-die-untergrenze-im-profil-21082026) |
| 2026-08-21 | [Die zweite Hälfte des Kundenwegs (21.08.2026)](#die-zweite-hälfte-des-kundenwegs-21082026) |
| 2026-08-21 | [Der Slicer sagte es, und der Nutzer erfuhr es nicht (21.08.2026)](#der-slicer-sagte-es-und-der-nutzer-erfuhr-es-nicht-21082026) |
| 2026-08-21 | [Was CuraEngine schreibt, ohne es zu prüfen (21.08.2026)](#was-curaengine-schreibt-ohne-es-zu-prüfen-21082026) |
| 2026-08-21 | [Dieselbe Zusatzsoftware, einen Schritt weiter gedacht (21.08.2026)](#dieselbe-zusatzsoftware-einen-schritt-weiter-gedacht-21082026) |
| 2026-08-21 | [Der Abbrechen-Knopf vor der Zwei-Sekunden-Schwelle — geprüft und geschlossen (21.08.2026)](#der-abbrechen-knopf-vor-der-zwei-sekunden-schwelle--geprüft-und-geschlossen-21082026) |
| 2026-08-21 | [Der dritte Durchgang: was hinter dem Wartezustand lag (21.08.2026)](#der-dritte-durchgang-was-hinter-dem-wartezustand-lag-21082026) |
| ohne Datum | [Zwölf ein halb wurden hundertfünfundzwanzig (21.08.2026, vierter Durchgang)](#zwölf-ein-halb-wurden-hundertfünfundzwanzig-21082026-vierter-durchgang) |
| 2026-08-21 | [Zwei Tabellen für dieselbe Sache (21.08.2026)](#zwei-tabellen-für-dieselbe-sache-21082026) |
| 2026-08-21 | [Der Kundendurchgang durch die vier Wege (21.08.2026)](#der-kundendurchgang-durch-die-vier-wege-21082026) |
| 2026-08-21 | [Der Kundendurchgang auf der ruhigen Maschine (21.08.2026)](#der-kundendurchgang-auf-der-ruhigen-maschine-21082026) |

---

## Gegen echte Modelle geprüft

68 Modelle aus einem privaten Druckordner (106 MB, STL und 3MF, von der
Torschloss-Adapterkappe bis zur Community-Katze mit 13,4 Millionen Dreiecken)
durch die ganze Kette. `tools/run_model_suite.py` macht denselben Lauf mit
einem Bericht statt Zusicherungen; `tests/test_real_models.py` hält die Funde
fest und überspringt sich, wo der Ordner fehlt.

**Alle 68 laufen durch.** Drei Dinge kamen trotzdem heraus:

* Ein Modell mit 13,4 Millionen Dreiecken brauchte 100 Sekunden und **sagte
  nichts dazu**. Es wird nicht abgelehnt — die Grenze dafür liegt bei 20
  Millionen — aber ab 500 000 sagt die Eingangsstufe jetzt, dass Analysekarten
  und Merkmalserkennung ab hier ablehnen und dass Dezimieren hilft.
* Sechs von 68 sind nicht geschlossen. Das ist bei Community-Modellen normal
  und wird korrekt gemeldet.
* Die Kollisionsprüfung verglich nur Hüllquader. Ein Stab, der frei in einer
  Nut steht, war damit eine Kollision — bei jeder Baugruppe, die ineinander
  greift. Jetzt zweistufig: Boxen als Vorfilter, danach der Kern. Ein leerer
  Schnitt ist dabei die Antwort, nicht der Fehlschlag, den die Rückfallkette
  daraus macht.

## Referenzkorpus und Passungen vervollständigt

Der Korpus aus §34 ist jetzt komplett: `broken_selfint.stl` (zwei Würfel, die
sich durchdringen), `colored.3mf` (zwei Materialgruppen, mit der eigenen
3MF-Hälfte geschrieben) und `assembly_fit.p3d` (Platte, Deckel, Passungspaar).
Beim letzten sind die Zahlen die Lehre: 6 mm Bohrung wird 6,2 wegen der
Kompensation, PETG will 0,25 Spiel, also ist der Stift 5,95 — und in einem
anderen Material meldet sich die Passung von selbst.

Dabei kam heraus, dass **`flush` als Passungsart nie geprüft wurde**: angenommen,
abgespeichert und stillschweigend übersprungen. Jetzt wird der Abstand der
zweiten Fläche von der Ebene der ersten gemessen — die Zahl, die man mit einem
Haarlineal über die Baugruppe findet. Zwei Flächen, die nicht parallel stehen,
sind ein anderer Fehler und werden als solcher gemeldet.

**Zur Paketgröße:** 749 MB im Ordner, **255 MB gepackt** — das ist die Zahl, die
jemand herunterlädt, und sie liegt im Rahmen vergleichbarer Anwendungen. VTK von
Hand zu beschneiden würde davon vielleicht 50 MB sparen und dafür Abstürze in
selten benutzten Pfaden riskieren, die erst beim Nutzer auffallen. Bewusst
gelassen.

## Durchsicht nach P12 — was noch offen ist

**Vollständigkeit gegen §25.** Der Abgleich der Kategorienliste mit dem
Register hat neun Operationen aufgedeckt, die der Plan nennt und die es nicht
gab — die Kategorien „Netz" und „Beschriftung" waren leer, und der
Variantengenerator war gebaut, getestet und von keiner Oberfläche erreichbar.
Alle neun sind jetzt da: Spiegeln, Dezimieren, Glätten, Neu vernetzen,
Aushöhlen mit Entlüftung, Elefantenfuß ausgleichen, Senken, Bohrung
verschließen, Text aufbringen, Zeichnung extrudieren (SVG und DXF) — dazu der
Weg zum Variantengenerator.

Das ist zugleich die Antwort auf „je mehr in der App statt außen": Beschriftung
und Umriss-Extrusion sind die zwei häufigsten Gründe, ein zweites Programm zu
öffnen. Beide brauchen jetzt keines mehr.

**Behoben in dieser Runde**

* Anordnen und Kollisionsprüfung liefen auf einer leeren Eingabeliste — sie
  sind `consumes=0, produces=VARIABLE`, bekamen von der Oberfläche aber keine
  Objekte. Die Regel steht jetzt einmal im Register (`takes_whole_scene`).
* Die Suite las die echten Nutzerverzeichnisse. Ein kalibriertes Material auf
  dem Entwicklerrechner änderte, was die Tests sehen — und ein Testlauf ließ
  Kalibrierungen im Profilordner zurück.
* Der Signierschritt der CI hätte nie ausgelöst: `env` einer Schrittdefinition
  ist in deren eigenem `if` nicht lesbar. Jetzt auf Job-Ebene.
* Die CI installierte kein `brep` — die B-Rep-Tests hätten sich dort still
  übersprungen und der Kern wäre nie geprüft worden.
* Die Paketierung sah OCP und V-HACD nicht: beide werden absichtlich erst in
  der Funktion importiert, und PyInstaller liest nur Importe auf Modulebene.
  Ein gebautes Paket hätte stillschweigend keine Verrundungen gehabt.

**Bewusst offen**

* **Schichtanalyse 1,7 s statt 300 ms** (§31). Was übrig ist, sind Polygonaufbau
  und Mengenoperationen in GEOS. Das braucht einen kompilierten Kern; der Wert
  ist festgehalten, ein Rückschritt fällt auf.
* **CI nie gelaufen.** Es gibt kein Remote — die Datei ist geprüft (YAML
  geparst, Bedingungen nachgerechnet), aber nicht ausgeführt. Beim ersten Push
  auf einen Server ist damit zu rechnen, dass Kleinigkeiten auftauchen.
  *Überholt am 02.08.2026: das Repository liegt auf GitHub, die CI ist
  gelaufen — siehe „Der erste echte CI-Lauf". Der Satz bleibt stehen, weil er
  richtig vorhergesagt hat, was dann passierte: es waren vier Kleinigkeiten.
  Offen ist allein der `workflow_dispatch`-Lauf über alle drei Plattformen.*
* **Keine Website** (§37.3). Marketing, kein Programmteil; kommt, wenn es
  etwas zu veröffentlichen gibt.
* **Der Slicer bleibt außen** (§22.5, §28). Ein eigener G-Code-Generator wäre
  fünfzehn Jahre fremde Arbeit schlechter nachgebaut; die Schichtanalyse sucht
  und bewertet, die Druckdatei kommt weiter aus dem Slicer.

## Aus dem Modellordner abgeleitet

Nicht aus dem Plan, sondern aus dem, was 68 echte Modelle zeigen. Zwei Dinge
kamen vor, für die man bisher aus Solidon heraus musste:

* **Prüfstück erzeugen** (`test_piece`). Ein Würfel um die Stelle, die man
  ausprobieren will, herausgeschnitten — nicht nachgebaut. Ausgeschnitten
  bleibt es die echte Geometrie mit der echten Toleranz; nachgebaut wäre es
  eine zweite Konstruktion, die anders druckt als das Teil, für das sie steht.
  Gemessen an einer gebohrten Platte: 20 × 20 × 8 mm, 2975 von 31 775 mm³,
  geschlossen, auf dem Bett.
* **Beschriftung in zwei Farben, auf beiden Wegen.** `label_text` bekam einen
  Materialslot — die Buchstaben tragen ihn in die Vereinigung, der
  Attributübergang aus P9 bringt ihn heraus, und der 3MF-Export macht daraus
  den Farbwechsel in *einer* Datei. Daneben `create_label`, das den Schriftzug
  als eigenes Objekt anlegt: für den Drucker, an dem von Hand gewechselt wird,
  und für Lettern zum Aufkleben. Welcher Weg besser ist, entscheidet der
  Drucker, also gibt es beide.

**Dabei aufgefallen — zwei Fehler, die still waren**

* **Die Rückfallkette hielt „nichts" für „gescheitert".** Für eine Differenz,
  die jemand wollte, ist ein leeres Ergebnis der Hinweis, dass der Kern
  aufgegeben hat, und die nächste Stufe ist richtig. Für einen Schnitt kann es
  die Antwort sein: die Körper treffen sich nicht. Das Prüfstück über einer
  Bohrung war damit kein Nutzerhinweis, sondern eine `BooleanFailedError` nach
  vier Stufen. `boolean(..., allow_empty=True)` sagt es jetzt einmal; die
  Stelle in der Kollisionsprüfung, die den Kern deshalb direkt fragt, hatte
  denselben Grund.
* **Die konvexe Zerlegung lief nie.** Der Aufruf übergab ein `randomizeSeed`,
  das dieses V-HACD nicht kennt; der `TypeError` wurde als „Modul fehlt"
  gelesen, die Funktion gab eine leere Liste zurück, und der Test übersprang
  sich mit „optionale Abhängigkeit". Damit war der Hinweispfad der
  Trennebenensuche seit P10 tot — hinter einer grünen Suite. Der Aufruf stimmt
  jetzt (das L zerfällt in vier Stücke), der Test überspringt sich nicht mehr,
  und weil dieses V-HACD keinen Zufallsregler hat und nachgemessen
  deterministisch ist, ist die `seed`-Kette durch sechs Signaturen ersatzlos
  weg statt weiter mitgeschleppt.

## Eine Szene ist nicht ein Material

Der dritte Fund aus dem Modellordner, und der einzige, bei dem bisher etwas
**falsch** gerechnet wurde statt nur zu fehlen: Baugruppen mit einer TPU-
Dichtung in einem PETG-Gehäuse. Toleranz, Schwund und Elefantenfuß kamen für
beide Körper aus dem Projektmaterial.

`SceneObject.material` trägt das jetzt am Körper, `profiles.for_object` löst es
auf, und `set_material` setzt es als Operation im Stack — damit gilt §11 weiter:
kein verstecktes Attribut, rücknehmbar, im Projekt gespeichert.

Was daran hängt:

* **Passungen.** `auto:` heißt „das, worin das hier gedruckt wird", und das sind
  bei zwei Körpern zwei Antworten. Wo sie sich unterscheiden, gewinnt der
  größere Wert — bei Spiel der weitere Spalt, bei Presssitz die *kleinere*
  Pressung, weil die Werte negativ sind. Eine Regel für beides, und beide Male
  die, deren Fehlschlag ein brauchbares Teil übrig lässt: was lose sitzt, kann
  man kleben; ein Gehäuse, das beim Fügen gerissen ist, ist Ausschuss. Ein
  ausgeschriebenes `auto:petg` bleibt, was dasteht — das hat jemand mit Absicht
  hingeschrieben.
* **Elefantenfuß.** TPU quetscht 0,25 mm breit, PETG 0,2. Auf einer Dichtung
  ist das der Unterschied zwischen dichten und nicht dichten.
* **Passstifte** nehmen das Spiel des geteilten Körpers, nicht das des Projekts.
* **Steckbrief und Objektbaum** nennen ein abweichendes Material; ein
  übereinstimmendes nicht, sonst steht es an jedem Körper und niemand liest es.
* **Cache.** Das Material steht im Objekt-Eintrag; ohne das käme nach einem
  Neustart der Körper mit dem alten Material zurück.

## Deckel aus der Öffnung — und ein Fehler, der darunter lag

Die vierte Funktion aus dem Modellordner: eine Schachtel ist da, ein Deckel
fehlt. Von Hand heißt das den Hohlraum abmessen, ihn eine Kleinigkeit kleiner
neu zeichnen und am Drucker erfahren, um wie viel die Kleinigkeit falsch war.

`create_lid` misst nicht, es schneidet: ein Querschnitt durch die Wand an der
Öffnung gibt die Außenkontur und den Hohlraum darin, die Platte ist die gefüllte
Außenkontur, der Kragen der Hohlraum minus dem Spiel aus dem Materialprofil
(§12). Damit entscheidet über den Deckel dieselbe Zahl wie über jede andere
Passung, und eine Kalibrierung nach §28.3 erreicht auch Deckel, die vorher
entstanden sind. Ein geteilter Kasten bekommt einen Kragen je Fach — das ist,
was den Deckel am Verdrehen hindert.

Nachgemessen an einem Gehäuse 60 × 40 × 30 mit 3 mm Wand: Kragen 53,10 × 33,10
(Hohlraum 54 × 34 minus zweimal 0,45), Deckel geschlossen, gemeinsames Volumen
mit dem Gehäuse **0,0 mm³** — er geht hinein.

**Der Fehler darunter.** Der erste Versuch bekam an jeder Höhe „hier schneidet
nichts". Der Grund lag nicht im Deckel, sondern in der Schichtanalyse: beim
Verschachteln der Ringe wurde gefragt, ob ein Punkt der *Außenkontur* eines
Teils in einem anderen liegt. Bei einer Schachtel ist die Außenkontur das äußere
Rechteck, und dessen Mitte liegt im Hohlraum — Wand und Hohlraum erklärten sich
gegenseitig zum Loch, beide kamen ungerade heraus, und ein Schnitt, den man
sehen kann, kam als `None` zurück.

Betroffen war **jede Schicht jedes hohlen Körpers**, und damit Wandkarte,
Überhänge und Stützvolumen. Der vorhandene Korpus hat es verdeckt, weil seine
Bohrungen außermittig sitzen: eine mittige Bohrung in einer Platte reicht schon.
Gefragt wird jetzt nach einem Punkt des Teils selbst, nicht seiner Hülle; drei
Tests halten den Fall fest.

**Dazu:** eine Berührung ist keine Überschneidung. Deckel auf dem Rand, Teil auf
der Platte, zwei Hälften eines Schnitts — der Durchschnitt ist ein flaches,
geschlossenes Blatt ohne Inhalt, und trimesh teilt beim Schwerpunkt durch dessen
Null. `boolean.shared_volume` beantwortet das einmal für alle, und die
Kollisionsprüfung benutzt es.

**Und ein zweiter Fall, den der erste Fix freigelegt hat.** Wo vorher früh
`None` zurückkam, werden jetzt Polygone gebaut — und drei Modelle des Korpus
haben eine Tasche, die genau bis an die Außenwand reicht. Das Loch trifft die
Außenkontur in einem Punkt, GEOS baut das Polygon klaglos und wirft bei der
nächsten Operation darüber eine `TopologyException` mit einer Koordinate und
sonst nichts. Geheilt wird jetzt dort, wo es entsteht (`buffer(0)`, weil eine
Fläche gesucht ist). Der Korpus läuft wieder **68 von 68** durch.

Die Prüfung im heißen Pfad kostet nichts Nennenswertes: Schichtanalyse 1076 ms
gegen 1062 ms, Wandkarte 3331 gegen 3226 — für Zahlen, die vorher für jeden
hohlen Körper gar nicht erst entstanden sind.

## Aus der Struktur des Modellordners

Die Runde vorher kam aus den Modellen. Diese kommt aus den *Dateinamen und
Ordnern*: `Versuch 1` neben `Versuch 2`, `Clippy_Filament-Clip_x10`,
`Wasserfall_1_Koerper` bis `_4_TPU-Liner`, `deckel_dreh` neben
`gewuerzbehaelter_body`. Was jemand in einen Dateinamen schreibt, ist das, wofür
das Programm keinen Platz hat.

### 3MF wurde falsch gelesen

22 der 3MF im Ordner nutzen die Produktions-Erweiterung: die Objekte liegen in
eigenen Dateien unter `3D/Objects/`, das Build verweist über Komponenten darauf.
trimesh löst eine solche Komponente auf die **ganze Datei** auf statt auf das
eine Objekt, das sie nennt. Nachgemessen:

| Datei | Dreiecke echt | gelesen | Faktor |
|---|---|---|---|
| Pool-Fountain_Nozzle_horizontal | 290 120 | 580 240 | 2,0 |
| Scraper_with_Magnets | 53 800 | 107 600 | 2,0 |
| Cat_Phone_Stand_Kawaii | 787 836 | 13 393 212 | **17,0** |

Kein Tempoproblem, sondern ein falsches Ergebnis: die Düse hat zwei Körper
(21,68 und 30,37 cm³), gelesen wurden vier — jeder deckungsgleich verdoppelt.
Volumen 104,11 statt 52,05 cm³, und damit Materialschätzung und Druckzeit
doppelt.

*Nachgemessen und dabei eine eigene Behauptung zurückgenommen:* die
Wasserdichtheit ist davon **nicht** betroffen. Zwei deckungsgleiche, aber nicht
verschweißte Kopien sind je für sich geschlossen, also bleibt die Datei dicht.
Dass die Düse als „nicht geschlossen" gemeldet wird, liegt an einem ihrer beiden
echten Körper — vorher wie nachher richtig.

Jetzt liest ein eigener Geometrieleser das Format — im 3MF-Modul, wo das übrige
3MF-Wissen schon steht. Dieselbe Katze: 787 836 Dreiecke in **2,6 s** statt
13,4 Millionen in 44,8 s.

### Ein 3MF ist eine Baugruppe

Auch richtig gelesen verschmolz alles zu einem Körper. `Wasserfall_.3mf` sind
vier Teile — Körper, Deckel, Tülle, TPU-Liner —, `Taschentuchbox` sind 21. Genau
die Aufteilung, die das Material pro Körper und die Platte pro Teil braucht. Die
Namen holt der Leser aus `Metadata/model_settings.config`, weil das die einzige
Stelle ist, an der sie stehen; Farbgruppen liest er je Körper, wo der alte Leser
aufgab, sobald eine Datei mehr als einen enthielt.

Zwei Folgeänderungen: `takes_whole_scene` wird deklariert statt aus
`(consumes=0, produces=VARIABLE)` geschlossen, und `OperationDraft.produces`
sagt dem Stapel, wie viele Objekte eine Datei mitbringt — er vergibt die IDs,
bevor die Datei gelesen ist.

### Stückzahl

„x10" im Dateinamen ist eine Zahl, die keiner mehr ändern kann. „Objekt
duplizieren" hat jetzt eine Anzahl bis hundert: ein Schritt mit einer Zahl statt
neun gleicher Schritte im Stapel. Eine Operation sagt dazu im Register, in
welchem Parameter ihre Ausgabezahl steht (`produces_from`); ein Ausdruck (§13)
geht dort nicht, weil die IDs vor der Auflösung vergeben werden, und wird mit
genau diesem Satz abgelehnt.

### Drehdeckel — und das Gewinde, das nicht griff

`deckel_dreh` neben `gewuerzbehaelter_body`, `kartuschen_deckel` neben
`kartuschen_kaefig`: Schraubdeckel. Der Gewinde-Baustein kann nur M2 bis M8, ein
Glashals mit 40 mm und grober Steigung war unerreichbar. `screw_lid` setzt den
Hals auf die Öffnung und macht den Deckel dazu — beide aus einer Operation, weil
sie eine Entscheidung sind.

**Dabei kam heraus, dass das Gewindepaar der Bausteinbibliothek nie gegriffen
hat.** Die Mutter wurde auf den Außendurchmesser gebohrt statt auf den Kern:
damit bleibt nichts stehen, woran der Kamm der Schraube sich hält. Gemessen an
M6: Schraubenkamm r = 2,925, Mutterbohrung beginnt bei r = 3,075 — 150 µm Luft,
die Schraube fällt durch. Jede Hälfte war für sich richtig, wasserdicht und
maßhaltig; nur das Paar war es nicht, und getestet wurde jede Hälfte für sich.

Jetzt wird das Innengewinde vom Kern plus Spiel geschnitten. M6 nachgemessen:
Schraube 2,375–2,925, Mutter 2,525–3,075 — 0,15 mm auf beiden Flanken, genau das
Spiel aus dem Parameter. Der Drehdeckel rechnet nach derselben Regel: Hals
18,34–20,00, Deckel 18,465–20,125. Die 0,55 der Rippentiefe heißt jetzt
`RIDGE_SHARE` und steht an einer Stelle, weil drei Rechnungen sich darauf
verlassen — und zwei davon, die verschiedene Zahlen benutzen, sind ein Paar, das
nicht zusammenpasst, ohne dass es einer der beiden Hälften anzusehen ist.

## Auswahl, Ort und Änderbarkeit

Aus einer Frage entstanden: „kann man einzelne Flächen auswählen und dort eine
Operation ansetzen, oder wie fügt man Operationen zu einem Objekt hinzu?" Beim
Nachsehen war die Antwort unbefriedigend — das Fundament stand, aber drei Drähte
waren nicht angeschlossen.

**Der Klick kam nie am Dialog an.** Merkmale werden seit P3 erkannt, stehen im
Objektbaum und sind im Fenster anklickbar; `applies_to` sagt, welche Operation
sich für welches Merkmal anbietet. Der Dialog danach öffnete trotzdem mit
Vorgabewerten. Wer in die gerade angeklickte Fläche bohren wollte, las deren
Koordinaten von der Analysekarte ab und tippte sie ein.

`scene.placement.values_for` ist die Verbindung, und sie liegt im Kern, weil die
Regel auf der Kommandozeile und für den Agenten dieselbe sein muss. Was ein
Merkmal beiträgt, ist der Ort und die Richtung — **nicht die Größe**: eine Senkung
nimmt den Kopfdurchmesser der Schraube, nicht den der Bohrung, auf der sie sitzt,
und eine hilfsbereit eingetragene 5,2 wäre dort eine falsche Zahl, die aussieht
wie eine gemessene. Eine Fläche, die schräg steht, nennt keine Achse: ein
gerundeter Wert, von dem niemand erfährt, ist schlimmer als keiner.

**Die Deckel-Ops nahmen die Fläche nicht.** Sie deklarierten `applies_to=["face"]`
und rechneten mit der Oberkante — eine seitliche Fläche auswählen und einen
Drehdeckel erzeugen arbeitete trotzdem oben. Jetzt haben sie einen Parameter
`An Fläche`; die Auswahl trägt ihn ein, und die Operation liest die Fläche selbst,
damit sie prüfen kann: eine, die nicht waagerecht liegt, wird zurückgewiesen
statt als Höhe gelesen zu werden.

**Eine Operation war nicht änderbar.** Nur Projekt-Parameter (§13) ließen sich
drehen; die Zahlen einer Operation nicht. Eine Bohrung zwei Millimeter zu
versetzen hieß: zurücknehmen und neu bohren. `History.change_params` macht daraus
eine Änderung — Doppelklick auf den Schritt im Verlauf öffnet denselben
erzeugten Dialog auf den Werten, die in der Datei stehen. Neu gerechnet wird nur
der Zweig darunter, der Rest kommt aus dem Cache (§15).

Zwei Dinge daran sind bewusst eng: zurückgenommene Transaktionen fallen weg wie
beim Anwenden, weil es keine Zweige gibt (§15.4). Und eine Änderung, die die
*Anzahl* der Objekte ändert, während spätere Schritte damit arbeiten, wird
abgelehnt — die IDs der neuen Körper sind nicht die alten, und ein Fehler am
Ende des Stapels über eine Zahl am Anfang ist einer, den niemand mit dem
verbindet, was er getan hat.

Der Dialog kennt jetzt Startwerte, und dieselbe Zeile trägt beides: den Klick auf
eine Fläche und das erneute Öffnen einer Operation. Ein zweiter Dialog für den
zweiten Fall wäre eine zweite Stelle, an der ein Parameter fehlen kann.

*Nebenbei zum dritten Mal in die gleiche Falle getreten:* ein Test, der ein
lebendes `MainWindow` etwas fehlschlagen lässt, hängt — das Fenster antwortet auf
`session.failed` mit einem modalen Meldungsfenster. Steht jetzt im Kopf der
Testdatei.

## Tiefes Review

Geleitet von den Mustern, die diese Sitzung dreimal gezeigt hat: eine
Fehlerbehandlung, die einen echten Fehler als erwarteten Sonderfall verbucht;
ein Test, der den Pfad nie betritt; ein Paar, dessen Hälften einzeln stimmen;
eine Behauptung im Kommentar, die keiner nachgemessen hat. Fünf Funde.

**Ein zyklisches 3MF hängte die Anwendung auf.** Die Tiefengrenze bremst jeden
*Pfad* bei 32 — bei zwei Komponenten je Objekt sind das 2³² Pfade, alle 32 tief
und keiner wiederholt. Eine Datei von 500 Byte, und der Import kommt nie zurück.
Was hilft, ist ein Objekt nicht zu betreten, das auf dem Weg dorthin schon liegt:
0,001 s statt unendlich (§32 — eine Grenze sagt etwas, sie hängt nicht).

**Der Planer vergab 5 Millionen Objekt-IDs in 1,1 Sekunden.** Die Stückzahl
deklariert `maximum=100`, geprüft wird das aber erst, wo die Szene gerechnet
wird — und der Stapel vergibt die IDs vorher. Jetzt prüft er gegen dieselbe
Deklaration, also gegen eine Wahrheit statt gegen zwei.

**Eine nach unten zeigende Fläche war eine Öffnung.** „Waagerecht" war zu
großzügig: die Innendecke eines Hohlraums ist auch waagerecht. Als Öffnungshöhe
gewählt baute sie einen Deckel *im* Kasten, bei 26,9 von 30 mm, und keiner der
Schritte danach merkte etwas — ein Schnitt unter dieser Ebene trifft die Wand.
`faces_up` verlangt jetzt, dass sie nach oben zeigt.

**Die Fehlerbehandlung, die den V-HACD-Fehler verschluckt hat, hatte neun
Geschwister.** `PROGRAMMING_ERRORS` in `core/errors.py` benennt die drei Typen,
die heißen „der Code ist falsch", und neun Handler lassen sie durch, statt sie
als Umgebungsfehler zu verbuchen. Zwei Tests halten beide Hälften der Regel:
ein `TypeError` kommt durch, ein `RuntimeError` bleibt gefangen.

**Die Verwaisungsprüfung hat ihren eigenen Fall vorhergesagt.** Im Kommentar von
`references` stand: „Operations carry coordinates, not feature ids; when one of
them starts to reference a feature it is listed here too." Seit P5 tun sie es —
jeder eingesetzte Baustein trägt `at_feature`, achtzehn Operationen deklarieren
eine, und keine wurde je geprüft. Eine Datei, deren `hole_1` weg war, bekam
nicht die Frage aus §21.3, sondern blieb an der Operation mit einem Fehler
stehen. Welche Parameter zählen, ist jetzt deklariert (`kind="feature"` stand
seit P0 im Vertrag und hatte keinen Nutzer); wird ein Verweis fallen gelassen,
verliert die Operation nur den Namen und nicht ihre Geometrie.

**Zwei eigene Behauptungen zurückgenommen:** `values_for` liegt nicht im Kern,
„weil CLI und Agent dieselbe Regel brauchen" — sie benutzen es nicht. Es liegt
dort, weil es eine Regel über Geometrie und Parameter ist, prüfbar ohne Qt; der
Agent arbeitet aus dem Steckbrief, und **deshalb steht die Position jedes
Merkmals jetzt darin**. Vorher nannte der Steckbrief Durchmesser und Achse einer
Bohrung und nicht, wo sie ist — für „setze ein Teil an hole_1" reicht der Name,
für „bohre daneben" nicht. Und `record_solvers` behauptete, die notierte
Rückfallstufe lasse eine Datei gleich rechnen; die Auswertung liest sie nie —
gleich rechnet sie, weil die Kette deterministisch ist.

Korpus danach: **68 von 68**, 1681 Tests grün.

## Ein echtes Modell als Prüfstein

Ein heruntergeladener Eiffelturm, 15,6 MB, 312 970 Dreiecke, Ordner und Datei
chinesisch benannt. Vier Funde, jeder davon von der Datei selbst gestellt.

**Die CLI stürzte am Dateinamen ab.** `print` auf einer Windows-Konsole encodiert
nach cp1252, und `埃菲尔铁塔18cm.stl` gibt es dort nicht — der Import lief durch
und der Lauf endete im `UnicodeEncodeError` auf der Zeile, die den Erfolg meldet.
Deutsche Umlaute überleben cp1252, deshalb ist das eine ganze Phase lang niemandem
aufgefallen. Jetzt sprechen beide Ströme UTF-8 mit `backslashreplace`.

**Der Export verstümmelte den Namen.** `safe_name` schickte den ganzen Namen durch
ASCII: aus `埃菲尔铁塔18cm` wurde `18cm`, aus `Соединитель` wurde `teil`. Unsicher
ist eine kurze Liste — Pfadtrenner, Doppelpunkt, was Windows reserviert —, und der
reguläre Ausdruck hielt sich mit `\w` unter `re.UNICODE` längst daran. Die
ASCII-Zeile war es, die zerstörte. `Boîtier` behält jetzt auch seinen Zirkumflex.

**Die Kommandozeile konnte gar nicht exportieren.** Laden, reparieren,
beschreiben — und das Ergebnis blieb im Projekt. Der Schreiber aus §29 stand seit
P2 und war von außen nicht erreichbar. `solidon3d export` gibt es jetzt, mit
Objektauswahl, Namensschema und der Vorabprüfung vor dem ersten Byte.

**Und die Undichtigkeit war keine.** Der Turm hatte genau drei offene Kanten über
drei Punkte — kollinear bis auf die letzte Stelle, 3,853 + 1,927 = 5,780. Kein
Loch, sondern eine **T-Verbindung**: die lange Kante wurde beim Bauen der
Nachbarfläche geteilt und die Fläche auf der anderen Seite nie informiert.
`trimesh.repair.fill_holes` lehnt das zu Recht ab — ein Dreieck über drei
kollineare Punkte hat keine Fläche. `stitch_t_junctions` gibt stattdessen der
anderen Fläche den fehlenden Punkt: eine Fläche wird zu zweien, keine Geometrie
bewegt sich, das Volumen bleibt auf vier Stellen gleich. Ergebnis am Modell:
14 Teile → 2, Randkanten 12 → 0, wasserdicht.

Befund zum Modell selbst: 0 Inseln, keine Schicht unter Düsenbreite, längste
freie Spanne 8,33 mm bei z=69,1 — die Zusage „ohne Stützen" hält. Die zwölf
gelöschten Teile waren Splitter mit Volumen null; das dreizehnte, eine
freistehende Spitze von 3,3 × 3,3 × 25,2 mm, ist absichtlich da und blieb.

## Aus der Frage nach der Veröffentlichung

Der Anlass war keine technische: „wie weit sind wir weg, was fehlt, ist es gut
genug." Die Antwort auf die letzte Frage war das Problem — die Suite war grün,
und trotzdem war das, was ein Fremder als Erstes sieht, nicht vorführbar.

**Die Zusatzprogramme waren da und wurden nicht gefunden.** `shutil.which`
kennt nur den PATH, und Windows-Installationsprogramme tragen dort nichts ein:
OpenSCAD unter `C:\Program Files\OpenSCAD` und ein installierter Slicer galten
als fehlend, mit dem Angebot, sie ein zweites Mal zu installieren. Gesucht wird
jetzt an vier Stellen, und Dienste werden gefragt statt gesucht — ComfyUI
startet Solidon ohnehin nie, es redet über HTTP mit ihm. Wo alles das nichts
findet, gibt es den Weg, der immer geht: den Ort selbst angeben.

**201 von 325 Parametern hatten keinen Hilfetext.** Ein Zahlenfeld mit einer
Beschriftung darüber ist keine Erklärung. Alle 325 tragen jetzt einen Satz, und
wo möglich sagt er, was passiert, wenn man die Zahl falsch wählt. Ein Test im
Registerkonsistenzlauf hält das fest — auch gegen Texte, die nur den Titel
wiederholen.

**Es gab kein Handbuch.** Jetzt achtzehn Seiten, die Referenz davon erzeugt.

**Die Beispiele zeigten acht von zweiundsechzig Operationen** — und führten
dabei zwei Dinge vor, die nicht stimmten: vier Warnungen ohne Anlass und eine
Reparatur, die nicht reparierte. Jetzt sieben Projekte, und beim Bauen kamen
vier Fehler heraus, die jede Auswertung betreffen:

* Der **Mittelpunkt einer Fläche** war das Mittel über die Dreiecksschwerpunkte
  und hing damit an der Vernetzung. Eine Bohrung zog ihn um 16,8 mm zum Loch,
  und die Zuordnung hielt die Fläche danach für eine andere.
* Auf einem erzeugten Netz galten **181 Facetten als Flächen**, weil der Anteil
  an der größten Fläche nur bei einem konstruierten Teil filtert. Danach war
  jede Zuordnung mehrdeutig und die Auswertung hielt an — Weg 3 kam nach der
  Reparatur nicht weiter.
* **Mehrdeutig war jeder Kandidat, der überhaupt in Frage kam**: die Marge stand
  als `max(bester * 1,25, Annahmeschwelle)` da und war damit wirkungslos.
* **`match()` bekam nie sein `old_centre`.** Der Parameter steht seit P3 in der
  Signatur. Ohne ihn verlor *Auf dem Bett anordnen* jedes Merkmal jedes Objekts.

Dazu zwei Meldungen, die das Gegenteil dessen sagten, was passiert war: eine
geschlossene offene Kante als Warnung, und acht verwaiste Merkmale für ein
Prüfstück, das absichtlich 22 mm aus einem 70er Gehäuse schneidet.

**Bewusst offen, weil es niemand von hier aus erledigen kann**

* **Kein Remote, keine CI.** Die Datei ist geprüft, nie gelaufen.
* **Keine Website**, und die Adresse in `core/updates.py` ist ein Platzhalter.
* **Kein Zertifikat**, also SmartScreen beim ersten Start.
* **Kein Vertriebsweg** — kein Lizenzschlüssel, keine Testphase, kein
  Zahlungsanbieter, keine Rechtstexte.
* **Kein einziger fremder Nutzer.** 1797 Tests sagen, dass der Code tut, was
  gemeint war. Sie sagen nichts darüber, ob jemand anders die App bedienen kann.

---

## Website

Entschieden am 31.07.2026: statische Seite auf einem Webspace, Subdomain
`solidon3d.rs-digital.org` — dort liegen auch die `version.json` (§37.2,
`core/updates.py`) und der Installer. Die Quelldateien liegen in `website/`,
die Schrittliste für DNS und Upload in `website/README.md`. Impressum und
Datenschutz sind Entwürfe und vor der Veröffentlichung zu prüfen.

**Berichtigt am 06.08.2026: die Domain war erfunden.** Hier stand bis dahin
`solidon3d.rsdigital.de`, und die Adresse reiste von hier aus in
`branding.py`, `updates.py` und `version.json`. Diese Domain gibt es nicht
und gab es nie — es gibt genau eine, `rs-digital.org`, die primäre Domain des
Google Workspace. Der Vermerk weiter unten, es stünden „zwei Schreibweisen
nebeneinander, bewusst so entschieden oder zu vereinheitlichen", war die
richtige Beobachtung mit der falschen Erklärung: es waren nicht zwei
Schreibweisen einer Sache, sondern eine echte Adresse und eine angenommene.
Dass eine Annahme als „entschieden" in die Roadmap kam, ist der eigentliche
Fehler — Regel 21 gilt auch für Adressen.

**Entschieden am 08.08.2026: eine eigene Domain, `solidon3d.de`.** Damit
entfällt die Subdomain und mit ihr der teuerste Teil der Einrichtung. Die
Zone von `rs-digital.org` liegt in Google Cloud DNS, während Squarespace die
Registrierung hält — beide Häuser verweisen für einen freien Record
aufeinander, und einen A-Eintrag hätte dort niemand setzen können, ohne die
Workspace-Mail zu gefährden. Die eigene Domain wird beim Webspace-Anbieter
registriert und dort verwaltet: kein TXT-Token für eine externe Domain, kein
A-Record in fremder Zone, keine Subdomain mit eigenem Dokumentenstamm in
Plesk. `rs-digital.org` bleibt Firmendomain und trägt die Geschäftspost,
unberührt.

**Und die Support-Adresse zieht mit: `support@solidon3d.de`.** Der offene
Punkt stand in `branding.py` — Produktseite und Support lagen seit der
Umbenennung auf verschiedenen Domains, und wer eine Setup-Datei von der einen
Adresse lädt und im Programm eine Adresse der anderen findet, hat zwei Namen
vor sich und keinen Grund zu glauben, dass sie zusammengehören. Jetzt ist es
ein Name: Website, Download, `version.json`, Update-Hinweis, Über-Dialog,
Fehlerbericht, Impressum und beide Startseiten stehen unter `solidon3d.de`.
Die Schrittliste in `website/README.md` ist entsprechend neu geschrieben; sie
nennt jetzt auch SPF und DMARC für die neue Zone, die auf der Firmendomain
seit jeher fehlen.

## Aus der Frage nach dem Handbuch

Anlass war eine Feststellung, keine Fehlermeldung: „Wir wollen Geld dafür."
Das Handbuch hatte achtzehn Seiten, kein einziges Bild, und seine sieben
geschriebenen Seiten erklärten Begriffe statt Handgriffe. Wer Solidon zum
ersten Mal öffnete, fand nichts, was ihn vom Startbildschirm bis zur
exportierten Datei führt.

**Jetzt fünfundzwanzig Seiten, zwanzig Abbildungen, drei Ausgabewege.** Fünf
neue Kapitel: die ersten fünfzehn Minuten Klick für Klick, das Fenster, die
Bausteine, „Wenn etwas nicht geht" mit zehn Anfängerfällen, und ein Wörterbuch
mit dreißig Begriffen — „wasserdicht", „Elefantenfuß" und „Insel" kennt
niemand, der nicht schon drinsteckt.

**Keine Abbildung wird von Hand gepflegt.** Schemata entstehen als SVG aus
`core/drawing`, Bausteine und Op-Ergebnisse werden aus der echten Geometrie
projiziert, die fünf Bildschirmfotos nimmt `tools/make_figures.py` auf. Weil
die Beschriftungen Text bleiben, ist das englische Handbuch bis in die Bilder
hinein übersetzt.

Was dabei zutage kam:

* **Das Passungsbild zeigte 0,20 mm, im Materialprofil stehen 0,25.**
  Ausgerechnet die Abbildung, die erklärt, dass Toleranzen nicht abgetippt
  werden, hatte eine abgetippte Toleranz. Die Zahlen in den Zeichnungen kommen
  jetzt aus den Profilen — dasselbe galt für Elefantenfuß und Wandstärke.
* **Ein Körper aus achtundzwanzig Dreiecken ist ohne Kantenlinien ein grauer
  Fleck.** Die Projektion zeichnet jetzt Feature- und Silhouettenkanten und
  lässt abgewandte Flächen weg; das halbiert nebenbei die Dateigröße. Dazu ein
  Aufheller von hinten, sonst läuft jede abgewandte Fläche ins Schwarze.
* **Der feste Dreiviertelwinkel verdeckt bei einer Mutternfalle das Sechskant.**
  Die Kamera steht jetzt je Abbildung.
* **`QT_QPA_PLATFORM=offscreen` hat auf dieser Maschine null Schriftfamilien.**
  Jede Prüfung an einem Bild und jede Aufnahme läuft deshalb unter der echten
  Plattform. Unter `offscreen` wären alle Beschriftungen leere Kästchen —
  einmal fast übersehen, weil die Bilder als Bilder plausibel aussahen.
* **`QWidget.grab` erfasst keinen OpenGL-Inhalt.** Das Hauptfenster kam zweimal
  mit schwarzer Bildmitte zurück, bis es über den Bildschirm gegriffen wurde.
* **Im PDF passte das ganze Handbuch auf zwei Seiten.** `QTextDocument` rechnet
  in Pixeln; bei 1200 dpi ist eine Zwölf-Pixel-Schrift auf A4 ein Staubkorn.
  Bei 96 dpi sind es achtundzwanzig Seiten. Und weil `QTextDocument` kein
  `max-width` kennt, stand jedes Bildschirmfoto zur Hälfte außerhalb der Seite.
* **Beide Sprachen schrieben in denselben Bilderordner.** Der englische Lauf
  überschrieb die deutschen Zeichnungen, und die deutsche Seite zeigte
  englische Bilder.
* **Die Anker des Inhaltsverzeichnisses griffen ins Leere**, weil
  `core.markup` Überschriften eine Stufe nach unten rückt. Ein Test hat es
  gefunden, kein Auge — im Browser sieht ein toter Anker aus wie ein lebender.

Beim Aufnehmen des Bildes vom Prüfbericht fiel auf, dass über vier Befunden
„Keine Befunde" stand: gezählt wurde nur, was aus der Auswertung kam, nicht was
über `add_findings` dazukam. Behoben — gezählt wird jetzt, was in der Liste
steht. Ein Bild von der eigenen Oberfläche zwingt dazu, sie anzusehen.

**Offen: die Orientierungssuche reißt ihr Budget.** `orient_200` braucht auf
dieser Maschine 23,6 s, das Ziel aus §31 sind 20 s; zwei Läufe hintereinander
lieferten 23606 und 23654 ms, es ist also kein Rauschen. Der Docstring des
Tests nennt „etwa 16" — der Wert wurde einmal erreicht und gilt nicht mehr.
Betroffen ist `core/slice/orientation.py`, zuletzt inhaltlich geändert in
a8c6565; dazwischen liegt nur die Übersetzungsrunde, die keine Laufzeit kostet.
Nicht in derselben Runde angefasst: das ist Profiling-Arbeit an der
Orientierungssuche und gehört nicht ins Handbuch.

---

## Aus der Übersetzungsrunde

`app/`, `tests/` und `tools/` sind vollständig auf deutsche Docstrings und
Kommentare umgestellt — 2224 Bausteine, in Paketen committet. Der Nachsatz aus
`AGENTS.md`, es werde nur übersetzt, was ohnehin angefasst wird, ist damit
erledigt und dort gestrichen.

**Die Sprachregel stand an elf Stellen falsch.** Bauplan §4.1, der
Sitzungsstart-Hook und neun Agentenbeschreibungen sagten weiter „Docstrings und
Kommentare englisch" — zwei Sitzungen lang, während genau das Gegenteil
geschah. Alle nachgezogen. Der Bauplan war die gefährlichste davon: er ist die
Instanz, die bei Widerspruch gewinnt, hätte die Arbeit also formal für falsch
erklärt. Die Zeile über Commit-Nachrichten stand aus demselben Grund falsch —
sie sind seit dem ersten Commit deutsch.

**`ruff` und `mypy` fangen keine ungültige Escape-Sequenz.** Beim Übersetzen
von `export/writer.py` wurde aus `` ``\\w`` `` im Docstring ein `` ``\w`` ``.
Beide Werkzeuge liefen grün darüber; vier Tests fielen um, weil sie die Datei
mit `ast.parse` lesen und `filterwarnings = ["error"]` aus der SyntaxWarning
einen Fehler macht. Ein grünes `ruff check` heißt nicht, dass die Datei
fehlerfrei parst.

**Docstrings werden über die AST-Position ersetzt, nicht über Textsuche.** Der
Wortlaut wiederholt sich zu oft; adressiert wird über Funktions- und
Klassennamen, und bei einem Namen, den es zweimal gibt, bricht das Werkzeug ab,
statt zu raten. Die Einrückung braucht keine Sorgfalt — `ruff format`
normalisiert Docstrings ohnehin.

---

## Durchsicht: Politur, die man auf jedem Bild sieht

Anlass war die Frage nach Bedienfreundlichkeit, Logik und dem Stand gegen die
Mitbewerber. Der Befund zur Sache: die Alleinstellung — verstehen, beraten,
anpassen, übergeben in einem Programm — trägt; gegen Tinkercad zählt die
Druckintelligenz, gegen Fusion und FreeCAD die Druckfrage, die dort niemand
beantwortet, gegen die Text-to-CAD-Dienste die eine rücknehmbare Transaktion
je Vorschlag und der Betrieb ohne Cloud. Die zwei echten Lücken sind bekannt
und bleiben es: Skizzeneditor (P13) und Live-Vorschau im Op-Dialog (eigene
Phase). Was die Durchsicht fand, war Politur — sechs Funde, alle behoben:

- [x] **Auf jedem zweiten Dialog stand „Cancel".** Qt beschriftet seine
      Standardknöpfe selbst, und niemand hatte den qtbase-Katalog geladen —
      der Sprachtest sah es nicht, weil es keine eigene Zeichenkette ist.
      Geprüft wird jetzt am echten Artefakt, einer QDialogButtonBox
- [x] **Der Prüfbericht schnitt seine Sätze mitten im Wort ab** — genau die
      Sätze, für die §2.7 geschrieben wurde, hinter einer horizontalen
      Bildlaufleiste. Jetzt Umbruch statt Abschneiden
- [x] **„OK" sagte nicht, was es tut.** Der Bestätigen-Knopf jedes
      Operationsdialogs heißt jetzt wie die Operation — „Bohrung setzen"
      statt „OK", aus dem Register, also übersetzt
- [x] **Der Katalog zeigte zweieinhalb von dreizehn Bausteinen.** Jetzt ein
      Kachelraster; die Gruppenüberschrift nimmt die ganze Zeile, die
      Pfeiltasten laufen in beide Richtungen
- [x] **Das Handbuch war vom Startbildschirm aus unsichtbar** — 25 Seiten
      für die ersten fünfzehn Minuten, erreichbar nur über das Hilfemenü
      eines Fensters, das ein neuer Nutzer noch nie gesehen hat
- [x] **Die Handbuchbilder zeigten die Oberfläche von vor der Bedienrunde**
      — Siebzehn-Menü-Leiste mit Überlauf, ausgegraute Gruppen. Neu
      aufgenommen; `make_figures` wechselt jetzt auch Qts Knopfsprache mit,
      und wer die Oberfläche sichtbar ändert, nimmt die Bilder neu auf

## Die zweite Bedienrunde — was das Fenster versprach und nicht hielt

Anlass wie bei der ersten: die Frage nach Bedienfreundlichkeit, Logik und dem
Stand gegen die Mitbewerber. Die erste Runde hat die Struktur gerichtet, diese
fand die Versprechen, die noch offen waren — das größte stand sogar gedruckt
im eigenen Handbuch. Acht Funde, alle behoben:

* **„Datei → Exportieren" gab es nicht.** Das Handbuch beschreibt den Schritt
  wörtlich („*Datei → Exportieren*, dann 3MF…"), jeder der drei Hauptwege aus
  §2.2 endet mit ihm — aber der Schreiber aus §29 stand seit P2 im Kern, und
  der einzige Weg des Fensters zu einer Datei führte über einen installierten
  Slicer (Strg+P). Dieselbe Lücke hatte die Kommandozeile, bis der Eiffelturm
  sie fand. Jetzt: *Exportieren …* (Strg+E) — die Auswahl oder alles, ein 3MF
  als **eine** Baugruppe (§20), sonst eine Datei je Körper nach dem
  Namensschema; die Prüfung davor meldet in den Prüfbericht (§29).
* **Einen Parameter anlegen konnte nur der Agent.** §2.3 verspricht, dass
  ohne KI alles außer dem Chat funktioniert — Weg 2 lebt von benannten Maßen,
  und wer keinen Schlüssel hatte, konnte keines vergeben. Jetzt: Knopf in der
  Leiste, Eintrag unter *Bearbeiten*, Dialog mit Inline-Prüfung (Name,
  Grammatik, Zyklen — §13); die Änderung reist als `DocumentChange`, ein Undo
  entfernt den Parameter statt ihn zu nullen. Der leere Zustand der Leiste
  sagt jetzt außerdem, wozu sie da ist.
* **Auto Split rechnete im Hauptthread**, mit Wartezeiger — die
  Trennebenensuche schneidet jede Kandidatenebene durch das ganze Netz und
  braucht an einem großen Körper Minuten. `apply_split` ist in Suche und
  Anwendung geteilt; die Suche läuft im Arbeiter mit endlosem Balken und
  Abbrechen (das Ergebnis wird verworfen, wie beim Agentenzug), das Anwenden
  bleibt im Thread des Dokuments.
* **Drei Einträge waren modale Sackgassen auf leerer Szene.** *Automatisch
  teilen*, *Varianten erzeugen* und der neue Export folgen jetzt derselben
  Regel wie die siebzig Operationseinträge: ausgegraut, solange ihnen fehlt,
  was sie brauchen.
* **Die Update-Prüfung blockierte den Start.** Ihr Docstring sagte „niemand
  wartet auf sie" — das Fenster wartete bis zu vier Sekunden auf einen
  Server, dessen Adresse bis heute ein Platzhalter ist. Jetzt ein Arbeiter.
* **Schließen während der Schichtanalyse war ein Absturz beim Beenden.**
  `closeEvent` wartete auf den Karten-Arbeiter, nicht auf den
  Schicht-Arbeiter; `wait_for_idle` kannte den Split-Arbeiter nicht. Beide
  Lücken zu.
* **Der Prüfbericht wollte einen Doppelklick.** §18.4 sagt „Klick auf eine
  Warnung fährt die Kamera hin", `itemActivated` heißt aber Doppelklick oder
  Eingabetaste. Der Einfachklick tut es jetzt auch.
* **Im Katalog stand noch „OK".** Der Politur-Fund („OK sagt nicht, was es
  tut") war in jedem Operationsdialog behoben und im Bausteinkatalog nicht —
  der Knopf heißt jetzt *Einfügen*.

Der Befund zur Lage bleibt der der ersten Runde: die Alleinstellung —
verstehen, beraten, anpassen, übergeben in einem Programm, ohne Cloud, jeder
Vorschlag eine rücknehmbare Transaktion — trägt. Die zwei bekannten Lücken
(Skizzeneditor P13, Live-Vorschau im Op-Dialog) bleiben die zwei bekannten
Lücken. Die Handbuchbilder sind nach dieser Runde neu aufzunehmen — Menüs,
Parameterleiste und Katalog haben sich sichtbar geändert.

## Die zwei bekannten Lücken sind zu

Beide Runden nannten dieselben zwei Lücken gegen Fusion und Shapr3D — jetzt
sind sie gebaut, und beide auf den Wegen, die schon dalagen:

* **Die Live-Vorschau im Operationsdialog** ist dieselbe Differenzansicht
  wie beim Agentenvorschlag, nur früher: `preview_scene` verallgemeinert
  die Vorschau-Rechnung des Agenten (Kopie, Entwurfsqualität, Cache trägt
  die alten Schritte), `valuesChanged` am erzeugten Dialog entprellt auf
  300 ms, und die erste Vorschau läuft beim Öffnen — die Vorgaben sind
  schon eine Aussage. Auch das Wiederöffnen im Verlauf zeigt live, als
  geänderte Operation gerechnet, nicht als neuer Schritt (§15.4). Eine
  angehaltene Kette zeigt nichts statt einer leeren Differenz — die sähe
  aus wie „keine Änderung", und das wäre gelogen. Rückfragen stellt die
  Vorschau nie: was eine Antwort braucht, bekommt sie beim Anwenden.
* **Der grafische Skizzeneditor** (§30.1 Stufe zwei) zeichnet Punkt,
  Linie, Kreis und Bogen, fängt auf vorhandene Punkte (der Fang wird eine
  Deckungs-Bedingung, keine kopierte Zahl), setzt alle neun Bedingungen
  über Werkzeugleiste **und** Kontextmenü — angeboten nur, was zur
  Auswahl passt —, und Maße sind Ausdrücke der Grammatik mit
  Inline-Prüfung. Der Solver läuft nach jedem Schritt: die
  Freiheitsgrade stehen live in der Statuszeile, ein Konflikt nennt sein
  Paar und lässt die letzte gültige Lage stehen (§15.3). Grundformen
  kommen aus `shapes` mit verschobenen Zielen. Der Editor liest und
  schreibt den Text der Skizzen-Ops — es gibt keinen zweiten
  Skizzenbegriff, `change_params` und der Cache gelten unverändert.

**Zwei Funde nebenbei, beide älter als diese Runde:**

* **Das Handbuch behauptete „kein CAD-Ersatz — es gibt keine Skizzen und
  keine Zwangsbedingungen."** Seit P13 falsch, und der Launch soll die
  Skizzen als Kernargument führen. Die Seite sagt jetzt, was da ist.
* **Ein ersetzter Arbeiter wurde dem Speicherbereiniger überlassen.**
  „Eine neuere Anfrage ersetzt die wartende" hieß bei Analysekarte und
  Schichtanalyse: die Referenz überschreiben — und ein laufender QThread
  ohne Referenz wird mitsamt C++-Objekt zerstört. Das ist der Absturz
  ohne Zeile, der die Suite heute zweimal sporadisch riss
  (`Windows fatal exception: access violation`, „Garbage-collecting").
  Ersetzte Arbeiter bleiben jetzt referenziert, bis sie ausgelaufen sind
  (`_retire`, `_previews`-Pool), und ein Stresstest hält das Muster fest.

## Der erste echte CI-Lauf

Am 02.08.2026 ging das Repository auf GitHub (privat, `RS-Digital-Studio/
Solidon`), und die CI lief zum ersten Mal wirklich — mit vier Funden, von
denen keiner auf dieser Maschine sichtbar war:

* **Ein frisches Environment zieht trimesh 5.0.0**, und der Major-Sprung
  riss mypy (die neuen Annotationen geben für `concatenate` den Obertyp
  `Geometry`) und mehrere Tests. Die Engführung auf `Trimesh` lebt jetzt an
  einer Stelle (`mesh.concatenated`); trimesh ist unter 5 gepinnt.
  **Offen: die trimesh-5-Migration als eigener Durchgang** — venv anheben,
  Suite durchmessen, dann den Pin lösen. Nicht nebenbei machen: der erste
  Lauf zeigte auf Windows drei zusätzliche rote Tests und eine abgerissene
  pytest-Ausgabe.
* **„C:/…" ist auf POSIX ein Ordnername.** Die Absolutpfad-Prüfung der
  Projektdatei (Regel 12) urteilte mit dem Plattform-`Path` und ließ
  Laufwerkspfade auf dem Mac durch — und `..\` mit Backslash gleich mit.
  Jetzt urteilt `PureWindowsPath` über beide Konventionen, die Fälle sind
  Testfälle.
* **Die Runner haben kein libEGL.** PySide6 lädt es auch offscreen; ein
  apt-Schritt stellt die Qt-Systembibliotheken in beiden Jobs bereit.
* **Die Leistungstests messen auf geteilten Runnern nur Streuung.** §31
  meint eine Referenzmaschine; die CI läuft `-m "not performance"`, das
  Budget prüft der lokale Lauf.

## Die Beispiele wurden Touren

Der Anlass war ein Satz aus der Neulingsperspektive: „Ich wüsste nicht, was
ich machen soll." §37.2 nennt die Beispiele Doku — sie waren aber fertige
Projekte: das Ergebnis sichtbar, der Auftrag unsichtbar, und alles Wissen
über das Warum steckte in Docstrings von `tools/make_examples.py`, wo kein
Nutzer je liest.

Jetzt öffnet sich jedes der sieben Beispiele mit einer Tour im rechten
Bereich (dritter Reiter neben Prüfbericht und Chat): Schritt für Schritt,
und die Tour erkennt am Dokument und am Verlauf, wann ein Schritt getan
ist — Durchmesser gedreht, Strg+Z, Strg+Y, Baustein gesetzt. Undo und Redo
sind damit das Lehrmittel, nicht nur ein Menüeintrag. Drei Entscheidungen
dabei:

* **Ein Angebot, keine Sperre.** „Weiter" schaltet jeden Schritt auch ohne
  Erkennung, „Tour beenden" steht immer daneben (Regel 19). Erledigt trägt
  einen Haken, der aktuelle Schritt Pfeil und Fettschrift (Regel 18).
* **Die Schritte leben im Kern** (`app/core/tour.py`, ohne Qt), die
  Erkennung ist eine Funktion auf Dokument und Verlauf. `tests/test_tour.py`
  spielt jede Tour als Drehbuch durch — driftet sie gegen
  `tools/make_examples.py`, wird genau das rot.
* **Der Warnungssprung zum Prüfbericht lässt der aktiven Tour den Reiter.**
  Sonst risse die Anleitung genau dann ab, wenn das Beispiel planmäßig
  Befunde erzeugt (Weg 1: die Reparatur).

**Die neuen Tests fanden einen alten Absturz.** Die Suite riss sporadisch
Tests *nach* den Tour-Tests ohne eine Zeile Traceback ab (Exit 127, kein
Faulthandler-Dump). Eingekreist über Wegwerf-Sonden mit Etappenmeldungen:
`Session._on_thread_done` läuft als Slot des `finished`-Signals seines
eigenen Arbeiters und überschrieb dort die letzte Referenz — der
PySide-Wrapper starb mitsamt C++-QThread, während Qt die Zustellung noch auf
dem Stapel hatte. Ausgelöst hat es erst die Tour: ihre Tests fahren schnelle
Ketten (ändern, Undo, Redo) auf einem schweren Dokument, jede davon ersetzt
einen laufenden Arbeiter. Der Fix hält den ausgelaufenen Arbeiter fest, bis
ihn der nächste ablöst — dasselbe Muster wie `_retired` im Hauptfenster.
Sechzehn Läufe des vorher zu etwa der Hälfte roten Testpaars sind seither
grün. **Anzusehen bleibt:** `_on_agent_done` und der Split-Arbeiter lassen
ihre Referenz genauso los; dort hämmert nur niemand.

Nebenbefund, behoben: die Transaktionstitel der Beispiele („Bohrung setzen",
„Anordnen") standen als deutsche Zeichenketten in den Projektdateien und
blieben auch in der englischen Oberfläche deutsch — die englischen Tourtexte
zitierten sie deshalb deutsch. Jetzt reist ein Titel aus dem Code als
Message-ID (Formatversion 6, `title_translatable`) und löst sich erst bei
der Anzeige auf; was ein Nutzer selbst benannt hat, bleibt wörtlich, und
ältere Dateien bleiben es auch — welcher alte Titel aus dem Code kam, steht
nirgends, ein Katalogabgleich wäre geraten. Die Beispiele sind neu gebaut,
die englischen Tourtexte zitieren die englischen Titel („Drill a bore",
„Arrange"), und die Extraktion sammelt die Titel der Beispiel-Bauer über
`EXTRA_SOURCES` mit ein. Im zweiten Durchgang vergibt auch die Oberfläche
ihre Titel über `_()` („Direkt bewegt", „Bemalen", „Modell laden", „STEP
laden", „Zeichnung extrudieren", „Drucker und Material") — nur die
zusammengesetzten Parameter-Titel (`Parameter {name}`) bleiben wörtlich:
eine Message-ID kennt keine Platzhalter, und der Nutzername im Titel gehört
ohnehin nicht übersetzt.

## Ein frischer Klon war rot, ohne dass sich Code geändert hatte

Ein am 2026-08-06 neu geklontes Arbeitsverzeichnis, Umgebung frisch aufgebaut:
**16 Tests rot, `mypy` gar nicht erst durchgelaufen** — bei einem Stand, der
auf der Maschine daneben grün war. Kein Fehler lag im eigenen Code.

Die Ursache ist eine einzige. Alle Abhängigkeiten in `pyproject.toml` haben
offene Untergrenzen, also zog `pip` überall das Neueste; **numpy 2.5 hat
`arr.shape = ...` als veraltet markiert**, VTK 9.6 und scikit-image 0.26
benutzen es noch, und `filterwarnings = ["error"]` macht aus jeder solchen
Warnung einen Fehler. Zwölf Tests fielen direkt darüber.

**Die Voxelstufe der Booleschen Kette fiel als Folgeschaden komplett aus.**
`trimesh.voxel.ops` ruft `skimage.marching_cubes`, dort löste dieselbe Warnung
aus, damit war Stufe 4 tot — und weil die Kette danach zu Ende ist, kam
`BooleanFailedError` heraus: „auf allen Stufen gescheitert" für eine Operation,
an der nichts falsch war. Vier Tests, alle mit `voxel` im Namen.

**Der `mypy`-Abbruch traf auch die CI, unabhängig von dieser Maschine.**
`numpy/__init__.pyi` benutzt die `type`-Anweisung (PEP 695), und geprüft wurde
gegen Zielversion 3.11 — Abbruch mit `errors prevented further checking`, also
keine einzige Projektdatei geprüft. `python_version` ist die Zielversion der
Prüfung, nicht der Interpreter; der CI-Lauf auf 3.11 landet im gleichen
Abbruch. Das Tor war vermutlich rot, seit numpy 2.5 erschien.

**Was den Sprung überlebt hat, ist die eigentliche Nachricht.** manifold3d
ging von 2.5 auf 3.5.2 — der Geometriekern, zwei Hauptversionen — ohne eine
einzige Beanstandung. Ebenso `pytest` 8→9, `ruff` 0.6→0.16 (zehn Nebenversionen
ohne neue Regelverstöße), `PySide6` 6.7→6.11, `lxml` 5→6, `svg.path` 6→7. Und
`mypy` 2.3 mit `strict = true` und den neuen strengeren Vorgaben
(`local-partial-types`, `strict-bytes`) findet in 184 Dateien nichts.

### Was daraus wurde

* **Python-Untergrenze auf 3.13**, an allen sieben Stellen zugleich:
  `requires-python`, `ruff target-version`, `mypy python_version`, beide
  CI-Jobs, `CLAUDE.md` und der Sitzungsstart-Hook. Das löst den Stub-Konflikt
  an der Wurzel, statt numpy zu deckeln — eine Obergrenze hätte das Projekt
  auf einer alten Version festgehalten.
* **Die Fremdwarnung eng ausgeklammert**, auf `vtkmodules.*` und `skimage.*`
  begrenzt und mit Entfernungsbedingung kommentiert. Der eigene Kern kommt
  ohne die Zuweisung aus, geprüft — es wird also nichts Eigenes verdeckt.
* **`constraints.txt`**, der Versionssatz, gegen den die Suite grün ist. Suite
  und Paketierung bauen dagegen, ebenso der Erstaufbau in `README.md` und
  `CLAUDE.md`. Ohne ihn installiert jeder Klon etwas anderes, und genau das
  ist hier passiert.
* **Ein wöchentlicher CI-Job „Neueste Versionen"** löst bewusst ohne
  Constraints auf und protokolliert, was er installiert. Wird er rot, während
  die Suite grün bleibt, liegt es an einer neuen Version — die Frühwarnung, die
  hier gefehlt hat. Nur Ubuntu, nur montags: private Minuten sind gezählt.
* Nebenprodukt der Zielversion: `ruff` verlangte mit `py313` drei
  Umschreibungen auf PEP-695-Generics (`op_params`, `validate`, `_by_title`).
  Die modulweiten `TypeVar` und ihre Importe sind damit weg.

### Anzusehen

**manifold3d 3.x bringt vier Dinge, die auf offene Stellen hier passen.** Der
Kern läuft schon darauf, benutzt wird davon noch nichts:

* `ExecutionContext` (3.5) trägt Fortschritt und Abbruch **in** die Boolesche
  Operation. Heute reicht `app/core/geom/` `ctx.cancelled` an genau einer
  Stelle weiter (`prepare_ops.py:725`) — eine laufende Boolesche Op ist nicht
  abbrechbar, obwohl §2.8 das verlangt.
* Plattformübergreifend deterministisches Rechnen in doppelter Genauigkeit
  (3.5) — trifft Regel 6 und die Determinismus-Testart, bei Windows, macOS und
  Linux-Runnern im Spiel.
* Strahlschnitt über Kernel12 (3.5) — genau der Bereich der letzten Funde zum
  Anklicken von Flächen.
* `MinkowskiSum`/`MinkowskiDifference` (3.4) — echte Offsets für Passungsspiel
  und Dichtnuten, statt sie nachzubauen. Die Release-Notiz warnt selbst: bei
  komplexen Netzen langsam und speicherhungrig.

**`MeshIO` ist in manifold3d 3.4 aus der öffentlichen API verschwunden**;
Netz-Ein-/Ausgabe soll über trimesh laufen. Hier unkritisch, sonst wären die
Geometrietests nicht grün — aber es ist eine Stelle, die bei einer künftigen
Umstellung zu prüfen ist.

**trimesh 5.0 ist am 2026-08-01 erschienen** und bleibt gepinnt (`<5`). Der
Sprung ist weiter eine eigene Migration, und die Voxelkette über
`trimesh.voxel.ops` ist gerade die empfindlichste Stelle daran.

## Live gegen Fusion und den ElegooSlicer

Am 05.08.2026 lief die Anwendung gegen die beiden Programme, die auf dieser
Maschine tatsächlich neben ihr stehen: **Autodesk Fusion 2704.1.36** als Maßstab
fürs Konstruieren, **ElegooSlicer 1.5.3.4** als Empfänger des Ergebnisses.
Fünfzehn Funde, alle gemessen; das Konzept mit Zahlen, Ursachen und Reihenfolge
steht in `konzepte/konzept-live-durchsicht-2026-08.md`.

**Drei Dinge tragen besser, als das Repository sie darstellt.** Der STEP-Weg ist
in beide Richtungen bitgenau — Volumen und Fläche stimmen auf fünfzehn Stellen
mit Fusion überein, die Bohrung im zurückgeladenen Fusion-Körper wird erkannt.
Die Slicer-Übergabe meldet gegen 1.5.3.4 — eine Version neuer als die, gegen die
die Tabelle gebaut wurde — **null** übergangene Einstellungen; die Profilzuordnung
trifft ohne Zutun aus 9849 gelesenen Profilen. Und der ganze Weg läuft aus dem
Fenster heraus: Strg+P, Slicen, 0,8 Sekunden, Druckdatei.

**Was zu tun war**, nach Gewicht — abgearbeitet in den drei Paketen darunter,
mit Ausnahme der fehlenden Passung:

- [x] **Der Hüllquader eines exakten Körpers kommt aus seinen Dreiecken.**
      `Solid.bounds` gibt `mesh.bounds` zurück; der Fehler ist konstant 0,025 mm
      (halbe `DEFLECTION`), bei Ø 6 wie bei Ø 120. Fusion misst denselben Körper
      mit 25,00 mm Radius, Solidon mit 24,9755. Daran hängen Maßanzeige,
      Bauraumprüfung, Anordnung, Haftungsrand, `advise.for_part` und jede
      Passungsprüfung — ein Zehntel der Materialtoleranz, verloren vor dem ersten
      Druck. Fix: `BRepBndLib` statt Tessellation
- [x] **Die angeklickte Fläche ist die Mitte des Werkzeugs, nicht sein Anfang.**
      Klick auf eine 20-mm-Platte, Bohrung Tiefe 10 → 5 mm tief; Tiefe 0 („bohrt
      durch") → 10 mm und **kein Durchbruch**; Magnettasche → gar nichts. In
      Fusion ist der Klickpunkt die Mündung. Eigene Runde mit Formatversion und
      Migration, sie ändert bestehende Dateien
- [x] **Eine Operation, die nichts abgetragen hat, schweigt.** Die Magnettasche
      neben dem Körper erzeugt keinen Befund, keine Ausnahme, keinen Hinweis —
      unterhalb dessen, was Regel 17 überhaupt erfasst. Volumen vorher/nachher
      vergleichen, sonst Befund mit Vorschlag
- [x] **Solidons Anordnung erreicht den Slicer nicht.** Zwei Läufe, einmal in
      Modell- und einmal in Bettkoordinaten, ergeben denselben G-Code — der
      Slicer ordnet neu an. Mit `--arrange 0` und Bettkoordinaten kommt die
      Anordnung auf ein Zehntel an. Damit ist die ganze Plattenlogik für den
      Slicer-Weg heute folgenlos, und der offene Punkt zum Haftungsrand hätte
      einen Abstand berechnet, der nie ankommt
- [x] **`filament_cost = 0` überschreibt die 30 €/kg des Herstellers.** „0 heißt
      unbekannt, nicht kostenlos" steht im eigenen Docstring — geschrieben wird
      es trotzdem. Systematisch geprüft: der einzige Fall dieser Art
- [x] **Keine Operation legt eine Passung an.** `create_lid` baute den Deckel mit
      0,25 mm Spiel aus dem Materialprofil und trug keinen `Fit` ein; damit
      griffen genaue Außenwand, gebremste Beschleunigung und Bügeln nie. Der
      Deckelablauf legt sie jetzt an (`core/lid_flow.py`), über ein `fits`-Feld
      an `OpResult` — nachgetragen und nicht mitgegeben, weil erst der Verlauf
      die Objekt-IDs vergibt
- [x] **Die Gegenprobe vergleicht nur das Stützvolumen.** Live: 12 g / 46 min
      geschätzt gegen 10,0 g / 37 min gemessen — −17 % und −20 %, und kein Wort
      im Prüfbericht. `gcode.compare` kennt die 15-%-Schwelle und wird an genau
      einer Stelle gerufen
- [x] **`arrange_bed` ohne Eingaben hält die Auswertung an**, statt nichts zu
      tun. Der Test dazu prüft die Positionen und nicht `result.complete` — und
      deckt den Abbruch damit zu
- [x] **Im Viewport lässt sich nichts anklicken.** Links wählt nichts aus, rechts
      öffnet kein Menü; Rad und Rechtsziehen bewegen die Kamera. Ursache:
      gepickt wird mit `vtkPointPicker`, und der trifft Eckpunkte, keine Flächen.
      Daran hängen Auswahl, Kontextmenü am Merkmal (§18.5), Messen, Bemalen und
      die Flächenübernahme in Dialoge
- [x] **Ein Zylinder trägt einundfünfzig Flächenmerkmale**, in Fusion sind es
      drei. Facetten gehören zusammengefasst, bevor IDs vergeben werden — mit
      dem Zuordnungstest zusammen, nicht nebenbei
- [x] **Ein Rundstab meldet sich als Bohrung.** `brep/features.py` macht aus
      jeder geschlossenen Zylinderfläche ein `hole`, ohne die Materialseite zu
      prüfen. `boss` gehört zuerst in Bauplan §4.2
- [x] **Die Skizzenleiste liegt unter den Bereichen links und rechts** — verdeckt
      sind die *ersten* Werkzeuge, also Linie und Rechteck. Kein Platzproblem:
      bei 1296 wie bei 1900 Pixel. Die Kürzel selbst stimmen, `R` zeichnet ein
      Rechteck und die Skizze meldet sich als bestimmt
- [x] **Der Ersteinrichtungsdialog fragt den gefundenen Slicer nicht.** Er meldet
      „Slicer gefunden" und schlägt im selben Fenster den allgemeinen 220er und
      PLA vor, während der Profilbestand den Centauri Carbon 2 kennt
- [x] **Der Objektname reist nicht ins STEP** — in Fusion heißt das Teil
      „Körper1". Fürs 3MF war das schon einmal ein Fund und ist behoben
- [x] **Von der Aushöhlung zum Deckel fehlt ein Schritt.** `hollow_object`
      schließt den Hohlraum, `create_lid` verlangt eine Öffnung; der Weg zur Dose
      führt über zwei Zylinder und eine Differenz

## Paket 2 der Durchsicht: die Platte kommt an

Aus dem Konzept zur Live-Durchsicht war das der zweite Satz Arbeiten — und der
mit der unangenehmsten Voraussetzung: bevor irgendetwas an der Anordnung
verbessert werden konnte, musste sie den Slicer überhaupt erreichen.

**Sie erreichte ihn nicht.** Zwei Läufe derselben Szene, einmal in Modell- und
einmal in Bettkoordinaten, ergaben denselben G-Code — die Orca-Familie ordnet
in der Vorgabe immer neu an. Damit war alles folgenlos, was Solidon über die
Platte weiß: `arrange_bed`, der Haftungsrand aus `check_adhesion_clearance`,
`plates_by_material`, die Plattennummer am Objekt.

Drei Teile, alle am installierten ElegooSlicer 1.5.3.4 gemessen:

- [x] **Die Platzierung reist im 3MF mit.** Über die Matrix am `<item>` des
      Standards, nicht über die Punkte: die Geometrie in der Datei bleibt die
      des Dokuments, und wer sie als Modell liest, bekommt das Modell. Dass
      Orca diese Matrix wirklich liest, ist gemessen — mit ihr und
      `--arrange 0` stehen drei Teile im G-Code auf **0,00 mm** genau dort, wo
      das Dokument sie hat. Der verbleibende Versatz von 1,5 mm in Y ist der
      `extruder_offset` der Maschine, den der Slicer selbst einrechnet.
- [x] **`--arrange 0`, aber nur wenn die Anordnung eine ist.**
      `writer.arrangement_holds` prüft in der Aufsicht: kein Teil über einem
      anderen, keines außerhalb des Betts. Sonst bleibt es beim Anordnen des
      Slicers — zwei Teile übereinander wären schlimmer als eine verworfene
      Anordnung. Getragen wird die Entscheidung durch bis zum Aufruf, und die
      Datei bekommt ihre Platzierung nur dann.
- [x] **Der Abstand kennt die Haftung.** Der Dialog des Anordnens öffnet mit
      dem doppelten Haftungsrand als Abstand, wenn der größer ist als die
      Vorgabe der Operation.

Dazu zwei Funde, die auf dem Weg lagen:

- [x] **`arrange_bed` ohne Eingaben hielt die ganze Auswertung an.** Der Stapel
      plante einen Ausgang, die Operation lieferte ohne Eingaben keinen, und
      alles nach diesem Schritt wurde nicht mehr gerechnet. Der Test dazu
      verglich Positionen statt `result.complete` und deckte den Abbruch zu —
      eine abgebrochene Auswertung bewegt auch nichts.
- [x] **Die Platzierung gehört nicht in jede Datei.** Beim Export einer 3MF
      bleibt sie weg: ein von Hand geöffneter Slicer ordnet ohnehin neu an, und
      eine zurückgelesene Platte läge sonst um den halben Bauraum verschoben im
      nächsten Dokument. Zwei Zwecke, zwei Dateien — `place_on_bed` sagt welche.

## Paket 3 und 4 der Durchsicht — und die Bohrung, die daneben lag

Der Rest des Konzepts, in drei Runden. Paket 3 waren die Stellen, an denen
Solidon gegen Fusion nachweisbar falsch lag; Paket 4 die, an denen es zwar
rechnete, aber nichts sagte. A2 stand bewusst außerhalb, weil es als einzige
Änderung bestehende Projektdateien anders rechnen lässt.

- [x] **Der Hüllquader eines exakten Körpers kam aus den Dreiecken.** Der
      B-Rep-Kern hat einen Körper und meldete trotzdem die Ausdehnung seiner
      Vernetzung — konstant 0,025 mm zu groß gegen Fusion. `BRepBndLib`
      `AddOptimal_s` mit `SetGap(0)` fragt die Fläche selbst, und die
      Abweichung ist null.
- [x] **Eine Boolesche Operation ohne Wirkung meldet das.** Eine Magnettasche
      neben dem Teil war vorher nicht von einer im Teil zu unterscheiden:
      kein Fehler, kein Befund, ein Verlaufseintrag über nichts.
      `boolean.without_effect` vergleicht das Volumen und gibt eine Warnung
      zurück — Regel 17 verlangt einen Handlungsvorschlag, und der stille
      Fehlschlag stand darunter.
- [x] **Der Objektname reist ins STEP.** Fusion zeigte jeden Import als
      „Open CASCADE STEP translator". Der Name geht jetzt über
      `write.step.product.name` mit, gesetzt *vor* dem Transfer — danach
      gesetzt wirkt er nicht.
- [x] **Der Viewport traf, was angeklickt wurde.** Drei Ursachen
      hintereinander: pyvistas `enable_point_picking` scheiterte still an
      einem fehlenden `_parent`, ein `vtkPointPicker` trifft nur Eckpunkte,
      und ein Merkmal ohne vorher gewähltes Objekt hat niemanden. Jetzt ein
      `vtkCellPicker` im eigenen Interaktionsstil, Objekt vor Merkmal.
- [x] **Die Skizzenleiste lag unter den eingeklappten Bereichen.** Die
      Überlagerung kennt ihre Ränder und sagt sie dem Widget.
- [x] **Ein Rundstab war eine Bohrung.** Der B-Rep-Kern nannte jede
      zylindrische Fläche `hole`, auch die außen liegende. Die Orientierung
      der Fläche unterscheidet sie — `TopAbs_REVERSED` heißt hohl.
- [x] **Der Bericht schwieg über zwanzig Prozent.** Schätzung und G-Code
      liefen auseinander, ohne dass es jemand erfuhr; jetzt vergleicht
      `_compare_totals` Zeit und Material und meldet die Abweichung.
- [x] **Der Drucker kommt aus dem Slicer.** Beim ersten Start stand „Slicer
      gefunden" neben einem vorgeschlagenen 220er, während der Bestand des
      Slicers die eingestellte Maschine kannte.
- [x] **Die Position einer Bohrung ist ihre Mündung** (§25, Formatversion 7).
      `drill` legte den Zylinder mittig auf die Position — und ein Klick
      liefert eine Oberfläche. „Null bohrt durch das ganze Teil" tat das
      dadurch nicht. Der Parameter `anchor` unterscheidet `mouth` von
      `centre`; die Richtung ins Material folgt aus der Hälfte des
      Hüllquaders, damit auch eine von unten angeklickte Fläche stimmt.
      Migration 6 → 7 trägt alten Dateien `centre` ein, `drilled_v6.p3d`
      beweist an einem Volumen, dass sie weiter rechnen wie zuvor.
- [x] **Drei Bausteine bauten über ihrem Ursprung.** `magnet_pocket`,
      `keyhole` und `cable_gland` trugen an der angeklickten Fläche 0,0, 0,0
      und 0,2 mm³ ab. Die anderen dreizehn hielten die Konvention. Jetzt alle:
      Bibliotheksversion 2, Änderungseintrag `MOUTH_AT_ORIGIN`, und ein Test,
      der jeden abziehenden Baustein auf eine Platte setzt und misst, ob sie
      leichter wird.

- [x] **Ein Zylinder hatte einundfünfzig Flächen.** Jeder Mantelstreifen war
      3,4 Prozent der größten Fläche und galt damit als eben — die
      Zylindererkennung, die es längst gab, sah ihn nie. Die Trennlinie steht
      jetzt an der Naht zwischen zwei Dreiecken: koplanar ist dieselbe Fläche,
      ein deutlicher Knick eine Kante, alles unter dreißig Grad dazwischen eine
      Rundung. Zylinder mit Bohrung: vier Merkmale statt einundfünfzig, und ein
      Achteck-Prisma behält seine acht Seiten.
- [x] **Der Weg zur Dose war ein Umweg.** *Aushöhlen* endete immer bei einem
      geschlossenen Hohlraum, *Deckel erzeugen* verlangt eine Öffnung. Der
      Schalter „Oben öffnen" nimmt die Decke weg — das Werkzeug ist der oberste
      Querschnitt des Hohlraums, nach oben durchgezogen. Die Entlüftung
      entfällt dabei: eine offene Dose ist ihre eigene.

### Was die Arbeit gelehrt hat

**Eine Konvention, die nirgends geprüft wird, ist keine.** Dreizehn von
sechzehn Bausteinen bauten unter ihrem Ursprung, drei nicht — und niemand
konnte es sehen, weil kein Test die Wirkung maß, sondern nur Wasserdichtheit
und Wandstärke. Der neue Test prüft nichts Geometrisches, sondern eine
Erwartung: was Material wegnehmen soll, muss weniger Material hinterlassen.

**Eine Migration, die rechnen müsste, rechnet meistens falsch.** Die halbe
Tiefe auf die Position zu addieren hätte die Richtung ins Material gebraucht,
und die steckt in der Geometrie, nicht in der Datei. Ein Parameter, der die
alte Bedeutung festhält, ist ehrlicher als eine Umrechnung, die rät.

## Das Audit vom 06.08.2026 — und was unter dem Code lag

Anlass war eine Durchsicht der ganzen Anwendung. Der Befund zur Sache ist
kurz: der Code ist in Ordnung. Kein `eval`, kein `shell=True`, keine
GPL-Abhängigkeit, kein absoluter Pfad in einer Projektdatei, **kein einziges
TODO oder FIXME** in achtundfünfzigtausend Zeilen, Migrationen v1 bis v7
lückenlos mit eingecheckter Beispieldatei, keine feste Zeichenkette in der
Oberfläche. Vier von fünf Funden lagen deshalb nicht im Code, sondern
darunter.

- [x] **Die Umgebung fuhr Python 3.11, das Projekt verlangt 3.13.** Die `.venv`
      war am 27.07. mit 3.11.9 angelegt, `requires-python` stand längst auf
      3.13, und auf der Maschine gab es kein 3.13. Solange kein 3.12-Feature im
      Code stand, fiel das nicht auf; mit den ersten PEP-695-Typparametern
      (087e321) brach der Import der Anwendung, und damit starben pytest, mypy,
      die Kommandozeile und das Fenster. **`ruff` blieb grün** — es bringt einen
      eigenen Parser mit `target-version` mit und sieht den Interpreter nie an.
      3.13.14 installiert, Umgebung gegen `constraints.txt` neu aufgebaut; dabei
      kamen auch `pypdf` und die sechs Versionen nach, die von der Datei
      abwichen.
- [x] **Das Tor konnte still durchfallen.** `mypy` meldete „1 error ... errors
      prevented further checking" und prüfte dabei **null** Projektdateien —
      dieselbe Mechanik wie beim numpy-2.5-Vorfall zwei Tage zuvor, nur mit
      anderer Ursache. Zweimal in einer Woche, und nichts im Repository
      unterschied einen Abbruch von einem grünen Lauf.
      `tests/test_toolchain.py` prüft jetzt den laufenden Interpreter gegen
      `requires-python` und die Zielversionen von mypy und ruff gegen dieselbe
      Angabe. Danach: 190 Dateien geprüft statt keiner.
- [x] **Zwei Arbeiter räumten das Feld ihres Nachfolgers.** Das Muster stand
      fünfmal richtig im Haus — mit Kommentar, warum ein Lambda hier nicht geht
      — und zweimal falsch. Siehe Commit; die Regel steht jetzt in
      `.claude/rules/oberflaeche.md`, und ein Test sucht das falsche Muster im
      Quelltext der ganzen Oberfläche.
- [x] **Eine Webseite durfte am offenen Dokument arbeiten.** Bindung und
      Absenderadresse halten keinen Browser auf: der läuft auf diesem Rechner.
      `origin_allowed` kam dazu, die zweite Auflage heißt jetzt „dreimal
      geprüft".
- [x] **Die Zonen setzten sich gegenseitig, bis der Stapel überlief.** Fiel
      erst auf, als die Suite wieder lief — `tests/test_overlay.py` starb beim
      ersten Test, reproduzierbar. Kein reines Testartefakt: `resizeEvent` geht
      denselben Weg, und am Fensterrand zu ziehen ist derselbe Fall.

Stand danach: 2949 Tests grün, `ruff`, `ruff format` und `mypy` grün.

### Was das Audit gelernt hat

**Ein grüner Lauf sagt nur etwas, wenn er auf dem Richtigen lief.** Drei der
vier Werkzeuge des Tors sagten „in Ordnung", während zwei davon gar nichts
prüften und das dritte auf einer Interpreterversion lief, die das Projekt nicht
mehr unterstützt. Was das Tor über sich selbst behauptet, gehört genauso
geprüft wie das, was es über den Code behauptet.

**Eine Lehre, die nur an der Fundstelle gezogen wird, ist halb gezogen.** Der
Absturz durch die verlorene Arbeiter-Referenz war dreimal in `session.py`
behoben, einmal bei der Update-Abfrage, einmal bei der Analysekarte — jedes Mal
mit ausführlichem Kommentar. Zwei Stellen daneben machten weiter den alten
Fehler, und niemand konnte es sehen, weil nichts danach suchte. Dieselbe
Erkenntnis wie bei den drei Bausteinen über ihrem Ursprung, eine Etage höher.

- [x] **Zwei Anzeigen sprachen allein über Farbe** (Regel 18). In der
      Schichtanalyse lagen Insel und Überhang beide auf Strichstärke 3 — zwei
      gleich dicke Ringe übereinander, unterschieden allein durch die Farbe,
      und ausgerechnet bei den zwei Rollen, die eine Handlung nach sich ziehen.
      `LAYER_WIDTHS` gibt jeder ihre eigene Stärke, und die Schichtleiste trägt
      jetzt eine Legende, deren Strich so lang ist wie der Ring im Bild dick.
      Die Legende der Differenzansicht war ganz in der Farbe von „Hinzugefügt"
      gezeichnet — auch das Wort „Entfernt": eine Legende, die Farben erklären
      soll und beide gleich färbt, sagt das Falsche. Und die Schriftfarbe auf
      einem Farbfeld hing an einer festen Luminanzschwelle von 0,35, die über
      den mittleren Tönen von Viridis auf die schlechtere der beiden kippte
      (3,47 und 2,56); verglichen werden jetzt die zwei Kontraste.
- [x] **Objektbaum und Verlauf waren stumme Kästen**, und eine Suche ohne
      Treffer sagte an keiner der drei Stellen, dass nichts gefunden wurde. Ein
      neues Projekt beginnt in genau diesen Karten; die Parameterleiste daneben
      sagte seit jeher, wozu sie da ist. Befehlspalette und Bausteinkatalog
      nennen den Suchbegriff jetzt in einer nicht wählbaren Zeile, der
      Prüfbericht in einem Feld über der Liste — dort wird über `setHidden`
      gefiltert, ein Eintrag darin wäre beim nächsten Filtern im Weg.
- [x] **Kein ausgegrauter Menüeintrag nannte seinen Grund.** `_kind_hint` stieg
      sofort aus, wenn eine Operation kein `requires_kind` trägt — und das
      haben sieben von 84. Auf der leeren Szene stand damit bei jedem
      gesperrten Eintrag sein Beschreibungssatz: was er täte, wenn er könnte.
      Die Werkzeugzeile daneben sagte es im selben Augenblick richtig.
      `_reason_locked` nennt den Grund jetzt in der Reihenfolge, in der ein
      Nutzer ihn behebt: erst etwas in die Szene, dann etwas auswählen, dann
      die richtige Bauart. Ein Test vergleicht gegen den Beschreibungssatz —
      ein Hinweis, der ihm gleicht, ist keiner.
- [x] **Der Korrekturdialog verlor seine Klappe.** Wer eine Operation aus dem
      Verlauf öffnet, bekommt ihr ganzes Schema als Werte übergeben, und
      `entry.name in given` schob damit jedes Feld auf die Vorderseite — die
      gestufte Tiefe (§2.4) galt genau dann nicht, wenn jemand einen Wert
      nachbessern will. Nach vorn kommt jetzt, was vom Schema-Standard
      abweicht; Sammelwerte (Skizze, Striche, Skelett) bleiben hinten, was auch
      immer drinsteht.
- [x] **Der Knopf am gesperrten Chat führte in den falschen Dialog.** Er hieß
      „Zugang einrichten …" und öffnete die „Zusätzlichen Programme" — dort
      installiert man ein lokales Modell, trägt aber keinen Schlüssel ein. Der
      Dialog mit dem Schlüsselfeld heißt „Chat einrichten", steht im Menü unter
      genau diesem Namen und war vom Chat aus nicht erreichbar: einer der zwei
      Wege aus §27 fehlte. Knopf und Menüeintrag tragen jetzt wörtlich
      denselben Text und damit denselben Katalogeintrag.
- [x] **Eine Warnung erreichte niemanden mehr, sobald die rechte Spalte
      ausgeblendet war.** §2.5 nennt „Warnungen" für die Statusleiste, und dort
      standen sie nie; `_focus_report` steigt bei unsichtbarer Spalte zu Recht
      aus, und danach kam nichts. Der Zähler erscheint jetzt genau dann — bei
      offener Spalte trägt ihr Reiter die Zahl, und zwei Zähler wären einer zu
      viel — und ein Klick holt Spalte und Bericht zurück.
- [x] **„1 × warnings".** „Fehler", „Warnung" und „Hinweis" standen in allen
      fünf Katalogen im Plural, während die deutsche Quelle den Singular führt
      — nach dem Malzeichen steht er. Alle fünf sind gezogen.

- [x] **Was ein Bildschirmleser nicht las.** 44 von 102 fokussierbaren
      Elementen des Hauptfensters hatten keinen Namen — ein Feld ohne Namen
      wird als seine Art angesagt, „Eingabe", „Auswahl", „Schieber". Darunter
      die neun Beispielkacheln des Startbildschirms (das Erste, was jemand
      sieht: neun Mal „Rahmen"), die Wähler aller Leisten, jedes Suchfeld,
      jede Liste, der Schichtenregler. Jetzt trägt jedes bedienbare Element
      einen Namen; durch geht nur, was Qt selbst anlegt — die Aufklappliste
      eines Auswahlfelds trägt den Namen ihres Feldes, ein Reiterfeld wird
      über seine Reiter angesagt. Ein Test hält es bei null.
      Dazu zwei Nachbarn: Der Freischaltdialog war eine Tastenfalle — ein
      mehrzeiliges Feld nimmt den Tabulator als Zeichen, und wer ohne Maus
      arbeitet, kam aus dem Schlüsselfeld nicht mehr heraus. Und die
      Reiterleiste der rechten Spalte zeigte den Tastaturfokus mit null
      Bildpunkten Unterschied; sie bekommt eine gestrichelte Marke, denn der
      aktive Reiter trägt schon Akzentkante, Fläche und Fettschrift.

- [x] **Der Installationsdialog antwortete mit „Das hat nicht geklappt."** —
      und zeigte davor die rohe Befehlszeile und jede Zeile, die pip oder
      winget von sich geben, im Statuslabel. Wer das liest, weiß danach
      weniger als vorher. Der Kern gab bei einem Fehlschlag gar keinen Grund
      zurück, nur `installed=False`; er nennt jetzt einen, und zwar für alle
      drei Fälle — die Paketverwaltung ließ sich nicht starten, sie hat
      abgebrochen, oder sie meldete Erfolg und das Programm ist trotzdem nicht
      da. Der Rückgabewert steht bei den Einzelheiten statt im Satz: Dort
      gehört er hin, und ein Satz ohne Platzhalter übersetzt sich in fünf
      Sprachen leichter. Die rohe Ausgabe sammelt der Dialog und bietet sie
      hinter „Details anzeigen" an (§33.2).

- [x] **Zwei Sätze ohne Warum.** „Die Boolesche Operation ist
      fehlgeschlagen." stand noch in `profiles.py` — die zweite Stelle in
      `edit.py` war längst vorbildlich. Der Fall ist eng genug für einen
      richtigen Satz: Diese Verknüpfung fügt den Kern eines Gewindes mit
      seinem Gang zusammen, und was dort scheitert, scheitert an Flächen, die
      sich berühren statt zu überlappen. Der Ausweg ist ein anderes Maß, keine
      Reparatur — die gröbere Stufe versucht `_joined_rod` schon selbst.
      „Zwei Bedingungen widersprechen sich." nannte das Paar nicht, obwohl der
      Kern es seit jeher kennt und sogar anbietet, die eine oder die andere zu
      entfernen. Bei vierzehn Einträgen in der Liste durfte man suchen, welche
      zwei gemeint sind. Die Zeichenfläche merkt sich das Paar jetzt, und die
      Liste rechts schreibt beide an — mit einem Zeichen und nicht nur mit
      Farbe, denn eine Bedingungsliste wird auch ausgedruckt (Regel 18).
      Den Satz selbst baut die Oberfläche und nicht der Kern: Dort liegen die
      Beschriftungen, und der Kern führt seine Werte grundsätzlich über
      `values` statt über Platzhalter.

### Offen aus dem Audit

- [x] **Die englischen Docstrings sind übersetzt.** Es waren 56 in `app/`
      über 27 Dateien, dazu acht in `tests/` und `tools/` — fast alles
      einzeilige Attribut-Beschreibungen, die die Sprachprüfung nicht sieht,
      weil sie den Bezeichnern gilt. Erledigt in „Die letzten englischen
      Docstrings zogen nach" (5709245); der Suchlauf, der sie gefunden hat,
      findet jetzt nichts mehr.

## Durchsicht: was außerhalb der Anwendung läuft (07.08.2026)

Anlass war eine einfache Frage — läuft die Erzeugung, läuft der Chat? — gegen
eine echte Installation statt gegen die Suite. Von den vier externen Programmen
waren zwei in Ordnung, eines fehlte, und eines lief, während das, was Solidon
ihm schickte, nie gegen etwas Laufendes gehalten worden war.

- [x] **Die Graphen riefen Knoten, die es nirgends gibt.** Beide mitgelieferten
      Workflows nannten `Hy3DModelLoader`, `Hy3DGenerateMesh` und
      `Hy3DExportMesh` — Namen aus einem anderen Wrapper als dem installierten.
      ComfyUI wies sie beim Abschicken ab. `text_to_mesh` hängte zusätzlich
      einen `CLIPTextEncode` an einen Kern ohne Texteingang: Hunyuan3D kann
      kein Text-zu-3D, Text wird erst zu einem Bild. Beide Graphen laufen jetzt
      gegen `ComfyUI-Hunyuan3d-2-1`, mit SDXL und Freistellen davor.
- [x] **Ein gelungener Auftrag meldete, er habe nichts geliefert.** Die
      3D-Vorschau gibt den Pfad als blanken String zurück, `_download` verlangte
      einen Eintrag mit Feldern und übersprang ihn — die Datei lag auf der
      Platte, die Meldung sagte „kein Modell geliefert".
- [x] **Das empfohlene Modell schrieb seine Aufrufe hin, statt sie zu tun.**
      `qwen2.5-coder:14b` traf null von fünf Anfragen, weil es die Aufrufe als
      Fließtext ausgibt. Vorgabe ist jetzt `llama3.1:8b` (5/5), und
      `tools/check_local_model.py` hält die Messung nachfahrbar.
- [x] **Ollama fehlte ganz.** Installiert, Vorgabemodell geladen, Chat verifiziert:
      Kaltstart 31 s, warme Antwort 2,4 s.
- [x] **OpenSCAD und der Slicer waren in Ordnung.** OpenSCAD rendert,
      ElegooSlicer wird als Orca-Variante erkannt.

Gegengeprüft gegen die Installation: `text_to_mesh` 67 s auf 1,28 Mio Dreiecke,
`image_to_mesh` 40 s auf 550 Tsd, beide wasserdicht und über `read_mesh`
einlesbar. Stand danach: 2967 Tests grün, `ruff`, `ruff format` und `mypy` grün.

### Was diese Durchsicht gelernt hat

**Eine Datendatei ist Code, den niemand testet.** Die beiden Workflow-Graphen
lagen seit ihrer Entstehung im Repository, waren von der Suite abgedeckt — sie
prüfte, dass es gültiges JSON mit `class_type` und einem Platzhalter ist — und
hätten auf keiner Maschine der Welt funktioniert. Was nur gegen sich selbst
geprüft wird, ist nicht geprüft.

**Groß genug heißt nicht werkzeugfähig.** Die Modellwarnung misst
Parameterzahl, weil §27 das so sagt, und 14,8 Milliarden liegen weit über der
Grenze. Die Eigenschaft, an der die ganze Agentenschicht hängt, misst sie
nicht — und Ollamas eigene Fähigkeitsangabe auch nicht.

### Nachgezogen, gleiche Sitzung

- [x] **Die Graphen hängen nicht mehr an konkreten Modellnamen.** Sie nennen
      Rollen (`{model:image}`, `{model:shape}`, `{model:shape_vae}`), und
      `/object_info` sagt, was der Eingang zur Auswahl stellt. Die
      Ausschlussmuster sind der Kern: der Formkern liegt unter denselben
      Checkpoints wie die Bildmodelle. Passt kein Muster, wird genommen was da
      ist; fehlt die Datei ganz, sagt die Meldung genau das.
- [x] **Die Werkzeugprobe hat jetzt ein Feld, das sie prüfen kann.** Dahinter
      lag der größere Mangel: das lokale Modell ließ sich überhaupt nicht
      einstellen. „Zugang zum Sprachmodell" trägt jetzt beide Wege aus §27.
- [x] **Die letzten englischen Docstrings sind übersetzt** — 56 Stellen in 27
      Dateien unter `app/`, acht in `tests/` und `tools/`. Der Punkt oben aus
      dem Audit ist damit erledigt.

### Aus Kundensicht durchgegangen

Nicht der Code, sondern was jemand liest. Zwei Funde, beide auf demselben Weg:

- [x] **Fällt ComfyUI weg, stand dort ein Windows-Fehlercode.** Falscher Titel,
      roher Fremdtext als Grund, „Abbrechen" als einziger Vorschlag.
- [x] **Und selbst der gute Text kam nicht an.** Der Erzeugen-Dialog zeigte nur
      `problem.title`; Grund und Ausweg fielen still unter den Tisch.
- [x] **„Es ist kein Schlüssel hinterlegt"** stand im Zugangsdialog, während
      der Chat über das lokale Modell lief — es liest sich wie „geht nicht".

Dazu eine Lehre mit eigenem Wächter: **einen Fehlertext formatiert niemand
nach.** Ein `{platzhalter}` in `detail` oder `title` bleibt wörtlich stehen,
weil `show_details` den Text zeigt, wie er ist, und die `values` als eigene
Zeilen darunterhängt. In der Oberfläche ist derselbe Platzhalter richtig, dort
steht ein `.format` dahinter. `tests/test_errors.py` sucht im ganzen Kern
danach.

## Jeder Workflow einzeln durchgefahren (07.08.2026)

Nicht die Suite, sondern jeder Weg mit echten Läufen. Was dabei herauskam:

| Bereich | Umfang | Ergebnis |
|---|---|---|
| Operationsregister | alle 76, je ein Lauf | 62 durch, 12 begründete Ablehnungen, **2 Funde** |
| Bausteine | alle 18 über ihren Parameterbereich, 7–23 Proben je | alle sauber, jede Ablehnung begründet |
| Export | STL, 3MF, OBJ, PLY, STEP | vier rund und zurücklesbar; STEP lehnt Netze richtig ab |
| Schichtanalyse | 0,1 / 0,2 / 0,3 mm | 55 ms bei 0,2 mm — weit im Budget aus §31 |
| Oberfläche | Aufbau, Projekt laden, schließen | 0,47 s, **9 Menüs** (die Grenze), sauber zu |
| Handbuch | `manual.as_markdown()` | 102 730 Zeichen, 109 Abschnitte, 0,02 s |
| Erstinbetriebnahme | `tools.survey()` | alle vier Programme gefunden |
| Schnittstelle nach außen | `origin_allowed` in acht Fällen | hält, auch gegen `evil.localhost.attacker.com` |
| Auto Split | 300-mm-Körper auf 256er Bett | Befund, dann verstiftet in zwei geschlossene Körper |

Die beiden Funde waren derselbe, und er betraf **jede** Operation: Im
Prüfbericht stand die Entwicklernotiz statt des Satzes — `malformed target ''`
und eine halbe Seite roher OpenSCAD-Ausgabe, während „Das Ziel muss ein
Merkmal eines Objekts benennen" in `values` lag. Behoben, indem nur ein
übersetztes Detail nach vorn darf.

**Was dabei auffiel und keiner Änderung bedurfte:** die Ablehnungen. „Dieser
Körper ist schon geschlossen — eine zweite Haut darüber", „Der Körper ist auf
dieser Höhe massiv", „Die Wand ist für diese Steigung zu dünn". Zwölfmal
sagte das Programm genau, warum es nicht weitermacht. Das ist der Teil, den
ein Durchlauf wie dieser sonst nicht sichtbar macht.

## Die Wege einmal von Hand gefahren (07.08.2026)

Nicht die Suite, sondern die Anwendung: Weg 1 und 2 über die Kommandozeile,
die Übergabe an den echten ElegooSlicer, der Agent gegen ein lokales Modell,
dazu der Korpus mit seinen kaputten Dateien. Sechs Funde, alle auf dem
geradesten Weg, den es gibt.

- [x] **„Ein Objekt steht über den Bauraum hinaus"** bei einem 8 mm hohen Teil
      auf einem 256er Drucker. Es stand nicht hinaus, es lag halb unter der
      Platte — ein heruntergeladenes STL ist um den Ursprung zentriert. Der
      Satz schickt zum Skalieren, nötig war ein Aufsetzen.
- [x] **„Ein Merkmal hat keinen Nachfolger mehr"** als Warnung nach jedem
      Aushöhlen mit offener Decke. §21.3 knüpft das Melden an einen Verweis;
      ohne Verweis ist es eine Feststellung.
- [x] **`import` ohne `--unit` stürzte mit einem Stapelabzug ab**, sobald
      niemand antworten kann — in einer Pipe, einem Skript, auf einem
      Bauserver.
- [x] **`new --material PETG` legte eine kaputte Datei an.** Der Fehler kam
      erst beim nächsten Befehl. Die Falle ist eingebaut: `profiles` zeigt den
      Titel `PETG`, die Kennung ist `petg`.
- [x] **Die Slicer-Übergabe verlangte nur eines der zwei nötigen Profile.**
      Ohne Prozessprofil lehnt die Orca-Familie Solidons Prozessdatei ab.
      Mit beiden läuft der ganze Weg bis zu den G-Code-Kennzahlen.
- [x] **`tools/run_agent_suite.py` lief überhaupt nicht** — kein
      `load_operations()`, also leeres Register. Derselbe fehlende Aufruf in
      `check_local_model.py` hat die Modellwahl vom Vortag verdorben: gemessen
      wurde mit sieben Werkzeugen, der Agent bietet dreiundachtzig an.

### Was diese Begehung gelernt hat

**Ein leeres Register wirft keinen Fehler, es liefert nur weniger.** Beide
Werkzeuge außerhalb von Anwendung und CLI hatten denselben fehlenden Aufruf;
eines starb daran sichtbar, das andere lieferte still eine Zahl, die eine
Entscheidung getragen hat.

**Der Normalfall bekommt die schlechtesten Meldungen.** Beide Warnungstexte
oben standen nicht bei einem Fehler, sondern nach einer gelungenen Handlung —
und je häufiger eine Warnung zu Unrecht steht, desto weniger wert ist der
Platz, an dem die echten stehen.

### Nachgezogen

- [x] **Der flaky Beispieltest war rtree**, das in fremden Speicher greift —
      eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf, im Stapel
      `rtree/index.py:832`. `mesh.on_surface` fragt jetzt für alle drei
      Aufrufer und wiederholt einmal an einer Kopie des Netzes. Vorher 1 von
      20 rot, danach 0 von 40.
- [x] **Der Fortschritt trägt die verstrichene Zeit** und, wer wartet, seine
      Position in der Warteschlange.
- [x] **Die Agenten-Suite läuft und steht bei 8/33** (qwen3:14b, volles
      Register). Die eine Zahl, die §40 nicht als Quote führt, sondern als
      Regel, ist erreicht: **3/3 bei Mehrdeutigkeit gefragt**. Schwach bleibt
      „Baustein statt eigener Geometrie" mit 0/13.

      **Diese Zahlen sind überholt** — beide entstanden unter einem Prompt, den
      Ollama bei 4096 Token abgeschnitten hat. Der Stand nach dem Fund und
      Systemprompt v2 ist **22/33 und 8/13**; er steht im Punkt „Der Agent
      greift nicht zu den Bausteinen" unten in diesem Abschnitt. Wer hier
      aufhört zu lesen, nimmt den falschen Wert mit.
- [x] **Eine Operation ohne Eingangsobjekt** stürzte mit einem `IndexError`
      ab, statt anzuhalten — `example_v1.p3d` ließ sich damit gar nicht öffnen.

### Zwei Spuren, die hier enden

- [x] **Die Hardware-Spur wird nicht weiter verfolgt** (entschieden am
      14.08.2026). Die Messreihen bleiben stehen, weil sie eine Reihe von
      Verdächtigen ausschließen und niemand sie zweimal aufstellen soll. Was
      nicht bleibt, ist der offene Punkt: Es wird keine Speicherdiagnose und
      kein Prozessortest gefahren. Ein Testlauf, der rot wird, heißt damit
      wieder „Fehler im Code" — und der flackernde Rändel-Test verliert seine
      Erklärung und wird zur Fehlersuche wie jede andere.

      **Was das kostet, steht dazu:** Die beiden Pflaster in
      `mesh.on_surface` und `threemf._numbers_from` — einmal wiederholen, beim
      zweiten Fehlschlag durchlassen — bleiben im Code, ohne dass eine Ursache
      dahinter nachgewiesen ist. Sie fangen einen Fehlschlag, den niemand mehr
      erklärt. Wer sie anfasst, weiß damit, dass er eine Stütze wegnimmt und
      nicht eine Redundanz.

      Der Verdacht lag zuerst auf `rtree`; **das war falsch**, und die
      Korrektur ist der eigentliche Ertrag. Weiter eingegrenzt, jede Variante
      im eigenen Prozess:

      | Aufbau | Ergebnis |
      |---|---|
      | fertige Zahlenfelder + Trimesh, `rtree` geladen | 30/30 |
      | XML lesen + `np.array`, `rtree` geladen | 29/30 |
      | dasselbe, **`rtree` gesperrt** | 27/30 |
      | `np.array` über reine Python-Zeichenketten, **ohne XML** | 39/40 |
      | `np.fromiter` über Pythons eigenes `int()` | 57/60 |
      | reine Gleitkommaarbeit über SIMD | 40/40 |
      | reine Python-Arithmetik auf 32 Kernen | 72/72 |

      Damit fallen alle Verdächtigen der Reihe nach aus: nicht `rtree` (ohne
      es bleibt es rot, mit ihm und fertigen Feldern grün), nicht der
      XML-Leser (`lxml` verhält sich gleich, und ohne XML bleibt es rot),
      nicht NumPys Parser (Pythons `int()` ist genauso betroffen). Was übrig
      bleibt, ist die Kombination aus **vielen Speicherobjekten und ihrer
      Umwandlung** — und einmal kam dabei still eine falsche Summe heraus:
      `9.599.875.422` statt `9.599.880.000`, ohne jede Ausnahme.

      Die Maschine: i9-13900K (Raptor Lake, die Familie mit dem bekannten
      Instabilitätsproblem), 2×32 GB DDR5 auf 4800 MHz, zwei unerwartete
      Neustarts (14.07. und 20.07.2026), nie eine Speicherdiagnose gelaufen.

      **Am 08.08.2026 nachgemessen, und zwei Angaben oben stimmten nicht:**

      - **Es gibt einen WHEA-Eintrag.** 03.06.2026, ID 19: „Behobener
        Hardwarefehler, gemeldet von Komponente Prozessorkern, Fehlerquelle
        Corrected Machine Check, Fehlertyp **Translation Lookaside Buffer
        Error**, APIC-ID 40." Das zeigt auf die **CPU**, nicht auf den
        Speicher — und es ist genau das Fehlerbild, für das Raptor Lake
        bekannt ist. Er steht zudem *nach* dem BIOS vom 01.04.2026. Weiter
        zurück als der 29.04.2026 reicht das Protokoll nicht; ältere Einträge
        sind rotiert.
      - **Der Microcode ist nicht 0x12F, sondern 0x133** (Registry,
        `Update Revision`), also neuer als notiert.
      - **Der Rechenfehler ließ sich heute nicht reproduzieren.** 300 Runden
        derselben Bauart (17,7 MB XML, 200 000 Punkte und Dreiecke, `rtree`
        geladen): null Ausnahmen, null stille Abweichungen. Bei der gemessenen
        Rate von eins zu dreißig wären rund zehn Fehlschläge zu erwarten
        gewesen; dass keiner kam, ist mit 0,004 % Wahrscheinlichkeit
        Zufall. Das heißt nicht „behoben" — es heißt, dass die Bedingung
        fehlt, unter der er auftrat.

      **Und der letzte Datenpunkt spricht gegen die Spur, nicht für sie.**
      Dass 300 Runden derselben Bauart nichts fanden, wo zehn Fehlschläge zu
      erwarten waren, heißt: Die Bedingung, unter der der Rechenfehler auftrat,
      ist keine Eigenschaft der Maschine, sonst wäre sie reproduzierbar
      gewesen. Damit endet die Spur — nicht weil sie widerlegt ist, sondern
      weil sie nichts mehr vorhersagt.
- [x] **Der Agent greift nicht zu den Bausteinen (0/13) — es war das
      Kontextfenster.** Am 08.08.2026 gefunden, und es macht die ganze
      Untersuchung darunter zur Vorgeschichte: **Ollama schneidet den Prompt
      stillschweigend ab.** Sein Vorgabefenster ist 4096 Token, Solidon setzte
      `num_ctx` nicht, und allein die 84 Werkzeugschemata sind rund 99 000
      Zeichen — gemessen 21 162 Token. Was nicht hineinpasste, fiel weg, und
      mit ihm der Systemprompt samt der vier Vorrangregeln. Das Modell war
      nicht ungehorsam; es hat den Auftrag nie gesehen.

      Gemessen mit `qwen3:14b` an drei Anfragen, für die ein Baustein die
      richtige Antwort ist:

      | Fenster | verarbeitet | je Frage | Baustein |
      |---|---|---|---|
      | 4096 (Vorgabe) | 2 050, Rest weg | 30,1 s | 0 von 3 |
      | 8 192 | 4 098, Rest weg | 34,1 s | 0 von 3 |
      | 16 384 | 8 194, Rest weg | 36,1 s | 0 von 3 |
      | **32 768** | **21 162, ganz** | **21,2 s** | **3 von 3** |

      Das volle Fenster ist nicht nur richtiger, sondern **schneller** — ein
      Modell, das den Auftrag kennt, rät nicht herum. Es kostet Speicher: mit
      32 768 belegt `qwen3:14b` 14 GB und bleibt zu 100 % auf der Karte.
      `OLLAMA_CONTEXT_TOKENS` in `backends/llm.py` hält Wert und Messreihe.

      **Die volle Suite dazu, und sie hat zwei Seiten.** 33 Anfragen,
      `qwen3:14b`, gegen den Stand vor der Änderung:

      | Maß | vorher | nachher |
      |---|---|---|
      | gut beantwortet | 8/33 | **17/33** |
      | Baustein statt eigener Geometrie | **0/13** | **6/13** |
      | bei Mehrdeutigkeit gefragt (§40) | **3/3** | **1/3** |
      | Hauptmaße als Parameter | — | 2/3 |
      | Zeitüberschreitungen | 17 (mit 30b) | 2 |

      Die Gesamtquote verdoppelt sich, der gemeldete Befund ist weg — und
      **eine Zahl ist gefallen, und zwar die, die §40 als Regel führt.** Von
      den drei mehrdeutigen Anfragen fragt nur noch `join_what`;
      `which_hole` („Mach das Loch größer" bei vier Bohrungen) und
      `how_much_thinner` („Mach das Teil dünner") raten stattdessen —
      `which_hole` mit zwanzig Aufrufen von `drill_hole` und `plug_hole`
      hintereinander.

      Das ist die Kehrseite desselben Fundes: Wer alle vierundachtzig
      Werkzeuge sieht, findet immer eines, das plausibel aussieht. Vorher war
      die Auswahl beschnitten, und `ask_user` blieb übrig — die 3/3 waren
      also kein Gehorsam, sondern Mangel an Alternativen. Es bleibt
      trotzdem ein Verstoß gegen Regel 21 und gegen ein Abnahmekriterium.

      **Behoben im Systemprompt, Version 2.** „Fragen vor Raten" stand als
      vierte von vier Gewohnheiten — anleitend, nicht verhindernd. Davor steht
      jetzt eine Vorbedingung mit drei Prüfungen, von denen jede einzelne für
      eine Rückfrage genügt: Ziel eindeutig (ein Merkmal, das mehrfach
      vorkommt, und keines ausgewählt), Maß genannt (ein Vergleich ist kein
      Maß), Bezug vorhanden (mehr Objekte genannt als im Steckbrief). Dazu der
      Satz gegen das Herumprobieren — `which_hole` hatte zwanzig Aufrufe
      hintereinander abgesetzt: „Trifft eine der drei zu, rufe ask_user auf und
      sonst nichts."

      Die drei Prüfungen sind allgemein formuliert und nicht als Sonderfälle
      der drei Testanfragen. Auf die Suite hin zu optimieren hieße, sie als
      Maßstab zu verlieren.

      | Maß | vor `num_ctx` | Prompt v1 | **Prompt v2** |
      |---|---|---|---|
      | gut beantwortet | 8/33 | 17/33 | **22/33** |
      | Baustein statt eigener Geometrie | 0/13 | 6/13 | **8/13** |
      | bei Mehrdeutigkeit gefragt (§40) | 3/3 | 1/3 | **3/3** |
      | Hauptmaße als Parameter | — | 2/3 | 2/3 |
      | Schritte im Mittel | — | 4,1 | 4,4 |

      Kein Maß ist gefallen, also bleibt die Änderung — die Rücknahmeregel aus
      `AGENTS.md` greift nicht. Gewonnen haben `on_bed`, `orient` (vorher
      Zeitüberschreitung) und `split`.

      **Nachgesehen bei den zwei, die als verloren dastanden** — und eine der
      beiden Aussagen war falsch:

      - `handrail_bend` fiel nur unter Prompt 2 und wählt seither wieder
        `sketch_sweep` mit `shape=circle, length=12, bend_radius=60,
        bend_angle=90`. Das ist richtig; bei einem Kreis ist `length` das
        Querschnittsmaß. Und der Ausrutscher davor war geometrisch nicht
        einmal falsch: `sketch_revolve` hat einen Winkel und einen
        Achsabstand, ein Ø12-Kreis bei 54 mm und 90° ergibt denselben Bogen.
        Der Fall akzeptiert nur `sketch_sweep`, was vertretbar ist.
      - `pocket_plate` war **nie gewonnen** — es stand schon vorher rot, und
        die Ursache lag nicht bei der Op-Wahl. Ein Mitschnitt des Zuges zeigte
        sie: `create_box` erzeugt ein Netz, `sketch_pocket` scheitert daran
        viermal, und die einzige Auskunft lautete „Die Auswertung hält bei
        dieser Operation an". Der Grund stand die ganze Zeit im Prüfbericht —
        „Der gewählte Körper ist ein Netz" — und kam nur nicht an. Das Modell
        drehte deshalb an den Zahlen statt am Körpertyp.

      Behoben an zwei Stellen. `checks.check` reicht die Befunde der
      anhaltenden Operation durch. Und die Antwort ans Modell nimmt die
      `values` mit: die Fehlertexte des Kerns tragen keine Platzhalter, „Der
      Wert liegt unter dem zulässigen Mindestwert" ist der ganze Satz, und was
      er meint, stand daneben. Der Feldname gehört dabei ausdrücklich dazu —
      ohne ihn korrigierte das Modell dreimal die Tiefe, während `corners` die
      Grenze riss.

      Danach fährt derselbe Fall so: `create_brep_box` beim ersten Versuch
      exakt, `corners=0` → „field=corners, minimum=3" → korrigiert, ein
      Objektname statt einer ID → „missing=['deckel']" → korrigiert, und
      `sketch_pocket` läuft. Vier Schritte statt fünf, und jede Meldung führt
      zu einer gezielten Korrektur statt zu einem neuen Versuch.

      **Wogegen gemessen wurde**, weil es sonst später niemand zuordnen kann:
      der Stand vor `b8829c3` und `ecf4544`. Beide ändern Kontextaufbau,
      Werkzeuge und Steckbrief — also genau das, was diese Messung als
      Umgebung hatte. Wer die Zahlen fortschreibt, misst neu.

      **Das ändert eine Angabe, die dem Kunden gemacht wird.** Beide
      Startseiten und der Hinweis im Modelldialog nannten „rund 10 GB
      Grafikspeicher" — das galt für das Modell allein (9,3 GB). Mit dem
      Kontextfenster kommt der Schlüssel-Wert-Zwischenspeicher dazu, gemessen
      14 GB für das Modell und 15,7 GB belegt insgesamt. Die
      Systemvoraussetzung steht deshalb jetzt bei **16 GB**, in beiden
      Sprachen. Eine Karte mit zwölf würde auf die CPU auslagern — also genau
      die Zeitüberschreitungen zurückholen, die oben als Ausstattungsfrage
      standen.

      **Was daraus für die Vorgeschichte folgt:** Jede Zahl unten entstand
      unter abgeschnittenem Prompt. Die Werkzeugmengen-Tabelle misst nicht,
      wie gut ein Modell mit vielen Werkzeugen umgeht, sondern **ab wann sie
      nicht mehr ins Fenster passen** — bei zehn taten sie es, bei
      dreiundachtzig nicht. Und der Modellvergleich (`qwen3:30b-a3b` fünf von
      fünf gegen `qwen3:14b` in Prosa) verglich zwei Modelle, von denen
      keines den Systemprompt vollständig bekam. Er gehört wiederholt, bevor
      jemand daraus eine Anschaffung ableitet.

      <details><summary>Die Untersuchung, die zur falschen Fährte führte</summary>

      Nachgemessen wurde die Werkzeugmenge, mit demselben Fall und
      demselben Modell (`qwen3:14b`):

      | Angebot | wall_holder | magnet_lid | spacer |
      |---|---|---|---|
      | 10 Werkzeuge | `find_part` | `find_part` | `find_part` |
      | 25 Werkzeuge | `create_box` … | `create_from_scad` | `create_brep_cylinder` ×4 |
      | 83 Werkzeuge | `sketch_sweep` … | Prosa | Prosa |

      Bei zehn Werkzeugen folgt das Modell der Vorrangregel dreimal von drei —
      `find_part` ist genau der erste Schritt, den „Bausteine vor Primitiven"
      verlangt. Bei fünfundzwanzig bricht sie, bei dreiundachtzig antwortet es
      gar nicht mehr strukturiert. Der Systemprompt wird also gelesen und
      verstanden; was fehlt, ist die Fähigkeit, ihn unter voller Werkzeuglast
      in Aufrufe zu übersetzen.

      Damit ist es keine Regelfrage mehr. Und auch keine Bauplanfrage: §26.2
      schreibt „alle Ops aus dem Register" vor, und **das kann bleiben** —
      `qwen3:30b-a3b` trifft mit allen dreiundachtzig Werkzeugen fünf von
      fünf, wo `qwen3:14b` in Prosa fällt. Eine Auswahl nach `applies_to`
      wäre also nicht nötig, und sie wäre auch das, was §2 für die Oberfläche
      ausschließt.

      Nur nützt das auf **dieser** Maschine nichts: Das Modell belegt 19 GB,
      die Karte hat 16, es läuft zu einem Viertel auf der CPU — und die volle
      Suite endete bei 4/33, davon **17 Zeitüberschreitungen**. Gemessen wurde
      damit die Wartezeit, nicht die Fähigkeit. `qwen3:14b` passt in den
      Speicher und bleibt mit 8/33 die bessere Wahl, also auch die Vorgabe.

      | Modell | Werkzeugtest | Suite | Anmerkung |
      |---|---|---|---|
      | `qwen3:14b` | 4/5 | **8/33** | 9,3 GB, passt in den Speicher |
      | `qwen3:30b-a3b` | **5/5** | 4/33 | 19 GB, 17 Zeitüberschreitungen |

      Beide erfüllen die eine Zahl, die §40 als Regel führt: 3/3 bei
      Mehrdeutigkeit gefragt.

      Offen bleibt damit nicht die Regel, sondern die Ausstattung — und
      nebenbei ein Wert: `llm.TIMEOUT_SECONDS` steht auf 120, und ein lokales
      Modell mit CPU-Anteil braucht bei vollem Kontext länger. Ihn pauschal
      hochzusetzen verlängert aber die Wartezeit im Chat für alle; das will
      eigens entschieden werden.

      </details>

      Der Wert daneben hat sich damit auch geklärt: `llm.TIMEOUT_SECONDS`
      bleibt bei 120. Mit vollem Fenster antwortet `qwen3:14b` in 21 Sekunden
      und vollständig auf der Karte — die Zeitüberschreitungen kamen vom
      CPU-Anteil eines Modells, das nicht hineinpasste, nicht von der Grenze.

## Jeden Weg einzeln durchgespielt (07.08.2026, zweiter Durchgang)

Nicht über die Kommandozeile wie beim ersten Mal, sondern über die Verträge
selbst: Weg 1 gegen alle vierzehn Korpusdateien, Weg 2 über neunundfünfzig
Operationen mit ihren Vorgabewerten, Weg 3 gegen Werkzeugschemata,
Transaktionsregel und Quelltextprüfung. Vier Funde, und der größte davon
betrifft jede Fehlermeldung der Anwendung.

- [x] **Dreizehn von vierzehn Korpusdateien bekamen eine Bauraumwarnung.**
      `_message_for` unterschied längst drei Fälle — unter der Platte, neben
      der Platte, größer als der Bauraum —, die Schwere nicht. Damit warnte
      fast jede geladene Datei, denn ein heruntergeladenes Teil ist um den
      Ursprung zentriert. Die Trennlinie ist jetzt, ob das Teil nach dem
      Verschieben hineinpasst: dann ist es ein Hinweis. Über den Korpus
      gemessen bleibt eine Warnung übrig — `oversized.stl`, die einzige, auf
      die sie zutrifft.
- [x] **Jede Ausnahme nannte ihre Art und verschwieg ihren Grund.**
      `AppError.__init__` übergab nur den Titel an `Exception`. Der ist je
      Klasse gleich: über jedem `ValidationError` stand „Ein Wert liegt
      außerhalb des zulässigen Bereichs", ob es um eine Wandstärke ging oder
      um ein fehlendes `@` vor einem Parameternamen. Die Oberfläche liest
      beide Felder einzeln und merkte nichts; Protokoll und Traceback zeigten
      allein diesen Satz.
- [x] **Der Titel für Grammatikfehler war der falsche.** Bei einem unlesbaren
      Ausdruck liegt nichts außerhalb eines Bereichs.
- [x] **Der Steckbrief bot dem Agenten `-1.11022e-16` als Ort an.** Ein
      zentrierter Quader landet rechnerisch knapp neben null. Der Agent hat
      keine andere Quelle als diesen Text und liest die Zahl als Wert, der
      etwas bedeutet. Nebenbei wurde der Steckbrief um 64 Zeichen kürzer —
      bei jedem Aufruf.

### Was dieser Durchgang gelernt hat

**Eine Warnung, die fast immer dasteht, ist keine Warnung mehr.** Dasselbe
Muster wie beim ersten Durchgang, nur an anderer Stelle: der Platz, an dem die
echten Warnungen stehen, verliert seinen Wert mit jeder unberechtigten.

**Was die Oberfläche richtig zeigt, kann anderswo falsch ankommen.** Die drei
Fehlertext-Funde lagen alle daran, dass `title` und `detail` in der Oberfläche
getrennt gelesen werden und überall sonst nicht. Ein Fehlerpfad ist erst
geprüft, wenn er auch außerhalb des Dialogs gelesen wurde.

**Nicht jeder rote Befund ist ein Fund.** Vier Alarme dieses Durchgangs waren
Fehler im Prüfskript: eine Op, die anders heißt, ein Parameter, der `@`
braucht, eine Quelle, die zweimal eingetragen werden will, und eine
Sicherheitsprüfung, die ein Ergebnis zurückgibt statt zu werfen. Die
Quelltextprüfung nach §32 lehnt absolute Pfade, Schritte nach oben, URLs und
sogar `import(variable)` zuverlässig ab.

## Puppenhaus: beide Wege an einem Stück (07.08.2026)

Ein Puppenhaus für ein Kind — Architektur gezeichnet, Einrichtung erzeugt.
Gebaut wurde live in der Anwendung über Menüeinträge, Zeichenfläche und
Dialoge, nicht über die Session-API: was zwischen Menü und Geometrie liegt,
lief damit mit.

### Was trägt

- **Der Zeichenmodus trägt.** Rechteck 180 × 120 eingesetzt, elf
  Zwangsbedingungen, „Bestimmt — alle Freiheitsgrade sind vergeben", Fertig,
  Dialog, Körper. Boden 86,4 cm³ auf den Millimeter.
- **Speichern und Öffnen tragen.** Titel wechselt, `modified` wird falsch,
  Volumen vor und nach dem Neustart identisch bis auf drei Nachkommastellen.
- **Die Generierung trägt.** Vier Möbel über `ComfyBackend`, 16 bis 51
  Sekunden je Stück, alle vier angekommen.

### Was nicht trägt

- [x] **Vierzehn Werkzeuge in einer Zeile, jedes zweite Wort abgeschnitten.**
      Gemessen 1165 px nötig, 70 px je Knopf zugeteilt, 1800 px vorhanden.
      Behoben mit Zeichen statt Beschriftung.
- [x] **Objektbaum elf Pixel hoch, nötig hundertdrei.** `fit_to_rows` bemisst
      die Liste, nicht die Karte. Der Verlauf ebenso.
- [x] **Die Wiederherstellung fragte mit Ja und Nein** und verschwieg, wie alt
      die Sicherung ist.
- [x] **Aushöhlen macht aus einem exakten Körper ein Netz.** Danach lehnte
      „Tasche schneiden" ab: „braucht einen B-Rep-Körper; hier liegt ein
      Netz." Der Fehler kam erst drei Schritte später, und der Satz stand
      neben einer Operation, die nichts dafür konnte. Die Auswertung sagt es
      jetzt sofort (`evaluate.exact_became_mesh`) — an einer Stelle, und
      damit für **jede** Netz-Operation auf einem exakten Körper, nicht nur
      fürs Aushöhlen.
- [x] **`scale_object` deckelt bei Faktor 100, Weg 3 braucht mehr.** Was aus
      ComfyUI kommt, ist auf einen Einheitswürfel normiert: die vier Möbel
      maßen 0,6 bis 2,0 mm. Der Schrank hätte 141,7 gebraucht und blieb
      1,3 mm groß. Beides ist beantwortet: `fit_to_size` nimmt das Zielmaß
      statt eines Faktors und steht in der Generierungskette (`load`,
      `fit_to_size`, `repair`) — und der Faktor selbst reicht jetzt von einem
      Tausendstel bis Tausend. Hundert war willkürlich; tausend deckt den Weg
      vom Einheitswürfel bis an jeden Bauraum ab.
- [x] **Was ComfyUI liefert, ist nirgends wasserdicht.** Alle vier Möbel kamen
      offen an, mit 625 000 bis 1 229 000 Dreiecken. Sie kamen **geschlossen**
      an und wurden es hier nicht mehr: Verschweißen und Entarten messen
      absolut, und auf einem Einheitswürfel lag nicht der Doppelpunkt unter
      der Toleranz, sondern die halbe Lehne. Erst auf Maß, dann bereinigen —
      alle vier bleiben dicht und behalten 99,9 % ihrer Dreiecke.

## Gewürzdeckel: der Fehler saß im Deckel, nicht im Becher (07.08.2026)

Fotos vom gedruckten Deckel zeigten das Innere voller Fäden. Nachgemessen mit
Solidons Schichtanalyse und mit dem ElegooSlicer, beide am selben Teil.

### Der Befund

`deckel_basis.stl` hat bei **z = 13,10 einen Überhang von 845,6 mm²** auf einer
einzigen Schicht — vier Fünftel des gesamten Überhangs des Teils. Die
Lochplatte sitzt auf einem Vollzylinder, dessen Bohrung bei z = 13 endet: sie
fängt über der ganzen Gewindebohrung in der Luft an.

Der ElegooSlicer bestätigt es aus seiner Sicht. Auf dieser Höhe fährt er
**4909 Segmente `Bridge` und 12552 `Overhang wall`**.

Das ist derselbe Fehlertyp, den die Spezifikation als Nr. 5 führt — die
waagerechte Ringschulter im Becher, dort mit 2328 Brückensegmenten gemessen
und mit einem 45-Grad-Kegel behoben. Am Deckel wurde er nie gesucht, und er
ist **doppelt so groß**. Der Becher selbst ist sauber: höchstens 3,7 mm² je
Schicht.

Nicht die Ursache war dagegen das Profil (Nr. 6): der G-Code trägt
`print_settings_id = Gewuerzset @ECC2`, das eigene Profil wird geladen.

### Was eine Fase davon einfängt

Gemessen an vier Varianten: eine Hohlkehle unter der Platte halbiert es auf
404,8 mm², mehr gibt die Geometrie nicht her — die Platte muss über den
Behälterhals spannen, und der ist Ø 28 bis 35. Ein Trichter *in* der Platte
misst zwar besser, zerstört sie aber (23 % Volumenverlust). Offen bleibt damit
die konstruktive Frage, nicht die Diagnose.

### Zusammenspiel mit dem ElegooSlicer

- [x] **`machine_profile` und `base_process` müssen Pfade sein, nicht Namen —
      die Auflösung dazwischen steht.** Die Anforderungen ziehen auseinander:
      In die Projektdatei gehört der **Name** (ein Pfad dort verstößt gegen
      Regel 12), der Slicer nimmt nur die **Datei**. `handover.profile_file`
      löst beides auf und wird an allen vier Stellen benutzt — Maschine,
      Prozess, Filament und im Profilschreiber.

      **Am 14.08.2026 am echten Bestand nachgemessen:** ElegooSlicer, 3887
      gefundene Profile, `profile_file("0.12mm Fine @Afinia H+1(HS)", …)`
      liefert die existierende Datei unter `resources/profiles/…`. Fünf Tests
      in `tests/test_print_settings.py` halten Name, Pfad, falsche Art und den
      leeren Fall fest. Der Punkt stand offen, weil ihn niemand abgehakt hat —
      nicht, weil etwas fehlte.
- [x] Gefunden werden die Profile einwandfrei: 3887 Stück, die im Slicer
      eingestellte Maschine erkannt, sieben passende Prozesse dazu.
- [x] Der Rücklauf stimmt: Solidon liest seinen eigenen G-Code mit 10,38 g,
      72 min, 110 Schichten, 0,2 mm — und `extrudes()` sagt ja.

## Vollständige Verifikation des Gewürzsets (07.08.2026)

Alle vier Teile durch alle drei Ebenen: Solidons Schichtanalyse, die Übergabe
an den ElegooSlicer über Solidons eigenen Weg, und der zurückgelesene G-Code.

| Teil | Überhang schlimmste Schicht | Übergabe | G-Code |
|---|---|---|---|
| Deckelbasis | **845,6 mm² bei z 13,10** | ok | 10,38 g · 72 min |
| Streuscheibe | 0,0 mm² | ok | 2,46 g · 13 min |
| Behälter | 3,7 mm² | ok | 24,26 g · 97 min |
| Wandregal | 3253,6 mm² bei z 46,10 | ok | 139,32 g · 493 min |

Die Gegenprobe (`handover.verify`) meldet bei allen vier **null Abweichungen**:
der Slicer übernimmt jeden Wert, den Solidon schreibt. Alle vier fördern
Material.

### Der Unterschied zwischen Deckel und Regal

Beide melden einen 90-Grad-Überhang, und beim Regal ist er viermal so groß —
gemessen nachgeprüft: bei z 46,00 springt die Fläche in zwei Hundertsteln
Millimeter um 250 %, und dort liegen vier Dreiecke mit der Normalen genau nach
unten. Trotzdem fährt der Slicer dort nur **108 Brückensegmente**, am Deckel
aber **4909**.

Der Grund ist nicht die Geometrie, sondern was darunter liegt. Im Regal steht
Füllung (`Sparse infill` über die ganzen Schichten darunter), und die trägt.
Unter der Lochplatte des Deckels ist die Gewindebohrung — ein echter
Hohlraum, in dem nichts steht.

**Das ist eine Grenze von Solidons Schichtanalyse, die man kennen muss:** sie
misst die Geometrie und weiß nichts von der Füllung, die der Slicer später
hineinlegt. Ein gemeldeter Überhang über gefülltem Volumen ist deshalb kein
Befund, einer über einem Hohlraum schon. Wer die Zahl allein liest, hält das
Regal für schlimmer als den Deckel — und es ist umgekehrt.

### Und von Hand, über beide Oberflächen

Derselbe Deckel noch einmal, aber über die Bedienung statt über die Verträge:
Modell einfügen, Druckeinstellungen öffnen, Slicen drücken.

- **Modell einfügen** über `session.import_model`: ein Körper, 40 × 40 × 22 mm,
  9,12 cm³, geschlossen. Ein Befund, und der stimmt („Doppelte Punkte wurden
  verschweißt").
- **Die Profilsuche braucht 1,3 s** und läuft in einem Arbeiter-Thread; solange
  steht der Hinweis „Automatisch zugeordnet …" im Dialog. Danach: 1001
  Maschinen, 7 passende Prozesse, 42 Filamente — jede Liste **von selbst
  richtig vorbelegt** (Centauri Carbon 2 · 0.20mm Standard · Elegoo PETG),
  und alle drei tragen Pfade, die es gibt.
- **Der Dialog misst 561 × 867 px und braucht genau so viel** — nichts
  abgeschnitten.
- **Slicen** endet nach einer Sekunde mit „Druckzeit: 73 min · Material:
  10.6 g · Schichten: 110" in der Statuszeile. Der G-Code ist da (4657 KB),
  fördert Material, und von vier Befunden ist keiner eine Warnung.

Der Weg über die Oberfläche war nie vom Namen-gegen-Pfad-Fehler betroffen: der
Dialog legt `str(entry.path)` in die Auswahl, also von jeher die Datei. Wen es
traf, war jeder andere Aufrufer — die Kommandozeile, ein Skript, der Agent.

## Aus Kundensicht vollständig nachgefahren (08.08.2026)

Zehn Bedienläufe am echten Programm, **im Vollbild** (2560 × 1369 px), über den
Qt-Ereignisweg und den VTK-Interactor. Ergebnis:
**`konzepte/konzept-kundensicht-2026-08.md`** im Projektwurzelverzeichnis.

Durchgegangen: Erstinbetriebnahme mit frischem Nutzerverzeichnis · alle neun
Menüs mit 127 Einträgen · alle 77 Operationen, davon 72 Dialoge einzeln
vermessen · Viewport mit Auswahl, Merkmalen, Kontextmenü, beiden Messarten ·
alle sieben Analysekarten · Schichtenvorschau · alle sechs Zonen · Katalog ·
Skizzeneditor · sieben weitere Dialoge · Druckeinstellungen mit Profilsuche ·
Export in vier Formate und zurück · Handbuch · Auto Split · Rückgängig ·
Übersetzungskatalog · alle 14 Fehlerklassen.

### Die drei Befunde, aus denen die Arbeit folgt

1. **Die Karten wachsen nicht mit dem Fenster.** Im Vollbild bei 1188 px
   verfügbarer Höhe: Objektbaum 321 px statt 751 (Rollbalken, während unter
   der Karte 300 px leer bleiben), Prüfbericht 316 px mit Rollbalken bei
   **fünf** Befunden, Chat 170 px, Tour schneidet jeden Schritt ab. Zwei
   Ursachen: der feste Zeilendeckel `MAX_ROWS = 12` (`panels.py:981`, gesetzt
   über `setFixedHeight`) und `natural_height` (`overlay.py:160`), das für
   umbrechende Listen mit `sizeHintForRow` rechnet — ein zweizeiliger Befund
   gilt ihm als einer.
2. **Eine Parameteränderung kostet 9–15 s statt der 2 s aus §31.** Gemessen an
   `dose-mit-deckel.p3d`, sieben Ops: `hoehe` 40 → 60 braucht 14,75 s, 60 → 45
   dann 9,49 s, 45 → 40 nur 0,75 s — der letzte Wert lag im Cache. Jeder
   **neue** Wert kostet also zweistellig, und genau die sind es, um die es beim
   Drehen an einem Maß geht. Ohne Fremdlast gemessen (1 % CPU).
3. **Der Prozess stirbt gelegentlich.** Einmal in zehn Läufen: rtree-Zugriffs-
   verletzung, unmittelbar danach `SystemError: setobject.c:2676` beim
   Set-Zugriff in `features.py:261`, dann Segfault. Der Wiederholversuch in
   `mesh.py:180` heilt den Aufruf, nicht den Speicher.

### Weiteres

- Das Kontextmenü im Bild bietet zwei Einträge („Ausblenden", „Alles andere
  ausblenden") — §18.5 sieht dort `applies_to` vor.
- „Bohrung setzen" öffnet auf X/Y/Z = 0,00. Bei `weg1-halterung` liegt der
  Ursprung im Teil und es greift; bei `dose-mit-deckel` liegt er **65 mm
  daneben**, und die Operation meldet „Der Schnitt hat nichts abgetragen".
  Sobald „Auf dem Bett anordnen" gelaufen ist, ist das der Normalfall.
- Im Druckeinstellungs-Dialog ist die Spalte „Grund" in jeder Zeile
  abgeschnitten (561 px Dialogbreite auf 2560 px Bildschirm).
- `dose-mit-deckel.p3d` öffnet mit zwei Warnungen, darunter eine wirkungslose
  Boolesche, die keine Tour erklärt.
- STEP steht im Exportdialog und scheitert bei Netzen — mit vorbildlicher
  Meldung, aber erst nach der Formatwahl.
- Erstes Öffnen in einer Sitzung: 7,9–8,3 s; jedes weitere 0,2–0,4 s. Das sind
  die nachgeladenen Bibliotheken, nicht die Auswertung.
- Sechs von 77 Operationen tragen ein Tastenkürzel.

### Was trägt

Erstinbetriebnahme vollständig und vorbelegt, alle vier externen Programme
richtig erkannt · 77 Operationen, alle in Menüs, 72 Dialoge fehlerfrei, keiner
über 427 px · **der Viewport nimmt Klicks an** (`obj_2` und `face_7`, Baum
folgt) — der Fund aus `konzepte/konzept-bedienung.md` ist erledigt · **beide Messarten
tragen** (Abstand 48,91 mm, Wandstärke 2,0 mm; eine erste Gegenmessung war ein
Klick daneben) · sieben Analysekarten je 1,4–1,5 s bei 3 s Budget ·
Schichtenvorschau 2,67 s · Auto Split 1,77 s · Druckeinstellungen belegen
Maschine, Prozess und Filament von selbst richtig vor (1001 / 7 / 42 Einträge)
· STL, 3MF und OBJ schreiben und lesen zurück · 1986 Übersetzungen, keine
leer, kein Registertext ohne englische Entsprechung · alle 14 Fehlerklassen
mit Handlungsvorschlag · Rückgängig stellt den Stapel wieder her.

### Nachgezogen, gleiche Sitzung

- [x] **Acht Sekunden auf ein leeres Fenster.** Das erste Öffnen einer Sitzung
      dauert 7,9–8,3 s, und in dieser Zeit stand die Ansicht leer: kein
      Objektbaum, kein Körper, und als einzige Auskunft ein 180 px breiter
      Balken unten rechts — an der Stelle, an der beim Warten niemand hinsieht.
      Jetzt liegt `LoadingVeil` (`app/ui/loading.py`) über der Ansicht: das
      Anwendungssymbol wird gedruckt wie auf dem Ladebildschirm, darunter
      Fortschrittslinie, Prozentzahl, laufender Operationstitel und
      *Abbrechen*. Drei Kodierungen für dieselbe Zahl (Regel 18). Sie kommt
      erst nach 200 ms, sie liegt **unter** den schwebenden Karten, und sie
      kommt nur, wenn kein Körper im Bild steht — §2.8 lässt die letzte
      gültige Darstellung stehen. Das Zeichnen des halb gedruckten Zeichens
      teilt sie sich mit `splash.py` (`icons.paint_printed_mark`).
- [x] **Der Themenwechsel aus dem Einstellungsdialog erreichte die Karten
      nicht.** `action_theme` zog `_apply_card_style` nach, `_apply_settings`
      nicht — über den Dialog gewechselt, behielten die schwebenden Zonen die
      Farben des alten Themas.

### Behoben, am selben Tag

Alle Punkte bis auf die Tastenkürzel, jeder mit Test und am laufenden Fenster
nachgemessen. Der Nachtrag in `konzepte/konzept-kundensicht-2026-08.md` führt die
Zahlen; die wichtigsten:

- **Die Karten wachsen mit.** `MAX_ROWS` ist kein Deckel mehr, sondern eine
  Rückfallzahl: die Überlagerung teilt den Raum nach Bedarf zu (`_share_room`).
  `rows_height` fragt `visualRect` statt `sizeHintForRow`, `natural_height`
  achtet auf Rollbereiche und gesetzte Mindesthöhen. Prüfbericht 316 → 322 px
  ohne Rollbalken, Objektbaum 321 → 873 bei 871 Bedarf, Chat 170 → 334,
  Tour zeigt 139 von 139 statt von 152.
- **Eine Parameteränderung kostet 1,47 s statt 8,3.** Die Ursache lag nicht in
  der Auswertung, sondern in der Slot-Übertragung: sie suchte für jedes der
  vierzigtausend Dreiecke den Abstand zu jeder Quelle, auch zu einer
  Beschriftung aus sechshundert. Der Vorfilter in `geom.attributes` ist exakt
  — dreiunddreißig Aufrufe über vier Beispiele, kein einziges abweichendes
  Dreieck.
- **Dasselbe löste zwei weitere Funde.** Erstes Öffnen 8,0 → 1,55 s. Und die
  rtree-Anfragen je Auswertung fielen von 113168 auf 1180: sechzig
  Auswertungen hintereinander ohne einen Fehlgriff, wo etwa drei zu erwarten
  gewesen wären.
- **Das Kontextmenü am Merkmal** las den Durchmesser als Art des Merkmals.
  Jetzt stehen dort die Operationen aus `applies_to`; am ganzen Körper wird
  über zwölf Einträgen nach Kategorie gruppiert (`MENU_GROUPS` ist dafür nach
  `labels.py` gewandert).
- **„Bohrung setzen"** öffnet auf der obersten Fläche des gewählten Körpers
  statt auf dem Ursprung (`values_for_object`).
- **Kleineres:** die Spalte „Grund" im Druckdialog bricht um statt abzubrechen,
  STEP steht nur im Exportdialog, wenn ein Körper es tragen kann, und die
  Einpressbuchse im Dose-Beispiel sitzt auf dem Boden statt über dem Hohlraum
  — von acht Beispielen warnt nur noch das, dessen Zweck das Warnen ist.

**Eine Regression dabei, gemeldet und behoben:** Die erste Version der
Raumzuteilung las die Höhen, die sie gerade selbst gesetzt hatte, und die
linke Spalte lief bei jeder Aktion auf und ab — neunhundertfünf
Geometriewechsel für ein Aufklappen. Gerechnet wird jetzt nur mit dem
verfügbaren Raum und dem Bedarf, und eine Animation, die schon dorthin
unterwegs ist, wird nicht neu gestartet. Gemessen: eine Bewegung je Aktion.

**Offen:** die Tastenkürzel. Sechs in der Vorgabe ist eine Entscheidung und
keine Lücke — welche Operationen eine Taste verdienen, ist eine Design-Frage.

---

## Handbuch, Website und Rechtstexte durchgesehen (08.08.2026)

Anlass war eine Frage, keine Fehlermeldung: „Ist die Doku vollständig,
seriös, aktuell?" Geprüft wurden Handbuch, Website, README, Bauplan, die
Konzeptpapiere und die Roadmap — gegen den Code, nicht gegen die Erinnerung.

### Was falsch war und jetzt stimmt

- **Die Startseite trug „Formwerk".** In vier Seiten, jeweils Zeile 15, als
  `Form<span>werk</span>` — deshalb hat der Umbenennungs-Commit sie nicht
  gefunden, und deshalb findet keine Suche nach dem Namen sie. Der Name war
  gefallen, weil eine Wort-/Bildmarke „3D FORMWERK" für „Entwurf von
  3D-Modellen für den 3D-Druck" bestandskräftig wurde.
- **Drei der sieben Analysekarten hießen im Handbuch anders als im
  Programm.** „Dicke der ersten Schicht", „Abstand zum Bauraumrand" und
  „Materialverteilung" gibt es nicht; die drei heißen Netzfehler,
  Feature-Zuordnung und Passungen.
- **Die Toleranzleiter stand unter einem Menüeintrag, den es nicht gibt**
  („Passungsleiter" statt „Toleranz-Testkörper"), mit einem Bereich, den die
  Vorgaben nicht ergeben (0,10–0,40 statt 0,10–0,25 mm).
- **252 Zahlen im deutschen Handbuch schrieben einen Punkt.** Die erzeugte
  Referenz formatierte mit `:g`, neben einer Anwendung, die „2,40 mm" zeigt.
  `format_decimal` entscheidet das jetzt nach der Sprache.
- **Zwanzig Zeichnungen hatten weißen Grund** in einer Seite, die dem
  Systemthema folgt. Die dunkle Version gab es die ganze Zeit —
  `make_manual` rief nur `svg(key, "light")`.
- **Der Bauplan verbot den eigenen Namen.** §37.1 führte „kein ‚3D' im
  Namen" als Kriterium, und die Anwendung heißt Solidon3D. Das Kriterium ist
  gefallen, mit Begründung.
- **`.wrap` stand auf 62rem.** Auf 1920 × 1080 blieben 464 px Rand je Seite,
  der Hero-Text nutzte 32 % der Breite, und das Bildschirmfoto lag unter der
  Falz. Jetzt 76rem und ab 68rem zwei Spalten.
- **Der README beschrieb das Handbuch von vorgestern** („achtzehn Seiten:
  sieben geschriebene, elf erzeugte" statt 33 aus 18 und 15).
- **Die Bildschirmfotos zeigten behobene Fehler** — fünf UI-Commits lagen
  zwischen Aufnahme und heute. Dabei fiel auf, dass die Prüfbericht-Karte
  weiterhin nicht wächst, wenn Befunde **nach** der Auswertung dazukommen:
  ein `QListWidget` meldet sein Wachstum nicht, und die Karte hängt in
  keinem Layout, das es weiterreichen könnte (`contentGrew` → `reflow`).

### Neu

- **`EULA.md`, `AGB.md`, `WIDERRUF.md`.** Die Seite nennt seit ihrer
  Entstehung 49 €; es gab weder Endnutzer-Lizenzvertrag noch AGB noch
  Widerrufsbelehrung — die letzten beiden sind bei einem Verkauf an
  Verbraucher Pflicht. `tools/make_legal.py` macht daraus die Website-Seiten
  und die Lizenzseite des Installers, der bis dahin die Urheberrechtsnotiz
  zeigte. Der Entwurfshinweis hängt an den Platzhaltern und verschwindet von
  selbst, sobald sie ersetzt sind; `tests/test_legal.py` lässt keine Seite
  durch, die einen trägt und schweigt.
- **Auszeichnung für beide Startseiten und das Handbuch**: canonical,
  hreflang, Open Graph, JSON-LD. Geteilt wurden sie bis hierhin als nackte
  Links.

### Offen

- [x] **Der Zahlungsdienstleister ist entschieden: Paddle.** Als *Merchant of
      Record* wird er selbst Vertragspartner des Kaufs und trägt die
      Umsatzsteuer — § 4 der AGB war auf genau diesen Fall geschrieben und
      nennt ihn jetzt beim Namen: Paddle.com Market Limited, 30 Old Bailey,
      London EC4M 7AU (Companies House 08172165; die Anschrift hat am
      07.07.2026 gewechselt, die alte in Mora Street steht noch überall im
      Netz). Die Datenschutzerklärung hat dazu einen eigenen Abschnitt
      bekommen: sie schwieg zum Kauf, obwohl dort die einzigen
      personenbezogenen Daten anfallen, die es überhaupt gibt — samt dem
      Angemessenheitsbeschluss für das Vereinigte Königreich.
- **Die Rechtstexte fachlich prüfen lassen.** Sie sind sorgfältige Entwürfe
  und keine Rechtsberatung. Der Entwurfshinweis hing bis hierhin am
  Platzhalter, und mit Paddle wäre er gefallen: ein ungeprüfter Vertrag hätte
  ohne jeden Vorbehalt dagestanden. Er hängt jetzt an
  `make_legal.REVIEW_PENDING` und fällt erst, wenn die Prüfung stattgefunden
  hat — `tests/test_legal.py` hält das fest.

  **Was der Prüfung vorzulegen ist**, gesammelt statt „einmal drübersehen":

  1. **Die Rolle zieht weiter als § 4.** Ist Paddle Merchant of Record, ist
     Paddle der Verkäufer — und §§ 3, 5, 6 und 7 der AGB sind auf einen
     Direktvertrag geschrieben („Der Vertrag kommt zustande, wenn **wir** die
     Bestellung annehmen"). Zu klären, welche Teile für die Softwarenutzung
     bleiben und welche Paddles Bedingungen überlassen werden.
  2. **Paddles Rückgaberegel nennt sieben Tage** für digitale Inhalte, die
     Widerrufsbelehrung vierzehn. Beides kann nebeneinander richtig sein —
     nachgeprüft ist es nicht.
  3. **§ 356 Abs. 5 BGB im Bestellvorgang.** Die Belehrung wirkt nur, wenn
     Zustimmung *und* Kenntnisnahme dort abgefragt und auf dauerhaftem
     Datenträger bestätigt werden. Paddles Checkout kennt den Fall (Art. 16
     lit. m der Verbraucherrechte-Richtlinie); dass er für diesen Shop
     eingeschaltet und deutsch formuliert ist, muss beim Einrichten geprüft
     werden.
  4. **Der Testlauf von vierzehn Tagen** steht neben dem Widerrufsrecht und
     soll es nicht ersetzen — § 6 sagt das ausdrücklich, und genau dieser Satz
     gehört gelesen.

### Dritter Durchgang, gleicher Tag

Nochmal durchgesehen, diesmal gegen den Stand nach der Überarbeitung der
Startseite. Acht Funde, alle behoben:

- **Der Markenname stand mit Lücke da.** `.brand` ist ein Flex-Container mit
  `gap`, und in einem Flex-Container wird jeder Textknoten ein eigenes
  Element — „Solidon" und `<span>3D</span>` waren zwei davon. In der
  Kopfzeile stand deshalb „Solidon 3D", gegen Fenstertitel, Domain und
  `branding.py`. Der Abstand gehört an das Symbol, nicht zwischen die Silben.
- **„14 Tage Widerrufsrecht" widersprach der eigenen Belehrung.** Bei
  digitalen Inhalten erlischt es vorzeitig, wenn der Käufer der sofortigen
  Ausführung zustimmt — die Zusage stand ohne diesen Vorbehalt auf der Seite,
  die den Preis nennt.
- **Der Lizenzvertrag war strenger als das Programm.** §4 sagte, nach der
  Frist brauche man einen Schlüssel zum Weiterarbeiten. Die Grenze in
  `app/core/activation` verläuft anders: was liest, bleibt frei — Solidon
  ist danach ein vollständiger Betrachter der eigenen Projekte.
- **Die englische Seite verlinkte unangekündigt auf deutsche Verträge.**
  Jetzt steht der Hinweis oben auf allen drei Seiten, auf Englisch.
- **Zwei Konzepte sagten „Entwurf", während die ROADMAP sie abhakte** — P15
  und die Live-Durchsicht gegen Fusion.
- **Das Veröffentlichungskonzept nannte `app/core/licence/`**; gebaut wurde
  `app/core/activation/`.
- **Zwei Handbuch-PDFs unter dem alten Markennamen** lagen im
  Releases-Ordner. Entfernt.
- **Ein Repository-Pfad stand im Endnutzervertrag.** Der Käufer sieht
  `app/core/knowledge/parts/` nie; jetzt stehen dort Mutternfalle, Gewinde
  und Filmscharnier.

**Geprüft und in Ordnung:** alle 77 Operationen mit Erklärsatz, jeder
Parameter mit Beschreibung, kein englischer Rest, keine Vorgabe außerhalb
ihres Bereichs · das Register vollständig übersetzt · zehn Kontrastpaare in
beiden Themen über WCAG AA · `prefers-reduced-motion` schaltet alles ab ·
die sechs Zahlen der Startseite testgedeckt · beide PDFs mit richtigem
Deckblatt.

**Weiterhin offen und nicht von hier zu lösen:** die fachliche Prüfung der
Rechtstexte — was ihr vorzulegen ist, steht oben unter „Offen" als vier
benannte Fragen. Die beiden anderen Punkte, die hier standen, sind seit dem
08.08.2026 erledigt: die vier Grenzstellen rufen `require()`, ein
abgelaufener Testlauf sperrt die schreibende Seite (siehe „Die Lizenzgrenze
greift" weiter unten), und der Zahlungsdienstleister steht mit vollständiger
Firmierung in den AGB.

## Die Lizenzgrenze greift (08.08.2026)

V4, V4b und V4c aus dem Veröffentlichungskonzept in einem Zug; der Stand je
Paket steht in `konzepte/konzept-veroeffentlichung-1.0.md` §9.

- **V4 — die Grenze im Datenpfad.** `History.apply`, `write_plan`,
  `write_assembly`, `slice_model` und `AgentSession.propose` rufen
  `activation.require()`; was liest, bleibt frei. Fall für Fall in
  `tests/test_licence_boundary.py`. Dazu `integrity.py` (H4): beim ersten
  Zustandsabruf werden die vier Grenzdateien gegen das signierte Manifest
  geprüft — in der Entwicklung prüft es nichts, der Schlüssel dafür entsteht
  je Bau.
- **Der echte öffentliche Schlüssel steht in `key.py`.** Der private Teil
  liegt außerhalb des Repositorys (§8: Passwortmanager und Papier); der
  Rundlauf erzeugen→prüfen ist gegen den eingebauten Schlüssel belegt.
- **V4b — die Oberfläche.** Schreibende Einträge grauen mit Grund im
  Hinweistext aus, der Chat sagt es in einer Zeile mit Freischalten-Knopf,
  Statuszeile unter drei Resttagen, „Lizenziert für …" im Über-Dialog, ein
  Satz zum Testlauf in der Ersteinrichtung.
- **V4c — kompilierte Auslieferung, am Paket belegt.**
  `tools/build_licence_module.py` übersetzt das Prüfmodul mit Cython und
  signiert das Manifest mit einem je Bau frischen Paar; die Spec nimmt die
  Erweiterungen statt des Bytecodes und legt die vier Grenzdateien als
  Quelltext, `build.yml` ruft das Werkzeug vor dem Paketieren
  (`tests/test_licence_build.py` hält Spec, Werkzeug und CI zusammen).
  Ein vollständiger lokaler PyInstaller-Bau hat es bewiesen: kein
  `activation`-Python im Ordner oder PYZ, das Manifest deckt die vier
  Grenzdateien, die Anwendung startet aus dem Paket — und mit einem von
  Hand veränderten `writer.py` startet sie gesperrt (kein Testlaufmarker
  entsteht). Der Compiler steckt übrigens in Visual Studio 18; setuptools
  findet ihn dort nicht von allein — der Weg über `vcvars64.bat` steht im
  Docstring des Werkzeugs.

## Gizmo und Direktmanipulation durchgesehen (08.08.2026)

Anlass war die Frage, ob §18.11 hält, was der Bauplan verspricht. Die
Antwort: die Zerlegung eines Zugs in Operationen war richtig und getestet —
aber das Widget darüber hatte einen Lebenszyklus, den kein Test je angefasst
hat. Die Gizmo-Tests prüften reine Funktionen: Beschriftung, Größe,
Zerlegung. Das Widget selbst, sein Anhängen und Abnehmen, prüfte niemand.

### Was falsch war und jetzt stimmt

- **Der Gizmo ließ sich einschalten, aber nie abschalten.** `set_gizmo` rief
  `Off()` auf einem `AffineWidget3D` — eine Methode, die es dort nicht gibt
  (die API hat `remove()`, `disable()`, `enable()`). Der `AttributeError`
  verschwand in Qts Slot-Behandlung: der Griff blieb stehen, obwohl der
  Schalter aus war, und mit ihm Beschriftung und Flächenscheibe.
- **Nach jedem Zug hing der Griff an einem toten Actor.** Ein Zug erzeugt
  Operationen, die Auswertung baut alle Actors neu — und niemand hängte den
  Griff um. Schlimmer: pyvistas Widget merkt sich die Matrix über Züge
  hinweg, der zweite Zug hätte den ersten also noch einmal angewandt. Jetzt
  wird der Griff nach jedem Loslassen und bei jedem Szenenaufbau frisch
  angehängt — mit leerer Matrix, am aktuellen Actor.
- **Ein Zug unter der Fangschwelle hinterließ ein Bild ohne Szene.** 0,4 mm
  bei 1 mm Raster ergibt zu Recht keine Operation — aber das Widget hatte
  den Körper im Bild längst verschoben, und nichts stellte ihn zurück.
- **Der Griff folgte der Auswahl nicht.** Wer bei aktivem Gizmo ein anderes
  Objekt oder eine Fläche wählte, behielt den Griff am vorigen Ziel; das
  Versprechen „gewählte Fläche bekommt den Griff auf die Fläche" galt nur im
  Moment des Einschaltens. Jetzt wandert er mit — und eine leere Szene nimmt
  den Griff weg, aber nicht die Entscheidung, dass einer gewünscht ist.
- **Das Handbuch kannte weder Bewegen noch Bemalen.** Achtzehn Seiten, und
  die zwei Werkzeuge der Leiste, die das Modell wirklich ändern, kamen in
  keiner vor — „Hinsehen" beschreibt ausdrücklich nur die fünf, die nichts
  ändern. Neue Seite „Bewegen und Bemalen" dazwischen: Griff, Fang,
  Flächenzug, was der Griff absichtlich nicht kann, Pinsel und
  Filamentwechsel. Beide Sprachen, Website und PDFs neu erzeugt.

### Offen, mit Absicht festgehalten

- **Skalieren am Griff gibt es nicht.** §18.11 nennt es; pyvistas Widget
  kann nur Verschieben und Drehen. Der Weg über *Skalieren* und *Auf Maß
  bringen* deckt den Bedarf, das Handbuch sagt das jetzt ehrlich — aber es
  bleibt eine Abweichung vom Bauplan, keine Erfüllung.
- **Zahleneingabe während des Ziehens fehlt.** §18.11 verspricht sie; heute
  gibt es Zahlen nur vorher (Dialog) oder nachher (Verlauf). Wäre der
  nächste Schritt, wenn die Direktmanipulation wieder drankommt.
- **Die Achsbuchstaben wandern beim Ziehen nicht mit.** Sie sitzen nach
  jedem Zug wieder richtig (das Neuanhängen nimmt sie mit), aber während
  des Zugs bleiben sie stehen. Kosmetisch, nicht falsch.

### Nachgezogen, gleiche Sitzung

Die drei offenen Punkte der Gizmo-Durchsicht sind keine mehr, und beim
Abarbeiten kam ein vierter Fund dazu:

- **Skalieren am Griff gibt es jetzt** — ein Würfel auf der Raumdiagonale,
  beschriftet mit S, Interaktion pyvistas Widget nachgebaut
  (`app/ui/scale_widget.py`). Ziehen skaliert live um die Mitte, das
  Loslassen wird eine `scale_object`-Operation, der Faktor ist gegen
  Ausrutscher eingespannt. Achsweise bleibt Sache des Dialogs.
- **Zahleneingabe während des Ziehens gibt es jetzt** — die Zahl zum Zug
  steht über dem Bild, die erste Ziffer übernimmt den Zug, die
  Eingabetaste wendet genau den getippten Wert an (ohne Fang), Esc
  verwirft. Gilt für Pfeile, Ringe, Flächengriff und Würfel.
- **Die Achsbuchstaben reisen mit** — die Beschriftung hängt an einem
  lebenden PolyData, jedes Move-Ereignis versetzt die Punkte um die
  Matrix des Zugs.
- **Der vierte Fund:** pyvistas Widget stellt beim Loslassen *seinen*
  Trackball-Stil wieder her, nicht unseren — nach dem ersten Zug waren
  Auswahl-Klick, Kontextmenü und das Navigationsschema weg, und kein Test
  sah es, weil keiner je einen Zug zu Ende fuhr. Jetzt holt jedes
  Zugende den eigenen Stil zurück.

Handbuchseite „Bewegen und Bemalen" entsprechend fortgeschrieben, beide
Sprachen, Website und PDFs neu erzeugt. §18.11 ist damit vollständig:
Verschieben, Drehen, Skalieren, Raster- und Winkelfang, Zahleneingabe
während des Ziehens — und der Fang auf Fläche und Bohrungsachse über
`align_to_feature`, wie seit P3.

## Der Schatten im Viewport durchgesehen (08.08.2026)

Anlass war ein Satz ohne Fehlermeldung: „irgendwie sieht das komisch aus."
Nachgemessen an der laufenden Anwendung, mit Kamerastellungen statt mit
Eindrücken — und der Eindruck stimmte, aus einem Grund, den kein Test hätte
finden können, weil keiner die Kamera kannte.

### Was falsch war und jetzt stimmt

- **Der Schatten fiel auf den Betrachter zu.** `SHADOW_DIRECTION` war eine
  feste Weltrichtung (0,35 / 0,45), begründet mit „nach hinten rechts, weil
  die Standardansicht von vorn links kommt — so tritt der Schatten hinter dem
  Teil hervor statt davor, wo er die Sicht auf die Vorderkante nähme". Kein
  Teil dieses Satzes stimmte. Gemessen als Anteil an der Blickrichtung:
  Startansicht **−0,81** (also 0,81 nach vorn), eigene Iso +0,11. Jetzt in
  jeder Ansicht +0,95.
- **Der Grund lag tiefer als die Zahl.** Die Anwendung setzt kein eigenes
  Licht; pyvistas Lichtsatz hängt an der Kamera. Ein Körper ist damit in jeder
  Ansicht von vorn beleuchtet — und eine feste Weltrichtung für den Schatten
  passt deshalb zu **keinem** Blickwinkel, nicht nur zu einem falschen. Die
  Richtung folgt jetzt der Kamera (`shadow_direction`), nachgezogen bei jedem
  Ansichtswechsel und am Ende jeder Drehung. Der Beobachter hängt am
  Interactor und nicht am Interaktionsstil: den tauscht jeder Schemawechsel
  aus, und der Orientierungswürfel dreht an ihm vorbei.
- **Die Anwendung startete nicht in ihrer eigenen Ansicht.** `VIEW_DIRECTIONS`
  führt eine Iso-Vorgabe (1, −1, 0,8), gesetzt hat sie niemand — beim Start
  stand die Kamera auf pyvistas (1, 1, 1). Wer „Isometrisch" im Menü wählte,
  sprang also aus einer Ansicht in eine andere, obwohl er die zu sehen
  glaubte, in der er stand. Das war zugleich die Ursache dafür, dass die
  Richtung der Konstante gegen die falsche Ansicht gedacht war.
- **Der Umriss kostete zu viel und zu oft.** Er lief als Triangulierung über
  jeden Punkt des Anzeigenetzes, je Körper und Szenenaufbau, im
  Qt-Hauptthread: 5,2 ms bei dreitausend Dreiecken, 129 bei
  zweiundachtzigtausend, 528 bei dreihundertsiebenundzwanzigtausend. Jetzt
  steht die konvexe Hülle einmal je Körper, und ein Ansichtswechsel projiziert
  nur noch daraus.

| Körper | vorher | Aufbau | Ansichtswechsel | Abweichung |
|---|---|---|---|---|
| Quader, 3 072 Dreiecke | 5,2 ms | 1,8 ms | 0,65 ms | 0,000 mm |
| Kugel, 20 480 | 31,6 ms | 19,3 ms | 10,9 ms | 0,023 mm |
| Kugel, 81 920 | 128,8 ms | 21,7 ms | 11,2 ms | 0,028 mm |
| Kugel, 327 680 | 528,4 ms | 30,1 ms | 12,1 ms | 0,045 mm |

Der erste Anlauf war dabei ein Rückschritt und wurde als solcher gemessen: bei
einer feinen Kugel liegt **jeder** Punkt auf der Hülle, und die Rechnung kostete
59 ms statt 33. Die Hülle hat deshalb einen Kostendeckel
(`SHADOW_HULL_POINTS`) — eine Stichprobe, dazu die äußersten Punkte in
vierzehn Hauptrichtungen, damit ein kantiger Körper seine Ecken behält. Ein
Quader kommt dabei exakt heraus, eine Kugel auf fünf Hundertstel Millimeter.

### Was geprüft war und stimmte

- **Der Schatten löscht das Bettraster nicht aus.** Der erste Eindruck sagte
  das Gegenteil; nachgemessen an der Streuung im Bild (3,50 im Schatten gegen
  4,89 daneben, bei 0,35 Deckkraft) scheint es korrekt gedämpft durch.

### Die beiden offenen Punkte sind zu

- [x] **Steht ein Körper auf einem anderen, löst sich sein Schatten ab.** Er
      wurde immer auf die Platte geworfen, nie auf den Körper darunter. Ein
      Turm auf einer 12 mm hohen Platte hatte einen Schatten, der erst neben
      ihr auftauchte — ein Fleck ohne Verbindung zu dem, was ihn wirft.
      `_shadow_catchers` sucht jetzt zu jedem Körper die Flächen unter ihm, und
      `shadow_points` misst die Höhe ab der auffangenden Fläche statt ab null.
- [x] **Außerhalb der Platte fiel er ins Nichts.** Bei aufgezogener Explosion
      oder einem Körper weit vom Ursprung lag der dunkle Umriss auf blankem
      Hintergrund, ohne Fläche darunter. Der Schnitt gegen den Plattenrand ist
      gebaut (`clip_polygon`, Sutherland-Hodgman) und trägt beide Punkte: jedes
      Schattenstück wird am Umriss seiner Fläche beschnitten. Damit verdeckt
      eine Grundplatte genau den Teil des Plattenschattens, der sonst doppelt
      läge — die beiden Stücke überlappen sich nirgends sichtbar.

Der Umriss ist dabei von `delaunay_2d` auf die ebene konvexe Hülle
umgestellt (`outline_of`): beschneiden lässt sich ein Rand, keine Menge von
Dreiecken — und die Hülle ist zugleich billiger.

## Drei Meldungen aus der Bedienung (08.08.2026)

Robert meldete drei Dinge aus dem laufenden Gebrauch: die linke Spalte sei
beim Einklappen „recht buggy, wird abgeschnitten, zeigt die Hälfte", die
Schichtanalyse hänge an einer texturierten Fläche sehr, und auf dem
Startbildschirm stehe eine Menüleiste, deren meiste Einträge dort nichts tun.
Alle drei sind zu, und jede hatte einen messbaren Grund.

- **Die linke Spalte rechnete sich um zweihundert Pixel zu kurz.**
  `natural_height` zog für jede sichtbare Liste deren *rohe* Qt-Wunschhöhe ab
  — pauschal 192 Pixel, egal wie hoch die Liste wirklich ist. Die Listen der
  Spalte stehen aber per `fit_to_rows` auf festen Höhen weit darunter, und
  das Layout rechnet mit der geklemmten Zahl. Offscreen nachgemessen: die
  Zone bekam 159 Pixel für 371 Pixel Inhalt — Parameter und Verlauf hingen
  unterhalb der Kartenkante, und genau das sah man als „zeigt die Hälfte".
  Solange die Spalte voller ist als das Fenster hoch, deckelt `room` den
  Fehler zu; er wurde sichtbar, sobald Einklappen den Inhalt unter die
  Fensterhöhe brachte. Abgezogen wird jetzt der geklemmte Beitrag. Dazu
  wächst die Rundeck-Maske während der Bewegung mit statt erst am Ziel —
  eine unterwegs ersetzte Animation ließ sie sonst dauerhaft zu klein stehen,
  denn `stop()` sendet kein `finished`.
- **Die Schichtanalyse stand an der Textur aus drei Gründen zugleich.**
  Gemessen an einer 60×40-Platte mit feinem Rändel (46 000 Dreiecke, 2 898
  Ringe je Schicht in der Texturzone):
  1. `_polygon_from` stellte die Verschachtelungsfrage — wer ist Loch von
     wem — als n² einzelne `contains`-Aufrufe: 16,8 Millionen Stück, 63 von
     66 Sekunden des ganzen Laufs. Über `STRtree` sind es dieselben Paare in
     Millisekunden; `slice_body` fiel von 37 auf 4 Sekunden, bei
     unveränderten Kennzahlen. Der Fall steht als Budget in
     `test_performance.py`: viele Konturen sind der Härtefall, nicht viele
     Dreiecke.
  2. Jeder Schieberschritt startete einen **weiteren** Arbeiter, solange der
     erste noch rechnete — dreißig Schritte, dreißig parallele Läufe.
     `_slice_of` führt jetzt eine Warteschlange je Schlüssel: ein Arbeiter je
     Körper, wer das Ergebnis will, stellt sich an, die Schichtansicht nur
     einmal. Ein abgelöster Arbeiter wird beim Eintreffen verworfen, und eine
     neue Auswertung löst den laufenden ab — sein Schlüssel (Objekt und
     Dreieckszahl) überlebt eine Verschiebung, sein Ergebnis nicht.
  3. Der Viewport schnitt bei jedem Schritt die Körper an der neuen Höhe —
     ein echter `cut()` mit Deckel, an der Rändelplatte rund eine Sekunde,
     im Qt-Hauptthread, und zeichnete dazu je Ring einen eigenen
     `add_lines`-Actor, an einer Rändelschicht 2 898 Stück. Beim Fahren
     folgen jetzt nur noch die Konturen (ein Actor je Rolle); der
     Körperschnitt kommt nach 200 ms Ruhe (`LAYER_REBUILD_DELAY_MS`), bis
     dahin bleibt die letzte Darstellung stehen (§2.8).
- **Der Startbildschirm zeigt nur noch Menüs, die dort etwas tun.**
  Bearbeiten, die Operationsgruppen und Ansicht setzen eine offene Szene
  voraus und verschwinden mit ihr (§2.6); Datei und Hilfe bleiben, denn
  Öffnen, Beenden, Handbuch und Freischalten sind genau dort sinnvoll. Die
  Kürzel bleiben gültig — Qt registriert sie am Fenster, nicht an der
  Sichtbarkeit des Menüs.

## Agent und Chat vertiefen (08.08.2026) — Konzept steht

Aus einer vollständigen Gegenüberstellung von Ist (`app/core/agent/`,
`app/ui/chat.py`, Backends) und Soll (Bauplan, diese Liste):
**`konzepte/konzept-agent-vertiefung.md`** im Projektwurzelverzeichnis. Der Befund in
einem Satz: der Unterbau ist richtig, aber der Agent arbeitet halbblind
(keine Feature-IDs nach einer Op, keine Passungen, keine Analysen, keine
Ansichten nach §23), erreicht die Hebel der Menüs nicht (Druckeinstellungen,
Projektdrucker, Grundform-Skizzen nach §30.1), und der Nutzer sieht von
alldem nur einen endlosen Balken.

Sechs Schritte, jeder einzeln lieferbar, Abnahmekriterien je Schritt im
Konzept:

- [x] **0 — Messgrundlage:** Suite-Basislinie mit vollem Fenster steht
      (17/33, gemessen von der parallelen Durchsicht — siehe oben), die
      `invalid`-Kennzahl zählt jetzt wirklich (Vorschlag führt `tool_calls`
      und `invalid_calls`, der Läufer weist die Quote aus), das stabile
      Präfix aus Systemprompt und Werkzeugschemata liegt per `cache_control`
      im Zwischenspeicher, `max_tokens` ist ein Parameter (8192) und das
      Zugbudget deckelt jede Antwort.
- [x] **1 — Wahrnehmung Text:** Op-Ergebnisse nennen die neuen Merkmale mit
      IDs, `read_digest` liest den Steckbrief der Arbeitskopie mitten im
      Zug, der Steckbrief führt Passungen (mit Verletzt-Zustand),
      Druckeinstellungen, Quellen und den Verlauf mit den gesetzten Werten,
      `read_standard` schlägt die Normteiltabelle nach, und ein gedeckelter
      Chatverlauf sagt, wie viele ältere Beiträge fehlen. Beide neuen
      Werkzeuge auch über die Fernsteuerung.

      **Zwei Kernfehler dabei freigelegt, beide zu.** Ein gebohrtes Loch
      wurde nie ein Merkmal: sortiert sich die neue Bohrung in der Erkennung
      vor die bestehenden, rutschen deren Nummern, und in `apply_mapping`
      überschrieb das unzugeordnete neue Merkmal einen Überlebenden — eines
      von beiden verschwand wortlos aus der Szene. Unzugeordnete Merkmale
      bekommen jetzt eine frische ID, verwaiste Namen bleiben gesperrt. Und
      der zweite lag darunter, kaschiert von der stillen Wiederverwendung:
      nach einer 25°-Drehung liest die Erkennung Zylinderachsen mal als
      `+v`, mal als `-v`, und der vorzeichenempfindliche Vergleich in `cost`
      verwaiste die Hälfte der Löcher. Eine Bohrungsachse ist eine Linie,
      keine Richtung — verglichen wird jetzt das Minimum beider Vorzeichen;
      Flächennormalen behalten ihres, innen ist nicht außen
      (`tests/test_matching.py` hält beide Fälle fest).
- [x] **2 — Sichtbarkeit:** Die Sitzung meldet je Schritt, was läuft
      (Rückruf wie `ask`, kein Qt im Kern), die Statuszeile zeigt
      „Schritt 3/8 — Bohrung setzen" statt nur „Der Agent denkt nach.";
      die Entscheidungszeile nennt Schritte, Token und die Rückfragen samt
      Antworten (aufklappbar), eine erreichte Grenze steht ausgeschrieben
      da. §2.6 ist eingelöst: jede Werkzeugbeschreibung trägt ihren
      Menüort (die Zuordnung Kategorie → Menü lebt dafür im Register,
      die Oberfläche leitet weiter), Prompt-Version 3 verlangt, ihn bei
      Wie-Fragen zu nennen. Die Suite-Messung der Promptänderung steht
      gesammelt mit den neuen Fällen aus Schritt 3 an.
- [x] **3 — Handlungsraum:** `read_analysis` liest Druckbarkeit (Überhang,
      Inseln, Brücken, Stützvolumen), Zeit- und Materialschätzung,
      Einstellungsrat und Orientierungssuche — Herkunft je Antwort
      ausgewiesen (Regel 14), harter Dreiecksdeckel statt Zeitgewalt, die
      Orientierungssuche mit festem Startwert und kleiner Kandidatenzahl.
      `set_print_target` wechselt Drucker/Material als `DocumentChange` in
      der einen Transaktion — Undo stellt beide wieder her. **Eine
      Konzeptkorrektur dabei:** `set_print_setting` wird nicht gebaut —
      Einstellungen reisen nicht in Transaktionen (§15.5), und §28.2 sagt
      „Übernommen wird auf Klick"; der Agent liest die `advise`-Vorschläge
      und nennt sie samt Grund (Begründung in Konzept 5.1 und §26.2). Die
      Suite wächst auf **39 Fälle** (nachsehen statt raten, Druckziel,
      Menüort — gemessen über `proposal.readings`), §35 und die
      Testarten-Tabellen sind fortgeschrieben.
- [x] **4 — Augen und Autopilot:** Die gerenderten Ansichten aus §23
      erreichen den Agenten — zwei beschriftete PNG (schräg oben, von
      oben), offscreen gerendert von der Oberfläche (`app/ui/snapshots.py`;
      der Kern rastert nicht, seine Projektion ist SVG — Konzept 3.5
      entsprechend korrigiert). Nur ein Backend mit `supports_images`
      bekommt sie; Ollama bleibt fest ohne, bis ein Vision-Modell gemessen
      ist. Die automatische Übernahme (§26.5) läuft unter vier Bedingungen
      (`agent_apply.auto_acceptable`: nur umkehrbare Ops, kein
      `create_from_scad`, keine Warnungen, keine Rückfrage/kein Abbruch),
      die Leiste wird zur Übernommen-Leiste mit Rückgängig-Knopf, und die
      Einstellung `auto_accept_reversible` (Vorgabe: an) schaltet sie ab.
- [x] **5 — Grundform-Skizzen:** aufgelöst statt gebaut — der Weg
      existierte seit P13. Die Ist-Aufnahme sah die `sketch`-Sperre und
      übersah die Grundform-Parameter daneben; die vier Skizzenfälle waren
      nie strukturell ungewinnbar. Was fehlte, war der Beweis, und der
      steht jetzt als Test: die geratene Punktliste wird abgelehnt und
      zählt als ungültig, dieselbe Op läuft über `shape` durch, und jede
      erwartete Op bietet die Formen an (Konzept 5.3 trägt die Korrektur
      samt Lehre: eine Aussage ohne §-Beleg ist eine Vermutung, auch die
      eigene).

Begleitend: die doppelt implementierten Zusatzwerkzeuge aus
`main_window.run_remote` auf eine gemeinsame Werkzeuglogik zusammenziehen,
bevor Schritt 3 neue Werkzeuge anlegt. Bewusst nicht im Handlungsraum:
Export/Slicer-Start und Redo — Begründung in Konzept-Abschnitt 5.4.

**Die Nachher-Messung (08.08.2026, 39 Anfragen, `qwen3:14b`, volles
Fenster)** — gegen die Basislinie vom Mittag:

| Maß | vorher (33 Fälle) | nachher (39 Fälle) |
|---|---|---|
| gut beantwortet | 17/33 (52 %) | **28/39 (72 %)** — auf den 33 alten Fällen 25/33 (76 %) |
| bei Mehrdeutigkeit gefragt (§40) | **1/3** | **3/3** — die Kehrseite des Kontextfenster-Fundes ist geheilt |
| schemagültig im ersten Versuch | nie gemessen | **156/160 = 98 %** (Ziel 95 %, erstmals gemessen, erfüllt) |
| Baustein statt eigener Geometrie | 6/13 | 7/13 |
| Hauptmaße als Parameter | 2/3 | 2/3 |
| Zeitüberschreitungen | 2 | 1 |

Prompt-Version 3, die vollständige Werkzeugliste (86 Schemata samt
Menüort) und der größere Steckbrief passen weiter ins 32768er-Fenster —
die Quote wäre sonst eingebrochen statt gestiegen. Zwei der vier
Skizzenfälle (`hex_base`, `handrail_bend`) sind jetzt gewonnen,
`how_long` und `core_hole` wurden wirklich **nachgesehen** (gemessen über
`proposal.readings`), und `switch_material` setzt das Druckziel um.

Was `qwen3:14b` liegen lässt, hat ein Muster: die reinen
Auskunftsfälle verführen es zum Handeln (`where_menu` bohrte viermal,
statt den Menüort zu nennen; `printable` ordnete an, statt zu
analysieren). Das ist Stoff für die Regelsammlung oder den Prompt —
eine Regeländerung mit Messung vorher/nachher, nicht für heute
nebenbei. Gegen Anthropic ist die Suite noch nicht gefahren (kein
Schlüssel hinterlegt); der Lauf steht aus, sobald einer da ist.

## Die Agent-Vertiefung durchgesehen und behoben (09.08.2026)

Zwei Reviewer über die zwölf Commits, gegen die 22 Regeln und den Bauplan —
über vierzig Funde, alle behoben oder begründet vertagt. Die vier schweren:

- **Der Rückgängig-Knopf der Übernommen-Leiste nahm die falsche Transaktion
  zurück.** `History.undo` kennt nur „die oberste"; lag inzwischen etwas
  anderes obenauf, zerstörte der Knopf fremde Arbeit und ließ die
  versprochene stehen — und die Leiste überlebte sogar den Projektwechsel.
  Sie hängt jetzt am Dokument (`_refresh_applied_bar`), der Knopf prüft
  selbst und sagt sonst an, statt zu löschen.
- **VTK rendert nie wieder im Arbeiter-Thread.** Die Ansichten entstehen in
  `propose_async` im Hauptthread, der Arbeiter liest nur Bytes — die
  Absturzfamilie aus dem Projektgedächtnis bekommt keinen dritten Fall.
- **Ein Zug aus Druckziel und Rücknahme war unannehmbar.** Die
  Misch-Schranke kannte `print_target` nicht; jetzt tragen alle drei
  Stellen dieselbe Bedingung (`Proposal.creates_something`).
- **Der genannte Menüort stimmte für 72 von 77 Operationen nicht** — es
  fehlten die Untermenü-Ebenen. `menu_path` im Register baut den vollen
  Weg, und ein Test hält ihn Ebene für Ebene an der wirklich gebauten
  Leiste fest.

Dazu die Auskunftsfunde (Herkunftszeile je Analyseart statt einer für alle,
die Kurzsuche rechnet auf derselben Skala wie die Op, Profil zieht beim
Druckzielwechsel mit, unbekannte Objekt-IDs werden benannt und gezählt),
die Fernsteuerung trägt jetzt bei allen schreibenden Zusatzwerkzeugen den
Herkunftsvermerk und behauptet keinen Erfolg mehr, den es nicht gab, die
Orientierungssuche ist dort abgelehnt, bis sie einen Arbeiter hat (5,3 s im
Hauptthread, gemessen), reine Auskunftszüge bekommen keine
Übernehmen/Verwerfen-Leiste über „Keine Änderung" mehr, und drei
Zusicherungen der Tests waren offscreen Tautologien (`isVisible` →
`isVisibleTo`). Ein gemeinsamer Topf in `new_feature_lines` verschluckte
neue Merkmale auf einem zweiten Körper — je Objekt verglichen, mit Test.

Vertagt mit Begründung: die Orientierungssuche der Fernsteuerung in einen
Arbeiter legen; die englischen Bestands-Docstrings in fünf berührten
Dateien (nicht aus diesem Diff — CLAUDE.md verspricht mehr, als der
Bestand hält, eine der beiden Seiten gehört nachgezogen).

## Der Erzeugen-Einstieg, aufgeräumt (09.08.2026)

Roberts Beobachtung aus der Bedienung: das Zeichnen liegt zu tief, und im
Menü stehen zu viele ähnliche Einträge. Beides behoben:

- **„Zeichnen" steht jetzt oben neben „Modell einfügen".** Die
  Hauptwege-Tabelle nannte die Werkzeugzeile seit je als Ort für Weg 2 —
  belegt war er nie. Der Knopf startet den Skizzenmodus ohne festgelegte
  Operation; bei „Fertig" fragt ein Dialog, was aus der Skizze wird (die
  fünf Arten aus dem Register, mit der Zeichnung vor Augen statt vorab aus
  fünf Menüeinträgen). „Zurück zum Zeichnen" vernichtet nichts — es öffnet
  den Modus mit derselben Zeichnung wieder. Die fünf Menüeinträge bleiben
  als Direktwege.
- **Die Mesh/B-Rep-Zwillinge sind zusammengelegt.** „Quader anlegen" und
  „Exakten Quader anlegen" waren zwei Einträge für einen Quader (Zylinder
  ebenso). Jetzt: ein Eintrag, „Exakt (B-Rep)" als Umschalter hinten im
  Dialog, die Parameter gefiltert auf das Schema des gewählten Kerns, die
  Live-Vorschau wechselt mit. `MENU_TWINS` im Register hält die Zuordnung —
  auch `menu_path` und damit der Menüort, den der Agent nennt, sagen den
  Umschalter dazu. Beide Ops bleiben im Register, in der Palette und im
  Verlauf. Die Zusicherung „genau ein Menüeintrag je Operation" heißt jetzt
  „höchstens einer, und jede bleibt erreichbar" (Grenzen-Tabelle in
  `.claude/rules/oberflaeche.md` nachgezogen).

## Nachgesehen, was davon stimmt (09.08.2026)

Die Oberfläche von Hand durchgefahren — Werkzeugzeile, freies Zeichnen samt
Rückweg, beide Zwillingsdialoge, Weg 1 von der Datei bis zur Schichtanalyse —
und dabei drei Stellen gefunden, an denen der Bau seinem eigenen Text
hinterherhinkte:

- **„Gefiltert auf das Schema des gewählten Kerns" galt für die Werte, nicht
  für die Felder.** Bezugspunkt (Quader) und Segmentzahl (Zylinder) standen
  weiter da, wenn „Exakt" angekreuzt war — in derselben aufgeklappten Gruppe
  wie der Umschalter, also genau dort, wo jeder vorbeikommt, der ihn sucht.
  Auf „Ecke" gestellt kam ein mittiger Quader, ohne einen Ton dazu.
  `OperationDialog.switch_variant` blendet die Zeile jetzt aus und tauscht die
  Beschreibung mit (die des Netz-Quaders nennt eine Wahl, die es exakt nicht
  gibt).
- **Die Skizzenleiste sagte „die Operation öffnet auf der Skizze"**, auch beim
  freien Zeichnen, wo keine gewählt ist. Beide Texte — Leiste und Statuszeile
  — unterscheiden die zwei Wege jetzt.

Was die Durchsicht **bestätigt** hat: die vier Funde vom 05.08. sind zu.
`Solid.bounds` misst 40 × 30 × 10 und Ø 6 wie Ø 120 auf neun Stellen exakt
(`AddOptimal_s`), die Slicer-Übergabe schickt `--arrange 0`, `drill` verankert
am Mund der Bohrung, und gepickt wird mit `vtkCellPicker`. Die Suite läuft
grün (3393), Lint und Typprüfung ebenso; der Abriss im Lauf am Stück ist
weiter der bekannte native, kein Testfehler.

## Alle Operationen und die fremden Programme aus Kundensicht (09.08.2026)

Jede der 77 registrierten Operationen einmal so gefahren, wie ein Kunde sie
startet: Menüeintrag, Dialog mit seiner Vorbelegung, bestätigen — 92 Läufe
über den echten Stapel, die kritischen davon noch einmal durch die laufende
Oberfläche. Dazu die vier fremden Programme mit den Installationen dieser
Maschine.

**73 Läufe liefen vollständig durch, 19 hielten an** — fünfzehn davon zu Recht
und mit einem Satz, der weiterhilft („Der gewählte Körper ist ein Netz. Exakte
Körper kommen aus einer STEP-Datei …"). Was übrig bleibt:

- [x] **Neu vernetzen zerstört das Netz und meldet, die Form sei unverändert.**
      Aus 12 Dreiecken werden 36 864, und der Quader ist danach nicht mehr
      geschlossen und zerfällt in drei Komponenten: `remesh` baut das Ergebnis
      von `subdivide_to_size` mit `process=False` zusammen, die Punkte werden
      also nie verschweißt. Der einzige Befund lautet „Das Netz wurde feiner
      unterteilt; die Form ist unverändert" — geprüft hat das niemand.
      Die Folge ist gemessen: die nächste Differenz fällt auf die Voxelstufe,
      und aus 40 × 30 × 10 werden 40,18 × 30,39 × 10,20. Wer danach eine
      Passung baut, baut sie um bis zu vier Zehntel daneben.
- [x] **`split_plane` legt ein leeres Objekt an, wenn die Ebene nicht
      schneidet.** Der Dialog belegt `position = 0.0` vor, der Quader steht auf
      z = 0 — bestätigen ergibt „Quader A" mit 0 mm³ und null Dreiecken im
      Objektbaum, ohne einen Ton. Der Zwilling `split_pinned` hält bei
      derselben Lage mit „Diese Ebene teilt das Objekt nicht" an. Zwei
      Operationen, eine Lage, gegensätzliche Antwort.
- [x] **`create_from_scad` umgeht die Aufbereitung der Eingangsstufe.** Was
      OpenSCAD liefert, ist ein STL mit doppelten Punkten; über `load` wird es
      verschweißt und gemeldet („Doppelte Punkte wurden verschweißt"), über
      diesen Weg nicht. Ein Ø-12-Zylinder kommt als **252 lose Dreiecke** in
      die Szene, nicht geschlossen. Aufgefangen wird das erst von der
      Rückfallkette der nächsten Booleschen („gelang erst nach dem
      Verschweißen"); wer stattdessen exportiert, exportiert den Scherbenhaufen.
- [x] **`plug_hole` auf einem Körper ohne Bohrung tut nichts und sagt nichts.**
      Dieselbe Lage bei den Bausteinen meldet „Die Vereinigung hat nichts
      hinzugefügt — Position prüfen". Auch `repair` an einem gesunden Netz
      bleibt stumm.
- [x] **Sieben Operationen für exakte Körper sind bei einem Netz anklickbar.**
      Verrunden, Fase, Formschräge, Exakt aushöhlen, Fläche versetzen, In ein
      Netz umwandeln, Tasche schneiden. `_refresh_actions` fragt nur, wie viele
      Objekte gewählt sind, nie welcher Bauart sie sind — dabei steht
      `SceneObject.kind` daneben. Der Kunde füllt den Dialog aus und erfährt
      danach, dass die Operation hier nie ging.
- [x] **Leerer OpenSCAD-Quelltext meldet einen Übersetzungsfehler.** „OpenSCAD
      konnte den Quelltext nicht übersetzen" für ein leeres Feld; die
      Beschriftungs-Operationen sagen an derselben Stelle „Ohne Text gibt es
      nichts anzulegen".

### Die fremden Programme, alle vier real aufgerufen

| Programm | Stand |
|---|---|
| OpenSCAD 2021.01 | gefunden, Quelltextprüfung greift, Rendern in 0,2 s — aber siehe oben |
| PrusaSlicer 2.9.6 | Ende zu Ende: 21,0 min · 4,17 g · 1367 mm, mit 3MF wie mit STL |
| ElegooSlicer 1.5.3.4 | Ende zu Ende: 21,6 min · 4,88 g · 100 Schichten — **nur mit Pfaden** |
| CuraEngine 5.13.0 | **scheitert immer** über Solidons eigenen Weg |
| Ollama qwen3:14b | Chat Ende zu Ende in 71 s, Vorschlag als eine Transaktion |
| ComfyUI | nicht gestartet; `reachable()` meldet es sauber, nichts hängt |

- [x] **CuraEngine bekommt ein 3MF und kann keines lesen.** Der
      Druckeinstellungs-Dialog schreibt über `write_assembly` immer eine
      3MF-Baugruppe, unabhängig von `setup.flavour`, und `slice_model` reicht
      sie unverändert weiter. Derselbe Würfel als STL läuft durch (20,9 min,
      1998 mm). Der Roadmap-Punkt „Für Cura schreibt die Übergabe STL" aus der
      Cura-Kette ist damit nicht mehr erfüllt — die Umstellung auf die
      Baugruppe hat ihn überfahren. Die Tests decken es nicht ab: sie prüfen
      `slice_model` nur gegen Attrappen.
- [x] Der offene Punkt „`machine_profile` muss ein Pfad sein" ist bestätigt und
      erklärt den ganzen Rest: mit Namen endet der Lauf in
      `Slic3r::CLI::run found error`, mit Pfaden aus der Profilsuche läuft er.
      Die Oberfläche gibt Pfade, deshalb trifft es nur, wer die Verträge direkt
      benutzt.

### Und was das Modell beim Chatten anrichtet

Die Anfrage „Quader 30 × 20 × 10 und ein 5-mm-Loch mittig durch" ergab drei
Schritte, zwei Operationen, eine Transaktion — und ein Loch **an der Ecke**.
`create_box` legt den Quader um den Ursprung (−15 … 15), das Modell rechnete
mit einer Ecke im Ursprung und schickte `x = 15, y = 10`. Abgetragen wurden
53 statt 212 mm³, also ein Viertel. Danach schrieb der Agent: „Das Loch ist
durchgehend und mittig positioniert."

- [x] **Keine Prüfung schlägt an, wenn ein Schnittwerkzeug den Körper nur
      streift.** `checks.check` meldete zwei verwaiste Merkmale und sonst
      nichts. Bei der Vereinigung gibt es den Fall längst („hat nichts
      hinzugefügt"); bei der Differenz fehlt er.
- [x] **Der Steckbrief nennt keine Grenzen des Hüllquaders**, nur Flächenmitten
      — aus `face_5 bei (−15, 0, 5)` muss das Modell selbst schließen, wo die
      Mitte liegt. Ein Satz „liegt von … bis …" je Objekt kostet nichts.
      Danach die Agenten-Suite, vorher und nachher, wie es die Regel verlangt.

## Das Zeichnen im Handbuch und auf der Website (09.08.2026)

Auf die Frage, ob das Zeichnen sauber und detailliert beschrieben ist, war die
Antwort nein. Zwanzig geschriebene Seiten, und der Skizzeneditor kam in keiner
vor: ein Halbsatz auf Seite eins und die sechs Skizzen-Ops in der erzeugten
Referenz, die sagen, was aus einer fertigen Zeichnung wird — nicht, wie eine
entsteht. Auf der Website zwei Zeilen, ein Listenpunkt unter „Was sonst noch
drinsteckt". Behoben, und dabei fünf Stellen gefunden, an denen die Unterlagen
dem Programm widersprachen:

- **Das englische Handbuch behauptete auf Seite eins das Gegenteil.** „no CAD
  replacement — there are no sketches and no constraints" stand weiter mitten
  im Satz über den Slicer; auf Deutsch war er längst berichtigt, im Katalog
  nicht. Ein Kapitel später beschreibt dasselbe Handbuch die Bedingungen.
- **„Das Fenster" kannte nur eine Werkzeugleiste.** Der neue Absatz machte
  daraus eine Zeile mit „links hinsehen, rechts ändern" — das neu aufgenommene
  Bild zeigte zwei Leisten: oben Neu, Öffnen, Speichern, *Zeichnen*, unter dem
  Modell Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Bemalen. Dem
  Fensterschema fehlte die zweite ganz, deshalb stand sie in keinem Text.
- **„Weg 2 — selbst konstruieren" nannte Grundkörper und Bausteine**, und die
  Abbildung der drei Wege ebenso. Die Skizzen sind das Kernargument des
  Launches.
- **Die Statuszeile des Editors hatte keinen Singular.** „1 Freiheitsgrade
  frei" — aufgefallen, weil es sonst mit dem ersten Handbuchbild gedruckt
  worden wäre.
- **Drei Absätze druckten ihre eigenen Sternchen.** `**fett mit *kursiv*
  darin**` setzt `markup._STRONG` nicht um (das Muster lässt kein Sternchen im
  Inneren zu), und der Umsetzer schweigt dazu. `test_no_page_prints_its_own_markup`
  prüft es jetzt in **beiden** Sprachen — die englische Version ist ein
  Katalogeintrag, den kein Umsetzer korrigiert.

Neu: Kapitel „Zeichnen" vor den drei Wegen, mit drei Abbildungen — dem
aufgenommenen Skizzenmodus, dem Schema aus Werkzeugen, Bedingungsliste und
Statuszeile, und demselben Umriss als drei Körpern. Das Bildschirmfoto kam
zweimal untauglich aus dem Werkzeug, bevor es taugte: ein Lochkreis legte acht
Maßzahlen übereinander und füllte die Liste mit neun mal „Abstand 2,00", und
die 40-mm-Grundform lag als Briefmarke in der Bildmitte.

Auf der Website ist daraus der zweite Block im Funktionen-Abschnitt geworden,
gleich hinter dem Agenten, mit demselben Bildschirmfoto. Der Listenpunkt ist
weg.

### Und dann alles behoben (09.08.2026)

Neun Punkte, sechs Commits, 3417 grüne Tests. Was dabei über die Meldung
hinausging:

- **Neu vernetzen teilt jetzt gleichmäßig.** `subdivide_to_size` war die
  falsche Wahl, nicht ein Fehler in seiner Anwendung: es teilt jede Fläche
  nach *ihren* Kanten und lässt an der Naht zwischen zwei verschieden oft
  geteilten Flächen einen Punkt auf einer Kante liegen, die ihn nicht kennt.
  Verschweißen behebt die Komponenten, nicht die 192 offenen Kanten.
  `trimesh.remesh.subdivide` in Schritten bis zur Zielkantenlänge lässt keine
  solche Naht entstehen; der Preis sind Dreiecke, wo es schon fein genug war.
  Decke bei acht Millionen, sonst frisst eine kleine Kantenlänge den Speicher.
- **Zwei Slicer-Funde statt einem.** Dass Cura ein STL braucht, war der
  gesuchte; beim Nachmessen fiel der zweite auf, und er war der stillere:
  die Bettverschiebung galt für alle drei Familien, obwohl nur die
  Orca-Familie von der Ecke misst. Cura druckte 128 mm daneben, ohne zu
  klagen. **Wer eine Übergabe prüft, misst die Position im G-Code** — ein
  Lauf mit Rückgabe 0 sagt nichts darüber, wo das Teil landet.
- **Der Agentenfund brauchte drei Änderungen, nicht eine.** Ein Befund für das
  streifende Werkzeug, seine Durchreichung in `checks.PASSED_THROUGH` — und
  die Lage des Körpers im Steckbrief. Die ersten beiden allein hätten dem
  Modell gesagt, dass etwas falsch ist; erst die dritte sagt ihm, was.
  Nachgefahren mit qwen3:14b: dieselbe Anfrage ergibt jetzt x=0, y=0 und
  5804,21 mm³ gegen die Handrechnung 5803,65.
- **Was die Oberfläche ausgraut, sagt jetzt warum.** Ausgrauen allein ist die
  halbe Antwort — der Nutzer sieht, dass es nicht geht, und sucht den Grund
  bei sich.

Offen bleibt eine Messung: die Agenten-Suite vorher und nachher gegen die
Steckbrief-Erweiterung. Sie kostet Geld und rund anderthalb Stunden je Lauf und
läuft auf Ansage, nicht nebenbei.

Der zehnte Fund kam erst beim Nachmessen: **die Rastnase wurde nie ein Körper
mit ihrem Träger.** Sie steht mit 6 mal 1 mm auf der Fläche auf, und zwei
Volumen, die sich nur in einer Fläche berühren, brechen jede boolesche
Operation — wasserdicht, aber zwei Komponenten, nach der nächsten Bohrung drei.
Die breiteren Bausteine fielen nie auf, weil manifold sie verschmolz. Additive
Bausteine sinken jetzt in der Platzierung um den Überlappungswert ein.

**Bilanz des Reihendurchlaufs, vorher und nachher** (92 Läufe über 77
Operationen, jeweils mit der Vorbelegung des Dialogs):

| | vorher | nachher |
|---|---|---|
| Ergebnis nicht geschlossen oder Volumen ≤ 0 | 2 | **0** |
| Ergebnis in mehreren Komponenten | 2 | **0** |
| ohne Wirkung und ohne ein Wort dazu | 7 | **0** |
| angehalten | 19 | 20 (An Ebene teilen hält jetzt an, statt ein leeres Objekt anzulegen) |

Suite 3423 grün, Lint und Typprüfung ebenso.

## Das Zeichnen-Kapitel Satz für Satz gegen den Code (09.08.2026)

Zweiter Durchgang, auf die Bitte, alles gründlicher durchzugehen. Jede
Behauptung des neuen Kapitels gegen die Stelle im Code, die sie beschreibt —
und dabei kam heraus, dass zwei der Abweichungen keine Textfehler waren,
sondern Fehler im Editor. Vier Funde, alle behoben:

- **Strg+Z lag im Skizzenmodus beim Verlauf.** Das Kürzel hing am
  `SketchEditorDialog`, und den Dialog gibt es nur auf einem der beiden Wege.
  Im Skizzenmodus des Fensters nahm Strg+Z damit die letzte **Operation**
  zurück, während vor dem Nutzer eine Zeichenfläche stand. Jetzt bringt das
  Panel das Kürzel mit, und `_update_actions` graut Rückgängig/Wiederholen im
  Modus aus — beide Hälften nötig, denn bei zwei aktiven Belegungen derselben
  Taste feuert Qt keine (dieselbe Falle wie bei R und C).
- **Der Weg über das Operationsfeld war ärmer als der Skizzenmodus.** Kein
  Bauraumrand, keine Fläche des Körpers in der Ebenenwahl, und *Projizieren*
  antwortete „Es gibt keinen Körper, aus dem sich projizieren ließe" — an
  einem Modell, das im Fenster stand. Der Docstring von `SketchPanel`
  verspricht seit je, dass keiner der beiden Wege ein Werkzeug bekommt, das
  der andere nicht hat. `Surroundings` (Bauraum, Zeichenebenen,
  Projektionsvorlagen) trägt die drei Angaben jetzt zusammen,
  `MainWindow._sketch_surroundings()` ist die eine Quelle, und der
  Operationsdialog reicht sie an sein Skizzenfeld durch.
- **Der dritte Weg, einen Spline zu schließen, stand nur im Kommentar.**
  „Doppelklick, Eingabetaste oder ein zweiter Klick auf denselben Punkt" — den
  letzten gab es nicht: der Klick hängte einen weiteren, deckungsgleichen
  Punkt an die Kurve, still und ohne Ton. Wer den Griff aus einem CAD
  mitbringt, holte sich einen doppelten Punkt. `_on_last_pending` prüft jetzt
  in Bildschirmpunkten, mit derselben Toleranz wie der Fang.
- **Der README nannte die Seitenzahl des Handbuchs** — „dreiunddreißig
  Seiten: achtzehn geschriebene" — und lag zum dritten Mal daneben (der
  zweite Fall steht oben unter „Handbuch, Website und Rechtstexte
  durchgesehen"). Die Zahlen sind heraus, die Aussage bleibt: eine erzeugte
  Seite pro Kategorie. Was gezählt werden kann, zählt das Programm; der
  Vorspann der erzeugten Handbuchseite nennt die Zahl.

Und was im Kapitel schlicht **fehlte**, weil der Editor mehr kann, als beim
Schreiben in Erinnerung war: zoomen und schieben, das Ziehen eines Punktes mit
nachziehendem Solver, **Strg zum Sammeln** (ohne das kommt niemand auf
*Parallel*, das zwei Linien braucht), die zwei Bedeutungen von `Entf` je nach
Fokus, die zählende Klickreihenfolge. Dazu zwei zu grob formulierte Stellen:
das Maßfeld gilt nur für Linie und Kreis, nicht „nach dem ersten Klick"
allgemein, und bei einer angeklickten Fläche entscheidet deren Neigung über
die Schichtrichtung — nicht die Unterscheidung liegend/stehend.

Aus dem Vorschlag wurde derselbe Tag noch eine Umsetzung:

- [x] **Der Skizzeneditor kannte kein Einpassen.** Der Maßstab stand fest auf
      4 Punkte je Millimeter, und niemand rührte ihn an; eine geöffnete Skizze
      von 300 mm lag zur Hälfte außerhalb, der Bauraumrahmen von 220 × 220 beim
      Start gar nicht im Bild — ausgerechnet der, der die früheste Warnung
      tragen soll (E1). `fit_view` passt jetzt ein: eine vorhandene Zeichnung
      gibt das Maß (ragt sie über die Platte, kommt der Rahmen von selbst mit),
      ein leeres Blatt zeigt den Bauraum. Als Vorgabe **und** als Knopf mit
      `Pos1`, weil man sich verzoomt.

      Zwei Dinge kamen erst beim Nachmessen heraus. **Einmal einpassen genügt
      nicht:** der erste Versuch tat es beim ersten `resizeEvent` und
      verbrauchte sich — das Layout verteilt in mehreren Durchgängen, der erste
      bringt die Mindestgröße, und im Fenster fehlte danach ein Sechstel des
      Bauraums. Die Ansicht hängt jetzt an der Einpassung und zieht mit, bis
      jemand selbst zoomt oder schiebt. Und **der Rand ist an der Beschriftung
      bemessen, nicht an der Geometrie:** die Maßzahlen stehen außerhalb der
      Kontur, bei vierundzwanzig Punkten stand im Handbuchbild „60,0(" am
      rechten Rand.

## Dasselbe noch einmal, gründlicher (09.08.2026)

Der erste Durchgang fuhr jede Operation einmal mit ihren Vorgaben gegen einen
Quader. Das findet, was immer bricht. Dieser fragte weiter: gegen **fünf
Körperarten** (Netz, exakter Körper, importiertes STL, ausgehöhlt, Paar), an
**jeder Parametergrenze** des Schemas, und danach die vier Fragen, die eine
Anwendung beantworten muss — rechnet sie zweimal dasselbe, nimmt ein Undo sie
zurück, übersteht sie das Speichern, läuft die Entwurfsqualität.

712 Läufe. Was dabei herauskam:

- [x] **Neu vernetzen war nach dem letzten Commit für importierte Teile
      unbrauchbar.** Gleichmäßiges Teilen hält das Netz geschlossen und
      zerteilt dabei die winzigen Bohrungsfacetten mit: aus 796 Dreiecken
      wurden 815 104 bei fünf Millimetern, dreizehn Millionen bei einem —
      abgelehnt. Jetzt eine Kette wie bei den booleschen Operationen: erst
      nach Bedarf teilen, gleichmäßig nur, wenn das Netz sonst aufginge. Wer
      die Decke reißt, erfährt die Kantenlänge, die noch geht.
- [x] **Glätten stülpte einen ausgehöhlten Körper um** — minus 19 318 mm³,
      wasserdicht, exportierbar, und jede Kennzahl danach falsch. Und ein
      Vollquader aus zwölf Dreiecken schrumpfte auf sieben Prozent, während
      der Docstring „ohne den Körper zu schrumpfen" versprach.
- [x] **Die Merkmalszuordnung fragte ins Leere.** Sie stand außerhalb des
      Fehler-Fangs der Auswertung: wer keinen Frage-Dialog hat — Kommandozeile,
      Fernsteuerung, Agent —, bekam eine Ausnahme aus `evaluate` und einen
      leeren Prüfbericht statt der zwei Bohrungen, zwischen denen zu wählen war.
- [x] **Der exakte Gewindebolzen hielt nur ein Fünftel seines Schemas.** Ab
      50 mm Durchmesser kam nie ein geschlossener Körper heraus, bei 100 mm und
      1 mm Steigung einer mit null Volumen und null Komponenten, bei 0,25 mm
      Steigung neunzehn Bruchstücke — stumm. M2 mit 1,5 mm Steigung ergab einen
      Faden von 0,16 mm, weil die Kernprüfung nur fragte, ob überhaupt etwas
      übrig bleibt. Beides wird jetzt geprüft, bevor der Körper die Operation
      verlässt.
- [x] **Das OpenSCAD-Zeitlimit kam als `subprocess.TimeoutExpired`** heraus
      statt als Fehler mit Ausweg. `sphere(r = 50, $fn = 2000)` genügt dafür —
      ein Vertipper, kein Angriff.

### Was der Durchgang bestätigt hat

Das ist der andere Teil des Ergebnisses, und der größere:

| Frage | Läufe | Befund |
|---|---|---|
| Wirft je etwas anderes als ein `AppError`? | 712 | keiner |
| Zweite Auswertung gleich der ersten? | 74 | alle |
| Undo stellt den Vorzustand her? | 74 | alle |
| Speichern und Laden ändert nichts? | 74 | alle |
| Entwurfsqualität läuft, wo die feine läuft? | 74 | alle |
| Öffnet jeder Operationsdialog? | 77 | 71, die sechs anderen haben keine Parameter oder sind zu Recht ausgegraut |
| Felder auf der Vorderseite ≤ 8, Titel, Einheit, Erklärung? | 71 Dialoge | vollständig |
| Kommandozeile: alle Operationen, Fehler ohne Stapelabzug? | 77 + 7 Fehlerfälle | vollständig |

Suite 3438 grün (in zwei Portionen — der Abriss im Lauf am Stück ist weiter
der bekannte native, `test_chat_ui.py` läuft allein durch).

**Beobachtung ohne Fix:** `scale_object` mit Faktor 0,001 und `fit_to_size` mit
0,1 mm liefern einen Körper, den man nicht mehr sieht und nicht drucken kann —
mathematisch richtig, verlangt, und ohne ein Wort dazu. Eine Warnung „kleiner
als die Düse" wäre eine Erweiterung, kein Fehler; sie steht hier, damit die
Entscheidung eine ist.

## Der ganze Bestand durch die laufende Oberfläche (09.08.2026)

`tools/run_ui_audit.py` schickt alles, was auf dieser Maschine liegt, durch das
echte Fenster: 14 Projektdateien, 88 Modelle aus den Druckordnern und dem
Korpus, dazu den Weg von der leeren Szene bis zum geschriebenen Paket. Nicht
gegen den Kern — den prüft die Suite —, sondern mit Arbeitsfäden, Signalen und
Viewport, also dort, wo ein Fehler erst auftritt, wenn jemand davorsitzt.

**Ergebnis: 103 Stück, keins gestolpert.** Langsamstes Projekt
`puppenhaus_fertig` mit 7,1 s, langsamstes Modell die gähnende Katze mit 29 s,
der Aufbau von Null in 0,6 s.

Die Befunde sind die erwarteten für heruntergeladenes Fremdmaterial: 208-mal
„unter der Druckplatte" (Hinweis, nicht Warnung — heruntergeladene Teile sind
meist um den Ursprung zentriert), 86-mal verschweißte Punkte, 30-mal entartete
Dreiecke entfernt, 17-mal nicht wasserdicht, zehn Rückfragen nach der Einheit.

### Der eine Fehler, der dabei herauskam

`sketch_pocket` warf einen `ValidationError`, wenn der Körper ein Netz ist.
Dessen Titel lautet „Ein Wert liegt außerhalb des zulässigen Bereichs" — im
Prüfbericht stand damit eine Meldung über Zahlen, wo keine Zahl schuld war.
Für diesen Fall gibt es `NeedsSolidError`; `brep/ops.py` und `export/writer.py`
waren den Weg schon gegangen, diese Stelle war übersehen worden. Die Meldung
nennt jetzt den Ausweg (Regel 17): `shell_exact` statt `hollow_object`.

Sichtbar wurde es an `puppenhaus_fertig` und `puppenhaus_exakt`: dort höhlt
`hollow_object` den exakten Körper aus und gibt ein Netz zurück, worauf die
drei Taschen danach ins Leere laufen und die Auswertung bei Operation 4
stehenbleibt. **Die beiden Projekte sind damit nicht repariert** — ihre
Operationsreihenfolge kann so nicht funktionieren. Sie stehen im Bericht
weiter als `ABBRUCH@op4`, jetzt mit einer Meldung, die sagt, was zu tun wäre.

### Was der Durchgang über das Prüfen gelehrt hat

Sieben Fehler steckten im Prüfwerkzeug, einer in der Anwendung. Vier davon
waren geratene Signaturen (`result.findings` statt `scene.report.findings`,
`write_plan` mit einem Argument zu viel, `completed` — ein Tupel von Op-IDs —
statt der Property `complete`). Die teureren zwei waren Zeitfragen: wer nach
`start_new` nur auf `not busy` wartet, kommt durch, bevor der Arbeitsfaden
angelaufen ist, misst den Stand von vorher und bricht mit dem nächsten Aufruf
die laufende Auswertung ab. Elf von fünfzehn Modellen standen daraufhin als
„0 Objekte" im Bericht — sie luden alle. Im Sekundentakt wiederholt zerlegte
dasselbe Abbrechen den Prozess ohne Ausnahme; das sah lange nach einem
Absturz der Anwendung aus und war einer der Messung.

Der letzte Hänger kostete vier Minuten je Lauf und drei falsche Vermutungen:
`closeEvent` → `_may_discard` → `confirm_unsaved`. Das Fenster fragte beim
Schließen nach ungespeicherten Änderungen, und niemand antwortete. Ein
Stapelabzug hat das in einem Versuch beantwortet, wo Raten es dreimal nicht
tat — `faulthandler` bleibt deshalb über den ganzen Lauf scharf.

---

## Das Erzeugen-und-Agent-Konzept abgearbeitet (12.08.2026)

`konzepte/konzept-erzeugen-agent-oberflaeche-2026-08.md` ist umgesetzt. Zwei Punkte sind
dabei anders ausgefallen als geplant, beide begründet.

- [x] **Gedreht wird um das, was man ansieht.** Der Kamerafokus stand auf dem
      Weltursprung; ein heruntergeladenes Teil liegt fast nie dort und wanderte
      beim Drehen im Bogen durchs Bild. Blickrichtung und Abstand bleiben.
- [x] **Das Freistellmodell durfte nicht verkauft werden.** `RMBG-2.0` steht
      unter CC BY-NC und stand als Vorgabe in beiden Graphen; `INSPYRENET`
      (MIT) tut dasselbe. Ein Test verhindert den nächsten Fall.
- [x] **Hunyuan3D bleibt, mit einem Satz dazu.** Es ist für die EU ausdrücklich
      nicht lizenziert, ein Wechsel braucht aber eine andere Knotensammlung in
      ComfyUI. Solidon liefert keine Gewichte, der Graph nennt Rollen statt
      Dateien — Modulkopf und Handbuch sagen jetzt, was das bedeutet.
- [x] **Dezimieren in der Erzeugen-Kette.** Gemessen: 42 s, 1.588.016 Dreiecke,
      **null Merkmale** — der Agent hatte nichts, worauf er zeigen konnte.
      Oberhalb von 500.000 kommt jetzt eine vierte Transaktion auf 200.000.
- [x] **Das Werkzeugschema für lokale Modelle.** 99 → 79 KB, **ohne ein
      Werkzeug wegzulassen**: nach `applies_to` zu filtern wäre eine
      Betriebsart mit anderem Namen gewesen. Der größte Posten waren nicht die
      Beschreibungen (13 KB), sondern die Parametertexte (36 KB).
- [x] **Was ein lokales Modell leistet, steht an der Chatleiste** — drei von
      fünf Treffern, bis zu zwei Minuten je Aufruf, gemessen mit
      `tools/check_local_model.py`.
- [x] **Anschluss statt Wettlauf.** Wer mit Meshy, Tripo oder Rodin erzeugt,
      bringt das GLB her; druckbar wird es hier. Dazu im Handbuch der Satz,
      dass die MCP-Werkzeuge die Operationen der folgenden Kapitel sind.
- [x] **Karten wachsen mit breiten Fenstern**, anteilig und mit Deckel. Bei
      3413 px war die linke ein Zwölftel des Fensters, und die Maßspalte brach
      mitten in der Zahl ab.

### Was die Sitzung über das Prüfen gelernt hat

**Ein Messgerät, das seinen Gegenstand verändert, misst nichts.** Der
VTK-Screenshot rendert neu und reparierte damit genau den Zustand, den er
zeigen sollte; `QWidget.grab()` lässt den OpenGL-Bereich schwarz. Beide haben
mich stundenlang einen Viewport-Fehler jagen lassen, den es in der laufenden
Anwendung nicht gab: meine Prüfskripte fuhren `processEvents()` statt
`app.exec()`, und ein natives OpenGL-Fenster zeichnet so nur, solange etwas
passiert. Der Beweis war der Stand vom 08.08. — bei mir derselbe Fehler, in
der Anwendung intakt.

**Der eine Schritt, der die Frage beantwortet hätte, war die Anwendung
normal zu starten.** Eine Minute statt eines halben Tages.

**Und das Protokoll sagt, was die Ausnahme verschluckt.** Die Achsenanzeige
fehlte dreimal nacheinander, und jedes Mal stand der Grund als eine Zeile in
`app.log`: die Repräsentation kennt kein `SetViewport`, `add_axes` kennt kein
`shaft_type`, `label_color` setzt es selbst. Ein `except`, das nur
protokolliert, macht solche Fehler unsichtbar — die Anzeige war weg, und im
Fenster stand kein Wort darüber (Regel 17 dem Geist nach).

---

## Die Konzepte gegen den Code gehalten (14.08.2026)

Anlass war eine einzige Frage: *Sind alle Konzepte vollständig abgearbeitet und
aktuell?* Siebzehn Dokumente, jede Statusaussage im Code nachgeschlagen. Die
Antwort war zweigeteilt — inhaltlich fast alles durch, aber **fünf Dokumente
beschrieben einen Stand, den der Code überholt hatte.** Alle fünf sind
nachgezogen.

- [x] **Die Demo-Fortschrittstabelle stand auf zehnmal „offen"**, während sechs
      Pakete gebaut waren (`konzepte/konzept-demo-2026-10.md` §10). Wer den Stand dort
      statt in dieser Datei las, hielt die Demo für unangefangen. Jetzt mit
      Commit je Paket, und D6 und D9 stehen als „halb" da, weil sie es sind:
      dem einen fehlt der Download-Kasten mit Prüfsumme, dem anderen der
      Stichtag in `.claude/rules/kern.md`.
- [x] **Drei Sätze im organischen Konzept sagten „fehlt"**, während ein
      Nachtrag zwanzig Zeilen weiter „erledigt" sagte — Skeletteditor
      (`app/ui/pose_bar.py`, 14 Tests), Einback-Nachfrage (`bake_sculpt`, vier
      Fälle) und die Zeile „P16.6 bis P16.10: keiner begonnen", die aus dem
      Plan stehengeblieben war. Dazu führte die Restliste die Kategorie
      `organic` als offene Entscheidung, die am selben Tag entschieden wurde.
- [x] **Die Live-Durchsicht trug an vier von fünfzehn Befunden einen
      Erledigt-Vermerk**, obwohl alle fünfzehn erledigt sind. Die neun
      fehlenden sind nachgetragen, jeder mit der Stelle im Code — und zwei
      davon sind **anders** gebaut worden als vorgeschlagen: die Passung
      entsteht in `lid_flow.py` statt in den Ops (Regel 3 verbietet der Op die
      Dokumentänderung), und die neue Merkmalsart heißt `pin`, nicht `boss`.
      Genau solche Abweichungen verschwinden, wenn niemand den Vermerk setzt.
- [x] **Zwei B13-Abschnitte im Meshy-Konzept** mit verschiedenem Status, und
      die Schlusstabelle führte den Befund als abgeschlossen, während der
      eigene Nachtrag ihn auf „offen" gestellt hatte. Am Code entschieden:
      `autosplit.py` holt seine Normale weiter aus `AXIS_NORMALS`, die Suche
      kennt drei Achsen — also offen.
- [x] **Die Agent-Vertiefung verlangte in ihrer Reihenfolge-Tabelle ein
      Werkzeug `set_print_setting`**, das §5.1 desselben Dokuments schon am
      08.08. mit Begründung zurückgenommen hatte. Mit dem Werkzeug fiel auch
      seine Abnahme — sie prüfte, was nicht gebaut werden sollte.

**Was die Durchsicht nebenbei fand**, weil sie Zahlen nachzählte statt sie zu
lesen:

- [x] **„Beispiele — die drei Wege und was darauf bereitliegt"** stand als
      Beschriftung über neun Beispielen auf dem Startbildschirm, und es sind
      seit P16 **vier** Wege. Ein sichtbarer Text, den P16.10 übersehen hat;
      fünf Kataloge ziehen nach, die Wortwahl je Sprache aus dem
      Handbuchtitel *Die vier Wege* übernommen, damit die Oberfläche nicht
      zwei Wörter für dieselbe Sache führt. Der Kommentar in `examples.py`
      war dreifach falsch (vier statt fünf darunter, drei statt vier Wege).
- [x] **Die Version stand an zwei Orten und kein Test hielt sie zusammen.**
      `test_the_version_is_the_same_in_both_places_that_carry_it` tut es jetzt.
      Aufgefallen beim Heruntersetzen auf 0.1.0 — bis dahin hing die
      Übereinstimmung an Aufmerksamkeit.
- [x] **Die vier Wegekarten auf der Startseite waren textlastig und ihre
      Zeichnungen klein**, und die Ursache war nicht das Layout: Weg 3 trug
      89 Wörter gegen 25 bei Weg 2, und das Raster streckt jede Karte auf die
      Höhe der längsten. Der zweite Absatz von Weg 3 (Meshy, Tripo, Rodin)
      stand ohnehin doppelt — `ki-modelle.html` führt ihn — und ist dort
      gestrichen. Dazu zwei Spalten statt vier: 578 statt 279 px je Karte,
      533 statt 236 px Bildbreite, **233 statt 103 px Bildhöhe**, gerechnet
      aus `.wrap` 76rem, `gap` 1.25rem und dem Seitenverhältnis 320:140 der
      Vignetten. `align-items: start` nimmt den Streckzwang.

- [x] **Nachgemessen — und die Rechnung hatte recht, die Regel nicht**
      (14.08.2026). Chromium und Playwright liegen in dieser Umgebung bereit;
      gemessen wurde über `file://` bei neun Breiten von 1920 bis 360. Die
      Zahlen oben stimmen auf den Punkt: 578 px je Karte, 533 px Bildbreite,
      234 statt der gerechneten 233 px Höhe — der eine Pixel ist Chromiums
      Rundung. `align-items: start` sieht man im Bild: die vier Karten sind
      438 bis 538 px hoch und keine gestreckt.

      **Der Blick hat trotzdem etwas gefunden, das keine Rechnung zeigt.**
      `repeat(auto-fit, minmax(34rem, 1fr))` nimmt Spalten weg, aber es macht
      die *letzte* nicht schmaler als 34rem. Unter 544 px Fensterbreite stand
      also eine Spalte da, die weiter 544 px maß — und weil `html` und `body`
      `overflow-x: clip` tragen, war da auch nichts zu scrollen: Auf einem
      390er Telefon fehlten die rechten 150 px jeder Wegekarte, auf beiden
      Startseiten. `min(34rem, 100%)` um das Mindestmaß behebt es; breite
      Fenster bleiben unverändert bei zwei Spalten, bei 390 px ist die Karte
      350 px breit und vollständig. Nachgemessen und angesehen.

      `test_no_self_arranging_grid_stops_shrinking_above_phone_width` hält die
      Regel fest — nur für `auto-fit` und `auto-fill`, denn nur die versprechen
      mitzugehen; das Spaltenpaar der Kopfzeile steht in einem
      `@media (min-width: 68rem)` und ist eine Entscheidung, kein Versehen.

      Die Handbuchtabellen sahen in derselben Messung zuerst wie ein zweiter
      Fund aus — sie stehen bei 390 px bis zu 725 px breit da. Sie rollen aber
      in sich (`table { display: block; overflow-x: auto }`), und die Probe
      hatte nur die Kinder eines Rollbereichs nicht ausgenommen. Kein Befund.

### Review des Skizzeneditors — drei Funde, alle behoben (14.08.2026)

Ein Durchgang durch den gesamten uncommitteten Stand (40 Dateien, 959 Zeilen
Code). Zwei der Funde hat die parallele Sitzung noch während des Reviews
aufgegriffen; was hier steht, ist der Stand danach.

- [x] **Der Punktdialog rundete, was er nur anzeigen sollte.** `PointDialog`
      bindet seine Felder auf zwei Dezimalstellen — richtig, denn die Anzeige
      tut das überall (§11.2). Falsch war, dass `edit_point` das Ergebnis
      unbesehen zurückschrieb: Ein projizierter Punkt bei 30,125 mm kam als
      30,13 zurück, einer bei 0,001 mm als 0. **Ansehen war eine Änderung**, und
      Regel 6 sagt, dass nur die Anzeige rundet.

      Behoben mit einem Merker am `valueChanged`-Signal, nicht mit einem
      Zahlenvergleich — und das ist der lehrreiche Teil: Der erste Versuch
      verglich gegen die eigene Rundung und scheiterte an genau dem Wert, um den
      es ging. **Qt rundet 30,125 auf 30,13, Python auf 30,12** (round-half-even
      auf einer Zahl, die binär nicht exakt ist). Ein unangetastetes Feld gibt
      jetzt die genaue Lage zurück, ein angetastetes die Ansage des Nutzers.
      Zwei Tests, vier Werte gemessen.
- [x] **Zwei Wege zu einer Geste, und geprüft war der ungenutzte.** Der Griff
      auf einen vorhandenen Punkt stand im Mausereignis *und* in `place`. Das
      Ereignis kam zuerst und reichte Strg weiter, `place` nicht — also nahm die
      Maus einen anderen Weg als die drei Greif-Tests, die alle `place` rufen.
      Jetzt greift `place` allein und bekommt `extend` herein; ein Test hält
      fest, dass Strg dort ankommt.
- [x] **Beim Punktwerkzeug leuchtete nichts auf, obwohl ein Klick greift** —
      und nach der ersten Behebung leuchteten *zwei* Zeichen: der Punkt und die
      Fangmarke daneben, die eine Stelle zeigte, die der Klick nicht nimmt. Die
      Marke weicht jetzt.

      **Dabei fiel eine Doppelbedeutung auf:** `highlighted` trägt zweierlei —
      den Punkt unter dem Zeiger *und* die Punkte der überfahrenen Bedingung in
      der Liste (`highlight_points`). Die Fangmarke daran zu hängen hätte sie
      von der Maus über einer Liste abhängig gemacht. Der Treffer wird deshalb
      einmal je Mausbewegung gesucht und beiden Verbrauchern **als Argument**
      gegeben; `_note_hover` nimmt jetzt den Punkt statt der Position. Das
      spart zugleich den zweiten Durchlauf über alle Punkte.

### Der Absturz im langen Lauf: die Reihenfolge entscheidet (14.08.2026)

Nebenbefund derselben Sitzung, und er räumt eine Erklärung ab. Drei
Vollläufe, alle drei abgebrochen — und **zwei davon an derselben Stelle**:
`test_leaving_the_sketch_mode_empty_starts_no_operation`, im `MainWindow`-Aufbau,
bei 80 und 81 Prozent. Der erste Lauf brach bei 62 Prozent ohne Traceback ab und
sagte damit nichts.

- [x] **„Der Absturz wandert" gilt nicht mehr.** Er hing bisher am Cluster
      „diese Maschine rechnet sporadisch falsch", dessen Spur am selben Tag
      aufgegeben wurde. Zweimal derselbe Test ist keine Wanderung.
- [x] **Es sind zwei Abstürze, nicht einer.** Das ist der Fund, und er
      entstand aus einem eigenen Fehler: Der erste Reproduzierer wurde für den
      Volllauf-Absturz gehalten und ist ein anderer. Beide gemessen:

      | Aufruf | Fehlerbild | Wo |
      |---|---|---|
      | `pytest -q` (dreimal gefahren) | **Stack overflow** bei 80/81/82 % | jedes Mal `test_leaving_the_sketch_mode_empty_starts_no_operation`, im `MainWindow`-Aufbau |
      | `pytest -q --ignore=tests/test_translations.py` | **Stack overflow** bei 82 % | derselbe Test |
      | `pytest tests/test_translations.py tests/test_ui.py` | **Zugriffsverletzung** bei 22 % | `window`-Fixture von `test_ui.py`, in `render_window_interactor.initialize` |
      | `pytest tests/test_ui.py tests/test_translations.py` | 298 passed | — |
      | `pytest tests/test_ui.py` · `tests/test_sketch_editor.py` | 190 · 73 passed | — |

      **Absturz A — der Stapelüberlauf**, der die Vollläufe nimmt: viermal
      gefahren, **dreimal derselbe Test** (der vierte Lauf brach bei 62 % ohne
      Traceback ab und sagt nichts). Die gerissene Zeile wandert innerhalb des
      Fensteraufbaus — `overlay.py:327`, `overlay.py:333`,
      `main_window.py:790` —, und genau das ist das Bild eines Stapels, der
      schon fast voll ankommt: Es reißt, wo die nächste tiefe C-Rekursion
      liegt, nicht dort, wo die Ursache sitzt. `test_sketch_editor.py` allein
      ist grün, also braucht A einen Vorlauf.

      **Absturz B — die Zugriffsverletzung**, in 90 Sekunden reproduzierbar
      und **von A unabhängig**: Wer `test_translations.py` vor die
      fensterbauenden Dateien stellt, tötet einen späteren Aufbau in
      `render_window_interactor.initialize`; umgekehrte Reihenfolge läuft
      durch. Die Absturzstelle ist wörtlich die, die `conftest.py` als Folge
      eines **zerstörten** Fensters beschreibt — nur baut
      `test_translations.py` überhaupt kein Fenster: kein `MainWindow`, kein
      `build_application`, kein `deleteLater`. Es vergiftet, ohne eines
      anzufassen.
- [x] **A und B sind derselbe Fehler, und er ist behoben** (14.08.2026) — die
      Halbierung war die richtige nächste Frage, nur war die Antwort weder
      „die Kataloge" noch „die Importe von `app/ui/`". Siehe den Abschnitt
      *Ein Umgebungsartefakt, das keines war* weiter unten.

## Trennen, wo man hinzeigt — und vier Wörter weniger (14.08.2026)

Eine vollständige Durchsicht mit einer Frage: Wer das Programm zum ersten Mal
öffnet und ein Teil trennen will, kommt der an? Der lange Bericht steht in
`konzepte/konzept-durchsicht-2026-08-14.md`; hier die Arbeitsliste.

Vorweg das, was die Recherche über solche Programme sagt, weil es die
Reihenfolge bestimmt hat: **Gelobt wird Einfachheit und sonst nichts**
(Tinkercad wird für seine Oberfläche gelobt und für seinen Umfang kritisiert,
Fusion 360 andersherum). **Gefordert wird das Trennen mit Verbindern** — Cut
Tool mit Plug, Dowel und Snap ist in Bambu Studio, OrcaSlicer, Creality Print
und PrusaSlicer Standard, und diskutiert wird dort nur noch die Dübelform.
Solidon hatte drei Wege zu teilen und keinen, der über das Bild ging.

### Gebaut

- [x] **`split_line` — an einer gezeichneten Linie trennen.** Zwei Klicks auf
      das Teil, die Blickrichtung dazu, fertig ist die Ebene. Siebter
      Umschalter in der Werkzeugzeile (`SplitBar`, `Alt+7` — hier stand bis
      zum 19.08.2026 „achter", das ist `paint`), Verbindung vorgewählt,
      eine Transaktion, ein Undo, und je Stift ein Passungspaar (§14). Die
      Kamera steht nicht im Stapel: Die Blickrichtung wird einmal gelesen,
      und was in die Operation geht, sind Zahlen — sonst gäbe dieselbe Datei
      nach einem Schwenk ein anderes Teil (§11.2).
- [x] **Die Verstiftung kann jetzt schiefe Ebenen.** Das war der eigentliche
      Aufwand. `plan_pins` und `add_pins` rechneten mit einem Achsenbuchstaben,
      weil Auto Split nur achsparallele Ebenen legt; auf einer 45-Grad-Fläche
      steht ein so aufgestellter Stift schief in seiner eigenen Bohrung.
      Beide nehmen jetzt eine `SectionPlane`, gedreht wird mit derselben
      Matrix wie der Schnitt, nur invertiert. Drei Sonderfälle für drei Achsen
      sind dabei weggefallen, statt einen vierten zu bekommen — `upright_normal`
      hat die Eigenschaft, die alles trägt: die dritte Koordinate des gedrehten
      Punktes *ist* der Ebenenabstand, ohne Umrechnung.
- [x] **Auf dem Hauptknopf stand „etzt trenne".** Ein Fehler, der das ganze
      Programm betrifft und den man nur im Bild sieht: Das Stylesheet zeichnet
      `QPushButton:default` halbfett, Qt rechnet die bevorzugte Breite aus der
      normalen Schrift. „Jetzt trennen" sind 77 gegen 89 Bildpunkte, der Knopf
      bekam 104 — in einem Dialog fällt das nie auf, in einer engen Leiste
      immer. `style.make_primary()` setzt jetzt beides; alle sieben Hauptknöpfe
      gehen darüber, ein Test misst gegen die Schrift, mit der gezeichnet wird,
      ein zweiter verbietet `setDefault(True)` außerhalb von `style.py`.
- [x] **Vier Wörter, an denen ein Anfänger hängen bleibt.** *Boolesch* →
      **Verbinden und Abziehen**; *Druckvorbereitung* → **Teilen und Anpassen**
      (es stand als Untermenü unter *Vorbereiten*, zwei Ebenen mit fast
      demselben Wort); *Dezimieren* → **Dreiecke verringern**; *Muster* →
      **Kopien in Reihe oder Kreis** (*Textur aufbringen* hat einen Parameter
      „Muster", und der meint Rändel und Wabe). Bezeichner unverändert, fünf
      Kataloge nachgezogen, Handbuch neu erzeugt.
- [x] **„Automatisch teilen …" ist umgezogen**, von *Bearbeiten* nach
      *Vorbereiten*. Es stand dort, weil es technisch kein Registereintrag ist
      — eine Einteilung nach der Bauart der Funktion, nicht danach, wonach
      jemand sucht. Die vier Wege zu trennen stehen jetzt beieinander.

### Offen, mit Grund

Alle fünf sind inzwischen abgearbeitet — siehe den Abschnitt darunter.

## Die offenen Punkte abgearbeitet (14.08.2026)

Die fünf Punkte, die die Durchsicht offen ließ, plus das, was an Handbuch und
Website nur halb nachgezogen war.

- [x] **Ein Passungspaar entstand auch ohne Stifte.** War die Schnittfläche zu
      schmal, setzte `plan_pins` keinen einzigen und sagte das als Befund — das
      Dokument bekam seine `Fit`-Einträge trotzdem, und beide Seiten zeigten
      auf Merkmale, die es nie gab. Die Passungsprüfung meldete danach eine
      Verletzung an einem Teil, das in Ordnung ist.

      Die Zahl der Paare kommt jetzt aus `fitting_pins()` — derselben Planung,
      die die Operation gleich noch einmal macht, und weil sie deterministisch
      ist, stimmen beide Antworten überein. Damit sie das auch für Auto Split
      kann, führt jeder `Step` das Stück mit, das er geteilt hat: Gerechnet
      wird es nicht in `autosplit.py`, denn `pins.py` importiert das Modul —
      der Aufrufer in `split.py` hat beide.
- [x] **Die Hälften heißen jetzt „… A · Stifte" und „… B · Löcher".** Beim
      Export ist der Dateiname die einzige Auskunft darüber, welches der
      beiden Teile man in der Hand hat. Ein vorhandener Zusatz wird ersetzt
      statt ergänzt, sonst steht dort beim zweiten Teilen
      „Halter A · Stifte A · Stifte"; der Buchstabenpfad bleibt, er zeigt den
      Teilungsbaum. Getrennt wird an „ · " — das Zeichen kommt in Nutzernamen
      praktisch nicht vor, also nimmt das Abschneiden keine fremde Klammer mit.
- [x] **`MENU_TWINS` hängt nicht mehr an B-Rep.** Der Haken „Exakter Körper
      (B-Rep)" stand als feste Zeichenkette in der Oberfläche und
      „(Umschalter „Exakt")" im Menüweg; damit taugte die Zusammenlegung für
      nichts als die zwei Rechenkerne. Die Beschriftungen liegen jetzt in
      `TWIN_TOGGLES`, und wer dort fehlt, bekommt keinen Haken — sein
      Umschalter ist ein Wert im Dialog des Partners.

      Damit ist *An Ebene teilen* dorthin gezogen, wo es hingehört: unter
      *Teilen* (vormals *Teilen und verstiften*), mit der Null im Feld
      *Passstifte* als Umschalter. Aus drei „teilen"-Zeilen nebeneinander sind
      zwei geworden.
- [x] **Verbinder haben eine Form.** Rund, Sechskant, Schwalbenschwanz — als
      Querschnitt des `dowel`-Bausteins, also über den Parameterbereichstest
      mitgeprüft. Rund braucht zwei Stück gegen Verdrehen, die kantigen halten
      einzeln; gemessen wird das im Test als das, was von der Bohrung frei
      bliebe, wenn der Stift verdreht steckte. Die Fase bleibt für alle drei
      dieselbe Rechnung, weil sie über den Umkreis arbeitet. Die Wahl steht in
      der Trennleiste neben der Stiftzahl, nicht hinten in einem Dialog: Wer
      einen Schwalbenschwanz will, will ihn, *bevor* er trennt.
- [x] **Die acht Werkzeuge haben Kürzel**, `Alt+1` bis `Alt+8` in der
      Reihenfolge der Leiste. `Alt` und eine Ziffer mit Grund: Ein Kürzel ohne
      Modifikator feuert auch, während jemand in den Chat tippt, und schluckt
      dort den Buchstaben; die Ziffern allein gehören der Darstellung, `Ctrl`
      und Ziffer den Kameras. Das Kürzel steht im Tooltip und in der Palette —
      und es überlebt jetzt auch das Ausgrauen, das den Tooltip gegen den
      Grund tauscht.
- [x] **Handbuch und Website waren nur halb nachgezogen.** Die aus dem
      Register erzeugte Referenz stimmte von selbst; der *geschriebene* Teil
      nicht. Das Handbuch zählte die Werkzeugzeile weiter mit sieben
      Werkzeugen auf und schickte den Leser nach „Bearbeiten → Automatisch
      teilen" und „Ändern → Teilen und verstiften" — beide Wege gibt es so
      nicht mehr. Nachgezogen in allen fünf Sprachen, nicht nur auf Deutsch
      und Englisch: Kapitel 3 (Werkzeugzeile samt Kürzeln), Kapitel 13 und 14
      (das Trennwerkzeug, die Verbinderformen, die Namen der Hälften). Auf der
      Website hieß der Abschnitt *Auto-Split* und kannte nur die Suche; er
      heißt jetzt *Trennen und Auto-Split* und fängt mit den zwei Klicks an.

### Die Entscheidung, die eine Rechnung nicht überlebt hat

- [x] **Der Schnapper ist gebaut** (14.08.2026). Er stand hier als *bewusst
      offen*, mit drei Gründen — und zwei davon halten einer Messung nicht
      stand. Der eine, der hält, ist genau der, der ihn zum eigenen Baustein
      macht und nicht zu einem Wert in `_profile`.

      **Was stimmte:** Ein Schnapper ist kein Querschnitt. Rund, Sechskant und
      Schwalbenschwanz sind dieselbe Rechnung mit einem anderen Vieleck; der
      Schnapper ist ein Paar aus Federarm und Tasche mit Rastkante. Deshalb
      `snap_connector` als eigener Baustein — der vierzehnte, einer mehr als
      die Erstbestückung in §24.1, und das ist eine Ansage.

      **Was nicht stimmte, erstens: „der Hinterschnitt ist eine
      Überhangfläche, über die der Baustein etwas sagen müsste."** Er ist eine
      Brücke von der Breite des Hakenüberstands — bei einem 6-mm-Verbinder
      0,9 mm. Das legt jeder Drucker, und in der anderen Lage (Naht nach
      unten) gibt es überhaupt keinen Überhang. Ich hatte die Lage nicht
      durchgerechnet, sondern das Wort *Hinterschnitt* gelesen.

      **Und zweitens: „eine Federkraft, die ohne Kalibrierung geraten wäre."**
      Sie wird nicht geraten, sie wird gebaut: zehn zu eins ist das Verhältnis
      aus Länge zu Armstärke, das ein Arm zum Federn braucht, und es stand
      längst als `SNAP_RATIO` im Repository — `snap_fit` benutzt es seit der
      Erstbestückung. Der Baustein setzt die Stärke daraus, statt einen Regler
      dafür anzubieten.

      **Was die Rechnung wirklich begrenzt**, war keiner der drei Gründe: Aus
      zehn zu eins und zwei Außenwänden einer 0,4er Düse (0,8 mm) folgt eine
      Mindestlänge von 8 mm, und die Nahtplanung vergibt `1,5 · Ø` — ein
      Schnapper braucht also eine Naht, die mindestens **5,4 mm** hergibt. Ist
      sie schmaler, wird rund daraus **und der Prüfbericht sagt warum**
      (`split.snap_too_small`, Regel 21). Das ist die ehrliche Grenze, und sie
      ist eine Zahl statt einer Meinung.

      Gemessen: 144 Ecken des Parameterbereichs, alle wasserdicht, einteilig
      und innerhalb ihres Umkreises; der Anschlag beim Auseinanderziehen und
      die Durchfahrt des ausgewichenen Arms als Volumen, über vier Größen.

## Der eigene Änderungssatz im Review (14.08.2026)

Drei Commits, 46 Dateien — durchgesehen wie fremder Code, jeder Fund einzeln
behoben und mit einem Test festgenagelt.

**Zuerst ein Fehler an der Methode selbst.** Ich hielt den Diff gegen `main`
und las dabei fremden Code als meinen: `main` (62ba22a) liegt *hinter* meinem
Ausgangspunkt `051fdb6`, der Vergleich zeigte also auch Änderungen der
Nebensitzung. Wer seinen eigenen Satz prüfen will, vergleicht gegen den Stand,
auf dem er aufgesetzt hat — nicht gegen den Zweig, in den er später geht.

- [x] **Die kantigen Verbinder waren größer, als sie sagten.** `hexagon(width)`
      nimmt die Schlüsselweite, `dovetail(width)` die breite Seite — beide
      bekamen den Durchmesser roh durchgereicht. Bei `diameter = 6` maß der
      Sechskant 6,93 Umkreis und der Schwalbenschwanz 8,49; dessen Ecke allein
      nahm 1,24 mm der 1,6 mm Wandreserve, die die Stiftplanung stehen lassen
      wollte. `_profile()` rechnet jetzt um (√3/2 beim Sechskant, 1/√2 beim
      Schwalbenschwanz), und der Docstring sagt in einem Satz, was `diameter`
      ist: immer der Umkreis. Ein Test misst alle drei Formen gegen ihn.
- [x] **`fitting_pins()` sagte etwas anderes, als es tat.** Ohne Netz gab es
      null zurück, während der Docstring die gewünschte Zahl versprach. Null
      heißt hier „keine Passung eintragen" — bei einem Aufruf ohne
      ausgewerteten Körper wäre das stillschweigend die falsche Antwort statt
      einer offenen Frage. Es gibt jetzt `wanted` zurück: Wer kein Netz
      mitgibt, bekommt, was er wollte, und die Operation korrigiert es beim
      Rechnen.
- [x] **Die Begründung der Kürzel stimmte nicht.** Im Kommentar stand, ein
      Kürzel ohne Modifikator würde auch beim Tippen im Chat feuern. Mit
      `QTest.keyClick` gegen ein fokussiertes `QLineEdit` gemessen: tut es
      nicht, Qt gibt die Taste dem Eingabefeld. Der Grund für `Alt+Ziffer`
      bleibt trotzdem — die nackten Ziffern gehören der Darstellung, `Ctrl`
      und Ziffer den Kameras. Der Kommentar sagt das jetzt, und ein neuer Test
      prüft das ganze Fenster auf doppelt vergebene Kürzel statt nur die
      Werkzeugzeile.
- [x] **`half_names()` schnitt fremde Namensteile ab.** Es trennte am letzten
      „ · " und warf den Rest weg — ein Körper namens „Halter · Version 2"
      hieß nach dem Teilen „Halter A · Stifte". Abgeschnitten wird jetzt nur,
      was hinter dem Trenner steht *und* einer der eigenen Zusätze ist:
      „Stifte" und „Löcher", in der Quelle wie in jedem der fünf Kataloge —
      sonst verlöre ein auf Spanisch geteiltes und auf Deutsch weitergeteiltes
      Projekt die Regel. `_own_notes()` liest die Kataloge einmal
      (`lru_cache`), nicht bei jedem Namen.
- [x] **`split_plane` stapelte den Zusatz.** Die Op ohne Stifte baute ihre
      Namen selbst und kam an `half_names()` vorbei; zweimal geteilt stand
      „… A · Stifte A" da. Beide Ops gehen jetzt durch dieselbe Funktion.
- [x] **Kleinkram, der trotzdem in die Irre führt.** Der Docstring von
      `show_split_line` sprach von einem Kreuz an den Enden, gezeichnet wird
      eine Kugel; die Enden hatten keinen `name`, waren also nicht einzeln
      abräumbar; der B-Rep-Umschaltertext stand zweimal wörtlich in
      `TWIN_TOGGLES`; die Menüsuche für *Automatisch teilen* ging über den
      übersetzten Gruppentitel statt über die Kategorie und hätte in jeder
      anderen Sprache danebengegriffen; und ein Kommentar sprach noch von
      „drei anderen Wegen", wo es inzwischen vier sind.

### Was der Volllauf sagt

3357 bestanden, 10 übersprungen, 1 erwartet fehlgeschlagen; die Fensterdateien
Datei für Datei grün. `ruff`, `ruff format` und `mypy` sauber.

**Zwei Dateien brechen in diesem Container ab, beide ohne Zutun dieses
Zweigs** — nachgemessen, nicht angenommen:

* `test_manual.py` stirbt reproduzierbar beim Aufbau der `QApplication` unter
  `offscreen`, und zwar an derselben Stelle auf dem unveränderten `051fdb6`.
  Unter einem echten Bildschirm (`xvfb-run`) laufen alle 46 Prüfungen durch.
* `test_operation_ui.py` bricht unregelmäßig ab, mal beim Leeren der
  Verlaufsliste, mal beim Öffnen eines Dialogs — unter `offscreen` wie unter
  `xvfb`, und auf dem unveränderten Stand mit derselben Häufigkeit: ein
  Abbruch in sechs Läufen hier wie dort. Wo er nicht zuschlägt, sind alle 24
  Prüfungen grün.

> **Nachtrag (14.08.2026, eine Runde später): der erste Punkt war kein
> Umgebungsartefakt, sondern ein Fehler.** `tests/test_manual.py` importiert
> `tools.make_figures`, und dieses Modul setzte beim *Import*
> `QT_QPA_PLATFORM` zurück — danach baute die `QApplication` gegen eine echte
> Plattform, die es hier nicht gibt. Behoben, siehe den Abschnitt *Ein
> Umgebungsartefakt, das keines war* unten; die Datei läuft jetzt auch
> offscreen. „Auf dem unveränderten Stand genauso" war richtig gemessen und
> hat trotzdem zur falschen Schlussfolgerung geführt: Ein Fehler, der älter
> ist als der eigene Zweig, ist deswegen kein Fehler der Umgebung.
>
> Der zweite Punkt bleibt bestehen und ist ein eigener, dritter Absturz.

## Alles Offene abgearbeitet (14.08.2026)

Vier Punkte standen offen, drei davon länger als diese Sitzung. Alle vier sind
zu, und drei haben unterwegs etwas gefunden, das nicht auf der Liste stand.

- [x] **Die Wegekarten am Browser nachgemessen** — und dabei einen Fehler
      gefunden, den keine Rechnung zeigt: Unter 544 px Fensterbreite standen
      die Karten weiter 544 px breit da und wurden abgeschnitten. Der
      ausführliche Eintrag steht oben bei der Durchsicht, in der die Zahlen
      entstanden sind.
- [x] **Drei Namen für benachbarte Dinge** — zwei davon waren *derselbe
      Dialog*. Er heißt jetzt überall *Chat einrichten*: auf dem
      Erstlaufbildschirm, im Menü, im Fenstertitel, im Handbuch und in der
      README. Der dritte bleibt *Fernsteuerung*, weil die Zeile darunter und
      das Handbuchkapitel so heißen; geändert ist, was fehlte — „über MCP"
      nannte das Protokoll, jetzt steht dort *durch andere Programme*.
- [x] **Absturz A und B** — ein Fehler, eine Zeile, siehe oben.
- [x] **Der Schnapper** — gebaut, nachdem zwei meiner drei Ablehnungsgründe
      einer Messung nicht standhielten.

### Was die Suite dabei gefunden hat

Der neue Baustein hat sechs Prüfungen rot gemacht, und jede einzelne war
berechtigt — das ist der Teil, der ohne Suite still danebengegangen wäre:

* Der Baustein erzeugt eine Operation (`insert_snap_connector`), und die
  braucht einen Testaufruf.
* Die Startseiten führen die Zahl der Operationen und der Bausteine; beide
  standen auf dem alten Stand, in beiden Sprachen. Die Pressemitteilung auch.
* Der Registerkopf der ROADMAP führt jeden offenen Punkt — drei fielen weg,
  einer kam dazu.
* Und einer war ein echter Fund an einer ganz anderen Stelle: Der Katalogtest
  suchte nach „zzz-gibt-es-nicht" und erwartete null Treffer. `PARTS.search`
  zerlegt aber an jedem Nicht-Wortzeichen, aus dem Bindestrich wurden vier
  Wörter — und weil der neue Baustein einen Satz mit „gibt es" bekam, fand die
  angeblich leere Suche ihn. Die Anfrage heißt jetzt „qwertzuiopasdfgh": ein
  Buchstabensalat ohne Trennzeichen kann das nicht passieren.

**Volllauf danach:** 3374 bestanden, 10 übersprungen, 1 erwartet
fehlgeschlagen; jede Fensterdatei einzeln grün, `test_manual.py` zum ersten Mal
seit Langem auch offscreen. `ruff`, `ruff format` und `mypy` sauber.

## Drei Funde aus der Slicer-Übergabe (15.08.2026)

Drei Punkte aus der Praxis, alle drei über die laufende Oberfläche
nachgefahren — echte Qt-Plattform, echtes Hauptfenster, echter ElegooSlicer.

### Der Drucker, den es nicht gibt, hielt die Anwendung an

- [x] **Wer die Druckeinstellungen öffnete, ohne einen Drucker eingestellt zu
      haben, sah die Anwendung stehen.** Minutenlang, ohne Anzeige, ohne
      Ausweg. Der Auslöser ist kein Sonderfall, sondern die Vorgabe: Solidon
      startet mit dem „Allgemeinen FDM-Drucker 220 mm", und dazu hat kein
      Slicer ein Profil.

      Die Kette: `match()` findet nichts, `_fill_filaments` bekommt
      `machine=None`, und `match_filament` schlägt dann statt der verträglichen
      Profile **den ganzen Bestand** auf — jedes mit einer Erbkette aus
      Dateien. Gemessen am installierten ElegooSlicer:

      | | Filamente | Dauer |
      |---|---|---|
      | mit erkanntem Drucker | 42 | 0,97 s |
      | ohne | **5962** | nach zehn Minuten noch nicht durch |

      Der Kommentar an der Stelle warnt wörtlich davor („sonst kostete es
      Sekunden statt Zehntel"). Die Vorsicht hängt nur an der
      Verträglichkeitsprüfung, und die gibt es ohne Drucker nicht.

      **Wirkungslos war die Suche obendrein**: Ihr Treffer wird danach mit
      `findData` in einer Liste gesucht, die leer ist. Behoben auf beiden
      Ebenen — im Kern gibt `match_filament` ohne Drucker nichts zurück, in der
      Oberfläche wird nichts vorgewählt, wo nichts zu wählen ist.

      Eingekreist wurde er, indem der Ablauf gegen den unveränderten Stand
      gefahren wurde: Beide starben identisch, also lag es nicht am eigenen
      Änderungssatz. **Vollbild war es nicht** — er tritt in jedem
      Fenstermodus auf.

### Die Übergabe nahm nur Platte 1

- [x] **Der Export konnte alle Platten, die Übergabe eine.** Sie schrieb die
      Baugruppe von `plates[0]`, sagte „geslicet wird die erste" und hörte auf;
      der Satz stand eine Zeile über dem Fortschrittsbalken und wurde von ihm
      gleich wieder ersetzt.

      Eine Platte ist jetzt ein Lauf: eigene Baugruppe, eigene Materialslots,
      eigene Anordnungsprüfung, eigene Druckdatei. Das gilt für alle drei
      Slicer-Familien — die Orca-Familie könnte mehrere Platten in einer
      Projektdatei führen, Cura und PrusaSlicer nicht, und ein Weg, der überall
      gleich läuft, ist mehr wert als einer, der bei zweien anders aussieht.

      Zeit und Material addieren sich (`gcode.combine`), die Schichtzahl nicht:
      über zwei Platten summiert wäre sie eine Zahl, die es nirgends gibt.
      Fehlt ein Wert bei einer Platte, fehlt die Summe.

      **Über die Oberfläche nachgefahren**, sechs Teile auf zwei Platten:

      ```
      [ 0.3 s] Der Slicer rechnet — Platte 1 von 2 …
      [ 1.3 s] Der Slicer rechnet — Platte 2 von 2 …
      [ 2.0 s] Druckzeit: 512 min · Material: 235.9 g · Platten: 2
        Platte 1: solidon-1.gcode — 340 min, 156,9 g
        Platte 2: solidon-2.gcode — 172 min,  78,9 g
      ```

### Der Verbinder sitzt im Füllmuster

- [x] **Die Stiftplanung rechnet in Geometrie, gedruckt wird ein Ring mit
      Muster darin.** Am Querschnitt gemessen, so wie man es am geschnittenen
      Teil nachmisst — ein Zapfen mit Ø 5,04 mm aus `split_pinned`:

      | Wände | Material | Füllkern |
      |---|---|---|
      | 2 | 1,68 mm | **3,36 mm** |
      | 3 (Vorgabe) | 2,52 mm | 2,52 mm |

      Bei zwei Wänden ist mehr Muster als Material, und genau dort sitzt die
      Verbindung; ein Gyroid mit fünfzehn Prozent trifft diesen Kern womöglich
      gar nicht. Bei drei hält es sich die Waage, und dann sagt Solidon nichts —
      die Vorgabe ist in Ordnung.

      `advise._from_connectors` schlägt die Wandzahl vor, nicht die Füllung:
      Wände liegen deterministisch um den Zapfen, Füllung trifft ihn
      statistisch. **Nicht bis vollmassiv** — der Vorschlag bringt ihn genau
      auf die Schwelle, ab der das Material mindestens so breit ist wie sein
      Kern. Bis zum vollen Querschnitt wären es bei einem 8-mm-Zapfen zehn
      Wände auf dem ganzen Teil, und ein Vorschlag, den niemand annimmt, macht
      die vier daneben unglaubwürdig.

### Druckzeit und Materialbedarf des Videoprojekts

- [x] **Gemessen statt geschätzt.** Im Videotext stand keine Zahl, weil keine
      gemessen war. `gehaeuse-mit-bausteinen.p3d` einmal ganz durch die
      Übergabe, auf Elegoo Centauri Carbon 2 mit Elegoo PETG und dem Profil
      „0.20mm Standard @Elegoo CC2 0.4 nozzle":

      | `breite` | Druckzeit | Material | Schichten |
      |---|---|---|---|
      | 70 mm | **52 min** | **17,6 g** | 40 |
      | 96 mm | 64 min | 22,6 g | 40 |

      Der Zuschauer sieht den kleinen Stand, also steht der kleine Wert im
      Intro — in beiden Sprachen. Wer am Projekt oder am Profil dreht, misst
      neu, statt die Zahl anzupassen.

**Nebenbei:** Die Anwendung startet bildschirmfüllend statt auf 1280 auf 820 —
`showMaximized()` und nicht Vollbild, damit Titelleiste und Menüs bleiben.

## Die große Durchsicht vom 16.08.2026 — Code, Oberfläche, Wettbewerb

Sechs Durchgänge über den ganzen Stand: drei Code-Reviews über den Kern,
Oberfläche, Bedienlogik der vier Hauptwege, Wettbewerbsrecherche. Alle Funde
mit Stelle, Beleg und Fix-Skizze stehen in
`konzepte/durchsicht-2026-08-16.md` — hier nur, was daraus zu tun ist.

Vorab die Baseline: Umgebung auf `constraints.txt` gebracht (trimesh
4.12 → 5.0.0; der Major-Sprung ist nachweislich folgenlos, in beiden
Kern-Gebieten gegen die installierte Version aufgelöst), Suite portionsweise
**4009 Tests grün**, ruff/format/mypy grün. Der Lauf am Stück stirbt weiter
am nativen rtree-Abriss — Umgebung, nicht Code.

**Das Muster der Durchsicht:** Fünf der sieben Stopper sind grün getestet und
trotzdem falsch — die Suite kennt jeweils die Form nicht, in der der Fehler
auftritt (kein Test dividiert *durch* einen Parameter, keiner prüft die
`*_settings_id`-Inhalte, keiner den Slicer-Timeout, keiner die Slot-Filamente
am echten Eingang, keiner Weg 4 am laufenden Programm). **P16 hat nie eine
Live-Abnahme bekommen**, wie sie P15 und die August-Durchsicht hatten.

- [x] **K1 — Division durch einen Parameterverweis ist unmöglich** (§13).
      `expressions.check/references` parsen mit Platzhalter-Nullen, der
      Divisionsschutz lehnt `=@width/@count` überall ab; `sketch/serialize`
      frisst den Fehler still und rechnet mit altem Cache. Fix + Test zuerst.

      **Behoben:** Der Prüfmodus toleriert eine Null im Nenner genau dann,
      wenn der Nenner eine Referenz enthält — ein Zähler je Vorkommen, weil
      das deduplizierende Set als Vorher-nachher-Marke nicht taugt. Die
      Literal-Null (`/0`, `/(2-2)`) bleibt auch in der Prüfung ein Fehler,
      und die Auswertung mit echten Werten wirft unverändert. Vier neue
      Tests, darunter der Skizzenfall `=@d/@n`, dessen Referenzen jetzt in
      den Cache-Schlüssel kommen.
- [x] **K2 — OpenSCAD-Quelltextprüfung umgehbar** (Regel 11, §32).
      `import_stl`/`import_dxf`/`file=` gehen am Muster vorbei; gegen das
      installierte OpenSCAD belegt, die Datei wird gelesen. Vor jeder
      Auslieferung.

      **Behoben:** Beide Muster kennen jetzt die fünf veralteten
      Einbindungen und jedes `file=`; die Literal-Suche merkt sich Spannen
      statt Startpositionen, damit das `file=` innerhalb eines gelesenen
      `import(file="…")` nicht als zweite, ungelesene Anweisung gilt.
      Relative Altformen bleiben erlaubt (gleiche Regel wie `import`),
      `file=` mit Ausdruck statt Literal ist nicht prüfbar und wird
      abgelehnt. Zehn neue Testfälle.
- [x] **K3 — Slot-Filamente erreichen die Übergabe nie**: der Dialog sammelt
      `slot_profiles` ein und meldet Vollzug, `MaterialSlot.material` setzt
      niemand — alle Slots slicen mit dem Basisfilament.

      **Behoben:** `handover.with_slot_profiles` heftet die Wahl positionsweise
      an die Slots (die Position ist die Extruderbelegung), `_plate_run` ruft
      es — `write_config` war auf `MaterialSlot.material` längst vorbereitet.
      Der Dialogtest prüft jetzt den Eingang, nicht nur die Fähigkeit.
- [x] **K4 — die exportierte 3MF trägt absolute Pfade als Profil-IDs**
      (Regel 12; Orca erwartet Namen und trifft kein Preset).

      **Behoben:** `project_settings` schreibt Namen — das Maschinenprofil
      über `_profile_name` (beschnitten wird nur, was wie eine Profildatei
      endet; `.stem` auf „0.12mm Fine @…" schnitte mitten ins Maß), Prozess
      und Filament tragen den Solidon-Namen, unter dem `write_config` sie
      wirklich schreibt. Zwei Tests halten die IDs fest.
- [x] **K5 — Slicer-Lauf: Timeout tötet den Dialog, Schließen friert ein,
      Abbrechen fehlt** (§2.8, Regel 17; `reject()` umgeht `closeEvent`).

      **Behoben:** `_run_slicer` ersetzt das blinde `subprocess.run` —
      Zeitgrenze und Startfehler sind `ExternalToolError` mit Vorschlägen,
      und ein `CancelSignal` beendet den Kindprozess (erst höflich, dann
      endgültig). Der Dialog hat ein Abbrechen neben dem Balken, der bei
      mehreren Platten bestimmt zählt; `reject()` und `closeEvent` gehen
      beide durch `_settle`, das den Lauf abbricht statt ihn auszusitzen —
      das Warten bleibt als Absturzschutz, ist nach dem Kill aber kurz.
      Drei Tests, darunter der Zwilling zum OpenSCAD-Timeout.
- [x] **K6 — Cura scheitert am eigenen Türsteher**: der Dialog verlangt ein
      Maschinenprofil, das es bei Cura strukturell nicht gibt, obwohl der
      Kern die Maschine selbst beschreibt.

      **Behoben:** Der Türsteher gilt nur noch der Orca-Familie; Cura wird
      wie Prusa gar nicht erst durchsucht und sagt ehrlich, dass Solidon
      die Maschine selbst beschreibt (`_machine_keys`, `_cura_base`).
- [x] **K7 — Weg 4 ist gebaut, aber nicht benutzbar**: `finish_armature`
      schickt eine leere Pose (nichts passiert, ohne Ansage); eine getippte
      Pose tötet über ungeschütztes `json.loads` den Auswertungs-Thread und
      die Sitzung meldet Erfolg; „Relief auflegen" bietet kein Bild an (kein
      Bildformat führt in die Quellen); der Startbildschirm-Import lädt ins
      Unsichtbare — und genau darauf zeigt der Schlussknopf der
      Erstinbetriebnahme.

      **Behoben, vierteilig:** (1) Die beiden Sammelparameter-Leser in
      `pose.py` werfen bei fremder Eingabe eine `ValidationError` mit der
      erwarteten Form, und `evaluate` wandelt jede fremde Ausnahme unterhalb
      einer Op in einen `InternalError`-Befund, statt den Thread sterben zu
      lassen — die nächste ungeschützte `json.loads` wäre sonst derselbe
      Fund noch einmal. (2) „Fertig" im Skeletteditor gibt an
      `run_operation` ab, wie es die Skizze vormacht: der Dialog öffnet mit
      gesetztem Skelett. (3) Neuer Parameter- und Quellentyp `image`:
      `displace_image` listet nur Bildquellen, der Dialog bekommt „Bild
      wählen …" (`ImageSourceField`), `session.import_image` bettet ohne
      load-Operation ein, und ein auf das Fenster gezogenes Bild öffnet den
      Relief-Dialog auf dem gewählten Körper. (4) `action_import` legt vom
      Startbildschirm aus ein frisches Projekt an und fängt Fehler; der
      Wechsel in den Arbeitsbereich hängt jetzt am Dokument selbst
      (`_on_project`), damit die vergessene achte Stelle unmöglich wird.
      Offen bleibt das `ArmatureField` (Reihenfolge Punkt 12).
- [x] **Nebensitzung 3MF-Export**: Urteil *nachbessern* — ohne geöffneten
      Dialog ist `print_settings` weiter `None` (A1), der Einzelkörper-Export
      läuft am neuen Code vorbei (A2); Details und A3–A7 in der
      Durchsichts-Datei.

      **Nachgebessert und übernommen:** Jedes 3MF geht über `write_assembly`
      (auch ein Körper — der Plan-Weg kennt keine Einstellungen), `None`
      fällt auf `print_settings.resolve` zurück, `remembered_setup` löst je
      Material auf wie der Dialog selbst, und die Slicer-Suche läuft hinter
      dem Wartezeiger. Der Zip-Test deckt jetzt auch den Normalfall: ein
      Körper, Dialog nie geöffnet. Offen bleiben A5 (Profil erst beim
      Slicen gemerkt, nicht beim Schließen) und A6 (kein Abgleich des
      gemerkten Profils mit dem Drucker des Projekts) — beide gering, beide
      im Gering-Block.
- [x] **Mittel-Block Kern**: Platten-Cache verliert
      `findings`/`solver`/`transform`; T-Vernähen quadratisch und doppelt;
      Rückfallkette unabbrechbar; `FIT_TOLERANCE` widerspricht §14;
      `nut_trap`/`printed_thread` mit Konstanten-Toleranz (Kalibrierung
      erreicht sie nie); **eigene Bausteine werden nie geladen** (§24.5 ohne
      Aufrufer); Lizenzprüfung deckt `agent,brep` nicht; beschädigte
      Nutzer-TOML stürzt beim Start ab; Schlüsselwerkzeug erzeugt bei zwei
      Vorratsläufen identische Schlüssel; Zipbomben-Lücke beim 3MF;
      Einheitenantwort landet nicht in den Op-Parametern (§15.1);
      Nullmessung gilt als Übereinstimmung; Baumstützen erreichen Cura nie.

      **Alles behoben und einzeln committet** — mit zwei Vermerken:
      `FIT_TOLERANCE` ist jetzt im Code begründet (Tessellationsrauschen
      ±0,025 mm; mit `EPS_GEOM` wäre jede Passung auf einem exakten Körper
      „verletzt"), aber **§14 ist mit Ansage nachzuziehen** — Robert
      entscheidet. Und die **Einheitenantwort** bleibt offen: die saubere
      Lösung ist eine Entscheidung zwischen „vorab fragen wie die CLI"
      (kostet `read_mesh` doppelt, im Hauptthread) und
      „`history.change_params` nach der Antwort" (kostet eine eigene
      Undo-Stufe: das erste Undo stellte die Frage erneut) — ebenfalls
      Roberts Entscheidung.
- [x] **Mittel-Block Oberfläche**: Arbeiter-Halteleine in fünf Dialogen
      fehlt (Hauptfenster macht es vor — in ein Modul heben); Export rechnet
      im Hauptthread; Sculpting kennt kein Ziehen (20 Züge = 20 Klicks);
      während Gestensitzungen bleiben alle Ops anklickbar und *Fertig*
      verliert dann die Züge; die Befehlspalette umgeht die Gestenmodi und
      kennt keine Verfügbarkeit; Differenzlegende einfarbig; Fenstergeometrie
      wird nie gespeichert.

      **Fast durch:** Halteleine lebt in `app/ui/leash.py` (mit
      Wiederanstoß) und gilt in allen fünf Dialogen; Gestensitzungen sperren
      die Operationen und *Fertig* prüft sein Ziel; `launch_operation` ist
      der eine Einstieg für Menü und Palette, und die Palette zeigt
      Verfügbarkeit mit Grund; der Pinsel malt beim Ziehen (halber Radius
      als Mindestabstand); Legende zweifarbig, Fenstergeometrie gemerkt,
      Druckeinstellungsdialog wird freigegeben, Wandprüfung mit Wartezeiger,
      „Festschreiben" statt „OK". Der Export läuft im Arbeiter
      (`_ExportWorker`, ohne Abbrechen — mit Begründung im Docstring und in
      der Gebietsregel), die Druckeinstellungen öffnen sofort und
      `take_slice_result` trägt die Analyse nach, die synchronen Lesungen
      stehen unter `waiting()`. Und das letzte Paket ist drin: *Formen* und
      *Skelett* stehen als Knöpfe neben *Zeichnen* in der oberen
      Werkzeugleiste (ausgegraut mit Grund über `_pick_hint`), die Tour
      nennt den echten Weg und das Ziehen, und die Stellung eines Skeletts
      ist ein `ArmatureField` mit drei Zahlenfeldern je Knochen statt rohem
      JSON.
- [x] **Gering-Block als eigene Runde**: ~30 englische Docstrings (AGENTS.md
      behauptet Vollständigkeit), acht englische nutzersichtbare Fehlertexte
      in `backends/mesh.py`, „aufgeloest" in `advise.py`, deutsche
      Bezeichner in `tools/check_env.py` (Sprachprüfung sieht `tools/`
      nicht), Zylinder-Sortierung ohne Z, Redirect kann `check_url` umgehen,
      Analysekarten ohne Abbruch, Details in der Datei.

      **Vollständig erledigt** — Sprache (Übersetzungen, `mesh.py`-Texte
      samt Katalogen, `check_env.py`-Bezeichner, Sprachprüfung sieht
      `tools/`) und der Rest: Zylinder-Sortierung mit Z, `check_url` prüft
      den erreichten Ort nach der Weiterleitung, Analysekarten abbrechbar,
      abhängige Felder grauen mit Grund (G3), die Slicer-Wahl wird beim
      Schließen gemerkt (A5) und gegen den Drucker abgeglichen (A6), und
      *Hilfe → Beispiele* führt auf den Startbildschirm.
- [x] **Vier Stellen versprachen es, der Kern antwortete mit einer
      Fehlermeldung.** Ein Gelenkwinkel darf ein Projektparameter sein — das
      sagten der Registereintrag (*„Ein Winkel darf ein Projektparameter
      sein"*), der Docstring von `Pose` (*„`=@arm_angle` in einer Pose, und die
      Passung am Sockel rechnet mit"*), der `fx`-Umschalter am Winkelfeld des
      Dialogs und der Kopf von `tests/test_pose.py`. Wer es tat, las: **„Diese
      Stellung lässt sich nicht lesen."**

      **Der Denkfehler stand im Testkopf.** Dort hieß es, das prüfe „die
      Ausdrucksauflösung der Szene, nicht diese Datei". Sie prüft es nicht:
      `resolve_params` sieht die **oberste** Ebene eines Parametersatzes, und
      die Stellung steht dort als **ein** Wert — ein JSON-Text. Was darin an
      Ausdrücken steckt, sah nie jemand; `pose_from_text._vector` rief
      `float()` darauf. Ein Satz, der die Zuständigkeit woandershin verweist,
      ist genau die Sorte Beleg, die niemand nachprüft.

      Vier Stücke, und drei davon sind Rückwege, die vorher fehlten:

      **Auflösen** — `pose_from_text(text, values)` rechnet einen Winkel wie
      `=@neigung * 2` gegen dieselben Werte wie überall (§13). `values` ist ein
      Vorgabeargument und keine Pflicht, sonst müsste jeder Aufrufer mitziehen,
      auch die, die nie einen Ausdruck sehen. Ein unbekannter Parametername
      bekommt die Meldung des **Auswerters**, nicht die des unlesbaren Textes:
      Die Stellung ist ja gelesen, und wer den falschen Satz liest, sucht am
      JSON statt am Namen.

      **Sammeln** — `pose_parameter_references(text)`, das Gegenstück zu
      `sketch_parameter_references`. `NESTED_REFERENCES` in `evaluate.py` ist
      jetzt eine **Zuordnung statt einer Bedingung**: `sketch` stand dort hart
      verdrahtet, die Pose kam später und wurde übersehen. Ohne den Eintrag
      bliebe der Arm gebeugt, während die Zahl daneben schon die neue ist — die
      Gegenprobe fällt genau daran.

      **Zurücklesen** — `pose_angles(text)` gibt die Rohwerte, Zahl oder
      Ausdruck. Der Dialog **schrieb** einen Ausdruck wörtlich (das sagte sein
      Docstring zu und hielt es), **las** ihn aber über `pose_from_text`
      zurück, und die gibt drei Zahlen: Der Ausdruck ließ sie scheitern, der
      Fang machte daraus ein leeres Raster, und alle drei Winkel des Knochens
      standen auf null. Ein Rundlauf durch den Dialog verlor genau die
      Bindung, die er zu erhalten versprach.

      **Schreiben** — `pose_text(angles)` nimmt beides. Der Dialog hatte sich
      einen **zweiten Schreiber** für dasselbe Format gebaut (`json.dumps`),
      weil der im Kern nur `Pose` nahm und `Pose.angles` drei Zahlen sind —
      genau das, was sein eigener Docstring vermeiden wollte. Jetzt gibt es
      wieder einen.

      Drei Nachträge aus der Nachprüfung, und der erste ist der wertvollste:

      **Der neue Import schloss einen Kreis, und die Suite konnte ihn nicht
      sehen.** `geom.pose` braucht den Auswerter und importiert
      `scene.expressions`; Python lädt dabei das ganze Paket `scene`, dessen
      `__init__` `scene.evaluate` zieht — und das importierte `geom.pose`. In
      der Suite lief das durch, weil `scene` immer vorher dran war. Wer
      `app.core.geom.pose` **als erstes** lud — ein Skript, ein Werkzeug, eine
      Kommandozeile —, bekam einen `ImportError`. `nested_references()` ist
      deshalb träge.

      Der Test dagegen ist der eigentliche Gewinn:
      `test_every_core_module_imports_first` lädt jedes der 151 Kernmodule
      **als erstes**, mit geleertem `sys.modules` dazwischen. Der bisherige
      Test lud sie der Reihe nach in einem Prozess, und das ist schwächer, als
      es aussieht — ein Kreis zwischen zwei Modulen fällt nicht auf, solange
      das eine schon fertig ist, wenn das andere beginnt. Neun Sekunden für
      eine Klasse Fehler, die sonst erst ein Nutzer findet.

      **Der Skelett-Text kommt am Sammler vorbei**, weil beide Felder von
      `PoseParams` `kind="armature"` tragen. Er ist eine JSON-*Liste*, der
      Fang macht daraus ein leeres Ergebnis — richtig, denn ein Knochen ist
      eine Koordinate. Es steht jetzt im Docstring und in einem Test, weil ein
      stiller `AttributeError` wie ein Entwurf aussieht und nicht wie eine
      Entscheidung.

      **`format_version` bleibt bei 8**, und auch das ist eine Entscheidung.
      Das Schema ändert sich nicht — ein größerer Wertebereich in einem Feld
      ist kein neues Feld. Rückwärts gilt es nicht, aber eine Erhöhung würde
      **jede** neue Datei für die alte Version sperren, auch die ohne einen
      einzigen Ausdruck. Die Kette in `migrations.py` erhöht für
      Schemaänderungen, nicht für Fähigkeiten.

      Der kernnahe Cache-Test kam dazu: Der Ende-zu-Ende-Beleg ging über die
      Oberfläche, und fiele Qt aus, fiele der Beleg für §15 mit.
- [x] **Die Operationszahl im Fließtext war weggelaufen.** Das Register
      führt 85; die Funktionsseite sagte 83, die englische 84, während
      beide Startseiten richtig lagen. Der Grund steht weiter oben in
      dieser Datei: „`tests/test_website.py` prüft die Zahl gegen das
      Register und hat es gefangen, bevor die falsche Zahl auf der Seite
      stand" — das galt für die Kennzahlenleiste der zwei Startseiten und
      für sonst nichts. Die Zahl steht aber ein zweites Mal im Text, auf
      der Funktionsseite und in den häufigen Fragen. Der Test liest jetzt
      jede Seite unter `website/` statt einer festen Liste; der Stamm
      „oper" trägt durch alle sechs Sprachen, die Inline-SVG fallen vorher
      heraus (ihr „Vorschlag — 3 Operationen" ist ein Beispiel). Dieselbe
      Zahl stand im README: 84 Schemata und 97 KB, nachgemessen sind es 85
      mit 109 170 Zeichen, rund 107 KB.

      Nachgezogen am 18.08.: `tools.py` nannte 104 KB — gemessen sind es
      110 KB voll und 87 KB kompakt. `.claude/rules/agentenschicht.md`,
      `backends/llm.py` und `tests/test_backends.py` führten dieselben
      „84 Schemata, 99 000 Zeichen, 21 162 Token"; es sind 85 mit 109 170
      Zeichen. Die Tokenzahl kommt aus einem Lauf gegen `qwen3:14b`
      (`prompt_eval_count` bei `num_ctx` 32768, Basislinie ohne Werkzeuge
      abgezogen): **24 474 Token** für die Schemata allein, 26 601 für den
      ganzen Prompt mit allen 96 Werkzeugen, 19 249 für den kompakten Satz,
      den der Ollama-Weg fährt. Keiner davon wurde gekürzt — 81 % des
      Fensters, keine Halbierung, und 4,46 Zeichen je Token passen zur alten
      Messung (4,68). **32768 trägt also weiter**; die Schranke im Test steht
      jetzt auf 25 361 statt 21 162.

      Nebenbefund im selben Docstring: „der doc-Satz und der Menüort machen
      den größten Teil aus" stimmt nicht. Sie sind zusammen 14 013 Zeichen,
      die Parametertexte allein 40 945 — was der Kommentar dreißig Zeilen
      tiefer längst richtig sagte (dort stand 36 KB, gemessen 40 KB).

      Fünf weitere Stellen nannten denselben alten Bestand, ohne ihn zu
      messen: `session.py` („88 Werkzeuge mit 104 KB Schema"), `llm.py` oben
      („dreiundachtzig, rund 96 KB"), `tools/check_local_model.py` („sieben
      statt dreiundachtzig"), `.claude/rules/agentenschicht.md` („gegen 84
      Werkzeuge") und das Konzeptpapier vom August. Sie sind nachgezogen —
      aber nicht durch bloßes Ersetzen der Zahl: Jede nennt die Lage, in der
      **damals** gemessen wurde, und danach den heutigen Bestand. Wer nur die
      Zahl austauscht, behauptet eine Messung, die es nie gab; wer sie stehen
      lässt, beschreibt ein Register, das es nicht mehr gibt. Beides steht
      jetzt nebeneinander, und die Messwerte behalten ihren Bezug.

**Wettbewerb (Recherche 16.08., Quellen in der Durchsichts-Datei):** Die
Chat-Alleinstellung ist seit Zoo „Zookeeper" (01/2026) nicht mehr
konkurrenzlos — verteidigungsfähig als Paket *lokal + kalibrierte Passungen +
Schichtanalyse speist die Konstruktion + Einmalkauf*; kalibrierte Passungen
hat sonst niemand. Gefährlichstes Ökosystem ist Bambu/MakerWorld (Meshy-6,
Hunyuan 3.1, OpenSCAD-Customizer und Slicer-Werkzeuge in einem Gratis-Konto);
Backflip macht seit 03.08. Scan→Feature-Baum für ~10 USD. Die fünf größten
Lücken aus Kundensicht: Weg-3-Einstieg (ComfyUI-Hürde gegen Browser-Klick),
Verrundung auf importierten STLs, Gridfinity-Baustein, Messen am
Referenz-Mesh, Anschluss an fremde `.scad`-Customizer. Preis-Korridor:
69–99 € einmalig, Plasticity (150 USD) als Anker darüber.
## Die Oberfläche im Bild durchgesehen (17.08.2026)

Die vorige Durchsicht endete mit einem Satz, der eine Lücke benannte: *„Nicht
gemessen: das laufende Fenster als Bild. Der Container hier bringt VTK und die
Offscreen-Plattform nicht zusammen."* Diese hier hat genau dort angefangen —
auf einer Maschine, die rendert. Dazu sieben Prüfungen parallel gegen Menüs,
Dialoge, Aussehen, Texte, Rückmeldung, Barrierefreiheit und die vier Wege, jede
mit einer Gegenprüfung, die widerlegen sollte statt zu bestätigen.

**69 Funde haben die Gegenprüfung überlebt**, fünf sind daran gestorben. Was
unten unter „Behoben" steht, hat einen Test; was unter „Offen" steht, ist
belegt und mit Absicht liegen geblieben.

> **Drei der behobenen Funde waren am Quelltext unsichtbar.** Der Achsenmarker,
> die leeren Kästchen am Zahlenfeld und der verschwundene Platzhaltertext sind
> alle drei erst im Bild aufgefallen — und der erste stand seit jeher auf jedem
> Handbuchbild in jeder Sprache.

### Behoben

- [x] **Die Achsenanzeige lag hinter der linken Spalte.** Sichtbar war allein
      die Spitze des roten X-Pfeils, die unter der Karte hervorschaute; das
      sieht aus wie ein Grafikfehler und stand so auf jedem Bildschirmfoto.
      Der Wert `(0.0, 0.0, 0.16, 0.24)` trug die Begründung „unten links, wo
      keine Karte liegt" — dort liegen Objekte, Parameter und Verlauf. Anteile
      können das nicht lösen: Die Karte hält ihren Abstand in Bildpunkten.
      `orientation_corner()` rechnet jetzt aus Punkten, `resizeEvent` zieht
      nach. Unterwegs zwei weitere Funde: Der Docstring beschrieb einen
      anklickbaren Würfel, den es im ganzen Quelltext nicht gibt, und schloss
      mit „er ersetzt aber `add_axes`" — während die Zeilen darunter genau das
      aufrufen. Und `plotter.axes_widget` gibt es in pyvista 0.48 nicht; das
      Nachziehen lief still ins Leere und legte die Anzeige quer über das
      Modell, bis `axes_widget_of()` sie am Renderer suchte.
- [x] **Jedes Zahlenfeld zeigte zwei leere Kästchen statt der Pfeile.** Sobald
      ein Stylesheet an einem `QSpinBox` eine Rahmeneigenschaft setzt — und die
      Regel, die allen Eingabefeldern ihren Radius gibt, tut das —, hört Qt
      auf, dessen Unterelemente zu zeichnen. 27 Felder in 13 Dateien. Ein
      Dreieck aus Rahmenkanten half nicht (Qt füllt die Fläche und malt einen
      hellen Block), also sind es Bilder: zwei SVG im Cache (§38), je Thema in
      seiner Textfarbe geschrieben.
- [x] **Der Platzhaltertext verschwand.** `build_palette` setzte jede Rolle
      außer `PlaceholderText`, und was dort fehlt, kommt vom Betriebssystem.
      Auf einem dunkel eingestellten Windows war er hell — im hellen Thema
      damit weiß auf Weiß. Dreizehn Felder tragen ihre Auskunft dort, darunter
      das Muster `SOLIDON3D-1-…`, das als Einziges sagt, wie ein
      Lizenzschlüssel aussieht.
- [x] **Der Fokusring war im hellen Thema praktisch nicht da**: 2,06 auf einem
      weißen Feld, 1,70 auf dem Fenster, gefordert sind 3,0 (WCAG 1.4.11). Er
      nahm `highlight`; der Bernstein ist für den dunklen Untergrund gewählt.
      Er nimmt jetzt `accent_line` — dieselbe Farbe im dunklen Thema, im hellen
      der abgestufte Ton, den `theme.py` für genau diese Rechnung schon führte.
- [x] **Im Prüfbericht stand jede Zeile unter der Lesbarkeitsgrenze.** Die
      Befunde tragen ihre Rollenfarbe als Schrift (`panels.py`), und die ist
      für Dunkel gewählt: auf der weißen Liste des hellen Themas 2,22 für eine
      Warnung, 2,67 für einen Hinweis, 3,97 für einen Fehler. Der Test dazu
      fand gleich noch einen: Das Fehlerrot bringt auch **dunkel** nur 4,17 —
      im Standardthema, beim Schweregrad, der am dringendsten gelesen wird.
      `text_colour()` wählt den Ton jetzt nach der Helligkeit der Fläche, auf
      die geschrieben wird, nicht nach dem Namen des Themas.
- [x] **Gesperrtes sah aus wie bedienbar.** Die Palette setzte den
      Sperrzustand für `Text` und `ButtonText`, nicht für `WindowText` — und
      daran hängen QLabel, QCheckBox, QRadioButton und QGroupBox. Ein
      gesperrtes Ankreuzfeld war pixelgleich mit einem bedienbaren.
- [x] **Eine Farbe tat zwei Arbeiten und beide schlecht.** `disabled` war
      zugleich die Farbe für Nebentext — Maße, Spaltenköpfe, Gruppentitel, der
      stille Reiter. Damit war Nebentext bei 2,59 unlesbar und Gesperrtes nicht
      als solches zu erkennen. `muted` ist jetzt eine eigene Rolle.
- [x] **Der Splittergriff war einen Bildpunkt breit** — optisch eine Linie,
      praktisch nicht zu treffen. Jetzt zwei Rasterschritte, und er färbt sich
      beim Überfahren.
- [x] **Der Hinweis unter dem Zeiger hatte als einziges Element keine Form**
      und stand im hellen Thema auf dem Blassgelb, das Qt von Windows erbt: die
      einzige Farbe im hellen Thema, die aus keiner Tabelle dieser Anwendung
      stammte.
- [x] **Der Hauptknopf gab beim Drücken nicht nach.** `:default` steht später
      als `:pressed` und wiegt gleich schwer, gewinnt also — der lauteste Knopf
      der Anwendung war der einzige ohne Rückmeldung auf einen Klick.
- [x] **„Einfügen" im Bausteinkatalog versprach eine Wirkung, die er nicht
      hatte.** Ohne Auswahl stand er in voller Akzentfarbe da, nahm den Klick
      an, schloss den Dialog — und setzte nichts: `_accept` rief `accept()`
      auch ohne Baustein. Das ist die stillste Art, jemanden ratlos zu machen.
- [x] **Der Rat des Kernautors kam nie an.** Von 48 Kennungen, die der Kern in
      `Action(...)` vergibt, sind zehn verdrahtet; die übrigen wurden im
      Fehlerdialog verworfen, und an ihrer Stelle stand „Fehlerbericht
      erstellen" als Hauptknopf — auf einen reinen Bedienfehler, obwohl der
      Bericht laut `errors.py` dem `InternalError` gehört. Sätze wie
      „Schreiben Sie das Ziel als obj_2:hole_1." landeten im Nichts. Sie
      werden jetzt gelesen statt geklickt: Knöpfe bleiben denen vorbehalten,
      die etwas tun, der Rest steht als Text im Dialog (§2.7).
- [x] **Die Handbuchbilder zeigten die Oberfläche von vor dem Trennwerkzeug** —
      sieben Knöpfe statt acht, in allen sechs Sprachen. Alle 36 sind neu.
- [x] **Die Ebenentasten 1, 2 und 3 im Skizzeneditor taten nichts.** Die Ziffern
      des Ansicht-Menüs lagen darüber, und Qt lässt bei zwei aktiven Kürzeln
      derselben Taste keines von beiden feuern — eine Regel, die
      `main_window.py` selbst aufstellt und bis dahin nur auf `R` und `C`
      anwandte. Die Zeichenfläche versprach die Taste sichtbar: „(1)", „(2)",
      „(3)" stehen am Ebenenfeld und noch einmal im Tooltip. Die Einträge unter
      *Darstellung* sind im Skizzenmodus jetzt gesperrt — sie wirken dort
      ohnehin auf einen Viewport, den `start_sketch` aus dem Stapel nimmt. Der
      alte Test rief `choose_plane` an einem nackten Panel, also in genau der
      Umgebung ohne den Konflikt; der neue drückt die Taste im gebauten Fenster
      und macht im selben Lauf die Gegenprobe mit wieder aktiven Kürzeln.
- [x] **Der Download-Arbeiter fehlte beim Schließen.** Er folgt dem Muster mit
      `_retire` und `_hold_until_done` sauber, aber in `_retired` landet er
      erst, wenn er fertig ist — solange er lief, hielt ihn allein sein Feld,
      und `wait_for_workers` kannte es nicht. Ein Thread, der sein Fenster
      überlebt, nimmt den Prozess mit. Ein Test liest die Aufzählung jetzt
      gegen die Felder, damit der nächste nicht wieder durchrutscht.

### Offen

- [x] **Die Live-Vorschau rechnete den ganzen Stapel neu**, obwohl ihr
      Docstring seit jeher das Gegenteil zusagt: „der Cache trägt alle
      Schritte, die schon gerechnet sind". Der Aufruf reichte ihn nie durch —
      bei einem Dokument mit zwanzig Schritten also neunzehn fertige, für jede
      Änderung an einer einzigen Zahl. Voraussetzung dafür war ein Schloss im
      `ResultCache`: `_store` sind vier Schritte, und Auswertung, Agent und
      Vorschau schreiben aus eigenen Fäden hinein.

      **Der Test dazu war im ersten Anlauf wertlos**, und das ist die Lehre.
      Er war grün — aber auch ohne Schloss: Mit dem üblichen Umschaltintervall
      von fünf Millisekunden trifft der Fadenwechsel praktisch nie in die vier
      Schritte, die Gegenprobe lief null von fünf Mal auseinander. Mit einer
      Mikrosekunde fällt sie zehn von zehn. Wer hier etwas prüft, stellt das
      Intervall — sonst prüft er nichts.
- [x] **Der Slicer-Lauf ist abbrechbar.** `Popen` statt `run`, ein
      Abbruch-Token, das die Warteschleife abfragt, `terminate()` darauf, ein
      Abbrechen-Knopf am Fortschritt und ein `closeEvent`, das abbricht statt
      zu warten. Gebaut in einer parallelen Sitzung, genau auf dem Weg, den
      die Durchsicht vorgeschlagen hatte.
- [x] **Der Rest der Abbruchpunkte.** Fünf Stellen, und sie hatten alle
      dieselbe Bauart: Der Knopf wirkte, die Maschine hörte nicht auf.

      **Die Vorschau verwarf, statt anzuhalten.** `cancel_preview` erhöhte die
      Generation — das Ergebnis flog weg, die Rechnung lief zu Ende. Wer einen
      Dialog über einem großen Körper schloss, ließ zwei Boolesche Operationen
      je Körper hinter sich, und beim schnellen Tippen stapelten sie sich. Jeder
      Arbeiter führt jetzt ein **eigenes** `CancelSignal`; ein geteiltes mit
      `reset()` davor wäre ein Wettlauf, in dem der alte Lauf den gesetzten
      Zustand womöglich nie sieht. Eine neuere Anfrage bricht die älteren ab.

      **Die Trennebenensuche kannte keinen Abbruch von innen** — der Docstring
      sagte das sogar, als wäre es eine Eigenschaft. Sie schneidet jede
      Kandidatenebene durch das ganze Netz, Minuten an einem großen Körper, und
      „Abbrechen" hieß bisher: *das Ergebnis wird verworfen, wenn es kommt*.
      Das Token geht jetzt durch `plan_split` → `split_to_fit` → `find_plane`
      → `_judge`. Der Sonderfall dort ist die **Blockbildung**: Ein einziger
      Aufruf über alle Ebenen ist von außen nicht zu unterbrechen, und genau er
      ist die Minute — `_sections_in_blocks` schneidet zu acht und fragt
      dazwischen. Zusammengelegt wird gruppenweise, nicht blockweise, sonst
      stünde die Bewertung vor der falschen Nachbarschaft.

      **Im Erzeugen-Dialog war „Abbrechen" während des Laufs gesperrt** —
      `setEnabled(False)` traf die ganze Leiste und damit ausgerechnet den
      einen Knopf, den man bei einer Rechnung von Minuten braucht. Der Ausgang
      selbst war fertig gebaut (`reject` wartet auf den Thread), unerreichbar
      war nur sein Knopf; es blieb Esc, eine Taste, die niemand sucht, solange
      der Weg daneben grau dasteht. Dabei kam ein zweiter Fund mit heraus, den
      die gesperrte Leiste **verdeckt** hatte: `_update_state` hängt am
      Textfeld, und das bleibt bedienbar — wer weitertippte, machte *Erzeugen*
      wieder klickbar und startete einen zweiten Arbeiter über den ersten.

      **Eine abgebrochene Auswertung sagte es nur der Logdatei.** Balken weg,
      Knopf weg, dieselbe Ansicht wie vorher: von außen nicht zu unterscheiden
      von einer Rechnung, die *fertig* geworden ist. Der Satz nennt jetzt
      beides — das Aufhören und den Stand, den man vor sich hat —, und er geht
      in `_announcement`, damit ihn das nächste `_on_busy` nicht wegwischt.
      Gemeldet wird **nur der Abbruch durch einen Menschen**: Eine neuere
      Anfrage bricht die laufende ebenfalls ab, und das im Sekundentakt zu
      melden hieße, beim Ziehen an einem Schieber „abgebrochen" zu schreiben.

      **Speichern blockierte ohne jedes Zeichen.** Gemessen: 903 ms für ein
      Projekt mit einem 62-MiB-Netz — nach §2.8 die mittlere Stufe, Mauszeiger
      *und* Statusleiste, und beide fehlten. Kein Arbeiter dafür: Das Schreiben
      mutiert nichts, es blockiert einmal und ist fertig; ein Thread brächte
      Halteleine, Fehlerpfad und die Frage, was passiert, wenn dazwischen
      jemand weiterarbeitet. Die Zeile zeichnet sich vor dem Blockieren selbst
      neu (`repaint`, nicht `processEvents` — das eine Widget statt fremder
      Eingaben mitten im Aufruf).

      Die **Analysekarte** war der einzige Teil des Punkts, der schon stand:
      sie fragt am Eingang und in ihrer teuersten Schleife (`CANCEL_EVERY`).

      Und ein Nachbarfund: `_preview_finished` entfernte seinen Arbeiter
      **im** `finished`-Slot aus der Liste — die erste Hälfte der Falle aus der
      Gebietsregel, denn `finished` heißt „`run` ist zurück", nicht „das Objekt
      darf weg". Er geht jetzt denselben Weg über die Halteleine wie alle
      anderen.
- [x] **Die Befehlspalette ist der Universalzugang aus §19.2.** 38 von 136
      Menüzeilen fehlten, weil neben der Leiste ein von Hand gepflegtes
      Wörterbuch stand — und von Hand heißt driften. Gelesen wird jetzt die
      Leiste selbst: 82 Operationen kommen weiter aus dem Register (dort
      tragen sie Beschreibung, Kategorie und Verfügbarkeit), 60 Fensterbefehle
      aus dem Menü. Draußen bleiben genau zwei, und der Test nennt sie
      namentlich: *Beenden* ist in einer Liste, durch die man tippt, ein Klick
      zu nah am Verlust der Arbeit, und *Befehlspalette* öffnete sich selbst.
- [x] **Die Suche der Palette kannte weder Umlautfaltung noch ein Synonym.**
      Der Zugang stand, das Finden nicht: Wer „aushoehlen" tippte — und wer
      keine Umlaute auf der Tastatur hat, tippt so —, bekam **null Treffer**
      auf eine Operation, die es gibt. Dasselbe bei „groesse". Gemessen, nicht
      vermutet: die Zahlen unten sind vorher/nachher aus demselben Register.

      Drei Dinge, und jedes löst einen eigenen Fall:

      **Gefaltet wird auf beiden Seiten** (`fold`). „aushoehlen" findet
      „Aushöhlen", „Größe" findet, was intern `groesse` heißt. Angezeigt bleibt,
      was dasteht — gefaltet wird nur der Vergleich.

      **Der Wortstamm ist die zweite Runde, nicht die erste** (`matches(…,
      stem=True)`). „bohren" fand nichts, weil die Operation „Bohrung setzen"
      heißt — ein Fall, den keine Synonymtabelle je vollständig abdeckt und den
      die ersten Buchstaben lösen. Gelockert wird **erst, wenn die genaue Suche
      leer ausgeht**: immer zu lockern hieße, zwischen guten Treffern dauerhaft
      Ungefähres zu zeigen.

      **Ein Treffer im Titel wiegt schwerer als einer in der Beschreibung**
      (`rank`). Bei „bohrung" stand „An Merkmal ausrichten" vorn, weil dessen
      Beschreibung das Wort enthält, und „Bohrung setzen" auf Platz drei. Wer
      tippt, meint fast immer den Namen. Sortiert wird **stabil**, damit die
      Reihenfolge aus `applies_to` innerhalb derselben Güte stehen bleibt.

      | Eingabe | vorher | nachher | zuerst |
      |---|---|---|---|
      | `aushoehlen` | 0 | 2 | Aushöhlen |
      | `bohren` | 0 | 7 | Bohrung setzen |
      | `groesse` | 0 | 5 | Bohrung setzen |
      | `bohrung` | 7 | 7 | Bohrung setzen *(war: An Merkmal ausrichten)* |

      **Der Deckel auf dem Stamm ist der eigentliche Fund** (`STEM_CUT`). Die
      Untergrenze von vier Zeichen allein genügte nicht: „gibtsnicht" fand
      **acht** Einträge, weil „gibt" in acht Beschreibungen steht — und die
      Zeile „Kein Befehl passt zu …" kam nie zum Vorschein. Ein Stamm ist ein
      *gekürztes* Wort, kein beliebiger Anfang; höchstens drei Zeichen dürfen
      fallen. Aufgefallen ist das nicht beim Nachdenken, sondern weil ein
      **bestehender** Test rot wurde — der, der die Auskunftszeile prüft.

      Die **Bauart-Prüfung** war der dritte Teil des Punkts und ist bereits
      erledigt: `_palette_availability` liest sie aus denselben Menü-Actions,
      und ein nicht ausführbarer Eintrag steht ausgegraut da **samt Grund** —
      ausgrauen allein wäre die halbe Antwort (Regel 18).
- [x] **Zurückgenommen: Im deutschen Handbuchbild steht ein Komma, kein
      Punkt.** Der Fund war meiner, und er war falsch. Was ihn erzeugt hat, ist
      lehrreicher als er selbst.

      **Die Messung taugte nicht.** Ob ein Zeichen ein Komma ist, habe ich
      daran geprüft, ob es unter die Grundlinie reicht. Bei 9 pt tut das in
      Segoe UI **auch ein echtes Komma nicht** — es ist schlicht zu klein.
      Zwei Referenzfelder, eines mit „80,00" und eines mit „80.00", im selben
      Widget gerendert, unterscheiden sich in genau **sechs Bildpunkten**:

      ```
      Komma  y=15:  ####..####.##..####..####
      Punkt  y=15:  ####..####.###.####..####
      echtes Feld:  ####..####.##..####..####
      ```

      Zwei Punkte breit, nicht drei — das ist das Komma. Dazu kam die
      achtfache Vergrößerung, in der zwei Pixel auf der Grundlinie aussehen
      wie ein runder Punkt.

      **Was daran hängen blieb**, weil es teuer war: Ein Widerspruch zwischen
      dem, was ein Widget meldet (`lineEdit().text()` sagte durchweg Komma),
      und dem, was man im Bild zu sehen glaubt, ist zuerst ein Verdacht gegen
      die eigene Messung — nicht gegen Qt. Die Stunden, die hier in
      `QLocale`, `translate_parameter_titles` und die Aufnahmereihenfolge
      gingen, hätte ein Vergleich mit einer **Referenz** in fünf Minuten
      gespart: dasselbe Widget zweimal rendern, einmal mit dem vermuteten
      Falschen, einmal mit dem Richtigen.

- [x] **Weg 4 stand in keiner Unterlage** — und der Test wusste es besser als
      sie alle. `test_there_is_one_example_per_way` prüft seit P16 auf vier
      Wege, das Beispielprojekt liegt bei, das Handbuch hat sein Kapitel, die
      Oberflächenregel führt *Formen* und *Skelett* in der Werkzeugleiste.
      Nachgezogen sind jetzt die drei Stellen, die zurückhingen: §2.2 des
      Bauplans hieß „Drei Hauptwege" und listet den vierten jetzt mit seinem
      Ablauf (Grundkörper → verschmelzen → ausformen → exportieren) und mit dem
      Satz, warum Regel 2 dort besonders scharf gilt — hier zählt eine Geste
      und keine Zahl. Die README sprach von drei Wegen und acht
      Beispielprojekten, es sind vier und neun. Und die gezeichnete Abbildung
      im Handbuch zeigte drei Zeilen, während der Text daneben vier beschrieb;
      ihre Höhe folgt jetzt der Zahl der Zeilen, sonst stünde die nächste
      außerhalb des Bildes.
      Damit das nicht wieder driftet, zählt ein Test die Wege und die Beispiele
      **gegen `EXAMPLES`** und liest beide Unterlagen — samt der Tabelle in der
      README, in der jedes Beispiel seine Zeile haben muss. Die Website war
      bereits richtig; ihre 43 Zahlenprüfungen sind grün.

- [x] **Der Rest der Textfunde.** Drei Stück, und das zweite war das
      lehrreichste.

      **168 rohe Bezeichner gingen an den Nutzer.** „oversize_mm: 12.4" im
      Befund-Tooltip, „open_edges: 6" in den Einzelheiten eines Fehlers — eine
      feste englische Zeichenkette in der Oberfläche mit einem Umweg (Regel
      20). `value_label` in `app/ui/labels.py` übersetzt jetzt 156 Stämme; die
      **Einheit steht nicht im Wörterbuch**, sondern kommt aus dem Suffix, also
      teilen sich `size` und `size_mm` einen Eintrag und ein neuer Schlüssel
      mit bekanntem Stamm ist schon übersetzt. Vollständig gehalten wird die
      Liste **nicht von Hand** — von Hand heißt driften, daran war das
      Palettenwörterbuch gescheitert: `tests/test_value_labels.py` liest jeden
      `values=`-Schlüssel per AST aus `app/core` und wird rot, wenn einer keine
      Beschriftung hat. Und andersherum genauso, damit keine Beschriftung ohne
      Schlüssel fünf Kataloge belastet. Nebenbefund dabei: zwei Schlüssel
      hießen `erwartet` und `vorhanden` — **deutsch**, in einem Feld, das
      englisch zu sein hat.

      **Drei fertige Handlungen, an eine Ausnahme gehängt, die niemand wirft.**
      `OutOfBuildVolume` steht in `errors.py` mit *Modell teilen*, *Auf den
      Bauraum verkleinern* und *Anderes Druckerprofil wählen* — und keine Zeile
      im Programm erzeugt sie je. Das ist auch richtig so: Bauraum ist ein
      Bericht und keine Sperre (§29), gemeldet wird `arrange.out_of_build_volume`
      als Befund. Damit war der einzige Weg zu drei vollständig gebauten
      Vorschlägen zugemauert, und der Prüfbericht sagte, was nicht stimmt, und
      hörte auf — die halbe Antwort von §2.7.

      Der Befund bekommt jetzt ein **Kontextmenü** (`FINDING_ACTIONS`), das
      dieselben Handler ruft wie der Fehlerdialog; `as_error` verpackt ihn
      dafür, statt jede Handlung zweimal zu schreiben. Angeboten wird nur, wofür
      es einen Handler gibt — ein Befund ohne Handlung bekommt **kein leeres
      Menü**. Damit eine Handlung überhaupt greifen kann, trägt
      `check_build_volume` die Objektkennung mit: vorher stand dort nur ein
      laufender Index, und ein Bericht, der nicht sagt **welches** Teil zu groß
      ist, kann auch nichts dagegen anbieten.

      Und der Handler dahinter tat nichts: `_scale_after_error` las
      `build_volume` und `size` aus den Werten — zwei Schlüssel, die **weder
      Ausnahme noch Befund** je trägt. Die Bedingung darunter griff also immer,
      und die Methode kehrte still zurück. Gerechnet wird jetzt aus Profil und
      Szene; das ist keine zweite Wahrheit, sondern dieselbe, aus der auch
      `check_build_volume` rechnet.

      **Die Restzeitschätzung stand am falschen Ort.** §2.8 verlangt sie über
      zehn Sekunden — sie hing am Ladeschleier, und den gibt es nur, solange
      **kein** Körper dasteht. Bei jeder langen Rechnung an einem geladenen
      Modell, also genau im gemeinten Fall, stand in der Statusleiste Prozent
      ohne jede Zeitangabe. `remaining_time` ist jetzt eine freie Funktion,
      die beide benutzen.

> **Nachtrag vom 18.08.2026, beim Zusammenführen.** Zwei dieser Punkte hat eine
> parallele Sitzung in denselben Tagen erledigt, und das ist der Grund, warum
> sie hier nicht mehr stehen. Die vier Dialoge halten ihren Arbeiter jetzt über
> `app/ui/leash.py` — genau der Umbau, der oben als Weg beschrieben stand, mit
> einem eigenen Modul, aus dem Fenster und Dialoge erben. Und die Legende der
> Differenzansicht war dort unabhängig gefunden und behoben worden: zweimal
> derselbe Befund aus zwei Richtungen, was für ihn spricht. Geblieben ist die
> Version mit Farbfeld und gerechneter Schrift, weil sie neben der Zuordnung
> auch den Kontrast löst — als bloße Schriftfarbe kam die Legende in Graustufen
> auf 1,16 gegen ihr Band.

### Was die Durchsicht entlastet hat

Gezielt geprüft und in Ordnung: Der Prüfbericht trägt zu jeder Farbe ein
Symbol, die Menüs grauen vollständig richtig aus, die gestufte Tiefe hält in
jedem Operationsdialog außer dem einen oben, kein Parameter steht ohne `doc`,
und die Zahlenfelder der Skizzenleiste erklären sich über Tooltips. Fünf
gemeldete Funde sind an der Gegenprüfung gestorben — darunter die Behauptung,
der Startbildschirm trage einen veralteten Produktnamen: Die Domain heißt
`solidon3d.de`, und „Solidon3D" ist der Name, nicht der Rest eines alten.


## Die Bedienverträge durchgesehen (20.08.2026)

Geprüft wurde, was die Anwendung dem Nutzer *zusagt*, gegen das, was sie tut —
Registerfeld, Dialogtext, Knopf, Docstring, Testname. Der Begriff stand
nirgends im Repository; er kommt aus den fünf Commits davor, die alle dasselbe
Muster hatten. Durchgesehen: 85 Operationen mit 446 Parametern, 17 Bausteine
mit 79 Parametern, 22 Einstellungen, 126 Befundcodes, 29 Oberflächendateien.

**Was hält, und das ist der größere Teil.** Alle 446 Operationsparameter und
alle 79 Bausteinparameter werden gelesen — die drei Verdachtsfälle löste eine
Hilfsfunktion auf. Alle 22 Einstellungen werden gelesen. `takes_whole_scene`
beachten alle vier Oberflächen. Regel 19: genau eine Bestätigung, und sie
bewacht das Festschreiben einer Formsitzung. Regel 21: der Vorschau-Rückfall
`_no_questions` hält an, statt zu raten. `show_error` führt die gewählte
Handlung selbst aus und bietet nur an, was verdrahtet ist. Der Schnittschieber
ist entprellt.

### Behoben

- [x] **Zwei Wiederherstellungsdialoge, eine Lehre — und die war nur an einem
      angekommen.** `_offer_recovery` begründet seit einer früheren Runde
      ausführlich, warum „Ja"/„Nein" nicht taugt und warum das Alter der
      Sicherung dabeistehen muss. Sein Zwilling für namenlose Projekte,
      dreihundert Zeilen darüber, hatte beides nicht: `QMessageBox.question`
      mit Yes/No, und kein Wort dazu, wie alt die Sicherung ist — dabei ist sie
      dort das Einzige, was es gibt. `_ask_recovery` ist jetzt der Aufbau für
      beide Fälle; der Unterschied zwischen ihnen ist der Text und nicht die
      Bauart. `_when` gilt damit auch für den namenlosen Fall.

      **Ein Bruch zwischen Code und Katalog fiel dabei mit heraus.** Der Code
      fragte `„Sicherung: {backup}\nGespeicherter Stand: {saved}"` ab — einen
      Schlüssel, den **kein** Katalog trug, während die drei aufgeteilten leer
      danebenstanden. `test_translations.py` war deshalb rot, in allen fünf
      Sprachen; der Text fiel im Dialog auf die deutsche Quelle zurück.

      Und eine Bauart-Prüfung dazu: `QMessageBox.question` und
      `StandardButton.Yes` kommen in `app/ui/` nicht mehr vor, und
      `test_no_question_box_asks_yes_or_no` hält es dabei. Der nächste Ja/Nein-
      Dialog liest sich beim Schreiben jedes Mal harmlos.
- [x] **Ein Feld ohne Wirkung sagt es — an elf statt an einer Stelle.**
      `DEPENDENT_FIELDS` hatte einen Eintrag, während fünf Operationen bedingte
      Felder trugen. *Kopien in Reihe oder Kreis* allein sechs: Wer auf
      „kreisförmig" stellte, sah *Abstand* und *Richtung X/Y/Z* bedienbar
      dastehen, und die Operation liest sie im anderen Zweig. Bei *Textur
      aufbringen* ist es schärfer als ein Übergehen — beim Umlaufen setzt der
      Code die Drehung auf `0.0`, überschreibt den eingetragenen Wert also,
      wortlos.

      **Die `doc`-Sätze wussten es längst** („Von Mitte zu Mitte, bei der
      linearen Art", „Nur beim Umlaufen", „die Tiefe zählt dann nicht"). Die
      Angabe stand im Tooltip eines Feldes und nicht dort, wo sie wirkt.

      Der Haken ist eine neue Sorte in dieser Tabelle und brauchte zwei Dinge:
      einen **typtreuen** Vergleich, denn über `str()` hieße der gesuchte Wert
      „True" — und `1 == True` machte eine Anzahl von 1 zu einem gesetzten
      Haken; und einen eigenen Satz, denn „Wirkt nur, wenn „Gründlich suchen"
      auf „True" steht" ist die Bauart der Anwendung und nicht ihre Bedienung.

      **Der lehrreichste Fall stand in keiner der beiden Durchsichten, die dem
      Test vorausgingen:** `sketch_pocket.depth`. *Tiefe* steht vorn,
      *Durchgehend* hinten, und dessen doc-Satz sagt selbst, dass die Tiefe
      dann nicht zählt. Gefunden hat ihn erst der Test — Grund genug, ihn zu
      haben: `test_a_field_without_effect_says_so` liest den Quelltext jeder
      Operation und meldet jeden Parameter, dessen sämtliche Lesestellen in
      einem Zweig über einen Umschalter derselben Operation liegen.

      Zwei Verfeinerungen brauchte die Heuristik, und beide sind der Grund,
      warum sie brauchbar ist statt abgeschaltet: **in genau einem Zweig**
      gelesen, denn `apply_texture` liest seine sechs Platzierungswerte in
      beiden und wirkt damit immer; und **kein Aufruf, der den ganzen
      Parametersatz weitergibt**, denn `arrange_bed` liest sein `spacing` in
      `_arranged_by_material(ctx, params)`, wo der Blick von außen endet. Ohne
      die zweite Regel meldete die Prüfung acht Funde, von denen sieben keine
      waren.

      **Die Tabelle steht damit über ihrer eigenen Schwelle.** Ihr Kopf sagt
      seit je: „Wächst die Liste über eine Handvoll hinaus, gehört die
      Abhängigkeit an den Parameter." Elf Einträge sind darüber. Der Satz ist
      jetzt kein stiller Vorbehalt mehr, sondern benennt den fälligen Umbau —
      `ParamSpec` bekäme ein Feld, das Dialog, Kommandozeile, Handbuch und
      Agent gleichermaßen lesen. Das ist eine Entscheidung über den Vertrag aus
      §10 und keine Zeile in `op_dialog.py`, also steht sie unten als offener
      Punkt und nicht als Nebenwirkung.

### Offen

- [x] **`caveat` erreichte nur das Handbuch.** Zwölf Operationen tragen einen
      Vorbehalt („Nicht ohne Entlüftung, wenn im Slicer Stützen entstehen"),
      und die einzige Lesestelle im ganzen Programm war `documentation()`. Der
      Menüeintrag setzte `spec.doc` als Tooltip, der Dialog zeigte `spec.doc`
      als Beschreibung, `tool_schemas` gab dem Agenten `spec.doc` — an keiner
      dieser drei Stellen kam der Vorbehalt an, also nirgends dort, wo jemand
      die Operation gerade wählt. Der Docstring des Feldes argumentiert selbst
      mit der Oberfläche („dann steht neben jedem Menüeintrag eine Warnung"):
      Er nahm an, dass das Feld dort ankommt.

      `caveat_line()` ist jetzt die eine Quelle, und sie trägt auch das Wort
      davor — `caveat` ohne Vorwort liest sich als Fortsetzung des
      `doc`-Satzes, und genau davor warnt die Deklaration des Feldes. Drei
      Verwendungen: das Handbuch mit Sternchen (`markup=True`, derselbe String
      wie vorher), der Menü-Tooltip mit Leerzeile darunter, und der Dialog als
      **eigenes Label** — halbfett, mit dem Wort als zweiter Kodierung
      (Regel 18).

      Die Statuszeile bekommt ihn **nicht**: Sie ist eine Zeile, und eine
      abgeschnittene Warnung ist schlimmer als keine.

      Der Agent bekommt ihn ebenfalls — er wählt aus derselben Auskunft wie ein
      Mensch (§10, Leitprinzip 3). Ohne sie konnte er *Gitter füllen* für ein
      Teil vorschlagen, das dicht sein muss, und nichts in seiner Werkzeugliste
      sagte, dass das die falsche Wahl ist.

      Ein Fund in der eigenen Umsetzung kam dabei heraus: Das Label zuerst nur
      zu bauen, wenn es beim Öffnen etwas zu sagen hat, hätte einen
      Variantenwechsel **zu** einer Grenze hin stumm gelassen — `switch_variant`
      fände `None`. Es entsteht jetzt immer und ist sichtbar, wenn es Inhalt
      hat.
- [x] **Die Anzeigeeinheit erreichte drei Anzeigen — und der Test, der das
      Gegenteil behauptete, prüfte zwei.** `test_the_display_unit_reaches_
      everything_that_shows_a_length` prüfte Statusleiste und Objektbaum. Ein
      Testname ist eine Zusage, und diese war die gefährlichste Art: Weil der
      Test grün stand, sah der Vertrag erfüllt aus.

      Elf Textausgaben standen weiter auf der Vorgabe `unit="mm"` — der ganze
      Skizzeneditor, die Analyseleiste, die Schnittleiste und die
      Merkmalsbeschriftungen. Wer auf Zoll stellte, las im selben Fenster
      beides, im Skizzeneditor als Zahl ohne Einheit dazu.

      **Die Einheit ist jetzt ein Zustand, wie die Sprache einer ist**
      (`labels.set_display_unit`, `display_unit()`). Durch vierundzwanzig
      Konstruktoren zu reichen war der Weg dorthin, und er hätte beim nächsten
      Widget wieder eine Stelle vergessen: `labels.length` rufen Funktionen
      **ohne Widget** — die Merkmalsbeschriftung entsteht in der Überlagerung,
      im Objektbaum und in der Statusleiste. Ein ausdrücklich übergebenes
      Argument gewinnt weiter; das ist kein zweites Verzeichnis, sondern ein
      Vorrang.

      **Die Kopfzeile hing einen Schritt nach**, und der Grund war eine zweite
      Quelle: `_update_header` las `settings.display_unit` statt den Zustand.
      Beides war dasselbe, solange nur `_apply_settings` es setzte — genau
      darauf hatte es sich verlassen.

      Zwei Dinge, die der Umbau **nicht** durfte und die ihn erst sicher
      machten. `measured_expression` schreibt den Abstand zweier Punkte in ein
      **Maßfeld** und formatiert selbst — dort wäre eine umgerechnete Zahl ein
      Datenfehler und kein Anzeigefehler. Und die dreizehn Suffixe an
      Eingabefeldern bleiben, wo sie sind: Nur das Kürzel zu tauschen, ohne den
      Wert umzurechnen, hätte „20,00 in" an einen Wert von 20 mm geschrieben —
      schlimmer als vorher.

      Der Preis des Zustands steht in `tests/conftest.py`: Eine Fixture setzt
      ihn nach jedem Test zurück, sonst nähme ein Test, der auf Zoll stellt,
      jeden folgenden mit.
- [x] **`agent.not_watertight` trug keine Handlung.** Drei Befunde melden
      dasselbe Problem; `export.not_watertight` und `ingest.not_watertight`
      tragen beide *Reparieren und erneut versuchen* und *Stellen zeigen*,
      `agent.not_watertight` trug die Objektkennung und kein Menü. Wer über den
      Chat ein Objekt aufriss, bekam den Satz und sonst nichts — obwohl beide
      Handler gebaut und verdrahtet sind. Er ist dabei der einzige der drei,
      der seine Objektkennung mitbringt: `_object_of` muss hier nicht raten.

      Geprüft wird jetzt die **Familie** und nicht der Einzelfall
      (`test_the_same_problem_offers_the_same_actions`): Befunde mit demselben
      Namen hinter dem Punkt melden dasselbe Problem, und wenn einer von ihnen
      eine Handlung trägt, müssen es alle. Ein vierter Melder wird damit rot
      statt still — der dritte war still.
- [x] **Die Operationsdialoge nehmen jetzt Zoll — und geben Millimeter.**
      222 Parameter tragen `unit="mm"`, und jedes ihrer Felder schrieb `[mm]`
      aus dem Schema und nahm Millimeter, gleich was eingestellt war. `ValueField`
      rechnet jetzt an einer Stelle um: Grenzen, Nachkommastellen, Schrittweite
      und Beschriftung folgen der Anzeigeeinheit, der Kern bekommt in jedem Fall
      Millimeter (§11.1).

      Drei Dinge, die dabei nicht passieren durften. **Ein Winkel bleibt ein
      Winkel** — 30 Parameter tragen „grad" oder „°", und umgerechnet wird
      ausschließlich `unit="mm"`. **Ein Ausdruck bleibt wörtlich**: `=@breite/2`
      in eine Zahl zu verwandeln hieße, die Bindung zu verlieren. Und die
      **Schrittweite** ist `from_mm(1.0)` statt Qts Vorgabe 1.0 — ein ganzer
      Zoll je Klick wäre ein Sprung über den Wertebereich einer Wandstärke.

      **Der Fund kam aus dem eigenen Test, und er war der wichtigste dieser
      Runde:** 40 mm sind 1,5748 Zoll, und aus 1,5748 Zoll werden 39,99992 mm.
      Die Anzeige rundet auf ihre vier Stellen, und die Rückrechnung schriebe
      diese Rundung als Wert fest. Wer im Verlauf eine Operation aufschlägt, sie
      *ansieht* und bestätigt, hätte jedes Maß verschoben — beim Quader dreimal.
      Das Feld merkt sich deshalb den Wert, mit dem es gefüllt wurde, und gibt
      ihn unverändert zurück, solange die Anzeige ihn noch zeigt; verglichen
      wird auf Anzeigegenauigkeit und nicht mit `==` (Regel 6). Geprüft wird das
      über **jeden** Längenparameter jeder Operation, denn der Fehler hängt an
      der Zahl: 40 trifft es, 25,4 nicht.

      Auch in Zoll bleibt ein feines Feld fein: `decimals_for` ist jetzt
      öffentlich, und die Stellenzahl der Einheit trägt die Feinheitsregel
      obendrauf. Mit zwei Stellen wäre das Spiel aus einem Materialprofil nicht
      eintippbar — ein Hundertstelmillimeter ist ein Vierteltausendstel Zoll.
- [x] **Die dreizehn Felder der Leisten sprechen jetzt die Anzeigeeinheit.**
      Pinselradius, Formradius und -stärke, Schnittposition, Scheibendicke,
      Fangweite, Versatz, Messfeld, Rasterweite, Punktkoordinaten und die
      Zugleiste holten ihr Suffix aus `DISPLAY_UNITS[0]` — dem **ersten
      Eintrag** der Tabelle, also immer „mm".

      **Der Aufwand lag nicht am Suffix, sondern an den Lesestellen.** Die
      Leisten gaben `spin.value()` an den Kern; nur das Kürzel zu tauschen
      hätte „20,00 in" über einen Wert von 20 mm geschrieben. `LengthSpin`
      (`app/ui/labels.py`) stellt beide Seiten zusammen: Wer setzt oder liest,
      tut es in Millimetern (`value_mm`, `set_value_mm`, `set_range_mm`), und
      was im Feld steht, ist eine Anzeige. Damit ist die Umrechnung an einer
      Stelle statt dreizehnmal — und eine Lesestelle, die sie vergisst, gibt es
      nicht: `value()` heißt hier nicht mehr, was der Kern will.

      Vier Feinheiten, jede aus einem eigenen Fehler:

      * **Die Grenzen wandern mit.** Eine Untergrenze von 0,1 mm wäre als 0,1 in
        das Fünfundzwanzigfache.
      * **Die Feinheit auch.** Mit zwei Stellen wäre dieselbe Untergrenze in Zoll
        auf null gerundet, und `setRange` **nach** `setDecimals` — Qt schneidet.
      * **Die Schrittweite ist physisch**, nicht die gleiche Zahl: `from_mm(1.0)`
        statt Qts Vorgabe, sonst trägt ein Klick den fünfundzwanzigfachen Weg.
      * **Der Regler bleibt die Wahrheit.** In der Schnittleiste liest `_typed`
        jetzt `value_mm()` und nicht das Argument des Signals — das trägt die
        Anzeige, und in Zoll wäre der Regler auf ein Fünfundzwanzigstel der
        gemeinten Höhe gesprungen.

      Die Zugleiste zeigt drei Arten von Zahl im selben Feld — Strecke, Winkel,
      Faktor —, also führt sie mit, welche gerade dasteht (`follow_length` neben
      `follow`). Ohne die Unterscheidung hätte die Rückrechnung aus 45 Grad eine
      Strecke von 1143 Millimetern gemacht.

      Gehalten wird das von einer Bauart-Prüfung, die den **Syntaxbaum** liest
      und nicht den Text: `DISPLAY_UNITS[0]` kommt in `app/ui/` nicht mehr vor,
      außer im Einstellungsdialog, der aus der Tabelle die Auswahl baut. Der
      Docstring von `LengthSpin` nennt das alte Muster, um zu erklären, warum es
      weg ist — eine Textsuche fände genau die Erklärung.
- [x] **Ein Befund weiß jetzt, zu welchem Körper er gehört.**
      `ingest.not_watertight` trug keine `object_id`, und deshalb griff seine
      Handlung über `_object_of` auf die *Auswahl* zurück — eine Vermutung, die
      bei einer 3MF-Baugruppe falsch ist. Der Loader kann sie nicht mitgeben:
      Er arbeitet auf einem Netz, und die Kennungen vergibt der Stapel (§11),
      also kennt auch die `load`-Operation sie noch nicht — ihre Ausgaben tragen
      `id=""`.

      Die **Auswertung** kennt beide Seiten und trägt sie nach, an derselben
      Stelle, an der sie schon die `op_id` nachträgt. Das gilt damit für jeden
      Befund jeder Operation und nicht nur für diesen.

      **Eingetragen wird nur bei genau einer Ausgabe.** Bei mehreren gehört der
      Befund zu einem der Körper, und zu welchem, weiß dort niemand — eine
      Kennung einzusetzen wäre geraten, und die Handlung daran griffe den
      falschen (Regel 21). Ein Befund, der seine Kennung selbst mitbringt,
      behält sie.
- [x] **Die bedingte Wirkung steht jetzt am Parameter** (`ParamSpec.depends_on`).
      `DEPENDENT_FIELDS` ist weg. Die Tabelle hatte mit elf Einträgen die
      Schwelle gerissen, die ihr eigener Kopf nannte — und damit ihre eigene
      Begründung widerlegt: Sie stand in der Oberfläche, „weil sie eine Aussage
      über den *Dialog*" sei. Das war sie nie. Dieselbe Auskunft brauchen vier
      Oberflächen, und genau eine hatte sie.

      Jetzt liest jede das Schema: Der **Dialog** graut das Feld aus und sagt,
      woran es liegt; das **Handbuch** schreibt die Bedingung in die
      Parametertabelle; der **Agent** bekommt sie in der Werkzeugbeschreibung;
      die **Kommandozeile** liest dasselbe `json_schema`.

      **Agent und Mensch bekommen verschiedene Anreden, nicht verschiedene
      Inhalte.** „Gilt bei Art = circular" hilft im Handbuch, denn *Art* steht
      so im Dialog. Der Agent kennt kein *Art* — er setzt `kind`, und ein Satz
      mit einem Namen, den seine Werkzeugbeschreibung nicht führt, wäre eine
      Zuordnung, die er raten müsste. `condition_text(..., keys=True)` macht
      den Unterschied, und die Quelle bleibt eine.

      Der Dialog formuliert weiter eigenständig („Wirkt nur, wenn …"), weil er
      einen Tooltip an einem ausgegrauten Feld schreibt und die Auswahlwerte
      durch `choice_label` schickt. Zwei Formulierungen, eine Quelle — das ist
      kein Drift.

      Nebenbefund, und er bleibt offen: **Die Drift zwischen `documentation()`
      und den eingecheckten Handbuchseiten fängt kein Test.** `test_manual.py`
      prüft die Sprungmarken der Datei, nicht ihren Inhalt gegen den Erzeuger.
      Wer den Erzeuger ändert und `tools/make_manual.py` nicht laufen lässt,
      bekommt keinen roten Lauf — bemerkt habe ich es nur, weil ich es selbst
      war.
- [x] **Der Referenzteil der eingecheckten Seite hält jetzt am Register.**
      `documentation()` zu ändern und `tools/make_manual.py` nicht laufen zu
      lassen blieb unbemerkt: Der Test daneben prüfte die Kapitel — die
      *geschriebenen* Seiten — und die Sprungmarken, nicht den erzeugten Teil.
      In dieser Runde ist es aufgefallen, weil der Ändernde und der Prüfende
      dieselbe Person waren; das ist keine Absicherung, sondern ein Zufall.

      `test_the_website_page_carries_the_generated_reference` liest jetzt jeden
      Operationstitel, jeden Vorbehalt und jede Bedingung aus dem Register und
      sucht sie in der Seite — für Deutsch und Englisch. Gegen das **Register**
      und nicht gegen die ganze Datei: Zeichen für Zeichen zu vergleichen hieße,
      die Seite im Test noch einmal zu erzeugen, und dann prüfte er sich selbst.

      Gesucht wird der Vorbehalt **selbst** und nicht seine fertige Zeile: Im
      Handbuch steht sein Vorwort halbfett, also als `<strong>` und nicht mit
      den Sternchen, die `caveat_line` setzt. Gegengeprobt mit einem geänderten
      `caveat` — der Test wird rot und nennt die Operation.

> **Drei der vier offenen Punkte liegen in Dateien, die am 20.08. eine
> parallele Sitzung in Arbeit hatte** (`surfaces.py` für den caveat,
> `panels.py` für den Befund und für einen Teil der Anzeigeeinheit).
> Gleichzeitig dort zu schreiben hieße, sich gegenseitig zu überbügeln — das
> ist der Grund, warum sie offen stehen und nicht behoben sind, und nicht ihr
> Umfang. Zweimal hat dieses Repository das schon anders gelernt („Zwei
> Sitzungen, dieselbe Woche, dieselben Dateien"; „Zwei Sitzungen, ein Index").

### Nachtrag: die Abbildung zeigte drei Wege (20.08.2026)

Beim Neuerzeugen des Handbuchs für den Punkt darüber fiel ein Fund heraus, der
mit den Bedienverträgen nichts zu tun hat und alles mit demselben Muster:
`ways.svg` zeigte **drei** Wege, in allen sechs Sprachen.

- [x] **Der vierte Weg fehlte im Bild, seit es ihn gibt.** Der Eintrag zu Weg 4
      (19.08.) nennt die Ursache selbst: „die gezeichnete Abbildung im Handbuch
      zeigte drei Zeilen, während der Text daneben vier beschrieb; ihre Höhe
      folgt jetzt der Zahl der Zeilen". Der **Code** wurde damals repariert. Die
      **eingecheckte Datei** nicht — sie entsteht in `tools/make_manual.py`, und
      der lief nie. Sechs Sprachen, zweimal je Sprache (hell und dunkel):
      `viewBox="0 0 620 260"` gegen die 318, die vier Zeilen brauchen.

      Gefangen hätte es kein Test. Der eine prüft die Kapitelüberschriften der
      Seite, der zweite ihre Sprungmarken, der dritte — seit heute — ihren
      Referenztext. Ein Bild sagt keiner von ihnen etwas.

      `test_the_drawn_figures_are_the_ones_the_code_draws` vergleicht jetzt jede
      **gezeichnete** Abbildung Zeichen für Zeichen mit dem, was
      `figures.svg()` heute zeichnet — dreizehn Abbildungen, hell und dunkel,
      sechs Sprachen. Das geht, weil `core.drawing` ohne Qt arbeitet und damit
      dieselbe Datei liefert. Gerendertes und Bildschirmfotos bleiben außen vor:
      Sie hängen an VTK, an Schriften und am Bildschirm, und die zu vergleichen
      hieße die Maschine prüfen und nicht die Anwendung.

      Zwei Fallen steckten im Test selbst. Ohne `figures.forget()` kommt sechsmal
      die deutsche Version zurück — die Abbildungen werden gemerkt, und der
      Erzeuger leert den Vorrat bei jedem Sprachwechsel. Und die Zeilenenden
      bleiben außen vor: `write_text` setzt unter Windows CRLF und unter Linux
      LF, was keine Aussage über das Bild ist.

- [x] **Die Bildschirmfotos des Handbuchs sind neu aufgenommen und nicht
      eingecheckt.** Derselbe Lauf hat sie erneuert — sechs je Sprache, unter
      anderem mit dem neuen Vorbehalts-Label im Operationsdialog. Sie liegen
      ungesichert im Baum, weil am 20.08. eine parallele Sitzung an der
      Oberfläche arbeitete (Objektbaum, Palette, Druckdialog): Ein
      Bildschirmfoto von einer Baustelle zeigt die Baustelle.

      Erledigt am 20.08. mit dem Auftrag „alle Bilder neu aufnehmen" — und zwar
      gründlicher als hier gedacht: Aufgenommen wird seither bildschirmfüllend,
      und die drei Layoutfehler, die dabei ans Licht kamen, stehen unter
      „Alle Bilder neu aufgenommen".

## Die eigene Arbeit im Review (20.08.2026)

Durchgesehen wurden die vierzehn Commits dieser Sitzung, nicht der Arbeitsbaum:
dort lagen fremde Änderungen einer parallel laufenden Sitzung und die neu
aufgenommenen Handbuchbilder. Vier Funde, alle vier gegen einen Lauf
reproduziert, alle vier behoben. Und sieben neue Tests, die gegen den Stand von
vorher fallen — nachgewiesen in einem `git worktree` auf HEAD, nicht behauptet.

**Drei der vier sind derselbe Fehler, und er ist meiner.** Beim Umbau auf die
prozessweite Anzeigeeinheit (§19.3) habe ich `set_value`, `value()` und die
Grenzen umgestellt und die Stellen übersehen, an denen jemand *an* der
Umrechnung vorbeigreift. Was sie verband, ist ein fehlender Test: **keiner fuhr
eine Leiste oder einen Umschalter je in Zoll.** Geprüft war die Umschaltung an
ihren Anzeigen und an keiner Handlung — und genau dort, wo aus einer Anzeige ein
Dokumentwert wird, saßen alle drei.

### Behoben

- [x] **Sechs Stellen lasen die Bildhauerleiste in Anzeigewerten**
      (`0492b43`). `sculpt_bar.radius`/`.strength` mit `.value()` statt
      `.value_mm()`: In Zoll lief ein Pinsel von 0,2 mm, wo 5 mm eingestellt
      waren. Zwei der sechs gaben das an `stroke_at` — **Geometrie ins
      Dokument**. Eine verglich gegen `median_edge` in Millimetern, worauf die
      Warnung „Netz zu grob" grundlos erschien; eine rechnete daraus die
      Kantenlänge fürs Vernetzen; und eine gab den Wert als Pinselring in die
      Szene, wo er ein Fünfundzwanzigstel des Pinsels groß war.

      **Die Ursache lag tiefer als die sechs Zeilen.** `SculptBar.values()`
      beantwortete genau diese Frage, mit den richtigen Einheiten — und hatte
      **keinen Aufrufer**. Das Fenster baute dasselbe Wörterbuch daneben neu.
      Zwei Wege zu derselben Auskunft sind einer zu viel, und welcher benutzt
      wird, entscheidet nicht der Vorsatz. Jetzt gibt es einen; sein
      Rückgabetyp heißt `StrokeValues` und nicht `dict[str, object]`, denn mit
      Namen im Typ prüft mypy das Auspacken, und ohne sie nimmt es jede
      Verwechslung hin.

      Der Pinselring hing an `valueChanged` — Qts Signal, das die Zahl aus dem
      Feld trägt. Das war die Lesestelle, von der der Docstring von
      `LengthSpin` behauptete, es gebe sie nicht: Man überspringt die
      Umrechnung, ohne `value()` zu schreiben. `valueChangedMm` ist dieselbe
      Nachricht in der Einheit des Kerns.

- [x] **Ein Einheitenwechsel meldete einen geklemmten Zwischenwert**
      (`0492b43`). `refresh_unit` legte die neue Spanne, während noch der
      Wert der alten stand. Ein Feld auf 10 mm gab seinem Empfänger erst
      99,9998 und dann 10,0 — gemessen, nicht geschlossen. Getroffen hat es
      auch die Schnittleiste, deren `_typed` den Schieber nachzieht: Die
      Schnittebene wäre beim Umschalten der Einheit gesprungen. In Millimetern
      ändert sich beim Wechsel nichts, also gibt es nichts zu melden — der
      Tausch läuft unter `blockSignals`.

- [x] **Der Ausdrucksmodus übernahm den Anzeigewert** (`56c4ed0`). Ein Klick
      auf den Umschalter belegte das Ausdrucksfeld aus dem Drehfeld vor: In
      Zoll stand „=1.5748" dort, wo 40 mm gemeint waren, und weil ein
      Parameterausdruck nach §13 in Millimetern rechnet, war das ein
      Datenfehler und kein Anzeigefehler — der Ausdruck landet im Dokument.

      Der Hinweis darunter beschriftet mit `entry.unit` und las „= 1.5748 mm".
      Eine Anzeige, die ihren eigenen Fehler bezeugt, und niemand hatte
      hingesehen — dieselbe Sorte Fund wie beim Schattenwurf, wo der Kommentar
      beschrieb, wohin der Schatten fallen sollte, und keiner nachsah, wohin er
      fiel. `_number()` ist jetzt die eine Quelle für `value()` und das
      Umschalten.

- [x] **Die Flatpak-Quelle war der Ordner, in den der Bau selbst schreibt**
      (`ba8f101`). `path: ../dist` nahm alles unter `dist` mit, und dorthin
      schreiben `build_flatpak` (`flatpak-repo`, `flatpak-build`) und
      `build_appimage` (`Solidon3D.AppDir`) ihre Ergebnisse: Der zweite Lauf
      hätte die Zwischenausgabe des ersten eingepackt, nach einem
      AppImage-Bau eine vollständige zweite Kopie der Anwendung dazu. Verengt
      auf `../dist/Solidon3D`, `dest` hält das Unterverzeichnis, das die
      Baubefehle nennen.

      Aufgefallen wäre es nie: Der Bau braucht Linux und zwei externe
      Programme, und gelaufen ist er noch nie (Veröffentlichungskonzept §2 F).
      Ein Rezept, das niemand ausführt, prüft nur ein Test — der Drift-Test
      vom 20.08. hat beim Nachziehen prompt zugeschlagen und das eingecheckte
      Manifest als älter als seinen Erzeuger gemeldet.

### Was der Review entlastet hat

Geprüft und nicht beanstandet: alle elf `depends_on`-Deklarationen gegen den
Code, den sie beschreiben; die fünf `LengthSpin`-Verwender (`paint_bar`,
`sculpt_bar`, `section_bar`, `transform_bar`, `sketch_editor`), die alle
`value_mm()` nach außen geben; die achtzehn `valueChanged`-Anschlüsse, von denen
genau einer den rohen Wert weitergab; `caveat_line` über alle vier Oberflächen;
und die drei Rundungspfade, die 40 mm über beide Richtungen bei 40 mm halten.

`section_bar.position` sah nach einem sechsten Fund aus (`value()`, geteilt
durch `STEPS_PER_MM`) und ist keiner: ein `QSlider`, dessen `value()` Schritte
zählt und keine Millimeter. Der Unterschied zwischen einem Fund und einem
Verdacht ist eine Zeile nachsehen.
## Die Slicer-Übergabe gegen die echten Slicer geprüft (20.08.2026)

Alle drei Familien gegen die installierten Programme durchgemessen, nicht
gegen die Erinnerung: PrusaSlicer 2.9.6, ElegooSlicer 1.5.3.4, CuraEngine
5.13.0. Jede Behauptung unten hat einen Lauf hinter sich oder eine Zeile aus
`fdmprinter.def.json` beziehungsweise der ausgeschriebenen Prusa-Vorgabe
(`prusa-slicer-console --save`).

Das Ergebnis fällt scharf auseinander. **PrusaSlicer nimmt 53 von 53
geschriebenen Schlüsseln an, ElegooSlicer 56 von 56** — die Gegenprobe meldet
bei beiden nichts, und das stimmt auch. **CuraEngine ist ein anderer Fall**,
und der Grund steht am Ende dieses Abschnitts.

### Der Stützwinkel misst in zwei Richtungen — und Solidon schreibt eine Zahl

`SupportSettings.threshold_angle` ist dokumentiert als „Grad gegen die
Senkrechte, ab dem gestützt wird". Das ist Curas Konvention. PrusaSlicer und
die Orca-Familie messen **gegen die Horizontale**, und beide Tooltips sagen es
wörtlich: „slope angle (90° = vertical) is above the given threshold" bei
Prusa, „overhangs whose slope angle is below the threshold" bei Orca.

Gemessen an einem eigens gebauten Keil, dessen Überhangfläche 30° zur
Horizontalen steht — also 60° zur Senkrechten:

| geschriebener Wert | PrusaSlicer | ElegooSlicer | CuraEngine |
|---|---|---|---|
| 20 | keine Stütze | 68 Abschnitte | 136 Abschnitte |
| 40 | 260 Abschnitte | 236 Abschnitte | 136 Abschnitte |
| 50 | 260 Abschnitte | 236 Abschnitte | 136 Abschnitte |
| 70 | 260 Abschnitte | 236 Abschnitte | keine Stütze |

Der Kipppunkt liegt bei Prusa und Orca zwischen 20 und 40 — dort, wo der
Überhang 30 misst. Bei Cura zwischen 50 und 70 — dort, wo er 60 misst. Beide
haben recht, sie messen nur verschieden. Solidon schickt allen dreien
dieselbe Zahl. Für Prusa und Orca müsste sie `90 − Wert` lauten.

Bei der Vorgabe 50 gegen 40 ist der Unterschied noch verzeihlich. An den
Rändern kehrt er sich um: Wer 20 einstellt, meint „stütze fast alles" und
bekommt von PrusaSlicer „stütze fast nichts".

### CuraEngine löst keine Vererbung auf — und das kostet ein Drittel

`_machine_keys` sagt es bereits: „Sie löst keine Vererbung auf — was das
Fenster sonst aus Definition, Qualität, Material und Variante zusammenrechnet,
muss ihr einzeln mitgegeben werden." Der Satz stimmt, aber die Folgerung wurde
nur für drei Schlüssel gezogen (`roofing_layer_count`, `flooring_layer_count`,
`acceleration_enabled`) und für einen vierten in `_cura_dependants`
(`initial_layer_line_width_factor`). Sie gilt für zwölf weitere.

In `fdmprinter.def.json` trägt jede abgeleitete Einstellung einen
`value`-Ausdruck **und** einen `default_value`. Das Fenster wertet den
Ausdruck aus, `CuraEngine` nimmt den Vorgabewert. Was Solidon schreibt, bleibt
damit an seinem Schlüssel stehen und erreicht die Schlüssel nicht, aus denen
gerechnet wird:

| Solidon schreibt | erreicht **nicht** | die bleiben bei |
|---|---|---|
| `line_width=0.42` | `wall_line_width_0/x`, `skin_line_width`, `infill_line_width`, `skirt_brim_line_width`, `support_line_width`, `support_interface_line_width` | 0.4 |
| `infill_sparse_density=15` | `infill_line_distance` | **2 mm** statt 5,6 |
| `acceleration_print=8000` | 22 Feature-Beschleunigungen | 3000 |
| `cool_fan_speed=60` | `cool_fan_speed_min/max` | 100 |
| `material_flow=98` | sieben `*_material_flow` | 100 |
| `retraction_speed=35` | `retraction_retract_speed`, `retraction_prime_speed` | 25 |
| `speed_layer_0=20` | `speed_print_layer_0`, `skirt_brim_speed` | 30 |
| `speed_topbottom=40` | `speed_roofing`, `speed_flooring`, `speed_ironing` | 25 |
| `bottom_layers=4` | `initial_bottom_layers` | 6 |
| `support_infill_rate=15` | `support_line_distance` | 2.66 |
| `support_interface_height` | `support_roof_height`, `support_bottom_height` | 1 |

Gemessen an einem 20-mm-Würfel, zweimal derselbe Lauf, einmal wie Solidon
heute übergibt und einmal mit aufgelösten Werten:

```
                          Solidon heute    aufgeloest
Filament                     1100,4 mm      817,6 mm     +34,6 %
Druckzeit                       753 s         660 s      +14,1 %
Luefter (M106)                    255      153 / 255
Beschleunigung (M204)   3000/4000/5000   4000/5000/8000
```

Ein Drittel Material zu viel, und die Füllung ist der Hauptgrund: 2 mm
Linienabstand statt 5,6 sind nicht 15 Prozent, sondern gut vierzig.

### Drei Cura-Schlüssel treffen nichts

**`outer_inset_first` gibt es in Cura 5.13 nicht.** Der Schalter heißt
`inset_direction` mit `inside_out`/`outside_in`; der alte Name steht in keiner
der 753 Einstellungen der Definition. Ein unbekannter `-s`-Wert wird
stillschweigend verworfen. Gemessen: mit Solidons Übergabe beginnen **0 von 50
Lagen** außen, mit `inset_direction=outside_in` **49 von 50**. „Außenwand
zuerst" ist bei Cura folgenlos — und das ist die Einstellung, die `advise` bei
Passungen setzt.

**`retraction_hop` wirkt nicht ohne `retraction_hop_enabled`**, und dessen
Vorgabe ist `false`. Gemessen: 0 Z-Sprünge gegen 5, sonst gleicher Lauf.

**`support_interface_height` ist eine Höhe in Millimetern**, nicht eine
Schichtzahl. Solidons `interface_layers=2` wird zu 2 mm — bei 0,2er Schichten
das Zehnfache des Gemeinten. Orca (`support_interface_top_layers`) zählt
Schichten, Cura misst.

### Mit Stützen liefert CuraEngine gar nichts

Zwei Einstellungen fehlen dem Extruder-Zug, und der Lauf endet, bevor eine
Bahn entsteht:

```
style=grid   Rückgabewert 3221225477 (Access Violation), 444 Bytes ohne Bahn
             [error] Trying to retrieve setting with no value given: support_z_seam_away_from_model
style=tree   Rückgabewert 2, keine Datei
             [error] ... : min_wall_line_width
```

Mit `support_z_seam_away_from_model=false` läuft `grid` durch (136
Stützabschnitte), mit zusätzlich `min_wall_line_width` auch `tree`. Es ist
derselbe Fall wie `roofing_layer_count` — nur trifft er jeden Druck mit
Stützen, und Solidon fängt ihn nur als „Der Slicer hat das Modell nicht
verarbeitet" ab.

### Was Cura kennt und Solidon nicht schreibt

`shell.seam_position` → `z_seam_type`, `temperature.chamber` →
`build_volume_temperature`, `cooling.bridge_fan_speed` → `bridge_fan_speed`,
`filament.max_flow` → `material_max_flowrate`. Die beiden Brückenwerte
brauchen zusätzlich `bridge_settings_enabled=true` — ohne den gilt auch
`speed.bridge` nicht, das Solidon bereits schreibt.

Ohne Entsprechung und damit zu Recht ohne Eintrag: `wall_generator`,
`precise_outer_wall`, `retraction.wipe`, `filament.density`, `filament.colour`,
`filament.cost_per_kg`.

### PrusaSlicer: zwei Lücken

**`support.placement` erreicht PrusaSlicer nicht**, obwohl
`support_material_buildplate_only` in seiner Vorgabedatei steht. Gemessen an
demselben Keil: 260 Stützabschnitte wie Solidon übergibt, 234 mit dem Schalter.
Wer „nur auf der Platte" einstellt, bekommt Stützen auf dem Modell.

**`support.density` hat in keiner der beiden älteren Familien eine
Entsprechung in Prozent.** PrusaSlicer führt `support_material_spacing`, Orca
`support_base_pattern_spacing` — beides Abstände in Millimetern. Nur Cura
kennt `support_infill_rate`. Der Wert ist damit für zwei von drei Slicern
folgenlos, und der Dialog bietet ihn trotzdem an.

### Warum das keiner gemerkt hat

Die Gegenprobe in `verify()` liest die Konfiguration, die der Slicer als
Kommentar in die Druckdatei schreibt. Das ist die richtige Idee, und sie trägt
weit — aber nicht überall gleich weit:

```
Cura :  0 von 47 geschriebenen Schluesseln stehen im G-Code
Prusa: 53 von 53
Orca : 56 von 56
```

`CuraEngine` schreibt seine Einstellungen nicht in die Datei; das tut nur das
Fenster. Der Mechanismus, der die Zuordnung selbst prüft, ist genau dort
blind, wo die meisten Fehler sitzen. Was bei Cura hilft, ist kein
Konfigurationskommentar, sondern die Definition daneben: `fdmprinter.def.json`
liegt bei jeder Installation, nennt jeden gültigen Schlüssel, seine Einheit
und seinen Vorgabewert — und hätte `outer_inset_first` beim ersten Lauf
auffallen lassen.

Auf der Testseite fehlt dieselbe Frage.
`test_every_setting_in_a_table_actually_exists` prüft den Solidon-Pfad, nicht
den Namen beim Slicer; `test_the_core_settings_reach_every_slicer` prüft neun
von sechsundfünfzig Einstellungen, und keine der oben gefundenen ist unter den
neun.

### Nebenbei

Der Rückweg misst je Slicer verschieden vollständig: bei Cura bleibt
`filament_grams` leer, bei PrusaSlicer `layer_count`. Und eine exportierte 3MF
trägt ihre Einstellungen nur für die Orca-Familie — für PrusaSlicer enthält
sie `Metadata/model_settings.config` und sonst nichts, obwohl PrusaSlicer eine
eigene Konfigurationsdatei in der 3MF läse.

Der 3MF-Weg zu ElegooSlicer wurde mitgeprüft und ist in Ordnung: geschrieben,
geöffnet, gerechnet, und die Gegenprobe meldet keine Abweichung.

### Behoben (20.08.2026)

Alles aus der Durchsicht darüber, gemessen gegen dieselben drei Programme.

**Der Stützwinkel wird umgerechnet.** `_angle_from_horizontal` schreibt
PrusaSlicer und der Orca-Familie `90 − Wert`; Cura bekommt die Zahl wie sie
ist. Derselbe Keil, alle drei nachgemessen: der Kipppunkt liegt jetzt bei
allen zwischen 50 und 70, dort wo der Überhang steht.

**Die Cura-Ableitungen sind vollständig.** Reine Kopien in `CURA_MIRRORED`,
Faktoren in `CURA_SCALED`, Gerechnetes in `_cura_rated` — jede Zeile die
Formel aus `fdmprinter.def.json`, nicht eine Meinung darüber. Aus 47
geschriebenen Schlüsseln sind 224 geworden, und der 20-mm-Würfel braucht
**809,8 mm Filament statt 1100,4** und 647 Sekunden statt 753. Der Lüfter
fährt 60 Prozent, die Beschleunigung 8000, und die Außenwand kommt in
neunundvierzig von fünfzig Lagen zuerst.

Damit die Reihenfolge stimmt, kommen die drei Stufen jetzt an **einer** Stelle
zusammen: `values_for` legt Zuordnung, Maschine und Ableitung übereinander.
Vorher hätte die Ableitung auf einen Düsendurchmesser gerechnet, den sie noch
nicht kannte.

**Drei Cura-Schlüssel treffen jetzt.** `inset_direction` statt
`outer_inset_first`, `retraction_hop_enabled` neben dem Sprung,
`support_interface_height` als Millimeter aus Schichtzahl mal Schichthöhe —
samt der Schalter, ohne die Cura gar keine Schnittstelle baut.

**Mit Stützen läuft Cura wieder.** `support_z_seam_away_from_model` und
`min_wall_line_width` stehen bei `roofing_layer_count`, wo diese Sorte
hingehört. Beide Stützarten kommen durch: Gitter 220 Abschnitte, Baum 217.

**Vier neue Zuordnungen**, alle in der Definition nachgeschlagen:
`z_seam_type`, `build_volume_temperature`, `bridge_fan_speed` und
`material_max_flowrate` — dazu `bridge_settings_enabled`, ohne den weder die
Brückengeschwindigkeit noch der Brückenlüfter gelten, und `speed_print`, aus
dem Cura alles ableitet, was Solidon nicht einzeln setzt.

**PrusaSlicer bekommt die Stützplatzierung** (`support_material_buildplate_only`),
und beide älteren Familien die **Stützdichte** als Linienabstand, den sie
statt eines Anteils führen.

**Die exportierte 3MF trägt ihre Einstellungen auch für PrusaSlicer.** Er
schreibt `Metadata/Slic3r_PE.config` beim Konsolenexport selbst nicht mit,
liest sie aber: ohne `--load` geslict kamen sieben Wände und 33 Prozent
Füllung an. Eine Falle steckte darin — er **überspringt die erste Zeile**, und
ohne Kopfzeile fiel `avoid_crossing_perimeters` lautlos heraus. Gefunden, weil
die Gegenprobe danach genau diesen einen Wert meldete.

**Die Lücke in der Gegenprobe ist zu.** Für Cura gibt es keine Konfiguration
im G-Code, aber eine Definition neben dem Programm: `unknown_keys()` liest
`fdmprinter.def.json` der **installierten** Version und meldet, was sie nicht
kennt. Dieselbe Absicht wie `verify()`, aus der einzigen Quelle, die dieser
Slicer hergibt.

**Und die Tests, die das halten.** `test_every_setting_reaches_every_slicer`
prüft alle sechsundfünfzig Einstellungen gegen alle drei Familien statt neun
handverlesener; wo eine nicht ankommen kann, steht der Grund in `UNREACHABLE`.
`test_every_cura_key_exists_in_the_definition` und
`test_nothing_cura_derives_is_left_to_its_default` prüfen gegen eine echte
Cura-Installation und überspringen, wo keine liegt. Beide wurden gegen die
alten Fehler gehalten: sie schlagen an.

Nebenbei: **die Schichtzahl fehlte bei PrusaSlicer**, weil er sie im Kopf
nicht nennt — gezählt sind seine Wechselmarken dieselbe Auskunft. Das Gewicht
bei Cura rechnete `grams()` schon immer aus dem Volumen, wenn der Kopf
schweigt.

Offen bleibt einer: **die 3MF für Cura gibt es weiterhin nicht** — sie liest
nur sein Fenster, nicht die Rechenmaschine. Cura bekommt ein STL und seine
Einstellungen über die Kommandozeile, und das bleibt so.

**Ein bestehendes Projekt slict jetzt anders**, und das ist kein Versehen:
Die Druckeinstellungen reisen in der Projektdatei mit (`print_settings` in
`serialise.py`), und ein gespeicherter Stützwinkel kommt bei PrusaSlicer und
der Orca-Familie ab jetzt als `90 − Wert` an statt als Wert. Das Format ändert
sich nicht — die gespeicherte Zahl war immer gegen die Senkrechte gemeint, nur
die Übersetzung war falsch. Wer seinen Wert am alten Verhalten ausgerichtet
hat, richtet ihn einmal neu aus; wer ihn nach der Beschreibung eingestellt
hat, bekommt endlich das, was dort steht.

## Die Werkzeugleiste zeigt nur noch Zeichen (20.08.2026)

Auf Wunsch: die Leiste über dem Fenster trägt keine Beschriftungen mehr. Sieben
beschriftete Knöpfe brauchten 703 Pixel und drängten die Kopfzeile mit Projekt,
Maßen, Drucker und Material an den rechten Rand; ohne Text sind es 310.

Die Werkzeugzeile **unter** dem Viewport bleibt beschriftet. Der Unterschied
steht jetzt in `.claude/rules/oberflaeche.md`: Ein Zeichen darf allein stehen,
wenn es entweder ein geeinigtes Bild ist (Linie, Kreis, Diskette) oder die Zahl
klein und die Stelle fest bleibt. Acht Umschalter, die mit dem Zustand
wechseln, sind weder das eine noch das andere.

Drei Dinge, die daran hingen und beim Nachlesen aufgefallen sind:

- **Der Hinweis am Knopf war die stille Voraussetzung.** `_lock_hint` stellt
  den eigenen Hinweis aus dem `statusTip` wieder her — *Modell einfügen* und
  *Zeichnen* hatten gar keinen, und nach dem Freischalten wäre der Knopf ohne
  jede Auskunft dagestanden. Zwei Tests halten das jetzt fest.
- **Der Grund verdrängte den Namen.** `_lock_hint` und `_pick_hint` ersetzen
  den Hinweis vollständig; am beschrifteten Knopf war das folgenlos, am
  unbeschrifteten blieben ein Bild und ein zusammenhangloser Satz. `_with_name`
  stellt den Namen voran, getrennt mit Doppelpunkt — der Sperrgrund führt
  selbst einen Gedankenstrich.
- **Der Tooltip war ärmer als das Menü.** Er trug nur das Wort, während der
  Menüeintrag derselben Handlung längst „Ein gespeichertes Projekt öffnen
  (.p3d)." und sein Kürzel führt. `_button_tip` holt beides von dort, statt
  einen zweiten Satz danebenzustellen, der wegdriftet.

Nachgezogen: Handbuch (Kapitel *Das Fenster*, *Zeichnen* und *Die vier Wege*),
Tour Weg 4 — sie schickte den Anfänger „auf Formen" und hat `done=`-Bedingungen,
hängt also, wenn er das Wort sucht —, die fünf Sprachkataloge und die
Bildschirmfotos aller sechs Sprachen samt Handbuchseiten und Website.

Offen: Ob die Leiste auf Dauer bei sieben Knöpfen bleibt. Der zweite Grund
(„wenige, feste Stelle") trägt nicht beliebig weit; ein achter oder neunter
Knopf nimmt ihn weg, und dann ist die Beschriftung wieder fällig.

## Die Rückmeldung geht jetzt raus (20.08.2026)

Auf Wunsch: Was der Nutzer meldet — Vorschlag, Fehler, Frage oder Absturz —
geht aus dem Programm heraus an `support@solidon3d.de`, mit Bildschirmfoto,
Protokoll und auf Wunsch der laufenden Sitzung. Vorher war der Weg ein Ordner
im Nutzerverzeichnis und ein `mailto:` ohne Anhänge: drei Schritte, von denen
jeder einzelne der letzte sein kann, und der dritte hieß „Projektdatei suchen".

**Die Grenze zur verbotenen Telemetrie liegt beim Auslöser, nicht beim
Versand.** Es geht nichts von allein, nichts ungesehen und nichts ohne Inhalt —
ein geschriebener Satz, oder nach einem Absturz der Stapelabzug, der sich
selbst trägt. `support.send()` hat genau einen Aufrufer,
und der hängt an einem Knopf — `test_nothing_leaves_without_being_sent` liest
die Quelle und zählt ihn. Bauplan §37.2 und §33.2 sind entsprechend
nachgezogen, ebenso die Datenschutzerklärung: Was übertragen wird, steht dort
Feld für Feld, samt Zweck, Rechtsgrundlage und Aufbewahrungsdauer.

Was dabei zusammengelegt wurde: `ErrorReportDialog` und der Rückmeldungs-
`mailto` sind ein Dialog geworden (`app/ui/support_dialog.py`). Zwei Fenster,
die zu 80 % dasselbe taten, standen als zwei Einträge im Hilfe-Menü; jetzt ist
es einer. Der abgelegte Ordner ist dabei kein Notausgang, sondern ein Knopf
neben *Senden* — wer ohne Netz sitzt oder nichts aus der Hand geben will,
nimmt ihn, und §37.2 bleibt vollständig eingelöst.

Drei Dinge, die daran hingen:

- **Ein Programmfehler darf nicht wie ein Bedienfehler aussehen** (§33.1). Der
  zusammengelegte Dialog hätte den Satz „Das war ein Programmfehler, nicht Ihre
  Schuld" mit dem alten Modul verloren; er steht jetzt als eigene Ansage über
  `kind=crash`, samt eigenem Fenstertitel.
- **Der Kern formatiert keine Platzhalter.** Der Grund eines gescheiterten
  Versands steht in `values["reason"]`, nicht als `{reason}` im Satz — ein
  Kernfehlertext wird nicht formatiert, sondern angezeigt.
- **Der Trenner der Sendung wird nicht gewürfelt**, sondern aus ihrem Inhalt
  gebildet (sha256) und gegen Kollision geprüft. Ein Zufallstrenner müsste
  einen Startwert führen (Regel 9); die Frage stellt sich so gar nicht.

Der Gegenpart liegt im Repository: `website/api/support.php` nimmt die Sendung
an und reicht sie als Mail weiter. Er muss nach `httpdocs/api/` hochgeladen
werden — bis dahin scheitert *Senden* und bietet die beiden Wege an, die ohne
ihn gehen. Ein SMTP-Zugang im ausgelieferten Programm war die Alternative und
wäre ein Postfachpasswort in einer .exe gewesen.

Offen: Der Absender `noreply@solidon3d.de` muss auf dem Server existieren oder
SPF-seitig zugelassen sein, sonst wirft der eigene Mailserver die Nachricht weg.

## Der Erzeuger steht jetzt auf einer Lizenz, die hier gilt (20.08.2026)

Die mitgelieferten ComfyUI-Abläufe liefen gegen Hunyuan3D 2.1. Dessen Formen
waren gut, aber die Tencent Community License nimmt die Europäische Union
ausdrücklich aus — für eine Anwendung, die hier verkauft wird, ist das kein
Kleingedrucktes, sondern ein Ausschluss.

- [x] **TripoSG statt Hunyuan3D**, MIT für Quelltext *und* Gewichte. Vier
      Testkörper vom Drehkörper bis zur Figur mit dünnen Fortsätzen kamen
      geschlossen und aus einem Stück heraus, in rund dreizehn Sekunden auf
      einer RTX 4080.
- [x] **Die Knoten liegen im Repository** (`tools/comfyui/`), weil die
      vorhandenen seit über einem Jahr unangetastet sind.
      `python tools/setup_comfyui.py` richtet sie ein: kopieren, TripoSG
      klonen, zwei Stellen richten, drei Pakete nachziehen, 7,5 GB Gewichte
      holen. Erkannt wird am Ergebnis, ob das schon geschehen ist — nicht am
      eigenen Kommentar, sonst patcht der zweite Lauf eine von Hand geänderte
      Datei zu Bruch.
- [x] **Zwei Stellen im fremden Quelltext** mussten gerichtet werden: `diso`
      ist eine CUDA-Erweiterung ohne Windows-Wheel und wird nur im
      Flash-Decoder-Pfad gebraucht; der Fourier-Embedder gibt float32 zurück,
      woran die nächste Linearschicht mit halben Gewichten abbrach.
- [x] **`requirements.txt` von TripoSG darf nie ungefiltert laufen.** Sie
      nagelt `numpy==1.22.3` fest und zieht `pymeshlab` (GPL, Regel 15). Das
      Werkzeug installiert drei Pakete mit `--no-deps`.
- [x] **Die Zahlen im Graphen sind gemessen, nicht geraten.** `octree_depth`
      steht auf 8, weil 9 bei vierfacher Dreieckszahl keinen sichtbaren
      Unterschied brachte; `steps` auf 50, weil bei 25 dünne Flächen ausfransen.
- [x] **Fehlt die Knotensammlung, sagt Solidon das jetzt.** ComfyUI antwortet
      auf einen unbekannten Knoten mit einem leeren Objekt statt mit einem
      Fehler; die Meldung lautete darauf „es fehlt die Modelldatei" und schickte
      Leute 7,5 GB suchen, denen die Knoten fehlten.
- [x] **Zwei Dreiecke schlugen einen Körper von 1,57.** Beim Aufräumen wählte
      `abs(part.volume) or len(part.faces)` die größte Komponente — und ein
      offenes Fragment hat das Volumen 0,0, was für Python falsch ist. Der
      Ausdruck fiel auf die Dreieckszahl zurück und verglich sie mit dem
      *Volumen* der anderen. Das sah aus wie ein sporadischer Ausfall des
      Generators und führte auf eine falsche Spur zur halben Rechengenauigkeit;
      aufgeklärt hat es ein Lauf ohne den Aufräum-Knoten.

### Was dabei aufgefallen ist und offen bleibt

- [x] **`decimate` zerlegte keine glatten Körper — sondern unverschweißte.**
      Die Glätte war nie das Kennzeichen: Eine saubere Kugel dezimiert bis auf
      2 000 Dreiecke hinunter wasserdicht und einteilig. Was zerreißt, ist ein
      Netz ohne geteilte Kanten, und Quadrik-Dezimierung zieht genau Kanten
      zusammen. Nachgebaut mit einer Dreieckssuppe aus 81 920 einzelnen
      Dreiecken: **12 450 Teile, nicht wasserdicht.** Verschweißt kam dieselbe
      Kugel auf jedes Ziel als ein geschlossenes Stück durch. Dass „das kantige
      Gehäuse dieselbe Stufe unversehrt überstand", passt dazu — es war
      verschweißt, die Vase aus dem Erzeuger nicht.

      Über den ganzen Korpus gemessen ist das Verhältnis Punkt zu Dreieck der
      Verräter: **jedes** frisch gelesene STL steht auf genau 3,00, ein
      verschweißter Körper auf 0,50, und dazwischen liegt nichts. `decimate`
      verschweißt deshalb, wenn es das sieht, und sonst nicht: Auf einem
      sauberen Netz kostet `merge_vertices` 37 bis 43 Prozent der Vereinfachung
      obendrauf und bewegt null Punkte (103 ms zu 281 bei 328 k, 408 zu 951 bei
      1,3 Mio.) — und `decimate` läuft auch für die Anzeige im Viewport. Zwei
      Längen zu vergleichen kostet nichts.
- [x] **Die zwei Grenzen widersprechen sich nicht mehr**, und das ging erst
      nach dem Punkt darüber. Die Merkmalserkennung steigt bei 200 000 aus
      (`FEATURE_LIMIT_TRIANGLES`), die Automatik dezimierte erst ab 500 000 —
      begründet mit `agent.analysis.TRIANGLE_LIMIT`, und das ist die Grenze des
      *Steckbriefs*, nicht die der *Erkennung*. Was dazwischen lag, behielt
      seine Auflösung und verlor die Merkmale; bei TripoSG war das der
      Normalfall.

      `GENERATED_TRIANGLE_LIMIT` **ist** jetzt `FEATURE_LIMIT_TRIANGLES` —
      dieselbe Zahl und keine zweite daneben. Das Ziel steht auf drei Vierteln
      davon, als Anteil und nicht als eigene Zahl, damit eine spätere Boolesche
      Operation nicht sofort wieder darüber landet. Solange `decimate` riss,
      war jede Senkung ein Tausch wasserdicht gegen Merkmale; jetzt gibt es
      nichts zu tauschen, und der Test prüft beides an einem Körper.

      Dabei fiel ein Dritter auf: Der Befund `perceive.too_large` stand danach
      weiter im Bericht. Er stammt vom Laden, als das Netz noch 327 000 Dreiecke
      hatte, und beschrieb einen Zustand, den der dritte Schritt derselben Kette
      längst geändert hatte. Er steht jetzt in `SETTLED_BY` unter
      `mesh.deviation` — gestrichen und nicht herabgestuft, denn es *ist* nicht
      mehr zu fein, und ein Hinweis darauf wäre nicht milder, sondern falsch.
- [x] **Der Erscheinungstermin steht jetzt einmal je Startseite.** Er stand am
      Zähler (`data-countdown`) und an der Umschaltung (`data-release` am
      `<body>`) — zwölf Stellen für einen Zeitpunkt, und ein Test hielt sie
      gleich. Der Zähler liest ihn jetzt vom Körper; seine Markierung bleibt
      ohne Wert, denn sie sagt, *welcher* Absatz zählt, und das ist eine andere
      Auskunft als *wann*. Aus „beide müssen gleich sein" ist
      `test_the_moment_of_release_stands_exactly_once` geworden, und der prüft
      auch, dass niemand dem Zähler wieder einen eigenen Termin gibt —
      Gegenprobe gefahren, einen zurückgeholt, rot.

      Für JavaScript gibt es hier keinen Test, also am geladenen Browser
      gemessen: dieselbe Kette gegen die echte Seite, mit einem Termin in der
      Zukunft, ergibt „Noch 192 Tage, 20 Stunden" — aus `data-release` gelesen.
      Dass der Zähler in der Vorschau beim Laden nicht anspringt, liegt an ihr
      und nicht an der Änderung: `site.js` läuft dort überhaupt nicht, auch die
      unberührte Umschaltung setzte `data-released` nie.

## Die zwei Historien zusammengeführt (20.08.2026)

Achtzig Commits von hier gegen sechsunddreißig von oben, gemeinsame Basis
`b0415d6`, dreiundachtzig Konfliktdateien. Wie sie aufgelöst wurden, steht in
der Commit-Meldung des Merges; hier stehen die drei Tests, die **danach** rot
waren. Zwei davon konnte vorher niemand sehen: Der Test stand auf der einen
Seite, die Datei auf der anderen, und jede Seite war für sich grün.

- [x] **Der Fortschrittsbalken der Rückmeldung hätte seine Zahl in die Füllung
      geschrieben.** `support_dialog.py` kam von oben, die Regel dagegen von
      hier (`e6a506c`): vier Balken in vier Dateien, geprüft an der Quelle.
      Sein Bereich ist `(0, 0)`, Qt zeichnet dort keine Zahl — die Regel gilt
      trotzdem, denn ein Balken, der später doch zählt, hätte sie stillschweigend
      gerissen. `setTextVisible(False)`, ein Zeile, mit Begründung daneben.
- [x] **Der Nachweis der Search Console fiel durch den Sprungtest.**
      `google2f8f028be26a9b5e.html` ist eine Zeile Text unter einem
      `.html`-Namen, weil Google ihn so verlangt: keine Kopfzeile, kein Inhalt,
      nichts zu überspringen. Das Kriterium heißt jetzt „hat eine Kopfzeile" und
      nicht „steht auf einer Ausnahmeliste" — an einer Liste fehlt irgendwann
      eine. Gegenprobe gefahren: nimmt man `funktionen.html` den Sprung, ist der
      Test wieder rot.
- [x] **`tools/make_download.py` trug deutsche Bezeichner** — und das war **kein
      Fund des Merges**, sondern ein roter Lauf, der schon oben stand: Der
      Sprachtest sieht `tools/` seit dem 16.08. (`8a15cbc`), auf beiden Seiten,
      und die Version von `origin/main` bringt neun Treffer. Umbenannt wurde der
      ganze Satz und nicht die neun erkannten Stämme, sonst bliebe eine halb
      übersetzte Datei stehen. Über die **Token** umbenannt, damit Kommentare
      und Meldungen deutsch bleiben; `block` hieß an zwei Stellen zwei Dinge —
      die Funktion, die die Verweise baut, und der Datenblock der Prüfsumme —
      und heißt jetzt `links` und `chunk`.

Was dabei auffiel und liegen bleibt: `Package.size` schreibt
`f"{…:.0f} MB".replace(".", DECIMAL_MARK[…])`. Bei null Dezimalstellen gibt es
nichts zu ersetzen, das Trennzeichen ist damit ohne Wirkung. Entweder eine
Stelle mehr oder die Ersetzung weg — das ist eine Entscheidung über die Anzeige
und gehört dem, der den Kasten gebaut hat.

## Preis, und eine Zahl über die Besucher (20.08.2026)

Zwei Dinge an einem Tag, beide außerhalb des Programms: Der Preis stand zu
niedrig und trug einen Streichpreis, den es nie gegeben hat — und niemand
konnte sagen, ob die Seiten überhaupt gelesen werden.

- [x] **Der Preis steht jetzt bei 69 €, später 99 €.** Vorher waren es 49 €
      „statt 79 €". Zwei Gründe: Die Durchsicht vom 16.08. hatte den Korridor
      auf 69–99 € beziffert („unter 49 € wirkt es wie ein Tool"), und
      Plasticity nimmt für einen reinen B-Rep-Modellierer ohne Druckanalyse,
      ohne Agenten und ohne Bausteinbibliothek 175 USD bei nur zwölf Monaten
      Aktualisierungen. Von 69 € brutto bleiben nach Umsatzsteuer und
      Zahlungsdienst etwa 54 € — bei 49 € waren es 38,60 €, und eine einzige
      Rückfrage zu einer CAD-Anwendung kostet mehr Zeit, als diese Spanne
      hergibt. Geändert in allen sechs Startseiten samt `priceValidUntil` in
      der JSON-LD-Auszeichnung, dazu Pressemitteilung und Anschreiben.
- [x] **Der Streichpreis ist weg, an seiner Stelle steht eine Frist.** „49 €
      statt 79 €" nannte einen früheren Preis, den nie jemand gezahlt hat; das
      ist in Deutschland ein abmahnfähiger Fantasiepreis. Jetzt steht dort
      „69 €, Einführungspreis bis 31.01.2027, danach 99 €" — eine Ankündigung
      des künftigen Preises statt der Behauptung eines vergangenen. Zulässig,
      und mit einem Datum stärker als ohne.
- [x] **Ein eigener Zähler für Aufrufe und Downloads** (`website/api/count.php`,
      Auswertung in `website/api/stats.php`). Die üblichen Antworten heißen
      Google Analytics oder Matomo, und beide widersprechen dem, womit diese
      Website wirbt. Hier: kein Cookie, kein fremder Server, keine
      gespeicherte IP-Adresse. Besucher werden über einen gekürzten Hash aus
      IP, Browserkennung und einem täglich neu gewürfelten Zufallswert
      zusammengefasst, der nirgends aufgehoben wird — dieselbe Bauart wie bei
      Plausible, einwilligungsfrei nach § 25 Abs. 2 TDDDG. Wer „Do Not Track"
      gesetzt hat, wird nicht gezählt.
- [x] **Downloads zählen serverseitig, nicht im Skript.** Der Verweis im
      Kasten zeigt auf `api/count.php?f=…`, das zählt und dann auf `/dl/`
      weiterleitet; ausgeliefert wird die Datei weiter vom Webserver selbst,
      damit ein abgebrochener Download fortsetzbar bleibt. Ein Zähler im
      Skript hätte genau die Zahl verschluckt, auf die es ankommt — die
      blockt ein Werbefilter zuerst. `tools/make_download.py` erzeugt den
      Verweis so; die sechs bestehenden Kästen sind nachgezogen.
- [x] **Datenschutzerklärung und `robots.txt` nachgezogen.** Beide behaupteten
      das Gegenteil dessen, was jetzt läuft — die eine „keine Analyse- oder
      Tracking-Dienste", die andere wörtlich „kein Zählpixel". Der erste Satz
      stimmt weiter, sobald er von *Diensten Dritter* spricht; der Rest steht
      jetzt vollständig da, samt Rechtsgrundlage und Widerspruchsweg. `/api/`
      ist für Suchmaschinen gesperrt.

- [x] **Hochgeladen und am echten Server nachgemessen.** Elf Dateien, und
      danach die Probe gegen solidon3d.de: Preis und JSON-LD stehen auf 69,
      der Zählruf antwortet mit 204, der Download mit 302 auf die echte
      Datei, ein erfundener Name und `?f=../support.php` mit 404, die
      Auswertung mit 503, und `/api/.stats/` ist von außen nicht abrufbar.
      Der erste Anlauf scheiterte an `530 Login incorrect` — über FTPS heißt
      das wirklich das Passwort und nicht den SSH-Schalter, also nach
      **einem** Versuch angehalten statt ein zweites zu probieren; drei in
      Folge wären bei fail2ban eine gesperrte IP.

- [x] **Die Auswertung hat ihr Passwort.** `.stats-zugang.php` liegt auf dem
      Server, der Hash ist gültig — die Seite antwortet mit dem Formular
      statt mit „noch nicht eingerichtet", und ein falsches Passwort bekommt
      „Das war es nicht." statt der Meldung über einen unbrauchbaren Hash.
      Damit ist die Kette vom Zählruf bis zur Zahl geschlossen.
- [x] **Basic-Auth war der falsche Weg und ist ersetzt** (`c9288f0`). Das
      Browserfenster verlangte einen Benutzernamen, den niemand vergeben
      hatte, und es kam bei jedem Aufruf wieder: Unter CGI oder FastCGI —
      auf Plesk die Regel — reicht der Webserver den `Authorization`-Kopf
      nicht an PHP durch, das Passwort kam also nie an. Jetzt ein eigenes
      Formular mit einem signierten Cookie: kein Sitzungszustand auf dem
      Server, dreißig Tage gültig, nur unterhalb von `/api/`, und ein
      Passwortwechsel entwertet jedes ausgestellte Cookie.

## Ein Durchgang durchs Haus, und was dabei liegen blieb (20.08.2026)

Ein Auftrag ohne Ziel: aufräumen und optimieren. Das ist die Sorte, bei der man
am Ende viel angefasst und nichts verbessert hat, wenn man nicht vorher messen
geht. Also zuerst gemessen.

**Was strengere Regeln finden würden, ist jetzt eine Zahl und keine Ahnung.**
`pyproject.toml` schließt `PERF` und `DTZ` mit Begründung aus; über die übrigen
Regelfamilien stand dort nichts. Nachgezählt: `PLE` (echte Fehler) 0, `RET` 0,
`TID` 0, `PGH` 0 — die vier Familien, in denen ein Befund ein Mangel wäre, sind
leer. Die großen Zahlen sind durchweg Stil: `S` 6773 (fast alles `assert` in
Tests), `D` 3571 (Docstring-Form), `SLF` 865 (Tests greifen auf private Namen,
wie sie sollen), `ARG` 797. Von `PLW` bleiben 48, davon 18 `subprocess.run`
ohne `check` — alle in `tools/` und `tests/`, alle mit eigener Auswertung des
Rückgabewerts, keiner im Programm. Die 23 `PERF`-Befunde sind ausnahmslos
`PERF401` und keiner steht in einer heißen Schleife: Handbuchtext,
G-Code-*Lesen*, Register, Tests. Der Ausschluss bleibt, aber er ist jetzt
nachgemessen und nicht behauptet.

**Toter Code: 24 Kandidaten auf 2946 Definitionen.** Gesucht über den
Syntaxbaum von `app/`, gezählt gegen `app/`, `tests/`, `tools/`, `.claude/`,
`website/` und jede Markdown-Datei des Projekts — ein Name, der nur an seiner
eigenen Definitionsstelle vorkommt, ruft niemand. Vierzehn der
vierundzwanzig waren Rückrufe des Rahmens (`paintEvent`, `dropEvent`,
`do_POST`) oder Registereinträge, die über `@register_op` und `@register_part`
gefunden werden: richtig gezählt, falsch verdächtigt. Zehn waren echt.

- **`ChatPlaceholder` (`ui/panels.py`) war ein überholtes Duplikat.** Ein ganzes
  Widget mit dem Hinweis aus §2.3 — „Der Chat braucht einen Zugang zu einem
  Sprachmodell" —, das niemand baut. Denselben Satz zeigt
  `ChatPanel.set_available()` in `ui/chat.py`, und die kann mehr: einen Knopf
  zum Einrichten und den gesperrten Zustand nach Ablauf des Testlaufs. Der
  Beweis kam beim Löschen von selbst — danach war `ROOMY` in der Datei
  ungenutzt, das Widget war also ihre einzige Nutzerin.
- **`describe_plan` (`core/export/writer.py`) versprach zwei Aufrufer, die es
  nicht gibt.** „Für Statusleiste und Kommandozeile": Die Kommandozeile
  schreibt stattdessen eine Zeile je Datei, was mehr sagt als „3 Dateien ·
  42 mm · 12,3 cm³". Auch hier fiel ein Import mit — `tr` wurde in dieser Datei
  nur von ihr gebraucht.
- **`known_languages` (`i18n/__init__.py`) stand gegen `available_languages()`.**
  `AGENTS.md` nennt die zweite als *den* Weg, Sprachen zu finden; die erste
  zählte die geladenen Kataloge und war eine zweite Antwort auf dieselbe Frage.
- **`forget_images` (`ui/manual_window.py`) hatte nichts mehr zu tun.** Ihr
  Docstring nannte Sprach- und Themenwechsel: Das Thema steht längst im
  Cache-Schlüssel, und eine andere Sprache erscheint laut Einstellungsdialog
  „beim nächsten Start" — im laufenden Prozess wechselt sie nicht.
- Dazu `_cavity` (`geom/hollow.py`), `evaluated_object_ids` (`scene/evaluate.py`,
  eine Zeile um `tuple(result.scene.objects)`), `source_hash`
  (`scene/hashing.py` — die Identität läuft über `object_hash`),
  `with_findings` (`types.py`), `is_circle` (`sketch/profile.py`) und
  `language_model_available` (`core/tools.py` — die Oberfläche fragt
  `llm.first_available()` selbst).

Keiner der zehn Namen steht im Bauplan, und das war die Bedingung: Regel 5 sagt,
dass Signaturen aus §9 feststehen, bevor ein Modul entsteht. Eine davon zu
löschen wäre eine Bauplanänderung und kein Aufräumen.

**Kein verwaistes Modul.** Dieselbe Suche über ganze Dateien nannte sieben von
191 — und alle sieben waren Fehltreffer meines Ausdrucks: mehrzeilige Importe
(`parts/__init__.py` holt `mounting`, `structure` und `testbodies` in einer
Klammer) und die Ladeliste in `bootstrap.py`, die `colour_ops` sehr wohl nennt.

**Der wirkungslose Dezimaltrenner im Download-Kasten ist weg.** Der Fund vom
20.08. stand als Entscheidung da, und sie ist gefallen: `Package.size` schrieb
`f"{…:.0f} MB".replace(".", DECIMAL_MARK[language])`, und bei null
Dezimalstellen steht dort nie ein Punkt. Also die Ersetzung weg und nicht eine
Stelle mehr — „173 MB" ist, was eine Downloadseite zeigt, und eine Tabelle für
sechs Sprachen, die seit dem ersten Tag ohne Wirkung war, verdient keine
Dezimalstelle als Rechtfertigung. Mit ihr fällt der Parameter: `size` ist jetzt
eine Eigenschaft ohne Sprache. Der Grund steht im Docstring, für den Fall, dass
jemand den Trenner zurückholen will.

**Zwei Katalogruppen hießen fast gleich — in zwei Sprachen, nicht in einer.**
Der Fund vom 20.08. nannte Französisch: „Fixations" für Verbindungen neben
„Fixation" für Befestigung, im Katalog untereinander, ein Buchstabe
Unterschied. Portugiesisch hatte dasselbe mit „Fixações" gegen „Fixação", und
das hatte niemand gesehen. Die Gruppe `fasteners` trägt Mutternfalle, Gewinde
und Schraubenloch mit Senkung, also reine Schraubenware; `mounting` trägt
Wandhalter, Magnettasche und Schlüsselloch, also das Anbringen an etwas. Damit
heißen sie jetzt „Visserie" und „Parafusos e roscas", und „Fixation"
beziehungsweise „Fixação" bleibt der Befestigung.

**Der Wächter dazu war beim ersten Versuch hohl.** Er rief `install_language`
und las `str(GROUPS[…])` — `install_language` *lädt* einen Katalog, umschalten
tut `set_language`. Sechs Sprachen liefen also sechsmal gegen die deutschen
Namen und waren grün, auch mit den alten Werten wieder eingesetzt. Gezeigt hat
das erst die Gegenprobe. Jetzt löst der Test über `title.translate(language)`
auf — kein globaler Zustand, keine Reihenfolge — und prüft zuerst, dass
überhaupt etwas übersetzt wurde, sonst misst er wieder Deutsch.

Geprüft wird der **Wortstamm** und nicht die Gleichheit: Zwei verschiedene
Zeichenketten sind noch kein Unterschied, den jemand im Vorbeigehen sieht. Ein
Abstandsmaß über die ganzen Wörter hätte Portugiesisch durchgelassen, denn
zwischen „fixacao" und „fixacoes" liegen drei Änderungen. Was die beiden Fälle
verbindet, ist der gemeinsame Anfang, und den prüft der Test: die ersten fünf
Buchstaben ohne Akzente und Großschreibung. Gegenprobe gefahren, beide Sprachen
rot, danach beide grün.

**Die Suite: 4595 Tests, 132 von 133 Dateien grün.** Am Stück gefahren brach
sie bei 75 Prozent mit einer Zugriffsverletzung in `test_sculpt_session.py` ab
— der offene Punkt, den `tools/run_suite_isolated.py` in seinem Docstring
beschreibt, eine Beschädigung, die über Dateigrenzen kumuliert. Je Datei ein
Prozess: nur `test_performance.py` rot, und dort nur der *relative* Teil.

### Was dabei auffiel — und noch am selben Tag behoben wurde

- [x] **`sketch_solve_200` konnte seinen eigenen Vergleich nicht halten — es
      war der Müll seiner Vorgänger.** Die Bestmarke stand bei 117 ms, im Lauf
      der ganzen Datei kam der Test auf 155, also 1,33fach bei einer Schwelle
      von 1,25. Der Docstring der Datei nannte denselben Effekt seit je
      („allein 114 ms und hinter `test_slice.py` 162"), ohne seine Ursache.
      Gemessen wurde sie mit je drei frischen Prozessen und den fünf großen
      Messungen davor: ohne Aufräumen 142, 139 und 151 ms, mit `gc.collect()`
      126, 122 und 121 — und ein **Aufwärmlauf ändert nichts** (146, 149, 144).
      Es sind also keine trägen Importe und keine kalte erste Runde: Der Haufen
      ist nach einer Million Dreiecken gewachsen, die nächste
      Generation-2-Sammlung läuft über alles, und sie fällt dem zur Last, der
      gerade gemessen wird.

      `measure()` räumt jetzt **vor** der Uhr auf. Nicht während — was die
      gemessene Arbeit selbst an Müll erzeugt, kostet sie weiter Zeit, und das
      soll sie auch: Eine Prozedur, die den Speicher vollschreibt, bezahlt das.
      Weg ist nur die Rechnung des Vorgängers, und damit misst dieselbe
      Rechnung dasselbe, egal was vor ihr lief. Kein `gc.disable()` — das wäre
      Schönrechnen. Gegenprobe bei gleicher Marke und gleicher Reihenfolge:
      ohne den Aufruf wieder 1,33fach und rot, mit ihm 19 von 19 grün.
- [x] **Die Abbildungen des Handbuchs merken sich ihre Breite nicht mehr.**
      Der Cache lag unter `(key, theme)`, das gespeicherte Bild war aber schon
      auf `viewport().width() - 40` skaliert — die Breite fehlte im Schlüssel
      und steckte im Wert. Gemessen: bei 400 Punkten Spaltenbreite stand der
      Startbildschirm auf 374 und blieb dort, auch als das Fenster auf 1600
      aufging. Ein Schlüssel mit Breite allein hätte nichts geholfen, denn
      **Qt fragt nicht wieder** — nach zwei Größenänderungen kamen null
      weitere `loadResource`-Rufe an.

      Zwei Änderungen. Der Cache hält jetzt das **Urbild**, das von der
      Spaltenbreite nicht abhängt; das Skalieren passiert bei jedem Abruf und
      kostet nichts. Und `resizeEvent` legt die Abbildungen der offenen Seite
      über `addResource` neu ins Dokument, verzögert um 150 ms, weil ein Zug
      am Fensterrand hunderte Ereignisse schickt. Über `addResource` und nicht
      über ein neues `setMarkdown`: Das setzte die Leseposition zurück, mitten
      im Lesen.

      Gemerkt wird dabei **nur, was teuer ist** — das Rastern eines SVG. Die
      sechs Bildschirmfotos wiegen entpackt 51 MB, drei davon je 14; wer ihre
      Urbilder behält, um sie später anders skalieren zu können, tauscht ein
      Bildproblem gegen ein Speicherproblem. Sie kommen bei Bedarf von der
      Platte, und das passiert je Seitenwechsel einmal, weil Qt das Ergebnis
      selbst behält. Gegenprobe: mit stillgelegtem `_refit` bleiben alle fünf
      Abbildungen der Seite auf 374 Punkten, schmal wie breit.
- [x] **`profile_slot` war keine Vorarbeit ohne Zweck — der Fund war falsch
      begründet.** Bauplan §24.2 nennt „Aluprofil-Nutmaße" ausdrücklich als
      Teil der Normteiltabelle, und zwar als *Nachschlagewert*: „Loch für
      M4-Einpressmutter" muss eines sein. Die Erstbestückung in §24.1 listet
      dagegen keinen Aluprofil-Baustein — es fehlt also nichts. Und erreichbar
      ist der Wert längst: `standard_text("profile", "2020")` antwortet, für
      den Agenten und für die Fernsteuerung. Ein Baustein dafür wäre die volle
      Achter-Checkliste plus ein Maß, das die Tabelle nicht führt (die
      Kammertiefe), und damit eine Bauplanänderung — nicht Aufräumen.

      Beim Prüfen fiel ein **echter** Fund an, und der ist behoben: Die
      Zuordnung Art → Tabelle stand als `_STANDARD_TABLES` in
      `agent/session.py`, mit einem `getattr(standards.load(), …)` daneben.
      Damit lag das Wissen über die Tabellen in der Agentenschicht, an den acht
      typisierten Zugriffen vorbei, und eine neunte Tabelle hätte zwei Dateien
      gebraucht — von denen man die zweite still vergisst. Sie heißt jetzt
      `standards.TABLES` und steht neben den Tabellen; `standards.table(kind)`
      ist der eine Weg über den Namen, die typisierten Zugriffe bleiben der
      Weg über die Größe, weil nur sie einen Fehler mit Handlungsvorschlag
      werfen (Regel 17). `test_every_table_can_be_looked_up_by_its_kind` hält
      beides zusammen: jedes Tabellenfeld über eine Art erreichbar, jede Art
      auf ein Feld, das es gibt. Gegenprobe gefahren — `"profile"` aus der
      Zuordnung genommen, Test rot.

      Nebenbei verdeckte der Parameter `table` in `_lookup` nun die neue
      Modulfunktion gleichen Namens; er heißt `entries`.

## Die Bedienung an der Uhr gemessen (21.08.2026)

Zweiter Blick auf dieselbe Frage, mit einem anderen Messgerät: nicht durch das
Register und nicht durch einen Auditlauf, sondern an der **Zeitleiste der
Signale** einer laufenden Oberfläche. Gemessen wurde, was zwischen dem Ablegen
einer Datei und dem fertigen Modell passiert — und wann welche Anzeige dabei
kommt und geht.

Was dabei gehalten hat: Ablegen wirkt auf Fenster, Viewport und Objektbaum
(§2.3, alle drei geprüft). Der kürzeste Weg vom Sehen zum Tun steht — eine
angeklickte Bohrung bietet ihre vier Operationen direkt an, eine Fläche ihre
sechzehn in vier Gruppen. Dialoge sind vorbelegt; leer bleiben fünf Felder im
ganzen Register, und alle fünf zu Recht (Quelldatei, Name, Text). Rückfragen
gibt es nur vor dem Unwiderruflichen, beide mit Handlungsnamen auf den Knöpfen
statt Ja/Nein.

### Behoben, jeder mit Test

- [x] **Der Balken verschwand mitten in der Rechnung.** Ein Arbeiter ist
      fertig, bevor Qt sein `finished` zugestellt hat; in dieser Lücke startet
      der nächste Lauf. Der Nachzügler kam dann in `_on_thread_done` an,
      schrieb `None` in `_worker` — das Feld gehörte längst dem Nachfolger —
      und meldete `busyChanged(False)`. Zu sehen an der Stelle, an der jeder
      anfängt: Eine Datei auf den Startbildschirm ziehen legt zwei Läufe
      hintereinander, und bei `dense_1m.stl` (1,3 Mio Dreiecke) waren Balken,
      Abbrechen und Ladeanzeige nach 0,12 s weg, während die Anwendung noch
      4,7 s rechnete — §2.8 verlangt ab zwei Sekunden das Gegenteil. Unsichtbar
      und schwerer: `busy` log danach, `wait_for_idle` wartete nicht, und der
      nächste `evaluate_async` hätte einen zweiten Lauf **parallel** gestartet
      statt ihn einzureihen (§15.6). Dazu blitzte die leere Szene des
      Vorgängers über dem ladenden Modell auf (§15.3). `Session._outdated`
      beantwortet die Absenderfrage jetzt für alle vier Abschluss-Slots; ein
      ersetzter Lauf meldet kein `False` mehr, sonst flackert die Anzeige beim
      Ziehen an einem Schieber. Die Regel dazu stand in
      `.claude/rules/oberflaeche.md` — als Sache der Stabilität; sie ist
      genauso eine der Anzeige, und der Absatz sagt das jetzt.
- [x] **Die Einheitenfrage war nicht beantwortbar.** „In welcher Einheit ist
      diese Datei gespeichert?", zur Wahl „cm" und „in" — zwei Wörter. In
      keinem STL steht die Einheit; wer eine fremde Datei herunterlädt, kann es
      nicht wissen. Was er weiß, ist, wie groß das Teil sein soll. Neben jeder
      Antwort steht jetzt, wie groß das Modell mit ihr wäre (`unit_question`):
      `cm: 40.00 × 20.00 × 2.50 mm`, `in: 101.60 × 50.80 × 6.35 mm`. Anhalten
      und fragen war schon richtig (Leitprinzip 6) — eine Frage, die niemand
      beantworten kann, ist die halbe Regel.
- [x] **Der häufigste Befund von Weg 1 bot die zwei Handlungen an, die nicht
      helfen.** Ein heruntergeladenes Modell sitzt mittig auf z = 0 und steckt
      zur Hälfte unter der Platte. Der Kern unterschied den Fall längst im
      **Satz** und im Schweregrad — „ein Klick behebt sie, und das ist ein
      Hinweis" steht in `_severity_for` —, nur nicht in der **Kennung**, und
      der Prüfbericht hängt seine Handlungen an ihr auf. Angeboten wurden
      *Modell teilen* und *Auf den Bauraum verkleinern*: genau die falsche
      Fährte, vor der der Docstring daneben warnt. Jetzt `arrange.below_bed`
      mit *Auf das Bett setzen* und `arrange.off_the_plate` mit *Auf dem Bett
      anordnen*, beide verdrahtet. §17.1 sagt „anbieten, nicht erzwingen" —
      angeboten war es nirgends.
- [x] **Ein Merkmal ohne eigene Operationen gab weniger her als der Körper
      daneben.** Zu `thread` bestand das Menü aus Ausblenden, obwohl der Körper
      mitgewählt ist. Fällt die Merkmalsliste leer aus, stehen jetzt die
      Operationen des Körpers da — dieselbe Überlegung, aus der `applies_to` in
      der Befehlspalette eine Reihenfolge ist und keine Auswahl. Die offene
      fachliche Frage (welche Operation auf ein fertiges Gewinde gehört) bleibt
      offen und steht als benannte Ausnahme im Test.

### Der zweite Durchgang, tiefer: die Wege zurück (21.08.2026)

Gemessen wurde diesmal nicht, was die Anwendung anbietet, sondern **was ein
Kunde tut, wenn etwas schiefgeht**. Jede Ausnahme des Kerns wurde durch den
Fehlerdialog geschickt, jede Handlung gegen ihren Handler gehalten. Das Ergebnis
war eindeutig: Die häufigsten Vorschläge waren die ohne Wirkung.

- [x] **Die Handlungen am Befund fand nur, wer rechtsklickte** — der offene
      Punkt von oben, und mit dem Fund darunter wurde er dringend. `_on_menu`
      baute sie vollständig und richtig, nur hing der ganze Zugang an einem
      Rechtsklick auf eine Listenzeile. Unter der Liste steht jetzt eine
      Knopfzeile mit den Handlungen des gewählten Befunds; sie bleibt
      unsichtbar, solange es keine gibt, und beide Wege lesen aus derselben
      Quelle (`actions_for`).
- [x] **Der häufigste Fehler des Programms hatte keinen Weg zurück.** Eine
      Operation, deren Werte nicht gehen, wirft **keinen** Fehlerdialog — der
      Kern macht daraus einen Befund und hält die Kette an (§15.3). Im
      Prüfbericht stand dann „Der Wert liegt über dem zulässigen Höchstwert",
      und der Weg zu diesem Wert war, den Schritt im Verlauf zu suchen und
      doppelzuklicken. *Eingabe korrigieren* stand daneben — als Satz, denn es
      war mit fünf Ausnahmen die häufigste Handlung des Kerns und die einzige
      ohne Handler. Jetzt öffnet sie den Schritt (`edit_operation`), und zwar
      **mit dem Cursor in dem Feld, das der Kern nennt**: Der Befund trägt
      `field`, der Dialog hat `focus_field`, und ein Wert hinter „Weitere
      Einstellungen" klappt dabei auf. Beim Übernehmen wird der Schritt
      ersetzt, kein zweiter angelegt (§15.4) — damit ist auch §2.1 („jeder Wert
      nachträglich änderbar") an der Stelle eingelöst, an der es zählt.
- [x] **Ein gescheiterter Export ließ sich nur von vorn wiederholen.** Die
      häufigste Ursache ist eine Datei, die im Slicer offen liegt; wer sie dort
      schloss, musste Format, Ordner und Namen erneut wählen. `FileWriteError`
      schlägt *Erneut versuchen* vor, und wie bei *Eingabe korrigieren* fehlte
      der Handler. Angeboten wird er nur, solange es etwas zu wiederholen gibt.
- [x] **Ein gescheitertes *Speichern* bot gar nichts an** — und das ist der
      datenkritischste Schreibfehler von allen: Wessen Projekt sich nicht
      speichern lässt, hat seine Arbeit noch nicht in Sicherheit. Zwei Fälle
      kommen wirklich vor, und beide haben eine Antwort: Die Datei liegt in
      einem anderen Programm offen (dann hilft derselbe Weg noch einmal), oder
      das Laufwerk ist voll (dann hilft ein anderer Ort). `FileWriteError`
      führt jetzt `RETRY` und das neue `SAVE_ELSEWHERE` vorn, *Eingabe
      korrigieren* dahinter — an einem Schreibfehler gibt es keine Eingabe, und
      `NEEDS_OP` blendet es dort ohnehin aus. Export und Speichern teilen
      dieselbe Antwort (`_WriteFailure`): Beide scheitern am selben
      Betriebssystem.
- [x] **„Ein Update öffnet sie" — und niemand bot eines an.** Eine Projektdatei
      aus einer neueren Version wird abgelehnt, und der Satz dazu nannte den Weg
      seit je. Angeboten wurde *Eingabe korrigieren*, und an einer Datei aus der
      Zukunft gibt es keine Eingabe zu korrigieren. Die Migration schlägt jetzt
      `CHECK_UPDATES` vor, verdrahtet auf denselben Weg wie *Hilfe → Nach einer
      neuen Version sehen*. Dazu ein eigener Titel: „Die Eingabe war so nicht
      verwendbar" stand über einer Datei, an der niemand etwas eingegeben hat.
- [x] **Die dritte Bauraum-Handlung fehlte noch.** Teilen und Verkleinern kamen
      mit dem Kontextmenü des Berichts; *Anderes Druckerprofil wählen* blieb
      liegen, weil ihr Weg fehlte — der Drucker eines **offenen** Projekts wird
      in den Druckeinstellungen gewechselt, nicht in den
      Anwendungseinstellungen, wo nur die Vorgabe für neue Projekte steht. Für
      den Kunden mit zwei Maschinen ist sie die naheliegendste der drei.

### Was auffiel und eine Entscheidung braucht

- [x] **Sechs von 86 Operationen führten ein Kürzel** — und die Palette lehrt
      nebenbei nur, was auch dasteht (§19.2). Jetzt sind es vierzehn: die drei
      Booleschen (Strg+Umschalt+V/A/X), die beiden Handgriffe an der Platte
      (Strg+Umschalt+B und O), *Reparieren* (Strg+Umschalt+R), *Aushöhlen*
      (Strg+H) und *Spiegeln* (Strg+M). Die Regel dahinter steht in
      `.claude/rules/oberflaeche.md`: Der Buchstabe kommt aus dem deutschen
      Titel, bei Belegung kommt Umschalt dazu, und wo auch das belegt ist,
      bleibt die Operation ohne — *Skalieren* ist der Fall, denn S gehört dem
      Speichern und Umschalt+S dem Speichern unter.

      **Dabei fiel eine Lücke in der Prüfung auf.**
      `test_registry_consistency.py` hält die Kürzel der Operationen
      auseinander, und das Fenster bringt dreiundvierzig weitere mit, die nicht
      aus dem Register kommen. Eine Dublette dazwischen führt **keine** der
      beiden Aktionen aus (Qt meldet „Ambiguous shortcut overload") — und
      aufgefallen wäre sie erst beim Drücken. `test_ui.py` prüft das jetzt am
      gebauten Fenster.
- [x] **`label_text` zeigte acht Werte auf der Vorderseite** und füllte damit
      die Grenze aus `test_interface_limits.py` bis an den Rand, während §2.4
      von zwei bis drei spricht. *Tiefe* und *Materialslot* stehen jetzt hinten:
      0,6 mm sind drei Schichten und decken erhaben wie vertieft, und ein
      Farbwechsel setzt einen zweiten Filamentstrang voraus — wer ihn hat, sucht
      ihn gezielt. Vorn bleiben Text, Schriftgröße, Art und die Position, also
      vier Werte.

## Die Zusatzsoftware aus Kundensicht (21.08.2026)

Vier Programme kann Solidon benutzen, keines wird mitgeliefert (§36, §38). Die
Liste dazu stand seit langem; durchgesehen wurde diesmal der ganze Weg von
„fehlt" bis „läuft" — und der hatte an sechs Stellen ein Loch.

- [x] **Fehlende Software bat um einen Fehlerbericht.** `BRepUnavailable`
      nannte keine Vorschläge; `AppError` fällt dann auf „Abbrechen" zurück,
      und einem Dialog, dem sonst nichts bleibt, legt `offered_actions` den
      Fehlerbericht bei. Wer eine Verrundung ohne OpenCASCADE versuchte, wurde
      also gebeten, einen Fehler zu melden. `ScadUnavailable` schlug seit je
      `install` vor — verdrahtet war unter dieser Kennung **nichts**, die Liste
      der zusätzlichen Programme hing unter `open_settings`. Der Rat wurde
      damit ein grauer Satz, während der Dialog, der ihn einlöst, im
      Hilfe-Menü stand. Beide Enden sind jetzt verbunden, und `OPEN_SETTINGS`
      heißt wieder, was es tut: `INSTALL_MISSING` trägt den Namen des
      Menüeintrags, in den es führt (`tests/test_errors.py`,
      `tests/test_ui.py`).
- [x] **Der Kunde konnte seinen Schlüssel nicht ablegen.** `keyring` wird in
      `backends/keys.py` innerhalb einer Funktion importiert, damit die
      Anwendung ohne es startet — PyInstaller sieht das nicht, und im gebauten
      Paket lag es nicht bei. `keys.store()` gab dort **immer** False zurück:
      Der Chat-Dialog nahm einen Schlüssel an und behielt ihn nicht, der
      Rückfall war eine Umgebungsvariable für Bauserver. Die Liste bot daneben
      an, den Schlüsselbund zu installieren, mit einem Knopf, der in einem
      Paket nicht drückbar ist. `tests/test_packaging.py` prüft jetzt jede
      optionale Abhängigkeit gegen die hiddenimports.
- [x] **Der Dialog fror knapp drei Sekunden.** Gemessen, offscreen, mit warmem
      Cache: `InstallDialog()` **2,97 s**, jede Auffrischung weitere **2,10 s**
      — im Qt-Hauptthread, ohne Wartemarke, obwohl §38 dafür einen Arbeiter
      verlangt. Der Grund war nicht die Suche, sondern ihre Anzahl: Jede Zeile
      fragte `tools.state_of` **dreimal** (`present`, Fundort, Erklärung), und
      bei den zwei Diensten hing an jeder Frage eine Socket-Probe. Erhoben wird
      jetzt einmal je Zeile (`install.statuses`) in einem Arbeiter — **12 ms**
      bis zum offenen Dialog, **0 ms** bis zur Rückkehr aus `refresh()`, 1,0 s
      für die Erhebung selbst. Bis dahin steht ein drittes Zeichen in der
      Zeile: „?" statt einer Behauptung, die niemand geprüft hat.
- [x] **Auf macOS und Linux war der ganze Weg eine Sackgasse.** `installable`
      hing allein an `winget`; wer Solidon aus einem der Linux-Pakete oder von
      der Mac-Seite hatte, lag an jedem der vier Programme bei demselben Satz —
      unabhängig davon, ob eine Paketverwaltung fehlte oder das Programm dort
      keine Kennung hat. Dazugekommen sind **Homebrew** und **Flatpak**, und
      `apt`/`dnf` fehlen mit Absicht: Sie verlangen `sudo`, und eine
      Passwortabfrage in einem Unterprozess, den niemand sieht, hängt bis zum
      Zeitmaß. Flatpak installiert mit `--user`.

      Die Kennungen sind am 21.08.2026 einzeln nachgeschlagen, und zwei davon
      sind nicht die naheliegenden: Das Homebrew-Cask `openscad` ist als
      „fails_gatekeeper_check" veraltet und **zum 01.09.2026 abgeschaltet** —
      eingebaut hätte es in zehn Tagen einen Fehlschlag ausgeliefert, also
      steht `openscad@snapshot` dort. Und OrcaSlicer liegt auf Flathub unter
      `com.orcaslicer.OrcaSlicer`, nicht unter der Kennung des ursprünglichen
      Urhebers, die winget weiterführt. Die Flathub-Kennung wird zur Adresse
      einer `.flatpakref`: ohne sie bräuchte es eine eingerichtete Quelle, und
      wer die nicht hat, sähe „remote flathub not found".
- [x] **„Nach einem Neustart ist es zu sehen."** Das stand nach einer
      erfolgreichen Installation da, und der Grund war die Umgebung dieses
      Prozesses: Das Installationsprogramm ergänzt den PATH des *Systems*, die
      Kopie davon stammt vom Start. `discover.refresh_path()` liest beide
      Hälften aus der Registry nach, wie Windows sie selbst zusammensetzt —
      damit ist der Neustart der Ausnahmefall und nicht die Regel.
- [x] **Sieben Knöpfe einzeln.** *Alles Fehlende installieren* ordnet die
      Reihenfolge; die Entscheidung bleibt der eine Druck (§36). Dabei fand der
      Test einen Fehler im ersten Entwurf: Angestoßen aus `_finished`
      verschluckte die Reihe einen Eintrag, weil `done` kommt, während der
      Arbeiter noch läuft — `_start` sah ihn als beschäftigt und kehrte um,
      obwohl der Eintrag schon aus der Warteschlange genommen war. Von vier
      fehlenden Programmen wurden drei installiert, ohne ein Wort dazu.
      Weitergeschaltet wird jetzt in `_thread_done`.
- [x] **Und wo Solidon nicht installieren kann, steht der Befehl da.** „Auf
      diesem System geht es nicht" ist keine Auskunft, mit der jemand
      weiterkommt; die Zeile, die es täte, kennt Solidon — sie entsteht aus
      denselben Konstanten wie der ausgeführte Befehl, steht im Blick und
      liegt auf einem Knopf in der Ablage.

### Der zweite Schritt, den es nicht gab

Der eigentliche Fund, und er kam als Satz: „hab es installiert, aber danach
weiß man auch nicht was man machen soll". Beide Dienste brauchen nach der
Installation etwas, das nirgends stand außer in einem Satz mit einem
Terminalbefehl darin.

- [x] **Ollama** installiert bringt kein Modell mit und läuft nicht
      zwangsläufig. Die Auskunft dazu war „«ollama serve» startet es" und
      „«ollama pull» mit dem Modellnamen holt es" — gerichtet an jemanden, der
      in einem Fenster sitzt. *Chat einrichten* führt jetzt alle drei Schritte:
      ein Satz über den Dienst mit dem Knopf, der zu ihm gehört
      (`tools.start`, losgelassener Prozess, ohne Konsolenfenster, nie von
      Solidon beendet); eine Auswahl aus dem Installierten und den bewährten
      Modellen mit Größe und Messwert; und *Modell holen* über `/api/pull` mit
      echtem Prozentwert aus `total`/`completed` — neun Gigabyte an einem
      unbestimmten Balken sehen aus wie ein Hänger. Abbrechen geht, und der
      Satz dazu sagt, dass ein neuer Versuch fortsetzt: Ollama behält, was
      schon geladen ist.
- [x] **ComfyUI** braucht die Knoten und das Modell. Die Anwendung nannte
      dafür „«python tools/setup_comfyui.py»" — einen Befehl, den ein Kunde
      **nicht ausführen kann**: `tools/` steht nicht in den `datas` der Spec
      und reist im Paket nicht mit. Die Logik liegt jetzt in
      `app/core/backends/comfy_setup.py`, die Knoten in
      `app/core/backends/data/comfyui/` — beides paketiert —, und
      `app/ui/comfy_dialog.py` führt die vier Schritte mit Fortschritt und
      Abbrechen. `tools/setup_comfyui.py` ist ein dünner Aufrufer darauf und
      tut unverändert dasselbe. Ein Test hält fest, dass **kein Text, der durch
      `_()` oder `tr()` geht**, dieses Skript noch nennt.
- [x] **Der zweite Schritt ist ein Begriff im Kern**, kein Sonderfall der
      Oberfläche: `Requirement.follow_up` benennt ihn, die Zeile zeigt seinen
      Knopf, sobald das Programm da ist, und `tests/test_install.py` prüft, dass
      zu jeder Kennung ein Zweig steht. Ein Knopf ohne Wirkung ist schlimmer
      als keiner.
- [x] **Und eine Handbuchseite** — *Zusätzliche Programme einrichten*, in sechs
      Sprachen. Sie sagt je Programm, was es bringt und was danach noch zu tun
      ist, samt der Zahlen, die die Entscheidung tragen: 16 GB für qwen3:14b,
      sieben Milliarden Parameter als Untergrenze, 7,5 GB für TripoSG, und der
      Neustart von ComfyUI, ohne den alles liegt und nichts geht.
- [x] **Die Liste zeigt dem Kunden nur, was ihn angeht.** Von den sieben
      Einträgen sind drei Python-Pakete; im Paket reisen sie mit, standen dort
      als „vorhanden" und trugen einen Knopf, der von Entwicklungsumgebungen
      sprach — Rauschen vor den vier Zeilen, um die es geht. `install.shown()`
      lässt sie weg, **solange sie da sind**: Ein Paket ohne OpenCASCADE hat
      keine Fasen und kein STEP, und eine stille Lücke ist das Gegenteil von
      §36.

## Dieselben neun Modelle, diesmal nachgebaut (21.08.2026)

Zwei Vorwürfe zum vorigen Eintrag, beide berechtigt: die Modelle waren nie
**nachgebaut**, nur eingelesen und bearbeitet — und die Erweiterungen waren
austauschbar. Auf jedes Teil kam dasselbe Schraubenloch, dieselbe Beschriftung,
dieselbe Magnettasche, gleich was das Teil ist.

### Erst hinsehen, dann erweitern

Jedes Modell durch die Oberfläche geladen und angesehen, Körper für Körper.
Heraus kam, dass sechs der neun Dateien **ein Teilesystem** sind: 底座 (Fuß),
拓展架 (Auslegerarm) und drei Sätze 连接件 (Querstangen) bilden ein
Sechskant-Steckregal für Filamentrollen. Die Stangen tragen an beiden Enden
einen Sechskantzapfen Ø8,147 × 9, die Arme die passenden Buchsen; die Zahl im
Dateinamen ist die Rollenbreite. Die übrigen drei: eine KitKat-Nachbildung als
Kit-Card mit vier ausbrechbaren Riegeln, ein Flugpropeller-Spielzeug, eine
massive Entenfigur — und ein Modellbausatz mit 52 Teilen.

Damit werden die Erweiterungen andere. Die 222er Stange passt auf kein 220er
Bett, also wird sie **verstiftet geteilt** — mit Sechskantstiften, derselben
Verbindung, die das System ohnehin benutzt. Der Fuß trägt eine Rolle und kippt,
also bekommt er **Einpressbuchsen zum Festschrauben**. Die Kit-Card liegt herum,
also bekommt sie **Magnettaschen in der Unterseite** — nicht auf dem Bild — und
ein Loch für den Schlüsselring. Die Ente ist massiv, also wird sie
**ausgehöhlt**. Und dem Modellbausatz wird **nichts** angebaut: ein Bausatz, den
jemand entworfen hat, will gedruckt werden, nicht ergänzt. Die Arbeit liegt im
Anordnen und Schließen.

### Nachgebaut, und gemessen

Die Querstange 连接件-1 ist von Null entstanden, über *Neues Projekt* und die
Operationsdialoge: das Profil als Skizze (22 breit, 12 hoch, unten 1,2 mm
gefast auf 19,6 Basis, oben 6 mm gefast auf 10,0 Deckel — aus den Flächen des
Originals gelesen), 139,64 mm hochgezogen, an beiden Enden ein Sechskantzapfen
über `insert_dowel`.

| | Nachbau | Original | Abweichung |
|---|---|---|---|
| Querschnitt | 22,00 × 12,00 | 22,00 × 12,00 | 0,00 mm |
| Länge | 157,62 | 157,64 | −0,02 mm |
| Volumen | 32 410,1 mm³ | 32 634,5 mm³ | −0,69 % |

Dazu das Gegenstück, der Sechskantsitz — und genau daran kam ein Fehler heraus
(siehe unten).

**Was sich nicht nachbauen lässt, und warum.** Die Entenfigur ist organisch;
sie gehört zu Weg 3 oder 4, nicht zu Weg 2 — mit Grundkörpern kommt man dort
nicht hin, und das ist keine Lücke, sondern die Arbeitsteilung des Bauplans.
Der Schutzring des Propellersatzes verjüngt sich über die Höhe (1026 mm²
Querschnitt in halber Höhe gegen 749 mm² im Mittel): ein Strömungsprofil, kein
Bauteil aus Zylindern. Und die 52 Teile des Bausatzes einzeln nachzubauen wäre
kein Nachbau, sondern ein zweiter Entwurf.

### Zwei Funde, und beide sitzen im Konstruieren

- [x] **Eine Passbohrung, die Material hinzufügt.** `insert_dowel` heißt
      „Passstift und Passbohrung", hat einen Parameter *Art* mit `pin` und
      `bore`, rechnet für die Bohrung sogar das Spiel dazu (`diameter + play`)
      und gibt ein `bore`-Merkmal zurück. Abgezogen wird trotzdem nichts:
      `subtractive` ist eine **feste Eigenschaft des Bausteins**
      (`parts/registry.py`), der Dübel setzt sie nicht, und `parts/ops.py`
      entscheidet allein daran (`"difference" if spec.subtractive else
      "union"`). Gemessen an einem Klotz von 30 × 30 × 20:

      | Baustein | Art | ΔVolumen |
      |---|---|---|
      | `insert_dowel` | `bore` | **+411,7 mm³** |
      | `insert_dowel` | `pin` | +386,6 mm³ |
      | `insert_snap_connector` | `bore` | **+108,5 mm³** |
      | `insert_snap_connector` | `pin` | +43,1 mm³ |
      | `insert_magnet_pocket` | — | −159,9 mm³ |

      Die Bohrung wird also ein etwas **dickerer** Zapfen als der Zapfen — das
      Spiel und die Einführungsfase kommen obendrauf. Zwei Folgen über die
      Geometrie hinaus: Die Szene trägt danach ein `bore`-Merkmal an einer
      Stelle, an der ein Buckel steht, und `applies_to` bleibt leer (es wird
      aus `spec.subtractive` abgeleitet) — ein Klick auf eine Fläche bietet den
      Baustein also gar nicht an. Betroffen sind beide Bausteine mit einem
      Richtungsparameter. Die Frage ist, wo die Richtung hingehört: als
      aufrufbare Bedingung an `register_part`, als Deklaration am Parameter
      (`subtractive_when=("kind", "bore")`, passend zu „Die Angabe steht am
      Parameter"), oder als zwei getrennte Bausteine — was der Oberflächenregel
      „Eine Operation je Handlung, nicht je Variante" widerspräche.

      Entschieden wurde die Deklaration am Parameter — der Abschnitt
      darunter hält die Umsetzung.
- [x] **Das Ausrichten stellt Teile auf die Ecke.** `orient_for_print` legte die
      nachgebaute Stange auf die Diagonale. Gemessen am selben Körper:

      | Lage | Stützvolumen | erste Schicht | Höhe |
      |---|---|---|---|
      | liegend, breite Seite unten | 11,1 mm³ | 1424,3 mm² | 12 mm |
      | diagonal — Sieger der Suche | 0,6 mm³ | **0,1 mm²** | 112 mm |

      Die diagonale Lage gewinnt zu Recht beim Stützmaterial: ihre Flanken
      stehen 47° zur Waagerechten, also gerade steiler als die Stützschwelle,
      und brauchen keine. Sie steht dafür auf einem Hundertstel
      Quadratmillimeter. `better()` vergleicht lexikografisch — Stützvolumen
      zuerst —, und 0,6 gegen 11,1 ist kein Gleichstand, also kommt die
      Aufstandsfläche als Entscheider nie zum Zug. Der Docstring nennt die eine
      Richtung („eine große Aufstandsfläche darf sich nie an echtem
      Stützmaterial vorbeikaufen"); die andere fehlt: **ein paar Kubikmillimeter
      Stützmaterial dürfen keine Lage kaufen, die nicht stehen kann.** Wo die
      Untergrenze der ersten Schicht herkommt, ist die Entscheidung — aus dem
      Profil wie `smallest_printable_volume`, oder als Verhältnis zur
      Ausgangslage, die `search` als `baseline` ohnehin schon kennt.

      Entschieden wurde das Profil, aus demselben Abschnitt darunter.

## Die Richtung steht am Parameter, die Untergrenze im Profil (21.08.2026)

Die zwei Funde des vorigen Eintrags, entschieden und behoben.

### Behoben, jeder mit Test und Gegenprobe

- [x] **Die Passbohrung trägt jetzt ab.** `subtractive` ist eine Eigenschaft des
      Bausteins, und für zwei von ihnen sitzt sie an der falschen Stelle:
      *Passstift und Passbohrung* und *Schnappverbinder* sind je ein Paar, und
      welche Hälfte gemeint ist, entscheidet ein Parameter. Die Angabe steht
      deshalb jetzt **am Parameter** — `ParamSpec.subtractive_on`, deklariert wie
      `depends_on`, also dort, wo die Wahl getroffen wird. Drei Stellen lesen
      sie über `parts/ops.cuts()`: die Operation (welche Boolesche Op), der
      Registereintrag (ob ein Flächenklick den Baustein anbietet) und die
      Vorschau. Ohne Werte gilt „kann abtragen" — `applies_to` ist eine
      Reihenfolge und keine Sperre, und beide Hälften werden auf eine Fläche
      gesetzt.

      Dazu kam ein zweiter Teil desselben Fehlers: **beide Werkzeuge wuchsen
      nach oben**, also aus dem Körper heraus. Die Magnettasche sagt es seit je
      im Docstring — „Der Ursprung ist die Mündung, die Tasche liegt darunter
      (§24.1)" —, und diese zwei taten es nicht. Nur die Fase, die zufällig
      unter dem Ursprung lag, schnitt überhaupt etwas. Gemessen an einem Klotz
      von 30 auf 30 auf 20:

      | Baustein | Art | vorher | nachher |
      |---|---|---|---|
      | `insert_dowel` | `bore` | +411,7 mm³ | **−422,8 mm³** |
      | `insert_dowel` | `pin` | +386,6 mm³ | +386,6 mm³ |
      | `insert_snap_connector` | `bore` | +108,5 mm³ | **−108,6 mm³** |
      | `insert_snap_connector` | `pin` | +43,1 mm³ | +43,1 mm³ |
      | `insert_magnet_pocket` | — | −159,9 mm³ | −159,9 mm³ |

      Die 422,8 mm³ sind das Sechskantloch (Schlüsselweite 7,055 auf 9 tief,
      388 mm³) plus die Senkung an der Mündung — die verengte sich vorher zur
      Mündung hin, was aus einer Einführung eine Sperre gemacht hätte, wenn sie
      je im Material gelegen hätte. Beide Bausteine bekommen eine neue Version
      mit Änderungsverlauf (§24.4): aus einem Buckel wird ein Loch, und wer die
      Bohrung benutzt hat, muss das beim Öffnen erfahren.
- [x] **Das Ausrichten fragt jetzt, ob eine Lage stehen kann.**
      `Profile.smallest_first_layer` ist zehn Extrusionsbahnen im Quadrat — bei
      einer 0,4er Düse 4,2 auf 4,2 mm, also 17,6 mm². `better()` vergleicht
      diese Frage **vor** dem Stützvolumen: Wer stehen kann, gewinnt gegen jeden,
      der es nicht kann, und erst danach wird gerechnet. Gemessen an der
      nachgebauten Verbinderstange, gleiche Suche, gleicher Startwert:

      | | Stützvolumen | erste Schicht | Höhe |
      |---|---|---|---|
      | vorher | 4,4 mm³ | **1,6 mm²** | 111 mm |
      | nachher | 24,1 mm³ | **1327,9 mm²** | 19 mm |

      **Warum zehn Bahnen und nicht vier.** Vier wären das Wenigste, was ein
      Slicer als geschlossene Insel legt — als Grenze zu tief: die diagonale
      Lage kam damit auf 4,5 mm² und gewann weiter. Dasselbe Kandidatenfeld
      zeigt aber eine breite Lücke: die Lagen, die auf einer Fläche liegen,
      tragen 76 bis 2765 mm², die auf einer Kante stehenden 0,06 bis 4,5. Zehn
      Bahnen liegen mit Abstand dazwischen. Eine gewählte Zahl, aber eine mit
      Messung dahinter — und keine, die auf ein Zehntel ankommt. Aus dem Profil
      und nicht als Zahl im Code (Regel 7).

      **Die Grenze ordnet, sie lehnt nicht ab.** Ein Körper, dessen jede Lage
      darunter bleibt — eine Kugel —, bekommt trotzdem eine Antwort: dann tragen
      alle Kandidaten dieselbe, und es bleibt beim alten Vergleich. Gesagt wird
      es aber: `orient.no_footing`, „dieses Teil braucht einen Brim".

Der Testkörper für den zweiten Fund brauchte zwei Anläufe, und beide Fehlschläge
gehören zur Sache: Ein glatter Quader von 22 auf 12 auf 140 hat in jeder Lage
eine ebene Fläche unten, die von selbst gewinnt. Erst mit den Fasen **und** den
zwei Sechskantzapfen an den Enden entsteht der Fall — die Zapfen kosten in der
liegenden Lage Stützmaterial, in der diagonalen keines. Wer den Körper
vereinfacht, prüft etwas anderes, als er behauptet.

## Die zweite Hälfte des Kundenwegs (21.08.2026)

Die beiden Durchgänge davor hörten bei der exportierten Datei auf. Für einen
Kunden fängt dort an, was zählt: Trägt sich das Teil? Was schlägt die Anwendung
an Einstellungen vor? Was kostet der Druck, und stimmt die Schätzung? Dieser
Durchgang geht bis zum G-Code — über den echten `PrintSettingsDialog` und seinen
Knopf *Slicen*, nicht am Fenster vorbei.

**Drei Slicer statt einem.** Solidon behandelt drei Familien verschieden, und
geprüft war eine: Auf dieser Maschine lag nur der ElegooSlicer. Dazugekommen
sind **PrusaSlicer 2.9.6** und **CuraEngine 5.13.0** (winget, Hersteller-
manifeste). Alle drei werden erkannt und laufen; die Zahlen einer Platte mit
fünf Verbinderstangen:

| | Filament | Druckzeit | Schichten |
|---|---|---|---|
| Solidons Schätzung | 89,7 g | 6,28 h | — |
| PrusaSlicer 2.9.6 | 77,5 g | 7,13 h | 60 |
| ElegooSlicer 1.5.3.4 (Orca) | 76,4 g | 3,92 h | 60 |
| CuraEngine 5.13.0 | 70,0 g | 4,54 h | 60 |

Die Schätzung liegt 16 bis 28 Prozent über den Messungen, und die drei Slicer
sind sich untereinander beim **Faktor 1,8** in der Zeit uneins. Beides steht mit
ausgewiesener Herkunft im Prüfbericht (`info:gcode.material`,
`info:gcode.print_time`, Regel 14) — die Abweichung wird gemeldet, nicht
verrechnet. Curas Kopfzeile schreibt Platzhalter (`;TIME:6666`,
`;Filament used: 0m`, Hüllquader auf INT_MAX); `grams()` fängt das ab und
rechnet aus der geförderten Länge, das Fenster zeigt 70,0 g. Der Fall stand
schon im Docstring.

### Behoben, jeder mit Test und Gegenprobe

- [x] **Eine geratene Form setzte eine Einstellung.** Der Vorschlag *Wände*
      rechnet aus dem dicksten Verbinder, wie viele Wände sich in seiner Mitte
      treffen. `_connector_diameters` nahm dafür **jedes** Merkmal der Art
      `pin` — auch die, die die Merkmalserkennung am eingelesenen Modell geraten
      hatte. Der Docstring sagte seit je „wo er steht, ist das **erzeugte**
      Merkmal"; der Filter sagte es nicht. Gemessen: am Sockel ein Vorschlag von
      **376 Wänden**, an der Ente **185 784**, am Propellersatz 84 — und
      *Vorschläge übernehmen* schrieb sie ins Projekt. Die Schätzung des Sockels
      fiel nach dem Fix von 291 g auf 163,5 g, weil die 376 Wände nicht mehr
      mitgerechnet werden.
- [x] **Ein Merkmal, das nicht in seinen Körper passt, ist keines.** Die
      Zapfenerkennung passt Zylinder in nach außen gewölbte Flächen — und ein
      sanft gebogener Arm *ist* örtlich ein Zylinder mit großem Radius, mit
      kleinem Rückstand. Am Sockel von 160 auf 231 auf 14 mm kamen so zehn
      Zapfen heraus, der dickste mit **Ø 631,6 mm**. Über sieben Modelle waren es
      21 von 112 Zapfen und 19 von 165 Bohrungen, die breiter waren als ihr
      eigener Körper. `_fits_in_the_body` misst jetzt **quer zur eigenen Achse**
      und nicht an der dünnsten Kante — die erste Regel hätte 92 von 165
      Bohrungen verworfen, die meisten davon zu Recht vorhanden: ein Loch Ø 7,1
      durch eine 6,4 mm dünne Scheibe ist normal, dort liegt die dünne Richtung
      in der Achse. Kein Grenzwert, ein Widerspruch. Die echten Sechskantzapfen
      Ø 8,1468 der Querstangen bleiben unverändert erhalten.

### Was der Durchgang bestätigt hat

Die Schichtanalyse liefert je Körper Schichtzahl, Stützvolumen, Überhang
(gesamt und schlimmste Schicht), dünnste Struktur, Inselhöhen und weiteste
Brücke — bei 52 Körpern in Sekunden. Die Vorschlagsliste ist wirklich
teilspezifisch: Der Sockel bekommt die vier Passungsregeln, **weil das
verstiftete Teilen eine Passung angelegt hat**; die ausgehöhlte Ente bekommt
Baumstützen und eine längere Mindestschichtzeit; die Querstange den Verbinder-
vorschlag mit 3 → 5 Wänden. `warning:slice.long_bridge` und
`warning:arrange.adhesion_too_close` kamen dort, wo sie hingehören.

### Zwei Fehler im Prüflauf, die wie Fehler der Anwendung aussahen

Beide festgehalten, weil sie beim nächsten Mal wieder so aussehen werden.
**Erstens** brach der Lauf die Slicer ab, indem er zu früh weiterging: Der
Zustandstext wechselt sofort auf „Der Slicer rechnet …", und wer darauf wartet,
ist nach einem Wimpernschlag fertig. Im Bericht stand PrusaSlicer
„Abgebrochen." und Orca „Der Slicer rechnet …", und allein der letzte lief
durch. Das verlässliche Zeichen ist der Arbeiter (`_worker`).
**Zweitens** setzte der Lauf den Slicerpfad im offenen Dialog um — kein
Kundenweg, der wird im Konstruktor einmal gesucht. Die Profilauswahl der
Orca-Familie blieb dabei stehen, und CuraEngine bekam `-j <Orca-Profil>` und
starb in 0,1 Sekunden. Daraus wurde „Der Slicer hat keine Druckdatei
geschrieben" — ein Satz über das Ende, nicht über die Ursache.

### Was auffiel und eine Entscheidung braucht

- [x] **Der Slicer sagt, was er nicht konnte, und der Nutzer erfährt es nicht.**
      Eine Platte in Bettkoordinaten (so kommt sie aus einer fremden 3MF) an
      PrusaSlicer gegeben endet in `exit_code=0` und der Ausgabe „All objects
      are outside of the print volume." Solidon fängt sie auf und legt sie unter
      `values["output"]` ab, die Meldung lautet aber „Der Slicer hat keine
      Druckdatei geschrieben." Was hilft, ist ein Klick auf *Auf dem Bett
      anordnen* — und das steht nirgends. Regel 17 verlangt den
      Handlungsvorschlag; wo er hingehört (erkannte Slicer-Ausgaben auf
      Handlungen abbilden, wie `FINDING_ACTIONS` es für Befunde tut), ist eine
      Entscheidung. **Entschieden und behoben** im Abschnitt „Der Slicer
      sagte es, und der Nutzer erfuhr es nicht".
- [x] **Die Profilauswahl bleibt beim Slicerwechsel stehen.** `_start_profile_
      search` steigt für Prusa und Cura früh aus und lässt die Auswahlfelder,
      wie sie waren; `_slice` liest sie unbesehen. **Und erreichbar war es
      schon:** `recheck_slicer` sucht im offenen Dialog neu — genau der Weg,
      den jemand geht, der einen zweiten Slicer gerade installiert hat.
      Behoben im Abschnitt „Was CuraEngine schreibt, ohne es zu prüfen".

## Der Slicer sagte es, und der Nutzer erfuhr es nicht (21.08.2026)

Der offene Punkt vom Eintrag darüber, entschieden und behoben — und die
Entscheidung kam aus einer Messung: dieselbe Szene, drei Slicer.

Eine Platte in Bettkoordinaten, so wie sie aus einer fremden 3MF kommt (der
Sockel liegt dort bei 48 bis 208 mm, Solidon rechnet um die Mitte):

| Familie | Ergebnis | Ausgabe |
|---|---|---|
| PrusaSlicer 2.9.6 | keine Datei, Rückgabewert 0 | `All objects are outside of the print volume.` |
| ElegooSlicer (Orca) | keine Datei | `Slic3r::CLI::run found error, exit` |
| CuraEngine 5.13.0 | **schreibt eine Datei, die daneben druckt** | nichts |

Behoben ist der eine Fall, der sich belegen lässt: PrusaSlicers Satz wird
erkannt, und daraus wird „Der Slicer sagt, die Teile liegen außerhalb seines
Bauraums." mit *Auf dem Bett anordnen* als erster Handlung — das ist der Klick,
der es behebt. Vorher stand dort „Der Slicer hat keine Druckdatei geschrieben",
ein Satz über das Ende, dazu drei Handlungen, von denen keine hilft (Regel 17).

Die anderen zwei bleiben mit Begründung draußen. Die Orca-Familie verschluckt
die Ursache — denselben Satz meldet ihr CLI auch bei einem fehlenden
Maschinenprofil, er taugt nicht zur Unterscheidung. Und CuraEngine prüft den
Bauraum überhaupt nicht; dagegen steht `arrange.out_of_build_volume` im
Prüfbericht, und den hat Solidon in derselben Szene dreimal gemeldet. Aus
geratenen Sätzen eine Handlung zu bauen wäre schlimmer als keine.

- [x] **Nachgetragen:** Dass CuraEngine eine Datei schreibt, die neben der
      Platte druckt, meldet Solidon als `info` und nicht als Warnung — der
      Schweregrad folgt der Regel „ein Klick behebt es, also ist es ein
      Hinweis". Vor einem Slicerlauf ist das zu leise; der Nutzer schickt die
      Datei an den Drucker. Ob der Schweregrad an der Stelle vom Anlass abhängen
      soll, war eine Entscheidung über `_severity_for` — sie ist gefallen, und
      dazu kam eine Messung an der geschriebenen Datei selbst. Der Abschnitt
      darunter.

## Was CuraEngine schreibt, ohne es zu prüfen (21.08.2026)

Drei offene Punkte aus den zwei Abschnitten davor, alle drei am selben Ort: die
Übergabe an den Slicer. Gemessen, nicht wiederholt — ein Würfel von 40 × 40 ×
20 mm, 150 mm neben der Mitte, auf einem Bett von 220 mm. Erlaubt ist damit
x −110 bis 110, und derselbe Auftrag ging an alle drei Familien:

| Familie | Ergebnis | gedruckt wird |
|---|---|---|
| PrusaSlicer 2.9.6 | Datei | x −23,6 bis 23,6 — **er rückt selbst in die Mitte** |
| ElegooSlicer (Orca) | keine Datei | — |
| CuraEngine 5.13.0 | Datei | **x 130,2 bis 169,8** |

CuraEngine prüft seinen Bauraum nicht. Im Kopf der Datei steht dazu
`;MINX:2.14748e+06`, der unbesetzte Anfangswert eines Ganzzahltyps — also
nichts. Wer diese Datei an den Drucker schickt, fährt mit der Düse in den
Rahmen.

**Behoben in drei Schritten, jeder mit Test und Gegenprobe.**

- [x] **Vor dem Schreiben ist derselbe Befund keine Auskunft mehr, sondern eine
      Warnung.** `check_build_volume` stufte „steht über den Bauraum hinaus" als
      `info` ein, und mit gutem Grund: ein Klick auf *Auf dem Bett anordnen*
      behebt es, und §29 sagt „ein Bericht, keine Sperre". Beim **Schreiben**
      kippt die Rechnung — danach gibt es keinen Klick mehr, nur noch eine
      Datei. `_severity_for(bounds, allowed, about_to_write)` unterscheidet die
      zwei Anlässe, `export/writer.py` ist der eine, der `True` übergibt.
      Gesperrt wird weiterhin nichts.
- [x] **Und die geschriebene Datei wird selbst gemessen.**
      `gcode.printed_extent` liest, wohin die Bahnen wirklich fahren — die
      Stelle über alle Bewegungen nachgeführt, gezählt nur, wo die E-Achse
      fördert. Aus dem Kopf wäre es nicht zu erfahren; die Bogenformen `G2`/`G3`
      zählen mit, weil eine Kreiswand mit Bogenanpassung **nur** aus ihnen
      besteht. `handover.off_the_bed` beurteilt das Maß gegen den Bauraum, und
      zwar in den Koordinaten, in denen dieser Slicer schreibt: Cura und
      PrusaSlicer bekommen von Solidon eine Maschine um den Ursprung, die
      Orca-Familie lädt ihr eigenes Profil und misst von der Ecke. Beides zu
      verwechseln kostete einen falschen Befund bei jedem Lauf. Unter einer
      Bahnbreite wird nichts gemeldet. Was herauskommt, ist
      `error:gcode.off_the_bed` mit `source="gcode"` — gemessen, nie mit der
      Schätzung vermischt (Regel 14).
- [x] **Die Profilauswahl wird geleert, bevor eine neue Suche etwas
      hineinschreibt.** `_start_profile_search` kehrt für `prusa` und `cura`
      früh zurück; wer im offenen Dialog von der Orca-Familie auf CuraEngine
      wechselt, hatte danach drei gefüllte Auswahlfelder mit Orca-Profilen vor
      sich, `_slice` las sie unbesehen, und der Slicer bekam ein `-j` auf eine
      Orca-Datei. Der Eintrag von vorhin nannte das „heute unerreichbar" — das
      war falsch: `recheck_slicer` ist genau dieser Weg, und er steht am Ende
      des Einrichtungsdialogs. Geleert wird am **Anfang** der Suche, damit es
      auch für die Wege gilt, die vorzeitig zurückkehren. Dazu die Kehrseite:
      `_remember_slicer_choice` merkt nichts, wo es nichts zu wählen gibt —
      sonst löschte ein Cura-Lauf das Profil, das zum nächsten Orca-Lauf gehört.
- [x] **Und die Suite fand einen vierten, aus dem Durchgang von heute Mittag.**
      „Die Rasttasche trug nichts ab" (d75d9a5) schob den ganzen Taschenkörper
      um seine Tiefe nach unten — richtig für die Passbohrung, die bis auf ihre
      Fase drehsymmetrisch ist, und **halb** richtig für den Schnapper: Die
      Kerbe, die die Rastkante im Bauteil stehen lässt, wanderte mit ans tiefe
      Ende der Tasche. Dort findet der Haken nichts, was ihn hält; der Verbinder
      ging zusammen und genauso wieder auseinander. Gebaut wird jetzt von der
      Mündung nach unten, Schlitz und Kante einzeln gesetzt, `parts_version` auf
      4 mit Änderungsverlauf (§24.4).

      **Der Test war der Fund, und dann fast der zweite.** Er vergleicht Arm und
      Tasche als Volumen, und beide Körper liegen seit d75d9a5 in
      gegenläufigen Rahmen — er verglich zwei Dinge, die sich nicht treffen, und
      wurde rot. Die halbe Drehung um Y stellt das her, was beim Zusammenstecken
      wirklich passiert. Damit war er grün — **und mit der Kante am falschen
      Ende ebenfalls:** Der Haken greift dort genauso, und der ausgewichene Arm
      geht genauso vorbei. Beide Prüfungen sind blind gegen die Richtung.
      Dazugekommen ist deshalb die Aussage, um die es eigentlich geht: die Kerbe
      im Schlitz endet an der Mündung. Mit der Kante am tiefen Ende ist sie rot,
      und das ist gemessen, nicht angenommen.

### Ein Fehler im Bauen, der hier hingehört

Der erste Anlauf von `printed_extent` fand in einer Datei mit 37 154
Materialbahnen **keine einzige**. Der Grund lag nicht im Programm: In der
Achsensuche stand statt der zwei Zeichen `\b` ein einzelnes Byte 0x08 — ein
echter Rückschritt-Steuerzeichen, hineingeschrieben von einem Hilfsskript, das
seine Backslashes einmal zu oft aufgelöst hatte. In einem `r"..."`-Muster ist
das kein Wortanfang, sondern ein Zeichen, das in keiner Datei vorkommt. Sichtbar
war es nicht: weder `ruff` noch `mypy` noch die Anzeige der Datei zeigen den
Unterschied. Gefunden hat es die Messung an der echten Datei — der Grund, warum
sie hier immer gegen einen echten Slicer läuft und nicht gegen eine Attrappe.

## Dieselbe Zusatzsoftware, einen Schritt weiter gedacht (21.08.2026)

Der erste Durchgang hat das Installieren gebaut. Der zweite hat gefragt, was
danach passiert — und dort lagen die schwereren Funde.

### Installiert war es, gefunden nicht

- [x] **Nach einer Flatpak-Installation war das Programm für Solidon nicht
      vorhanden.** Flatpak legt die Startprogramme unter der
      Anwendungskennung ab (`org.openscad.OpenSCAD`) und setzt den PATH
      ausdrücklich nicht — „we're not automatically overriding PATH" steht so
      in ihrer Begründung. Weder `shutil.which("openscad")` noch der Durchgang
      durch `/opt` und `/usr/local` findet das. Der Knopf hätte also
      installiert, und die Zeile daneben hätte weiter „nicht gefunden" gesagt.
      `discover._from_flatpak` sieht in beiden Exportverzeichnissen nach, und
      verglichen wird über `plain_name`: „orca-slicer", „OrcaSlicer" und das
      letzte Stück von „com.orcaslicer.OrcaSlicer" sind derselbe Name. Das
      trägt auch für Anwendungen, die niemand hier eingetragen hat — ein selbst
      installiertes `com.prusa3d.PrusaSlicer` wird gefunden.
- [x] **Dasselbe auf macOS, aus einem anderen Grund.** Ein Homebrew-Cask legt
      `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD` ab; gesucht wurde
      direkt im Ordner und in `bin`. `parts_for()` kennt den Bündelpfad — als
      Funktion und nicht als Zeile mit `if sys.platform`, damit die Zuordnung
      von **jeder** Maschine aus prüfbar ist. Ein Test, der die Mac-Pfade nur
      auf einem Mac sehen kann, prüft sie nirgends.
- [x] **Und ein Flatpak hätte die Datei nicht lesen können, die es bearbeiten
      soll.** Es hat sein eigenes `/tmp`, und dorthin legt `tempfile` unter
      Linux: Der Aufruf käme an, das Programm startete, und es fände nichts —
      „Can't open input file", unmittelbar nach einer Installation über einen
      Knopf. Nachgesehen in den Flathub-Manifesten von OpenSCAD und OrcaSlicer:
      beide geben `--filesystem=home` frei und kein Verzeichnis, in dem wir
      sonst schreiben. `discover.workspace_for` legt den Arbeitsordner für
      eingesperrte Programme in den Nutzer-Cache; für jedes andere bleibt es
      beim Systemtemp, der zuverlässig aufgeräumt wird.

### Drei Dialoge warteten beim Öffnen

Derselbe Fehler wie beim Installationsdialog, an drei weiteren Stellen —
gemessen, offscreen:

| Dialog | vorher | nachher |
|---|---|---|
| Erstinbetriebnahme | 1,88 s | sofort |
| Chat einrichten | 2,98 s | 0,095 s |
| Liste der Programme (erster Durchgang) | 2,97 s | 0,012 s |

- [x] **Die Erstinbetriebnahme ist das Allererste, was ein Kunde sieht.** Vier
      Dinge liefen dafür im Oberflächen-Thread: die Suche nach vier Programmen,
      das Auslesen eines Slicer-Profils, die HTTP-Frage an Ollama und die
      Prüfung der optionalen Pakete. Sie sieht jetzt in einem Arbeiter nach.
      Der Druckervorschlag aus dem Slicer-Profil kommt nachgereicht und
      überschreibt keine getroffene Wahl — eine Vorgabe, die das täte, wäre
      keine (§2.4).
- [x] **Der Chat-Dialog kostete 2,98 Sekunden, davon 2,07 allein die Frage nach
      den installierten Ollama-Modellen.** Das war ein Einbau aus dem ersten
      Durchgang: die Modellauswahl, die dem Kunden die Namen nennt, statt sie
      ihn tippen zu lassen. Gut gemeint und an der falschen Stelle gerechnet.

### Ein Absturz, der älter ist als diese Arbeit

- [x] **Die Halteleine hielt einen Arbeiter erst, wenn er fertig war.** Solange
      er lief, hing er allein am Feld seines Dialogs — und ein Dialog, der
      vorher freigegeben wird, nimmt damit die letzte Referenz auf einen
      laufenden `QThread` mit. Der Speicherbereiniger zerstört das C++-Objekt
      darunter, und der Abriss kommt später und ohne Zeile: genau die Sorte,
      gegen die es `app/ui/leash.py` überhaupt gibt.

      Sichtbar wurde es, als die Erstinbetriebnahme ihre Erhebung bekam —
      `tests/test_first_run.py` brach reproduzierbar an der Stelle ab, an der
      ein Dialog aus einem vorigen Test einging. `WorkerLeash.start` hält ab
      dem ersten Moment, die Menge ist **modulweit**, und der Zeitgeber hängt
      an einem Objekt, das die Widgets überlebt. Betroffen war auch die
      Werkzeugprobe des Chat-Dialogs, die es seit je gibt.

      Nicht zu verwechseln mit dem offenen Punkt „Der Absturz in einer
      einzelnen Datei": Der bleibt und hat eine andere Ursache — `test_ui.py`,
      `test_analysis_ui.py` und `test_way_three.py` in **einem** Lauf stürzen
      weiterhin ab, einzeln sind alle drei grün, und das war vor dieser Arbeit
      genauso.

### Drei Wege, die ins Leere liefen

- [x] **„Bereit" stand da, sobald ein Port antwortete.** Wer ComfyUI
      installiert und gestartet hatte, ohne die Knoten einzurichten, tippte
      seinen Satz, drückte *Erzeugen*, wartete — und erfuhr es danach. Die
      Auskunft war die ganze Zeit einen HTTP-Aufruf entfernt.
      `ComfyBackend.readiness` unterscheidet vier Lagen, der Dialog nennt drei
      beim Namen, und wo die Knoten fehlen, führt der Knopf direkt in die
      Einrichtung statt in eine Liste. Gefragt wird nach dem Knoten, den der
      mitgelieferte Ablauf wirklich benutzt (`_own_node`) — wer ihn austauscht,
      tauscht damit auch, was geprüft wird (§27). `UNKNOWN` sperrt nichts: Auf
      dem Port kann alles liegen, und ein gesperrter Knopf wäre eine Behauptung
      darüber.
- [x] **Neun Gigabyte, und beim Abbrechen wären sie verfallen.** Der
      Chat-Dialog heißt „Chat einrichten" und hat *Speichern* und *Abbrechen*.
      Wer Ollama startete, ein Modell holte und dann abbrach — weil er gar
      keinen Schlüssel eintragen wollte —, hatte alles richtig gemacht und
      einen Chat, der weiter auf das alte Modell zeigte und grau blieb. Ein
      geholtes Modell gilt jetzt sofort; das Herunterladen ist eine Tatsache,
      nur die Eingabefelder warten auf eine Entscheidung. Und
      `action_llm_key` frischt in **jedem** Fall auf, nicht nur nach
      *Speichern*.
- [x] **„Kein Slicer eingerichtet" bot nichts an** — an der Stelle, an der
      jemand gerade slicen wollte. Der Satz bleibt (§27: das Backend meldet
      sich ab, es nörgelt nicht), der Weg kommt dazu, und
      `recheck_slicer` sieht danach neu nach.

### Was der Test gefunden hat, nicht ich

- [x] Die ComfyUI-Knoten trugen **deutsche Bezeichner** (`rechnen`,
      `schritte`). In `tools/` hatte die Sprachprüfung sie nie gesehen; seit
      sie unter `app/` liegen, sieht sie sie.
- [x] Der Sammelknopf **verschluckte einen Eintrag** der Warteschlange: `done`
      kommt, während der Arbeiter noch läuft, `_start` sah ihn als beschäftigt
      und kehrte um — obwohl der Eintrag schon herausgenommen war. Von vier
      fehlenden Programmen wurden drei installiert, ohne ein Wort dazu.
- [x] Der Einrichtungsdialog sagte **nicht, woran man den Ordner erkennt**.
      „Nicht gefunden — der Ordner gehört hier hinein" schickt jemanden suchen,
      ohne zu sagen, wonach.

## Der Abbrechen-Knopf vor der Zwei-Sekunden-Schwelle — geprüft und geschlossen (21.08.2026)

Gemessen am laufenden Fenster, nicht am Quelltext: Balken und Abbrechen-Knopf
erscheinen bei jeder Auswertung sofort, nicht gestaffelt.

| Operation | Rechnung | Balken ab | Abbrechen ab |
|---|---|---|---|
| Grundkörper | 409 ms | 216 ms | 216 ms |
| Bohrung | 856 ms | 493 ms | 493 ms |
| Verschieben | 417 ms | 67 ms | 67 ms |
| Drehen | 467 ms | 112 ms | 112 ms |

§2.8 staffelt: „Bis 2 s: Mauszeiger und Statusleiste. Darüber: Fortschritt in
der Statusleiste mit **Abbrechen**." Wörtlich gelesen erscheint der Knopf
viermal zu früh. **Trotzdem wird hier nichts geändert**, und die Begründung
gehört aufgeschrieben, damit die Messung nicht in einem Jahr als Fund
wiederkehrt:

- **Der Knopf hängt an fünf Stellen**, und sie meinen nicht dasselbe.
  `_on_busy` ist die kurze Auswertung; die beiden Stellen um 4446 und 4474
  gehören Chat und Trennebenensuche, und die laufen immer über zwei Sekunden.
  Dort muss der Knopf sofort dastehen. Eine Staffel bräuchte also drei
  verschiedene Regeln in einer Anzeige.
- **Der Nutzen ist die Ruhe, der Preis die Abbrechbarkeit.** Ein Lauf von 1,9 s
  wäre nach der Regel nicht abbrechbar. Dass man in 1,9 s kaum trifft, ist ein
  Argument dafür — aber keines, das die drei Regeln aufwiegt.
- **Das eigentliche Flackern ist schon behoben.** „Der Balken verschwand,
  während die Anwendung noch vier Sekunden rechnete" (b110744) hat den Fall
  erledigt, der wehtat: Beim Ziehen an einem Schieber bleibt die Anzeige
  stehen, statt bei jedem Zwischenschritt an- und auszugehen. Was bleibt, ist
  ein einzelnes Aufblitzen bei einer einzelnen kurzen Operation.

Bleibt als Beobachtung: Die 0,2-Sekunden-Grenze ist **nicht** widerlegt und
nicht bestätigt — keine der vier gemessenen Rechnungen war kürzer als 200 ms.
`LoadingVeil` hält sie mit `DELAY_MS = 200` ein und begründet es dort wörtlich
mit §2.8; für Balken und Knopf fehlt der Beweis in beide Richtungen.

## Der dritte Durchgang: was hinter dem Wartezustand lag (21.08.2026)

Zwei Durchgänge hatten die Zusatzsoftware von „fehlt" bis „läuft" gebracht. Der
dritte fragte, was passiert, wenn dabei etwas schiefgeht — und der Fund reicht
weit über das Thema hinaus.

### Zweiundzwanzig Arbeiter konnten ihr Fenster stillstellen

- [x] **Ein `run`, das eine Ausnahme durchlässt, sendet sein Ergebnissignal
      nie.** Nachgestellt am Einrichtungsdialog für ComfyUI: Liegt die
      Installation unter `Program Files`, wirft das Kopieren der Knoten einen
      `PermissionError`. Der Dialog fing `SetupFailed` und sonst nichts — die
      Ausnahme landete auf stderr, wo sie kein Kunde sieht, und im Fenster
      stand „Wird eingerichtet …", der Balken lief, der Knopf sagte
      „Abbrechen". Dabei blieb es, bis jemand das Programm beendet.

      Gezählt: Von **dreiundzwanzig** Arbeitern in der Oberfläche fing genau
      **einer** eine unerwartete Ausnahme — der Versand der Rückmeldung. Die
      anderen zweiundzwanzig konnten dasselbe anrichten: die Ladeanzeige der
      Auswertung, die für immer stehen bleibt; der Export-Menüeintrag, der für
      den Rest der Sitzung gesperrt ist; „Der Profilbestand wird durchgesehen
      …" als Dauerzustand.

      `leash.Worker` fängt, protokolliert und meldet über `crashed`. Erwartete
      Fehler bleiben in `work` und kommen als Ergebnis zurück; was bei
      `crashed` ankommt, ist ausdrücklich das Unerwartete. Wo ein Fehlerpfad
      existiert, geht es denselben Weg als `InternalError` — §33.1 ordnet ihm
      den Fehlerbericht zu.

      **Zwei Tests halten es**, und der zweite ist der wichtigere: dass kein
      Arbeiter mehr direkt von `QThread` erbt, und dass jede Datei, die einen
      baut, auf `crashed` hört. Die Basisklasse allein hätte den Fund nur
      verschoben.
- [x] Dabei kam heraus, dass der Installationsdialog nach einem Absturz **neu
      erhob** — und seine eigene Meldung eine Sekunde später mit der
      Zusammenfassung überschrieb. Der Kunde hatte den Satz gesehen und nicht
      gelesen.

### Der Installer meldete erst am Ende, was er tut

- [x] **`subprocess.run` sammelt die Ausgabe und gibt sie am Ende zurück.** Die
      Fortschrittszeilen wurden also erst durchgereicht, wenn niemand sie mehr
      brauchte: Bei OrcaSlicer sind das mehrere Minuten, in denen ein
      unbestimmter Balken lief und sonst nichts geschah.

      Gelesen wird jetzt zeilenweise, und der **Textmodus ist der Trick**:
      winget zeichnet seinen Balken mit Wagenrücklauf und ohne Zeilenumbruch,
      und erst die Übersetzung von `\r` in ein Zeilenende macht daraus Zeilen,
      die ankommen. Ohne sie käme bis zum Schluss keine.
- [x] **Was der Kunde davon sieht, ist die Zeit** — nicht die rohe Ausgabe, die
      weiter hinter „Details" gehört: „Wird installiert: OrcaSlicer (45 s)".
      Dasselbe im Einrichtungsdialog, wo die Zeit **je Schritt** neu beginnt,
      denn nur einer von fünf lädt 7,5 GB. Dasselbe Muster wie beim Erzeugen
      eines Modells (`mesh.py`).

### Und „Abbrechen" wirkte bei genau diesem Schritt nicht

- [x] Die Abbruchprüfung lag **zwischen** den Schritten, und `subprocess.run`
      blockiert bis zum Ende: Wer während des Downloads der Gewichte abbrach,
      wartete eine halbe Stunde auf etwas, das er nicht mehr wollte. Der Satz
      daneben — „der laufende Schritt läuft aus" — war wahr und keine Hilfe.
      Gefragt wird jetzt zwischen den Zeilen, und ein Abbruch beendet den
      Kindprozess. Was halb geladen ist, bleibt liegen: `huggingface_hub` setzt
      beim nächsten Lauf fort, die Knoten sind idempotent kopiert.

### Was beim Messen aufgefallen ist, und keine Regression war

- [x] **Die dreizehn roten Leistungstests waren ein Artefakt der Bestwerte.**
      `tests/.performance.json` liegt **je Arbeitsbaum** und wird bei jedem Lauf
      auf das Minimum gesenkt. Ein frischer Worktree hat keine Werte und ist
      deshalb grün; der gewachsene Hauptbaum vergleicht gegen Bestzeiten aus
      Läufen ohne Last. Gegengeprüft: dieselbe Bestwert-Datei in einen Worktree
      auf dem Stand *vor* dieser Arbeit kopiert und gemessen — **identisch
      dreizehn rot**. Wer die Datei zum Vergleich benutzt, kopiert sie mit.
- [x] **Der Wettlauf war kein Testproblem, sondern ein Kundenfehler.** Der Test
      war einmal rot in einem Lauf über 66 Dateien, sonst grün — und die Suche
      nach dem Grund führte an eine Stelle, die einen echten Schaden anrichtet:
      `_profiles_found` baut die Auswahl neu und setzt sie auf die gemerkte oder
      die zugeordnete Maschine. Wer in der Zwischenzeit **selbst** gewählt hat,
      sah seine Wahl auf etwas anderes springen — und beim Schließen wurde die
      neue gemerkt, nicht seine.

      Sichtbar wurde das erst mit `recheck_slicer`: Beim ersten Öffnen ist die
      Auswahl leer, danach nicht mehr. Eine getroffene Wahl bleibt jetzt stehen
      — dieselbe Regel wie beim Druckervorschlag der Erstinbetriebnahme, eine
      Vorgabe, die eine Wahl überschreibt, ist keine mehr (§2.4).

      Zwei Fallen lagen dabei im Weg, und beide sind im Test festgehalten. Die
      Auswahl muss **vor** dem Füllen gelesen werden: Nach dem ersten `addItem`
      steht der Index auf 0, und „was gewählt ist" wäre Qts Vorbelegung. Und
      der Test braucht **zwei** Profile — bei genau einem fällt
      `_profiles_found` auf Index 0 zurück, und der wäre zufällig der eigene
      Eintrag.

## Zwölf ein halb wurden hundertfünfundzwanzig (21.08.2026, vierter Durchgang)

Diesmal die Zahlen selbst — hinein und hinaus —, die Beschriftungen der
Operationsdialoge, und ein Reihe Winkel, die nichts ergaben und deshalb hier
mit ihrem Messwert stehen: Was gesund ist, soll man beim nächsten Durchgang
nicht zweimal messen.

### Behoben, jeder mit Test und Gegenprobe

- [x] **„12.5" ergab 125 Millimeter.** Ohne Fehler, ohne Rückfrage, ein Teil
      zehnmal zu groß. Qt liest den Punkt in einer deutschen Anzeigesprache als
      Tausendertrennung, und neun Zahlenfelder der Oberfläche waren gewöhnliche
      `QDoubleSpinBox`. Im englischen Fenster dasselbe mit dem Komma. Wer ein
      Maß aus einem Datenblatt, einer Fundstelle im Netz oder der eigenen
      Gewohnheit eintippt, trägt das Trennzeichen von dort — und die Anwendung
      sagte dazu nichts. Jetzt gibt es `NumberSpin`, und die Leseregel ist ein
      Satz: **das letzte Trennzeichen ist das Dezimaltrennzeichen, alle davor
      sind Tausendertrennungen.** Damit lesen alle Felder „12.5", „12,5",
      „1.000,50", „1,000.50" und „1.234.567,89" richtig, in jeder Sprache.
      `DragValueBar.typed_value` im Viewport entschied ähnlich seit je; die
      Regel stand nur an einer Stelle und nicht an den anderen neun. Ein
      Regeltest über `app/ui` hält die Klasse geschlossen.

      **Der erste Anlauf war selbst ein Fehler derselben Sorte** — gefunden in
      der Durchsicht am Abend, nicht von einem Test. Er tauschte jeden Punkt
      gegen ein Komma und gab den getauschten Text an Qt zurück; Qt übernahm ihn
      ins Feld, und damit stand die Absicht nach dem zweiten Tastendruck fest:
      Wer „1.000,50" tippte, sah „1," und verlor die dritte Null an `decimals` —
      heraus kam 100,50. Um den Faktor tausend falsch, sichtbar, aber falsch.
      Jetzt bleibt der getippte Text stehen, geprüft wird gegen beide Lesarten,
      und gelesen wird erst beim Übernehmen. Zweideutig bleibt nur eine Zahl
      ohne Nachkomma („1.000" ist eins), und was das Feld gelesen hat, steht
      danach darin.
- [x] **Dieselbe Zahl in zwei Schreibweisen, in jeder Sprache.** Die
      Gegenrichtung: `localised` gibt es, seit im Objektbaum Maße mit Punkt
      neben einem Feld mit Komma standen — neun weitere Stellen gingen daran
      vorbei. Die Parameterleiste schrieb im deutschen Fenster „12.50 mm"
      direkt neben ein Eingabefeld mit „12,50", der Chat „+1.25 cm³", die
      Kalibrierung „Spiel 0.25 mm", die Sendungsgröße „2.5 MB". Zwei Stellen
      setzten umgekehrt das Komma fest ein (`.replace(".", ",")`) und trafen
      damit in fünf von sechs Sprachen zufällig richtig — im englischen Fenster
      standen „8,4 g" und ein Maßband mit „12,50". Der Regeltest prüft jede
      Datei unter `app/ui` per AST: eine Kommazahl in einem Anzeigetext geht
      durch `localised`. Ausgenommen sind zwei Stellen, die keine Anzeige sind
      — `measured_expression` und `place_measured` füllen das Maßfeld des
      Skizzeneditors mit einem *Ausdruck* der Parametergrammatik (§13), und
      `expressions.evaluate("30,25")` lehnt ab. Das war der Beinahe-Fehler
      dieses Durchgangs: Erst nach dem Lokalisieren fiel der Satz im Docstring
      auf, der genau das erklärt.
- [x] **457 Parameter erklärten sich nur halb.** Jeder trägt seinen
      `doc`-Satz, und der stand allein am Eingabefeld — wer eine Zeile nicht
      versteht, zeigt auf das unverständliche Wort. Gemessen an vier Dialogen:
      47 Zeilen, 47 Sätze am Feld, null an der Beschriftung. Dieselbe Lücke wie
      in den Druckeinstellungen, eine Ebene höher und mit zehnmal so vielen
      Feldern. `_explain` setzt jetzt Tooltip, `statusTip` und
      `accessibleDescription`; die Beschriftung holt
      `QFormLayout.labelForField`. Bei einer **gesperrten** Zeile tragen beide
      Hälften den Grund statt des Satzes: In ein ausgegrautes Feld zeigt
      niemand.
- [x] **Zwei Tests hingen an der Sprache der Maschine.**
      `test_the_summary_names_what_would_change` und
      `test_every_plate_keeps_its_own_print_file` erwarteten „+2.00 cm³" und
      „20.0 g". Auf einem deutschen Windows steht dort jetzt ein Komma, in
      einer englischen CI ein Punkt — grün wären sie nur an einem der beiden
      Orte gewesen. Die Sprache ist jetzt festgenagelt, und der Chat-Test prüft
      beide Schreibweisen.
- [x] **Eine Begründung, die nicht stimmte.** Der Docstring von `_label` in den
      Druckeinstellungen behauptete, an ein von `addRow` gebautes Label käme
      niemand mehr heran. `QFormLayout.labelForField` gibt es heraus — der
      Operationsdialog macht es genau so. Die Wahl für ein eigenes Widget
      bleibt, die Begründung ist jetzt die richtige.

- [x] **Die Fläche blieb in Quadratmillimetern, als alles andere umschaltete.**
      Länge und Volumen folgen der Anzeigeeinheit seit je (`format_length`,
      `format_volume`) — wer in Zoll arbeitete, sah Maße in Zoll, Volumen in
      Kubikzoll und daneben „4334 mm²". Vier Stellen zeigen Flächen, und alle
      vier hatten die Einheit fest eingebaut; eine davon **im übersetzten
      Satz**: „Fläche an {object} — {area} mm², {side}" stand so im Katalog,
      in fünf Sprachen, und ein Satz mit eingebauter Einheit kann nicht in Zoll
      sprechen. Jetzt gibt es `units.format_area` und `labels.area`; die
      Stellen sind die Merkmalsangabe im Objektbaum, die Zeile der
      Schichtanalyse, die Beschriftung des Flächensprungs und der Wert selbst.
      In Millimetern bleibt es bei ganzen Quadratmillimetern, in Zoll wachsen
      die Stellen wie beim Volumen — ein Quadratmillimeter ist ein
      Anderthalbtausendstel Quadratzoll.

### Was auffiel und eine Entscheidung braucht

- [x] **Befundwerte folgten der Anzeigeeinheit nicht.** `value_line` schrieb
      „Übermaß (mm): 12,4" auch dann, wenn die Oberfläche auf Zoll stand: Die
      Einheit kam aus dem Suffix des Schlüssels und stand in der
      **Beschriftung** — dort kann sie nicht umschalten. Damit gab es zwei
      Antworten auf dieselbe Frage: Der Objektbaum zeigte Zoll, der Befund
      daneben Millimeter.

      Entschieden ist es jetzt, und die Entscheidung folgt aus §19.3 statt aus
      einer Abwägung: Wer eine Anzeigeeinheit einstellt, liest sie überall.
      Die Einheit steht am Wert, geschrieben von `length`, `area` und `volume`
      — denselben Funktionen, die der Objektbaum benutzt. Bei einem Volumen
      war die Beschriftung sogar falsch: Der Wert wechselt zwischen mm³ und
      cm³, je nach Größe, und „(mm³)" darüber behauptete etwas anderes.
      Dreißig Schlüssel tragen ein Suffix, und alle dreißig sind Längen,
      Flächen oder Volumen — geprüft, nicht angenommen. Steht dort keine Zahl,
      bleibt die Einheit des Schlüssels stehen; sie ist dann die einzige
      Auskunft, die es gibt.

      **Und eine Berichtigung:** Der Satz „`area_mm2` fehlt in `_VALUE_NAMES`"
      war falsch. Diesen Schlüssel hat keine Operation — er stammt aus meiner
      eigenen Messung. `test_every_value_key_has_a_label` sammelt die
      Schlüssel aus `app/core` und war zu diesem Punkt immer grün.
- [x] **Zwei Löcher im eingecheckten Stand, nicht in halbfertiger Arbeit.**
      „Die Skizze umschließt keine Fläche." stand in HEAD ohne Übersetzung —
      fünf Katalogeinträge. Und `format` fehlte in `_VALUE_NAMES`, weshalb ein
      Export-Befund den rohen Schlüssel zeigte („format: step") statt einer
      Beschriftung; `test_every_value_key_has_a_label` war deswegen am
      eingecheckten Stand rot.

      Beim Nachziehen fiel eine Falle auf, die eine eigene Zeile verdient: Ich
      hatte sechs fehlende Sätze gemessen und alle sechs übersetzt — fünf davon
      hatte die parallele Sitzung in der Zwischenzeit selbst übersetzt, und mein
      Eintrag hätte ihre Version überschrieben. Gegen HEAD neu gemessen war es
      genau einer. In einem geteilten Arbeitsbaum ist eine Messung von vor
      zwanzig Minuten keine Grundlage für einen Commit.

### Gemessen und gesund — nicht nachgesehen werden muss

- **Ausgegraute Menüeinträge:** 72, und alle 72 nennen ihren Grund im Tooltip.
- **Symbolknöpfe ohne Text:** 7, alle mit Namen für Tastatur und Vorleser.
- **Hauptknöpfe:** sagen, was sie tun („Bohrung setzen", nicht „OK").
- **Fokus beim Öffnen:** liegt im ersten Feld — Zahl, Auswahl oder Textfeld.
- **Abgeschnittene Beschriftungen ohne Tooltip:** keine.
- **Kleiner Bildschirm:** der größte Dialog braucht 970×555, passt also auf
  1366×768.
- **Zugriffstasten (`&`) je Menü:** keine Dublette in sechs Sprachen. Dass 160
  Einträge keine führen, ist kein Fund: §19.2 nennt die Befehlspalette als
  Universalzugang, und die hält ihr Versprechen aus §2.6 („alles aus dem
  Register").

## Zwei Tabellen für dieselbe Sache (21.08.2026)

Diesmal die Blickwinkel, die die beiden Durchgänge davor nicht hatten: die
langen Läufe an der Uhr, die Tastatur ohne Maus, der Erststart mit leerem
Profil — und der größte Dialog der Anwendung, den bis dahin keine Durchsicht
angesehen hatte.

**Was dabei hielt.** Die Orientierungssuche macht es vorbildlich: Balken und
Abbrechen nach 0,06 s, Prozent von Anfang an, ab acht Prozent eine
Restzeitschätzung („noch etwa 5 min"), Oberfläche bedienbar, und nach dem
Abbruch ein Satz, der sagt, was man vor sich hat. Die Analysekarte lehnt ein
Modell mit 1,3 Millionen Dreiecken mit einem klaren Satz ab statt still zu
scheitern. Die Fokuskette führt in vierundzwanzig Schritten durch alle Zonen,
jede Station benannt. Der Erststart fragt drei Dinge und lässt sich
überspringen, der Startbildschirm nennt alle vier Wege, neun Beispielprojekte
liegen bei, die Tour zählt „Schritt 1 / 4". Und der Verlauf kodiert einen
zurückgenommenen Schritt dreifach — Wort, Durchstreichung, Farbe (Regel 18).

### Behoben, jeder mit Test und Gegenprobe

- [x] **Sechzehn englische Schlüssel im deutschen Fenster** — und die Ursache
      war eine zweite Namenstabelle. Die Druckeinstellungen führten ihre eigene
      `CHOICE_LABELS` mit einer gleichnamigen `choice_label`-Funktion davor: Die
      eine verdeckte die andere, beide beschrifteten dieselben Schlüssel, und
      sie waren schon auseinandergelaufen — `cubic` hieß dort „Würfel" und in
      `labels` „Würfelgitter", `none` dort „Keine" und hier „Ohne". Zwei Werte
      hatte **keine** von beiden: Im Feld *Wandbahnen* stand „classic" und
      „arachne", englische Algorithmusnamen in einer deutschen Auswahl. Jetzt
      gibt es eine Tabelle (Leitprinzip 3), und die beiden Drifts sind
      entschieden. `skirt`, `brim` und `raft` bleiben englisch: Die Felder
      daneben heißen „Skirt-Runden", „Brim-Breite", „Raft-Schichten", und ein
      Wert, der anders heißt als sein Feld, ist eine Fährte ins Nichts.
- [x] **Die Prüfung sah nur die eine Hälfte.**
      `test_translations.py` hält Regel 20 für Auswahlwerte am
      Operationsregister — die sechsundfünfzig Felder der Druckeinstellungen
      sind eine eigene Liste und liefen daran vorbei. Genau dort saßen die
      sechzehn. Geprüft werden jetzt beide Quellen gegen dieselbe Tabelle, und
      sechs verwaiste Katalogeinträge sind mit dem Pflegewerkzeug gefallen.
- [x] **Kein Feld der Druckeinstellungen erklärte sich.** Sechsundfünfzig
      Felder, keines mit Tooltip — während jeder der 136 Menüeinträge einen
      Satz trägt und jeder Operationsparameter seinen `doc`-Satz. Die Frage
      war nicht *ob*, sondern *wie weit*, und ein Dialog, in dem fünfzehn von
      sechsundfünfzig Feldern einen Tooltip haben, lehrt niemanden, dass es
      Tooltips gibt (Konsistenz vor Vollständigkeit). Also alle
      sechsundfünfzig. Der Satz wiederholt nicht den Titel, sondern sagt, was
      passiert, wenn man den Wert bewegt: „Rechnet die Außenwand auf ihr
      Sollmaß statt auf die Bahnmitte. Für Passungen richtig, sonst unnötig."
      Er hängt an **beiden** Hälften der Zeile — am Eingabefeld und an der
      Beschriftung, denn wer eine Zeile nicht versteht, zeigt auf das
      unverständliche Wort und nicht auf den Kasten daneben — und dazu als
      `statusTip` und `accessibleDescription`. 336 Texte: 56 deutsche Quellen
      und 280 Katalogeinträge. Das Vokabular kommt aus den Feldtiteln, die es
      schon gab (Bahn → line / cordón / ligne / cordone / linha); Slicer,
      Brim, Skirt und Raft bleiben überall stehen, wie die Feldnamen daneben.
      Der Farbknopf ist der eine Sonderfall: Sein Tooltip nennt zuerst den
      Hexwert, den sonst nichts zeigt, und hängt den Satz dahinter.
- [x] **Ein Test lief nur, wenn vorher ein anderer gelaufen war.**
      `test_the_colour_button_says_which_colour_it_is` baute ein Widget ohne
      `QApplication`. Allein aufgerufen bringt das den ganzen Lauf mit
      0xC0000409 um — kein Wort Ausgabe, nur ein Rückgabewert; in der vollen
      Datei hatte ein früherer Test die Anwendung schon gebaut, und welcher
      der beiden Fälle eintritt, entscheidet `pytest-randomly`. Gefunden beim
      Gegenprobieren des Tooltip-Tests, der dasselbe Muster geerbt hatte.
- [x] **Zwei Körper gewählt, ein Loch — und kein Wort dazu, in welchem.** Eine
      Operation nimmt so viele Körper, wie sie deklariert, und zwar in
      Klickreihenfolge (`inputs_for`). Bei zwei gewählten Würfeln und *Bohrung
      setzen* bekam einer ein Loch und der andere nicht; im Dialog stand nichts
      davon, und der Fenstertitel ist beim Klicken nicht im Blick — das sagt
      der Kommentar am OK-Knopf selbst. Das war kein Raten (Regel 21), die
      Regel stand nur nirgends, wo sie jemand liest. Jetzt trägt der Dialog
      eine Zeile: „Angewendet wird auf cube_clean — der zuerst gewählte von 2."
      Sichtbar nur, wenn mehr gewählt ist als die Operation nimmt; der
      Normalfall braucht keine Erklärung.

### Was auffiel und eine Entscheidung braucht

## Der Kundendurchgang durch die vier Wege (21.08.2026)

Nach dem Bildweg die anderen drei, und zwar mit denselben Aufrufen, die die
Menüs machen: die neun Beispielprojekte geöffnet und gerechnet, Weg 2 von Hand
gefahren, Weg 4 von Hand gefahren, die zehn alten Projektdateien geöffnet und
im Rundlauf verglichen, und die Kommandozeile von außen bedient. Vier Funde,
und drei Verdachtsfälle, die sich als richtig gebaut erwiesen haben — die stehen
mit dabei, weil eine Durchsicht, die nur die Treffer aufschreibt, beim nächsten
Mal denselben Weg zweimal geht.

### Was gut lief

Die neun Beispielprojekte öffnen alle, rechnen alle, halten nirgends an und
stellen **keine einzige Rückfrage** — zwischen 0,05 s und 2,9 s. Die zehn alten
Projektdateien in `tests/data/projects/` migrieren von v1 bis v8 durch, und der
Rundlauf über `save`/`load` liefert dieselben Objekte samt identischen
Kennungen. Weg 2 trägt vollständig: Parameter anlegen, `create_box` mit
`=@breite` daran hängen, die Zahl von 40 auf 60 drehen — das Modell folgt —,
Undo nimmt es zurück, Export als STL und 3MF schreibt. Weg 4 ebenso: Box und
Kugel, verschieben, `blend_union` auf 5736 Dreiecke, `remesh_uniform` auf
10 720, wasserdicht und aus einem Stück.

### Ein Reparaturschritt lief ins Leere, und niemand erfuhr es

- [x] **`resolve_self_intersections` wurde an Netzen versucht, die keine
      Volumen sind, und musste scheitern.** Die Booleschen Kerne rechnen mit
      Volumina, und der Aufruf endete in „Not all meshes are volumes!" — einer Fremdmeldung im Protokoll, die niemand liest. Gefunden
      beim Öffnen von `weg3-generiert-aufbereiten`, also am Beispielprojekt für
      genau diesen Fall.

      **Die Reihenfolge war die Ursache, und der erste Befund lag daneben.**
      Naheliegend war: Der Schritt läuft vor dem Löcherschließen, also gehört er
      dahinter. Gemessen an `broken_open` und `generated_figure` half das nicht
      — beide sind auch nach `fill_holes` keine Volumen —, und damit schien die
      Reihenfolge widerlegt. Sie war es nicht: Am Körper des Beispielprojekts
      gemessen ist er nach dem Schließen **wasserdicht und trotzdem kein
      Volumen**, weil die Wicklung noch uneinheitlich ist. Das richtet erst
      `unify_normals`, und das läuft in der Kette danach.

      | Zustand | wasserdicht | Wicklung | Volumen | wirkt |
      |---|---|---|---|---|
      | vor dem Schließen | nein | — | nein | nein |
      | nach dem Schließen | ja | nein | nein | nein |
      | nach den Normalen | ja | ja | ja | **ja** |

      Der Schritt läuft jetzt **zuletzt**, und die Vorprüfung fragt nach
      `is_volume` und nicht nach `is_watertight` — eine Prüfung auf Dichtheit
      hätte den Aufruf durchgelassen und dieselbe Fremdmeldung erzeugt. Teuer
      ist das nicht: gemessene 0,1 bis 0,2 ms auf derselben Kantentabelle, die
      die Kette ohnehin aufbaut. Die 1,3 Sekunden, die eine erste Messung für
      `is_volume` zeigte, waren der erste Aufbau dieser Tabelle auf einem
      frischen Netz mit 1,3 Millionen Dreiecken — also nichts, was hier
      dazukommt.

      **Damit tut der Schritt zum ersten Mal, wofür er da ist.** Der Prüfbericht
      des Beispielprojekts liest sich jetzt schlüssig: Löcher geschlossen,
      Normalen korrigiert, Selbstdurchdringungen aufgelöst. Vorher stand dort
      keine dieser drei Zeilen zusammen mit einer wahren vierten.

      Und **was nicht getan wurde, steht im Bericht** (§2.7) — für den einen
      Fall, der übrig bleibt: `broken_open` ist von sechs geprüften
      Korpusdateien die einzige, die auch nach der ganzen Kette kein Volumen
      ist. Der Satz nennt, was dann hilft: neu vernetzen, dann ein zweiter
      Lauf.

### STEP wurde geplant, ohne dass es gehen konnte

- [x] **Der Exportplan trug keinen einzigen Befund, und der Fehler kam beim
      Schreiben.** `plan_export` prüft Wasserdichtigkeit, Bauraum, Lizenzen —
      aber nicht, ob das gewählte Format zum Körpertyp passt. Wer STEP wählte
      und ein Netz hatte, bekam einen fertigen Plan mit Dateinamen und danach
      `NeedsSolidError`. Die Auskunft war die ganze Zeit verfügbar: Der Körper
      weiß, ob er exakt ist, und das Format weiß, ob es das braucht.

      Das Fenster ist hier schon vorsorglich — es bietet STEP nur an, wenn
      wenigstens ein exakter Körper dabei ist. Zwei Fälle bleiben trotzdem: die
      **Kommandozeile**, die keinen Dialog hat, der etwas ausgraut und die
      Befunde des Plans vor dem Schreiben zeigt; und die **gemischte Auswahl**,
      bei der das Fenster STEP anbietet, weil ein Körper es tragen kann, und
      die Netze daneben einzeln scheitern. Der Befund nennt deshalb das
      betroffene Objekt und nicht bloß das Format.

### Ein Hilfetext nannte eine Form, die der eigene Auswerter ablehnt

- [x] **`create_box --width` empfahl `=breite*2` — ohne das `@`.** So getippt
      antwortet der Auswerter „Unbekannter Name im Ausdruck. Parameter werden
      mit @ geschrieben." Der Kunde wird also aufgefangen, aber er wurde vorher
      falsch losgeschickt, und zwar von der Hilfe. Gefunden beim Lesen von
      `solidon3d run create_box --help`; es war die einzige solche Stelle im
      ganzen Register.

      Abgesichert ist es jetzt breiter als behoben:
      `test_every_expression_example_in_the_register_actually_evaluates` nimmt
      jeden Titel- und `doc`-Text jeder Operation und jedes Parameters, sucht
      darin nach Ausdrucksbeispielen und rechnet sie gegen den echten Auswerter.
      Wer künftig ein Beispiel schreibt, das nicht durchgeht, bekommt einen
      roten Lauf und nicht einen Kunden.

### `run` nimmt die Operation zuerst, alle anderen Befehle den Pfad

- [x] **Wer das verwechselte, las eine wahre und nutzlose Auskunft.** `new`,
      `info`, `import`, `undo` und `export` nehmen den Pfad als erstes Argument;
      `run` nimmt die Operation. Beim Vertauschen stand da „Diese Operation gibt
      es nicht: C:/…/halter.p3d" und darunter der Vorschlag, sich die
      Operationen auflisten zu lassen — beides richtig und beides am Problem
      vorbei.

      Der Pfad wird jetzt am Namen erkannt und nicht am Dateisystem: ein
      vertippter Pfad ist derselbe Fall und verdient dieselbe Antwort. Die
      Erkennung von Tippfehlern in Operationsnamen bleibt daneben stehen und
      wird von einem eigenen Test gehalten — sie war das Erste, was die Stelle
      gelernt hatte, und sollte es nicht wieder verlernen.

### Drei Verdachtsfälle, die keine waren

Aufgeschrieben, damit sie nicht ein zweites Mal geprüft werden:

- **`arrange.below_bed` als `info`** ist richtig: `check_build_volume` schärft
  die Stufe über `about_to_write`, und während der Konstruktion beantwortet ein
  Klick dieselbe Frage. Beim Export wiegt die Lage so schwer wie die Größe.
- **Die Ausdrucksform `=@breite`** steht im Handbuch an drei Stellen, als
  Platzhalter in zwei Dialogen, in der Menüerklärung zum Parameteranlegen und
  im Hinweis des Skizzeneditors. Ein Kunde, der eine Zahl durch einen Ausdruck
  ersetzen will, findet sie.
- **Die acht `example_v*.p3d` halten beim Rechnen an**, und das ist korrekt:
  Ihre Operationen tragen `inputs: null`, sie sind für die Migrationsprüfung
  gebaut und nicht zum Rechnen. Der Befund sagt genau das —
  `evaluate.too_few_inputs`, „Dieser Operation fehlt das Objekt, auf dem sie
  arbeiten soll."

## Der Kundendurchgang auf der ruhigen Maschine (21.08.2026)

Der Durchgang davor lief, während eine zweite Sitzung im selben Baum drei
Suiten fuhr: jede Messung lag gleichmäßig 1,35- bis 1,75-fach über dem besten
bekannten Lauf, und keine Zahl daraus taugte zum Vergleich. Dieser hier lief
auf einer nachweislich ruhigen Maschine — null fremde Testläufe, Last 8 bis
28 Prozent, im Bericht je Etappe mitgeschrieben. Der Treiber verweigert den
Start, solange ein fremder Testlauf läuft.

**Das Leistungsbudget hält.** Alle 19 Messungen aus §31 grün, und jede innerhalb
weniger Prozent des besten je auf dieser Maschine gemessenen Laufs:

| Messung | jetzt | bester Lauf | Ziel |
|---|---|---|---|
| `orient_200` — Orientierungssuche über 200 Lagen | 17 585 ms | 16 378 ms | < 20 000 ms |
| `ingest_dense` — Eingangsstufe, 1 Mio. Dreiecke | 3 545 ms | 3 082 ms | — |
| `slice_knurl` — Schichtanalyse am Rändelknopf | 5 373 ms | 4 498 ms | — |
| `map_wall_medium` — Wandstärkenkarte | 4 345 ms | 4 197 ms | < 3 000 ms je Körper |
| `subdivide_surface` | 2 153 ms | 2 091 ms | < 3 000 ms |
| `sketch_solve_200` | 122 ms | 117 ms | — |

`orient_200` war unter Last bei 21 bis 23 Sekunden und riss damit das
§31-Ziel — nachgemessen am Stand **vor** meiner Änderung an `better()` lag es
bei denselben 21 Sekunden, also war es die Last und keine Regression. Auf der
ruhigen Maschine sind es 17,6 Sekunden.

**Neun Modelle, drei Etappen, nichts rot.** Einfügen, optimieren, ausbauen,
speichern, wieder öffnen, weiterbearbeiten, exportieren, zurücklesen — dann
Schichtanalyse, Vorschläge, Schätzung — dann drei Slicer-Familien. Dazu die
drei Nachbauten und das Plattenbild. Die Zeiten für einen Kunden: Einfügen und
acht Schritte an 52 Körpern in 87 Sekunden, an einem Vierteilesatz in 16.

### Behoben, jeder mit Test und Gegenprobe

- [x] **Die Reinigungsbahn des Slicers war kein Druck neben der Platte.** Der
      neue Befund `gcode.off_the_bed` meldete beim ersten echten Lauf den
      falschen Slicer — den ElegooSlicer statt CuraEngine. Zwei Ursachen:
      `G1 E6 F120` fördert sechs Millimeter, ohne einen zu fahren (die
      Bedingung „muss X oder Y führen" trägt `_EXTRUSION` seit je, die neue
      Messung nicht), und die Bahn danach fährt wirklich, steht aber **vor der
      ersten Schicht** — der Startcode des Maschinenprofils, den die
      Orca-Familie aus ihrem Bestand mitbringt. Gemessen wird jetzt ab
      `;LAYER:0` bzw. `;LAYER_CHANGE`. Dazu die dritte Hälfte:
      `gcode.stated_bed` liest, was die Datei selbst über ihr Bett sagt
      (`printable_area`, `bed_shape`) — gegen Solidons eigenen Bauraum
      gemessen hieße „außerhalb" bei der Orca-Familie entweder „daneben
      gedruckt" oder „zwei Profile meinen verschiedene Maschinen".
- [x] **Der häufigste Importfall bekam drei Handlungen, die nicht helfen.**
      Eine 3MF aus Bambu Studio, Orca oder Elegoo führt Bettkoordinaten;
      gemessen an einer heruntergeladenen Ente liegen die drei Körper bei
      x 83 bis 216, y 43 bis 113 — auf einem 256er Bett um den Ursprung ist
      das rechts draußen. Der größte ist 132 mm breit und passt dreimal.
      `_verdict_for` fragte, über **welche Seite** ein Körper hinaussteht, und
      nannte alles „über den Bauraum hinaus", was nicht nach unten hing: also
      *Modell teilen*, *Auf den Bauraum verkleinern*, *Anderen Drucker
      wählen*. Gefragt wird jetzt zuerst, ob der Körper überhaupt passt
      (`_fits_at_all`, Rand eine Bahnbreite) — dann ist es
      `arrange.off_the_plate` und die Handlung *Auf dem Bett anordnen*.
      Dieselbe Trennlinie stand seit je im Docstring von `_severity_for`; die
      Kennung hielt sich nicht daran.
- [x] **Vereinfachen machte aus einem geschlossenen Körper einen offenen — und
      sagte es nicht.** Am ausgehöhlten Entenmodell: *Netz vereinfachen* auf
      60 000 Dreiecke, danach nicht mehr wasserdicht, und im Prüfbericht stand
      „Die Fläche hat sich dabei kaum verschoben" — richtig und vollkommen
      nebensächlich. `_deviation_findings` meldet jetzt zusätzlich
      `mesh.not_watertight`; die Kennung endet so, weil Einlesen, Export und
      Agentenzug dieselbe Sache melden und die Familie dieselben zwei
      Handlungen trägt.
- [x] **Nach einem gescheiterten Slicerlauf hatte das Fenster den Lauf
      vergessen.** `_slice_failed` setzte die Zustandszeile auf leer und zeigte
      den Fehler. Sobald das Fehlerfenster zuging, stand dort, wo eben noch
      „Der Slicer rechnet …" stand, nichts mehr. Gemessen: PrusaSlicer lehnte
      die Platte der Ente ab („Der Slicer sagt, die Teile liegen außerhalb
      seines Bauraums"). Jetzt trägt die Zeile den Satz des Fehlers — nicht
      eine zweite eigene Formulierung, die auseinanderdriftet.
- [x] **Die Schätzung lag systematisch zu hoch, und zwar an der Schale.**
      `Oberfläche mal Wandstärke` zählt jede Kante doppelt: Beim 20-mm-Würfel
      3024 mm³ statt 2659. Gemessen gegen PrusaSlicer 2.9.6 an vier
      analytischen Körpern +5 bis +22 Prozent, an sieben Modellen des
      Durchgangs +10 bis +41. Gerechnet wird jetzt über die **mittlere
      Wanddicke** `3V/A` — für Kugel und Würfel genau der Inkugelradius —, und
      der Kern ist `((Dicke − Wand)/Dicke)³` des Volumens.

      Drei Modelle, dieselben sieben Messungen:

      | Modell | gemessen | Fläche mal Dicke | Hüllquader | 3V/A |
      |---|---|---|---|---|
      | Querstangen 210 | 77,7 g | +16 % | −6 % | +7 % |
      | Querstangen 220 | 82,0 g | +16 % | −5 % | +7 % |
      | Querstangen ohne Kasten | 77,5 g | +16 % | −6 % | +7 % |
      | Regalfuß | 140,4 g | +17 % | −41 % | +3 % |
      | Auslegerarm | 128,7 g | +16 % | −49 % | +1 % |
      | Kit-Card | 27,5 g | +41 % | −33 % | +20 % |
      | Propellersatz | 44,2 g | +10 % | −46 % | −2 % |
      | **Mittel** | | **19 %** | **27 %** | **7 %** |

      Der Hüllquader war der zweite Versuch, und er ist der lehrreiche: Er traf
      die vier analytischen Körper auf zwei Prozent und hielt zugleich einen
      flachen Rahmen für einen flachen Klotz. **Ein Modell an vier Körpern zu
      prüfen, die alle kompakt sind, prüft es nicht.** Deshalb steht neben der
      gemessenen Tabelle jetzt ein zweiter Test, der einen Rahmen gegen einen
      Klotz derselben Hüllmaße hält.

### Was offen bleibt

- [x] **Der Absturz beim Aufräumen kommt auch auf der ruhigen Maschine.**
      Dreimal heute, an drei verschiedenen Stellen: zweimal in einem vollen
      Suitenlauf (`test_pose_session.py`, `test_ui.py`) und einmal in der
      Druckbarkeitsetappe des 52-teiligen Modells, jeweils **nach** der
      letzten Zeile und mit geschriebenem Bericht, mit `0xC0000409`. Jede der
      drei Stellen läuft allein grün, zwei Wiederholungen der Etappe ebenso.
      Damit ist die Last als Erklärung erledigt — sie war die letzte
      naheliegende. Was bleibt, ist der Weg, der schon beim Fund
      „Ein Umgebungsartefakt, das keines war" genannt wurde: ein Lauf unter
      einem Werkzeug, das doppelte Freigaben sieht. Ohne das ist jeder Eingriff
      geraten, und Raten ist hier teurer als Warten.
- [x] **Der Schnapper kam nicht durch die Oberfläche.** Der 220er-Plan teilt
      seit heute mit Schnappverbindern, damit die korrigierte Version 4 des
      Bausteins durch den Kundenweg läuft. Gemeldet wurde
      `info:split.snap_too_small`: Die Naht der Sechskantstange gibt die
      5,4 mm nicht her, die ein Federarm braucht, und Solidon fällt
      dokumentiert auf Rundstifte zurück. Das ist richtig — aber es heißt, dass
      die neue Taschengeometrie nur im Test steht und nicht im Durchgang. Was
      fehlt, ist ein Modell mit einer breiten Naht; die 234er Basis des
      Bausatzes wäre eines.
