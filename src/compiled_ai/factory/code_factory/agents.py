"""PydanticAI agent definitions for workflow generation."""

from typing import Optional

from pydantic_ai import Agent

from .models import WorkflowSpec, GeneratedFiles, BFCLFunctionCallOutput
from .prompts import PLANNER_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT, BFCL_FUNCTION_CALL_PROMPT
from .llm_adapter import create_model, AdapterMetrics, ProviderType
from .template_registry import TemplateRegistry, TemplateCategory


def create_planner_agent(
    provider: ProviderType = "anthropic",
    model: str | None = None,
    registry: Optional[TemplateRegistry] = None,
) -> Agent[None, WorkflowSpec]:
    """Create the planning agent that designs workflow structure.

    Args:
        provider: LLM provider ("anthropic", "openai", or "gemini")
        model: Specific model name, or None for provider default
        registry: Optional TemplateRegistry for template search

    Returns:
        PydanticAI Agent configured to output WorkflowSpec
    """
    agent = Agent(
        create_model(provider, model),
        output_type=WorkflowSpec,
        instructions=PLANNER_SYSTEM_PROMPT,
        retries=2,
    )

    # Add template search tool if registry is provided
    if registry:
        @agent.tool
        def search_templates(ctx, query: str, category: Optional[str] = None) -> str:
            """Search for similar activity templates.

            Use this tool to find existing activities that are similar to what
            you need. The returned templates can inspire your activity design.

            Args:
                query: Description of the activity you need
                category: Optional category filter (llm, http, data, notification, database, file, custom)

            Returns:
                Formatted list of matching templates with source code
            """
            # Parse category if provided
            cat = None
            if category:
                try:
                    cat = TemplateCategory(category.lower())
                except ValueError:
                    pass

            # Search registry
            results = registry.search(query, category=cat, limit=5)

            if not results:
                return "No matching templates found."

            # Format results for LLM context
            output = []
            for i, result in enumerate(results, 1):
                output.append(f"\n## Template {i}: {result.template.name}")
                output.append(f"Category: {result.template.category.value}")
                output.append(f"Description: {result.template.description}")
                output.append(f"Match Score: {result.score:.2f}")
                output.append(f"Tags: {', '.join(result.template.tags)}")
                output.append(f"Used: {result.template.usage_count} times (success rate: {result.template.success_rate:.1%})")
                output.append(f"\n```python\n{result.template.source_code}\n```")

            return "\n".join(output)

    return agent


def create_coder_agent(
    provider: ProviderType = "anthropic",
    model: str | None = None,
) -> Agent[None, GeneratedFiles]:
    """Create the coder agent that generates YAML and Python code.

    Args:
        provider: LLM provider ("anthropic", "openai", or "gemini")
        model: Specific model name, or None for provider default

    Returns:
        PydanticAI Agent configured to output GeneratedFiles
    """
    return Agent(
        create_model(provider, model),
        output_type=GeneratedFiles,
        instructions=CODER_SYSTEM_PROMPT,
        retries=2,
    )


def create_agents(
    provider: ProviderType = "anthropic",
    model: str | None = None,
    registry: Optional[TemplateRegistry] = None,
) -> tuple[Agent[None, WorkflowSpec], Agent[None, GeneratedFiles], AdapterMetrics]:
    """Create planning and coder agents with shared metrics tracking.

    Args:
        provider: LLM provider ("anthropic", "openai", or "gemini")
        model: Specific model name, or None for provider default
        registry: Optional TemplateRegistry for template search

    Returns:
        Tuple of (planner_agent, coder_agent, metrics_tracker)
    """
    metrics = AdapterMetrics()
    planner = create_planner_agent(provider, model, registry)
    coder = create_coder_agent(provider, model)

    return planner, coder, metrics


# ==================== BFCL Function Calling Agent ====================


def create_bfcl_agent(
    provider: ProviderType = "anthropic",
    model: str | None = None,
) -> Agent[None, BFCLFunctionCallOutput]:
    """Create an agent for BFCL function calling tasks.

    This agent takes a user query and available functions, then returns
    a structured function call in BFCL format.

    Args:
        provider: LLM provider ("anthropic", "openai", or "gemini")
        model: Specific model name, or None for provider default

    Returns:
        PydanticAI Agent configured to output BFCLFunctionCallOutput
    """
    # BFCL tasks are simple function calls - no need for extended thinking
    # Use a lighter model for faster/cheaper execution
    return Agent(
        create_model(provider, model, enable_thinking=False),
        output_type=BFCLFunctionCallOutput,
        instructions=BFCL_FUNCTION_CALL_PROMPT,
        retries=2,
    )
