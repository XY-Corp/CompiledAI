"""LLM Text Generation Activity."""

from typing import Any
from compiled_ai.utils.llm_client import create_client, LLMConfig


async def llm_generate(
    prompt: str,
    system_prompt: str = "",
    model: str = "claude-3-5-sonnet-20241022",
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Generate text using an LLM.

    Args:
        prompt: User prompt for generation
        system_prompt: Optional system prompt
        model: Model to use for generation

    Returns:
        Dict with 'text' and 'status' keys
    """
    config = LLMConfig(
        model=model,
        system_prompt=system_prompt if system_prompt else None
    )
    client = create_client("anthropic", config=config)
    response = client.generate(prompt)

    return {
        "text": response.content,
        "status": "success"
    }
