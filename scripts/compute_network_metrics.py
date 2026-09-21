from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import igraph as ig
from river_networks.config import load_rivers, get_river
from river_networks.graph.metrics import compute_network_metrics
from river_networks.storage.paths import RiverPaths

def compute_and_save_river_metrics(river_id: str, force: bool = False) -> dict | None:
    river = get_river(river_id)
    paths = RiverPaths.for_river(river_id)
    graph_dir = paths.graphs / "river_graph"
    graph_path = graph_dir / "directed.graphml"
    metrics_path = graph_dir / "network_metrics.json"

    if not graph_path.is_file():
        print(f"[{river['display_name']}] Skipped: directed.graphml not found at {graph_path}")
        return None

    if not force and metrics_path.is_file():
        print(f"[{river['display_name']}] Already computed: {metrics_path}", flush=True)
        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    print(f"[{river['display_name']}] Loading river graph...", flush=True)
    t0 = time.time()
    extracted_parquet = paths.processed / "extracted_network.parquet"
    if extracted_parquet.is_file():
        import pyarrow.parquet as pq
        table = pq.read_table(extracted_parquet, columns=["HYRIV_ID", "NEXT_DOWN"])
        hyriv = table["HYRIV_ID"].to_numpy()
        next_down = table["NEXT_DOWN"].to_numpy()
        sources = [f"junction:{h}" for h in hyriv]
        targets = [f"junction:{n}" if n != 0 else f"outlet:{h}" for h, n in zip(hyriv, next_down)]
        node_ids = sorted(set(sources) | set(targets))
        index = {node_id: i for i, node_id in enumerate(node_ids)}
        g = ig.Graph(n=len(node_ids), directed=True)
        g.vs["node_id"] = node_ids
        g.add_edges([(index[s], index[t]) for s, t in zip(sources, targets)])

        in_deg = g.indegree()
        node_types = []
        for i, nid in enumerate(node_ids):
            if nid.startswith("outlet:"):
                node_types.append("downstream/outlet")
            elif in_deg[i] == 0:
                node_types.append("headwater")
            elif in_deg[i] > 1:
                node_types.append("confluence/junction")
            else:
                node_types.append("intermediate/topology-preserving")
        g.vs["node_type"] = node_types
    else:
        g = ig.Graph.Read_GraphML(str(graph_path))

    read_time = time.time() - t0
    print(f"  Loaded graph ({g.vcount():,} nodes, {g.ecount():,} edges) in {read_time:.2f}s", flush=True)

    print(f"[{river['display_name']}] Computing network metrics...", flush=True)
    t1 = time.time()
    metrics = compute_network_metrics(g)
    compute_time = time.time() - t1
    print(f"  Calculated metrics in {compute_time:.2f}s", flush=True)

    metrics_payload = {
        "river_id": river_id,
        "river_name": river["display_name"],
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": metrics,
    }

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    print(f"  Saved -> {metrics_path}", flush=True)
    return metrics_payload

def main() -> int:
    parser = argparse.ArgumentParser(description="Compute network science metrics for configured river networks.")
    parser.add_argument("--river", choices=sorted(load_rivers()), help="Compute for one specific river")
    parser.add_argument("--force", action="store_true", help="Recompute even if network_metrics.json exists")
    args = parser.parse_args()

    rivers = [args.river] if args.river else sorted(load_rivers())
    print(f"Computing network metrics for {len(rivers)} river(s): {', '.join(rivers)}\n")

    for river_id in rivers:
        compute_and_save_river_metrics(river_id, force=args.force)

    print("\nAll network metrics computed successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
