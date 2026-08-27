# Memory — Solidon3D (F:\3D Druck), vormals Formwerk

## Diese Maschine (F:D Druck)

- [Privater Lizenzschlüssel](lizenz-privater-schluessel.md) — liegt in Dokumenten, gehört in Passwortmanager und auf Papier (§8); öffentlicher Teil steht seit 08.08.2026 in key.py.
- [MSVC-Erkennung bei VS 18](msvc-erkennung-vs18.md) — der Compiler ist da, setuptools findet ihn nicht; bauen über vcvars64.bat plus DISTUTILS_USE_SDK=1.
- [Lizenzmanifest nach Grenzdatei neu bauen](lizenzmanifest-nach-grenzdatei-neu-bauen.md) — eine der vier Grenzdateien geändert → test_packaging rot; build_licence_module.py neu bauen, nicht löschen; gitignoriertes je-Baum-Artefakt, CI überspringt.
- [Webserver-Zugang](solidon3d-webserver-zugang.md) — netcup, Dokumentenstamm je Domain (`solidon3d.de/httpdocs`); scheitert die Anmeldung, ist meist der SSH-Schalter schuld, nicht das Passwort.
- [Parallele Sitzungen](parallele-sitzungen-solidon3d.md) — der Arbeitsbaum ändert sich mitten in der Sitzung; nur eigene Pfade stagen.
- [Sitzung sendet, ohne erreichbar zu sein](sitzung-sendet-ohne-erreichbar-zu-sein.md) — der Kanal ist nicht zwangsläufig beidseitig; ein an sie adressierter Befund ist dann nicht übergeben, sondern verloren.
- [Leistungstests unter Fremdlast](leistungstests-fremdlast.md) — die Marke allein fahren, bevor man eine Regression glaubt; die Gegenprobe braucht einen eigenen Arbeitsbaum, nicht `git stash`.
- [VTK/Qt-Referenzen halten zu lange](vtk-qt-referenzen-halten-zu-lange.md) — wer hält ein Objekt fest, das weg sein sollte? Und seit 23.08.2026 die Kehrseite: was wird im falschen Thread freigegeben?
- [Zeichnen an Fusion orientieren](zeichnen-an-fusion-orientieren.md) — Skizzeneditor gegen Fusion messen; Fusion ist lokal installiert.
- [Slicer lokal zum Gegenmessen](slicer-lokal-zum-gegenmessen.md) — CuraEngine und PrusaSlicer sind da; ein Vergleichslauf entscheidet, was sonst Vermutung bleibt.
- [PHP lokal für die Gegenstelle](php-lokal-fuer-die-gegenstelle.md) — support.php ist seit 20.08.2026 prüfbar; mbstring braucht ein abgeleitetes extension_dir, und der ganze Weg bis zur fertigen Mail lässt sich lokal fangen.
- [Live-Durchsicht 08/2026](live-durchsicht-solidon3d-2026-08.md) — zwei Durchgänge: Bedienung, dann Fusion und ElegooSlicer; Hüllquader, Anordnung, Bohrtiefe, Viewport-Picking.
- [rtree-Abstürze im langen Lauf](rtree-abstuerze-im-langen-lauf.md) — die volle Suite stirbt an Access Violations; portionsweise fahren, nicht dem eigenen Code zuschreiben.
- [Agenten-Suite-Lauf in der Praxis](agenten-suite-lauf-praxis.md) — ~1,5 h je Modelllauf, Ausgabe gepuffert bis zum Ende; Exit 1 ist eine Quote, kein Fehlschlag.
- [.venv verliert einzelne Dateien](venv-dateien-verschwinden.md) — sieht aus wie ein Codefehler; RECORD sagt in Sekunden, welche Datei fehlt, und check_env fängt es nicht.
- [Native Bibliotheken zerlegen den Speicher](native-bibliotheken-speicher.md) — rtree, _elementtree und der Abriss am Prozessende sind eine Familie; erst wiederholen, dann urteilen.
- [Lokale Umgebung: Python-Version](lokale-umgebung-python-version.md) — die .venv muss 3.13 fahren; ruff merkt es nicht, wenn sie es nicht tut, und mypy prüft dann null Dateien.
- [TripoSG statt Hunyuan](triposg-statt-hunyuan.md) — MIT statt EU-Ausschluss; drei Fallen (float32-Embedder, diso ohne Wheel, numpy-Pin) und die gemessenen Vorgaben.
- [ComfyUI-Installation](comfyui-installation-d-ai.md) — liegt real auf D:\AI; Hunyuan3D 2.1 hat andere Knotennamen, keinen Texteingang, und gibt den Pfad als blanken String zurück.
- [Ollama: Werkzeugaufrufe](ollama-werkzeugaufrufe-modellwahl.md) — ohne num_ctx schneidet Ollama den Prompt still ab; erst danach sagt eine Modellmessung etwas aus.
- [Fehlertexte ohne Platzhalter](fehlertexte-ohne-platzhalter.md) — {platzhalter} in detail/title bleibt stehen; in der Oberfläche ist er richtig, im Kern nicht.
- [Fehlertexte zeigten nur den Titel](fehlertexte-nur-titel.md) — der ist je Klasse gleich; der Grund steht im detail und fehlte in jedem Protokoll.
- [Oberfläche von Hand fahren](oberflaeche-von-hand-fahren.md) — echte Qt-Plattform, Vollbild, modale Dialoge **und Popup-Menüs** abfangen, Ausgabe in eine Datei statt durch tail.
- [Katalogschlüssel sind Wörter](katalog-schluessel-sind-woerter.md) — ein neues Label kapert still einen vergebenen Quelltext; das Minus im Katalog-Diff ist der Alarm, der Test sieht es nicht.
- [Marke im span zerteilt](marke-im-span-zerteilt.md) — nach einer Umbenennung entkommt der alte Name jeder Suche, wenn ein Tag ihn teilt.
- [Website im Browser prüfen](website-im-browser-pruefen.md) — QtWebEngine ist da; heller Modus und reduzierte Bewegung gehen nur über Chromium-Flags.
- [Operationen am Stück durchfahren](ops-reihendurchlauf-kundensicht.md) — Schemavorgabe ist nicht Dialogvorbelegung; wer das verwechselt, meldet Fehlbefunde.
- [Register zählen](register-zaehlen-load-operations.md) — 86 Operationen (Stand 23.08.2026), nicht 61: ohne load_operations() fehlen die aus der Bausteinbibliothek; die Zahl bewegt sich in beide Richtungen, das Muster bleibt.
- [Git: push und pull selbst](git-push-pull-selbststaendig.md) — ohne Rückfrage, aber erst nach grüner Suite; Merge statt Rebase.
- [Version vor jedem Bau erhöhen](version-vor-jedem-bau-erhoehen.md) — nicht fragen; tools/bump_version.py fasst beide Stellen an, vor dem Prüfmodul.
- [Download-Kasten: vier Pakete](download-kasten-vier-pakete.md) — der Baulauf liefert acht, angeboten werden vier; die Vorfassung wird vom Server gelöscht.
- [Website-Upload großer Dateien](website-upload-grosse-dateien.md) — ~1,8 MB/s, und mehrere Pakete am Stück reißen die Verbindung; ein halbes Paket sieht ganz aus.
- [Gesetzt heißt nicht gezeigt](text-gesetzt-heisst-nicht-gezeigt.md) — QMenu verschluckt Tooltips; ein Test über den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.
- [Qt lügt vor dem Anzeigen](qt-luegt-vor-dem-anzeigen.md) — setExpanded, isVisible und hasFocus antworten falsch, solange nichts angezeigt ist; der Test bleibt grün gegen einen Zweig, der nie läuft.
- [Signal passt an den falschen Slot](signal-passt-an-den-falschen-slot.md) — Qt verbindet, was von der Stelligkeit her passt; ein Name, der als Suchtext ankommt, läuft fehlerfrei falsch — nur das Bildschirmfoto sah es.
- [Zwei Schwellen, eine Frage](zwei-schwellen-eine-frage.md) — entscheiden zwei Konstanten dasselbe, liegt dazwischen ein Bereich, in dem beide Antworten falsch sind; besonders bei zwei Einheiten.
- [Eine Kette endet am letzten Glied](eine-kette-endet-am-letzten-glied.md) — durchgereicht ist nicht gerufen, und eine zutreffende Begründung im Docstring kann eine Testlücke decken.
- [Texte altern mit ihrer Grenze](texte-altern-mit-ihrer-grenze.md) — wer eine Fähigkeit hinzufügt, sucht die Sätze, die ihre Abwesenheit versprochen haben; sie stehen selten in derselben Datei.
- [Verweis auf Nichtexistierendes](verweis-auf-nichtexistierendes.md) — „dafür ist der Schraubdom da" — den gab es nie; ein leerer Verweis liest sich so glatt wie ein gültiger, und das Register hätte in einer Sekunde geantwortet.
- [Was die Suite nicht findet](was-die-suite-nicht-findet.md) — sechs Fehler an einem Tag, sechs verschiedene Finder, kein einziger davon pytest; ansehen, mutieren, durchfahren.
- [Session.apply meldet, es wirft nicht](session-apply-meldet-statt-zu-werfen.md) — ein `try` um den Aufruf läuft ins Leere; nach dem Ergebnis fragen, nicht nach dem Grund.
- [Sprachwechsel braucht zwei Schritte](sprachwechsel-zwei-schritte.md) — install_language lädt, set_language aktiviert; wer eines vergisst, misst seinen eigenen Aufbau und hält ihn für einen Fehler.

