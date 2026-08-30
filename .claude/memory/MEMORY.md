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
- [Qt-Prüfstand misst zu früh](qt-pruefstand-misst-zu-frueh.md) — processEvents stellt DeferredDelete nicht zu und rechnet ein Layout nicht fertig; 6 statt 1 Widget, 757 statt 855 Punkte, und die Nicht-Monotonie war das Warnsignal.
- [Katalogschlüssel sind Wörter](katalog-schluessel-sind-woerter.md) — ein neues Label kapert still einen vergebenen Quelltext; das Minus im Katalog-Diff ist der Alarm, der Test sieht es nicht.
- [Marke im span zerteilt](marke-im-span-zerteilt.md) — nach einer Umbenennung entkommt der alte Name jeder Suche, wenn ein Tag ihn teilt.
- [Website im Browser prüfen](website-im-browser-pruefen.md) — QtWebEngine ist da; heller Modus und reduzierte Bewegung gehen nur über Chromium-Flags.
- [Operationen am Stück durchfahren](ops-reihendurchlauf-kundensicht.md) — Schemavorgabe ist nicht Dialogvorbelegung; wer das verwechselt, meldet Fehlbefunde.
- [Register zählen](register-zaehlen-load-operations.md) — 86 Operationen (Stand 23.08.2026), nicht 61: ohne load_operations() fehlen die aus der Bausteinbibliothek; die Zahl bewegt sich in beide Richtungen, das Muster bleibt.
- [Zwei Läufe nach jeder Code-Änderung](zwei-laeufe-nach-jeder-code-aenderung.md) — `test_language_rules` und `ruff check .` **ohne Pfadangabe**; dreimal an einem Tag daran gescheitert, dass die Datei grün war und der Bestand rot.
- [Git: push und pull selbst](git-push-pull-selbststaendig.md) — ohne Rückfrage, aber erst nach grüner Suite; Merge statt Rebase.
- [Version vor jedem Bau erhöhen](version-vor-jedem-bau-erhoehen.md) — nicht fragen; tools/bump_version.py fasst beide Stellen an, vor dem Prüfmodul.
- [Download-Kasten: vier Pakete](download-kasten-vier-pakete.md) — der Baulauf liefert acht, angeboten werden vier (Linux ist das Flatpak); dazu die Reihenfolge des Veröffentlichens und `--nachpruefen` am Ende.
- [Website-Upload großer Dateien](website-upload-grosse-dateien.md) — ~1,8 MB/s, und mehrere Pakete am Stück reißen die Verbindung; ein halbes Paket sieht ganz aus.
- [Gesetzt heißt nicht gezeigt](text-gesetzt-heisst-nicht-gezeigt.md) — QMenu verschluckt Tooltips; ein Test über den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.
- [Qt lügt vor dem Anzeigen](qt-luegt-vor-dem-anzeigen.md) — setExpanded, isVisible und hasFocus antworten falsch, solange nichts angezeigt ist; der Test bleibt grün gegen einen Zweig, der nie läuft.
- [Signal passt an den falschen Slot](signal-passt-an-den-falschen-slot.md) — Qt verbindet, was von der Stelligkeit her passt; ein Name, der als Suchtext ankommt, läuft fehlerfrei falsch — nur das Bildschirmfoto sah es.
- [Zwei Schwellen, eine Frage](zwei-schwellen-eine-frage.md) — entscheiden zwei Konstanten dasselbe, liegt dazwischen ein Bereich, in dem beide Antworten falsch sind; besonders bei zwei Einheiten.
- [Eine Kette endet am letzten Glied](eine-kette-endet-am-letzten-glied.md) — durchgereicht ist nicht gerufen, und eine zutreffende Begründung im Docstring kann eine Testlücke decken.
- [Knopf und Handlung fragen verschieden](knopf-und-handlung-fragen-verschieden.md) — freigegeben bei A, ausgeführt bei B; dazwischen ist der Klick folgenlos. Die Ausbreitung ist gemessen und klein.
- [Roh gegen gerendert vergleichen](roh-gegen-gerendert-vergleichen.md) — wer Quelltext in fertigem HTML sucht, prüft die Maskierung mit; der Test verwarf richtige Texte und schwieg zu falschen.
- [Texte altern mit ihrer Grenze](texte-altern-mit-ihrer-grenze.md) — wer eine Fähigkeit hinzufügt, sucht die Sätze, die ihre Abwesenheit versprochen haben; sie stehen selten in derselben Datei.
- [Verweis auf Nichtexistierendes](verweis-auf-nichtexistierendes.md) — „dafür ist der Schraubdom da" — den gab es nie; ein leerer Verweis liest sich so glatt wie ein gültiger, und das Register hätte in einer Sekunde geantwortet.
- [Wächter zählt das Falsche](waechter-zaehlt-das-falsche.md) — „assert gebaut“ fragte, ob das Wörterbuch voll ist, statt ob Operationen darin stehen; der Test verglich null und blieb in der Mutationsprobe grün.
- [Was die Suite nicht findet](was-die-suite-nicht-findet.md) — sechs Fehler an einem Tag, sechs verschiedene Finder, kein einziger davon pytest; ansehen, mutieren, durchfahren.
- [Testprojekt trifft den Fall nicht](testprojekt-trifft-den-fall-nicht.md) — selbst gebaut enthält, was der Test hineinlegt; ausgeliefert enthält, was die Anwendung erzeugt — acht von neun Beispielen fielen, der grüne Test sah keines.
- [Prüfstand geht den Weg der Oberfläche](pruefstand-geht-den-weg-der-oberflaeche.md) — wer den Kern direkt ruft, misst eine Lage, die kein Klick herstellt; vier Fehlbefunde an einem Tag.
- [Gegenprobe bei geänderter Bauart](gegenprobe-bei-geaenderter-bauart.md) — die Mutation an der neuen Zeile blieb grün; rot wurde sie erst, als sie die alte Bauart nachbaute.
- [Session.apply meldet, es wirft nicht](session-apply-meldet-statt-zu-werfen.md) — ein `try` um den Aufruf läuft ins Leere; nach dem Ergebnis fragen, nicht nach dem Grund.
- [Sprachwechsel braucht zwei Schritte](sprachwechsel-zwei-schritte.md) — install_language lädt, set_language aktiviert; wer eines vergisst, misst seinen eigenen Aufbau und hält ihn für einen Fehler.

