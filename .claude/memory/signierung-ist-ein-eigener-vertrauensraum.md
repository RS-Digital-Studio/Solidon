---
name: signierung-ist-ein-eigener-vertrauensraum
description: OIDC und Signiergeheimnisse gehören nicht in den Baujob; eine prüfsummengebundene Übergabe trennt Bauen, Freigeben und Signieren.
metadata:
  node_type: memory
  type: project
  modified: 2026-08-31T00:00:00.000Z
---

Ein Job mit `id-token: write` gibt jedem darin laufenden Schritt die
Möglichkeit, ein OIDC-Token anzufordern. Signiergeheimnisse auf Jobebene sind
noch breiter: Auch Checkout, Paketinstallation, Generatoren und fremde Actions
laufen dann im selben Vertrauensraum. Ein `if` am Signierschritt verkleinert
diesen Raum nicht.

Solidon trennt deshalb sogar **zwischen** zwei Signaturen. Der Paketjob hat nur
`contents: read` und bindet den vollständigen App-Baum samt Installer-Eingängen
als relative Pfadliste mit SHA-256. Ein geschützter Azure-Job prüft Archiv,
exakte Dateimenge, Pfadcontainment und feste Produktpfade und signiert nur die
Anwendung. Der ISCC-Lauf folgt in einem ungeschützten Job. Erst danach signiert
ein zweiter geschützter Azure-Job die fest benannte Setup-Datei. Nur diese zwei
Jobs erhalten `id-token: write`. Die beiden PFX-Jobs haben kein OIDC und löschen
ihre PFX jeweils im festen Signierschritt; der unsignierte Weg berührt keinen
geschützten Job.

macOS folgt derselben Grenze: Developer-ID-Appsignatur, ungeschützter
Paketbau und Developer-ID-Installersignatur sind drei Jobs. Die geschützten
Jobs checken nichts aus, führen kein Python und keinen Übergabecode aus; ihr
Schlüsselbund lebt nur innerhalb des festen `codesign`- beziehungsweise
`productsign`-Schritts. Notarisierung folgt erst nach dessen Löschung.

Auch andere externe Bauwerkzeuge folgen derselben Regel: feste Veröffentlichung,
vollständige Commit-ID beziehungsweise feste Asset-URL und SHA-256 vor dem
ersten Ausführen. Beim AppImage gilt das für appimagetool **und** den
eingebetteten Type-2-Laufzeitkern; sonst bliebe ausgerechnet der erste Code des
Kundenpakets beweglich.

**How to apply:** Neue Actions nur mit vollständiger 40-stelliger Commit-ID.
Neue Downloads nur von einer unveränderlichen Veröffentlichung und nach
Prüfsummenprüfung. Einen neuen Signierweg nie in den Paketjob legen. Vor einem
Signierschlüssel darf nur ein vollständig gebundener Eingang liegen; danach
laufen bis zur Schlüssellöschung ausschließlich fest definierte
Signier-/Prüfbefehle.
