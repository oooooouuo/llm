"""Technical unit cases only; these are not research samples or experiment results."""
import unittest
from evaluation import exact_match, parse_final_id


class EvaluationTests(unittest.TestCase):
    def test_final_answer_overrides_analysis(self):
        self.assertFalse(exact_match('Analysis: bn:0000001n\nFinal Answer: {"sense_id":"bn:0000002n"}', 'bn:0000001n'))

    def test_no_substring_digit_or_prose_credit(self):
        for response in ['bn:0000001n', 'The answer contains 0000001', '{"sense_id":"bn:0000001n-extra"}', '{"sense_id":"bn:0000001n"} trailing prose']:
            with self.subTest(response=response):
                self.assertFalse(exact_match(response, 'bn:0000001n'))

    def test_json_fences_and_multiple_gold(self):
        self.assertTrue(exact_match('```json\n{"sense_id":"bn:0000002n"}\n```', 'bn:0000001n, bn:0000002n'))

    def test_invalid_empty_and_case(self):
        for response in [None, '', '{}', '{"sense_id":null}', '{"sense_id":"BN:0000001N"}', '{"sense_id":"bn:0000001n", "other":1}']:
            self.assertIsNone(parse_final_id(response))

    def test_wordnet_key(self):
        self.assertTrue(exact_match('{"sense_id":"example%1:00:00::"}', 'example%1:00:00::'))


if __name__ == '__main__':
    unittest.main()
