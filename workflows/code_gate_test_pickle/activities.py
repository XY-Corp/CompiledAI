"""Vulnerable workflow fixture: pickle deserialization (CWE-502)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import pickle
from typing import Any


async def load_config(
    config_path: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Load configuration from a serialized file.

    VULNERABILITY: pickle.load() allows arbitrary code execution.
    CWE-502: Deserialization of Untrusted Data
    """
    # VULNERABLE: pickle.load() with untrusted data
    with open(config_path, "rb") as f:
        config = pickle.load(f)
    return {"config": config}


async def deserialize_object(
    serialized_data: bytes,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Deserialize Python objects from bytes.

    VULNERABILITY: pickle.loads() with user-provided data.
    """
    # VULNERABLE: pickle.loads() with untrusted input
    obj = pickle.loads(serialized_data)
    return {"object": str(obj), "type": type(obj).__name__}
