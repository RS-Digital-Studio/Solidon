---
paths:
  - "app/core/**/*.py"
---

# Regeln für den Kern

Der Kern ist der Teil, der ohne Fenster funktioniert. Alles hier gilt
zusätzlich zu `AGENTS.md`.

## Grenze nach oben

- **Kein `PySide6`, kein Qt, kein `print`, kein `input`.**
  `tests/test_core_isolation.py` importiert `app.core` ohne installiertes Qt.
- Kommunikation nach außen ausschließlich über den `OpContext`:
  `ctx.progress`, `ctx.ask`, `ctx.cancelled`, `ctx.quality`, `ctx.seed`.
  Keine globalen Objekte, kein Logger, der etwas anzeigt, kein Dialog.
- **Fragen statt raten** (Regel 21): In einer Op-Auswertung geht
  Mehrdeutigkeit über `ctx.ask`, der Agent verwendet `ask_user`; andere
  Kernwege geben strukturierte Optionen zurück. Der Kern entscheidet nicht
  für den Nutzer und öffnet keinen Dialog.

## Zahlen

- Millimeter und `float` (doppelte Genauigkeit). Gerundet wird in der Anzeige,
  nie im Kern.
- Geometrische Gleichheit oder Gültigkeit wird nie mit exaktem
  Fließkommavergleich entschieden. Fertigungstoleranzen kommen aus Projekt oder
  Materialprofil (`auto:<material>`), numerische Robustheit aus `EPS_GEOM`,
  `EPS_DISPLAY` oder `EPS_MATCH`.
- Jede randomisierte Prozedur nimmt `ctx.seed` und trägt `deterministic=False`.
  Ohne beides ist sie falsch, auch wenn sie funktioniert.

## Fehler

Jeder Fehler, der die Oberfläche erreicht, ist ein `AppError` und trägt
`suggestions: list[Action]` — anklickbare, passende Handlungen statt bloßer
Prosa. Interne Assertions und Programmierausnahmen werden diagnostiziert und
an der Oberflächengrenze als `InternalError` übersetzt. Ein Fehler endet nie
mit „fehlgeschlagen", sondern nennt: was nicht ging, warum, was jetzt möglich
ist (§2.7, §33.1).

Die Hierarchie unterscheidet Bedienfehler von Programmfehlern:
`UserError` (korrigierbar), `GeometryError` (mit Vorschlag),
`ExternalToolError` (Hinweis auf die Einstellung), `InternalError`
(Fehlerbericht). Ein Programmfehler darf nie wie ein Bedienfehler aussehen —
und umgekehrt. `tests/test_errors.py` prüft, dass jede Ausnahme einen
Vorschlag trägt.

Ins Protokoll gehen Kennzahlen, nie Geometriedaten. Das Protokoll verlässt den
Rechner nur, wenn der Nutzer es selbst anhängt (§33.2) — alles andere wäre die
verbotene Telemetrie.

**Es gibt genau einen Weg hinaus, und der heißt `support.send()`**
(`app/core/support.py`). Die Grenze zur Telemetrie liegt beim Auslöser: Der
Versand hängt an einem Knopf, vorher steht die vollständige Sendung in einer
Vorschau, und `tests/test_support.py` zählt die Aufrufer — genau einer. Ein
Zeitgeber, ein Fehlerpfad oder ein Startaufruf, der selbst sendet, ist ein
Verstoß, gleich wie freundlich er begründet wird. `app/core/report.py`
schreibt weiter nur einen Ordner und darf kein `urlopen` kennen.

## Auswertung

`OpContext.scene` ist nur lesend. Ops erzeugen Objekte, sie ändern keine.
Zweimal auswerten muss identisch sein; ändert sich die Objektzahl, hält die
Auswertung an, statt still weiterzurechnen.

## Am Dokument wird nie vorbei geschrieben

Alles, was das Dokument ändert, geht durch eine Transaktion — auch das, was
keine Operation ist. Parameter, Passungen, Drucker und Material reisen als
`DocumentChange` mit (§15.5); `History.apply(..., changes=...)` nimmt sie
entgegen, `undo` und `redo` spielen sie zurück und vor. Die Vorher-Seite baut
`change_for()` aus dem Dokument — wer sie selbst zusammensucht, vergisst einen
Fall.

**Auch das nachträgliche Ändern eines Schritts** — andere Parameter, andere
Eingänge, der Zwilling im anderen Rechenkern. Die drei `change_*`-Methoden
schrieben lange direkt in `document.ops`: Der alte Stand war nach dem
Speichern unwiederbringlich, und Strg+Z traf einen anderen Schritt. Seit
Format v12 trägt die Transaktion beide **Fassungen** des Schritts
(`DocumentState.edited_ops`, `History._swap_operation`): Kennung und Platz
bleiben, der Verlauf wächst um keinen Schritt (§15.4), und `restore` legt
die Fassung in beide Richtungen zurück. Wer einen vierten Änderungsweg baut,
geht durch `_swap_operation` — und misst „kein zweiter Schritt" an der
Schrittliste, nie an der Transaktionszahl: Genau diese Verwechslung hatte
einen Test die Nicht-Rücknehmbarkeit festschreiben lassen.

