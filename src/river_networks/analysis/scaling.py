"""Geomorphological and hydrological scaling analysis: Horton, Hack, and Tokunaga statistics."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from scipy import stats

def compute_horton_ratios(frame: pd.DataFrame) -> dict[str, Any]:
    """Computes empirical Horton bifurcation (RB), length (RL), and area (RA) ratios with linear regressions."""
    required = {"ORD_STRA", "LENGTH_KM", "UPLAND_SKM", "HYRIV_ID", "NEXT_DOWN"}
    if not required.issubset(frame.columns):
        return {}

    sub = frame[["ORD_STRA", "LENGTH_KM", "UPLAND_SKM", "HYRIV_ID", "NEXT_DOWN"]].copy()
    sub["ORD_STRA"] = pd.to_numeric(sub["ORD_STRA"], errors="coerce")
    sub["LENGTH_KM"] = pd.to_numeric(sub["LENGTH_KM"], errors="coerce")
    sub["UPLAND_SKM"] = pd.to_numeric(sub["UPLAND_SKM"], errors="coerce")
    sub = sub.dropna(subset=["ORD_STRA"])
    sub["ORD_STRA"] = sub["ORD_STRA"].astype(int)

    order_by_id = sub.set_index("HYRIV_ID")["ORD_STRA"]
    downstream_order = sub["NEXT_DOWN"].map(order_by_id)
    endpoints = sub.loc[downstream_order.ne(sub["ORD_STRA"])]
    counts = endpoints.groupby("ORD_STRA").size()
    orders = sorted(counts.index)
    if len(orders) < 2:
        return {}
    stream_counts = counts.loc[orders].tolist()
    mean_lengths = (sub.groupby("ORD_STRA")["LENGTH_KM"].sum() / counts).loc[orders].tolist()
    mean_areas = endpoints.groupby("ORD_STRA")["UPLAND_SKM"].mean().loc[orders].tolist()

    orders_arr = np.array(orders, dtype=float)
    counts_arr = np.array(stream_counts, dtype=float)
    log_counts = np.log(np.maximum(1.0, counts_arr))

    # Law of stream numbers: log(N_w) = a - w * log(R_B)
    slope_b, intercept_b, r_value_b, _, _ = stats.linregress(orders_arr, log_counts)
    r_b = float(np.exp(-slope_b))
    r2_b = float(r_value_b ** 2)
    fitted_counts = np.exp(intercept_b + slope_b * orders_arr).tolist()

    # Law of stream lengths: log(L_w) = b + w * log(R_L)
    log_lengths = np.log(np.maximum(1e-3, np.array(mean_lengths, dtype=float)))
    slope_l, _, r_value_l, _, _ = stats.linregress(orders_arr, log_lengths)
    r_l = float(np.exp(slope_l))
    r2_l = float(r_value_l ** 2)

    # Law of stream areas: log(A_w) = c + w * log(R_A)
    log_areas = np.log(np.maximum(1e-3, np.array(mean_areas, dtype=float)))
    slope_a, _, r_value_a, _, _ = stats.linregress(orders_arr, log_areas)
    r_a = float(np.exp(slope_a))
    r2_a = float(r_value_a ** 2)

    return {
        "orders": [int(o) for o in orders],
        "stream_counts": [int(c) for c in stream_counts],
        "fitted_counts": [float(f) for f in fitted_counts],
        "mean_lengths_km": [float(l) for l in mean_lengths],
        "mean_areas_skm": [float(a) for a in mean_areas],
        "bifurcation_ratio": r_b,
        "r2_bifurcation": r2_b,
        "length_ratio": r_l,
        "r2_length": r2_l,
        "area_ratio": r_a,
        "r2_area": r2_a,
        "counting_method": "same-order streams ending at a higher order or outlet",
    }

def compute_hack_law(frame: pd.DataFrame, sample_size: int = 5000) -> dict[str, Any]:
    """Computes Hack's law exponent h: L = c * A^h via log-log regression."""
    cols = ["DIST_UP_KM", "UPLAND_SKM"]
    if not all(c in frame.columns for c in cols):
        cols = ["LENGTH_KM", "UPLAND_SKM"]
        if not all(c in frame.columns for c in cols):
            return {}

    sub = frame[cols].dropna().copy()
    sub[cols[0]] = pd.to_numeric(sub[cols[0]], errors="coerce")
    sub[cols[1]] = pd.to_numeric(sub[cols[1]], errors="coerce")
    sub = sub[(sub[cols[0]] > 0) & (sub[cols[1]] > 0)]

    if len(sub) < 10:
        return {}

    population_size = len(sub)
    if len(sub) > sample_size:
        sub = sub.sample(sample_size, random_state=42)

    log_l = np.log(sub[cols[0]].to_numpy())
    log_a = np.log(sub[cols[1]].to_numpy())
    if np.ptp(log_a) == 0:
        return {}

    slope, intercept, r_val, _, std_err = stats.linregress(log_a, log_l)
    return {
        "hack_exponent": float(slope),
        "intercept_c": float(np.exp(intercept)),
        "r2": float(r_val ** 2),
        "std_error": float(std_err),
        "sample_size": len(sub),
        "population_size": population_size,
        "length_field": cols[0],
        "theoretical_benchmark": "h ≈ 0.55 - 0.60 for dendritic basins",
    }

