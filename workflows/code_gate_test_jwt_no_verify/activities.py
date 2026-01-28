"""
Activities for JWT token handling workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-347: Improper Verification of Cryptographic Signature
"""
import jwt
import json
import base64


def decode_jwt_token(token: str) -> dict:
    """Decode JWT token without verification.

    VULNERABILITY: JWT decoded without signature verification
    """
    # VULNERABLE: verify=False allows forged tokens
    decoded = jwt.decode(token, options={"verify_signature": False})
    return {"payload": decoded}


def parse_jwt_claims(token: str) -> dict:
    """Parse JWT claims by manually decoding base64.

    VULNERABILITY: Manual parsing bypasses signature verification
    """
    # VULNERABLE: Manual decode without any verification
    parts = token.split('.')
    payload = parts[1]
    # Add padding if needed
    payload += '=' * (4 - len(payload) % 4)
    decoded = json.loads(base64.b64decode(payload))
    return {"claims": decoded}
