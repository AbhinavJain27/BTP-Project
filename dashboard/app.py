from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from river_networks.config import get_river, load_rivers, resolve_config
from river_networks.visualization import (
    NODE_TYPE_LABELS,
    NODE_TYPE_ORDER,
    ORDER_FIELD_LABELS,
    geometry_map,
    geometry_map_highlight_orders,
    inject_style,
    make_betweenness_histogram,
    make_comparative_radar_chart,
    make_csi_fragmentation_chart,
    make_degree_chart,
    make_distribution_chart,
    make_endorheic_donut,
    make_horton_chart,
    make_hydraulic_geometry_scatter,
    make_network_degree_chart,
    make_node_donut,
    make_order_chart,
    make_pagerank_histogram,
    make_scaling_regression_chart,
    make_shortest_path_histogram,
    metric_card,
    node_explorer_map,
)

st.set_page_config(page_title="River Networks", layout="wide")

from data_bootstrap import ensure_data

ensure_data()

REQUIRED_REACH_COLUMNS = {
    "HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "HYBAS_ID", "LENGTH_KM", "DIST_DN_KM",
    "DIST_UP_KM", "CATCH_SKM", "UPLAND_SKM", "DIS_AV_CMS", "ENDORHEIC", "ORD_STRA",
    "ORD_CLAS", "ORD_FLOW", "geometry",
}

def river_paths(river_id: str) -> dict[str, Path]:
    resolved = resolve_config(river_id)["paths"]
    root = Path(resolved["river_root"])
    return {
        "river_root": root,
        "extracted": root / "processed" / "extracted_network.parquet",
        "graph_dir": root / "graphs" / "river_graph",
        "graph_directed": root / "graphs" / "river_graph" / "directed.graphml",
        "graph_undirected": root / "graphs" / "river_graph" / "undirected.graphml",
        "graph_metadata": root / "graphs" / "river_graph" / "metadata.json",
        "graph_nodes": root / "graphs" / "river_graph" / "nodes.parquet",
        "graph_metrics": root / "graphs" / "river_graph" / "network_metrics.json",
        "metadata": root / "metadata",
        "exports": root / "exports",
    }

def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {"value": value}
    except Exception as exc:
        return {"_error": f"Could not read {path.name}: {exc}"}

def load_network_metrics(paths: dict[str, Path]):
    metrics_file = paths.get("graph_metrics")
    if metrics_file and metrics_file.is_file():
        data = read_json(metrics_file)
        if data and "metrics" in data:
            return data["metrics"], None
        if data and "node_count" in data:
            return data, None
    return None, "Network metrics not found. Run python scripts/compute_network_metrics.py to generate."

def format_number(value: Any, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "\u2014"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)

def format_int(value: Any) -> str:
    if value is None:
        return "\u2014"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "\u2014"

@st.cache_data(show_spinner=False, max_entries=2)
def _read_reach_parquet(path_str: str, mtime: float) -> gpd.GeoDataFrame:
    return gpd.read_parquet(path_str)

def load_river_data(river_id: str):
    paths = river_paths(river_id)
    if not paths["extracted"].is_file():
        return None, paths, "The extracted GeoParquet does not exist yet."
    try:
        stat = paths["extracted"].stat()
        frame = _read_reach_parquet(str(paths["extracted"]), stat.st_mtime).copy()
    except Exception as exc:
        return None, paths, f"Could not read extracted_network.parquet: {exc}"
    missing = REQUIRED_REACH_COLUMNS - set(frame.columns)
    if missing:
        return None, paths, f"The extracted artifact is missing required columns: {', '.join(sorted(missing))}"
    return frame, paths, None

def load_graph_metadata(paths: dict[str, Path]):
    metadata = read_json(paths["graph_metadata"])
    if metadata is None:
        return None, "Graph metadata.json is missing."
    if "_error" in metadata:
        return None, metadata["_error"]
    return metadata, None

@st.cache_data(show_spinner=False, max_entries=2)
def _read_node_parquet(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)

