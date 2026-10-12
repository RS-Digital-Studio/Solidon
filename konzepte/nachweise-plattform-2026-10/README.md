# Nachweise: Solidon auf Intel-Mac, Apple-Silicon-Mac und Linux (12.10.2026)

Anlass: der Verdacht, dass Solidon 0.6.0 auf echten Intel-Macs mit macOS 26
weiter nicht startet. Drei unabhängige Aufnahmen, je von einem eigenen Agenten,
am Stand `cedc42b75` (main) und am Tag-Lauf v0.6.0 (38170638968). Daraus
entstanden RM-800 bis RM-809 und die Nachträge an RM-070, RM-104 und RM-770
in `ROADMAP.md`.

| Datei | Inhalt |
|---|---|
| `bericht-forensik.md` | Jede Mach-O-Datei beider signierter Mac-Bundles (Signatur, Team-ID, Seitenhashes, Berechtigungen, Mindest-macOS, Architektur, Befehlssatz) und jede ELF-Datei des AppImage (glibc, Abhängigkeiten) — gemessen am Artefakt |
| `bericht-geschichte-ci.md` | Register, Archiv, Changelog, Startpfad im Code und die Mac-/Linux-Jobs der CI: was belegt ist, was offen, was am Runner unsichtbar bleibt |
| `bericht-web.md` | Fremde Quellen: libffi und Hardened Runtime auf x86_64, Bibliotheksprüfung, Qt und Metal auf macOS 26, wgpu, Gatekeeper, Linux (glibc, x86-64-v2, xcb, Flatpak) |
| `skripte/` | Die Messskripte der Forensik (Mach-O- und ELF-Leser ohne macOS-Werkzeuge, Befehlssatzscan mit capstone) — reiner Python-Code, von ruff ausgenommen |
| `ergebnis/` | Ihre Textauswertungen; die großen JSON-Rohdaten und die Artefakte selbst sind nicht abgelegt |

**Ergebnis in einem Satz:** Die Ursache des Intel-Hängers bis 0.5.3 ist am
Quelltext belegt, und das ausgelieferte 0.6.0 trägt die Korrektur ohne einen
Befund, der den Start verhindert; dass es auf einem echten Intel-Mac startet,
belegt erst ein Gerät. Nebenbei kamen die Fehler heraus, die RM-800 bis RM-809
führen.
