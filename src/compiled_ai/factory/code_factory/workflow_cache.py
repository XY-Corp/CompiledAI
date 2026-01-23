"""Workflow cache management with LRU eviction and similarity-based reuse."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import logging

from .task_signature import TaskSignature, TaskSignatureExtractor
from .factory import FactoryResult

logger = logging.getLogger(__name__)


@dataclass
class CachedWorkflow:
    """
    Compiled workflow with metadata for cache management.

    Tracks reuse statistics and timestamps to enable LRU eviction
    and performance analysis.

    Attributes:
        signature: Task signature this workflow was compiled for
        factory_result: Compiled workflow and activities
        compiled_at: Timestamp when workflow was first compiled
        reuse_count: Number of times this workflow has been reused
        last_used: Timestamp of most recent use
    """

    signature: TaskSignature
    factory_result: FactoryResult
    compiled_at: datetime
    reuse_count: int = 0
    last_used: datetime = field(default_factory=datetime.now)

    def record_reuse(self) -> None:
        """Update reuse statistics after cache hit."""
        self.reuse_count += 1
        self.last_used = datetime.now()


class WorkflowCacheManager:
    """
    Manage compiled workflow cache with intelligent reuse.

    Features:
    - Exact match lookup for cache hits (O(1))
    - Similarity-based fallback for related tasks (O(n))
    - LRU eviction when cache reaches capacity
    - Reuse statistics tracking for analysis

    The cache enables "compile once, execute many" by storing compiled
    workflows and reusing them for similar tasks based on task signatures.

    Example:
        >>> cache = WorkflowCacheManager(max_cache_size=50)
        >>> cache.put(signature1, compiled_workflow)
        >>> cached = cache.get(signature2)  # Exact match
        >>> if not cached:
        ...     cached = cache.find_similar(signature2, threshold=0.7)
    """

    def __init__(self, max_cache_size: int = 50):
        """
        Initialize workflow cache manager.

        Args:
            max_cache_size: Maximum number of workflows to cache.
                When limit is reached, least recently used workflow
                is evicted.

        Example:
            >>> cache = WorkflowCacheManager(max_cache_size=100)
        """
        self._cache: Dict[TaskSignature, CachedWorkflow] = {}
        self._max_size = max_cache_size

    def get(self, signature: TaskSignature) -> Optional[CachedWorkflow]:
        """
        Get exact match from cache.

        Args:
            signature: Task signature to look up

        Returns:
            Cached workflow if exact match exists, None otherwise

        Example:
            >>> cached = cache.get(signature)
            >>> if cached:
            ...     print(f"Cache hit! Reused {cached.reuse_count} times")
        """
        cached = self._cache.get(signature)
        if cached:
            cached.record_reuse()
            logger.debug(
                f"Cache HIT: {signature.category} (reused {cached.reuse_count} times)"
            )
        return cached

    def find_similar(
        self,
        signature: TaskSignature,
        threshold: float = TaskSignatureExtractor.REUSE_THRESHOLD,
    ) -> Optional[CachedWorkflow]:
        """
        Find most similar workflow above similarity threshold.

        Searches all cached workflows and returns the one with highest
        similarity score, if it exceeds the threshold.

        Args:
            signature: Task signature to match
            threshold: Minimum similarity score (0.0-1.0) for reuse.
                Default is 0.7 (70% similar)

        Returns:
            Most similar cached workflow if similarity >= threshold,
            None otherwise

        Example:
            >>> # Task is 80% similar to cached workflow
            >>> cached = cache.find_similar(signature, threshold=0.7)
            >>> if cached:
            ...     print(f"Using similar workflow: {cached.signature.category}")
        """
        best_match: Optional[CachedWorkflow] = None
        best_score = 0.0

        for cached_sig, cached_wf in self._cache.items():
            score = signature.similarity_score(cached_sig)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = cached_wf

        if best_match:
            best_match.record_reuse()
            logger.info(
                f"Cache SIMILAR: {signature.category} → {best_match.signature.category} "
                f"(similarity: {best_score:.2f}, reused {best_match.reuse_count} times)"
            )
        else:
            logger.debug(
                f"Cache MISS: {signature.category} (no similar workflow found)"
            )

        return best_match

    def put(self, signature: TaskSignature, result: FactoryResult) -> None:
        """
        Add compiled workflow to cache.

        If cache is at capacity, evicts least recently used workflow
        before adding new one.

        Args:
            signature: Task signature for this workflow
            result: Compiled workflow from CodeFactory

        Example:
            >>> cache.put(signature, factory_result)
        """
        # Evict LRU if cache full
        if len(self._cache) >= self._max_size:
            self._evict_lru()

        cached = CachedWorkflow(
            signature=signature, factory_result=result, compiled_at=datetime.now()
        )
        self._cache[signature] = cached

        logger.info(
            f"Cache ADD: {signature.category} "
            f"(workflow: {result.plan.name}, activities: {len(result.plan.activities)})"
        )

    def _evict_lru(self) -> None:
        """
        Evict least recently used workflow from cache.

        Internal method called automatically when cache reaches capacity.
        """
        if not self._cache:
            return

        # Find LRU entry
        lru_sig = min(self._cache.keys(), key=lambda s: self._cache[s].last_used)
        evicted = self._cache.pop(lru_sig)

        logger.warning(
            f"Cache EVICT: {evicted.signature.category} "
            f"(last used: {evicted.last_used}, reused {evicted.reuse_count} times)"
        )

    def get_statistics(self) -> Dict:
        """
        Get cache statistics for analysis.

        Returns:
            Dictionary with cache metrics:
            - cache_size: Current number of cached workflows
            - max_size: Maximum cache capacity
            - total_reuses: Sum of all reuse counts
            - workflows: List of cached workflows with details

        Example:
            >>> stats = cache.get_statistics()
            >>> print(f"Cache utilization: {stats['cache_size']}/{stats['max_size']}")
            >>> print(f"Total reuses: {stats['total_reuses']}")
        """
        if not self._cache:
            return {"cache_size": 0, "max_size": self._max_size, "workflows": []}

        workflows = []
        for sig, cached in self._cache.items():
            workflows.append(
                {
                    "category": sig.category,
                    "workflow_name": cached.factory_result.plan.name,
                    "compiled_at": cached.compiled_at.isoformat(),
                    "reuse_count": cached.reuse_count,
                    "last_used": cached.last_used.isoformat(),
                }
            )

        return {
            "cache_size": len(self._cache),
            "max_size": self._max_size,
            "total_reuses": sum(w["reuse_count"] for w in workflows),
            "workflows": workflows,
        }
