# Begründungen zu `.claude/rules/kern.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Eine ohne Wahl geschlossene Frage sagt der Frage ab, nicht der Rechnung

Anlass war RM-024: „Wer eine neue Frage außerhalb eines Schritts stellt,
entscheidet dasselbe ausdrücklich — ein stiller Abbruch ohne Satz ist keine
Antwort (RM-024)."

Warum jede optionale Frage denselben Rückweg braucht: „Wer eine weitere
optionale Frage baut, gibt ihr denselben Rückweg; sonst hält ein Import an,
der vorher durchlief."

## Dieselbe Datei, dasselbe Teil — auf jeder Maschine

Die Überschrift trug die Nummer RM-187 (plattformgleiche Rechnung).

Der Fall, aus dem die Regel über die Summenfolge bei mehreren Arbeitern
stammt:

> Die Stützsäulen summierten bis zur Durchsicht 0.5.1 je Gruppe von
> Startschichten, und dieselbe Naht kostete auf vier Kernen eine andere
> letzte Stelle als auf acht (RM-266, `analysis._above_material_shared`).

Warum `Point.buffer` und `shapely.affinity.rotate` auf der Liste stehen: Ein
Kreis aus `Point.buffer` und eine Drehung aus `shapely.affinity.rotate` nehmen
die Winkelfunktionen der Plattform, und der Rauschtest sieht beides nicht.
Warum keine Potenz `**`: Das `pow` der Plattform rundet nicht immer korrekt,
und auch das sieht das Rauschen nicht.

Warum der Skizzenlöser ausgenommen ist (RM-541): `least_squares` rechnet in
scipy über SVD, `lstsq` und `lsmr`, und ein eigener Löser ohne BLAS wäre ein
zweites Projekt. Gleich heißt dort deshalb nicht bitgleich, sondern dieselbe
Lösbarkeit und dieselbe Lage bis `_TOL`, an jedem Ort und unter
Rundungsrauschen. Das Paar, das eine Meldung nennt, ist meist, aber nicht
immer dasselbe: In der Breitensonde der Nachprüfung wechselte es an 4 von 195
unlösbaren Zufallsskizzen mit Ort oder Rauschen (Begründung der Skizzenkarte,
„Welche zwei eine Meldung nennt“). Bauplan §11.2 verweist für die Plattform
auf diese Regel; die Ausnahme gilt deshalb auch dort. Die Ortswächter in
`tests/test_sketch.py` ändern über Versätze die Rundung jeder Rechnung; die
Nachprüfung des Pakets verrauschte zusätzlich scipy selbst. Wo die Wegwahl
eine Rangfrage über LAPACK ist (`dogbox` nur bei vollem Rang), liegt die
Schranke von `matrix_rank` weit über dem Rauschen; was sie allein nicht trug,
fängt die Wegfolge in `_solve_part` (Review H-A).

## Eine Merkmalsnummer kommt aus dem Körper, nie aus der Reihenfolge

Warum keine eigene Sortierung nach der gerundeten Mitte:

> (RM-211: zwei Rundungen eines gebogenen Winkels tauschten ihre Namen,
> sobald die Dreiecke rückwärts im Netz standen)

Warum die Summen in der Ordnung des Körpers laufen:

> Mit umgekehrter Dreiecksfolge lieferten 12 von 101 Korpuskörpern andere
> Merkmale (22.09.2026), danach keiner.

Die Regel, dass keine Wahl an der Ordnung hängen darf, stammt aus RM-210. Die
Grenze `MIN_ROUND_ARC` ist eine Entscheidung Roberts vom 23.09.2026.

