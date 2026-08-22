# Faktenkarten für `konzept-fassungspflege-2026-08.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

## python-fassungen

_Fassungsstand der Python-Abhängigkeiten (constraints.txt), Python selbst, trimesh-Grenze, Windows-Auslieferung_

- **Python (CPython)** — Die neueste stabile Fassung ist Python 3.14.7, die siebte Wartungsfreigabe der 3.14-Reihe mit rund 499 Fehlerbehebungen von 86 Beitragenden.
  · Stand: Freigegeben 5. August 2026, Seite abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Solidons Arbeitsumgebung faehrt 3.14, die CI 3.13 — beide Zweige sind im Fehlerbehebungsdienst, kein Handlungsdruck.
  · https://www.python.org/downloads/release/python-3147/
  · https://www.python.org/downloads/
- **Python (CPython)** — Die aktuellen Staende je Zweig sind 3.15.0rc1 (4.8.2026), 3.14.7 (5.8.2026), 3.13.15 (5.8.2026), 3.12.14, 3.11.16 und 3.10.21 (alle 12.8.2026).
  · Stand: Stand der Quellseite am 19. August 2026 · Sicherheit: belegt
  · Anmerkung: 3.12, 3.11 und 3.10 erhielten am selben Tag (12.8.2026) Freigaben — das Muster einer gebuendelten Sicherheitsrunde; den Anlass nennt die Seite nicht.
  · https://www.python.org/downloads/source/
- **Python (CPython)** — Im Sicherheitsdienst stehen 3.12 (bis Oktober 2028), 3.11 (bis Oktober 2027) und 3.10 (bis Oktober 2026); 3.14 und 3.13 sind im Fehlerbehebungsdienst, 3.9 ist seit 31. Oktober 2025 am Ende.
  · Stand: Statustabelle des Entwicklerhandbuchs, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: 3.10 faellt in zwei Monaten aus dem Dienst; Solidons Untergrenze liegt ohnehin bei 3.13, das beruehrt uns nicht.
  · https://devguide.python.org/versions/
  · https://www.python.org/downloads/
- **Python 3.15** — Python 3.15.0rc1 erschien am 4. August 2026, rc2 ist fuer den 1. September 2026 gesetzt und die endgueltige Freigabe fuer den 1. Oktober 2026; der Dienst laeuft bis etwa Oktober 2031.
  · Stand: PEP 790 und Python-Insider-Blog, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Kopfmerkmale sind PEP 810 (traege Importe), PEP 814 (frozendict), PEP 686 (UTF-8 als Vorgabe) und ein eingebauter Abtastprofiler (PEP 799).
  · https://peps.python.org/pep-0790/
  · https://blog.python.org/2026/08/python-3150-rc1/
- **PySide6** — Die neueste Fassung ist PySide6 6.11.2 vom 18. August 2026; festgeschrieben ist 6.11.1.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Ein Patchsprung innerhalb 6.11 — geringes Risiko, aber er enthaelt laut Qt auch Sicherheitsverbesserungen und lohnt daher.
  · https://pypi.org/project/PySide6/
  · https://pypi.org/pypi/PySide6/json
- **PySide6** — PySide6 6.11.2 deklariert als Interpreterbereich 'Python <3.15, >=3.10' — Python 3.15 wird also nicht unterstuetzt.
  · Stand: PyPI-Metadaten, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Fuer Solidon die harte Obergrenze: solange Qt keine 3.15-Raeder liefert, kann die Anwendung 3.15 (ab 1.10.2026) nicht fahren, egal was numpy und Co. koennen.
  · https://pypi.org/project/PySide6/
- **shiboken6** — shiboken6 6.11.2 erschien am 18. August 2026 und liefert abi3-Raeder fuer Python 3.10 bis 3.14 bei deklariertem Bereich 'Python <3.15, >=3.10'.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Deckt sich mit PySide6 — die beiden muessen ohnehin in gleicher Fassung laufen.
  · https://pypi.org/project/shiboken6/
- **Qt 6.11.2** — Qt 6.11.2 wurde am 18. August 2026 freigegeben und bringt rund 400 Fehlerbehebungen, Sicherheitsverbesserungen und Qualitaetskorrekturen ueber Qt 6.11.1.
  · Stand: Qt-Blog, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Reine Patchfassung, keine neuen Merkmale; welche Sicherheitsluecken gemeint sind, nennt die Ankuendigung nicht.
  · https://www.qt.io/blog/qt-6.11.2-released
