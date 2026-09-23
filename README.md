# River Networks (Phase 1)

A configuration-driven pipeline and interactive Streamlit dashboard for extracting, analyzing, and exploring large-scale river drainage networks from HydroSHEDS HydroRIVERS v1.0 data.

🌐 **Live Dashboard & Computed Data**: Access the interactive dashboard and explore all computed datasets online at **[https://river-networks.streamlit.app/](https://river-networks.streamlit.app/)**.

---

## Key Features

- **Six Global River Basins Fully Processed**:
  - **Amazon** (South America): 744,786 reaches, 2,345-hop directed diameter.
  - **Ganga-Brahmaputra-Meghna** (Asia): 163,484 reaches, 1,415-hop directed diameter.
  - **Yangtze** (Asia): 140,974 reaches, 1,738-hop directed diameter.
  - **Nile** (Africa): 133,798 reaches, 1,940-hop directed diameter.
  - **Godavari** (India): 18,703 reaches, 449-hop directed diameter.
  - **Krishna** (India): 16,084 reaches, 396-hop directed diameter.
- **Network Science & Graph Metrics**:
  - Topological metrics: node/edge count, graph density, self-loops (strictly 0).
  - Degree distributions: in-degree (confluence capacity), out-degree, total degree.
  - Diameters & path lengths: directed diameter, undirected diameter (via O(V) 2-sweep BFS), average path length, shortest path hops to outlet.
  - Centrality measures: betweenness centrality (flow bottlenecks), PageRank (tributary accumulation).
  - Component analysis & transitivity: DAG verification, weak/strong components, clustering coefficient (transitivity = 0.0 for dendritic trees).
- **Interactive Streamlit Dashboard**:
  - **Overview**: Hydrology & Network summary metric cards with native `(?)` 1–2 line tooltip explanations.
  - **Distributions**: Reach attribute distributions (length, discharge, catchment area, Strahler order, Horton's law) and network metric histograms.
  - **Reach Map**: Multi-order toggleable highlighting in bold, high-contrast colors against dull gray background reaches, with cleared initial state on country boundaries.
  - **Node Explorer**: Topological point explorer (headwaters in vivid sky blue, confluences in orange, outlets in crimson red, intermediates in purple) with balanced quota sampling and legend preservation.
  - **Data Viewer & Download**: Human-friendly dataset inspection and custom column export (processed basin networks in `.csv` for Excel, and regional hydrography in `.parquet`/`.csv`).
  - **Provenance / Logs**: Pipeline execution status and metadata audit trail.
- **Zero-RAM Deployment Architecture**:
  - Built-in bundler (`scripts/build_deploy_bundle.py`) that converts 1.65 GB of raw GraphML into columnar `nodes.parquet`, shrinking the entire 6-river dataset to **~35 MB zipped** for instant, low-memory deployment on Streamlit Community Cloud.

---

## Quickstart

### 1. Installation

Clone the repository and install the project in a Python environment (Python 3.10+):

```bash
git clone https://github.com/<username>/river-networks.git
cd river-networks
pip install -e .
```

### 2. Launch the Dashboard

**Live App**: You can explore the live dashboard directly without local installation at **[https://river-networks.streamlit.app/](https://river-networks.streamlit.app/)** to view maps, metrics, and download all computed datasets.

To run locally:

```bash
streamlit run dashboard/app.py
```

The app will open in your browser. On a local checkout with processed data, it loads directly from `datasets/`.

---

## Running the Pipeline

The CLI allows running individual stages or the full end-to-end pipeline:

```bash
# Check status and configuration
river-networks config --river godavari

# Run pipeline for a specific river
river-networks pipeline --river godavari

# Recompute network metrics for all rivers
python scripts/compute_network_metrics.py
```

### Pipeline Stages
1. **Acquisition**: Verifies regional HydroRIVERS File Geodatabases in `datasets/raw/`.
2. **Preprocessing**: Validates schema, repairs linework geometries, normalizes types, and outputs shared regional GeoParquet.
3. **Extraction**: Filters reaches by verified `MAIN_RIV` identifiers and enforces topological closure (every `NEXT_DOWN` points to an in-network reach or `0`).
4. **Graph Construction**: Builds directed and undirected `igraph` models, tags topological node roles, and saves GraphML + metadata.
5. **Validation & Metrics**: Verifies DAG acyclicity, computes diameters, path lengths, centralities, and writes `network_metrics.json`.

---

## Streamlit Cloud Deployment

To deploy on Streamlit Community Cloud without exceeding container memory limits:

1. **Build the deploy bundle locally**:
   ```bash
   python scripts/build_deploy_bundle.py
   ```
   This generates `deploy_bundle.zip` (~35 MB) containing pruned reach parquets, precomputed `nodes.parquet` tables, and metadata.

2. **Publish on GitHub Releases**:
   Create a release in your GitHub repository (e.g. tag `v1.0-data`) and attach `deploy_bundle.zip`.

3. **Deploy on Streamlit Cloud**:
   - Repository: your GitHub repo
   - Main file path: `dashboard/app.py`
   - In **Settings $\to$ Secrets**, add:
     ```toml
     DATA_BUNDLE_URL = "https://github.com/<username>/<repo>/releases/download/v1.0-data/deploy_bundle.zip"
     ```
   The app will automatically download and unpack the bundle on first run.

---

## Repository Structure

```text
├── config/                     # Pipeline & river selection configs
│   ├── paths.yaml              # Regional source paths and download URLs
│   └── rivers.yaml             # River basin definitions & selection IDs
├── dashboard/                  # Streamlit web application
│   ├── app.py                  # Main dashboard application
│   └── data_bootstrap.py       # Container bootstrap loader
├── docs/                       # Architectural & technical documentation
│   ├── acquisition.md          # Regional data acquisition guide
│   ├── architecture.md         # System architecture & stage flow
│   ├── data_model.md           # Schema & entity definitions
│   ├── extraction.md           # Extraction logic & closure validation
│   ├── graph.md                # Graph construction & network science metrics
│   ├── phase1.md               # Phase 1 operational overview
│   └── preprocessing.md        # Standardization & geometry cleaning
├── scripts/                    # Utility scripts
│   ├── build_deploy_bundle.py  # Zero-RAM deploy bundle builder
│   ├── compute_network_metrics.py # Precomputes graph metrics
│   └── preflight_phase1.py     # Pre-run verification checker
├── src/river_networks/         # Core Python package
│   ├── acquisition/            # Data acquisition & GDB inspection
│   ├── graph/                  # Graph builders, fields, and network metrics
│   ├── pipeline/               # Pipeline execution runner
│   ├── preprocessing/          # Parquet readers, standardizers, extractors
│   ├── storage/                # GraphML/Parquet I/O and path resolution
│   └── validation/             # Sanity & schema validators
├── tests/                      # Automated test suite
├── .gitignore                  # Git exclusion rules
├── requirements.txt            # Runtime dependencies
└── setup.py                    # Package configuration
```

---

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file. Data source: HydroSHEDS / HydroRIVERS v1.0.