Warum jeder zuordnende Weg Zwillinge selbst entscheidet (04.10.2026, RM-226
Nachtrag): Nur die Auswertung am Netz fragte die Lage der Oberfläche
(`matching.settled_by_surface`). Die Auswertung eines exakten Körpers und jeder
Neubau, der danach alte Merkmale neuen zuordnet (`prepare_ops`:
`_exact_features_after`, `_preserved_exact_features`, `_exact_rest_carried`;
der Baustein am exakten Träger, `knowledge.parts.ops._read_exactly`), ordneten
nur über den Merkmalsvektor zu, fanden zwei gleiche Rundungen mehrdeutig und
gaben ihnen neue Namen: Die zwei Wandstücke einer geschlitzten Tasche hießen
nach einer Kopie, die sie nicht berührte, `fillet_3` und `fillet_4`, an der
Lochplatte `pegboard-gs-100-v2` die zwei Bögen der Kehle `torus_3` und
`torus_4`, am Teppichclip zwei Kegelstücke nach einer Bohrung anderswo
`cone_12` und `cone_13`; ein Verweis auf das alte Merkmal hielt an. Die
Operation fragt selbst, nicht nur die Auswertung: Über `FEATURE_LIMIT_COUNT`
ordnet die Auswertung nicht neu zu, und dann gilt die Ausgabe des Neubaus. Den
Ort eines alten Merkmals messen seine alten Dreiecke am alten Körper; was der
Neubau schon an seiner Stelle wiedergefunden hat, trägt Nummern des neuen und
bleibt draußen, und ein Baustein misst am Träger vor dem ersten Ziel, weil er
dessen Merkmale ohne Dreiecke durchreicht (`tests/test_exact_body_parity.py`,
Tasche aus `_slotted_pocket`).

## Was je Aufruf teuer ist, gehört nicht in eine Schleife über Flecken

### `scipy.spatial.ConvexHull`

> Der Qhull-Wrapper legt **je Aufruf eine Temporärdatei** an
> (`tempfile.mkstemp` für den Meldungsstrom). Einmal je Körper ist das
> nichts; einmal je Fleck ist es eine Dateisystemoperation mitten in einer
> Geometrierechnung, und die kostet nicht das, was sie im Leerlauf kostet: An
> einer Platte mit 64 verrundeten Taschen rief
> `perceive.features.radial_cylinder` sie 256-mal je Erkennung — gemessen
> 0,30 ms allein, 60 ms im Lauf, zusammen 15,4 s in `nt.open` und `detect`
> bei 8382 statt 1272 ms (12.09.2026).
>
> Für eine ebene Hülle nimmt der Kern deshalb GEOS:
> `MultiPoint(punkte).convex_hull`. Gemessen an 73 Flecken des Korpus: gleiche
> Umrisse, gleiche Radien, gleiche Rundungsfehler, 1439,6 ms gegen 3,8 ms.

### `np.unique(…, axis=0)`

> Dieselbe Bauart wie oben, eine Bibliothek weiter: `np.unique` über eine
> Achse sortiert Zeilen als Strukturen und ist an 180 000 Kanten viermal
> langsamer als dieselbe Frage an einer Zahl je Kante (gemessen am
> 22.09.2026: 70 gegen 16 ms). Die Randringe der Merkmalsketten stellten sie
> je Facette, und an der unterteilten Lochplatte kostete jeder Szenenaufbau
> des Objektbaums 0,4 s allein damit; die Fleckenlesung sortierte je Fleck
> ihre Ecken als Zeilen.

Warum auch einmal je Körper `vertex_rank` gefragt wird:

> — dieselbe Nummerierung, fünfmal so schnell, und nach dem ersten Leser
> umsonst (die Platzierungsnachbarschaft sortierte sie ein drittes Mal,
> RM-232).

### Eine Ebene höher: die Schattenprojektion der Ansicht

