# Memory — Solidon3D (F:\3D Druck)

Verwandte Einträge stehen auf einer Zeile; jede Datei trägt ihre eigene Beschreibung.

## Diese Maschine

- [Privater Lizenzschlüssel](lizenz-privater-schluessel.md) · [Release-Schlüssel](release-schluessel-fuer-version-json.md) — gehören in den Passwortmanager; ohne Release-Schlüssel kein Update.
- [MSVC bei VS 18](msvc-erkennung-vs18.md) · [Inno Setup 7](inno-setup-7-nicht-ueber-winget.md) · [Installer-Probe](installer-probe-nicht-mit-fenster.md) — vcvars64.bat; signiert aus dem GitHub-Release; Robert klickt durch.
- [Webserver-Zugang](solidon3d-webserver-zugang.md) · [PHP lokal](php-lokal-fuer-die-gegenstelle.md) · [Website im Browser](website-im-browser-pruefen.md) — netcup-Stamm je Domain; support.php lokal; QtWebEngine.
- [Fusion ist da](zeichnen-an-fusion-orientieren.md) · [Slicer sind da](slicer-lokal-zum-gegenmessen.md) · [Live-Durchsicht 08/2026](live-durchsicht-solidon3d-2026-08.md) — Vergleichswerkzeuge lokal.
- [ComfyUI](comfyui-installation-d-ai.md) · [Eine Grafikkarte](lokale-ki-teilt-eine-grafikkarte.md) · [Ollama-Werkzeuge](ollama-werkzeugaufrufe-modellwahl.md) · [Agenten-Suite](agenten-suite-lauf-praxis.md) — D:\AI; VRAM serialisieren; num_ctx; ~1,5 h.
- [Config-Dir ohne Schalter](config-dir-hat-keinen-schalter.md) · [Scratchpad nicht dauerhaft](scratchpad-ist-nicht-dauerhaft.md) · [Sandbox ohne Eingabegeräte](sandbox-sieht-keine-eingabegeraete.md) — Sonden treffen Roberts echte Daten.
- [.venv auf 3.14.7](lokale-umgebung-python-version.md) · [.venv verliert Dateien](venv-dateien-verschwinden.md) — seit 06.09.2026 3.14; RECORD nennt die fehlende Datei.
- [Abgebrochener Lauf: Waisen](abgebrochener-lauf-hinterlaesst-waisen.md) · [Wartebedingung](wartebedingung-kennt-nur-einen-zustand.md) — Prozesse ohne Eltern; die Elternkette lügt nach einem Tod, nur die eigene Ausgabedatei beweist etwas; `until !` mit Umlaut meldet sofort.
- [make_manual ohne --help](make-manual-kennt-kein-help.md) · [commit-msg verlangt Umlaute](commit-msg-hook-verlangt-echte-umlaute.md) — jedes Argument erzeugt alles; ASCII bricht den Commit.

## Roberts Vorgaben

- [Aus Kundensicht perfekt](aus-kundensicht-perfekt.md) · [Fehlerzählung](zaehlung-eigener-fehler-ist-kein-kundennutzen.md) · [Version statt Fassung](kundentexte-sagen-version.md) · [Nicht nach KI klingen](nicht-nach-ki-klingen.md) — Kundentexte.
- [Hardware-Fenster acht Jahre](hardware-fenster-acht-jahre.md) · [Plattformen gleich](plattformen-funktionieren-gleich.md) — alte Karten kein Kriterium; was Windows kann, können Mac und Linux.
- [Beheben statt notieren](beheben-statt-notieren.md) · [Durchsicht je Version](durchsicht-je-version.md) · [Härtung trifft Altes](haertung-trifft-alten-zustand.md) — Fund → Messung → Fix → Test; „offen" am Code nachmessen.
- [Befund aus dem laufenden Fenster altert](befund-aus-dem-laufenden-fenster-altert.md) — sein Fenster trägt den Stand seines Starts; den Fall erst am HEAD nachstellen, dann bauen.
- [Nur das Nötigste](tests-und-rendern-nur-das-noetigste.md) · [Zwei Läufe](zwei-laeufe-nach-jeder-code-aenderung.md) · [Review vollständig](review-immer-vollstaendig.md) — affected_tests je Schritt, Tor vor dem Commit, jeden Diff lesen.
- [Push und Pull selbst](git-push-pull-selbststaendig.md) · [Version vor jedem Bau](version-vor-jedem-bau-erhoehen.md) — Merge, kein Rebase; bump_version.py.
- [Changelog vor dem Versionssprung](changelog-vor-dem-versionssprung.md) — Abschnitt zuerst, auch für unfertige Arbeit; die Version hebt erst der Bau.
- [Freies Gebiet](freies-gebiet-einfach-machen.md) · [Weitergabe: die Handlung entscheidet](weitergabe-die-handlung-entscheidet.md) — was frei ist, wird gemacht; nachgefragt wird nach der Grenze der Handlung, nicht nach dem Absender.
- [Übersetzung neu](uebersetzung-neu-statt-flicken.md) · [Weg nie bis zum Ende](weg-nie-bis-zum-ende-gemessen.md) — anhängen nur, wenn es für sich steht; zwölf Tag-Läufe, keine Ursache zweimal.
- [Mehrsitzungs-Setup ist ausgebaut](mehrsitzungs-setup-ist-ausgebaut.md) — Brett, Schloss, Worktree-Weg und privater Index sind am 09.09.2026 gefallen; nicht erneut vorschlagen.
- [Rechtemodus bleibt bypass](rechtemodus-bleibt-bypass.md) — die Umstellung auf `auto` ist am 04.09.2026 abgelehnt; nicht erneut vorschlagen.

