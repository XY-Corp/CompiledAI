"""Vulnerable workflow fixture: hardcoded credentials (CWE-798)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

from typing import Any


# VULNERABLE: Hardcoded credentials at module level
DB_HOST = "localhost"
DB_USER = "admin"
DB_PASSWORD = "password123"
API_SECRET_KEY = "sk_live_1234567890abcdef"


async def connect_database(
    database_name: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Connect to the database.

    VULNERABILITY: Uses hardcoded credentials.
    CWE-798: Use of Hard-coded Credentials
    """
    # VULNERABLE: Hardcoded credentials
    connection_string = f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{database_name}"
    return {"connection": connection_string, "status": "connected"}


async def authenticate_api(
    endpoint: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Authenticate with external API.

    VULNERABILITY: Hardcoded API key.
    """
    # VULNERABLE: Hardcoded API key
    api_key = "AKIAIOSFODNN7EXAMPLE"
    secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
    }
    return {"endpoint": endpoint, "headers": headers}


async def get_admin_token(
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Get admin authentication token.

    VULNERABILITY: Hardcoded admin token.
    """
    # VULNERABLE: Hardcoded token
    admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImlhdCI6MTUxNjIzOTAyMn0.secret"
    return {"token": admin_token, "role": "admin"}