Wer stattdessen `document.parameters[...] = ...` schreibt, baut den Fehler
nach, der hier zweimal steckte: die Änderung ist nicht rücknehmbar, sie gilt
nicht als Änderung, und beim Schließen ist sie weg.

Die Grenze verläuft an der Auswertung: was sie beeinflusst, gehört in die
Transaktion. Druckeinstellungen und Sichtbarkeit tun das nicht — die
Einstellungen reisen zum Slicer, die Sichtbarkeit gehört der Ansicht.

## Die Lizenzgrenze

Was das Dokument ändert oder ein Ergebnis herausgibt, ruft
`activation.require(<handlung>)` — was nur liest, nie (Konzept §2 C). Die
fünf Stellen sind `History.apply` und `History.remove_operations` (beide
CHANGE), `export/writer.py` (EXPORT), `export/handover.py` (SLICER) und
`agent/session.py` (CHAT); jede holt den Zustand selbst und wirft selbst (H3). Eine **neue** Stelle, die schreibt oder
herausgibt, ohne durch eine der vier zu gehen, braucht ihren eigenen
`require`-Aufruf — und einen Fall in `tests/test_licence_boundary.py`, in
beide Richtungen: gesperrt lehnt ab, lesend läuft weiter.

Die Oberfläche graut nur vorher aus, sie ist nie die Hürde. Kein Schalter,
keine Umgebungsvariable, keine Freigabedatei — die Suite patcht
`activation._cached` über monkeypatch. Wer eine der vier Grenzdateien
umbenennt oder verschiebt, zieht `integrity.BOUNDARY_FILES` und die
PyInstaller-Spec nach (`tests/test_licence_build.py` hält beide zusammen).
Das Manifest deckt **genau diese vier** — eine Änderung an `activation/`
selbst macht es nicht ungültig (am 26.08.2026 zweimal falsch zugeschrieben;
`integrity.boundary_hashes()` antwortet in einer Sekunde).

**Die Testphase ist eine harte Grenze, keine Erinnerung** (Entscheidung
Robert, 26.08.2026). Der Marker liegt doppelt (`trial.json` im
Einstellungs-, `activation.state` im Datenordner), trägt eine HMAC-Unterschrift
über seine Tage, und die Zusammenführung lässt den früheren ersten Start und
den späteren gesehenen Tag gewinnen: Löschen oder Editieren **eines** Ortes
ist wirkungslos, ein angefasster Marker (falsche Unterschrift) beendet die
Frist. Wer beide Orte löscht, beginnt neu — das ist die bewusste Restgrenze,
denn die Alternative wäre ein Konto oder ein Server, und §2 sagt „ohne Netz,
ohne Konto" zu. Ein **Aktivierungsserver** ist entschieden und wird als
Konzept ausgearbeitet, bevor er gebaut wird. Vier Uhr-Deckel halten die
Zählung: Rückwärtsschutz (höchster gesehener Tag), Horizont (ein Jahr),
Untergrenze Auslieferungstag, und eine Uhr **vor** der Auslieferung wird gar
nicht erst festgeschrieben — sie ist beweisbar falsch, und der Zukunftsdeckel
feuert nur bei glaubwürdiger Uhr, sonst zerstörte ein Uhr-Rücksprung einen
echten Marker.

**Antworten auf Fragen der Auswertung sind Lesen, keine Änderung.**
`History.record_answers` und `record_matches` laufen ohne `require` — mit
Absicht: Sie schreiben nur fest, was die Auswertung selbst erfragt hat
(Einheit, Merkmalszuordnung), und ein `require` dort sperrte das **Öffnen**
einer Datei mit offener Rückfrage. `tests/test_licence_boundary.py` nagelt
sie ausdrücklich als frei fest, damit die Entscheidung beim nächsten Audit
nicht wieder als Lücke aufgeht.

## Pfade

Keine absoluten Pfade in Projektdateien. Nutzerverzeichnisse kommen aus
`app.core.paths` — die Suite biegt sie um, damit ein Testlauf nichts im Profil
des Entwicklers hinterlässt (§38).

## Externe Programme: installieren heißt nicht finden

Wer einen Installationsweg dazunimmt, nimmt zwei Aufgaben dazu. Die zweite ist
die, die vergessen wird: **Solidon muss finden, was es gerade installiert
hat.** Sonst läuft der Knopf durch, und die Zeile daneben sagt weiter „nicht
gefunden" — die schlechteste aller Antworten, weil sie den Nutzer an seiner
eigenen Handlung zweifeln lässt.

