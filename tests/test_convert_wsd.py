"""XML format unit fixtures only; no external corpus or model calls."""
from pathlib import Path
import csv
import tempfile
import unittest
from convert_wsd import convert


class ConversionTests(unittest.TestCase):
    def test_targets_gold_and_unlabelled_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xml, gold, output = root / 'unit.xml', root / 'unit.keys', root / 'unit.csv'
            xml.write_text('<corpus><text id="doc"><sentence id="sentence">'
                           '<wf>Example</wf><instance id="a" lemma="word">word</instance>'
                           '<instance id="b">other</instance></sentence></text></corpus>')
            gold.write_text('a bn:00000001n bn:00000002n\n')
            report = convert(xml, gold, output, 'en')
            with output.open(encoding='utf-8-sig') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['sentence'], 'Example <WSD>word</WSD> other')
            self.assertEqual(rows[0]['senseid'], 'bn:00000001n bn:00000002n')
            self.assertEqual(report['unlabelled_instance_ids'], ['b'])
            self.assertFalse(report['historical_conversion'])
            with self.assertRaises(ValueError):
                convert(xml, gold, output, 'en')


if __name__ == '__main__':
    unittest.main()
