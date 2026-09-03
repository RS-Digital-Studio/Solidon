# Memory — Solidon3D (F:\3D Druck)

## Diese Maschine

- [Privater Lizenzschlüssel](lizenz-privater-schluessel.md) — in Dokumenten; gehört in den Passwortmanager.
- [MSVC bei VS 18](msvc-erkennung-vs18.md) — setuptools findet ihn nicht; über vcvars64.bat bauen.
- [Webserver-Zugang](solidon3d-webserver-zugang.md) — netcup, Stamm je Domain; meist der SSH-Schalter.
- [Fusion ist da](zeichnen-an-fusion-orientieren.md) — Skizzeneditor daran messen.
- [Slicer sind da](slicer-lokal-zum-gegenmessen.md) — CuraEngine, PrusaSlicer; Vergleichslauf entscheidet.
- [PHP lokal](php-lokal-fuer-die-gegenstelle.md) — support.php bis zur fertigen Mail prüfbar.
- [Website im Browser](website-im-browser-pruefen.md) — QtWebEngine; heller Modus nur per Chromium-Flag.
- [ComfyUI](comfyui-installation-d-ai.md) — auf D:\AI; Hunyuan3D 2.1 hat andere Knoten.
- [Eine Grafikkarte](lokale-ki-teilt-eine-grafikkarte.md) — Ollama und ComfyUI serialisieren, VRAM freigeben.
- [Ollama-Werkzeuge](ollama-werkzeugaufrufe-modellwahl.md) — ohne num_ctx wird der Prompt still gekürzt.
- [.venv auf 3.13](lokale-umgebung-python-version.md) — sonst prüft mypy still null Dateien.
- [.venv verliert Dateien](venv-dateien-verschwinden.md) — RECORD nennt die fehlende, check_env nicht.
- [Installer-Probe](installer-probe-nicht-mit-fenster.md) — Robert klickt durch; {app} zeigt auf HKCU.
- [Sandbox ohne Eingabegeräte](sandbox-sieht-keine-eingabegeraete.md) — HID und Raw Input bleiben leer.
- [$TEMP ist maschinenweit](temp-dateien-sind-maschinenweit.md) — alle Sitzungen teilen die Dateien.
- [Abgebrochener Lauf hinterlässt Waisen](abgebrochener-lauf-hinterlaesst-waisen.md) — vier Prozesse ohne lebenden Elternteil; „rechnet er“ und „wem gehört er“ sind zwei Fragen.
- [Wartebedingung kennt nur einen Zustand](wartebedingung-kennt-nur-einen-zustand.md) — ein Muster mit Umlaut trifft nie; `until !` meldet dann sofort Vollzug.
- [Agenten-Suite](agenten-suite-lauf-praxis.md) — ~1,5 h je Modell; Exit 1 ist eine Quote.
- [Live-Durchsicht 08/2026](live-durchsicht-solidon3d-2026-08.md) — Bedienung, Fusion, ElegooSlicer.

## Roberts Vorgaben

- [Aus Kundensicht perfekt](aus-kundensicht-perfekt.md) — muss der Kunde raten, ist es falsch.
- [Nicht nach KI klingen](nicht-nach-ki-klingen.md) — sieben Merkmale; Rückspiegeln ist eines.
- [Beheben statt notieren](beheben-statt-notieren.md) — Fund → Messung → Fix → Test in dieser Sitzung.
- [Nur das Nötigste](tests-und-rendern-nur-das-noetigste.md) — je Schritt affected_tests; Tor vor dem Commit.
- [Review vollständig](review-immer-vollstaendig.md) — jeden Diff ganz lesen.
- [Zwei Läufe](zwei-laeufe-nach-jeder-code-aenderung.md) — test_language_rules und `ruff check .` ohne Pfad.
- [Push und Pull selbst](git-push-pull-selbststaendig.md) — nach grüner Suite; Merge, kein Rebase.
- [Version vor jedem Bau](version-vor-jedem-bau-erhoehen.md) — nicht fragen; bump_version.py.
- [Weitergegebene Anweisungen](weitergegebene-anweisungen-gelten.md) — von einer Sitzung weitergegeben zählt.
- [Freies Gebiet](freies-gebiet-einfach-machen.md) — bei niemandem eingetragen → machen, nicht vorlegen.
- [Worktrees enden auf main](worktrees-enden-auf-main.md) — Probe-Bäume fallen; alles Gebaute liegt auf main.
- [Übersetzung neu](uebersetzung-neu-statt-flicken.md) — anhängen nur, wenn der Zusatz für sich steht.
- [Härtung trifft alten Zustand](haertung-trifft-alten-zustand.md) — die neue Prüfung deckt auf, was seit Tagen falsch steht; nach dem Upload die Endpunkte abfragen.
- [Ein Weg, der nie bis zum Ende lief](weg-nie-bis-zum-ende-gemessen.md) — zwölf Tag-Läufe für 0.3.0, zwölf verschiedene Orte, keine Ursache zweimal.
- [Durchsicht je Version](durchsicht-je-version.md) — „offen" wird am Code nachgemessen, nicht abgeschrieben.

