from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from river_networks.config import get_river, load_rivers, resolve_config

st.set_page_config(page_title="River Networks", layout="wide")

from data_bootstrap import ensure_data

ensure_data()

REQUIRED_REACH_COLUMNS = {
    "HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "HYBAS_ID", "LENGTH_KM", "DIST_DN_KM",
    "DIST_UP_KM", "CATCH_SKM", "UPLAND_SKM", "DIS_AV_CMS", "ENDORHEIC", "ORD_STRA",
    "ORD_CLAS", "ORD_FLOW", "geometry",
}

NODE_TYPE_LABELS = {
    "headwater": "Headwater",
    "confluence/junction": "Confluence / junction",
    "downstream/outlet": "Outlet",
    "intermediate/topology-preserving": "Intermediate",
}
NODE_TYPE_COLORS = {
    "headwater": "#00a6fb",
    "confluence/junction": "#ff7f0e",
    "downstream/outlet": "#d62728",
    "intermediate/topology-preserving": "#9467bd",
}
NODE_TYPE_ORDER = ["downstream/outlet", "confluence/junction", "headwater", "intermediate/topology-preserving"]

COLOR_SCALE = ["#1f77b4", "#2ca02c", "#e6c229", "#ff7f0e", "#d62728", "#9467bd"]

ORDER_COLORS = [
    "#1f77b4",
    "#2ca02c",
    "#ff7f0e",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
    "#333333",
]

def inject_style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f6f7f9; }
        .rn-hero {
            background: #1a2942; border-left: 5px solid #4a6fa5;
            padding: 1.3rem 1.8rem; margin-bottom: 1.2rem;
        }
        .rn-hero h1 { color: #ffffff; margin: 0; font-size: 1.6rem; font-weight: 600; letter-spacing: 0.01em; }
        .rn-hero p { color: #c7d2e0; margin: 0.3rem 0 0 0; font-size: 0.9rem; }
        [data-testid="stMetric"] {
            background: #ffffff; border-radius: 6px; padding: 0.7rem 0.9rem 0.6rem 0.9rem;
            border: 1px solid #dde3ea;
        }
        [data-testid="stMetricLabel"] {
            color: #3c4a5c;
            font-weight: 600;
            font-size: 0.85rem !important;
        }
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] > div {
            color: #1a2942;
            font-size: 1.25rem !important;
            line-height: 1.3 !important;
        }
        section[data-testid="stSidebar"] {
            background: #f0f2f5; border-right: 1px solid #d7dce2;
        }
        section[data-testid="stSidebar"] h3 { color: #1a2942; font-weight: 700; }
        section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] p {
            color: #4a5568;
        }
        .rn-section-title {
            font-size: 1.0rem; font-weight: 700; color: #1a2942; margin: 0.2rem 0 0.6rem 0;
            text-transform: uppercase; letter-spacing: 0.03em;
        }
        .rn-note {
            background: #ffffff; border: 1px solid #d7dce2; border-left: 4px solid #4a6fa5;
            padding: 0.7rem 1rem; border-radius: 4px; font-size: 0.88rem; color: #2c3648;
            margin-bottom: 0.6rem;
        }
        [data-testid="stTabs"] button { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )

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
    }

def load_network_metrics(paths: dict[str, Path]):
    metrics_file = paths.get("graph_metrics")
    if metrics_file and metrics_file.is_file():
        data = read_json(metrics_file)
        if data and "metrics" in data:
            return data["metrics"], None
    return None, "Network metrics not found. Run python scripts/compute_network_metrics.py to generate."

def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {"value": value}
    except Exception as exc:
        return {"_error": f"Could not read {path.name}: {exc}"}

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

@st.cache_data(show_spinner=False)
def _read_graph_nodes(path_str: str, mtime: float) -> pd.DataFrame:
    import igraph as ig

    graph = ig.Graph.Read_GraphML(path_str)
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
    return pd.DataFrame(rows)

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
        import igraph
    except ImportError:
        return None, "igraph is not installed; the node explorer requires the project dependencies."
    if not paths["graph_directed"].is_file():
        return None, "Directed GraphML is missing."
    try:
        stat = paths["graph_directed"].stat()
        return _read_graph_nodes(str(paths["graph_directed"]), stat.st_mtime), None
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

def metric_card(label: str, value: str, help_text: str | None = None):
    st.metric(label, value, help=help_text)