- **numpy** — numpy 2.5.2 vom 9. August 2026 ist die neueste Fassung und damit identisch mit dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: 2.5.2 bringt bereits Raeder fuer Python 3.15.0rc1 und behebt, dass PyArray_StringDTypeObject in 2.5 versehentlich in der freithreading-faehigen stabilen ABI sichtbar war.
  · https://pypi.org/project/numpy/
  · https://github.com/numpy/numpy/releases/tag/v2.5.2
- **numpy 2.5.0** — numpy 2.5.0 hat Python 3.11 fallen gelassen, numpy.distutils vollstaendig entfernt und zahlreiche 2.0-Abkuendigungen verfallen lassen — darunter numpy.row_stack, recfromtxt/recfromcsv, maximum_sctype und den Datentyp-Alias 'a'.
  · Stand: NumPy-Freigabenotizen 2.5.0, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Erklaert nachtraeglich den Vorfall vom 6.8.2026 im Kopf von constraints.txt: linalg.eig liefert jetzt immer komplex, numpy.where wirft OverflowError statt still zu kuerzen, meshgrid gibt stets ein Tupel zurueck — alles Kandidaten fuer die sechzehn gefallenen Tests. Zusaetzlich: Mindestfassung Cython 3.0 und MSVC 19.35.
  · https://numpy.org/devdocs/release/2.5.0-notes.html
- **scipy** — scipy 1.18.0 vom 19. Juni 2026 ist die neueste Fassung und stimmt mit dem festgeschriebenen Stand ueberein.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf.
  · https://pypi.org/project/scipy/
- **trimesh** — trimesh 5.0.0 vom 1. August 2026 ist die neueste Fassung, verlangt Python >=3.10, und eine 6er-Reihe gibt es nicht; der festgeschriebene Stand ist bereits 5.0.0.
  · Stand: PyPI-Projektseite, PyPI-JSON und GitHub-Freigabeliste, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Als Bruch nennt die Freigabenotiz zu 5.0.0 nur den Wegfall von Python 3.8/3.9 und modernisierte Typannotationen — einen Migrationsleitfaden gibt es nicht, der Hauptversionssprung ist weit kleiner als der Name verspricht. Die Grenze 'trimesh<5' aus CLAUDE.md steht in pyproject.toml nicht mehr; dort heisst es seit dem 14.08.2026 'trimesh>=5.0'. Die GitHub-Seite wurde beim Abruf mit Jahr 2024 gelesen, PyPI nennt Aug 2026 und ist massgeblich.
  · https://pypi.org/project/trimesh/
  · https://pypi.org/pypi/trimesh/json
  · https://github.com/mikedh/trimesh/releases/tag/5.0.0
- **manifold3d** — manifold3d 3.5.2 vom 27. Juni 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand; Raeder gibt es fuer Python 3.9 bis 3.14.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf; Raeder fuer 3.14 sind vorhanden, was die Arbeitsumgebung braucht.
  · https://pypi.org/project/manifold3d/
- **shapely** — shapely 2.1.2 vom 24. September 2025 ist weiterhin die neueste Fassung; eine 2.2er-Reihe ist nicht erschienen.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Fast elf Monate ohne Freigabe — kein Risiko, aber die Bibliothek bewegt sich langsam. Entspricht dem festgeschriebenen Stand.
  · https://pypi.org/project/shapely/
- **vtk** — vtk 9.7.0 erschien am 15. August 2026 auf PyPI (Ankuendigung im VTK-Forum am 17. August 2026); festgeschrieben ist 9.6.2.
  · Stand: PyPI-Projektseite und VTK-Discourse, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Der Sprung ist derzeit gesperrt: pyvista 0.48.4 verlangt vtk<9.7.0 (siehe eigene Karte). Erst eine neue pyvista-Fassung macht ihn moeglich.
  · https://pypi.org/project/vtk/
  · https://discourse.vtk.org/t/vtk-9-7-0-release/16512