- [Zufallsziehung ist keine Zuordnung](zufallsziehung-ist-keine-zuordnung.md) — sporadische Abstürze ordnet erst eine Verteilung zu; drei rote Läufe und eine grüne Gegenprobe waren zwei Ziehungen aus 7/8.
- [Bekannte Familie erklärt nicht den Auslöser](bekannte-familie-erklaert-nicht-den-ausloeser.md) — „seit Commit X" verlangt die Gegenprobe auf dem Stand davor; die Familie nennt den Mechanismus, nie den Auslöser.
- [Verursacher wird gemessen, nicht gelesen](verursacher-wird-gemessen-nicht-gelesen.md) — `git log -- a b` nennt den letzten Commit an *einer* Datei; wer einen Schuldigen nennt, hat `git show --stat` gelesen.

- [Suche prüft ihre eigene Trefferzahl](suche-prueft-ihre-eigene-trefferzahl.md) — ein Filter, der nichts trifft, sieht aus wie einer, der nichts findet; und 265 Treffer belegen so wenig wie null.
- [Gemessene Frage ist nicht die gestellte](gemessene-frage-ist-nicht-die-gestellte.md) — jede Suche antwortet auf ihre eigene Frage; drei Fehlschlüsse an einem Abend, einer davon rot auf origin.
- [Exakte Passung ist kein Beweis](exakte-passung-ist-kein-beweis.md) — 270 war exakt der französische Wert, und niemand setzte Französisch; die Messung stimmte, die Kette dahinter war erfunden.
- [Sondenbau](sondenbau.md) — wenn ein Test nur in großen Läufen kippt, misst eine Sonde den Unterschied; sechs Bauarten, an denen sie sich selbst maß statt der Sache.
- [Messung trägt nur am Ort ihrer Messung](messung-traegt-nur-am-ort-ihrer-messung.md) — drei gefallene Befunde an einem Tag; beim dritten war die Messung echt und galt nur woanders.
- [Gefahren ist nicht gefordert](gefahren-ist-nicht-gefordert.md) — eine Auflage nannte „die Agenten-Werkzeugbeschreibungs-Tests“, ich fuhr test_agent.py; der gemeinte hieß test_agent_suite.py und war schon auf HEAD rot.
- [Vier Torläufe, ein Stand](vier-torlaeufe-ein-stand.md) — mypy lief vor dem vorletzten Commit, die Suite nach dem letzten; 4246 grüne Tests sehen einen Reexport nie.
- [Prognose ohne geprüfte Voraussetzung](prognose-ohne-gepruefte-voraussetzung.md) — „das heilt sich später von selbst" setzt jemanden voraus, der heilen kann; die Urheber-Sitzung war seit zwei Stunden beendet.
- [Beleg stand im eigenen Kontext](beleg-stand-im-eigenen-kontext.md) — bevor man eine Wissenslücke behauptet, sucht man über py/md/toml, nicht nur Markdown; Regeln stehen auch im eingecheckten Hook, und der injiziert sie oben in den eigenen Kontext.

