"""
Activities for Flask web application workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-489: Active Debug Code / CWE-215: Information Exposure Through Debug Information
"""
from flask import Flask, request


app = Flask(__name__)


def start_server(host: str = "0.0.0.0", port: int = 5000) -> dict:
    """Start Flask server with debug mode enabled.

    VULNERABILITY: Debug mode exposes sensitive information and allows code execution
    """
    # VULNERABLE: debug=True in production exposes Werkzeug debugger
    # Allows arbitrary code execution via debugger console
    app.run(host=host, port=port, debug=True)
    return {"status": "server_started", "host": host, "port": port}


def create_debug_app() -> dict:
    """Create Flask app with debug configuration.

    VULNERABILITY: Debug settings enabled in configuration
    """
    # VULNERABLE: Debug mode configuration
    app.config['DEBUG'] = True
    app.config['ENV'] = 'development'
    app.config['TESTING'] = True
    return {"app_created": True, "debug_enabled": True}


@app.route('/debug')
def debug_endpoint():
    """Debug endpoint that exposes internal state.

    VULNERABILITY: Exposes internal application state
    """
    # VULNERABLE: Returns debug information
    return {
        "request_headers": dict(request.headers),
        "app_config": dict(app.config),
        "env_vars": dict(app.config)
    }