- **VTK 9.7** — VTK 9.7 verlangt mindestens Python 3.10, hat die 3.9-Raeder entfernt und bildet numpy-Typen jetzt ueber den zugrunde liegenden C-Typ ab — auf LP64 wird numpy.int64 damit zu VTK_LONG statt VTK_LONG_LONG.
  · Stand: VTK-Freigabenotizen 9.7, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Eine stille Verhaltensaenderung an der numpy-Bruecke; ausserdem entfielen die Modulkonstanten VTK_ID_TYPE_SIZE, ID_TYPE_CODE, VTK_LONG_TYPE_SIZE, LONG_TYPE_CODE und ULONG_TYPE_CODE aus numpy_support. Betrifft Solidon nur indirekt, da vtk ueber pyvista laeuft.
  · https://docs.vtk.org/en/latest/release_details/index.html
- **pyvista** — pyvista 0.48.4 vom 18. Mai 2026 ist die neueste Fassung und deklariert 'vtk>=9.2.2', 'vtk<9.7.0', 'vtk!=9.4.0' und 'vtk!=9.4.1'.
  · Stand: PyPI-Projektseite und PyPI-JSON, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Das ist der eigentliche Befund des Themenfelds: vtk 9.7.0 und pyvista 0.48.4 sind gemeinsam nicht installierbar. Solidon bleibt bei vtk 9.6.2, bis pyvista nachzieht.
  · https://pypi.org/project/pyvista/
  · https://pypi.org/pypi/pyvista/json
- **pyvistaqt** — pyvistaqt 0.12.0 vom 2. Juli 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf.
  · https://pypi.org/project/pyvistaqt/
- **scikit-image** — scikit-image 0.26.0 vom 20. Dezember 2025 ist weiterhin die neueste Fassung; eine 0.27 ist nicht erschienen.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Entspricht dem festgeschriebenen Stand.
  · https://pypi.org/project/scikit-image/
  · https://scikit-image.org/docs/stable/release_notes/release_0.26.html
- **matplotlib** — matplotlib 3.11.1 vom 18. Juli 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf.
  · https://pypi.org/project/matplotlib/
- **pillow** — pillow 12.3.0 vom 1. Juli 2026 ist die neueste Fassung; sie schliesst unter anderem CVE-2026-55798 (Befehlseinschleusung in ImageShow.WindowsViewer.get_command) sowie die Entpackbomben CVE-2026-54059, CVE-2026-54060, CVE-2026-55379 und CVE-2026-55380.
  · Stand: Pillow-Freigabenotizen 12.3.0, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Solidon ist mit 12.3.0 auf dem sicheren Stand. Aeltere Faeden derselben Reihe (CVE-2026-25990 bis 12.1.0, CVE-2026-40192 und CVE-2026-42309 bis 12.1.1) sind damit ebenfalls erledigt. Nebenwirkung laut Notiz: keine freithreading-Raeder fuer Python 3.13 mehr.
  · https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html
  · https://pypi.org/project/pillow/
- **networkx** — networkx 3.6.1 vom 8. Dezember 2025 ist die neueste stabile Fassung; 3.7 steht als 3.7rc0.dev0 noch in Entwicklung.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Entspricht dem festgeschriebenen Stand.
  · https://pypi.org/project/networkx/
  · https://networkx.org/documentation/latest/
- **rtree** — rtree 1.4.1 vom 13. August 2025 ist weiterhin die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Ein Jahr ohne Freigabe; kein Risiko erkennbar.
  · https://pypi.org/project/rtree/
- **mypy** — mypy 2.3.1 vom 15. August 2026 ist die neueste Fassung; festgeschrieben ist 2.3.0.
  · Stand: PyPI-Projektseite und mypy-Aenderungsliste, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: 2.3.1 ist reine Fehlerbehebung: mypyc-Abstuerze bei doppelt liefernden Iteratoren und bei geerbtem dataclass-default_factory, dazu Korrekturen an Koroutinenumgebung und Rueckgabewert-Entpackung — risikoarmer Sprung. Der harte Bruch lag frueher: mypy 2.0 (6. Mai 2026) schaltete --local-partial-types und --strict-bytes standardmaessig ein, aenderte --allow-redefinition und liess das Pruefziel Python 3.9 fallen; es brachte auch --num-workers fuer paralleles Pruefen. Solidon steht mit 2.3 bereits darueber.
  · https://pypi.org/project/mypy/
  · https://mypy.readthedocs.io/en/latest/changelog.html
  · https://mypy-lang.org/news.html
