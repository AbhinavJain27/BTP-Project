from pathlib import Path
from typing import Any
import yaml

PACKAGE_ROOT=Path(__file__).resolve().parent
PROJECT_ROOT=PACKAGE_ROOT.parents[1]
CONFIG_ROOT=PROJECT_ROOT/"config"

def _load_yaml(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as file:
        return yaml.safe_load(file) or {}

def load_rivers(path:Path|None=None)->dict[str,Any]:
    return _load_yaml(path or CONFIG_ROOT/"rivers.yaml").get("rivers",{})

def load_paths(path:Path|None=None)->dict[str,Any]:
    return _load_yaml(path or CONFIG_ROOT/"paths.yaml").get("paths",{})

def get_river(river_id:str)->dict[str,Any]:
    rivers=load_rivers()
    key=river_id.strip().lower()
    if key not in rivers:
        available=", ".join(sorted(rivers))
        raise KeyError(f"Unknown river '{river_id}'. Available rivers: {available}")
    return rivers[key]

_SELECTION_KEYS = {
    "main_riv": "main_riv_ids",
    "hyriv_ids": "hyriv_ids",
    "hybas_ids": "hybas_ids",
}

def validate_river_config(river_id: str, river: dict[str, Any] | None = None, require_identifiers: bool = False) -> None:
    river = river or get_river(river_id)
    selection = river.get("selection") or {}
    method = selection.get("method")
    if method not in _SELECTION_KEYS:
        raise ValueError(
            f"River '{river_id}' has invalid selection.method={method!r}. "
            f"Expected one of: {', '.join(_SELECTION_KEYS)}."
        )
    expected_key = _SELECTION_KEYS[method]
    active = [key for key in _SELECTION_KEYS.values() if selection.get(key)]
    if active and active != [expected_key]:
        raise ValueError(
            f"River '{river_id}' has selection.method={method!r}, but populated "
            f"selection identifiers are {active}. Populate only {expected_key!r}."
        )
    if require_identifiers and not active:
        raise ValueError(
            f"River '{river_id}' has selection.method={method!r} but no verified identifiers. "
            f"Populate {expected_key!r} from the regional HydroRIVERS source."
        )
    output_location = river.get("output_location")
    expected_location = f"{river['region']}/{river['artifact_id']}"
    if output_location != expected_location:
        raise ValueError(
            f"River '{river_id}' has output_location={output_location!r}; "
            f"expected {expected_location!r} from region/artifact_id."
        )

def resolve_config(river_id:str)->dict[str,Any]:
    river=get_river(river_id)
    paths=load_paths()
    root=PROJECT_ROOT/paths["datasets_root"]
    region_root=PROJECT_ROOT/paths[f"{river['region']}_root"]
    output=region_root/river["artifact_id"]
    source_id=river["source"]["regional_source"]
    regional_sources=paths.get("regional_sources") or {}
    if source_id not in regional_sources:
        raise ValueError(f"River '{river_id}' references unknown regional source '{source_id}'. Add it to paths.yaml.")
    source=regional_sources[source_id]
    raw_root=PROJECT_ROOT/source["raw_root"]
    processed_root=PROJECT_ROOT/source["processed_root"]
    source_path=raw_root/source["directory"]
    regional_processed=processed_root/source["processed_file"]
    return {"river":river,"source":source,"paths":{**paths,"datasets_root":str(root),"river_root":str(output),"raw":str(raw_root),"regional_source":str(source_path),"regional_processed":str(regional_processed),"regional_source_id":source_id,"processed":str(output/paths["processed_root"]),"graphs":str(output/paths["graph_root"]),"analysis":str(output/paths["analysis_root"]),"exports":str(output/paths["export_root"]),"metadata":str(output/paths["metadata_root"])}}