## Produkt und Entscheidungen

- [Alexander Schneider](alexander-schneider-kunde-und-mac-tester.md) · [Ralph W. Dietrich](ralph-dietrich-mac-kunde-3d-maus.md) — SKÅDIS-Kunde; Mac-Zahntechniker (3D-Maus); Mac-Berichte stehen aus.
- [Vorstufe vor dem Slicer](solidon-ist-die-vorstufe-vor-dem-slicer.md) · [Technische Produktreife](technische-produktreife-konzept.md) · [Firmennutzung](marktwert-zielgruppe-und-firmenvalidierung.md) — Maker, Einmalkauf, ehrliche Übergabe.
- [Viewport: zwei Renderer messen](viewport-zwei-renderer-messen.md) — PyVista fällt; **GFX (pygfx) gewählt** (Robert, 06.09.2026), der VTK-Renderer ist ausgebaut.
- [Modellkette vor Freigabe](modellkette-vor-erzeugerfreigabe.md) · [KI-Hinweis sperrt](ki-hinweis-sperrt-den-ersten-modellaufruf.md) · [Kein Rechteübergang](neu-speichern-aendert-keine-urheberschaft.md) — TripoSG bleibt; je Modellgrenze; Provenienz bleibt.
- [Baustein je Sprache](baustein-begriff-je-sprache.md) · [Bausteinbereich ist Vertrag](bausteinbereich-ist-ein-produktionsvertrag.md) · [Generatorrahmen](generatorrahmen-ist-teil-der-sprache.md) — Begriffe und Rahmen je Sprache.
- [Gestellte Daten](gestellte-daten-widersprechen-echten-daneben.md) · [Beispielmaße](beispiel-masse-gegen-parameter-messen.md) · [Bündel erbt kein Ziel](ein-buendel-erbt-nicht-das-erste-ziel.md) — aus echten Läufen; je Mitglied prüfen.

## Paket, Release, Website

- [SBOM aus dem Artefakt](sbom-aus-dem-kundenartefakt.md) · [Lizenzmanifest neu bauen](lizenzmanifest-nach-grenzdatei-neu-bauen.md) · [Signierung getrennt](signierung-ist-ein-eigener-vertrauensraum.md) — Paketinhalt, Lizenzen, Signatur.
- [Download-Kasten](download-kasten-vier-pakete.md) · [Upload großer Dateien](website-upload-grosse-dateien.md) · [Datei ohne Manifest](datei-ohne-manifest-hat-keinen-pruefer.md) — vier Pakete; ~1,8 MB/s; AppImage ohne Prüfer.
- [Cache-Fehler](entwickler-sieht-den-cache-fehler-nie.md) · [Paketfix ≠ Anwendungsfix](paketfix-ist-kein-anwendungsfix.md) · [Behoben, nie draußen](behobener-fehler-war-nie-draussen.md) — Paket sieht anderes; `git tag --contains`.
- [Rechnung warnt](rechnung-warnt-sie-erlaubt-nicht.md) · [Prüfjob nur beim Tag](pruefjob-nur-beim-tag-hat-nie-gemessen.md) — was weg soll, wird benannt; einmal über ein echtes Paket fahren.
- [mypy prüft die Plattform](mypy-prueft-die-laufende-plattform.md) · [Zusage über die Umgebung](zusage-ueber-die-umgebung.md) · [Prüfstand nutzt Windows-Bordmittel](pruefstand-nutzt-windows-bordmittel.md) — Windows-Tor und Linux-CI sehen anderes; Git-bash ist keine sh, socketpair kein AF_UNIX.
- [Datei zuerst, Register danach](datei-zuerst-register-danach.md) · [Erzeugte Datei](erzeugte-datei-fuehrt-ins-fremde-werkzeug.md) — atomar veröffentlichen; Antwort im fremden Werkzeug.

