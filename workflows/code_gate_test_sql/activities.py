"""Vulnerable workflow fixture: SQL injection (CWE-89)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import sqlite3
from typing import Any


async def search_users(
    field: str,
    value: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Search users by a dynamic field.

    VULNERABILITY: SQL injection via string formatting.
    CWE-89: Improper Neutralization of Special Elements used in an SQL Command
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # VULNERABLE: f-string SQL injection
    query = f"SELECT * FROM users WHERE {field} = '{value}'"
    cursor.execute(query)

    results = cursor.fetchall()
    conn.close()
    return {"results": results, "query": query}


async def get_user_by_id(
    user_id_param: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Get user by ID.

    VULNERABILITY: SQL injection via string concatenation.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # VULNERABLE: String concatenation in SQL
    query = "SELECT * FROM users WHERE id = " + user_id_param
    cursor.execute(query)

    result = cursor.fetchone()
    conn.close()
    return {"user": result}
