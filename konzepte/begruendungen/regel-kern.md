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

## Eine Merkmalsnummer kommt aus dem Körper, nie aus der Reihenfolge

Warum keine eigene Sortierung nach der gerundeten Mitte:

> (RM-211: zwei Rundungen eines gebogenen Winkels tauschten ihre Namen,
> sobald die Dreiecke rückwärts im Netz standen)

Warum die Summen in der Ordnung des Körpers laufen:

> Mit umgekehrter Dreiecksfolge lieferten 12 von 101 Korpuskörpern andere
> Merkmale (22.09.2026), danach keiner.

Die Regel, dass keine Wahl an der Ordnung hängen darf, stammt aus RM-210. Die
Grenze `MIN_ROUND_ARC` ist eine Entscheidung Roberts vom 23.09.2026.

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

### Was auf einer Plattform gilt, ist keine Zusage

> Dieselbe Durchsicht hat fünf Stellen gefunden, an denen Linux oder macOS
> weniger konnten als Windows — Zeigergröße, Slicer-Profile,
> ComfyUI-Rateorte, AppImages, die Zeichenkodierung von Prozessausgaben.
> Keine war eine Entscheidung; alle fünf waren dort entstanden, wo entwickelt
> wird.

> Am 27.08.2026 war ein Commit auf drei Windows-Maschinen rot und auf dem
> Bauserver grün.

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
