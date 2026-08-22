# Faktenkarten für `konzept-agent-vertiefung.md`

Recherchiert am 19.08.2026. Jede Karte trägt ihre Quelle. Was nicht gefunden
wurde, steht unter „Nicht belegbar“ — das ist kein Freibrief, es plausibel
zu ergänzen, sondern der Grund, es im Konzept offen zu lassen.

## llm-backends

_LLM-Backends für die Agentenschicht (Ollama, lokale Modelle, OpenAI-kompatible Server, gehostete Preise) — Stand 19. August 2026_

- **Anthropic — claude-sonnet-4-5** — claude-sonnet-4-5-20250929 ist heute weiterhin ein gültiger, aktiver Modellname; die Tabelle nennt als Rückzugsdatum "Not sooner than September 29, 2026", eine Abkündigung ist bisher nicht ausgesprochen (Spalte "Deprecated": N/A).
  · Stand: Abruf 19.08.2026, Seite ohne eigenes Datum · Sicherheit: belegt
  · Anmerkung: Entscheidungsrelevant für Solidon: das Datum liegt rund sechs Wochen vor uns. Anthropic sagt zu, mindestens 60 Tage vor einem Rückzug zu benachrichtigen — eine Abkündigung müsste also spätestens jetzt kommen, sonst verschiebt sich das Datum. Im Modellüberblick steht Sonnet 4.5 bereits unter "Legacy models", nicht mehr in der Haupttabelle.
  · https://platform.claude.com/docs/en/about-claude/model-deprecations
- **Anthropic — claude-sonnet-4-5 (Alias)** — Der kurze Name claude-sonnet-4-5 ist ein Bequemlichkeits-Alias auf den datierten Schnappschuss claude-sonnet-4-5-20250929; ab der 4.6-Generation gibt es keine Aliase mehr, dort ist die datumslose ID selbst der feste Schnappschuss.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wer in Solidon claude-sonnet-4-5 fest einträgt, trägt einen Alias ein, kein gepinntes Modell.
  · https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions
- **Anthropic — Nachfolger von Sonnet 4.5** — Aktiv sind heute claude-sonnet-5 (2 USD Eingabe / 10 USD Ausgabe je Mio. Token, 1 Mio. Kontext) und claude-sonnet-4-6 (3/15 USD); Sonnet 4.5 kostet 3/15 USD bei 200k Kontext.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Nachfolger ist billiger als das Modell, das er ersetzt. Ein Wechsel von 4.5 auf claude-sonnet-5 senkt die Kosten und verlängert das Kontextfenster.
  · https://platform.claude.com/docs/en/about-claude/models/overview
- **Anthropic — API-Parameter** — temperature, top_p und top_k sind ab Claude Opus 4.7 abgekündigt: ein Nicht-Standardwert liefert einen 400-Fehler.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Trifft Solidon direkt, falls die Agentenschicht temperature fest mitsendet. Bei Sonnet 4.5/4.6 noch erlaubt, bei den neuen Modellen nicht.
  · https://platform.claude.com/docs/en/about-claude/model-deprecations
- **Ollama** — Aktuelle Fassung ist v0.32.14; der Atom-Feed datiert sie auf den 16.08.2026, die Releases-Übersicht auf den 15.08.2026.
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Datumsabweichung zwischen Feed und Übersichtsseite um einen Tag; die Fassungsnummer stimmt in beiden.
  · https://github.com/ollama/ollama/releases.atom
  · https://github.com/ollama/ollama/releases
