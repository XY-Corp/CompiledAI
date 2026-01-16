import os
import json
import logging
from utils.logger import get_logger
from dotenv import load_dotenv

logger: logging.Logger = get_logger("validate")


def get_project_root() -> str:
    """Get the project root directory."""
    # Get the directory of this file (utils/)
    current_file = os.path.abspath(__file__)
    utils_dir = os.path.dirname(current_file)
    # Go up one level to get project root
    project_root = os.path.dirname(utils_dir)
    return project_root


def validate_google_credentials() -> None:
    """Validate that Google Cloud credentials are properly configured."""
    # Load .env from project root
    project_root = get_project_root()
    env_path = os.path.join(project_root, '.env')
    load_dotenv(env_path)
    
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path:
        # If path is relative, resolve it relative to project root
        if not os.path.isabs(creds_path):
            creds_path = os.path.join(project_root, creds_path)
        
        # Normalize the path (resolve any .. or . components)
        creds_path = os.path.normpath(creds_path)
        
        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Google Cloud credentials file not found: {creds_path}"
            )
        if os.path.getsize(creds_path) == 0:
            raise ValueError(f"Google Cloud credentials file is empty: {creds_path}")
        try:
            with open(creds_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"File {creds_path} is not a valid JSON file: {e}")
        
        # Update the environment variable with the absolute path
        # This ensures the BigQuery client can find the file
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
    else:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS environment variable is not set"
        )
    logger.info("🛡️ Google Cloud credentials validated")
