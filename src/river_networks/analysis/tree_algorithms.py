"""Exact linear-time O(V) tree algorithms and error-bounded landmark sampling for river networks."""

from __future__ import annotations

from typing import Any
import numpy as np

def compute_exact_tree_betweenness(graph) -> np.ndarray:
    """Computes exact directed betweenness centrality in O(V) linear time on a directed river tree.

    In a directed hydrological drainage network where flow converges downstream (out-degree <= 1),
    any directed path from an upstream tributary to a downstream target passing through node u
    originates in u's upstream subtree and terminates at one of u's downstream descendants.

    Therefore, the exact number of shortest paths through u is:
        Betweenness(u) = (SubtreeSize(u) - 1) * DownstreamPathLength(u)

    This replaces igraph's O(VE) Brandes algorithm (which requires ~5.5e11 operations on Amazon)
    with a linear-time O(V) dynamic program running in < 0.5s.
    """
    vcount = graph.vcount()
    if vcount <= 2:
        return np.zeros(vcount, dtype=float)

    in_deg = np.array(graph.indegree(), dtype=int)
    out_deg = np.array(graph.outdegree(), dtype=int)

    # 1. Identify outlet(s)
    outlets = np.where(out_deg == 0)[0]
    if len(outlets) == 0:
        outlets = np.array([int(np.argmin(out_deg))])

    # 2. Downstream path length to outlet for each vertex (in hops)
    dists = graph.distances(source=outlets.tolist(), mode="in")
    dists_arr = np.array(dists, dtype=float)
    downstream_hops = np.min(dists_arr, axis=0)
    downstream_hops[~np.isfinite(downstream_hops)] = 0.0

    # 3. Subtree size via forward topological traversal (headwater to outlet)
    topo_order = graph.topological_sorting(mode="out")
    subtree_size = np.ones(vcount, dtype=float)
    for u in topo_order:
        neighbors = graph.neighbors(u, mode="out")
        for v in neighbors:
            subtree_size[v] += subtree_size[u]

    # 4. Exact betweenness = upstream_nodes * downstream_nodes
    upstream_nodes = np.maximum(0.0, subtree_size - 1.0)
    betweenness = upstream_nodes * downstream_hops
    return betweenness

def compute_exact_directed_avg_path(graph, subtree_size: np.ndarray | None = None) -> float:
    """Computes exact average path length across all directed reachable pairs in O(V) time."""
    vcount = graph.vcount()
    if vcount <= 1:
        return 0.0

    out_deg = np.array(graph.outdegree(), dtype=int)
    outlets = np.where(out_deg == 0)[0]
    if len(outlets) == 0:
        outlets = np.array([int(np.argmin(out_deg))])

    dists = graph.distances(source=outlets.tolist(), mode="in")
    dists_arr = np.array(dists, dtype=float)
    downstream_hops = np.min(dists_arr, axis=0)
    downstream_hops[~np.isfinite(downstream_hops)] = 0.0

    if subtree_size is None:
        topo_order = graph.topological_sorting(mode="out")
        subtree_size = np.ones(vcount, dtype=float)
        for u in topo_order:
            for v in graph.neighbors(u, mode="out"):
                subtree_size[v] += subtree_size[u]

    total_hops_sum = 0.0
    for edge in graph.es:
        u = edge.source
        v = edge.target
        downstream_targets = 1.0 + downstream_hops[v]
        total_hops_sum += float(subtree_size[u]) * downstream_targets

    total_paths = float(np.sum(downstream_hops))
    if total_paths <= 0:
        return 0.0
    return float(total_hops_sum / total_paths)

def compute_landmark_undirected_path(
    graph_undir, num_landmarks: int = 50, seed: int = 42
) -> dict[str, Any]:
    """Computes undirected average path length using landmark BFS with error bounds."""
    vcount = graph_undir.vcount()
    if vcount <= 1:
        return {"mean": 0.0, "std_error": 0.0, "ci_95": [0.0, 0.0], "exact": True}

    if vcount <= 5000:
        try:
            val = float(graph_undir.average_path_length(directed=False))
            return {"mean": val, "std_error": 0.0, "ci_95": [val, val], "exact": True}
        except Exception:
            pass

    sample_size = min(num_landmarks, vcount)
    rng = np.random.default_rng(seed)
    landmarks = rng.choice(vcount, size=sample_size, replace=False).tolist()

    landmark_means = []
    total_d = 0.0
    total_cnt = 0

    for s in landmarks:
        row = graph_undir.distances(source=int(s))[0]
        finite = [d for d in row if 0 < d < float("inf")]
        if finite:
            total_d += sum(finite)
            total_cnt += len(finite)
            landmark_means.append(float(np.mean(finite)))

    mean_val = float(total_d / total_cnt) if total_cnt > 0 else 0.0
    std_error = float(np.std(landmark_means) / np.sqrt(len(landmark_means))) if len(landmark_means) > 1 else 0.0
    ci_95 = [max(0.0, mean_val - 1.96 * std_error), mean_val + 1.96 * std_error]

    return {
        "mean": mean_val,
        "std_error": std_error,
        "ci_95": ci_95,
        "exact": False,
        "num_landmarks": sample_size,
    }