- [Bekannte Familie erklärt nicht den Auslöser](bekannte-familie-erklaert-nicht-den-ausloeser.md) — „seit Commit X" verlangt die Gegenprobe auf dem Stand davor; die Familie nennt den Mechanismus, nie den Auslöser.
- [Verursacher wird gemessen, nicht gelesen](verursacher-wird-gemessen-nicht-gelesen.md) — `git log -- a b` nennt den letzten Commit an *einer* Datei; wer einen Schuldigen nennt, hat `git show --stat` gelesen.

- [Gemessene Frage ist nicht die gestellte](gemessene-frage-ist-nicht-die-gestellte.md) — jede Suche antwortet auf ihre eigene Frage; drei Fehlschlüsse an einem Abend, einer davon rot auf origin.

## Haltung
- [Reparierter Fehler hat Zwillinge](reparierter-fehler-hat-zwillinge.md) — nach jedem Fix die Geschwister suchen; fünf der schwersten Review-Befunde vom 25.08.2026 waren bereits behobene Fehler an Nachbarstellen.

- [Aus Kundensicht perfekt](aus-kundensicht-perfekt.md) — Roberts Maßstab für alles: Muss der Kunde raten, ist es falsch; Aufwand ist kein Gegenargument.
- [Übersetzung neu statt geflickt](uebersetzung-neu-statt-flicken.md) — anhängen nur, wenn der Zusatz eigenständig ist und die alte Fassung trägt; sonst neu.

