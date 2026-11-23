# River Networks Dashboard

A real-data Streamlit dashboard for the Phase 1 HydroRIVERS pipeline. It reads the project's existing GeoParquet, GraphML, and JSON artifacts directly and never fabricates metrics for missing rivers.

## Run

From the repository root:

```bash
pip install -e .
streamlit run dashboard/app.py
```

The app will open at the local Streamlit URL printed by the command.

## Implemented

- Six-river selector from `config/rivers.yaml`.
- Explicit pending/unavailable state for rivers without `processed/extracted_network.parquet`.
- Reach count and total reach length.
- Aggregate `CATCH_SKM` and maximum `UPLAND_SKM`.
- Mean `DIS_AV_CMS`.
- Headwater, confluence/junction, outlet, and intermediate node counts from directed GraphML.
- Maximum `ORD_STRA` and endorheic reach count/percentage.
- Graph validation status, weak-component count, and density from `metadata.json`.
- Reach-length and stream-order distributions.
- Node-type distribution.
- Interactive geographic reach view using the real reach geometries. MultiLineString geometries are supported.
- Pipeline provenance/status panel for acquisition, preprocessing, extraction, validation, and graph metadata.
- Clear error states for missing/malformed artifacts.
- Filtered basin CSV and Parquet downloads with a column selector.
- Cross-basin comparison using saved values. The radar includes axes shared by all displayed basins.
- Horton and fragmentation charts when the required Phase 2 metrics have been generated.

The map defaults to a bounded number of reaches for browser responsiveness. It does not alter or recompute the stored dataset; it only controls how many real geometries are drawn.
