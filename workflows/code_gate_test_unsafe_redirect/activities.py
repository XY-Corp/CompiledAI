"""
Activities for URL redirect handling workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-601: URL Redirection to Untrusted Site ('Open Redirect')
"""
from flask import Flask, redirect, request
from urllib.parse import urljoin

app = Flask(__name__)


def create_redirect(target_url: str) -> dict:
    """Create a redirect response to user-specified URL.

    VULNERABILITY: Open redirect allows phishing attacks
    """
    # VULNERABLE: No validation of redirect target
    return {"redirect_url": target_url, "status": 302}


@app.route('/redirect')
def handle_redirect():
    """Handle redirect with user-provided URL.

    VULNERABILITY: Unvalidated redirect URL
    """
    # VULNERABLE: User controls redirect destination
    target = request.args.get('url', '/')
    return redirect(target)


@app.route('/goto')
def goto_url():
    """Redirect to URL from query parameter.

    VULNERABILITY: No validation allows external redirects
    """
    # VULNERABLE: Concatenation doesn't prevent open redirect
    next_url = request.args.get('next', '/')
    # This "validation" can be bypassed with //evil.com
    if not next_url.startswith('/'):
        next_url = '/' + next_url
    return redirect(next_url)


def build_redirect_url(base_url: str, path: str) -> dict:
    """Build redirect URL from base and path.

    VULNERABILITY: urljoin can be abused for open redirect
    """
    # VULNERABLE: urljoin with user-controlled path allows //evil.com
    full_url = urljoin(base_url, path)
    return {"url": full_url}
