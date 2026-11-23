"""Analysis package for River Networks: scaling laws, exact tree algorithms, and perturbation."""

from .fragmentation import compute_connectivity_status_index, simulate_perturbation_curves
from .scaling import (
    compute_all_scaling_metrics,
    compute_hack_law,
    compute_horton_ratios,
    compute_tokunaga_statistics,
)
from .tree_algorithms import (
    compute_exact_directed_avg_path,
    compute_exact_tree_betweenness,
    compute_landmark_undirected_path,
)

__all__ = [
    "compute_exact_tree_betweenness",
    "compute_exact_directed_avg_path",
    "compute_landmark_undirected_path",
    "compute_horton_ratios",
    "compute_hack_law",
    "compute_tokunaga_statistics",
    "compute_all_scaling_metrics",
    "compute_connectivity_status_index",
    "simulate_perturbation_curves",
]
