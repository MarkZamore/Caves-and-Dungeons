#!/usr/bin/env python3
"""Stage a separate private Forge server from the exact author snapshot.

The server is a disposable QA fixture, never a production role. This script
does not touch the source pack or copy personal worlds. All 93 author JARs
are included initially; optional --exclusions records must bind exact SHA256
and explain proven client-only code. This does not change the shipped pack.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import import_upstream as upstream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--library-cache", action="append", default=[], type=Path)
    parser.add_argument("--exclusions", type=Path)
    args = parser.parse_args()
    pack, output = args.pack.resolve(), args.out.resolve()
    if output == pack or (output.is_relative_to(pack) and not output.is_relative_to(pack / "artifacts")):
        raise ValueError("QA target must be independent from shipped pack files")
    if output.exists() and any(output.iterdir()):
        raise ValueError("QA target must be empty; choose a new independent fixture")
    lock = json.loads((pack / "tools/upstream-lock.json").read_text(encoding="utf-8"))
    upstream.validate_lock(lock)
    exclusions = json.loads(args.exclusions.read_text(encoding="utf-8")) if args.exclusions else []
    by_path = {record["path"]: record for record in lock["files"]}
    for row in exclusions:
        original = by_path.get(row["path"])
        if not original or row["sha256"] != original["sha256"] or not row.get("reason"):
            raise ValueError("Exclusion does not bind an exact author JAR and reason")
    # Verify all source bytes, even client-only files omitted from this fixture.
    for row in [*lock["files"], *lock["overrides"]]:
        if not upstream.expected_ok(pack / row["path"], row["sizeBytes"], {"sha256": row["sha256"]}):
            raise ValueError("Source no longer matches untouched author snapshot: " + row["path"])
    installer_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.1-47.3.7/forge-1.20.1-47.3.7-installer.jar.sha1"
    request = urllib.request.Request(installer_url, headers={"User-Agent": "LANMinecraft-CavesAndDungeons-QA/1"})
    with urllib.request.urlopen(request, timeout=40) as response:
        installer_sha1 = response.read().decode("ascii").strip().split()[0]
    if upstream.digest(args.installer, "sha1") != installer_sha1:
        raise ValueError("Installer differs from Forge's official published SHA1")
    output.mkdir(parents=True, exist_ok=True)
    # Seed only named installer libraries from independent read-only caches.
    with zipfile.ZipFile(args.installer) as installer:
        profile = json.loads(installer.read("install_profile.json"))
        version = json.loads(installer.read("version.json"))
    seeded = 0
    for row in [*profile.get("libraries", []), *version.get("libraries", [])]:
        artifact = row.get("downloads", {}).get("artifact", {})
        relative = artifact.get("path")
        if not relative:
            continue
        target = output / "libraries" / relative
        if target.exists():
            continue
        for cache in args.library_cache:
            source = cache / relative
            if source.is_file() and (not artifact.get("sha1") or upstream.digest(source, "sha1") == artifact["sha1"]):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                seeded += 1
                break
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with (output / "installer-console.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([str(args.java), "-Djava.awt.headless=true", "-jar", str(args.installer.resolve()),
                                 "--installServer", str(output)], cwd=output, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=flags, timeout=300)
    if result.returncode:
        raise ValueError("Forge server installation failed; inspect installer-console.log")
    excluded = {row["path"] for row in exclusions}
    for row in [*lock["files"], *lock["overrides"]]:
        if row["path"] in excluded:
            continue
        target = output / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pack / row["path"], target)
    (output / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (output / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=25586\nonline-mode=false\nlevel-name=qa-baseline-world\n"
        "view-distance=4\nsimulation-distance=4\nmax-players=2\nenable-rcon=false\nenable-query=false\n"
        "motd=Private Caves and Dungeons QA\n", encoding="utf-8")
    report = {"schemaVersion": 1, "purpose": "independent private dedicated QA; no personal world",
              "upstreamArchiveSha256": upstream.CLIENT_SHA256, "upstreamLockSha256": upstream.digest(pack / "tools/upstream-lock.json"),
              "minecraftVersion": "1.20.1", "forgeVersion": "47.3.7", "installerSha1": installer_sha1,
              "modsIncluded": len(lock["files"]) - len(excluded), "clientOnlyExclusions": exclusions,
              "seededLibraries": seeded, "sourceFiles": [*lock["files"], *lock["overrides"]],
              "worldPreset": "server default; not evidence for Ultra Caves"}
    upstream.write_json(output / "qa-stage.json", report)
    print(json.dumps({"output": str(output), "modsIncluded": report["modsIncluded"], "seededLibraries": seeded}))


if __name__ == "__main__":
    main()