- **Ollama — Kontextfenster** — Die Standard-Kontextlänge ist seit 2026 nicht mehr fest 4096, sondern nach VRAM gestaffelt: "< 24 GiB VRAM: 4k context, 24-48 GiB VRAM: 32k context, >= 48 GiB VRAM: 256k context".
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Widerspruch in Ollamas eigener Doku: die FAQ-Seite (https://docs.ollama.com/faq) behauptet weiterhin "By default, Ollama uses a context window size of 4096 tokens". Der Quelltext gibt der context-length-Seite recht: OLLAMA_CONTEXT_LENGTH hat den Vorgabewert 0 mit dem Kommentar "(default: 4k/32k/256k based on VRAM)". Für Solidon heißt das: auf einer 16-GB-Karte bekommt der Nutzer stillschweigend 4k, ohne dass irgendwo eine Fehlermeldung erscheint.
  · https://docs.ollama.com/context-length
  · https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go
- **Ollama — Kontextfenster setzen** — num_ctx wird über das options-Objekt von /api/chat und /api/generate gesetzt; serverweit über OLLAMA_CONTEXT_LENGTH beim Start; dauerhaft je Modell über PARAMETER num_ctx in einem Modelfile plus ollama create.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Desktop-App hat zusätzlich einen Schieberegler in den Einstellungen.
  · https://docs.ollama.com/api/chat
  · https://docs.ollama.com/context-length
- **Ollama — OpenAI-Endpunkt** — Über /v1/chat/completions lässt sich die Kontextlänge nicht setzen: die OpenAI-Spezifikation kennt keinen solchen Parameter, Ollama verweist auf den Umweg über ein eigenes Modelfile mit PARAMETER num_ctx und ollama create.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Wenn Solidon Ollama über den OpenAI-kompatiblen Weg anspricht, ist das Kontextfenster nicht steuerbar — der native /api/chat-Weg ist der einzige, der num_ctx durchreicht.
  · https://docs.ollama.com/openai
- **Ollama — OpenAI-Endpunkt** — /v1/chat/completions unterstützt tools, aber tool_choice, logprobs, logit_bias und n werden nicht unterstützt.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Erzwungener Werkzeugaufruf (tool_choice: "required") ist über Ollama also nicht möglich. Wer das braucht, muss über den Systemprompt gehen oder LM Studio nehmen (dort seit 0.3.15 unterstützt).
  · https://docs.ollama.com/openai
- **Ollama — Endpunkte** — Unterstützt werden /v1/chat/completions, /v1/completions, /v1/embeddings, /v1/models und /v1/responses (die OpenAI Responses API, nur nicht-zustandsbehaftet, eingeführt in v0.13.3).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Seit v0.32.11 kann die Responses-API zusätzlich Websuche.
  · https://docs.ollama.com/openai
- **Ollama — /api/chat** — Der Parameter think akzeptiert true/false oder die Stufen "low", "medium", "high", "max"; tools nimmt Funktionsdefinitionen entgegen; stream steht standardmäßig auf true.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Denkstufen sind neu gegenüber dem Stand Mai 2026 und für Solidons Agentenschicht ein Stellhebel gegen lange Latenz.
  · https://docs.ollama.com/api/chat
- **Ollama — Empfehlung Kontext** — Ollama empfiehlt für Websuche, Agenten und Coding-Werkzeuge mindestens 64.000 Token Kontext; die belegte Länge lässt sich mit ollama ps prüfen.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Steht in direktem Widerspruch zum Vorgabewert von 4k auf einer 16-GB-Karte.
  · https://docs.ollama.com/context-length
- **Ollama — Werkzeugaufrufe** — Werkzeuge werden als JSON-Schemata übergeben; bei gestreamten Antworten müssen thinking, content und tool_calls aus allen Teilstücken eingesammelt und gemeinsam mit den Werkzeugergebnissen in die Folgeanfrage zurückgegeben werden.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite nennt keine ausdrückliche Liste werkzeugfähiger Modelle, sie zeigt nur qwen3 in den Beispielen.
  · https://docs.ollama.com/capabilities/tool-calling
- **Ollama — Modellkatalog mit Werkzeugfähigkeit** — Die Filterung auf die Fähigkeit "tools" liefert heute vorne: glm-5.2, deepseek-v4-flash, kimi-k3, qwen3.8 (27B), muse-glimmer (30B), nemotron-3.5-lightning (30B MoE), gemma4 (12B/26B/31B), qwen3.6 (27B/35B), glm-5.1, minimax-m2.7, nemotron-3-super, ornith (9B/35B), minimax-m3, nemotron3 (33B), lfm2 (24B), kimi-k2.7-code, granite4.1 (3B/8B/30B), mistral-medium-3.5 (128B), kimi-k2.6, deepseek-v4-pro.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Bemerkenswert: llama3.x, mistral, devstral und gpt-oss stehen nicht mehr vorne in dieser Liste. Das Feld hat sich seit Mai 2026 vollständig umgeschlagen.
  · https://ollama.com/search?c=tools
- **Qwen3.8-27B** — Am 14.08.2026 veröffentlicht, 27,8 Mrd. Parameter, Apache 2.0, nativ 262.144 Token Kontext (bis 1 Mio. mit RoPE-Skalierung), Text/Bild/Video, Denkmodus standardmäßig an und je Anfrage abschaltbar.
  · Stand: Modellkarte, Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Der Ollama-Tag qwen3.8:27b ist 18 GB groß und trägt die Fähigkeiten vision, tools und thinking — läuft damit auf einer 24-GB-Karte, nicht auf 16 GB.
  · https://huggingface.co/Qwen/Qwen3.8-27B
  · https://ollama.com/library/qwen3.8
- **Muse Glimmer 30B (Meta)** — Meta hat am 10.08.2026 Muse Glimmer veröffentlicht: ~30 Mrd. Parameter, Apache 2.0, ausdrücklich "tuned for tool use" mit "reliable tool-calling", gedacht für eine einzelne GPU; Meta nennt MCP Atlas 75,5, GAIA2 43,3 und τ³-Banking 23,5.
  · Stand: Meta-Modellseite, Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Selbstauskunft des Herstellers, keine unabhängige Messung. Der Ollama-Tag muse-glimmer:30b ist 18 GB groß bei 128K Kontext, Fähigkeiten vision/tools/thinking — der derzeit stärkste Kandidat für Solidons lokalen Weg auf 24 GB VRAM.
  · https://developer.meta.com/ai/models/muse-glimmer/
  · https://ollama.com/library/muse-glimmer
  · https://ollama.com/blog
- **NVIDIA Nemotron 3.5 Lightning** — Am 11.08.2026 bei Ollama erschienen: 30 Mrd. Parameter als Mixture-of-Experts mit 3 Mrd. aktiven Parametern, bis 1 Mio. Token Kontext, ausdrücklich für dauerlaufende Agenten mit Werkzeugaufrufen gebaut.
  · Stand: 11.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Tag nemotron-3.5-lightning:30b ist 25 GB groß und passt damit nicht auf eine 24-GB-Karte; die MLX-Variante ist 23 GB bei 256K Kontext. Ollama nennt keine VRAM-Zahl.
  · https://ollama.com/blog/nemotron-3-5-lightning
  · https://ollama.com/library/nemotron-3.5-lightning
- **Gemma 4 (Google)** — Werkzeugfähig, in den Größen 12B (7,6 GB Tag, 256K Kontext), 26B (18 GB) und 31B (20 GB) sowie E2B/E4B (6,5–9,6 GB, 128K, zusätzlich Audio).
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: gemma4:12b mit 7,6 GB ist der praktikable Kandidat für 16 GB VRAM. LM Studio 0.4.10 (April 2026) verbesserte ausdrücklich die Zuverlässigkeit der Gemma-4-Werkzeugaufrufe — ein Hinweis darauf, dass sie vorher nicht zuverlässig waren.
  · https://ollama.com/library/gemma4
  · https://ollama.com/search?c=tools
- **Qwen3.6** — 27B-Tag 17 GB, 35B-Tag 24 GB, jeweils 256K Kontext, mit vision/tools/thinking; vor rund drei bis vier Monaten aktualisiert.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: qwen3.6:27b (17 GB) ist der bequemste Treffer für 24 GB VRAM mit Reserve fürs Kontextfenster; 5,9 Mio. Pulls, also die breiteste Erprobung im Feld.
  · https://ollama.com/library/qwen3.6
- **IBM Granite 4.1** — Werkzeugfähig in 3B (2,1 GB), 8B (5,3 GB) und 30B (17 GB), je 128K Kontext, ausdrücklich für "function-calling tasks" beworben.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: granite4.1:8b mit 5,3 GB ist der kleinste ernsthafte Werkzeugaufrufer und passt zusammen mit einem großen Kontextfenster auf 16 GB.
  · https://ollama.com/library/granite4.1
  · https://ollama.com/search?c=tools
- **gpt-oss (OpenAI)** — Unverändert seit rund zehn Monaten: gpt-oss:20b 14 GB, gpt-oss:120b 65 GB, je 128K Kontext, mit Funktionsaufrufen und strukturierter Ausgabe. Eine neuere Fassung gibt es nicht.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: gpt-oss:20b passt mit 14 GB auf 16 GB VRAM, ist aber gemessen am August-2026-Feld ein alter Stand und steht nicht mehr in der vorderen tools-Liste.
  · https://ollama.com/library/gpt-oss
- **Devstral (Mistral)** — devstral:24b ist 14 GB groß bei 128K Kontext und seit rund einem Jahr nicht aktualisiert; ein Devstral 2 ist auf der Ollama-Seite nicht zu finden.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Sekundärquellen sprechen von einem "Devstral-2 22B"; auf Mistrals oder Ollamas eigenen Seiten habe ich das nicht bestätigt gefunden. Nicht als belegt behandeln.
  · https://ollama.com/library/devstral
- **Llama 3.3 / Mistral Small** — llama3.3:70b ist 43 GB groß (128K, tools) und seit einem Jahr unverändert; mistral-small3.2 (24B) ist ebenfalls rund ein Jahr alt und wird für "enhanced function calling" beworben.
  · Stand: Ollama-Bibliothek, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Llama 3.3 70B passt weder auf 16 noch auf 24 GB. Die Llama-Linie hat 2026 keinen Nachfolger bekommen — Meta ist stattdessen mit Muse Glimmer zurückgekommen.
  · https://ollama.com/library/llama3.3
  · https://ollama.com/search?q=mistral
- **llama.cpp** — Neuester Nightly-Bau ist b10499 vom 18.08.2026; seit dem 17.08.2026 gibt es zusätzlich semantische Fassungen v0.1.0, v0.1.1 und v0.1.2, wobei die Anmerkung lautet: "Semantic versioning is still work in progress".
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Für Solidon relevant, falls eine Mindestfassung dokumentiert werden soll: bis vor drei Tagen gab es nur Baunummern, jetzt kommt ein zweites Schema dazu.
  · https://github.com/ggml-org/llama.cpp/releases.atom
  · https://github.com/ggml-org/llama.cpp/releases
- **llama.cpp — Werkzeugaufrufe** — Funktionsaufrufe im OpenAI-Stil werden mit dem Flag --jinja aktiviert. Native Handler nennt die Doku für "Llama 3.1 / 3.3 (including builtin tools support), Llama 3.2, Functionary v3.1 / v3.2, Hermes 2/3, Qwen 2.5, Qwen 2.5 Coder, Mistral Nemo, Firefunction v2, Command R7B, DeepSeek R1"; alles andere fällt auf ein generisches Format zurück.
  · Stand: Abruf 19.08.2026 (Doku im master-Zweig) · Sicherheit: belegt
  · Anmerkung: Die Modellliste ist erkennbar veraltet (Qwen 2.5, Llama 3.x) und deckt keines der August-2026-Modelle ab. Parallele Werkzeugaufrufe sind standardmäßig aus und müssen mit "parallel_tool_calls": true angefordert werden. Starke KV-Quantisierung (-ctk q4_0) verschlechtert die Werkzeugaufrufe deutlich.
  · https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md
- **llama.cpp — Anthropic-kompatibler Endpunkt** — Seit dem 19.01.2026 stellt llama-server POST /v1/messages im Anthropic-Format bereit, samt tool_use- und tool_result-Blöcken, Streaming mit Anthropic-SSE-Ereignissen und /v1/messages/count_tokens; intern wird nach OpenAI umgesetzt.
  · Stand: 19.01.2026 · Sicherheit: belegt
  · Anmerkung: Für Solidon architektonisch interessant: derselbe Anthropic-Client könnte auf ein lokales llama-server zeigen, statt einen zweiten Adapter zu brauchen. Der Beitrag warnt, dass Werkzeugnutzung Modelle mit eingebauter Werkzeugfähigkeit voraussetzt.
  · https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp
- **LM Studio** — Neueste Fassung ist 0.4.21 vom 12.08.2026.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · https://lmstudio.ai/changelog/lmstudio
- **LM Studio — Werkzeugaufrufe** — Werkzeuge laufen über /v1/chat/completions und /v1/responses. Native Vorlagen nennt die Doku für Qwen2.5, Llama-3.1/3.2 und Mistral/Ministral (GGUF wie MLX, in der App mit Hammer-Symbol markiert); alle übrigen Modelle bekommen einen Systemprompt mit dem Ersatzformat [TOOL_REQUEST]{...}[END_TOOL_REQUEST].
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Auch diese Liste ist veraltet und nennt kein Modell aus 2026. Das Ersatzformat funktioniert laut Doku überall, aber "results vary based on training".
  · https://lmstudio.ai/docs/developer/openai-compat/tools
- **LM Studio — API-Verlauf** — tool_choice ("auto"/"none"/"required") seit 0.3.15 (24.04.2025); Streaming der Werkzeugargumente seit 0.3.17; /v1/responses seit 0.3.29 (06.10.2025) mit previous_response_id und eigenen Werkzeugen; Anthropic-kompatibles POST /v1/messages seit 0.4.1, Systemnachrichten dort seit 0.4.15.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: LM Studio ist damit derzeit der einzige der drei lokalen Server, der tool_choice, Responses-API und Anthropic-Format zugleich anbietet.
  · https://lmstudio.ai/docs/developer/api-changelog
  · https://lmstudio.ai/changelog/lmstudio
- **vLLM** — Neueste Fassung ist v0.27.1 vom 11.08.2026, aufgesetzt auf v0.27.0 vom 10.08.2026 (561 Commits, 242 Beitragende, u. a. Kimi-K3-Unterstützung, PyTorch 2.13.0, FlashAttention 4).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · https://github.com/vllm-project/vllm/releases.atom
  · https://github.com/vllm-project/vllm/releases
- **vLLM — Werkzeugaufrufe** — Werkzeugaufrufe brauchen zwei Flags: --enable-auto-tool-choice und --tool-call-parser. Parser gibt es für Hermes, Mistral, Llama 3.1/3.2/4, Qwen, DeepSeek, Granite, die OSS-Modelle von OpenAI sowie InternLM, Jamba, xLAM, Kimi, Hunyuan, Cohere Command, LongCat, GLM, FunctionGemma, Qwen3-Coder, Olmo 3, Gigachat 3 und Apertus; eigene Parser lassen sich über ToolParserManager registrieren.
  · Stand: Doku-Zeitstempel 23.06.2026, Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: vLLM hat die mit Abstand breiteste Parser-Abdeckung, verlangt aber die ausdrückliche Wahl des Parsers je Modell — für eine Desktop-Anwendung ein Konfigurationsaufwand, den Ollama und LM Studio nicht haben.
  · https://docs.vllm.ai/en/latest/features/tool_calling.html
- **OpenAI — API-Preise** — Je Mio. Token (Eingabe / zwischengespeicherte Eingabe / Ausgabe, USD): gpt-5.6-sol 5,00 / 0,50 / 30,00; gpt-5.6-terra 2,00 / 0,20 / 12,00; gpt-5.6-luna 0,20 / 0,02 / 1,20; gpt-5.5 5,00 / 0,50 / 30,00; gpt-5.4 2,50 / 0,25 / 15,00; gpt-5.4-mini 0,75 / 0,075 / 4,50; gpt-5.4-nano 0,20 / 0,02 / 1,25; gpt-5-mini 0,25 / 0,025 / 2,00; gpt-5-nano 0,05 / 0,005 / 0,40; gpt-5.3-codex 1,75 / 0,175 / 14,00.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: openai.com/api/pricing antwortet mit 403; die Preisliste liegt jetzt unter developers.openai.com. Sekundärquellen behaupten eine Preissenkung am 30.07.2026 für terra und luna — auf OpenAIs eigener Seite steht dazu nichts, die Behauptung ist unbestätigt.
  · https://developers.openai.com/api/docs/pricing
- **Google — Gemini-Preise** — Je Mio. Token (Eingabe / Ausgabe, USD, bezahlte Stufe): Gemini 3.7 Flash 0,75 / 3,75 bis 31.12.2026, danach 1,50 / 7,50; Gemini 3.6 Flash ebenso; Gemini 3.5 Flash 1,50 / 9,00; Gemini 3.5 Flash-Lite 0,30 / 2,50; Gemini 3.1 Pro Preview 2,00 / 12,00 bis 200k Prompt, darüber 4,00 / 18,00.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Der Einführungspreis von Gemini 3.7 Flash halbiert sich zum 01.01.2027 nicht, sondern verdoppelt sich — wer heute damit kalkuliert, kalkuliert mit einem Ablaufdatum.
  · https://ai.google.dev/gemini-api/docs/pricing
- **Google — Gemini-Modellkennungen** — Aktuelles Spitzenmodell ist gemini-3.7-flash, beworben für "complex coding, agentic workflows, and reliable multi-step execution"; daneben stabil: gemini-3.6-flash, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemini-2.5-flash, gemini-2.5-pro.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite nennt weder Kontextfenster je Modell noch eine Liste, welche Modelle Funktionsaufrufe können — Funktionsaufrufe werden nur allgemein als API-Fähigkeit geführt.
  · https://ai.google.dev/gemini-api/docs/models
- **Mistral — API-Preise** — Je Mio. Token (Eingabe / Ausgabe, USD): Mistral Medium 3.5 1,50 / 7,50; Mistral Small 4 0,15 / 0,60; Mistral Large 3 0,50 / 1,50; Codestral 0,30 / 0,90; Ministral 3 (3B) 0,10 / 0,10, (8B) 0,15 / 0,15, (14B) 0,20 / 0,20; GLM 5.2 über Mistral 1,40 / 4,40.
  · Stand: Abruf 19.08.2026 · Sicherheit: mehrere_quellen
  · Anmerkung: Die Übersichtsseite nennt für Mistral Large denselben Preis (0,50 / 1,50), beide Mistral-Seiten stimmen überein. Auffällig: Mistral Large 3 ist billiger als Medium 3.5.
  · https://mistral.ai/pricing/api
  · https://mistral.ai/pricing
- **DeepSeek — API-Preise** — Je Mio. Token in USD: DeepSeek-V4-Flash Eingabe bei Cache-Treffer 0,007 (Nebenzeit) / 0,014, Cache-Fehltreffer 0,22 / 0,44, Ausgabe 0,66 / 1,32. DeepSeek-V4-Pro: 0,022 / 0,044, 0,66 / 1,32, Ausgabe 1,98 / 3,96. Beide bis 1 Mio. Token Kontext und bis 384k Ausgabe.
  · Stand: Abruf 19.08.2026 · Sicherheit: unsicher
  · Anmerkung: Die Zeitangabe der Seite las sich beim Abruf widersprüchlich ("Peak hours are 01:00-04:00 and 06:00-10:00 UTC (all other hours are off-peak)" bei gleichzeitig "Off-peak rates are half of the peak rates") — die Zuordnung Haupt-/Nebenzeit vor einer Kalkulation nachprüfen. Die Preishöhe selbst ist von der Anbieterseite.
  · https://api-docs.deepseek.com/quick_start/pricing
- **xAI — Grok-Preise** — Je Mio. Token (Eingabe / zwischengespeichert / Ausgabe, USD): grok-4.6 2,00 / 0,50 / 6,00 unter 200k Prompt, darüber 4,00 / 1,00 / 12,00, 500k Kontext; grok-4.5 2,00 / 0,30 / 6,00; grok-4.3 1,25 / 0,20 / 2,50 bei 1 Mio. Kontext; grok-build-0.1 1,00 / 0,20 / 2,00 bei 256k.
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Seite sagt nicht, welche Modelle Funktionsaufrufe unterstützen. Achtung bei der Staffel: ab 200k Token wird die ganze Anfrage zum höheren Satz abgerechnet.
  · https://docs.x.ai/docs/models
- **OpenRouter** — OpenRouter nimmt 5,5 % (mindestens 0,80 USD) auf Guthabenkäufe per Stripe, 5 % bei Kryptozahlung; bei eigenen Anbieterschlüsseln (BYOK) 5 % auf die Nutzung oberhalb eines Freibetrags von 25.000 USD Listenpreis-Inferenz im Monat (Enterprise: 200.000 USD).
  · Stand: Abruf 19.08.2026 · Sicherheit: belegt
  · Anmerkung: Für eine Desktop-Anwendung mit Schlüssel des Nutzers ein realistischer vierter Weg: ein Schlüssel, viele Modelle. Der Aufschlag trifft den Nutzer beim Aufladen, nicht je Anfrage.
  · https://openrouter.ai/docs/faq
- **MCP Atlas (Scale) — Werkzeugaufruf-Benchmark** — Bestenliste zum Abruf: Muse Spark 1.1 88,10 %, Claude Opus-5 (xhigh) 85,80 %, Gemini-3.5-Flash (high) 83,60 %, Claude Fable 5 83,30 %, Kimi-K3 (max) 82,30 %, GPT-5.6 (sol) 81,80 %, bis hinunter zu Claude Haiku-4-5 mit 40,20 % bei 26 Einträgen.
  · Stand: Seite nennt 08.04.2026 als letzte Aktualisierung · Sicherheit: unsicher
  · Anmerkung: Kein offen gewichtetes, lokal lauffähiges Modell ist in der Liste ausgewiesen — der Vergleich hilft also nur für die gehosteten Wege. Sekundärquellen nennen Juni 2026 als Stand, die Seite selbst April 2026; Widerspruch nicht auflösbar.
  · https://labs.scale.com/leaderboard/mcp_atlas
- **Ollama v0.32.10 — Standardwerte** — Mit v0.32.10 (12./13.08.2026) wurde der Vorgabewert von repeat_penalty von 1,1 auf 1,0 geändert; außerdem wurde eine Umgehung der Blob-Prüfung bei OCI-Manifesten mit geteilten Digests behoben.
  · Stand: 12.–13.08.2026 · Sicherheit: belegt
  · Anmerkung: Die Änderung von repeat_penalty verändert reproduzierbare Ausgaben still — relevant, wenn Solidon Determinismus gegen Ollama prüft. Der Blob-Fix ist eine Sicherheitskorrektur beim Modellbezug.
  · https://github.com/ollama/ollama/releases.atom

**Nicht belegbar:**
- Zuverlässigkeit der Werkzeugaufrufe je lokalem Modell unter 35B: gesucht auf der Berkeley Function Calling Leaderboard (https://gorilla.cs.berkeley.edu/leaderboard.html — Tabelle wurde nicht mitgeliefert, nur Rahmentext; Stand angeblich BFCL V4 vom 12.04.2026) und auf MCP Atlas (dort kein offen gewichtetes Modell ausgewiesen). Es gibt derzeit keine von mir geprüfte, neutrale Rangliste, die sagt, welches lokale Modell Werkzeuge zuverlässig aufruft. Alles, was dazu kursiert, sind Herstellerangaben oder Blogs.
- VRAM-Bedarf der neuen Modelle: weder Meta (https://developer.meta.com/ai/models/muse-glimmer/) noch NVIDIA/Ollama (https://ollama.com/blog/nemotron-3-5-lightning) nennen eine VRAM-Zahl. Die hier angegebenen GB-Werte sind Dateigrößen der Ollama-Tags, nicht der Speicherbedarf im Betrieb — dazu kommt der KV-Cache, der beim empfohlenen 64k-Kontext erheblich ist.
- Offizielles Kontextfenster und offizielles Erscheinungsdatum von Muse Glimmer: Metas eigene Modellseite nennt beides nicht. Der Ollama-Tag zeigt 128K, Sekundärquellen nennen 131.072 und den 10.08.2026 — von Meta selbst nicht bestätigt.
- Existenz eines "Devstral 2" bzw. "Devstral-2 22B": auf https://ollama.com/library/devstral steht nur devstral:24b, seit rund einem Jahr unverändert. Nur Blogs behaupten eine zweite Fassung. Nicht als vorhanden annehmen.
- Eine neuere gpt-oss-Fassung: https://ollama.com/library/gpt-oss zeigt seit rund zehn Monaten dieselben Tags. Ein gpt-oss 2 ist nicht auffindbar.
- Ollamas Standard-Kontextlänge in der eigenen FAQ: https://docs.ollama.com/faq behauptet weiterhin fest 4096 Token und widerspricht damit https://docs.ollama.com/context-length und dem Quelltext. Welche Seite gepflegt wird, ist nicht feststellbar — der Quelltext gibt der context-length-Seite recht.
- Ob Ollamas OpenAI-Endpunkt inzwischen tool_choice unterstützt: https://docs.ollama.com/openai führt es ausdrücklich unter den nicht unterstützten Parametern. Ein Änderungseintrag, der das aufhebt, war in den Fassungsanmerkungen nicht zu finden — die Doku könnte aber hinterherhinken.
- Behauptete OpenAI-Preissenkung am 30.07.2026 (terra minus 20 %, luna minus 80 %): nur in Sekundärquellen gefunden, auf https://developers.openai.com/api/docs/pricing steht kein Änderungsdatum. Die dort abgerufenen Preise gelten, die Vorgeschichte ist unbelegt.
- Welche Grok-Modelle Funktionsaufrufe können: https://docs.x.ai/docs/models nennt Preise und Kontext, aber keine Fähigkeitenspalte.
- Preise weiterer gehosteter Anbieter, die für einen Desktop-Schlüssel in Frage kämen (Groq, Together AI, Fireworks AI, Cerebras): nicht recherchiert, keine Zahl dazu vorhanden.
- Genaue VRAM-Schwellen im Ollama-Quelltext für die Kontextstaffelung: die Dokumentation nennt "< 24 GiB / 24-48 GiB / >= 48 GiB", Sekundärquellen nennen abweichend 23 GiB und 47 GiB als tatsächliche Schwellen. Die Stelle im Quelltext, die das entscheidet, habe ich nicht gefunden (server/sched.go enthält nur die Rückstufung bei Speichermangel: 32768 → 4096 → 0).
- Ob claude-sonnet-4-5 ein formelles Abkündigungsschreiben erhalten hat: in der Deprecation-Historie auf https://platform.claude.com/docs/en/about-claude/model-deprecations gibt es keinen Eintrag dazu. Der Zustand ist "Active" mit vorläufigem Rückzugsdatum, nicht "Deprecated".

**Neu seit Anfang August:**
- Meta ist am 10.08.2026 mit Muse Glimmer zurück auf offene Gewichte gegangen: 30 Mrd. Parameter, Apache 2.0, ausdrücklich auf zuverlässige Werkzeugaufrufe getrimmt, 18 GB als Ollama-Tag — damit läuft zum ersten Mal ein für Agenten gebautes Modell auf einer einzelnen 24-GB-Karte. Für Solidons lokalen Weg ist das der wichtigste Fund der letzten drei Wochen.
- Qwen3.8-27B kam am 14.08.2026 (Apache 2.0, 262k Kontext, 18 GB Tag) und Ollama hat innerhalb von Stunden nachgezogen — v0.32.12 bis v0.32.14 drehen sich fast ausschließlich um dieses Modell. Wer eine Modellliste in Solidon fest einträgt, veraltet derzeit im Wochentakt.
- NVIDIA Nemotron 3.5 Lightning (11.08.2026, 30B MoE mit 3B aktiv, 1 Mio. Kontext) ist ausdrücklich für dauerlaufende Agenten mit Werkzeugaufrufen gebaut — mit 25 GB Tag aber knapp jenseits einer 24-GB-Karte.
- llama.cpp hat am 17.08.2026 angefangen, semantische Fassungen zu vergeben (v0.1.0 bis v0.1.2, parallel zu den Baunummern b104xx). Eine dokumentierte Mindestfassung in Solidon müsste sich jetzt entscheiden, welches Schema sie nennt.
- Ollamas Standard-Kontextlänge hängt inzwischen vom VRAM ab (4k unter 24 GiB, 32k bis 48 GiB, 256k darüber). Auf einer 16-GB-Karte bekommt ein Solidon-Nutzer also still 4096 Token, während Ollama selbst für Agenten mindestens 64.000 empfiehlt. Wenn Solidon num_ctx nicht ausdrücklich setzt, bricht die Agentensitzung auf kleiner Hardware ohne erkennbaren Grund ab.
- Ollama v0.32.10 (12.08.2026) hat den Vorgabewert von repeat_penalty von 1,1 auf 1,0 geändert — eine stille Änderung an der Ausgabe, die Determinismusprüfungen gegen ältere Ollama-Fassungen auseinanderlaufen lässt.
- Ollama v0.32.10 hat außerdem eine Umgehung der Blob-Verifikation bei OCI-Manifesten mit geteilten Digests geschlossen. Wer Ollama als Bezugsweg für Modelle beschreibt, sollte die Mindestfassung entsprechend hochsetzen.
- xAI hat am 12.08.2026 Grok 4.6 veröffentlicht (2 / 6 USD je Mio. Token unter 200k, 500k Kontext), vLLM 0.27.0/0.27.1 kamen am 10./11.08.2026, LM Studio 0.4.21 am 12.08.2026 — das gesamte Feld hat sich in der ersten Augusthälfte bewegt.
- claude-sonnet-4-5-20250929 ist noch aktiv, aber sein vorläufiges Rückzugsdatum (29.09.2026) liegt rund sechs Wochen vor uns. Der Nachfolger claude-sonnet-5 kostet mit 2/10 USD weniger als Sonnet 4.5 mit 3/15 USD und hat 1 Mio. statt 200k Kontext — der Wechsel ist billiger und besser, nicht bloß nötig.
- temperature, top_p und top_k liefern ab Claude Opus 4.7 einen 400-Fehler, wenn sie auf einen Nicht-Standardwert gesetzt werden. Wenn Solidons Agentenschicht temperature pauschal mitsendet, funktioniert sie mit Sonnet 4.5 und scheitert mit jedem neueren Modell.
