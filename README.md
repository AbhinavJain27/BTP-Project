# River Networks

A configuration-driven pipeline and interactive Streamlit dashboard for extracting, analyzing, and exploring large-scale river drainage networks from HydroSHEDS HydroRIVERS v1.0 data.

[Hosted dashboard](https://river-networks.streamlit.app/) · [Phase 2 data bundle](https://github.com/AbhinavJain27/BTP-Project/releases/tag/v3-data_bundle) · [Baseline bundle](https://github.com/AbhinavJain27/BTP-Project/releases/tag/v2-data_bundle)

Phase 1 established the six-basin extraction and graph benchmark. Phase 2 adds exact directed-tree
metrics, scaling and fragmentation analysis, cross-basin browsing and exports, RiverBot Q&A, and
a separate river-width prediction benchmark. This README describes the current source checkout.
The hosted dashboard uses the bundle URL configured in its Streamlit settings.

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
- **Compact dashboard bundle**: The published `v3-data_bundle` ZIP is about 55 MB and includes updated metrics for all six basins.

---

## Quickstart

### 1. Clone and install locally

Install Git and Python 3.10 or later, then clone the repository. Run the remaining commands
from the repository root.

```sh
git clone https://github.com/AbhinavJain27/BTP-Project.git
cd BTP-Project
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -e .
```

These commands use the virtual environment's interpreter directly, so PowerShell activation
is optional. If `py` is unavailable, use `python` to create the environment.

**macOS or Linux**

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -e .
```

### 2. Load the data bundle and launch the dashboard

Choose either automatic download or manual extraction. The Phase 2 bundle contains processed
data for six basins. The dashboard can use these files immediately without running the pipeline.

**Automatic download.** Create `.streamlit/secrets.toml` in the repository root and add:

```toml
DATA_BUNDLE_URL = "https://github.com/AbhinavJain27/BTP-Project/releases/download/v3-data_bundle/deploy_bundle.zip"
```

The dashboard downloads this ZIP and extracts it into `datasets/` on first launch when
no local basin data is detected. You can also set `DATA_BUNDLE_URL` as an environment variable.

**Manual extraction.** Download `deploy_bundle.zip` from the [Phase 2 release](https://github.com/AbhinavJain27/BTP-Project/releases/tag/v3-data_bundle)
and extract its contents directly into `datasets/`. Check that the result includes
`datasets/india/ganga/processed/extracted_network.parquet` and
`datasets/global/amazon/processed/extracted_network.parquet`. If your extractor creates a
wrapper folder named `deploy_bundle`, move its contents up into `datasets/`.

**Launch** from the repository root:

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

```sh
# macOS or Linux, with the virtual environment active
python -m streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`, then select
a river in the sidebar. To test a newer release with automatic download, use a fresh checkout
or stop Streamlit and temporarily move the existing `datasets/` directory aside. Changing the
URL alone leaves an existing `.bundle_ready` marker or extracted basin Parquet in use.

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

Recompute the metrics before building a new bundle after changing the analysis. The research notebook
uses the published baseline bundle to reproduce the original width experiment. The export CLI also supports CSV,
GeoJSON, and Parquet.

## Add a river or basin

### 1. Find the HydroRIVERS source and outlet ID

Open the [regional HydroRIVERS layer](https://www.hydrosheds.org/products/hydrorivers)
in a GIS such as QGIS. Locate the intended river and verify its `MAIN_RIV` value in the
attribute table. `MAIN_RIV` identifies the terminal reach of the connected system.
Confirm that the terminal reach matches the basin you want. A tributary can share its
parent basin's `MAIN_RIV` value, so this selection can include the entire parent basin.

### 2. Register the river in `config/rivers.yaml`

Add an entry under the existing `rivers:` mapping. Replace `example_river`, the display name,
and `12345678` with your own ID, name, and verified `MAIN_RIV`. Choose `india` or `global`
for the artifact directory, and select the continental source separately.

```yaml
  example_river:
    river_id: example_river
    display_name: Example River
    region: global
    source:
      dataset: HydroRIVERS
      provider: HydroSHEDS
      version: v1.0
      regional_source: asia
      format: filegdb
    selection:
      method: main_riv
      main_riv_ids: [12345678]
      hyriv_ids: []
      hybas_ids: []
    artifact_id: example_river
    output_location: global/example_river
```

Keep `output_location` equal to `<region>/<artifact_id>`. The `regional_source` value must
match a key under `paths.regional_sources` in [`config/paths.yaml`](config/paths.yaml).
For an unlisted continent, add a source there using an existing entry as a template.
Set the official ZIP URL, the expected `.gdb` directory and layer names, and the raw and
processed paths. The dashboard reads `config/rivers.yaml` to populate its river selector.

### 3. Prepare the source, build the graph, and compute metrics

Run `river-networks config --river example_river` to print the resolved paths and source URL.
Download and unpack the regional archive so the `.gdb` directory sits at the reported
`paths.regional_source` location. For the Asia example, that is
`datasets/india/raw/HydroRIVERS_v10_as.gdb`, even though the basin artifacts go under `global/`.
The `acquire` command checks the local geodatabase and layer.

```sh
river-networks acquire --river example_river
river-networks pipeline --river example_river
python scripts/compute_network_metrics.py --river example_river --force
```

On Windows without activation, use `.\.venv\Scripts\river-networks.exe` in place of
`river-networks` and `.\.venv\Scripts\python.exe` in place of `python`.
`pipeline` standardizes the regional layer to GeoParquet, extracts reaches matching the
configured selection, checks downstream closure, and builds and validates the graph.
The metrics command then computes topology, centrality, scaling, and fragmentation.

### 4. Check the generated Parquet and JSON files

Each basin gets its own directory under `datasets/<region>/<artifact_id>/`.

| Relative path | What it contains |
| --- | --- |
| `processed/extracted_network.parquet` | GeoParquet with one row per reach and its line geometry. `HYRIV_ID` identifies the reach, `MAIN_RIV` identifies the basin, and each `NEXT_DOWN` is `0` or points to another reach in the same file. Keep `ORD_STRA`, `LENGTH_KM`, `UPLAND_SKM`, and `DIST_UP_KM` for the scaling and fragmentation calculations. |
| `graphs/river_graph/nodes.parquet` | Node attributes generated from the extracted reach graph for the Node Explorer. The pipeline also writes directed and undirected GraphML. |
| `graphs/river_graph/network_metrics.json` | Generated metrics payload with `river_id`, `river_name`, `computed_at`, and the `metrics` object. The script takes the river ID and name from the configuration. |
| `graphs/river_graph/metadata.json` and `metadata/*.json` | Graph metadata, validation, and provenance from the pipeline stages. |

To add new reach records, update the source layer and rerun the pipeline with `--force`,
then recompute the metrics. This regenerates the basin GeoParquet, the node table, and JSON
from the same source. The river registry is YAML. `network_metrics.json` and
`BUNDLE_MANIFEST.json` are generated outputs and require no schema edits to register a river.

### 5. Verify and package the new basin

Restart Streamlit. Select the new river and check the Overview, Reach Map, Node Explorer,
and saved metrics. If the selector shows **(not extracted yet)**, compare the actual
Parquet location with the paths printed by `river-networks config`.

```sh
python scripts/build_deploy_bundle.py
```

The builder packages configured rivers with extracted Parquet present in `datasets/`.
Keep the existing basins' artifacts available when building a bundle intended to contain them.
Check the build summary and the generated `BUNDLE_MANIFEST.json` for the new river, then
test the ZIP in a clean checkout with the updated `config/rivers.yaml`. If deploying, publish
the ZIP and update `DATA_BUNDLE_URL` as described in [Streamlit Cloud Deployment](#streamlit-cloud-deployment).

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
   - In **Settings → Secrets**, set the bundle URL:
     ```toml
     DATA_BUNDLE_URL = "https://github.com/AbhinavJain27/BTP-Project/releases/download/v3-data_bundle/deploy_bundle.zip"
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
