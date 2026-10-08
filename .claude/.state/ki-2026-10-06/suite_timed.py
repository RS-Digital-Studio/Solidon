"""Agenten-Suite mit Zeit- und Tokenzahlen je Fall, gegen einen wählbaren Baum.

python suite_timed.py <baumwurzel> <modell> <ausgabe.json> [--only id] [--ctx N]

Je Fall wird die Belegung der Grafikkarte vor dem Fall festgehalten (gpu):
Fremdlast soll im Ergebnis stehen, nicht nur im Gedächtnis.
"""
import json, subprocess, sys, time
root = sys.argv[1]
sys.path.insert(0, root)
model = sys.argv[2]
out = sys.argv[3]
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
import app, tools.run_agent_suite as runner
from app.core.backends import llm as _llm
if "--ctx" in sys.argv:
    _llm.OLLAMA_CONTEXT_TOKENS = int(sys.argv[sys.argv.index("--ctx") + 1])

def gpu():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as problem:  # nur Protokoll
        return f"? {problem}"
assert app.__file__.replace("\\", "/").startswith(root.replace("\\", "/")), app.__file__
from app.core.bootstrap import load_operations
from app.core.backends.llm import OllamaBackend
load_operations()
backend = OllamaBackend(model=model)
calls = []
original = backend.transport
def counting(url, headers, payload):
    started = time.perf_counter()
    answer = original(url, headers, payload)
    calls.append({"seconds": round(time.perf_counter() - started, 2),
                  "in": answer.get("prompt_eval_count"), "out": answer.get("eval_count"),
                  "load_s": round((answer.get("load_duration") or 0) / 1e9, 2),
                  "prompt_s": round((answer.get("prompt_eval_duration") or 0) / 1e9, 2),
                  "tools": len(payload.get("tools", ()))})
    return answer
backend.transport = counting
captured = {}
class Recording(runner.AgentSession):
    def propose(self, request):
        proposal = super().propose(request)
        captured["p"] = proposal
        return proposal
runner.AgentSession = Recording
results = []
cases = [c for c in runner.ALL_CASES if not only or c.id == only]
print(f"{model} — {len(cases)} Fälle, Baum {root}, Fenster {_llm.OLLAMA_CONTEXT_TOKENS}", flush=True)
for case in cases:
    calls.clear()
    before = gpu()
    started = time.perf_counter()
    outcome = runner.run_case(case, backend)
    seconds = time.perf_counter() - started
    entry = {"id": case.id, "good": outcome.good, "asked": outcome.asked, "ambiguous": case.ambiguous,
             "expects_part": case.expects_part, "expects_parameter": case.expects_parameter,
             "ops": list(outcome.operations), "parameters": outcome.parameters, "calls": outcome.calls,
             "invalid": outcome.invalid, "steps": outcome.steps, "error": outcome.error,
             "answer": outcome.answer[:300], "seconds": round(seconds, 1), "requests": list(calls),
             "lookups": getattr(captured.get("p"), "lookups", 0), "gpu": before, "stopped": getattr(captured.get("p"), "stopped", "")}
    captured.clear()
    results.append(entry)
    print(("ok " if outcome.good else "-- ") + f"{case.id:22} {seconds:6.1f}s  " + (outcome.error or ", ".join(outcome.operations) or "keine Operation") + ("  [gefragt]" if outcome.asked else "") + (f"  [{outcome.invalid} ungültig]" if outcome.invalid else ""), flush=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"model": model, "root": root, "window": _llm.OLLAMA_CONTEXT_TOKENS, "results": results}, handle, ensure_ascii=False, indent=1)
good = sum(e["good"] for e in results)
amb = [e for e in results if e["ambiguous"]]
calls_total = sum(e["calls"] for e in results); invalid = sum(e["invalid"] for e in results)
part = [e for e in results if e["expects_part"]]
par = [e for e in results if e["expects_parameter"]]
print(f"\ngut {good}/{len(results)}; gefragt {sum(e['asked'] for e in amb)}/{len(amb)}; "
      f"schemagültig {calls_total-invalid}/{calls_total}; Baustein {sum(any(o.startswith('insert_') for o in e['ops']) for e in part)}/{len(part)}; "
      f"Parameter {sum(bool(e['parameters']) for e in par)}/{len(par)}; Zeit {sum(e['seconds'] for e in results)/60:.1f} min", flush=True)
