"""Regression cases for source identity and non-destructive historical restore."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import import_upstream as importer


class AuthorManifestTests(unittest.TestCase):
    def manifest(self):
        return {"name": "Cave and Dungeons", "version": "1.4", "manifestType": "minecraftModpack", "manifestVersion": 1,
                "minecraft": {"version": "1.20.1", "modLoaders": [{"id": "forge-47.3.7", "primary": True}]},
                "overrides": "overrides", "files": [{"projectID": i + 1, "fileID": i + 1000, "required": True} for i in range(93)]}

    def test_manifest_keeps_all_required_files_and_aligned_project_pages(self):
        manifest = self.manifest()
        importer.validate_manifest(manifest, [{}] * 93)
        for mutation in ("loader", "version", "count", "optional", "duplicate"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(manifest)
                if mutation == "loader":
                    changed["minecraft"]["modLoaders"][0]["id"] = "forge-47.4.0"
                elif mutation == "version":
                    changed["version"] = "1.5"
                elif mutation == "count":
                    changed["files"].pop()
                elif mutation == "optional":
                    changed["files"][0]["required"] = False
                else:
                    changed["files"][0] = changed["files"][1]
                with self.assertRaises(ValueError):
                    importer.validate_manifest(changed, [{}] * 93)
        with self.assertRaises(ValueError):
            importer.validate_manifest(manifest, [{}] * 92)

    def test_withdrawn_metadata_exception_is_exact_file_and_hash(self):
        metadata, hashes = importer.resolve_metadata(818324, 4721801, None)
        self.assertEqual("Illuminative-mc1.20.1-1.2.0.jar", metadata["fileName"])
        self.assertEqual(262664, metadata["fileLength"])
        self.assertEqual("6c2ebc5b55d1f1b3320855ad05475d3f5e227858d740768cbe613e6696f19223", hashes["sha256"])
        with self.assertRaisesRegex(ValueError, "unavailable"):
            importer.resolve_metadata(818324, 4721802, None)
        changed = dict(metadata, fileLength=262665)
        with self.assertRaisesRegex(ValueError, "pinned identity"):
            importer.resolve_metadata(818324, 4721801, changed)

    def test_another_project_or_loader_cannot_supply_a_pinned_file(self):
        metadata = {"id": 123, "projectId": 456, "fileName": "mod.jar", "fileLength": 1,
                    "gameVersions": ["Forge", "1.20.1"]}
        with self.assertRaisesRegex(ValueError, "another project/file"):
            importer.resolve_metadata(457, 123, metadata)
        metadata["gameVersions"] = ["Fabric", "1.20.1"]
        with self.assertRaisesRegex(ValueError, "another Minecraft version or loader"):
            importer.resolve_metadata(456, 123, metadata)


class HistoricalRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payloads = {}
        self.lock = {
            "schemaVersion": 1,
            "pack": {"projectId": 971867, "clientFileId": 6164816, "clientArchiveSha256": importer.CLIENT_SHA256,
                     "version": "1.4", "minecraftVersion": "1.20.1", "loader": {"type": "forge", "version": "47.3.7"}},
            "files": [], "overrides": [],
        }
        for i in range(93):
            name = f"source-{i}.jar"
            record = self.record("mods/" + name, f"source payload {i}".encode())
            record.update(projectId=i + 1000, fileId=i + 2000, fileName=name, included=True,
                          sourceUrl=importer.file_url(i + 2000, name))
            self.lock["files"].append(record)
        for i in range(3):
            self.lock["overrides"].append(self.record(f"config/original-{i}.json", f"config{i}".encode()))
        self.lock["client"] = self.record(importer.CLIENT_NAME, b"Mojang fixture")
        self.lock["client"]["sourceUrl"] = "https://piston-data.mojang.com/v1/objects/test/client.jar"
        self.save_lock()

    def record(self, relative, data):
        self.payloads[relative] = data
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": relative, "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def save_lock(self):
        importer.write_json(self.root / "tools/upstream-lock.json", self.lock)

    def test_restore_uses_committed_bytes_without_mutable_metadata(self):
        missing = self.lock["files"][0]
        target = self.root / missing["path"]
        target.unlink()

        def supply(url, payload, size, hashes):
            self.assertEqual(missing["sourceUrl"], url)
            self.assertEqual({"sha256": missing["sha256"]}, hashes)
            self.assertEqual(missing["sizeBytes"], size)
            payload.parent.mkdir(parents=True, exist_ok=True)
            payload.write_bytes(self.payloads[missing["path"]])

        with patch.object(importer, "fetch_json", side_effect=AssertionError("Mutable metadata must not be queried")), \
                patch.object(importer, "download", side_effect=supply) as download:
            importer.restore_locked_files(self.root, self.root / "artifacts/cache")
        download.assert_called_once()
        self.assertEqual(self.payloads[missing["path"]], target.read_bytes())

    def test_a_modified_override_stops_restore_before_any_download(self):
        missing = self.root / self.lock["files"][0]["path"]
        missing.unlink()
        changed = self.root / self.lock["overrides"][-1]["path"]
        changed.write_bytes(b"distribution customization")
        with patch.object(importer, "download") as download:
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                importer.restore_locked_files(self.root, self.root / "artifacts/cache")
        download.assert_not_called()
        self.assertFalse(missing.exists())
        self.assertEqual(b"distribution customization", changed.read_bytes())

    def test_restore_rejects_an_exclusion_or_foreign_source_before_writing(self):
        for mutation in ("exclude", "url", "duplicate"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.lock)
                if mutation == "exclude":
                    changed["files"][0]["included"] = False
                elif mutation == "url":
                    changed["files"][0]["sourceUrl"] = "https://unrelated.example/mod.jar"
                else:
                    changed["overrides"][-1]["path"] = changed["overrides"][0]["path"]
                importer.write_json(self.root / "tools/upstream-lock.json", changed)
                with patch.object(importer, "download") as download:
                    with self.assertRaises(ValueError):
                        importer.restore_locked_files(self.root, self.root / "artifacts/cache")
                download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