## Produkt und Entscheidungen

- [Vorstufe vor dem Slicer](solidon-ist-die-vorstufe-vor-dem-slicer.md) — vier Wege, eine Szene, ehrliche Übergabe.
- [Technische Produktreife](technische-produktreife-konzept.md) — Qualitätsvertrag, messbare KI, Updates.
- [Firmennutzung](marktwert-zielgruppe-und-firmenvalidierung.md) — Maker und Einmalkauf bleiben der Kurs.
- [Modellkette vor Freigabe](modellkette-vor-erzeugerfreigabe.md) — TripoSG bleibt (Robert, 02.09.2026).
- [KI-Hinweis sperrt](ki-hinweis-sperrt-den-ersten-modellaufruf.md) — an jeder Modellgrenze erneut.
- [Kein Rechteübergang](neu-speichern-aendert-keine-urheberschaft.md) — CC BY/SA und Provenienz bleiben.
- [Baustein je Sprache](baustein-begriff-je-sprache.md) — bloque, bloc, blocco, bloco; pieza/peça heißt Teil.
- [Bausteinbereich ist Vertrag](bausteinbereich-ist-ein-produktionsvertrag.md) — Parameterprodukt und Wandvertrag.
- [Generatorrahmen](generatorrahmen-ist-teil-der-sprache.md) — Navigation und PDF-Rand übersetzen.
- [Gestellte Daten](gestellte-daten-widersprechen-echten-daneben.md) — Erzeugnisse aus echten Läufen.
- [Beispielmaße gegen Parameter](beispiel-masse-gegen-parameter-messen.md) — 40,01 statt 40,00; Hülle je Schritt.
- [Bündel erbt kein Ziel](ein-buendel-erbt-nicht-das-erste-ziel.md) — Ziele und Auswege je Mitglied prüfen.

## Paket, Release, Website

- [SBOM aus dem Artefakt](sbom-aus-dem-kundenartefakt.md) — das Paket liefert CPython und jede native Datei.
- [Lizenzmanifest neu bauen](lizenzmanifest-nach-grenzdatei-neu-bauen.md) — nach Grenzdatei neu bauen, nicht löschen.
- [Signierung getrennt](signierung-ist-ein-eigener-vertrauensraum.md) — Windows lokal, macOS in geschützten Jobs.
- [Download-Kasten](download-kasten-vier-pakete.md) — vier von acht Paketen; `--nachpruefen` am Ende.
- [Upload großer Dateien](website-upload-grosse-dateien.md) — ~1,8 MB/s; ein halbes Paket sieht ganz aus.
- [Datei ohne Manifest](datei-ohne-manifest-hat-keinen-pruefer.md) — die AppImage steht in keiner version.json; jede Prüfung überspringt sie.
- [Cache-Fehler](entwickler-sieht-den-cache-fehler-nie.md) — der Code-Hash räumt nur beim Entwickler auf.
- [Paketfix ist kein Anwendungsfix](paketfix-ist-kein-anwendungsfix.md) — im Manifest behoben, im AppImage noch da.
- [Rechnung warnt, sie erlaubt nicht](rechnung-warnt-sie-erlaubt-nicht.md) — was weg soll, wird benannt; „überall vorhanden" ist keine Messung.
- [Prüfjob nur beim Tag](pruefjob-nur-beim-tag-hat-nie-gemessen.md) — einmal über ein echtes Paket fahren.
- [mypy prüft die Plattform](mypy-prueft-die-laufende-plattform.md) — Windows-Tor und Linux-CI sehen anderes.
- [Datei zuerst, Register danach](datei-zuerst-register-danach.md) — atomar veröffentlichen, nur vorwärts aktivieren.
- [Erzeugte Datei](erzeugte-datei-fuehrt-ins-fremde-werkzeug.md) — Befund hier, Antwort im fremden Werkzeug.

