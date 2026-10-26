#!/usr/bin/env python3
"""Move proven client-only JARs aside inside an existing disposable QA fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, default=Path(__file__).with_name("client-only-exclusions.json"))
    args = parser.parse_args()
    root = args.server.resolve()
    stage_path = root / "qa-stage.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    if stage.get("purpose") != "independent private dedicated QA; no personal world":
        raise ValueError("Not a disposable QA fixture")
    by_path = {row["path"]: row for row in stage["sourceFiles"]}
    exclusions = json.loads(args.exclusions.read_text(encoding="utf-8"))
    targets = []
    for row in exclusions:
        relative = Path(row["path"])
        source = (root / relative).resolve()
        destination = (root / "excluded-client-mods" / relative.name).resolve()
        if (not source.is_relative_to(root / "mods") or len(relative.parts) != 2 or
                not destination.is_relative_to(root / "excluded-client-mods") or not row.get("reason") or
                row["path"] not in by_path or row["sha256"] != by_path[row["path"]]["sha256"]):
            raise ValueError("Unsafe or unbound client-only exclusion")
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"] or destination.exists():
            raise ValueError("QA source changed or target already exists")
        targets.append((source, destination))
    # Keep the previous failed observation before another launch overwrites it.
    evidence = root / "qa-attempt-original93"
    evidence.mkdir(exist_ok=False)
    for filename in ("qa-console.log", "qa-result.json", "qa-stage.json"):
        source = root / filename
        if source.is_file():
            shutil.copy2(source, evidence / filename)
    for source, destination in targets:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    stage["clientOnlyExclusions"] = exclusions
    stage["modsIncluded"] -= len(exclusions)
    stage_path.write_text(json.dumps(stage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"excludedClientJars": len(exclusions), "modsIncluded": stage["modsIncluded"]}))


if __name__ == "__main__":
    main()