- [Durchsicht je Version](durchsicht-je-version.md) — je Version ein Durchsicht-HTML als Artifact; jede neue beginnt mit dem Übertrag, und jeder „offene" Punkt der Vorversion wird am Code nachgemessen, nicht abgeschrieben.

## Haltung
- [Schutz verliert ein Geschwister](schutz-verliert-ein-geschwister.md) — wer eine Funktion um eine Variante erweitert, grept den alten Namen durch conftest, Fixtures und Wächter; ein ins Leere gehender Patch ist schlimmer als keiner.
- [Reparierter Fehler hat Zwillinge](reparierter-fehler-hat-zwillinge.md) — nach jedem Fix die Geschwister suchen; fünf der schwersten Review-Befunde vom 25.08.2026 waren bereits behobene Fehler an Nachbarstellen.

- [Aus Kundensicht perfekt](aus-kundensicht-perfekt.md) — Roberts Maßstab für alles: Muss der Kunde raten, ist es falsch; Aufwand ist kein Gegenargument.
- [Ein Druckziel, vier Wege, ein Vertrauensmodell](solidon-ist-die-vorstufe-vor-dem-slicer.md) — Produktkern aus dem Dental-Kundenfeedback: fremdes Modell, Konstruieren, Generieren und Formen führen in derselben Szene nachvollziehbar bis zur ehrlichen Slicer-Übergabe; alle Sitzungen und Website-Versprechen zusammen denken.
- [Technische Produktreife](technische-produktreife-konzept.md) — Konzeptlinie für die gesamte App: Kundenerlebnis als Qualitätsvertrag, begrenzte und messbare KI, gezielte Bibliotheken und reproduzierbare Updates; keine Arbeitsliste und keine Roadmap-Änderung.
- [Review immer vollständig](review-immer-vollstaendig.md) — Roberts Vorgabe für die Freigabe-Rolle: jeden Diff ganz lesen, keine Stichproben-Ökonomie; Sollprobe, Nachmessung und Katalogfrage bleiben zusätzlich.
- [Übersetzung neu statt geflickt](uebersetzung-neu-statt-flicken.md) — anhängen nur, wenn der Zusatz eigenständig ist und die alte Fassung trägt; sonst neu.

## Sitzungsbetrieb — gilt auf allen drei Maschinen