## Qt, VTK, Oberfläche

- [VTK/Qt-Referenzen](vtk-qt-referenzen-halten-zu-lange.md) — wer hält, was weg sein sollte?
- [VTK sagt ja und tut nichts](vtk-sagt-ja-und-tut-nichts.md) — Hardware-Picker treffen hier nichts, Depth Peeling läuft nie.
- [Verwaiste Widgets](verwaiste-widgets-sterben-im-falschen-moment.md) — gc.disable trennt Zeitpunkt und Zerstörung.
- [Prüfstand misst zu früh](qt-pruefstand-misst-zu-frueh.md) — processEvents stellt DeferredDelete nicht zu.
- [Qt lügt vor dem Anzeigen](qt-luegt-vor-dem-anzeigen.md) — isVisible und hasFocus antworten falsch.
- [Gesetzt ist nicht gezeigt](text-gesetzt-heisst-nicht-gezeigt.md) — QMenu verschluckt Tooltips.
- [Suite ohne Stylesheet](suite-faehrt-ohne-stylesheet.md) — ein Farbtest misst Windows.
- [Signal am falschen Slot](signal-passt-an-den-falschen-slot.md) — Qt verbindet nach Stelligkeit.
- [Warnungsmarke ist Zustand](warnungsmarke-ist-semantischer-zustand.md) — Aktoren überleben keinen Szenenaufbau.
- [Kalenderdatum](kalenderdatum-folgt-appsprache.md) — `QLocale()` ohne Argument folgt dem Prozess.
- [Sprachwechsel: zwei Schritte](sprachwechsel-zwei-schritte.md) — install_language lädt, set_language aktiviert.
- [Startfläche](startflaeche-braucht-breite-und-skalierung.md) — Breite und Skalierung getrennt prüfen.
- [Oberfläche von Hand](oberflaeche-von-hand-fahren.md) — echte Plattform, Dialoge und Popups abfangen.
- [Prüfstand auf dem Klickweg](pruefstand-geht-den-weg-der-oberflaeche.md) — der Kern direkt misst ohne Klick.
- [Katalogschlüssel sind Wörter](katalog-schluessel-sind-woerter.md) — ein neues Label kapert einen Quelltext.
- [Marke im span zerteilt](marke-im-span-zerteilt.md) — ein Tag im Namen entkommt jeder Suche.
- [Fehlertexte ohne Platzhalter](fehlertexte-ohne-platzhalter.md) — {platzhalter} bleibt im Kern stehen.
- [Fehlertexte nur Titel](fehlertexte-nur-titel.md) — der Grund steht im detail.
- [Session.apply meldet](session-apply-meldet-statt-zu-werfen.md) — ein `try` läuft ins Leere; Ergebnis fragen.
- [Ops am Stück durchfahren](ops-reihendurchlauf-kundensicht.md) — Schemavorgabe ist nicht Dialogvorbelegung.
- [Register zählen](register-zaehlen-load-operations.md) — ohne load_operations() fehlen die Bausteine.
- [Knopf und Handlung](knopf-und-handlung-fragen-verschieden.md) — freigegeben bei A, ausgeführt bei B.
- [Reparatur vor den Fehler](reparatur-muss-vor-den-fehler.md) — Suffix atomar ersetzen, ersten Klick sperren.
- [Kette endet am letzten Glied](eine-kette-endet-am-letzten-glied.md) — durchgereicht ist nicht gerufen.
- [Rezept ist der Fund](rezept-ist-der-fund-op-ist-die-ursache.md) — die Prüfung fehlte in der Operation.
- [Architektur-Sonde](architektur-sonde-type-checking.md) — TYPE_CHECKING ausschließen; Kernänderung = Suite.

