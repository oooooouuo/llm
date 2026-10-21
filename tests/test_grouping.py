"""Unit-level arithmetic fixtures; no model calls or experiment exports."""
import unittest
from experiment_runner1_v2 import ActualFusionRunner, ExperimentResult


class GroupingTests(unittest.TestCase):
    def make_result(self, source, version, accuracy):
        return ExperimentResult('test_only', 'gpt-4o', source, 'fr', 'simple', version, accuracy=accuracy)

    def test_sources_use_their_own_baseline(self):
        runner = ActualFusionRunner.__new__(ActualFusionRunner)
        runner.existing_summary = [self.make_result('real', 'Baseline', 0.2),
                                   self.make_result('artificial', 'Baseline', 0.8),
                                   self.make_result('real', 'Ours(Fusion)', 0.3)]
        runner._calculate_improvement()
        self.assertAlmostEqual(runner.existing_summary[-1].improvement, 0.1)

    def test_missing_baseline_is_not_zero(self):
        runner = ActualFusionRunner.__new__(ActualFusionRunner)
        runner.existing_summary = [self.make_result('problem', 'Ours(Fusion)', 0.3)]
        runner._calculate_improvement()
        self.assertIsNone(runner.existing_summary[0].improvement)


if __name__ == '__main__':
    unittest.main()