def load_graph_nodes(paths: dict[str, Path]):
    node_parquet = paths.get("graph_nodes")
    if node_parquet is not None and node_parquet.is_file():
        try:
            stat = node_parquet.stat()
            return _read_node_parquet(str(node_parquet), stat.st_mtime), None
        except Exception as exc:
            return None, f"Could not read nodes.parquet: {exc}"
    try:
        import igraph as ig
    except ImportError:
        return None, "igraph is not installed; the node explorer requires the project dependencies."
    if not paths["graph_directed"].is_file():
        return None, "Directed GraphML is missing."
    try:
        stat = paths["graph_directed"].stat()
        graph = ig.Graph.Read_GraphML(str(paths["graph_directed"]))
        attrs = graph.vs.attributes()
        rows = []
        for v in graph.vs:
            node_id = v["node_id"] if "node_id" in attrs else v.index
            reach_id = str(node_id).split(":", 1)[-1] if ":" in str(node_id) else str(node_id)
            rows.append({
                "node_id": node_id,
                "reach_id": reach_id,
                "node_type": v["node_type"] if "node_type" in attrs else "unknown",
                "in_degree": v["in_degree"] if "in_degree" in attrs else graph.degree(v.index, mode="in"),
                "out_degree": v["out_degree"] if "out_degree" in attrs else graph.degree(v.index, mode="out"),
                "degree": v["degree"] if "degree" in attrs else graph.degree(v.index),
                "x": v["x"] if "x" in attrs else None,
                "y": v["y"] if "y" in attrs else None,
            })
        return pd.DataFrame(rows), None
    except Exception as exc:
        return None, f"Could not read directed GraphML: {exc}"

def node_breakdown(nodes: pd.DataFrame | None) -> dict[str, int]:
    if nodes is None or nodes.empty:
        return {}
    counts = nodes["node_type"].value_counts().to_dict()
    return {
        "headwater": int(counts.get("headwater", 0)),
        "confluence/junction": int(counts.get("confluence/junction", 0)),
        "outlet": int(counts.get("downstream/outlet", 0)),
        "intermediate": int(counts.get("intermediate/topology-preserving", 0)),
    }

def metadata_panel(paths: dict[str, Path], river: dict[str, Any], graph_metadata: dict[str, Any] | None):
    st.write({
        "source_dataset": river.get("source", {}).get("dataset"),
        "provider": river.get("source", {}).get("provider"),
        "version": river.get("source", {}).get("version"),
        "selection": river.get("selection"),
    })
    for stage in ("acquisition", "preprocessing", "extraction", "validation"):
        path = paths["metadata"] / f"{stage}.json"
        payload = read_json(path)
        st.markdown(f"**{stage.title()}** \u2014 `{path}`")
        if payload is None:
            st.caption("Metadata file not present yet.")
        else:
            st.json(payload, expanded=False)
    if graph_metadata:
        st.markdown("**Graph metadata**")
        st.json(graph_metadata, expanded=False)

inject_style()
rivers = load_rivers()
river_ids = list(rivers.keys())

availability: dict[str, bool] = {}
for _rid in river_ids:
    availability[_rid] = river_paths(_rid)["extracted"].is_file()

with st.sidebar:
    st.markdown("### River Networks (Phase 2)")
    options = []
    for _id in river_ids:
        label = rivers[_id]["display_name"]
        if not availability[_id]:
            label += " (not extracted yet)"
        options.append((_id, label))
    selected = st.selectbox("River", options, format_func=lambda x: x[1])
    river_id = selected[0]

river = get_river(river_id)
frame, paths, data_error = load_river_data(river_id)

st.markdown(
    f"""<div class="rn-hero">
    <h1>{river['display_name']} river network</h1>
    <p>HydroSHEDS HydroRIVERS v1.0 Graph Analytics & Intelligent Platform —
    <a href="https://www.hydrosheds.org/products/hydrorivers" target="_blank">HydroSHEDS Source</a></p>
    </div>""",
    unsafe_allow_html=True,
)

if frame is None:
    st.warning(f"{river['display_name']} is not yet extracted in this environment.")
    st.markdown(
        """<div class="rn-note">No <code>extracted_network.parquet</code> found for this river.
        Check that raw regional FileGDB datasets exist under <code>datasets/</code> and run
        <code>river-networks pipeline --river &lt;id&gt;</code> to extract the basin.</div>""",
        unsafe_allow_html=True,
    )
    if data_error:
        st.code(data_error)
    with st.expander("Logs", expanded=False):
        metadata_panel(paths, river, None)
    st.stop()

