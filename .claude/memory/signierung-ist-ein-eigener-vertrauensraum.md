---
name: signierung-ist-ein-eigener-vertrauensraum
description: Signiergeheimnisse gehören nicht in den Baujob; eine prüfsummengebundene Übergabe trennt Bauen, Freigeben und Signieren — auf Windows bis auf Roberts Rechner.
metadata:
  node_type: memory
  type: project
  modified: 2026-09-02T00:00:00.000Z
---

Ein Job mit `id-token: write` gibt jedem darin laufenden Schritt die
Möglichkeit, ein OIDC-Token anzufordern. Signiergeheimnisse auf Jobebene sind
noch breiter: Auch Checkout, Paketinstallation, Generatoren und fremde Actions
laufen dann im selben Vertrauensraum. Ein `if` am Signierschritt verkleinert
diesen Raum nicht.

Solidon trennt deshalb Bauen und Signieren vollständig. Der Paketjob hat nur
`contents: read` und bindet den vollständigen Windows-App-Baum samt
Installer-Eingängen als relative Pfadliste mit SHA-256
(`solidon3d-windows-signing-input`). **Windows verlässt damit die CI:** Seit
dem 02.09.2026 (Entscheidung Robert) gibt es dort keinen Azure- und keinen
PFX-Weg mehr. Das Certum-Zertifikat liegt in der SimplySign-Cloud und verlangt
einen Einmalcode vom Handy; `tools/sign_release.py` prüft das Archiv, jede
Prüfsumme und die Produktangaben, signiert die Anwendung, baut den Installer,
signiert die Setup-Datei und hält bei jeder Abweichung an, bevor ein
Zertifikat ins Spiel kommt. Die CI baut aus derselben Übergabe den
unsignierten Installer für Demo und Releaseprüfung.

macOS bleibt in der CI, mit derselben Grenze: Developer-ID-Appsignatur,
ungeschützter Paketbau und Developer-ID-Installersignatur sind drei Jobs. Die
geschützten Jobs checken nichts aus, führen kein Python und keinen
Übergabecode aus; ihr Schlüsselbund lebt nur innerhalb des festen `codesign`-
beziehungsweise `productsign`-Schritts. Notarisierung folgt erst nach dessen
Löschung.

Auch andere externe Bauwerkzeuge folgen derselben Regel: feste Veröffentlichung,
vollständige Commit-ID beziehungsweise feste Asset-URL und SHA-256 vor dem
ersten Ausführen. Beim AppImage gilt das für appimagetool **und** den
eingebetteten Type-2-Laufzeitkern; sonst bliebe ausgerechnet der erste Code des
Kundenpakets beweglich.

**How to apply:** Neue Actions nur mit vollständiger 40-stelliger Commit-ID.
Neue Downloads nur von einer unveränderlichen Veröffentlichung und nach
Prüfsummenprüfung. Einen Signierweg nie in den Paketjob legen — und für
Windows keinen in die CI: Der Weg geht über die Übergabe und das lokale
Werkzeug. Vor einem Signierschlüssel darf nur ein vollständig gebundener
Eingang liegen; danach laufen bis zur Schlüssellöschung ausschließlich fest
definierte Signier-/Prüfbefehle.
