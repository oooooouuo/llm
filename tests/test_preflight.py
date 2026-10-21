"""Temporary schema fixtures are unit-test inputs, not experimental datasets."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from preflight import validate_inputs


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = self.base / 'evaluation'
        self.support = self.base / 'support'
        self.inventory = self.base / 'inventory.json'
        self.inventory.write_text(json.dumps({'fr:mot': [{'id': 'bn:0000001n', 'gloss': 'unit test only'}]}))
        self.write_csv(self.data / 'artificial_fr.csv', 'Evaluation <WSD>mot</WSD> context.')
        self.write_csv(self.support / 'artificial_fr.csv', 'Independent French <WSD>mot</WSD> context.')
        self.write_csv(self.support / 'artificial_en.csv', 'Independent English <WSD>word</WSD> context.')

    def write_csv(self, path, sentence, complexity=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ['sentence', 'senseid'] + (['complexity'] if complexity else [])
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            row = {'sentence': sentence, 'senseid': 'bn:0000001n'}
            if complexity:
                row['complexity'] = 'simple'
            writer.writerow(row)

    def check_inputs(self):
        return validate_inputs(self.data, self.support, self.inventory, ['artificial'], ['fr'])

    def test_valid_schema_and_hashes(self):
        errors, manifest = self.check_inputs()
        self.assertEqual(errors, [])
        self.assertEqual(len(manifest), 4)
        self.assertTrue(all(len(item['sha256']) == 64 for item in manifest))

    def test_overlap_is_rejected(self):
        self.write_csv(self.support / 'artificial_en.csv', 'EVALUATION  <WSD>mot</WSD> context.')
        errors, _ = self.check_inputs()
        self.assertTrue(any('相同句子' in e for e in errors))

    def test_missing_difficulty_is_rejected(self):
        self.write_csv(self.data / 'artificial_fr.csv', 'Evaluation <WSD>mot</WSD> context.', complexity=False)
        errors, _ = self.check_inputs()
        self.assertTrue(any('complexity' in e for e in errors))

    def test_gold_not_used_to_patch_inventory(self):
        self.inventory.write_text(json.dumps({'fr:mot': [{'id': 'bn:0000002n', 'gloss': 'unit test only'}]}))
        before = self.inventory.read_bytes()
        errors, _ = self.check_inputs()
        self.assertTrue(any('禁止用评估标签' in e for e in errors))
        self.assertEqual(before, self.inventory.read_bytes())

    def test_missing_english_support_rejected(self):
        (self.support / 'artificial_en.csv').unlink()
        errors, _ = self.check_inputs()
        self.assertTrue(any('artificial_en.csv' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
