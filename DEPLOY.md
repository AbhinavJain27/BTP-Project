# Deploying the River Networks dashboard to Streamlit Community Cloud

## The constraint you're working against

Streamlit Community Cloud gives each app, as of the currently published limits:

| Resource | Limit |
|---|---|
| Memory | 690 MB minimum, **2.7 GB maximum** |
| CPU | 0.078–2 cores |
| Disk | 50 GB |
| Hibernation | after 12 h with no traffic |

So the 6 GB is not one problem, it's two:

- **Disk is fine.** 50 GB comfortably holds 6 GB. Disk is not why you'd fail.
- **RAM is the wall, and GitHub is the other wall.** GitHub rejects any file over 100 MB, so the data cannot live in the repo regardless of size.

The good news is that your dashboard never needs the 6 GB. Reading `dashboard/app.py`, the only artifacts it touches per river are:

- `processed/extracted_network.parquet`
- `graphs/river_graph/metadata.json` and `directed.graphml`
- `metadata/*.json`

The continental HydroRIVERS `.gdb` sources and `HydroRIVERS_v10_*.parquet` files are pipeline inputs only. They're the bulk of your 6 GB and none of it is needed at runtime.

## The shape of the deployment

```
GitHub repo  (code only, ~300 KB)  ->  Streamlit Cloud builds container
GitHub Release asset (data bundle) ->  downloaded to container disk on first run
```

## Step 1 — Drop the kit into your project

From your project root:

```bash
cp deploy-kit/scripts/build_deploy_bundle.py   scripts/
cp deploy-kit/scripts/apply_deploy_patches.py  scripts/
cp deploy-kit/dashboard/data_bootstrap.py      dashboard/
cp -r deploy-kit/.streamlit                    .
cp deploy-kit/requirements.txt                 requirements.txt
cat deploy-kit/gitignore-additions.txt >>      .gitignore
```

Note that this replaces `requirements.txt` with a leaner deploy-only list. Your original is preserved in `pyproject.toml` if you need it back.

## Step 2 — Patch the app

```bash
python scripts/apply_deploy_patches.py
```

This makes four idempotent edits to `dashboard/app.py`, backing up the original to `dashboard/app.py.pre-deploy.bak` first:

1. Calls `ensure_data()` right after `st.set_page_config`, so the container fetches data before any path check runs.
2. Teaches `load_graph_nodes()` to read a precomputed `nodes.parquet`, falling back to GraphML parsing when it isn't there.
3. Adds the matching path key.
4. Bounds `_read_reach_parquet`'s cache to `max_entries=2`.

Edit 2 matters most. Right now the node explorer calls `ig.Graph.Read_GraphML()` and builds a Python dict per vertex. On an Amazon-scale network that will run out of memory inside a 2.7 GB container. Precomputing the identical table offline and shipping parquet removes the heaviest runtime operation entirely.

Edit 4 matters because with an unbounded cache, a visitor clicking through all six rivers holds six full GeoDataFrames resident at once. The app also calls `.copy()` on the cached frame, so each river is briefly resident twice.

Revert anytime with `python scripts/apply_deploy_patches.py --revert`.

## Step 3 — Build the data bundle

On your local machine, where the full `datasets/` tree lives:

```bash
python scripts/build_deploy_bundle.py --max-mb 400
```

This prunes each reach table to the fourteen columns the dashboard requires, downcasts the numerics, converts each `directed.graphml` to a compact `nodes.parquet`, re-compresses with zstd, and writes `deploy_bundle.zip`. It prints before/after sizes per river, so you'll see exactly where the weight is.

If it's still too big, tighten in this order:

```bash
# ~100 m tolerance; map fidelity drops, all metrics unaffected
python scripts/build_deploy_bundle.py --simplify 0.001

# ~200 m
python scripts/build_deploy_bundle.py --simplify 0.002
```

