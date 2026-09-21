# Phase 1 Operational Overview

Phase 1 establishes a reproducible, configuration-driven pipeline for standardizing HydroRIVERS regional data, extracting complete river basins, constructing topological graph networks, computing network science metrics, and presenting the results in an interactive Streamlit dashboard.

---

## 1. Supported River Basins

The pipeline currently supports six global and Indian river basins:

| River | Region | Source Dataset | Selection Identifier (`MAIN_RIV`) | Reaches Extracted |
|---|---|---|---|---|
| **Amazon** | South America (`sa`) | HydroRIVERS v1.0 | `60443230` | 744,786 |
| **Ganges-Brahmaputra-Meghna** | Asia (`as`) | HydroRIVERS v1.0 | `41067217` | 163,484 |
| **Yangtze** | Asia (`as`) | HydroRIVERS v1.0 | `40613666` | 140,974 |
| **Nile** | Africa (`af`) | HydroRIVERS v1.0 | `10047863` | 133,798 |
| **Godavari** | India (Asia `as`) | HydroRIVERS v1.0 | `41275841` | 18,703 |
| **Krishna** | India (Asia `as`) | HydroRIVERS v1.0 | `41297283` | 16,084 |

---

## 2. Pipeline Execution

Install the project in editable mode:
```bash
pip install -e .
```

Inspect resolved configuration for any river:
```bash
river-networks config --river godavari
```

Run individual stages:
```bash
river-networks acquire --river godavari
river-networks preprocess --river godavari
river-networks extract --river godavari
river-networks graph --river godavari
river-networks validate --river godavari
```

Or run the full pipeline in one command:
```bash
river-networks pipeline --river godavari
```

The pipeline automatically fingerprints input sources and configurations; stages are cached and only re-executed when fingerprints change or `--force` is supplied.

---

## 3. Output Artifacts

Each river basin produces a self-contained artifact bundle under `datasets/<region>/<river_id>/`:

```text
datasets/<region>/<river_id>/
├── processed/
│   └── extracted_network.parquet    # Standardized GeoParquet of reach records
├── graphs/
│   └── river_graph/
│       ├── directed.graphml         # Directed igraph artifact (downstream flow)
│       ├── undirected.graphml       # Undirected igraph artifact
│       ├── metadata.json            # Graph validation metadata & component counts
│       ├── network_metrics.json     # Precomputed network science metrics
│       └── nodes.parquet            # Compact columnar node table for dashboard
└── metadata/
    ├── acquisition.json             # Source dataset provenance
    ├── preprocessing.json           # Standardization audit trail
    ├── extraction.json              # Criteria & reach counts
    └── validation.json              # Topology health checks
```

---

## 4. Interactive Dashboard

Launch the Streamlit dashboard:
```bash
streamlit run dashboard/app.py
```

Features:
- **Overview**: Hydrology metrics (reaches, length, catchment area, discharge, Strahler order, endorheic counts) and Network metrics (density, self-loops, diameter, path lengths, degree stats, centralities, clustering coefficient) with native `(?)` tooltip explanations.
- **Distributions**: Attribute distributions and network science histograms.
- **Reach Map**: Multi-order toggleable highlighting in distinct colors against dull gray background reaches.
- **Node Explorer**: Full topological profiling (headwaters, confluences, outlets, intermediates) with balanced sampling and vivid distinct colors.
- **Provenance / Logs**: Pipeline execution status and metadata audit trail.
