"""RAG package for River Networks: structured tools, document vector store, and synthesis agent."""

from .agent import answer_river_query
from .tools import (
    compare_basins,
    get_perturbation_metrics,
    get_scaling_metrics,
    get_topological_metrics,
    list_available_rivers,
)
from .vectorstore import retrieve_context_chunks

__all__ = [
    "answer_river_query",
    "get_topological_metrics",
    "get_scaling_metrics",
    "get_perturbation_metrics",
    "compare_basins",
    "list_available_rivers",
    "retrieve_context_chunks",
]
