---
name: hintergrundlauf-meldet-seinen-wrapper
description: "Ein Hintergrundlauf meldet den Status seiner Hülle, nicht den des Befehls — 282 von 448 Tests bei gemeldetem Exit 0, ohne ein einziges F."
metadata:
  node_type: memory
  type: feedback
---

`CLAUDE.md` nennt zwei Gestalten der Exit-Code-Falle: die Pipeline (`| tail`
meldet den Erfolg von `tail`) und den nachgestellten Befehl (`echo` als letztes
Glied). **Es gibt eine dritte, und sie ist die schlimmste, weil kein sichtbarer
Befehl dazwischensteht.**

Am 04.09.2026 fuhr ich `pytest tests/test_ui.py` als Hintergrundlauf. Die
Meldung: „completed (exit code 0)". Nachgezählt:

    Fortschrittszeichen: 282     gesammelt: 448
    Schlusszeile:        keine

**166 Tests hatten nie gemessen.** Der Lauf war mit einem Speicherriss
abgerissen — VTK, über dreihundert Fenster in einem Prozess. Ein Abriss
schreibt keine Zusammenfassung und zeigt kein einziges `F`; das Protokoll sieht
aus wie ein Lauf, bei dem nichts kaputt war. Die `0` kam von der Hülle des
Hintergrundlaufs, nicht von pytest.

Ohne den Zufall, dass 81 in derselben Minute vor genau diesem Fall warnte,
wäre „test_ui.py Exit 0" in meine Fertigmeldung gegangen.

**Why:** Bei Pipeline und `echo` steht der Übeltäter in der eigenen Befehlszeile
— man kann ihn sehen und weglassen. Hier steht er nicht in der Zeile: Die
Hülle gehört dem Werkzeug, und ihr Status ist ehrlich für das, was sie misst
(„der Prozess ist beendet"). Sie misst nur nicht, was man wissen will.

**How to apply:** Bei jedem Lauf, der Tests fährt, **Fortschrittszeichen gegen
Sollgröße zählen** statt auf einen Code zu sehen:

    zeichen=$(grep -oE "^[.sFEx]+" ausgabe.txt | tr -d "
" | wc -c)
    soll=$(pytest <datei> --collect-only -q | grep -c "::")

Weniger Zeichen als Soll heißt: Tests wurden verschluckt, gleich was der Code
sagt. `suite-getrennt.sh` macht genau das und halbiert dann die Portion; wer
einen eigenen Lauf baut, muss es selbst tun. Gemessen am selben Abend: Eine
Portion von 40 riss bei 7, dieselben 40 Tests liefen in Zehnergruppen grün
durch — die Portionsgröße ist der Regler, nicht der Code.

Verwandt: [[fortschrittszeichen-zaehlen-nicht-wie-collect]] (das n-te `F` ist
nicht die n-te Zeile), [[rtree-abstuerze-im-langen-lauf]],
[[native-bibliotheken-speicher]], [[gekillter-lauf-schreibt-weiter]].
