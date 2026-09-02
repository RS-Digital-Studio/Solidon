<?php
/** Gibt den Platz des signierenden, aktuell aktivierten Rechners frei. */

declare(strict_types=1);

require_once __DIR__ . '/activation_common.php';

header('Content-Type: application/json; charset=utf-8');
activation_security_headers();
try {
    activation_require_method('POST');
    activation_require_trusted_origin();
    // Erst die Erweiterung, dann Rumpf und Ratenbegrenzung: Beide brauchen
    // sodium selbst (activation_seed), und ohne die Prüfung davor endete ein
    // fehlendes sodium im allgemeinen 503 statt in der gezielten Meldung.
    if (!function_exists('sodium_crypto_sign_verify_detached')
        || !extension_loaded('pdo_sqlite')) {
        throw new ActivationFailure(
            'Der Aktivierungsdienst ist auf diesem Server noch nicht vollständig eingerichtet.',
            503,
            'service_unavailable'
        );
    }
    $raw = activation_read_json_body();
    activation_consume_client_rate('deactivate', 30, 900);
    activation_deactivate(activation_deactivation_request($raw));
    echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
} catch (ActivationFailure $problem) {
    activation_answer_error($problem);
} catch (Throwable $problem) {
    error_log('Solidon deactivation internal error: ' . get_class($problem));
    activation_answer_error(new ActivationFailure(
        'Der Aktivierungsdienst ist vorübergehend nicht verfügbar. Bitte später erneut versuchen.',
        503,
        'service_unavailable'
    ));
}
