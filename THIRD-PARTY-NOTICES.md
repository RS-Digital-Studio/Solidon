# Drittanbieter-Lizenzen

Erzeugt aus den tatsächlich installierten Laufzeit-Abhängigkeiten
(Bauplan §36). Die Freigabeliste steht in
`app/core/knowledge/data/licences.toml`, geprüft wird sie von
`tests/test_licences.py` — dort verlangt
`test_the_notice_file_names_every_runtime_package` auch, dass jedes Paket des
Laufzeitbaums hier namentlich steht. Diese Datei reist mit dem Paket
(`packaging/solidon3d.spec`), sie ist also der Hinweis, den BSD und MIT
verlangen, und nicht nur eine Übersicht.

Neu erzeugen:

    python -m app.core.knowledge.licences

| Paket | Lizenz |
|---|---|
| ImageIO | BSD-2-Clause |
| PySide6 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| Pygments | BSD-2-Clause |
| QtPy | MIT License |
| attrs | MIT |
| certifi | Mozilla Public License 2.0 (MPL 2.0) |
| charset-normalizer | MIT |
| contourpy | BSD License |
| cycler | BSD License |
| cyclopts | Apache-2.0 |
| docstring_parser | MIT License |
| fast_simplification | MIT License |
| fonttools | MIT |
| idna | BSD-3-Clause |
| kiwisolver | BSD License |
| lazy-loader | BSD-3-Clause |
| lxml | BSD-3-Clause |
| manifold3d | Apache Software License |
| markdown-it-py | MIT License |
| matplotlib | Python Software Foundation License |
| mdurl | MIT License |
| networkx | BSD-3-Clause |
| numpy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| packaging | Apache-2.0 OR BSD-2-Clause |
| pillow | MIT-CMU |
| platformdirs | MIT |
| pooch | BSD-3-Clause |
| pyparsing | MIT |
| python-dateutil | BSD License, Apache Software License |
| pyvista | MIT |
| pyvistaqt | MIT License |
| requests | Apache Software License |
| rich | MIT License |
| rich-rst | MIT |
| rtree | MIT |
| scikit-image | BSD License |
| scipy | BSD License |
| scooby | MIT |
| shapely | BSD License |
| shiboken6 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| six | MIT License |
| svg.path | MIT License |
| tifffile | BSD-3-Clause |
| trimesh | MIT License |
| typing_extensions | PSF-2.0 |
| urllib3 | MIT |
| vhacdx | BSD-3-Clause |
| vtk | BSD License |