> **Und die Regel gilt eine Ebene höher genauso** (16.09.2026). Die
> Schattenprojektion der Ansicht rechnete ihre ebene Hülle selbst über
> `scipy.spatial.ConvexHull` — je Körper, je Hüllstück und je Auffangfläche,
> an `1-24+scale+polebarn.3mf` mit 89 Körpern **3541-mal für eine einzige
> Kamerageste**: 1843 ms, davon 1679 in der Hülle und 635 im Anlegen der
> Temporärdateien (Robert: „nach jedem kameraverschieben hängt es erstmal").
> `geom.mesh.planar_outline` rechnet sie jetzt über GEOS, die Ansicht fragt
> nur noch — dieselbe Grenze wie bei `hull_planes`: In `app/ui` wird keine
> Geometrie gerechnet. Danach 199 ms, mit den zwei Änderungen daneben 126 ms.
>
> Die allgemeine Form, weil dieselbe Falle zweimal an verschiedenen Orten
> stand: **Eine Regel über eine Bibliothek gilt der Bibliothek, nicht dem
> Verzeichnis, in dem sie zuerst auffiel.**

### Auswahl aus `body.faces` über `np.asarray`

> an 4,5 Millionen Dreiecken 34 ms für die Dreiecke, 17 ms für die Ecken — je
> Zugriff. In einer Schleife über Flecken wird daraus Minuten: Die Vorschau
> von *Kanten verfeinern* auf 0,04 mm am Spielwürfel stand über zehn Minuten
> in `perceive.features._area_and_reach` (Durchsicht 0.5.1, Stapelabzug).

## Ein Kernaufruf an einem ganzen Körper rechnet im Hilfsprozess

RM-212, Entscheidung Robert vom 27.09.2026: ein Hilfsprozess statt eines Kerns,
der den GIL hergibt. Gemessen am 27.09.2026 mit einem 2-ms-Takt neben dem
Aufruf (`konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/gil_kern.py`; die übrigen
Sonden dieses Abschnitts liegen daneben): Jeder Aufruf von `manifold3d` hält
den GIL für seine ganze Dauer — der Aufbau aus `Mesh64` 110 ms am Spielwürfel
(250 488 Dreiecke) bis 1,1 s am Spielbrett (1,95 Mio.), `simplify` 0,13 bis
1,4 s, `refine_to_length` 1,5 bis 8,2 s, `to_mesh64` des feinen Netzes 0,2 bis
0,4 s. Beim Übernehmen von *Kanten verfeinern* am Spielwürfel (0,05 mm, 5,8 Mio.
Dreiecke) stand das Fenster 22,7 und 15,0 s am Stück, im zweiten und dritten
Durchgang von `refine_to_length`; die erste grobe Vorschau stand je Körper 0,4
bis 0,9 s.

- **Gemeinsamer Speicher statt `pickle`**: `pickle.dumps`/`loads` der 147 MB
  des verfeinerten Würfels hielten den GIL 70 und 37 ms, `np.copyto` in den
  gemeinsamen Speicher und die Kopie heraus je 1 ms.
- **Die Schwelle** (`OFFLOAD_ABOVE`, `schwelle.py`): Unter
  10 000 Dreiecken hielt eine Rechnung im Prozess den Hauptfaden höchstens
  16 bis 18 ms an, ein Bild bei 60 Hz; darüber wächst es mit der Größe (27 ms
  an 20 480, 178 ms an 327 680), während der Hilfsprozess 1 bis 3 ms
  Stillstand kostet.
- **Eine Stufe unter der Anwendung**: Mit gleicher Priorität wachte der
  Hauptfaden neben dem rechnenden Hilfsprozess 912 ms zu spät aus einem
  10-ms-Schlaf auf, ohne dass ein Python-Faden rechnete — der Kern belegt jeden
  freigegebenen Kern.
- **Bitgleich**: 26 Fälle vorher, nachher und im Hilfsprozess
  (`referenz.py`), dazu je Rechnung ein Fall in
  `tests/test_kernel_process.py`.
- **Im Paket** startet `Solidon3D.exe` als Hilfsprozess und ist nach 0,4 bis
  0,8 s bereit (`eingefroren/`); der Vorstart hinter dem
  Fenster (`warm_up`) nimmt diese Zeit aus der ersten Vorschau.
- **Und die Buchhaltung danach**: Nach dem Hilfsprozess blieben am
  verfeinerten Würfel Stillstände von 0,2 bis 0,54 s, keiner davon im Kern —
  ein `repr` über alle Merkmale (569 ms, die größte Fläche trägt 3 979 168
  Dreiecksnummern), dreimal `sorted` je Merkmal (117 ms), `fsum(tolist())`
  (179 ms), `csgraph` im Zusammenhang (224 ms). Seit `python_values`,
  `array("q")` und der Rechnung `component_labels` im Hilfsprozess stand das
  Fenster beim Übernehmen höchstens 94 ms (Spielbrett 128 ms).
- **Ein BLAS-Faden, keine BLAS-Rechnung**: OpenBLAS legt beim Laden je
  Rechenkern einen Puffer an — `import numpy` 758 MB privater Speicher an 32
  Kernen, `scipy` noch einmal so viel, mit `OPENBLAS_NUM_THREADS=1` 19 MB
  (`privat.py`, 28.09.2026). Ein untätiger Hilfsprozess
  trug danach 761 MB frisch und 1 605 MB nach der ersten
  Zusammenhangsrechnung, mit einem Faden 21 und 135 MB; Arbeitssatz und
  Dauer der Verfeinerung blieben gleich (`speicher.py`). Das geht nur, weil
  keine Rechnung BLAS ruft — sonst hinge ihr Ergebnis an der Fadenzahl.
- **Nachgeladen wird vor dem Zurückstellen** (RM-380, 04.10.2026): Unter
  Windows rechnet der Hilfsprozess eine Klasse tiefer, und der Planer teilt
  streng nach Klasse zu. `component_labels` lud `trimesh.graph` (rund tausend
  Module mit `scipy` und `PIL`, knapp eine CPU-Sekunde) erst zurückgestellt
  nach; auf zwei Kernen, die vier Schleifen normaler Priorität auslasteten,
  kam der Hilfsprozess in 300 s von 0,36 auf 0,92 CPU-Sekunden und wurde nicht
  fertig. Im Entwicklungstor kamen so drei Fälle von `test_kernel_process.py`
  in 120 s nicht zurück, die allein in einer Sekunde grün sind — ein
  Verhungern, keine Rechenzeit: Die Rechnung selbst braucht Millisekunden. Mit
  `PREPARATIONS` war derselbe Fall nach 6,2 s fertig, ganz ohne Zurückstellen
  nach 2,9 s (`hunger.py`, `hunger-last.txt`).
- **Was nicht hinein- oder herauskommt, rechnet hier; fehlender Speicher ist
  `MemoryError`** (Durchsicht RM-212, B2, 28.09.2026): Ein nicht anlegbarer
  oder nicht zu öffnender gemeinsamer Speicher und ein Hilfsprozess, der vor
  dem Senden starb, kamen als roher `OSError`, `PermissionError` oder
  `BrokenPipeError` beim Kunden an. Windows lehnt einen Speicher über der
  Zusagegrenze mit `WinError` 1455 oder 8 ab, nicht mit `MemoryError` — der
  Speicherhinweis von `remesh`, `uniform` und `subdivided` griff auf diesem Weg
  nie. Ein untätiger Hilfsprozess endet nach dem Schließen der Leitung in 32
  bis 45 ms (`sanft_enden.py`); `GRACEFUL_SECONDS` (0,5 s)
  lässt ihm das Zehnfache.
- **Ein verlorener Hilfsprozess ist kein Kern, der aufgibt** (B3): Die
  Boolesche Kette fing ihn als Stufenfehler, startete dieselbe Last noch
  zweimal und nahm das Ergebnis still aus der Voxelstufe; `shared_volume`
  antwortete „nichts gemeinsam“.

## Eine neue gemerkte Frage wird geteilt oder gebunden — ausdrücklich

**`contains_xy` und `intersects_xy` bereiten eine Fläche selbst vor**
(08.10.2026, RM-566). Ein Merker für die Schichtflächen der Kanalsperre gab
dieselben Flächen allen Scheibenarbeitern, und jeder fragte sie mit
`shapely.contains_xy`. Der Prozess stürzte nativ ab: Der Bechertest allein,
sechsmal gepinnt, endete fünfmal mit 0xC0000005 oder 0xC0000409, mit einem
Lock um das Bauen noch dreimal, einmal mit 0xC0000374 (Heap). Shapely 2.1
bereitet eine übergebene Einzelfläche in `predicates.py` selbst vor; je Faden
eine eigene Fläche lief sauber, eine geteilte stürzte ab, auch wenn der
Hauptfaden sie vorher gefragt hatte (Review 3, `prepared_race2.py`). Ein Lock
um das Bauen schützt das Fragen nicht.

## Über die Körpergrenze merkt sich nur, wer außer seiner Lesung nichts liest

Der Merker über die Körpergrenze entstand mit RM-261. Warum die Boolesche
Ungeschnittenes in der Darstellung ihres Eingangs zurücklegen muss:

> Ohne das trafen am Gartenschlauchhalter null von 2 743 Kegelfragen; mit ihm
> 2 605, und die Erkennung nach dem Versetzen einer Bohrung sank von 27 auf 6
> bis 8 s unter Last.

## Fehler

### Ein Zeitlimit ist keine Frist

> Ein Gegenüber, das seine Kopfzeilen byteweise mit Pausen knapp unterhalb
> des Limits schickt, hält die Verbindung beliebig lange offen, ohne es je zu
> verletzen — gemessen am 10.09.2026: eine volle Sekunde für Statuszeile und
> Kopfzeilen bei einem Zeitlimit von fünfzig Millisekunden, und die Antwort
> kam mit 200 zurück.

> Zehn Stellen waren es beim Anschließen, und keine davon war falsch
> geschrieben; jede hatte nur eine Zusage nicht mitgenommen, die es anderswo
> schon gab.

## Auswertung

**Ein Befund über mehrere Körper nennt sie alle.** Fund N1 bei der Behebung
des Reviews zu `bbd41ff2d`: Zwei sich überschneidende Quader, *Überschneidungen
prüfen*, den zweiten entfernt — „Zwei Objekte überschneiden sich.“ stand weiter
am bleibenden Körper. `prepare.named_for` nannte den zweiten nur beim Namen,
und `evaluate._without_discarded` sah nur `object_id`. Der Fügeweg nannte
keinen von beiden, er spricht immer über seine zwei Eingänge. Seitdem trägt der
Befund beide Kennungen (`Finding.object_ids`). Die Liste reist im Plattencache
mit, nicht in der Projektdatei (wie `outline`: der Bericht wird beim Öffnen neu
gerechnet), und `_without_repeats` vergleicht sie mit — zwei Paare mit gleich
benannten Partnern sind zwei Aussagen, und fiele eine weg, nähme das Entfernen
des einen Partners den letzten Satz über das andere Paar mit. Geändert haben
sich damit die Befunde von *Überschneidungen prüfen*, *Fügeweg prüfen*, *Auf
dem Bett anordnen* und *Druckoptimal ausrichten*; ihre `cache_version` stieg.

## Am Dokument wird nie vorbei geschrieben

Warum `document.parameters[...] = ...` verboten ist: „Wer stattdessen
`document.parameters[...] = ...` schreibt, baut den Fehler nach, der hier
zweimal steckte."

Warum das nachträgliche Ändern eines Schritts eine Transaktion mit beiden
Fassungen ist:

> Die drei `change_*`-Methoden schrieben lange direkt in `document.ops`: Der
> alte Stand war nach dem Speichern unwiederbringlich, und Strg+Z traf einen
> anderen Schritt. Seit Format v12 trägt die Transaktion beide **Fassungen**
> des Schritts

Warum „kein zweiter Schritt" an der Schrittliste gemessen wird: „Genau diese
Verwechslung hatte einen Test die Nicht-Rücknehmbarkeit festschreiben
lassen."

Warum mehrere Schritte in einer Transaktion wechseln: Der gespeicherte
Bausteinstand (`History.use_part_states`, RM-138) „stellt jeden Einsatz
desselben Bausteins um, und ein halb umgestelltes Projekt rechnete mit zwei
Ständen nebeneinander."

Der Umbau des Verlaufs (Einfügen, Verschieben, Aus- und Einschalten) kam mit
RM-188 P7.

## Die Lizenzgrenze

Zum Manifest: „(am 26.08.2026 zweimal falsch zugeschrieben;
`integrity.boundary_hashes()` antwortet in einer Sekunde)" — zweimal wurde
eine Änderung an `activation/` für einen Bruch des Manifests gehalten.

Die Testphase als harte Grenze ist eine Entscheidung Roberts vom 26.08.2026.
Die Restgrenze und der Stand des Aktivierungsservers lauteten:

> Wer beide Orte löscht, beginnt neu — das ist die bewusste Restgrenze, denn
> die Alternative wäre ein Konto oder ein Server, und §2 sagt „ohne Netz,
> ohne Konto" zu. Ein **Aktivierungsserver** ist entschieden und wird als
> Konzept ausgearbeitet, bevor er gebaut wird.

*Anmerkung bei der Verdichtung:* Der zweite Satz ist überholt. Der
Aktivierungsdienst steht (`tools/setup_activation_server.py`,
`activation/certificate.py`), und die Testfrist ist ein optionales Angebot
(`store.TRIAL_FROM`); die Marker-Regeln gelten für sie unverändert.

Warum eine Uhr vor der Auslieferung nicht festgeschrieben wird:

> sie ist beweisbar falsch, und der Zukunftsdeckel feuert nur bei
> glaubwürdiger Uhr, sonst zerstörte ein Uhr-Rücksprung einen echten Marker.

Warum `reopen_recognition` und die zwei Aufzeichner frei bleiben und warum
der Test sie ausdrücklich festhält:

> Dasselbe gilt für `reopen_recognition`: Es nimmt nur eine solche Antwort
> zurück (die Erkennungswahl am Ladeschritt), damit die Frage wiederkommt.
> `tests/test_licence_boundary.py` nagelt alle drei ausdrücklich als frei
> fest, damit die Entscheidung beim nächsten Audit nicht wieder als Lücke
> aufgeht.

## Externe Programme: installieren heißt nicht finden

> Wer einen Installationsweg dazunimmt, nimmt zwei Aufgaben dazu. Die zweite
> ist die, die vergessen wird: **Solidon muss finden, was es gerade
> installiert hat.** Sonst läuft der Knopf durch, und die Zeile daneben sagt
> weiter „nicht gefunden" — die schlechteste aller Antworten, weil sie den
> Nutzer an seiner eigenen Handlung zweifeln lässt.
>
> Zweimal danebengegangen, beide Fälle stehen in `app/core/discover.py`:

Zu Flatpak: „Weder `shutil.which` noch ein Durchgang durch `/opt` findet das.
Verglichen wird deshalb über `plain_name` — klein, ohne Trenner —, damit
„orca-slicer", „OrcaSlicer" und das letzte Stück der Kennung derselbe Name
sind."

Zum eigenen `/tmp` eines Flatpaks: „Ein Arbeitsordner aus `tempfile` ist für
es unsichtbar; der Aufruf kommt an, und das Programm findet die Datei nicht."

### Im eigenen Flatpak sieht der Rechner anders aus

Die Überschrift hieß „Und die vierte: Wir sind selbst einer".

> Die drei Absätze oben sprechen über **fremde** Sandkästen. Sie waren
> vollständig, genau und blind für den Fall, der am 27.08.2026 aufgeschlagen
> ist: Solidon wird als Flatpak ausgeliefert. Von innen sieht der Rechner
> anders aus, und zwar an mehr Stellen, als eine Aufzählung vermuten lässt:

| Was von innen anders ist | Folge, wenn man es nicht weiß |
|---|---|
| Der PATH und die Installationsordner des Rechners fehlen | Kein Slicer wird gefunden, obwohl einer läuft |
| `subprocess` startet **im** Sandkasten | Das Programm gibt es dort nicht — `on_host` legt `flatpak-spawn --host` davor |
| `is_dir()`/`is_file()` auf einen Host-Pfad sagt nein | `install_root` fand keine Cura-Definition, und ohne `-j` startet CuraEngine gar nicht |
| `XDG_CONFIG_HOME` zeigt in den eigenen Sandkasten | Die Profile eines fremden Slicers liegen nie dort |
| `XDG_CACHE_HOME` auch — und `--filesystem=home` nimmt `~/.var` **aus** | Der Austauschordner liegt in `$HOME` und ist für den Slicer trotzdem unsichtbar |

> * **Wer einen neuen Startpfad baut, legt `discover.on_host` davor** — vier
>   Stellen liefen ohne ihn weiter, nachdem die fünfte repariert war.
> * **Im Flatpak gilt die XDG-Variable nicht, gemeint ist der Rechner.**
>   `config_home` und `exchange_dir` sagen beide genau das, und sie sind an
>   einem Tag unabhängig voneinander entstanden.
>
> Der Grund, warum das lange stehen konnte, gehört dazu, weil er wiederkommt:
>
> > **Ein Modul, das eine Falle richtig benennt, ist gegen sie nicht immun.**
>
> `discover.py` beschrieb die Flatpak-Falle über zwanzig Zeilen und zählte
> sich selbst nicht mit. `find_program` schrieb in seinen Docstring, eine
> falsche Auskunft sei teurer als keine, und meldete zwanzig Zeilen später
> einen eingetragenen Host-Pfad als verschwunden. Der Satz liest sich als
> Beleg, dass jemand nachgedacht hat — und genau deshalb prüft die Stelle
> niemand ein zweites Mal. Siehe `.claude/memory/benannte-falle-schuetzt-nicht.md`.

Zu Curas eigenem Lader unter Linux (RM-521): Der Pfad aus `AppRun.env` geht
vollständig mit, LIBC-Pfad zuerst, weil ein gekürzter die `libstdc++` des
Rechners nachzieht und mit ihr eine zu neue glibc.

### Was auf einer Plattform gilt, ist keine Zusage

> Dieselbe Durchsicht hat fünf Stellen gefunden, an denen Linux oder macOS
> weniger konnten als Windows — Zeigergröße, Slicer-Profile,
> ComfyUI-Rateorte, AppImages, die Zeichenkodierung von Prozessausgaben.
> Keine war eine Entscheidung; alle fünf waren dort entstanden, wo entwickelt
> wird.

> Am 27.08.2026 war ein Commit auf drei Windows-Maschinen rot und auf dem
> Bauserver grün.

Warum die Plattform ein Parameter ist und kein `sys.platform` im Rumpf: Ein
Zweig, den nur ein Mac sieht, wird nirgends geprüft, und `mypy` meldet
`sys.platform`-Ketten auf den anderen Maschinen als `unreachable`, was die
Linux-CI nie sieht.

Zur Prüfung mit `mypy --platform …`: „das kostet drei Läufe und fängt genau
den Fall, den ein grüner CI-Lauf nicht zurückholt." Und `ComfyBackend.readiness`
„unterscheidet vier Lagen, wo vorher ein Wahrheitswert stand".

## Einrichten heißt nicht laufen

> Die Stufe darüber, und sie ist beim ersten echten Lauf des Bildwegs
> aufgefallen (21.08.2026). Ein Einrichtungsschritt, der **behauptet**, fertig
> zu sein, ist schlechter als keiner: Der Kunde geht weiter und scheitert an
> einer Stelle, die nichts mit der Einrichtung zu tun zu haben scheint.
>
> - **Am Ende wird nachgesehen, nicht behauptet.** `comfy_setup.nodes_load`
>   lädt die Knoten im Python **von ComfyUI** — nur dort steht, was ComfyUI
>   hat. Zwei Sekunden, und sie stehen **vor** dem 7,5-GB-Download: Ein
>   fehlendes Paket nach zwei Sekunden zu melden ist mehr wert als nach einer
>   halben Stunde. Genau dieser Schritt hat einen selbstgemachten Fehler
>   gefangen, der die Knotensammlung als Ganzes ausfallen ließ.
> - **Wer prüft, prüft den ganzen Ablauf.** `readiness` fragte den Knoten aus
>   unserer eigenen Sammlung — der lag vor, also stand „Bereit" da, und
>   abgeschickt scheiterte der Auftrag an einem anderen Knoten desselben
>   Ablaufs. `missing_nodes` nennt die Namen; „ein Knoten fehlt" schickt
>   niemanden weiter (Regel 17).
> - **Eine Paketliste ist an dem Rechner gemessen, auf dem sie entstand.** Sie
>   nannte drei, und auf einem frischen ComfyUI fehlten sechs — die übrigen
>   hatten andere Knoten mitgebracht. Wer eine solche Liste schreibt, prüft
>   sie gegen eine Installation, die *nichts* hat.
> - **Ein fremdes Programm notiert, wo es liegt.** Raten ist der letzte
>   Ausweg, nicht der erste: ComfyUI Desktop schreibt seinen
>   Installationsordner in eine eigene Datei, samt einem selbst gewählten.
>   Gelesen wird sie tolerant — sie gehört jemand anderem, ihr Aufbau ist
>   nirgends zugesagt.
> - **Ein Fehler des fremden Programms wird durchgereicht, nicht
>   ausgewartet.** ComfyUI beendet einen Auftrag mit `status_str: "error"`
>   und schreibt den Grund in den Verlauf. Wer nur fragt, ob Ausgaben da sind,
>   wartet zehn Minuten auf einen toten Auftrag und sagt dann „Zeitlimit". Der
>   Satz des fremden Programms reist unübersetzt mit — er ist genauer als jede
>   Umschreibung, und wer damit zum Support geht, bringt die Zeile mit.
> - **Ein Zeitlimit gilt dem Hängen, nicht der Langsamkeit.** Zehn Minuten
>   waren an einer RTX 4080 gemessen. Solange der Auftrag in der
>   Warteschlange des fremden Programms steht, wird gewartet; eine harte
>   Obergrenze fängt nur den Fall, dass die Schlange lügt.

Seit TRELLIS.2 (RM-003) bringt ComfyUI die Knoten selbst mit, und die
billige Prüfung ist die Fassung (`comfy_setup.check_version`): Ein zu altes
ComfyUI wird vor dem ersten Download genannt, statt nach acht Gigabyte am
fehlenden Knoten zu scheitern.

## Die Lizenz kann in einer Datendatei stecken

> Regel 15 sagt „keine GPL-Abhängigkeit", und die Lizenzprüfung liest
> `pyproject.toml`. Ein mitgelieferter **ComfyUI-Ablauf** ist keine
> Abhängigkeit in diesem Sinn und verlangt trotzdem fremden Code: Beide
> Abläufe sprachen `RMBG` aus `ComfyUI-RMBG` an — GPL-3.0. Damit verlangte
> Solidon vom Kunden eine GPL-Installation, damit Weg 3 läuft, und keine
> Prüfung hatte das gesehen.

> Und die erste Frage ist, ob das Zielprogramm es **selbst** kann: ComfyUI
> kann freistellen, seit 0.33, mit Gewichten unter MIT. Damit fiel neben der
> Lizenz auch ein Installationsschritt weg.

## Wo die kurze Kette nur ausgeht (RM-534)

Die Regel in voller Länge, mit dem Warum:

**Wo die kurze Kette nur ausgeht, rechnen Fenster, Umbau und Agent weiter;
eine Vorschau nie** (RM-534, §17.2): Hält ein Schritt mit einem
`BooleanFailedError`, dessen Kette die Güte gekürzt hat (`cut_short`, nicht
eine verlangte Stufenfolge) und der *Voxelstufe erzwingen* anbietet, und hat
er nach der Güte gefragt, rechnet `evaluate` ihn mit `full_chain_when_stuck`
im selben Lauf mit der vollen Kette (`_FullChain`). Gesetzt wird es nur in
`Session.run_evaluation`, `_RevisionWorker` und `AgentSession` — die
Voxelstufe kostet an einem überdeckenden Werkzeug Sekunden, in einer Vorschau
je Wert. Eine Vorschau nimmt ein Urteil der vollen Kette aus dem Cache und
hält sonst mit `short_chain_only`; das Band sagt `SHORT_CHAIN_PREVIEW`, und
*Übernehmen* bleibt frei. Eine Frage des ersten Durchgangs beantwortet der
zweite aus dem Gedächtnis (`_WatchedAsk.again`). Ohne Frage merkt sich die
Speicherebene sofort das gerettete Ergebnis und das Urteil der vollen Kette
(`ResultCache.refuse`: nur ein `BooleanFailedError` mit gelaufener
Voxelstufe und ohne `transient` — Speichermangel ist kein Urteil —, als
Ausnahme; der Befund entsteht am Treffer mit der heutigen Kennung), auch wenn
ein späterer Schritt anhält; auf die Platte geht nur ein vollständiger
Durchlauf (§15.6). Der Agent rechnet mit dem Sitzungscache
(`AgentSession.cache`). Ein Halt nimmt mit, ob der Schritt nach der Güte
fragte (`reads_quality`); sonst gilt ein Entwurfshalt als fein, und Export wie
Slicer rechnen nie nach.
