"""Die Statistikseite stellt zuerst, was der Betreiber zuerst wissen will.

Oben stehen die Warnungen, dann die letzten sieben Tage als vier gleich gebaute
Karten — Downloads, Besuche, Update-Prüfungen, Seitenaufrufe — und die
Versionen derselben Woche; darunter die Sätze, die nicht schon als Zahl in
einer Karte stehen. Lange Ranglisten zeigen ihre ersten Zeilen und klappen den
Rest auf. Die JSON-Ausgabe bleibt dabei, wie Skripte sie lesen.

Herausgelöst aus ``test_public_php_security.py`` (Regel 6: keine neue
Definition in einer Datei über 2 000 Zeilen); Prüfserver und Zählzeilen von
dort.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from tests.helpers import php_server
from tests.test_public_php_security import (
    display_today,
    stats_request,
    stats_row,
    stats_test_access,
    write_stats_rows,
)

API = Path(__file__).resolve().parent.parent / "website" / "api"

#: Neun Versionen, die neueste zuerst — zwei mehr, als die Tabelle „Je Version“
#: offen zeigt.
VERSIONS = ["0.5.0", "0.4.4", "0.4.3", "0.4.2", "0.4.1", "0.4.0", "0.3.3", "0.3.1", "0.2.2"]


def _rows(today: datetime) -> list[dict]:
    """Zwei Wochen Zählzeilen mit einem Trend bei Besuchen und Downloads.

    Heute fünfzehn Besuche aus fünfzehn Herkünften, drei davon laden; acht bis
    dreizehn Tage zurück je zwei Besuche ohne Herkunft und ein Download. Jeden
    Tag prüft jede der neun Versionen einmal. Was der Monat zeigt, liegt auf
    heute, damit der Fall an jedem Kalendertag gleich ausgeht.
    """
    day = timedelta(days=1)
    minute = timedelta(minutes=1)
    rows = [
        stats_row(
            today + index * minute, "p", "/", f"quelle{index:02d}.example", f"aaaa{index:04d}"
        )
        for index in range(15)
    ]
    rows += [
        stats_row(
            today + (20 + index) * minute, "d", "Solidon3D-Setup-0.5.0.exe", "", f"aaaa{index:04d}"
        )
        for index in range(3)
    ]
    for days_ago in range(8, 14):
        when = today - days_ago * day
        rows += [
            stats_row(when + visit * minute, "p", "/", "", f"bb{days_ago:02d}{visit:04d}")
            for visit in range(2)
        ]
        rows.append(
            stats_row(
                when + 5 * minute, "d", "Solidon3D-Setup-0.4.4.exe", "", f"bb{days_ago:02d}0000"
            )
        )
    for days_ago in range(14):
        when = today - days_ago * day
        rows += [
            stats_row(when + (30 + index) * minute, "u", version)
            for index, version in enumerate(VERSIONS)
        ]
    return rows


def _render(tmp_path: Path) -> tuple[str, dict]:
    """Die Seite und ihre JSON-Ausgabe zu ``_rows``; im Download-Ordner liegt
    von der angebotenen Version nur das Windows-Paket — das ergibt eine Warnung."""
    docroot = tmp_path / "website"
    shutil.copytree(API, docroot / "api")
    (docroot / "dl").mkdir()
    (docroot / "dl" / "Solidon3D-Setup-0.5.0.exe").write_bytes(b"kein echtes Paket")
    (docroot / "version.json").write_text('{"version": "0.5.0"}', encoding="ascii")
    today = display_today()
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    write_stats_rows(stats, _rows(today))
    environment, headers = stats_test_access(tmp_path)
    shown = today.strftime("%Y-%m")
    with php_server(tmp_path, environment, docroot=docroot) as base:
        status, _headers, page = stats_request(f"{base}/stats.php?m={shown}", headers=headers)
        json_status, _json_headers, body = stats_request(
            f"{base}/stats.php?m={shown}&format=json", headers=headers
        )
    assert status == json_status == 200 and "</html>" in page
    return page, json.loads(body)


def test_stats_puts_warnings_first_and_the_week_above_the_details(tmp_path: Path) -> None:
    """Warnungen vor allem anderen, dann die Woche, erst danach die Sätze.

    Jeder Befund steht einmal auf der Seite: die Warnungen im Warnblock, der
    Satz zur aktuellen und zur ältesten Version in der Versionskarte, der Rest
    unter „Was auffällt“. Die Trendsätze der Woche stehen nicht noch einmal da —
    ihre Zahlen tragen die Karten: Wert, Veränderung und der Wert davor.
    """
    page, report = _render(tmp_path)
    marks = [
        '<h2 id="befunde">',
        'class="warnungen"',
        'id="jetzt"',
        'id="woche-versionen"',
        '<h3 class="zwischen">Was auffällt</h3>',
        '<h2 id="reichweite">',
    ]
    positions = [page.index(mark) for mark in marks]
    assert positions == sorted(positions), marks

    findings = report["findings"]
    warnings = [item["text"] for item in findings if item["tone"] == "warnung"]
    assert warnings, "der Fall braucht eine Warnung, sonst prüft er den Block nicht"
    block = page.split('class="warnungen"')[1].split("</section>")[0]
    assert block.count("<li>") == len(warnings)
    for text in warnings:
        assert f'<span class="ton">Achtung</span>{html.escape(text, quote=False)}' in block

    trends = [
        item["text"]
        for item in findings
        if item["text"].startswith(("Besuche der letzten 7 Tage", "Downloads der letzten 7 Tage"))
    ]
    assert len(trends) == 2, findings
    readable = html.unescape(page)
    for item in findings:
        expected = 0 if item["text"] in trends else 1
        assert readable.count(item["text"]) == expected, item["text"]

    # Die vier Karten in der Reihenfolge der Fragen, jede mit Wert, Veränderung
    # und dem Wert der sieben Tage davor — dieselben Zahlen wie im JSON.
    week = report["now"]["windows"][0]
    top = page.split('id="jetzt"')[1].split('id="woche-versionen"')[0]
    cards = re.findall(
        r'<h3>([^<]+)</h3>\s*<p class="wert">([\d.]+)<span class="delta[^"]*">([^<]+)</span></p>'
        r'\s*<p class="notiz">[^<]*davor ([\d.]+)</p>',
        top,
    )
    assert [card[0] for card in cards] == [
        "Downloads",
        "Besuche",
        "Update-Prüfungen",
        "Seitenaufrufe",
    ]
    for (_title, value, _delta, before), key in zip(cards, ["d", "visits", "u", "p"], strict=True):
        assert (int(value.replace(".", "")), int(before.replace(".", ""))) == (
            week["now"][key],
            week["before"][key],
        ), key
    # 15 Besuche gegen 12 und 3 Downloads gegen 6: Vorzeichen als Text, die
    # Farbe nur dazu.
    assert (cards[0][2], cards[1][2]) == ("−50 %", "+25 %")
    assert '<span class="delta minus">−50 %</span>' in top
    assert '<span class="delta plus">+25 %</span>' in top

    # Die Versionskarte nennt jede Version der Woche mit Zahl und Anteil.
    versions = page.split('id="woche-versionen"')[1].split("</article>")[0]
    for version in VERSIONS:
        assert f"<b>{version}</b>" in versions, version
    assert (
        'role="img" aria-label="Anteile an den Update-Prüfungen der letzten 7 Tage: 0.5.0 11 %'
        in versions
    )


def test_stats_folds_long_tables_behind_their_first_rows(tmp_path: Path) -> None:
    """Lange Tabellen zeigen ihre ersten Zeilen und klappen den Rest auf.

    Sechzehn Herkünfte (fünfzehn Hosts und „direkt“) zeigen zehn, neun
    Versionen die sieben farbigen; die Tabelle der Versionen Tag für Tag ist
    Rohstoff und steht ganz hinter einem geschlossenen Aufklapper. Gezählt
    wird an den Zeilen, damit eine offene zweite Tabelle nicht durchrutscht.
    """
    page, _report = _render(tmp_path)

    sources = page.split("<h3>Woher</h3>")[1].split("</article>")[0]
    shown, folded = sources.split("<details>")
    assert shown.count("<tr>") == 1 + 10, "Kopf und zehn Zeilen"
    assert "<summary>6 weitere Herkünfte</summary>" in folded
    assert folded.count("<tr>") == 6, "der Rest ohne zweiten Kopf"

    lifecycle = page.split('<h3 id="versionen">Je Version</h3>')[1].split("</article>")[0]
    shown, folded, _meaning = lifecycle.split("<details>")
    assert shown.count("<tr>") == 1 + 7
    assert "<summary>2 ältere Versionen</summary>" in folded and folded.count("<tr>") == 2

    daily = page.split("<h3>Versionen Tag für Tag</h3>")[1].split("</article>")[0]
    assert "<details>" in daily and "<details open" not in daily


def test_stats_json_keeps_every_key_scripts_read(tmp_path: Path) -> None:
    """Die Umgestaltung ändert die Seite, nicht die JSON-Ausgabe.

    Skripte lesen ``?format=json``; jeder Schlüssel, den die Ausgabe vor dem
    Umbau trug, steht weiter darin. Neue Schlüssel dürfen dazukommen, ein
    Befund trägt genau Ton und Text.
    """
    _page, report = _render(tmp_path)
    counts = {"p", "d", "u", "visits", "home", "switched"}
    contract = {
        "": (
            report,
            {
                "month",
                "zone",
                "today",
                "complete",
                "months_available",
                "findings",
                "now",
                "reach",
                "conversion",
                "usage",
            },
        ),
        "now": (report["now"], {"complete", "coverage_from", "today", "windows"}),
        "now.today": (report["now"]["today"], counts),
        "window": (report["now"]["windows"][0], {"days", "from", "to", "now", "before"}),
        "window.now": (report["now"]["windows"][0]["now"], counts),
        "reach": (
            report["reach"],
            {
                "pages",
                "visits",
                "pages_per_visit",
                "median_duration_seconds",
                "per_day",
                "months",
                "direct",
                "sources",
                "languages",
                "language_switches",
                "without_page",
                "paths",
                "unread",
                "entry_pages",
                "exit_pages",
                "depth",
                "duration",
                "by_hour",
                "by_weekday",
            },
        ),
        "reach.direct": (report["reach"]["direct"], {"visits", "pages", "downloaded", "downloads"}),
        "reach.language_switches": (
            report["reach"]["language_switches"],
            {"home_visits", "stayed", "languages"},
        ),
        "reach.paths[]": (report["reach"]["paths"][0], {"name", "count"}),
        "conversion": (
            report["conversion"],
            {
                "downloads",
                "visits_with_download",
                "visits_with_download_percent",
                "downloads_without_page",
                "platforms",
                "matrix",
                "platform_totals",
                "page_before_download",
                "files",
            },
        ),
        "conversion.matrix[]": (report["conversion"]["matrix"][0], {"version", "cells", "total"}),
        "conversion.files[]": (report["conversion"]["files"][0], {"name", "count", "bytes"}),
        "usage": (
            report["usage"],
            {
                "from",
                "to",
                "complete",
                "updates",
                "updates_per_day",
                "release",
                "release_share_percent",
                "release_share_last_7_days_percent",
                "versions",
                "version_columns",
                "versions_per_day",
                "lifecycle",
            },
        ),
        "usage.versions_per_day[]": (
            report["usage"]["versions_per_day"][0],
            {"day", "cells", "total", "new", "release_share_percent"},
        ),
        "usage.lifecycle[]": (
            report["usage"]["lifecycle"][0],
            {
                "version",
                "current",
                "published_on",
                "release_covered",
                "first_seen",
                "numbered",
                "since_data_start",
                "last_seen",
                "active_days",
                "checks",
                "share_percent",
                "last_7_days",
                "last_7_days_share_percent",
                "peak_day",
                "peak",
                "majority_from",
                "days_to_majority",
                "first_week_share_percent",
            },
        ),
    }
    for place, (value, keys) in contract.items():
        assert keys <= set(value), f"{place or 'oben'}: es fehlen {sorted(keys - set(value))}"
    assert report["findings"], "ohne Befund prüfte die letzte Zeile nichts"
    assert all(set(item) == {"tone", "text"} for item in report["findings"])
