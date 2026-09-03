---
name: erzeugen
description: >
  Erzeugt und liefert aus, was nicht Code ist: Bildschirmfotos, Handbuch,
  Website-Bilder, SEO-Dateien, Symbol, Installationsdatei, Linux-Pakete,
  Download-Kasten, ComfyUI-Einrichtung, Website-Upload — dazu Erstaufbau der
  Umgebung und Versionspflege über check_env. Benutzen, sobald eines dieser
  Werkzeuge laufen soll, und bevor ein Paket gebaut wird.
argument-hint: "[was erzeugt werden soll]"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Erzeugen und Ausliefern

**Wann:** Bilder, Website-Bilder, Handbuch und PDFs werden **vor einem
Release** erzeugt — nicht nach jedem Schritt (Entscheidung Robert,
02.09.2026). Und auch dort nur, was sich geändert hat: Hat sich seit dem
letzten Lauf weder die Oberfläche noch ein Katalog noch eine Handbuchseite
geändert, bleiben die Bilder stehen; hat sich nur eine Sprache geändert,
läuft nur sie (`make_figures.py <sprache>`). Der volle Lauf über alle sechs
Sprachen gehört zu einem Release, bei dem sich die Oberfläche geändert hat —
und er bleibt ein Werkzeug, denn der `TypeError` der Statuszeile am
02.09.2026 fiel nur auf, weil alle Bilder liefen.

Alle Werkzeuge laufen über die virtuelle Umgebung, nie über das System-Python.
Reihenfolge und Fallen stehen unter der Liste — sie sind kein Beiwerk.

```
.venv\Scripts\python.exe tools/make_figures.py                  # Bildschirmfotos fürs Handbuch — Fenster bildschirmfüllend, `--schirm N` wählt den Monitor
.venv\Scripts\python.exe tools/make_web_images.py               # dieselben Fenster kleiner plus Bausteinband, für die Verkaufsseiten
.venv\Scripts\python.exe tools/make_manual.py                   # Handbuch als Website und PDF
.venv\Scripts\python.exe tools/make_icon.py                     # Anwendungssymbol rastern: ICO und Website-Favicon
.venv\Scripts\python.exe tools/make_seo.py                      # robots.txt, sitemap.xml, llms.txt, FAQ-Auszeichnung — nach den beiden darüber
.venv\Scripts\python.exe tools/make_installer.py                # Setup-Datei aus dist/Solidon, braucht Inno Setup 6
.venv\Scripts\python.exe tools/make_linux_packages.py --files   # Menüeintrag, Flatpak-Manifest, AppStream — läuft überall
.venv\Scripts\python.exe tools/make_download.py <pakete>        # Pakete in den Download-Kasten aller sechs Sprachen, mit SHA-256; ohne Argument leert es ihn
.venv\Scripts\python.exe tools/setup_comfyui.py                 # ComfyUI für Weg 3 einrichten: Knoten, TripoSG, 7,5 GB Gewichte
.venv\Scripts\python.exe tools/build_slice_core.py              # Konturverkettung übersetzen (optional, 1,34× auf die Schichtanalyse)
.venv\Scripts\python.exe tools/check_support.py                 # kommt eine Rückmeldung wirklich an? schickt eine echte Sendung
.venv\Scripts\python.exe tools/stamp_assets.py                  # Inhaltsstempel an jeden Verweis — **immer als Letztes vor dem Upload**
.venv\Scripts\python.exe tools/upload_website.py --seit <commit> # Website hochladen (FTPS); Zugang in .webserver.json, nicht im Repository
python tools/check_env.py                                       # stimmen die Versionen? läuft auch ohne .venv
python tools/check_env.py --install                             # sie stimmen machen (braucht Netz)
python tools/check_env.py --outdated                            # was wäre neuer, und was verbietet eine Grenze
python tools/check_env.py --freeze                              # constraints.txt neu schreiben — erst nach grüner Suite
```


**Vor dem Bau steigt die Version — ohne Rückfrage.**

```
.venv\Scripts\python.exe tools/bump_version.py            # 0.1.1 → 0.1.2
.venv\Scripts\python.exe tools/bump_version.py --minor    # eine Entscheidung
```

