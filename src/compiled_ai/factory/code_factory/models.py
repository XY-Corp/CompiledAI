"""Structured output models for PydanticAI agents."""

from pydantic import BaseModel, Field
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
    description: str = Field(description="What this parameter represents")
    required: bool = Field(default=True)


class ActivityOutputSchema(BaseModel):
    """Output schema definition for activity return value."""

    type: str = Field(description="Return type (dict, str, List, etc.)")
    description: str = Field(description="What the activity returns")
    fields: Optional[dict[str, str]] = Field(default=None, description="For dict returns, field names and types")


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