def compute_tokunaga_statistics(frame: pd.DataFrame) -> dict[str, Any]:
    """Calculates Tokunaga side-branching matrix T_{i,j} for stream orders."""
    if "ORD_STRA" not in frame.columns or "NEXT_DOWN" not in frame.columns or "HYRIV_ID" not in frame.columns:
        return {}

    valid = frame.dropna(subset=["ORD_STRA"])
    orders = valid.set_index("HYRIV_ID")["ORD_STRA"].astype(int)
    downstream = valid["NEXT_DOWN"].map(orders)
    upstream = valid["ORD_STRA"].astype(int)
    max_ord = int(orders.max()) if not orders.empty else 1
    if max_ord < 2:
        return {"tokunaga_applicable": False}

    target_stream_counts = upstream[upstream.ne(downstream)].value_counts()
    # Equal-order pairs that initiate the target stream are excluded from side branching.
    incoming = pd.DataFrame({"target": valid["NEXT_DOWN"], "order": upstream})
    highest = incoming.groupby("target")["order"].transform("max")
    highest_count = upstream.eq(highest).groupby(valid["NEXT_DOWN"]).transform("sum")
    forms_target = upstream.eq(highest) & highest_count.ge(2) & downstream.eq(upstream + 1)
    side = upstream.lt(downstream) & ~forms_target
    branch_counts = pd.crosstab(upstream[side], downstream[side])

    t_matrix: dict[str, dict[str, float]] = {}
    totals_by_lag: dict[int, list[tuple[int, int]]] = {}

    for i in range(1, max_ord):
        t_matrix[f"order_{i}"] = {}
        for j in range(i + 1, max_ord + 1):
            denom = int(target_stream_counts.get(j, 0))
            if not denom:
                continue
            count = int(branch_counts.get(j, pd.Series(dtype=int)).get(i, 0))
            ratio = count / denom
            t_matrix[f"order_{i}"][f"to_{j}"] = round(ratio, 3)
            totals_by_lag.setdefault(j - i, []).append((count, denom))

    by_lag = {
        lag: sum(count for count, _ in samples) / sum(denom for _, denom in samples)
        for lag, samples in totals_by_lag.items()
    }
    positive = [(lag, value) for lag, value in by_lag.items() if value > 0]
    k = None
    if len(positive) >= 2:
        lags, values = zip(*positive)
        k = float(np.exp(stats.linregress(lags, np.log(values)).slope))
    return {
        "tokunaga_applicable": True,
        "max_order": max_ord,
        "t_matrix": t_matrix,
        "mean_first_order_branching_T1": by_lag.get(1),
        "branching_ratio_K": k,
        "branching_by_order_difference": by_lag,
    }

def compute_all_scaling_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    """Master helper computing all geomorphological scaling descriptors."""
    return {
        "horton": compute_horton_ratios(frame),
        "hack": compute_hack_law(frame),
        "tokunaga": compute_tokunaga_statistics(frame),
    }
