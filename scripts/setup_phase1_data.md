# Phase 1 data setup

There are two separate prerequisites for a river to produce artifacts.

## 1. Put the regional HydroRIVERS File Geodatabase in the configured raw directory

The project intentionally does not commit or silently download large source datasets.
The configured sources are:

| Region | Rivers | Expected `.gdb` directory | Download URL |
|---|---|---|---|
| Asia | Ganga, Yamuna, Yangtze | `datasets/india/raw/HydroRIVERS_v10_as.gdb` | `https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as.gdb.zip` |
| South America | Amazon | `datasets/global/raw/HydroRIVERS_v10_sa.gdb` | `https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_sa.gdb.zip` |
| North/Central America | Mississippi | `datasets/global/raw/HydroRIVERS_v10_na.gdb` | `https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_na.gdb.zip` |
| Africa | Nile | `datasets/global/raw/HydroRIVERS_v10_af.gdb` | `https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_af.gdb.zip` |

Download each ZIP from HydroSHEDS, extract it, and ensure the directory name and configured layer match `config/paths.yaml`.

Verify each source with:

```bash
river-networks acquire --river ganga
river-networks acquire --river yamuna
river-networks acquire --river amazon
river-networks acquire --river mississippi
river-networks acquire --river nile
river-networks acquire --river yangtze
```

## 2. Verify and populate selection identifiers

Do not guess these values. `MAIN_RIV` is the ID of the most downstream reach of a connected HydroRIVERS basin, so it can select a broader connected network than a named river. For a narrower named-river artifact, use a verified `HYRIV_ID` upstream trace or `HYBAS_ID` selection as appropriate.

For each river, inspect the corresponding regional HydroRIVERS table and determine the intended scope. Then populate exactly one of:

```yaml
selection:
  method: main_riv
  main_riv_ids: [VERIFIED_ID]
  hyriv_ids: []
  hybas_ids: []
```

or:

```yaml
selection:
  method: hyriv_ids
  main_riv_ids: []
  hyriv_ids: [VERIFIED_ID_1, VERIFIED_ID_2]
  hybas_ids: []
```

or:

```yaml
selection:
  method: hybas_ids
  main_riv_ids: []
  hyriv_ids: []
  hybas_ids: [VERIFIED_ID]
```

The current repository intentionally leaves Yamuna, Amazon, Mississippi, Nile, and Yangtze empty rather than fabricating identifiers.

## 3. Run the pipeline

After a source and verified selection are present:

```bash
river-networks pipeline --river ganga --force
```

Repeat for each configured river. `--force` is useful after changing selection configuration or replacing a regional source.

## 4. Start the dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard will show a river as `data not extracted yet` until its real GeoParquet exists.
