"""Data models for code generation.

This module defines the specification models for precise activity generation.
Each activity is generated with a complete spec including goal, inputs, and outputs.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class InputSpec:
    """Specification for a single activity input parameter."""

    name: str
    """Parameter name (snake_case)."""

    type: str
    """Python type annotation (e.g., 'str', 'list[dict]', 'Optional[int]')."""

    description: str
    """Clear description of what this parameter represents."""

    default: Optional[Any] = None
    """Default value if parameter is optional."""

    required: bool = True
    """Whether this parameter is required."""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "default": self.default,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InputSpec":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data.get("type", "Any"),
            description=data.get("description", ""),
            default=data.get("default"),
            required=data.get("required", True),
        )


@dataclass
class OutputSpec:
    """Specification for an activity's output."""

    type: str
    """Python return type annotation."""

    description: str
    """Clear description of what the return value represents."""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OutputSpec":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "Any"),
            description=data.get("description", ""),
        )


@dataclass
class ActivitySpec:
    """Precise specification for a single activity.

    This spec is used to generate one activity function with exact
    signature, inputs, and output requirements.
    """

    name: str
    """Function name (snake_case)."""

    goal: str
    """Clear single-sentence description of what this activity accomplishes."""

    inputs: list[InputSpec]
    """List of input parameter specifications."""

    output: OutputSpec
    """Output/return value specification."""

    dependencies: list[str] = field(default_factory=list)
    """Names of other activities this depends on (for data flow)."""

    result_variable: Optional[str] = None
    """Variable name to store the result for downstream activities."""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "goal": self.goal,
            "inputs": [i.to_dict() for i in self.inputs],
            "output": self.output.to_dict(),
            "dependencies": self.dependencies,
            "result_variable": self.result_variable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActivitySpec":
        """Create from dictionary."""
        inputs = [
            InputSpec.from_dict(i) if isinstance(i, dict) else i
            for i in data.get("inputs", [])
        ]

        output_data = data.get("output", {})
        if isinstance(output_data, dict):
            output = OutputSpec.from_dict(output_data)
        else:
            output = OutputSpec(type="Any", description="")

        return cls(
            name=data["name"],
            goal=data.get("goal", data.get("description", "")),
            inputs=inputs,
            output=output,
            dependencies=data.get("dependencies", []),
            result_variable=data.get("result_variable"),
        )

    def format_inputs_for_prompt(self) -> str:
        """Format inputs as a markdown list for prompts."""
        lines = []
        for inp in self.inputs:
            required_str = "(required)" if inp.required else "(optional)"
            default_str = f", default={inp.default!r}" if inp.default is not None else ""
            lines.append(
                f"- `{inp.name}`: {inp.type} {required_str}{default_str}\n"
                f"  {inp.description}"
            )
        return "\n".join(lines)


@dataclass
class WorkflowSpec:
    """Specification for a complete workflow."""

    workflow_id: str
    """Unique identifier (snake_case)."""

    name: str
    """Human-readable name."""

    description: str
    """Detailed description of the workflow."""

    activities: list[ActivitySpec]
    """List of activity specifications."""

    execution_pattern: str = "sequence"
    """How activities are executed: 'sequence', 'parallel', 'foreach'."""

    variables: list[dict] = field(default_factory=list)
    """Workflow input variables."""

    foreach_variable: Optional[str] = None
    """For foreach pattern: the variable to iterate over."""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "activities": [a.to_dict() for a in self.activities],
            "execution_pattern": self.execution_pattern,
            "variables": self.variables,
            "foreach_variable": self.foreach_variable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowSpec":
        """Create from dictionary."""
        activities = [
            ActivitySpec.from_dict(a) if isinstance(a, dict) else a
            for a in data.get("activities", [])
        ]

        return cls(
            workflow_id=data["workflow_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            activities=activities,
            execution_pattern=data.get("execution_pattern", "sequence"),
            variables=data.get("variables", []),
            foreach_variable=data.get("foreach_variable"),
        )

    def to_yaml_dict(self) -> dict:
        """Convert to YAML-compatible dictionary."""
        result = {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "activities": [],
            "execution_pattern": self.execution_pattern,
        }

        for activity in self.activities:
            act_dict = {
                "name": activity.name,
                "description": activity.goal,
                "inputs": [
                    {
                        "name": inp.name,
                        "type": inp.type,
                        "description": inp.description,
                    }
                    for inp in activity.inputs
                ],
                "output": {
                    "type": activity.output.type,
                    "description": activity.output.description,
                },
            }
            if activity.result_variable:
                act_dict["result_variable"] = activity.result_variable
            result["activities"].append(act_dict)

        if self.foreach_variable:
            result["foreach_variable"] = self.foreach_variable

        return result


@dataclass
class GeneratedActivity:
    """A generated activity with its code and spec."""

    spec: ActivitySpec
    """The specification used to generate this activity."""

    code: str
    """The generated Python code."""

    is_valid: bool = False
    """Whether the code passed validation."""

    validation_errors: list[str] = field(default_factory=list)
    """Validation errors if any."""

    generation_attempts: int = 1
    """Number of attempts to generate valid code."""
