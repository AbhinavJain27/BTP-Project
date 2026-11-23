import unittest
import numpy as np
import igraph as ig

from river_networks.analysis.tree_algorithms import (
    compute_exact_directed_avg_path,
    compute_exact_tree_betweenness,
    compute_landmark_undirected_path,
)

class TestTreeAlgorithms(unittest.TestCase):
    def setUp(self):
        # Build synthetic tree:
        # 0 -> 2, 1 -> 2, 2 -> 3 (3 is outlet)
        self.g = ig.Graph(n=4, directed=True)
        self.g.vs["node_id"] = ["junction:1", "junction:2", "junction:3", "outlet:3"]
        self.g.add_edges([(0, 2), (1, 2), (2, 3)])
        self.g.es["HYRIV_ID"] = [1, 2, 3]

    def test_exact_tree_betweenness_matches_igraph_exact(self):
        igraph_bw = np.array(self.g.betweenness(directed=True), dtype=float)
        tree_bw = compute_exact_tree_betweenness(self.g)

        # On node 2 (confluence), paths 0->2->3 and 1->2->3 pass through 2. Betweenness = 2.0
        self.assertEqual(tree_bw[2], 2.0)
        self.assertEqual(tree_bw[0], 0.0)
        self.assertEqual(tree_bw[1], 0.0)
        self.assertEqual(tree_bw[3], 0.0)
        np.testing.assert_allclose(tree_bw, igraph_bw, rtol=1e-5)

    def test_exact_directed_avg_path(self):
        # Paths:
        # 0->2 (1 hop), 0->3 (2 hops)
        # 1->2 (1 hop), 1->3 (2 hops)
        # 2->3 (1 hop)
        # Total hops = 1 + 2 + 1 + 2 + 1 = 7 hops. Total paths = 5. Mean = 7/5 = 1.4 hops
        mean_path = compute_exact_directed_avg_path(self.g)
        self.assertAlmostEqual(mean_path, 1.4, places=4)

    def test_landmark_undirected_path(self):
        g_undir = self.g.as_undirected()
        res = compute_landmark_undirected_path(g_undir, num_landmarks=4)
        self.assertIn("mean", res)
        self.assertIn("ci_95", res)
        self.assertGreater(res["mean"], 0.0)

if __name__ == "__main__":
    unittest.main()
