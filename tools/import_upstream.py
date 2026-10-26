#!/usr/bin/env python3
"""Reproduce the unmodified Caves and Dungeons 1.4 author export.

Python 3.12 standard library only. No upstream mod is excluded or updated.
The exact export is pinned by SHA-256; its aligned manifest/modlist identifies
all 93 files and official project pages. The first import records every byte's
SHA-256. Later imports and --restore-locked-files require the recorded hashes.

Illuminative's file metadata has been withdrawn, but its exact original file
remains on CurseForge's official CDN. Only that exact project/file pair uses
the independently verified filename, size and SHA-256 below. No mirror is used.

This historical importer deliberately refuses to overwrite a modified pack.
Launcher-specific additions belong in a separate distribution lock; do not
use this importer to reset an already customized distribution.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import zipfile

PROJECT_ID = 971867
CLIENT_FILE_ID = 6164816
CLIENT_ARCHIVE = "Caves-and-Dungeons-1.4-forge-1.20.1.zip"
CLIENT_SIZE = 6636979
CLIENT_SHA256 = "b7d41eea56ebf42c7eb115b00cfc2840cda28f1d222ca9edc853b3aeec09df5e"
PACK_VERSION = "1.4"
MINECRAFT_VERSION = "1.20.1"
FORGE_VERSION = "47.3.7"
PROJECT_URL = "https://www.curseforge.com/minecraft/modpacks/caves-and-dungeons"
CLIENT_NAME = "minecraft-1.20.1-client.jar"
FILE_COUNT = 93
OVERRIDE_COUNT = 3
USER_AGENT = "LANMinecraft-CavesAndDungeons-UpstreamImporter/1"
CHUNK = 1024 * 1024
OFFICIAL_HOSTS = {"edge.forgecdn.net", "piston-data.mojang.com", "launcher.mojang.com"}
WITHDRAWN_FILES = {
    (818324, 4721801): {
        "id": 4721801, "projectId": 818324,
        "fileName": "Illuminative-mc1.20.1-1.2.0.jar", "fileLength": 262664,
        "sha256": "6c2ebc5b55d1f1b3320855ad05475d3f5e227858d740768cbe613e6696f19223",
        "gameVersions": ["Forge", "1.20.1"],
    }
}


def digest(path: Path, algorithm="sha256") -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def fetch_json(url: str):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)


def safe_relative(value: str) -> str:
    if not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("Unsafe upstream path: " + repr(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise ValueError("Unsafe upstream path: " + repr(value))
    return path.as_posix()


def target_path(root: Path, relative: str) -> Path:
    target = root / safe_relative(relative)
    for part in [target, *target.parents]:
        if part == root.parent:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing linked destination: " + str(part))
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Destination escapes pack: " + relative)
    return target


def expected_ok(path: Path, size: int, hashes: dict[str, str]) -> bool:
    return path.is_file() and path.stat().st_size == size and all(
        digest(path, algorithm).lower() == value.lower() for algorithm, value in hashes.items())


def official_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS or
            parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Nonofficial locked download URL: " + url)
    return url


def download(url: str, target: Path, size: int, hashes: dict[str, str]):
    official_url(url)
    if expected_ok(target, size, hashes):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        temporary = target.with_name(target.name + ".part")
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output, CHUNK)
            if not expected_ok(temporary, size, hashes):
                raise ValueError("Size/hash mismatch: " + target.name)
            os.replace(temporary, target)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def install(source: Path, target: Path):
    if target.exists():
        if expected_ok(target, source.stat().st_size, {"sha256": digest(source)}):
            return
        raise ValueError("Existing file differs; refusing to overwrite: " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


class ProjectLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = dict(attrs).get("href", "")
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.netloc != "www.curseforge.com" or
                    not parsed.path.startswith("/minecraft/mc-mods/")):
                raise ValueError("Nonofficial project link in upstream modlist")
            self.current = {"websiteUrl": url, "title": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.rows.append(self.current)
            self.current = None


def file_url(file_id: int, filename: str) -> str:
    safe_relative(filename)
    if "/" in filename:
        raise ValueError("Upstream filename contains a directory")
    return f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000:03d}/{quote(filename)}"


def validate_manifest(manifest: dict, pages: list[dict]):
    if (manifest.get("name") != "Cave and Dungeons" or manifest.get("version") != PACK_VERSION or
            manifest.get("manifestType") != "minecraftModpack" or manifest.get("manifestVersion") != 1 or
            manifest.get("minecraft") != {"version": MINECRAFT_VERSION, "modLoaders": [{"id": "forge-" + FORGE_VERSION, "primary": True}]} or
            manifest.get("overrides") != "overrides" or len(manifest.get("files", [])) != FILE_COUNT or len(pages) != FILE_COUNT):
        raise ValueError("Unexpected pinned client manifest or modlist")
    pairs = [(row["projectID"], row["fileID"]) for row in manifest["files"]]
    if len(set(pairs)) != FILE_COUNT or any(row.get("required") is not True for row in manifest["files"]):
        raise ValueError("Unexpected duplicate or optional upstream file")


def resolve_metadata(project_id: int, file_id: int, metadata: dict | None) -> tuple[dict, dict[str, str]]:
    key = project_id, file_id
    exception = WITHDRAWN_FILES.get(key)
    if metadata is None:
        if exception is None:
            raise ValueError(f"Upstream metadata unavailable: project {project_id}, file {file_id}")
        metadata = dict(exception)
    if metadata.get("id") != file_id or metadata.get("projectId") != project_id:
        raise ValueError("CurseForge returned metadata for another project/file")
    if not {"Forge", MINECRAFT_VERSION}.issubset(metadata.get("gameVersions", [])):
        raise ValueError("Upstream metadata has another Minecraft version or loader")
    hashes = { {1: "sha1", 2: "md5"}[h["algo"]]: h["value"] for h in metadata.get("hashes", []) if h.get("algo") in (1, 2) }
    if exception:
        if any(metadata[field] != exception[field] for field in ("fileName", "fileLength")):
            raise ValueError("Withdrawn file differs from pinned identity")
        hashes["sha256"] = exception["sha256"]
    return metadata, hashes


def extract_overrides(archive: zipfile.ZipFile, pack: Path, cache: Path):
    records, seen = [], set()
    for item in archive.infolist():
        if not item.filename.startswith("overrides/") or item.is_dir():
            continue
        relative = safe_relative(item.filename[len("overrides/"):])
        if stat.S_ISLNK(item.external_attr >> 16) or relative.casefold() in seen:
            raise ValueError("Linked or duplicate upstream entry: " + relative)
        seen.add(relative.casefold())
        target = target_path(pack, relative)
        with tempfile.TemporaryDirectory(prefix="override-", dir=cache) as folder:
            temporary = Path(folder) / "payload"
            with archive.open(item) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output, CHUNK)
            install(temporary, target)
        records.append({"path": relative, "sizeBytes": target.stat().st_size, "sha256": digest(target)})
    if len(records) != OVERRIDE_COUNT:
        raise ValueError("Unexpected number of pinned upstream overrides")
    return records


def validate_lock(lock: dict):
    pack = lock.get("pack", {})
    if (lock.get("schemaVersion") != 1 or pack.get("projectId") != PROJECT_ID or
            pack.get("clientFileId") != CLIENT_FILE_ID or pack.get("clientArchiveSha256") != CLIENT_SHA256 or
            pack.get("version") != PACK_VERSION or pack.get("minecraftVersion") != MINECRAFT_VERSION or
            pack.get("loader") != {"type": "forge", "version": FORGE_VERSION} or
            len(lock.get("files", [])) != FILE_COUNT or len(lock.get("overrides", [])) != OVERRIDE_COUNT):
        raise ValueError("Unexpected Caves and Dungeons upstream lock identity")
    if any(row.get("included") is not True for row in lock["files"]):
        raise ValueError("The author snapshot may not omit upstream files")
    if len({(r["projectId"], r["fileId"]) for r in lock["files"]}) != FILE_COUNT:
        raise ValueError("Duplicate file identity in upstream lock")
    seen = set()
    for record in [*lock["files"], *lock["overrides"], lock["client"]]:
        relative = safe_relative(record["path"])
        if relative.casefold() in seen:
            raise ValueError("Duplicate path in upstream lock: " + relative)
        seen.add(relative.casefold())
        size, sha256 = record.get("sizeBytes"), record.get("sha256")
        if (not isinstance(size, int) or isinstance(size, bool) or size < 0 or
                not isinstance(sha256, str) or not re.fullmatch("[0-9a-f]{64}", sha256)):
            raise ValueError("Invalid size/hash in upstream lock: " + relative)
    for record in [*lock["files"], lock["client"]]:
        official_url(record["sourceUrl"])
    for record in lock["files"]:
        if record["path"] != "mods/" + record["fileName"] or record["sourceUrl"] != file_url(record["fileId"], record["fileName"]):
            raise ValueError("Locked file URL/path differs from project/file identity")
        exception = WITHDRAWN_FILES.get((record["projectId"], record["fileId"]))
        if exception and (record["fileName"] != exception["fileName"] or record["sizeBytes"] != exception["fileLength"] or record["sha256"] != exception["sha256"]):
            raise ValueError("Locked withdrawn file differs from pinned identity")
    if lock["client"]["path"] != CLIENT_NAME:
        raise ValueError("Unexpected locked Minecraft client path")


def restore_locked_files(pack: Path, cache: Path):
    """Restore only exact historical binaries, without mutable metadata APIs."""
    lock = json.loads((pack / "tools/upstream-lock.json").read_text(encoding="utf-8-sig"))
    validate_lock(lock)
    downloads = [*lock["files"], lock["client"]]
    # Validate the complete existing tree before downloading or writing anything.
    for record in [*downloads, *lock["overrides"]]:
        target = target_path(pack, record["path"])
        if target.exists() and not expected_ok(target, record["sizeBytes"], {"sha256": record["sha256"]}):
            raise ValueError("Existing file differs from committed lock; refusing to overwrite: " + record["path"])
    for record in lock["overrides"]:
        if not target_path(pack, record["path"]).is_file():
            raise ValueError("Missing upstream override: " + record["path"] + "; restore checkout or run a full import")
    restored = 0
    for record in downloads:
        target = target_path(pack, record["path"])
        if target.is_file():
            continue
        payload = cache / "locked" / record["sha256"]
        download(record["sourceUrl"], payload, record["sizeBytes"], {"sha256": record["sha256"]})
        install(payload, target)
        restored += 1
    print(f"Verified locked author pack: {len(downloads)} downloads, {OVERRIDE_COUNT} overrides; restored {restored}", flush=True)


def import_pack(pack: Path, cache: Path, workers: int):
    lock_path = pack / "tools/upstream-lock.json"
    old_lock = json.loads(lock_path.read_text(encoding="utf-8-sig")) if lock_path.exists() else None
    if old_lock:
        validate_lock(old_lock)
    old_files = {(r["projectId"], r["fileId"]): r for r in old_lock["files"]} if old_lock else {}
    client = cache / CLIENT_ARCHIVE
    download(file_url(CLIENT_FILE_ID, CLIENT_ARCHIVE), client, CLIENT_SIZE, {"sha256": CLIENT_SHA256})
    with zipfile.ZipFile(client) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        links = ProjectLinks()
        links.feed(archive.read("modlist.html").decode("utf-8-sig"))
        validate_manifest(manifest, links.rows)
        overrides = extract_overrides(archive, pack, cache)
    write_json(cache / "client-manifest.json", manifest)
    metadata_path = cache / "client-file-metadata.json"
    cached = json.loads(metadata_path.read_text(encoding="utf-8-sig")) if metadata_path.exists() else []
    metadata_by_id = {(r["projectID"], r["fileID"]): r["metadata"] for r in cached}

    def import_file(pair):
        row, project = pair
        project_id, file_id = row["projectID"], row["fileID"]
        key = project_id, file_id
        metadata_url = f"https://www.curseforge.com/api/v1/mods/{project_id}/files/{file_id}"
        raw = metadata_by_id.get(key)
        if raw is None:
            raw = fetch_json(metadata_url)["data"]
        metadata, hashes = resolve_metadata(project_id, file_id, raw)
        filename, size = metadata["fileName"], metadata["fileLength"]
        if not filename.lower().endswith(".jar"):
            raise ValueError("Pinned author pack contains an unexpected non-JAR manifest file")
        relative, url = "mods/" + filename, file_url(file_id, filename)
        locked = old_files.get(key)
        if locked:
            if any(locked[k] != v for k, v in {"path": relative, "sizeBytes": size, "websiteUrl": project["websiteUrl"]}.items()):
                raise ValueError("Upstream metadata differs from committed lock: " + filename)
            hashes["sha256"] = locked["sha256"]
        payload = cache / "files" / str(file_id) / filename
        download(url, payload, size, hashes)
        install(payload, target_path(pack, relative))
        record = {"projectId": project_id, "fileId": file_id, "fileName": filename, "path": relative,
                  "sizeBytes": size, "sourceUrl": url, "websiteUrl": project["websiteUrl"], "title": project["title"],
                  "metadataUrl": metadata_url, "included": True, "sha256": digest(payload)}
        if key in WITHDRAWN_FILES:
            record["metadataException"] = "Withdrawn API metadata; exact original file retained on official CurseForge CDN and pinned by SHA-256"
        return record, {"projectID": project_id, "fileID": file_id, "metadata": metadata}

    records, metadata_rows, errors = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(import_file, pair) for pair in zip(manifest["files"], links.rows, strict=True)]
        for completed, future in enumerate(concurrent.futures.as_completed(pending), 1):
            try:
                record, metadata = future.result()
                records.append(record)
                metadata_rows.append(metadata)
            except Exception as error:
                errors.append(str(error))
                print("ERROR: " + str(error), flush=True)
            if completed % 20 == 0 or completed == FILE_COUNT:
                print(f"Imported {completed}/{FILE_COUNT} upstream files ({len(errors)} errors)", flush=True)
    write_json(metadata_path, sorted(metadata_rows, key=lambda r: (r["projectID"], r["fileID"])))
    if errors:
        write_json(cache / "import-errors.json", errors)
        raise ValueError("Import incomplete: " + "; ".join(errors))
    versions = fetch_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
    version_ref = next(item for item in versions["versions"] if item["id"] == MINECRAFT_VERSION)
    version = fetch_json(version_ref["url"])
    client_download = version["downloads"]["client"]
    client_payload = cache / CLIENT_NAME
    download(client_download["url"], client_payload, client_download["size"], {"sha1": client_download["sha1"]})
    install(client_payload, target_path(pack, CLIENT_NAME))
    lock = {"schemaVersion": 1,
            "pack": {"projectId": PROJECT_ID, "clientFileId": CLIENT_FILE_ID, "version": PACK_VERSION,
                     "minecraftVersion": MINECRAFT_VERSION, "loader": {"type": "forge", "version": FORGE_VERSION},
                     "url": PROJECT_URL, "clientArchiveSha256": CLIENT_SHA256},
            "files": sorted(records, key=lambda r: (r["projectId"], r["fileId"])),
            "overrides": sorted(overrides, key=lambda r: r["path"]),
            "client": {"path": CLIENT_NAME, "sizeBytes": client_download["size"], "sha1": client_download["sha1"],
                       "sha256": digest(client_payload), "sourceUrl": client_download["url"]}}
    validate_lock(lock)
    write_json(lock_path, lock)
    print(f"Verified author snapshot: {len(records)} files, {len(overrides)} overrides; no exclusions or replacements", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--restore-locked-files", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    pack = args.pack.resolve()
    cache = (args.cache or pack / "artifacts/upstream").resolve()
    pack.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    if args.restore_locked_files:
        restore_locked_files(pack, cache)
    else:
        import_pack(pack, cache, args.workers)


if __name__ == "__main__":
    main()
