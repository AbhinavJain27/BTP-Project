from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "dashboard" / "app.py"
BACKUP = PROJECT_ROOT / "dashboard" / "app.py.pre-deploy.bak"

ANCHOR_IMPORT = 'st.set_page_config(page_title="River Networks", layout="wide")'
INSERT_IMPORT = ANCHOR_IMPORT + """

from data_bootstrap import ensure_data  # noqa: E402

# Pulls the data bundle onto the container's disk on first run. No-op locally.
ensure_data()"""

ANCHOR_PATHS = '        "graph_metadata": root / "graphs" / "river_graph" / "metadata.json",'
INSERT_PATHS = (
    ANCHOR_PATHS
    + '\n        "graph_nodes": root / "graphs" / "river_graph" / "nodes.parquet",'
)

ANCHOR_NODES = '''def load_graph_nodes(paths: dict[str, Path]):
    try:
        import igraph  # noqa: F401
    except ImportError:
        return None, "igraph is not installed; the node explorer requires the project dependencies."
    if not paths["graph_directed"].is_file():
        return None, "Directed GraphML is missing."
    try:
        stat = paths["graph_directed"].stat()
        return _read_graph_nodes(str(paths["graph_directed"]), stat.st_mtime), None
    except Exception as exc:
        return None, f"Could not read directed GraphML: {exc}"'''

INSERT_NODES = '''@st.cache_data(show_spinner=False, max_entries=2)
def _read_node_parquet(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)

def load_graph_nodes(paths: dict[str, Path]):
    # Deployed builds ship a precomputed node table; parsing GraphML at runtime is
    # far too memory-hungry for a 2.7 GB container.
    node_parquet = paths.get("graph_nodes")
    if node_parquet is not None and node_parquet.is_file():
        try:
            stat = node_parquet.stat()
            return _read_node_parquet(str(node_parquet), stat.st_mtime), None
        except Exception as exc:
            return None, f"Could not read nodes.parquet: {exc}"
    try:
        import igraph  # noqa: F401
    except ImportError:
        return None, "igraph is not installed; the node explorer requires the project dependencies."
    if not paths["graph_directed"].is_file():
        return None, "Directed GraphML is missing."
    try:
        stat = paths["graph_directed"].stat()
        return _read_graph_nodes(str(paths["graph_directed"]), stat.st_mtime), None
    except Exception as exc:
        return None, f"Could not read directed GraphML: {exc}"'''

ANCHOR_CACHE = '''@st.cache_data(show_spinner=False)
def _read_reach_parquet(path_str: str, mtime: float) -> gpd.GeoDataFrame:'''
INSERT_CACHE = '''@st.cache_data(show_spinner=False, max_entries=2)
def _read_reach_parquet(path_str: str, mtime: float) -> gpd.GeoDataFrame:'''

EDITS = [
    ("bootstrap call", ANCHOR_IMPORT, INSERT_IMPORT),
    ("graph_nodes path", ANCHOR_PATHS, INSERT_PATHS),
    ("nodes.parquet loader", ANCHOR_NODES, INSERT_NODES),
    ("bounded reach cache", ANCHOR_CACHE, INSERT_CACHE),
]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revert", action="store_true", help="Restore app.py from the backup")
    args = parser.parse_args()

    if args.revert:
        if not BACKUP.is_file():
            print("No backup found; nothing to revert.")
            return 1
        shutil.copy2(BACKUP, APP)
        print(f"Restored {APP} from backup.")
        return 0

    if not APP.is_file():
        print(f"Could not find {APP}. Run this from the project root.")
        return 1

    text = APP.read_text(encoding="utf-8")
    if not BACKUP.is_file():
        shutil.copy2(APP, BACKUP)
        print(f"Backed up original to {BACKUP}")

    for label, anchor, replacement in EDITS:
        if replacement in text:
            print(f"  = {label}: already applied")
            continue
        if anchor not in text:
            print(f"  ! {label}: anchor not found -- app.py may have diverged. Apply this edit by hand.")
            continue
        text = text.replace(anchor, replacement, 1)
        print(f"  + {label}: applied")

    APP.write_text(text, encoding="utf-8")
    print(f"\nWrote {APP}. Revert any time with: python scripts/apply_deploy_patches.py --revert")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
