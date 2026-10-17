"""Die Statistik zeigt den Wechsel von der deutschen Startseite in eine andere Fassung.

Herausgelöst aus ``test_public_php_security.py`` (Regel 6: keine neue
Definition in einer Datei über 2 000 Zeilen); Prüfserver und Zählzeilen von
dort.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.helpers import php_server
from tests.test_public_php_security import (
    display_today,
    stats_request,
    stats_row,
    stats_test_access,
    write_stats_rows,
)


@pytest.mark.parametrize(
    ("now_home", "before_home", "finding"),
    [
        (
            20,
            20,
            "6 von 20 Besuchen der letzten 7 Tage (30 %), in den 7 Tagen davor 1 von 20 (5 %)",
        ),
        (20, 19, "6 von 20 Besuchen der letzten 7 Tage (30 %)"),
        (19, 20, ""),
    ],
    ids=["vergleich-ab-20", "ohne-vergleich-unter-20", "stumm-unter-20"],
)
def test_stats_shows_language_switches_from_the_german_start_page(
    tmp_path: Path, now_home: int, before_home: int, finding: str
) -> None:
    """Der Sprachhinweis der deutschen Startseite wirkt nur messbar, wenn der
    Wechsel in der Auswertung steht.

    Gezählt wird nichts Neues: Ein Besuch, der auf ``/`` beginnt und danach eine
    andere Sprachfassung öffnet, ist ein Wechsel — über den Hinweis oder die
    Sprachverweise in Kopf- und Fußzeile, alle führen auf dieselbe Adresse. Ein Besuch,
    der anderswo beginnt, zählt nicht mit, auch wenn er später ``/`` öffnet.
    Der Befund vergleicht die letzten sieben Tage mit den sieben davor; das ist
    der Vorher-nachher-Vergleich um den Tag, an dem der Hinweis online geht.
    Beide Fenster stehen an der Schwelle von 20 Besuchen: Unter 20 im älteren
    fällt der Vergleich weg, unter 20 im jüngeren schweigt der Satz ganz.
    """
    today = display_today()
    day = timedelta(days=1)
    minute = timedelta(minutes=1)
    recent = today - day
    earlier = today - 9 * day

    def visit(when: datetime, mark: str, paths: list[str], download: str = "") -> list[dict]:
        rows = [stats_row(when + i * minute, "p", path, "", mark) for i, path in enumerate(paths)]
        if download:
            rows.append(stats_row(when + len(paths) * minute, "d", download, "", mark))
        return rows

    rows: list[dict] = []
    # Letzte sieben Tage: 20 oder 19 Besuche beginnen auf /. Fünf wechseln
    # nach /en/, zwei davon laden; einer kommt über eine Unterseite nach /fr/.
    for index in range(now_home):
        paths = ["/"]
        if index < 5:
            paths.append("/en/")
        elif index == 5:
            paths += ["/funktionen.html", "/fr/features.html"]
        download = "Solidon3D-Setup-0.4.1.exe" if index < 2 else ""
        rows += visit(recent, f"aaaa{index:04d}", paths, download)
    # Beginnt auf /en/ und öffnet danach / — kein Wechsel von der Startseite.
    rows += visit(recent, "bbbb0001", ["/en/", "/"])
    # Die sieben Tage davor: 20 oder 19 Besuche auf /, einer wechselt nach /es/.
    for index in range(before_home):
        rows += visit(earlier, f"cccc{index:04d}", ["/", "/es/"] if index == 0 else ["/"])
    # Ein Aufruf vor beiden Fenstern, damit der Vergleichszeitraum ganz
    # abgedeckt ist — sonst lässt die Auswertung den Vergleich zu Recht weg.
    rows += visit(today - 15 * day, "dddd0001", ["/datenschutz.html"])
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    write_stats_rows(stats, rows)
    environment, headers = stats_test_access(tmp_path)
    shown = recent.strftime("%Y-%m")
    with php_server(tmp_path, environment) as base:
        status, _headers, body = stats_request(
            f"{base}/stats.php?format=json&m={shown}", headers=headers
        )
        page_status, _page_headers, page = stats_request(
            f"{base}/stats.php?m={shown}", headers=headers
        )
    assert status == 200 and page_status == 200 and "</html>" in page
    report = json.loads(body)

    opening = "Von der deutschen Startseite in eine andere Sprachfassung gewechselt: "
    said = [item["text"] for item in report["findings"] if item["text"].startswith(opening)]
    assert said == ([f"{opening}{finding}."] if finding else [])
    if finding:
        assert f"{opening}{finding}." in page
    week = report["now"]["windows"][0]
    assert (week["now"]["home"], week["now"]["switched"]) == (now_home, 6)
    assert (week["before"]["home"], week["before"]["switched"]) == (before_home, 1)

    # Der Monat des jüngeren Fensters; das ältere liegt je nach Datum darin
    # oder im Monat davor.
    same_month = earlier.strftime("%Y-%m") == shown
    switches = report["reach"]["language_switches"]
    assert switches["home_visits"] == now_home + (before_home if same_month else 0)
    assert switches["languages"]["en"] == {"visits": 5, "downloaded": 2}
    assert switches["languages"]["fr"] == {"visits": 1, "downloaded": 0}
    assert ("es" in switches["languages"]) is same_month
    stayed = now_home - 6 + (before_home - 1 if same_month else 0)
    assert switches["stayed"] == {"visits": stayed, "downloaded": 0}
    table = page.split("<h3>Wechsel von der deutschen Startseite</h3>")[1].split("</table>")[0]
    assert re.search(
        r"<td>Englisch</td>\s*<td class=\"n\">5</td>\s*<td class=\"n\">[\d,]+ %</td>"
        r"\s*<td class=\"n\">2</td>",
        table,
    )
    assert "blieben auf Deutsch" in table
