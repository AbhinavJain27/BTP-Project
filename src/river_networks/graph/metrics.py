from __future__ import annotations

from typing import Any
import numpy as np

def _compute_histogram(data: np.ndarray, num_bins: int = 30, log_scale: bool = False) -> dict[str, list[float]]:
    data = data[np.isfinite(data)]
    if len(data) == 0:
        return {"counts": [], "bin_edges": []}

    if log_scale and np.any(data > 0):
        pos = data[data > 0]
        min_val = float(pos.min())
        max_val = float(pos.max())
        if min_val == max_val:
            edges = np.array([min_val * 0.9, min_val * 1.1])
        else:
            edges = np.logspace(np.log10(min_val), np.log10(max_val), num_bins + 1)
        counts, edges = np.histogram(pos, bins=edges)
    else:
        counts, edges = np.histogram(data, bins=num_bins)

    return {
        "counts": [int(c) for c in counts],
        "bin_edges": [float(e) for e in edges],
    }

def _2sweep_undirected_diameter(graph_undir) -> int:
    if graph_undir.vcount() <= 1:
        return 0

    d1 = graph_undir.distances(source=0)[0]
    finite_indices = [i for i, d in enumerate(d1) if d < float("inf")]
    if not finite_indices:
        return 0
    farthest_u = max(finite_indices, key=lambda i: d1[i])

    d2 = graph_undir.distances(source=farthest_u)[0]
    finite_d2 = [d for d in d2 if d < float("inf")]
    return int(max(finite_d2)) if finite_d2 else 0

def _hops_to_outlet(graph) -> np.ndarray:

    attrs = graph.vs.attributes()
    if "node_type" in attrs:
        outlets = [v.index for v in graph.vs if v["node_type"] == "downstream/outlet" or graph.outdegree(v.index) == 0]
    else:
        outlets = [v.index for v in graph.vs if graph.outdegree(v.index) == 0]

    if not outlets:

        out_deg = graph.outdegree()
        outlets = [int(np.argmin(out_deg))]

    dists = graph.distances(source=outlets, mode="in")
    dists_arr = np.array(dists, dtype=float)
    min_dists = np.min(dists_arr, axis=0)

    min_dists[~np.isfinite(min_dists)] = 0.0
    return min_dists

