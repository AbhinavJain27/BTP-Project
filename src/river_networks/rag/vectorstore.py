"""In-process semantic vector and document retrieval store for River Networks documentation and literature."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]

LITERATURE_SNIPPETS = [
    {
        "source": "literature/horton_1945.md",
        "title": "Horton's Laws of Drainage Networks (1945)",
        "content": (
            "Robert E. Horton (1945) established fundamental empirical scaling laws for drainage basins: "
            "1. Law of Stream Numbers: stream counts decrease geometrically with Strahler order with bifurcation ratio R_B ≈ 3.0 - 5.0. "
            "2. Law of Stream Lengths: mean stream length increases geometrically with order with ratio R_L ≈ 1.5 - 3.0. "
            "3. Law of Stream Areas: mean catchment area increases with order with ratio R_A ≈ 3.0 - 6.0. "
            "Networks obeying these laws are statistically self-similar dendritic branching trees."
        ),
    },
    {
        "source": "literature/hack_1957.md",
        "title": "Hack's Law of Stream Length and Drainage Area (1957)",
        "content": (
            "John T. Hack (1957) demonstrated a power-law scaling relationship between main river length L and drainage basin area A: "
            "L = c * A^h, where the scaling exponent h is typically between 0.55 and 0.60. "
            "An exponent h > 0.5 indicates slight elongation of larger basins, departing from perfect geometric similarity (which would predict h = 0.50)."
        ),
    },
    {
        "source": "literature/grill_2019_csi.md",
        "title": "Connectivity Status Index (CSI) & River Fragmentation (Grill et al., 2019)",
        "content": (
            "The Connectivity Status Index (CSI) quantifies the longitudinal, lateral, and temporal connectivity of river systems. "
            "Dams and impoundments act as impassable structural barriers, fragmenting upstream spawning grounds from downstream estuaries. "
            "A river is classified as free-flowing if its CSI exceeds 95% from headwaters to ocean outlet."
        ),
    },
]

class DocumentStore:
    """In-memory semantic and keyword search engine over repository documentation and literature."""

    def __init__(self) -> None:
        self.chunks: list[dict[str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        doc_files = [
            PROJECT_ROOT / "data_dictionary.md",
            PROJECT_ROOT / "docs" / "graph.md",
            PROJECT_ROOT / "docs" / "architecture.md",
            PROJECT_ROOT / "docs" / "extraction.md",
            PROJECT_ROOT / "docs" / "data_model.md",
            PROJECT_ROOT / "docs" / "phase1.md",
        ]

        for p in doc_files:
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8")
            # Chunk by Markdown sections (H1 / H2 headers)
            sections = re.split(r"\n(?=##?\s+)", text)
            for section in sections:
                clean = section.strip()
                if not clean:
                    continue
                first_line = clean.split("\n", 1)[0].replace("#", "").strip()
                self.chunks.append({
                    "source": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "title": first_line,
                    "content": clean,
                })

        for lit in LITERATURE_SNIPPETS:
            self.chunks.append(lit)

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", text.lower()))

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Retrieves most relevant documentation sections for a query using BM25-like scoring."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return self.chunks[:top_k]

        scored = []
        for chunk in self.chunks:
            title_tokens = self._tokenize(chunk["title"])
            content_tokens = self._tokenize(chunk["content"])

            # Match score with higher weight for section title matches
            overlap_title = len(query_tokens & title_tokens)
            overlap_content = len(query_tokens & content_tokens)

            # Cosine-like normalization
            score = (overlap_title * 3.5 + overlap_content) / (math.sqrt(len(content_tokens)) + 1.0)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

_DOC_STORE: DocumentStore | None = None

def get_document_store() -> DocumentStore:
    global _DOC_STORE
    if _DOC_STORE is None:
        _DOC_STORE = DocumentStore()
    return _DOC_STORE

def retrieve_context_chunks(query: str, top_k: int = 3) -> list[dict[str, str]]:
    """Public helper to retrieve semantic documentation chunks for any user question."""
    store = get_document_store()
    return store.search(query, top_k=top_k)
