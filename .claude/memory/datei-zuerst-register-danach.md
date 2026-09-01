# Datei zuerst, Register danach

Eine dauerhafte Datei und ein Registereintrag lassen sich nicht in derselben
atomaren Betriebssystemoperation ändern. Die sichere Reihenfolge ist trotzdem
eindeutig: Den vollständigen Folgezustand beider Register zuerst isoliert
aufbauen und prüfen; dann vollständige Bytes in einer Tempdatei desselben
Zielordners schreiben, synchronisieren und atomar veröffentlichen; danach nur
noch die vorbereiteten Abbildungen aktivieren.

Beim neuen Import veröffentlicht ein harter Link ohne Überschreiben. Beim
ausdrücklichen Ersetzen tauscht `replace` die fertige Tempdatei atomar gegen die
alte. Nach diesem Commit gibt es keinen erneut fehlbaren Aufbau und keinen
Plattenrollback mehr: Eine Unterbrechung schließt beide Register vorwärts auf
den vorbereiteten neuen Zustand ab. Ein Prozessabbruch verliert ohnehin den
Speicherzustand; der nächste Start baut ihn aus der vollständigen neuen Datei.

Die Tests injizieren Teilwrite vor `fsync`, Kollision beim Veröffentlichen,
Fehler schon in der isolierten Vorbereitung und eine Unterbrechung zwischen den
beiden Registerwechseln. Außerdem trennen sie nicht unterstütztes
Verzeichnis-`fsync` von echten Datenträgerfehlern und räumen nur alte, reguläre
Tempdateien im eigenen Namensraum und Besitz. Nur das Endergebnis zählt — nie
eine halbe Datei und nie ein Registerstand, den der Neustart nicht wiederherstellen
kann.
