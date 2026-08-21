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
- **Fragen statt raten** (Regel 21): Mehrdeutigkeit geht über `ctx.ask`.
  Der Kern entscheidet nicht für den Nutzer.

## Zahlen

- Millimeter und `float` (doppelte Genauigkeit). Gerundet wird in der Anzeige,
  nie im Kern.
- Kein `==` auf Fließkomma. Toleranzen kommen aus dem Materialprofil
  (`auto:<material>`), nicht als Zahl in den Code.
- Jede randomisierte Prozedur nimmt `ctx.seed` und trägt `deterministic=False`.
  Ohne beides ist sie falsch, auch wenn sie funktioniert.

## Fehler

Jede Ausnahme erbt von `AppError` und trägt `suggestions: list[Action]` —
anklickbare Handlungen, keine Prosa. Ein Fehler endet nie mit
„fehlgeschlagen", sondern nennt: was nicht ging, warum, was jetzt möglich ist
(§2.7, §33.1).

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

Wer stattdessen `document.parameters[...] = ...` schreibt, baut den Fehler
nach, der hier zweimal steckte: die Änderung ist nicht rücknehmbar, sie gilt
nicht als Änderung, und beim Schließen ist sie weg.

Die Grenze verläuft an der Auswertung: was sie beeinflusst, gehört in die
Transaktion. Druckeinstellungen und Sichtbarkeit tun das nicht — die
Einstellungen reisen zum Slicer, die Sichtbarkeit gehört der Ansicht.

## Die Lizenzgrenze

Was das Dokument ändert oder ein Ergebnis herausgibt, ruft
`activation.require(<handlung>)` — was nur liest, nie (Konzept §2 C). Die
vier Stellen sind `History.apply` (CHANGE), `export/writer.py` (EXPORT),
`export/handover.py` (SLICER) und `agent/session.py` (CHAT); jede holt den
Zustand selbst und wirft selbst (H3). Eine **neue** Stelle, die schreibt oder
herausgibt, ohne durch eine der vier zu gehen, braucht ihren eigenen
`require`-Aufruf — und einen Fall in `tests/test_licence_boundary.py`, in
beide Richtungen: gesperrt lehnt ab, lesend läuft weiter.

Die Oberfläche graut nur vorher aus, sie ist nie die Hürde. Kein Schalter,
keine Umgebungsvariable, keine Freigabedatei — die Suite patcht
`activation._cached` über monkeypatch. Wer eine der vier Grenzdateien
umbenennt oder verschiebt, zieht `integrity.BOUNDARY_FILES` und die
PyInstaller-Spec nach (`tests/test_licence_build.py` hält beide zusammen).

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
  (`org.openscad.OpenSCAD`) und setzt den PATH ausdrücklich **nicht**. Weder
  `shutil.which` noch ein Durchgang durch `/opt` findet das. Verglichen wird
  deshalb über `plain_name` — klein, ohne Trenner —, damit „orca-slicer",
  „OrcaSlicer" und das letzte Stück der Kennung derselbe Name sind.
* **Homebrew-Casks** legen das Binary in `<Name>.app/Contents/MacOS/<Name>`.
  Was in `parts_for()` fehlt, wird nicht gefunden.

Und die dritte Aufgabe kommt bei Sandboxen dazu: **Ein Flatpak hat sein
eigenes `/tmp`.** Ein Arbeitsordner aus `tempfile` ist für es unsichtbar; der
Aufruf kommt an, und das Programm findet die Datei nicht. `workspace_for` legt
ihn für eingesperrte Programme in den Nutzer-Cache, weil die Pakete
`--filesystem=home` freigeben — **nachgelesen im Flathub-Manifest**, nicht
angenommen. Wer ein weiteres Programm dazunimmt, sieht dort nach, welche
Verzeichnisse es überhaupt lesen darf.

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