## Qt, VTK, Oberfläche

- [VTK/Qt-Referenzen](vtk-qt-referenzen-halten-zu-lange.md) · [Verwaiste Widgets](verwaiste-widgets-sterben-im-falschen-moment.md) · [Prüfstand misst zu früh](qt-pruefstand-misst-zu-frueh.md) — wer hält; gc.disable; DeferredDelete.
- [Renderfenster 160x160](renderfenster-bleibt-briefmarkengross.md) · [VTK sagt ja, tut nichts](vtk-sagt-ja-und-tut-nichts.md) — Bildpunkte messen die Umgebung; Picker und Depth Peeling laufen nie.
- [Qt lügt vor dem Anzeigen](qt-luegt-vor-dem-anzeigen.md) · [Gesetzt ≠ gezeigt](text-gesetzt-heisst-nicht-gezeigt.md) · [Suite ohne Stylesheet](suite-faehrt-ohne-stylesheet.md) — isVisible, Tooltips, Farben nur am Fenster.
- [Signal am falschen Slot](signal-passt-an-den-falschen-slot.md) · [Warnungsmarke ist Zustand](warnungsmarke-ist-semantischer-zustand.md) · [Zweite Stelle setzt dieselbe Sichtbarkeit](zweite-stelle-setzt-dieselbe-sichtbarkeit.md) — Stelligkeit; Aktoren überleben keinen Szenenaufbau; wer wieder einblendet, überschreibt jeden, der ausgeblendet hat.
- [Kalenderdatum](kalenderdatum-folgt-appsprache.md) · [Sprachwechsel](sprachwechsel-zwei-schritte.md) · [Katalogschlüssel](katalog-schluessel-sind-woerter.md) · [Marke im span](marke-im-span-zerteilt.md) — Sprache und Kataloge.
- [Startfläche](startflaeche-braucht-breite-und-skalierung.md) · [Oberfläche von Hand](oberflaeche-von-hand-fahren.md) · [Klickweg](pruefstand-geht-den-weg-der-oberflaeche.md) — echte Plattform, Klickweg, Skalierung.
- [Fehlertexte ohne Platzhalter](fehlertexte-ohne-platzhalter.md) · [Fehlertexte nur Titel](fehlertexte-nur-titel.md) · [Session.apply meldet](session-apply-meldet-statt-zu-werfen.md) — Titel, detail, Signal statt try.
- [Ops am Stück](ops-reihendurchlauf-kundensicht.md) · [Register zählen](register-zaehlen-load-operations.md) · [Rezept ist der Fund](rezept-ist-der-fund-op-ist-die-ursache.md) — load_operations(); Prüfung in der Op.
- [Knopf und Handlung](knopf-und-handlung-fragen-verschieden.md) · [Reparatur vor den Fehler](reparatur-muss-vor-den-fehler.md) · [Kette endet am letzten Glied](eine-kette-endet-am-letzten-glied.md) — Klickketten bis zum Ende.
- [Architektur-Sonde](architektur-sonde-type-checking.md) — TYPE_CHECKING ausschließen; Kernänderung = Suite.

## Messen und Prüfen

