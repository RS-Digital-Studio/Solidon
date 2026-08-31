/* Die Tauschbörse im Browser: suchen, blättern, hochladen.
 *
 * Eigene Datei und nicht in site.js: Die Börse ist eine Seite von vielen, und
 * ihr Skript soll nicht auf jeder anderen mitgeladen werden. Ohne fremden
 * Code, wie alles hier — die Zusage „nichts von außen" gilt für die Börse wie
 * für die Startseite.
 *
 * **Was ohne dieses Skript passiert.** Das Suchformular ist ein echtes
 * `<form>` und das Hochladeformular auch: Beide haben ein `action` und
 * funktionieren mit einem gewöhnlichen Absenden, nur ohne die schöne Antwort.
 * Was hier dazukommt, ist die Liste ohne Neuladen und ein Fehler, der als Satz
 * dasteht statt als JSON-Seite.
 *
 * **Die Fehlertexte kommen aus dem `code`-Feld der Antwort, nicht aus ihrem
 * `error`-Feld.** Der Server antwortet auf Deutsch — PHP kennt die Sprache des
 * Besuchers nicht und hat keinen Katalog. Die Seite kennt beides, also
 * übersetzt sie den Code und nimmt den Servertext nur als Rückfall, wenn ein
 * Code neu ist.
 */
