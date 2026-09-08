---
name: pruefstand-nutzt-windows-bordmittel
description: "Vier Prüfstände scheiterten am selben Abend auf Linux und macOS, weil ihre Nachstellung Windows-Bordmittel nutzte — Git-bash als sh, socketpair als TCP, ein Dateisystem ohne Groß- und Kleinschreibung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d1ad1c97-7651-4b81-a2c7-02836d949873
  modified: 2026-09-08T00:04:24.392Z
---

Ein Prüfstand baut sein Gegenüber aus Bordmitteln — einer Shell, einem Socket,
einem Verzeichnis, einem Bibliothekspfad. **Diese Bordmittel sind unter Windows
andere**, und zwar so, dass sie mehr erlauben statt weniger. Der Prüfstand ist
hier grün und dort rot, ohne dass am Prüfling etwas anders wäre.

Gemessen am 07./08.09.2026: Der Tag-Lauf für 0.3.5 machte drei von vier Suiten
rot, während das Windows-Tor grün war, und alle vier Befunde hatten diese
Gestalt.

| Bordmittel | unter Windows | unter Linux/macOS |
|---|---|---|
| `sh` | Git für Windows liefert eine **bash** | `dash` bzw. macOS-`sh`, streng POSIX |
| `socket.socketpair()` | über TCP nachgebildet (kein AF_UNIX) | AF_UNIX — `TCP_NODELAY` wird abgelehnt |
| Dateiname | ohne Groß-/Kleinschreibung | `Solidon3D` ≠ `solidon3d` (Linux) |
| Qt-Kataloge | neben dem Python-Paket | woanders (macOS) |

Konkret: ein Shell-Funktionsname mit Bindestrich (`xvfb-run() {`) — bash nimmt
ihn, dash sagt `Bad function name` und bricht das **ganze** Skript ab, bevor
eine Zeile läuft. Darunter lag ungesehen eine zweite Schicht: `set -o pipefail`
im selben Block, ebenfalls kein POSIX. Und `http.client.connect` setzt auf
jeder Verbindung `TCP_NODELAY`, was ein Unix-Socket mit Errno 95 bzw. 102
zurückweist.

**Why:** Die Plattformmatrix findet das, aber erst im Tag-Lauf — und weil der
Paketjob an `needs: suite` hängt, entstand aus dem Tag **kein einziges Paket**.
Der Fehler saß seit dem Vortag im Baum, drei main-Läufe hatten ihn gemeldet,
und keine Sitzung hatte hingesehen, weil das lokale Tor grün war.
Verwandt: [[zusage-ueber-die-umgebung]] (Umgebung vorausgesetzt statt
hergestellt) und [[mypy-prueft-die-laufende-plattform]] (dieselbe Blindheit
eine Ebene tiefer).

**How to apply:**

- **Beim Schreiben eines Prüfstands fragen: Welches Bordmittel stelle ich
  hier ein, und ist es auf drei Plattformen dasselbe?** Wer eine Shell ruft,
  ruft die, die der Prüfling deklariert (`shell: bash` im Arbeitsablauf heißt
  bash im Test, nicht `sh`). Wer ein Socket braucht, nimmt die Art, die der
  echte Fall hat.
- **Einen Pfad nie raten, wenn die Bibliothek ihn selbst nennt.** Qts
  Kataloge liegen dort, wo `QLibraryInfo.path(TranslationsPath)` sagt — die
  Spec suchte sie neben dem Python-Paket und traf auf macOS für **keine**
  Sprache etwas. Auf jedem Standardknopf im Mac-Paket stand „Cancel".
- **Nach einem roten CI-Lauf die FAILED-Liste jeder Plattform ganz lesen,
  nicht die erste Familie beheben.** Hier lagen vier Ursachen übereinander,
  und die oberste verdeckte drei.
- **Ein grüner Lauf hier ist keine Zusage über dort.** Vor einem Tag lohnt
  `gh workflow run build.yml -f tests_only=true`: alle vier Plattformen, ohne
  Paketbau.