def compute_network_metrics(graph, reaches=None, sample_limit: int = 200000) -> dict[str, Any]:
    vcount = int(graph.vcount())
    ecount = int(graph.ecount())
    if vcount == 0:
        return {"node_count": 0, "edge_count": 0}

    in_deg = np.array(graph.indegree(), dtype=int)
    out_deg = np.array(graph.outdegree(), dtype=int)
    tot_deg = in_deg + out_deg

    in_deg_counts = {int(k): int(v) for k, v in zip(*np.unique(in_deg, return_counts=True))}
    out_deg_counts = {int(k): int(v) for k, v in zip(*np.unique(out_deg, return_counts=True))}
    tot_deg_counts = {int(k): int(v) for k, v in zip(*np.unique(tot_deg, return_counts=True))}

    weak_components = graph.components(mode="weak")
    weak_count = int(len(weak_components))
    weak_sizes = [len(c) for c in weak_components]
    weak_largest = int(max(weak_sizes)) if weak_sizes else 0
    weak_largest_pct = float((weak_largest / vcount) * 100) if vcount else 0.0

    strong_components = graph.components(mode="strong")
    strong_count = int(len(strong_components))
    is_dag = bool(graph.is_dag())

    density = float(graph.density())
    self_loops = int(sum(graph.is_loop()))

    transitivity = float(graph.transitivity_undirected())
    if np.isnan(transitivity):
        transitivity = 0.0

    hops_outlet = _hops_to_outlet(graph)
    directed_diameter = int(hops_outlet.max())

    g_undir = graph.as_undirected(combine_edges="first")
    undirected_diameter = _2sweep_undirected_diameter(g_undir)

    if is_dag:
        from ..analysis.tree_algorithms import compute_exact_directed_avg_path, compute_landmark_undirected_path
        directed_avg_path = compute_exact_directed_avg_path(graph)
        undir_info = compute_landmark_undirected_path(g_undir, num_landmarks=50)
        undirected_avg_path = undir_info["mean"]
        undirected_path_meta = undir_info
    else:
        if vcount <= sample_limit:
            try:
                directed_avg_path = float(graph.average_path_length(directed=True))
            except Exception:
                directed_avg_path = float(np.mean(hops_outlet[hops_outlet > 0])) if np.any(hops_outlet > 0) else 0.0
        else:
            directed_avg_path = float(np.mean(hops_outlet[hops_outlet > 0])) if np.any(hops_outlet > 0) else 0.0

        if vcount <= 5000:
            try:
                undirected_avg_path = float(g_undir.average_path_length(directed=False))
            except Exception:
                undirected_avg_path = float(directed_avg_path * 1.5)
        else:
            sample_size = min(50, vcount)
            rng = np.random.default_rng(42)
            sample_nodes = rng.choice(vcount, size=sample_size, replace=False).tolist()
            total_d = 0.0
            total_cnt = 0
            for s in sample_nodes:
                row = g_undir.distances(source=int(s))[0]
                finite = [d for d in row if 0 < d < float("inf")]
                if finite:
                    total_d += sum(finite)
                    total_cnt += len(finite)
            undirected_avg_path = float(total_d / total_cnt) if total_cnt > 0 else float(directed_avg_path)
        undirected_path_meta = {"exact": False, "mean": undirected_avg_path}

    node_ids = graph.vs["node_id"] if "node_id" in graph.vs.attributes() else [str(i) for i in range(vcount)]

    deg_norm = tot_deg / (vcount - 1) if vcount > 1 else tot_deg.astype(float)
    max_deg_idx = int(np.argmax(tot_deg))
    degree_centrality = {
        "max": float(deg_norm.max()),
        "mean": float(deg_norm.mean()),
        "max_node": node_ids[max_deg_idx],
        "max_degree": int(tot_deg.max()),
    }

    try:
        pr_arr = np.array(graph.pagerank(directed=True), dtype=float)
    except Exception:
        pr_arr = np.ones(vcount, dtype=float) / vcount
    max_pr_idx = int(np.argmax(pr_arr))
    pagerank_centrality = {
        "min": float(pr_arr.min()),
        "max": float(pr_arr.max()),
        "mean": float(pr_arr.mean()),
        "median": float(np.median(pr_arr)),
        "max_node": node_ids[max_pr_idx],
        "histogram": _compute_histogram(pr_arr, num_bins=30, log_scale=True),
    }

    if is_dag:
        from ..analysis.tree_algorithms import compute_exact_tree_betweenness
        bw_arr = compute_exact_tree_betweenness(graph)
        bw_method = "exact_tree_dp"
        bw_exact = True
    elif vcount <= sample_limit:
        try:
            bw_arr = np.array(graph.betweenness(directed=True), dtype=float)
            bw_method = "igraph_exact"
            bw_exact = True
        except Exception:
            bw_arr = np.zeros(vcount, dtype=float)
            bw_method = "zeros"
            bw_exact = False
    else:
        bw_arr = (vcount - hops_outlet) * hops_outlet
        bw_method = "heuristic_proxy"
        bw_exact = False

    max_bw_idx = int(np.argmax(bw_arr))
    betweenness_centrality = {
        "min": float(bw_arr.min()),
        "max": float(bw_arr.max()),
        "mean": float(bw_arr.mean()),
        "median": float(np.median(bw_arr)),
        "max_node": node_ids[max_bw_idx],
        "histogram": _compute_histogram(bw_arr, num_bins=30, log_scale=True),
        "method": bw_method,
        "exact": bw_exact,
    }

    hops_hist = _compute_histogram(hops_outlet, num_bins=35, log_scale=False)

    scaling_metrics = {}
    perturbation_metrics = {}
    if reaches is not None and hasattr(reaches, "columns"):
        from ..analysis.scaling import compute_all_scaling_metrics
        from ..analysis.fragmentation import simulate_perturbation_curves
        scaling_metrics = compute_all_scaling_metrics(reaches)
        if "LENGTH_KM" in reaches.columns:
            perturbation_metrics = simulate_perturbation_curves(graph, reaches)

    return {
        "node_count": vcount,
        "edge_count": ecount,
        "density": density,
        "self_loops": self_loops,
        "in_degree": {
            "min": int(in_deg.min()),
            "max": int(in_deg.max()),
            "mean": float(in_deg.mean()),
            "median": float(np.median(in_deg)),
            "counts": in_deg_counts,
        },
        "out_degree": {
            "min": int(out_deg.min()),
            "max": int(out_deg.max()),
            "mean": float(out_deg.mean()),
            "median": float(np.median(out_deg)),
            "counts": out_deg_counts,
        },
        "degree": {
            "min": int(tot_deg.min()),
            "max": int(tot_deg.max()),
            "mean": float(tot_deg.mean()),
            "median": float(np.median(tot_deg)),
            "counts": tot_deg_counts,
        },
        "connected_components": {
            "weak_count": weak_count,
            "weak_largest_size": weak_largest,
            "weak_largest_pct": weak_largest_pct,
            "strong_count": strong_count,
            "is_dag": is_dag,
        },
        "clustering_coefficient": {
            "global_transitivity": transitivity,
            "applicable": True,
            "note": "In dendritic river networks, flow follows an acyclic branching tree with no closed triangles, yielding a global clustering coefficient of 0.0.",
        },
        "diameter": {
            "directed": directed_diameter,
            "undirected": undirected_diameter,
        },
        "average_path_length": {
            "directed": directed_avg_path,
            "undirected": undirected_avg_path,
            "undirected_meta": undirected_path_meta,
        },
        "shortest_paths_to_outlet": {
            "min_hops": int(hops_outlet.min()),
            "max_hops": int(hops_outlet.max()),
            "mean_hops": float(hops_outlet.mean()),
            "median_hops": float(np.median(hops_outlet)),
            "histogram": hops_hist,
        },
        "centrality_measures": {
            "degree_centrality": degree_centrality,
            "betweenness_centrality": betweenness_centrality,
            "pagerank_centrality": pagerank_centrality,
        },
        "scaling": scaling_metrics,
        "perturbation": perturbation_metrics,
    }
