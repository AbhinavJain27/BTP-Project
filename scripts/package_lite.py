from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from river_networks.config import load_rivers
from river_networks.storage.paths import RiverPaths

def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="drive_package", help="Destination folder (default: drive_package)")
    parser.add_argument("--include-graphs", action="store_true", help="Also copy the .graphml graph artifacts")
    parser.add_argument("--zip", action="store_true", help="Also create <output>.zip when done")
    args = parser.parse_args()

    output_root = (PROJECT_ROOT / args.output).resolve()
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    rivers = load_rivers()
    total_copied = 0
    total_skipped_graph = 0
    rows: list[tuple[str, str]] = []

    for river_id, river in sorted(rivers.items()):
        paths = RiverPaths.for_river(river_id)
        extracted = paths.processed / "extracted_network.parquet"
        if not extracted.is_file():
            rows.append((river["display_name"], "not extracted yet -- skipped"))
            continue

        dest_root = output_root / Path(river["output_location"])
        (dest_root / "processed").mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted, dest_root / "processed" / "extracted_network.parquet")
        copied_size = extracted.stat().st_size

        if paths.metadata.is_dir():
            dest_meta = dest_root / "metadata"
            dest_meta.mkdir(parents=True, exist_ok=True)
            for f in paths.metadata.glob("*.json"):
                shutil.copy2(f, dest_meta / f.name)
                copied_size += f.stat().st_size

        graph_dir = paths.graphs / "river_graph"
        if args.include_graphs and graph_dir.is_dir():
            dest_graph = dest_root / "graphs" / "river_graph"
            dest_graph.mkdir(parents=True, exist_ok=True)
            for f in graph_dir.glob("*"):
                shutil.copy2(f, dest_graph / f.name)
                copied_size += f.stat().st_size
        elif graph_dir.is_dir():
            total_skipped_graph += dir_size(graph_dir)

        total_copied += copied_size
        rows.append((river["display_name"], human_size(copied_size)))

    print(f"Copied into: {output_root}")
    print()
    for name, size in rows:
        print(f"  {name:<12} {size}")
    print()
    print(f"Total copied: {human_size(total_copied)}")
    if not args.include_graphs and total_skipped_graph:
        print(f"Skipped .graphml artifacts (regenerate with 'river-networks build-graph --river <id>'): {human_size(total_skipped_graph)} left out")

    if args.zip:
        zip_path = shutil.make_archive(str(output_root), "zip", root_dir=output_root)
        print(f"\nZipped to: {zip_path} ({human_size(Path(zip_path).stat().st_size)})")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
