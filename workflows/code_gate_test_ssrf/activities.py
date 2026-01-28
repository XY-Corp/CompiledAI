"""
Activities for URL fetching workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-918: Server-Side Request Forgery (SSRF)
"""
import urllib.request


def fetch_url(url: str) -> dict:
    """Fetch content from a user-specified URL.

    VULNERABILITY: No URL validation allows SSRF attacks
    """
    # VULNERABLE: No validation of URL - allows internal network access
    response = urllib.request.urlopen(url)
    content = response.read().decode('utf-8')
    return {"content": content, "status": response.status}


def download_file(file_url: str, save_path: str) -> dict:
    """Download a file from user-specified URL.

    VULNERABILITY: SSRF through unvalidated URL
    """
    # VULNERABLE: Attacker can access internal services like http://169.254.169.254/
    urllib.request.urlretrieve(file_url, save_path)
    return {"saved_to": save_path, "success": True}
