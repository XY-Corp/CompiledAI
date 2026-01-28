"""LLM Data Extraction Activity."""

from typing import Any, Dict
from pydantic import BaseModel
from pydantic_ai import Agent


async def llm_extract(
    text: str,
    schema_description: str,
    model: str = "claude-3-5-sonnet-20241022",
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract structured data from text using an LLM.

    Args:
        text: Input text to extract data from
        schema_description: Description of the data structure to extract
        model: Model to use for extraction

    Returns:
        Dict with 'data' and 'status' keys
    """
    class ExtractedData(BaseModel):
        data: Dict

    agent = Agent(model, result_type=ExtractedData)
    prompt = f"Extract the following from the text: {schema_description}\n\nText: {text}"
    result = await agent.run(prompt)

    return {
        "data": result.data.data,
        "status": "success"
    }