if data_error:
    st.error(data_error)
    st.stop()

graph_metadata, graph_error = load_graph_metadata(paths)
nodes, nodes_error = load_graph_nodes(paths)
node_counts = node_breakdown(nodes)
net_metrics, net_metrics_error = load_network_metrics(paths)

if graph_metadata is None:
    st.warning(graph_error or "Graph metadata is unavailable.")

reaches = len(frame)
total_length = pd.to_numeric(frame["LENGTH_KM"], errors="coerce").sum()
catchment = pd.to_numeric(frame["CATCH_SKM"], errors="coerce").sum()
avg_discharge = pd.to_numeric(frame["DIS_AV_CMS"], errors="coerce").mean()
max_order = pd.to_numeric(frame["ORD_STRA"], errors="coerce").max()
endorheic = pd.to_numeric(frame["ENDORHEIC"], errors="coerce").eq(1).sum()
endorheic_pct = (endorheic / reaches * 100) if reaches else 0

tab_overview, tab_dist, tab_map, tab_nodes, tab_viewer, tab_compare, tab_prov = st.tabs(
    [
        "Overview",
        "Distributions",
        "Reach Map",
        "Node Explorer",
        "Data Viewer & Export",
        "Cross-Basin Comparison",
        "Logs",
    ]
)

