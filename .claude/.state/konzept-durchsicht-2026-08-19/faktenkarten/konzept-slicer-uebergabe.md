# Faktenkarten für `konzept-slicer-uebergabe.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

## slicer

_Slicer und die Übergabe an sie (OrcaSlicer, ElegooSlicer, PrusaSlicer, Bambu Studio, Cura, Creality Print, 3MF, Elegoo Centauri Carbon 2) — Stand 19. August 2026_

- **OrcaSlicer** — Neueste stabile Fassung ist v2.4.2, veröffentlicht am 7. Juli 2026.
  · Stand: 2026-07-07 (published_at der GitHub-Freigabe), abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Die GitHub-Seite zeigt nur relative Datumsangaben; das exakte Datum stammt aus dem API-Feld published_at. Eine Suchtreffer-Zusammenfassung nannte v2.3.1 (Februar 2026) noch als aktuell — das ist überholt.
  · https://api.github.com/repos/SoftFever/OrcaSlicer/releases?per_page=12
  · https://github.com/OrcaSlicer/OrcaSlicer/releases
- **OrcaSlicer** — Die Fassungen v2.4.0 (20. Juni 2026) und v2.4.1 (28. Juni 2026) gingen v2.4.2 unmittelbar voraus; die 2.4er-Reihe entstand innerhalb von drei Wochen.
  · Stand: 2026-06-20 bzw. 2026-06-28 · Sicherheit: belegt
  · Anmerkung: Drei Freigaben in drei Wochen heißt: eine Fassungsnummer, die Solidon fest verdrahtet, ist binnen Wochen falsch.
  · https://api.github.com/repos/SoftFever/OrcaSlicer/releases?per_page=12
  · https://api.github.com/repos/SoftFever/OrcaSlicer/releases/tags/v2.4.0
- **OrcaSlicer** — Das Vorhaben liegt heute unter der Organisation OrcaSlicer/OrcaSlicer (nicht mehr SoftFever/OrcaSlicer), steht unter AGPL-3.0, hat 15.429 Sterne und wurde zuletzt am 19. August 2026 bepusht.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Der alte Pfad SoftFever/OrcaSlicer wird umgeleitet und liefert im API dasselbe Repository (full_name: OrcaSlicer/OrcaSlicer). Fest hinterlegte Links in Solidon sollten auf den neuen Pfad zeigen. AGPL-3.0 ist für Regel 15 unkritisch, solange Solidon den Slicer nur extern aufruft und nicht mitliefert.
  · https://api.github.com/repos/OrcaSlicer/OrcaSlicer
  · https://api.github.com/repos/SoftFever/OrcaSlicer
- **OrcaSlicer** — v2.4.0 führte eine je Drucker einstellbare Option ein, Druckaufträge als gepacktes .gcode.3mf statt als reinen G-Code an den Drucker zu senden, mit eingebetteten Schicht-Metadaten, die an Objektbezeichnungen hängen.
  · Stand: 2026-06-20 · Sicherheit: belegt
  · Anmerkung: Für die Übergabe aus Solidon heraus relevant: das Zielformat ist nicht mehr zwingend .gcode.
  · https://api.github.com/repos/SoftFever/OrcaSlicer/releases/tags/v2.4.0
- **OrcaSlicer** — v2.4.0 brachte „Orca Cloud" — eine eigene zentrale Plattform für Profile und deren Abgleich, mit Offline-Anmeldung über den System-Schlüsselspeicher und Benachrichtigung bei Profil-Aktualisierungen.
  · Stand: 2026-06-20 · Sicherheit: mehrere_quellen
  · Anmerkung: Neu seit Mai/Juni 2026 und im Trainingswissen nicht enthalten. Eine Profildatei auf der Platte ist damit nicht mehr notwendigerweise der vollständige Stand.
  · https://api.github.com/repos/SoftFever/OrcaSlicer/releases/tags/v2.4.0
  · https://all3dp.com/4/massive-orcaslicer-update-lands-with-z-anti-aliasing-stronger-gyroid-infill-and-a-cloud-of-its-own/
- **OrcaSlicer** — Die Kommandozeile nimmt unter anderem --slice (0 = alle Platten, n = eine Platte), --load-settings "machine.json;process.json", --load-filaments, --load-filament-ids, --load-assemble-list, --load-custom-gcodes, --datadir, --allow-newer-file, --outputdir, --export-3mf, --export-slicedata, --load-slicedata, --pipe, --debug, --arrange, --orient, --info.
  · Stand: OrcaSlicer 2.4.0, Fremdartikel vom 16. April 2026; dazu eine Vorhabens-Diskussion · Sicherheit: mehrere_quellen
  · Anmerkung: Es gibt keine offizielle Wikiseite des Vorhabens zur Kommandozeile — die Import/Export-Seite beschreibt nur die Oberfläche. Gestützt wird die Liste durch das gleichlautende Bambu-Studio-Wiki (gemeinsame Code-Herkunft). Reihenfolge beachten: Maschinen- vor Prozesseinstellungen.
  · https://printago.io/blog/orca-slicer-cli-reference
  · https://github.com/OrcaSlicer/OrcaSlicer/discussions/8593
  · https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- **OrcaSlicer** — Die Rangfolge der Einstellungen ist: Kommandozeilenschalter schlagen --load-settings/--load-filaments, und diese schlagen die im 3MF eingebetteten Werte — ein fremdes Programm kann Druckeinstellungen also ohne Oberfläche mitgeben.
  · Stand: OrcaSlicer 2.4.0 (Artikel 16. April 2026); Bambu-Wiki nennt dieselbe Rangfolge · Sicherheit: mehrere_quellen
  · Anmerkung: Genau der Weg für Solidons handover.py: 3MF schreiben, Einstellungen als JSON danebenlegen, beides an die Kommandozeile geben.
  · https://printago.io/blog/orca-slicer-cli-reference
  · https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- **OrcaSlicer** — --export-3mf liefert kein reines .gcode, sondern ein 3MF-Archiv mit dem G-Code unter Metadata/plate_1.gcode; daneben entsteht eine result.json mit Rückgabecode und Fehlern.
  · Stand: OrcaSlicer 2.4.0 (Artikel 16. April 2026) · Sicherheit: mehrere_quellen
  · Anmerkung: Wer aus Solidon heraus eine .gcode-Datei erwartet, bekommt ein ZIP. Beim kopflosen Schneiden bleiben zudem die Vorschaubilder im Archiv leer.
  · https://printago.io/blog/orca-slicer-cli-reference
  · https://github.com/OrcaSlicer/OrcaSlicer/discussions/8593
