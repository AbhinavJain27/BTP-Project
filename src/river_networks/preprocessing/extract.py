from pathlib import Path
from typing import Any

from ..config import get_river,validate_river_config
from ..storage.paths import RiverPaths
from .reader import read_hydrorivers,validate_hydrorivers_columns

def _configured_selection(river_id:str)->dict[str,Any]:
    river=get_river(river_id)
    validate_river_config(river_id, river, require_identifiers=True)
    selection=river.get("selection") or {}
    if not selection:
        raise ValueError(f"River '{river_id}' has no extraction selection configured. Add selection.main_riv_ids, selection.hyriv_ids, or selection.hybas_ids to rivers.yaml.")
    if not any(selection.get(key) for key in ("main_riv_ids","hyriv_ids","hybas_ids")):
        raise ValueError(f"River '{river_id}' has no verified extraction identifier configured. Populate exactly one of selection.main_riv_ids, selection.hyriv_ids, or selection.hybas_ids from the regional HydroRIVERS source.")
    return selection

def _match_selection(frame, selection):
    method_to_field = {
        "main_riv": ("MAIN_RIV", "main_riv_ids"),
        "hyriv_ids": ("HYRIV_ID", "hyriv_ids"),
        "hybas_ids": ("HYBAS_ID", "hybas_ids"),
    }
    method = selection.get("method")
    if method not in method_to_field:
        raise ValueError(
            f"Unsupported extraction selection.method={method!r}. "
            f"Expected one of: {', '.join(method_to_field)}."
        )
    field, key = method_to_field[method]
    values = selection.get(key) or []
    if not values:
        raise ValueError(
            f"Selection method '{method}' has no configured identifiers in '{key}'. "
            "Populate a verified identifier from the regional HydroRIVERS source."
        )
    normalized = {int(value) for value in values}
    mask = frame[field].isin(normalized)
    criteria = [f"{field} in {sorted(normalized)}"]
    return mask, criteria

def extract_river_network(source_path:Path,output_path:Path,river_id:str)->dict[str,Any]:
    selection=_configured_selection(river_id)
    frame=read_hydrorivers(source_path)
    missing=validate_hydrorivers_columns(frame.columns)
    if missing:
        raise ValueError(f"HydroRIVERS source is missing required columns: {', '.join(missing)}")
    mask,criteria=_match_selection(frame,selection)
    selected=frame.loc[mask].copy()
    if selected.empty:
        raise ValueError(f"Extraction for '{river_id}' produced zero reaches using criteria: {'; '.join(criteria)}")
    ids=set(selected["HYRIV_ID"].dropna().astype(int))
    if selected["HYRIV_ID"].duplicated().any():
        raise ValueError(f"Extraction for '{river_id}' contains duplicate HYRIV_ID values.")
    missing_down=sorted({int(value) for value in selected["NEXT_DOWN"].dropna().astype(int) if value!=0 and value not in ids})
    if missing_down:
        raise ValueError(f"Extraction for '{river_id}' is incomplete: {len(missing_down)} NEXT_DOWN references point outside the selected network. First missing IDs: {missing_down[:10]}")
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    selected.to_parquet(output_path,index=False)
    river=get_river(river_id)
    return {"river_id":river_id,"river_name":river["display_name"],"number_of_reaches":len(selected),"total_reach_length_km":float(selected["LENGTH_KM"].fillna(0).sum()),"source_dataset":river["source"]["dataset"],"output_path":str(output_path),"extraction_criteria":criteria}

def extract_configured_river(river_id:str)->dict[str,Any]:
    paths=RiverPaths.for_river(river_id)
    source_path=paths.regional_processed
    if not source_path.is_file():
        raise FileNotFoundError(f"Standardized regional HydroRIVERS dataset was not found at {source_path}. Run 'river-networks preprocess --river {river_id}' first.")
    output_path=paths.processed/"extracted_network.parquet"
    return extract_river_network(source_path,output_path,river_id)