## Messen und Prüfen

- [Was die Suite nicht findet](was-die-suite-nicht-findet.md) — ansehen, mutieren, durchfahren.
- [Zwei Schwellen, eine Frage](zwei-schwellen-eine-frage.md) — dazwischen sind beide Antworten falsch.
- [Roh gegen gerendert](roh-gegen-gerendert-vergleichen.md) — Maskierung mitprüfen.
- [Texte altern mit ihrer Grenze](texte-altern-mit-ihrer-grenze.md) — nach der Verneinung suchen.
- [Verweis ins Leere](verweis-auf-nichtexistierendes.md) — liest sich so glatt wie ein gültiger.
- [Wächter sieht nur Getanes](waechter-sieht-nur-das-getane.md) — blind für das Framework.
- [Regel gilt weiter als gemeint](regel-gilt-weiter-als-gemeint.md) — richtige Regel, ungeprüfter Rand.
- [Wächter zählt das Falsche](waechter-zaehlt-das-falsche.md) — fragte „voll?" statt „was drin?".
- [Verkürzung ist eine Messung](jede-verkuerzung-ist-eine-messung.md) — `head`, `[:165]`, Kontextfenster, fehlende Wortgrenze.
- [Testprojekt trifft nicht](testprojekt-trifft-den-fall-nicht.md) — selbst gebaut enthält, was man hineinlegt.
- [Voraussetzung nur im Namen](voraussetzung-im-namen-statt-hergestellt.md) — fünf Korpusse formal sauber, unbrauchbar.
- [Gegenprobe bei neuer Bauart](gegenprobe-bei-geaenderter-bauart.md) — die Mutation baut die alte Bauart nach.
- [Zufall ist keine Zuordnung](zufallsziehung-ist-keine-zuordnung.md) — erst eine Verteilung ordnet zu.
- [Familie ≠ Auslöser](bekannte-familie-erklaert-nicht-den-ausloeser.md) — Gegenprobe auf dem Stand davor.
- [Verursacher wird gemessen](verursacher-wird-gemessen-nicht-gelesen.md) — `git show --stat` lesen.
- [Absturz-Frame](absturz-frame-ist-die-naechste-allokation.md) — wandert er, ist keine Stelle die Ursache.
- [Zwei Zeilen](zwei-zeilen-sind-nicht-die-funktion.md) — lesen, was mit dem Rückgabewert geschieht.
- [Versatz sieht aus wie viele Abweichungen](versatz-sieht-aus-wie-viele-abweichungen.md) — zwei Listen über den Index, eine hat einen Eintrag mehr; echte Abweichungen sind punktuell.
- [Suche prüft ihre Trefferzahl](suche-prueft-ihre-eigene-trefferzahl.md) — nichts getroffen sieht aus wie nichts da.
- [Gemessene Frage](gemessene-frage-ist-nicht-die-gestellte.md) — jede Suche antwortet auf ihre eigene.
- [Bestätigung verstärkt](bestaetigung-verstaerkt-die-fehlannahme.md) — zwei Messungen derselben falschen Frage.
- [Zahl beschreibt die Regel](zahl-beschreibt-die-regel-nicht-das-bild.md) — getComputedStyle liest den Basiswert.
- [Zustandswert widerlegt keinen Hänger](zustandswert-widerlegt-keinen-haenger.md) — nur eine Differenz trennt.
- [Exakte Passung ist kein Beweis](exakte-passung-ist-kein-beweis.md) — die Kette dahinter war erfunden.
- [Sondenbau](sondenbau.md) — im großen Lauf misst eine Sonde den Unterschied.
- [Hilfsmodul verstellt den Suchpfad](hilfsmodul-verstellt-den-suchpfad.md) — run_ui_audit setzt `F:\3D Druck` an sys.path[0]; der Fix sieht wirkungslos aus.
- [Mutation trifft nicht](mutation-die-den-fall-nicht-trifft.md) — grün heißt zuerst „die Probe griff nicht".
- [Messung trägt nur am Ort](messung-traegt-nur-am-ort-ihrer-messung.md) — echt gemessen, woanders gültig.
- [Gefahren ist nicht gefordert](gefahren-ist-nicht-gefordert.md) — der gemeinte Test hieß anders.
- [Fortschritt ≠ collect](fortschrittszeichen-zaehlen-nicht-wie-collect.md) — das n-te `F` ist nicht die n-te Zeile.
- [Vier Torläufe, ein Stand](vier-torlaeufe-ein-stand.md) — mypy davor, Suite danach; der Reexport fehlt beiden.
- [Prognose ohne Voraussetzung](prognose-ohne-gepruefte-voraussetzung.md) — „heilt später" braucht einen Heiler.
- [Fehlalarm zu mehreren](fehlalarm-den-mehrere-fuer-einen-halten.md) — verrechnet ist keine bloße Messung.
- [Beleg im eigenen Kontext](beleg-stand-im-eigenen-kontext.md) — erst suchen, dann eine Lücke behaupten.
- [Zusicherung wird stumpf](zusicherung-wird-stumpf-ohne-rot-zu-werden.md) — anderswo geändert, der Test bleibt grün.
- [Zahl im Fließtext](zahl-im-fliesstext-hat-begleiter.md) — daneben rechnet eine zweite mit.
- [Vorgabelage bricht fremde Tests](vorgabelage-bricht-fremde-tests.md) — 17 rot in 5 Dateien, keine vom Einlesen.
- [Abgelesene Zahl altert](abgelesene-zahl-altert-still.md) — stimmt nur in ihrer Entstehungslage.
- [Messung galt dem Stand davor](messung-galt-fuer-den-stand-davor.md) — nach dem Umbau ist sie über gestern.
- [Spanne ist keine Zahl](eine-spanne-ist-keine-zahl.md) — Vereinheitlichen frisst das Bewegliche.
- [Eigener Messfehler](eigener-messfehler-widerlegt-den-befund-nicht.md) — zwei getrennte Fragen.
- [Am Eingang drehen](am-eingang-drehen.md) — antwortet die Messung immer gleich, misst sie nichts.
- [Eingestellt ≠ Ergebnis](eingestellter-wert-ist-nicht-das-ergebnis.md) — `ch` ist nicht Zeichen, String nicht Bild.
- [Schwelle, falsche Achse](schwelle-misst-die-falsche-achse.md) — je schlimmer der Fall, desto stiller.
- [Benannte Falle schützt nicht](benannte-falle-schuetzt-nicht.md) — der Satz liest sich als Beleg.
- [Messwerkzeug misst sich selbst](messwerkzeug-misst-sich-selbst.md) — bis ein Fall mit bekanntem Ausgang es prüft.
- [Iterierte die Schlüssel](messung-iterierte-die-schluessel.md) — `for o in <dict>` gibt Schlüssel.
- [Wächter-Reichweite](waechter-reichweite-nur-im-kommentar.md) — der Kommentar zählte, was das Muster nie traf.
- [Wächter lesen Kommentare](waechter-lesen-kommentare-mit.md) — verbotene Muster nie zitieren.
- [Fünf Tests, eine Lage](fuenf-tests-eine-lage.md) — quer zur Achse sind sie einer.
- [Sollwert aus dem Prüfling](sollwert-aus-dem-pruefling.md) — prüft Aktualität statt Richtigkeit.
- [Rückbau kann scheitern](rueckbau-kann-scheitern.md) — `finally` garantiert den Lauf, nicht das Gelingen.
- [Fix macht nicht grün](fix-der-nicht-gruen-macht.md) — dann war die Diagnose falsch.
- [Schutz verliert ein Geschwister](schutz-verliert-ein-geschwister.md) — den alten Namen überall grepen.
- [Reparierter Fehler hat Zwillinge](reparierter-fehler-hat-zwillinge.md) — nach jedem Fix die Geschwister suchen.
- [Anker nach dem Formatierer](anker-nach-dem-formatierer.md) — ruff format bricht den Suchtext um; der Patch greift halb.
- [Halbe Regel sieht ganz aus](die-halbe-regel-sieht-aus-wie-eine-ganze.md) — Hauptwert geprüft, Nachbar nicht; ein Feld von sieben.
- [Der Nachbar findet den Fehler](der-nachbar-findet-den-fehler.md) — der eigene Blick folgt der Absicht.
- [Fremde Erklärung altert mit](fremde-erklaerung-altert-mit.md) — beim zweiten Mal prüfen, nicht erklären.
- [Leistungstests unter Fremdlast](leistungstests-fremdlast.md) — allein fahren, bevor man Regression glaubt.
- [rtree-Abstürze](rtree-abstuerze-im-langen-lauf.md) — die volle Suite stirbt; portionsweise fahren.
- [Native Bibliotheken](native-bibliotheken-speicher.md) — rtree, _elementtree, Abriss: eine Familie.
- [Gekillter Lauf schreibt weiter](gekillter-lauf-schreibt-weiter.md) — die Hülle überlebt; je Lauf ein Ordner.
- [Eigenen Lauf beenden](eigenen-lauf-ueber-die-elternkette-beenden.md) — eigener Prozessbaum, Blätter zuerst.

