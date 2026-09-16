from __future__ import annotations

import unittest

from tools.quality.check_mypy import count_errors, evaluate_result


class MypyBaselineTests(unittest.TestCase):
    def test_count_errors_reads_mypy_error_lines(self) -> None:
        output = "a.py:1: error: bad [misc]\nb.py:2: note: detail\nc.py:3: error: bad [arg-type]\n"
        self.assertEqual(count_errors(output), 2)

    def test_gate_rejects_new_errors(self) -> None:
        passed, message = evaluate_result(1, 51, 50)
        self.assertFalse(passed)
        self.assertIn("increased", message)

    def test_gate_accepts_current_baseline(self) -> None:
        passed, message = evaluate_result(1, 50, 50)
        self.assertTrue(passed)
        self.assertIn("unchanged", message)

    def test_gate_accepts_improvement_and_requests_ratchet(self) -> None:
        passed, message = evaluate_result(1, 40, 50)
        self.assertTrue(passed)
        self.assertIn("lower baseline", message)

    def test_gate_rejects_unclassified_mypy_failure(self) -> None:
        passed, message = evaluate_result(2, 0, 50)
        self.assertFalse(passed)
        self.assertIn("without countable", message)


if __name__ == "__main__":
    unittest.main()
