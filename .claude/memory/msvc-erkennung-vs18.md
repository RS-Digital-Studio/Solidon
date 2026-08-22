---
name: msvc-erkennung-vs18
description: "MSVC ist da (Visual Studio 18), aber setuptools/vswhere finden es nicht — bauen über vcvars64.bat plus DISTUTILS_USE_SDK=1."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8811cff7-7fae-425d-ab57-eafbbbd01787
  modified: 2026-08-08T10:19:03.147Z
---

Auf Roberts Maschine liegt der C-Compiler unter
`C:\Program Files\Microsoft Visual Studio\18\Community` (VS 18/2026, drei
MSVC-Toolsets: 14.38/14.44/14.51). Der Ordner `...\2022` ist **leer**.
`vswhere` (3.1.7) und damit setuptools finden die Installation nicht und
brechen mit „Microsoft Visual C++ 14.0 or greater is required" ab, obwohl
alles installiert ist.

**Why:** setuptools' MSVC-Suche kennt die VS-18-Registrierung nicht; die
Fehlermeldung führt in die Irre („Build Tools installieren" ist unnötig).

**How to apply:** Compiler-Umgebung von Hand aktivieren, dann bauen — per
Batch, nicht als verschachteltes cmd-Quoting durch die Git-Bash (das
scheitert am Pfad):

```bat
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set DISTUTILS_USE_SDK=1
set MSSdk=1
.venv\Scripts\python.exe tools\build_licence_module.py
```

So lief der V4c-Bau (fünf .pyd + signiertes Manifest) am 08.08.2026 lokal
durch. Siehe [[lizenz-privater-schluessel]].
