---
name: lizenz-privater-schluessel
description: Der private Ed25519-Lizenzschlüssel liegt in Roberts Dokumenten-Ordner und muss noch in den Passwortmanager und auf Papier.
metadata: 
  node_type: memory
  type: project
  originSessionId: 8811cff7-7fae-425d-ab57-eafbbbd01787
  modified: 2026-08-08T10:02:39.611Z
---

Das Lizenz-Schlüsselpaar für Solidon 1.x wurde am 08.08.2026 erzeugt. Der
öffentliche Teil steht in `app/core/activation/key.py` (`PUBLIC_KEY`); der
private liegt als Hex-Text in
`C:\Users\rober\Documents\solidon3d-lizenz-privatschluessel.txt` — **nie ins
Repository**.

**Why:** Konzept §8: geht er verloren, kann niemand mehr Schlüssel
ausstellen; wird er bekannt, braucht es eine neue Hauptversion. Vorgesehene
Ablage ist Passwortmanager plus Papierfassung an einem zweiten Ort — die
Datei in Dokumenten ist nur die Zwischenstation aus der Erzeugungssitzung.

**Am 03.09.2026 lag der Inhalt einmal in einem Sitzungsprotokoll.** Robert
hatte drei Dateien aus dem Dokumente-Ordner mitgegeben, um den *Release*-
Schlüssel zu liefern ([[release-schluessel-fuer-version-json]]); mitgelesen
wurden dabei der Lizenz-Privatschlüssel und zwanzig unbenutzte Kaufschlüssel.
Folgenlos, weil Lizenzschlüssel erst ab 1.0 gebraucht werden und noch keiner im
Umlauf ist (Entscheidung Robert) — **und genau deshalb hier vermerkt: Vor 1.0
ein neues Paar erzeugen**, solange das nichts kostet. Danach kostet es eine
Hauptversion.

Daraus folgt fürs nächste Mal: Wer einen Schlüssel braucht, nennt **die eine
Datei**, die er meint. Ein Ordner voller Geheimnisse ist kein Ort, aus dem man
„eben schnell" etwas mitgibt.

**How to apply:** Zum Ausstellen von Schlüsseln:
`python tools/make_licence_keys.py --private <pfad> --order … --holder …`.
Robert erinnern, den Inhalt in den Passwortmanager zu übernehmen und
auszudrucken; die Datei darf danach an einen sicheren Ort. Nie den Inhalt in
Ausgaben oder Commits ziehen. Siehe [[msvc-cpp-workload-fehlt]] für den
Bau des Prüfmoduls.