Simplification rewrites stored coordinates. Every headline metric in the dashboard — reach counts, `LENGTH_KM`, `CATCH_SKM`, `UPLAND_SKM`, `DIS_AV_CMS`, stream order, node types — comes from columns or the graph, not from geometry, so those stay exact. Only the drawn map changes. Given your README's stance on not fabricating metrics, it's worth adding a caption noting the deployed geometry is simplified if you use this.

If you're still over budget, cut rivers rather than fidelity: comment some out of `config/rivers.yaml` for the deployed build. The app already handles a river having no artifacts.

## Step 4 — Push the code

```bash
git init            # if not already a repo
git add -A
git commit -m "Add cloud deployment kit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Confirm nothing large slipped in:

```bash
git ls-files | xargs -I{} du -h {} 2>/dev/null | sort -rh | head -10
```

Everything should be kilobytes. Your `.gitignore` already excludes `*.parquet`, `*.graphml` and `*.json`, which is why the data stays out — but it also means if you ever *do* want to commit something in those formats you'll need `git add -f`.

## Step 5 — Host the bundle as a GitHub Release

In your repo on GitHub: **Releases → Create a new release**, tag it `data-v1`, attach `deploy_bundle.zip`, publish. Copy the asset's download URL:

```
https://github.com/<you>/<repo>/releases/download/data-v1/deploy_bundle.zip
```

Release assets allow up to 2 GB each and don't count against repo size. Prefer this over Google Drive. Drive serves an HTML confirmation interstitial for large files and enforces an anonymous download quota — when you hit it, your app just stops booting with no useful error. If you must use Drive, share the file as "Anyone with the link", uncomment `gdown` in `requirements.txt`, and set `DATA_BUNDLE_GDRIVE_ID` instead of `DATA_BUNDLE_URL`.

## Step 6 — Deploy

Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, click **Create app**, then:

- Repository: `<you>/<repo>`
- Branch: `main`
- **Main file path: `dashboard/app.py`**

Before clicking Deploy, open **Advanced settings → Secrets** and paste:

```toml
DATA_BUNDLE_URL = "https://github.com/<you>/<repo>/releases/download/data-v1/deploy_bundle.zip"
```

Then deploy. Your URL will be `https://<name>.streamlit.app`.

First boot takes a few minutes: it installs the wheels, then downloads and unpacks the bundle with a progress indicator. Subsequent loads are fast until the container hibernates after 12 h idle, at which point the next visitor triggers one more download.

## Step 7 — Verify

Open **Manage app** (bottom right) for live logs. Check each river renders, the map draws, and the node explorer works. Watch memory in the logs while clicking between rivers.

## If it fails

**"Error installing requirements"** — geopandas and shapely ship manylinux wheels, so no `packages.txt` should be needed. If a wheel is missing for the resolved Python version, pin `python_version = "3.11"` in your Streamlit app's advanced settings.

**"🤯 This app has gone over its resource limits"** — RAM, essentially always. Rebuild the bundle with `--simplify`, lower the map's default reach cap in `app.py`, or reduce `max_entries` to 1.

**App boots but every river says "not extracted yet"** — the bundle's internal layout is wrong. Unzipped into `datasets/`, it must produce `datasets/india/ganga/processed/extracted_network.parquet`. Check with `unzip -l deploy_bundle.zip | head`.

**Download fails on every boot** — the URL isn't publicly reachable. Test it with `curl -IL "<url>"` from a machine that isn't logged into GitHub.

## One thing I couldn't verify

This container has no network access, so I could only syntax-check the patched `app.py` and confirm every patch anchor matches your actual source — I couldn't install Streamlit and run it. Do a local run before pushing:

```bash
streamlit run dashboard/app.py
```

With your full `datasets/` present, `ensure_data()` detects local data and skips the download, so this exercises the patched code path without touching the network.

## If you outgrow the free tier

Streamlit grants increased resources for educational, nonprofit and open-source projects — given this is a HydroSHEDS benchmark toolkit, it's a reasonable application to make. Look for the "good for the world" resource request form in the Community Cloud docs. If that doesn't pan out, the same repo runs unchanged on Hugging Face Spaces (16 GB RAM on the free CPU tier) with just a Dockerfile or a `streamlit` SDK config.
