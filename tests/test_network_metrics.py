import unittest
import numpy as np

try:
    import igraph as ig
except ImportError:
    ig = None

from river_networks.graph.metrics import compute_network_metrics

class TestNetworkMetrics(unittest.TestCase):
    def setUp(self):
        if ig is None:
            self.skipTest("igraph is not installed")

    def test_synthetic_tree_metrics(self):

        g = ig.Graph(n=4, directed=True)
        g.vs["node_id"] = ["junction:1", "junction:2", "junction:3", "outlet:3"]
        g.vs["node_type"] = ["headwater", "headwater", "confluence/junction", "downstream/outlet"]
        g.add_edges([(0, 2), (1, 2), (2, 3)])
        g.es["HYRIV_ID"] = [1, 2, 3]

        metrics = compute_network_metrics(g)

        self.assertEqual(metrics["node_count"], 4)
        self.assertEqual(metrics["edge_count"], 3)
        self.assertEqual(metrics["self_loops"], 0)
        self.assertTrue(metrics["connected_components"]["is_dag"])
        self.assertEqual(metrics["connected_components"]["weak_count"], 1)

        self.assertEqual(metrics["in_degree"]["max"], 2)
        self.assertEqual(metrics["in_degree"]["min"], 0)
        self.assertEqual(metrics["out_degree"]["max"], 1)
        self.assertEqual(metrics["out_degree"]["min"], 0)

        self.assertEqual(metrics["clustering_coefficient"]["global_transitivity"], 0.0)

        self.assertEqual(metrics["diameter"]["directed"], 2)
        self.assertEqual(metrics["diameter"]["undirected"], 2)
        self.assertEqual(metrics["shortest_paths_to_outlet"]["max_hops"], 2)
        self.assertEqual(metrics["shortest_paths_to_outlet"]["min_hops"], 0)

        self.assertIn("betweenness_centrality", metrics["centrality_measures"])
        self.assertIn("pagerank_centrality", metrics["centrality_measures"])
        self.assertIn("degree_centrality", metrics["centrality_measures"])
        self.assertEqual(metrics["centrality_measures"]["degree_centrality"]["max_degree"], 3)

if __name__ == "__main__":
    unittest.main()
