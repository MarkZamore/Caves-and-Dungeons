"""Content coverage, language isolation and gameplay preservation for localization."""
from pathlib import Path
import copy
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('russian_advancement_audit', ROOT / 'tools/russian-advancements/audit.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class RussianAdvancementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effective, cls.original, cls.languages, _ = AUDIT.scan_pack(ROOT)
        cls.report = AUDIT.audit(ROOT)

    def test_all_shipped_mod_displays_resolve_to_russian(self):
        self.assertEqual(567, self.report['visibleCount'])
        self.assertEqual(457, self.report['checkedCount'])
        self.assertEqual([], self.report['failures'])

    def test_only_literal_display_is_overridden_and_gameplay_is_identical(self):
        changed = {key for key in self.original if self.original[key] != self.effective[key]}
        self.assertEqual({'nova_structures:adventure/tavern_quest'}, changed)
        for key in changed:
            before = copy.deepcopy(self.original[key])
            after = copy.deepcopy(self.effective[key])
            for field in ('title', 'description'):
                before['display'].pop(field)
                after['display'].pop(field)
            self.assertEqual(before, after)

    def test_literal_override_keeps_original_english(self):
        identifier = 'nova_structures:adventure/tavern_quest'
        for field in ('title', 'description'):
            key = self.effective[identifier]['display'][field]['translate']
            self.assertEqual(self.original[identifier]['display'][field], self.languages['en_us'][key])
            self.assertRegex(self.languages['ru_ru'][key], '[А-Яа-яЁё]')

    def test_display_override_is_inside_dedicated_builtin_datapack(self):
        root = AUDIT.RESOURCES / AUDIT.BUILTIN
        metadata = json.loads((root / 'pack.mcmeta').read_text(encoding='utf-8'))
        self.assertEqual(15, metadata['pack']['pack_format'])
        paths = [path.relative_to(root).as_posix() for path in root.rglob('*.json')]
        self.assertEqual(['data/nova_structures/advancements/adventure/tavern_quest.json'], paths)
        self.assertFalse((AUDIT.RESOURCES / 'data/nova_structures/advancements/adventure/tavern_quest.json').exists())

    def test_translation_sources_are_only_russian_plus_two_literal_fallbacks(self):
        for path in AUDIT.RESOURCES.glob('assets/*/lang/ru_ru.json'):
            values = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(values)
            for key, value in values.items():
                self.assertIsInstance(value, str)
                self.assertRegex(value, '[А-Яа-яЁё]', (path.name, key))
        en = json.loads((AUDIT.RESOURCES / 'assets/caves_and_dungeons/lang/en_us.json').read_text(encoding='utf-8'))
        self.assertEqual(2, len(en))


if __name__ == '__main__':
    unittest.main()
