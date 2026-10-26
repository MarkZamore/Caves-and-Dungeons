"""Active restoration never falls back to superseded author files."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import restore_distribution as restore


class DistributionRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payloads = {}
        self.lock = {"schemaVersion": 1, "packId": restore.PACK_ID,
                     "upstreamArchiveSha256": restore.CLIENT_SHA256,
                     "files": [], "overrides": [], "supportFiles": [],
                     "replacements": [{"old": {"path": "mods/old-map.jar"}}]}
        mod = self.record("mods/new-map.jar", b"pinned replacement")
        mod.update(sourceUrl="https://edge.forgecdn.net/files/9067/273/new-map.jar",
                   projectId=123, fileId=9067273)
        self.lock["files"] = [mod]
        for index, path in enumerate(sorted(restore.UPSTREAM_OVERRIDES)):
            self.lock["overrides"].append(self.record(path, f"author override {index}".encode()))
        client = self.record(restore.CLIENT_NAME, b"Minecraft client")
        client.update(sourceUrl="https://piston-data.mojang.com/v1/objects/test/client.jar",
                      sha1=hashlib.sha1(self.payloads[restore.CLIENT_NAME]).hexdigest())
        self.lock["client"] = client
        self.lock["supportFiles"] = [self.record("library/content.json", b"reviewed description")]
        self.save_lock()

    def record(self, relative, data):
        self.payloads[relative] = data
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": relative, "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def save_lock(self):
        path = self.root / "tools/distribution-lock.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.lock), encoding="utf-8")

    def missing_mod(self):
        path = self.root / self.lock["files"][0]["path"]
        path.unlink()
        return path

    def supply_mod(self, url, target, size, hashes):
        record = self.lock["files"][0]
        self.assertEqual(record["sourceUrl"], url)
        self.assertEqual(record["sizeBytes"], size)
        self.assertEqual({"sha256": record["sha256"]}, hashes)
        target.write_bytes(self.payloads[record["path"]])

    def test_missing_replacement_restores_only_the_active_pinned_file(self):
        target = self.missing_mod()
        with patch.object(restore, "download", side_effect=self.supply_mod) as download:
            result = restore.restore_distribution(self.root)
        download.assert_called_once()
        self.assertEqual(1, result["restored"])
        self.assertEqual(b"pinned replacement", target.read_bytes())
        self.assertFalse((self.root / "mods/old-map.jar").exists())

    def test_verify_only_has_no_network_or_cache_writes(self):
        with patch.object(restore, "download") as download:
            result = restore.restore_distribution(self.root, verify_only=True)
        self.assertTrue(result["verified"])
        download.assert_not_called()
        self.assertFalse((self.root / "artifacts").exists())
        target = self.missing_mod()
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "Missing active"):
                restore.restore_distribution(self.root, verify_only=True)
        download.assert_not_called()
        self.assertFalse(target.exists())
        self.assertFalse((self.root / "artifacts").exists())

    def test_existing_corruption_fails_before_any_download_or_overwrite(self):
        target = self.root / self.lock["files"][0]["path"]
        target.write_bytes(b"corrupted replacement")
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                restore.restore_distribution(self.root)
        download.assert_not_called()
        self.assertEqual(b"corrupted replacement", target.read_bytes())
        self.assertFalse((self.root / "artifacts").exists())

    def test_superseded_jar_is_unknown_and_never_silently_removed(self):
        target = self.missing_mod()
        old = self.root / "mods/old-map.jar"
        old.write_bytes(b"old author version")
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "Unknown active mod"):
                restore.restore_distribution(self.root)
        download.assert_not_called()
        self.assertEqual(b"old author version", old.read_bytes())
        self.assertFalse(target.exists())

    def test_changed_or_missing_tracked_support_is_never_restored(self):
        target = self.missing_mod()
        support = self.root / self.lock["supportFiles"][0]["path"]
        support.write_bytes(b"concurrent description change")
        for present in (True, False):
            with self.subTest(present=present):
                if not present:
                    support.unlink()
                with patch.object(restore, "download") as download:
                    with self.assertRaises(ValueError):
                        restore.restore_distribution(self.root)
                download.assert_not_called()
                self.assertFalse(target.exists())
                self.assertFalse((self.root / "artifacts").exists())
        self.assertFalse(support.exists())

    def test_malformed_lock_is_rejected_before_writing(self):
        original = copy.deepcopy(self.lock)
        for kind in ("identity", "hash", "size", "duplicate", "escape", "alias", "url"):
            with self.subTest(kind=kind):
                self.lock = copy.deepcopy(original)
                record = self.lock["files"][0]
                if kind == "identity":
                    self.lock["upstreamArchiveSha256"] = "0" * 64
                elif kind == "hash":
                    record["sha256"] = "invalid"
                elif kind == "size":
                    record["sizeBytes"] = True
                elif kind == "duplicate":
                    self.lock["files"].append(dict(record))
                elif kind == "escape":
                    record["path"] = "../foreign.jar"
                elif kind == "alias":
                    record["path"] = "mods/con.jar"
                else:
                    record["sourceUrl"] = "http://edge.forgecdn.net/unsafe.jar"
                self.save_lock()
                with patch.object(restore, "download") as download:
                    with self.assertRaises(ValueError):
                        restore.restore_distribution(self.root)
                download.assert_not_called()
                self.assertFalse((self.root / "artifacts").exists())

    def test_bad_download_never_becomes_an_active_file(self):
        target = self.missing_mod()

        def bad_download(url, payload, size, hashes):
            payload.write_bytes(b"wrong bytes")

        with patch.object(restore, "download", side_effect=bad_download):
            with self.assertRaisesRegex(ValueError, "pinned hash"):
                restore.restore_distribution(self.root)
        self.assertFalse(target.exists())

    def test_missing_author_override_is_extracted_from_the_pinned_archive(self):
        record = self.lock["overrides"][0]
        target = self.root / record["path"]
        target.unlink()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("overrides/" + record["path"], self.payloads[record["path"]])
        data = buffer.getvalue()
        fixture_sha = hashlib.sha256(data).hexdigest()
        self.lock["upstreamArchiveSha256"] = fixture_sha
        self.save_lock()

        def supply_archive(url, payload, size, hashes):
            self.assertEqual(restore.file_url(restore.CLIENT_FILE_ID, restore.CLIENT_ARCHIVE), url)
            self.assertEqual({"sha256": fixture_sha}, hashes)
            self.assertEqual(len(data), size)
            payload.write_bytes(data)

        with patch.object(restore, "CLIENT_SHA256", fixture_sha), \
                patch.object(restore, "CLIENT_SIZE", len(data)), \
                patch.object(restore, "download", side_effect=supply_archive) as download:
            result = restore.restore_distribution(self.root)
        download.assert_called_once()
        self.assertEqual(1, result["restored"])
        self.assertEqual(self.payloads[record["path"]], target.read_bytes())

    def test_linked_destination_is_rejected_without_writes(self):
        target = self.root / self.lock["files"][0]["path"]
        target.unlink()
        foreign = self.root / "foreign.jar"
        foreign.write_bytes(b"foreign")
        try:
            target.symlink_to(foreign)
        except OSError:
            # Junction/reparse checks use the same explicit refusal in target_path.
            with patch.object(Path, "is_symlink", side_effect=lambda: True):
                with self.assertRaisesRegex(ValueError, "linked"):
                    restore.target_path(self.root, self.lock["files"][0]["path"])
            return
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "linked"):
                restore.restore_distribution(self.root)
        download.assert_not_called()
        self.assertEqual(b"foreign", foreign.read_bytes())

    def test_reviewed_tracked_helper_is_allowed_but_never_downloaded(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("META-INF/mods.toml",
                             '[[mods]]\nmodId="cad_world_type_lock"\nversion="1.0.0"\n')
        helper = self.record("mods/cad-world-type-lock-1.0.0.jar", buffer.getvalue())
        self.lock["supportFiles"].append(helper)
        local_entry = dict(helper, modIds=[restore.HELPER_MOD_ID], websiteUrl=restore.HELPER_PROJECT_URL)
        local = {"schemaVersion": 1, "files": [local_entry]}
        self.lock["supportFiles"].append(self.record("tools/local-mods.json", json.dumps(local).encode()))
        self.save_lock()
        with patch.object(restore, "download") as download:
            result = restore.restore_distribution(self.root, verify_only=True)
        download.assert_not_called()
        self.assertEqual(3, result["supportFiles"])
        (self.root / helper["path"]).unlink()
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "refusing to restore"):
                restore.restore_distribution(self.root)
        download.assert_not_called()

    def test_arbitrary_support_jar_cannot_bypass_the_unknown_mod_check(self):
        helper = self.record("mods/arbitrary.jar", b"unreviewed executable")
        self.lock["supportFiles"].append(helper)
        self.save_lock()
        with patch.object(restore, "download") as download:
            with self.assertRaisesRegex(ValueError, "reviewed local helper identity"):
                restore.restore_distribution(self.root)
        download.assert_not_called()
        self.assertFalse((self.root / "artifacts").exists())


if __name__ == "__main__":
    unittest.main()
