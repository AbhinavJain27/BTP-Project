"""Export subsystem for River Networks: CSV, GeoJSON, GeoParquet, and metric summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import geopandas as gpd
import pandas as pd

from .paths import RiverPaths

SUPPORTED_EXPORT_FORMATS = ("csv", "geojson", "parquet", "metrics_json")

def export_river_data(
    river_id: str,
    output_format: str = "csv",
    columns: list[str] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Exports extracted reach network and/or metrics for a river in the requested format."""
    format_lower = output_format.lower().strip()
    if format_lower not in SUPPORTED_EXPORT_FORMATS:
        raise ValueError(
            f"Unsupported export format '{output_format}'. "
            f"Supported formats: {', '.join(SUPPORTED_EXPORT_FORMATS)}"
        )

    paths = RiverPaths.for_river(river_id)
    extracted_parquet = paths.processed / "extracted_network.parquet"
    if not extracted_parquet.is_file():
        raise FileNotFoundError(
            f"Extracted network not found for river '{river_id}' at {extracted_parquet}. "
            f"Run 'river-networks extract --river {river_id}' first."
        )

    dest_dir = paths.exports
    dest_dir.mkdir(parents=True, exist_ok=True)

    if format_lower == "metrics_json":
        metrics_file = paths.graphs / "river_graph" / "network_metrics.json"
        if not metrics_file.is_file():
            raise FileNotFoundError(f"Network metrics not found at {metrics_file}")
        target_path = output_path or (dest_dir / f"{river_id}_network_metrics.json")
        target_path.write_bytes(metrics_file.read_bytes())
        return {
            "river_id": river_id,
            "format": format_lower,
            "output_file": str(target_path),
            "size_bytes": target_path.stat().st_size,
        }

    frame = gpd.read_parquet(extracted_parquet)
    if columns:
        valid_cols = [c for c in columns if c in frame.columns]
        if "geometry" not in valid_cols and "geometry" in frame.columns and format_lower == "geojson":
            valid_cols.append("geometry")
        frame = frame[valid_cols]

    if format_lower == "csv":
        target_path = output_path or (dest_dir / f"{river_id}_reaches.csv")
        # Exclude complex geometry object if exporting to plain tabular CSV or export WKT
        csv_frame = frame.copy()
        if "geometry" in csv_frame.columns:
            csv_frame["geometry_wkt"] = csv_frame["geometry"].apply(lambda g: g.wkt if g is not None else None)
            csv_frame = csv_frame.drop(columns=["geometry"])
        csv_frame.to_csv(target_path, index=False, encoding="utf-8-sig")

    elif format_lower == "geojson":
        target_path = output_path or (dest_dir / f"{river_id}_reaches.geojson")
        frame.to_file(target_path, driver="GeoJSON")

    elif format_lower == "parquet":
        target_path = output_path or (dest_dir / f"{river_id}_reaches.parquet")
        frame.to_parquet(target_path, compression="zstd", index=False)

    return {
        "river_id": river_id,
        "format": format_lower,
        "records_exported": len(frame),
        "columns_exported": list(frame.columns),
        "output_file": str(target_path),
        "size_bytes": target_path.stat().st_size,
    }