def make_distribution_chart(series: pd.Series, title: str, x_title: str, log_x: bool = False, color: str = "#3282b8"):
    clean = pd.to_numeric(series, errors="coerce").dropna()
    clean = clean[clean >= 0]
    if clean.empty:
        st.info(f"No valid {x_title.lower()} values are available.")
        return

    if log_x and (clean > 0).any():

        positive = clean[clean > 0]
        zero_count = int((clean == 0).sum())
        edges = np.logspace(np.log10(positive.min()), np.log10(positive.max()), 41)
        counts, edges = np.histogram(positive, bins=edges)
        centers = np.sqrt(edges[:-1] * edges[1:])
        widths = edges[1:] - edges[:-1]
        fig = go.Figure(go.Bar(x=centers, y=counts, width=widths, marker_color=color, name=x_title))
        fig.update_xaxes(type="log")
        chart_title = title + (f" ({zero_count:,} zero values excluded)" if zero_count else "")
        fig.update_layout(title=chart_title, height=340, margin=dict(l=10, r=10, t=50, b=10),
                           xaxis_title=x_title, yaxis_title="Reach count", bargap=0.02)
    else:
        fig = go.Figure(go.Histogram(x=clean, nbinsx=40, marker_color=color, name=x_title))
        fig.update_layout(title=title, height=340, margin=dict(l=10, r=10, t=50, b=10),
                           xaxis_title=x_title, yaxis_title="Reach count", bargap=0.03)
    st.plotly_chart(fig, width="stretch")

def make_order_chart(frame: gpd.GeoDataFrame):
    values = pd.to_numeric(frame["ORD_STRA"], errors="coerce").dropna().astype(int)
    counts = values.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index.astype(str), y=counts.values, marker_color="#3282b8"))
    fig.update_layout(title="Strahler stream-order distribution", xaxis_title="ORD_STRA",
                       yaxis_title="Reach count", height=340, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

def make_horton_chart(frame: gpd.GeoDataFrame):
    values = pd.to_numeric(frame["ORD_STRA"], errors="coerce").dropna().astype(int)
    counts = values.value_counts().sort_index()
    if counts.empty:
        st.info("No ORD_STRA values are available.")
        return
    fig = go.Figure(go.Scatter(
        x=counts.index, y=counts.values, mode="lines+markers",
        marker=dict(size=9, color="#e6550d"), line=dict(color="#e6550d", width=2),
    ))
    fig.update_layout(
        title="Horton's law of stream numbers (log scale)",
        xaxis_title="Strahler order", yaxis_title="Reach count (log)",
        yaxis_type="log", height=340, margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption("A roughly straight line indicates a self-similar dendritic network, per Horton's law of stream numbers.")

def make_node_donut(counts: dict[str, int]):
    labels = ["Headwater", "Confluence / junction", "Outlet", "Intermediate"]
    keys = ["headwater", "confluence/junction", "outlet", "intermediate"]
    colors = [NODE_TYPE_COLORS["headwater"], NODE_TYPE_COLORS["confluence/junction"],
              NODE_TYPE_COLORS["downstream/outlet"], NODE_TYPE_COLORS["intermediate/topology-preserving"]]
    values = [counts.get(k, 0) for k in keys]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors),
                            textinfo="label+percent", sort=False))
    fig.update_layout(title="Node-type composition", height=360, margin=dict(l=10, r=10, t=50, b=10),
                       showlegend=False)
    st.plotly_chart(fig, width="stretch")