- [Saubere Messung, falsche Frage](saubere-messung-falsche-frage.md) · [Gemessene Frage](gemessene-frage-ist-nicht-die-gestellte.md) · [Bestätigung verstärkt](bestaetigung-verstaerkt-die-fehlannahme.md) · [Am Eingang drehen](am-eingang-drehen.md) — jede Messung antwortet auf ihre eigene Frage.
- [Was die Suite nicht findet](was-die-suite-nicht-findet.md) · [Lehre schützt ihre Gestalt](lehre-schuetzt-nur-ihre-eigene-gestalt.md) · [Benannte Falle](benannte-falle-schuetzt-nicht.md) · [Geprüft fühlt sich wie vollständig an](geprueft-fuehlt-sich-wie-vollstaendig-an.md) — ansehen, mutieren; Notiz gekannt, Fehler gemacht; die geprüfte Hälfte deckt die andere.
- [Begrenzt am falschen Maß](begrenzt-am-falschen-mass.md) · [Schranke aus einem Messwert](schranke-aus-einem-messwert-ist-geraten.md) · [Zwei Schwellen](zwei-schwellen-eine-frage.md) · [Schwelle, falsche Achse](schwelle-misst-die-falsche-achse.md) — Grenzen.
- [Roh gegen gerendert](roh-gegen-gerendert-vergleichen.md) · [Zahl beschreibt die Regel](zahl-beschreibt-die-regel-nicht-das-bild.md) · [Eingestellt ≠ Ergebnis](eingestellter-wert-ist-nicht-das-ergebnis.md) — das Bild misst, nicht der Wert.
- [Texte altern mit ihrer Grenze](texte-altern-mit-ihrer-grenze.md) · [Verweis ins Leere](verweis-auf-nichtexistierendes.md) · [Docstring, ungefahrener Weg](docstring-nennt-den-weg-den-der-test-nicht-faehrt.md) · [Zwei Dinge, eines geprüft](zwei-dinge-nur-eines-geprueft.md) — Texte.
- [Wächter sieht nur Getanes](waechter-sieht-nur-das-getane.md) · [Regel gilt weiter](regel-gilt-weiter-als-gemeint.md) · [Wächter zählt das Falsche](waechter-zaehlt-das-falsche.md) · [Wächter-Reichweite](waechter-reichweite-nur-im-kommentar.md) · [Wächter lesen Kommentare](waechter-lesen-kommentare-mit.md) — Wächter.
- [Verkürzung ist Messung](jede-verkuerzung-ist-eine-messung.md) · [Suche prüft Trefferzahl](suche-prueft-ihre-eigene-trefferzahl.md) · [Iterierte die Schlüssel](messung-iterierte-die-schluessel.md) · [Versatz sieht aus wie viele](versatz-sieht-aus-wie-viele-abweichungen.md) — Suchen.
- [Testprojekt trifft nicht](testprojekt-trifft-den-fall-nicht.md) · [Voraussetzung nur im Namen](voraussetzung-im-namen-statt-hergestellt.md) · [Nachstellung](pruefstand-misst-seine-nachstellung.md) · [Sollwert aus dem Prüfling](sollwert-aus-dem-pruefling.md) — Testbau.
- [Attrappenwert = Rückfallwert](attrappenwert-gleich-rueckfallwert.md) — eine Attrappe, die zufällig den Rückfall des Prüflings trifft, macht die Gegenprobe blind.
- [Gegenprobe bei neuer Bauart](gegenprobe-bei-geaenderter-bauart.md) · [Mutation trifft nicht](mutation-die-den-fall-nicht-trifft.md) · [Fix macht nicht grün](fix-der-nicht-gruen-macht.md) · [Test auf Abwesenheit](test-der-eine-abwesenheit-festschreibt.md) — Mutation.
- [Familie ≠ Auslöser](bekannte-familie-erklaert-nicht-den-ausloeser.md) · [Verursacher wird gemessen](verursacher-wird-gemessen-nicht-gelesen.md) · [Welche Bedingung allein](welche-bedingung-entscheidet-allein.md) · [Zufall ≠ Zuordnung](zufallsziehung-ist-keine-zuordnung.md) — Ursache.
- [Absturz-Frame](absturz-frame-ist-die-naechste-allokation.md) · [Speicherriss ohne Zeile](speicherriss-hat-keine-ausloesende-zeile.md) · [rtree-Abstürze](rtree-abstuerze-im-langen-lauf.md) · [Native Bibliotheken](native-bibliotheken-speicher.md) — Abrisse: eine Familie.
- [Zwei Zeilen](zwei-zeilen-sind-nicht-die-funktion.md) · [Exakte Passung](exakte-passung-ist-kein-beweis.md) · [Zustandswert](zustandswert-widerlegt-keinen-haenger.md) · [Beleg im eigenen Kontext](beleg-stand-im-eigenen-kontext.md) — Code lesen.
- [any misst den Rand](any-ueber-einen-flicken-misst-den-rand.md) · [Periode antwortet auf Teiler](periodizitaet-antwortet-auch-auf-teiler.md) · [Form festhalten](form-festhalten-eine-achse-variieren.md) · [Spanne ≠ Zahl](eine-spanne-ist-keine-zahl.md) — Flächen, Reihen.
- [Sondenbau](sondenbau.md) · [Hilfsmodul verstellt Suchpfad](hilfsmodul-verstellt-den-suchpfad.md) · [Messwerkzeug misst sich selbst](messwerkzeug-misst-sich-selbst.md) · [Eigener Messfehler](eigener-messfehler-widerlegt-den-befund-nicht.md) · [Gefilterte Ansicht zeigt keine Zugehörigkeit](gefilterte-codeansicht-zeigt-keine-zugehoerigkeit.md) — Sonden; ein Filter darf einen Block finden, nie über seinen Kontrollfluss entscheiden.
- [Gefahren ≠ gefordert](gefahren-ist-nicht-gefordert.md) · [Fortschritt ≠ collect](fortschrittszeichen-zaehlen-nicht-wie-collect.md) · [Hintergrundlauf meldet Hülle](hintergrundlauf-meldet-seinen-wrapper.md) · [Vier Torläufe](vier-torlaeufe-ein-stand.md) · [Ausschlussliste mit CR](ausschlussliste-mit-wagenruecklauf.md) — Läufe und Exit-Codes; ein 
 im --ignore ignoriert nichts.
