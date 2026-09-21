from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from river_networks.acquisition.sources import acquire_hydrorivers
from river_networks.config import get_river, validate_river_config, load_rivers
from river_networks.storage.paths import RiverPaths

def check_river(river_id: str) -> bool:
    river = get_river(river_id)
    print(f"\n[{river['display_name']}] ({river_id})")
    ok = True

    try:
        validate_river_config(river_id, require_identifiers=True)
        print("  selection:       OK — verified identifier configured")
    except Exception as exc:
        print(f"  selection:       BLOCKED — {exc}")
        ok = False

    source = acquire_hydrorivers(river_id)
    if source.get("valid"):
        print(f"  regional source: OK — {source['source_path']}")
    else:
        print(f"  regional source: BLOCKED — {source.get('message', 'source unavailable')}")
        print(f"                   Download: {source.get('download_url')}")
        ok = False

    paths = RiverPaths.for_river(river_id)
    extracted = paths.processed / "extracted_network.parquet"
    graph_dir = paths.graphs / "river_graph"
    if extracted.is_file():
        print(f"  extracted data:  READY — {extracted}")
    else:
        print(f"  extracted data:  pending — run pipeline after prerequisites are fixed")
        ok = False
    if (graph_dir / "directed.graphml").is_file() and (graph_dir / "metadata.json").is_file():
        print("  graph artifacts: READY")
    else:
        print("  graph artifacts: pending")
        ok = False
    return ok

def main() -> int:
    parser = argparse.ArgumentParser(description="Check all Phase 1 river prerequisites before running pipelines.")
    parser.add_argument("--river", choices=sorted(load_rivers()), help="Check only one river")
    args = parser.parse_args()
    river_ids = [args.river] if args.river else list(load_rivers())
    results = [check_river(river_id) for river_id in river_ids]
    print("\nPRE-FLIGHT RESULT:", "READY" if all(results) else "ACTION REQUIRED")
    return 0 if all(results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
