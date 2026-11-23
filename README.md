# River Networks

A configuration-driven pipeline and interactive Streamlit dashboard for extracting, analyzing, and exploring large-scale river drainage networks from HydroSHEDS HydroRIVERS v1.0 data.

[Hosted dashboard](https://river-networks.streamlit.app/) · [Published baseline data bundle](https://github.com/AbhinavJain27/BTP-Project/releases/tag/v2-data_bundle)

Phase 1 established the six-basin extraction and graph benchmark. Phase 2 adds exact directed-tree
metrics, scaling and fragmentation analysis, cross-basin browsing and exports, RiverBot Q&A, and
a separate river-width prediction benchmark. This README describes the current source checkout.
The hosted dashboard and published baseline bundle can lag local changes.

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
  - Diameters and path lengths: directed and undirected diameter, mean path length, and hops to outlet. For the six drainage trees, the directed mean is exact and the undirected mean uses landmark sampling.
  - Centrality measures: exact directed-tree betweenness for all six basins, including Amazon, and PageRank.
  - Component analysis & transitivity: DAG verification, weak/strong components, clustering coefficient (transitivity = 0.0 for dendritic trees).
  - Phase 2 metrics: Horton bifurcation, length, and area ratios, Hack’s exponent, and Tokunaga branching statistics. Fragmentation compares betweenness-ranked removal with eight seeded random trials and measures the share of reach length still connected to the original outlets. See the [metrics methods](docs/graph.md#4-phase-2-metrics).
- **Interactive Streamlit Dashboard**:
  - **Overview**: Hydrology & Network summary metric cards with native `(?)` 1–2 line tooltip explanations.
  - **Distributions**: Reach attribute distributions (length, discharge, catchment area, Strahler order, Horton's law) and network metric histograms.
  - **Reach Map**: Multi-order toggleable highlighting in bold, high-contrast colors against dull gray background reaches, with cleared initial state on country boundaries.
  - **Node Explorer**: Topological point explorer (headwaters in vivid sky blue, confluences in orange, outlets in crimson red, intermediates in purple) with balanced quota sampling and legend preservation.
  - **Data Viewer & Download**: Filter the selected basin by stream order, choose columns, and download CSV or Parquet.
  - **Cross-Basin Comparison**: Compare saved metrics in a table and on a radar chart. The radar includes only metrics available for every displayed basin.
  - **RiverBot Q&A**: Ask for a definition, look up a basin value, choose a suggested question, or clear the conversation.
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

The app reads processed data from `datasets/`. A fresh checkout can download the published
baseline bundle. Set `DATA_BUNDLE_URL` in the environment or in `.streamlit/secrets.toml`
before starting the app:

```toml
DATA_BUNDLE_URL = "https://github.com/AbhinavJain27/BTP-Project/releases/download/v2-data_bundle/deploy_bundle.zip"
```

```bash
streamlit run dashboard/app.py
```

### 3. Use RiverBot

Open **RiverBot Q&A**. “What is the Horton bifurcation ratio?” asks Gemini for an explanation.
“What is the Horton bifurcation ratio for Ganga?” reads the saved basin value and cites its source.
Gemini receives the question, a short history of user questions, and project context. The app
validates numerical lookup requests and reads saved values locally. Unsupported requests receive
“This is out of scope for the bot.”

For Gemini support, install `pip install -e ".[gemini]"` and set `GEMINI_API_KEY` in
`.streamlit/secrets.toml` or the environment. RiverBot can use local metric lookup rules and
matching project definitions without a key.

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

# Export one basin's saved metrics
river-networks export --river godavari --format metrics_json
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

Recompute the metrics before building a bundle with the Phase 2 results. The published baseline
bundle contains the six basin extracts and baseline metrics. The export CLI also supports CSV,
GeoJSON, and Parquet.

## River-width prediction benchmark

The [Colab notebook](research/river_width_gnn_colab.ipynb) matches HydroRIVERS reaches to
[Landsat river-width observations](https://zenodo.org/records/1297434), then holds out one whole
basin at a time. It compares a hydraulic power law, two XGBoost variants, a multilayer perceptron
(MLP) without graph edges, and a directed graph neural network (GNN).

The local and Colab CPU runs used the same **45,328 matched reaches** from **2,621 distinct
Landsat segments**. Mean absolute error, averaged equally across the six held-out basins:

| Model | Local MAE (m) | Colab MAE (m) |
| --- | ---: | ---: |
| MLP without edges | **212.7** | **212.4** |
| Directed GNN | 218.2 | 218.5 |
| XGBoost with local features | 229.6 | 229.8 |
| XGBoost with upstream summaries | 227.1 | 232.9 |
| Hydraulic power law | 258.5 | 258.5 |

The MLP ranked first in both runs. Directed message passing did not improve on the MLP for this
setup. The experiment covers screened channels at least 90 m wide and does not establish accuracy
for narrow tributaries.

To reproduce it, upload the notebook to Colab and run all cells with `QUICK_CHECK = False`.
The notebook downloads the public inputs and exports `river_width_results.zip` with per-basin
and width-class metrics, predictions, matching diagnostics, and a comparison plot. Generated
results, notebook checkpoints, and local report output are ignored by Git.

---

## Streamlit Cloud Deployment

See the [deployment guide](DEPLOY.md) for clean-bundle and dashboard checks.

1. **Build the deploy bundle locally**:
   ```bash
   python scripts/build_deploy_bundle.py
   ```
   This generates `deploy_bundle.zip` with pruned reach Parquet, node tables, saved metrics, and provenance.

2. **Publish on GitHub Releases**:
   Create a data release and attach `deploy_bundle.zip`.

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
├── research/                   # Reproducible river-width Colab notebook
├── scripts/                    # Utility scripts
│   ├── build_deploy_bundle.py  # Dashboard data bundle builder
│   ├── compute_network_metrics.py # Precomputes graph metrics
│   └── preflight_phase1.py     # Pre-run verification checker
├── src/river_networks/         # Core Python package
│   ├── acquisition/            # Data acquisition & GDB inspection
│   ├── analysis/               # Tree algorithms, scaling, and fragmentation
│   ├── graph/                  # Graph builders, fields, and network metrics
│   ├── pipeline/               # Pipeline execution runner
│   ├── preprocessing/          # Parquet readers, standardizers, extractors
│   ├── rag/                     # RiverBot routing, document retrieval, and metric lookups
│   ├── storage/                # GraphML/Parquet I/O and path resolution
│   ├── validation/             # Sanity & schema validators
│   └── visualization/          # Dashboard charts, maps, and styles
├── tests/                      # Automated test suite
├── .gitignore                  # Git exclusion rules
├── requirements.txt            # Runtime dependencies
└── pyproject.toml              # Package configuration
```

---

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file. Data source: HydroSHEDS / HydroRIVERS v1.0.
