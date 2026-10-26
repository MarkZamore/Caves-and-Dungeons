#!/usr/bin/env python3
"""Verify or restore the active Caves and Dungeons distribution, never its history.

Only missing active binaries and the exact author-export overrides are restored.
Changed existing files and unknown mods stop the operation before any download.
Tracked support files must already match the checkout and are never overwritten.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

from import_upstream import (CLIENT_ARCHIVE, CLIENT_FILE_ID, CLIENT_NAME,
                             CLIENT_SHA256, CLIENT_SIZE, download, expected_ok,
                             file_url, official_url)
from pack_library import read_mods


PACK_ID = "caves-and-dungeons"
HELPER_MOD_ID = "cad_world_type_lock"
HELPER_PREFIX = "cad-world-type-lock-"
HELPER_PROJECT_URL = "https://github.com/MarkZamore/Caves-and-Dungeons"
UPSTREAM_OVERRIDES = {
    "resourcepacks/Quark Programmer Art.zip",
    "resourcepacks/VanillaTweaks(For-CaD).zip",
    "scripts/recipes_for_CaD.zs",
}
RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                  *(f"lpt{i}" for i in range(1, 10))}


def safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or any(c in value for c in "\\:\x00"):
        raise ValueError("Unsafe distribution path: " + repr(value))
    parts = value.split("/")
    if (PurePosixPath(value).is_absolute() or
            any(p in ("", ".", "..") or p.endswith((" ", ".")) or
                p.split(".", 1)[0].casefold() in RESERVED_NAMES or
                any(ord(c) < 32 or c in '<>\"|?*' for c in p) for p in parts)):
        raise ValueError("Unsafe distribution path: " + repr(value))
    return "/".join(parts)


def target_path(root: Path, relative: str) -> Path:
    target = root / safe_relative(relative)
    for part in [target, *target.parents]:
        if part == root.parent:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing linked distribution path: " + relative)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Distribution path escapes pack: " + relative)
    return target


def validate_lock(lock: object) -> tuple[list[dict], list[dict], list[dict]]:
    if (not isinstance(lock, dict) or type(lock.get("schemaVersion")) is not int or
            lock["schemaVersion"] != 1 or lock.get("packId") != PACK_ID or
            lock.get("upstreamArchiveSha256") != CLIENT_SHA256):
        raise ValueError("Unexpected active distribution lock identity")
    active, overrides, support = (lock.get(key) for key in ("files", "overrides", "supportFiles"))
    if (not isinstance(active, list) or not active or not isinstance(overrides, list) or
            not isinstance(support, list) or not isinstance(lock.get("client"), dict)):
        raise ValueError("Invalid active distribution sections")
    seen = set()
    for record in [*active, *overrides, lock["client"], *support]:
        if not isinstance(record, dict):
            raise ValueError("Invalid distribution file record")
        relative = safe_relative(record.get("path"))
        if relative.casefold() in seen:
            raise ValueError("Duplicate distribution path: " + relative)
        seen.add(relative.casefold())
        if (type(record.get("sizeBytes")) is not int or record["sizeBytes"] < 0 or
                not isinstance(record.get("sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])):
            raise ValueError("Invalid distribution size/hash: " + relative)
        if "sha1" in record and (not isinstance(record["sha1"], str) or
                                  not re.fullmatch(r"[0-9a-f]{40}", record["sha1"])):
            raise ValueError("Invalid distribution SHA-1: " + relative)
    if {record["path"] for record in overrides} != UPSTREAM_OVERRIDES:
        raise ValueError("Unexpected author override paths")
    for record in active:
        parts = PurePosixPath(record["path"]).parts
        if (len(parts) != 2 or parts[0] != "mods" or
                not parts[1].lower().endswith(".jar") or record.get("included") is False):
            raise ValueError("Invalid active mod path: " + record["path"])
    if lock["client"]["path"] != CLIENT_NAME:
        raise ValueError("Unexpected Minecraft client path")
    for record in [*active, lock["client"]]:
        if not isinstance(record.get("sourceUrl"), str):
            raise ValueError("Missing active download URL: " + record["path"])
        official_url(record["sourceUrl"])
    return active, overrides, support


def hashes(record: dict) -> dict[str, str]:
    return {name: record[name] for name in ("sha256", "sha1") if name in record}


def reviewed_support_mods(root: Path, support: list[dict]) -> set[str]:
    """A tracked helper is allowed only with its separate exact local identity."""
    support_jars = {record["path"]: record for record in support
                    if record["path"].startswith("mods/") and record["path"].lower().endswith(".jar")}
    local_path = target_path(root, "tools/local-mods.json")
    if not local_path.exists():
        if support_jars:
            raise ValueError("Tracked support JAR lacks reviewed local helper identity")
        return set()
    doc = json.loads(local_path.read_text(encoding="utf-8-sig"))
    if (not isinstance(doc, dict) or type(doc.get("schemaVersion")) is not int or
            doc["schemaVersion"] != 1 or not isinstance(doc.get("files"), list) or
            len(doc["files"]) > 1):
        raise ValueError("Unexpected local helper lock")
    reviewed = set()
    for entry in doc["files"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid local helper record")
        relative = safe_relative(entry.get("path"))
        if (not re.fullmatch(r"mods/" + re.escape(HELPER_PREFIX) +
                             r"[A-Za-z0-9._+-]+\.jar", relative) or
                entry.get("modIds") != [HELPER_MOD_ID] or
                entry.get("websiteUrl") != HELPER_PROJECT_URL):
            raise ValueError("Unexpected local helper identity: " + relative)
        support_entry = support_jars.get(relative)
        if (support_entry is None or type(entry.get("sizeBytes")) is not int or
                entry["sizeBytes"] != support_entry["sizeBytes"] or
                entry.get("sha256") != support_entry["sha256"]):
            raise ValueError("Local helper differs from tracked support identity: " + relative)
        target = target_path(root, relative)
        if not expected_ok(target, support_entry["sizeBytes"], hashes(support_entry)):
            raise ValueError("Tracked helper is missing or differs; refusing to restore: " + relative)
        if sorted(mod["id"] for mod in read_mods(target.read_bytes(), target.name)) != [HELPER_MOD_ID]:
            raise ValueError("Tracked helper has unexpected actual mod IDs: " + relative)
        reviewed.add(relative.casefold())
    if reviewed != {relative.casefold() for relative in support_jars}:
        raise ValueError("Unreviewed tracked support JAR")
    return reviewed


def preflight(root: Path, lock: dict, verify_only: bool):
    active, overrides, support = validate_lock(lock)
    known_mods = {r["path"].casefold() for r in active} | reviewed_support_mods(root, support)
    mods = target_path(root, "mods")
    if mods.exists() and not mods.is_dir():
        raise ValueError("The mods path is not a directory")
    if mods.is_dir():
        for directory, names, files in os.walk(mods, followlinks=False):
            for name in [*names, *files]:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                target_path(root, relative)
                if path.is_file() and path.suffix.lower() == ".jar" and relative.casefold() not in known_mods:
                    raise ValueError("Unknown active mod: " + relative)
    missing_downloads, missing_overrides = [], []
    for record in [*active, lock["client"], *overrides, *support]:
        path = target_path(root, record["path"])
        if path.exists():
            if not expected_ok(path, record["sizeBytes"], hashes(record)):
                raise ValueError("Existing file differs from active lock; refusing to overwrite: " + record["path"])
        elif record in support:
            raise ValueError("Missing tracked support file: " + record["path"])
        elif verify_only:
            raise ValueError("Missing active distribution file: " + record["path"])
        elif record in overrides:
            missing_overrides.append(record)
        else:
            missing_downloads.append(record)
    return active, overrides, support, missing_downloads, missing_overrides


def install_missing(root: Path, record: dict, payload: Path):
    if not expected_ok(payload, record["sizeBytes"], hashes(record)):
        raise ValueError("Restored payload differs from active lock: " + record["path"])
    target = target_path(root, record["path"])
    if target.exists():
        if expected_ok(target, record["sizeBytes"], hashes(record)):
            return
        raise ValueError("File changed during restore; refusing to overwrite: " + record["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target_path(root, record["path"])
    # Exclusive creation also refuses a file appearing after the last check.
    with target.open("xb") as destination, payload.open("rb") as source:
        shutil.copyfileobj(source, destination)


def restore_distribution(pack: Path, cache: Path | None = None, *, verify_only=False) -> dict:
    root = pack.absolute()
    if not root.is_dir():
        raise ValueError("Pack root is not a directory")
    target_path(root, "tools/distribution-lock.json")
    lock = json.loads((root / "tools/distribution-lock.json").read_text(encoding="utf-8-sig"))
    active, overrides, support, missing_downloads, missing_overrides = preflight(root, lock, verify_only)
    result = {"activeMods": len(active), "overrides": len(overrides),
              "supportFiles": len(support), "restored": 0, "verified": bool(verify_only)}
    if not missing_downloads and not missing_overrides:
        return result
    cache = cache.absolute() if cache is not None else root / "artifacts/distribution-cache"
    try:
        cache_relative = cache.relative_to(root).as_posix()
    except ValueError:
        raise ValueError("Distribution cache must stay within the pack") from None
    target_path(root, cache_relative)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restore-", dir=cache) as temporary:
        folder = Path(temporary)
        payloads = []
        if missing_overrides:
            archive_path = folder / CLIENT_ARCHIVE
            download(file_url(CLIENT_FILE_ID, CLIENT_ARCHIVE), archive_path,
                     CLIENT_SIZE, {"sha256": CLIENT_SHA256})
            if not expected_ok(archive_path, CLIENT_SIZE, {"sha256": CLIENT_SHA256}):
                raise ValueError("Author override archive differs from the pinned SHA-256")
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                for index, record in enumerate(missing_overrides):
                    name = "overrides/" + record["path"]
                    if names.count(name) != 1:
                        raise ValueError("Missing or duplicate author override entry: " + name)
                    info = archive.getinfo(name)
                    if stat.S_ISLNK(info.external_attr >> 16) or info.file_size != record["sizeBytes"]:
                        raise ValueError("Unexpected author override entry: " + name)
                    payload = folder / f"override-{index}"
                    with archive.open(info) as source, payload.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                    if not expected_ok(payload, record["sizeBytes"], hashes(record)):
                        raise ValueError("Author override differs from active lock: " + record["path"])
                    payloads.append((record, payload))
        for index, record in enumerate(missing_downloads):
            payload = folder / f"active-{index}"
            download(record["sourceUrl"], payload, record["sizeBytes"], hashes(record))
            if not expected_ok(payload, record["sizeBytes"], hashes(record)):
                raise ValueError("Active download differs from pinned hash: " + record["path"])
            payloads.append((record, payload))
        # Validate the live tree again after downloading, before installing.
        preflight(root, lock, False)
        for record, payload in payloads:
            install_missing(root, record, payload)
            result["restored"] += 1
    preflight(root, lock, True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(restore_distribution(args.pack, args.cache, verify_only=args.verify_only)))


if __name__ == "__main__":
    main()
