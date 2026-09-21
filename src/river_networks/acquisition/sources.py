from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging
from datetime import datetime,timezone

from ..config import resolve_config
from ..preprocessing.reader import available_layers,read_hydrorivers,validate_hydrorivers_columns

@dataclass(frozen=True)
class HydroRIVERSSource:
    dataset:str="HydroRIVERS"
    provider:str="HydroSHEDS"
    version:str="v1.0"

logger=logging.getLogger(__name__)

def get_source_metadata(river_id:str)->dict[str,Any]:
    resolved=resolve_config(river_id)
    river=resolved["river"]
    source={**resolved["source"],**river["source"]}
    source_path=Path(resolved["paths"]["regional_source"])
    return {
        "river_id":river["river_id"],
        "display_name":river["display_name"],
        "dataset":source.get("dataset","HydroRIVERS"),
        "provider":source.get("provider","HydroSHEDS"),
        "version":source.get("version","v1.0"),
        "regional_source":river["source"]["regional_source"],
        "source_format":source["format"],
        "source_layer":source["layer"],
        "source_path":str(source_path),
        "source_exists":source_path.exists(),
        "raw_directory":str(source_path.parent),
        "regional_processed_path":resolved["paths"]["regional_processed"],
        "download_url":source["download_url"],
        "next_action":"Download and extract the configured regional source, then place the .gdb directory at the expected path.",
    }

def _missing(path:Path,source_format:str)->dict[str,Any]:
    message="HydroRIVERS regional source not found" if source_format=="filegdb" else "HydroRIVERS source not found"
    return {"valid":False,"exists":False,"is_file":False,"is_directory":False,"size_bytes":0,"message":f"{message}: {path}"}

def validate_source_file(source_path:Path,source_format:str="filegdb",layer:str|None=None)->dict[str,Any]:
    source_path=Path(source_path)
    if not source_path.exists():
        logger.warning("HydroRIVERS regional source is unavailable: %s",source_path)
        return _missing(source_path,source_format)
    if source_format=="filegdb":
        if not source_path.is_dir():
            return {"valid":False,"exists":True,"is_file":source_path.is_file(),"is_directory":False,"size_bytes":0,"message":f"Expected File Geodatabase directory does not exist: {source_path}"}
        if not layer:
            return {"valid":False,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"message":f"HydroRIVERS File Geodatabase layer is not configured for: {source_path}"}
        try:
            layers=available_layers(source_path)
        except Exception as exc:
            return {"valid":False,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"message":f"HydroRIVERS layer could not be opened: {source_path}. {exc}"}
        if layer not in layers:
            return {"valid":False,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"available_layers":layers,"message":f"HydroRIVERS layer could not be opened: expected '{layer}' in {source_path}"}
        try:
            sample=read_hydrorivers(source_path,source_format=source_format,layer=layer,rows=1)
        except Exception as exc:
            return {"valid":False,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"message":f"HydroRIVERS layer could not be opened: {source_path}/{layer}. {exc}"}
        missing=validate_hydrorivers_columns(sample.columns)
        if missing:
            return {"valid":False,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"available_layers":layers,"message":f"Required HydroRIVERS fields are missing in {source_path}/{layer}: {', '.join(missing)}"}
        return {"valid":True,"exists":True,"is_file":False,"is_directory":True,"size_bytes":0,"available_layers":layers,"message":f"HydroRIVERS File Geodatabase source is available: {source_path}/{layer}","crs":sample.crs.to_string() if sample.crs is not None else None}
    if not source_path.is_file():
        return {"valid":False,"exists":True,"is_file":False,"is_directory":source_path.is_dir(),"size_bytes":0,"message":f"HydroRIVERS source path is not a file: {source_path}"}
    size=source_path.stat().st_size
    if size==0:
        return {"valid":False,"exists":True,"is_file":True,"is_directory":False,"size_bytes":0,"message":f"HydroRIVERS source file is empty: {source_path}"}
    return {"valid":True,"exists":True,"is_file":True,"is_directory":False,"size_bytes":size,"message":f"HydroRIVERS source file is available: {source_path}"}

def acquire_hydrorivers(river_id:str)->dict[str,Any]:
    metadata=get_source_metadata(river_id)
    validation=validate_source_file(Path(metadata["source_path"]),metadata["source_format"],metadata["source_layer"])
    return {**metadata,**validation,"checked_at":datetime.now(timezone.utc).isoformat()}
