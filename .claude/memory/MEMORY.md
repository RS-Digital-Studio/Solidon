# Memory — Solidon3D (F:\3D Druck)

## Diese Maschine

- [Privater Lizenzschlüssel](lizenz-privater-schluessel.md) · [Release-Schlüssel](release-schluessel-fuer-version-json.md) — Passwortmanager; ohne Release-Schlüssel kein Update.
- [MSVC bei VS 18](msvc-erkennung-vs18.md) · [Inno Setup 7](inno-setup-7-nicht-ueber-winget.md) · [Installer-Probe](installer-probe-nicht-mit-fenster.md) — vcvars64; signiert aus dem Release; Robert klickt.
- [Webserver-Zugang](solidon3d-webserver-zugang.md) · [PHP lokal](php-lokal-fuer-die-gegenstelle.md) · [Website im Browser](website-im-browser-pruefen.md) — netcup; support.php lokal; QtWebEngine.
- [Fusion ist da](zeichnen-an-fusion-orientieren.md) · [Slicer sind da](slicer-lokal-zum-gegenmessen.md) · [Live-Durchsicht 08/2026](live-durchsicht-solidon3d-2026-08.md) · [Downloads als Korpus](downloads-ordner-als-3mf-korpus.md) — lokal; Downloads als Korpus.
- [ComfyUI](comfyui-installation-d-ai.md) · [Eine Grafikkarte](lokale-ki-teilt-eine-grafikkarte.md) · [Ollama-Werkzeuge](ollama-werkzeugaufrufe-modellwahl.md) · [Ollama verwirft Schemafelder](ollama-verwirft-schema-felder.md) · [Agenten-Suite](agenten-suite-lauf-praxis.md) — D:\AI; VRAM; num_ctx; ~1,5 h.
- [Config-Dir ohne Schalter](config-dir-hat-keinen-schalter.md) · [Scratchpad nicht dauerhaft](scratchpad-ist-nicht-dauerhaft.md) · [Sandbox ohne Eingabegeräte](sandbox-sieht-keine-eingabegeraete.md) — Sonden treffen echte Daten.
- [.venv auf 3.14.7](lokale-umgebung-python-version.md) · [.venv verliert Dateien](venv-dateien-verschwinden.md) · [Abgebrochener Lauf: Waisen](abgebrochener-lauf-hinterlaesst-waisen.md) · [Wartebedingung](wartebedingung-kennt-nur-einen-zustand.md) — RECORD; nur die eigene Ausgabedatei beweist etwas.
- [Handbuch nur beim Paketbau](handbuch-nur-beim-paketbau.md) · [Release-Weg 0.4.1](release-weg-0-4-1-gemessen.md) · [make_manual ohne --help](make-manual-kennt-kein-help.md) · [commit-msg verlangt Umlaute](commit-msg-hook-verlangt-echte-umlaute.md) — test_wording dazwischen rot.

## Roberts Vorgaben

