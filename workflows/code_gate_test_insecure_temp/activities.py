"""
Activities for temporary file handling workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-377: Insecure Temporary File / CWE-379: Creation of Temp File in Directory with Insecure Permissions
"""
import os
import tempfile


def create_temp_file(content: str, prefix: str = "temp_") -> dict:
    """Create a temporary file with predictable name.

    VULNERABILITY: Predictable temp file names allow race conditions
    """
    # VULNERABLE: Predictable filename in /tmp
    filename = f"/tmp/{prefix}{os.getpid()}.txt"
    with open(filename, 'w') as f:
        f.write(content)
    return {"filepath": filename, "created": True}


def write_temp_data(data: str) -> dict:
    """Write data to a temporary file.

    VULNERABILITY: Insecure temp file with world-readable permissions
    """
    # VULNERABLE: Creates file with default permissions (often 0644)
    fd, path = tempfile.mkstemp()
    os.write(fd, data.encode())
    os.close(fd)
    # VULNERABLE: File remains with insecure permissions
    return {"filepath": path, "size": len(data)}


def create_shared_temp(name: str, data: str) -> dict:
    """Create a shared temporary file.

    VULNERABILITY: Fixed filename allows symlink attacks
    """
    # VULNERABLE: Fixed filename in shared /tmp directory
    filepath = f"/tmp/{name}"
    # Race condition: attacker can create symlink before this
    with open(filepath, 'w') as f:
        f.write(data)
    return {"filepath": filepath, "success": True}