Die letzte Stelle steigt mit **jedem ausgelieferten Bau** um eins; das ist die
Zählregel aus `app/branding.py` und keine Ermessensfrage. Zwei Pakete mit
derselben Nummer kann niemand auseinanderhalten — nicht der Über-Dialog, nicht
der Update-Hinweis, nicht der Support vor einem Fehlerbericht. Die vorderen
Stellen bewegen sich nur bei einer größeren Änderung, und *das* ist eine
Entscheidung, die Robert trifft.

Das Werkzeug fasst beide Orte an, die die Zahl tragen (`branding.py` und
`pyproject.toml`; `tests/test_toolchain.py` hält sie zusammen).
`website/version.json` bleibt liegen: Sie sagt, was **veröffentlicht** ist, und
das stimmt erst, wenn die Pakete oben liegen — sie wird zuletzt hochgeladen.

Erhöht wird **vor** dem Prüfmodul und dem Bau. Danach trägt der Bau eine
Nummer, die es schon gab, und `make_installer.py` merkt davon nichts.

**Die Pakete baut die CI, nicht diese Maschine** (Entscheidung Robert,
27.08.2026). Der Grund ist nicht Bequemlichkeit, sondern Reichweite: Hier
entsteht ein Windows-Paket, dort entstehen vier — Windows, Linux und zwei
Macs, denn ein auf Apple Silicon gebautes Paket startet auf keinem Intel-Mac,
und das betrifft jedes Gerät vor 2020.

Ausgelöst wird der Job **nur von einem Tag oder einem Handstart**
(`workflow_dispatch`); ein gewöhnlicher Push lässt ihn aus, und er hängt an
`needs: suite` — aus einem roten Lauf entsteht kein Paket. Ein GitHub-Release
legt er nicht an, den Schritt hat der Workflow nicht: Der Tag baut, und
veröffentlicht wird erst, wenn `version.json` oben liegt.

```
git tag -a v0.2.1 -F -   &&  git push origin v0.2.1     # baut alle vier
gh run watch <lauf-id> --exit-status                    # Suite, dann Paket
gh run download <lauf-id> -D dist/ci                    # vier Artefakte
```

Die Artefakte heißen `solidon3d-setup-windows`, `solidon3d-linux`,
`solidon3d-macos-X64` und `solidon3d-macos-ARM64`, jedes mit seiner `.sha256`.

**Neun Dateien kommen an, sechs gehen hinaus.** Windows baut zwei, Linux drei
(Archiv, AppImage, Flatpak), macOS zwei je Architektur. Angeboten werden diese:

| Zielsystem | Datei |
|---|---|
| Windows | `Solidon3D-Setup-<version>.exe` |
| Windows (ohne Installation) | `Solidon3D-<version>-windows-x86_64.zip` |
| Linux (direkter Start) | `Solidon3D-<version>-x86_64.AppImage` |
| Linux (verwaltet) | `Solidon3D-<version>-x86_64.flatpak` |
| macOS (Apple Silicon) | `Solidon3D-<version>-macos-arm64.pkg` |
| macOS (Intel) | `Solidon3D-<version>-macos-x86_64.pkg` |

Nicht hinaus gehen: das Linux-Archiv (`.tar.gz`, setzt ein Terminal voraus) und
die beiden macOS-Archive (`.zip`, Bauartefakte des Signierwegs).

**Das Windows-Archiv entsteht im Signierlauf**, nicht in der CI — es soll
dieselbe signierte `.exe` tragen wie die Setup-Datei, und ein ZIP nimmt selbst
keine Signatur an. `sign_release.py` legt es neben das Setup, mit `.sha256`.
Wer ohne Signierlauf paketiert, hat es nicht, und `make_download.py` hält dann
an und sagt, welche Datei fehlt. Der Anlass steht in `packaging/CLAUDE.md`: Am
03.09.2026 scheiterte bei einem Kunden die Setup-Datei über zwei Versionen und
vier Downloads reproduzierbar, bei bytegenau angekommener Datei — und es gab
keinen zweiten Weg.

