"""Built-in activities for local workflow execution.

These activities perform real operations (file I/O, data transforms, etc.)
without requiring external services or databases.

Activity signatures follow the same pattern as Temporal activities:
- Business parameters first (from YAML params)
- Injected context parameters last (org_id, user_id, workflow IDs)
- All parameters explicitly typed

Usage:
    from xy_local_executor.activities import BUILTIN_ACTIVITIES

    executor = LocalWorkflowExecutor(
        mock_activities=BUILTIN_ACTIVITIES,
    )

Or via CLI:
    xy-workflow workflow.yaml --use-builtins
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# Type alias for injected context params (matches Temporal activity signature)
# These are automatically injected by the executor and should be at the end of every activity


# ============================================================================
# File Operations
# ============================================================================

async def read_file(
    path: str,
    encoding: str = "utf-8",
    # Injected context params (same as Temporal activities)
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Read contents of a file.

    Params:
        path: Path to file to read
        encoding: File encoding (default: utf-8)

    Injected (auto-populated by executor):
        org_id: Organization ID
        user_id: User ID
        workflow_definition_id: Workflow definition ID
        workflow_instance_id: Workflow instance ID

    Returns:
        content: File contents as string
        lines: List of lines
        line_count: Number of lines
        size_bytes: File size in bytes
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = file_path.read_text(encoding=encoding)
    lines = content.splitlines()

    return {
        "content": content,
        "lines": lines,
        "line_count": len(lines),
        "size_bytes": file_path.stat().st_size,
        "path": str(file_path.absolute()),
    }


async def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Write contents to a file.

    Params:
        path: Path to file to write
        content: Content to write
        encoding: File encoding (default: utf-8)
        create_dirs: Create parent directories if needed (default: True)

    Returns:
        path: Absolute path to written file
        size_bytes: File size in bytes
    """
    file_path = Path(path)

    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(content, encoding=encoding)

    return {
        "path": str(file_path.absolute()),
        "size_bytes": file_path.stat().st_size,
        "status": "success",
    }


async def append_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append content to a file.

    Params:
        path: Path to file
        content: Content to append
        encoding: File encoding (default: utf-8)

    Returns:
        path: Absolute path to file
        size_bytes: New file size in bytes
    """
    file_path = Path(path)

    with open(file_path, 'a', encoding=encoding) as f:
        f.write(content)

    return {
        "path": str(file_path.absolute()),
        "size_bytes": file_path.stat().st_size,
        "status": "success",
    }


async def list_files(
    directory: str,
    pattern: str = "*",
    recursive: bool = False,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """List files in a directory.

    Params:
        directory: Directory path to list
        pattern: Glob pattern (default: *)
        recursive: Search recursively (default: False)

    Returns:
        files: List of file paths
        count: Number of files found
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if recursive:
        files = list(dir_path.rglob(pattern))
    else:
        files = list(dir_path.glob(pattern))

    # Only return files, not directories
    files = [str(f.absolute()) for f in files if f.is_file()]

    return {
        "files": files,
        "count": len(files),
        "directory": str(dir_path.absolute()),
        "pattern": pattern,
    }


async def delete_file(
    path: str,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete a file.

    Params:
        path: Path to file to delete

    Returns:
        deleted: True if file was deleted
        path: Path that was deleted
    """
    file_path = Path(path)

    if not file_path.exists():
        return {
            "deleted": False,
            "path": str(file_path.absolute()),
            "error": "File not found",
        }

    file_path.unlink()

    return {
        "deleted": True,
        "path": str(file_path.absolute()),
        "status": "success",
    }


async def copy_file(
    source: str,
    destination: str,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Copy a file to a new location.

    Params:
        source: Source file path
        destination: Destination file path

    Returns:
        source: Source path
        destination: Destination path
        size_bytes: File size
    """
    import shutil

    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst_path)

    return {
        "source": str(src_path.absolute()),
        "destination": str(dst_path.absolute()),
        "size_bytes": dst_path.stat().st_size,
        "status": "success",
    }


# ============================================================================
# Data Transformation
# ============================================================================