- [Kurze Texte in der App](kurze-texte-in-der-app.md) · [Aus Kundensicht perfekt](aus-kundensicht-perfekt.md) · [Fehlerzählung](zaehlung-eigener-fehler-ist-kein-kundennutzen.md) · [Version statt Fassung](kundentexte-sagen-version.md) · [Nicht nach KI klingen](nicht-nach-ki-klingen.md)
- [Hardware-Fenster acht Jahre](hardware-fenster-acht-jahre.md) · [Plattformen gleich](plattformen-funktionieren-gleich.md) · [ARM rechnet anders](arm-rechnet-anders-als-x86.md) — Mac-CI ist ARM64.
- [Beheben statt notieren](beheben-statt-notieren.md) · [Durchsicht je Version](durchsicht-je-version.md) · [Härtung trifft Altes](haertung-trifft-alten-zustand.md) · [Befund altert](befund-aus-dem-laufenden-fenster-altert.md) — Fund → Fix → Test; am HEAD nachstellen.
- [Nur das Nötigste](tests-und-rendern-nur-das-noetigste.md) · [Zwei Läufe](zwei-laeufe-nach-jeder-code-aenderung.md) · [Review vollständig](review-immer-vollstaendig.md) — affected_tests je Schritt.
- [Push und Pull selbst](git-push-pull-selbststaendig.md) · [Version vor jedem Bau](version-vor-jedem-bau-erhoehen.md) · [Changelog vor dem Sprung](changelog-vor-dem-versionssprung.md) · [Wächter nach dem Sprung](changelog-waechter-nach-dem-versionssprung.md) · [Kein zweites Tor vor dem Tag](kein-zweites-tor-vor-dem-tag.md) — Merge, kein Rebase; bump_version; direkt taggen.
- [Serverstand sofort prüfen](serverstand-sofort-selbst-pruefen.md) · [Freies Gebiet](freies-gebiet-einfach-machen.md) · [Weitergabe: die Handlung](weitergabe-die-handlung-entscheidet.md) — messen statt fragen.
- [Übersetzung neu](uebersetzung-neu-statt-flicken.md) · [Weg nie bis zum Ende](weg-nie-bis-zum-ende-gemessen.md) · [Mehrsitzungs-Setup ausgebaut](mehrsitzungs-setup-ist-ausgebaut.md) · [Rechtemodus bleibt bypass](rechtemodus-bleibt-bypass.md) — nicht erneut vorschlagen.

## Produkt und Entscheidungen

- [Alexander Schneider](alexander-schneider-kunde-und-mac-tester.md) · [Ralph W. Dietrich](ralph-dietrich-mac-kunde-3d-maus.md) — Kunden; Mac-Berichte stehen aus.
- [Verkaufsphase und Demo-Zahlen](verkaufsphase-preise-und-demo-zahlen.md) — 69/199/249 €; 5000 Besucher, 1700 Downloads seit 23.08.
- [Vorstufe vor dem Slicer](solidon-ist-die-vorstufe-vor-dem-slicer.md) · [Technische Produktreife](technische-produktreife-konzept.md) · [Firmennutzung](marktwert-zielgruppe-und-firmenvalidierung.md) — Maker, Einmalkauf.
- [Viewport: zwei Renderer](viewport-zwei-renderer-messen.md) — GFX (pygfx) gewählt, VTK ausgebaut.
- [Modellkette vor Freigabe](modellkette-vor-erzeugerfreigabe.md) · [KI-Hinweis sperrt](ki-hinweis-sperrt-den-ersten-modellaufruf.md) · [Kein Rechteübergang](neu-speichern-aendert-keine-urheberschaft.md) — TripoSG; Provenienz bleibt.
- [Baustein je Sprache](baustein-begriff-je-sprache.md) · [Bausteinbereich ist Vertrag](bausteinbereich-ist-ein-produktionsvertrag.md) · [Generatorrahmen](generatorrahmen-ist-teil-der-sprache.md) — Begriffe je Sprache.
- [Gestellte Daten](gestellte-daten-widersprechen-echten-daneben.md) · [Beispielmaße](beispiel-masse-gegen-parameter-messen.md) · [Bündel erbt kein Ziel](ein-buendel-erbt-nicht-das-erste-ziel.md) — je Mitglied prüfen.

## Paket, Release, Website

- [SBOM aus dem Artefakt](sbom-aus-dem-kundenartefakt.md) · [Lizenzmanifest neu bauen](lizenzmanifest-nach-grenzdatei-neu-bauen.md) · [Signierung getrennt](signierung-ist-ein-eigener-vertrauensraum.md)
- [Download-Kasten](download-kasten-vier-pakete.md) · [Upload großer Dateien](website-upload-grosse-dateien.md) · [Datei ohne Manifest](datei-ohne-manifest-hat-keinen-pruefer.md) — fünf Pakete; ~1,8 MB/s.
- [Cache-Fehler](entwickler-sieht-den-cache-fehler-nie.md) · [Paketfix ≠ Anwendungsfix](paketfix-ist-kein-anwendungsfix.md) · [Behoben, nie draußen](behobener-fehler-war-nie-draussen.md) — `git tag --contains`.
- [Rechnung warnt](rechnung-warnt-sie-erlaubt-nicht.md) · [Prüfjob nur beim Tag](pruefjob-nur-beim-tag-hat-nie-gemessen.md) — ein echtes Paket fahren.
- [mypy prüft die Plattform](mypy-prueft-die-laufende-plattform.md) · [Zusage über die Umgebung](zusage-ueber-die-umgebung.md) · [Windows-Bordmittel](pruefstand-nutzt-windows-bordmittel.md) — Git-bash ist keine sh.
- [Datei zuerst, Register danach](datei-zuerst-register-danach.md) · [Erzeugte Datei](erzeugte-datei-fuehrt-ins-fremde-werkzeug.md) — atomar veröffentlichen.

