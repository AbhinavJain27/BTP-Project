import pandas as pd
import pytest

from river_networks.analysis.fragmentation import (
    compute_connectivity_status_index,
    simulate_perturbation_curves,
)
from river_networks.graph.builder import build_river_graph


def test_cuts_disconnect_upstream_reaches_from_original_outlets():
    reaches = pd.DataFrame({
        "HYRIV_ID": [1, 2, 3, 4],
        "NEXT_DOWN": [3, 3, 0, 0],
        "LENGTH_KM": [2, 3, 5, 10],
    })
    graph, _ = build_river_graph(reaches)
    assert compute_connectivity_status_index(graph, reaches) == 100
    assert compute_connectivity_status_index(graph, reaches, {3}) == 50
    assert compute_connectivity_status_index(graph, reaches, {1}) == 90
    simulation = simulate_perturbation_curves(graph, reaches, [0, 0.25, 1])
    assert simulation["csi_targeted_pct"] == [100, 50, 0]
    assert simulation["critical_reach_ids_top5"][0] == 3
    assert simulation["csi_random_pct"][1] == pytest.approx(75, abs=25)
    assert simulation["random_trials"] == 8