# ----------------- Tab 1: Overview -----------------
with tab_overview:
    st.markdown('<div class="rn-section-title">Hydrology metrics</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        metric_card("Reaches", format_int(reaches), "Total river segments in extracted network.")
    with cols[1]:
        metric_card("Total network length", f"{format_number(total_length)} km", "Sum of lengths across all river reaches.")
    with cols[2]:
        metric_card("Total catchment area", f"{format_number(catchment)} km\u00b2", "Aggregate direct sub-catchment area.")
    with cols[3]:
        metric_card("Average discharge", f"{format_number(avg_discharge)} m\u00b3/s", "Mean naturalized discharge across segments.")

    cols = st.columns(4)
    with cols[0]:
        metric_card("Max Strahler order", format_int(max_order), "Highest stream order in basin.")
    with cols[1]:
        metric_card("Endorheic reaches", f"{format_int(endorheic)} ({endorheic_pct:.2f}%)", "Reaches terminating in inland sinks.")
    with cols[2]:
        val_status = graph_metadata.get("validation", {}).get("valid") if graph_metadata else False
        metric_card("Graph health", "VALID" if val_status else "Unavailable", "Acyclicity, connectivity, and zero self-loops.")

    st.markdown('<div class="rn-section-title">Network metrics</div>', unsafe_allow_html=True)
    if net_metrics is None:
        st.warning(net_metrics_error or "Network metrics unavailable.")
    else:
        cols1 = st.columns(4)
        with cols1[0]:
            metric_card("Node count (|V|)", format_int(net_metrics.get("node_count")), "Total topological junctions & endpoints.")
        with cols1[1]:
            metric_card("Edge count (|E|)", format_int(net_metrics.get("edge_count")), "Directed downstream reaches.")
        with cols1[2]:
            metric_card("Graph density", f"{net_metrics.get('density', 0.0):.6e}", "Graph density |E| / (|V|(|V|-1)).")
        with cols1[3]:
            metric_card("Self-loops", format_int(net_metrics.get("self_loops")), "Strictly 0 in valid drainage trees.")

        cols2 = st.columns(4)
        diam = net_metrics.get("diameter", {})
        with cols2[0]:
            metric_card("Directed diameter", f"{format_int(diam.get('directed'))} hops", "Longest downstream flow path in hops.")
        with cols2[1]:
            metric_card("Undirected diameter", f"{format_int(diam.get('undirected'))} hops", "Longest shortest path in hops.")
        with cols2[2]:
            apl_dir = net_metrics.get("average_path_length", {}).get("directed", 0.0)
            metric_card("Avg path length (dir)", f"{apl_dir:.2f} hops", "Mean distance across directed reachable pairs.")
        with cols2[3]:
            apl_undir = net_metrics.get("average_path_length", {}).get("undirected", 0.0)
            metric_card("Avg path length (undir)", f"{apl_undir:.2f} hops", "Mean undirected shortest path distance.")

        cols3 = st.columns(4)
        cent = net_metrics.get("centrality_measures", {})
        bw = cent.get("betweenness_centrality", {})
        pr = cent.get("pagerank_centrality", {})
        clust = net_metrics.get("clustering_coefficient", {})
        with cols3[0]:
            metric_card("Clustering coefficient", f"{clust.get('global_transitivity', 0.0):.4f}", "Strictly 0.0 in dendritic trees.")
        with cols3[1]:
            sp = net_metrics.get("shortest_paths_to_outlet", {})
            metric_card("Avg hops to outlet", f"{sp.get('mean_hops', 0.0):.1f} hops", "Average travel distance to terminal outlet.")
        with cols3[2]:
            if bw.get("method") == "exact_tree_dp":
                bw_badge = '<span class="rn-badge-exact">EXACT O(V)</span>'
            elif bw.get("exact"):
                bw_badge = '<span class="rn-badge-exact">EXACT</span>'
            elif bw.get("method"):
                bw_badge = '<span class="rn-badge-sampled">HEURISTIC</span>'
            else:
                bw_badge = None
            metric_card("Peak betweenness", format_number(bw.get("max", 0), 0), "Bottleneck node score.", badge=bw_badge)
            st.caption(f"Top node: `{bw.get('max_node', 'N/A')}`")
        with cols3[3]:
            metric_card("Peak PageRank", f"{pr.get('max', 0.0):.4e}", "Downstream tributary accumulation score.")
            st.caption(f"Top node: `{pr.get('max_node', 'N/A')}`")

    if node_counts:
        st.markdown('<div class="rn-section-title">Graph nodes</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        with cols[0]:
            metric_card("Headwaters", format_int(node_counts["headwater"]), "Originating source tips.")
        with cols[1]:
            metric_card("Confluences / junctions", format_int(node_counts["confluence/junction"]), "Tributary meeting points.")
        with cols[2]:
            metric_card("Outlets", format_int(node_counts["outlet"]), "Terminal basin exit points.")
        left, right = st.columns(2)
        with left:
            make_node_donut(node_counts)
        with right:
            make_endorheic_donut(frame)

# ----------------- Tab 2: Distributions -----------------
with tab_dist:
    st.markdown('<div class="rn-section-title">Reach-attribute distributions</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        make_distribution_chart(frame["LENGTH_KM"], "Reach length distribution", "Length (km)", log_x=True, color="#3282b8")
    with right:
        make_distribution_chart(frame["DIS_AV_CMS"], "Average discharge distribution", "DIS_AV_CMS (m\u00b3/s)", log_x=True, color="#0f4c75")

    left, right = st.columns(2)
    with left:
        make_distribution_chart(frame["CATCH_SKM"], "Local catchment area distribution", "CATCH_SKM (km\u00b2)", log_x=True, color="#2ca25f")
    with right:
        make_order_chart(frame)

    left, right = st.columns(2)
    with left:
        make_horton_chart(frame)
    with right:
        if nodes is not None and not nodes.empty:
            make_degree_chart(nodes)

    st.markdown('<div class="rn-section-title">Downstream hydraulic geometry</div>', unsafe_allow_html=True)
    make_hydraulic_geometry_scatter(frame)

    st.markdown('<div class="rn-section-title">Network science distributions</div>', unsafe_allow_html=True)
    if net_metrics is not None:
        dist_col1, dist_col2 = st.columns(2)
        with dist_col1:
            make_network_degree_chart(net_metrics)
        with dist_col2:
            make_shortest_path_histogram(net_metrics)
        dist_col3, dist_col4 = st.columns(2)
        with dist_col3:
            make_betweenness_histogram(net_metrics)
        with dist_col4:
            make_pagerank_histogram(net_metrics)

        # Phase 2 Extension: Geomorphological Scaling & Fragmentation
        scaling_info = net_metrics.get("scaling", {}).get("horton")
        if scaling_info:
            st.markdown('<div class="rn-section-title">Phase 2 Geomorphological Scaling</div>', unsafe_allow_html=True)
            make_scaling_regression_chart(scaling_info)

        frag_info = net_metrics.get("perturbation")
        if frag_info:
            st.markdown('<div class="rn-section-title">Phase 2 Network Robustness & Fragmentation</div>', unsafe_allow_html=True)
            make_csi_fragmentation_chart(frag_info)

# ----------------- Tab 3: Reach Map -----------------
with tab_map:
    st.markdown('<div class="rn-section-title">Reach network map</div>', unsafe_allow_html=True)
    map_row1_col1, map_row1_col2 = st.columns([1, 1])
    with map_row1_col1:
        if reaches <= 500:
            max_reaches = reaches
        else:
            slider_max = max(500, min(20000, reaches))
            max_reaches = st.slider("Maximum reaches drawn", min_value=500, max_value=slider_max,
                                     value=min(5000, slider_max), step=500)
    with map_row1_col2:
        color_by = st.selectbox("Map emphasis", ["ORD_STRA", "DIS_AV_CMS"],
                                 format_func=lambda x: "Strahler order" if x == "ORD_STRA" else "Average discharge")

    st.markdown("**Highlight by order attribute**")
    map_row2_col1, map_row2_col2 = st.columns([1, 1])
    with map_row2_col1:
        highlight_field = st.pills(
            "Order attribute", options=["ORD_STRA", "ORD_CLAS", "ORD_FLOW"],
            format_func=lambda x: ORDER_FIELD_LABELS.get(x, x),
            key=f"reach_highlight_field_{river_id}",
        )

    selected_order_numbers = []
    if highlight_field:
        with map_row2_col2:
            field_values = sorted(int(v) for v in pd.to_numeric(frame[highlight_field], errors="coerce").dropna().unique())
            selected_str_choices = st.pills(
                f"Select {ORDER_FIELD_LABELS[highlight_field]} number(s)",
                options=[str(v) for v in field_values], selection_mode="multi",
                key=f"reach_highlight_choice_{river_id}_{highlight_field}",
            )
            if selected_str_choices:
                selected_order_numbers = [int(v) for v in selected_str_choices]

    if highlight_field:
        geometry_map_highlight_orders(frame, max_reaches, highlight_field, selected_order_numbers)
    else:
        geometry_map(frame, max_reaches, color_by)

# ----------------- Tab 4: Node Explorer -----------------
with tab_nodes:
    st.markdown('<div class="rn-section-title">Node explorer</div>', unsafe_allow_html=True)
    st.caption("Hover any point for full topological profile (in/out-degree, role, coordinates).")
    if nodes is None or nodes.empty:
        st.info(nodes_error or "No graph nodes available.")
    else:
        total_nodes = len(nodes)
        ctrl_col1, ctrl_col2 = st.columns([1, 1])
        with ctrl_col1:
            show_types = st.multiselect(
                "Node roles shown", options=NODE_TYPE_ORDER,
                default=["downstream/outlet", "confluence/junction", "headwater"],
                format_func=lambda t: NODE_TYPE_LABELS.get(t, t),
            )
        with ctrl_col2:
            if total_nodes <= 500:
                max_nodes = total_nodes
            else:
                node_slider_max = max(500, min(15000, total_nodes))
                max_nodes = st.slider("Maximum nodes drawn", min_value=500, max_value=node_slider_max,
                                       value=min(3000, node_slider_max), step=500)
        if show_types:
            node_explorer_map(nodes, max_nodes, show_types)

# ----------------- Tab 5: Data Viewer & Export (Phase 2) -----------------
with tab_viewer:
    st.markdown('<div class="rn-section-title">Data Viewer & Multi-Format Exporter</div>', unsafe_allow_html=True)
    st.caption("Inspect extracted reach attributes, filter by stream order or discharge, and export customized subsets.")

    view_cols = st.multiselect(
        "Columns to view / export",
        options=list(frame.columns),
        default=["HYRIV_ID", "NEXT_DOWN", "ORD_STRA", "LENGTH_KM", "DIS_AV_CMS", "CATCH_SKM", "UPLAND_SKM"],
    )

    col1, col2 = st.columns(2)
    with col1:
        min_ord, max_ord = int(frame["ORD_STRA"].min()), int(frame["ORD_STRA"].max())
        ord_filter = st.slider("Filter by Strahler Order range", min_value=min_ord, max_value=max_ord, value=(min_ord, max_ord))
    with col2:
        max_preview_rows = st.selectbox("Rows in preview", [50, 100, 500, 1000], index=1)

    filtered = frame[(frame["ORD_STRA"] >= ord_filter[0]) & (frame["ORD_STRA"] <= ord_filter[1])]
    if view_cols:
        preview_data = filtered[view_cols].head(max_preview_rows)
        # Drop geometry column from UI dataframe preview for performance
        if "geometry" in preview_data.columns:
            display_df = preview_data.drop(columns=["geometry"])
        else:
            display_df = preview_data
        st.dataframe(display_df, use_container_width=True)
        st.caption(f"Showing {len(display_df):,} of {len(filtered):,} filtered reaches ({reaches:,} total in basin).")

        export_format = st.radio("Export format", ["CSV", "Parquet"], horizontal=True)
        if st.button("Prepare filtered basin download"):
            export = filtered[view_cols]
            if export_format == "CSV":
                if "geometry" in export.columns:
                    export = export.assign(geometry_wkt=export.geometry.to_wkt()).drop(columns=["geometry"])
                data = export.to_csv(index=False).encode("utf-8-sig")
                extension, mime = "csv", "text/csv"
            else:
                data = export.to_parquet(index=False, compression="zstd")
                extension, mime = "parquet", "application/octet-stream"
            st.download_button(
                label=f"Download {export_format} ({len(filtered):,} reaches)",
                data=data,
                file_name=f"{river_id}_reaches.{extension}",
                mime=mime,
            )

# ----------------- Tab 6: Cross-Basin Comparison (Phase 2) -----------------
with tab_compare:
    st.markdown('<div class="rn-section-title">Cross-Basin Benchmark Comparison</div>', unsafe_allow_html=True)
    st.caption("Compare topological efficiency, Horton scaling, and hydrological characteristics across global biomes.")

    benchmark_rows = []
    radar_dict = {}
    for rid, rinfo in sorted(rivers.items()):
        paths_r = river_paths(rid)
        m_r, _ = load_network_metrics(paths_r)
        if m_r:
            d_dir = m_r.get("diameter", {}).get("directed", 0)
            d_undir = m_r.get("diameter", {}).get("undirected", 0)
            e_cnt = m_r.get("edge_count", 0)
            mean_in = m_r.get("in_degree", {}).get("mean", 0.0)
            scale = m_r.get("scaling", {}).get("horton", {})
            r_b = scale.get("bifurcation_ratio")
            hack_exp = m_r.get("scaling", {}).get("hack", {}).get("hack_exponent")

            benchmark_rows.append({
                "Basin": rinfo["display_name"],
                "Region": rinfo["region"].title(),
                "Graph edges (|E|)": e_cnt,
                "Nodes (|V|)": m_r.get("node_count", 0),
                "Dir Diameter": f"{d_dir:,} hops",
                "Undir Diameter": f"{d_undir:,} hops",
                "Mean In-Degree": f"{mean_in:.2f}",
                "Horton R_B": format_number(r_b),
                "Hack Exp (h)": format_number(hack_exp),
            })
            radar_dict[rinfo["display_name"]] = m_r

    if benchmark_rows:
        st.dataframe(pd.DataFrame(benchmark_rows), use_container_width=True)
        if len(radar_dict) >= 2:
            make_comparative_radar_chart(radar_dict)
    else:
        st.info("Cross-basin comparisons require computed network metrics across rivers.")

# ----------------- Tab 7: Logs -----------------
with tab_prov:
    st.markdown('<div class="rn-section-title">Logs & Provenance</div>', unsafe_allow_html=True)
    metadata_panel(paths, river, graph_metadata)

st.caption(" ")
