"""Semantic search for activity discovery using embeddings and tree-based indexing.

This module provides efficient semantic search over activity templates using:
- Sentence embeddings (all-MiniLM-L6-v2) for semantic representation
- Ball Tree for O(log n) nearest neighbor search
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
import json
import numpy as np

if TYPE_CHECKING:
    from .template_registry import ActivityTemplate


# Lazy loading to avoid import overhead when not using semantic search
_model = None
_tree_impl = None


def _get_embedding_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: Fast, small (80MB), good quality
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_ball_tree():
    """Lazy load BallTree implementation."""
    global _tree_impl
    if _tree_impl is None:
        from sklearn.neighbors import BallTree
        _tree_impl = BallTree
    return _tree_impl


@dataclass
class SemanticSearchResult:
    """Result from semantic search with similarity score."""

    template_name: str
    similarity: float  # Cosine similarity (0 to 1)
    distance: float    # Tree distance (lower = more similar)

    def __lt__(self, other: "SemanticSearchResult") -> bool:
        """Compare by similarity for sorting."""
        return self.similarity < other.similarity


class SemanticActivityIndex:
    """Tree-based semantic index for efficient activity search.

    Uses sentence embeddings and Ball Tree for O(log n) nearest neighbor queries.
    Supports incremental updates and persistence.

    Example:
        >>> index = SemanticActivityIndex()
        >>> index.add_activity("parse_address", "Parse address into components", ["text", "extraction"])
        >>> index.add_activity("normalize_address", "Normalize and validate address", ["data", "normalization"])
        >>> results = index.search("extract address parts", k=5)
        >>> print(results[0].template_name)  # "parse_address" - semantically similar
    """

    def __init__(self, cache_path: Path | str | None = None):
        """Initialize the semantic index.

        Args:
            cache_path: Optional path to cache embeddings (speeds up subsequent loads)
        """
        self.cache_path = Path(cache_path) if cache_path else None

        # Activity data
        self._activities: dict[str, dict] = {}  # name -> {description, tags, embedding}

        # Tree index (rebuilt when activities change)
        self._tree = None
        self._tree_names: list[str] = []  # Maps tree indices to activity names
        self._embeddings_matrix: np.ndarray | None = None

        # Track if tree needs rebuild
        self._dirty = False

        # Load from cache if available
        if self.cache_path and self.cache_path.exists():
            self._load_cache()

    def add_activity(
        self,
        name: str,
        description: str,
        tags: list[str],
        source_code: str = "",
    ) -> None:
        """Add an activity to the index.

        Args:
            name: Unique activity name
            description: Natural language description
            tags: List of tags/keywords
            source_code: Optional source code (used for richer embeddings)
        """
        # Create rich text for embedding: name + description + tags
        embed_text = self._create_embed_text(name, description, tags, source_code)

        # Generate embedding
        model = _get_embedding_model()
        embedding = model.encode(embed_text, normalize_embeddings=True)

        self._activities[name] = {
            "description": description,
            "tags": tags,
            "embedding": embedding,
        }

        self._dirty = True

    def add_activities_batch(
        self,
        activities: list[tuple[str, str, list[str], str]],
    ) -> None:
        """Add multiple activities efficiently (batched embedding computation).

        Args:
            activities: List of (name, description, tags, source_code) tuples
        """
        if not activities:
            return

        # Create embed texts
        embed_texts = [
            self._create_embed_text(name, desc, tags, code)
            for name, desc, tags, code in activities
        ]

        # Batch encode (much faster than one-by-one)
        model = _get_embedding_model()
        embeddings = model.encode(embed_texts, normalize_embeddings=True, show_progress_bar=False)

        # Store activities
        for i, (name, desc, tags, _) in enumerate(activities):
            self._activities[name] = {
                "description": desc,
                "tags": tags,
                "embedding": embeddings[i],
            }

        self._dirty = True

    def remove_activity(self, name: str) -> bool:
        """Remove an activity from the index.

        Args:
            name: Activity name to remove

        Returns:
            True if removed, False if not found
        """
        if name in self._activities:
            del self._activities[name]
            self._dirty = True
            return True
        return False

    def search(self, query: str, k: int = 5) -> list[SemanticSearchResult]:
        """Find semantically similar activities.

        Uses Ball Tree for efficient O(log n) nearest neighbor search.

        Args:
            query: Natural language query (e.g., "extract address parts")
            k: Number of results to return

        Returns:
            List of SemanticSearchResult sorted by similarity (highest first)
        """
        if not self._activities:
            return []

        # Rebuild tree if needed
        if self._dirty or self._tree is None:
            self._rebuild_tree()

        # Embed the query
        model = _get_embedding_model()
        query_embedding = model.encode(query, normalize_embeddings=True)

        # Query the tree
        k = min(k, len(self._activities))
        distances, indices = self._tree.query([query_embedding], k=k)

        # Convert to results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            name = self._tree_names[idx]
            # Convert angular distance to cosine similarity
            # Ball tree uses Euclidean distance on normalized vectors
            # cosine_sim = 1 - (euclidean_dist^2 / 2)
            similarity = 1.0 - (dist ** 2 / 2)
            results.append(SemanticSearchResult(
                template_name=name,
                similarity=float(similarity),
                distance=float(dist),
            ))

        # Sort by similarity (highest first)
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results

    def get_embedding(self, name: str) -> np.ndarray | None:
        """Get the embedding vector for an activity.

        Args:
            name: Activity name

        Returns:
            Embedding vector if found, None otherwise
        """
        if name in self._activities:
            return self._activities[name]["embedding"]
        return None

    def save_cache(self) -> None:
        """Save embeddings to cache file for faster subsequent loads."""
        if not self.cache_path:
            return

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert embeddings to lists for JSON serialization
        cache_data = {
            "version": "1.0",
            "activities": {
                name: {
                    "description": data["description"],
                    "tags": data["tags"],
                    "embedding": data["embedding"].tolist(),
                }
                for name, data in self._activities.items()
            },
        }

        with open(self.cache_path, "w") as f:
            json.dump(cache_data, f)

    def _load_cache(self) -> None:
        """Load embeddings from cache file."""
        if not self.cache_path or not self.cache_path.exists():
            return

        try:
            with open(self.cache_path) as f:
                cache_data = json.load(f)

            for name, data in cache_data.get("activities", {}).items():
                self._activities[name] = {
                    "description": data["description"],
                    "tags": data["tags"],
                    "embedding": np.array(data["embedding"], dtype=np.float32),
                }

            self._dirty = True  # Need to rebuild tree

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load semantic cache: {e}")

    def _rebuild_tree(self) -> None:
        """Rebuild the Ball Tree index from current activities."""
        if not self._activities:
            self._tree = None
            self._tree_names = []
            self._embeddings_matrix = None
            self._dirty = False
            return

        # Build embeddings matrix
        self._tree_names = list(self._activities.keys())
        self._embeddings_matrix = np.array([
            self._activities[name]["embedding"]
            for name in self._tree_names
        ], dtype=np.float32)

        # Build Ball Tree
        BallTree = _get_ball_tree()
        self._tree = BallTree(self._embeddings_matrix, metric="euclidean")

        self._dirty = False

    def _create_embed_text(
        self,
        name: str,
        description: str,
        tags: list[str],
        source_code: str = "",
    ) -> str:
        """Create rich text for embedding from activity metadata.

        Combines name, description, and tags into a single text that
        captures the semantic meaning of the activity.
        """
        parts = [
            # Name (snake_case to words)
            name.replace("_", " "),
            # Description
            description,
            # Tags as context
            f"tags: {', '.join(tags)}" if tags else "",
        ]

        # Optionally include code comments/docstrings for richer semantics
        if source_code:
            # Extract just docstring if present (first triple-quoted string)
            import re
            docstring_match = re.search(r'"""(.+?)"""', source_code, re.DOTALL)
            if docstring_match:
                parts.append(docstring_match.group(1).strip()[:200])

        return " ".join(p for p in parts if p)

    def __len__(self) -> int:
        """Return number of indexed activities."""
        return len(self._activities)

    def __contains__(self, name: str) -> bool:
        """Check if activity is in index."""
        return name in self._activities