## Qt, VTK, Oberfläche

- [VTK/Qt-Referenzen](vtk-qt-referenzen-halten-zu-lange.md) · [Verwaiste Widgets](verwaiste-widgets-sterben-im-falschen-moment.md) · [Prüfstand misst zu früh](qt-pruefstand-misst-zu-frueh.md) — gc.disable; DeferredDelete.
- [Renderfenster 160x160](renderfenster-bleibt-briefmarkengross.md) · [VTK sagt ja, tut nichts](vtk-sagt-ja-und-tut-nichts.md) — Picker läuft nie.
- [Qt lügt vor dem Anzeigen](qt-luegt-vor-dem-anzeigen.md) · [Gesetzt ≠ gezeigt](text-gesetzt-heisst-nicht-gezeigt.md) · [Suite ohne Stylesheet](suite-faehrt-ohne-stylesheet.md) — nur am Fenster messen.
- [Signal am falschen Slot](signal-passt-an-den-falschen-slot.md) · [weak_slot verwirft Signalargumente](weak-slot-verwirft-signalargumente.md) · [Warnungsmarke ist Zustand](warnungsmarke-ist-semantischer-zustand.md) · [Zweite Stelle setzt Sichtbarkeit](zweite-stelle-setzt-dieselbe-sichtbarkeit.md) — Stelligkeit; ohne `forward=True` kein Argument.
- [Kalenderdatum](kalenderdatum-folgt-appsprache.md) · [QDateEdit-Sonderwert](qdateedit-sonderwert-schluckt-die-eingabe.md) · [Sprachwechsel](sprachwechsel-zwei-schritte.md) · [Katalogschlüssel](katalog-schluessel-sind-woerter.md) · [Marke im span](marke-im-span-zerteilt.md) — Sprache und Kataloge.
- [Startfläche](startflaeche-braucht-breite-und-skalierung.md) · [Oberfläche von Hand](oberflaeche-von-hand-fahren.md) · [Klickweg](pruefstand-geht-den-weg-der-oberflaeche.md) · [Sonde baut wie die Anwendung](sonde-baut-das-fenster-wie-die-anwendung.md) — echte Plattform.
- [Fehlertexte ohne Platzhalter](fehlertexte-ohne-platzhalter.md) · [Fehlertexte nur Titel](fehlertexte-nur-titel.md) · [Session.apply meldet](session-apply-meldet-statt-zu-werfen.md) — Titel, detail, Signal statt try.
- [Ops am Stück](ops-reihendurchlauf-kundensicht.md) · [Register zählen](register-zaehlen-load-operations.md) · [Rezept ist der Fund](rezept-ist-der-fund-op-ist-die-ursache.md) · [Arbeiter verlegt die Wartezeit](arbeiter-verlegt-die-wartezeit-ans-ende.md) — load_operations(); zwei Enden.
- [Knopf und Handlung](knopf-und-handlung-fragen-verschieden.md) · [Reparatur vor den Fehler](reparatur-muss-vor-den-fehler.md) · [Kette endet am letzten Glied](eine-kette-endet-am-letzten-glied.md) · [Architektur-Sonde](architektur-sonde-type-checking.md) — Klickketten bis zum Ende.

## Messen und Prüfen

