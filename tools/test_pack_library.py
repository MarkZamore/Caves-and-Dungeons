import json
import pathlib
import tempfile
import unittest
import zipfile
from pack_library import build_library, stage_library, verify_library, read_mods, merge_mods


class LibraryPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pack = pathlib.Path(self.temp.name) / "Example Pack"
        (self.pack / "mods").mkdir(parents=True)
        (self.pack / "library").mkdir()
        (self.pack / "portable-pack.json").write_text(json.dumps({"minecraftVersion": "1.21.1", "loader": {"type": "NeoForge"}}))
        self.content = {"id": "example", "name": "Example", "relativePath": "Stable Folder", "summary": "A short story", "description": "A longer story",
                        "parents": {"addon": "base"}, "libraryIds": ["helper"]}
        self.pages = {mid: "https://www.curseforge.com/minecraft/mc-mods/" + mid
                      for mid in ("base", "addon", "helper", "integration")}
        self.write_pages()
        self.write_content()
        (self.pack / "library/preview.jpg").write_bytes(b"test preview bytes")
        for mod_id, name in (("base", "Base Mod"), ("addon", "An Addon"), ("helper", "A Helper Library"), ("integration", "Independent integration")):
            with zipfile.ZipFile(self.pack / "mods" / (mod_id + ".jar"), "w") as archive:
                archive.writestr("META-INF/neoforge.mods.toml", f'[[mods]]\nmodId="{mod_id}"\ndisplayName="{name}"\nversion="1.2.3"\n[[dependencies.{mod_id}]]\nmodId="base"\ntype="required"\n')

    def tearDown(self):
        self.temp.cleanup()

    def write_pages(self):
        (self.pack / "library/mod-pages.json").write_text(json.dumps(self.pages))

    def write_content(self):
        (self.pack / "library/content.json").write_text(json.dumps(self.content))

    def test_actual_names_curated_addons_and_libraries_not_the_whole_dependency_graph(self):
        payload = build_library(self.pack, "revision-one")
        target = pathlib.Path(self.temp.name) / "bundle.zip"
        target.write_bytes(payload)
        with zipfile.ZipFile(target) as archive:
            data = json.loads(archive.read("library.json"))
        mods = {m["id"]: m for m in data["mods"]}
        self.assertEqual("An Addon", mods["addon"]["name"])
        self.assertEqual(self.pages["addon"], mods["addon"]["websiteUrl"])
        self.assertEqual(self.pages["base"], mods["base"]["websiteUrl"])
        self.assertEqual(self.pages["helper"], mods["helper"]["websiteUrl"])
        self.assertEqual("base", mods["addon"]["parentId"])
        self.assertIsNone(mods["integration"]["parentId"])
        self.assertTrue(mods["helper"]["isLibrary"])
        self.assertEqual("1.21.1", data["minecraftVersion"])
        self.assertEqual("revision-one", data["revision"])
        self.assertEqual("Stable Folder", data["relativePath"])

    def test_bundle_is_deterministic_and_tampering_fails_verification(self):
        self.assertEqual(build_library(self.pack, "r1"), build_library(self.pack, "r1"))
        out = pathlib.Path(self.temp.name) / "out"
        descriptor = stage_library(self.pack, out, "r1")
        verify_library(out, descriptor)
        (out / "assets" / descriptor["name"]).write_bytes(b"tampered")
        with self.assertRaises(AssertionError):
            verify_library(out, descriptor)

    def test_new_mod_requires_an_explicit_official_project_page(self):
        del self.pages["addon"]
        self.write_pages()
        with self.assertRaisesRegex(ValueError, "official project page for mod: addon"):
            build_library(self.pack, "r1")

    def test_only_https_project_pages_are_published(self):
        for value in ("javascript:alert(1)", "file:///C:/mod.jar", "https://user:secret@example.com/mod", ""):
            self.pages["addon"] = value
            self.write_pages()
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_library(self.pack, "r1")
        self.pages["addon"] = "https://modrinth.com/mod/an-addon"
        self.write_pages()
        self.assertTrue(build_library(self.pack, "r1"))

    def test_unavailable_author_page_is_preserved_but_not_clickable(self):
        self.pages["addon"] = {"url": "https://github.com/author/unavailable", "available": False}
        self.write_pages()
        payload = build_library(self.pack, "r1")
        import io
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            mods = json.loads(archive.read("library.json"))["mods"]
        addon = next(mod for mod in mods if mod["id"] == "addon")
        self.assertFalse(addon["websiteAvailable"])
        self.assertEqual(self.pages["addon"]["url"], addon["websiteUrl"])

    def test_cyclic_addon_map_cannot_be_published(self):
        self.content["parents"] = {"addon": "base", "base": "addon"}
        self.write_content()
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            build_library(self.pack, "r1")

    def nested_mod(self, parent, version, forge_metadata=True):
        import io
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as nested:
            if forge_metadata:
                nested.writestr("META-INF/mods.toml",
                                f'[[mods]]\nmodId="shared"\ndisplayName="Shared Library"\nversion="{version}"\n')
            else:
                nested.writestr("fabric.mod.json", json.dumps({"id": "fabric_only", "version": version}))
        path = "META-INF/jarjar/shared.jar"
        with zipfile.ZipFile(self.pack / "mods" / (parent + ".jar"), "a") as archive:
            archive.writestr(path, buffer.getvalue())
            archive.writestr("META-INF/jarjar/metadata.json", json.dumps({"jars": [{"path": path}]}))

    def test_parent_and_reused_nested_library_are_both_listed_once(self):
        import io
        self.nested_mod("base", "0.3.6")
        self.nested_mod("addon", "0.4.1")
        self.pages["shared"] = "https://github.com/author/shared"
        self.write_pages()
        self.content["libraryIds"].append("shared")
        self.write_content()
        with zipfile.ZipFile(io.BytesIO(build_library(self.pack, "r1"))) as archive:
            mods = json.loads(archive.read("library.json"))["mods"]
        shared = [mod for mod in mods if mod["id"] == "shared"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["version"], "0.4.1")
        self.assertTrue(shared[0]["isLibrary"])
        self.assertEqual({mod["id"] for mod in mods}, {"base", "addon", "helper", "integration", "shared"})

    def test_generated_fabric_metadata_does_not_invent_nested_forge_mod(self):
        self.nested_mod("base", "1.0.0", forge_metadata=False)
        data = (self.pack / "mods/base.jar").read_bytes()
        self.assertEqual([mod["id"] for mod in read_mods(data, "base.jar")], ["base"])

    def test_duplicate_metadata_conflict_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting metadata"):
            merge_mods([{"id": "shared", "name": "Real Project", "version": "1.0.0"},
                        {"id": "shared", "name": "Other Project", "version": "1.0.0"}])


if __name__ == "__main__":
    unittest.main()