- **OrcaSlicer** — System-Profile sind JSON-Dateien mit den Schlüsseln type (machine_model/machine/filament/process), name, inherits, from ("system"), instantiation und version im Format 01.00.00.00; jedes instanziierte Preset braucht eine global eindeutige setting_id, Basisprofile dürfen keine haben.
  · Stand: Wiki-Stand abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Ablage unter resources/profiles/<Hersteller>/{machine,process,filament}/, dazu eine Hersteller-Metadatei. Das Vorhaben liefert Prüfskripte (assign_vendor_setting_ids.py, orca_extra_profile_check.py).
  · https://www.orcaslicer.com/wiki/guides/how_to_create_profiles
- **OrcaSlicer** — Nutzer-Prozessprofile verlangen ein anderes, nirgends dokumentiertes JSON-Format als System-Profile: Pflichtfelder sind from: "User", inherits (muss auf ein vorhandenes System-Preset zeigen), version, print_settings_id und is_custom_defined, und es dürfen nur geänderte Einstellungen darinstehen.
  · Stand: Fehlerbericht gegen OrcaSlicer 2.3.1, als Duplikat geschlossen · Sicherheit: belegt
  · Anmerkung: Wichtig für Solidon: ein vollständiger Konfigurationsblock mit inherits: "" wird stillschweigend abgewiesen, ebenso compatible_printers in Nutzerprofilen und eine Ablage unter process/base/. Fehlermeldungen sind irreführend. Sicherer bleibt --load-settings, statt Profildateien zu installieren.
  · https://github.com/OrcaSlicer/OrcaSlicer/issues/12223
- **ElegooSlicer** — Neueste Fassung ist v1.5.3.4 vom 6. August 2026; sie hat die meisten Funktionen der offiziellen OrcaSlicer-Fassung v2.4.2 übernommen. Das Vorhaben ist eine Abspaltung von Orca Slicer und steht unter AGPL-3.0.
  · Stand: 2026-08-06 · Sicherheit: belegt
  · Anmerkung: Der Rückstand auf OrcaSlicer beträgt derzeit rund einen Monat, nicht ein bis zwei Fassungen. Die Änderungsnotiz nennt zusätzlich eine korrigierte Druckzeitschätzung für Mehrfarbdruck auf dem Centauri Carbon 2. Es existiert daneben elegooofficial/ElegooSlicer; die Freigaben liegen unter elegoo-repo.
  · https://api.github.com/repos/elegoo-repo/ElegooSlicer/releases?per_page=12
  · https://github.com/elegoo-repo/ElegooSlicer
- **ElegooSlicer** — Fassungsverlauf 2026: v1.3.0.11 (12. Januar), v1.5.0.7 (16. April), v1.5.1.6 (27. Mai, Device Assistant für Centauri Carbon 2), v1.5.2.2 (25. Juni, Unterstützung für den Centauri 2), v1.5.3.4 (6. August).
  · Stand: 2026-01-12 bis 2026-08-06 · Sicherheit: belegt
  · Anmerkung: Zwischen v1.1.8.2 (März 2025) und v1.3.0.11 (Januar 2026) liegt eine Lücke von zehn Monaten — aus der Fassungsnummer lässt sich der Orca-Unterbau nicht ableiten.
  · https://api.github.com/repos/elegoo-repo/ElegooSlicer/releases?per_page=12
- **ElegooSlicer** — ElegooSlicer unterstützt Centauri Carbon (CC1) und Centauri Carbon 2 (CC2) einschliesslich des vierfarbigen CANVAS-Systems sowie die Neptune-Reihen 2, 3 und 4; Motor und Kommandozeilenverhalten sind mit OrcaSlicer gemeinsam, das Projektformat ist der Orca-Dialekt des 3MF.
  · Stand: Artikel vom 11. Juni 2026 · Sicherheit: unsicher
  · Anmerkung: Fremdquelle, kein Herstellerbeleg. Die Aussage zur Kommandozeile ist eine Ableitung aus der Code-Herkunft, keine geprüfte Messung — vor dem Einbau in Solidon gegen die installierte Binärdatei prüfen.
  · https://printago.io/blog/elegoo-slicer
