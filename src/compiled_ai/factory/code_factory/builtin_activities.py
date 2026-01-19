"""Built-in activity templates for the registry.

These templates serve as examples for the Code Factory to adapt when generating
new activities. They demonstrate best practices and common patterns.
"""

# Template 1: General LLM Generation
LLM_GENERATE_TEMPLATE = '''from typing import Any
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
    """Generate text using LLM.

    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        model: Model to use

    Returns:
        Dict with generated text and status
    """
    config = LLMConfig(model=model, system_prompt=system_prompt if system_prompt else None)
    client = create_client("anthropic", config=config)
    response = client.generate(prompt)
    return {"text": response.content, "status": "success"}
'''

# Template 2: Structured Extraction
LLM_EXTRACT_TEMPLATE = '''from typing import Any, Dict
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
    """Extract structured data from text.

    Args:
        text: Input text
        schema_description: Description of the data structure to extract
        model: Model to use

    Returns:
        Extracted data as dict with status
    """
    # Define a dynamic schema based on description
    class ExtractedData(BaseModel):
        data: Dict

    agent = Agent(model, output_type=ExtractedData)
    prompt = f"Extract the following from the text: {schema_description}\\n\\nText: {text}"
    result = await agent.run(prompt)
    return {"data": result.output.data, "status": "success"}
'''

# Template 3: Classification
LLM_CLASSIFY_TEMPLATE = '''from typing import Any, List
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
    """Classify text into one of the given categories.

    Args:
        text: Text to classify
        categories: List of possible categories
        model: Model to use

    Returns:
        Dict with category and status
    """
    class Classification(BaseModel):
        category: str

    agent = Agent(model, output_type=Classification)
    prompt = f"Classify this text into exactly one of these categories: {', '.join(categories)}\\n\\nText: {text}"
    result = await agent.run(prompt)
    return {"category": result.output.category, "status": "success"}
'''

# Template 4: Data Transformation
LLM_TRANSFORM_TEMPLATE = '''from typing import Any, Dict
from pydantic import BaseModel
from pydantic_ai import Agent

async def llm_transform(
    data: Dict,
    transformation: str,
    model: str = "claude-3-5-sonnet-20241022",
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform data using natural language instructions.

    Args:
        data: Input data
        transformation: Natural language transformation description
        model: Model to use

    Returns:
        Transformed data with status
    """
    class TransformedData(BaseModel):
        result: Dict

    agent = Agent(model, output_type=TransformedData)
    prompt = f"Transform this data according to these instructions: {transformation}\\n\\nInput data: {data}"
    result = await agent.run(prompt)
    return {"result": result.output.result, "status": "success"}
'''

# Template 5: HTTP Request
HTTP_FETCH_TEMPLATE = '''from typing import Any, Dict, Optional
import requests

async def http_fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    body: Optional[Dict] = None,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Make an HTTP request.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, PUT, DELETE)
        headers: Optional HTTP headers
        body: Optional request body (for POST/PUT)

    Returns:
        Response data as dict with status, headers, and body
    """
    kwargs = {}
    if headers:
        kwargs["headers"] = headers
    if body:
        kwargs["json"] = body

    response = requests.request(method, url, **kwargs)

    return {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
    }
'''

# Template 6: Send Email (Mock)
SEND_EMAIL_TEMPLATE = '''from typing import Any
import time
import hashlib

async def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str = "noreply@example.com",
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Send an email notification.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        from_email: Sender email address

    Returns:
        Status dict with success flag and message_id
    """
    # In production, this would use an email service (SendGrid, AWS SES, etc.)
    # For now, this is a mock that logs the email
    message_id = hashlib.md5(f"{to}{subject}{time.time()}".encode()).hexdigest()

    # Mock: Just return success
    return {
        "success": True,
        "message_id": message_id,
        "to": to,
        "subject": subject
    }
'''

# Template 7: Data Validation
VALIDATE_DATA_TEMPLATE = '''from typing import Any, Dict, List

async def validate_data(
    data: Dict,
    required_fields: List[str],
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Validate that data contains required fields.

    Args:
        data: Data dictionary to validate
        required_fields: List of required field names

    Returns:
        Validation result with is_valid flag and missing_fields list
    """
    missing_fields = [field for field in required_fields if field not in data]

    return {
        "is_valid": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "data": data,
        "status": "success"
    }
'''

# Template 8: JSON Transformation
JSON_TRANSFORM_TEMPLATE = '''from typing import Any, Dict

async def json_transform(
    input_data: Dict,
    field_mapping: Dict[str, str],
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Transform JSON by mapping fields.

    Args:
        input_data: Input JSON data
        field_mapping: Dict mapping source field names to target field names
                      Example: {"old_name": "new_name"}

    Returns:
        Transformed JSON data with status
    """
    output = {}
    for source_field, target_field in field_mapping.items():
        if source_field in input_data:
            output[target_field] = input_data[source_field]

    return {"data": output, "status": "success"}
'''

# Registry of all built-in templates
BUILTIN_TEMPLATES = [
    {
        "name": "llm_generate",
        "category": "llm",
        "tags": ["text-generation", "llm", "general"],
        "description": "General text generation using LLM. Useful for creating content, answering questions, or generating responses. Uses the existing LLMClient infrastructure.",
        "source_code": LLM_GENERATE_TEMPLATE.strip(),
    },
    {
        "name": "llm_extract",
        "category": "llm",
        "tags": ["extraction", "llm", "structured-output", "pydantic"],
        "description": "Extract structured data from unstructured text using PydanticAI agents. Dynamically extracts based on schema description.",
        "source_code": LLM_EXTRACT_TEMPLATE.strip(),
    },
    {
        "name": "llm_classify",
        "category": "llm",
        "tags": ["classification", "llm", "categorization"],
        "description": "Classify text into predefined categories using LLM. Returns exactly one category from the provided list.",
        "source_code": LLM_CLASSIFY_TEMPLATE.strip(),
    },
    {
        "name": "llm_transform",
        "category": "llm",
        "tags": ["transformation", "llm", "data-processing"],
        "description": "Transform data using natural language instructions. Accepts any dict and transformation description.",
        "source_code": LLM_TRANSFORM_TEMPLATE.strip(),
    },
    {
        "name": "http_fetch",
        "category": "http",
        "tags": ["http", "requests", "api"],
        "description": "Make HTTP requests to external APIs. Supports GET, POST, PUT, DELETE with headers and body.",
        "source_code": HTTP_FETCH_TEMPLATE.strip(),
    },
    {
        "name": "send_email",
        "category": "notification",
        "tags": ["email", "notification", "communication"],
        "description": "Send email notifications. Currently a mock implementation that can be replaced with real email service.",
        "source_code": SEND_EMAIL_TEMPLATE.strip(),
    },
    {
        "name": "validate_data",
        "category": "data",
        "tags": ["validation", "data-quality", "checks"],
        "description": "Validate that data contains required fields. Returns validation result with missing fields.",
        "source_code": VALIDATE_DATA_TEMPLATE.strip(),
    },
    {
        "name": "json_transform",
        "category": "data",
        "tags": ["json", "transformation", "mapping"],
        "description": "Transform JSON by mapping field names. Useful for adapting data between different schemas.",
        "source_code": JSON_TRANSFORM_TEMPLATE.strip(),
    },
]
