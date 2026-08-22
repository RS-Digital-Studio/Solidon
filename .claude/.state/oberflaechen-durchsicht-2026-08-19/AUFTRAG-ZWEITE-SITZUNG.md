# Text für die zweite Sitzung — die acht offenen Gebiete

Ganz kopieren und als **erste** Nachricht in die andere Sitzung schicken. Sie
enthält die Workflow-Freigabe („arbeite mit Workflows") — ohne die im eigenen
Wortlaut startet dort keiner.

---

Arbeite mit Workflows. In `.claude/.state/oberflaechen-durchsicht-2026-08-19/`
läuft eine Oberflächendurchsicht, die noch nicht fertig ist. Lies dort zuerst
`FORTSETZUNG.md`, dann `BEHOBEN.md`.

Deine Aufgabe sind **nur die acht Gebiete, die nie gelaufen sind**:
`druckdialog`, `chat`, `skizze`, `viewport`, `webseite`, `barrierefreiheit`,
`wartezeit`, `handbuch`. Alles andere ist entweder gesichert oder wird in der
ersten Sitzung behoben — fass es nicht an.

Die beiden Workflow-Skripte liegen in `workflow-skripte/` und sind schon ohne
Prüfstufe gebaut. Nimm eines davon, kürze die Gebietsliste `AREAS` auf die acht
oben und starte es über `Workflow({scriptPath: "…"})`. `resumeFromRunId` hilft
nicht, das war eine andere Sitzung.

Auftrag der Durchsicht, unverändert: Bedienbarkeit, Funktionen,
Übersichtlichkeit, modernes Aussehen — **auch was schon einmal kontrolliert
wurde**. Alle Funde beheben, egal wie klein.

Vier Dinge, die dort Geld gekostet haben:

1. **Die Funde sind roh und ungeprüft.** Etwa jeder fünfte stirbt am Code. Halte
   jeden einzeln gegen die Quelle, bevor du ihn behebst — und wenn du an der
   laufenden Oberfläche nachsiehst: `load_operations()` vor
   `build_application()` (sonst ist das Register leer und jedes Menü sieht
   kaputt aus), und `QScreen.grabWindow(window.winId())` statt `QWidget.grab`
   (sonst ist der Viewport im Bild schwarz und du meldest einen Fehler, den es
   nicht gibt).
2. **Gegenprobe zu jedem Test.** Fix aushebeln, roter Lauf sehen, Fix zurück.
   Drei meiner Tests waren grün, ohne etwas zu prüfen.
3. **Nie mit Pipe messen.** `pytest … | tail` gibt den Rückgabewert von `tail`
   zurück; ein Absturz mit 139 sah zweimal wie ein grüner Lauf aus.
4. **Arbeite in einem eigenen Arbeitsbaum** (`git worktree add`). Das ist die
   wichtigste Zeile hier. Zwei Sitzungen in einem Baum haben sich am 19./20.08.
   dreimal gegenseitig Dateien in fremde Commits gezogen — einmal ich ihre,
   zweimal sie meine. Pfadbeschränktes Committen (`git commit -F msg --
   <pfade>`) hilft nur gegen fremde Dateien, nicht dagegen, dass jemand deine
   mitnimmt: Wer den ganzen Baum committet, committet auch, was du gerade erst
   geschrieben hast. Verloren geht dabei nichts, aber die Historie erzählt
   danach etwas anderes als das, was passiert ist. Die fünf `konzept-*.md` im
   Baum sind **nicht** von dieser Durchsicht — nicht anfassen.

Nach jedem Schritt das Tor: `pytest -q -m "not performance"`, `ruff check`,
`ruff format --check`, `mypy`. Die Fensterdateien laufen einzeln, nicht im
großen Stapel — `suite-getrennt.sh` im Zustandsordner macht das. Halte den
Stand in `FORTSETZUNG.md` fort, damit man wieder anhalten kann.

Was du **nicht** entscheidest, sondern nur meldest: alles zur Auslieferung der
Demo (PyInstaller, Inno Setup, Download-Kasten auf der Webseite, Signatur). Das
gehört Robert, und es steht am Ende von `FORTSETZUNG.md`.
