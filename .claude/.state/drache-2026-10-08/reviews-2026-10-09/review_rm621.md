# Review RM-621 (`F:/sl-signal`, `slicer/signaltod`) — solidon3d-review, 09.10.2026

Schwer: keine. Mittel: keine. Fünf leichte Befunde, ein Nebenbefund.

- **L1** Archiveintrag RM-621 fehlt (Index und Abschnitt wie RM-620).
- **L2** Regel sagt „128 + Signal“, tragend ist die Auswahl: Orca-Absagen in Byteform
  fallen auf 128 + Signal (−100 = 156 = 128 + SIGWINCH, −101 = 155 SIGPROF, −102 bis −105 =
  154 bis 151, −64 bis −69 = 192 bis 187 Echtzeitsignale). Regel: „hinter Flatpak 128 +
  Absturzsignal“; Begründung: „Andere Signale wären Absagen: −100 kommt als 156“; Test
  `(156, False)`, wahlweise 152 bis 154.
- **L3** (a) Spanne „−1 bis −110, 146 bis 255“ unbelegt: belegt −1 bis −105
  (`src/libslic3r/Utils.hpp`, Bambu `CLI_GCODE_IN_WRAPPING_DETECT_AREA` −105), also 151 bis
  255. (b) „Ein SIGSEGV war dort 139, und der Kunde las …“ ist Herleitung, keine Messung —
  als Herleitung schreiben.
- **L4** `_wrapped` und `discover.sandboxed` leiten dieselbe Bedingung her
  (`discover.py:1099-1118`) — `return discover.sandboxed(setup.executable)`.
- **L5** Changelog es/pt anders als die Meldung: es „se ha bloqueado“, pt „encerrou
  inesperadamente“.
- **Nebenbefund**: Beendet Solidon einen Orca-Lauf nach `result.json` selbst (linger,
  SIGTERM, `process.py:838-847`), kommt −15 zurück; ohne Druckdatei macht `crashed(-15)`
  „abgestürzt“ daraus, auch wenn `result.json` eine Absage meldet. Im eigenen Flatpak 143.

Geprüft ohne Befund: bwrap/flatpak-spawn 128 + WTERMSIG (`bubblewrap.c:425-441`,
`flatpak-spawn.c:77-89`, `flatpak-run.c:4080`); kein bekannter Rückgabewert in {132, 134,
135, 136, 137, 139}; nur `slice_model` wertet einen Slicer-Rückgabewert aus; AppImage
startet per `execv`/`exec` (negativ). Sieben Gegenproben rot, 2119 Tests grün.
