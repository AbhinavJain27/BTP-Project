"""Visual styling constants, CSS injections, and color maps for River Networks."""

from __future__ import annotations
import streamlit as st

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

NODE_TYPE_ORDER = [
    "downstream/outlet",
    "confluence/junction",
    "headwater",
    "intermediate/topology-preserving",
]

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

ORDER_FIELD_LABELS = {
    "ORD_STRA": "Strahler order",
    "ORD_CLAS": "Order class",
    "ORD_FLOW": "Flow order",
}

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
        .rn-badge-exact {
            display: inline-block; background: #e6f4ea; color: #137333;
            padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;
            border: 1px solid #ceead6;
        }
        .rn-badge-sampled {
            display: inline-block; background: #fef7e0; color: #b06000;
            padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;
            border: 1px solid #feefc3;
        }
        .rn-badge-fact {
            display: inline-block; background: #e8f0fe; color: #1a73e8;
            padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;
            border: 1px solid #d2e3fc;
        }
        [data-testid="stTabs"] button { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )
