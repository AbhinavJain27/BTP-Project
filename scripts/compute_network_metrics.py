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
import pandas as pd
from pyarrow.parquet import read_schema
from river_networks.graph.builder import build_river_graph
from river_networks.config import load_rivers, get_river
from river_networks.graph.metrics import compute_network_metrics
from river_networks.storage.paths import RiverPaths

def compute_and_save_river_metrics(river_id: str, force: bool = False) -> dict | None:
    river = get_river(river_id)
    paths = RiverPaths.for_river(river_id)
    graph_dir = paths.graphs / "river_graph"
    graph_path = graph_dir / "directed.graphml"
    metrics_path = graph_dir / "network_metrics.json"

    if not force and metrics_path.is_file():
        print(f"[{river['display_name']}] Already computed: {metrics_path}", flush=True)
        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    print(f"[{river['display_name']}] Loading river graph...", flush=True)
    t0 = time.time()
    extracted_parquet = paths.processed / "extracted_network.parquet"
    reaches = None
    if extracted_parquet.is_file():
        available = set(read_schema(extracted_parquet).names)
        analysis_columns = ["ORD_STRA", "LENGTH_KM", "UPLAND_SKM", "DIST_UP_KM"]
        columns = ["HYRIV_ID", "NEXT_DOWN"] + [name for name in analysis_columns if name in available]
        reaches = pd.read_parquet(extracted_parquet, columns=columns)
        g, undirected = build_river_graph(reaches[["HYRIV_ID", "NEXT_DOWN"]])
        del undirected
    elif graph_path.is_file():
        g = ig.Graph.Read_GraphML(str(graph_path))
    else:
        print(f"[{river['display_name']}] No extracted Parquet or directed GraphML.")
        return None

    read_time = time.time() - t0
    print(f"  Loaded graph ({g.vcount():,} nodes, {g.ecount():,} edges) in {read_time:.2f}s", flush=True)

    print(f"[{river['display_name']}] Computing network metrics...", flush=True)
    t1 = time.time()
    metrics = compute_network_metrics(g, reaches=reaches)
    compute_time = time.time() - t1
    print(f"  Calculated metrics in {compute_time:.2f}s", flush=True)

    metrics_payload = {
        "river_id": river_id,
        "river_name": river["display_name"],
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": metrics,
    }

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = metrics_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(metrics_payload, indent=2, allow_nan=False), encoding="utf-8")
    temporary_path.replace(metrics_path)
    print(f"  Saved -> {metrics_path}", flush=True)
    return metrics_payload

def main() -> int:
    parser = argparse.ArgumentParser(description="Compute network science metrics for configured river networks.")
    parser.add_argument("--river", choices=sorted(load_rivers()), help="Compute for one specific river")
    parser.add_argument("--force", action="store_true", help="Recompute even if network_metrics.json exists")
    args = parser.parse_args()

    rivers = [args.river] if args.river else sorted(load_rivers())
    print(f"Computing network metrics for {len(rivers)} river(s): {', '.join(rivers)}\n")

    missing = [river_id for river_id in rivers if compute_and_save_river_metrics(river_id, force=args.force) is None]
    if missing:
        print("Metrics unavailable for: " + ", ".join(missing))
        return 1

    print("\nAll network metrics computed successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