## Geteilter Baum und Shell

- [Parallele Sitzungen](parallele-sitzungen-solidon3d.md) — der Baum ändert sich mitten in der Sitzung.
- [Parallele Sitzung im Baum](parallele-sitzung-im-arbeitsbaum.md) — Fremdes aussortieren, privater Index.
- [Sitzung sendet ins Leere](sitzung-sendet-ohne-erreichbar-zu-sein.md) — der Kanal ist nicht beidseitig.
- [Git-Identität mitgeben](git-identitaet-mitgeben.md) — sonst Exit 128.
- [Erinnerungen im Repository](erinnerungen-liegen-im-repository.md) — neue Maschine: link_memory.py.
- [Geteilter Index hält Altes](geteilter-index-haelt-alten-stand.md) — committet Fremdes als gelöscht.
- [Index altert](index-altert-zwischen-lesen-und-commit.md) — Sorgfalt vergrößert das Fenster.
- [Sollprobe gegen eigenen Hash](sollprobe-liest-den-fremden-commit.md) — nie gegen HEAD.
- [Commit-Meldung ist geteilt](commit-meldung-ist-eine-geteilte-datei.md) — den Betreff der Ausgabe lesen.
- [Privater Index: fester Name](privater-index-fester-name.md) — `$$` zeigt beim nächsten Aufruf ins Leere.
- [Privater Index: Spuren](privater-index-hinterlaesst-spuren.md) — eine neue Datei steht danach als gelöscht.
- [`-o` nimmt den Dateistand](commit-o-nimmt-den-dateistand.md) — nicht den fremden Stand einer gemeinsamen Datei.
- [Blob-Commit verliert](blob-commit-verliert-den-wettlauf.md) — „cannot lock ref" heißt nicht passiert.
- [Patchskript schneidet Fremdes](patchskript-schneidet-fremdes-weg.md) — „ab Marke bis Ende" löscht den Nachbarn.
- [Sicherung ist Zeitmaschine](sicherung-ist-eine-zeitmaschine.md) — spielt den ganzen Stand von damals zurück.
- [Probe-Worktree altert](probe-worktree-altert.md) — gegen den aktuellen HEAD prüfen.
- [Sonde im geteilten Baum](sonde-im-geteilten-baum.md) — was den Bestand ändert, in einen eigenen Worktree.
- [Geteilter Baum: ein Zeitpunkt](geteilter-baum-misst-zeitpunkt.md) — `git diff HEAD` vorher.
- [Zeuge wird überschrieben](zeuge-wird-beim-messen-ueberschrieben.md) — vor jeder Wiederholung den Diff lesen.
- [Fremde Zwischenstände](fremde-zwischenstaende-verfaelschen-messungen.md) — erst den Zeitstempel der Datei lesen.
- [Probe mit Commits](probe-die-commits-erzeugt-schaltet-push-ab.md) — der post-commit läuft in jedem Worktree.
- [Deutscher Text nicht durch die Shell](deutscher-text-geht-nicht-durch-die-shell.md) — Write-Datei, `-F`; `!r`; newline beidseits.
