---
name: release-weg-0-4-1-gemessen
description: "Was der Release-Weg am 13.09.2026 an Zeit und Fallen gekostet hat — Bildschirmfotos brauchen die Slicersuche, Bildmaße im HTML altern, Kaltimport im Leistungstest, Agent-Worktree scheitert an der Verifikation"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6535be56-54ec-49cb-8596-f35a930bf28d
  modified: 2026-09-13T15:47:48.210Z
---

Release 0.4.1 am 13.09.2026 (Auftrag 10:56, Tag um 17:40): 403 Commits
seit v0.4.0 und 116 ungestagete Dateien von sechs Sitzungen. Was den Weg
außer dem Bekannten ([[download-kasten-vier-pakete]],
[[release-schluessel-fuer-version-json]]) gekostet hat:

- **Das Tor über einen fremden Baum dauert nicht 12, sondern 70 Minuten**,
  wenn daneben Leseagenten und zwei Solidon-Instanzen laufen — und die
  Zeitüberschreitungsfamilie (Kindprozess-Tests mit 60-s-Limits in
  `test_process`, `test_packaging`, `test_suite_script`,
  `test_render_factory`, `test_tool_review_regressions`) wird von 3 auf 14
  rot. Allein bestehen sie in drei Minuten. Erst die Fremdlast beenden, dann
  fahren.
- **`make_figures` riss mit Exit 127 nach neun fertigen Bildern:** Der
  Druckdialog sucht seine Slicer seit diesem Tag im Arbeiter (kalt 11–13 s),
  `release()` wartet zwei Sekunden, und der Thread überlebte den Prozess. Das
  Werkzeug wartet jetzt über `wait_for_slicers()` — sonst stünde außerdem
  „Die Slicer werden gesucht …" im Handbuchbild.
- **Die Bildmaße in `funktionen.html` und fünf `features.html` sind von Hand
  gepflegt** und altern mit jedem Dialog, der höher wird (Bohrdialog mit
  Langloch-Haken: 291 statt 195 Punkte). `test_website` hält das Tor rot;
  die Maße kommen aus dem PNG-Header (Bytes 16–24), je Sprache anders.
- **Ein Gedankenstrich direkt hinter Kursiv bricht das Markup:**
  `*Generar*—;` in `es.json` ließ einen ganzen Handbuchabsatz von der
  erzeugten Seite verschwinden. Die deutsche Quelle hatte `*Erzeugen*;`.
- **`open_multicolour_example` misst den trimesh-Kaltimport mit** (~1,1 s
  von 2,0 s im Kontext „allein"); warm sind es 800 ms auf dem Stand davor
  wie danach. Ein roter Lauf dort ist ein Rückschritt erst, wenn die Sonde
  kalt/warm auf beiden Ständen einen Unterschied zeigt ([[sondenbau]]).
- **`Agent(isolation="worktree")` scheitert hier reproduzierbar** mit „git
  could not be run to resolve it" — der Worktree unter `.claude/worktrees/`
  wird aber angelegt und funktioniert. Den Agenten ohne Isolationsflag
  starten und ihm den Worktree-Pfad nennen; `.venv` des Hauptklons als
  Interpreter, `git apply --3way` zurück, Katalogkonflikte nach Schlüssel
  vereinigen.
- **Ein Tag-Push löst zwei Läufe aus** (main und Tag); der main-Lauf misst
  denselben Commit und lässt sich abbrechen (`gh run cancel`).
- **Windows-Signierung:** kein Certum-Zertifikat und kein SimplySign Desktop
  auf dieser Maschine; das Setup ging bei 0.4.0 und 0.4.1 unsigniert hinaus.
  RM-001 bleibt für Windows offen.

**Why:** Vier Stunden vom Auftrag bis zum Tag, davon gut zwei im Tor — und
jede der Fallen oben hat einen eigenen Umlauf gekostet.

**How to apply:** Vor dem nächsten Release: Fremdlast beenden, Bildmaße nach
`make_figures` prüfen, Changelog-Wächter vor dem Versionssprung von Hand
zählen ([[changelog-waechter-nach-dem-versionssprung]]), Leistungsmarken
kalt/warm sondieren statt zu glauben.

**Nachtrag 14.09.2026 — der Tag brauchte acht Läufe, und jeder fand die
nächste Schicht.** Die Reihenfolge, damit sie beim nächsten Mal in einem
Lauf steht: (1) `version.json` trägt bis `make_download` den veröffentlichten
Stand — ein `notes_version` neben einer älteren `version` lässt den
Upload-Validator und damit die Suite abbrechen. (2) Tests, die ein Komma
erwarten, setzen die `QLocale` selbst (`qt_app` tut es, freie Tests nicht).
(3) Testdateien für PHP-Zähler mit `_chmod_private` — der Runner hat Umask
0644, `count.php` verlangt 0600. (4) Der Hook-Test verlangt eine `.venv` am
Hauptklon, die der Runner nicht hat. (5) Zwei sporadische Plattformfälle
(macOS Ollama-Abbruch, Xvfb-Renderer) und ein flackernder Geometrietest
(Tetraederecke, Linux) tragen nicht strenge `xfail`-Marken, Abnahme im
Register — eine **strenge** Marke macht einen grünen Lauf rot. (6) Der
Signierschlüsselbund gehört in die **Suchliste** (`security list-keychains
-d user -s`); `find-identity` sieht ihn auch ohne, `codesign` nicht.
(7) Nichts neben `Contents/` im Bundle — die Lizenzbeilage lag dort und
gehört nach `Contents/MacOS/`, wo die Anwendung sie liest. (8) Apples
Notarisierung kann über eine Stunde „In Progress" bleiben und dann eine
Statusabfrage mit Timeout reißen; `gh run rerun <lauf> --failed` fährt nur
den Signierjob erneut, ohne neuen Tag. Ein Tag, der kein Paket erzeugt hat,
wird gelöscht und neu gesetzt (`git push origin :refs/tags/v…`); jeder
Tag-Push startet auch einen main-Lauf, der sich abbrechen lässt.
