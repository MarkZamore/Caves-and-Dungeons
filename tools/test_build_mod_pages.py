import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from build_mod_pages import build_pages, LOCAL_PROJECT_URL, UPSTREAM_SHA256


class ProjectPagesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.pack = Path(self.temporary.name)
        (self.pack / "mods").mkdir()
        (self.pack / "tools").mkdir()
        self.lock = {"schemaVersion": 1,
                     "pack": {"projectId": 971867, "clientFileId": 6164816},
                     "files": []}

    def jar(self, filename, mod_id):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("META-INF/mods.toml",
                             f'[[mods]]\nmodId="{mod_id}"\nversion="1.0.0"\n')
        data = buffer.getvalue()
        (self.pack / "mods" / filename).write_bytes(data)
        return {"path": "mods/" + filename, "sizeBytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}

    def save_upstream(self):
        (self.pack / "tools/upstream-lock.json").write_text(json.dumps(self.lock))

    def save_local(self, entry):
        (self.pack / "tools/local-mods.json").write_text(
            json.dumps({"schemaVersion": 1, "files": [entry]}))

    def save_distribution(self, entries, **changes):
        doc = {"schemaVersion": 1, "packId": "caves-and-dungeons",
               "upstreamArchiveSha256": UPSTREAM_SHA256, "files": entries}
        doc.update(changes)
        (self.pack / "tools/distribution-lock.json").write_text(json.dumps(doc))

    def original(self, filename="original.jar", mod_id="original"):
        entry = self.jar(filename, mod_id)
        entry.update(projectId=1, fileId=2,
                     websiteUrl="https://www.curseforge.com/minecraft/mc-mods/original")
        return entry

    def add_nested(self, entry):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as nested:
            nested.writestr("META-INF/mods.toml",
                             '[[mods]]\nmodId="nested"\nversion="1.0.0"\n')
        path = "META-INF/jarjar/nested.jar"
        with zipfile.ZipFile(self.pack / entry["path"], "a") as archive:
            archive.writestr(path, buffer.getvalue())
            archive.writestr("META-INF/jarjar/metadata.json", json.dumps({"jars": [{"path": path}]}))
        data = (self.pack / entry["path"]).read_bytes()
        entry.update(sizeBytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def helper(self):
        entry = self.jar("cad-world-type-lock-1.0.0.jar", "cad_world_type_lock")
        entry.update(websiteUrl=LOCAL_PROJECT_URL, modIds=["cad_world_type_lock"])
        return entry

    def test_original_project_is_bound_to_exact_bytes(self):
        entry = self.jar("original.jar", "original")
        entry.update(projectId=1, fileId=2,
                     websiteUrl="https://www.curseforge.com/minecraft/mc-mods/original")
        self.lock["files"] = [entry]
        self.save_upstream()
        self.assertEqual(build_pages(self.pack), {"original": entry["websiteUrl"]})
        with (self.pack / "mods/original.jar").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "hash-verified"):
            build_pages(self.pack)

    def test_unavailable_origin_remains_nonclickable(self):
        entry = self.jar("original.jar", "illuminative")
        entry.update(projectId=818324, fileId=4721801,
                     websiteUrl="https://www.curseforge.com/minecraft/mc-mods/illuminative")
        self.lock["files"] = [entry]
        self.save_upstream()
        self.assertEqual(build_pages(self.pack)["illuminative"],
                         {"url": entry["websiteUrl"], "available": False})

    def test_unknown_jar_cannot_borrow_a_project_page(self):
        self.jar("unknown.jar", "unknown")
        self.save_upstream()
        with self.assertRaisesRegex(ValueError, "hash-verified"):
            build_pages(self.pack)

    def test_reviewed_local_helper_has_own_source(self):
        entry = self.helper()
        self.save_upstream()
        self.save_local(entry)
        self.assertEqual(build_pages(self.pack), {"cad_world_type_lock": LOCAL_PROJECT_URL})

    def test_local_helper_requires_actual_ids(self):
        entry = self.helper()
        self.jar("cad-world-type-lock-1.0.0.jar", "unreviewed_mod")
        self.save_upstream()
        # Match the changed bytes to prove the mod identity check is independent.
        data = (self.pack / entry["path"]).read_bytes()
        entry.update(sha256=hashlib.sha256(data).hexdigest(), sizeBytes=len(data))
        self.save_local(entry)
        with self.assertRaisesRegex(ValueError, "reviewed identity"):
            build_pages(self.pack)

    def test_missing_locked_helper_stops_publication(self):
        entry = self.helper()
        self.save_upstream()
        self.save_local(entry)
        (self.pack / entry["path"]).unlink()
        self.jar("original.jar", "original")
        data = (self.pack / "mods/original.jar").read_bytes()
        self.lock["files"] = [{"path": "mods/original.jar", "sizeBytes": len(data),
                               "sha256": hashlib.sha256(data).hexdigest(),
                               "projectId": 1, "fileId": 2,
                               "websiteUrl": "https://example.com/original"}]
        self.save_upstream()
        with self.assertRaisesRegex(ValueError, "helper is missing"):
            build_pages(self.pack)

    def test_helper_cannot_claim_another_project(self):
        entry = self.helper()
        entry["websiteUrl"] = "https://example.com/other"
        self.save_upstream()
        self.save_local(entry)
        with self.assertRaisesRegex(ValueError, "helper identity"):
            build_pages(self.pack)

    def test_active_replacement_wins_without_rewriting_history(self):
        original = self.original()
        self.lock["files"] = [original]
        self.save_upstream()
        history = (self.pack / "tools/upstream-lock.json").read_bytes()
        replacement = self.original("updated.jar")
        (self.pack / original["path"]).unlink()
        self.save_distribution([replacement])
        self.assertEqual(build_pages(self.pack), {"original": original["websiteUrl"]})
        self.assertEqual((self.pack / "tools/upstream-lock.json").read_bytes(), history)

    def test_invalid_active_identity_never_falls_back_to_history(self):
        entry = self.original()
        self.lock["files"] = [entry]
        self.save_upstream()
        self.save_distribution([entry], upstreamArchiveSha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "distribution lock"):
            build_pages(self.pack)

    def test_active_missing_jar_and_unknown_old_jar_are_rejected(self):
        entry = self.original()
        missing = dict(entry, path="mods/missing.jar")
        self.save_distribution([entry, missing])
        with self.assertRaisesRegex(ValueError, "Active locked jar is missing"):
            build_pages(self.pack)
        self.save_distribution([missing])
        with self.assertRaisesRegex(ValueError, "hash-verified"):
            build_pages(self.pack)

    def test_page_override_must_name_actual_nested_mod(self):
        entry = self.original()
        entry["modPages"] = {"nonexistent": "https://example.com/library"}
        self.save_distribution([entry])
        with self.assertRaisesRegex(ValueError, "absent mod"):
            build_pages(self.pack)
        entry["modPages"] = {"original": "https://example.com/unrelated"}
        self.save_distribution([entry])
        with self.assertRaisesRegex(ValueError, "parent project"):
            build_pages(self.pack)

    def test_nested_library_needs_own_reviewed_source(self):
        entry = self.original()
        self.add_nested(entry)
        self.save_distribution([entry])
        with self.assertRaisesRegex(ValueError, "own reviewed project page"):
            build_pages(self.pack)
        entry["modPages"] = {"nested": "https://github.com/author/nested"}
        self.save_distribution([entry])
        self.assertEqual(build_pages(self.pack),
                         {"original": entry["websiteUrl"], "nested": entry["modPages"]["nested"]})

    def test_reused_nested_mod_cannot_claim_conflicting_sources(self):
        entries = [self.original("one.jar", "one"), self.original("two.jar", "two")]
        for index, entry in enumerate(entries):
            self.add_nested(entry)
            entry["modPages"] = {"nested": "https://github.com/author/nested-" + str(index)}
        self.save_distribution(entries)
        with self.assertRaisesRegex(ValueError, "Conflicting upstream projects"):
            build_pages(self.pack)


if __name__ == "__main__":
    unittest.main()