`make_download.py` weist seit dem 27.08.2026 alles andere ab (`DELIVERED`) —
davor stand die Liste nirgends außer in der Gewohnheit dessen, der die Dateien
aufzählte, und an dem Tag gingen alle acht in den Kasten. Die Startseiten
verwiesen danach in sechs Sprachen auf vier Dateien, die nie hochgeladen
werden.

Der Ablauf danach, und die Reihenfolge ist keine Empfehlung:

```
python tools/make_download.py website/dl/<die vier>     # Kasten + version.json
python tools/sign_version.py --private <schlüsseldatei>  # sonst verwirft jede Installation sie
python tools/stamp_assets.py                             # immer als Letztes vor dem Upload
python tools/upload_website.py website/dl/<jedes Paket einzeln>
python tools/upload_website.py --fehlend                 # Seiten und version.json
python tools/upload_website.py --alte-pakete --wirklich  # erst ganz zum Schluss
```

**Die Pakete gehen einzeln und zuerst.** `--fehlend` nimmt `dl/` bewusst aus
(`wanted()` — Pakete gehen einmal hoch, nicht bei jedem Abgleich), lädt aber
`version.json` mit, und die zeigt genau dorthin: Am 27.08.2026 versprach die
Seite minutenlang Fassung 0.2.1, und alle drei Pakete gaben 404. `version.json`
wartet seither von selbst, bis ihre Pakete oben liegen — verlass dich trotzdem
nicht darauf, sondern lade sie vorher.

Einzeln, weil mehrere am Stück die Verbindung reißen, und der Pfad beginnt mit
`website/` — `dl/…` allein sucht das Werkzeug im Repository-Stamm und endet
mit „Gibt es nicht". Wer das im Hintergrund startet, liest die **Ausgabedatei**
und nicht die Abschlussmeldung: Sie meldet den Status der Hülle, und der war
an dem Tag dreimal 0 über einem Upload, der gar nicht stattgefunden hat.

**Zum Schluss gegen den Server messen, nicht gegen die Platte.** Lokal ist
nach einem Release immer alles stimmig; falsch ist, was oben liegt. Ein
`HEAD`-Abruf auf jede Datei, die `version.json` **und** die Startseiten
versprechen, kostet zehn Sekunden und ist die einzige Prüfung, die den Fehler
von 0.1.3 und 0.2.1 gesehen hätte.

---

