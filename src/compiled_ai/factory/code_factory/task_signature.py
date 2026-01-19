"""Task signature extraction for workflow caching and reuse."""

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class TaskSignature:
    """
    Immutable task fingerprint for similarity matching.

    A task signature captures the essential characteristics of a task
    to determine if two tasks are similar enough to reuse the same
    compiled workflow.

    Attributes:
        category: Task category extracted from task_id prefix
        prompt_hash: Hash of normalized prompt structure
        io_schema: Serialized input/output schema from context
    """

    category: str
    prompt_hash: str
    io_schema: str

    def __hash__(self) -> int:
        """Enable use as dictionary key."""
        return hash((self.category, self.prompt_hash, self.io_schema))

    def similarity_score(self, other: "TaskSignature") -> float:
        """
        Calculate similarity score between two task signatures.

        Uses weighted scoring:
        - Category match: 50% weight (must be same task type)
        - Prompt structure match: 30% weight (similar logic flow)
        - I/O schema match: 20% weight (compatible interfaces)

        Args:
            other: Another task signature to compare against

        Returns:
            Similarity score between 0.0 (completely different) and
            1.0 (identical)

        Example:
            >>> sig1 = TaskSignature("classification", "abc123", "in:text")
            >>> sig2 = TaskSignature("classification", "abc123", "in:text")
            >>> sig1.similarity_score(sig2)
            1.0
        """
        score = 0.0

        # Category match (50% weight) - exact match required
        if self.category == other.category:
            score += 0.5

        # Prompt hash match (30% weight) - structural similarity
        if self.prompt_hash == other.prompt_hash:
            score += 0.3

        # I/O schema match (20% weight) - interface compatibility
        if self.io_schema == other.io_schema:
            score += 0.2

        return score


class TaskSignatureExtractor:
    """
    Extract task signatures from TaskInput objects.

    The extractor normalizes task characteristics to enable intelligent
    workflow reuse. It extracts category from task_id, normalizes prompts
    to capture structure rather than specific values, and serializes I/O
    schemas for comparison.
    """

    # Configurable threshold for workflow reuse
    REUSE_THRESHOLD: float = 0.7

    @staticmethod
    def extract_category(task_id: str) -> str:
        """
        Extract category from task_id.

        Follows convention: task_id format is "category_XX_instance_YY"
        Example: "classification_01_ticket_001" → "classification"

        Args:
            task_id: Task identifier string

        Returns:
            Category string (lowercased, normalized)

        Examples:
            >>> TaskSignatureExtractor.extract_category("classification_01_ticket_001")
            'classification'
            >>> TaskSignatureExtractor.extract_category("normalization_02")
            'normalization'
            >>> TaskSignatureExtractor.extract_category("my_task")
            'my'
        """
        if not task_id:
            return "unknown"

        # Split on underscore and find first numeric part
        parts = task_id.split("_")
        for i, part in enumerate(parts):
            if part.isdigit():
                # Category is everything before first numeric part
                return "_".join(parts[:i]).lower() if i > 0 else "unknown"

        # Fallback: use first part
        return parts[0].lower() if parts else "unknown"

    @staticmethod
    def normalize_prompt(prompt: str) -> str:
        """
        Normalize prompt to extract structural pattern.

        Removes specific values while preserving structure:
        - Numbers → <NUM>
        - Emails → <EMAIL>
        - URLs → <URL>
        - Quoted strings → <STR>
        - Excessive whitespace → single spaces
        - Case variations → lowercase

        This allows prompts with similar structure but different
        values to be recognized as similar.

        Args:
            prompt: Raw prompt text

        Returns:
            Normalized prompt structure

        Examples:
            >>> TaskSignatureExtractor.normalize_prompt("Classify 123 tickets")
            'classify <NUM> tickets'
            >>> TaskSignatureExtractor.normalize_prompt("Email test@example.com")
            'email <EMAIL>'
        """
        if not prompt:
            return ""

        # Lowercase for consistency
        normalized = prompt.lower()

        # Remove common variable patterns
        normalized = re.sub(r"\b\d+\b", "<NUM>", normalized)  # Numbers
        normalized = re.sub(r"\S+@\S+", "<EMAIL>", normalized)  # Emails
        normalized = re.sub(r"https?://\S+", "<URL>", normalized)  # URLs
        normalized = re.sub(r'"[^"]*"', "<STR>", normalized)  # Quoted strings
        normalized = re.sub(r"'[^']*'", "<STR>", normalized)  # Single quotes

        # Normalize whitespace
        normalized = " ".join(normalized.split())

        return normalized

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """
        Generate deterministic hash of prompt structure.

        Uses SHA256 truncated to 16 characters for compactness.

        Args:
            prompt: Prompt text (should be normalized first)

        Returns:
            16-character hexadecimal hash

        Examples:
            >>> TaskSignatureExtractor.hash_prompt("classify text")
            'a1b2c3d4e5f67890'  # (example output)
        """
        if not prompt:
            return "empty"
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    @staticmethod
    def extract_io_schema(context: dict) -> str:
        """
        Extract I/O schema from task context.

        Creates a serialized representation including schema values.
        For transformation tasks, includes the actual schema structure
        to prevent incorrect workflow reuse across different schemas.

        Args:
            context: Task context dictionary

        Returns:
            Serialized schema string with value hashes for schemas

        Examples:
            >>> TaskSignatureExtractor.extract_io_schema({"text": "...", "categories": []})
            'in:categories,text'
            >>> TaskSignatureExtractor.extract_io_schema({})
            'empty'
        """
        if not context:
            return "empty"

        # Sort keys for deterministic comparison
        keys = sorted(context.keys())
        schema_parts = [f"keys:{','.join(keys)}"]

        # For schema-dependent tasks (transformations), include schema structure
        import json
        for key in keys:
            if "schema" in key.lower():
                # Hash the schema value to distinguish different schemas
                value = context[key]
                if isinstance(value, (dict, list)):
                    schema_str = json.dumps(value, sort_keys=True)
                else:
                    schema_str = str(value)
                schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()[:8]
                schema_parts.append(f"{key}:{schema_hash}")

        return "|".join(schema_parts)

    def extract(self, task_input) -> TaskSignature:
        """
        Extract complete signature from TaskInput.

        Combines category, prompt structure, and I/O schema into an
        immutable signature for caching and similarity comparison.

        Args:
            task_input: TaskInput object with task_id, prompt, context

        Returns:
            Immutable TaskSignature

        Example:
            >>> from compiled_ai.baselines import TaskInput
            >>> task = TaskInput(
            ...     task_id="classification_01_ticket_001",
            ...     prompt="Classify this support ticket",
            ...     context={"ticket_text": "..."}
            ... )
            >>> extractor = TaskSignatureExtractor()
            >>> sig = extractor.extract(task)
            >>> sig.category
            'classification'
        """
        category = self.extract_category(task_input.task_id)
        normalized_prompt = self.normalize_prompt(task_input.prompt)
        prompt_hash = self.hash_prompt(normalized_prompt)
        io_schema = self.extract_io_schema(task_input.context or {})

        return TaskSignature(
            category=category,
            prompt_hash=prompt_hash,
            io_schema=io_schema,
        )