Zweimal danebengegangen, beide Fälle stehen in `app/core/discover.py`:

* **Flatpak** legt seine Startprogramme unter der Anwendungskennung ab
  (`com.orcaslicer.OrcaSlicer`) und setzt den PATH ausdrücklich **nicht**. Weder
  `shutil.which` noch ein Durchgang durch `/opt` findet das. Verglichen wird
  deshalb über `plain_name` — klein, ohne Trenner —, damit „orca-slicer",
  „OrcaSlicer" und das letzte Stück der Kennung derselbe Name sind.
* **Homebrew-Casks** legen das Binary in `<Name>.app/Contents/MacOS/<Name>`.
  Was in `parts_for()` fehlt, wird nicht gefunden.

Und die dritte Aufgabe kommt bei Sandboxen dazu: **Ein Flatpak hat sein
eigenes `/tmp`.** Ein Arbeitsordner aus `tempfile` ist für es unsichtbar; der
Aufruf kommt an, und das Programm findet die Datei nicht. `workspace_for` legt
ihn für eingesperrte Programme unter `$HOME`, weil die Pakete
`--filesystem=home` freigeben — **nachgelesen im Flathub-Manifest**, nicht
angenommen. Wer ein weiteres Programm dazunimmt, sieht dort nach, welche
Verzeichnisse es überhaupt lesen darf.

### Und die vierte: Wir sind selbst einer

Die drei Absätze oben sprechen über **fremde** Sandkästen. Sie waren
vollständig, genau und blind für den Fall, der am 27.08.2026 aufgeschlagen
ist: Solidon wird als Flatpak ausgeliefert. Von innen sieht der Rechner anders
aus, und zwar an mehr Stellen, als eine Aufzählung vermuten lässt:

| Was von innen anders ist | Folge, wenn man es nicht weiß |
|---|---|
| Der PATH und die Installationsordner des Rechners fehlen | Kein Slicer wird gefunden, obwohl einer läuft |
| `subprocess` startet **im** Sandkasten | Das Programm gibt es dort nicht — `on_host` legt `flatpak-spawn --host` davor |
| `is_dir()`/`is_file()` auf einen Host-Pfad sagt nein | `install_root` fand keine Cura-Definition, und ohne `-j` startet CuraEngine gar nicht |
| `XDG_CONFIG_HOME` zeigt in den eigenen Sandkasten | Die Profile eines fremden Slicers liegen nie dort |
| `XDG_CACHE_HOME` auch — und `--filesystem=home` nimmt `~/.var` **aus** | Der Austauschordner liegt in `$HOME` und ist für den Slicer trotzdem unsichtbar |

Zwei Sätze für alles davon:

* **Wer einen neuen Startpfad baut, legt `discover.on_host` davor** — vier
  Stellen liefen ohne ihn weiter, nachdem die fünfte repariert war.
* **Im Flatpak gilt die XDG-Variable nicht, gemeint ist der Rechner.**
  `config_home` und `exchange_dir` sagen beide genau das, und sie sind an
  einem Tag unabhängig voneinander entstanden.

Der Grund, warum das lange stehen konnte, gehört dazu, weil er
wiederkommt:

> **Ein Modul, das eine Falle richtig benennt, ist gegen sie nicht immun.**

`discover.py` beschrieb die Flatpak-Falle über zwanzig Zeilen und zählte sich
selbst nicht mit. `find_program` schrieb in seinen Docstring, eine falsche
Auskunft sei teurer als keine, und meldete zwanzig Zeilen später einen
eingetragenen Host-Pfad als verschwunden. Der Satz liest sich als Beleg, dass
jemand nachgedacht hat — und genau deshalb prüft die Stelle niemand ein
zweites Mal. Siehe `.claude/memory/benannte-falle-schuetzt-nicht.md`.

### Was auf einer Plattform gilt, ist keine Zusage

Dieselbe Durchsicht hat fünf Stellen gefunden, an denen Linux oder macOS
weniger konnten als Windows — Zeigergröße, Slicer-Profile, ComfyUI-Rateorte,
AppImages, die Zeichenkodierung von Prozessausgaben. Keine war eine
Entscheidung; alle fünf waren dort entstanden, wo entwickelt wird.

**Eine Plattformkette gehört deshalb in eine Funktion mit der Plattform als
Parameter**, nicht als `sys.platform` in den Rumpf. `parts_for`,
`guesses_for`, `config_home` und `cursors.system_size` machen es so, und der
Grund ist nicht Stil:

* Ein Zweig, den nur ein Mac sehen kann, **wird nirgends geprüft**.
* `mypy` prüft die Plattform, auf der es läuft. Eine Kette aus
  `sys.platform`-Vergleichen ist auf zwei von drei Maschinen tot und wird
  dort als `unreachable` gemeldet — die Linux-CI sieht das nie. Am 27.08.2026
  war ein Commit auf drei Windows-Maschinen rot und auf dem Bauserver grün.

