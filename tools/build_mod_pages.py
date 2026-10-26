#!/usr/bin/env python3
"""Build official project links from exact upstream and reviewed local JARs.

Upstream pages come from the original export's aligned manifest/modlist, bound
to the installed file's SHA-256. A locally authored helper may additionally be
listed in tools/local-mods.json; its hash, size and actual mod IDs must match.
The historical upstream lock is never rewritten by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from pack_library import read_mods


LOCAL_PROJECT_URL = "https://github.com/MarkZamore/Caves-and-Dungeons"
LOCAL_MOD_ID = "cad_world_type_lock"
UPSTREAM_SHA256 = "b7d41eea56ebf42c7eb115b00cfc2840cda28f1d222ca9edc853b3aeec09df5e"
# The original export confirms this origin. Current project/file metadata is
# unavailable and the page could not be verified. This does not prove deletion.
UNAVAILABLE_PROJECTS = {(818324, 4721801)}


def project_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A locked jar has no verified project page")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or len(value) > 2048):
        raise ValueError("Invalid locked project page: " + value)
    return value


def local_files(pack: Path) -> dict[str, dict]:
    path = pack / "tools/local-mods.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("schemaVersion") != 1:
        raise ValueError("Unsupported local mod lock")
    files = {}
    for entry in doc["files"]:
        relative = entry["path"]
        parts = PurePosixPath(relative).parts
        if (len(parts) != 2 or parts[0] != "mods" or "\\" in relative or
                not parts[1].startswith("cad-world-type-lock-") or
                not parts[1].endswith(".jar") or relative in files):
            raise ValueError("Unexpected local helper path: " + relative)
        if (entry.get("websiteUrl") != LOCAL_PROJECT_URL or
                entry.get("modIds") != [LOCAL_MOD_ID]):
            raise ValueError("Unexpected local helper identity: " + relative)
        files[relative] = entry
    if len(files) > 1:
        raise ValueError("Only one active world-type helper is allowed")
    return files


def active_files(pack: Path) -> list[dict]:
    path = pack / "tools/distribution-lock.json"
    if path.exists():
        lock = json.loads(path.read_text(encoding="utf-8-sig"))
        if (lock.get("schemaVersion") != 1 or
                lock.get("packId") != "caves-and-dungeons" or
                lock.get("upstreamArchiveSha256") != UPSTREAM_SHA256):
            raise ValueError("Unexpected Caves and Dungeons distribution lock")
    else:
        lock = json.loads((pack / "tools/upstream-lock.json").read_text(encoding="utf-8-sig"))
        if (lock.get("schemaVersion") != 1 or
                lock.get("pack", {}).get("projectId") != 971867 or
                lock["pack"].get("clientFileId") != 6164816):
            raise ValueError("Unexpected Caves and Dungeons upstream lock")
    files = lock.get("files")
    if not isinstance(files, list):
        raise ValueError("Missing active jar list")
    seen = set()
    for entry in files:
        relative = entry["path"]
        parts = PurePosixPath(relative).parts
        if (len(parts) != 2 or parts[0] != "mods" or "\\" in relative or
                ":" in relative or not parts[1].lower().endswith(".jar") or
                entry.get("included") is False or relative.casefold() in seen):
            raise ValueError("Invalid or duplicate active jar path: " + relative)
        seen.add(relative.casefold())
    return files


def build_pages(pack: Path) -> dict[str, str | dict]:
    locked_files: dict[str, list[dict]] = {}
    for entry in active_files(pack):
        locked_files.setdefault(entry["path"], []).append(entry)
    unused_active = set(locked_files)
    local = local_files(pack)
    unused_local = set(local)
    pages: dict[str, str | dict] = {}
    jars = sorted((pack / "mods").glob("*.jar"))
    if not jars:
        raise ValueError("No shipped jars to audit")
    for jar in jars:
        relative = jar.relative_to(pack).as_posix()
        data = jar.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        mods = read_mods(data, jar.name)
        top_ids = {mod["id"] for mod in read_mods(data, jar.name, include_nested=False)}
        candidates = [entry for entry in locked_files.get(relative, [])
                      if entry["sha256"] == digest and entry["sizeBytes"] == len(data)]
        if len(candidates) == 1:
            entry = candidates[0]
            unused_active.remove(relative)
            page = project_url(entry["websiteUrl"])
            if (entry["projectId"], entry["fileId"]) in UNAVAILABLE_PROJECTS:
                page = {"url": page, "available": False}
        elif not candidates and relative in local:
            entry = local[relative]
            if (entry["sha256"] != digest or entry["sizeBytes"] != len(data) or
                    sorted(mod["id"] for mod in mods) != entry["modIds"]):
                raise ValueError("Local helper differs from its reviewed identity: " + relative)
            unused_local.remove(relative)
            page = project_url(entry["websiteUrl"])
        else:
            raise ValueError("Jar has no unique hash-verified project: " + relative)
        mod_pages = entry.get("modPages", {})
        if not isinstance(mod_pages, dict) or set(mod_pages) - {mod["id"] for mod in mods}:
            raise ValueError("Project-page override names an absent mod: " + relative)
        nested_ids = {mod["id"] for mod in mods} - top_ids
        if nested_ids - set(mod_pages):
            raise ValueError("Nested mod needs its own reviewed project page: " +
                             relative + ": " + ", ".join(sorted(nested_ids - set(mod_pages))))
        if set(mod_pages) & top_ids:
            raise ValueError("A project-page override cannot replace the parent project: " + relative)
        for mod in mods:
            assigned = project_url(mod_pages[mod["id"]]) if mod["id"] in mod_pages else page
            previous = pages.setdefault(mod["id"], assigned)
            if previous != assigned:
                raise ValueError("Conflicting upstream projects for mod: " + mod["id"])
    if unused_active:
        raise ValueError("Active locked jar is missing: " + ", ".join(sorted(unused_active)))
    if unused_local:
        raise ValueError("Locked local helper is missing: " + ", ".join(sorted(unused_local)))
    return dict(sorted(pages.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    pages = build_pages(args.pack)
    path = args.pack / "library/mod-pages.json"
    if args.verify_only:
        if json.loads(path.read_text(encoding="utf-8-sig")) != pages:
            raise ValueError("Project-page mapping is stale; run tools/build_mod_pages.py")
    else:
        path.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    urls = {entry["url"] if isinstance(entry, dict) else entry for entry in pages.values()}
    print(json.dumps({"modIds": len(pages), "projectPages": len(urls),
                      "verified": args.verify_only}))


if __name__ == "__main__":
    main()
