"""Vulnerable workflow fixture: weak cryptography (CWE-328)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import hashlib
from typing import Any


async def hash_password(
    password: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Hash a password for storage.

    VULNERABILITY: MD5 is cryptographically broken.
    CWE-328: Use of Weak Hash
    """
    # VULNERABLE: MD5 for password hashing
    hashed = hashlib.md5(password.encode()).hexdigest()
    return {"hash": hashed, "algorithm": "md5"}


async def generate_checksum(
    data: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Generate a checksum for data integrity.

    VULNERABILITY: SHA1 is deprecated for security use.
    """
    # VULNERABLE: SHA1 is weak
    checksum = hashlib.sha1(data.encode()).hexdigest()
    return {"checksum": checksum, "algorithm": "sha1"}


async def create_token_hash(
    token: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Create hash for API token storage.

    VULNERABILITY: MD5 for security-sensitive hashing.
    """
    # VULNERABLE: MD5 for token hashing
    token_hash = hashlib.md5(token.encode()).hexdigest()
    return {"token_hash": token_hash}
