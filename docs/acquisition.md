# Data Acquisition

HydroRIVERS v1.0 is produced by the [HydroSHEDS](https://www.hydrosheds.org/products/hydrorivers) project and distributed as regional File Geodatabases (`.gdb`).

---

## 1. Regional Sources & Mapping

The pipeline maps each configured river to its continental regional source via [`config/paths.yaml`](file:///d:/BTP-abhinav/river-networks-phase1-complete/config/paths.yaml) and [`config/rivers.yaml`](file:///d:/BTP-abhinav/river-networks-phase1-complete/config/rivers.yaml):

| Continent / Region | File Geodatabase | Layer Name | Rivers |
|---|---|---|---|
| **Asia** | `HydroRIVERS_v10_as.gdb` | `HydroRIVERS_v10_as` | Ganga, Godavari, Krishna, Yangtze |
| **South America** | `HydroRIVERS_v10_sa.gdb` | `HydroRIVERS_v10_sa` | Amazon |
| **Africa** | `HydroRIVERS_v10_af.gdb` | `HydroRIVERS_v10_af` | Nile |

---

## 2. Acquisition Command

To inspect the acquisition requirements for any river:

```bash
river-networks acquire --river godavari
```

The command checks:
- Whether the expected raw File Geodatabase directory exists under `datasets/raw/`.
- Whether the configured layer is present and can be opened with Pyogrio/GeoPandas.
- Whether the required HydroRIVERS columns are accessible from a one-row test read.
- Emits a structured report and saves `metadata/acquisition.json`.

---

## 3. External Data Storage Policy

- **No Raw Data in Git**: Raw `.gdb` directories and large intermediate regional files exceed GitHub file limits and are excluded via `.gitignore`.
- **Reproducible Downloads**: Official download links are tracked in `config/paths.yaml`. Download archives once into `datasets/raw/`; the pipeline handles all subsequent extractions and graph builds reproducibly.
