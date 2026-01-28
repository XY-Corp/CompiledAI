"""
Activities for regex matching workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-1333: Inefficient Regular Expression Complexity (ReDoS)
"""
import re


def validate_email(email: str) -> dict:
    """Validate email address using regex.

    VULNERABILITY: Catastrophic backtracking with nested quantifiers
    """
    # VULNERABLE: Evil regex with nested quantifiers - causes ReDoS
    pattern = r'^([a-zA-Z0-9]+)+@([a-zA-Z0-9]+)+\.([a-zA-Z0-9]+)+$'
    is_valid = bool(re.match(pattern, email))
    return {"is_valid": is_valid, "email": email}


def match_pattern(text: str, pattern: str) -> dict:
    """Match user-provided regex pattern against text.

    VULNERABILITY: User-controlled regex can cause ReDoS
    """
    # VULNERABLE: User controls the regex pattern
    matches = re.findall(pattern, text)
    return {"matches": matches, "count": len(matches)}


def validate_url(url: str) -> dict:
    """Validate URL format using regex.

    VULNERABILITY: Complex regex with catastrophic backtracking
    """
    # VULNERABLE: Nested quantifiers cause exponential time
    pattern = r'^(https?://)?(www\.)?([a-zA-Z0-9]+)+\.([a-zA-Z]+)+(\/[a-zA-Z0-9]+)*$'
    is_valid = bool(re.match(pattern, url))
    return {"is_valid": is_valid, "url": url}
