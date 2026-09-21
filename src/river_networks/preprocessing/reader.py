from pathlib import Path

from ..graph.fields import HYDRORIVERS_SOURCE_FIELDS

def _geopandas():
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise RuntimeError("GeoPandas is required to read HydroRIVERS. Install project dependencies before preprocessing.") from exc
    return gpd

def read_hydrorivers(source_path:Path,source_format:str|None=None,layer:str|None=None,rows:int|None=None):
    source_path=Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"HydroRIVERS regional source not found: {source_path}")
    if source_format=="filegdb" and not source_path.is_dir():
        raise ValueError(f"Expected File Geodatabase directory does not exist: {source_path}")
    if source_format=="filegdb" and not layer:
        raise ValueError("A HydroRIVERS File Geodatabase layer must be configured.")
    if source_path.suffix.lower()==".parquet":
        return _geopandas().read_parquet(source_path)
    options={"layer":layer,"engine":"pyogrio"}
    if rows is not None:
        options["rows"]=rows
    return _geopandas().read_file(source_path,**options)

def available_layers(source_path:Path):
    try:
        import pyogrio
    except ImportError as exc:
        raise RuntimeError("Pyogrio is required to inspect HydroRIVERS File Geodatabases. Install project dependencies before preprocessing.") from exc
    return [str(row[0]) for row in pyogrio.list_layers(source_path)]

def validate_hydrorivers_columns(columns)->list[str]:
    available=set(columns)
    return [source for canonical,source in HYDRORIVERS_SOURCE_FIELDS.items() if source not in available and canonical not in available]
