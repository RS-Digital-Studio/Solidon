---
name: inno-setup-7-nicht-ueber-winget
description: "Inno Setup 7 kommt nicht über winget (dort steht nur 6.7.3), sondern als signierte Datei aus dem GitHub-Release jrsoftware/issrc; seit dem 05.09.2026 liegt 7.1.0 per Benutzer neben der 6"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T16:43:05.150Z
---

`winget upgrade` kennt für `JRSoftware.InnoSetup` nur 6.7.3, und
`https://jrsoftware.org/download.php/is.exe` liefert keine Datei, sondern eine
HTML-Seite mit den Links. Der Weg zur 7 (05.09.2026):

- Datei: `https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe`
  (14,3 MB), Authenticode gültig, Aussteller `Pyrsys B.V.` (Noord-Holland).
- Installation per Benutzer wie die vorhandene 6:
  `innosetup-7.1.0-x64.exe /VERYSILENT /CURRENTUSER /NORESTART /SUPPRESSMSGBOXES`
  → `%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe`; die 6 bleibt daneben liegen.
- `tools/make_installer.find_compiler()` nimmt seither die 7 zuerst
  (`COMPILER_CANDIDATES`); der Bau der Setup-Datei mit 7 steht als Registerpunkt
  in `ROADMAP.md`.

**Why:** Der Gesamtreview vom 05.09.2026 verlangte 7.1.0; wer nur winget fragt,
hält 6.7.3 für den neuesten Stand.

**How to apply:** Bei der nächsten Version von Inno Setup zuerst das
GitHub-Release ansehen, die Signatur mit `Get-AuthenticodeSignature` prüfen,
dann per Benutzer installieren. Siehe [[installer-probe-nicht-mit-fenster]].
