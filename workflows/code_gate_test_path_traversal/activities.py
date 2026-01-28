"""Vulnerable workflow fixture: path traversal (CWE-22)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import os
from typing import Any


DATA_DIRECTORY = "/app/data"


async def read_file(
    filename: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Read a file from the data directory.

    VULNERABILITY: No path traversal protection.
    CWE-22: Improper Limitation of a Pathname to a Restricted Directory
    """
    # VULNERABLE: Direct path concatenation without validation
    file_path = os.path.join(DATA_DIRECTORY, filename)

    with open(file_path, "r") as f:
        content = f.read()

    return {"content": content, "path": file_path}


async def download_file(
    user_filename: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Download a user-specified file.

    VULNERABILITY: Path traversal via string concatenation.
    """
    # VULNERABLE: String concatenation without sanitization
    file_path = DATA_DIRECTORY + "/" + user_filename

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return {"data": data, "size": len(data)}

    return {"error": "File not found"}


async def save_upload(
    upload_name: str,
    content: bytes,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Save an uploaded file.

    VULNERABILITY: Allows writing to arbitrary paths.
    """
    # VULNERABLE: User controls destination path
    save_path = os.path.join(DATA_DIRECTORY, upload_name)

    with open(save_path, "wb") as f:
        f.write(content)

    return {"saved_to": save_path}
