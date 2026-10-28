"""Content checks: real advancement coverage, reachable route, and no rewards."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("generate.py")
SPEC = importlib.util.spec_from_file_location("cad_quest_generator", MODULE)
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class QuestBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = MODULE.resolve().parents[2]
        cls.outputs, cls.report = generator.generate(cls.root)
        cls.quests = [q for data in cls.outputs.values() for q in data.get("quests", [])]
        cls.advancements = generator.advancements(cls.root)

    def test_committed_book_matches_current_mods_and_authored_guide(self):
        generator.run(self.root, verify=True)

    def test_every_mod_display_has_exactly_one_automatic_task(self):
        excluded = generator.exclusions(self.root, self.advancements)
        expected = {key for key, data in self.advancements.items()
                    if not key.startswith("minecraft:") and data.get("display") and key not in excluded}
        tasks = [task for quest in self.quests for task in quest["tasks"] if task["type"] == "advancement"]
        ids = [task["advancement"] for task in tasks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(expected.issubset(ids))
        self.assertTrue(all(task["criterion"] == "" for task in tasks))
        self.assertTrue(all(key in self.advancements for key in ids))
        self.assertFalse(excluded.intersection(ids))

    def test_native_snapshot_detects_missing_targets_and_newly_enabled_mod_targets(self):
        excluded = generator.exclusions(self.root, self.advancements)
        available = {key: data for key, data in self.advancements.items() if data.get("display") and key not in excluded}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            path.write_text(json.dumps({"advancements": available}), encoding="utf-8")
            generator.verify_runtime(self.outputs, path)
            available["quark:influence"] = self.advancements["quark:influence"]
            path.write_text(json.dumps({"advancements": available}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "uncovered mods.*quark:influence"):
                generator.verify_runtime(self.outputs, path)
            del available["quark:influence"]
            del available["alexscaves:alexscaves/cave_map"]
            path.write_text(json.dumps({"advancements": available}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing=.*alexscaves:alexscaves/cave_map"):
                generator.verify_runtime(self.outputs, path)

    def test_no_reward_or_consumption_path(self):
        for quest in self.quests:
            self.assertEqual([], quest["rewards"])
            for task in quest["tasks"]:
                self.assertIn(task["type"], {"advancement", "checkmark", "item"})
                if task["type"] == "item":
                    self.assertIs(task["consume_items"], False)
        data = self.outputs[generator.BOOK / "data.snbt"]
        self.assertIs(data["default_consume_items"], False)
        self.assertIs(data["drop_loot_crates"], False)
        self.assertEqual([], data["emergency_items"])
        self.assertFalse(any("reward_tables" in str(p) for p in self.outputs))

    def test_primary_route_has_no_cycles_or_nether_requirements(self):
        quests = {q["id"]: q for q in self.quests}
        checked = set()
        active = set()

        def visit(qid):
            self.assertNotIn(qid, active)
            if qid in checked:
                return
            active.add(qid)
            for dependency in quests[qid].get("dependencies", []):
                self.assertIn(dependency, quests)
                visit(dependency)
            active.remove(qid)
            checked.add(qid)

        for qid in quests:
            visit(qid)
        main_tasks = [t for p, data in self.outputs.items() if p.name in {"start.snbt", "equipment.snbt", "caves.snbt", "end.snbt"}
                      for q in data["quests"] for t in q["tasks"]]
        self.assertFalse(any(t.get("advancement", "").startswith("minecraft:nether/") for t in main_tasks))
        mine_diamond = quests[generator.code("quest/minecraft:story/mine_diamond")]
        self.assertEqual([generator.code("quest/spelunkery:spelunkery/diamond_grindstone")], mine_diamond["dependencies"])
        for quest in self.quests:
            if quest.get("optional"):
                self.assertFalse(quest.get("dependencies"), "An inaccessible native parent must not gate side quests")
        item_ids = {q["id"] for q in self.quests if any(t["type"] == "item" for t in q["tasks"])}
        for quest in self.quests:
            self.assertFalse(item_ids.intersection(quest.get("dependencies", [])),
                             "Already consumed route ingredients must not block an old save")

    def test_nether_free_recipe_hints_match_author_scripts(self):
        script = (self.root / "scripts/recipes_for_CaD.zs").read_text(encoding="utf-8")
        self.assertIn('craftingTable.addShapeless("blazepowder", <item:minecraft:blaze_powder>, [<item:alexscaves:sulfur_dust>, <item:minecraft:glowstone_dust>])', script)
        self.assertIn('craftingTable.addShapeless("blazerod", <item:minecraft:blaze_rod> * 3, [<item:alexscaves:ambersol>])', script)
        self.assertIn('craftingTable.addShapeless("glowstonedust", <item:minecraft:glowstone_dust>, [<item:minecraft:sand>, <item:cavesanddepths:glittering_dust>])', script)

    def test_native_components_are_valid_and_item_format_is_1201(self):
        for quest in self.quests:
            for value in [quest["title"], *quest["description"]]:
                if value.lstrip().startswith(("{", "[")):
                    self.assertIsNotNone(json.loads(value))
            self.assertIsInstance(quest["icon"], str)
            self.assertNotIn("components", quest)


if __name__ == "__main__":
    unittest.main()
