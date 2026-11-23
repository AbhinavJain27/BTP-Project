"""Deterministic, zero-hallucination structured metrics extraction tools for the River Networks RAG layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_river, load_rivers
from ..storage.paths import RiverPaths

def _load_river_metrics_payload(river_id: str) -> tuple[dict[str, Any] | None, str | None]:
    paths = RiverPaths.for_river(river_id)
    metrics_path = paths.graphs / "river_graph" / "network_metrics.json"
    if not metrics_path.is_file():
        return None, f"network_metrics.json not found for {river_id}"
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("metrics", data), dict):
            return None, f"Invalid metrics object in {metrics_path}"
        return data, str(metrics_path)
    except Exception as exc:
        return None, f"Error reading {metrics_path}: {exc}"

def list_available_rivers() -> list[dict[str, str]]:
    """Returns list of configured river basins in the repository with region and display name."""
    rivers = load_rivers()
    return [
        {"river_id": rid, "display_name": info["display_name"], "region": info["region"]}
        for rid, info in sorted(rivers.items())
    ]

def get_topological_metrics(river_id: str) -> dict[str, Any]:
    """Retrieves exact node/edge counts, density, self-loops, diameters, and degree distributions."""
    rid = river_id.lower().strip()
    payload, src = _load_river_metrics_payload(rid)
    if not payload:
        return {"error": src, "river_id": rid}

    m = payload.get("metrics", payload)
    return {
        "river_id": rid,
        "river_name": payload.get("river_name", get_river(rid)["display_name"]),
        "provenance_source": src,
        "computed_at": payload.get("computed_at"),
        "node_count": m.get("node_count"),
        "edge_count": m.get("edge_count"),
        "density": m.get("density"),
        "self_loops": m.get("self_loops"),
        "directed_diameter_hops": m.get("diameter", {}).get("directed"),
        "undirected_diameter_hops": m.get("diameter", {}).get("undirected"),
        "directed_avg_path_hops": m.get("average_path_length", {}).get("directed"),
        "undirected_avg_path_hops": m.get("average_path_length", {}).get("undirected"),
        "clustering_coefficient": m.get("clustering_coefficient", {}).get("global_transitivity"),
        "max_in_degree": m.get("in_degree", {}).get("max"),
        "mean_in_degree": m.get("in_degree", {}).get("mean"),
        "max_betweenness": m.get("centrality_measures", {}).get("betweenness_centrality", {}).get("max"),
        "max_betweenness_node": m.get("centrality_measures", {}).get("betweenness_centrality", {}).get("max_node"),
        "betweenness_method": m.get("centrality_measures", {}).get("betweenness_centrality", {}).get("method"),
    }

def get_scaling_metrics(river_id: str) -> dict[str, Any]:
    """Retrieves exact Horton bifurcation (RB), length (RL), area (RA) ratios and Hack's law parameters."""
    rid = river_id.lower().strip()
    payload, src = _load_river_metrics_payload(rid)
    if not payload:
        return {"error": src, "river_id": rid}

    m = payload.get("metrics", payload)
    scaling = m.get("scaling", {})
    horton = scaling.get("horton", {})
    hack = scaling.get("hack", {})
    tokunaga = scaling.get("tokunaga", {})

    return {
        "river_id": rid,
        "river_name": payload.get("river_name", get_river(rid)["display_name"]),
        "provenance_source": src,
        "horton_bifurcation_ratio_RB": horton.get("bifurcation_ratio"),
        "horton_r2_bifurcation": horton.get("r2_bifurcation"),
        "horton_length_ratio_RL": horton.get("length_ratio"),
        "horton_area_ratio_RA": horton.get("area_ratio"),
        "hack_law_exponent_h": hack.get("hack_exponent"),
        "hack_law_r2": hack.get("r2"),
        "tokunaga_first_order_ratio_T1": tokunaga.get("mean_first_order_branching_T1"),
    }

def get_perturbation_metrics(river_id: str) -> dict[str, Any]:
    """Retrieves Connectivity Status Index (CSI) degradation curves under simulated reach disruptions."""
    rid = river_id.lower().strip()
    payload, src = _load_river_metrics_payload(rid)
    if not payload:
        return {"error": src, "river_id": rid}

    m = payload.get("metrics", payload)
    perturbation = m.get("perturbation", {})
    return {
        "river_id": rid,
        "river_name": payload.get("river_name", get_river(rid)["display_name"]),
        "provenance_source": src,
        "removed_fractions_pct": perturbation.get("removed_fraction_pct"),
        "csi_targeted_pct": perturbation.get("csi_targeted_pct"),
        "csi_random_pct": perturbation.get("csi_random_pct"),
        "critical_choke_point_reaches": perturbation.get("critical_reach_ids_top5", []),
    }

def compare_basins(river_ids: list[str]) -> list[dict[str, Any]]:
    """Generates side-by-side benchmark comparison for multiple river basins."""
    results = []
    for rid in river_ids:
        metrics = get_topological_metrics(rid)
        scaling = get_scaling_metrics(rid)
        if "error" not in metrics:
            results.append({
                "river": metrics["river_name"],
                "reaches": metrics["edge_count"],
                "directed_diameter": metrics["directed_diameter_hops"],
                "undirected_diameter": metrics["undirected_diameter_hops"],
                "avg_path_length": metrics["directed_avg_path_hops"],
                "horton_RB": scaling.get("horton_bifurcation_ratio_RB"),
                "hack_exponent": scaling.get("hack_law_exponent_h"),
            })
    return results
