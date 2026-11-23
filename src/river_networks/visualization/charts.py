"""Plotly-based statistical, distribution, and comparative charts for river networks."""

from __future__ import annotations

import math
from typing import Any
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .styles import NODE_TYPE_COLORS

def metric_card(label: str, value: str, help_text: str | None = None, badge: str | None = None) -> None:
    """Renders a formatted metric card with optional help tooltip and status badge."""
    st.metric(label, value, help=help_text)
    if badge:
        st.markdown(badge, unsafe_allow_html=True)

def make_distribution_chart(
    series: pd.Series, title: str, x_title: str, log_x: bool = False, color: str = "#3282b8"
) -> None:
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
        fig.update_layout(
            title=chart_title, height=340, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title=x_title, yaxis_title="Reach count", bargap=0.02
        )
    else:
        fig = go.Figure(go.Histogram(x=clean, nbinsx=40, marker_color=color, name=x_title))
        fig.update_layout(
            title=title, height=340, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title=x_title, yaxis_title="Reach count", bargap=0.03
        )
    st.plotly_chart(fig, width="stretch")

def make_order_chart(frame: pd.DataFrame) -> None:
    values = pd.to_numeric(frame["ORD_STRA"], errors="coerce").dropna().astype(int)
    counts = values.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index.astype(str), y=counts.values, marker_color="#3282b8"))
    fig.update_layout(
        title="Strahler stream-order distribution", xaxis_title="ORD_STRA",
        yaxis_title="Reach count", height=340, margin=dict(l=10, r=10, t=50, b=10)
    )
    st.plotly_chart(fig, width="stretch")

def make_horton_chart(frame: pd.DataFrame) -> None:
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
    st.caption("A straight line indicates topological self-similarity per Horton's law of stream numbers.")

def make_node_donut(counts: dict[str, int]) -> None:
    labels = ["Headwater", "Confluence / junction", "Outlet", "Intermediate"]
    keys = ["headwater", "confluence/junction", "outlet", "intermediate"]
    colors = [
        NODE_TYPE_COLORS["headwater"], NODE_TYPE_COLORS["confluence/junction"],
        NODE_TYPE_COLORS["downstream/outlet"], NODE_TYPE_COLORS["intermediate/topology-preserving"]
    ]
    values = [counts.get(k, 0) for k in keys]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors),
                           textinfo="label+percent", sort=False))
    fig.update_layout(title="Node-type composition", height=360, margin=dict(l=10, r=10, t=50, b=10),
                      showlegend=False)
    st.plotly_chart(fig, width="stretch")

def make_degree_chart(nodes: pd.DataFrame) -> None:
    deg = pd.to_numeric(nodes["in_degree"], errors="coerce").dropna().astype(int)
    counts = deg.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=[str(d) for d in counts.index], y=counts.values, marker_color="#0f4c75"))
    fig.update_layout(
        title="Node in-degree distribution (tributaries meeting at a point)",
        xaxis_title="In-degree", yaxis_title="Node count (log)", yaxis_type="log",
        height=340, margin=dict(l=10, r=10, t=50, b=10)
    )
    st.plotly_chart(fig, width="stretch")

def make_hydraulic_geometry_scatter(frame: pd.DataFrame, max_points: int = 8000) -> None:
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
        st.caption(f"Sampled {max_points:,} of {len(frame):,} reaches for responsiveness.")

def make_endorheic_donut(frame: pd.DataFrame) -> None:
    endorheic = pd.to_numeric(frame["ENDORHEIC"], errors="coerce").eq(1).sum()
    other = len(frame) - endorheic
    fig = go.Figure(go.Pie(
        labels=["Exorheic (drains to ocean)", "Endorheic (internal drainage)"],
        values=[other, endorheic], hole=0.55,
        marker=dict(colors=["#3282b8", "#bdbdbd"]), textinfo="label+percent", sort=False,
    ))
    fig.update_layout(title="Endorheic vs. exorheic reaches", height=340, margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")

def make_network_degree_chart(metrics: dict[str, Any]) -> None:
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
        xaxis_title="Degree (k)", yaxis_title="Node count (log scale)", yaxis_type="log",
        barmode="group", height=340, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")

def make_shortest_path_histogram(metrics: dict[str, Any]) -> None:
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
        xaxis_title="Topological distance to outlet (hops)", yaxis_title="Node count",
        height=340, margin=dict(l=10, r=10, t=50, b=10), bargap=0.03,
    )
    st.plotly_chart(fig, width="stretch")

def make_betweenness_histogram(metrics: dict[str, Any]) -> None:
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
        xaxis_title="Betweenness centrality (log scale)", yaxis_title="Node count",
        height=340, margin=dict(l=10, r=10, t=50, b=10), bargap=0.02,
    )
    st.plotly_chart(fig, width="stretch")