- [Messung nur am Ort](messung-traegt-nur-am-ort-ihrer-messung.md) · [Abgelesene Zahl altert](abgelesene-zahl-altert-still.md) · [Stand davor](messung-galt-fuer-den-stand-davor.md) · [Zahl im Fließtext](zahl-im-fliesstext-hat-begleiter.md) — Zahlen altern.
- [Prognose ohne Voraussetzung](prognose-ohne-gepruefte-voraussetzung.md) · [Fehlalarm zu mehreren](fehlalarm-den-mehrere-fuer-einen-halten.md) · [Zusicherung wird stumpf](zusicherung-wird-stumpf-ohne-rot-zu-werden.md) · [Zusage nur in der Oberfläche](zusage-die-nur-die-oberflaeche-einloest.md) — Zusagen.
- [Vorgabelage bricht Tests](vorgabelage-bricht-fremde-tests.md) · [Fünf Tests, eine Lage](fuenf-tests-eine-lage.md) · [Leistungstests unter Fremdlast](leistungstests-fremdlast.md) · [Erzeugtes nicht in der CI](erzeugtes-laeuft-nicht-in-der-ci.md) — die Lage, in der gemessen wird, gehört zum Messwert.
- [Rückbau kann scheitern](rueckbau-kann-scheitern.md) · [Schutz verliert Geschwister](schutz-verliert-ein-geschwister.md) · [Fehler hat Zwillinge](reparierter-fehler-hat-zwillinge.md) · [Anker nach dem Formatierer](anker-nach-dem-formatierer.md) — nach dem Fix.
- [Halbe Regel sieht ganz aus](die-halbe-regel-sieht-aus-wie-eine-ganze.md) · [Der Nachbar findet den Fehler](der-nachbar-findet-den-fehler.md) — der eigene Blick folgt der Absicht.
- [Gekillter Lauf schreibt weiter](gekillter-lauf-schreibt-weiter.md) · [Schreibfehler auf Datei](schreibfehler-auf-eine-vorhandene-datei.md) · [Eigenen Lauf beenden](eigenen-lauf-ueber-die-elternkette-beenden.md) · [Hintergrundlauf stirbt mit der Sitzung](hintergrundlauf-stirbt-mit-der-sitzung.md) — je Lauf ein Ordner; OSError 22/13; Blätter zuerst; lange Läufe abkoppeln.
- [Zweite Sitzung im selben Baum](zweite-sitzung-im-selben-baum.md) — vor Kill und Torlauf prüfen, wem was gehört; wer während eines Tors schreibt, macht es wertlos.

## Shell und Git

- [Deutscher Text nicht durch die Shell](deutscher-text-geht-nicht-durch-die-shell.md) — Write-Datei, `-F`; `!r`; newline beidseits.
- [Kette mit ; läuft nach dem Kill weiter](kette-mit-semikolon-laeuft-nach-dem-kill-weiter.md) · [Agent-Edits schreiben CRLF](agent-edits-schreiben-crlf.md) — erst den Wrapper beenden, `&&` statt `;`; nach jedem Prosa-Durchgang `git diff --stat` auf CRLF-Warnungen lesen, AST-Vergleich sagt „nur Prosa“.
- [Git-Identität](git-identitaet-mitgeben.md) · [Erinnerungen im Repository](erinnerungen-liegen-im-repository.md) — Exit 128 ohne Autor; link_memory.py hängt das Gedächtnis ins Repository.
- [Katalogschreiber überschreibt still](katalogschreiber-ueberschreibt-still.md) — `git diff HEAD --numstat` vor dem Commit; jede Zahl in der zweiten Spalte ist ein überschriebener Eintrag.
- [Heredoc frisst den Backslash](heredoc-frisst-den-backslash.md) — ein `\n` darin wird zum echten Umbruch; Skript als Datei ablegen.