- **PrusaSlicer** — Neueste stabile Fassung ist 2.9.6, veröffentlicht am 25. Juni 2026; Hauptneuerung ist ColorMix, das Farben durch schichtweisen Materialwechsel mischt.
  · Stand: 2026-06-25 · Sicherheit: belegt
  · Anmerkung: Davor: 2.9.5 am 19. Mai 2026, 2.9.4 am 7. November 2025. Zwischen 2.9.4 und 2.9.5 lagen mehr als sechs Monate.
  · https://api.github.com/repos/prusa3d/PrusaSlicer/releases?per_page=10
  · https://github.com/prusa3d/PrusaSlicer/releases
- **PrusaSlicer** — Die Kommandozeile lädt Konfigurationen als .ini über --load, das mehrfach angegeben werden darf; typischer Aufruf: prusa-slicer-console.exe --load my_config.ini --export-gcode --output my_model.gcode my_model.stl. Einzelne Parameter lassen sich zusätzlich direkt auf der Kommandozeile überschreiben.
  · Stand: abgerufen 2026-08-19; die Schnittstelle geht auf Slic3r zurück · Sicherheit: mehrere_quellen
  · Anmerkung: Die offizielle Wikiseite (zweite URL) war am 19. August 2026 nicht abrufbar — GitHub lieferte nur die Wiki-Startseite mit Ladefehlern. Die Angaben stammen daher aus Sekundärquellen; --help gibt die vollständige Liste aus.
  · https://www.accessiblestem.org/fabrication%20lab/prusa-slicer-advanced.html
  · https://github.com/prusa3d/PrusaSlicer/wiki/Command-Line-Interface
  · https://github.com/prusa3d/PrusaSlicer/issues/3893
- **PrusaSlicer** — Es ist berichtet, dass --load mit einer .ini die in einer 3MF-Projektdatei eingebetteten Profile nicht überschreibt, sondern ignoriert wird; der Fehlerbericht ist ohne Entwicklerantwort offen.
  · Stand: Fehlerbericht #3893, Stand des Abrufs 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Widerspricht der Rangfolge der Orca-/Bambu-Familie, wo die Kommandozeile das 3MF schlägt. Ob das in 2.9.6 noch gilt, wurde nicht geprüft. Für Solidon: bei PrusaSlicer nicht darauf bauen, Einstellungen per --load über ein 3MF zu legen.
  · https://github.com/prusa3d/PrusaSlicer/issues/3893
- **PrusaSlicer** — Profile liegen als .ini vor, in drei Ausprägungen: Einzelkonfiguration, Konfigurationsbündel (alle eigenen Einstellungen) und Bündel mit physischen Druckern (enthält API-Schlüssel und IP-Adressen). Import geht über Datei → Import als Config (.ini oder .gcode), Config aus Projekt (.3mf, .amf) oder Config-Bündel.
  · Stand: Wissensdatenbank abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Dass Konfigurationen aus einer .gcode-Datei zurückgelesen werden können, ist für Solidons Trennung von Schichtanalyse und G-Code (Regel 14) bemerkenswert: der G-Code trägt die Einstellungen mit.
  · https://help.prusa3d.com/article/how-to-import-and-export-custom-profiles-in-prusaslicer_382766