def make_pagerank_histogram(metrics: dict[str, Any]) -> None:
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
        xaxis_title="PageRank score (log scale)", yaxis_title="Node count",
        height=340, margin=dict(l=10, r=10, t=50, b=10), bargap=0.02,
    )
    st.plotly_chart(fig, width="stretch")

def make_scaling_regression_chart(scaling_data: dict[str, Any]) -> None:
    """Renders empirical Horton ratios (RB, RL, RA) and fitted regression lines."""
    orders = scaling_data.get("orders", [])
    stream_counts = scaling_data.get("stream_counts", [])
    fitted_counts = scaling_data.get("fitted_counts", [])
    r_b = scaling_data.get("bifurcation_ratio")
    r2_b = scaling_data.get("r2_bifurcation")

    if not orders or not stream_counts:
        st.info("Scaling regression data is unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=orders, y=stream_counts, mode="markers", name="Observed Streams",
        marker=dict(size=9, color="#e6550d")
    ))
    if fitted_counts and r_b is not None and r2_b is not None:
        fig.add_trace(go.Scatter(
            x=orders, y=fitted_counts, mode="lines", name=f"Horton Fit (R_B={r_b:.2f}, R\u00b2={r2_b:.3f})",
            line=dict(color="#2ca02c", dash="dash", width=2)
        ))
    fig.update_layout(
        title="Horton's Law of Stream Numbers: Empirical Regression",
        xaxis_title="Strahler Order (\u03c9)", yaxis_title="Number of Streams (log scale)",
        yaxis_type="log", height=360, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, width="stretch")

def make_csi_fragmentation_chart(frag_data: dict[str, Any]) -> None:
    """Plots Connectivity Status Index (CSI) curve under progressive reach removal."""
    fractions = frag_data.get("removed_fraction_pct", [])
    csi_targeted = frag_data.get("csi_targeted_pct", [])
    csi_random = frag_data.get("csi_random_pct", [])

    if not fractions or not csi_targeted:
        st.info("Fragmentation curve data is unavailable.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fractions, y=csi_targeted, mode="lines+markers", name="Targeted reach removal",
        line=dict(color="#d62728", width=2), marker=dict(size=6)
    ))
    if csi_random:
        trials = frag_data.get("random_trials")
        spread = frag_data.get("csi_random_std_pct")
        fig.add_trace(go.Scatter(
            x=fractions, y=csi_random, mode="lines",
            name=f"Random mean ({trials} trials)" if trials else "Random reach removal",
            error_y=dict(array=spread, type="data") if spread else None,
            line=dict(color="#1f77b4", dash="dot", width=2)
        ))
    fig.update_layout(
        title="Network Robustness: Connectivity Status Index (CSI) vs. Disruption",
        xaxis_title="Reaches removed (%)", yaxis_title="Length connected to original outlets (%)",
        height=360, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, width="stretch")

def make_comparative_radar_chart(rivers_metrics: dict[str, dict[str, Any]]) -> None:
    """Compare saved metrics on axes scaled to the largest available basin value."""
    axes = {
        "Directed diameter": lambda m: m.get("diameter", {}).get("directed"),
        "Undirected diameter": lambda m: m.get("diameter", {}).get("undirected"),
        "Graph edges": lambda m: m.get("edge_count"),
        "Mean in-degree": lambda m: m.get("in_degree", {}).get("mean"),
        "Horton bifurcation ratio": lambda m: m.get("scaling", {}).get("horton", {}).get("bifurcation_ratio"),
        "Mean reach discharge": lambda m: m.get("mean_discharge"),
    }
    names = list(rivers_metrics)
    values_by_axis = {}
    for label, lookup in axes.items():
        values = [lookup(metrics) for metrics in rivers_metrics.values()]
        if values and all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
                          for value in values) and max(values) > 0:
            values_by_axis[label] = values
    if len(values_by_axis) < 3:
        st.info("The radar chart needs at least three metrics available for every basin.")
        return
    categories = list(values_by_axis)
    labels = categories + categories[:1]
    maxima = [max(values) for values in values_by_axis.values()]
    fig = go.Figure()
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    for i, name in enumerate(names):
        raw = [values[i] for values in values_by_axis.values()]
        scaled = [100 * value / maximum for value, maximum in zip(raw, maxima)]
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatterpolar(
            r=scaled + scaled[:1], theta=labels, customdata=raw + raw[:1], name=name,
            hovertemplate="%{theta}: %{customdata:,.4g}<br>%{r:.1f}% of maximum",
            line=dict(color=color, width=2), fill="toself", opacity=0.25
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
        showlegend=True, height=450, margin=dict(l=30, r=30, t=40, b=30),
        title="Basin metrics as a percentage of the highest value on each axis"
    )
    st.plotly_chart(fig, width="stretch")