- [Nachricht ist ein Satzende](nachricht-ist-ein-satzende.md) · [Prüfstand ohne Profil](pruefstand-ohne-profil-meldet-fremden-fehler.md) — Anfang holen; Bedienweg ganz.
- [Saubere Messung, falsche Frage](saubere-messung-falsche-frage.md) · [Gemessene Frage](gemessene-frage-ist-nicht-die-gestellte.md) · [Bestätigung verstärkt](bestaetigung-verstaerkt-die-fehlannahme.md) · [Am Eingang drehen](am-eingang-drehen.md) — jede Messung hat ihre eigene Frage.
- [Was die Suite nicht findet](was-die-suite-nicht-findet.md) · [Lehre schützt ihre Gestalt](lehre-schuetzt-nur-ihre-eigene-gestalt.md) · [Benannte Falle](benannte-falle-schuetzt-nicht.md) · [Geprüft fühlt sich vollständig an](geprueft-fuehlt-sich-wie-vollstaendig-an.md) — ansehen, mutieren.
- [Begrenzt am falschen Maß](begrenzt-am-falschen-mass.md) · [Schranke aus einem Messwert](schranke-aus-einem-messwert-ist-geraten.md) · [Obergrenze ≠ Zusicherung](obergrenze-ist-keine-zusicherung.md) · [Zwei Schwellen](zwei-schwellen-eine-frage.md) · [Schwelle, falsche Achse](schwelle-misst-die-falsche-achse.md) — Grenzen.
- [Roh gegen gerendert](roh-gegen-gerendert-vergleichen.md) · [Zahl beschreibt die Regel](zahl-beschreibt-die-regel-nicht-das-bild.md) · [Eingestellt ≠ Ergebnis](eingestellter-wert-ist-nicht-das-ergebnis.md) — das Bild misst.
- [Texte altern](texte-altern-mit-ihrer-grenze.md) · [Verweis ins Leere](verweis-auf-nichtexistierendes.md) · [Docstring, ungefahrener Weg](docstring-nennt-den-weg-den-der-test-nicht-faehrt.md) · [Zwei Dinge, eines geprüft](zwei-dinge-nur-eines-geprueft.md)
- [Wächter sieht nur Getanes](waechter-sieht-nur-das-getane.md) · [Regel gilt weiter](regel-gilt-weiter-als-gemeint.md) · [Wächter zählt das Falsche](waechter-zaehlt-das-falsche.md) · [Wächter-Reichweite](waechter-reichweite-nur-im-kommentar.md) · [Wächter lesen Kommentare](waechter-lesen-kommentare-mit.md)
- [Verkürzung ist Messung](jede-verkuerzung-ist-eine-messung.md) · [Suche prüft Trefferzahl](suche-prueft-ihre-eigene-trefferzahl.md) · [Iterierte die Schlüssel](messung-iterierte-die-schluessel.md) · [Versatz sieht aus wie viele](versatz-sieht-aus-wie-viele-abweichungen.md) — Suchen.
- [Testprojekt trifft nicht](testprojekt-trifft-den-fall-nicht.md) · [Voraussetzung nur im Namen](voraussetzung-im-namen-statt-hergestellt.md) · [Nachstellung](pruefstand-misst-seine-nachstellung.md) · [Sollwert aus dem Prüfling](sollwert-aus-dem-pruefling.md) — Testbau.
- [Eigene Toleranz, fremde Netze](eigene-toleranz-gilt-nicht-fuer-fremde-netze.md) · [Attrappenwert = Rückfallwert](attrappenwert-gleich-rueckfallwert.md) — Siebhalter+X1C.3mf.
- [Gegenprobe bei neuer Bauart](gegenprobe-bei-geaenderter-bauart.md) · [Mutation trifft nicht](mutation-die-den-fall-nicht-trifft.md) · [Fix macht nicht grün](fix-der-nicht-gruen-macht.md) · [Test auf Abwesenheit](test-der-eine-abwesenheit-festschreibt.md) — Mutation.
- [Familie ≠ Auslöser](bekannte-familie-erklaert-nicht-den-ausloeser.md) · [Verursacher wird gemessen](verursacher-wird-gemessen-nicht-gelesen.md) · [Welche Bedingung allein](welche-bedingung-entscheidet-allein.md) · [Zufall ≠ Zuordnung](zufallsziehung-ist-keine-zuordnung.md) — Ursache.
- [Ungenutzter Import reißt](ungenutzter-import-reisst-den-prozess.md) · [Absturz-Frame](absturz-frame-ist-die-naechste-allokation.md) · [Speicherriss ohne Zeile](speicherriss-hat-keine-ausloesende-zeile.md) · [rtree-Abstürze](rtree-abstuerze-im-langen-lauf.md) · [Native Bibliotheken](native-bibliotheken-speicher.md) · [ast.walk reißt](ast-walk-reisst-im-torlauf.md) — Abrisse.
- [Zwei Zeilen](zwei-zeilen-sind-nicht-die-funktion.md) · [Exakte Passung](exakte-passung-ist-kein-beweis.md) · [Zustandswert](zustandswert-widerlegt-keinen-haenger.md) · [Beleg im eigenen Kontext](beleg-stand-im-eigenen-kontext.md) — Code lesen.
- [Unbelegter Rand ist nicht scharf](unbelegter-rand-ist-nicht-scharf.md) — „jede Naht ist scharf“ über face_adjacency besteht leer, wo eine STL T-Stöße hat; Kantenzahl gegenzählen, am Korpus messen.
- [any misst den Rand](any-ueber-einen-flicken-misst-den-rand.md) · [Periode antwortet auf Teiler](periodizitaet-antwortet-auch-auf-teiler.md) · [Form festhalten](form-festhalten-eine-achse-variieren.md) · [Spanne ≠ Zahl](eine-spanne-ist-keine-zahl.md) — Flächen, Reihen.
- [Sonde über alle Operationen](sonde-ueber-alle-operationen.md) · [Sondenbau](sondenbau.md) · [Hilfsmodul verstellt Suchpfad](hilfsmodul-verstellt-den-suchpfad.md) · [Messwerkzeug misst sich selbst](messwerkzeug-misst-sich-selbst.md) · [Eigener Messfehler](eigener-messfehler-widerlegt-den-befund-nicht.md) · [Gefilterte Ansicht](gefilterte-codeansicht-zeigt-keine-zugehoerigkeit.md) — Sonden.
- [Gefahren ≠ gefordert](gefahren-ist-nicht-gefordert.md) · [Fortschritt ≠ collect](fortschrittszeichen-zaehlen-nicht-wie-collect.md) · [Hintergrundlauf meldet Hülle](hintergrundlauf-meldet-seinen-wrapper.md) · [Vier Torläufe](vier-torlaeufe-ein-stand.md) · [Ausschlussliste mit CR](ausschlussliste-mit-wagenruecklauf.md) — Läufe und Exit-Codes.
- [Messung nur am Ort](messung-traegt-nur-am-ort-ihrer-messung.md) · [Abgelesene Zahl altert](abgelesene-zahl-altert-still.md) · [Stand davor](messung-galt-fuer-den-stand-davor.md) · [Zahl im Fließtext](zahl-im-fliesstext-hat-begleiter.md) — Zahlen altern.
- [Prognose ohne Voraussetzung](prognose-ohne-gepruefte-voraussetzung.md) · [Fehlalarm zu mehreren](fehlalarm-den-mehrere-fuer-einen-halten.md) · [Zusicherung wird stumpf](zusicherung-wird-stumpf-ohne-rot-zu-werden.md) · [Zusage nur in der Oberfläche](zusage-die-nur-die-oberflaeche-einloest.md) — Zusagen.
- [Vorgabelage bricht Tests](vorgabelage-bricht-fremde-tests.md) · [Fünf Tests, eine Lage](fuenf-tests-eine-lage.md) · [Leistungstests unter Fremdlast](leistungstests-fremdlast.md) · [Erzeugtes nicht in der CI](erzeugtes-laeuft-nicht-in-der-ci.md) — die Lage gehört zum Messwert.
- [Rückbau kann scheitern](rueckbau-kann-scheitern.md) · [Schutz verliert Geschwister](schutz-verliert-ein-geschwister.md) · [Fehler hat Zwillinge](reparierter-fehler-hat-zwillinge.md) · [Anker nach dem Formatierer](anker-nach-dem-formatierer.md) — nach dem Fix.
- [Halbe Regel sieht ganz aus](die-halbe-regel-sieht-aus-wie-eine-ganze.md) · [Der Nachbar findet den Fehler](der-nachbar-findet-den-fehler.md) · [Regel gilt je Bedienort](regel-gilt-je-bedienort.md) · [Zwei Wünsche, eine Taste](zwei-wuensche-eine-taste-die-lage-entscheidet.md) · [Warnung ist keine Wirkung](warnung-ist-keine-wirkung.md) — jeden Ort einmal fahren.
- [Gekillter Lauf schreibt weiter](gekillter-lauf-schreibt-weiter.md) · [Schreibfehler auf Datei](schreibfehler-auf-eine-vorhandene-datei.md) · [Eigenen Lauf beenden](eigenen-lauf-ueber-die-elternkette-beenden.md) · [Hintergrundlauf stirbt mit der Sitzung](hintergrundlauf-stirbt-mit-der-sitzung.md) — je Lauf ein Ordner.
- [Suite abgekoppelt starten](suite-abgekoppelt-per-pwsh-start-process.md) · [$args als Parametername](powershell-args-als-parametername.md) · [Zweite Sitzung im selben Baum](zweite-sitzung-im-selben-baum.md) — pwsh Start-Process.
- [Teardown-Riss bei gewählter Fläche](teardown-riss-bei-gewaehlter-flaeche.md) · [Leere Transkriptdatei ist kein Hänger](leere-transkriptdatei-ist-kein-haenger.md) — Auswahl vor dem Testende leeren.
- [Parallele Reviewer kollidieren](parallele-reviewer-kollidieren-an-den-raendern.md) · [Patchübernahme in den geteilten Baum](patchuebernahme-in-den-geteilten-baum.md) · [Skript im Worktree lädt app aus dem Hauptbaum](skript-im-worktree-laedt-app-aus-dem-hauptbaum.md) — Patches in Reihenfolge; sys.path[0].
- [Paketexport verdeckt das Modul](paketexport-verdeckt-das-modul.md) · [OCP-Paketattribut ist nicht das Modul](ocp-paketattribut-ist-nicht-das-modul.md) — import_module; `import OCP.X as X` patchen.

