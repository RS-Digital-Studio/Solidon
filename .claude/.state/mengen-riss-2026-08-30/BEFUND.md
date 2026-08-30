# Der Mengen-Riss in `test_print_settings_ui.py` — gemessen am 30.08.2026

Auftrag war die Frage aus dem Register: **Welche nativen Handles wachsen mit
der Sammelmenge?** Die Antwort ist: keine. Und die Messung hat dabei etwas
anderes gefunden, das schärfer ist.

## Was gemessen wurde

Ein pytest-Plugin (`messplugin.py`) schreibt nach **jedem** Teardown eine
Zeile: offene Kernel-Handles, Arbeitssatz, Auslagerungsbedarf, Zahl der
`topLevelWidgets`, wie viele davon eine tote C++-Seite haben, die Länge von
`leash._alive` und die Zahl der gc-Objekte. Zeilenweise geschrieben
(`buffering=1`), denn der Lauf, um den es geht, stürzt ab — ein Werkzeug, das
erst am Sitzungsende ausgibt, misst genau den Fall nicht, für den es gebaut
ist.

## Befund 1 — nichts läuft voll

| | Test 1 | Test 24 | Test 25 | Test 33 (Riss) |
|---|---|---|---|---|
| Handles | 270 | 281 | **350** | 358 |
| Arbeitssatz | 102 MB | 113 MB | **196 MB** | 208 MB |
| gc-Objekte | 89 315 | 89 657 | **140 796** | 140 727 |
| `topLevelWidgets` | 10 | 20 | 10 | 50 |
| tote Wrapper darin | 0 | 0 | 0 | **0** |
| `leash._alive` | 0 | 0 | 0 | **0** |

Der Sprung zwischen Test 24 und 25 ist ein **einmaliges Laden** — er trifft
Handles, Speicher und gc-Objekte gleichzeitig und wiederholt sich nicht.
Danach ist alles flach. Die Zahl der Fenster schwingt zwischen 10 und 63 und
fällt regelmäßig zurück: Der Pin sammelt hier **nicht** an, und `leash._alive`
steht durchgehend auf null — es hängt kein Arbeiter.

**Damit ist die naheliegendste Ursachenklasse ausgeschlossen**, und zwar mit
Zahlen statt mit einem Eindruck.

## Befund 2 — der Riss liegt im Aufbau, nicht im Abbau

Das Register führte ihn als „139 im Teardown der Aufräum-Fixture
(`conftest.py:836`)". Vier Läufe sagen etwas anderes:

| Lauf | Position | oberster Frame |
|---|---|---|
| mit Plugin (2) | 33 | `print_settings_dialog.py:3242` `_label` |
| mit Plugin (3) | 31 | `print_settings_dialog.py:2055` `_build_tabs` |
| **ohne** Plugin | 33 | `print_settings_dialog.py:3242` `_label` |
| ohne den Sprachwechsel-Test | 34 | `print_settings_dialog.py:1130` `_make_setting_editor` |

Darunter steht in **allen vier** dieselbe Kette: `_build_tabs` bzw.
`_build_front` ← `PrintSettingsDialog.__init__` ← das `dialog`-Fixture
(`test_print_settings_ui.py:57`). Der Prozess stirbt beim **Bauen des nächsten
Dialogs**, im Fixture-Setup — nicht beim Aufräumen des vorigen.

## Befund 3 — die Stelle ist der Zeitpunkt, nicht die Ursache

Innerhalb des Dialogbaus wandert der Frame: dreimal `_label` (dort entsteht
ein `QLabel`), einmal `_make_setting_editor`. Beides sind **Allokationen**.
Das ist das Bild einer Heap-Beschädigung, die erst zuschlägt, wenn der nächste
größere Block angefordert wird — und es deckt sich mit der Notiz in
`tests/conftest.py`, wonach ein Lauf ohne Sammler „an einer Allokation weiter
hinten" riss.

Wer die nächste Zuschreibung an eine Codezeile schreibt, schreibt damit einen
Zeitpunkt auf. Die Zeile ist unschuldig; sie ist nur die erste, die den
beschädigten Heap anfasst.

## Was ausgeschlossen ist

* **Das Messwerkzeug.** Ohne Plugin riss es an derselben Stelle nach derselben
  Zahl von Tests.
* **Der Sprachwechsel.** `test_a_dialog_built_after_a_language_change_speaks_
  that_language` steht unmittelbar vor dem Riss, und `_label` löst gerade
  träge Texte auf — ein naheliegender Verdacht. Mit `--deselect` lief es
  trotzdem in den Riss, einen Test später und an anderer Stelle. Widerlegt.
* **Ein einzelner Test.** Die Position streut über 31, 33, 33, 34 bei
  gleichbleibender Kette.

## Was das Werkzeug selbst gelehrt hat

Die erste Fassung gab **62 Zeilen lang** `handles=-1` und `arbeitssatz=0`
zurück. Ohne `argtypes`/`restype` schneidet ctypes das Prozess-Handle auf
32 Bit ab; der Aufruf gelingt scheinbar und liefert nichts. Aufgefallen ist es
nur, weil die Zahl **konstant** war — genau die Regel aus
`.claude/rules/tests.md`: Eine Zahl, die sich nicht bewegt, ist ein Zeiger.
Beide Zähler sind jetzt an einem Fall mit bekanntem Ausgang geprüft (136
Handles, 15 MB in einem nackten Python), bevor sie eine Aussage getragen
haben.

## Der nächste Schritt für den, der weitermacht

Alle bisherigen Anläufe — vier gc-Varianten, `deleteLater`, der Pin — haben am
**Zeitpunkt** angesetzt. Was den **Ort der Beschädigung** zeigen würde, ist
der Page Heap von Windows:

```
gflags /p /enable python.exe /full
```

Er lässt jede Allokation an einer eigenen Seite enden; ein Schreibzugriff
hinter das Ende bricht dann **dort** ab, wo er stattfindet, statt beim nächsten
Anfordern. Der Lauf wird dabei um ein Vielfaches langsamer — für eine Datei
mit 73 Tests ist das tragbar, für die Suite nicht. Danach unbedingt wieder
abschalten (`gflags /p /disable python.exe`).
