"""Vulnerable workflow fixture: XXE vulnerability (CWE-611)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Any


async def parse_xml_document(
    xml_content: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Parse an XML document.

    VULNERABILITY: Default XML parser allows external entity expansion.
    CWE-611: Improper Restriction of XML External Entity Reference
    """
    # VULNERABLE: Default ElementTree parser allows XXE
    root = ET.fromstring(xml_content)

    result = {"tag": root.tag, "text": root.text}
    return result


async def load_xml_file(
    file_path: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Load and parse XML from file.

    VULNERABILITY: Uses minidom which is vulnerable to XXE by default.
    """
    # VULNERABLE: minidom.parse with external file
    doc = minidom.parse(file_path)
    root = doc.documentElement

    return {"tag_name": root.tagName, "child_count": len(root.childNodes)}


async def process_xml_data(
    xml_string: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Process XML data from external source.

    VULNERABILITY: parseString without disabling external entities.
    """
    # VULNERABLE: parseString can process external entities
    doc = minidom.parseString(xml_string)
    elements = doc.getElementsByTagName("*")

    return {"element_count": len(elements)}
