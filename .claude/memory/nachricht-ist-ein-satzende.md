---
name: nachricht-ist-ein-satzende
description: "Beginnt Roberts Nachricht mitten im Satz („selbst wenn wäre …"), ist sie der Rest einer längeren aus einer abgebrochenen Sitzung — die Transkriptsuche liefert den Anfang, bevor ich rate."
metadata:
  type: feedback
---

Am 11.09.2026 kam als ganze Nachricht: „selbst wenn wäre eine warnung bei in
einzelteile zerlegen gut, aber da geht nichts mehr wenn ich die operation
ausführe". Ohne Kontext hieß das drei Dinge, und ich habe eine Stunde lang den
falschen Weg gemessen (Zerlegen selbst, Dialog, Rendern — alles lief). Die
Suche über die Sitzungstranskripte (`search_session_transcripts` mit einem
Stück des Satzes) fand die Ursprungssitzung: Der Satz war das Ende einer
Meldung über Schriftzug → zerlegen → ausrichten → **Schrift wechseln**, und
erst damit ließ sich der Fall nachstellen (Halt an der Zerlegung, jeder neue
Schritt landete still dahinter).

**Why:** Eine abgebrochene Sitzung (Robert unterbricht, startet neu) trägt den
Satzanfang mit sich; im neuen Fenster steht nur der Rest. Wer den Rest als
Ganzes nimmt, misst eine Frage, die niemand gestellt hat
([[gemessene-frage-ist-nicht-die-gestellte]]).

**How to apply:** Beginnt eine Nachricht mit „selbst wenn", „aber", „und
dann" oder nennt sie „die Operation" ohne Namen — zuerst
`search_session_transcripts` mit einem markanten Teilsatz, dann
`list_events` der Treffersitzung. Auch in eigenen Kommentaren im Baum
nachsehen: Wer denselben Satz schon zitiert hat, hat den Rest gelesen.
