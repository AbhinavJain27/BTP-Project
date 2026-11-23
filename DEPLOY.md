# Deploying the River Networks dashboard

## Build and verify locally

From the repository root, install the project and its runtime dependencies. Use
the extracted data under `datasets/`, or start with the published
[v3-data_bundle release](https://github.com/AbhinavJain27/BTP-Project/releases/tag/v3-data_bundle).
The published ZIP is about 55 MB and contains the updated six-basin metrics.

Run these commands after changing metrics:

```bash
python scripts/compute_network_metrics.py --force
python scripts/build_deploy_bundle.py
```

The metrics script accepts extracted basin Parquet. The dashboard bundle contains
each basin's reach Parquet, node Parquet, saved metrics, and available provenance.
The bundler reuses existing node Parquet or converts directed GraphML if needed.
Raw regional File Geodatabases and regional Parquet remain pipeline inputs.

Test the new ZIP with a clean data directory. Check that every configured basin
opens and that the overview, reach map, node explorer, provenance, comparison,
and saved analysis charts display. In the Data Viewer, prepare and verify CSV
and Parquet downloads, including a full Amazon export. Check memory on Amazon
and after switching between basins.

## Publish when ready

Attach the tested `deploy_bundle.zip` to a GitHub release. Deploy the repository
with `dashboard/app.py` as the main file, and set `DATA_BUNDLE_URL` in the app's
Streamlit secrets to the direct download URL for that release. The Phase 2
configuration uses:

```toml
DATA_BUNDLE_URL = "https://github.com/AbhinavJain27/BTP-Project/releases/download/v3-data_bundle/deploy_bundle.zip"
```

The bootstrap downloads the ZIP on first run when local basin files are absent.
After changing the URL, test a clean deployment so a previously unpacked bundle
cannot mask a bad URL or missing artifact. Keep credentials in Streamlit secrets.
