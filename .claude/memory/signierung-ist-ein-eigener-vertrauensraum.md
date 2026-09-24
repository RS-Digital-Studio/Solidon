---
name: signierung-ist-ein-eigener-vertrauensraum
description: Signiergeheimnisse gehören nicht in den Baujob; eine prüfsummengebundene Übergabe trennt Bauen, Freigeben und Signieren — auf Windows bis auf Roberts Rechner.
metadata:
  node_type: memory
  type: project
  modified: 2026-09-23T00:00:00.000Z
---

Ein Job mit `id-token: write` gibt jedem darin laufenden Schritt die
Möglichkeit, ein OIDC-Token anzufordern. Signiergeheimnisse auf Jobebene sind
noch breiter: Auch Checkout, Paketinstallation, Generatoren und fremde Actions
laufen dann im selben Vertrauensraum. Ein `if` am Signierschritt verkleinert
diesen Raum nicht.

Solidon trennt deshalb Bauen und Signieren vollständig. Der Paketjob hat nur
`contents: read` und bindet den vollständigen Windows-App-Baum samt
Installer-Eingängen als relative Pfadliste mit SHA-256
(`solidon3d-windows-signing-input`). **Nur die Windows-Signaturen verlassen
die CI:** Anwendung und Installer werden beide dort gebaut (Entscheidung
Robert für 0.5.0, 23.09.2026). Das Certum-Zertifikat liegt in der
SimplySign-Cloud und verlangt einen Einmalcode vom Handy. Die lokale Phase
`application` von `tools/sign_release.py` prüft die Herkunft aus einem
erfolgreichen manuellen main- oder echten Versions-Tag-Lauf, das frisch geladene Archiv, jede Prüfsumme
und die Produktangaben, bevor sie die Anwendung signiert.

Ein unveröffentlichter Release-Entwurf transportiert ausschließlich die
signierte EXE und ihre Herkunftsakte zurück zur CI. Der separate Workflow
`windows-signed-installer.yml` prüft den Quellcommit, Archiv und
Anwendung samt Herausgeber und Zeitstempel und baut den Installer ohne
Signierschlüssel. Die lokale Phase `installer` bindet dessen Rückgabe und
den verbliebenen Eingangsbaum erneut an die ursprüngliche CI-Übergabe,
signiert die Setup-Datei und prüft die endgültige Releaseakte. Die genaue
Aufrufkette steht in `Signierung/README.md`. Der unsignierte Installer des
gewöhnlichen Hauptbaulaufs bleibt ein internes Prüfpaket.

**Unveröffentlichte GitHub-Entwürfe verlangen Push-Rechte.** Ein Workflow mit
`contents: read` kann den internen Transport deshalb nicht lesen; der
Installerjob erhält gezielt `contents: write`, ohne Signiergeheimnisse oder
automatische Veröffentlichung. Ein Rechtefix darf den bereits geprüften
Produktstand nicht ersetzen: Bei verschiedenen Anwendungs- und
Installercommits vergleicht ein gemeinsamer Prüfer beide vollständigen
Git-Bäume. Nur eng benannte Dateien des Signierablaufs, seiner Tests und
Dokumentation dürfen abweichen; alle übrigen Blattpfade, Typen, Modi und
Objekt-SHAs müssen gleich sein. Unvollständige Antworten halten an. Die
Installerakte nennt den tatsächlichen Installercommit und Lauf, die lokale
Phase prüft beide erneut. Eine ursprüngliche Anwendungssignatur bleibt an
ihren Quelllauf gebunden; der Versions-Tag wird dafür nie verschoben.

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
