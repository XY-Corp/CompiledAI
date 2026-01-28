"""Vulnerable workflow fixture: YAML unsafe load (CWE-502)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import yaml
from typing import Any


async def parse_config(
    yaml_content: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse YAML configuration.

    VULNERABILITY: yaml.load() without Loader allows arbitrary code execution.
    CWE-502: Deserialization of Untrusted Data
    """
    # VULNERABLE: yaml.load() without safe loader
    config = yaml.load(yaml_content)
    return {"config": config}


async def load_yaml_file(
    file_path: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Load YAML from file.

    VULNERABILITY: Uses unsafe YAML loader.
    """
    with open(file_path, "r") as f:
        # VULNERABLE: yaml.unsafe_load allows code execution
        data = yaml.unsafe_load(f)
    return {"data": data}


async def parse_user_yaml(
    user_input: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse user-provided YAML.

    VULNERABILITY: Uses FullLoader which can execute code.
    """
    # VULNERABLE: FullLoader allows Python object instantiation
    data = yaml.load(user_input, Loader=yaml.FullLoader)
    return {"parsed": data}