## Shell und Git

- [Deutscher Text nicht durch die Shell](deutscher-text-geht-nicht-durch-die-shell.md) · [Heredoc frisst den Backslash](heredoc-frisst-den-backslash.md) — Write-Datei, `-F`.
- [Kette mit ; läuft nach dem Kill weiter](kette-mit-semikolon-laeuft-nach-dem-kill-weiter.md) · [Agent-Edits schreiben CRLF](agent-edits-schreiben-crlf.md) — `&&` statt `;`; CRLF-Warnungen lesen.
- [Checkout-Reflex löscht eigene Arbeit](checkout-reflex-loescht-eigene-arbeit.md) · [Git-Identität](git-identitaet-mitgeben.md) · [Erinnerungen im Repository](erinnerungen-liegen-im-repository.md) — vorwärts berichtigen; link_memory.py.
- [Datei vor dem Patch modifiziert](datei-die-vor-dem-patch-modifiziert-war-geht-nur-als-blob.md) · [Katalogschreiber überschreibt still](katalogschreiber-ueberschreibt-still.md) · [Geteilter Index veraltet](geteilter-index-nach-fremdem-commit-veraltet.md) · [Fremder Commit nimmt Hunks mit](fremder-commit-nimmt-unfertige-hunks-mit.md) — numstat vor dem Commit; mit Pathspec committen.
