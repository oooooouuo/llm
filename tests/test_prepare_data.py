"""Temporary schema fixtures, never research samples or inference results."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from prepare_data import prepare


class DataPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'raw'
        self.source.mkdir()
        self.inventory = self.root / 'inventory.json'
        self.ids = [f'bn:{i:08d}n' for i in range(1, 41)]
        self.inventory.write_text(json.dumps({f'{lang}:word': [{'id': value, 'gloss': 'unit test definition'}
                                                               for value in self.ids]
                                                for lang in ['en', 'fr']} | {'empty:entry': []}))
        self.rows = []
        for language in ['en', 'fr']:
            rows = [{'sentence': f'{language} unit context {i} <WSD>word</WSD>.',
                     'senseid': value, 'complexity': 'simple'} for i, value in enumerate(self.ids)]
            path = self.source / f'artificial_{language}.csv'
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['sentence', 'senseid', 'complexity'])
                writer.writeheader()
                writer.writerows(rows + rows[:1] + [{'sentence': 'invalid marker', 'senseid': self.ids[0],
                                                      'complexity': 'simple'}])

    def test_grouping_isolation_provenance_and_determinism(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()}
        first = prepare([self.source], self.inventory, self.root / 'first')
        second = prepare([self.source], self.inventory, self.root / 'second')
        self.assertEqual(first, second)
        self.assertEqual(first['input_rows'], 84)
        self.assertEqual(first['excluded_rows'], 4)
        partitions = {}
        for role, folder in [('evaluation', 'data'), ('support', 'support_data')]:
            values, groups = set(), set()
            for p in (self.root / 'first' / folder).glob('*.csv'):
                with p.open(encoding='utf-8-sig') as stream:
                    for row in csv.DictReader(stream):
                        values.add(row['senseid'])
                        groups.add(row['split_group'])
                        self.assertEqual(len(row['source_sha256']), 64)
            partitions[role] = (values, groups)
        self.assertFalse(partitions['evaluation'][0] & partitions['support'][0])
        self.assertFalse(partitions['evaluation'][1] & partitions['support'][1])
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()})
        with self.assertRaises(ValueError):
            prepare([self.source], self.inventory, self.root / 'first')

    def test_real_sentence_with_distinct_targets_keeps_both_instances(self):
        inventory = json.loads(self.inventory.read_text())
        inventory['fr:first'] = [{'id': self.ids[0], 'gloss': 'unit test'}]
        inventory['fr:second'] = [{'id': self.ids[1], 'gloss': 'unit test'}]
        self.inventory.write_text(json.dumps(inventory))
        path = self.source / 'sem13_fr.csv'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['sentence', 'senseid', 'complexity', 'fileid'])
            writer.writeheader()
            for doc in range(30):
                for word, sense in [('first', self.ids[0]), ('second', self.ids[1])]:
                    text = f'unit document {doc} first second'
                    text = text.replace(word, f'<WSD>{word}</WSD>')
                    writer.writerow({'sentence': text, 'senseid': sense,
                                     'complexity': 'simple', 'fileid': f'doc{doc}'})
        manifest = prepare([self.source], self.inventory, self.root / 'real_check', allow_missing_english=True)
        counts = [x for x in manifest['unit_partition_counts'] if x['source'] == 'real'][0]
        self.assertEqual(counts['evaluation'] + counts['support'], 60)
        documents = {}
        for role, folder in [('evaluation', 'data'), ('support', 'support_data')]:
            with (self.root / 'real_check' / folder / 'fr/sem13_fr.csv').open(encoding='utf-8-sig') as stream:
                documents[role] = {row['fileid'] for row in csv.DictReader(stream)}
        self.assertFalse(documents['evaluation'] & documents['support'])


if __name__ == '__main__':
    unittest.main()
