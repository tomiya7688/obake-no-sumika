from __future__ import annotations

import unittest

from tools.performance.compare_runtime import compare_metric, regression_limit


class PerformanceRegressionTests(unittest.TestCase):
    def test_percentage_limit_wins_when_larger_than_noise_floor(self) -> None:
        self.assertAlmostEqual(regression_limit(10.0, 35.0, 3.0), 13.5)

    def test_noise_floor_wins_for_small_frame_times(self) -> None:
        self.assertAlmostEqual(regression_limit(1.5, 35.0, 0.5), 2.025)

    def test_comparison_rejects_value_above_limit(self) -> None:
        self.assertFalse(compare_metric("game", 1.5, 2.1, 35.0, 0.5, "ms/frame"))

    def test_comparison_accepts_value_inside_limit(self) -> None:
        self.assertTrue(compare_metric("engine", 9.0, 11.5, 35.0, 3.0, "ms"))


if __name__ == "__main__":
    unittest.main()