(() => {
  "use strict";

  const liste = document.getElementById("ergebnis");
  if (!liste) return;

  const suche = document.querySelector(".boerse-suche");
  const hinweis = document.getElementById("ergebnis-hinweis");
  const mehrZeile = document.getElementById("mehr-zeile");
  const mehr = document.getElementById("mehr");

  /* Die Sätze zu den Codes, die der Server schicken kann. Was hier fehlt,
     fällt auf den Servertext zurück — deshalb steht die Liste nicht unter
     Vollständigkeitsdruck, und ein neuer Code bricht nichts. */
  const GRUENDE = {
    rejected: "Diese Datei ist kein Rezept, das die Börse annehmen kann.",
    too_large: "Diese Datei ist größer, als die Börse annimmt.",
    too_many: "Von dieser Adresse sind heute schon genug Einreichungen gekommen. Morgen wieder.",
    invalid_request: "Die Angaben sind unvollständig.",
    service_unavailable: "Die Börse ist gerade nicht erreichbar. Versuche es später noch einmal.",
    storage: "Der Server konnte die Datei nicht ablegen.",
    mail_failed:
      "Der Baustein liegt auf dem Server, aber die Bestätigungsmail ging nicht hinaus. " +
      "Schreib an support@solidon3d.de, dann schalten wir ihn von Hand frei.",
    server_error: "Auf dem Server ist etwas schiefgegangen.",
  };

  const LIZENZEN = {
    "CC0-1.0": "CC0",
    "CC-BY-4.0": "CC BY",
    "CC-BY-SA-4.0": "CC BY-SA",
  };

  let seite = 0;
  let gesamt = 0;

  /* Text und nicht HTML: Titel, Erklärtext und Autorenname kommen von
     Fremden. Der Server verbietet Auszeichnung darin, und diese Zeile ist die
     zweite Sperre — eine Prüfung auf der einen Seite und eine auf der anderen
     sind zwei, und genau das ist beabsichtigt. */
  const text = (wert) => document.createTextNode(String(wert ?? ""));

  const kachel = (teil) => {
    const eintrag = document.createElement("li");
    const kopf = document.createElement("h3");
    kopf.appendChild(text(teil.title));
    eintrag.appendChild(kopf);

    if (teil.doc) {
      const satz = document.createElement("p");
      satz.appendChild(text(teil.doc));
      eintrag.appendChild(satz);
    }

    const zeile = document.createElement("p");
    zeile.className = "sub";
    const stuecke = [];
    if (teil.author) stuecke.push("von " + teil.author);
    if (teil.licence) stuecke.push(LIZENZEN[teil.licence] || teil.licence);
    /* **Die eingebettete Geometrie steht an der Kachel**, nicht im Kleingedruckten:
       Wer ein Rezept übernimmt, das ein fremdes Netz mitbringt, soll es vorher
       wissen und nicht danach. */
    if (teil.has_geometry) stuecke.push("mit eingebetteter Geometrie");
    zeile.appendChild(text(stuecke.join(" · ")));
    eintrag.appendChild(zeile);

    const holen = document.createElement("a");
    holen.className = "btn ghost";
    holen.href = "/api/shared.php?do=download&slug=" + encodeURIComponent(teil.slug);
    holen.appendChild(text("Rezept holen"));
    eintrag.appendChild(holen);
    return eintrag;
  };

  const zeigen = async (anhaengen) => {
    const werte = new URLSearchParams({ do: "list", page: String(seite) });
    if (suche) {
      const q = suche.querySelector("#q");
      const lizenz = suche.querySelector("#lizenz");
      if (q && q.value.trim()) werte.set("q", q.value.trim());
      if (lizenz && lizenz.value) werte.set("licence", lizenz.value);
    }

    liste.setAttribute("aria-busy", "true");
    let antwort;
    try {
      /* **Mit Frist.** Ohne sie wartet `fetch` unbegrenzt, und die Seite steht
         auf „wird geladen", bis jemand sie neu lädt. Der Zustand, den Robert
         am 31.08.2026 gesehen hat, sah aus wie ein langsamer Server und war
         einer, der gar nicht antwortet. */
      const abbruch = new AbortController();
      const frist = setTimeout(() => abbruch.abort(), 8000);
      const daten = await fetch("/api/shared.php?" + werte.toString(), {
        signal: abbruch.signal,
      });
      clearTimeout(frist);
      /* Ein Server ohne PHP liefert die Datei als Quelltext — mit Status 200.
         `fetch` ist damit zufrieden, und erst `json()` merkt es. Deshalb wird
         beides hier gefangen und nicht nur der Netzfehler. */
      antwort = await daten.json();
    } catch (fehler) {
      liste.setAttribute("aria-busy", "false");
      /* **Nicht „prüfe deine Verbindung".** Wenn der Server nicht antwortet,
         liegt es nicht am Kunden, und ein Rat, der ihn seine Leitung suchen
         schickt, ist schlechter als keiner.

         **Und nicht den Satz aus dem Markup stehen lassen.** Der sagt heute
         „die Börse öffnet mit Version 0.2.3" — richtig, solange sie noch nicht
         offen ist, und falsch am Tag danach. Ein Zustand, der von einem Datum
         abhängt, das im HTML steht, ist einer, den irgendwann niemand mehr
         nachzieht.

         Was hier steht, stimmt in beiden Zeiten und lässt etwas tun (Regel
         17): Es sagt, was ist, und bietet den einen Griff an, der hilft. */
      liste.textContent = "";
      const gescheitert = document.createElement("p");
      gescheitert.className = "sub";
      gescheitert.appendChild(text("Die Liste lässt sich gerade nicht laden."));
      liste.appendChild(gescheitert);

      const nochmal = document.createElement("button");
      nochmal.type = "button";
      nochmal.className = "btn ghost";
      nochmal.appendChild(text("Nochmal versuchen"));
      nochmal.addEventListener("click", () => {
        seite = 0;
        zeigen(false);
      });
      liste.appendChild(nochmal);
      return;
    }
    liste.setAttribute("aria-busy", "false");

    if (!antwort.ok) {
      if (hinweis) hinweis.textContent = GRUENDE[antwort.code] || antwort.error || "";
      return;
    }

    gesamt = Number(antwort.total || 0);
    const teile = Array.isArray(antwort.parts) ? antwort.parts : [];

    let behaelter = liste.querySelector("ul");
    if (!anhaengen || !behaelter) {
      liste.textContent = "";
      behaelter = document.createElement("ul");
      behaelter.className = "boerse-liste";
      liste.appendChild(behaelter);
    }
    for (const teil of teile) behaelter.appendChild(kachel(teil));

    if (!gesamt) {
      liste.textContent = "";
      const leer = document.createElement("p");
      leer.className = "sub";
      /* **Ein leeres Ergebnis sagt, was zu tun ist** (Regel 17 gilt hier
         genauso wie in der Anwendung): Zu Anfang ist die Börse wirklich leer,
         und dann ist „nichts gefunden" die falsche Auskunft. */
      leer.textContent = werte.has("q") || werte.has("licence")
        ? "Dazu steht noch nichts in der Börse. Suche mit einem anderen Wort, oder lade den ersten Baustein selbst hoch."
        : "In der Börse steht noch nichts. Der erste Baustein kann deiner sein.";
      liste.appendChild(leer);
    }

    const gezeigt = behaelter ? behaelter.children.length : 0;
    if (mehrZeile) mehrZeile.hidden = gezeigt >= gesamt;
  };

  if (suche) {
    suche.addEventListener("submit", (ereignis) => {
      ereignis.preventDefault();
      seite = 0;
      zeigen(false);
    });
  }
  if (mehr) {
    mehr.addEventListener("click", () => {
      seite += 1;
      zeigen(true);
    });
  }

  zeigen(false);

  /* --- Hochladen ------------------------------------------------------- */

  const formular = document.getElementById("hochladen");
  const antwortfeld = document.getElementById("hochladen-antwort");
  if (!formular || !antwortfeld) return;

  const melden = (satz, gruende) => {
    antwortfeld.textContent = "";
    const absatz = document.createElement("p");
    absatz.className = "sub";
    absatz.appendChild(text(satz));
    antwortfeld.appendChild(absatz);
    if (!gruende || !gruende.length) return;
    /* **Alle Gründe auf einmal.** Der Server gibt sie so heraus, und die Seite
       zeigt sie so — wer zweimal hochladen muss, um beide zu erfahren, hat die
       schlechtere Prüfung. */
    const punkte = document.createElement("ul");
    for (const grund of gruende) {
      const punkt = document.createElement("li");
      punkt.appendChild(text(grund));
      punkte.appendChild(punkt);
    }
    antwortfeld.appendChild(punkte);
  };

  formular.addEventListener("submit", async (ereignis) => {
    ereignis.preventDefault();
    const knopf = formular.querySelector("button[type=submit]");
    if (knopf) knopf.disabled = true;
    melden("Wird geprüft …");

    try {
      const daten = await fetch(formular.action, {
        method: "POST",
        body: new FormData(formular),
      });
      const antwort = await daten.json();
      if (antwort.ok) {
        melden(
          "Angenommen. In deinem Postfach liegt ein Link — erst nach dem Klick darauf " +
            "ist der Baustein öffentlich sichtbar. Die zweite Adresse in derselben Mail " +
            "zieht ihn jederzeit wieder zurück; heb sie auf."
        );
        formular.reset();
      } else {
        melden(GRUENDE[antwort.code] || antwort.error || "Das hat nicht geklappt.", antwort.findings);
      }
    } catch (fehler) {
      melden("Die Börse war nicht erreichbar. Prüfe deine Verbindung und versuche es noch einmal.");
    } finally {
      if (knopf) knopf.disabled = false;
    }
  });
})();
