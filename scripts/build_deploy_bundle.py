from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import geopandas as gpd
import pandas as pd

from river_networks.config import load_rivers
from river_networks.storage.paths import RiverPaths

REQUIRED_REACH_COLUMNS = [
    "HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "HYBAS_ID", "LENGTH_KM", "DIST_DN_KM",
    "DIST_UP_KM", "CATCH_SKM", "UPLAND_SKM", "DIS_AV_CMS", "ENDORHEIC", "ORD_STRA",
    "ORD_CLAS", "ORD_FLOW", "geometry",
]

INT_COLUMNS = ["ENDORHEIC", "ORD_STRA", "ORD_CLAS", "ORD_FLOW"]
FLOAT_COLUMNS = ["LENGTH_KM", "DIST_DN_KM", "DIST_UP_KM", "CATCH_SKM", "UPLAND_SKM", "DIS_AV_CMS"]

def human(num_bytes: float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def shrink_reaches(src: Path, dest: Path, simplify: float | None, keep_all: bool, downcast: bool) -> int:
    frame = gpd.read_parquet(src)

    if not keep_all:
        present = [c for c in REQUIRED_REACH_COLUMNS if c in frame.columns]
        missing = set(REQUIRED_REACH_COLUMNS) - set(present)
        if missing:
            raise SystemExit(
                f"{src} is missing columns the dashboard requires: {', '.join(sorted(missing))}.\n"
                "Re-run the extraction for this river before bundling."
            )
        frame = frame[present]

    if downcast:
        for col in INT_COLUMNS:
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0).astype("int16")
        for col in FLOAT_COLUMNS:
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float32")

    if simplify:

        frame["geometry"] = frame.geometry.simplify(simplify, preserve_topology=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(dest, compression="zstd", index=False)
    return dest.stat().st_size

def graphml_to_nodes_parquet(src: Path, dest: Path) -> int:
    import igraph as ig

    graph = ig.Graph.Read_GraphML(str(src))
    attrs = graph.vs.attributes()
    rows = []
    for v in graph.vs:
        node_id = v["node_id"] if "node_id" in attrs else v.index
        reach_id = str(node_id).split(":", 1)[-1] if ":" in str(node_id) else str(node_id)
        rows.append({
            "node_id": node_id,
            "reach_id": reach_id,
            "node_type": v["node_type"] if "node_type" in attrs else "unknown",
            "in_degree": v["in_degree"] if "in_degree" in attrs else graph.degree(v.index, mode="in"),
            "out_degree": v["out_degree"] if "out_degree" in attrs else graph.degree(v.index, mode="out"),
            "degree": v["degree"] if "degree" in attrs else graph.degree(v.index),
            "x": v["x"] if "x" in attrs else None,
            "y": v["y"] if "y" in attrs else None,
        })
    nodes = pd.DataFrame(rows)
    for col in ("in_degree", "out_degree", "degree"):
        nodes[col] = pd.to_numeric(nodes[col], errors="coerce").fillna(0).astype("int16")
    for col in ("x", "y"):
        nodes[col] = pd.to_numeric(nodes[col], errors="coerce").astype("float32")
    nodes["node_type"] = nodes["node_type"].astype("category")

    dest.parent.mkdir(parents=True, exist_ok=True)
    nodes.to_parquet(dest, compression="zstd", index=False)
    return dest.stat().st_size

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="deploy_bundle", help="Output folder name (default: deploy_bundle)")
    parser.add_argument("--simplify", type=float, default=None,
                        help="Simplify geometries by this tolerance in degrees (e.g. 0.001 ~ 100m). Off by default.")
    parser.add_argument("--keep-all-columns", action="store_true", help="Do not prune to the dashboard's required columns")
    parser.add_argument("--no-downcast", action="store_true", help="Do not downcast numeric dtypes")
    parser.add_argument("--no-graphs", action="store_true", help="Skip the graph node tables entirely")
    parser.add_argument("--max-mb", type=float, default=None,
                        help="Warn loudly if the final zip exceeds this many MB")
    parser.add_argument("--no-zip", action="store_true", help="Leave the folder, do not zip it")
    args = parser.parse_args()

    out_root = (PROJECT_ROOT / args.output).resolve()
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    rivers = load_rivers()
    rows: list[tuple[str, str, str]] = []
    total = 0

    for river_id, river in sorted(rivers.items()):
        paths = RiverPaths.for_river(river_id)
        extracted = paths.processed / "extracted_network.parquet"
        if not extracted.is_file():
            rows.append((river["display_name"], "-", "not extracted -- skipped"))
            continue

        dest_root = out_root / Path(river["output_location"])
        before = extracted.stat().st_size
        size = shrink_reaches(
            extracted,
            dest_root / "processed" / "extracted_network.parquet",
            args.simplify,
            args.keep_all_columns,
            not args.no_downcast,
        )
        note = f"reaches {human(before)} -> {human(size)}"

        if paths.metadata.is_dir():
            dest_meta = dest_root / "metadata"
            dest_meta.mkdir(parents=True, exist_ok=True)
            for f in paths.metadata.glob("*.json"):
                shutil.copy2(f, dest_meta / f.name)
                size += f.stat().st_size

        graph_dir = paths.graphs / "river_graph"
        if not args.no_graphs and graph_dir.is_dir():
            dest_graph = dest_root / "graphs" / "river_graph"
            dest_graph.mkdir(parents=True, exist_ok=True)
            meta_src = graph_dir / "metadata.json"
            if meta_src.is_file():
                shutil.copy2(meta_src, dest_graph / "metadata.json")
                size += meta_src.stat().st_size
            metrics_src = graph_dir / "network_metrics.json"
            if metrics_src.is_file():
                shutil.copy2(metrics_src, dest_graph / "network_metrics.json")
                size += metrics_src.stat().st_size
            directed = graph_dir / "directed.graphml"
            nodes = graph_dir / "nodes.parquet"
            if nodes.is_file():
                shutil.copy2(nodes, dest_graph / nodes.name)
                size += nodes.stat().st_size
                note += f" | carried over node table ({human(nodes.stat().st_size)})"
            elif directed.is_file():
                gm_before = directed.stat().st_size
                nsize = graphml_to_nodes_parquet(directed, dest_graph / "nodes.parquet")
                size += nsize
                note += f" | graph {human(gm_before)} -> {human(nsize)}"

        total += size
        rows.append((river["display_name"], human(size), note))

    print(f"Bundle root: {out_root}\n")
    for name, size, note in rows:
        print(f"  {name:<12} {size:>10}   {note}")
    print(f"\nUncompressed total: {human(total)}")

    manifest = {
        "rivers": [r[0] for r in rows if r[1] != "-"],
        "simplify_tolerance_degrees": args.simplify,
        "columns_pruned": not args.keep_all_columns,
        "graphs_as_node_parquet": not args.no_graphs,
    }
    (out_root / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.no_zip:
        zip_path = Path(shutil.make_archive(str(out_root), "zip", root_dir=out_root))
        zsize = zip_path.stat().st_size
        print(f"Zipped: {zip_path} ({human(zsize)})")
        if args.max_mb and zsize > args.max_mb * 1024 * 1024:
            print(f"\n!! Over your --max-mb budget of {args.max_mb} MB.")
            print("   Try: --simplify 0.002, or drop a river from config/rivers.yaml for the deployed build.")
        elif zsize > 2 * 1024 ** 3:
            print("\n!! Over 2 GB -- too large for a single GitHub Release asset. Simplify or split.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