- [Git-Identität mitgeben](git-identitaet-mitgeben.md) — `git commit` bricht ohne `-c user.name`/`user.email` mit Exit 128 ab
- [Benannte Falle schützt nicht](benannte-falle-schuetzt-nicht.md) — ein Modul, das eine Gefahr richtig beschreibt, fällt trotzdem hinein; der Satz liest sich als Beleg und verhindert die Prüfung.
- [mypy prüft die laufende Plattform](mypy-prueft-die-laufende-plattform.md) — Windows-Tor und Linux-CI sehen verschiedene Fehler; ein grüner Bau sagt nichts über den lokalen Lauf.
- [Patchskript schneidet Fremdes weg](patchskript-schneidet-fremdes-weg.md) — „ab Marke bis Ende" ersetzen löscht, was die Nachbarsitzung dort einfügte; `--stat` sieht aus wie Umformatierung.
- [Geteilter Index hält alten Stand](geteilter-index-haelt-alten-stand.md) — fünf Dateien als `MM`, alle fünf identisch mit HEAD; ein Index, der zurückliegt, sieht aus wie fremde laufende Arbeit und committet sie als gelöscht.
- [Index altert zwischen Lesen und Commit](index-altert-zwischen-lesen-und-commit.md) — der private Index war korrekt aus HEAD gelesen; in den Minuten fürs Prüfen fiel ein fremder Commit, und der Index nahm ihn zurück. Sorgfalt vergrößert das Fenster.
- [Privater Index: fester Name](privater-index-fester-name.md) — `$$` im `GIT_INDEX_FILE` zeigt im nächsten Aufruf ins Leere; ein fehlender Index ist ein leerer, und der committet 1175 Dateien als gelöscht.
- [`-o` nimmt den Dateistand](commit-o-nimmt-den-dateistand.md) — der private Index hält fremde *Dateien* heraus, nicht den fremden Stand einer *gemeinsamen*; erst die eigene Zahl ansagen, dann `--numstat`.
- [$TEMP ist maschinenweit](temp-dateien-sind-maschinenweit.md) — alle Sitzungen schreiben ihre Torläufe in dieselben Dateien; eine fremde oder eigene alte Zahl sieht aus wie die aktuelle.
- [Im geteilten Baum misst man einen Zeitpunkt](geteilter-baum-misst-zeitpunkt.md) — ein Fremdbefund, den man nachmisst, kann längst repariert sein; `git diff HEAD` vor der Messung.
- [Ein Probe-Worktree altert](probe-worktree-altert.md) — sein Baum ist ein vollständiger Zustand, kein Diff; übertragen nimmt er jeden Commit zurück, der seit dem Abzweig kam. Index-Diff gegen den **aktuellen** HEAD prüfen, nicht gegen die Basis.
- [Ein Fix, der nicht grün macht](fix-der-nicht-gruen-macht.md) — bleibt der Test nach der Behebung rot, war die Diagnose falsch, nicht die Behebung unvollständig; die plausible Erzählung ging sonst ungeprüft bis in einen fremden Bericht.
- [Parallele Sitzung im Arbeitsbaum](parallele-sitzung-im-arbeitsbaum.md) — geteilter Index: fremde Änderungen aussortieren, privaten Index benutzen
- [Freies Gebiet: einfach machen](freies-gebiet-einfach-machen.md) — ist die Datei bei niemandem eingetragen, wird nicht vorgelegt, sondern gearbeitet
- [Worktrees enden auf main](worktrees-enden-auf-main.md) — Roberts Regel: Probe-Bäume fallen nach Gebrauch, am Ende zeigt `git worktree list` nur den Hauptbaum, und alles Gebaute ist auf main.
- [Weitergegebene Anweisungen gelten](weitergegebene-anweisungen-gelten.md) — was eine andere Sitzung von Robert weitergibt, ist Roberts Anweisung
- [Ein Messwerkzeug misst sich selbst](messwerkzeug-misst-sich-selbst.md) — was ein Werkzeug meldet, ist eine Eigenschaft des Werkzeugs, bis man es an einem Fall geprüft hat, dessen Ausgang man kennt.
- [Messung iterierte die Schlüssel](messung-iterierte-die-schluessel.md) — `for o in <dict>` gibt Zeichenketten, `getattr` darauf gibt `None`, und `None == None` liest sich wie Gleichheit; neun grüne Zeilen und eine verkehrte Entwarnung.
- [Wächter-Reichweite nur im Kommentar](waechter-reichweite-nur-im-kommentar.md) — der Kommentar zählte „opérations" ausdrücklich mit, das Muster traf es nie; genau dort stand dann der Fehler.
- [Fünf Tests, eine Lage](fuenf-tests-eine-lage.md) — fünf Sollwert-Tests quer zur Achse sind ein Test; der Normalfall einer Funktion ist oft die Lage, in der der Fehlerterm wegfällt, und der exakte Treffer ist der einzige konstruktionsfreie Sollwert.
- [Sollwert aus dem Prüfling](sollwert-aus-dem-pruefling.md) — wer die Erwartung mit der geprüften Funktion erzeugt, prüft Aktualität statt Richtigkeit; und ein Fehler, den eine spätere Stufe halb aufräumt, tarnt sich selbst.
- [Heredoc verschluckt \n](heredoc-verschluckt-backslash-n.md) — Bash-Heredoc + Python-Patchskript faltet Escape-Folgen; Mehrzeiliges ohne Backslashes bauen, dreimal an einem Abend zugeschnappt.
- [Heredoc kann Umlaute](heredoc-kann-umlaute.md) — aus Angst vor Quoting ASCII zu schreiben bricht die Sprachregel; gemessen überträgt es sie sauber, und die Verallgemeinerung war die eigentliche Falle.
- [Commit-Nachricht gehört in eine Datei](commit-nachricht-gehoert-in-eine-datei.md) — `python - << ENDE` liest stdin mit der System-Codepage; aus einem echten Encoding-Fehler wurde die falsche Verallgemeinerung, und ein Commit ging in ASCII hinaus.
- [Rückbau kann scheitern](rueckbau-kann-scheitern.md) — ein `finally` garantiert, dass der Block läuft, nicht dass er gelingt; die Mutation blieb stehen, und das Skript meldete einen sauberen Lauf.
- [Sonde im geteilten Baum](sonde-im-geteilten-baum.md) — eine Messung, die den Bestand verändert, gehört in einen eigenen Worktree; der Syntaxfehler war nicht das Problem, sondern der Ort.
- [Wächter lesen Kommentare mit](waechter-lesen-kommentare-mit.md) — Quelltext-Wächter treffen auch Docstrings/Kommentare; verbotene Muster umschreiben, nie zitieren.
- [Erinnerungen liegen im Repository](erinnerungen-liegen-im-repository.md) — .claude/memory ist die Quelle; neue Maschine: `python tools/link_memory.py`
- [Merkmalsmehrdeutigkeit: erledigt](merkmalsmehrdeutigkeit-entwurf.md) — §15.7 ist seit eb77658 gebaut und angeschlossen; die Notiz führte ihn zwei Tage zu lange als offen.
