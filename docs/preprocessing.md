# Preprocessing & Standardization

The preprocessing stage converts raw, multi-gigabyte regional File Geodatabases into clean, standardized, columnar GeoParquet files.

---

## 1. Objectives

- **One-Time Ingestion**: Reads the raw regional File Geodatabase (`.gdb`) once per continental region (Asia, Africa, South America) rather than duplicating the full source per river.
- **Linework Geometry Repair**: Fixes invalid or self-intersecting geometries while strictly preserving linear network topology.
- **Schema Canonicalization**: Maps source fields (e.g. `HYBAS_L12` $\to$ `HYBAS_ID`) and normalizes data types.
- **Fast Columnar Storage**: Emits standardized regional GeoParquet (`.parquet`) compressed with Zstandard for fast downstream queries.

---

## 2. Standardization Steps

In [`standardize.py`](../src/river_networks/preprocessing/standardize.py):

1. **Schema Validation**:
   - Asserts that all 15 required HydroRIVERS fields are present before processing.
2. **Column Renaming**:
   - Renames `HYBAS_L12` to `HYBAS_ID`.
3. **Type Normalization**:
   - Casts identifiers (`HYRIV_ID`, `NEXT_DOWN`, `MAIN_RIV`, `HYBAS_ID`) and orders (`ORD_STRA`, `ORD_CLAS`, `ORD_FLOW`, `ENDORHEIC`) to 64-bit nullable integers (`Int64`).
   - Casts lengths, areas, and discharge to 64-bit floats.
4. **Geometry Cleaning (`validate_and_clean_geometry`)**:
   - Drops null or empty geometries.
   - Applies `shapely.validation.make_valid()` to self-intersecting coordinates.
   - Enforces that only `LineString` and `MultiLineString` geometries pass to the graph layer (any non-linework repairs like points or polygons are stripped).
5. **Deduplication**:
   - Drops duplicate `HYRIV_ID` records, retaining the first occurrence.
6. **Export**:
   - Saves the standardized regional table to `datasets/<region>/processed/<source_name>.parquet`.
