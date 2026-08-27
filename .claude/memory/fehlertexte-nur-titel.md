---
name: fehlertexte-nur-titel
description: AppError zeigte als str() nur den Titel — der ist je Klasse gleich und sagt nichts; das Detail trägt den Grund.
metadata: 
  node_type: memory
  type: project
  originSessionId: e360bc6c-4421-4ddb-8fa4-73c323548099
  modified: 2026-08-07T11:54:50.864Z
---

`AppError.__init__` rief `super().__init__(str(self.title))`. Der Titel nennt
die **Art** des Fehlers und ist darum je Klasse identisch: über jedem
`ValidationError` stand „Ein Wert liegt außerhalb des zulässigen Bereichs" —
ob es um eine Wandstärke ging oder um ein fehlendes `@` vor einem
Parameternamen. Der Satz, der weiterhilft, steht im `detail` daneben.

**Why:** Die Oberfläche liest `title` und `detail` getrennt und zeigt beide,
also fiel es dort nie auf. Protokoll, Traceback und jedes Testskript sehen nur
`str(exception)` — und damit nichts Brauchbares. Gefunden am 07.08.2026 beim
Durchspielen von Weg 2: drei verschiedene Ausdrucksfehler, dreimal derselbe
nichtssagende Satz.

**How to apply:** Seit `6c1ff54` zeigt `str()` beide Teile. Wer einen neuen
`AppError` baut, steckt den Grund ins `detail` — der Titel bleibt die Art.
Verwandt, aber nicht dasselbe: [[fehlertexte-ohne-platzhalter]] — dort geht es
darum, dass `{platzhalter}` im Kern nicht substituiert wird; die Werte reisen
stattdessen in `values` mit.
