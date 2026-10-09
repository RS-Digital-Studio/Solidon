# Nachweise: Örtliche Neuerkennung nach einem Schritt (Oktober 2026)

Belege zu [RM-592](../../ROADMAP.md#rm-592) und zum
[Konzept](../konzept-oertliche-erkennung-2026-10.md). Zeilenangaben, Zeiten und Stände gelten
für ihren Tag; Modelle liegen nicht bei (Kundendateien aus `F:\3D Dateien`).

| Ort | Inhalt |
|---|---|
| `konzept-sonden/` | Die zwei Sonden des Konzepts, unverändert, mit ihren Protokollen (als `.txt`, weil `*.log` ignoriert ist): `probe_local.py` (Erkennung nach einem abgezogenen Zylinder je Stufe, Treffer des Merkers über die Körpergrenze; `riser_*.txt`, `eiffel_cut.txt`, `spider_*.txt`) und `probe_floor.py` (zwei vertauschte Dreiecke als Untergrenze, Wegwerf-Prototyp der Lesung und tangentialen Trennung je Fleck; `floor_*.txt`). Gemessen unter starker Fremdlast; belastbar sind Verhältnisse und Zählerstände |
| `messbank/` | Die Messbank (Konzept §11, P0). `folge.py` fährt die Folge aus §10 A1 über eine Fallliste — Laden, drei Bohrungen, Versetzen, Aufweiten, Entfernen, Quader abziehen, Zapfen vereinen, Abschneiden, Verschieben, Bohren — durch Verlauf und Auswertung wie das Fenster und schreibt je Zustand den Abdruck der rohen Erkennung Bit für Bit, Nebentabellen, Namen, `object_hash`, das ferne Merkmal (A2) und Treffer je gemerkter Frage; `--gedaechtnis aus` ist die Kontrolle ohne Gedächtnis über die Körpergrenze, `--weglassen` die Gegenprobe je Schlüsselteil. `folge_lauf.sh` teilt eine Liste auf Prozesse auf, `vergleich.py` vergleicht zwei Läufe Zustand für Zustand. `tempo.py` misst A4 (feste Stellen an Ständer und Eiffelturm, vertauschte Dreiecke am Spiderman, Versetzen am Gartenschlauchhalter, wirkungslose Boolesche), `tempo_wechsel.sh` im Wechsel zweier Bäume; `kalt.py` die kalte Erkennung für A5. `liste_klein.txt` (219 Fälle: zwölf Beispielprojekte, `tests/data`, Kundendateien) und `liste_gross.txt` (die Paket-L-Modelle und der Gartenschlauchhalter). Jede Sonde setzt den gemessenen Baum an `sys.path[0]` und prüft `app.__file__` |
| `ergebnisse/` | Ausgaben von `vergleich.py` und den Zeitmessungen je Paket, mit Baum und Datum im Namen |