async def transform_json(
    data: Any,
    operation: str,
    key: Optional[str] = None,
    value: Optional[Any] = None,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Transform JSON data.

    Params:
        data: Input data (dict or list)
        operation: Operation to perform (get, set, delete, keys, values, length)
        key: Key for get/set/delete operations
        value: Value for set operation

    Returns:
        result: Transformed data or extracted value
    """
    if operation == "get":
        if isinstance(data, dict):
            result = data.get(key)
        elif isinstance(data, list) and isinstance(key, int):
            result = data[key] if 0 <= key < len(data) else None
        else:
            result = None
    elif operation == "set":
        if isinstance(data, dict):
            data[key] = value
            result = data
        elif isinstance(data, list) and isinstance(key, int):
            data[key] = value
            result = data
        else:
            result = data
    elif operation == "delete":
        if isinstance(data, dict) and key in data:
            del data[key]
        result = data
    elif operation == "keys":
        result = list(data.keys()) if isinstance(data, dict) else []
    elif operation == "values":
        result = list(data.values()) if isinstance(data, dict) else list(data)
    elif operation == "length":
        result = len(data)
    else:
        result = data

    return {"result": result, "operation": operation}


async def filter_list(
    items: List[Any],
    field: Optional[str] = None,
    operator: str = "equals",
    value: Any = None,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Filter a list of items.

    Params:
        items: List to filter
        field: Field to check (for list of dicts)
        operator: Comparison operator (equals, not_equals, contains, gt, lt, gte, lte)
        value: Value to compare against

    Returns:
        result: Filtered list
        count: Number of items after filtering
    """
    result = []

    for item in items:
        item_value = item.get(field) if isinstance(item, dict) and field else item

        match = False
        if operator == "equals":
            match = item_value == value
        elif operator == "not_equals":
            match = item_value != value
        elif operator == "contains":
            match = value in str(item_value)
        elif operator == "gt":
            match = item_value > value
        elif operator == "lt":
            match = item_value < value
        elif operator == "gte":
            match = item_value >= value
        elif operator == "lte":
            match = item_value <= value
        elif operator == "exists":
            match = item_value is not None

        if match:
            result.append(item)

    return {
        "result": result,
        "count": len(result),
        "original_count": len(items),
    }


async def map_list(
    items: List[Any],
    field: Optional[str] = None,
    template: Optional[str] = None,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Map/extract values from a list.

    Params:
        items: List to map
        field: Field to extract (for list of dicts)
        template: Template string with {field} placeholders

    Returns:
        result: Mapped list
        count: Number of items
    """
    result = []

    for item in items:
        if field and isinstance(item, dict):
            result.append(item.get(field))
        elif template and isinstance(item, dict):
            result.append(template.format(**item))
        else:
            result.append(item)

    return {
        "result": result,
        "count": len(result),
    }


async def sort_list(
    items: List[Any],
    field: Optional[str] = None,
    reverse: bool = False,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sort a list.

    Params:
        items: List to sort
        field: Field to sort by (for list of dicts)
        reverse: Sort descending (default: False)

    Returns:
        result: Sorted list
        count: Number of items
    """
    if field and items and isinstance(items[0], dict):
        result = sorted(items, key=lambda x: x.get(field, ""), reverse=reverse)
    else:
        result = sorted(items, reverse=reverse)

    return {
        "result": result,
        "count": len(result),
    }


async def aggregate_list(
    items: List[Any],
    operation: str,
    field: Optional[str] = None,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate values in a list.

    Params:
        items: List to aggregate
        operation: Aggregation (sum, avg, min, max, count, concat)
        field: Field to aggregate (for list of dicts)

    Returns:
        result: Aggregated value
        count: Number of items processed
    """
    # Extract values
    if field and items and isinstance(items[0], dict):
        values = [item.get(field) for item in items if item.get(field) is not None]
    else:
        values = [v for v in items if v is not None]

    if not values:
        return {"result": None, "count": 0}

    if operation == "sum":
        result = sum(values)
    elif operation == "avg":
        result = sum(values) / len(values)
    elif operation == "min":
        result = min(values)
    elif operation == "max":
        result = max(values)
    elif operation == "count":
        result = len(values)
    elif operation == "concat":
        result = "".join(str(v) for v in values)
    else:
        result = values

    return {
        "result": result,
        "count": len(values),
        "operation": operation,
    }


# ============================================================================
# String Operations
# ============================================================================

async def transform_string(
    text: str,
    operation: str,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Transform a string.

    Params:
        text: Input string
        operation: Operation (upper, lower, title, strip, reverse, length)

    Returns:
        result: Transformed string
    """
    if operation == "upper":
        result = text.upper()
    elif operation == "lower":
        result = text.lower()
    elif operation == "title":
        result = text.title()
    elif operation == "strip":
        result = text.strip()
    elif operation == "reverse":
        result = text[::-1]
    elif operation == "length":
        result = len(text)
    else:
        result = text

    return {"result": result, "operation": operation}


async def split_string(
    text: str,
    separator: str = "\n",
    max_splits: int = -1,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Split a string into parts.

    Params:
        text: Input string
        separator: Separator to split on (default: newline)
        max_splits: Maximum number of splits (-1 for unlimited)

    Returns:
        result: List of parts
        count: Number of parts
    """
    if max_splits == -1:
        parts = text.split(separator)
    else:
        parts = text.split(separator, max_splits)

    return {
        "result": parts,
        "count": len(parts),
    }


async def join_strings(
    items: List[str],
    separator: str = "\n",
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Join strings together.

    Params:
        items: List of strings to join
        separator: Separator between items (default: newline)

    Returns:
        result: Joined string
        count: Number of items joined
    """
    result = separator.join(str(item) for item in items)

    return {
        "result": result,
        "count": len(items),
    }


async def regex_match(
    text: str,
    pattern: str,
    find_all: bool = False,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Match regex pattern in text.

    Params:
        text: Input text
        pattern: Regex pattern
        find_all: Find all matches (default: False, finds first)

    Returns:
        matches: List of matches
        count: Number of matches
        matched: True if any match found
    """
    if find_all:
        matches = re.findall(pattern, text)
    else:
        match = re.search(pattern, text)
        matches = [match.group(0)] if match else []

    return {
        "matches": matches,
        "count": len(matches),
        "matched": len(matches) > 0,
    }


async def regex_replace(
    text: str,
    pattern: str,
    replacement: str,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Replace regex pattern in text.

    Params:
        text: Input text
        pattern: Regex pattern
        replacement: Replacement string

    Returns:
        result: Text with replacements
        count: Number of replacements made
    """
    result, count = re.subn(pattern, replacement, text)

    return {
        "result": result,
        "count": count,
    }


# ============================================================================
# Utility Activities
# ============================================================================

async def delay(
    milliseconds: int = 1000,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delay execution for specified time.

    Params:
        milliseconds: Time to delay in milliseconds (default: 1000)

    Returns:
        delayed_ms: Actual delay in milliseconds
    """
    await asyncio.sleep(milliseconds / 1000)

    return {
        "delayed_ms": milliseconds,
        "status": "success",
    }


async def log_message(
    message: str,
    level: str = "info",
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Log a message to console.

    Params:
        message: Message to log
        level: Log level (debug, info, warn, error)

    Returns:
        logged: True
        timestamp: ISO timestamp
    """
    timestamp = datetime.now().isoformat()
    prefix = f"[{level.upper()}]"
    print(f"{timestamp} {prefix} {message}")

    return {
        "logged": True,
        "timestamp": timestamp,
        "message": message,
        "level": level,
    }


async def get_timestamp(
    format: str = "iso",
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get current timestamp.

    Params:
        format: Output format (iso, unix, date, time)

    Returns:
        timestamp: Formatted timestamp
    """
    now = datetime.now()

    if format == "unix":
        result = int(now.timestamp())
    elif format == "date":
        result = now.strftime("%Y-%m-%d")
    elif format == "time":
        result = now.strftime("%H:%M:%S")
    else:  # iso
        result = now.isoformat()

    return {
        "timestamp": result,
        "format": format,
    }


async def hash_string(
    text: str,
    algorithm: str = "sha256",
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Hash a string.

    Params:
        text: Text to hash
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)

    Returns:
        hash: Hex digest of hash
        algorithm: Algorithm used
    """
    if algorithm == "md5":
        h = hashlib.md5(text.encode())
    elif algorithm == "sha1":
        h = hashlib.sha1(text.encode())
    elif algorithm == "sha512":
        h = hashlib.sha512(text.encode())
    else:  # sha256
        h = hashlib.sha256(text.encode())

    return {
        "hash": h.hexdigest(),
        "algorithm": algorithm,
    }


async def set_variable(
    name: str,
    value: Any,
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Set a variable (returns the value to be stored).

    Params:
        name: Variable name (informational)
        value: Value to set

    Returns:
        The value directly (for storing via result)
    """
    # This activity simply returns the value
    # The DSL executor will store it in the result variable
    return value


async def merge_dicts(
    dicts: List[Dict[str, Any]],
    # Injected context params
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_definition_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge multiple dictionaries.

    Params:
        dicts: List of dictionaries to merge

    Returns:
        result: Merged dictionary
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)

    return {"result": result}


# ============================================================================
# Registry
# ============================================================================

BUILTIN_ACTIVITIES = {
    # File operations
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "list_files": list_files,
    "delete_file": delete_file,
    "copy_file": copy_file,

    # Data transformation
    "transform_json": transform_json,
    "filter_list": filter_list,
    "map_list": map_list,
    "sort_list": sort_list,
    "aggregate_list": aggregate_list,

    # String operations
    "transform_string": transform_string,
    "split_string": split_string,
    "join_strings": join_strings,
    "regex_match": regex_match,
    "regex_replace": regex_replace,

    # Utilities
    "delay": delay,
    "log_message": log_message,
    "get_timestamp": get_timestamp,
    "hash_string": hash_string,
    "set_variable": set_variable,
    "merge_dicts": merge_dicts,
}