def make_degree_chart(nodes: pd.DataFrame):
    deg = pd.to_numeric(nodes["in_degree"], errors="coerce").dropna().astype(int)
    counts = deg.value_counts().sort_index()
    labels = [str(d) if d < counts.index.max() or d >= 4 else str(d) for d in counts.index]
    fig = go.Figure(go.Bar(x=[str(d) for d in counts.index], y=counts.values, marker_color="#0f4c75"))
    fig.update_layout(title="Node in-degree distribution (tributaries meeting at a point)",
                       xaxis_title="In-degree", yaxis_title="Node count (log)", yaxis_type="log",
                       height=340, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

def make_hydraulic_geometry_scatter(frame: gpd.GeoDataFrame, max_points: int = 8000):
    data = frame[["UPLAND_SKM", "LENGTH_KM", "ORD_STRA"]].copy()
    data["UPLAND_SKM"] = pd.to_numeric(data["UPLAND_SKM"], errors="coerce")
    data["LENGTH_KM"] = pd.to_numeric(data["LENGTH_KM"], errors="coerce")
    data["ORD_STRA"] = pd.to_numeric(data["ORD_STRA"], errors="coerce")
    data = data.dropna()
    data = data[(data["UPLAND_SKM"] > 0) & (data["LENGTH_KM"] > 0)]
    if data.empty:
        st.info("No valid UPLAND_SKM/LENGTH_KM pairs are available.")
        return
    if len(data) > max_points:
        data = data.sample(max_points, random_state=42)
    fig = go.Figure(go.Scattergl(
        x=data["UPLAND_SKM"], y=data["LENGTH_KM"], mode="markers",
        marker=dict(size=4, color=data["ORD_STRA"], colorscale="Blues", showscale=True,
                    colorbar=dict(title="ORD_STRA"), opacity=0.55),
    ))
    fig.update_layout(
        title="Reach length vs. upstream drainage area (log-log)",
        xaxis_title="Upstream drainage area, UPLAND_SKM (km\u00b2, log)",
        yaxis_title="Reach length, LENGTH_KM (km, log)",
        xaxis_type="log", yaxis_type="log", height=380, margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, width="stretch")
    if len(frame) > max_points:
        st.caption(f"Sampled {max_points:,} of {len(frame):,} reaches for plotting responsiveness.")

def make_endorheic_donut(frame: gpd.GeoDataFrame):
    endorheic = pd.to_numeric(frame["ENDORHEIC"], errors="coerce").eq(1).sum()
    other = len(frame) - endorheic
    fig = go.Figure(go.Pie(
        labels=["Exorheic (drains to ocean)", "Endorheic (internal drainage)"],
        values=[other, endorheic], hole=0.55,
        marker=dict(colors=["#3282b8", "#bdbdbd"]), textinfo="label+percent", sort=False,
    ))
    fig.update_layout(title="Endorheic vs. exorheic reaches", height=340, margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")

def make_network_degree_chart(metrics: dict[str, Any]):
    in_deg = metrics.get("in_degree", {}).get("counts", {})
    tot_deg = metrics.get("degree", {}).get("counts", {})
    all_degrees = sorted(set(int(k) for k in in_deg.keys()) | set(int(k) for k in tot_deg.keys()))
    x_labels = [str(d) for d in all_degrees]
    in_vals = [in_deg.get(str(d), 0) for d in all_degrees]
    tot_vals = [tot_deg.get(str(d), 0) for d in all_degrees]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_labels, y=in_vals, name="In-Degree (tributaries in)", marker_color="#0f4c75"))
    fig.add_trace(go.Bar(x=x_labels, y=tot_vals, name="Total Degree (in + out)", marker_color="#3282b8"))
    fig.update_layout(
        title="Node degree distribution (in-degree vs. total degree)",
        xaxis_title="Degree (k)",
        yaxis_title="Node count (log scale)",
        yaxis_type="log",
        barmode="group",
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")

def make_shortest_path_histogram(metrics: dict[str, Any]):
    hist = metrics.get("shortest_paths_to_outlet", {}).get("histogram", {})
    counts = hist.get("counts", [])
    edges = hist.get("bin_edges", [])
    if not counts or not edges or len(edges) < 2:
        st.info("Shortest path histogram is unavailable.")
        return
    centers = [(edges[i] + edges[i+1]) / 2 for i in range(len(counts))]
    widths = [edges[i+1] - edges[i] for i in range(len(counts))]
    fig = go.Figure(go.Bar(x=centers, y=counts, width=widths, marker_color="#2ca25f", name="Hops to outlet"))
    fig.update_layout(
        title="Shortest path to outlet distribution (downstream hops)",
        xaxis_title="Topological distance to outlet (hops)",
        yaxis_title="Node count",
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        bargap=0.03,
    )
    st.plotly_chart(fig, width="stretch")

def make_betweenness_histogram(metrics: dict[str, Any]):
    bw = metrics.get("centrality_measures", {}).get("betweenness_centrality", {})
    hist = bw.get("histogram", {})
    counts = hist.get("counts", [])
    edges = hist.get("bin_edges", [])
    if not counts or not edges or len(edges) < 2:
        st.info("Betweenness centrality distribution is unavailable.")
        return
    centers = [math.sqrt(max(1e-12, edges[i] * edges[i+1])) for i in range(len(counts))]
    widths = [edges[i+1] - edges[i] for i in range(len(counts))]
    fig = go.Figure(go.Bar(x=centers, y=counts, width=widths, marker_color="#e6550d", name="Betweenness"))
    fig.update_xaxes(type="log")
    fig.update_layout(
        title="Betweenness centrality distribution (flow bottlenecks)",
        xaxis_title="Betweenness centrality (log scale)",
        yaxis_title="Node count",
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        bargap=0.02,
    )
    st.plotly_chart(fig, width="stretch")

def make_pagerank_histogram(metrics: dict[str, Any]):
    pr = metrics.get("centrality_measures", {}).get("pagerank_centrality", {})
    hist = pr.get("histogram", {})
    counts = hist.get("counts", [])
    edges = hist.get("bin_edges", [])
    if not counts or not edges or len(edges) < 2:
        st.info("PageRank centrality distribution is unavailable.")
        return
    centers = [math.sqrt(max(1e-12, edges[i] * edges[i+1])) for i in range(len(counts))]
    widths = [edges[i+1] - edges[i] for i in range(len(counts))]
    fig = go.Figure(go.Bar(x=centers, y=counts, width=widths, marker_color="#8856a7", name="PageRank"))
    fig.update_xaxes(type="log")
    fig.update_layout(
        title="PageRank centrality distribution (downstream flow convergence)",
        xaxis_title="PageRank score (log scale)",
        yaxis_title="Node count",
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        bargap=0.02,
    )
    st.plotly_chart(fig, width="stretch")

def _line_coords(geom) -> list[tuple[float, float]] | None:
    if geom is None or geom.is_empty:
        return None
    parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
    coords: list[tuple[float, float]] = []
    for part in parts:
        part_coords = list(part.coords)
        if len(part_coords) < 2:
            continue
        coords.extend((float(lon), float(lat)) for lon, lat, *_ in part_coords)
    return coords or None

def geometry_map(frame: gpd.GeoDataFrame, max_reaches: int, color_by: str):
    if frame.empty:
        st.info("No reach geometry is available.")
        return
    data = frame.copy()
    data["_metric"] = pd.to_numeric(data[color_by], errors="coerce")

    data = data.sort_values("_metric", ascending=False, na_position="last").head(max_reaches)

    valid_metric = data["_metric"].dropna()
    bin_edges = None
    if not valid_metric.empty:

        bin_edges = sorted(set(valid_metric.quantile([i / len(COLOR_SCALE) for i in range(len(COLOR_SCALE) + 1)]).tolist()))

    metric_label = "Strahler order" if color_by == "ORD_STRA" else "Average discharge (m\u00b3/s)"
    fig = go.Figure()
    total_drawn = 0

    if bin_edges is None or len(bin_edges) < 2:
        lons: list[float | None] = []
        lats: list[float | None] = []
        for geom in data.geometry:
            coords = _line_coords(geom)
            if not coords:
                continue
            for lon, lat in coords:
                lons.append(lon)
                lats.append(lat)
            lons.append(None)
            lats.append(None)
            total_drawn += 1
        if lons:
            fig.add_trace(go.Scattergeo(lon=lons, lat=lats, mode="lines", line=dict(width=1, color=COLOR_SCALE[-1]), hoverinfo="skip", showlegend=False))
    else:
        for i in range(len(bin_edges) - 1):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            is_last = i == len(bin_edges) - 2
            mask = (data["_metric"] >= lo) & (data["_metric"] <= hi if is_last else data["_metric"] < hi)
            band = data[mask]
            if band.empty:
                continue
            lons, lats = [], []
            for geom in band.geometry:
                coords = _line_coords(geom)
                if not coords:
                    continue
                for lon, lat in coords:
                    lons.append(lon)
                    lats.append(lat)
                lons.append(None)
                lats.append(None)
                total_drawn += 1
            if not lons:
                continue
            color = COLOR_SCALE[min(i, len(COLOR_SCALE) - 1)]
            fig.add_trace(go.Scattergeo(
                lon=lons, lat=lats, mode="lines", line=dict(width=1, color=color), hoverinfo="skip",
                name=f"{lo:,.2f} \u2013 {hi:,.2f}",
            ))
        no_metric = data[data["_metric"].isna()]
        lons, lats = [], []
        for geom in no_metric.geometry:
            coords = _line_coords(geom)
            if not coords:
                continue
            for lon, lat in coords:
                lons.append(lon)
                lats.append(lat)
            lons.append(None)
            lats.append(None)
            total_drawn += 1
        if lons:
            fig.add_trace(go.Scattergeo(lon=lons, lat=lats, mode="lines", line=dict(width=1, color="#bdbdbd"), hoverinfo="skip", name="No value"))

    if total_drawn == 0:
        st.info("No drawable LineString/MultiLineString geometries are available.")
        return

    fig.update_geos(fitbounds="locations", visible=False, showcountries=True, showcoastlines=True, showland=True, landcolor="#f4f4f2")
    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(title=metric_label, orientation="h", yanchor="bottom", y=-0.12, x=0),
    )
    st.plotly_chart(fig, width="stretch")
    if total_drawn < len(frame):
        st.caption(f"Showing {total_drawn:,} of {len(frame):,} reaches, prioritized by {metric_label.lower()}. Increase the map limit to show more.")

