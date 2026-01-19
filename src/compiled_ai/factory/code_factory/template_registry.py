"""Template registry with hybrid search for activity discovery.

This module provides a searchable registry of activity templates that can be used
by the planner agent to find similar activities and adapt them for new tasks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re

from .builtin_activities import BUILTIN_TEMPLATES


class TemplateCategory(str, Enum):
    """Categories for organizing activity templates."""

    LLM = "llm"  # LLM-based activities
    HTTP = "http"  # HTTP requests
    DATA = "data"  # Data processing
    NOTIFICATION = "notification"  # Email, SMS, etc.
    DATABASE = "database"  # DB operations
    FILE = "file"  # File I/O
    CUSTOM = "custom"  # Custom generated


@dataclass
class ActivityTemplate:
    """Searchable activity template with metadata."""

    name: str
    category: TemplateCategory
    tags: list[str]
    description: str
    source_code: str

    # Lineage tracking
    generation_prompt: Optional[str] = None
    parent_templates: list[str] = field(default_factory=list)

    # Usage tracking
    usage_count: int = 0
    success_rate: float = 1.0

    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1

    def update_success_rate(self, success: bool) -> None:
        """Update success rate with new result."""
        # Weighted average with decay (recent results matter more)
        weight = 0.3
        if success:
            self.success_rate = self.success_rate * (1 - weight) + weight
        else:
            self.success_rate = self.success_rate * (1 - weight)


@dataclass
class SearchResult:
    """Template search result with relevance score."""

    template: ActivityTemplate
    score: float
    match_type: str  # "keyword", "category", "tag", "name"

    def __lt__(self, other: "SearchResult") -> bool:
        """Compare by score for sorting."""
        return self.score < other.score


class TemplateRegistry:
    """Searchable registry of activity templates.

    Features:
    - Hybrid search (keyword + category + tag matching)
    - Auto-registration of successful generations
    - Template lineage tracking
    - Usage statistics
    """

    def __init__(self):
        """Initialize registry and load built-in templates."""
        self._templates: dict[str, ActivityTemplate] = {}
        self._load_builtin_templates()

    def search(
        self,
        query: str,
        category: Optional[TemplateCategory] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Hybrid search for similar templates.

        Uses a combination of:
        - Exact name matching (highest priority)
        - Tag matching
        - Category filtering
        - Keyword matching in description and code

        Args:
            query: Natural language description
            category: Optional category filter
            limit: Max results to return

        Returns:
            Ranked list of matching templates
        """
        query_lower = query.lower()
        query_words = self._extract_keywords(query_lower)

        results = []

        for template in self._templates.values():
            # Skip if category filter doesn't match
            if category and template.category != category:
                continue

            score = 0.0
            match_types = []

            # 1. Exact name match (highest priority)
            if query_lower == template.name.lower():
                score += 10.0
                match_types.append("name_exact")

            # 2. Name substring match
            if query_lower in template.name.lower() or template.name.lower() in query_lower:
                score += 5.0
                match_types.append("name")

            # 3. Tag matching
            template_tags_lower = [tag.lower() for tag in template.tags]
            for word in query_words:
                if any(word in tag for tag in template_tags_lower):
                    score += 3.0
                    match_types.append("tag")
                    break

            # 4. Category match (if no filter, bonus for matching category)
            if not category:
                if template.category.value in query_lower:
                    score += 2.0
                    match_types.append("category")

            # 5. Description keyword matching
            desc_lower = template.description.lower()
            desc_matches = sum(1 for word in query_words if word in desc_lower)
            if desc_matches > 0:
                score += desc_matches * 1.0
                match_types.append("keyword")

            # 6. Code keyword matching (lower weight)
            code_lower = template.source_code.lower()
            code_matches = sum(1 for word in query_words if word in code_lower)
            if code_matches > 0:
                score += code_matches * 0.5
                match_types.append("keyword")

            # 7. Usage bonus (popular templates get small boost)
            if template.usage_count > 0:
                score += min(template.usage_count * 0.1, 2.0)

            # 8. Success rate bonus
            score += template.success_rate * 0.5

            if score > 0:
                match_type = match_types[0] if match_types else "keyword"
                results.append(SearchResult(template, score, match_type))

        # Sort by score descending and return top N
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def register(self, template: ActivityTemplate) -> str:
        """Register a new template.

        Args:
            template: ActivityTemplate to register

        Returns:
            Template name (used as ID)

        Raises:
            ValueError: If template with same name already exists
        """
        if template.name in self._templates:
            raise ValueError(f"Template '{template.name}' already exists")

        self._templates[template.name] = template
        return template.name

    def get(self, name: str) -> Optional[ActivityTemplate]:
        """Get template by name.

        Args:
            name: Template name

        Returns:
            ActivityTemplate if found, None otherwise
        """
        return self._templates.get(name)

    def list_all(self, category: Optional[TemplateCategory] = None) -> list[ActivityTemplate]:
        """List all templates, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of templates
        """
        if category:
            return [t for t in self._templates.values() if t.category == category]
        return list(self._templates.values())

    def remove(self, name: str) -> bool:
        """Remove a template by name.

        Args:
            name: Template name

        Returns:
            True if removed, False if not found
        """
        if name in self._templates:
            del self._templates[name]
            return True
        return False

    def _load_builtin_templates(self) -> None:
        """Load built-in activity templates."""
        for template_dict in BUILTIN_TEMPLATES:
            template = ActivityTemplate(
                name=template_dict["name"],
                category=TemplateCategory(template_dict["category"]),
                tags=template_dict["tags"],
                description=template_dict["description"],
                source_code=template_dict["source_code"],
            )
            self._templates[template.name] = template

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text.

        Removes common stop words and short words.

        Args:
            text: Input text

        Returns:
            List of keywords
        """
        # Simple stop words list
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "will",
            "with",
        }

        # Extract words (alphanumeric + underscores)
        words = re.findall(r"\b[a-z0-9_]+\b", text.lower())

        # Filter out stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords
