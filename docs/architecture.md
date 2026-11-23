# System Architecture

The project is structured around a modular, reproducible data pipeline with decoupled layers for data ingestion, topological extraction, graph construction, metrics computation, and interactive visualization.

---

## 1. Pipeline Layer

The execution pipeline operates in five sequential stages, managed by [`run_pipeline()`](../src/river_networks/pipeline/runner.py):

```text
[Regional GDB]
       │
       ▼ (1. Acquisition)
[Raw Verification]
       │
       ▼ (2. Preprocessing)
[Standardized Regional GeoParquet]
       │
       ▼ (3. Extraction)
[River Extracted GeoParquet] ─── (Topological Closure Check)
       │
       ▼ (4. Graph Construction)
[Directed & Undirected GraphML] + [nodes.parquet]
       │
       ▼ (5. Validation & Metrics)
[Validation Metadata]
```

### Stage Responsibilities
1. **Acquisition**: Validates that the regional HydroRIVERS File Geodatabase exists in `datasets/raw/` and contains the expected layer and schema.
2. **Preprocessing**: Reads the raw GDB once per continental region, validates columns, repairs self-intersecting geometries, casts integer IDs, and writes a shared regional GeoParquet file (`datasets/<region>/processed/`).
3. **Extraction**: Filters the shared regional dataset by verified selection criteria (`MAIN_RIV`), validates that every `NEXT_DOWN` reference points inside the selected network or to an outlet (`0`), and writes `extracted_network.parquet`.
4. **Graph Construction**: Converts reaches to directed edges and connection points to vertices (`junction:ID`, `outlet:ID`), assigns node roles, and exports GraphML artifacts.
5. **Validation**: Verifies graph topology and writes validation metadata. The separate metrics script computes network statistics and Phase 2 analyses in `network_metrics.json`.

---

## 2. Storage & Caching Layer

- **Fingerprint-Based Invalidation**: Each stage hashes its input configuration and upstream file signatures (`_file_signature`). If an artifact exists on disk and its `cache_key` matches `metadata.json`, execution is skipped (`status: reused`).
- **Path Resolution**: [`RiverPaths`](../src/river_networks/storage/paths.py) dynamically resolves all filesystem paths from `config/paths.yaml` and `config/rivers.yaml`. There are no hardcoded filesystem paths in the codebase.
- **Git Separation**: Raw GDBs, regional GeoParquets, and river artifacts are excluded from Git via `.gitignore`.

---

## 3. Visualization Layer

- **Streamlit Dashboard** ([`dashboard/app.py`](../dashboard/app.py)):
  - Built with Plotly and Streamlit.
  - Multi-tab layout: Overview, Distributions, Reach Map, Node Explorer, and Provenance / Logs.
  - Responsive reach and node maps with toggleable multi-order filtering and balanced topological role sampling.
- **Deployment Bootstrap** ([`dashboard/data_bootstrap.py`](../dashboard/data_bootstrap.py)):
  - Automatically fetches and unpacks `deploy_bundle.zip` on ephemeral cloud containers (e.g. Streamlit Community Cloud) using direct HTTPS or Google Drive fallback.