_ORDER_FIELD_LABELS = {
    "ORD_STRA": "Strahler order",
    "ORD_CLAS": "Order class",
    "ORD_FLOW": "Flow order",
}

def geometry_map_highlight_orders(frame: gpd.GeoDataFrame, max_reaches: int, field: str, selected_values: list[int]):
    field_label = _ORDER_FIELD_LABELS.get(field, field)
    fig = go.Figure()

    minx, miny, maxx, maxy = frame.total_bounds
    fig.add_trace(go.Scattergeo(
        lon=[minx, maxx],
        lat=[miny, maxy],
        mode="markers",
        marker=dict(size=0.1, color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    if not selected_values:
        fig.update_geos(
            fitbounds="locations", visible=False,
            showcountries=True, countrycolor="#b0b8c1",
            showcoastlines=True, coastlinecolor="#94a3b8",
            showland=True, landcolor="#f4f4f2",
            showocean=True, oceancolor="#e2e8f0",
        )
        fig.update_layout(
            height=620, margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Map cleared for {field_label}. Select one or more order numbers above to highlight them.")
        return

    data = frame.copy()
    data["_order"] = pd.to_numeric(data[field], errors="coerce")

    # Sort data deterministically so that any subsample takes the most significant reaches
    # (by discharge, length, then ID) consistently across selections.
    sort_cols = [c for c in ["DIS_AV_CMS", "LENGTH_KM", "HYRIV_ID"] if c in data.columns]

    matches = data[data["_order"].isin(selected_values)]
    other = data[~data["_order"].isin(selected_values)]

    # Background reaches: keep a subtle context layer without overcrowding
    bg_budget = min(1500, max(500, max_reaches // 4))
    if not other.empty:
        if sort_cols:
            other_sample = other.sort_values(sort_cols, ascending=False).head(bg_budget)
        else:
            other_sample = other.head(bg_budget)
    else:
        other_sample = other.iloc[0:0]

    total_context = 0
    lons_other, lats_other = [], []
    for geom in other_sample.geometry:
        coords = _line_coords(geom)
        if not coords:
            continue
        for lon, lat in coords:
            lons_other.append(lon)
            lats_other.append(lat)
        lons_other.append(None)
        lats_other.append(None)
        total_context += 1

    if lons_other:
        fig.add_trace(go.Scattergeo(
            lon=lons_other, lat=lats_other, mode="lines",
            line=dict(width=0.8, color="#b0bec5"),
            hoverinfo="skip",
            name="Other reaches",
            opacity=1.0,
        ))

    # Fair quota allocation across selected orders (water-filling)
    # This guarantees that rare/major orders (like Strahler 9 or Class 1) are NEVER drowned out
    # by massive lower-order sets (like Strahler 1), and that reach subsets are deterministic prefixes.
    sorted_orders = sorted(selected_values)
    order_groups = {}
    for val in sorted_orders:
        grp = matches[matches["_order"] == val]
        if not grp.empty:
            if sort_cols:
                grp = grp.sort_values(sort_cols, ascending=False)
            order_groups[val] = grp

    counts = {v: len(grp) for v, grp in order_groups.items()}
    rem_budget = max_reaches
    active_orders = list(order_groups.keys())
    quotas = {v: 0 for v in active_orders}

    while active_orders and rem_budget > 0:
        fair_share = max(1, rem_budget // len(active_orders))
        finished = []
        for v in active_orders:
            needed = counts[v] - quotas[v]
            if needed <= fair_share:
                quotas[v] += needed
                rem_budget -= needed
                finished.append(v)
            else:
                quotas[v] += fair_share
                rem_budget -= fair_share
        if not finished or rem_budget <= 0:
            break
        for v in finished:
            active_orders.remove(v)

    total_highlight = 0
    for i, val in enumerate(sorted_orders):
        if val not in order_groups:
            continue
        band = order_groups[val].iloc[:quotas[val]]
        if band.empty:
            continue
        lons, lats = [], []
        for geom in band.geometry:
            coords = _line_coords(geom)
            if not coords:
                continue
            for lon, lat in coords:
                lons.append(lon)
                lats.append(lat)
            lons.append(None)
            lats.append(None)
            total_highlight += 1

        if lons:
            color = ORDER_COLORS[i % len(ORDER_COLORS)]
            fig.add_trace(go.Scattergeo(
                lon=lons, lat=lats, mode="lines",
                line=dict(width=2.4, color=color),
                hoverinfo="skip",
                name=f"{field_label} {val}",
                opacity=1.0,
            ))

    fig.update_geos(
        fitbounds="locations", visible=False,
        showcountries=True, countrycolor="#b0b8c1",
        showcoastlines=True, coastlinecolor="#94a3b8",
        showland=True, landcolor="#f4f4f2",
        showocean=True, oceancolor="#e2e8f0",
    )
    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Highlighting {total_highlight:,} reaches across {len(selected_values)} selected {field_label.lower()} "
        f"against {total_context:,} background reaches."
    )

def node_explorer_map(nodes: pd.DataFrame, max_nodes: int, show_types: list[str]):
    sub = nodes[nodes["node_type"].isin(show_types)].dropna(subset=["x", "y"]).copy()
    if sub.empty:
        st.info("No node coordinates are available for the selected node types.")
        return

    sub["degree"] = pd.to_numeric(sub["degree"], errors="coerce").fillna(0)

    if len(sub) <= max_nodes:
        data = sub
    else:

        selected_parts = []
        remaining_budget = max_nodes

        if "downstream/outlet" in show_types:
            outlets = sub[sub["node_type"] == "downstream/outlet"]
            take_outlets = outlets.head(remaining_budget)
            selected_parts.append(take_outlets)
            remaining_budget -= len(take_outlets)

        other_types = [t for t in show_types if t != "downstream/outlet"]
        if other_types and remaining_budget > 0:
            type_dfs = {}
            for t in other_types:
                t_df = sub[sub["node_type"] == t]
                if t == "headwater":

                    type_dfs[t] = t_df.sample(len(t_df), random_state=42)
                else:

                    type_dfs[t] = t_df.sort_values("degree", ascending=False)

            types_left = list(other_types)
            while types_left and remaining_budget > 0:
                quota = max(1, remaining_budget // len(types_left))
                under_quota = [t for t in types_left if len(type_dfs[t]) <= quota]
                if under_quota:
                    for t in under_quota:
                        selected_parts.append(type_dfs[t])
                        remaining_budget -= len(type_dfs[t])
                        types_left.remove(t)
                else:
                    per_type = remaining_budget // len(types_left)
                    remainder = remaining_budget % len(types_left)
                    for idx, t in enumerate(types_left):
                        take_n = min(len(type_dfs[t]), per_type + (1 if idx < remainder else 0))
                        selected_parts.append(type_dfs[t].head(take_n))
                    break

        data = pd.concat(selected_parts, ignore_index=True) if selected_parts else sub.head(max_nodes)

    fig = go.Figure()
    for node_type in NODE_TYPE_ORDER:
        if node_type not in show_types:
            continue
        band = data[data["node_type"] == node_type]
        label = NODE_TYPE_LABELS.get(node_type, node_type)
        if band.empty:

            fig.add_trace(go.Scattergeo(
                lon=[], lat=[], mode="markers", name=label,
                marker=dict(
                    size=7 if node_type in ("downstream/outlet", "confluence/junction") else 5,
                    color=NODE_TYPE_COLORS.get(node_type, "#888888"),
                    line=dict(width=0.6, color="white"),
                    opacity=1.0,
                ),
                showlegend=True,
            ))
            continue

        customdata = band[["node_id", "reach_id", "in_degree", "out_degree", "degree", "y", "x"]].to_numpy()
        fig.add_trace(go.Scattergeo(
            lon=band["x"], lat=band["y"], mode="markers", name=label,
            marker=dict(
                size=7 if node_type in ("downstream/outlet", "confluence/junction") else 5,
                color=NODE_TYPE_COLORS.get(node_type, "#888888"),
                line=dict(width=0.6, color="white"),
                opacity=1.0,
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Reach ID (HYRIV_ID): %{customdata[1]}<br>"
                "Role: " + label + "<br>"
                "In-degree (tributaries in): %{customdata[2]}<br>"
                "Out-degree: %{customdata[3]}<br>"
                "Total degree: %{customdata[4]}<br>"
                "Latitude: %{customdata[5]:.5f}<br>"
                "Longitude: %{customdata[6]:.5f}"
                "<extra></extra>"
            ),
        ))

    fig.update_geos(fitbounds="locations", visible=False, showcountries=True, showcoastlines=True, showland=True, landcolor="#f4f4f2")
    fig.update_layout(
        height=640, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0),
        hoverlabel=dict(bgcolor="white", bordercolor="#0f4c75", font_size=12, align="left"),
    )
    st.plotly_chart(fig, width="stretch")
    if len(data) < len(sub):
        st.caption(f"Showing {len(data):,} of {len(sub):,} matching nodes, balanced across selected roles. Hover any point for its full topological profile.")

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
    st.markdown("### River Networks")
    options = []
    for river_id in river_ids:
        label = rivers[river_id]["display_name"]
        if not availability[river_id]:
            label += " (not extracted yet)"
        options.append((river_id, label))
    selected = st.selectbox("River", options, format_func=lambda x: x[1])
    river_id = selected[0]

river = get_river(river_id)
frame, paths, data_error = load_river_data(river_id)

st.markdown(
    f"""<div class="rn-hero">
    <h1>{river['display_name']} river network</h1>
    <p>Data Taken from HydroRIVERS v1.0 (HydroSHEDS) —
    <a href="https://www.hydrosheds.org/products/hydrorivers">Link to Dataset</a></p>
    </div>""",
    unsafe_allow_html=True,
)

if frame is None:
    st.warning(f"{river['display_name']} is not yet available in the dashboard.")
    st.markdown(
        """<div class="rn-note">No <code>extracted_network.parquet</code> was found for this river.
        The pipeline configuration currently has no verified selection identifier for it, so the
        project intentionally does not fabricate a network. Add the regional HydroRIVERS dataset,
        verify a selection identifier, populate <code>config/rivers.yaml</code>, then run the pipeline.</div>""",
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
max_upland = pd.to_numeric(frame["UPLAND_SKM"], errors="coerce").max()
avg_discharge = pd.to_numeric(frame["DIS_AV_CMS"], errors="coerce").mean()
max_order = pd.to_numeric(frame["ORD_STRA"], errors="coerce").max()
endorheic = pd.to_numeric(frame["ENDORHEIC"], errors="coerce").eq(1).sum()
endorheic_pct = (endorheic / reaches * 100) if reaches else 0

tab_overview, tab_dist, tab_map, tab_nodes, tab_prov = st.tabs(
    ["Overview", "Distributions", "Reach Map", "Node Explorer", "Logs"]
)

with tab_overview:
    st.markdown('<div class="rn-section-title">Hydrology metrics</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        metric_card("Reaches", format_int(reaches),
                    "Total number of river channel segments between two junctions or topological endpoints in the extracted network.")
    with cols[1]:
        metric_card("Total network length", f"{format_number(total_length)} km",
                    "Sum of lengths across all river reaches in the basin, computed directly from reach geometries in kilometers.")
    with cols[2]:
        metric_card("Total catchment area", f"{format_number(catchment)} km\u00b2",
                    "Aggregate local sub-catchment drainage area (sum of CATCH_SKM) contributing runoff directly to the network.")
    with cols[3]:
        metric_card("Average discharge", f"{format_number(avg_discharge)} m\u00b3/s",
                    "Mean long-term naturalized discharge (DIS_AV_CMS) across all river segments in cubic meters per second.")

    cols = st.columns(4)
    with cols[0]:
        metric_card("Max Strahler order", format_int(max_order),
                    "Highest stream order in the basin, reflecting hierarchical branching complexity from headwaters (1) to the main stem.")
    with cols[1]:
        metric_card("Endorheic reaches", f"{format_int(endorheic)} ({endorheic_pct:.2f}%)",
                    "Count and percentage of inland reaches that terminate in interior sinks or depressions without flowing to the ocean.")
    with cols[2]:
        if graph_metadata and "validation" in graph_metadata:
            validation = graph_metadata["validation"]
            valid = validation.get("valid")
            metric_card("Graph health", "VALID" if valid else "INVALID",
                        "Topological validation status checking connectivity, absence of cycles or self-loops, and valid tree structure.")
        else:
            metric_card("Graph health", "Unavailable",
                        "Topological validation status checking connectivity, absence of cycles or self-loops, and valid tree structure.")

    st.markdown('<div class="rn-section-title">Network metrics</div>', unsafe_allow_html=True)
    if net_metrics is None:
        st.warning(net_metrics_error or "Network metrics unavailable.")
    else:
        cols1 = st.columns(4)
        with cols1[0]:
            metric_card("Node count (|V|)", format_int(net_metrics["node_count"]),
                        "Total topological vertices (headwaters, confluences, and outlets) representing junction points in the river graph.")
        with cols1[1]:
            metric_card("Edge count (|E|)", format_int(net_metrics["edge_count"]),
                        "Total directed river reach connections between vertices, representing downstream flow paths in the network.")
        with cols1[2]:
            metric_card("Graph density", f"{net_metrics['density']:.6e}",
                        "Ratio of actual reaches to all possible pairwise connections |E| / (|V|(|V|-1)); near zero for dendritic river trees.")
        with cols1[3]:
            metric_card("Self-loops", format_int(net_metrics["self_loops"]),
                        "Number of edges connecting a node to itself; strictly 0 in a topologically valid river drainage network.")

        cols2 = st.columns(4)
        with cols2[0]:
            metric_card("Directed diameter", f"{format_int(net_metrics['diameter']['directed'])} hops",
                        "Length of the longest downstream directed path from any headwater to an outlet, measured in reach hops.")
        with cols2[1]:
            metric_card("Undirected diameter", f"{format_int(net_metrics['diameter']['undirected'])} hops",
                        "Longest shortest path between any two vertices across the entire basin ignoring flow direction, in reach hops.")
        with cols2[2]:
            metric_card("Avg path length (dir)", f"{net_metrics['average_path_length']['directed']:.2f} hops",
                        "Mean topological distance across all reachable downstream node pairs following directed flow to the outlet.")
        with cols2[3]:
            metric_card("Avg path length (undir)", f"{net_metrics['average_path_length']['undirected']:.2f} hops",
                        "Mean shortest path distance between all connected node pairs in the basin ignoring flow direction.")

        cols3 = st.columns(4)
        in_d = net_metrics["in_degree"]
        out_d = net_metrics["out_degree"]
        tot_d = net_metrics["degree"]
        comp = net_metrics["connected_components"]
        with cols3[0]:
            metric_card("In-degree (max / mean)", f"{in_d['max']} / {in_d['mean']:.2f}",
                        "Number of upstream tributaries entering a junction: 0 for headwaters, 1 for pass-throughs, and 2+ for confluences.")
            st.caption(f"Headwaters (in=0): {format_int(in_d['counts'].get('0', 0))}")
        with cols3[1]:
            metric_card("Out-degree (max / mean)", f"{out_d['max']} / {out_d['mean']:.2f}",
                        "Number of downstream paths leaving a node: 1 for flowing reaches and 0 for terminal basin outlets.")
            st.caption(f"Outlets (out=0): {format_int(out_d['counts'].get('0', 0))}")
        with cols3[2]:
            metric_card("Total degree (max / mean)", f"{tot_d['max']} / {tot_d['mean']:.2f}",
                        "Total incident reaches (tributaries in + channels out) meeting at a vertex, indicating topological junction scale.")
            st.caption(f"Median degree: {tot_d['median']:.0f}")
        with cols3[3]:
            metric_card("Connected components", f"{format_int(comp['weak_count'])} weak / {format_int(comp['strong_count'])} strong",
                        "Count of weakly connected sub-networks and strongly connected components (verifying an acyclic DAG structure).")
            st.caption(f"DAG: {comp['is_dag']} (acyclic flow)")

        cols4 = st.columns(4)
        clust = net_metrics["clustering_coefficient"]
        sp = net_metrics["shortest_paths_to_outlet"]
        cent = net_metrics["centrality_measures"]
        bw = cent["betweenness_centrality"]
        pr = cent["pagerank_centrality"]
        with cols4[0]:
            metric_card("Clustering coefficient", f"{clust['global_transitivity']:.4f}",
                        "Global transitivity measuring closed triangles; strictly 0.0 in dendritic river networks due to tree-like branching.")
            st.caption("Dendritic trees have 0 closed triangles.")
        with cols4[1]:
            metric_card("Shortest paths to outlet", f"{sp['mean_hops']:.1f} hops (avg)",
                        "Average topological distance (in reach hops) required for runoff at any node to travel downstream to the outlet.")
            st.caption(f"Max distance: {format_int(sp['max_hops'])} hops")
        with cols4[2]:
            metric_card("Max betweenness centrality", format_number(bw["max"], 0),
                        "Peak fraction of all network shortest paths passing through a single junction, identifying main flow bottlenecks.")
            st.caption(f"Top node: `{bw['max_node']}`")
        with cols4[3]:
            metric_card("Max PageRank centrality", f"{pr['max']:.4e}",
                        "Highest downstream accumulation score, identifying nodes with the greatest cumulative tributary drainage.")
            st.caption(f"Top node: `{pr['max_node']}`")

    if node_counts:
        st.markdown('<div class="rn-section-title">Graph nodes</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        with cols[0]:
            metric_card("Headwaters", format_int(node_counts["headwater"]),
                        "Originating source vertices of streams where flow begins (in-degree = 0, out-degree = 1).")
        with cols[1]:
            metric_card("Confluences / junctions", format_int(node_counts["confluence/junction"]),
                        "Topological meeting points where two or more upstream tributaries merge into a single channel (in-degree ≥ 2).")
        with cols[2]:
            metric_card("Outlets", format_int(node_counts["outlet"]),
                        "Terminal destination vertices where river flow exits the network into the ocean or an endorheic sink (out-degree = 0).")
        left, right = st.columns(2)
        with left:
            make_node_donut(node_counts)
        with right:
            make_endorheic_donut(frame)
    if nodes_error:
        st.caption(f"Node breakdown unavailable: {nodes_error}")

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
        else:
            st.info("Node-degree distribution requires the directed GraphML artifact.")

    st.markdown('<div class="rn-section-title">Downstream hydraulic geometry</div>', unsafe_allow_html=True)
    make_hydraulic_geometry_scatter(frame)

    st.markdown('<div class="rn-section-title">Network metrics distributions</div>', unsafe_allow_html=True)
    if net_metrics is None:
        st.info(net_metrics_error or "Network metrics distributions unavailable.")
    else:
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

with tab_map:
    st.markdown('<div class="rn-section-title">Reach network map</div>', unsafe_allow_html=True)
    map_row1_col1, map_row1_col2 = st.columns([1, 1])
    with map_row1_col1:
        if reaches <= 500:
            max_reaches = reaches
            st.caption(f"Drawing all {reaches:,} reaches (below the {500:,}-reach slider threshold).")
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
            "Order attribute",
            options=["ORD_STRA", "ORD_CLAS", "ORD_FLOW"],
            format_func=lambda x: _ORDER_FIELD_LABELS.get(x, x),
            key=f"reach_highlight_field_{river_id}",
            help="Click an attribute to highlight; click it again to deselect.",
        )

    selected_order_numbers = []
    if highlight_field:
        with map_row2_col2:
            field_values = sorted(int(v) for v in pd.to_numeric(frame[highlight_field], errors="coerce").dropna().unique())
            selected_str_choices = st.pills(
                f"Select {_ORDER_FIELD_LABELS[highlight_field]} number(s) to highlight",
                options=[str(v) for v in field_values],
                selection_mode="multi",
                key=f"reach_highlight_choice_{river_id}_{highlight_field}",
                help="Click one or more numbers to highlight them on the map in distinct colors. Click again to deselect.",
            )
            if selected_str_choices:
                selected_order_numbers = [int(v) for v in selected_str_choices]

    if highlight_field:
        geometry_map_highlight_orders(frame, max_reaches, highlight_field, selected_order_numbers)
    else:
        geometry_map(frame, max_reaches, color_by)

with tab_nodes:
    st.markdown('<div class="rn-section-title">Node explorer</div>', unsafe_allow_html=True)
    st.caption("Hover any node for its full topological profile: role, in/out-degree, total degree, source reach ID, and coordinates.")
    if nodes is None or nodes.empty:
        st.info(nodes_error or "No graph nodes are available for this river.")
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
                st.caption(f"Drawing all {total_nodes:,} nodes.")
            else:
                node_slider_max = max(500, min(15000, total_nodes))
                max_nodes = st.slider("Maximum nodes drawn", min_value=500, max_value=node_slider_max,
                                       value=min(3000, node_slider_max), step=500)
        if show_types:
            node_explorer_map(nodes, max_nodes, show_types)
        else:
            st.info("Select at least one node role to draw the map.")

with tab_prov:
    st.markdown('<div class="rn-section-title">Logs</div>', unsafe_allow_html=True)
    metadata_panel(paths, river, graph_metadata)

st.caption(" ")
