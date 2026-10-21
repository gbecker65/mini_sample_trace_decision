"""Tests for mini_sample_trace_decision.core."""

import hashlib
import math
import unittest

from mini_sample_trace_decision import TraceSampler, SamplingDecision


class TestConstructor(unittest.TestCase):
    def test_rate_zero_allowed(self):
        self.assertEqual(TraceSampler(0.0).rate, 0.0)

    def test_rate_one_allowed(self):
        self.assertEqual(TraceSampler(1.0).rate, 1.0)

    def test_rate_in_middle_allowed(self):
        self.assertAlmostEqual(TraceSampler(0.25).rate, 0.25)

    def test_rate_negative_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(-0.01)

    def test_rate_above_one_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(1.01)

    def test_rate_nan_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(float("nan"))

    def test_rate_inf_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(float("inf"))

    def test_rate_neg_inf_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(float("-inf"))


class TestDecide(unittest.TestCase):
    def test_rate_zero_drops_everything(self):
        sampler = TraceSampler(0.0)
        self.assertFalse(sampler.should_keep("abc123"))
        self.assertFalse(sampler.decide("abc123").kept)

    def test_rate_one_keeps_everything(self):
        sampler = TraceSampler(1.0)
        self.assertTrue(sampler.should_keep("abc123"))
        self.assertTrue(sampler.decide("abc123").kept)

    def test_decision_is_deterministic(self):
        sampler = TraceSampler(0.5)
        first = sampler.decide("trace-xyz")
        second = sampler.decide("trace-xyz")
        self.assertEqual(first, second)

    def test_decision_returns_sampling_decision(self):
        sampler = TraceSampler(0.5)
        decision = sampler.decide("trace-xyz")
        self.assertIsInstance(decision, SamplingDecision)
        self.assertIsInstance(decision.kept, bool)
        self.assertIsInstance(decision.ratio, float)

    def test_ratio_matches_documented_formula(self):
        """The exposed ratio must equal sha256(id)[:8] / 2**64."""
        trace_id = "trace-xyz"
        digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
        expected = int.from_bytes(digest[:8], "big", signed=False) / (2**64)
        decision = TraceSampler(1.0).decide(trace_id)
        self.assertAlmostEqual(decision.ratio, expected, places=15)

    def test_ratio_is_in_unit_interval(self):
        sampler = TraceSampler(0.5)
        for tid in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            ratio = sampler.decide(tid).ratio
            self.assertGreaterEqual(ratio, 0.0)
            self.assertLess(ratio, 1.0)

    def test_kept_iff_ratio_below_rate(self):
        """kept must be exactly the comparison ratio < rate."""
        trace_id = "trace-xyz"
        digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
        ratio = int.from_bytes(digest[:8], "big", signed=False) / (2**64)
        # Rate just above the ratio -> kept.
        just_above = math.nextafter(ratio, 1.0)
        self.assertTrue(TraceSampler(just_above).decide(trace_id).kept)
        # Rate equal to the ratio -> dropped, because the check is strict <.
        self.assertFalse(TraceSampler(ratio).decide(trace_id).kept)
        # Rate just below the ratio -> dropped.
        just_below = math.nextafter(ratio, 0.0)
        self.assertFalse(TraceSampler(just_below).decide(trace_id).kept)

    def test_empty_trace_id_rejected(self):
        with self.assertRaises(ValueError):
            TraceSampler(0.5).decide("")

    def test_non_string_trace_id_rejected(self):
        with self.assertRaises(TypeError):
            TraceSampler(0.5).decide(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            TraceSampler(0.5).decide(None)  # type: ignore[arg-type]

    def test_different_trace_ids_can_differ(self):
        """Two ids that hash to opposite sides of the threshold differ."""
        sampler = TraceSampler(0.5)
        # Find one kept and one dropped among a small fixed set so the
        # assertion is deterministic and does not depend on hash luck.
        ids = ["id-%d" % i for i in range(50)]
        kept = [i for i in ids if sampler.should_keep(i)]
        dropped = [i for i in ids if not sampler.should_keep(i)]
        self.assertTrue(kept, "expected at least one kept id in the set")
        self.assertTrue(dropped, "expected at least one dropped id in the set")


if __name__ == "__main__":
    unittest.main()
