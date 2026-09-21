import hashlib
import json
from pathlib import Path
from typing import Any

from ..acquisition import acquire_hydrorivers
from ..config import get_river, validate_river_config
from ..graph.builder import build_river_graph, validate_graph
from ..preprocessing import extract_configured_river, preprocess_hydrorivers
from ..storage.graph import load_graph_artifact, save_graph_artifact
from ..storage.metadata import write_metadata
from ..storage.paths import RiverPaths

def _file_signature(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"path": str(path), "exists": False}
    if path.is_dir():
        members = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                stat = child.stat()
                members.append((str(child.relative_to(path)), stat.st_mtime_ns, stat.st_size))
        return {"path": str(path), "exists": True, "type": "directory", "members": members}
    stat = path.stat()
    return {"path": str(path), "exists": True, "type": "file", "mtime_ns": stat.st_mtime_ns, "size": stat.st_size}

def _cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _selection_signature(river: dict[str, Any]) -> dict[str, Any]:
    selection = river.get("selection") or {}
    return {
        "method": selection.get("method"),
        "main_riv_ids": list(selection.get("main_riv_ids") or []),
        "hyriv_ids": list(selection.get("hyriv_ids") or []),
        "hybas_ids": list(selection.get("hybas_ids") or []),
    }

def _metadata_matches(path: Path, cache_key: str) -> bool:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False
    return metadata.get("cache_key") == cache_key

def run_pipeline(river_id: str, force: bool = False) -> dict[str, Any]:
    river = get_river(river_id)

    paths = RiverPaths.for_river(river_id)
    results = {"river_id": river_id, "river_name": river["display_name"], "stages": []}

    acquisition = acquire_hydrorivers(river_id)
    write_metadata(paths.metadata / "acquisition.json", acquisition)
    results["stages"].append({"stage": "acquisition", "status": "passed" if acquisition["valid"] else "failed", "details": acquisition})
    if not acquisition["valid"]:
        raise RuntimeError(
            f"{acquisition['message']}. River: {river_id}. Regional source: {acquisition['regional_source']}. "
            f"Expected path: {acquisition['source_path']}. Download URL: {acquisition['download_url']}. "
            f"Next action: {acquisition['next_action']}"
        )

    source_signature = _file_signature(Path(acquisition["source_path"]))
    preprocessing_key = _cache_key({
        "stage": "preprocessing",
        "source": source_signature,
        "source_format": acquisition["source_format"],
        "source_layer": acquisition["source_layer"],
    })
    processed_path = paths.regional_processed
    preprocessing_meta_path = paths.metadata / "preprocessing.json"
    if not force and processed_path.is_file() and _metadata_matches(preprocessing_meta_path, preprocessing_key):
        preprocessing = {"status": "reused", "output_path": str(processed_path), "cache_key": preprocessing_key}
    else:
        preprocessing = preprocess_hydrorivers(
            Path(acquisition["source_path"]), processed_path,
            acquisition["source_format"], acquisition["source_layer"]
        )
        preprocessing.update({"status": "created", "cache_key": preprocessing_key})
    write_metadata(preprocessing_meta_path, preprocessing)
    results["stages"].append({"stage": "preprocessing", "status": "passed", "details": preprocessing})

    try:
        validate_river_config(river_id, river, require_identifiers=True)
    except ValueError:

        raise

    extraction_key = _cache_key({
        "stage": "extraction",
        "processed": _file_signature(processed_path),
        "selection": _selection_signature(river),
    })
    extracted_path = paths.processed / "extracted_network.parquet"
    extraction_meta_path = paths.metadata / "extraction.json"
    if not force and extracted_path.is_file() and _metadata_matches(extraction_meta_path, extraction_key):
        extraction = {"status": "reused", "output_path": str(extracted_path), "cache_key": extraction_key}
    else:
        extraction = extract_configured_river(river_id)
        extraction.update({"status": "created", "cache_key": extraction_key})
    write_metadata(extraction_meta_path, extraction)
    results["stages"].append({"stage": "extraction", "status": "passed", "details": extraction})

    graph_directory = paths.graphs / "river_graph"
    graph_meta_path = graph_directory / "metadata.json"
    graph_key = _cache_key({
        "stage": "graph",
        "extracted": _file_signature(extracted_path),
        "selection": _selection_signature(river),
    })
    if (
        not force
        and (graph_directory / "directed.graphml").is_file()
        and (graph_directory / "undirected.graphml").is_file()
        and _metadata_matches(graph_meta_path, graph_key)
    ):
        directed, undirected, metadata = load_graph_artifact(graph_directory)
        validation = validate_graph(directed)
        if not validation["valid"]:
            raise RuntimeError(f"Existing graph validation failed: {validation['issues']}")
        graph_result = {"status": "reused", "summary": validation, "directory": str(graph_directory), "cache_key": graph_key}
    else:
        import geopandas as gpd
        reaches = gpd.read_parquet(extracted_path)
        directed, undirected = build_river_graph(reaches)
        validation = validate_graph(directed)
        if not validation["valid"]:
            raise RuntimeError(f"Graph validation failed: {validation['issues']}")
        graph_result = {
            "status": "created",
            "summary": validation,
            **save_graph_artifact(
                directed, undirected, graph_directory,
                {
                    "river_id": river_id,
                    "river_name": river["display_name"],
                    "source_dataset": river["source"]["dataset"],
                    "validation": validation,
                    "cache_key": graph_key,
                },
            ),
        }
    results["stages"].append({"stage": "graph", "status": "passed", "details": graph_result})
    validation_stage = graph_result.get("summary", {"status": "reused"})
    write_metadata(paths.metadata / "validation.json", validation_stage)
    results["stages"].append({"stage": "validation", "status": "passed", "details": validation_stage})
    return results
