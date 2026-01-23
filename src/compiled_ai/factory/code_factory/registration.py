"""Auto-registration system for successful activity templates.

This module handles the automatic registration of successfully validated activities
into the template registry for future discovery and reuse.
"""

import ast
import re
from dataclasses import dataclass
from typing import Optional

from .template_registry import ActivityTemplate, TemplateCategory, TemplateRegistry


@dataclass
class RegistrationPolicy:
    """Policy for auto-registration."""

    require_validation: bool = True
    min_success_rate: float = 0.8
    allow_duplicates: bool = False
    max_name_length: int = 50


@dataclass
class RegistrationResult:
    """Result of registration attempt."""

    success: bool
    template_id: str
    message: str
    conflict: Optional[str] = None


class ActivityRegistrar:
    """Handles auto-registration of successful activities."""

    def __init__(
        self, registry: TemplateRegistry, policy: Optional[RegistrationPolicy] = None
    ):
        """Initialize registrar.

        Args:
            registry: TemplateRegistry instance
            policy: Registration policy (uses default if None)
        """
        self.registry = registry
        self.policy = policy or RegistrationPolicy()

    def attempt_registration(
        self,
        name: str,
        source_code: str,
        generation_prompt: str,
        parent_templates: list[str],
        validation_result: dict,
    ) -> RegistrationResult:
        """Attempt to register a successfully generated activity.

        Args:
            name: Activity name
            source_code: Full Python code
            generation_prompt: Prompt that generated it
            parent_templates: Template names used for inspiration
            validation_result: Result from validation pipeline

        Returns:
            Registration result with success status
        """
        # Check policy requirements
        if self.policy.require_validation and not validation_result.get("passed"):
            return RegistrationResult(
                success=False, template_id="", message="Validation failed"
            )

        # Check name length
        if len(name) > self.policy.max_name_length:
            return RegistrationResult(
                success=False,
                template_id="",
                message=f"Activity name too long (max {self.policy.max_name_length})",
            )

        # Check for conflicts
        if not self.policy.allow_duplicates:
            existing = self.registry.get(name)
            if existing:
                return RegistrationResult(
                    success=False,
                    template_id="",
                    message=f"Template '{name}' already exists",
                    conflict=name,
                )

        # Extract metadata and create template
        try:
            template = self._create_template(
                name, source_code, generation_prompt, parent_templates
            )
        except Exception as e:
            return RegistrationResult(
                success=False,
                template_id="",
                message=f"Failed to create template: {str(e)}",
            )

        # Register template
        try:
            template_id = self.registry.register(template)
            return RegistrationResult(
                success=True,
                template_id=template_id,
                message=f"Registered template '{name}'",
            )
        except ValueError as e:
            return RegistrationResult(
                success=False, template_id="", message=str(e), conflict=name
            )

    def _create_template(
        self,
        name: str,
        source_code: str,
        generation_prompt: str,
        parent_templates: list[str],
    ) -> ActivityTemplate:
        """Create template from generated activity.

        Extracts category, tags, and description using heuristics.

        Args:
            name: Activity name
            source_code: Python source code
            generation_prompt: Generation prompt
            parent_templates: Parent template names

        Returns:
            ActivityTemplate instance
        """
        # Extract category (heuristic-based)
        category = self._infer_category(name, source_code, generation_prompt)

        # Extract tags (heuristic-based)
        tags = self._extract_tags(name, source_code, generation_prompt)

        # Extract description from docstring or generate from name/prompt
        description = self._extract_description(source_code, name, generation_prompt)

        return ActivityTemplate(
            name=name,
            category=category,
            tags=tags,
            description=description,
            source_code=source_code.strip(),
            generation_prompt=generation_prompt,
            parent_templates=parent_templates,
            usage_count=0,
            success_rate=1.0,
        )

    def _infer_category(
        self, name: str, source_code: str, generation_prompt: str
    ) -> TemplateCategory:
        """Infer category from name, code, and prompt.

        Args:
            name: Activity name
            source_code: Python source code
            generation_prompt: Generation prompt

        Returns:
            Inferred TemplateCategory
        """
        text = f"{name} {source_code} {generation_prompt}".lower()

        # Check for keywords indicating specific categories
        if any(
            keyword in text
            for keyword in ["llm", "agent", "generate", "extract", "classify", "transform"]
        ):
            return TemplateCategory.LLM

        if any(keyword in text for keyword in ["http", "request", "api", "fetch", "get", "post"]):
            return TemplateCategory.HTTP

        if any(
            keyword in text
            for keyword in ["email", "notification", "send", "alert", "notify"]
        ):
            return TemplateCategory.NOTIFICATION

        if any(
            keyword in text
            for keyword in ["database", "db", "sql", "query", "insert", "update"]
        ):
            return TemplateCategory.DATABASE

        if any(keyword in text for keyword in ["file", "read", "write", "path", "directory"]):
            return TemplateCategory.FILE

        if any(
            keyword in text
            for keyword in ["data", "validate", "transform", "process", "parse"]
        ):
            return TemplateCategory.DATA

        return TemplateCategory.CUSTOM

    def _extract_tags(
        self, name: str, source_code: str, generation_prompt: str
    ) -> list[str]:
        """Extract relevant tags from name, code, and prompt.

        Args:
            name: Activity name
            source_code: Python source code
            generation_prompt: Generation prompt

        Returns:
            List of tags
        """
        tags = set()

        # Add tags from name (split by underscores)
        name_parts = name.lower().split("_")
        tags.update(part for part in name_parts if len(part) > 2)

        # Extract common libraries/patterns from imports
        import_patterns = [
            (r"import requests", "http"),
            (r"from requests", "http"),
            (r"import pydantic", "pydantic"),
            (r"from pydantic", "pydantic"),
            (r"pydantic_ai", "llm"),
            (r"Agent", "agent"),
            (r"BaseModel", "pydantic"),
            (r"import json", "json"),
            (r"from json", "json"),
            (r"\.json\(\)", "json"),
            (r"import asyncio", "async"),
            (r"async def", "async"),
        ]

        for pattern, tag in import_patterns:
            if re.search(pattern, source_code):
                tags.add(tag)

        # Extract keywords from prompt
        prompt_words = re.findall(r"\b[a-z]{4,}\b", generation_prompt.lower())
        relevant_words = [
            w
            for w in prompt_words
            if w
            in {
                "classification",
                "extraction",
                "transformation",
                "validation",
                "notification",
                "processing",
                "generation",
            }
        ]
        tags.update(relevant_words)

        # Limit to most relevant tags
        return sorted(list(tags))[:10]

    def _extract_description(
        self, source_code: str, name: str, generation_prompt: str
    ) -> str:
        """Extract or generate description.

        Args:
            source_code: Python source code
            name: Activity name
            generation_prompt: Generation prompt

        Returns:
            Description string
        """
        # Try to extract from docstring
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        # Return first line of docstring
                        first_line = docstring.split("\n")[0].strip()
                        return first_line
        except:
            pass

        # Fallback: Generate from name and prompt
        # Convert snake_case to human readable
        readable_name = name.replace("_", " ")

        # Try to extract intent from prompt (first sentence)
        if generation_prompt:
            sentences = generation_prompt.split(".")
            if sentences:
                return sentences[0].strip() + "."

        return f"Activity: {readable_name}"