- **ruff** — ruff 0.16.3 vom 13. August 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite und GitHub-Freigabeliste, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: 0.16.3 bringt Vorschauregeln fuer pylint und pyupgrade sowie PGO-Uebersetzung; kein Bruch gegenueber 0.16.2 (6.8.2026) und 0.16.1 (30.7.2026). Der Bruch war 0.16.0 (23.7.2026): der Standardregelsatz wuchs von 59 auf 413 Regeln, dabei fielen 18 meinungsstarke E- und F-Regeln (E401, E402, E701–E703, E711–E714, E721, E731, E741–E743, F403, F405, F406, F722) aus der Vorgabe. Alter Zustand ueber select = ["E4","E7","E9","F"]; ausserdem koennen filename, location und end_location in der JSON-Ausgabe jetzt null sein.
  · https://pypi.org/project/ruff/
  · https://github.com/astral-sh/ruff/releases
  · https://astral.sh/blog/ruff-v0.16.0
- **pytest** — pytest 9.1.1 vom 19. Juni 2026 ist die neueste Fassung, verlangt Python >=3.10 und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseiten, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf.
  · https://pypi.org/project/pytest/
  · https://pypi.org/project/pytest/9.1.1/
- **cadquery-ocp / cadquery-ocp-novtk** — cadquery-ocp und cadquery-ocp-novtk stehen beide bei 7.9.3.1.1 vom 28. Mai 2026 — genau dem festgeschriebenen Stand — bei deklariertem Interpreterbereich 'Python <3.15, >=3.10'.
  · Stand: PyPI-Projektseiten und PyPI-JSON, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Fassungsnummer legt OCCT 7.9.3 nahe, die Paketbeschreibung nennt aber keine OCCT-Nummer ausdruecklich. Wie PySide6 sperrt auch OCP Python 3.15. Dass Solidon die novtk-Variante nimmt, haelt den OCP-Zweig aus dem vtk-Konflikt heraus.
  · https://pypi.org/project/cadquery-ocp/
  · https://pypi.org/project/cadquery-ocp-novtk/
  · https://pypi.org/pypi/cadquery-ocp/json
- **fast_simplification** — fast-simplification 0.2.0 vom 12. August 2026 ist die neueste Fassung, verlangt Python >=3.9 und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite und PyPI-JSON, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Der Sprung von 0.1.12 (August 2025) auf 0.2.0 liegt keine Woche zurueck und ist im Repository offenbar schon nachgezogen. Eine Aenderungsliste zu 0.2.0 war nicht auffindbar — ein Nebenversionssprung ohne einsehbare Notizen bleibt ein blinder Fleck.
  · https://pypi.org/project/fast-simplification/
  · https://pypi.org/pypi/fast-simplification/json
- **vhacdx** — vhacdx 0.0.10 ist die neueste Fassung; die Dateien wurden am 2. Dezember 2025 hochgeladen und decken Python 3.8 bis 3.14 ab.
  · Stand: PyPI-JSON, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Die HTML-Projektseite lieferte beim Abruf nur eine Fehlerseite; die Angabe stammt aus der JSON-Schnittstelle desselben Anbieters. Entspricht dem festgeschriebenen Stand.
  · https://pypi.org/pypi/vhacdx/json
- **lxml** — lxml 6.1.2 erschien am 19. August 2026 auf PyPI (die Aenderungsliste datiert den Stand auf 2026-08-18); festgeschrieben ist 6.1.1.
  · Stand: PyPI-Projektseite und lxml-Aenderungsliste, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Inhalt sind fehlende Dateien im Quellpaket und kleine Korrekturen an der Fehlerbehandlung; gebaut mit Cython 3.2.9. Kein Sicherheitsanlass, der Sprung ist risikoarm und nicht dringend. Die sicherheitsrelevante Fassung war die bereits festgeschriebene 6.1.1 (18.5.2026): sie ergaenzte das fehlende xlink:href in lxml.html.defs.link_attrs gegen URL-Umgehungen in eingebettetem SVG/MathML und lieferte gepatchtes libxslt gegen CVE-2025-7424 und CVE-2025-11731 (Windows-Raeder mit libxslt 1.1.45). Anbieter und PyPI nennen verschiedene Tage — Freigabe gegen Veroeffentlichung.
  · https://pypi.org/project/lxml/
  · https://lxml.de/changes-6.1.2.html
- **requests** — requests 2.34.2 vom 14. Mai 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Kein Handlungsbedarf.
  · https://pypi.org/project/requests/
- **urllib3** — urllib3 2.7.0 vom 7. Mai 2026 ist die neueste Fassung und schliesst die beiden am selben Tag veroeffentlichten hochstufigen Meldungen GHSA-mf9v-mfxr-j63j (Entpackbomben-Schutz in Teilen der Stream-Schnittstelle umgangen) und GHSA-qccp-gfcp-xxvc (sensible Kopfzeilen ueber Ursprungsgrenzen weitergereicht).
  · Stand: PyPI-Projektseite und GitHub-Sicherheitsmeldungen, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Meldungsseite fuehrt keine CVE-Nummern; Drittquellen ordnen CVE-2026-44431 und CVE-2026-44432 der Fassung 2.7.0 zu und CVE-2026-21441 der 2.6.3. Solidon ist mit 2.7.0 gedeckt. urllib3 stand nicht auf der Wunschliste, ist aber die Transportschicht unter requests und traegt hier die eigentlichen Sicherheitsinhalte.
  · https://pypi.org/project/urllib3/
  · https://github.com/urllib3/urllib3/security/advisories
- **setuptools** — setuptools 84.0.0 vom 8. August 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: 84.0.0 entfernte die Unterstuetzung fuer Konfignamen mit Bindestrich und Grossbuchstaben in setup.cfg und brach damit Teile des Oekosystems; ausserdem entfiel 'legacy-editable' und develop ruft nicht mehr easy_install. Solidon nutzt pyproject.toml, ist also nicht selbst betroffen — eine Drittabhaengigkeit im frischen Klon kann es sehr wohl sein.
  · https://pypi.org/project/setuptools/
  · https://setuptools.pypa.io/en/stable/history.html
- **Cython** — Cython 3.2.9 vom 24. Juli 2026 ist die neueste Fassung und entspricht dem festgeschriebenen Stand.
  · Stand: PyPI-Projektseite, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Relevant fuer tools/build_slice_core.py; auch lxml 6.1.2 wurde mit genau dieser Fassung gebaut. numpy 2.5 verlangt Cython >= 3.0 als Mindestfassung.
  · https://pypi.org/project/Cython/
- **PyInstaller** — PyInstaller 6.22.2 vom 17. August 2026 ist die neueste Fassung; sie unterstuetzt Python 3.8 bis 3.15 und behebt eine falsch ausgeloeste Sicherheitspruefung, wenn eine onefile-Anwendung aus einem symbolisch verknuepften Verzeichnis oder einer Junction gestartet wird.
  · Stand: PyPI-Projektseite und PyInstaller-Aenderungsliste, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Genau das Fehlerbild einer Windows-Auslieferung. 6.22.0 kam am 8.8.2026, 6.22.1 am 15.8.2026 (behob fehlerhafte Spec-Dateien bei --hide-console), 6.21.0 am 13.6.2026 brachte Python-3.15-Unterstuetzung. PyInstaller steht nicht in constraints.txt.
  · https://pypi.org/project/pyinstaller/
  · https://pyinstaller.org/en/stable/CHANGES.html
- **Inno Setup** — Die aktuelle stabile Fassung ist Inno Setup 7.1.0 vom 12. August 2026 (32- und 64-Bit-Ausgabe); die 6er-Reihe endete bei 6.7.3 vom 26. Mai 2026.
  · Stand: jrsoftware.org Downloadseite und Aenderungsverzeichnisse, abgerufen 19. August 2026 · Sicherheit: mehrere_quellen
  · Anmerkung: tools/make_installer.py verlangt laut CLAUDE.md Inno Setup 6 — die Angabe ist eine Reihe hinter dem Stand. 7 und 6 lassen sich laut Anbieter nebeneinander installieren.
  · https://jrsoftware.org/isdl.php
  · https://jrsoftware.org/files/is7-whatsnew.htm
  · https://jrsoftware.org/files/is6-whatsnew.htm
