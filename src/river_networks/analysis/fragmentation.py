"""Measure the share of reach length connected to the original basin outlets."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _forest_inputs(graph, frame: pd.DataFrame):
    if not graph.is_dag() or max(graph.outdegree(), default=0) > 1:
        raise ValueError("Fragmentation requires an acyclic, converging drainage network")
    ids = np.asarray(graph.es["HYRIV_ID"], dtype=np.int64)
    lengths = frame.set_index("HYRIV_ID")["LENGTH_KM"].reindex(ids).to_numpy(dtype=float)
    if not np.isfinite(lengths).all() or (lengths < 0).any() or lengths.sum() <= 0:
        raise ValueError("Fragmentation requires valid reach lengths and a positive total length")

    edges = np.asarray(graph.get_edgelist(), dtype=np.int64)
    source, target = edges.T
    outgoing = np.full(graph.vcount(), -1, dtype=np.int64)
    outgoing[source] = np.arange(len(ids))
    topo = graph.topological_sorting(mode="out")
    depth = np.zeros(graph.vcount(), dtype=np.int64)
    for vertex in reversed(topo):
        edge = outgoing[vertex]
        if edge >= 0:
            depth[vertex] = depth[target[edge]] + 1
    sorted_edges = np.argsort(depth[source], kind="stable")
    breaks = np.flatnonzero(np.diff(depth[source[sorted_edges]])) + 1
    levels = np.split(sorted_edges, breaks)
    return ids, lengths, source, target, topo, outgoing, depth, levels


def _connected_percentage(lengths, source, target, levels, removed, vertex_count):
    connected = np.ones(vertex_count, dtype=bool)
    for edges in levels:
        connected[source[edges]] = connected[target[edges]] & ~removed[edges]
    return float(100 * lengths[connected[source]].sum() / lengths.sum())


def compute_connectivity_status_index(
    graph, reach_frame: pd.DataFrame, removed_edges: set[int] | None = None
) -> float:
    """Return the percentage of total reach length connected to original outlets."""
    ids, lengths, source, target, _, _, _, levels = _forest_inputs(graph, reach_frame)
    removed = np.isin(ids, list(removed_edges or ()))
    return _connected_percentage(lengths, source, target, levels, removed, graph.vcount())


def simulate_perturbation_curves(
    graph, reach_frame: pd.DataFrame, fractions: list[float] | None = None
) -> dict[str, Any]:
    """Compare exact edge-betweenness targeting with repeated seeded random cuts."""
    if graph.ecount() == 0:
        return {}
    fractions = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10] if fractions is None else fractions
    if not fractions or any(not 0 <= fraction <= 1 for fraction in fractions):
        raise ValueError("Removal fractions must be a nonempty list between zero and one")
    handles = _forest_inputs(graph, reach_frame)
    ids, lengths, source, target, topo, outgoing, depth, levels = handles
    subtree = np.ones(graph.vcount(), dtype=np.int64)
    for vertex in topo:
        edge = outgoing[vertex]
        if edge >= 0:
            subtree[target[edge]] += subtree[vertex]
    # Paths through an edge pair any upstream source with any downstream target.
    score = subtree[source] * depth[source]
    targeted = np.lexsort((ids, -score))
    cut_counts = [int(fraction * len(ids)) for fraction in fractions]

    def curve(order):
        values = []
        removed = np.zeros(len(ids), dtype=bool)
        for count in cut_counts:
            removed.fill(False)
            removed[order[:count]] = True
            values.append(_connected_percentage(lengths, source, target, levels, removed, graph.vcount()))
        return values

    rng = np.random.default_rng(42)
    trials = np.asarray([curve(rng.permutation(len(ids))) for _ in range(8)])
    return {
        "removed_fraction_pct": [round(f * 100, 2) for f in fractions],
        "removed_edge_counts": cut_counts,
        "csi_targeted_pct": [round(value, 2) for value in curve(targeted)],
        "csi_random_pct": trials.mean(axis=0).round(2).tolist(),
        "csi_random_std_pct": trials.std(axis=0).round(2).tolist(),
        "random_trials": len(trials),
        "random_seed": 42,
        "targeted_method": "exact_directed_forest_edge_betweenness",
        "critical_reach_ids_top5": ids[targeted[:5]].tolist(),
    }
