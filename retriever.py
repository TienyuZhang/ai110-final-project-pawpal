"""
RAG retrieval engine for PawPal+.

Loads pet care knowledge chunks from knowledge_base/*.json and scores them
against a free-text query using weighted keyword overlap.  No external
embedding API is required — retrieval is purely local and deterministic.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Words too common to be useful for scoring
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "can", "its", "it", "this", "that", "as", "by", "from", "up", "about",
    "into", "through", "per", "also", "their", "they", "we", "you", "your",
}


class PetCareRetriever:
    """Load knowledge base chunks and retrieve the most relevant ones for a query."""

    def __init__(self, kb_dir: str | Path | None = None):
        if kb_dir is None:
            kb_dir = Path(__file__).parent / "knowledge_base"
        self.kb_dir = Path(kb_dir)
        self.chunks: list[dict] = []
        self._load()

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Read every *.json file in the knowledge base directory."""
        if not self.kb_dir.exists():
            logger.warning("Knowledge base directory not found: %s", self.kb_dir)
            return
        for path in sorted(self.kb_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                loaded = data if isinstance(data, list) else [data]
                self.chunks.extend(loaded)
                logger.debug("Loaded %d chunks from %s", len(loaded), path.name)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load %s: %s", path.name, exc)
        logger.info("Knowledge base ready: %d chunks total", len(self.chunks))

    # ── Scoring ───────────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase, strip punctuation, remove stop words."""
        tokens = []
        for word in text.lower().split():
            clean = word.strip(".,;:!?()-\"'")
            if clean and clean not in _STOP_WORDS and len(clean) > 1:
                tokens.append(clean)
        return tokens

    def _score(self, chunk: dict, query_tokens: list[str]) -> float:
        """
        Weighted keyword overlap score:
          - Match in explicit keywords list → 2.0 points
          - Match in title                  → 1.5 points
          - Match in content body           → 1.0 points
        """
        if not query_tokens:
            return 0.0

        keyword_tokens = set(self._tokenize(" ".join(chunk.get("keywords", []))))
        title_tokens   = set(self._tokenize(chunk.get("title", "")))
        body_tokens    = set(self._tokenize(chunk.get("content", "")))

        score = 0.0
        for token in query_tokens:
            if token in keyword_tokens:
                score += 2.0
            elif token in title_tokens:
                score += 1.5
            elif token in body_tokens:
                score += 1.0
        return score

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        species: str | None = None,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Return the top-k most relevant chunks for *query*.

        Parameters
        ----------
        query   : free-text search string (e.g. "exercise grooming daily routine")
        species : if provided, restrict to chunks whose 'species' field matches
                  this value or 'all'
        top_k   : maximum number of chunks to return

        Returns
        -------
        List of chunk dicts sorted by descending relevance score.
        If no chunk scores above zero, returns the top-k unfiltered chunks
        so the caller always gets something useful.
        """
        if not self.chunks:
            logger.warning("Retriever has no chunks loaded.")
            return []

        # Optional species filter
        candidates = [
            c for c in self.chunks
            if species is None or c.get("species") in (species, "all")
        ]
        if not candidates:
            candidates = self.chunks  # fall back to everything

        query_tokens = self._tokenize(query)
        scored = [(chunk, self._score(chunk, query_tokens)) for chunk in candidates]
        scored.sort(key=lambda x: -x[1])

        top = [chunk for chunk, score in scored[:top_k] if score > 0]
        if not top:
            # No keyword overlap — return highest-scoring regardless
            top = [chunk for chunk, _ in scored[:top_k]]

        logger.info(
            "Retrieved %d chunks for query %r (species=%s): %s",
            len(top),
            query[:60],
            species,
            [c.get("id") for c in top],
        )
        return top

    def retrieve_by_category(self, category: str, species: str | None = None) -> list[dict]:
        """Return all chunks matching a specific care category."""
        return [
            c for c in self.chunks
            if c.get("category") == category
            and (species is None or c.get("species") in (species, "all"))
        ]

    def all_categories(self, species: str | None = None) -> list[str]:
        """Return the distinct care categories available for a species."""
        return sorted({
            c["category"] for c in self.chunks
            if species is None or c.get("species") in (species, "all")
        })
