"""Fährt Renderer nacheinander und erhält die gesamte Prozesshistorie einer Phase."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def append_record(path, record):
    """Vorhandene Durchgänge erhalten, auch nach Pause und erneutem Start."""
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not any(row.get("run_id") == record["run_id"] for row in rows):
        rows.append(record)
    temporary = path.with_suffix(".next.json")
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def gpu():
    try:
        run = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10,
             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return run.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--indices", nargs="+", type=int, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--gesture-only", action="store_true")
    parser.add_argument("--renderers", nargs="+", choices=("gfx", "vtk"), default=["gfx", "vtk"])
    args = parser.parse_args()
    source = args.source.resolve()
    failed = 0
    for index in args.indices:
        for backend in args.renderers:
            if (ROOT / "pause-before-next").exists():
                print("PAUSE", flush=True)
                return 75
            run_id = uuid.uuid4().hex
            command = [sys.executable, str(ROOT / "probe.py"), "--index", str(index),
                       "--renderer", backend, "--source", str(source), "--phase", args.phase]
            if args.full:
                command.append("--full")
            if args.gesture_only:
                command.append("--gesture-only")
            environment = dict(os.environ, SOLIDON_AUDIT_RUN_ID=run_id)
            out = ROOT / args.phase / backend / f"file-{index:02d}"
            out.mkdir(parents=True, exist_ok=True)
            print(f"START {args.phase} {index:02d} {backend}", flush=True)
            before = gpu()
            started = time.time()
            record = {"run_id": run_id, "index": index, "renderer": backend, "phase": args.phase,
                      "started_at": started, "full": args.full, "gesture_only":args.gesture_only,
                      "source_directory": str(source), "output_directory":str(out),
                      "command": command, "gpu_start": before}
            try:
                run = subprocess.run(command, cwd=str(source), env=environment, timeout=960,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                record["exit"] = run.returncode
            except subprocess.TimeoutExpired:
                record.update(exit=124, process_timeout=True)
            except OSError as error:
                record.update(exit=127, launch_error=str(error))
            record.update(elapsed_seconds=time.time()-started, gpu_end=gpu())
            result = out / "result.json"
            if result.exists():
                data = json.loads(result.read_text(encoding="utf-8"))
                fresh = data.get("run_id") == run_id
                record["result_belongs_to_run"] = fresh
                if fresh:
                    record["complete"] = data.get("complete", False)
                    record["fatal"] = data.get("fatal")
                    record["source_unchanged"] = {
                        name: hashlib.sha256((source/name).read_bytes()).hexdigest() == value
                        for name, value in data["source_files_sha256"].items()}
                    record["metrics"] = {row["label"]: {key: value for key, value in row.items()
                                          if key.endswith("_ms")}
                                         for row in data["checks"] if "median_ms" in row}
            payload = json.dumps(record, ensure_ascii=False, indent=2)
            (out / "process.json").write_text(payload, encoding="utf-8")
            (out / f"process-{run_id}.json").write_text(payload, encoding="utf-8")
            append_record(ROOT / (args.phase + "-processes.json"), record)
            unchanged = all(record.get("source_unchanged", {}).values())
            failed += int(record["exit"] != 0 or not record.get("complete") or not unchanged)
            print(json.dumps({key:record.get(key) for key in
                ("index","renderer","phase","exit","complete","elapsed_seconds","metrics")}
                | {"source_unchanged":unchanged}, ensure_ascii=False), flush=True)
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())

