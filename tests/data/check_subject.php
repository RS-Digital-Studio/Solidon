<?php
/**
 * Prüft encode_subject() aus website/api/support.php gegen RFC 2047.
 *
 * Aufruf: php -d extension=mbstring check_subject.php <pfad-zu-support.php>
 * Ausgabe: "ok" — oder der Grund, warum nicht.
 *
 * Warum als eigene Datei und nicht als Zeichenkette im Test: PHP in einem
 * Python-String, der wiederum PHP-Fluchtfolgen enthält, ist zweimal maskiert
 * und einmal zu oft. Hier steht PHP als PHP.
 *
 * Geladen wird die Funktion per Ausschneiden, nicht per include: support.php
 * ist ein Endpunkt, der beim Einbinden Kopfzeilen schickt und mit exit endet.
 */

declare(strict_types=1);

$source = file_get_contents($argv[1]);
if ($source === false) {
    exit('CANNOT READ ' . $argv[1]);
}
if (!preg_match('/\r?\nfunction encode_subject\(.*?\r?\n\}\r?\n/s', $source, $found)) {
    exit('encode_subject() IS GONE');
}
eval($found[0]);

$cases = [
    'x',
    str_repeat('ä', 100),          // nur Mehrbyte — hier zerschneidet ein Bytezähler
    str_repeat('x', 200),          // die volle erlaubte Länge
    'Solidon3D 0.1.1 — Fehler: Größere Schaltflächen für Türgriffe',
    '',
];

foreach ($cases as $case) {
    $encoded = encode_subject($case);
    $words = $encoded === '' ? [] : explode("\r\n ", $encoded);
    $back = '';
    foreach ($words as $word) {
        if (strlen($word) > 75) {
            exit('TOO LONG: ' . strlen($word) . ' > 75');
        }
        if (!preg_match('/^=\?UTF-8\?B\?(.*)\?=$/', $word, $part)) {
            exit('NOT AN ENCODED-WORD: ' . $word);
        }
        $back .= base64_decode($part[1]);
    }
    if ($back !== $case) {
        exit('LOST IN ENCODING: ' . $case);
    }
}

echo 'ok';
