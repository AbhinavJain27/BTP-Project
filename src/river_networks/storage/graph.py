import json
from pathlib import Path
from typing import Any

INTEGER_VERTEX_ATTRIBUTES = {"in_degree", "out_degree", "degree"}
INTEGER_EDGE_ATTRIBUTES = {
    "HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "HYBAS_ID", "ENDORHEIC",
    "ORD_STRA", "ORD_CLAS", "ORD_FLOW",
}
FLOAT_EDGE_ATTRIBUTES = {
    "LENGTH_KM", "DIST_DN_KM", "DIST_UP_KM", "CATCH_SKM",
    "UPLAND_SKM", "DIS_AV_CMS",
}

def _graphml_ready(graph):
    result = graph.copy()

    for sequence in (result.vs, result.es):
        for name in sequence.attributes():
            values = sequence[name]
            sequence[name] = ["" if value is None else value for value in values]
    return result

def _restore_numeric_attributes(graph):
    for name in graph.vs.attributes():
        if name in INTEGER_VERTEX_ATTRIBUTES:
            graph.vs[name] = [None if value in ("", None) else int(float(value)) for value in graph.vs[name]]
    for name in graph.es.attributes():
        if name in INTEGER_EDGE_ATTRIBUTES:
            graph.es[name] = [None if value in ("", None) else int(float(value)) for value in graph.es[name]]
        elif name in FLOAT_EDGE_ATTRIBUTES:
            graph.es[name] = [None if value in ("", None) else float(value) for value in graph.es[name]]
    return graph

def save_graph_artifact(directed, undirected, output_directory: Path, metadata: dict[str, Any]) -> dict[str, str]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    directed_path = output_directory / "directed.graphml"
    undirected_path = output_directory / "undirected.graphml"
    metadata_path = output_directory / "metadata.json"
    _graphml_ready(directed).write_graphml(str(directed_path))
    _graphml_ready(undirected).write_graphml(str(undirected_path))
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    # Native Phase 2 enhancement: emit compact columnar nodes.parquet
    import pandas as pd
    attrs = directed.vs.attributes()
    rows = []
    for v in directed.vs:
        node_id = v["node_id"] if "node_id" in attrs else v.index
        reach_id = str(node_id).split(":", 1)[-1] if ":" in str(node_id) else str(node_id)
        rows.append({
            "node_id": node_id,
            "reach_id": reach_id,
            "node_type": v["node_type"] if "node_type" in attrs else "unknown",
            "in_degree": v["in_degree"] if "in_degree" in attrs else directed.degree(v.index, mode="in"),
            "out_degree": v["out_degree"] if "out_degree" in attrs else directed.degree(v.index, mode="out"),
            "degree": v["degree"] if "degree" in attrs else directed.degree(v.index),
            "x": v["x"] if "x" in attrs else None,
            "y": v["y"] if "y" in attrs else None,
        })
    nodes_df = pd.DataFrame(rows)
    for col in ("in_degree", "out_degree", "degree"):
        nodes_df[col] = pd.to_numeric(nodes_df[col], errors="coerce").fillna(0).astype("int16")
    for col in ("x", "y"):
        nodes_df[col] = pd.to_numeric(nodes_df[col], errors="coerce").astype("float32")
    nodes_df["node_type"] = nodes_df["node_type"].astype("category")
    nodes_path = output_directory / "nodes.parquet"
    nodes_df.to_parquet(nodes_path, compression="zstd", index=False)

    return {
        "directory": str(output_directory),
        "directed": str(directed_path),
        "undirected": str(undirected_path),
        "metadata": str(metadata_path),
        "nodes": str(nodes_path),
    }

def load_graph_artifact(directory: Path):
    try:
        import igraph as ig
    except ImportError as exc:
        raise RuntimeError("igraph is required to load graph artifacts. Install project dependencies before loading a graph.") from exc
    directory = Path(directory)
    directed = _restore_numeric_attributes(ig.Graph.Read_GraphML(str(directory / "directed.graphml")))
    undirected = _restore_numeric_attributes(ig.Graph.Read_GraphML(str(directory / "undirected.graphml")))
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    return directed, undirected, metadata
