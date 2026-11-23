"""Interactive geographic maps for river reaches and topological graph nodes."""

from __future__ import annotations

from typing import Any
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .styles import (
    COLOR_SCALE,
    NODE_TYPE_COLORS,
    NODE_TYPE_LABELS,
    NODE_TYPE_ORDER,
    ORDER_COLORS,
    ORDER_FIELD_LABELS,
)

def _line_coords(geom: Any) -> list[tuple[float, float]] | None:
    """Extracts sequence of (lon, lat) tuples from a LineString or MultiLineString."""
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

def geometry_map(frame: pd.DataFrame, max_reaches: int, color_by: str) -> None:
    """Renders the global/regional reach map with quantitative color emphasis."""
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
        st.caption(f"Showing {total_drawn:,} of {len(frame):,} reaches, prioritized by {metric_label.lower()}. Increase slider to show more.")

def geometry_map_highlight_orders(
    frame: pd.DataFrame, max_reaches: int, field: str, selected_values: list[int]
) -> None:
    """Renders the reach network with multi-order toggleable highlighting against dull background."""
    field_label = ORDER_FIELD_LABELS.get(field, field)
    fig = go.Figure()

    minx, miny, maxx, maxy = frame.total_bounds
    fig.add_trace(go.Scattergeo(
        lon=[minx, maxx], lat=[miny, maxy], mode="markers",
        marker=dict(size=0.1, color="rgba(0,0,0,0)"), hoverinfo="skip", showlegend=False,
    ))

    if not selected_values:
        fig.update_geos(
            fitbounds="locations", visible=False, showcountries=True, countrycolor="#b0b8c1",
            showcoastlines=True, coastlinecolor="#94a3b8", showland=True, landcolor="#f4f4f2",
            showocean=True, oceancolor="#e2e8f0",
        )
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Map cleared for {field_label}. Select one or more order numbers above to highlight them.")
        return

    data = frame.copy()
    data["_order"] = pd.to_numeric(data[field], errors="coerce")
    sort_cols = [c for c in ["DIS_AV_CMS", "LENGTH_KM", "HYRIV_ID"] if c in data.columns]
    matches = data[data["_order"].isin(selected_values)]
    other = data[~data["_order"].isin(selected_values)]

    bg_budget = min(1500, max(500, max_reaches // 4))
    if not other.empty:
        other_sample = other.sort_values(sort_cols, ascending=False).head(bg_budget) if sort_cols else other.head(bg_budget)
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
            line=dict(width=0.8, color="#b0bec5"), hoverinfo="skip", name="Other reaches", opacity=1.0,
        ))

    sorted_orders = sorted(selected_values)
    order_groups = {}
    for val in sorted_orders:
        grp = matches[matches["_order"] == val]
        if not grp.empty:
            order_groups[val] = grp.sort_values(sort_cols, ascending=False) if sort_cols else grp

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
                lon=lons, lat=lats, mode="lines", line=dict(width=2.4, color=color),
                hoverinfo="skip", name=f"{field_label} {val}", opacity=1.0,
            ))

    fig.update_geos(
        fitbounds="locations", visible=False, showcountries=True, countrycolor="#b0b8c1",
        showcoastlines=True, coastlinecolor="#94a3b8", showland=True, landcolor="#f4f4f2",
        showocean=True, oceancolor="#e2e8f0",
    )
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Highlighting {total_highlight:,} reaches across {len(selected_values)} selected {field_label.lower()} "
        f"against {total_context:,} background reaches."
    )

def node_explorer_map(nodes: pd.DataFrame, max_nodes: int, show_types: list[str]) -> None:
    """Renders topological point map with balanced quota sampling across node roles."""
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
                    color=NODE_TYPE_COLORS.get(node_type, "#888888"), line=dict(width=0.6, color="white"),
                ),
                showlegend=True,
            ))
            continue

        customdata = band[["node_id", "reach_id", "in_degree", "out_degree", "degree", "y", "x"]].to_numpy()
        fig.add_trace(go.Scattergeo(
            lon=band["x"], lat=band["y"], mode="markers", name=label,
            marker=dict(
                size=7 if node_type in ("downstream/outlet", "confluence/junction") else 5,
                color=NODE_TYPE_COLORS.get(node_type, "#888888"), line=dict(width=0.6, color="white"),
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Reach ID (HYRIV_ID): %{customdata[1]}<br>"
                "Role: " + label + "<br>"
                "In-degree: %{customdata[2]}<br>"
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
        st.caption(f"Showing {len(data):,} of {len(sub):,} matching nodes, balanced across selected roles.")