- **Bambu Studio** — Neueste stabile Fassung ist v02.08.02.60 („2.8.2 Public Release") vom 14. August 2026; davor war v02.07.01.62 vom 16. Juni 2026 die stabile Reihe.
  · Stand: 2026-08-14 · Sicherheit: belegt
  · Anmerkung: Die 2.8er-Reihe lief seit 25. Juni 2026 als öffentliche Beta (v02.08.00.50, dann v02.08.01.55 am 14. Juli). Die Fassungsnummern im Tag sind nullgepolstert (02.08.02.60), im Namen nicht (2.8.2) — beim Vergleichen aufpassen.
  · https://api.github.com/repos/bambulab/BambuStudio/releases?per_page=10
  · https://github.com/bambulab/BambuStudio/releases
- **Bambu Studio** — Die Kommandozeile ist offiziell im Vorhabens-Wiki dokumentiert: --load-settings, --load-filaments, --outputdir, --arrange, --orient, --scale, --export-3mf, --export-settings, --export-slicedata, --load-slicedata, --info, --pipe, --slice, --uptodate, --debug.
  · Stand: Wiki abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: --export-settings schreibt die aktuelle Konfiguration als JSON heraus — der bequemste Weg, aus einer bestehenden Einstellung eine Datei für --load-settings zu gewinnen, ohne das Format raten zu müssen.
  · https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- **Bambu Studio** — Die Rangfolge ist ausdrücklich festgelegt: Werte von der Kommandozeile im Format --key=value haben Vorrang, danach die über --load-settings/--load-filaments geladenen Dateien, zuletzt die im 3MF eingebetteten Einstellungen. Die JSON-Dateien müssen vollständige Konfigurationen sein, keine Teilmengen.
  · Stand: Wiki abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: „full config", nicht nur die Abweichungen — genau umgekehrt zum Nutzerprofil-Format von OrcaSlicer, wo nur die Abweichungen erlaubt sind.
  · https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- **Bambu Studio / OrcaSlicer (3MF-Aufbau)** — Ein ungeschnittenes Projekt-3MF enthält 3D/3dmodel.model (Geometrie), Metadata/project_settings.config (JSON mit allen Slicer-Parametern), Metadata/model_settings.config (XML mit Plattenbelegung und Objektlage) und Metadata/custom_gcode_per_layer.xml (Werkzeugwechsel).
  · Stand: Artikel vom 13. April 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Das ist die Schnittstelle, an der Solidon Druckeinstellungen mitgeben kann, ohne die Oberfläche zu bedienen: project_settings.config ins 3MF schreiben.
  · https://printago.io/blog/3mf-file-format
  · https://radagast.ca/linux/3mf-file-format.html
  · https://deepwiki.com/bambulab/BambuStudio/2.3-3mf-project-file-handling
- **Bambu Studio / OrcaSlicer (3MF-Aufbau)** — Ein geschnittenes .gcode.3mf ergänzt Metadata/plate_N.gcode, vier Vorschaubild-Varianten je Platte (plate_N.png, plate_N_no_light.png, top_plate_N.png, pick_plate_N.png) und Metadata/slice_info.config mit Druckzeit und Filamentverbrauch.
  · Stand: Artikel vom 13. April 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: radagast.ca bestätigt zusätzlich plate_1.json, plate_1.gcode.md5 und _rels/model_settings.config.rels. slice_info.config führt den Schlüssel X-BBL-Client-Version, aus dem sich die erzeugende Slicer-Fassung ablesen lässt.
  · https://printago.io/blog/3mf-file-format
  · https://radagast.ca/linux/3mf-file-format.html
- **Bambu Studio / OrcaSlicer (Einstellungsschlüssel)** — In project_settings.config stehen unter anderem printer_model, printer_variant (Düsendurchmesser), die parallel indizierten Felder filament_type, filament_colour und filament_ids, ausserdem print_compatible_printers, upward_compatible_machine, enable_support, support_filament und support_interface_filament.
  · Stand: Artikel vom 13. April 2026 · Sicherheit: unsicher
  · Anmerkung: Einzelquelle, Fremdartikel. Fallen: Filament-Steckplätze sind überall 1-basiert, in den Feldern selbst 0-basiert; used_m in slice_info.config ist in Metern; Werte in model_settings.config sind XML-entitätskodiert (& erscheint als &amp;).
  · https://printago.io/blog/3mf-file-format
- **Bambu Studio (3MF-Metadaten)** — Beim Öffnen liest Bambu Studio die Geometrie aus 3D/3dmodel.model, prüft die Marke BambuStudio:3mfVersion, liest model_id, holt die eingebetteten Drucker-, Filament- und Prozess-Presets aus Metadata/ und stellt die Platten samt Druckbett-Typ, Massen und Ursprung wieder her. Beim Speichern schreibt es ein 512×512-Vorschaubild und je Platte plate_*.png.
  · Stand: abgerufen 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Automatisch erzeugte Code-Dokumentation, kein Herstellertext. Die Herstellerseite wiki.bambulab.com/en/software/bambu-studio/3mf-compatibility antwortete mit HTTP 402 und liess sich nicht prüfen.
  · https://deepwiki.com/bambulab/BambuStudio/2.3-3mf-project-file-handling
- **Bambu Studio / OrcaSlicer (3MF-Abweichungen)** — Beide erweitern das offene 3MF um Metadaten, die nirgends dokumentiert sind: eigene Namensräume (xmlns:BambuStudio), Bemalungsfarben als Bitmasken-Codes auf einzelnen Dreiecken ("4", "8", "0C") und verschachtelte Modelldateien, auf die 3D/3dmodel.model verweist.
  · Stand: Artikel vom 13. April 2026 bzw. abgerufen 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: radagast.ca merkt an, dass die von Bambu Studio exportierte G-Code-3MF nur Metadaten und einen leeren resources-Abschnitt enthält, also keine Geometrie — ob das nach 3MF-Norm gültig ist, stellt der Autor ausdrücklich in Frage. Ein von Solidon geschriebenes normkonformes 3MF ist nicht dasselbe wie ein Bambu-3MF.
  · https://printago.io/blog/3mf-file-format
  · https://radagast.ca/linux/3mf-file-format.html
- **3MF (Norm)** — Die 3MF-Kernspezifikation steht bei Fassung 1.4.0, freigegeben am 11. Februar 2025; seither gab es keine neuere Freigabe.
  · Stand: 2025-02-11, geprüft 2026-08-19 · Sicherheit: belegt
  · Anmerkung: 1.4.0 entfernte die überholte Spiegelungs-Funktion, präzisierte Formen und Baugruppen und führte einen Änderungsverlauf ein. Vorgänger war 1.3.0 vom 7. Oktober 2021.
  · https://api.github.com/repos/3MFConsortium/spec_core/releases?per_page=8
  · https://github.com/3MFConsortium/spec_core/releases
- **3MF (Norm)** — Die Spezifikationssuite ist seit 2025 als internationale Norm ISO/IEC 25422:2025 „Information technology — 3D Manufacturing Format (3MF) specification suite" anerkannt.
  · Stand: 2025, Konsortiumsseite abgerufen 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Fällt hinter Solidons Trainingswissen und ist ein belastbares Argument dafür, den 3MF-Export gegen die Norm zu schreiben statt gegen den Bambu-Dialekt.
  · https://3mf.io/spec/
  · https://www.iso.org/standard/90283.html
  · https://3mf.io/announcement/2025/07/3mf-an-iso-standard-for-the-future-of-additive-manufacturing/
- **3MF (Erweiterungen)** — Freigabestände der einschlägigen Erweiterungen: Production 1.2.0 (11. August 2022), Slice 1.0.2 (12. März 2019), Beam Lattice 1.2.0 (29. März 2021).
  · Stand: jeweils genanntes Datum, geprüft 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Widerspruch: eine Übersicht vom Februar 2026 führt Production noch als v1.1.2, während die Freigabeliste des Konsortiums auf GitHub 1.2.0 zeigt. Ich nehme die GitHub-Freigabe des Konsortiums. Beam Lattice 1.2.0 verschob das Element „ball" in einen neuen Namensraum — wer 1.1.0 liest, findet es woanders.
  · https://api.github.com/repos/3MFConsortium/spec_production/releases?per_page=5
  · https://api.github.com/repos/3MFConsortium/spec_slice/releases?per_page=5
  · https://api.github.com/repos/3MFConsortium/spec_beamlattice/releases?per_page=5
- **Ultimaker Cura** — Neueste stabile Fassung ist 5.13.0 vom 28. Mai 2026; 5.14.0-alpha.0 erschien am 25. Juni 2026 und bringt das Bemalen von Stützstellen sowie versuchsweise Windows-ARM.
  · Stand: 2026-05-28 bzw. 2026-06-25 · Sicherheit: belegt
  · Anmerkung: Davor 5.12.1 (13. April 2026) und 5.12.0 (5. März 2026). Die offizielle Ankündigungsseite ultimaker.com/learn/introducing-cura-5-13/ antwortete mit HTTP 403 und konnte nicht gegengeprüft werden.
  · https://api.github.com/repos/Ultimaker/Cura/releases?per_page=10
  · https://api.github.com/repos/Ultimaker/Cura/releases/latest
- **Ultimaker Cura** — Die Oberfläche von Cura benutzt die Kommandozeile ihres Motors nicht, sondern spricht über ein Protokoll auf Basis von Google Protobuf mit einem dauerhaft laufenden CuraEngine-Prozess.
  · Stand: abgerufen 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Forenbeleg, kein Herstellerdokument. Folge für Solidon: Cura lässt sich nicht wie OrcaSlicer mit Projekt und Einstellungen von aussen aufrufen — der Weg führt über CuraEngine oder über eine Projektdatei, die der Nutzer selbst öffnet.
  · https://community.ultimaker.com/topic/43914-command-line-for-curaengine/
- **CuraEngine** — Der Aufruf lautet CuraEngine slice [-v] [-p] [-j <settings.json>] [-s <settingkey>=<value>] [-g] [-e<extruder_nr>] [-o <output.gcode>] [-l <model.stl>] [--next]; -j lädt eine Definitionsdatei, -s überschreibt einzelne Einstellungen.
  · Stand: Handbuchseite, Stand des Abrufs 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Die abgerufene Handbuchseite stammt aus einer alten Ubuntu-Fassung; ob die Schalter in der mit Cura 5.13 ausgelieferten CuraEngine unverändert gelten, wurde nicht geprüft. Anders als bei Orca gibt es keine Projektdatei mit Einstellungen — jede Einstellung wird einzeln als -s key=value übergeben.
  · https://manpages.ubuntu.com/manpages/bionic/man1/CuraEngine.1.html
  · https://gist.github.com/JacobFV/3bcc83a2c6cc77f2b7eb6ed5c8f1ebaa
- **Ultimaker Cura (Profilformate)** — Exportierte Profile tragen die Endung .curaprofile und sind ZIP-Archive, die entpackt .inst.cfg-Dateien enthalten; Druckerdefinitionen liegen als .def.json vor. Projektdateien sind 3MF, dazu gibt es das Universal Cura Project als Sonderform, mit der sich Einstellungen gezielt mit ausgeben lassen.
  · Stand: abgerufen 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Gemischte Quellenlage aus Forum und automatisch erzeugter Code-Dokumentation. Ein Herstellerdokument zu den Dateiformaten wurde nicht gefunden. Die Schlüsselnamen weichen von der Orca-Familie ab; eine Entsprechungstabelle wurde in dieser Recherche nicht belegt.
  · https://deepwiki.com/Ultimaker/Cura/5-file-handling
  · https://community.ultimaker.com/topic/46077-importing-profiles/
- **Creality Print** — Neueste Fassung ist V7.2.1, auf GitHub freigegeben am 4. August 2026; davor V7.2.0 am 30. Juni 2026, V7.1.1 am 28. April 2026, V7.1.0 am 30. März 2026, V7.0.1 am 31. Januar 2026.
  · Stand: 2026-08-04 · Sicherheit: belegt
  · Anmerkung: Widerspruch: eine Suchtreffer-Zusammenfassung nennt V7.2.1.5476 mit Datum 5. August 2026 auf den Downloadseiten von Creality. Die Herstellerseiten crealitycloud.com/downloads und wiki.creality.com liessen sich nicht abrufen (ECONNRESET bzw. keine Inhalte), daher steht hier das belegte GitHub-Datum. Die vierte Stelle ist offenbar eine Build-Nummer.
  · https://api.github.com/repos/CrealityOfficial/CrealityPrint/releases?per_page=8
  · https://github.com/CrealityOfficial/CrealityPrint/releases
- **Creality Print** — Creality Print ist eine Abspaltung von Orca Slicer (und darüber von Bambu Studio, PrusaSlicer, Slic3r), steht unter AGPL-3.0 und unterstützt kopfloses Schneiden über --slice mit Ausgabeverzeichnis, Laden von Einstellungen und Filamenten, Fehlersuchstufen und Protokolldatei — für ganze Projektdateien ebenso wie für STL/OBJ mit externen Presets.
  · Stand: README abgerufen 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Das README nennt sich selbst noch „Creality Print 6.0", die Freigaben stehen bei 7.2.1 — das README ist nicht nachgezogen. Die genauen Schalternamen wurden nicht einzeln belegt.
  · https://github.com/CrealityOfficial/CrealityPrint
- **Elegoo Centauri Carbon 2** — Bauraum 256 × 256 × 256 mm, CoreXY, gehärtete Düse bis 350 °C, beheiztes Bett bis 110 °C, bis 500 mm/s Druckgeschwindigkeit und bis 20.000 mm/s² Beschleunigung, Direktantrieb mit Doppelzahnrad, Filament 1,75 mm, Schichthöhe 0,1–0,4 mm (0,2 mm empfohlen).
  · Stand: Händlerseite abgerufen 2026-08-19 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Herstellerseiten elegoo.com und wiki.elegoo.com lieferten HTTP 403 bzw. leere, per Skript nachgeladene Inhalte; die Zahlen stammen daher von einem deutschen Fachhändler und decken sich mit Bauraum und Düsentemperatur aus Elegoos eigener Produktbezeichnung. Vor dem Eintrag in ein Solidon-Druckerprofil am Gerät gegenprüfen.
  · https://www.3dmensionals.de/elegoo-centauri-carbon-2-combo-8244
  · https://us.elegoo.com/products/centauri-carbon-2
  · https://www.tomshardware.com/3d-printing/elegoo-centauri-carbon-2-review
- **Elegoo Centauri Carbon 2** — Weitere Daten: vollständig geschlossenes Gehäuse mit Aktivkohlefilter, 31 Sensoren, automatische Nivellierung, RFID-Filamenterkennung, Kamera mit Fehlererkennung, WLAN und USB, Aussenmasse 500 × 480 × 743 mm, 19,35 kg, maximal 1100 W, unter 45 dB. Preise im Elegoo-Shop Deutschland: Combo 379 € (herabgesetzt von 439 €), Einzelgerät 349 €.
  · Stand: abgerufen 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Die Geräuschangabe und die 31 Sensoren sind Marketingzahlen ohne Messbedingung. Der Herstellerpreis ist ein Aktionspreis; ein deutscher Fachhändler führt die Combo zu 439 €. Keine Zahl, die in Solidon fest stehen sollte.
  · https://www.3dmensionals.de/elegoo-centauri-carbon-2-combo-8244
  · https://de.elegoo.com/products/centauri-carbon-2-combo
- **Elegoo Centauri Carbon 2 Combo** — CANVAS ist Elegoos vierfarbiges Drucksystem für die Centauri-Carbon-2- und Centauri-2-Reihe mit eigenen Filamentmotoren, RFID-Erkennung, automatischem Nachschub und Verhedderungsschutz.
  · Stand: Stand des Abrufs 2026-08-19 · Sicherheit: unsicher
  · Anmerkung: Die Produktseite liess sich nur in Teilen auslesen. ElegooSlicer steuert CANVAS laut Fremdquelle über einen eigenen G-Code-Befehl M6211 für Spülparameter — herstellerspezifisch und in keiner Norm.
  · https://us.elegoo.com/products/centauri-carbon-2-combo
  · https://printago.io/blog/elegoo-slicer
- **Elegoo Centauri Carbon 2** — Der vorgesehene Slicer ist ElegooSlicer; Firmware-Aktualisierungen kommen als .zip.sig und werden entweder über WLAN vom Touchscreen oder offline über USB (Einstellungen → Nach Aktualisierungen suchen → Offline-Update) eingespielt.
  · Stand: Anleitung vom 8. Juli 2026 · Sicherheit: unsicher
  · Anmerkung: Fremdquellen. Ausdrücklich betont wird, dass CC1 und CC2 verschiedene Geräte sind und die Firmware-Datei zum Modell passen muss. Eine Fassungsnummer nennt die Anleitung nicht.
  · https://printago.io/guides/elegoo-centauri-carbon-firmware
  · https://printago.io/blog/elegoo-slicer
- **Elegoo Centauri Carbon 2** — Elegoo veröffentlicht Quelltext zum CC2 unter GPL-3.0 im Repository elegooofficial/CentauriCarbon2; er enthält Build-Werkzeuge für die MCU-Firmware (AR100, RP2040, STM32, toolhead_gd32, bed_sensor) und wurde zuletzt am 19. August 2026 bepusht.
  · Stand: 2026-08-19 · Sicherheit: belegt
  · Anmerkung: Im README taucht die Verzeichnisbezeichnung printer-realase-2602101855 auf, was auf einen Zeitstempel Februar 2026 hindeutet; eine tatsächliche Firmware-Fassungsnummer nennt der Quelltext nicht (Beispiele stehen auf 00.00.00.00 bzw. 00.00.00.02).
  · https://api.github.com/repos/elegooofficial/CentauriCarbon2/contents/
  · https://raw.githubusercontent.com/elegooofficial/CentauriCarbon2/main/README.md
  · https://api.github.com/search/repositories?q=CentauriCarbon+user:elegooofficial
- **Bambu Lab (Zugang für fremde Programme)** — Seit dem am 16. Januar 2025 angekündigten Authorization Control System liegen Druckstart, Bewegungssteuerung, Lüfter- und Hotend-Temperatur, AMS-Konfiguration, Kalibrierungen, Fernvideo und Firmware-Aktualisierung hinter einer Bambu-Anmeldung; fremde Slicer senden Aufträge nicht mehr direkt über das lokale Netz, sondern müssen über die geschlossene Zwischenschicht Bambu Connect gehen. Ende April 2026 folgte eine Unterlassungsaufforderung gegen die Abspaltung OrcaSlicer-BambuLab (Repository am 23. April entfernt, öffentliche Antwort Bambus am 7. Mai 2026); der OrcaSlicer-Betreuer bekam keine API-Schlüssel und erklärte, direktes Senden werde künftig nicht unterstützt.
  · Stand: Ankündigung 2025-01-16, Ereignisse April/Mai 2026, Wiki-Eintrag zuletzt 2026-06-03 bearbeitet · Sicherheit: unsicher
  · Anmerkung: Kein Herstellerbeleg — Bambus eigene Seite wurde nicht geprüft, der Tom's-Hardware-Text liess sich nur als Überschrift auslesen. Für Solidon dennoch die wichtigste Aussage des Themenfelds: „Datei an den Drucker schicken" ist bei Bambu kein offener Weg mehr; die Übergabe an Bambu Studio als Programm (3MF öffnen, Kommandozeile) bleibt davon unberührt.
  · https://consumerrights.wiki/w/Bambu_Lab_cease_and_desist_against_OrcaSlicer_fork_developer
  · https://consumerrights.wiki/w/Bambu_Lab_Authorization_Control_System
  · https://www.tomshardware.com/3d-printing/developer-re-enables-3d-printer-features-that-bambu-lab-disabled-firm-promptly-threatens-legal-action-orcaslicer-bambulab-project-now-shuttered

**Nicht belegbar:**
- Fassungsnummer und Erscheinungsdatum der aktuellen Firmware des Elegoo Centauri Carbon 2. Gesucht auf wiki.elegoo.com/update-log, wiki.elegoo.com/faq/centauri-carbon-2-combo, docs.opencentauri.cc/software/updates-cc2/ (HTTP 403), im GPL-Quelltext elegooofficial/CentauriCarbon2 und in einer Firmware-Anleitung vom 8. Juli 2026. Die Elegoo-Wikiseiten laden ihre Inhalte per Skript nach und liefern über WebFetch nur Titel und Navigation; die Anleitung nennt ausdrücklich keine Fassungsnummern. Es steht keine belastbare CC2-Firmware-Fassung fest.
- Offizielle Herstellerdokumentation der OrcaSlicer-Kommandozeile. Die Wikiseite github.com/OrcaSlicer/OrcaSlicer/wiki/import_export beschreibt ausschliesslich Menübefehle der Oberfläche; eine offizielle Seite zu --slice/--load-settings wurde nicht gefunden. Die Schalterliste stützt sich auf einen Fremdartikel (printago.io, 16. April 2026), eine Vorhabens-Diskussion und das gleichlautende Bambu-Studio-Wiki.
- Offizielle Liste der PrusaSlicer-Kommandozeilenschalter. github.com/prusa3d/PrusaSlicer/wiki/Command-Line-Interface lieferte am 19. August 2026 nur die Wiki-Startseite mit der Meldung, dass die Artikel nicht geladen werden konnten; raw.githubusercontent.com/wiki/prusa3d/PrusaSlicer/Command-Line-Interface.md gab HTTP 404. Die genannten Schalter stammen aus Sekundärquellen.
- Ob der Fehler, dass PrusaSlicer --load gegenüber den in einer 3MF eingebetteten Profilen ignoriert (Bericht #3893), in Fassung 2.9.6 noch besteht. Der Bericht ist ohne Entwicklerantwort; ein Gegentest wurde nicht durchgeführt.
- Vollständige Listen der Einstellungsschlüssel je Slicer und ihre Entsprechungen untereinander (Orca/Bambu gegen PrusaSlicer gegen Cura). Belegt sind nur einzelne Beispiele aus project_settings.config. Eine Übersetzungstabelle, wie Solidons slicer_keys.py sie braucht, liess sich aus keiner Quelle vollständig belegen.
- Aussagen des Herstellers Bambu Lab zur 3MF-Kompatibilität. wiki.bambulab.com/en/software/bambu-studio/3mf-compatibility antwortete mit HTTP 402 Payment Required. Die Beschreibung des 3MF-Aufbaus stützt sich daher auf Fremdquellen und automatisch erzeugte Code-Dokumentation.
- Offizielle Ankündigung und Merkmalsliste zu Cura 5.13 von UltiMaker. ultimaker.com/learn/introducing-cura-5-13/ gab HTTP 403. Fassung und Datum stammen aus den GitHub-Freigaben.
- Änderungsnotizen zu Creality Print 7.2.0 und 7.2.1 von Creality selbst. wiki.creality.com/en/software/6-0/release-notes-7-2-0 brach zweimal mit ECONNRESET ab, crealitycloud.com/downloads wurde nicht abgerufen. Die Fassungsdaten stammen aus den GitHub-Freigaben; der Widerspruch zur Nummer V7.2.1.5476 mit Datum 5. August 2026 blieb ungeklärt.
- Ob Creality Print die Schalter der Orca-Familie unverändert führt. Das README nennt nur --slice und beschreibt die Möglichkeiten in Prosa; eine Schalterliste wurde nicht belegt. Eine gezielte Websuche dazu war nicht mehr möglich (Suchbudget der Sitzung erschöpft).
- Ob ElegooSlicer eine eigene, von OrcaSlicer abweichende Kommandozeile oder eigene Profilschlüssel hat. Weder das README noch eine Elegoo-Seite dokumentiert die Kommandozeile; die Gleichsetzung mit OrcaSlicer ist eine Ableitung aus der Code-Herkunft in einer Fremdquelle.
- Welches der beiden Repositories (elegoo-repo/ElegooSlicer oder elegooofficial/ElegooSlicer) Elegoo auf seiner Downloadseite verlinkt. Die Freigaben liegen unter elegoo-repo; die Elegoo-Downloadseite wurde nicht abgerufen.
- Die auf 3mf.io/spec/ aufgeführten Einzelfassungen der neun 3MF-Spezifikationen (Core, Materials, Production, Beam Lattice, Slice, Volumetric, Secure Content, Boolean Operations, Displacement). Die Seite lieferte im abgerufenen HTML nur den Hinweis auf ISO/IEC 25422:2025, keine Fassungstabelle. Der Widerspruch bei der Production-Erweiterung (1.1.2 in einer Übersicht vom Februar 2026 gegen 1.2.0 in der GitHub-Freigabe) konnte deshalb nicht am Konsortium selbst aufgelöst werden. Auch die Liste „neun Dokumente" stammt nur aus dieser Übersicht.
- Ob Bambu Studio 2.8.2 (14. August 2026) am Zugangssystem für fremde Programme etwas geändert hat. Die Änderungsnotiz liess sich nur zusammengefasst lesen; ein gezielter Abruf des Freigabetexts über die GitHub-API gab HTTP 403.
- Datum und Inhalt der Meldung, wonach die Software Freedom Conservancy Bambu Lab einen Lizenzverstoss vorwirft. Nur die Überschrift bei Tom's Hardware war lesbar, der Fliesstext nicht.
- Preis des Centauri Carbon 2 im US-Shop von Elegoo. us.elegoo.com lieferte nur Navigation, elegoo.com gab HTTP 403.

**Neu seit Anfang August:**
- ElegooSlicer v1.5.3.4 erschien am 6. August 2026 und hat die meisten Funktionen von OrcaSlicer v2.4.2 übernommen. Der Rückstand des Elegoo-Ablegers auf den Hauptzweig beträgt damit rund einen Monat, nicht wie vielfach behauptet ein bis zwei Fassungen. Wer in Solidon Orca- und Elegoo-Verhalten getrennt behandelt hat, kann das zusammenführen — aber mit Prüfung, nicht auf Zuruf.
- Bambu Studio v02.08.02.60 („2.8.2") erschien am 14. August 2026 als erste stabile Fassung der 2.8er-Reihe. Alles, was Solidon gegen 2.7.1 geprüft hat, ist gegen 2.8.2 ungeprüft.
- Creality Print V7.2.1 erschien am 4. August 2026 — die fünfte Freigabe seit Januar 2026. Der Takt ist zu schnell, um eine Fassung in Solidon fest zu hinterlegen.
- OrcaSlicer ist innerhalb von drei Wochen von 2.4.0 (20. Juni) über 2.4.1 (28. Juni) auf 2.4.2 (7. Juli 2026) gesprungen und wurde am 19. August 2026 zuletzt bepusht. Eine Fassungsprüfung in Solidons handover.py muss mit unbekannt neueren Nummern umgehen können, nicht mit einer Liste bekannter.
- Das Repository heisst heute OrcaSlicer/OrcaSlicer, nicht mehr SoftFever/OrcaSlicer. Fest hinterlegte Links und Erkennungsmuster auf den alten Pfad funktionieren nur noch über die Umleitung.
- Mit v2.4.0 kann OrcaSlicer Druckaufträge als gepacktes .gcode.3mf statt als reinen G-Code an den Drucker senden — je Drucker einstellbar. Das berührt Solidons Annahme, was am Ende der Übergabekette steht, und mittelbar Regel 14: Schicht-Metadaten reisen jetzt neben dem G-Code im selben Behälter.
- „Orca Cloud" ist seit Juni 2026 die zentrale Profilablage von OrcaSlicer, mit Offline-Anmeldung im System-Schlüsselspeicher. Eine Profildatei auf der Platte ist damit nicht mehr notwendigerweise der vollständige Stand — wenn Solidon Profile liest, liest es womöglich einen veralteten Abzug.
- 3MF ist seit 2025 als ISO/IEC 25422:2025 anerkannt, die Kernspezifikation steht seit dem 11. Februar 2025 bei 1.4.0. Das ist ein Argument, Solidons 3MF-Export gegen die Norm zu schreiben und die Bambu-/Orca-Eigenheiten sauber als Dialekt danebenzulegen, statt sie zu vermischen.
- Der Streit zwischen Bambu Lab und dem Entwickler der Abspaltung OrcaSlicer-BambuLab (Unterlassungsaufforderung Ende April 2026, Rückzug des Repositories am 23. April, öffentliche Antwort am 7. Mai) endete damit, dass der OrcaSlicer-Betreuer keine API-Schlüssel bekam und direktes Senden an Bambu-Drucker künftig nicht unterstützt wird. Für Solidon heisst das: „an den Drucker übergeben" und „an den Slicer übergeben" sind bei Bambu zwei verschiedene Dinge, und nur das zweite ist offen.
