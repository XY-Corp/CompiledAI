"""Structured output models for PydanticAI agents."""

from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


class ActivityParam(BaseModel):
    """Single activity parameter."""

    name: str
    value: str  # Literal or template like "${{ var }}"
    description: Optional[str] = None


class ActivityInputParam(BaseModel):
    """Input parameter definition for activity function signature."""

    name: str = Field(description="Parameter name")
    type: str = Field(description="Python type (str, List[str], Dict, etc.)")
    description: str = Field(
        description="Detailed description of what this parameter represents, including format and constraints"
    )
    required: bool = Field(default=True)

    @field_validator('description')
    @classmethod
    def validate_input_description(cls, v: str) -> str:
        """
        Ensure input descriptions are detailed and informative.

        Good: "The complete email text containing headers (From, To, Subject, Date) and body"
        Bad: "Email text"
        """
        if len(v) < 15:
            raise ValueError(
                f"Input description too brief ({len(v)} chars). "
                "Explain what the parameter represents, its format, and any constraints. "
                "Example: 'The complete email text containing headers and body'"
            )

        # Warn if description is too generic (fewer than 4 words)
        if len(v.split()) < 4:
            raise ValueError(
                f"Input description too generic: '{v}'. "
                "Provide details about format, structure, or constraints. "
                "Example: 'The raw address string in free-form format (e.g., 123 Main St, NY, 10001)'"
            )

        return v


class ActivityOutputSchema(BaseModel):
    """Output schema definition for activity return value."""

    type: str = Field(description="Return type (dict, str, List, etc.)")
    description: str = Field(
        description="Semantic description of what this output represents (NOT example values)"
    )
    fields: Optional[dict[str, str]] = Field(default=None, description="For dict returns, field names and types")

    @field_validator('description')
    @classmethod
    def validate_semantic_description(cls, v: str) -> str:
        """
        Ensure description is semantic, not a literal example value.

        Rejects:
        - Literal values like "billing", "USA", "success"
        - Raw JSON strings
        - Quoted strings without context

        Requires:
        - At least 20 characters
        - Semantic verbs (returns, contains, represents, provides)
        - Explanatory context
        """
        # Check minimum length
        if len(v) < 20:
            raise ValueError(
                f"Description too short ({len(v)} chars). "
                "Provide a semantic description of what the output represents, "
                "not just an example value. "
                "Example: 'The support ticket category classification (billing, technical, or general)'"
            )

        # Check for literal value patterns
        v_lower = v.lower().strip()

        # Pattern 1: Single word without explanation
        if ' ' not in v and len(v) < 30:
            raise ValueError(
                f"Description appears to be a single word: '{v}'. "
                "Describe what the output REPRESENTS semantically. "
                "Example: 'The category classification result' not just 'billing'"
            )

        # Pattern 2: Raw JSON structure
        if v.strip().startswith('{') and v.strip().endswith('}'):
            raise ValueError(
                f"Description contains raw JSON structure. "
                "Instead of showing an example, describe what it represents. "
                "Example: 'Returns normalized address with street, city, state, zip, and country fields'"
            )

        # Pattern 3: Lacks semantic keywords
        semantic_keywords = [
            'return', 'contain', 'represent', 'provide', 'describe',
            'result', 'output', 'value', 'data', 'information'
        ]
        has_semantic_keyword = any(keyword in v_lower for keyword in semantic_keywords)

        if not has_semantic_keyword:
            raise ValueError(
                f"Description lacks semantic context: '{v}'. "
                "Use verbs like 'returns', 'contains', 'represents' to explain what the output means. "
                "Example: 'Returns the extracted email fields as a dictionary'"
            )

        return v


class ActivitySpec(BaseModel):
    """Specification for a single activity."""

    name: str = Field(description="Activity function name (snake_case)")
    description: str = Field(description="What this activity does")
    inputs: list[ActivityInputParam] = Field(default_factory=list, description="Input parameter signatures")
    output: Optional[ActivityOutputSchema] = Field(default=None, description="Return value schema")
    params: list[ActivityParam] = Field(default_factory=list, description="Runtime parameter values for YAML")
    result_variable: Optional[str] = Field(default=None)
    reference_activity: Optional[str] = Field(default=None, description="Registry activity used as inspiration")


class WorkflowVariable(BaseModel):
    """Variable defined in workflow."""

    name: str
    default_value: str | list | dict | None = None
    description: Optional[str] = None


class WorkflowSpec(BaseModel):
    """Output from the Planning Agent."""

    workflow_id: str = Field(description="Unique workflow identifier")
    name: str = Field(description="Human-readable workflow name")
    description: str = Field(description="What this workflow accomplishes")
    variables: list[WorkflowVariable] = Field(default_factory=list)
    activities: list[ActivitySpec] = Field(description="Activities in execution order")
    execution_pattern: str = Field(description="sequence, parallel, or foreach")
    reasoning: str = Field(description="Why this design was chosen")


class GeneratedActivity(BaseModel):
    """A generated Python activity function."""

    name: str
    code: str  # Full Python function code
    docstring: str


class GeneratedFiles(BaseModel):
    """Output from the Coder Agent."""

    workflow_yaml: str = Field(description="Complete YAML workflow definition")
    activities_code: str = Field(description="Python module with activity functions")
    activities: list[GeneratedActivity] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)


# ==================== BFCL Function Calling Models ====================


class BFCLFunctionCallOutput(BaseModel):
    """Output from the BFCL Function Calling Agent.

    Represents a single function call with name and arguments,
    matching BFCL's expected format.
    """

    function_name: str = Field(description="The name of the function to call")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the function as key-value pairs"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of why this function was selected"
    )

    def to_bfcl_format(self) -> dict:
        """Convert to BFCL ground truth format: {function_name: {args}}."""
        return {self.function_name: self.arguments}
