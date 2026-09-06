<?php
/**
 * In welcher Zeitzone Tage gezählt und angezeigt werden.
 *
 * Gespeichert wird UTC. count.php zieht hier die Tagesgrenze, stats.php zeigt in
 * derselben Zone an — eine Stelle, damit beide dieselbe bleiben. Bis zum
 * 06.09.2026 stand der Name in beiden Dateien, mit einem Kommentar, der auf die
 * jeweils andere verwies.
 */
declare(strict_types=1);

const DAY_ZONE = 'Europe/Berlin';