Wer eine solche Funktion schreibt, prüft mit
`mypy --platform linux|darwin|win32` nach; das kostet drei Läufe und fängt
genau den Fall, den ein grüner CI-Lauf nicht zurückholt.

Und wo ein Programm **mehr als Installation** braucht, ist das eine Eigenschaft
der Sache und kein Sonderfall der Oberfläche: `Requirement.follow_up` benennt
den zweiten Schritt, und die Prüfung „läuft es" ist dann nicht dieselbe wie
„kann es das" — `ComfyBackend.readiness` unterscheidet vier Lagen, wo vorher
ein Wahrheitswert stand.

## Einrichten heißt nicht laufen

Die Stufe darüber, und sie ist beim ersten echten Lauf des Bildwegs
aufgefallen (21.08.2026). Ein Einrichtungsschritt, der **behauptet**, fertig zu
sein, ist schlechter als keiner: Der Kunde geht weiter und scheitert an einer
Stelle, die nichts mit der Einrichtung zu tun zu haben scheint.

- **Am Ende wird nachgesehen, nicht behauptet.** `comfy_setup.nodes_load` lädt
  die Knoten im Python **von ComfyUI** — nur dort steht, was ComfyUI hat. Zwei
  Sekunden, und sie stehen **vor** dem 7,5-GB-Download: Ein fehlendes Paket
  nach zwei Sekunden zu melden ist mehr wert als nach einer halben Stunde.
  Genau dieser Schritt hat einen selbstgemachten Fehler gefangen, der die
  Knotensammlung als Ganzes ausfallen ließ.
- **Wer prüft, prüft den ganzen Ablauf.** `readiness` fragte den Knoten aus
  unserer eigenen Sammlung — der lag vor, also stand „Bereit" da, und
  abgeschickt scheiterte der Auftrag an einem anderen Knoten desselben
  Ablaufs. `missing_nodes` nennt die Namen; „ein Knoten fehlt" schickt
  niemanden weiter (Regel 17).
- **Eine Paketliste ist an dem Rechner gemessen, auf dem sie entstand.** Sie
  nannte drei, und auf einem frischen ComfyUI fehlten sechs — die übrigen
  hatten andere Knoten mitgebracht. Wer eine solche Liste schreibt, prüft sie
  gegen eine Installation, die *nichts* hat.
- **Ein fremdes Programm notiert, wo es liegt.** Raten ist der letzte Ausweg,
  nicht der erste: ComfyUI Desktop schreibt seinen Installationsordner in eine
  eigene Datei, samt einem selbst gewählten. Gelesen wird sie tolerant — sie
  gehört jemand anderem, ihr Aufbau ist nirgends zugesagt.
- **Ein Fehler des fremden Programms wird durchgereicht, nicht ausgewartet.**
  ComfyUI beendet einen Auftrag mit `status_str: "error"` und schreibt den
  Grund in den Verlauf. Wer nur fragt, ob Ausgaben da sind, wartet zehn
  Minuten auf einen toten Auftrag und sagt dann „Zeitlimit". Der Satz des
  fremden Programms reist unübersetzt mit — er ist genauer als jede
  Umschreibung, und wer damit zum Support geht, bringt die Zeile mit.
- **Ein Zeitlimit gilt dem Hängen, nicht der Langsamkeit.** Zehn Minuten waren
  an einer RTX 4080 gemessen. Solange der Auftrag in der Warteschlange des
  fremden Programms steht, wird gewartet; eine harte Obergrenze fängt nur den
  Fall, dass die Schlange lügt.

## Die Lizenz kann in einer Datendatei stecken

Regel 15 sagt „keine GPL-Abhängigkeit", und die Lizenzprüfung liest
`pyproject.toml`. Ein mitgelieferter **ComfyUI-Ablauf** ist keine Abhängigkeit
in diesem Sinn und verlangt trotzdem fremden Code: Beide Abläufe sprachen
`RMBG` aus `ComfyUI-RMBG` an — GPL-3.0. Damit verlangte Solidon vom Kunden eine
GPL-Installation, damit Weg 3 läuft, und keine Prüfung hatte das gesehen.

Wer eine Datendatei anlegt, die einen fremden Knoten, ein fremdes Modell oder
ein fremdes Programm benennt, stellt die Lizenzfrage dort — `tests/`
prüft die Namen im Ablauf, nicht eine Liste daneben. Und die erste Frage ist,
ob das Zielprogramm es **selbst** kann: ComfyUI kann freistellen, seit 0.33,
mit Gewichten unter MIT. Damit fiel neben der Lizenz auch ein
Installationsschritt weg.
