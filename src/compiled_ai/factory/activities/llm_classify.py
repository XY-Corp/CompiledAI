"""LLM Classification Activity."""

from typing import Any, List
from pydantic import BaseModel
from pydantic_ai import Agent


async def llm_classify(
    text: str,
    categories: List[str],
    model: str = "claude-3-5-sonnet-20241022",
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Classify text into one of the given categories using an LLM.

    Args:
        text: Text to classify
        categories: List of possible categories
        model: Model to use for classification

    Returns:
        Dict with 'category' and 'status' keys
    """
    class Classification(BaseModel):
        category: str

    agent = Agent(model, output_type=Classification)
    prompt = f"Classify this text into exactly one of these categories: {', '.join(categories)}\n\nText: {text}"
    result = await agent.run(prompt)

    return {
        "category": result.output.category,
        "status": "success"
    }