**Lokal bauen bleibt möglich** — für eine Probe, oder wenn die CI nicht kann.
Dann aus einem eigenen Arbeitsbaum, nicht aus diesem: Ein Paketierlauf dauert
eine Viertelstunde, und arbeitet in der Zeit jemand am Repository, packt er
dessen halbfertigen Stand mit ein — `make_installer.py` merkt es und
verweigert („Der Bau ist älter als app/"), aber dann fängt man von vorn an.
Der Weg ohne dieses Rennen:

```
git worktree add ../solidon-release HEAD
cd ..\solidon-release
<Prüfmodul bauen>  &&  pyinstaller packaging/solidon3d.spec  &&  make_installer.py
git worktree remove ../solidon-release
```

Das Prüfmodul (`build_licence_module.py`) gehört **in denselben Baum** und vor
den Bau: Es signiert die vier Grenzdateien aus §2 C, und wer danach eine davon
ändert, liefert ein Paket aus, das startet und in dem nichts geht. Seit dem
20.08.2026 vergleicht `make_installer.py` die Prüfsummen und bricht ab; davor
fiel es erst im Protokoll einer Testinstallation auf.

Zwei Dinge fehlen der Maschine dabei gern, und beide melden sich schlecht:
`pyinstaller --version` endete am 27.08.2026 in einem Traceback über
`ModuleNotFoundError: No module named 'altgraph'` — PyInstaller selbst war
da (6.22.2), eine seiner Abhängigkeiten war es nicht. Das ist der bekannte
Fall, dass die `.venv` einzelne Dateien verliert; `pip install altgraph`
genügte. Inno Setup 6 lag an dem Tag gar nicht auf der Maschine, `ISCC.exe`
war unter beiden Programmordnern nicht zu finden. Beides fällt erst
mitten im Bau auf, wenn man es nicht vorher prüft.

`make_figures.py`, `make_web_images.py` und `make_manual.py` laufen **nicht**
offscreen und dürfen es nicht: unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien,
und jede Beschriftung in jedem Bild wird zu einem leeren Kästchen. Wer ein
erzeugtes Bild prüft, prüft es aus demselben Grund unter der echten Plattform.

**Handbuch und Website brauchen verschiedene Maße.** Das Handbuch zeigt die
Fenster so, wie sie beim ersten Start aufgehen — bildschirmfüllend, hier 2560
Punkte breit. Auf einer Verkaufsseite steht dasselbe Bild in einer Spalte von
650 Punkten und ist damit auf ein Viertel gestaucht; gemessen wurden 25 Prozent
beim Hauptfenster und 19 beim Skizzenmodus. Deshalb nimmt `make_web_images.py`
dieselben Fenster ein zweites Mal auf, kleiner, und schneidet aus dem Katalog
ein Band aus zwei Gruppen. Die Reihenfolge ist `make_figures` →
`make_web_images` → `make_manual`; die `<img>`-Maße der von Hand gepflegten
Seiten müssen danach den echten Dateien entsprechen.

**Und `stamp_assets.py` läuft als Letztes, nach jedem Erzeuger.** Es hängt
jedem Verweis den Inhaltsstempel seiner Datei an (`style.css?v=3f332ace`) —
und jeder Erzeuger, der HTML schreibt, wirft die Stempel seiner Seiten wieder
weg. Wer danach hochlädt, liefert Seiten aus, die auf `bilder/x.png` zeigen,
und ein Browser mit einem alten Eintrag dafür fragt nicht nach.

Das ist kein theoretischer Fall: Am 27.08.2026 meldete Robert „Ohne STRG+F5
sehe ich noch die alten Bilder", und der Server war dabei richtig eingestellt
— `no-cache` für Seiten *und* Bilder, gemessen an der laufenden Website. Ein
Header erreicht eben nur die Antwort, die er begleitet, und nicht einen
Eintrag, der seit der Woche vom 20. bis 25.08. mit `max-age=604800` im
Browser liegt. Dreimal wurde das an den Headern behoben und kam dreimal
wieder; `tests/test_website.py::test_every_reference_carries_the_stamp_of_the_
file_it_points_at` macht daraus jetzt einen roten Lauf statt einer
Erinnerung.

**Die Bilderläufe sterben mitten in der Reihe — und nehmen die übrigen
Sprachen mit.** Am 23.08.2026 beim Lauf für 0.1.3 gemessen: Der Prozess endete
mit `0xc0000374` (Heap-Korruption), **nachdem** fünf Sprachen fertig waren.
Die vier portugiesischen Bilder blieben dabei drei Tage alt stehen, und
**nichts hat das gesagt** — kein Protokolleintrag, keine Fehlermeldung, eine
leere Ausgabedatei. In der Shell kam die Zahl als **127** an, und 127 sagt
nichts (siehe `ROADMAP.md`).

**Und dieser Absturz ist nicht „die Familie“.** `0xc0000374` heißt „der Heap
ist kaputt“ und sagt **nicht**, wer ihn kaputtgemacht hat — derselbe Vorhang wie
die 127, eine Ebene tiefer: Die 127 wirft verschiedene Windows-Codes in einen
Topf, `0xc0000374` wirft verschiedene Ursachen in einen Code. Die Abstürze der
Fenstertests teilen sich mit diesem hier den Code und sonst nichts Belegtes;
geprüft am 23.08.2026 an vier Testdateien, und die Fensterzahl erklärt sie
nicht (40 reißt konsistent, 118 nie).

Das Mittel ist dasselbe wie bei der Suite: **weniger Fenster je Prozess** —
eine Sprache je Aufruf. Es ist das beste verfügbare Mittel und keine Garantie:

**Auch ein Ein-Sprachen-Lauf stirbt.** Am 31.08.2026 riss `make_figures.py es`
in seinem eigenen Prozess nach **drei von neun** Bildern mit Segmentation
fault; die übrigen sechs blieben acht Stunden alt stehen. Fünf andere Sprachen
liefen in derselben Reihe beim ersten Anlauf sauber durch, `es` beim zweiten.
Hier stand vorher, ein einzelsprachiger Lauf laufe „gemessen sauber durch" —
das war die Messung eines Abends und keine Eigenschaft des Werkzeugs, dieselbe
Falle wie bei den Zahlen darüber.

**Was daraus folgt, ist keine andere Aufrufweise, sondern eine
Wiederholung mit Prüfung:** Nach jedem Lauf die Zeitstempel zählen, und bei
einer alten Datei denselben Aufruf noch einmal. Der Exit-Code trägt das nicht
— die Shell meldete 139, und 139 sagt so wenig wie die 127 darüber.

```
.venv\Scripts\python.exe tools/make_figures.py    de en
.venv\Scripts\python.exe tools/make_figures.py    es fr
.venv\Scripts\python.exe tools/make_figures.py    it pt
.venv\Scripts\python.exe tools/make_web_images.py de
.venv\Scripts\python.exe tools/make_web_images.py en
... und so fort, eine Sprache je Aufruf
```

**Beide Werkzeuge trifft es, und die Zahl davor ist keine Eigenschaft des
Werkzeugs.** Hier stand, `make_figures.py` breche nach vier Sprachen ab und
`make_web_images.py` nach fünf — beides am 23.08.2026 gemessen und beides am
27.08.2026 nicht mehr wahr: `make_web_images.py` starb da **zweimal
hintereinander nach der ersten Sprache**, und `make_figures.py` kam in
Zweiergruppen ohne einen einzigen Abriss durch.

Das ist keine Verschlechterung, sondern dasselbe Bild aus einem anderen
Winkel: Ein kaputter Heap reißt, wenn genug Speicher zerfallen ist, und wie
viel das ist, hängt an dem, was sonst auf der Maschine läuft. **Eine Zahl aus
einem früheren Lauf sagt deshalb nichts über den nächsten.** Wer sich auf sie
verlässt, hält vier frische und zwei alte Sprachen für sechs frische — genau
der Fall vom 27.08., und aufgefallen ist er allein an den Zeitstempeln.

Sicher ist nur: **eine Sprache je Aufruf**, und danach hinsehen.

Das Werkzeug nimmt seine Sprachen aus `sys.argv[1:]`; ohne Argument macht es
alle sechs. **Nach jedem Lauf die Zeitstempel prüfen** — vier Dateien je
Sprache, und eine alte fällt nur auf, wenn man hinsieht:

```
ls -l --time-style=+%d.%m_%H:%M website/bilder/*.png | sort
```

Erstaufbau: `python -m venv .venv` und
`.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui,agent,brep]"`.
Das `-c` ist kein Beiwerk: ohne es zieht ein frischer Klon andere Versionen als
die CI, und die Suite wird rot, ohne dass eine Zeile Code sich geändert hat.
Beides zusammen macht auch `python tools/check_env.py --install`.

Arbeiten mehrere am selben Repository, genügt der gute Vorsatz nicht: Der
Sitzungsstart-Hook gleicht die installierten Versionen gegen `constraints.txt`
ab und sagt, wenn etwas abweicht — samt Befehl. Er läuft dafür auch ohne
`.venv`, sonst könnte er im frischen Klon nicht melden, dass sie fehlt.

**Festgenagelt ist nicht gepflegt.** Der wöchentliche CI-Lauf „Neueste
Versionen" (montags, ohne `constraints.txt`) meldet, wenn eine neue Version
etwas *bricht* — dass es überhaupt eine neuere *gäbe*, sagt er niemandem.
Dafür ist `--outdated` da; es trennt, was gehen würde, von dem, was eine
Grenze in `pyproject.toml` ausschließt — **dort steht seit dem 14.08.2026 keine
mehr**, denn die letzte (`trimesh<5`) ist mit der Migration gefallen. Kommt eine
neue dazu, ist sie eine Entscheidung und gehört begründet. Die nächste zeichnet
sich schon ab, und sie liegt nicht in unserer Hand: `vtk 9.7.0` ist da, aber
`pyvista` verlangt `vtk<9.7.0`. Steht der Satz länger als drei Monate, erinnert
der Sitzungsstart-Hook daran. Der Weg zum neuen Stand ist immer derselbe:
aktualisieren, **Suite fahren**, dann `--freeze` — nie umgekehrt.
