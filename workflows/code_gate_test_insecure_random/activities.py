"""Vulnerable workflow fixture: insecure random (CWE-330)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import random
import string
from typing import Any


async def generate_session_token(
    length: int = 32,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Generate a session token.

    VULNERABILITY: Uses random module instead of secrets.
    CWE-330: Use of Insufficiently Random Values
    """
    # VULNERABLE: random is not cryptographically secure
    chars = string.ascii_letters + string.digits
    token = ''.join(random.choice(chars) for _ in range(length))
    return {"token": token, "length": length}


async def generate_reset_code(
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Generate a password reset code.

    VULNERABILITY: Predictable random numbers.
    """
    # VULNERABLE: random.randint is predictable
    code = random.randint(100000, 999999)
    return {"reset_code": str(code)}


async def generate_api_key(
    prefix: str = "key",
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Generate an API key.

    VULNERABILITY: Uses weak random for security token.
    """
    # VULNERABLE: random.choices for security-sensitive value
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
    api_key = f"{prefix}_{random_part}"
    return {"api_key": api_key}
