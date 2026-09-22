# Anschlusskorrekturen nach dem ersten vollständigen Tor

Ausgang: `0094eea20b12180f90f58ff51140a210bc74eba4`.
Der eingefrorene Lauf in
`C:/Users/rober/AppData/Local/Temp/solidon-cad-round-final-deae57cb87014a11ac0a8880cfde6abc`
endete mit **12298 bestanden, 26 übersprungen, 5 fehlgeschlagen**,
576,86 Sekunden, Suite und Elternprozess jeweils Exit 1. Ruff, Format und
mypy waren grün. Der Lauf bleibt ein roter Nachweis.

- Drei Befunde betreffen bisherige Passungsaussagen in Korpus/Beispielen.
  Die historische Baugruppe enthält tatsächlich kollidierende Grundkörper;
  ihre alte Projektdatei bleibt als Migrationsbeleg erhalten. Eine explizite
  zusätzliche Transformation stellt für positive Tests die Einbaulage her.
  Getrennte Drucklagen bleiben in den Kundenbeispielen erhalten und tragen
  eine offene Einbaulage. Die Tour muss nach Undo die wiederhergestellten
  Maßvorgaben von einer noch unbelegten Montage unterscheiden.
- Das ignorierte lokale `packaging/build/licence.manifest` deckte noch die
  vorige Version von `core/export/writer.py`. Das vollständige vorhandene
  Werkzeug `tools/build_licence_module.py` hat Prüfmodule und Manifest als
  zusammengehörigen lokalen Entwicklungsnachweis neu gebaut, Exit 0.
  Compiler: Visual Studio 18 Community, vcvars64; kein Paket oder Release.
  `tools/affected_tests.py tests/test_packaging.py tests/test_licence_build.py
  --run`: **109 bestanden, 15,59 Sekunden, Exit 0**. Belege in
  `C:/Users/rober/AppData/Local/Temp/solidon-local-licence-refresh-a4ef4e93961840abb28489462b40c490`.
- Der PHP-Verbindungsabbruch WinError 10054 trat nach dem erfolgreichen
  Serverstart auf. Genau ein gezielter Nachlauf des betroffenen Falls war
  grün: **1 bestanden, 1,05 Sekunden, Exit 0**. Ursache mangels
  Serverdiagnostik im ursprünglichen Lauf offen; keine Produkt- oder
  Teständerung. Beleg:
  `C:/Users/rober/AppData/Local/Temp/solidon-php-rate-diagnose-32bf690eac11485698e1026da1b77cb4`.

Erst ein neues vollständiges Entwicklungstor am nachgezogenen Stand erlaubt
die vorbereiteten Commits. Ganze Fensterdateien und Leistungsprüfungen
bleiben ausdrücklich bis zum Release zurückgestellt. Website unverändert.
