# River Networks

A configuration-driven pipeline and interactive Streamlit dashboard for extracting, analyzing, and exploring large-scale river drainage networks from HydroSHEDS HydroRIVERS v1.0 data.

🌐 **Live Dashboard & Computed Data**: Access the interactive dashboard and explore all computed datasets online at **[https://river-networks.streamlit.app/](https://river-networks.streamlit.app/)**.

---

## Key Features

- **Six Global River Basins Fully Processed**:
  - **Amazon** (South America): 744,786 reaches, 2,345-hop directed diameter.
  - **Ganga-Brahmaputra-Meghna** (Asia): 163,483 reaches, 1,415-hop directed diameter.
  - **Yangtze** (Asia): 140,973 reaches, 1,738-hop directed diameter.
  - **Nile** (Africa): 133,797 reaches, 1,940-hop directed diameter.
  - **Godavari** (India): 18,702 reaches, 449-hop directed diameter.
  - **Krishna** (India): 16,083 reaches, 396-hop directed diameter.
- **Network Science & Graph Metrics**:
  - Topological metrics: node/edge count, graph density, self-loops (strictly 0).
  - Degree distributions: in-degree (confluence capacity), out-degree, total degree.
  - Diameters and path lengths: directed diameter, undirected diameter, average path length, and hops to outlet. Large-basin undirected average path lengths use landmark sampling.
  - Centrality measures: betweenness centrality (flow bottlenecks), PageRank (tributary accumulation).
  - Component analysis & transitivity: DAG verification, weak/strong components, clustering coefficient (transitivity = 0.0 for dendritic trees).
  - Phase 2 metrics: Horton, Hack, and Tokunaga scaling plus simulated reach fragmentation. See the [metrics methods](docs/graph.md#4-phase-2-metrics).
- **Interactive Streamlit Dashboard**:
  - **Overview**: Hydrology & Network summary metric cards with native `(?)` 1–2 line tooltip explanations.
  - **Distributions**: Reach attribute distributions (length, discharge, catchment area, Strahler order, Horton's law) and network metric histograms.
  - **Reach Map**: Multi-order toggleable highlighting in bold, high-contrast colors against dull gray background reaches, with cleared initial state on country boundaries.
  - **Node Explorer**: Topological point explorer (headwaters in vivid sky blue, confluences in orange, outlets in crimson red, intermediates in purple) with balanced quota sampling and legend preservation.
  - **Data Viewer & Download**: Filter the selected basin by stream order, choose columns, and download CSV or Parquet.
  - **Cross-Basin Comparison**: Compare shared saved metrics with a table and radar chart.
  - **Provenance / Logs**: Pipeline execution status and metadata audit trail.
- **Compact dashboard bundle**: The bundler packages basin reaches, node tables, metrics, and provenance. The published `v2-data_bundle` ZIP is about 55 MB.

---

## Quickstart

### 1. Installation

Clone the repository and install the project in a Python environment (Python 3.10+):

```bash
git clone https://github.com/AbhinavJain27/BTP-Project.git
cd BTP-Project
pip install -e .
```

### 2. Launch the Dashboard

**Live App**: You can explore the live dashboard directly without local installation at **[https://river-networks.streamlit.app/](https://river-networks.streamlit.app/)** to view maps, metrics, and download all computed datasets.

To run locally:

```bash
streamlit run dashboard/app.py
```

The app opens in your browser and reads processed data from `datasets/`. On a fresh checkout, set
`DATA_BUNDLE_URL` in the environment or in `.streamlit/secrets.toml` to the published bundle URL
shown below.

---

## Running the Pipeline

The CLI allows running individual stages or the full end-to-end pipeline:

```bash
# Check status and configuration
river-networks config --river godavari

# Run pipeline for a specific river
river-networks pipeline --river godavari

# Recompute network metrics for all rivers
python scripts/compute_network_metrics.py --force
```

### Pipeline Stages
1. **Acquisition**: Verifies regional HydroRIVERS File Geodatabases in the raw directories defined in `config/paths.yaml`.
2. **Preprocessing**: Validates schema, repairs linework geometries, normalizes types, and outputs shared regional GeoParquet.
3. **Extraction**: Filters reaches by verified `MAIN_RIV` identifiers and enforces topological closure (every `NEXT_DOWN` points to an in-network reach or `0`).
4. **Graph Construction**: Builds directed and undirected `igraph` models, tags topological node roles, and saves GraphML + metadata.
5. **Validation**: Checks topology and writes validation metadata.

The metrics script runs separately and writes `network_metrics.json`. It can recompute topology,
centrality, scaling, and fragmentation directly from extracted basin Parquet. GraphML-only inputs
can produce baseline graph metrics.

---

## Streamlit Cloud Deployment

To deploy on Streamlit Community Cloud without exceeding container memory limits:

1. **Build the deploy bundle locally**:
   ```bash
   python scripts/build_deploy_bundle.py
   ```
   This generates `deploy_bundle.zip` with pruned reach Parquet, node tables, saved metrics, and provenance.

2. **Publish on GitHub Releases**:
   Create a release in your GitHub repository (e.g. tag `v1.0-data`) and attach `deploy_bundle.zip`.

3. **Deploy on Streamlit Cloud**:
   - Repository: your GitHub repo
   - Main file path: `dashboard/app.py`
   - In **Settings → Secrets**, set the bundle URL. The published baseline bundle is:
     ```toml
     DATA_BUNDLE_URL = "https://github.com/AbhinavJain27/BTP-Project/releases/download/v2-data_bundle/deploy_bundle.zip"
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
│   ├── build_deploy_bundle.py  # Dashboard data bundle builder
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
└── pyproject.toml              # Package configuration
```

---

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file. Data source: HydroSHEDS / HydroRIVERS v1.0.
