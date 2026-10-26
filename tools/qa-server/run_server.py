#!/usr/bin/env python3
"""Run one staged loopback QA server, observe Done, then save and stop it."""
import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--port", type=int, default=25586)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--settle", type=int, default=15)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    root = args.server.resolve()
    stage = json.loads((root / "qa-stage.json").read_text(encoding="utf-8"))
    if stage.get("forgeVersion") != "47.3.7":
        raise ValueError("Unexpected QA fixture Forge version")
    properties = (root / "server.properties").read_text(encoding="utf-8")
    if "server-ip=127.0.0.1\n" not in properties or f"server-port={args.port}\n" not in properties:
        raise ValueError("QA server must remain on the selected loopback port")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", args.port))
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    command = [str(args.java.resolve()), "-Xms512M", "-Xmx3G", "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8",
               "@libraries/net/minecraftforge/forge/1.20.1-47.3.7/win_args.txt", "nogui"]
    start = time.monotonic()
    done_at = None
    requested_stop = False
    timed_out = False
    console = root / "qa-console.log"
    with console.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=flags, text=True, encoding="utf-8")
        try:
            while process.poll() is None:
                text = console.read_text(encoding="utf-8", errors="replace")
                if done_at is None and re.search(r'Done \([\d.]+s\)! For help', text):
                    done_at = time.monotonic()
                    print("Server reached Done; observing ticks before save/stop", flush=True)
                if done_at is not None and time.monotonic() - done_at >= args.settle:
                    process.stdin.write("list\nsave-all flush\nstop\n")
                    process.stdin.flush()
                    requested_stop = True
                    break
                if time.monotonic() - start > args.timeout:
                    process.stdin.write("stop\n")
                    process.stdin.flush()
                    requested_stop = True
                    timed_out = True
                    break
                time.sleep(0.5)
            process.wait(timeout=60)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
    text = console.read_text(encoding="utf-8", errors="replace")
    errors = [line[:1500] for line in text.splitlines() if re.search(r'/(?:ERROR|FATAL)\]|Exception|Caused by:', line)]
    report = {"done": done_at is not None, "requestedGracefulStop": requested_stop,
              "timedOut": timed_out, "exitCode": process.returncode, "elapsedSeconds": round(time.monotonic() - start, 2),
              "stoppedServer": "Stopping server" in text, "savedWorld": "All dimensions are saved" in text,
              "errorLines": errors, "worldPreset": stage["worldPreset"],
              "boundary": stage.get("boundary", "dedicated backend only; no client, LAN join or Ultra Caves preset assertion")}
    (root / "qa-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if not report["done"] or report["timedOut"] or process.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