- **Inno Setup 7** — Inno Setup 7 verlangt fuer kommerzielle Nutzung eine gekaufte Lizenz; diese ist unbefristet und enthaelt zwei Jahre Aktualisierungen.
  · Stand: Inno Setup 7 Aenderungsverzeichnis, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Fuer Solidon nicht nebensaechlich: das Projekt hat eine Freischaltung mit Schluessel und Demo-Frist (app/core/activation/), ist also auf kommerzielle Auslieferung angelegt. Die Lizenzpflicht kam bereits mit 6.5.0 (12.8.2025).
  · https://jrsoftware.org/files/is7-whatsnew.htm
- **Inno Setup 7** — Inno Setup 7.0.0 brachte 64-Bit-Installer (SetupArchitecture=x64) und Pfade jenseits von MAX_PATH und benannte den Compiler von Compil32.exe in ISIDE.exe um; entfallen sind EnableFsRedirection, der Zugriff auf {sysnative} aus 64-Bit-Prozessen und Compilerdirektiven in .isl-Sprachdateien.
  · Stand: Inno Setup 7 Aenderungsverzeichnis, abgerufen 19. August 2026 · Sicherheit: belegt
  · Anmerkung: Weitere Vorgabenaenderungen: AppVerName ist jetzt leerzeichengetrennt, ArchiveExtraction steht auf 'auto', TimeStampsInUTC auf 'yes'. Ein Umstieg von 6 auf 7 ist kein reines Fassungshochzaehlen — tools/make_installer.py und das .iss-Skript muessen durch. Ergaenzend kennt Inno Setup seit 6.5.0 eine eigene Signaturpruefung ([ISSigKeys] mit ECDSA P-256, Kennzeichen issigverify, Werkzeug ISSigTool.exe); sie ist reine Unversehrtheitspruefung und ersetzt kein Authenticode.
  · https://jrsoftware.org/files/is7-whatsnew.htm
- **Windows SmartScreen** — Microsoft stellt ausdruecklich fest, dass EV-Zertifikate SmartScreen nicht mehr umgehen: OV- wie EV-signierte Anwendungen zeigen beim ersten Herunterladen eine Warnung, bis Ruf ueber Downloadvolumen aufgebaut ist.
  · Stand: Microsoft-Learn-Seite, Dokumentdatum 4. Mai 2026, zuletzt aktualisiert 17. August 2026 · Sicherheit: belegt
  · Anmerkung: Woertlich: 'EV certificates no longer bypass SmartScreen.' Der Rufaufbau dauert laut Seite mehrere Wochen und Hunderte sauberer Installationen; einen Antrag auf Pruefung gibt es fuer Endkundengeraete nicht. Ausserdem: Smart App Control unter Windows 11 blockiert unsignierte Dateien ohne positiven Ruf ganz.
  · https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- **Microsoft Artifact Signing** — Microsofts empfohlener Signierdienst fuer Auslieferung ausserhalb des Stores heisst jetzt Artifact Signing (frueher Trusted Signing), beginnt bei 9,99 US-Dollar im Monat und braucht keinen Hardware-Token.
  · Stand: Microsoft-Learn-Seite, zuletzt aktualisiert 17. August 2026 · Sicherheit: belegt
  · Anmerkung: Die Umbenennung ist neu; wer nach 'Trusted Signing' sucht, findet aeltere Anleitungen. Auch hier baut sich der Ruf erst ueber die Zeit auf — der Dienst kauft keinen Vertrauensvorschuss.
  · https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation

**Nicht belegbar:**
- Ob und wann pyvista die Obergrenze 'vtk<9.7.0' aufhebt — gesucht wurde nach 'pyvista 0.48 VTK 9.7 compatibility support' und in den pyvista-Metadaten; es gibt weder eine Fassung noch ein angekuendigtes Datum, das vtk 9.7 zulaesst.
- Das Freigabedatum von trimesh 5.0.0 auf GitHub: die Freigabeseite wurde beim Abruf als 'August 1, 2024' gelesen, PyPI nennt 'Aug 1, 2026'. Die PyPI-Angabe wurde uebernommen, die GitHub-Jahresangabe ist nicht gesichert.
- Ein ausdruecklicher Migrationsleitfaden trimesh 4 → 5 — gesucht nach 'trimesh 5.0.0 release notes breaking changes migration guide' und in trimesh.org; es existiert keiner, die Freigabenotiz nennt nur den Wegfall von Python 3.8/3.9 und modernisierte Typannotationen.
- Welche konkreten Sicherheitsluecken Qt 6.11.2 schliesst — die Ankuendigung spricht nur allgemein von 'security improvements' und nennt keine CVE-Nummern.
- Ob und wann PySide6 Raeder fuer Python 3.15 liefert — gesucht nach 'PySide6 Python 3.15 support wheels Qt for Python roadmap'; die Qt-Entwicklungsnotizen aeussern sich dazu nicht. Belegt ist nur die heutige Obergrenze 'Python <3.15'.
- Der auf jrsoftware.org/isdl.php genannte Herausgebername der Installersignatur, 'Pyrsys B.V.' — eine zweite Quelle liess sich nicht finden; die Suche nach 'Inno Setup Pyrsys jrsoftware' ergab nichts, die Suchtreffer nennen als Entwickler weiterhin Jordan Russell und Martijn Laan. Die Angabe wurde deshalb in keine Faktenkarte uebernommen.
- Eine Aenderungsliste zu fast-simplification 0.2.0 — weder die PyPI-Unterseite zur Fassung (lieferte eine Fehlerseite) noch die JSON-Schnittstelle nennen den Inhalt des Sprungs von 0.1.12 auf 0.2.0 oder das Hochladedatum der 0.2.0-Dateien; belegt ist nur das Freigabedatum 12. August 2026.
- Eine Aenderungsliste zu manifold3d 3.5.2 — gesucht nach '"manifold3d" 3.5 release changes 2026'; die Treffer fuehrten fast alle auf ein gleichnamiges DJI-Produkt. Belegt ist nur das PyPI-Freigabedatum 27. Juni 2026, nicht der Inhalt.
- Die Freigabedaten der mypy-Fassungen 2.3.0 und 2.3.1 aus der Aenderungsliste selbst — die Liste fuehrt keine Daten; der 15. August 2026 fuer 2.3.1 stammt von PyPI, der 13. Juli 2026 fuer 'Mypy 2.3' von mypy-lang.org/news.html.
- Die CVE-Nummer fuer die in Pillow 12.3.0 behobene EPS-Endlosschleife — die Pillow-Freigabenotiz beschreibt die Behebung ohne Nummer; CVE-2026-59203 stammt aus einer Drittquelle (SentinelOne) und wurde daher nicht in die Faktenkarte uebernommen.
- Die vollstaendige Deprecations- und Removals-Liste von VTK 9.7 — nur die Python- und numpy-bezogenen Punkte wurden gelesen; die Ankuendigung im VTK-Forum selbst nennt gar keine Aenderungen und verweist nur auf die Notizen.
- Ob die am 12. August 2026 gebuendelt erschienenen Python-Freigaben 3.12.14, 3.11.16 und 3.10.21 eine gemeinsame Sicherheitsursache haben — die Uebersichtsseite nennt keinen Anlass, die einzelnen Freigabeseiten wurden nicht geprueft.
- certifi wurde mitgeprueft (2026.7.22 vom 22. Juli 2026, entspricht dem Festgeschriebenen, Quelle https://pypi.org/project/certifi/), stand aber nicht auf der Wunschliste und bekam wegen der Kartengrenze keine eigene Karte.
- Fuer die uebrigen Eintraege aus constraints.txt (attrs, contourpy, cyclopts, fonttools, keyring, kiwisolver, librt, packaging, pooch, pypdf, QtPy, rich, svg.path, tifffile, typing_extensions u.a.) wurde der Fassungsstand nicht geprueft — sie standen nicht auf der Wunschliste.

**Neu seit Anfang August:**
- VTK 9.7.0 kam am 15. August 2026 auf PyPI, ist aber fuer Solidon gesperrt: pyvista 0.48.4 deklariert 'vtk<9.7.0'. Wer beim naechsten --freeze blind aktualisiert, bekommt entweder einen Aufloesungsfehler oder ein stilles Zurueckfallen auf 9.6.x. vtk gehoert damit auf die Ausnahmeliste, bis pyvista nachzieht — genau die Sorte Grenze, die tools/check_env.py --outdated ausweisen sollte.
- Python 3.15.0rc1 erschien am 4. August 2026, die endgueltige Freigabe steht auf dem 1. Oktober 2026 — aber PySide6 6.11.2, shiboken6 6.11.2 und cadquery-ocp 7.9.3.1.1 deklarieren alle 'Python <3.15'. Solidon kann 3.15 nicht am Erscheinungstag fahren, egal wie bereit die Numerik ist.
- numpy 2.5.2 (9. August 2026) liefert bereits Raeder fuer Python 3.15.0rc1, und PyInstaller unterstuetzt 3.15 seit 6.21.0 (13. Juni 2026). Die Schere zwischen vorbereiteter Numerik und Verpackung einerseits und der fehlenden Qt-Seite andererseits ist der Grund, warum ein Interpreterwechsel im Herbst blockiert.
- PySide6 und Qt sprangen am 18. August 2026 auf 6.11.2, mit rund 400 Behebungen samt Sicherheitsverbesserungen. Der Sprung 6.11.1 → 6.11.2 ist risikoarm und der lohnendste offene Punkt im ganzen Satz.
- mypy 2.3.1 (15. August 2026) ist eine reine mypyc-Fehlerbehebung ohne Verhaltensaenderung fuer die Pruefung; lxml 6.1.2 (19. August 2026, also heute) behebt nur fehlende Dateien im Quellpaket. Beide Spruenge sind ungefaehrlich, aber auch nicht dringend.
- setuptools 84.0.0 (8. August 2026) hat die Konfignamen mit Bindestrich und Grossbuchstaben in setup.cfg entfernt und damit ueber zwoelftausend Pakete gebrochen. Solidon nutzt pyproject.toml und ist nicht selbst betroffen — beim naechsten frischen Klon kann aber eine Drittabhaengigkeit daran scheitern, und das saehe aus wie ein Fehler im eigenen Aufbau.
- Inno Setup 7.1.0 (12. August 2026) hat die 6er-Reihe abgeloest. Der Umstieg ist kein Fassungshochzaehlen: der Compiler heisst jetzt ISIDE.exe statt Compil32.exe (jeder Pfadfund in tools/make_installer.py bricht), EnableFsRedirection ist weg, {sysnative} aus 64-Bit-Setups nicht mehr erreichbar, .isl-Sprachdateien duerfen keine Compilerdirektiven mehr enthalten, und AppVerName, ArchiveExtraction sowie TimeStampsInUTC haben neue Vorgaben. Kommerzielle Nutzung ist lizenzpflichtig. CLAUDE.md nennt weiterhin Inno Setup 6.
- PyInstaller veroeffentlichte binnen zehn Tagen 6.22.0, 6.22.1 und 6.22.2 (8., 15. und 17. August 2026). 6.22.2 behebt eine falsch ausgeloeste Bootloader-Sicherheitspruefung, wenn eine onefile-Anwendung aus einer Junction oder einem symbolisch verknuepften Verzeichnis startet — unter Windows ein realistisches Auslieferungsbild und ein Grund, nicht auf 6.22.0 stehenzubleiben.
- Die Microsoft-Seite zu SmartScreen wurde am 17. August 2026 zuletzt angefasst und stellt ausdruecklich fest, dass EV-Zertifikate SmartScreen nicht mehr umgehen; der empfohlene Dienst heisst jetzt Artifact Signing (frueher Trusted Signing), ab 9,99 US-Dollar im Monat. Wer die Auslieferung von Solidon plant, muss mit Warnungen in den ersten Wochen rechnen — unabhaengig vom Zertifikatstyp und vom Preis.
- Die trimesh-Grenze aus der Aufgabenstellung stimmt nicht mehr: pyproject.toml verlangt seit dem 14. August 2026 'trimesh>=5.0', constraints.txt schreibt 5.0.0 fest, und PyPI bestaetigt 5.0.0 als neuesten Stand. CLAUDE.md nennt 'trimesh<5' weiter als aufgeschobene Migration — die Hausordnung ist an dieser Stelle veraltet und sollte nachgezogen werden, sonst schiebt der naechste Durchgang eine Migration auf, die es nicht mehr gibt.
