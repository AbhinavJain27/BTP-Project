import argparse
import json
import logging
from pathlib import Path

from .acquisition import acquire_hydrorivers
from .config import load_rivers,resolve_config
from .pipeline import run_pipeline
from .preprocessing import extract_configured_river,preprocess_hydrorivers
from .graph.builder import build_river_graph,validate_graph
from .storage.graph import save_graph_artifact
from .storage.paths import RiverPaths

logging.basicConfig(level=logging.INFO,format="%(levelname)s: %(message)s")

def build_parser()->argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="river-networks",description="River network data and graph analytics toolkit")
    subparsers=parser.add_subparsers(dest="command")
    subparsers.add_parser("help",help="show available commands")
    config_parser=subparsers.add_parser("config",help="show resolved river configuration")
    config_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    acquire_parser=subparsers.add_parser("acquire",help="check HydroRIVERS source availability")
    acquire_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    preprocess_parser=subparsers.add_parser("preprocess",help="preprocess HydroRIVERS into GeoParquet")
    preprocess_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    preprocess_parser.add_argument("--force",action="store_true",help="rebuild the cached preprocessing artifact")
    extract_parser=subparsers.add_parser("extract",help="extract a configured river network")
    extract_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    extract_parser.add_argument("--force",action="store_true",help="rebuild the cached extraction artifact")
    graph_parser=subparsers.add_parser("build-graph",help="build a directed river graph")
    graph_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    graph_parser.add_argument("--force",action="store_true",help="rebuild the cached graph artifacts")
    pipeline_parser=subparsers.add_parser("pipeline",help="run the complete Phase 1 pipeline")
    pipeline_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    pipeline_parser.add_argument("--force",action="store_true",help="rebuild all cached pipeline stages")
    export_parser=subparsers.add_parser("export",help="export river network in CSV, GeoJSON, or Parquet format")
    export_parser.add_argument("--river",required=True,choices=sorted(load_rivers()))
    export_parser.add_argument("--format",default="csv",choices=["csv","geojson","parquet","metrics_json"],help="export format")
    return parser

def _processed_output(river_id:str)->Path:
    return RiverPaths.for_river(river_id).regional_processed

def _source_result(river_id:str):
    result=acquire_hydrorivers(river_id)
    if not result["valid"]:
        print(json.dumps(result,indent=2))
        return None
    return result

def main()->int:
    parser=build_parser()
    args=parser.parse_args()
    if args.command=="config":
        print(json.dumps(resolve_config(args.river),indent=2))
        return 0
    if args.command=="acquire":
        result=acquire_hydrorivers(args.river)
        print(json.dumps(result,indent=2))
        return 0 if result["valid"] else 1
    if args.command=="preprocess":
        acquisition=_source_result(args.river)
        if acquisition is None:
            print(f"Expected source location: {acquire_hydrorivers(args.river)['source_path']}")
            return 1
        try:
            if args.force:
                _processed_output(args.river).unlink(missing_ok=True)
            result=preprocess_hydrorivers(Path(acquisition["source_path"]),_processed_output(args.river),acquisition["source_format"],acquisition["source_layer"])
        except (FileNotFoundError,ValueError,RuntimeError) as exc:
            print(f"Preprocessing failed: {exc}")
            return 1
        print(json.dumps(result,indent=2))
        return 0
    if args.command=="extract":
        try:
            if args.force:
                extracted=RiverPaths.for_river(args.river).processed/"extracted_network.parquet"
                extracted.unlink(missing_ok=True)
            result=extract_configured_river(args.river)
        except (FileNotFoundError,ValueError,RuntimeError) as exc:
            print(f"Extraction failed: {exc}")
            return 1
        print(json.dumps(result,indent=2))
        return 0
    if args.command=="build-graph":
        processed_path=RiverPaths.for_river(args.river).processed/"extracted_network.parquet"
        if not processed_path.is_file():
            print(f"Graph construction failed: extracted network not found at {processed_path}. Run 'river-networks extract --river {args.river}' first.")
            return 1
        try:
            if args.force:
                graph_dir=RiverPaths.for_river(args.river).graphs/"river_graph"
                import shutil
                shutil.rmtree(graph_dir,ignore_errors=True)
            import geopandas as gpd
            directed,undirected=build_river_graph(gpd.read_parquet(processed_path))
            validation=validate_graph(directed)
            if not validation["valid"]:
                print(json.dumps(validation,indent=2))
                return 1
            paths=RiverPaths.for_river(args.river)
            result=save_graph_artifact(directed,undirected,paths.graphs/"river_graph",{"river_id":args.river,"river_name":resolve_config(args.river)["river"]["display_name"],"source_dataset":resolve_config(args.river)["river"]["source"]["dataset"],"validation":validation})
            print(json.dumps({"summary":validation,**result},indent=2))
            return 0
        except (ValueError,RuntimeError,ImportError) as exc:
            print(f"Graph construction failed: {exc}")
            return 1
    if args.command=="pipeline":
        try:
            result=run_pipeline(args.river, force=args.force)
        except (FileNotFoundError,ValueError,RuntimeError) as exc:
            print(f"Pipeline failed: {exc}")
            return 1
        for stage in result["stages"]:
            print(f"{stage['stage']}: {stage['status']}")
        print(json.dumps(result,indent=2))
        return 0
    if args.command=="export":
        from .storage import export_river_data
        try:
            result = export_river_data(args.river, output_format=args.format)
            print(json.dumps(result, indent=2))
            return 0
        except Exception as exc:
            print(f"Export failed: {exc}")
            return 1
    if args.command=="help" or args.command is None:
        parser.print_help()
        return 0
    return 1

if __name__=="__main__":
    raise SystemExit(main())
