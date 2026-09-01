"""Der Bausteinaustausch bleibt lokal; die frühere Hosting-Strecke bleibt entfernt."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "website"

RETIRED_HOSTED_PATHS = (
    "api/shared-rules.json",
    "api/shared-texts.json",
    "api/shared.php",
    "api/shared_common.php",
    "api/shared_moderate.php",
    "api/shared_store.php",
    "boerse.html",
    "boerse.js",
    "en/exchange.html",
    "es/exchange.html",
    "fr/exchange.html",
    "it/exchange.html",
    "pt/exchange.html",
    "tauschboerse-bedingungen.html",
)

RETIRED_REPOSITORY_PATHS = (
    "tests/data/check_shared.php",
    "tests/test_shared_endpoint.py",
    "tests/test_shared_php.py",
    "tools/make_shared_cases.py",
    "tools/make_shared_rules.py",
    "tools/make_shared_texts.py",
)


def test_hosted_exchange_implementation_is_absent() -> None:
    """Website, Serverwerkzeuge und deren Paritätstests reisen nicht mehr mit."""
    remaining = [str(path) for path in RETIRED_HOSTED_PATHS if (WEBSITE / path).exists()]
    remaining.extend(path for path in RETIRED_REPOSITORY_PATHS if (ROOT / path).exists())
    assert remaining == []


def test_upload_tool_rejects_every_retired_exchange_path() -> None:
    """Eine alte Arbeitskopie kann den entfernten Dienst nicht zurückladen."""
    from tools import upload_website

    assert set(RETIRED_HOSTED_PATHS) <= upload_website.RETIRED_HOSTED_PATHS
    for relative in RETIRED_HOSTED_PATHS:
        assert not upload_website.wanted(WEBSITE / relative), relative


def test_delivered_website_has_no_link_to_the_retired_exchange() -> None:
    """Navigation, Sitemap und Skripte zeigen auf keinen früheren Hosting-Pfad."""
    # Handbuch und Changelog werden bewusst erst nach der vollständigen
    # Oberflächenprüfung neu erzeugt. Ihre Generatoren sind bereits umgestellt;
    # die noch alten Ausgaben prüft der abschließende Dokumentationslauf.
    generated_documentation = {"handbuch.html", "manual.html", "changelog.html"}
    delivered = [
        *(path for path in WEBSITE.rglob("*.html") if path.name not in generated_documentation),
        *WEBSITE.rglob("*.js"),
        *WEBSITE.rglob("*.css"),
        WEBSITE / "sitemap.xml",
        WEBSITE / "llms.txt",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in delivered if path.is_file())
    forbidden = (
        "/boerse.html",
        "/boerse.js",
        "/en/exchange.html",
        "/es/exchange.html",
        "/fr/exchange.html",
        "/it/exchange.html",
        "/pt/exchange.html",
        "/tauschboerse-bedingungen.html",
        "/api/shared",
    )
    assert [needle for needle in forbidden if needle in text] == []


def test_app_offers_the_local_recipe_file_path() -> None:
    """Der JSON-Weg der Anwendung heißt Import/Export und verspricht keinen Upload."""
    main_window = (ROOT / "app/ui/main_window.py").read_text(encoding="utf-8")
    catalog = (ROOT / "app/ui/catalog.py").read_text(encoding="utf-8")

    assert "Baustein aus Datei importieren" in main_window
    assert "Baustein als Datei exportieren" in main_window
    assert "Als Datei exportieren …" in catalog

    customer_text = "\n".join((main_window, catalog))
    assert "Veröffentlichten Baustein einlesen" not in customer_text
    assert "Veröffentlichen …" not in customer_text
    assert "zur Tauschbörse" not in customer_text
    assert "Der Server prüft dasselbe" not in customer_text
