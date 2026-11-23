import unittest
import pandas as pd

from river_networks.analysis.scaling import (
    compute_all_scaling_metrics,
    compute_hack_law,
    compute_horton_ratios,
    compute_tokunaga_statistics,
)

class TestScaling(unittest.TestCase):
    def setUp(self):
        # Create a synthetic hierarchy:
        # Order 1: 16 streams, Order 2: 4 streams, Order 3: 1 stream (RB ~ 4)
        records = []
        for i in range(16):
            records.append({"HYRIV_ID": i + 1, "NEXT_DOWN": 17 + (i // 4), "ORD_STRA": 1, "LENGTH_KM": 2.0, "UPLAND_SKM": 10.0, "CATCH_SKM": 10.0})
        for i in range(4):
            records.append({"HYRIV_ID": 17 + i, "NEXT_DOWN": 21, "ORD_STRA": 2, "LENGTH_KM": 5.0, "UPLAND_SKM": 50.0, "CATCH_SKM": 10.0})
        records.append({"HYRIV_ID": 21, "NEXT_DOWN": 0, "ORD_STRA": 3, "LENGTH_KM": 12.0, "UPLAND_SKM": 250.0, "CATCH_SKM": 10.0})
        self.frame = pd.DataFrame(records)

    def test_horton_bifurcation_ratio(self):
        res = compute_horton_ratios(self.frame)
        self.assertIn("bifurcation_ratio", res)
        # Ratio 16/4 = 4.0, 4/1 = 4.0 -> RB should be ~ 4.0
        self.assertAlmostEqual(res["bifurcation_ratio"], 4.0, delta=0.5)
        self.assertGreater(res["r2_bifurcation"], 0.95)

    def test_hack_law(self):
        res = compute_hack_law(self.frame)
        self.assertIn("hack_exponent", res)
        self.assertGreater(res["hack_exponent"], 0.0)

    def test_tokunaga_statistics(self):
        res = compute_tokunaga_statistics(self.frame)
        self.assertTrue(res.get("tokunaga_applicable"))
        self.assertIn("t_matrix", res)
        self.assertIsNone(res["branching_ratio_K"])

    def test_horton_counts_a_chain_of_same_order_reaches_as_one_stream(self):
        extra = pd.DataFrame([{
            "HYRIV_ID": 22, "NEXT_DOWN": 1, "ORD_STRA": 1, "LENGTH_KM": 2.0,
            "UPLAND_SKM": 3.0, "CATCH_SKM": 3.0,
        }])
        result = compute_horton_ratios(pd.concat([self.frame, extra], ignore_index=True))
        self.assertEqual(result["stream_counts"], [16, 4, 1])
        self.assertAlmostEqual(result["mean_lengths_km"][0], 34 / 16)

    def test_compute_all_scaling_metrics(self):
        all_metrics = compute_all_scaling_metrics(self.frame)
        self.assertIn("horton", all_metrics)
        self.assertIn("hack", all_metrics)
        self.assertIn("tokunaga", all_metrics)

if __name__ == "__main__":
    unittest.main()
