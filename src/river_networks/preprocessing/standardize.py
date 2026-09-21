from pathlib import Path
from typing import Any
from datetime import datetime,timezone

from ..graph.fields import HYDRORIVERS_FIELD_TYPES,HYDRORIVERS_FIELDS,HYDRORIVERS_SOURCE_FIELDS
from .reader import read_hydrorivers,validate_hydrorivers_columns

def _normalize_integer_column(frame,column):
    values=frame[column].replace({"":None,"None":None,"nan":None})
    numeric=__import__("pandas").to_numeric(values,errors="coerce")
    frame[column]=numeric.round().astype("Int64")

def _normalize_float_column(frame,column):
    values=frame[column].replace({"":None,"None":None,"nan":None})
    frame[column]=__import__("pandas").to_numeric(values,errors="coerce")

def normalize_hydrorivers_types(frame):
    for column,field_type in HYDRORIVERS_FIELD_TYPES.items():
        if column=="geometry" or column not in frame.columns:
            continue
        if field_type=="int":
            _normalize_integer_column(frame,column)
        elif field_type=="float":
            _normalize_float_column(frame,column)
    return frame

def canonicalize_hydrorivers_columns(frame):
    rename={source:canonical for canonical,source in HYDRORIVERS_SOURCE_FIELDS.items() if source!=canonical and source in frame.columns}
    return frame.rename(columns=rename)

def normalize_identifiers(frame):
    for column in ("HYRIV_ID","NEXT_DOWN","MAIN_RIV","HYBAS_ID"):
        if column in frame.columns:
            _normalize_integer_column(frame,column)
    return frame

def validate_and_clean_geometry(frame):
    frame=frame.copy()
    frame=frame[~frame.geometry.isna() & ~frame.geometry.is_empty].copy()
    if frame.empty:
        return frame
    invalid=~frame.geometry.is_valid
    if invalid.any():
        repaired=frame.loc[invalid,"geometry"].make_valid()
        supported=repaired.geom_type.isin(["LineString","MultiLineString"])
        invalid_repairs=repaired.index[~supported]
        if len(invalid_repairs):
            frame=frame.drop(index=invalid_repairs)
        repaired=repaired.loc[repaired.index.intersection(frame.index)]
        frame.loc[repaired.index,"geometry"]=repaired
    frame=frame[~frame.geometry.isna() & ~frame.geometry.is_empty].copy()

    frame=frame[frame.geometry.geom_type.isin(["LineString","MultiLineString"])].copy()
    return frame

def remove_invalid_records(frame):
    frame=frame.copy()
    frame=frame[frame["HYRIV_ID"].notna()].copy()
    frame=frame.drop_duplicates(subset=["HYRIV_ID"],keep="first")
    return frame

def standardize_hydrorivers(frame):
    missing=validate_hydrorivers_columns(frame.columns)
    if missing:
        raise ValueError(f"HydroRIVERS source is missing required columns: {', '.join(missing)}")
    frame=canonicalize_hydrorivers_columns(frame.copy())
    frame=normalize_hydrorivers_types(frame)
    frame=normalize_identifiers(frame)
    frame=validate_and_clean_geometry(frame)
    frame=remove_invalid_records(frame)
    frame=frame[list(HYDRORIVERS_FIELDS)]
    return frame

def preprocess_hydrorivers(source_path:Path,output_path:Path,source_format:str|None=None,layer:str|None=None)->dict[str,Any]:
    source_path=Path(source_path)
    output_path=Path(output_path)
    frame=read_hydrorivers(source_path,source_format=source_format,layer=layer)
    original_count=len(frame)
    crs=frame.crs
    frame=standardize_hydrorivers(frame)
    if crs is not None:
        frame=frame.set_crs(crs,allow_override=True)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    if output_path.suffix.lower()!=".parquet":
        raise ValueError(f"Preprocessed output must use GeoParquet with a .parquet extension: {output_path}")
    try:
        frame.to_parquet(output_path,index=False)
    except ImportError as exc:
        raise RuntimeError("PyArrow is required to write GeoParquet. Install project dependencies before preprocessing.") from exc
    return {"source_path":str(source_path),"source_format":source_format,"source_layer":layer,"output_path":str(output_path),"input_records":original_count,"output_records":len(frame),"removed_records":original_count-len(frame),"crs":crs.to_string() if crs is not None else None,"field_mapping":HYDRORIVERS_SOURCE_FIELDS,"processed_at":datetime.now(timezone.utc).isoformat()}
