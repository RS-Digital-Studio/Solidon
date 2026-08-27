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

**Ausgeliefert wird aus einem eigenen Arbeitsbaum, nicht aus diesem.** Ein
Paketierlauf dauert eine Viertelstunde, und arbeitet in der Zeit jemand am
Repository, packt er dessen halbfertigen Stand mit ein — `make_installer.py`
merkt es und verweigert („Der Bau ist älter als app/"), aber dann fängt man
von vorn an. Der Weg ohne dieses Rennen:

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

**Die Bilderläufe sterben an der fünften oder sechsten Sprache — und nehmen
die übrigen mit.** Am 23.08.2026 beim Lauf für 0.1.3 gemessen: Der Prozess endete
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

Das Mittel ist dasselbe wie bei der Suite: **weniger Fenster je Prozess.**
Gemessen läuft ein Lauf mit einer einzelnen Sprache sauber durch:

```
.venv\Scripts\python.exe tools/make_figures.py    de en es fr
.venv\Scripts\python.exe tools/make_figures.py    it pt
.venv\Scripts\python.exe tools/make_web_images.py de en es fr it
.venv\Scripts\python.exe tools/make_web_images.py pt
```

**Beide Werkzeuge trifft es, an verschiedenen Stellen:** `make_figures.py`
brach am 23.08.2026 nach **vier** Sprachen ab und ließ `it` und `pt` mit den
Bildern des vorigen Laufs stehen — die zeigten dann noch die alten
Übersetzungen. `make_web_images.py` brach nach **fünf** ab. Einzeln gefahren
läuft jede Sprache sauber durch (Exit 0, gemessen).

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