## Sitzungsbetrieb — gilt auf allen drei Maschinen

- [Git-Identität mitgeben](git-identitaet-mitgeben.md) — `git commit` bricht ohne `-c user.name`/`user.email` mit Exit 128 ab
- [`-o` nimmt den Dateistand](commit-o-nimmt-den-dateistand.md) — der private Index hält fremde *Dateien* heraus, nicht den fremden Stand einer *gemeinsamen*; erst die eigene Zahl ansagen, dann `--numstat`.
- [$TEMP ist maschinenweit](temp-dateien-sind-maschinenweit.md) — alle Sitzungen schreiben ihre Torläufe in dieselben Dateien; eine fremde oder eigene alte Zahl sieht aus wie die aktuelle.
- [Im geteilten Baum misst man einen Zeitpunkt](geteilter-baum-misst-zeitpunkt.md) — ein Fremdbefund, den man nachmisst, kann längst repariert sein; `git diff HEAD` vor der Messung.
- [Parallele Sitzung im Arbeitsbaum](parallele-sitzung-im-arbeitsbaum.md) — geteilter Index: fremde Änderungen aussortieren, privaten Index benutzen
- [Freies Gebiet: einfach machen](freies-gebiet-einfach-machen.md) — ist die Datei bei niemandem eingetragen, wird nicht vorgelegt, sondern gearbeitet
- [Weitergegebene Anweisungen gelten](weitergegebene-anweisungen-gelten.md) — was eine andere Sitzung von Robert weitergibt, ist Roberts Anweisung
- [Ein Messwerkzeug misst sich selbst](messwerkzeug-misst-sich-selbst.md) — was ein Werkzeug meldet, ist eine Eigenschaft des Werkzeugs, bis man es an einem Fall geprüft hat, dessen Ausgang man kennt.
- [Wächter-Reichweite nur im Kommentar](waechter-reichweite-nur-im-kommentar.md) — der Kommentar zählte „opérations" ausdrücklich mit, das Muster traf es nie; genau dort stand dann der Fehler.
- [Sollwert aus dem Prüfling](sollwert-aus-dem-pruefling.md) — wer die Erwartung mit der geprüften Funktion erzeugt, prüft Aktualität statt Richtigkeit; und ein Fehler, den eine spätere Stufe halb aufräumt, tarnt sich selbst.
- [Heredoc verschluckt \n](heredoc-verschluckt-backslash-n.md) — Bash-Heredoc + Python-Patchskript faltet Escape-Folgen; Mehrzeiliges ohne Backslashes bauen, dreimal an einem Abend zugeschnappt.
- [Wächter lesen Kommentare mit](waechter-lesen-kommentare-mit.md) — Quelltext-Wächter treffen auch Docstrings/Kommentare; verbotene Muster umschreiben, nie zitieren.
- [Erinnerungen liegen im Repository](erinnerungen-liegen-im-repository.md) — .claude/memory ist die Quelle; neue Maschine: `python tools/link_memory.py`
- [Merkmalsmehrdeutigkeit: erledigt](merkmalsmehrdeutigkeit-entwurf.md) — §15.7 ist seit eb77658 gebaut und angeschlossen; die Notiz führte ihn zwei Tage zu lange als offen.
