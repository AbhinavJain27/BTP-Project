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
    return {
        "directory": str(output_directory),
        "directed": str(directed_path),
        "undirected": str(undirected_path),
        "metadata": str(metadata_path),
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
